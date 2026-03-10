"""Audit record model and helpers for SIP observability.

Every intent processed by the broker generates an AuditRecord that captures
the actor, capability selected, policy decision, and outcome. These records
are the primary audit trail for SIP.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field


class ActionTaken(str, Enum):
    """What action was taken after negotiation and policy evaluation."""

    PLAN_CREATED = "plan_created"
    PLAN_REJECTED = "plan_rejected"
    APPROVAL_REQUESTED = "approval_requested"
    CLARIFICATION_REQUESTED = "clarification_requested"
    POLICY_DENIED = "policy_denied"
    VALIDATION_FAILED = "validation_failed"


class OutcomeSummary(str, Enum):
    """High-level outcome of processing the intent."""

    SUCCESS = "success"
    PENDING_APPROVAL = "pending_approval"
    NEEDS_CLARIFICATION = "needs_clarification"
    DENIED = "denied"
    ERROR = "error"


class AuditRecord(BaseModel):
    """Immutable audit record for a processed SIP intent.

    An AuditRecord is created by the broker for every intent it processes,
    regardless of outcome. Records should be persisted to an append-only
    audit log in production.
    """

    audit_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique audit record identifier.",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When this audit record was created.",
    )
    trace_id: str = Field(description="Distributed trace identifier.")
    intent_id: str = Field(description="ID of the processed intent.")
    actor_id: str = Field(description="ID of the originating actor.")
    actor_type: str = Field(description="Type of the originating actor.")
    intent_name: str = Field(description="Machine-readable intent name.")
    intent_domain: str = Field(description="Functional domain of the intent.")
    operation_class: str = Field(description="Operation class.")
    selected_capability_id: str | None = Field(
        default=None,
        description="ID of the capability selected, if any.",
    )
    selected_binding: str | None = Field(
        default=None,
        description="Binding selected for execution, if any.",
    )
    action_taken: ActionTaken = Field(description="What action was taken.")
    policy_allowed: bool = Field(description="Whether policy allowed the action.")
    approval_state: str = Field(
        default="not_required",
        description="Approval state (not_required | pending | approved | denied).",
    )
    outcome_summary: OutcomeSummary = Field(description="High-level outcome.")
    notes: str = Field(
        default="",
        description="Additional notes or error messages.",
    )

    model_config = {"frozen": True}


def create_audit_record(
    *,
    trace_id: str,
    intent_id: str,
    actor_id: str,
    actor_type: str,
    intent_name: str,
    intent_domain: str,
    operation_class: str,
    selected_capability_id: str | None,
    selected_binding: str | None,
    action_taken: ActionTaken,
    policy_allowed: bool,
    approval_state: str = "not_required",
    outcome_summary: OutcomeSummary = OutcomeSummary.SUCCESS,
    notes: str = "",
) -> AuditRecord:
    """Construct an AuditRecord from named parameters.

    All required fields are keyword-only to prevent accidental positional
    argument errors.
    """
    return AuditRecord(
        trace_id=trace_id,
        intent_id=intent_id,
        actor_id=actor_id,
        actor_type=actor_type,
        intent_name=intent_name,
        intent_domain=intent_domain,
        operation_class=operation_class,
        selected_capability_id=selected_capability_id,
        selected_binding=selected_binding,
        action_taken=action_taken,
        policy_allowed=policy_allowed,
        approval_state=approval_state,
        outcome_summary=outcome_summary,
        notes=notes,
    )
