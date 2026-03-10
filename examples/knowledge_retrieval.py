"""Example: Enterprise Knowledge Retrieval.

This example demonstrates how SIP processes an intent to retrieve the latest
approved architecture document and summarize its main design decisions.

Run with:
    python examples/knowledge_retrieval.py
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sip.broker.service import BrokerService
from sip.envelope.models import (
    ActorDescriptor,
    ActorType,
    BindingType,
    DesiredOutcome,
    IntentEnvelope,
    IntentPayload,
    OperationClass,
    ProtocolBinding,
    TargetDescriptor,
    TargetType,
    TrustLevel,
)
from sip.registry.bootstrap import seed_registry
from sip.registry.service import CapabilityRegistryService


def main() -> None:
    # --- Setup: build a seeded registry and broker ---
    registry = CapabilityRegistryService()
    seed_registry(registry)
    broker = BrokerService(registry=registry)

    print("=" * 70)
    print("SIP Example: Enterprise Knowledge Retrieval")
    print("=" * 70)

    # --- Build the intent envelope ---
    envelope = IntentEnvelope(
        actor=ActorDescriptor(
            actor_id="enterprise-portal",
            actor_type=ActorType.SERVICE,
            name="Enterprise Portal",
            trust_level=TrustLevel.INTERNAL,
            scopes=["sip:knowledge:read"],
        ),
        target=TargetDescriptor(target_type=TargetType.CAPABILITY),
        intent=IntentPayload(
            intent_name="retrieve_document",
            intent_domain="knowledge_management",
            operation_class=OperationClass.RETRIEVE,
            natural_language_hint=(
                "Get the latest approved architecture document for private "
                "service exchange and summarize the main design decisions."
            ),
            parameters={
                "query": "latest approved architecture document",
                "collection": "architecture",
                "output_format": "markdown",
            },
        ),
        desired_outcome=DesiredOutcome(
            summary="Retrieve the architecture document and identify design decisions.",
            output_format="markdown",
        ),
        protocol_bindings=[
            ProtocolBinding(binding_type=BindingType.RAG),
            ProtocolBinding(binding_type=BindingType.REST),
        ],
    )

    print("\n[Intent]")
    print(f"  ID:      {envelope.intent_id}")
    print(f"  Name:    {envelope.intent.intent_name}")
    print(f"  Domain:  {envelope.intent.intent_domain}")
    print(f"  Hint:    {envelope.intent.natural_language_hint}")

    # --- Process through the broker ---
    result, translation = broker.translate(envelope)

    print("\n[Negotiation]")
    if result.negotiation_result:
        nr = result.negotiation_result
        if nr.selected_capability:
            print(f"  Selected:  {nr.selected_capability.capability_id}")
            print(f"  Binding:   {nr.selected_binding}")
            print(f"  Rationale: {nr.selection_rationale}")
        print(f"  Candidates: {[c.capability.capability_id for c in nr.ranked_candidates[:3]]}")

    print("\n[Policy]")
    if result.negotiation_result:
        pd = result.negotiation_result.policy_decision
        print(f"  Allowed:          {pd.allowed}")
        print(f"  Requires Approval: {pd.requires_approval}")
        for note in pd.policy_notes:
            print(f"  Note: {note}")

    print("\n[Execution Plan]")
    if result.execution_plan:
        plan = result.execution_plan
        print(f"  Plan ID:    {plan.plan_id}")
        print(f"  Capability: {plan.selected_capability.capability_id}")
        print(f"  Binding:    {plan.selected_binding}")
        print(f"  Approval:   {plan.approval_required}")
        print(f"  Parameters: {json.dumps(plan.grounded_parameters, indent=4)}")

    print(f"\n[Translation ({result.execution_plan.selected_binding if result.execution_plan else 'N/A'})]")
    if translation:
        print(json.dumps(translation.payload, indent=2))

    print("\n[Audit Record]")
    ar = result.audit_record
    print(f"  Outcome:    {ar.outcome_summary}")
    print(f"  Action:     {ar.action_taken}")
    print(f"  Policy:     {'allowed' if ar.policy_allowed else 'denied'}")
    print(f"  Trace ID:   {ar.trace_id}")
    print()


if __name__ == "__main__":
    main()
