"""Tests for NormalizedIntent model and from_envelope adapter."""

from __future__ import annotations

import pytest

from sip.core.normalized_intent import NormalizedIntent, from_envelope, NormalizedActor, NormalizedConstraints
from sip.envelope.models import (
    ActorDescriptor,
    ActorType,
    BindingType,
    CapabilityRequirement,
    ContextBlock,
    DataSensitivity,
    DesiredOutcome,
    IntentEnvelope,
    IntentPayload,
    OperationClass,
    ProvenanceBlock,
    ProtocolBinding,
    TargetDescriptor,
    TargetType,
    TrustBlock,
    TrustLevel,
)


def _make_envelope(
    *,
    intent_name: str = "retrieve_document",
    intent_domain: str = "knowledge_management",
    operation_class: OperationClass = OperationClass.RETRIEVE,
    trust_level: TrustLevel = TrustLevel.INTERNAL,
    scopes: list[str] | None = None,
    data_sensitivity: DataSensitivity = DataSensitivity.INTERNAL,
    outcome_summary: str = "Return document contents.",
    provenance: ProvenanceBlock | None = None,
    context_additional: dict | None = None,
    protocol_bindings: list[ProtocolBinding] | None = None,
    capability_requirements: list[CapabilityRequirement] | None = None,
) -> IntentEnvelope:
    return IntentEnvelope(
        actor=ActorDescriptor(
            actor_id="test-actor",
            actor_type=ActorType.SERVICE,
            name="Test Actor",
            trust_level=trust_level,
            scopes=scopes if scopes is not None else ["sip:knowledge:read"],
        ),
        target=TargetDescriptor(target_type=TargetType.CAPABILITY),
        intent=IntentPayload(
            intent_name=intent_name,
            intent_domain=intent_domain,
            operation_class=operation_class,
        ),
        desired_outcome=DesiredOutcome(summary=outcome_summary),
        constraints=sip.envelope.models.Constraints(data_sensitivity=data_sensitivity),
        context=ContextBlock(additional=context_additional or {}),
        provenance=provenance,
        protocol_bindings=protocol_bindings or [],
        capability_requirements=capability_requirements or [],
    )


import sip.envelope.models


class TestNormalizedIntentModel:
    def test_creates_valid_model(self) -> None:
        actor = NormalizedActor(
            actor_id="a1",
            actor_type="service",
            name="A",
            trust_level=TrustLevel.INTERNAL,
        )
        ni = NormalizedIntent(
            intent_id="i1",
            correlation_id="c1",
            actor=actor,
            goal="do something",
            constraints=NormalizedConstraints(),
            data_sensitivity=DataSensitivity.INTERNAL,
            trust_requirements=TrustLevel.INTERNAL,
            raw_request={},
        )
        assert ni.intent_id == "i1"
        assert ni.correlation_id == "c1"

    def test_fails_closed_on_empty_intent_id(self) -> None:
        actor = NormalizedActor(
            actor_id="a1",
            actor_type="service",
            name="A",
            trust_level=TrustLevel.INTERNAL,
        )
        with pytest.raises(Exception):
            NormalizedIntent(
                intent_id="",
                correlation_id="c1",
                actor=actor,
                goal="goal",
                constraints=NormalizedConstraints(),
                data_sensitivity=DataSensitivity.INTERNAL,
                trust_requirements=TrustLevel.INTERNAL,
                raw_request={},
            )

    def test_fails_closed_on_empty_goal(self) -> None:
        actor = NormalizedActor(
            actor_id="a1",
            actor_type="service",
            name="A",
            trust_level=TrustLevel.INTERNAL,
        )
        with pytest.raises(Exception):
            NormalizedIntent(
                intent_id="i1",
                correlation_id="c1",
                actor=actor,
                goal="",
                constraints=NormalizedConstraints(),
                data_sensitivity=DataSensitivity.INTERNAL,
                trust_requirements=TrustLevel.INTERNAL,
                raw_request={},
            )


class TestFromEnvelopeAdapter:
    def test_basic_conversion(self) -> None:
        envelope = _make_envelope()
        ni = from_envelope(envelope)
        assert ni.intent_id == envelope.intent_id
        assert ni.correlation_id == envelope.trace_id
        assert ni.actor.actor_id == envelope.actor.actor_id
        assert ni.goal == envelope.desired_outcome.summary

    def test_actor_trust_level_preserved(self) -> None:
        envelope = _make_envelope(trust_level=TrustLevel.PRIVILEGED)
        ni = from_envelope(envelope)
        assert ni.actor.trust_level == TrustLevel.PRIVILEGED

    def test_scopes_preserved(self) -> None:
        envelope = _make_envelope(scopes=["sip:knowledge:read", "sip:admin"])
        ni = from_envelope(envelope)
        assert "sip:knowledge:read" in ni.actor.scopes
        assert "sip:admin" in ni.actor.scopes

    def test_data_sensitivity_preserved(self) -> None:
        envelope = _make_envelope(data_sensitivity=DataSensitivity.CONFIDENTIAL)
        ni = from_envelope(envelope)
        assert ni.data_sensitivity == DataSensitivity.CONFIDENTIAL
        assert ni.constraints.data_sensitivity == DataSensitivity.CONFIDENTIAL

    def test_goal_from_desired_outcome(self) -> None:
        envelope = _make_envelope(outcome_summary="Return the Q4 report.")
        ni = from_envelope(envelope)
        assert ni.goal == "Return the Q4 report."

    def test_preferred_execution_mode_from_binding(self) -> None:
        envelope = _make_envelope(
            protocol_bindings=[ProtocolBinding(binding_type=BindingType.MCP)]
        )
        ni = from_envelope(envelope)
        assert ni.preferred_execution_mode == "mcp"

    def test_no_preferred_execution_mode_when_no_bindings(self) -> None:
        envelope = _make_envelope(protocol_bindings=[])
        ni = from_envelope(envelope)
        assert ni.preferred_execution_mode is None

    def test_required_capabilities_extracted(self) -> None:
        envelope = _make_envelope(
            capability_requirements=[
                CapabilityRequirement(capability_name="retrieve_document"),
                CapabilityRequirement(capability_name="summarize_text"),
            ]
        )
        ni = from_envelope(envelope)
        assert "retrieve_document" in ni.required_capabilities
        assert "summarize_text" in ni.required_capabilities

    def test_tenant_from_context(self) -> None:
        envelope = _make_envelope(context_additional={"tenant": "acme-corp"})
        ni = from_envelope(envelope)
        assert ni.tenant == "acme-corp"

    def test_jurisdiction_from_context(self) -> None:
        envelope = _make_envelope(context_additional={"jurisdiction": "EU"})
        ni = from_envelope(envelope)
        assert ni.jurisdiction == "EU"

    def test_compliance_list_from_context(self) -> None:
        envelope = _make_envelope(context_additional={"compliance": ["GDPR", "SOC2"]})
        ni = from_envelope(envelope)
        assert "GDPR" in ni.compliance_requirements
        assert "SOC2" in ni.compliance_requirements

    def test_compliance_string_from_context(self) -> None:
        envelope = _make_envelope(context_additional={"compliance": "HIPAA"})
        ni = from_envelope(envelope)
        assert "HIPAA" in ni.compliance_requirements

    def test_raw_request_populated(self) -> None:
        envelope = _make_envelope()
        ni = from_envelope(envelope)
        assert isinstance(ni.raw_request, dict)
        assert "intent_id" in ni.raw_request

    def test_provenance_originator_captured(self) -> None:
        prov = ProvenanceBlock(
            originator="original-agent",
            submitted_by="test-actor",
            delegation_chain=["original-agent"],
        )
        envelope = _make_envelope(provenance=prov)
        ni = from_envelope(envelope)
        assert ni.actor.originator == "original-agent"
        assert "original-agent" in ni.actor.delegation_chain

    def test_no_provenance_originator_is_none(self) -> None:
        envelope = _make_envelope(provenance=None)
        ni = from_envelope(envelope)
        assert ni.actor.originator is None
        assert ni.actor.delegation_chain == []

    def test_schema_version_present(self) -> None:
        envelope = _make_envelope()
        ni = from_envelope(envelope)
        assert ni.schema_version is not None
        assert len(ni.schema_version) > 0

    def test_metadata_contains_intent_info(self) -> None:
        envelope = _make_envelope(intent_name="retrieve_document")
        ni = from_envelope(envelope)
        assert ni.metadata.get("intent_name") == "retrieve_document"

    def test_frozen_model(self) -> None:
        envelope = _make_envelope()
        ni = from_envelope(envelope)
        with pytest.raises(Exception):
            ni.goal = "hacked"  # type: ignore[misc]
