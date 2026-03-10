"""Unit tests for IntentEnvelope models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from sip.envelope.models import (
    ActorDescriptor,
    ActorType,
    BindingType,
    Constraints,
    ContextBlock,
    DataSensitivity,
    DesiredOutcome,
    DeterminismLevel,
    IntentEnvelope,
    IntentPayload,
    MessageType,
    OperationClass,
    Priority,
    ProtocolBinding,
    TargetDescriptor,
    TargetType,
    TrustBlock,
    TrustLevel,
)


def make_minimal_envelope(**overrides: object) -> IntentEnvelope:
    """Build a minimal valid IntentEnvelope with optional overrides."""
    defaults: dict = {
        "actor": ActorDescriptor(
            actor_id="test-actor",
            actor_type=ActorType.SERVICE,
            name="Test Service",
            trust_level=TrustLevel.INTERNAL,
            scopes=["sip:knowledge:read"],
        ),
        "target": TargetDescriptor(target_type=TargetType.CAPABILITY),
        "intent": IntentPayload(
            intent_name="retrieve_document",
            intent_domain="knowledge_management",
            operation_class=OperationClass.RETRIEVE,
        ),
        "desired_outcome": DesiredOutcome(
            summary="Retrieve the architecture document."
        ),
    }
    defaults.update(overrides)
    return IntentEnvelope(**defaults)  # type: ignore[arg-type]


class TestEnvelopeConstruction:
    def test_minimal_envelope_is_valid(self) -> None:
        envelope = make_minimal_envelope()
        assert envelope.sip_version == "0.1"
        assert envelope.message_type == MessageType.INTENT_REQUEST
        assert envelope.intent_id is not None
        assert envelope.trace_id is not None
        assert envelope.span_id is not None
        assert envelope.timestamp is not None

    def test_intent_id_is_unique(self) -> None:
        e1 = make_minimal_envelope()
        e2 = make_minimal_envelope()
        assert e1.intent_id != e2.intent_id

    def test_envelope_is_frozen(self) -> None:
        envelope = make_minimal_envelope()
        with pytest.raises(ValidationError):
            envelope.sip_version = "9.9"  # type: ignore[misc]

    def test_actor_type_enum(self) -> None:
        envelope = make_minimal_envelope()
        assert envelope.actor.actor_type == ActorType.SERVICE

    def test_operation_class_enum(self) -> None:
        envelope = make_minimal_envelope()
        assert envelope.intent.operation_class == OperationClass.RETRIEVE

    def test_trust_level_enum(self) -> None:
        envelope = make_minimal_envelope()
        assert envelope.actor.trust_level == TrustLevel.INTERNAL

    def test_constraints_defaults(self) -> None:
        envelope = make_minimal_envelope()
        assert envelope.constraints.priority == Priority.NORMAL
        assert envelope.constraints.determinism_required == DeterminismLevel.STRICT
        assert envelope.constraints.data_sensitivity == DataSensitivity.INTERNAL

    def test_constraints_time_budget_must_be_non_negative(self) -> None:
        with pytest.raises(ValidationError):
            Constraints(time_budget_ms=-1)

    def test_constraints_cost_budget_must_be_non_negative(self) -> None:
        with pytest.raises(ValidationError):
            Constraints(cost_budget=-0.01)

    def test_constraints_positive_budget_is_valid(self) -> None:
        c = Constraints(time_budget_ms=5000, cost_budget=10.0)
        assert c.time_budget_ms == 5000
        assert c.cost_budget == 10.0

    def test_protocol_binding_type(self) -> None:
        envelope = make_minimal_envelope(
            protocol_bindings=[
                ProtocolBinding(binding_type=BindingType.REST, endpoint="https://api.example.com")
            ]
        )
        assert envelope.protocol_bindings[0].binding_type == BindingType.REST

    def test_trust_block_delegation_chain(self) -> None:
        trust = TrustBlock(
            declared_trust_level=TrustLevel.PRIVILEGED,
            delegation_chain=["actor-1", "actor-2"],
        )
        assert len(trust.delegation_chain) == 2

    def test_write_operation_class(self) -> None:
        envelope = make_minimal_envelope(
            actor=ActorDescriptor(
                actor_id="test-actor",
                actor_type=ActorType.SERVICE,
                name="Test Service",
                trust_level=TrustLevel.INTERNAL,
            ),
            intent=IntentPayload(
                intent_name="reserve_table",
                intent_domain="booking",
                operation_class=OperationClass.WRITE,
            ),
        )
        assert envelope.intent.operation_class == OperationClass.WRITE

    def test_all_binding_types(self) -> None:
        for bt in BindingType:
            binding = ProtocolBinding(binding_type=bt)
            assert binding.binding_type == bt

    def test_all_operation_classes(self) -> None:
        for oc in OperationClass:
            payload = IntentPayload(
                intent_name="test",
                intent_domain="test",
                operation_class=oc,
            )
            assert payload.operation_class == oc
