"""Tests for SDK builder helpers."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from sip.sdk import (
    ActorType,
    BindingType,
    DataSensitivity,
    DeterminismLevel,
    IntentEnvelope,
    OperationClass,
    TargetType,
    TrustLevel,
    build_actor,
    build_intent_envelope,
    build_protocol_binding,
    build_provenance,
    build_target,
)
from sip.sdk.errors import SIPValidationError


class TestBuildActor:
    def test_minimal_actor(self) -> None:
        actor = build_actor(actor_id="svc-1", name="Service One")
        assert actor.actor_id == "svc-1"
        assert actor.name == "Service One"
        assert actor.actor_type == ActorType.SERVICE
        assert actor.trust_level == TrustLevel.INTERNAL
        assert actor.scopes == []

    def test_actor_with_all_fields(self) -> None:
        actor = build_actor(
            actor_id="agent-1",
            name="Agent One",
            actor_type="ai_agent",
            trust_level="privileged",
            scopes=["sip:knowledge:read", "sip:data:write"],
        )
        assert actor.actor_type == ActorType.AI_AGENT
        assert actor.trust_level == TrustLevel.PRIVILEGED
        assert "sip:knowledge:read" in actor.scopes

    def test_actor_invalid_type_raises(self) -> None:
        with pytest.raises(SIPValidationError):
            build_actor(actor_id="x", name="X", actor_type="not_a_valid_type")

    def test_actor_invalid_trust_level_raises(self) -> None:
        with pytest.raises(SIPValidationError):
            build_actor(actor_id="x", name="X", trust_level="superuser")

    def test_actor_enum_instances_accepted(self) -> None:
        actor = build_actor(
            actor_id="svc",
            name="Svc",
            actor_type=ActorType.HUMAN,
            trust_level=TrustLevel.ADMIN,
        )
        assert actor.actor_type == ActorType.HUMAN
        assert actor.trust_level == TrustLevel.ADMIN


class TestBuildTarget:
    def test_default_target(self) -> None:
        target = build_target()
        assert target.target_type == TargetType.CAPABILITY
        assert target.target_id is None

    def test_target_with_id(self) -> None:
        target = build_target(target_type="agent", target_id="my-agent")
        assert target.target_type == TargetType.AGENT
        assert target.target_id == "my-agent"

    def test_invalid_target_type_raises(self) -> None:
        with pytest.raises(SIPValidationError):
            build_target(target_type="unknown")


class TestBuildProvenance:
    def test_empty_provenance(self) -> None:
        prov = build_provenance()
        assert prov.originator is None
        assert prov.delegation_chain == []

    def test_full_provenance(self) -> None:
        prov = build_provenance(
            originator="user-1",
            submitted_by="agent-1",
            delegation_chain=["user-1", "agent-0"],
            on_behalf_of="user-1",
            delegation_purpose="automated workflow",
            authority_scope=["sip:knowledge:read"],
        )
        assert prov.originator == "user-1"
        assert len(prov.delegation_chain) == 2
        assert prov.authority_scope == ["sip:knowledge:read"]


class TestBuildProtocolBinding:
    def test_rest_binding(self) -> None:
        binding = build_protocol_binding("rest", endpoint="https://api.example.com")
        assert binding.binding_type == BindingType.REST
        assert binding.endpoint == "https://api.example.com"

    def test_binding_with_metadata(self) -> None:
        binding = build_protocol_binding(
            BindingType.MCP,
            metadata={"tool": "search"},
        )
        assert binding.binding_type == BindingType.MCP
        assert binding.metadata["tool"] == "search"

    def test_invalid_binding_type_raises(self) -> None:
        with pytest.raises(SIPValidationError):
            build_protocol_binding("soap")


class TestBuildIntentEnvelope:
    def _make_actor(self) -> object:
        return build_actor(
            actor_id="test-actor",
            name="Test Actor",
            scopes=["sip:knowledge:read"],
        )

    def test_minimal_envelope(self) -> None:
        actor = self._make_actor()
        envelope = build_intent_envelope(
            actor=actor,  # type: ignore[arg-type]
            intent_name="retrieve_document",
            intent_domain="knowledge_management",
            operation_class="retrieve",
            outcome_summary="Get the architecture doc.",
        )
        assert isinstance(envelope, IntentEnvelope)
        assert envelope.intent.intent_name == "retrieve_document"
        assert envelope.intent.intent_domain == "knowledge_management"
        assert envelope.intent.operation_class == OperationClass.RETRIEVE
        assert envelope.desired_outcome.summary == "Get the architecture doc."
        assert envelope.actor.actor_id == "test-actor"

    def test_envelope_is_frozen(self) -> None:
        actor = self._make_actor()
        envelope = build_intent_envelope(
            actor=actor,  # type: ignore[arg-type]
            intent_name="x",
            intent_domain="y",
            operation_class="read",
            outcome_summary="ok",
        )
        with pytest.raises(ValidationError):
            envelope.sip_version = "9.9"  # type: ignore[misc]

    def test_envelope_with_provenance(self) -> None:
        actor = self._make_actor()
        prov = build_provenance(originator="original-user", submitted_by="test-actor")
        envelope = build_intent_envelope(
            actor=actor,  # type: ignore[arg-type]
            intent_name="x",
            intent_domain="y",
            operation_class="read",
            outcome_summary="ok",
            provenance=prov,
        )
        assert envelope.provenance is not None
        assert envelope.provenance.originator == "original-user"

    def test_envelope_with_bindings(self) -> None:
        actor = self._make_actor()
        binding = build_protocol_binding("rest", endpoint="https://api.example.com")
        envelope = build_intent_envelope(
            actor=actor,  # type: ignore[arg-type]
            intent_name="x",
            intent_domain="y",
            operation_class="read",
            outcome_summary="ok",
            protocol_bindings=[binding],
        )
        assert len(envelope.protocol_bindings) == 1
        assert envelope.protocol_bindings[0].binding_type == BindingType.REST

    def test_default_constraints_applied(self) -> None:
        actor = self._make_actor()
        envelope = build_intent_envelope(
            actor=actor,  # type: ignore[arg-type]
            intent_name="x",
            intent_domain="y",
            operation_class="read",
            outcome_summary="ok",
        )
        assert envelope.constraints.determinism_required == DeterminismLevel.STRICT
        assert envelope.constraints.data_sensitivity == DataSensitivity.INTERNAL

    def test_invalid_operation_class_raises(self) -> None:
        actor = self._make_actor()
        with pytest.raises(SIPValidationError):
            build_intent_envelope(
                actor=actor,  # type: ignore[arg-type]
                intent_name="x",
                intent_domain="y",
                operation_class="fly",
                outcome_summary="ok",
            )

    def test_unique_intent_ids(self) -> None:
        actor = self._make_actor()
        e1 = build_intent_envelope(
            actor=actor,  # type: ignore[arg-type]
            intent_name="x",
            intent_domain="y",
            operation_class="read",
            outcome_summary="ok",
        )
        e2 = build_intent_envelope(
            actor=actor,  # type: ignore[arg-type]
            intent_name="x",
            intent_domain="y",
            operation_class="read",
            outcome_summary="ok",
        )
        assert e1.intent_id != e2.intent_id
