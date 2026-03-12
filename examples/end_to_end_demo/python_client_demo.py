"""End-to-end Python client demo for SIP.

Demonstrates the full SIP Python SDK pipeline in a single script:

1. Build an IntentEnvelope (actor, provenance, binding)
2. Submit to an in-process BrokerService (seeded registry, no server required)
3. Print NegotiationResult (ranked candidates, selected capability)
4. Print ExecutionPlan (binding, parameters)
5. Print AuditRecord (outcome, trace, provenance)

Run:
    python examples/end_to_end_demo/python_client_demo.py
"""

from __future__ import annotations

import json

from sip.broker.service import BrokerService
from sip.policy.engine import PolicyEngine
from sip.registry.bootstrap import build_seeded_registry
from sip.sdk import (
    ActorType,
    BindingType,
    OperationClass,
    TrustLevel,
    build_actor,
    build_intent_envelope,
    build_protocol_binding,
    build_provenance,
    validate_envelope,
)


def _separator(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print("=" * 60)


def main() -> None:
    print("=== SIP End-to-End Python Client Demo ===\n")

    # ------------------------------------------------------------------
    # Step 1: Build the actor
    # ------------------------------------------------------------------
    _separator("Step 1: Build the actor")
    actor = build_actor(
        actor_id="demo-agent-001",
        name="Demo AI Agent",
        actor_type=ActorType.AI_AGENT,
        trust_level=TrustLevel.INTERNAL,
        scopes=["sip:knowledge:read"],
    )
    print(f"actor_id:    {actor.actor_id}")
    print(f"actor_type:  {actor.actor_type.value}")
    print(f"trust_level: {actor.trust_level.value}")
    print(f"scopes:      {actor.scopes}")

    # ------------------------------------------------------------------
    # Step 2: Build provenance (delegation chain)
    # ------------------------------------------------------------------
    _separator("Step 2: Build provenance")
    provenance = build_provenance(
        originator="user-alice",
        submitted_by="demo-agent-001",
        delegation_chain=["user-alice"],
        delegation_purpose="Automated knowledge retrieval for report generation",
        authority_scope=["sip:knowledge:read"],
    )
    print(f"originator:       {provenance.originator}")
    print(f"submitted_by:     {provenance.submitted_by}")
    print(f"delegation_chain: {provenance.delegation_chain}")
    print(f"authority_scope:  {provenance.authority_scope}")

    # ------------------------------------------------------------------
    # Step 3: Build the IntentEnvelope
    # ------------------------------------------------------------------
    _separator("Step 3: Build and validate IntentEnvelope")
    binding = build_protocol_binding(
        binding_type=BindingType.RAG,
        endpoint="https://knowledge-api.example.com",
    )
    envelope = build_intent_envelope(
        actor=actor,
        intent_name="retrieve_document",
        intent_domain="knowledge_management",
        operation_class=OperationClass.RETRIEVE,
        outcome_summary="Retrieve the SIP architecture document for report generation.",
        target_id="sip.knowledge.retrieve",
        intent_parameters={
            "document_id": "arch-doc-001",
            "query": "SIP protocol architecture",
        },
        natural_language_hint="Get me the architecture document",
        provenance=provenance,
        protocol_bindings=[binding],
    )
    print(f"intent_id:   {envelope.intent_id}")
    print(f"trace_id:    {envelope.trace_id}")
    print(f"intent_name: {envelope.intent.intent_name}")
    print(f"domain:      {envelope.intent.intent_domain}")

    validation = validate_envelope(envelope)
    print(f"valid:       {validation.valid}")
    if not validation.valid:
        print(f"errors:      {validation.errors}")
        return

    # ------------------------------------------------------------------
    # Step 4: Submit to the in-process broker
    # ------------------------------------------------------------------
    _separator("Step 4: Submit to SIP broker")
    broker = BrokerService(
        registry=build_seeded_registry(),
        policy_engine=PolicyEngine(enforce_approval_policy=False),
    )
    result = broker.handle(envelope)
    print("Broker processed the intent.")

    # ------------------------------------------------------------------
    # Step 5: Print NegotiationResult
    # ------------------------------------------------------------------
    _separator("Step 5: NegotiationResult")
    neg = result.negotiation_result
    print(f"total_candidates:   {len(neg.ranked_candidates)}")
    for rank, candidate in enumerate(neg.ranked_candidates, start=1):
        print(
            f"  #{rank}  {candidate.capability.capability_id}  "
            f"score={candidate.score:.2f}  "
            f"risk={candidate.capability.risk_level.value}"
        )
    if neg.selected_capability:
        print(f"\nselected_capability: {neg.selected_capability.capability_id}")
        print(f"selected_name:       {neg.selected_capability.name}")

    # ------------------------------------------------------------------
    # Step 6: Print ExecutionPlan
    # ------------------------------------------------------------------
    _separator("Step 6: ExecutionPlan")
    plan = result.execution_plan
    print(f"plan_id:          {plan.plan_id}")
    print(f"selected_binding: {plan.selected_binding}")
    print(f"approval_required:{plan.approval_required}")
    print(f"steps:            {len(plan.execution_steps)}")
    for step in plan.execution_steps:
        print(f"  step_index: {step.step_index}")
        print(f"  step_name:  {step.step_name}")
        print(f"  binding:    {step.binding.value}")
        print(f"  params:     {json.dumps(step.parameters, indent=4)}")

    # ------------------------------------------------------------------
    # Step 7: Print AuditRecord
    # ------------------------------------------------------------------
    _separator("Step 7: AuditRecord")
    audit = result.audit_record
    print(f"trace_id:              {audit.trace_id}")
    print(f"intent_id:             {audit.intent_id}")
    print(f"actor_id:              {audit.actor_id}")
    print(f"outcome:               {audit.outcome_summary}")
    print(f"policy_allowed:        {audit.policy_allowed}")
    print(f"selected_capability:   {audit.selected_capability_id}")
    print(f"selected_binding:      {audit.selected_binding}")
    print(f"action_taken:          {audit.action_taken}")
    print(f"timestamp:             {audit.timestamp}")

    # ------------------------------------------------------------------
    # Step 8: Print provenance details from audit record
    # ------------------------------------------------------------------
    _separator("Step 8: Provenance details (from AuditRecord)")
    print(f"originator:       {audit.originator}")
    print(f"submitting_actor: {audit.submitting_actor}")
    print(f"delegation_chain: {audit.delegation_chain}")

    print("\n=== Demo complete. ===")


if __name__ == "__main__":
    main()
