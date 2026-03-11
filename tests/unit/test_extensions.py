"""Unit tests for SIP protocol extension points.

Tests cover:
- extensions preserved on IntentEnvelope, CapabilityDescriptor, NegotiationResult,
  ExecutionPlan, AuditRecord
- invalid extension keys are rejected
- reserved core field names cannot be used as extension keys
- backward compatibility: objects without extensions work as before
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from sip.envelope.models import (
    ActorDescriptor,
    ActorType,
    BindingType,
    DesiredOutcome,
    IntentEnvelope,
    IntentPayload,
    OperationClass,
    TargetDescriptor,
    TargetType,
    TrustLevel,
)
from sip.extensions import RESERVED_CORE_FIELDS, validate_extension_keys
from sip.negotiation.results import NegotiationResult, PolicyDecisionSummary
from sip.observability.audit import AuditRecord, ActionTaken, OutcomeSummary
from sip.registry.models import (
    CapabilityDescriptor,
    ProviderMetadata,
    SchemaReference,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _minimal_envelope(**kw: object) -> IntentEnvelope:
    defaults = dict(
        actor=ActorDescriptor(
            actor_id="test",
            actor_type=ActorType.SERVICE,
            name="Test",
            trust_level=TrustLevel.INTERNAL,
            scopes=["sip:knowledge:read"],
        ),
        target=TargetDescriptor(target_type=TargetType.CAPABILITY),
        intent=IntentPayload(
            intent_name="retrieve_document",
            intent_domain="knowledge_management",
            operation_class=OperationClass.RETRIEVE,
        ),
        desired_outcome=DesiredOutcome(summary="Get doc"),
    )
    defaults.update(kw)
    return IntentEnvelope(**defaults)  # type: ignore[arg-type]


def _minimal_capability(**kw: object) -> CapabilityDescriptor:
    defaults = dict(
        capability_id="retrieve_document",
        name="Retrieve Document",
        description="Retrieves a document",
        provider=ProviderMetadata(provider_id="p1", provider_name="Provider"),
        intent_domains=["knowledge_management"],
        input_schema=SchemaReference(),
        output_schema=SchemaReference(),
        operation_class=OperationClass.RETRIEVE,
        supported_bindings=[BindingType.REST],
    )
    defaults.update(kw)
    return CapabilityDescriptor(**defaults)  # type: ignore[arg-type]


def _minimal_audit(**kw: object) -> AuditRecord:
    defaults = dict(
        trace_id="trace-1",
        intent_id="intent-1",
        actor_id="actor-1",
        actor_type="service",
        intent_name="retrieve_document",
        intent_domain="knowledge_management",
        operation_class="retrieve",
        action_taken=ActionTaken.PLAN_CREATED,
        policy_allowed=True,
        outcome_summary=OutcomeSummary.SUCCESS,
    )
    defaults.update(kw)
    return AuditRecord(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Extension key validation helper
# ---------------------------------------------------------------------------


class TestValidateExtensionKeys:
    def test_valid_x_prefix_key(self) -> None:
        result = validate_extension_keys({"x_my_field": 1})
        assert result == {"x_my_field": 1}

    def test_valid_vendor_dot_key(self) -> None:
        result = validate_extension_keys({"acme.priority": "high"})
        assert result == {"acme.priority": "high"}

    def test_valid_nested_vendor_key(self) -> None:
        result = validate_extension_keys({"org.example.foo": True})
        assert result == {"org.example.foo": True}

    def test_empty_extensions_ok(self) -> None:
        result = validate_extension_keys({})
        assert result == {}

    def test_invalid_plain_key(self) -> None:
        with pytest.raises(ValueError, match="invalid"):
            validate_extension_keys({"my_field": 1})

    def test_invalid_key_starts_with_underscore(self) -> None:
        with pytest.raises(ValueError, match="invalid"):
            validate_extension_keys({"_private": 1})

    def test_reserved_core_field_rejected(self) -> None:
        with pytest.raises(ValueError, match="reserved"):
            validate_extension_keys({"intent_id": "override"})

    def test_multiple_reserved_fields_first_one_caught(self) -> None:
        # Any reserved field should trigger rejection
        with pytest.raises(ValueError):
            validate_extension_keys({"actor": "bad"})

    def test_multiple_valid_keys(self) -> None:
        data = {"x_a": 1, "vendor.b": 2, "org.c.d": 3}
        assert validate_extension_keys(data) == data

    def test_reserved_fields_set_is_comprehensive(self) -> None:
        # Key protocol fields must be in the reserved set
        for name in ("intent_id", "actor", "trace_id", "plan_id", "audit_id"):
            assert name in RESERVED_CORE_FIELDS


# ---------------------------------------------------------------------------
# IntentEnvelope extensions
# ---------------------------------------------------------------------------


class TestIntentEnvelopeExtensions:
    def test_envelope_without_extensions_is_backward_compatible(self) -> None:
        env = _minimal_envelope()
        assert env.extensions == {}

    def test_envelope_with_valid_extensions(self) -> None:
        env = _minimal_envelope(extensions={"x_routing_hint": "region-a"})
        assert env.extensions == {"x_routing_hint": "region-a"}

    def test_envelope_with_vendor_extension(self) -> None:
        env = _minimal_envelope(extensions={"acme.priority": "critical"})
        assert env.extensions["acme.priority"] == "critical"

    def test_envelope_rejects_invalid_extension_key(self) -> None:
        with pytest.raises(ValidationError):
            _minimal_envelope(extensions={"bad_key": 1})

    def test_envelope_rejects_reserved_extension_key(self) -> None:
        with pytest.raises(ValidationError):
            _minimal_envelope(extensions={"intent_id": "override"})

    def test_envelope_extensions_preserved_in_roundtrip(self) -> None:
        original = _minimal_envelope(extensions={"x_tag": "test", "org.foo.bar": 42})
        data = original.model_dump(mode="json")
        restored = IntentEnvelope.model_validate(data)
        assert restored.extensions == {"x_tag": "test", "org.foo.bar": 42}

    def test_unknown_extensions_do_not_affect_processing(self) -> None:
        env = _minimal_envelope(
            extensions={"x_unknown_future_field": {"nested": "data"}}
        )
        # Extensions must not cause the envelope to fail basic attribute access
        assert env.intent.intent_name == "retrieve_document"

    def test_extension_cannot_shadow_core_field(self) -> None:
        with pytest.raises(ValidationError):
            _minimal_envelope(extensions={"actor": "spoofed"})


# ---------------------------------------------------------------------------
# CapabilityDescriptor extensions
# ---------------------------------------------------------------------------


class TestCapabilityDescriptorExtensions:
    def test_capability_without_extensions_is_backward_compatible(self) -> None:
        cap = _minimal_capability()
        assert cap.extensions == {}

    def test_capability_with_valid_x_prefix_extension(self) -> None:
        cap = _minimal_capability(extensions={"x_sla_tier": "gold"})
        assert cap.extensions["x_sla_tier"] == "gold"

    def test_capability_with_vendor_extension(self) -> None:
        cap = _minimal_capability(extensions={"myco.feature_flags": ["beta"]})
        assert cap.extensions["myco.feature_flags"] == ["beta"]

    def test_capability_rejects_invalid_key(self) -> None:
        with pytest.raises(ValidationError):
            _minimal_capability(extensions={"reserved": "value"})

    def test_capability_rejects_reserved_key(self) -> None:
        with pytest.raises(ValidationError):
            _minimal_capability(extensions={"capability_id": "hack"})

    def test_capability_extensions_preserved_in_roundtrip(self) -> None:
        cap = _minimal_capability(extensions={"x_region": "us-east-1"})
        data = cap.model_dump(mode="json")
        restored = CapabilityDescriptor.model_validate(data)
        assert restored.extensions == {"x_region": "us-east-1"}


# ---------------------------------------------------------------------------
# NegotiationResult extensions
# ---------------------------------------------------------------------------


class TestNegotiationResultExtensions:
    def test_negotiation_result_without_extensions(self) -> None:
        result = NegotiationResult(intent_id="i1")
        assert result.extensions == {}

    def test_negotiation_result_with_valid_extension(self) -> None:
        result = NegotiationResult(
            intent_id="i1",
            extensions={"x_match_strategy": "strict"},
        )
        assert result.extensions["x_match_strategy"] == "strict"

    def test_negotiation_result_rejects_invalid_key(self) -> None:
        with pytest.raises(ValidationError):
            NegotiationResult(intent_id="i1", extensions={"BAD_KEY": 1})

    def test_negotiation_result_rejects_reserved_key(self) -> None:
        with pytest.raises(ValidationError):
            NegotiationResult(intent_id="i1", extensions={"ranked_candidates": []})

    def test_negotiation_result_extensions_preserved_in_roundtrip(self) -> None:
        result = NegotiationResult(
            intent_id="i1",
            extensions={"x_confidence": 0.95},
        )
        data = result.model_dump(mode="json")
        restored = NegotiationResult.model_validate(data)
        assert restored.extensions == {"x_confidence": 0.95}


# ---------------------------------------------------------------------------
# AuditRecord extensions
# ---------------------------------------------------------------------------


class TestAuditRecordExtensions:
    def test_audit_record_without_extensions(self) -> None:
        rec = _minimal_audit()
        assert rec.extensions == {}

    def test_audit_record_with_valid_extension(self) -> None:
        rec = _minimal_audit(extensions={"x_compliance_tag": "SOC2"})
        assert rec.extensions["x_compliance_tag"] == "SOC2"

    def test_audit_record_rejects_invalid_key(self) -> None:
        with pytest.raises(ValidationError):
            _minimal_audit(extensions={"invalid key!": 1})

    def test_audit_record_rejects_reserved_key(self) -> None:
        with pytest.raises(ValidationError):
            _minimal_audit(extensions={"intent_id": "override"})

    def test_audit_record_extensions_preserved_in_roundtrip(self) -> None:
        rec = _minimal_audit(extensions={"x_env": "staging"})
        data = rec.model_dump(mode="json")
        restored = AuditRecord.model_validate(data)
        assert restored.extensions == {"x_env": "staging"}
