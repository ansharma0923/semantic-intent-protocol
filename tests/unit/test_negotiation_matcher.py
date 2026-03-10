"""Unit tests for the capability matcher (negotiation)."""

from __future__ import annotations

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
from sip.negotiation.matcher import CapabilityMatcher
from sip.registry.bootstrap import build_seeded_registry


def _make_envelope(
    intent_name: str,
    intent_domain: str,
    operation_class: OperationClass = OperationClass.RETRIEVE,
    trust_level: TrustLevel = TrustLevel.INTERNAL,
    preferred_binding: BindingType | None = None,
    scopes: list[str] | None = None,
    candidate_capabilities: list[str] | None = None,
    allow_fallback: bool = True,
) -> IntentEnvelope:
    bindings = [ProtocolBinding(binding_type=preferred_binding)] if preferred_binding else []
    return IntentEnvelope(
        actor=ActorDescriptor(
            actor_id="matcher-test",
            actor_type=ActorType.SERVICE,
            name="Matcher Test",
            trust_level=trust_level,
            scopes=scopes or ["sip:knowledge:read"],
        ),
        target=TargetDescriptor(target_type=TargetType.CAPABILITY),
        intent=IntentPayload(
            intent_name=intent_name,
            intent_domain=intent_domain,
            operation_class=operation_class,
        ),
        desired_outcome=DesiredOutcome(summary="Test"),
        protocol_bindings=bindings,
        negotiation=NegotiationHints(
            candidate_capabilities=candidate_capabilities or [],
            allow_fallback=allow_fallback,
        ),
    )


class TestCapabilityMatcher:
    def setup_method(self) -> None:
        self.registry = build_seeded_registry()
        self.matcher = CapabilityMatcher(self.registry)

    def test_exact_intent_name_match(self) -> None:
        envelope = _make_envelope("retrieve_document", "knowledge_management")
        result = self.matcher.match(envelope)
        assert result.selected_capability is not None
        assert result.selected_capability.capability_id == "retrieve_document"

    def test_no_match_triggers_clarification(self) -> None:
        envelope = _make_envelope("nonexistent_intent", "nonexistent_domain")
        result = self.matcher.match(envelope)
        assert result.requires_clarification is True
        assert len(result.clarification_questions) > 0

    def test_ranked_candidates_sorted_by_score(self) -> None:
        envelope = _make_envelope("retrieve_document", "knowledge_management")
        result = self.matcher.match(envelope)
        assert len(result.ranked_candidates) > 0
        scores = [c.score for c in result.ranked_candidates]
        assert scores == sorted(scores, reverse=True)

    def test_preferred_binding_rest(self) -> None:
        envelope = _make_envelope(
            "retrieve_document",
            "knowledge_management",
            preferred_binding=BindingType.REST,
        )
        result = self.matcher.match(envelope)
        assert result.selected_binding == BindingType.REST

    def test_preferred_binding_rag(self) -> None:
        envelope = _make_envelope(
            "retrieve_document",
            "knowledge_management",
            preferred_binding=BindingType.RAG,
        )
        result = self.matcher.match(envelope)
        assert result.selected_binding == BindingType.RAG

    def test_allowed_bindings_are_set(self) -> None:
        envelope = _make_envelope("retrieve_document", "knowledge_management")
        result = self.matcher.match(envelope)
        assert len(result.allowed_bindings) > 0

    def test_knowledge_domain_matches_search(self) -> None:
        envelope = _make_envelope("search_knowledge_base", "enterprise_search")
        result = self.matcher.match(envelope)
        assert result.selected_capability is not None
        assert "search" in result.selected_capability.capability_id

    def test_booking_intent(self) -> None:
        envelope = _make_envelope(
            "reserve_table",
            "booking",
            operation_class=OperationClass.WRITE,
            trust_level=TrustLevel.INTERNAL,
            scopes=["sip:booking:write"],
        )
        result = self.matcher.match(envelope)
        assert result.selected_capability is not None
        assert result.selected_capability.capability_id == "reserve_table"

    def test_network_diagnostics_intent(self) -> None:
        envelope = _make_envelope(
            "diagnose_network_issue",
            "network_operations",
            operation_class=OperationClass.ANALYZE,
            trust_level=TrustLevel.INTERNAL,
            scopes=["sip:network:read"],
        )
        result = self.matcher.match(envelope)
        assert result.selected_capability is not None
        assert result.selected_capability.capability_id == "diagnose_network_issue"

    def test_intent_id_matches_envelope(self) -> None:
        envelope = _make_envelope("retrieve_document", "knowledge_management")
        result = self.matcher.match(envelope)
        assert result.intent_id == envelope.intent_id

    def test_selection_rationale_is_populated(self) -> None:
        envelope = _make_envelope("retrieve_document", "knowledge_management")
        result = self.matcher.match(envelope)
        if result.selected_capability:
            assert len(result.selection_rationale) > 0

    def test_no_match_policy_decision_is_not_allowed(self) -> None:
        """When no capability is selected, policy_decision.allowed must be False."""
        envelope = _make_envelope("totally_unknown_intent", "totally_unknown_domain")
        result = self.matcher.match(envelope)
        assert result.requires_clarification is True
        assert result.selected_capability is None
        assert result.policy_decision.allowed is False

    def test_successful_match_policy_decision_is_allowed(self) -> None:
        """When a capability is selected, policy_decision.allowed must be True."""
        envelope = _make_envelope("retrieve_document", "knowledge_management")
        result = self.matcher.match(envelope)
        assert result.selected_capability is not None
        assert result.policy_decision.allowed is True

    def test_allowed_bindings_filtered_to_preferred(self) -> None:
        """When envelope specifies a binding, only that binding should be in allowed_bindings."""
        envelope = _make_envelope(
            "retrieve_document",
            "knowledge_management",
            preferred_binding=BindingType.REST,
        )
        result = self.matcher.match(envelope)
        assert result.selected_capability is not None
        # All allowed bindings should be REST since that's the only one requested
        for b in result.allowed_bindings:
            assert b == BindingType.REST

    def test_allowed_bindings_all_when_no_preference(self) -> None:
        """When no binding preference is set, all supported bindings should be allowed."""
        envelope = _make_envelope("retrieve_document", "knowledge_management")
        result = self.matcher.match(envelope)
        assert result.selected_capability is not None
        # Should include all bindings supported by the capability
        cap_bindings = set(result.selected_capability.supported_bindings)
        allowed = set(result.allowed_bindings)
        assert allowed == cap_bindings
