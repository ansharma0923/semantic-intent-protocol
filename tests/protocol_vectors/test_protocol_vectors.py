"""Protocol vector tests for the Semantic Intent Protocol.

These tests load each canonical JSON fixture from the protocol-vectors/
directory, parse it into the corresponding SIP model, verify validation
passes, serialize back to JSON, and confirm round-trip equality.

Passing these tests confirms that the Python reference implementation
is compatible with SIP v0.1 protocol vectors.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sip.sdk.serialization import (
    parse_audit_record,
    parse_capability_descriptor,
    parse_execution_plan,
    parse_intent_envelope,
    parse_negotiation_result,
    to_dict,
)

# Directory containing the canonical protocol vectors
VECTORS_DIR = Path(__file__).parent.parent.parent / "protocol-vectors"


def _load_vector(filename: str) -> dict:
    """Load a protocol vector JSON file."""
    path = VECTORS_DIR / filename
    assert path.exists(), f"Protocol vector not found: {path}"
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# IntentEnvelope vectors
# ---------------------------------------------------------------------------


class TestIntentEnvelopeBasic:
    """Tests for intent-envelope-basic.json."""

    def test_loads_without_error(self) -> None:
        raw = _load_vector("intent-envelope-basic.json")
        envelope = parse_intent_envelope(raw)
        assert envelope is not None

    def test_required_fields(self) -> None:
        raw = _load_vector("intent-envelope-basic.json")
        envelope = parse_intent_envelope(raw)
        assert envelope.sip_version == "0.1"
        assert envelope.message_type.value == "intent_request"
        assert envelope.intent_id == "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        assert envelope.actor.actor_id == "agent-001"
        assert envelope.actor.actor_type.value == "ai_agent"
        assert envelope.intent.intent_name == "retrieve_document"
        assert envelope.intent.intent_domain == "knowledge_management"
        assert envelope.intent.operation_class.value == "retrieve"

    def test_no_provenance(self) -> None:
        raw = _load_vector("intent-envelope-basic.json")
        envelope = parse_intent_envelope(raw)
        assert envelope.provenance is None

    def test_no_extensions(self) -> None:
        raw = _load_vector("intent-envelope-basic.json")
        envelope = parse_intent_envelope(raw)
        assert envelope.extensions == {}

    def test_round_trip(self) -> None:
        raw = _load_vector("intent-envelope-basic.json")
        envelope = parse_intent_envelope(raw)
        serialized = to_dict(envelope)
        # Re-parse to confirm the round-trip does not corrupt data
        envelope2 = parse_intent_envelope(serialized)
        assert envelope2.intent_id == envelope.intent_id
        assert envelope2.actor.actor_id == envelope.actor.actor_id
        assert envelope2.intent.intent_name == envelope.intent.intent_name
        assert envelope2.provenance == envelope.provenance

    def test_capability_requirements(self) -> None:
        raw = _load_vector("intent-envelope-basic.json")
        envelope = parse_intent_envelope(raw)
        assert len(envelope.capability_requirements) == 1
        req = envelope.capability_requirements[0]
        assert req.capability_name == "sip.knowledge.retrieve"
        assert "sip.knowledge.read" in req.required_scopes

    def test_constraints(self) -> None:
        raw = _load_vector("intent-envelope-basic.json")
        envelope = parse_intent_envelope(raw)
        assert envelope.constraints.time_budget_ms == 3000
        assert envelope.constraints.determinism_required.value == "strict"
        assert envelope.constraints.priority.value == "normal"


class TestIntentEnvelopeWithProvenance:
    """Tests for intent-envelope-with-provenance.json."""

    def test_loads_without_error(self) -> None:
        raw = _load_vector("intent-envelope-with-provenance.json")
        envelope = parse_intent_envelope(raw)
        assert envelope is not None

    def test_provenance_block(self) -> None:
        raw = _load_vector("intent-envelope-with-provenance.json")
        envelope = parse_intent_envelope(raw)
        assert envelope.provenance is not None
        assert envelope.provenance.originator == "user-researcher-042"
        assert envelope.provenance.submitted_by == "orchestrator-agent-007"
        assert len(envelope.provenance.delegation_chain) == 2
        assert envelope.provenance.on_behalf_of == "user-researcher-042"
        assert envelope.provenance.authority_scope is not None
        assert "sip.knowledge.read" in envelope.provenance.authority_scope

    def test_extensions(self) -> None:
        raw = _load_vector("intent-envelope-with-provenance.json")
        envelope = parse_intent_envelope(raw)
        assert "x_routing_hint" in envelope.extensions
        assert envelope.extensions["x_routing_hint"] == "prefer-local"

    def test_privileged_trust_level(self) -> None:
        raw = _load_vector("intent-envelope-with-provenance.json")
        envelope = parse_intent_envelope(raw)
        assert envelope.actor.trust_level.value == "privileged"

    def test_round_trip_preserves_provenance(self) -> None:
        raw = _load_vector("intent-envelope-with-provenance.json")
        envelope = parse_intent_envelope(raw)
        serialized = to_dict(envelope)
        envelope2 = parse_intent_envelope(serialized)
        assert envelope2.provenance is not None
        assert envelope2.provenance.originator == envelope.provenance.originator
        assert envelope2.provenance.delegation_chain == envelope.provenance.delegation_chain
        assert envelope2.extensions == envelope.extensions


# ---------------------------------------------------------------------------
# CapabilityDescriptor vector
# ---------------------------------------------------------------------------


class TestCapabilityDescriptorBasic:
    """Tests for capability-descriptor-basic.json."""

    def test_loads_without_error(self) -> None:
        raw = _load_vector("capability-descriptor-basic.json")
        cap = parse_capability_descriptor(raw)
        assert cap is not None

    def test_required_fields(self) -> None:
        raw = _load_vector("capability-descriptor-basic.json")
        cap = parse_capability_descriptor(raw)
        assert cap.capability_id == "sip.knowledge.retrieve"
        assert cap.name == "Knowledge Retrieval"
        assert cap.operation_class.value == "retrieve"
        assert cap.risk_level.value == "low"
        assert "sip.knowledge.read" in cap.required_scopes

    def test_provider_metadata(self) -> None:
        raw = _load_vector("capability-descriptor-basic.json")
        cap = parse_capability_descriptor(raw)
        assert cap.provider.provider_id == "knowledge_service"
        assert cap.provider.version == "1.2.0"

    def test_supported_bindings(self) -> None:
        raw = _load_vector("capability-descriptor-basic.json")
        cap = parse_capability_descriptor(raw)
        binding_values = [b.value for b in cap.supported_bindings]
        assert "rag" in binding_values
        assert "rest" in binding_values

    def test_intent_domains(self) -> None:
        raw = _load_vector("capability-descriptor-basic.json")
        cap = parse_capability_descriptor(raw)
        assert "knowledge_management" in cap.intent_domains

    def test_round_trip(self) -> None:
        raw = _load_vector("capability-descriptor-basic.json")
        cap = parse_capability_descriptor(raw)
        serialized = to_dict(cap)
        cap2 = parse_capability_descriptor(serialized)
        assert cap2.capability_id == cap.capability_id
        assert cap2.provider.provider_id == cap.provider.provider_id
        assert cap2.operation_class == cap.operation_class


# ---------------------------------------------------------------------------
# NegotiationResult vector
# ---------------------------------------------------------------------------


class TestNegotiationResultBasic:
    """Tests for negotiation-result-basic.json."""

    def test_loads_without_error(self) -> None:
        raw = _load_vector("negotiation-result-basic.json")
        result = parse_negotiation_result(raw)
        assert result is not None

    def test_intent_id(self) -> None:
        raw = _load_vector("negotiation-result-basic.json")
        result = parse_negotiation_result(raw)
        assert result.intent_id == "a1b2c3d4-e5f6-7890-abcd-ef1234567890"

    def test_ranked_candidates(self) -> None:
        raw = _load_vector("negotiation-result-basic.json")
        result = parse_negotiation_result(raw)
        assert len(result.ranked_candidates) == 1
        candidate = result.ranked_candidates[0]
        assert candidate.capability.capability_id == "sip.knowledge.retrieve"
        assert candidate.score == pytest.approx(0.95)

    def test_selected_capability(self) -> None:
        raw = _load_vector("negotiation-result-basic.json")
        result = parse_negotiation_result(raw)
        assert result.selected_capability is not None
        assert result.selected_capability.capability_id == "sip.knowledge.retrieve"

    def test_selected_binding(self) -> None:
        raw = _load_vector("negotiation-result-basic.json")
        result = parse_negotiation_result(raw)
        assert result.selected_binding is not None
        assert result.selected_binding.value == "rag"

    def test_policy_decision(self) -> None:
        raw = _load_vector("negotiation-result-basic.json")
        result = parse_negotiation_result(raw)
        assert result.policy_decision.allowed is True
        assert result.policy_decision.requires_approval is False
        assert result.policy_decision.denied_scopes == []

    def test_no_clarification_required(self) -> None:
        raw = _load_vector("negotiation-result-basic.json")
        result = parse_negotiation_result(raw)
        assert result.requires_clarification is False

    def test_round_trip(self) -> None:
        raw = _load_vector("negotiation-result-basic.json")
        result = parse_negotiation_result(raw)
        serialized = to_dict(result)
        result2 = parse_negotiation_result(serialized)
        assert result2.intent_id == result.intent_id
        assert len(result2.ranked_candidates) == len(result.ranked_candidates)
        assert result2.selected_binding == result.selected_binding


# ---------------------------------------------------------------------------
# ExecutionPlan vector
# ---------------------------------------------------------------------------


class TestExecutionPlanBasic:
    """Tests for execution-plan-basic.json."""

    def test_loads_without_error(self) -> None:
        raw = _load_vector("execution-plan-basic.json")
        plan = parse_execution_plan(raw)
        assert plan is not None

    def test_plan_ids(self) -> None:
        raw = _load_vector("execution-plan-basic.json")
        plan = parse_execution_plan(raw)
        assert plan.plan_id == "p7q8r9s0-t1u2-v3w4-x5y6-z789012345ab"
        assert plan.intent_id == "a1b2c3d4-e5f6-7890-abcd-ef1234567890"

    def test_selected_binding(self) -> None:
        raw = _load_vector("execution-plan-basic.json")
        plan = parse_execution_plan(raw)
        assert plan.selected_binding.value == "rag"

    def test_execution_steps(self) -> None:
        raw = _load_vector("execution-plan-basic.json")
        plan = parse_execution_plan(raw)
        assert len(plan.execution_steps) == 1
        step = plan.execution_steps[0]
        assert step.step_index == 0
        assert step.capability_id == "sip.knowledge.retrieve"
        assert step.binding.value == "rag"

    def test_grounded_parameters(self) -> None:
        raw = _load_vector("execution-plan-basic.json")
        plan = parse_execution_plan(raw)
        assert "query" in plan.grounded_parameters
        assert plan.grounded_parameters["query"] == "Q4 2023 financial results"

    def test_policy_checks(self) -> None:
        raw = _load_vector("execution-plan-basic.json")
        plan = parse_execution_plan(raw)
        assert len(plan.policy_checks_passed) == 2
        check_names = [c.check_name for c in plan.policy_checks_passed]
        assert "trust_level" in check_names
        assert "operation_class_match" in check_names

    def test_no_approval_required(self) -> None:
        raw = _load_vector("execution-plan-basic.json")
        plan = parse_execution_plan(raw)
        assert plan.approval_required is False

    def test_no_provenance_summary(self) -> None:
        raw = _load_vector("execution-plan-basic.json")
        plan = parse_execution_plan(raw)
        assert plan.provenance_summary is None

    def test_round_trip(self) -> None:
        raw = _load_vector("execution-plan-basic.json")
        plan = parse_execution_plan(raw)
        serialized = to_dict(plan)
        plan2 = parse_execution_plan(serialized)
        assert plan2.plan_id == plan.plan_id
        assert plan2.intent_id == plan.intent_id
        assert plan2.selected_binding == plan.selected_binding
        assert len(plan2.execution_steps) == len(plan.execution_steps)


# ---------------------------------------------------------------------------
# AuditRecord vector
# ---------------------------------------------------------------------------


class TestAuditRecordBasic:
    """Tests for audit-record-basic.json."""

    def test_loads_without_error(self) -> None:
        raw = _load_vector("audit-record-basic.json")
        record = parse_audit_record(raw)
        assert record is not None

    def test_required_fields(self) -> None:
        raw = _load_vector("audit-record-basic.json")
        record = parse_audit_record(raw)
        assert record.audit_id == "e8f9a0b1-c2d3-e4f5-a6b7-c8d9e0f12345"
        assert record.trace_id == "b2c3d4e5-f6a7-8901-bcde-f01234567891"
        assert record.intent_id == "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        assert record.actor_id == "agent-001"
        assert record.actor_type == "ai_agent"

    def test_intent_info(self) -> None:
        raw = _load_vector("audit-record-basic.json")
        record = parse_audit_record(raw)
        assert record.intent_name == "retrieve_document"
        assert record.intent_domain == "knowledge_management"
        assert record.operation_class == "retrieve"

    def test_outcome(self) -> None:
        raw = _load_vector("audit-record-basic.json")
        record = parse_audit_record(raw)
        assert record.action_taken.value == "plan_created"
        assert record.policy_allowed is True
        assert record.outcome_summary.value == "success"
        assert record.approval_state == "not_required"

    def test_selected_capability(self) -> None:
        raw = _load_vector("audit-record-basic.json")
        record = parse_audit_record(raw)
        assert record.selected_capability_id == "sip.knowledge.retrieve"
        assert record.selected_binding == "rag"

    def test_no_provenance_in_basic_record(self) -> None:
        raw = _load_vector("audit-record-basic.json")
        record = parse_audit_record(raw)
        assert record.originator is None
        assert record.delegation_chain == []

    def test_round_trip(self) -> None:
        raw = _load_vector("audit-record-basic.json")
        record = parse_audit_record(raw)
        serialized = to_dict(record)
        record2 = parse_audit_record(serialized)
        assert record2.audit_id == record.audit_id
        assert record2.intent_id == record.intent_id
        assert record2.action_taken == record.action_taken
        assert record2.outcome_summary == record.outcome_summary
