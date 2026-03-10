"""Functional test: network troubleshooting flow.

Scenario: Diagnose intermittent packet loss on edge router R1 in site SJC01.

Expected behavior:
  - Matches diagnose_network_issue capability
  - Uses REST, gRPC, or MCP binding
  - Read/analyze action (no write)
  - Requires sip:network:read scope
  - No write operation → no approval required
  - Execution plan is produced with device parameters
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
    OperationClass,
    ProtocolBinding,
    TargetDescriptor,
    TargetType,
    TrustLevel,
)
from sip.observability.audit import OutcomeSummary


def make_network_troubleshooting_envelope() -> IntentEnvelope:
    """Build the network troubleshooting intent envelope."""
    return IntentEnvelope(
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
                "Root cause is identified",
                "Recommended actions are provided",
                "Severity is assessed",
            ],
        ),
        protocol_bindings=[
            ProtocolBinding(binding_type=BindingType.GRPC),
            ProtocolBinding(binding_type=BindingType.REST),
            ProtocolBinding(binding_type=BindingType.MCP),
        ],
    )


class TestNetworkTroubleshootingFlow:
    def test_flow_produces_success_outcome(self, broker: BrokerService) -> None:
        envelope = make_network_troubleshooting_envelope()
        result = broker.handle(envelope)
        assert result.audit_record.outcome_summary == OutcomeSummary.SUCCESS

    def test_flow_selects_diagnose_network_issue(self, broker: BrokerService) -> None:
        envelope = make_network_troubleshooting_envelope()
        result = broker.handle(envelope)
        assert result.audit_record.selected_capability_id == "diagnose_network_issue"

    def test_flow_uses_supported_binding(self, broker: BrokerService) -> None:
        envelope = make_network_troubleshooting_envelope()
        result = broker.handle(envelope)
        assert result.audit_record.selected_binding in ("grpc", "rest", "mcp")

    def test_flow_does_not_require_approval(self, broker: BrokerService) -> None:
        """Network analysis is MEDIUM risk + ANALYZE, so no approval needed."""
        envelope = make_network_troubleshooting_envelope()
        result = broker.handle(envelope)
        assert result.execution_plan is not None
        assert result.execution_plan.approval_required is False

    def test_flow_grounded_parameters_have_device_id(self, broker: BrokerService) -> None:
        envelope = make_network_troubleshooting_envelope()
        result = broker.handle(envelope)
        assert result.execution_plan is not None
        assert result.execution_plan.grounded_parameters.get("device_id") == "R1"

    def test_flow_grounded_parameters_have_site(self, broker: BrokerService) -> None:
        envelope = make_network_troubleshooting_envelope()
        result = broker.handle(envelope)
        assert result.execution_plan is not None
        assert result.execution_plan.grounded_parameters.get("site") == "SJC01"

    def test_flow_policy_requires_network_read_scope(self, broker: BrokerService) -> None:
        """Without network:read scope, policy should deny."""
        envelope_no_scope = IntentEnvelope(
            actor=ActorDescriptor(
                actor_id="unauthorized-actor",
                actor_type=ActorType.SERVICE,
                name="Unauthorized",
                trust_level=TrustLevel.INTERNAL,
                scopes=[],
            ),
            target=TargetDescriptor(target_type=TargetType.CAPABILITY),
            intent=IntentPayload(
                intent_name="diagnose_network_issue",
                intent_domain="network_operations",
                operation_class=OperationClass.ANALYZE,
            ),
            desired_outcome=DesiredOutcome(summary="Diagnose"),
        )
        result = broker.handle(envelope_no_scope)
        assert result.audit_record.policy_allowed is False

    def test_flow_grpc_translation_has_correct_structure(self, broker: BrokerService) -> None:
        """When gRPC is selected, the translated payload has required fields."""
        from sip.translator.grpc_adapter import GrpcAdapter

        envelope = make_network_troubleshooting_envelope()
        result, translation = broker.translate(envelope)
        assert result.execution_plan is not None

        if result.execution_plan.selected_binding == BindingType.GRPC:
            assert translation is not None
            assert "service_name" in translation.payload
            assert "method_name" in translation.payload
            assert "request_message" in translation.payload
            # Method name should reflect the capability
            assert "Diagnose" in translation.payload["method_name"]

    def test_flow_produces_audit_record(self, broker: BrokerService) -> None:
        envelope = make_network_troubleshooting_envelope()
        result = broker.handle(envelope)
        assert result.audit_record.actor_id == "noc-automation-system"
        assert result.audit_record.intent_domain == "network_operations"
        assert result.audit_record.operation_class == "analyze"
