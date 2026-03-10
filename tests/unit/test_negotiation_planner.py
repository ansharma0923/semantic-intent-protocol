"""Unit tests for the execution planner."""

from __future__ import annotations

import pytest

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
from sip.negotiation.matcher import CapabilityMatcher
from sip.negotiation.planner import ExecutionPlanner
from sip.registry.bootstrap import build_seeded_registry


def _make_envelope(
    intent_name: str,
    intent_domain: str,
    operation_class: OperationClass = OperationClass.RETRIEVE,
    trust_level: TrustLevel = TrustLevel.INTERNAL,
    preferred_binding: BindingType | None = None,
    scopes: list[str] | None = None,
    parameters: dict | None = None,
) -> IntentEnvelope:
    bindings = [ProtocolBinding(binding_type=preferred_binding)] if preferred_binding else []
    return IntentEnvelope(
        actor=ActorDescriptor(
            actor_id="planner-test",
            actor_type=ActorType.SERVICE,
            name="Planner Test",
            trust_level=trust_level,
            scopes=scopes or ["sip:knowledge:read"],
        ),
        target=TargetDescriptor(target_type=TargetType.CAPABILITY),
        intent=IntentPayload(
            intent_name=intent_name,
            intent_domain=intent_domain,
            operation_class=operation_class,
            parameters=parameters or {},
        ),
        desired_outcome=DesiredOutcome(summary="Test"),
        protocol_bindings=bindings,
    )


class TestExecutionPlanner:
    def setup_method(self) -> None:
        self.registry = build_seeded_registry()
        self.matcher = CapabilityMatcher(self.registry)
        self.planner = ExecutionPlanner()

    def test_plan_created_for_valid_intent(self) -> None:
        envelope = _make_envelope("retrieve_document", "knowledge_management")
        negotiation = self.matcher.match(envelope)
        plan = self.planner.plan(envelope, negotiation)
        assert plan is not None
        assert plan.plan_id is not None
        assert plan.intent_id == envelope.intent_id

    def test_plan_has_execution_steps(self) -> None:
        envelope = _make_envelope("retrieve_document", "knowledge_management")
        negotiation = self.matcher.match(envelope)
        plan = self.planner.plan(envelope, negotiation)
        assert len(plan.execution_steps) >= 1

    def test_plan_selected_capability_matches_negotiation(self) -> None:
        envelope = _make_envelope("retrieve_document", "knowledge_management")
        negotiation = self.matcher.match(envelope)
        plan = self.planner.plan(envelope, negotiation)
        assert plan.selected_capability.capability_id == (
            negotiation.selected_capability.capability_id
        )

    def test_plan_selected_binding_matches_negotiation(self) -> None:
        envelope = _make_envelope("retrieve_document", "knowledge_management")
        negotiation = self.matcher.match(envelope)
        plan = self.planner.plan(envelope, negotiation)
        assert plan.selected_binding == negotiation.selected_binding

    def test_plan_has_trace_metadata(self) -> None:
        envelope = _make_envelope("retrieve_document", "knowledge_management")
        negotiation = self.matcher.match(envelope)
        plan = self.planner.plan(envelope, negotiation)
        assert plan.trace.trace_id == envelope.trace_id
        assert plan.trace.intent_id == envelope.intent_id

    def test_plan_has_deterministic_target(self) -> None:
        envelope = _make_envelope("retrieve_document", "knowledge_management")
        negotiation = self.matcher.match(envelope)
        plan = self.planner.plan(envelope, negotiation)
        assert "capability_id" in plan.deterministic_target
        assert "binding_type" in plan.deterministic_target

    def test_plan_parameters_from_envelope(self) -> None:
        params = {"query": "architecture document", "collection": "design-docs"}
        envelope = _make_envelope(
            "retrieve_document",
            "knowledge_management",
            parameters=params,
        )
        negotiation = self.matcher.match(envelope)
        plan = self.planner.plan(envelope, negotiation)
        assert plan.grounded_parameters["query"] == "architecture document"

    def test_plan_raises_if_no_capability_selected(self) -> None:
        envelope = _make_envelope("nonexistent_intent", "nonexistent_domain")
        negotiation = self.matcher.match(envelope)
        # negotiation.requires_clarification is True, no capability selected
        with pytest.raises(ValueError, match="no capability selected"):
            self.planner.plan(envelope, negotiation)

    def test_plan_policy_checks_are_populated(self) -> None:
        envelope = _make_envelope("retrieve_document", "knowledge_management")
        negotiation = self.matcher.match(envelope)
        plan = self.planner.plan(envelope, negotiation)
        assert len(plan.policy_checks_passed) > 0

    def test_plan_rest_binding(self) -> None:
        envelope = _make_envelope(
            "retrieve_document",
            "knowledge_management",
            preferred_binding=BindingType.REST,
        )
        negotiation = self.matcher.match(envelope)
        plan = self.planner.plan(envelope, negotiation)
        assert plan.selected_binding == BindingType.REST

    def test_execution_step_has_correct_capability(self) -> None:
        envelope = _make_envelope("diagnose_network_issue", "network_operations",
                                   operation_class=OperationClass.ANALYZE,
                                   scopes=["sip:network:read"])
        negotiation = self.matcher.match(envelope)
        plan = self.planner.plan(envelope, negotiation)
        assert plan.execution_steps[0].capability_id == "diagnose_network_issue"
