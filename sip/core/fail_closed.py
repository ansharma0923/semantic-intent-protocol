"""Fail-closed logic for the SIP pipeline.

Provides explicit fail-closed checks that gate every stage of the SIP
processing pipeline.  When a check fails the pipeline raises a
``FailClosedError`` rather than proceeding with an unsafe or incomplete
decision.

Design principles
-----------------
* All checks default to *deny* when information is absent or ambiguous.
* Each check returns a ``StructuredDenial`` that carries a machine-readable
  ``reason_code``, a human-readable ``reason``, and a list of
  ``required_actions`` so callers know exactly what is needed to proceed.
* ``FailClosedError`` wraps a ``StructuredDenial`` so it is always safe to
  catch the error and inspect the denial detail.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from sip.policy.interface import ReasonCode


# ---------------------------------------------------------------------------
# StructuredDenial
# ---------------------------------------------------------------------------


class StructuredDenial(BaseModel):
    """A structured denial produced by a fail-closed check.

    Fields
    ------
    reason_code
        Machine-readable denial reason (see ``ReasonCode``).
    reason
        Human-readable description.
    required_actions
        List of actions the caller must take before retrying.
    metadata
        Arbitrary additional metadata for debugging.
    """

    reason_code: str = Field(description="Machine-readable reason code.")
    reason: str = Field(description="Human-readable denial reason.")
    required_actions: list[str] = Field(
        default_factory=list,
        description="Actions required before retrying.",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"frozen": True}


# ---------------------------------------------------------------------------
# FailClosedError
# ---------------------------------------------------------------------------


class FailClosedError(Exception):
    """Raised when a fail-closed check prevents the pipeline from proceeding.

    Always wraps a ``StructuredDenial`` so callers can inspect the reason
    without parsing the exception message.
    """

    def __init__(self, denial: StructuredDenial) -> None:
        self.denial = denial
        super().__init__(f"[{denial.reason_code}] {denial.reason}")

    @classmethod
    def from_reason(
        cls,
        reason_code: str,
        reason: str,
        required_actions: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "FailClosedError":
        """Convenience constructor."""
        return cls(
            StructuredDenial(
                reason_code=reason_code,
                reason=reason,
                required_actions=required_actions or [],
                metadata=metadata or {},
            )
        )


# ---------------------------------------------------------------------------
# Fail-closed check functions
# ---------------------------------------------------------------------------


def check_policy_decision_present(policy_result: Any) -> None:
    """Fail closed if ``policy_result`` is None.

    Args:
        policy_result: The result returned by the policy engine.

    Raises:
        FailClosedError: If policy_result is None.
    """
    if policy_result is None:
        raise FailClosedError.from_reason(
            reason_code=ReasonCode.EVALUATION_ERROR,
            reason="Policy evaluation produced no result; failing closed.",
            required_actions=["Ensure the policy engine returns a PolicyResult for all inputs."],
        )


def check_policy_allowed(policy_result: Any) -> None:
    """Fail closed if the policy decision does not allow the intent.

    Args:
        policy_result: A ``PolicyResult`` instance.

    Raises:
        FailClosedError: If the policy denies the intent.
    """
    check_policy_decision_present(policy_result)
    if not policy_result.allowed:
        raise FailClosedError.from_reason(
            reason_code=policy_result.reason_code,
            reason=policy_result.reason or "Policy denied the intent.",
            required_actions=["Review policy decision and resolve the denial condition."],
            metadata={"evaluation_notes": policy_result.evaluation_notes},
        )


def check_provenance_present(
    normalized_intent: Any,
    *,
    require_provenance: bool = False,
) -> None:
    """Optionally fail closed if provenance is absent.

    By default (``require_provenance=False``) provenance is optional and
    this check is a no-op.  When ``require_provenance=True`` this enforces
    that the intent carries a known originator.

    Args:
        normalized_intent: A ``NormalizedIntent`` instance.
        require_provenance: When True, deny if originator is missing.

    Raises:
        FailClosedError: When required and originator is absent.
    """
    if not require_provenance:
        return
    if not normalized_intent.actor.originator:
        raise FailClosedError.from_reason(
            reason_code=ReasonCode.MISSING_PROVENANCE,
            reason="Provenance is required but the intent has no declared originator.",
            required_actions=[
                "Include a ProvenanceBlock with a non-null originator in the IntentEnvelope."
            ],
        )


def check_trust_level_present(normalized_intent: Any) -> None:
    """Fail closed if the actor's trust level is missing.

    Args:
        normalized_intent: A ``NormalizedIntent`` instance.

    Raises:
        FailClosedError: If trust_level is not set on the actor.
    """
    if normalized_intent.actor.trust_level is None:
        raise FailClosedError.from_reason(
            reason_code=ReasonCode.MISSING_TRUST_LEVEL,
            reason="Actor trust level is missing; failing closed.",
            required_actions=[
                "Provide a valid TrustLevel in ActorDescriptor.trust_level."
            ],
        )


def check_allowed_capabilities_present(policy_result: Any) -> None:
    """Fail closed if the policy result contains no allowed capabilities.

    Args:
        policy_result: A ``PolicyResult`` instance.

    Raises:
        FailClosedError: If allowed_capabilities is empty.
    """
    if not policy_result.allowed_capabilities:
        raise FailClosedError.from_reason(
            reason_code=ReasonCode.NO_ALLOWED_CAPABILITIES,
            reason="No allowed capabilities remain after policy filtering.",
            required_actions=[
                "Supply at least one candidate capability that satisfies the policy requirements."
            ],
        )


def check_required_approvals_met(
    policy_result: Any,
    *,
    provided_approvals: list[str] | None = None,
) -> None:
    """Fail closed if required approvals are not satisfied.

    ``required_approvals`` in the ``PolicyResult`` is a list of approver IDs
    or roles that must sign off before execution.  When this list is non-empty
    and no ``provided_approvals`` are given the check fails closed.

    Args:
        policy_result: A ``PolicyResult`` instance.
        provided_approvals: Approvals that have already been granted.

    Raises:
        FailClosedError: When required approvals are missing.
    """
    required = set(policy_result.required_approvals)
    if not required:
        return
    provided = set(provided_approvals or [])
    missing = required - provided
    if missing:
        raise FailClosedError.from_reason(
            reason_code=ReasonCode.MISSING_REQUIRED_APPROVALS,
            reason=f"Required approvals not satisfied: {sorted(missing)}.",
            required_actions=[
                f"Obtain approval from: {sorted(missing)} before proceeding."
            ],
            metadata={"required": sorted(required), "provided": sorted(provided)},
        )


def check_no_deterministic_plan_possible(plan: Any) -> None:
    """Fail closed if no execution plan could be produced.

    Args:
        plan: The result of the deterministic planner (may be None).

    Raises:
        FailClosedError: If plan is None.
    """
    if plan is None:
        raise FailClosedError.from_reason(
            reason_code=ReasonCode.NO_ALLOWED_CAPABILITIES,
            reason="Deterministic planner could not produce a safe execution plan.",
            required_actions=[
                "Ensure candidate capabilities are compatible with the intent and policy."
            ],
        )
