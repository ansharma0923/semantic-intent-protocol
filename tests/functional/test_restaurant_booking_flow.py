"""Functional test: restaurant booking flow.

Scenario: A user wants to book a table for two near downtown tomorrow at 7 PM.

Expected behavior:
  - Matches reserve_table capability
  - Uses REST or MCP binding
  - Write action (requires sip:booking:write scope)
  - Policy allows the action (no high-risk approval at MEDIUM risk level)
  - Execution plan is produced with grounded booking parameters
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
from sip.observability.audit import ActionTaken, OutcomeSummary


def make_restaurant_booking_envelope() -> IntentEnvelope:
    """Build the restaurant booking intent envelope."""
    return IntentEnvelope(
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
            },
        ),
        desired_outcome=DesiredOutcome(
            summary="Confirm a restaurant table reservation for two people.",
            success_criteria=[
                "Reservation is confirmed",
                "Confirmation code is returned",
            ],
        ),
        protocol_bindings=[
            ProtocolBinding(binding_type=BindingType.REST),
            ProtocolBinding(binding_type=BindingType.MCP),
        ],
    )


class TestRestaurantBookingFlow:
    def test_flow_produces_success_outcome(self, broker_no_approval: BrokerService) -> None:
        envelope = make_restaurant_booking_envelope()
        result = broker_no_approval.handle(envelope)
        assert result.audit_record.outcome_summary == OutcomeSummary.SUCCESS

    def test_flow_selects_reserve_table_capability(self, broker_no_approval: BrokerService) -> None:
        envelope = make_restaurant_booking_envelope()
        result = broker_no_approval.handle(envelope)
        assert result.audit_record.selected_capability_id == "reserve_table"

    def test_flow_uses_rest_or_mcp_binding(self, broker_no_approval: BrokerService) -> None:
        envelope = make_restaurant_booking_envelope()
        result = broker_no_approval.handle(envelope)
        assert result.audit_record.selected_binding in ("rest", "mcp")

    def test_flow_creates_execution_plan(self, broker_no_approval: BrokerService) -> None:
        envelope = make_restaurant_booking_envelope()
        result = broker_no_approval.handle(envelope)
        assert result.execution_plan is not None

    def test_flow_grounded_parameters_contain_booking_info(
        self, broker_no_approval: BrokerService
    ) -> None:
        envelope = make_restaurant_booking_envelope()
        result = broker_no_approval.handle(envelope)
        assert result.execution_plan is not None
        params = result.execution_plan.grounded_parameters
        assert params.get("customer_name") == "Alex"
        assert params.get("party_size") == 2

    def test_flow_policy_is_allowed(self, broker_no_approval: BrokerService) -> None:
        envelope = make_restaurant_booking_envelope()
        result = broker_no_approval.handle(envelope)
        assert result.audit_record.policy_allowed is True

    def test_flow_denied_without_booking_scope(self, broker: BrokerService) -> None:
        """Without the booking:write scope, the policy should deny the request."""
        envelope_no_scope = IntentEnvelope(
            actor=ActorDescriptor(
                actor_id="user-mobile-app",
                actor_type=ActorType.HUMAN,
                name="Mobile App User",
                trust_level=TrustLevel.INTERNAL,
                scopes=[],  # No booking scope
            ),
            target=TargetDescriptor(target_type=TargetType.CAPABILITY),
            intent=IntentPayload(
                intent_name="reserve_table",
                intent_domain="booking",
                operation_class=OperationClass.WRITE,
            ),
            desired_outcome=DesiredOutcome(summary="Book a table"),
        )
        result = broker.handle(envelope_no_scope)
        assert result.audit_record.policy_allowed is False
        assert result.audit_record.outcome_summary == OutcomeSummary.DENIED

    def test_flow_produces_audit_record_for_write(
        self, broker_no_approval: BrokerService
    ) -> None:
        envelope = make_restaurant_booking_envelope()
        result = broker_no_approval.handle(envelope)
        assert result.audit_record.operation_class == "write"
        assert result.audit_record.actor_id == "user-mobile-app"

    def test_write_operation_execution_step_uses_post(
        self, broker_no_approval: BrokerService
    ) -> None:
        """The REST adapter for a write operation should produce a POST request."""
        from sip.translator.rest_adapter import RestAdapter

        envelope = make_restaurant_booking_envelope()
        result = broker_no_approval.handle(envelope)
        assert result.execution_plan is not None

        if result.execution_plan.selected_binding == BindingType.REST:
            adapter = RestAdapter()
            translation = adapter.translate(result.execution_plan)
            assert translation.payload["method"] == "POST"
