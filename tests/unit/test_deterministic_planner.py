"""Tests for DeterministicPlanner and ExecutionType."""

from __future__ import annotations

import pytest

from sip.core.deterministic_planner import DeterministicPlanner
from sip.core.fail_closed import FailClosedError
from sip.core.normalized_intent import NormalizedActor, NormalizedConstraints, NormalizedIntent
from sip.core.policy_engine import CanonicalPolicyEngine
from sip.envelope.models import (
    BindingType,
    DataSensitivity,
    OperationClass,
    TrustLevel,
)
from sip.negotiation.planner import ExecutionType, binding_to_execution_type
from sip.policy.interface import PolicyResult, ReasonCode
from sip.registry.bootstrap import build_seeded_registry
from sip.registry.models import (
    CapabilityConstraints,
    CapabilityDescriptor,
    ExecutionMetadata,
    ProviderMetadata,
    SchemaReference,
)


def _make_intent(
    *,
    scopes: list[str] | None = None,
    data_sensitivity: DataSensitivity = DataSensitivity.INTERNAL,
    preferred_execution_mode: str | None = None,
) -> NormalizedIntent:
    return NormalizedIntent(
        intent_id="test-intent",
        correlation_id="test-trace",
        actor=NormalizedActor(
            actor_id="test-actor",
            actor_type="service",
            name="Test",
            trust_level=TrustLevel.INTERNAL,
            scopes=scopes or ["sip:knowledge:read"],
        ),
        goal="Retrieve a document.",
        constraints=NormalizedConstraints(data_sensitivity=data_sensitivity),
        data_sensitivity=data_sensitivity,
        trust_requirements=TrustLevel.INTERNAL,
        raw_request={},
        preferred_execution_mode=preferred_execution_mode,
    )


def _make_cap(
    capability_id: str,
    provider_id: str = "provider-a",
    bindings: list[BindingType] | None = None,
    requires_human_approval: bool = False,
) -> CapabilityDescriptor:
    return CapabilityDescriptor(
        capability_id=capability_id,
        name=capability_id.replace("_", " ").title(),
        description=f"Test capability {capability_id}.",
        provider=ProviderMetadata(provider_id=provider_id, provider_name=provider_id),
        intent_domains=["test"],
        input_schema=SchemaReference(),
        output_schema=SchemaReference(description="Test output"),
        operation_class=OperationClass.RETRIEVE,
        risk_level=sip.registry.models.RiskLevel.LOW,
        minimum_trust_tier=TrustLevel.INTERNAL,
        supported_bindings=bindings or [BindingType.REST],
        constraints=CapabilityConstraints(requires_human_approval=requires_human_approval),
    )


import sip.registry.models


class TestExecutionType:
    def test_all_binding_types_have_mapping(self) -> None:
        for binding in BindingType:
            exec_type = binding_to_execution_type(binding)
            assert isinstance(exec_type, ExecutionType)

    def test_rest_maps_to_rest_api(self) -> None:
        assert binding_to_execution_type(BindingType.REST) == ExecutionType.REST_API

    def test_mcp_maps_to_mcp_tool(self) -> None:
        assert binding_to_execution_type(BindingType.MCP) == ExecutionType.MCP_TOOL

    def test_grpc_maps_to_grpc_service(self) -> None:
        assert binding_to_execution_type(BindingType.GRPC) == ExecutionType.GRPC_SERVICE

    def test_a2a_maps_to_a2a_agent(self) -> None:
        assert binding_to_execution_type(BindingType.A2A) == ExecutionType.A2A_AGENT


class TestDeterministicPlanner:
    def setup_method(self) -> None:
        self.planner = DeterministicPlanner()

    def _allow_result(self, *caps: CapabilityDescriptor) -> PolicyResult:
        return PolicyResult.allow(allowed_capabilities=list(caps))

    # --- Happy path ---

    def test_plan_created_for_single_candidate(self) -> None:
        intent = _make_intent()
        cap = _make_cap("cap_a")
        policy = self._allow_result(cap)
        plan = self.planner.plan(intent, policy, [cap])
        assert plan is not None
        assert plan.intent_id == intent.intent_id

    def test_plan_selects_first_alphabetically(self) -> None:
        """Stable tie-breaking: (provider_id, capability_id) sort."""
        intent = _make_intent()
        cap_z = _make_cap("zzz_cap", provider_id="provider-a")
        cap_a = _make_cap("aaa_cap", provider_id="provider-a")
        policy = self._allow_result(cap_z, cap_a)
        # Supply in reverse order to ensure sorting is applied
        plan = self.planner.plan(intent, policy, [cap_z, cap_a])
        assert plan.selected_capability.capability_id == "aaa_cap"

    def test_stable_tie_breaking_by_provider_then_capability(self) -> None:
        """When capability IDs are equal, sort by provider_id first."""
        intent = _make_intent()
        cap_b = _make_cap("same_cap", provider_id="provider-b")
        cap_a = _make_cap("same_cap", provider_id="provider-a")
        policy = self._allow_result(cap_b, cap_a)
        plan = self.planner.plan(intent, policy, [cap_b, cap_a])
        assert plan.selected_capability.provider.provider_id == "provider-a"

    def test_deterministic_same_inputs_same_output(self) -> None:
        """Same inputs must always produce the same plan."""
        intent = _make_intent()
        cap_a = _make_cap("cap_a")
        cap_b = _make_cap("cap_b")
        policy = self._allow_result(cap_a, cap_b)
        plan1 = self.planner.plan(intent, policy, [cap_a, cap_b])
        plan2 = self.planner.plan(intent, policy, [cap_b, cap_a])
        # Same capability and binding selected regardless of input order
        assert plan1.selected_capability.capability_id == plan2.selected_capability.capability_id
        assert plan1.selected_binding == plan2.selected_binding

    def test_plan_has_execution_steps(self) -> None:
        intent = _make_intent()
        cap = _make_cap("cap_a")
        policy = self._allow_result(cap)
        plan = self.planner.plan(intent, policy, [cap])
        assert len(plan.execution_steps) >= 1

    def test_plan_has_execution_type(self) -> None:
        intent = _make_intent()
        cap = _make_cap("cap_a", bindings=[BindingType.MCP])
        policy = self._allow_result(cap)
        plan = self.planner.plan(intent, policy, [cap])
        assert plan.execution_type == ExecutionType.MCP_TOOL
        assert plan.execution_steps[0].execution_type == ExecutionType.MCP_TOOL

    def test_plan_has_preconditions(self) -> None:
        intent = _make_intent()
        cap = _make_cap("cap_a")
        policy = PolicyResult.allow(
            allowed_capabilities=[cap],
            conditions=["Must have valid token"],
        )
        plan = self.planner.plan(intent, policy, [cap])
        assert "Must have valid token" in plan.preconditions

    def test_plan_has_fallback_behavior(self) -> None:
        intent = _make_intent()
        cap = _make_cap("cap_a")
        policy = self._allow_result(cap)
        plan = self.planner.plan(intent, policy, [cap])
        assert plan.fallback_behavior == "fail_closed"

    def test_plan_has_selection_basis(self) -> None:
        intent = _make_intent()
        cap = _make_cap("cap_a")
        policy = self._allow_result(cap)
        plan = self.planner.plan(intent, policy, [cap])
        assert len(plan.selection_basis) > 0

    def test_preferred_binding_honored(self) -> None:
        intent = _make_intent(preferred_execution_mode="mcp")
        cap = _make_cap("cap_a", bindings=[BindingType.REST, BindingType.MCP])
        policy = self._allow_result(cap)
        plan = self.planner.plan(intent, policy, [cap])
        assert plan.selected_binding == BindingType.MCP

    def test_approval_required_when_policy_has_required_approvals(self) -> None:
        intent = _make_intent()
        cap = _make_cap("cap_a")
        policy = PolicyResult.allow(
            allowed_capabilities=[cap],
            required_approvals=["security-team"],
        )
        plan = self.planner.plan(intent, policy, [cap])
        assert plan.approval_required is True

    def test_only_policy_allowed_candidates_considered(self) -> None:
        """Candidates not in policy_result.allowed_capabilities are excluded."""
        intent = _make_intent()
        cap_allowed = _make_cap("allowed_cap")
        cap_denied = _make_cap("denied_cap")
        policy = self._allow_result(cap_allowed)  # only allowed_cap
        # Supply both, but planner should only use allowed_cap
        plan = self.planner.plan(intent, policy, [cap_allowed, cap_denied])
        assert plan.selected_capability.capability_id == "allowed_cap"

    def test_uses_registry_candidates_when_external_empty(self) -> None:
        """When candidate_capabilities is empty, fall back to policy allowed set."""
        intent = _make_intent()
        cap = _make_cap("cap_a")
        policy = self._allow_result(cap)
        plan = self.planner.plan(intent, policy, [])  # no external candidates
        assert plan.selected_capability.capability_id == "cap_a"

    # --- Fail-closed scenarios ---

    def test_fail_closed_when_policy_denied(self) -> None:
        intent = _make_intent()
        cap = _make_cap("cap_a")
        policy = PolicyResult.deny(
            reason_code=ReasonCode.MISSING_SCOPES,
            reason="Missing scopes.",
        )
        with pytest.raises(FailClosedError) as exc_info:
            self.planner.plan(intent, policy, [cap])
        assert exc_info.value.denial.reason_code == ReasonCode.MISSING_SCOPES

    def test_fail_closed_when_no_allowed_capabilities(self) -> None:
        intent = _make_intent()
        policy = PolicyResult.allow(allowed_capabilities=[])
        with pytest.raises(FailClosedError):
            self.planner.plan(intent, policy, [])

    def test_fail_closed_when_no_binding_available(self) -> None:
        intent = _make_intent()
        cap = CapabilityDescriptor(
            capability_id="no_binding_cap",
            name="No Binding Cap",
            description="No bindings.",
            provider=ProviderMetadata(provider_id="p1", provider_name="P1"),
            intent_domains=["test"],
            input_schema=SchemaReference(),
            output_schema=SchemaReference(),
            operation_class=OperationClass.RETRIEVE,
            minimum_trust_tier=TrustLevel.INTERNAL,
            supported_bindings=[],  # empty!
        )
        policy = PolicyResult.allow(allowed_capabilities=[cap])
        with pytest.raises(FailClosedError):
            self.planner.plan(intent, policy, [cap])

    # --- Integration with registry ---

    def test_plan_with_registry_capabilities(self) -> None:
        registry = build_seeded_registry()
        engine = CanonicalPolicyEngine()
        planner = DeterministicPlanner()

        intent = _make_intent(scopes=["sip:knowledge:read"])
        cap = registry.get_by_id("retrieve_document")
        assert cap is not None

        policy = engine.evaluate(intent, [cap])
        assert policy.allowed is True

        plan = planner.plan(intent, policy, [cap])
        assert plan.selected_capability.capability_id == "retrieve_document"
        assert plan.execution_type is not None
