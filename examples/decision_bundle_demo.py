#!/usr/bin/env python3
"""Example: End-to-end SIPPipeline flow – intent → policy → plan → audit.

This script demonstrates the canonical SIP pre-execution control plane using
``SIPPipeline``.  It shows the complete flow from a raw ``IntentEnvelope``
through normalization, policy evaluation, deterministic planning, and audit
record generation.

SIP is the *pre-execution* decision layer.  It does NOT:
- Perform capability discovery (candidates are supplied externally)
- Rank providers
- Execute requests

It DOES:
1. Normalize raw intent into a canonical ``NormalizedIntent``
2. Evaluate policy and produce a ``PolicyResult``
3. Produce a deterministic ``ExecutionPlan`` over externally-supplied candidates
4. Generate a mandatory pre-execution ``AuditRecord``
5. Return all four outputs as a ``DecisionBundle``

Usage::

    python examples/decision_bundle_demo.py
"""

from __future__ import annotations

import json

from sip.core.pipeline import SIPPipeline
from sip.envelope.models import (
    ActorDescriptor,
    ActorType,
    BindingType,
    CapabilityRequirement,
    Constraints,
    DataSensitivity,
    DeterminismLevel,
    DesiredOutcome,
    IntentEnvelope,
    IntentPayload,
    OperationClass,
    Priority,
    ProtocolBinding,
    TargetDescriptor,
    TargetType,
    TrustLevel,
)
from sip.observability.audit import AuditRecord
from sip.registry.bootstrap import build_seeded_registry


def _section(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print("=" * 60)


def run_allow_path(audit_log: list[AuditRecord]) -> None:
    """Happy-path: intent is allowed, plan is produced."""

    _section("ALLOW PATH – knowledge retrieval intent")

    # ── 1. Build the IntentEnvelope ──────────────────────────────────────────
    # In production this would arrive from an AI agent or application.
    envelope = IntentEnvelope(
        actor=ActorDescriptor(
            actor_id="demo-agent-001",
            actor_type=ActorType.AI_AGENT,
            name="Demo AI Agent",
            trust_level=TrustLevel.INTERNAL,
            scopes=["sip:knowledge:read"],
        ),
        target=TargetDescriptor(
            target_type=TargetType.CAPABILITY,
            target_id="retrieve_document",
        ),
        intent=IntentPayload(
            intent_name="retrieve_document",
            intent_domain="knowledge_management",
            operation_class=OperationClass.RETRIEVE,
            natural_language_hint="Retrieve the Q3 financial report.",
            parameters={"document_id": "Q3-2024-FINANCE"},
        ),
        desired_outcome=DesiredOutcome(
            summary="Return the Q3 2024 financial report as a structured document.",
            output_format="json",
            success_criteria=["document returned", "non-empty content"],
        ),
        constraints=Constraints(
            time_budget_ms=5000,
            data_sensitivity=DataSensitivity.INTERNAL,
            determinism_required=DeterminismLevel.STRICT,
            priority=Priority.NORMAL,
        ),
        protocol_bindings=[
            ProtocolBinding(binding_type=BindingType.REST),
        ],
        capability_requirements=[
            CapabilityRequirement(
                capability_name="retrieve_document",
                required_scopes=["sip:knowledge:read"],
                preferred_binding=BindingType.REST,
                minimum_trust_tier=TrustLevel.INTERNAL,
            )
        ],
    )

    print(f"\nIntentEnvelope.intent_id  : {envelope.intent_id}")
    print(f"IntentEnvelope.trace_id   : {envelope.trace_id}")
    print(f"Actor                     : {envelope.actor.name} ({envelope.actor.actor_type.value})")
    print(f"Goal                      : {envelope.desired_outcome.summary}")

    # ── 2. Supply candidate capabilities (external discovery) ────────────────
    # In production these would come from ADP or another discovery layer.
    registry = build_seeded_registry()
    candidates = [registry.get_by_id("retrieve_document")]
    print(f"\nExternally supplied candidates : {[c.capability_id for c in candidates]}")

    # ── 3. Run the SIPPipeline ───────────────────────────────────────────────
    pipeline = SIPPipeline(audit_log=audit_log)
    bundle = pipeline.process(envelope, candidates)

    # ── 4. Inspect the DecisionBundle ───────────────────────────────────────
    print(f"\n── NormalizedIntent ──")
    ni = bundle.normalized_intent
    print(f"  intent_id        : {ni.intent_id}")
    print(f"  correlation_id   : {ni.correlation_id}")
    print(f"  schema_version   : {ni.schema_version}")
    print(f"  actor.actor_id   : {ni.actor.actor_id}")
    print(f"  actor.trust_level: {ni.actor.trust_level.value}")
    print(f"  goal             : {ni.goal}")
    print(f"  data_sensitivity : {ni.data_sensitivity.value}")

    print(f"\n── PolicyResult ──")
    pr = bundle.policy_result
    print(f"  allowed          : {pr.allowed}")
    print(f"  reason_code      : {pr.reason_code}")
    print(f"  reason           : {pr.reason}")
    print(f"  conditions       : {pr.conditions}")
    print(f"  required_approvals: {pr.required_approvals}")
    print(f"  allowed_caps     : {[c.capability_id for c in pr.allowed_capabilities]}")

    assert bundle.execution_plan is not None, "Expected an execution plan on the allow path"
    print(f"\n── ExecutionPlan ──")
    ep = bundle.execution_plan
    print(f"  plan_id          : {ep.plan_id}")
    print(f"  intent_id        : {ep.intent_id}")
    print(f"  selected_cap     : {ep.selected_capability.capability_id}")
    print(f"  selected_binding : {ep.selected_binding.value}")
    print(f"  execution_type   : {ep.execution_type.value}")
    print(f"  steps            : {len(ep.execution_steps)}")
    print(f"  preconditions    : {ep.preconditions}")
    print(f"  guard_conditions : {ep.guard_conditions}")
    print(f"  fallback_behavior: {ep.fallback_behavior}")
    print(f"  approval_required: {ep.approval_required}")
    print(f"  selection_basis  : {ep.selection_basis[:80]}…")

    print(f"\n── AuditRecord ──")
    ar = bundle.audit_record
    print(f"  audit_id              : {ar.audit_id}")
    print(f"  policy_allowed        : {ar.policy_allowed}")
    print(f"  action_taken          : {ar.action_taken.value}")
    print(f"  outcome_summary       : {ar.outcome_summary.value}")
    print(f"  pre_execution_denial  : {ar.pre_execution_denial}")
    print(f"  correlation_id        : {ar.correlation_id}")
    print(f"  normalized_intent_id  : {ar.normalized_intent_id}")
    print(f"  selection_basis       : {(ar.selection_basis or '')[:60]}…")
    print(f"  expected_execution_path: {ar.expected_execution_path}")

    print(f"\n✅  ALLOW PATH complete – bundle.allowed = {bundle.allowed}")


def run_deny_path(audit_log: list[AuditRecord]) -> None:
    """Deny path: missing scopes → policy denial, audit record still produced."""

    _section("DENY PATH – missing scopes")

    envelope = IntentEnvelope(
        actor=ActorDescriptor(
            actor_id="untrusted-agent-002",
            actor_type=ActorType.AI_AGENT,
            name="Untrusted Agent",
            trust_level=TrustLevel.INTERNAL,
            scopes=[],  # ← No scopes granted
        ),
        target=TargetDescriptor(
            target_type=TargetType.CAPABILITY,
            target_id="retrieve_document",
        ),
        intent=IntentPayload(
            intent_name="retrieve_document",
            intent_domain="knowledge_management",
            operation_class=OperationClass.RETRIEVE,
            natural_language_hint="Retrieve the confidential document.",
        ),
        desired_outcome=DesiredOutcome(
            summary="Return confidential document.",
        ),
    )

    registry = build_seeded_registry()
    candidates = [registry.get_by_id("retrieve_document")]

    pipeline = SIPPipeline(audit_log=audit_log)
    bundle = pipeline.process(envelope, candidates)

    print(f"\n── PolicyResult (DENY) ──")
    pr = bundle.policy_result
    print(f"  allowed     : {pr.allowed}")
    print(f"  reason_code : {pr.reason_code}")
    print(f"  reason      : {pr.reason}")

    print(f"\n── AuditRecord (pre-execution denial) ──")
    ar = bundle.audit_record
    print(f"  audit_id             : {ar.audit_id}")
    print(f"  policy_allowed       : {ar.policy_allowed}")
    print(f"  action_taken         : {ar.action_taken.value}")
    print(f"  outcome_summary      : {ar.outcome_summary.value}")
    print(f"  pre_execution_denial : {ar.pre_execution_denial}")
    print(f"  policy_reason_code   : {ar.policy_reason_code}")

    assert bundle.denied is True
    assert bundle.execution_plan is None
    assert bundle.audit_record.pre_execution_denial is True

    print(f"\n✅  DENY PATH complete – bundle.denied = {bundle.denied}")


def run_fail_closed_missing_provenance(audit_log: list[AuditRecord]) -> None:
    """Fail-closed: provenance required but missing → denial."""

    _section("FAIL CLOSED – missing provenance (when required)")

    from sip.envelope.models import ContextBlock, TrustBlock

    envelope = IntentEnvelope(
        actor=ActorDescriptor(
            actor_id="agent-no-provenance",
            actor_type=ActorType.AI_AGENT,
            name="Agent Without Provenance",
            trust_level=TrustLevel.INTERNAL,
            scopes=["sip:knowledge:read"],
        ),
        target=TargetDescriptor(
            target_type=TargetType.CAPABILITY,
            target_id="retrieve_document",
        ),
        intent=IntentPayload(
            intent_name="retrieve_document",
            intent_domain="knowledge_management",
            operation_class=OperationClass.RETRIEVE,
        ),
        desired_outcome=DesiredOutcome(
            summary="Retrieve the annual report.",
        ),
        # No ProvenanceBlock attached
    )

    registry = build_seeded_registry()
    candidates = [registry.get_by_id("retrieve_document")]

    # Pipeline with require_provenance=True → must deny if no originator
    pipeline = SIPPipeline(require_provenance=True, audit_log=audit_log)
    bundle = pipeline.process(envelope, candidates)

    print(f"\n  bundle.denied             : {bundle.denied}")
    print(f"  policy_result.reason_code : {bundle.policy_result.reason_code}")
    print(f"  audit.pre_execution_denial: {bundle.audit_record.pre_execution_denial}")

    assert bundle.denied is True
    print(f"\n✅  FAIL CLOSED (missing provenance) complete")


def main() -> None:
    audit_log: list[AuditRecord] = []

    run_allow_path(audit_log)
    run_deny_path(audit_log)
    run_fail_closed_missing_provenance(audit_log)

    _section("AUDIT LOG SUMMARY")
    print(f"\n  Total audit records accumulated : {len(audit_log)}")
    for i, rec in enumerate(audit_log, 1):
        print(
            f"  [{i}] intent_id={rec.intent_id[:8]}… "
            f"allowed={rec.policy_allowed} "
            f"action={rec.action_taken.value} "
            f"outcome={rec.outcome_summary.value} "
            f"pre_denial={rec.pre_execution_denial}"
        )

    print("\n✅  All demo scenarios completed successfully.\n")


if __name__ == "__main__":
    main()
