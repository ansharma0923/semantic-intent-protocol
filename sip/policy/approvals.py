"""Approval workflow models and helpers for SIP policy.

Provides approval state tracking for intents that require human review
before execution proceeds.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class ApprovalState(str, Enum):
    """State of a human approval request."""

    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    NOT_REQUIRED = "not_required"


class ApprovalRecord(BaseModel):
    """Record of an approval decision for an intent."""

    intent_id: str = Field(description="The intent requiring approval.")
    plan_id: str = Field(description="The execution plan requiring approval.")
    state: ApprovalState = Field(description="Current approval state.")
    requested_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When approval was requested.",
    )
    decided_at: datetime | None = Field(
        default=None,
        description="When the approval decision was made.",
    )
    approver_id: str | None = Field(
        default=None,
        description="ID of the approver (human or system).",
    )
    notes: str = Field(
        default="",
        description="Notes from the approver.",
    )

    def approve(self, approver_id: str, notes: str = "") -> "ApprovalRecord":
        """Return a new record with approved state."""
        return self.model_copy(
            update={
                "state": ApprovalState.APPROVED,
                "decided_at": datetime.now(timezone.utc),
                "approver_id": approver_id,
                "notes": notes,
            }
        )

    def deny(self, approver_id: str, notes: str = "") -> "ApprovalRecord":
        """Return a new record with denied state."""
        return self.model_copy(
            update={
                "state": ApprovalState.DENIED,
                "decided_at": datetime.now(timezone.utc),
                "approver_id": approver_id,
                "notes": notes,
            }
        )
