"""Broker pipeline handlers for SIP.

Contains the core ``process_intent`` function that orchestrates the full
SIP pipeline: validation → negotiation → policy → planning → audit.
"""

from __future__ import annotations

from dataclasses import dataclass

from sip.envelope.models import IntentEnvelope
from sip.envelope.validator import validate_envelope
from sip.negotiation.matcher import CapabilityMatcher
from sip.negotiation.planner import ExecutionPlan, ExecutionPlanner
from sip.negotiation.results import NegotiationResult
from sip.observability.audit import (
    ActionTaken,
    AuditRecord,
    OutcomeSummary,
    create_audit_record,
)
from sip.observability.logger import get_logger
from sip.policy.engine import PolicyEngine
from sip.translator.base import BaseAdapter

logger = get_logger(__name__)


@dataclass
class BrokerResult:
    """Result returned by the broker after processing an intent."""

    audit_record: AuditRecord
    negotiation_result: NegotiationResult | None = None
    execution_plan: ExecutionPlan | None = None
    validation_errors: list[str] | None = None


def process_intent(
    *,
    envelope: IntentEnvelope,
    matcher: CapabilityMatcher,
    planner: ExecutionPlanner,
    policy_engine: PolicyEngine,
    adapters: dict[str, BaseAdapter] | None = None,
) -> BrokerResult:
    """Process a SIP IntentEnvelope through the full pipeline.

    Pipeline steps:
      1. Envelope validation
      2. Capability negotiation (registry matching + ranking)
      3. Policy evaluation
      4. Execution plan creation
      5. Audit record generation

    Args:
        envelope: The intent to process.
        matcher: Capability matcher instance.
        planner: Execution planner instance.
        policy_engine: Policy engine instance.
        adapters: Optional dict of binding → adapter (unused here; translation
            is handled separately).

    Returns:
        A BrokerResult with the outcome of each pipeline stage.
    """
    trace_id = envelope.trace_id
    intent_id = envelope.intent_id
    actor_id = envelope.actor.actor_id
    actor_type = envelope.actor.actor_type.value
    intent_name = envelope.intent.intent_name
    intent_domain = envelope.intent.intent_domain
    operation_class = envelope.intent.operation_class.value

    # Extract provenance metadata for audit records
    prov = envelope.provenance
    originator = prov.originator if prov else None
    submitting_actor = prov.submitted_by if prov else None
    delegation_chain = list(prov.delegation_chain) if prov else []

    logger.info(
        "Processing intent: intent_id=%s actor=%s intent=%s",
        intent_id,
        actor_id,
        intent_name,
    )

    # --- Step 1: Envelope validation ---
    validation = validate_envelope(envelope)
    if not validation.valid:
        logger.warning(
            "Envelope validation failed: intent_id=%s errors=%s",
            intent_id,
            validation.errors,
        )
        audit = create_audit_record(
            trace_id=trace_id,
            intent_id=intent_id,
            actor_id=actor_id,
            actor_type=actor_type,
            intent_name=intent_name,
            intent_domain=intent_domain,
            operation_class=operation_class,
            selected_capability_id=None,
            selected_binding=None,
            action_taken=ActionTaken.VALIDATION_FAILED,
            policy_allowed=False,
            outcome_summary=OutcomeSummary.ERROR,
            notes="; ".join(validation.errors),
            originator=originator,
            submitting_actor=submitting_actor,
            delegation_chain=delegation_chain,
        )
        return BrokerResult(
            audit_record=audit,
            validation_errors=validation.errors,
        )

    if validation.warnings:
        for warning in validation.warnings:
            logger.warning("Envelope warning: intent_id=%s %s", intent_id, warning)

    # --- Step 2: Capability negotiation ---
    negotiation = matcher.match(envelope)

    if negotiation.requires_clarification:
        logger.info(
            "Clarification required: intent_id=%s questions=%s",
            intent_id,
            negotiation.clarification_questions,
        )
        audit = create_audit_record(
            trace_id=trace_id,
            intent_id=intent_id,
            actor_id=actor_id,
            actor_type=actor_type,
            intent_name=intent_name,
            intent_domain=intent_domain,
            operation_class=operation_class,
            selected_capability_id=None,
            selected_binding=None,
            action_taken=ActionTaken.CLARIFICATION_REQUESTED,
            policy_allowed=True,
            outcome_summary=OutcomeSummary.NEEDS_CLARIFICATION,
            notes="; ".join(negotiation.clarification_questions),
            originator=originator,
            submitting_actor=submitting_actor,
            delegation_chain=delegation_chain,
        )
        return BrokerResult(
            audit_record=audit,
            negotiation_result=negotiation,
        )

    # --- Step 3: Policy evaluation ---
    negotiation = policy_engine.evaluate(envelope, negotiation)
    policy = negotiation.policy_decision

    if not policy.allowed:
        logger.warning(
            "Policy denied: intent_id=%s notes=%s",
            intent_id,
            policy.policy_notes,
        )
        audit = create_audit_record(
            trace_id=trace_id,
            intent_id=intent_id,
            actor_id=actor_id,
            actor_type=actor_type,
            intent_name=intent_name,
            intent_domain=intent_domain,
            operation_class=operation_class,
            selected_capability_id=(
                negotiation.selected_capability.capability_id
                if negotiation.selected_capability
                else None
            ),
            selected_binding=(
                negotiation.selected_binding.value
                if negotiation.selected_binding
                else None
            ),
            action_taken=ActionTaken.POLICY_DENIED,
            policy_allowed=False,
            outcome_summary=OutcomeSummary.DENIED,
            notes="; ".join(policy.policy_notes),
            originator=originator,
            submitting_actor=submitting_actor,
            delegation_chain=delegation_chain,
        )
        return BrokerResult(
            audit_record=audit,
            negotiation_result=negotiation,
        )

    # --- Step 4: Execution plan creation ---
    plan: ExecutionPlan | None = None
    try:
        plan = planner.plan(envelope, negotiation)
    except ValueError as exc:
        logger.error("Planning failed: intent_id=%s error=%s", intent_id, exc)
        audit = create_audit_record(
            trace_id=trace_id,
            intent_id=intent_id,
            actor_id=actor_id,
            actor_type=actor_type,
            intent_name=intent_name,
            intent_domain=intent_domain,
            operation_class=operation_class,
            selected_capability_id=None,
            selected_binding=None,
            action_taken=ActionTaken.PLAN_REJECTED,
            policy_allowed=True,
            outcome_summary=OutcomeSummary.ERROR,
            notes=str(exc),
            originator=originator,
            submitting_actor=submitting_actor,
            delegation_chain=delegation_chain,
        )
        return BrokerResult(
            audit_record=audit,
            negotiation_result=negotiation,
        )

    # --- Step 5: Audit record ---
    if policy.requires_approval:
        action = ActionTaken.APPROVAL_REQUESTED
        outcome = OutcomeSummary.PENDING_APPROVAL
        approval_state = "pending"
    else:
        action = ActionTaken.PLAN_CREATED
        outcome = OutcomeSummary.SUCCESS
        approval_state = "not_required"

    audit = create_audit_record(
        trace_id=trace_id,
        intent_id=intent_id,
        actor_id=actor_id,
        actor_type=actor_type,
        intent_name=intent_name,
        intent_domain=intent_domain,
        operation_class=operation_class,
        selected_capability_id=negotiation.selected_capability.capability_id,
        selected_binding=(
            negotiation.selected_binding.value if negotiation.selected_binding else None
        ),
        action_taken=action,
        policy_allowed=True,
        approval_state=approval_state,
        outcome_summary=outcome,
        notes="; ".join(policy.policy_notes),
        originator=originator,
        submitting_actor=submitting_actor,
        delegation_chain=delegation_chain,
    )

    logger.info(
        "Plan created: plan_id=%s capability=%s binding=%s approval=%s",
        plan.plan_id,
        plan.selected_capability.capability_id,
        plan.selected_binding,
        plan.approval_required,
    )

    return BrokerResult(
        audit_record=audit,
        negotiation_result=negotiation,
        execution_plan=plan,
    )
