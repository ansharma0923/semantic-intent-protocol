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
    """

    registry: CapabilityRegistryService = field(
        default_factory=CapabilityRegistryService
    )
    policy_engine: PolicyEngine = field(default_factory=PolicyEngine)
    audit_log: list[AuditRecord] = field(default_factory=list)

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

    @property
    def _registry(self) -> CapabilityRegistryService:
        return self.registry

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
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import JSONResponse

    app = FastAPI(
        title="SIP Broker API",
        description="Semantic Intent Protocol – minimal broker HTTP API",
        version="0.1.0",
    )

    # Module-level broker instance for the API
    _broker = BrokerService()

    @app.post("/intents", summary="Submit an intent for processing")
    async def submit_intent(envelope_data: dict[str, Any]) -> JSONResponse:
        """Accept an IntentEnvelope as JSON and process it through the broker."""
        try:
            envelope = IntentEnvelope.model_validate(envelope_data)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        result = _broker.handle(envelope)
        return JSONResponse(
            content={
                "intent_id": result.audit_record.intent_id,
                "outcome": result.audit_record.outcome_summary,
                "action_taken": result.audit_record.action_taken,
                "policy_allowed": result.audit_record.policy_allowed,
                "approval_required": (
                    result.execution_plan.approval_required
                    if result.execution_plan
                    else False
                ),
                "plan_id": (
                    result.execution_plan.plan_id if result.execution_plan else None
                ),
                "requires_clarification": (
                    result.negotiation_result.requires_clarification
                    if result.negotiation_result
                    else True
                ),
            }
        )

    @app.get("/capabilities", summary="List registered capabilities")
    async def list_capabilities() -> JSONResponse:
        """Return all registered capabilities."""
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

    @app.get("/health", summary="Health check")
    async def health() -> JSONResponse:
        return JSONResponse(content={"status": "ok", "capabilities": _broker.registry.count()})

except ImportError:
    # FastAPI is optional — broker still works without it
    pass
