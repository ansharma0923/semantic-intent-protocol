"""Negotiation result models for SIP."""

from __future__ import annotations

from pydantic import BaseModel, Field

from sip.envelope.models import BindingType
from sip.registry.models import CapabilityDescriptor


class RankedCandidate(BaseModel):
    """A ranked capability candidate produced during negotiation."""

    capability: CapabilityDescriptor
    score: float = Field(description="Matching score (higher is better).")
    rationale: str = Field(
        default="",
        description="Human-readable explanation of why this candidate was ranked.",
    )


class PolicyDecisionSummary(BaseModel):
    """Summary of the policy evaluation that was applied during negotiation."""

    allowed: bool = Field(
        description="Whether policy allows this negotiation to proceed."
    )
    requires_approval: bool = Field(
        default=False,
        description="Whether human approval is required before execution.",
    )
    denied_scopes: list[str] = Field(
        default_factory=list,
        description="Scopes that were denied.",
    )
    policy_notes: list[str] = Field(
        default_factory=list,
        description="Human-readable policy evaluation notes.",
    )


class NegotiationResult(BaseModel):
    """Result of SIP capability negotiation for an intent.

    Produced by the negotiation engine after querying the registry and applying
    scoring and policy checks.
    """

    intent_id: str = Field(description="ID of the originating intent.")
    ranked_candidates: list[RankedCandidate] = Field(
        default_factory=list,
        description="All evaluated candidates, sorted by score descending.",
    )
    selected_capability: CapabilityDescriptor | None = Field(
        default=None,
        description="The capability selected for execution, if any.",
    )
    selection_rationale: str = Field(
        default="",
        description="Explanation of why the selected capability was chosen.",
    )
    requires_clarification: bool = Field(
        default=False,
        description="Whether clarification from the actor is required.",
    )
    clarification_questions: list[str] = Field(
        default_factory=list,
        description="Questions to ask the actor when clarification is required.",
    )
    allowed_bindings: list[BindingType] = Field(
        default_factory=list,
        description="Bindings that are compatible and policy-allowed.",
    )
    selected_binding: BindingType | None = Field(
        default=None,
        description="The binding selected for execution.",
    )
    policy_decision: PolicyDecisionSummary = Field(
        default_factory=lambda: PolicyDecisionSummary(allowed=True),
        description="Summary of policy evaluation.",
    )
