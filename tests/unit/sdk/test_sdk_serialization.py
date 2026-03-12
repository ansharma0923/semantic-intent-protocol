"""Tests for SDK serialization helpers."""

from __future__ import annotations

import json

import pytest

from sip.sdk import (
    build_actor,
    build_intent_envelope,
    build_provenance,
    parse_intent_envelope,
    to_dict,
    to_json,
)
from sip.sdk.errors import SIPValidationError
from sip.sdk.serialization import (
    parse_capability_descriptor,
    parse_negotiation_result,
)


def _make_envelope() -> object:
    actor = build_actor(
        actor_id="serial-test",
        name="Serialization Test",
        scopes=["sip:knowledge:read"],
    )
    return build_intent_envelope(
        actor=actor,  # type: ignore[arg-type]
        intent_name="retrieve_document",
        intent_domain="knowledge_management",
        operation_class="retrieve",
        outcome_summary="Get the architecture document.",
    )


class TestToDict:
    def test_returns_dict(self) -> None:
        envelope = _make_envelope()
        result = to_dict(envelope)  # type: ignore[arg-type]
        assert isinstance(result, dict)

    def test_contains_required_fields(self) -> None:
        envelope = _make_envelope()
        d = to_dict(envelope)  # type: ignore[arg-type]
        assert "intent_id" in d
        assert "sip_version" in d
        assert "actor" in d
        assert "intent" in d
        assert "desired_outcome" in d

    def test_enum_values_are_strings(self) -> None:
        envelope = _make_envelope()
        d = to_dict(envelope)  # type: ignore[arg-type]
        assert d["actor"]["actor_type"] == "service"
        assert d["intent"]["operation_class"] == "retrieve"

    def test_datetime_is_string(self) -> None:
        envelope = _make_envelope()
        d = to_dict(envelope)  # type: ignore[arg-type]
        # timestamp should be an ISO string, not a datetime object
        assert isinstance(d["timestamp"], str)


class TestToJson:
    def test_returns_string(self) -> None:
        envelope = _make_envelope()
        result = to_json(envelope)  # type: ignore[arg-type]
        assert isinstance(result, str)

    def test_valid_json(self) -> None:
        envelope = _make_envelope()
        j = to_json(envelope)  # type: ignore[arg-type]
        parsed = json.loads(j)
        assert isinstance(parsed, dict)

    def test_indent_produces_pretty_output(self) -> None:
        envelope = _make_envelope()
        pretty = to_json(envelope, indent=2)  # type: ignore[arg-type]
        assert "\n" in pretty


class TestParseIntentEnvelope:
    def test_roundtrip_from_dict(self) -> None:
        envelope = _make_envelope()
        d = to_dict(envelope)  # type: ignore[arg-type]
        restored = parse_intent_envelope(d)
        assert restored.intent_id == envelope.intent_id  # type: ignore[union-attr]
        assert restored.actor.actor_id == envelope.actor.actor_id  # type: ignore[union-attr]

    def test_roundtrip_from_json(self) -> None:
        envelope = _make_envelope()
        j = to_json(envelope)  # type: ignore[arg-type]
        restored = parse_intent_envelope(j)
        assert restored.intent_id == envelope.intent_id  # type: ignore[union-attr]

    def test_invalid_json_raises(self) -> None:
        with pytest.raises(SIPValidationError):
            parse_intent_envelope("{not valid json}")

    def test_invalid_data_raises(self) -> None:
        with pytest.raises(SIPValidationError):
            parse_intent_envelope({"completely": "wrong"})

    def test_provenance_preserved(self) -> None:
        actor = build_actor(
            actor_id="agent-x",
            name="Agent X",
            scopes=["sip:knowledge:read"],
        )
        prov = build_provenance(
            originator="user-1",
            submitted_by="agent-x",
            delegation_chain=["user-1"],
            authority_scope=["sip:knowledge:read"],
        )
        envelope = build_intent_envelope(
            actor=actor,  # type: ignore[arg-type]
            intent_name="x",
            intent_domain="y",
            operation_class="read",
            outcome_summary="ok",
            provenance=prov,
        )
        d = to_dict(envelope)
        restored = parse_intent_envelope(d)
        assert restored.provenance is not None
        assert restored.provenance.originator == "user-1"
        assert restored.provenance.delegation_chain == ["user-1"]
        assert restored.provenance.authority_scope == ["sip:knowledge:read"]

    def test_extensions_preserved(self) -> None:
        actor = build_actor(actor_id="svc", name="Svc")
        envelope = build_intent_envelope(
            actor=actor,  # type: ignore[arg-type]
            intent_name="x",
            intent_domain="y",
            operation_class="read",
            outcome_summary="ok",
            extensions={"x_custom_flag": True},
        )
        d = to_dict(envelope)
        restored = parse_intent_envelope(d)
        assert restored.extensions.get("x_custom_flag") is True


class TestParseCapabilityDescriptor:
    def test_valid_descriptor(self) -> None:
        data = {
            "capability_id": "sip.test.cap",
            "name": "Test Capability",
            "description": "For testing",
            "provider": {
                "provider_id": "test-provider",
                "provider_name": "Test Provider",
            },
            "intent_domains": ["testing"],
            "operation_class": "read",
            "risk_level": "low",
            "supported_bindings": ["rest"],
            "input_schema": {},
            "output_schema": {},
        }
        cap = parse_capability_descriptor(data)
        assert cap.capability_id == "sip.test.cap"
        assert cap.name == "Test Capability"

    def test_invalid_data_raises(self) -> None:
        with pytest.raises(SIPValidationError):
            parse_capability_descriptor({"bad": "data"})


class TestParseNegotiationResult:
    def test_minimal_valid_result(self) -> None:
        data = {
            "intent_id": "test-intent-123",
            "policy_decision": {"allowed": True},
        }
        result = parse_negotiation_result(data)
        assert result.intent_id == "test-intent-123"
        assert result.policy_decision.allowed is True

    def test_invalid_raises(self) -> None:
        with pytest.raises(SIPValidationError):
            parse_negotiation_result("not-json-at-all!!!")
