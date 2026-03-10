"""Example: Restaurant Booking.

This example demonstrates how SIP processes a write intent to book a
restaurant table.

Run with:
    python examples/restaurant_booking.py
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
from sip.policy.engine import PolicyEngine
from sip.registry.bootstrap import seed_registry
from sip.registry.service import CapabilityRegistryService


def main() -> None:
    # --- Setup ---
    registry = CapabilityRegistryService()
    seed_registry(registry)
    # Disable approval enforcement for this example
    engine = PolicyEngine(enforce_approval_policy=False)
    broker = BrokerService(registry=registry, policy_engine=engine)

    print("=" * 70)
    print("SIP Example: Restaurant Booking")
    print("=" * 70)

    envelope = IntentEnvelope(
        actor=ActorDescriptor(
            actor_id="user-mobile-app",
            actor_type=ActorType.HUMAN,
            name="Mobile App User",
            trust_level=TrustLevel.INTERNAL,
            scopes=["sip:booking:write"],
        ),
        target=TargetDescriptor(target_type=TargetType.CAPABILITY),
        intent=IntentPayload(
            intent_name="reserve_table",
            intent_domain="booking",
            operation_class=OperationClass.WRITE,
            natural_language_hint=(
                "Book a table for two near downtown tomorrow at 7 PM under the name Alex."
            ),
            parameters={
                "location": "downtown",
                "date": "2024-12-15",
                "time": "19:00",
                "party_size": 2,
                "customer_name": "Alex",
                "special_requests": "window seat if available",
            },
        ),
        desired_outcome=DesiredOutcome(
            summary="Confirm a restaurant table reservation for two people.",
        ),
        protocol_bindings=[
            ProtocolBinding(binding_type=BindingType.REST),
            ProtocolBinding(binding_type=BindingType.MCP),
        ],
    )

    print("\n[Intent]")
    print(f"  Name:   {envelope.intent.intent_name}")
    print(f"  Hint:   {envelope.intent.natural_language_hint}")
    print(f"  Params: {json.dumps(envelope.intent.parameters, indent=4)}")

    result, translation = broker.translate(envelope)

    print("\n[Negotiation]")
    if result.negotiation_result and result.negotiation_result.selected_capability:
        nr = result.negotiation_result
        print(f"  Selected:  {nr.selected_capability.capability_id}")
        print(f"  Binding:   {nr.selected_binding}")
        print(f"  Rationale: {nr.selection_rationale}")

    print("\n[Policy]")
    if result.negotiation_result:
        pd = result.negotiation_result.policy_decision
        print(f"  Allowed:           {pd.allowed}")
        print(f"  Requires Approval: {pd.requires_approval}")
        for note in pd.policy_notes:
            print(f"  Note: {note}")

    print("\n[Execution Plan]")
    if result.execution_plan:
        plan = result.execution_plan
        print(f"  Capability:  {plan.selected_capability.capability_id}")
        print(f"  Binding:     {plan.selected_binding}")
        print(f"  Parameters:  {json.dumps(plan.grounded_parameters, indent=4)}")
        print(f"  Approval:    {plan.approval_required}")

    if translation:
        print(f"\n[Translation ({translation.binding_type.value})]")
        print(json.dumps(translation.payload, indent=2))

    print("\n[Audit Record]")
    ar = result.audit_record
    print(f"  Outcome:  {ar.outcome_summary}")
    print(f"  Action:   {ar.action_taken}")
    print(f"  Policy:   {'allowed' if ar.policy_allowed else 'denied'}")
    print()


if __name__ == "__main__":
    main()
