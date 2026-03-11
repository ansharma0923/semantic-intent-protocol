"""SIP Broker service.

The broker orchestrates the full SIP processing pipeline:
  1. Validate the envelope
  2. Registry lookup (via negotiation)
  3. Policy evaluation
  4. Execution plan creation
  5. Audit record generation

The broker does NOT execute plans — it hands them to adapters/translators.

This module also exposes a minimal FastAPI application for serving the broker
over HTTP when needed. The FastAPI app is optional and can be omitted.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from sip.broker.handlers import BrokerResult, process_intent
from sip.broker.federation import FederationConfig
from sip.envelope.models import IntentEnvelope
from sip.negotiation.matcher import CapabilityMatcher
from sip.negotiation.planner import ExecutionPlanner
from sip.observability.audit import AuditRecord
from sip.observability.logger import get_logger
from sip.policy.engine import PolicyEngine
from sip.registry.service import CapabilityRegistryService
from sip.translator.a2a_adapter import A2aAdapter
from sip.translator.base import BaseAdapter, TranslationResult
from sip.translator.grpc_adapter import GrpcAdapter
from sip.translator.mcp_adapter import McpAdapter
from sip.translator.rag_adapter import RagAdapter
from sip.translator.rest_adapter import RestAdapter

logger = get_logger(__name__)


@dataclass
class BrokerService:
    """Orchestrates the SIP processing pipeline.

    Wire up components at construction time. The default setup uses an
    in-memory registry and default policy settings. For production use,
    inject your own registry, policy engine, and adapter registry.

    Args:
        registry: Capability registry.  Defaults to in-memory.
        policy_engine: Policy engine.  Defaults to default settings.
        audit_log: List that accumulates audit records.
        federation: Optional federation configuration for multi-broker mode.
    """

    registry: CapabilityRegistryService = field(
        default_factory=CapabilityRegistryService
    )
    policy_engine: PolicyEngine = field(default_factory=PolicyEngine)
    audit_log: list[AuditRecord] = field(default_factory=list)
    federation: FederationConfig | None = field(default=None)

    def __post_init__(self) -> None:
        self._matcher = CapabilityMatcher(self._registry)
        self._planner = ExecutionPlanner()
        self._adapters: dict[str, BaseAdapter] = {
            "rest": RestAdapter(),
            "grpc": GrpcAdapter(),
            "mcp": McpAdapter(),
            "a2a": A2aAdapter(),
            "rag": RagAdapter(),
        }
        # Lazily-constructed discovery service
        self._discovery_svc: Any = None

    @property
    def _registry(self) -> CapabilityRegistryService:
        return self.registry

    @property
    def discovery(self) -> Any:
        """Return the DiscoveryService, creating it lazily."""
        if self._discovery_svc is None:
            from sip.broker.discovery import DiscoveryService
            self._discovery_svc = DiscoveryService(
                registry=self.registry,
                federation=self.federation,
            )
        return self._discovery_svc

    def handle(self, envelope: IntentEnvelope) -> BrokerResult:
        """Process an IntentEnvelope through the full SIP pipeline.

        Args:
            envelope: The intent to process.

        Returns:
            A BrokerResult with the negotiation result, execution plan (if any),
            translation result (if any), and audit record.
        """
        result = process_intent(
            envelope=envelope,
            matcher=self._matcher,
            planner=self._planner,
            policy_engine=self.policy_engine,
            adapters=self._adapters,
        )
        self.audit_log.append(result.audit_record)
        logger.info(
            "Intent processed: intent_id=%s outcome=%s",
            envelope.intent_id,
            result.audit_record.outcome_summary,
        )
        return result

    def translate(
        self, envelope: IntentEnvelope
    ) -> tuple[BrokerResult, TranslationResult | None]:
        """Process an envelope and also translate the plan if one was created.

        Returns:
            Tuple of (BrokerResult, TranslationResult | None).
        """
        result = self.handle(envelope)
        translation: TranslationResult | None = None

        if result.execution_plan is not None:
            binding = result.execution_plan.selected_binding
            adapter = self._adapters.get(binding.value)
            if adapter:
                try:
                    translation = adapter.translate(result.execution_plan)
                except Exception:
                    logger.exception(
                        "Translation failed for plan %s", result.execution_plan.plan_id
                    )
        return result, translation


# ---------------------------------------------------------------------------
# Optional FastAPI application
# ---------------------------------------------------------------------------

try:
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse

    from sip.broker.identity import map_identity_headers
    from sip.observability.audit import OutcomeSummary

    app = FastAPI(
        title="SIP Broker API",
        description=(
            "Semantic Intent Protocol – broker HTTP API (v0.1).\n\n"
            "The HTTP API is one transport surface for SIP; it is not the protocol "
            "definition itself.  All SIP semantics, policy evaluation, provenance "
            "tracking, and audit behaviour are identical regardless of transport."
        ),
        version="0.1.0",
    )

    # Module-level broker instance for the API
    _broker = BrokerService()

    # ------------------------------------------------------------------
    # Health endpoint
    # ------------------------------------------------------------------

    @app.get("/healthz", summary="Health check", tags=["meta"])
    async def healthz() -> JSONResponse:
        """Return a simple liveness response with capability count."""
        return JSONResponse(
            content={
                "status": "ok",
                "version": "0.1.0",
                "capabilities": _broker.registry.count(),
            }
        )

    # ------------------------------------------------------------------
    # Intent submission endpoint
    # ------------------------------------------------------------------

    @app.post(
        "/sip/intents",
        summary="Submit an intent envelope for processing",
        tags=["intents"],
    )
    async def submit_intent(request: Request) -> JSONResponse:
        """Accept an IntentEnvelope as JSON and process it through the broker.

        **Request body:** a JSON-serialised ``IntentEnvelope``.

        **External identity headers (optional, requires trusted deployment):**

        When ``SIP_TRUSTED_IDENTITY_HEADERS=true`` the broker will read the
        following headers and use them to override the actor fields in the
        request body:

        * ``X-Actor-Id``    – actor identifier
        * ``X-Actor-Type``  – actor type (human / ai_agent / service / system)
        * ``X-Actor-Name``  – human-readable actor name
        * ``X-Trust-Level`` – trust level (public / internal / privileged / admin)
        * ``X-Scopes``      – comma-separated list of scopes

        **Response status codes:**

        * ``200`` – successfully processed, plan created
        * ``202`` – processed, but approval required before execution
        * ``400`` – envelope validation failed
        * ``403`` – policy denied
        * ``422`` – malformed request body (cannot parse as IntentEnvelope)
        * ``500`` – unexpected internal error
        """
        # --- Parse body ---
        try:
            body = await request.json()
        except Exception as exc:
            return JSONResponse(
                status_code=422,
                content={"error": "malformed_request", "detail": str(exc)},
            )

        # --- Validate envelope ---
        try:
            envelope = IntentEnvelope.model_validate(body)
        except Exception as exc:
            return JSONResponse(
                status_code=422,
                content={"error": "invalid_envelope", "detail": str(exc)},
            )

        # --- Apply external identity headers (if trusted mapping is enabled) ---
        headers = dict(request.headers)
        updated_actor = map_identity_headers(envelope.actor, headers)
        if updated_actor is not envelope.actor:
            envelope = envelope.model_copy(update={"actor": updated_actor})

        # --- Process through broker pipeline ---
        try:
            result = _broker.handle(envelope)
        except Exception as exc:
            logger.exception("Unexpected error processing intent %s", envelope.intent_id)
            return JSONResponse(
                status_code=500,
                content={"error": "internal_error", "detail": str(exc)},
            )

        # --- Build structured response ---
        audit = result.audit_record
        plan = result.execution_plan

        response_body: dict[str, Any] = {
            "intent_id": audit.intent_id,
            "outcome": audit.outcome_summary,
            "action_taken": audit.action_taken,
            "policy_allowed": audit.policy_allowed,
            "approval_required": plan.approval_required if plan else False,
            "plan_id": plan.plan_id if plan else None,
            "requires_clarification": (
                result.negotiation_result.requires_clarification
                if result.negotiation_result
                else True
            ),
            "policy_notes": (
                result.negotiation_result.policy_decision.policy_notes
                if result.negotiation_result and result.negotiation_result.policy_decision
                else []
            ),
            "audit_record": {
                "trace_id": audit.trace_id,
                "intent_id": audit.intent_id,
                "actor_id": audit.actor_id,
                "actor_type": audit.actor_type,
                "intent_name": audit.intent_name,
                "intent_domain": audit.intent_domain,
                "operation_class": audit.operation_class,
                "selected_capability_id": audit.selected_capability_id,
                "selected_binding": audit.selected_binding,
                "action_taken": audit.action_taken,
                "policy_allowed": audit.policy_allowed,
                "outcome_summary": audit.outcome_summary,
                "notes": audit.notes,
                "timestamp": audit.timestamp.isoformat(),
            },
        }

        # --- Determine HTTP status code ---
        # Status code derivation:
        #   - Validation failures (envelope could not be parsed/validated) → 400
        #   - Policy denials (valid envelope, but authorization denied) → 403
        #   - Approval required → 202
        #   - Clarification needed or other errors without validation failures → 200
        #     (clarification is a normal SIP negotiation outcome, not an error)
        #   - All other success cases → 200
        #
        # Note: validation_errors is checked in multiple branches because an ERROR
        # outcome can result from either envelope validation failure (400) or from
        # a planning or pipeline failure (200/500 depending on context).
        outcome = audit.outcome_summary
        if outcome == OutcomeSummary.DENIED or not audit.policy_allowed:
            # Distinguish envelope validation failure (400) from policy denial (403)
            if result.validation_errors:
                status_code = 400
            else:
                status_code = 403
        elif outcome == OutcomeSummary.PENDING_APPROVAL:
            status_code = 202
        elif outcome in (OutcomeSummary.ERROR, OutcomeSummary.NEEDS_CLARIFICATION):
            # ERROR with validation_errors → bad request; otherwise clarification is normal
            if result.validation_errors:
                status_code = 400
            else:
                status_code = 200  # NEEDS_CLARIFICATION is a normal SIP negotiation outcome
        else:
            status_code = 200

        return JSONResponse(status_code=status_code, content=response_body)

    # ------------------------------------------------------------------
    # Capabilities listing endpoint
    # ------------------------------------------------------------------

    @app.get("/capabilities", summary="List registered capabilities (legacy)", tags=["registry"])
    async def list_capabilities_legacy() -> JSONResponse:
        """Return all registered capabilities (legacy path – prefer /sip/capabilities)."""
        caps = _broker.registry.list_all()
        return JSONResponse(
            content=[
                {
                    "capability_id": c.capability_id,
                    "name": c.name,
                    "operation_class": c.operation_class,
                    "supported_bindings": [b.value for b in c.supported_bindings],
                }
                for c in caps
            ]
        )

    # ------------------------------------------------------------------
    # SIP capability discovery endpoints
    # ------------------------------------------------------------------

    @app.get(
        "/sip/capabilities",
        summary="List all registered capabilities",
        tags=["capabilities"],
    )
    async def sip_list_capabilities() -> JSONResponse:
        """Return the full list of registered capabilities as SIP descriptors."""
        caps = _broker.registry.list_all()
        return JSONResponse(
            content=[c.model_dump(mode="json") for c in caps]
        )

    @app.get(
        "/sip/capabilities/{capability_id}",
        summary="Get a capability by ID",
        tags=["capabilities"],
    )
    async def sip_get_capability(capability_id: str) -> JSONResponse:
        """Return a single capability descriptor by its ID.

        **Response status codes:**

        * ``200`` – capability found
        * ``404`` – capability not found
        """
        cap = _broker.registry.get_by_id(capability_id)
        if cap is None:
            return JSONResponse(
                status_code=404,
                content={
                    "error": "not_found",
                    "detail": f"Capability '{capability_id}' not found.",
                },
            )
        return JSONResponse(content=cap.model_dump(mode="json"))

    @app.post(
        "/sip/capabilities/discover",
        summary="Discover capabilities for a semantic intent query",
        tags=["capabilities"],
    )
    async def sip_discover_capabilities(request: Request) -> JSONResponse:
        """Accept a discovery request and return ranked capability candidates.

        The request body must be a ``DiscoveryRequest`` JSON object with any
        of the following optional fields:

        * ``intent_name``          – machine-readable intent name
        * ``intent_domain``        – functional domain
        * ``operation_class``      – operation class
        * ``preferred_bindings``   – list of preferred binding types
        * ``candidate_capabilities`` – hint: preferred capability IDs
        * ``trust_level``          – trust level of the requesting actor
        * ``max_results``          – maximum number of candidates (default 5)
        * ``include_remote``       – include peer broker results (default true)

        **Response status codes:**

        * ``200`` – success (may have zero candidates)
        * ``400`` – invalid discovery request
        * ``500`` – internal error
        """
        from sip.broker.discovery import DiscoveryRequest

        try:
            body = await request.json()
        except Exception as exc:
            return JSONResponse(
                status_code=400,
                content={"error": "malformed_request", "detail": str(exc)},
            )

        try:
            disc_req = DiscoveryRequest.model_validate(body)
        except Exception as exc:
            return JSONResponse(
                status_code=400,
                content={"error": "invalid_discovery_request", "detail": str(exc)},
            )

        try:
            disc_resp = _broker.discovery.discover(disc_req)
        except Exception as exc:
            logger.exception("Unexpected error during capability discovery")
            return JSONResponse(
                status_code=500,
                content={"error": "internal_error", "detail": str(exc)},
            )

        return JSONResponse(content=disc_resp.model_dump(mode="json"))

    # ------------------------------------------------------------------
    # Legacy health alias (kept for backward compatibility)
    # ------------------------------------------------------------------

    @app.get("/health", summary="Health check (legacy alias)", tags=["meta"])
    async def health() -> JSONResponse:
        """Legacy health alias – prefer /healthz."""
        return JSONResponse(
            content={
                "status": "ok",
                "capabilities": _broker.registry.count(),
            }
        )

except ImportError:
    # FastAPI is optional — broker still works without it
    pass

