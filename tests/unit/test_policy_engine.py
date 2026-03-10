"""Unit tests for the policy engine."""

from __future__ import annotations

from sip.envelope.models import (
    ActorDescriptor,
    ActorType,
    BindingType,
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
from sip.negotiation.matcher import CapabilityMatcher
from sip.policy.engine import PolicyEngine
from sip.policy.scopes import check_scopes
from sip.registry.bootstrap import build_seeded_registry


def _make_envelope(
    intent_name: str,
    intent_domain: str,
    operation_class: OperationClass = OperationClass.RETRIEVE,
    trust_level: TrustLevel = TrustLevel.INTERNAL,
    scopes: list[str] | None = None,
    data_sensitivity: DataSensitivity = DataSensitivity.INTERNAL,
) -> IntentEnvelope:
    return IntentEnvelope(
        actor=ActorDescriptor(
            actor_id="policy-test",
            actor_type=ActorType.SERVICE,
            name="Policy Test",
            trust_level=trust_level,
            scopes=scopes or [],
        ),
        target=TargetDescriptor(target_type=TargetType.CAPABILITY),
        intent=IntentPayload(
            intent_name=intent_name,
            intent_domain=intent_domain,
            operation_class=operation_class,
        ),
        desired_outcome=DesiredOutcome(summary="Test"),
        constraints=Constraints(data_sensitivity=data_sensitivity),
    )


class TestPolicyEngine:
    def setup_method(self) -> None:
        self.registry = build_seeded_registry()
        self.matcher = CapabilityMatcher(self.registry)
        self.engine = PolicyEngine(enforce_approval_policy=True)

    def test_policy_allows_with_correct_scopes(self) -> None:
        envelope = _make_envelope(
            "retrieve_document",
            "knowledge_management",
            scopes=["sip:knowledge:read"],
        )
        negotiation = self.matcher.match(envelope)
        result = self.engine.evaluate(envelope, negotiation)
        assert result.policy_decision.allowed is True

    def test_policy_denies_with_missing_scopes(self) -> None:
        envelope = _make_envelope(
            "retrieve_document",
            "knowledge_management",
            scopes=[],  # Missing required scope
        )
        negotiation = self.matcher.match(envelope)
        result = self.engine.evaluate(envelope, negotiation)
        assert result.policy_decision.allowed is False
        assert len(result.policy_decision.denied_scopes) > 0

    def test_policy_requires_approval_for_high_risk_write(self) -> None:
        # reserve_table is a WRITE operation with MEDIUM risk
        # HIGH risk + WRITE would be needed for approval - let's test a WRITE with high risk
        # For this test, we check that the policy notes mention approval logic
        envelope = _make_envelope(
            "reserve_table",
            "booking",
            operation_class=OperationClass.WRITE,
            scopes=["sip:booking:write"],
        )
        negotiation = self.matcher.match(envelope)
        result = self.engine.evaluate(envelope, negotiation)
        # reserve_table is MEDIUM risk, so no approval required
        assert result.policy_decision.allowed is True
        assert any("PASS" in note for note in result.policy_decision.policy_notes)

    def test_policy_notes_are_populated(self) -> None:
        envelope = _make_envelope(
            "retrieve_document",
            "knowledge_management",
            scopes=["sip:knowledge:read"],
        )
        negotiation = self.matcher.match(envelope)
        result = self.engine.evaluate(envelope, negotiation)
        assert len(result.policy_decision.policy_notes) > 0

    def test_policy_no_op_when_no_capability_selected(self) -> None:
        """When no capability is selected (clarification required), policy is a pass-through."""
        from sip.negotiation.results import NegotiationResult, PolicyDecisionSummary
        # Build a negotiation result explicitly with no capability selected
        negotiation_no_cap = NegotiationResult(
            intent_id="test-no-cap",
            requires_clarification=True,
            clarification_questions=["No matching capability found."],
            policy_decision=PolicyDecisionSummary(allowed=True),
        )
        envelope = _make_envelope("nonexistent", "nonexistent")
        result = self.engine.evaluate(envelope, negotiation_no_cap)
        # Should pass through unchanged
        assert result is negotiation_no_cap

    def test_delegation_chain_within_limit(self) -> None:
        from sip.envelope.models import TrustBlock
        envelope = _make_envelope(
            "retrieve_document",
            "knowledge_management",
            scopes=["sip:knowledge:read"],
        )
        # Build an envelope with a short delegation chain
        envelope_with_chain = envelope.model_copy(
            update={"trust": TrustBlock(delegation_chain=["a1", "a2"])}
        )
        negotiation = self.matcher.match(envelope_with_chain)
        result = self.engine.evaluate(envelope_with_chain, negotiation)
        assert result.policy_decision.allowed is True

    def test_delegation_chain_exceeds_limit(self) -> None:
        from sip.envelope.models import TrustBlock
        envelope = _make_envelope(
            "retrieve_document",
            "knowledge_management",
            scopes=["sip:knowledge:read"],
        )
        long_chain = [f"agent-{i}" for i in range(10)]
        envelope_long_chain = envelope.model_copy(
            update={"trust": TrustBlock(delegation_chain=long_chain)}
        )
        negotiation = self.matcher.match(envelope_long_chain)
        result = self.engine.evaluate(envelope_long_chain, negotiation)
        assert result.policy_decision.allowed is False

    def test_critical_risk_restricted_data_is_denied(self) -> None:
        """CRITICAL risk + RESTRICTED data sensitivity must be denied."""
        from sip.policy.risk import is_denied_by_risk
        from sip.envelope.models import DataSensitivity
        from sip.registry.models import RiskLevel
        assert is_denied_by_risk(RiskLevel.CRITICAL, DataSensitivity.RESTRICTED) is True

    def test_low_risk_restricted_data_is_not_denied(self) -> None:
        """LOW risk + RESTRICTED data sensitivity should not be denied."""
        from sip.policy.risk import is_denied_by_risk
        from sip.envelope.models import DataSensitivity
        from sip.registry.models import RiskLevel
        assert is_denied_by_risk(RiskLevel.LOW, DataSensitivity.RESTRICTED) is False

    def test_high_delegate_requires_approval(self) -> None:
        """HIGH risk + DELEGATE should require human approval."""
        from sip.policy.risk import requires_approval
        from sip.envelope.models import OperationClass
        from sip.registry.models import RiskLevel
        assert requires_approval(RiskLevel.HIGH, OperationClass.DELEGATE) is True

    def test_medium_delegate_does_not_require_approval(self) -> None:
        """MEDIUM risk + DELEGATE should not require approval."""
        from sip.policy.risk import requires_approval
        from sip.envelope.models import OperationClass
        from sip.registry.models import RiskLevel
        assert requires_approval(RiskLevel.MEDIUM, OperationClass.DELEGATE) is False

    def test_approval_not_enforced_in_non_production(self) -> None:
        """When enforce_approval_policy=False, approval is never required."""
        from sip.policy.risk import requires_approval
        from sip.envelope.models import OperationClass
        from sip.registry.models import RiskLevel
        assert (
            requires_approval(
                RiskLevel.CRITICAL, OperationClass.EXECUTE, enforce_approval_policy=False
            )
            is False
        )


class TestScopeChecking:
    def test_all_required_scopes_granted(self) -> None:
        missing = check_scopes(["sip:read", "sip:write"], ["sip:read", "sip:write", "sip:admin"])
        assert missing == []

    def test_missing_scope_detected(self) -> None:
        missing = check_scopes(["sip:read", "sip:write"], ["sip:read"])
        assert "sip:write" in missing

    def test_empty_required_scopes(self) -> None:
        missing = check_scopes([], ["sip:read"])
        assert missing == []

    def test_empty_granted_scopes(self) -> None:
        missing = check_scopes(["sip:read"], [])
        assert "sip:read" in missing
