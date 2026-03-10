"""Unit tests for audit record generation."""

from __future__ import annotations

from datetime import UTC

from sip.observability.audit import (
    ActionTaken,
    OutcomeSummary,
    create_audit_record,
)
from sip.observability.tracing import new_span_id, new_trace_id


class TestAuditRecord:
    def test_create_audit_record(self) -> None:
        record = create_audit_record(
            trace_id=new_trace_id(),
            intent_id="test-intent-id",
            actor_id="actor-1",
            actor_type="service",
            intent_name="retrieve_document",
            intent_domain="knowledge_management",
            operation_class="retrieve",
            selected_capability_id="retrieve_document",
            selected_binding="rag",
            action_taken=ActionTaken.PLAN_CREATED,
            policy_allowed=True,
            outcome_summary=OutcomeSummary.SUCCESS,
        )
        assert record.intent_id == "test-intent-id"
        assert record.action_taken == ActionTaken.PLAN_CREATED
        assert record.policy_allowed is True
        assert record.outcome_summary == OutcomeSummary.SUCCESS

    def test_audit_record_has_timestamp(self) -> None:
        record = create_audit_record(
            trace_id=new_trace_id(),
            intent_id="id1",
            actor_id="a",
            actor_type="service",
            intent_name="test",
            intent_domain="test",
            operation_class="read",
            selected_capability_id=None,
            selected_binding=None,
            action_taken=ActionTaken.VALIDATION_FAILED,
            policy_allowed=False,
            outcome_summary=OutcomeSummary.ERROR,
        )
        assert record.timestamp is not None
        assert record.timestamp.tzinfo == UTC

    def test_audit_record_is_frozen(self) -> None:
        import pytest
        from pydantic import ValidationError

        record = create_audit_record(
            trace_id=new_trace_id(),
            intent_id="id1",
            actor_id="a",
            actor_type="service",
            intent_name="test",
            intent_domain="test",
            operation_class="read",
            selected_capability_id=None,
            selected_binding=None,
            action_taken=ActionTaken.VALIDATION_FAILED,
            policy_allowed=False,
            outcome_summary=OutcomeSummary.ERROR,
        )
        with pytest.raises(ValidationError):
            record.intent_id = "modified"  # type: ignore[misc]

    def test_audit_record_unique_ids(self) -> None:
        r1 = create_audit_record(
            trace_id="t1", intent_id="i1", actor_id="a", actor_type="service",
            intent_name="test", intent_domain="test", operation_class="read",
            selected_capability_id=None, selected_binding=None,
            action_taken=ActionTaken.PLAN_CREATED, policy_allowed=True,
            outcome_summary=OutcomeSummary.SUCCESS,
        )
        r2 = create_audit_record(
            trace_id="t2", intent_id="i2", actor_id="a", actor_type="service",
            intent_name="test", intent_domain="test", operation_class="read",
            selected_capability_id=None, selected_binding=None,
            action_taken=ActionTaken.PLAN_CREATED, policy_allowed=True,
            outcome_summary=OutcomeSummary.SUCCESS,
        )
        assert r1.audit_id != r2.audit_id

    def test_action_taken_enum_values(self) -> None:
        assert ActionTaken.PLAN_CREATED == "plan_created"
        assert ActionTaken.POLICY_DENIED == "policy_denied"
        assert ActionTaken.VALIDATION_FAILED == "validation_failed"

    def test_outcome_summary_enum_values(self) -> None:
        assert OutcomeSummary.SUCCESS == "success"
        assert OutcomeSummary.DENIED == "denied"
        assert OutcomeSummary.NEEDS_CLARIFICATION == "needs_clarification"

    def test_approval_state_defaults_to_not_required(self) -> None:
        record = create_audit_record(
            trace_id="t", intent_id="i", actor_id="a", actor_type="service",
            intent_name="test", intent_domain="test", operation_class="read",
            selected_capability_id="cap", selected_binding="rest",
            action_taken=ActionTaken.PLAN_CREATED, policy_allowed=True,
            outcome_summary=OutcomeSummary.SUCCESS,
        )
        assert record.approval_state == "not_required"


class TestTracing:
    def test_new_trace_id_is_string(self) -> None:
        tid = new_trace_id()
        assert isinstance(tid, str)
        assert len(tid) > 0

    def test_new_trace_ids_are_unique(self) -> None:
        ids = {new_trace_id() for _ in range(100)}
        assert len(ids) == 100

    def test_new_span_id_is_string(self) -> None:
        sid = new_span_id()
        assert isinstance(sid, str)
        assert len(sid) > 0
