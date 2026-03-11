"""Functional test: multi-agent collaboration flow.

Scenario: Collect telemetry from network diagnostics agent, then ask a
summarization agent to produce a customer-friendly report.

Expected behavior:
  - First step: collect_device_telemetry or diagnose_network_issue via A2A or gRPC
  - Second step: summarize_for_customer via REST, MCP, or A2A
  - Both intents produce execution plans
  - The second intent's trace is linked to the first
  - Orchestration is fully deterministic (SIP pipeline performs no LLM inference)
"""

from __future__ import annotations

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
from sip.observability.audit import OutcomeSummary


def make_telemetry_collection_envelope(trace_id: str) -> IntentEnvelope:
    """Build the telemetry collection intent envelope."""
    return IntentEnvelope(
        trace_id=trace_id,
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
            natural_language_hint=(
                "Ask the network diagnostics agent to collect telemetry from R1."
            ),
            parameters={
                "device_id": "R1",
                "metrics": ["packet_loss", "cpu_utilization", "interface_errors"],
                "time_window_seconds": 300,
            },
        ),
        desired_outcome=DesiredOutcome(
            summary="Collect telemetry data from device R1.",
            success_criteria=["Telemetry data is returned"],
        ),
        protocol_bindings=[
            ProtocolBinding(binding_type=BindingType.A2A),
            ProtocolBinding(binding_type=BindingType.GRPC),
        ],
        negotiation=NegotiationHints(
            candidate_capabilities=["collect_device_telemetry"],
            allow_fallback=True,
        ),
    )


def make_customer_summary_envelope(
    trace_id: str,
    telemetry_content: str = "packet_loss=5%, cpu=80%, interface_errors=12",
) -> IntentEnvelope:
    """Build the customer summarization intent envelope."""
    return IntentEnvelope(
        trace_id=trace_id,
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
                "Ask the summarization agent to produce a customer-friendly report "
                "based on the telemetry data."
            ),
            parameters={
                "content": telemetry_content,
                "context": "Network telemetry for device R1, site SJC01",
                "tone": "friendly",
            },
        ),
        desired_outcome=DesiredOutcome(
            summary="Produce a customer-friendly summary of the network telemetry.",
            output_format="markdown",
            success_criteria=["Customer-friendly summary is produced"],
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


class TestMultiAgentCollaborationFlow:
    def test_telemetry_step_produces_success(self, broker: BrokerService) -> None:
        envelope = make_telemetry_collection_envelope(trace_id="shared-trace-001")
        result = broker.handle(envelope)
        assert result.audit_record.outcome_summary == OutcomeSummary.SUCCESS

    def test_telemetry_step_selects_correct_capability(self, broker: BrokerService) -> None:
        envelope = make_telemetry_collection_envelope(trace_id="shared-trace-001")
        result = broker.handle(envelope)
        assert result.audit_record.selected_capability_id == "collect_device_telemetry"

    def test_summary_step_produces_success(self, broker: BrokerService) -> None:
        trace_id = "shared-trace-002"
        envelope = make_customer_summary_envelope(trace_id=trace_id)
        result = broker.handle(envelope)
        assert result.audit_record.outcome_summary == OutcomeSummary.SUCCESS

    def test_summary_step_selects_correct_capability(self, broker: BrokerService) -> None:
        envelope = make_customer_summary_envelope(trace_id="shared-trace-003")
        result = broker.handle(envelope)
        assert result.audit_record.selected_capability_id == "summarize_for_customer"

    def test_both_steps_share_trace_id(self, broker: BrokerService) -> None:
        shared_trace = "multi-agent-trace-001"
        step1 = make_telemetry_collection_envelope(trace_id=shared_trace)
        step2 = make_customer_summary_envelope(trace_id=shared_trace)
        result1 = broker.handle(step1)
        result2 = broker.handle(step2)
        assert result1.audit_record.trace_id == shared_trace
        assert result2.audit_record.trace_id == shared_trace

    def test_both_plans_are_deterministic(self, broker: BrokerService) -> None:
        """Running the same envelopes twice should produce equivalent plans."""
        trace_id = "determinism-test"
        step1 = make_telemetry_collection_envelope(trace_id=trace_id)
        result1a = broker.handle(step1)
        result1b = broker.handle(step1)
        # Both runs select the same capability and binding
        assert (
            result1a.audit_record.selected_capability_id
            == result1b.audit_record.selected_capability_id
        )
        assert (
            result1a.audit_record.selected_binding == result1b.audit_record.selected_binding
        )

    def test_telemetry_step_no_approval_required(self, broker: BrokerService) -> None:
        envelope = make_telemetry_collection_envelope(trace_id="t")
        result = broker.handle(envelope)
        assert result.execution_plan is not None
        assert result.execution_plan.approval_required is False

    def test_summary_step_no_approval_required(self, broker: BrokerService) -> None:
        envelope = make_customer_summary_envelope(trace_id="t")
        result = broker.handle(envelope)
        assert result.execution_plan is not None
        assert result.execution_plan.approval_required is False

    def test_full_multi_step_pipeline(self, broker: BrokerService) -> None:
        """Simulate a two-step orchestration and verify both steps succeed."""
        shared_trace = "full-pipeline-test"

        # Step 1: Collect telemetry
        step1_envelope = make_telemetry_collection_envelope(trace_id=shared_trace)
        step1_result = broker.handle(step1_envelope)
        assert step1_result.execution_plan is not None
        assert step1_result.audit_record.outcome_summary == OutcomeSummary.SUCCESS

        # Simulate extracting telemetry output (in reality, the executor would do this)
        telemetry_output = (
            f"device_id=R1, packet_loss=5.2%, cpu=78%, "
            f"errors=14 (from capability: "
            f"{step1_result.audit_record.selected_capability_id})"
        )

        # Step 2: Summarize for customer
        step2_envelope = make_customer_summary_envelope(
            trace_id=shared_trace,
            telemetry_content=telemetry_output,
        )
        step2_result = broker.handle(step2_envelope)
        assert step2_result.execution_plan is not None
        assert step2_result.audit_record.outcome_summary == OutcomeSummary.SUCCESS

        # Verify audit log captured both steps
        audit_traces = [r.trace_id for r in broker.audit_log]
        assert audit_traces.count(shared_trace) >= 2

    def test_a2a_translation_for_telemetry(self, broker: BrokerService) -> None:
        """When A2A is selected, the translation has correct structure."""
        envelope = make_telemetry_collection_envelope(trace_id="a2a-test")
        result, translation = broker.translate(envelope)
        assert result.execution_plan is not None

        if result.execution_plan.selected_binding == BindingType.A2A:
            assert translation is not None
            assert "agent_task_type" in translation.payload
            assert "target_agent" in translation.payload
            assert "task_payload" in translation.payload
