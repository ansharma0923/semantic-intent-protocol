"""Example: Multi-Agent Collaboration.

This example demonstrates how SIP orchestrates a two-step workflow:
  1. Collect telemetry from the network diagnostics agent
  2. Ask the summarization agent to produce a customer-friendly report

Run with:
    python examples/multi_agent_collaboration.py
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
    NegotiationHints,
    OperationClass,
    ProtocolBinding,
    TargetDescriptor,
    TargetType,
    TrustLevel,
)
from sip.observability.tracing import new_trace_id
from sip.registry.bootstrap import seed_registry
from sip.registry.service import CapabilityRegistryService


def main() -> None:
    # --- Setup ---
    registry = CapabilityRegistryService()
    seed_registry(registry)
    broker = BrokerService(registry=registry)

    # All steps in this multi-agent workflow share the same trace ID
    shared_trace_id = new_trace_id()

    print("=" * 70)
    print("SIP Example: Multi-Agent Collaboration")
    print(f"Shared Trace ID: {shared_trace_id}")
    print("=" * 70)

    # -----------------------------------------------------------------------
    # Step 1: Collect telemetry from the network diagnostics agent
    # -----------------------------------------------------------------------
    print("\n--- Step 1: Collect Device Telemetry ---")

    step1_envelope = IntentEnvelope(
        trace_id=shared_trace_id,
        actor=ActorDescriptor(
            actor_id="orchestrator-agent",
            actor_type=ActorType.AI_AGENT,
            name="Orchestrator Agent",
            trust_level=TrustLevel.INTERNAL,
            scopes=["sip:network:read"],
        ),
        target=TargetDescriptor(
            target_type=TargetType.AGENT,
            target_id="network_ops",
            namespace="network_operations",
        ),
        intent=IntentPayload(
            intent_name="collect_device_telemetry",
            intent_domain="network_operations",
            operation_class=OperationClass.READ,
            natural_language_hint="Collect telemetry from device R1.",
            parameters={
                "device_id": "R1",
                "metrics": ["packet_loss", "cpu_utilization", "interface_errors"],
                "time_window_seconds": 300,
            },
        ),
        desired_outcome=DesiredOutcome(summary="Collect telemetry from R1"),
        protocol_bindings=[
            ProtocolBinding(binding_type=BindingType.A2A),
            ProtocolBinding(binding_type=BindingType.GRPC),
        ],
        negotiation=NegotiationHints(
            candidate_capabilities=["collect_device_telemetry"],
            allow_fallback=True,
        ),
    )

    result1, translation1 = broker.translate(step1_envelope)

    print(f"  Capability: {result1.audit_record.selected_capability_id}")
    print(f"  Binding:    {result1.audit_record.selected_binding}")
    print(f"  Outcome:    {result1.audit_record.outcome_summary}")

    if translation1:
        print(f"  Translation ({translation1.binding_type.value}):")
        print("  " + json.dumps(translation1.payload, indent=4).replace("\n", "\n  "))

    # Simulate the output of the telemetry collection (in a real system this
    # would be returned by the actual executor)
    simulated_telemetry = (
        "device_id=R1, site=SJC01, collected_at=2024-12-15T19:00:00Z, "
        "packet_loss=5.2%, cpu_utilization=78%, interface_errors=14, "
        "rx_bytes=1024000, tx_bytes=982000"
    )
    print(f"\n  [Simulated Telemetry Output]: {simulated_telemetry}")

    # -----------------------------------------------------------------------
    # Step 2: Summarize the telemetry for the customer
    # -----------------------------------------------------------------------
    print("\n--- Step 2: Summarize for Customer ---")

    step2_envelope = IntentEnvelope(
        trace_id=shared_trace_id,
        actor=ActorDescriptor(
            actor_id="orchestrator-agent",
            actor_type=ActorType.AI_AGENT,
            name="Orchestrator Agent",
            trust_level=TrustLevel.INTERNAL,
            scopes=["sip:knowledge:read"],
        ),
        target=TargetDescriptor(
            target_type=TargetType.AGENT,
            target_id="ai_summarizer",
            namespace="summarization",
        ),
        intent=IntentPayload(
            intent_name="summarize_for_customer",
            intent_domain="summarization",
            operation_class=OperationClass.ANALYZE,
            natural_language_hint=(
                "Produce a customer-friendly report based on the telemetry data."
            ),
            parameters={
                "content": simulated_telemetry,
                "context": "Network performance report for device R1, site SJC01",
                "tone": "friendly",
            },
        ),
        desired_outcome=DesiredOutcome(
            summary="Customer-friendly summary of network performance.",
            output_format="markdown",
        ),
        protocol_bindings=[
            ProtocolBinding(binding_type=BindingType.A2A),
            ProtocolBinding(binding_type=BindingType.REST),
            ProtocolBinding(binding_type=BindingType.MCP),
        ],
        negotiation=NegotiationHints(
            candidate_capabilities=["summarize_for_customer"],
            allow_fallback=True,
        ),
    )

    result2, translation2 = broker.translate(step2_envelope)

    print(f"  Capability: {result2.audit_record.selected_capability_id}")
    print(f"  Binding:    {result2.audit_record.selected_binding}")
    print(f"  Outcome:    {result2.audit_record.outcome_summary}")

    if translation2:
        print(f"  Translation ({translation2.binding_type.value}):")
        print("  " + json.dumps(translation2.payload, indent=4, default=str).replace("\n", "\n  "))

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    print("\n--- Workflow Summary ---")
    print(f"  Shared Trace ID:   {shared_trace_id}")
    print(f"  Step 1 Capability: {result1.audit_record.selected_capability_id}")
    print(f"  Step 2 Capability: {result2.audit_record.selected_capability_id}")
    print(f"  Audit Log Entries: {len(broker.audit_log)}")
    print(f"  SIP Pipeline Deterministic: True")
    print(
        "  Note: SIP execution planning is deterministic. "
        "AI or LLM systems may generate intents outside the protocol layer."
    )
    print()


if __name__ == "__main__":
    main()
