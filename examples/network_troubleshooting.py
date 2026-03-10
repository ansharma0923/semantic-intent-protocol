"""Example: Network Troubleshooting.

This example demonstrates how SIP processes an analysis intent to diagnose
intermittent packet loss on a network device.

Run with:
    python examples/network_troubleshooting.py
"""

from __future__ import annotations

import json
import sys
import os

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
    # --- Setup ---
    registry = CapabilityRegistryService()
    seed_registry(registry)
    broker = BrokerService(registry=registry)

    print("=" * 70)
    print("SIP Example: Network Troubleshooting")
    print("=" * 70)

    envelope = IntentEnvelope(
        actor=ActorDescriptor(
            actor_id="noc-automation-system",
            actor_type=ActorType.SYSTEM,
            name="NOC Automation System",
            trust_level=TrustLevel.INTERNAL,
            scopes=["sip:network:read"],
        ),
        target=TargetDescriptor(
            target_type=TargetType.CAPABILITY,
            namespace="network_operations",
        ),
        intent=IntentPayload(
            intent_name="diagnose_network_issue",
            intent_domain="network_operations",
            operation_class=OperationClass.ANALYZE,
            natural_language_hint=(
                "Diagnose intermittent packet loss on edge router R1 in site SJC01."
            ),
            parameters={
                "device_id": "R1",
                "site": "SJC01",
                "symptom": "intermittent packet loss",
                "diagnostic_depth": "deep",
            },
        ),
        desired_outcome=DesiredOutcome(
            summary="Identify root cause of packet loss on R1 and recommend actions.",
            success_criteria=[
                "Root cause identified",
                "Severity assessed",
                "Recommended actions provided",
            ],
        ),
        protocol_bindings=[
            ProtocolBinding(binding_type=BindingType.GRPC),
            ProtocolBinding(binding_type=BindingType.REST),
            ProtocolBinding(binding_type=BindingType.MCP),
        ],
    )

    print(f"\n[Intent]")
    print(f"  Name:   {envelope.intent.intent_name}")
    print(f"  Hint:   {envelope.intent.natural_language_hint}")
    print(f"  Params: {json.dumps(envelope.intent.parameters, indent=4)}")

    result, translation = broker.translate(envelope)

    print(f"\n[Negotiation]")
    if result.negotiation_result and result.negotiation_result.selected_capability:
        nr = result.negotiation_result
        print(f"  Selected:   {nr.selected_capability.capability_id}")
        print(f"  Binding:    {nr.selected_binding}")
        print(f"  Candidates: {[c.capability.capability_id for c in nr.ranked_candidates[:3]]}")

    print(f"\n[Policy]")
    if result.negotiation_result:
        pd = result.negotiation_result.policy_decision
        print(f"  Allowed:           {pd.allowed}")
        print(f"  Requires Approval: {pd.requires_approval}")
        for note in pd.policy_notes:
            print(f"  Note: {note}")

    print(f"\n[Execution Plan]")
    if result.execution_plan:
        plan = result.execution_plan
        print(f"  Plan ID:    {plan.plan_id}")
        print(f"  Capability: {plan.selected_capability.capability_id}")
        print(f"  Binding:    {plan.selected_binding}")
        print(f"  Parameters: {json.dumps(plan.grounded_parameters, indent=4)}")

    if translation:
        print(f"\n[Translation ({translation.binding_type.value})]")
        print(json.dumps(translation.payload, indent=2, default=str))

    print(f"\n[Audit Record]")
    ar = result.audit_record
    print(f"  Outcome:  {ar.outcome_summary}")
    print(f"  Action:   {ar.action_taken}")
    print(f"  Policy:   {'allowed' if ar.policy_allowed else 'denied'}")
    print()


if __name__ == "__main__":
    main()
