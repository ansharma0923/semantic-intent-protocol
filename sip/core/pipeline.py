"""SIP Pipeline – canonical pre-execution control plane.

``SIPPipeline`` orchestrates the full SIP processing pipeline from an
``IntentEnvelope`` (and optional externally-supplied candidate capabilities)
to a ``DecisionBundle``.

Pipeline stages
---------------
1. **Intent ingestion** – accept ``IntentEnvelope`` + external candidates.
2. **Intent normalization** – convert envelope to ``NormalizedIntent``.
3. **Intent validation** – validate the envelope via existing validator.
4. **Policy evaluation** – run ``CanonicalPolicyEngine`` on the normalized
   intent and the supplied candidates.
5. **Deterministic planning** – run ``DeterministicPlanner`` to produce an
   ``ExecutionPlan``.
6. **Audit record generation** – always create an ``AuditRecord`` capturing
   the full pre-execution state.
7. **Decision bundle output** – return a ``DecisionBundle``.

SIP does NOT execute; it does NOT discover capabilities; it does NOT perform
ranking.  All of these are responsibilities of the caller.

Usage::

    pipeline = SIPPipeline()
    bundle = pipeline.process(envelope, candidate_capabilities=[...])
    if bundle.allowed:
        # Hand bundle.execution_plan to the execution layer
        ...
    else:
        # Inspect bundle.policy_result and bundle.audit_record
        ...

Architecture note
-----------------
``SIPPipeline`` is an additive companion to the legacy ``BrokerService`` and
``process_intent`` pipeline.  Existing callers that use ``BrokerService`` or
``process_intent`` are completely unaffected.  The canonical pipeline uses
``NormalizedIntent`` internally and produces richer ``DecisionBundle`` output.
"""

from __future__ import annotations

import logging
from typing import Any

from sip.core.decision_bundle import DecisionBundle
from sip.core.deterministic_planner import DeterministicPlanner
from sip.core.fail_closed import FailClosedError
from sip.core.normalized_intent import NormalizedIntent, from_envelope
from sip.core.policy_engine import CanonicalPolicyEngine
from sip.envelope.models import IntentEnvelope
from sip.envelope.validator import validate_envelope
from sip.negotiation.planner import ExecutionPlan
from sip.observability.audit import (
    ActionTaken,
    AuditRecord,
    OutcomeSummary,
    create_audit_record,
)
from sip.policy.interface import PolicyEngineInterface, PolicyResult, ReasonCode
from sip.registry.models import CapabilityDescriptor

logger = logging.getLogger(__name__)


class SIPPipeline:
    """Canonical SIP pre-execution control plane pipeline.

    Args:
        policy_engine: Policy engine to use.  Defaults to
            ``CanonicalPolicyEngine`` with production settings.
        planner: Deterministic planner.  Defaults to ``DeterministicPlanner``.
        require_provenance: When True, deny any intent that has no declared
            originator.  Defaults to False.
        audit_log: Optional list to accumulate audit records.
    """

    def __init__(
        self,
        *,
        policy_engine: PolicyEngineInterface | None = None,
        planner: DeterministicPlanner | None = None,
        require_provenance: bool = False,
        audit_log: list[AuditRecord] | None = None,
    ) -> None:
        self._policy_engine: PolicyEngineInterface = policy_engine or CanonicalPolicyEngine(
            require_provenance=require_provenance,
        )
        self._planner = planner or DeterministicPlanner()
        self._audit_log: list[AuditRecord] = audit_log if audit_log is not None else []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process(
        self,
        envelope: IntentEnvelope,
        candidate_capabilities: list[CapabilityDescriptor] | None = None,
    ) -> DecisionBundle:
        """Process an ``IntentEnvelope`` through the full SIP pipeline.

        Args:
            envelope: The intent to process.
            candidate_capabilities: Externally-supplied candidate capabilities.
                SIP does not perform discovery; these must be provided by the
                caller (e.g. from an external ADP discovery layer).

        Returns:
            A ``DecisionBundle`` with the normalized intent, policy decision,
            execution plan (if allowed), and audit record.
        """
        candidates = candidate_capabilities or []
        logger.info(
            "SIPPipeline.process: intent_id=%s actor=%s candidates=%d",
            envelope.intent_id,
            envelope.actor.actor_id,
            len(candidates),
        )

        # Stage 1 + 2: Ingestion + Normalization
        try:
            normalized = from_envelope(envelope)
        except (ValueError, Exception) as exc:
            logger.error(
                "Normalization failed: intent_id=%s error=%s",
                envelope.intent_id,
                exc,
            )
            policy_result = PolicyResult.deny(
                reason_code=ReasonCode.EVALUATION_ERROR,
                reason=f"Intent normalization failed: {exc}",
            )
            audit = self._build_denial_audit(
                envelope=envelope,
                normalized=None,
                policy_result=policy_result,
                action=ActionTaken.VALIDATION_FAILED,
                notes=str(exc),
            )
            self._audit_log.append(audit)
            return DecisionBundle(
                normalized_intent=_stub_normalized(envelope),
                policy_result=policy_result,
                audit_record=audit,
                denied=True,
            )

        # Stage 3: Envelope validation (structural + protocol rules)
        validation = validate_envelope(envelope)
        if not validation.valid:
            logger.warning(
                "Validation failed: intent_id=%s errors=%s",
                envelope.intent_id,
                validation.errors,
            )
            policy_result = PolicyResult.deny(
                reason_code=ReasonCode.EVALUATION_ERROR,
                reason="Envelope validation failed: " + "; ".join(validation.errors),
                evaluation_notes=validation.errors,
            )
            audit = self._build_denial_audit(
                envelope=envelope,
                normalized=normalized,
                policy_result=policy_result,
                action=ActionTaken.VALIDATION_FAILED,
                notes="; ".join(validation.errors),
            )
            self._audit_log.append(audit)
            return DecisionBundle(
                normalized_intent=normalized,
                policy_result=policy_result,
                audit_record=audit,
                denied=True,
            )

        # Stage 4: Policy evaluation
        policy_result = self._policy_engine.evaluate(normalized, candidates)

        if not policy_result.allowed:
            logger.warning(
                "Policy denied: intent_id=%s reason=%s",
                envelope.intent_id,
                policy_result.reason_code,
            )
            audit = self._build_denial_audit(
                envelope=envelope,
                normalized=normalized,
                policy_result=policy_result,
                action=ActionTaken.POLICY_DENIED,
                notes="; ".join(policy_result.evaluation_notes[-5:]),  # last 5 notes
            )
            self._audit_log.append(audit)
            return DecisionBundle(
                normalized_intent=normalized,
                policy_result=policy_result,
                audit_record=audit,
                denied=True,
            )

        # Stage 5: Deterministic planning
        plan: ExecutionPlan | None = None
        try:
            plan = self._planner.plan(normalized, policy_result, candidates)
        except FailClosedError as exc:
            logger.error(
                "Planning failed (fail-closed): intent_id=%s reason=%s",
                envelope.intent_id,
                exc.denial.reason_code,
            )
            fail_policy = PolicyResult.deny(
                reason_code=exc.denial.reason_code,
                reason=exc.denial.reason,
                evaluation_notes=[exc.denial.reason],
            )
            audit = self._build_denial_audit(
                envelope=envelope,
                normalized=normalized,
                policy_result=fail_policy,
                action=ActionTaken.PLAN_REJECTED,
                notes=exc.denial.reason,
            )
            self._audit_log.append(audit)
            return DecisionBundle(
                normalized_intent=normalized,
                policy_result=fail_policy,
                audit_record=audit,
                denied=True,
            )

        # Stage 6: Audit record generation
        approval_required = plan.approval_required
        if approval_required:
            action = ActionTaken.APPROVAL_REQUESTED
            outcome = OutcomeSummary.PENDING_APPROVAL
            approval_state = "pending"
        else:
            action = ActionTaken.PLAN_CREATED
            outcome = OutcomeSummary.SUCCESS
            approval_state = "not_required"

        prov = envelope.provenance
        expected_path = [s.step_name for s in plan.execution_steps]

        audit = create_audit_record(
            trace_id=envelope.trace_id,
            intent_id=envelope.intent_id,
            actor_id=envelope.actor.actor_id,
            actor_type=envelope.actor.actor_type.value,
            intent_name=envelope.intent.intent_name,
            intent_domain=envelope.intent.intent_domain,
            operation_class=envelope.intent.operation_class.value,
            selected_capability_id=plan.selected_capability.capability_id,
            selected_binding=plan.selected_binding.value,
            action_taken=action,
            policy_allowed=True,
            approval_state=approval_state,
            outcome_summary=outcome,
            notes="; ".join(policy_result.evaluation_notes[-3:]),
            originator=prov.originator if prov else None,
            submitting_actor=prov.submitted_by if prov else None,
            delegation_chain=list(prov.delegation_chain) if prov else [],
            correlation_id=normalized.correlation_id,
            normalized_intent_id=normalized.intent_id,
            policy_reason_code=policy_result.reason_code,
            selection_basis=plan.selection_basis,
            expected_execution_path=expected_path,
            pre_execution_denial=False,
        )
        self._audit_log.append(audit)

        logger.info(
            "SIPPipeline.process: plan_id=%s capability=%s binding=%s",
            plan.plan_id,
            plan.selected_capability.capability_id,
            plan.selected_binding.value,
        )

        return DecisionBundle(
            normalized_intent=normalized,
            policy_result=policy_result,
            execution_plan=plan,
            audit_record=audit,
            denied=False,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_denial_audit(
        self,
        *,
        envelope: IntentEnvelope,
        normalized: NormalizedIntent | None,
        policy_result: PolicyResult,
        action: ActionTaken,
        notes: str,
    ) -> AuditRecord:
        prov = envelope.provenance
        return create_audit_record(
            trace_id=envelope.trace_id,
            intent_id=envelope.intent_id,
            actor_id=envelope.actor.actor_id,
            actor_type=envelope.actor.actor_type.value,
            intent_name=envelope.intent.intent_name,
            intent_domain=envelope.intent.intent_domain,
            operation_class=envelope.intent.operation_class.value,
            selected_capability_id=None,
            selected_binding=None,
            action_taken=action,
            policy_allowed=False,
            outcome_summary=OutcomeSummary.DENIED,
            notes=notes,
            originator=prov.originator if prov else None,
            submitting_actor=prov.submitted_by if prov else None,
            delegation_chain=list(prov.delegation_chain) if prov else [],
            correlation_id=normalized.correlation_id if normalized else envelope.trace_id,
            normalized_intent_id=normalized.intent_id if normalized else envelope.intent_id,
            policy_reason_code=policy_result.reason_code,
            pre_execution_denial=True,
        )


def _stub_normalized(envelope: IntentEnvelope) -> NormalizedIntent:
    """Build a minimal NormalizedIntent stub for error cases.

    Used when normalization itself fails so that a ``DecisionBundle`` can
    still be returned with a non-None ``normalized_intent``.
    """
    from sip.core.normalized_intent import NormalizedActor, NormalizedConstraints

    return NormalizedIntent(
        intent_id=envelope.intent_id,
        correlation_id=envelope.trace_id,
        actor=NormalizedActor(
            actor_id=envelope.actor.actor_id,
            actor_type=envelope.actor.actor_type.value,
            name=envelope.actor.name,
            trust_level=envelope.actor.trust_level,
        ),
        goal=envelope.desired_outcome.summary or "<unknown>",
        constraints=NormalizedConstraints(),
        data_sensitivity=envelope.constraints.data_sensitivity,
        trust_requirements=envelope.trust.declared_trust_level,
        raw_request={},
    )
