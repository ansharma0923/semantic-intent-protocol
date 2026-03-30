"""Tests for PolicyEngineInterface, PolicyResult, and CanonicalPolicyEngine."""

from __future__ import annotations

import pytest

from sip.core.normalized_intent import NormalizedActor, NormalizedConstraints, NormalizedIntent, from_envelope
from sip.core.policy_engine import CanonicalPolicyEngine
from sip.envelope.models import (
    ActorDescriptor,
    ActorType,
    DataSensitivity,
    DesiredOutcome,
    IntentEnvelope,
    IntentPayload,
    OperationClass,
    TargetDescriptor,
    TargetType,
    TrustLevel,
    Constraints,
)
from sip.policy.interface import PolicyEngineInterface, PolicyResult, ReasonCode
from sip.registry.bootstrap import build_seeded_registry
from sip.registry.models import CapabilityDescriptor, RiskLevel


def _make_normalized_intent(
    *,
    actor_id: str = "test-actor",
    trust_level: TrustLevel = TrustLevel.INTERNAL,
    scopes: list[str] | None = None,
    data_sensitivity: DataSensitivity = DataSensitivity.INTERNAL,
    originator: str | None = None,
    delegation_chain: list[str] | None = None,
    goal: str = "Test goal.",
) -> NormalizedIntent:
    actor = NormalizedActor(
        actor_id=actor_id,
        actor_type="service",
        name="Test Actor",
        trust_level=trust_level,
        scopes=scopes if scopes is not None else ["sip:knowledge:read"],
        originator=originator,
        delegation_chain=delegation_chain or [],
    )
    return NormalizedIntent(
        intent_id="test-intent-1",
        correlation_id="test-trace-1",
        actor=actor,
        goal=goal,
        constraints=NormalizedConstraints(data_sensitivity=data_sensitivity),
        data_sensitivity=data_sensitivity,
        trust_requirements=trust_level,
        raw_request={},
    )


def _get_capability(registry, capability_id: str) -> CapabilityDescriptor:
    return registry.get(capability_id)


class TestPolicyResult:
    def test_deny_factory(self) -> None:
        result = PolicyResult.deny(
            reason_code=ReasonCode.MISSING_SCOPES,
            reason="Missing required scopes.",
        )
        assert result.allowed is False
        assert result.reason_code == ReasonCode.MISSING_SCOPES
        assert result.allowed_capabilities == []

    def test_allow_factory(self) -> None:
        result = PolicyResult.allow(allowed_capabilities=[])
        assert result.allowed is True
        assert result.reason_code == ReasonCode.ALLOWED

    def test_allow_with_conditions(self) -> None:
        result = PolicyResult.allow(
            allowed_capabilities=[],
            conditions=["human approval required"],
            required_approvals=["approver-1"],
        )
        assert result.conditions == ["human approval required"]
        assert "approver-1" in result.required_approvals


class TestPolicyEngineInterface:
    def test_canonical_engine_implements_interface(self) -> None:
        engine = CanonicalPolicyEngine()
        assert isinstance(engine, PolicyEngineInterface)


class TestCanonicalPolicyEngine:
    def setup_method(self) -> None:
        self.registry = build_seeded_registry()
        self.engine = CanonicalPolicyEngine(enforce_approval_policy=True)

    def _get_caps(self, *ids: str) -> list[CapabilityDescriptor]:
        return [self.registry.get_by_id(cid) for cid in ids if self.registry.get_by_id(cid)]

    # --- Allow path ---

    def test_allow_with_correct_scopes(self) -> None:
        intent = _make_normalized_intent(scopes=["sip:knowledge:read"])
        caps = self._get_caps("retrieve_document")
        result = self.engine.evaluate(intent, caps)
        assert result.allowed is True
        assert len(result.allowed_capabilities) == 1

    def test_allowed_capabilities_filtered_correctly(self) -> None:
        """Only capabilities that pass all checks are included."""
        intent = _make_normalized_intent(scopes=["sip:knowledge:read"])
        caps = self._get_caps("retrieve_document")
        result = self.engine.evaluate(intent, caps)
        cap_ids = [c.capability_id for c in result.allowed_capabilities]
        assert "retrieve_document" in cap_ids

    def test_allow_multiple_candidates(self) -> None:
        intent = _make_normalized_intent(
            scopes=["sip:knowledge:read", "sip:booking:write"]
        )
        caps = self._get_caps("retrieve_document", "reserve_table")
        result = self.engine.evaluate(intent, caps)
        assert result.allowed is True
        # At least one capability allowed
        assert len(result.allowed_capabilities) >= 1

    # --- Deny path ---

    def test_deny_missing_scopes(self) -> None:
        intent = _make_normalized_intent(scopes=[])
        caps = self._get_caps("retrieve_document")
        result = self.engine.evaluate(intent, caps)
        assert result.allowed is False
        assert result.reason_code == ReasonCode.NO_ALLOWED_CAPABILITIES

    def test_deny_no_candidates(self) -> None:
        intent = _make_normalized_intent(scopes=["sip:knowledge:read"])
        result = self.engine.evaluate(intent, [])
        assert result.allowed is False
        assert result.reason_code == ReasonCode.NO_ALLOWED_CAPABILITIES

    def test_deny_trust_level_too_low(self) -> None:
        """Capability requires PRIVILEGED but actor has INTERNAL."""
        from sip.registry.models import CapabilityDescriptor, ProviderMetadata, SchemaReference, CapabilityConstraints, ExecutionMetadata
        from sip.envelope.models import BindingType, OperationClass, TrustLevel
        cap = CapabilityDescriptor(
            capability_id="privileged_op",
            name="Privileged Op",
            description="Requires high trust.",
            provider=ProviderMetadata(provider_id="p1", provider_name="P1"),
            intent_domains=["test"],
            input_schema=SchemaReference(),
            output_schema=SchemaReference(),
            operation_class=OperationClass.EXECUTE,
            risk_level=RiskLevel.HIGH,
            minimum_trust_tier=TrustLevel.PRIVILEGED,
            supported_bindings=[BindingType.REST],
        )
        intent = _make_normalized_intent(
            trust_level=TrustLevel.INTERNAL,
            scopes=[],
        )
        result = self.engine.evaluate(intent, [cap])
        assert result.allowed is False

    def test_deny_critical_risk_restricted_data(self) -> None:
        from sip.registry.models import CapabilityDescriptor, ProviderMetadata, SchemaReference
        from sip.envelope.models import BindingType, OperationClass, TrustLevel
        cap = CapabilityDescriptor(
            capability_id="critical_cap",
            name="Critical Cap",
            description="Critical risk.",
            provider=ProviderMetadata(provider_id="p1", provider_name="P1"),
            intent_domains=["test"],
            input_schema=SchemaReference(),
            output_schema=SchemaReference(),
            operation_class=OperationClass.EXECUTE,
            risk_level=RiskLevel.CRITICAL,
            minimum_trust_tier=TrustLevel.INTERNAL,
            supported_bindings=[BindingType.REST],
        )
        intent = _make_normalized_intent(
            data_sensitivity=DataSensitivity.RESTRICTED,
            scopes=[],
        )
        result = self.engine.evaluate(intent, [cap])
        assert result.allowed is False

    # --- Fail-closed scenarios ---

    def test_fail_closed_missing_trust_level(self) -> None:
        """Missing trust_level (via model_construct bypass) → denial."""
        # Pydantic enums prevent None directly, so use model_construct to simulate
        # an internal state where trust_level is missing (e.g. deserialization edge case).
        intent = NormalizedIntent.model_construct(
            intent_id="i1",
            correlation_id="c1",
            actor=NormalizedActor.model_construct(
                actor_id="a1",
                actor_type="service",
                name="A",
                trust_level=None,
                scopes=[],
                delegation_chain=[],
            ),
            goal="goal",
            constraints=NormalizedConstraints(),
            data_sensitivity=DataSensitivity.INTERNAL,
            trust_requirements=TrustLevel.INTERNAL,
            raw_request={},
            schema_version="0.2",
            required_capabilities=[],
            compliance_requirements=[],
            jurisdiction=None,
            preferred_execution_mode=None,
            tenant=None,
            risk_level=None,
            metadata={},
        )
        caps = self._get_caps("retrieve_document")
        result = self.engine.evaluate(intent, caps)
        assert result.allowed is False
        assert result.reason_code == ReasonCode.MISSING_TRUST_LEVEL

    def test_fail_closed_missing_provenance_when_required(self) -> None:
        engine = CanonicalPolicyEngine(require_provenance=True)
        intent = _make_normalized_intent(originator=None)
        caps = self._get_caps("retrieve_document")
        result = engine.evaluate(intent, caps)
        assert result.allowed is False
        assert result.reason_code == ReasonCode.MISSING_PROVENANCE

    def test_pass_with_provenance_when_required(self) -> None:
        engine = CanonicalPolicyEngine(require_provenance=True)
        intent = _make_normalized_intent(
            originator="orig-agent",
            scopes=["sip:knowledge:read"],
        )
        caps = self._get_caps("retrieve_document")
        result = engine.evaluate(intent, caps)
        assert result.allowed is True

    def test_fail_closed_delegation_chain_too_long(self) -> None:
        intent = _make_normalized_intent(
            delegation_chain=[f"agent-{i}" for i in range(10)],
            scopes=["sip:knowledge:read"],
        )
        caps = self._get_caps("retrieve_document")
        result = self.engine.evaluate(intent, caps)
        assert result.allowed is False
        assert result.reason_code == ReasonCode.DELEGATION_CHAIN_TOO_LONG

    def test_approval_required_for_high_risk_write(self) -> None:
        from sip.registry.models import CapabilityDescriptor, ProviderMetadata, SchemaReference, CapabilityConstraints
        from sip.envelope.models import BindingType, OperationClass
        cap = CapabilityDescriptor(
            capability_id="high_risk_write",
            name="High Risk Write",
            description="High risk write op.",
            provider=ProviderMetadata(provider_id="p1", provider_name="P1"),
            intent_domains=["test"],
            input_schema=SchemaReference(),
            output_schema=SchemaReference(),
            operation_class=OperationClass.WRITE,
            risk_level=RiskLevel.HIGH,
            minimum_trust_tier=TrustLevel.INTERNAL,
            supported_bindings=[BindingType.REST],
        )
        intent = _make_normalized_intent(scopes=[])
        result = self.engine.evaluate(intent, [cap])
        # No scopes required → allowed but approval required
        assert result.allowed is True
        assert len(result.required_approvals) > 0

    def test_evaluation_notes_populated(self) -> None:
        intent = _make_normalized_intent(scopes=["sip:knowledge:read"])
        caps = self._get_caps("retrieve_document")
        result = self.engine.evaluate(intent, caps)
        assert len(result.evaluation_notes) > 0

    def test_fail_closed_on_evaluation_error(self) -> None:
        """If evaluation throws, the engine must return a denial."""
        class BrokenEngine(CanonicalPolicyEngine):
            def _evaluate_internal(self, intent, candidates):
                raise RuntimeError("simulated error")

        engine = BrokenEngine()
        intent = _make_normalized_intent()
        result = engine.evaluate(intent, [])
        assert result.allowed is False
        assert result.reason_code == ReasonCode.EVALUATION_ERROR
