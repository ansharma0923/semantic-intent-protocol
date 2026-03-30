"""Pluggable policy engine interface for SIP.

Defines the ``PolicyEngineInterface`` ABC and the ``PolicyResult`` model.
Concrete implementations must evaluate an intent and a set of candidate
capabilities and return a ``PolicyResult``.

Design principles
-----------------
* **Fail closed by default**: if evaluation cannot complete, the result must
  be a denial (``allowed=False``).
* **Machine-readable reason codes**: every denial includes a ``reason_code``
  so callers can handle outcomes programmatically without parsing human text.
* **Stable filtering**: ``allowed_capabilities`` is the subset of the supplied
  candidates that passed all policy checks.

Architecture note
-----------------
The existing ``PolicyEngine`` in ``sip.policy.engine`` continues to work
unchanged as the legacy evaluation path.  ``CanonicalPolicyEngine`` in
``sip.core.policy_engine`` implements this interface using ``NormalizedIntent``
as its input type.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

from sip.registry.models import CapabilityDescriptor


# ---------------------------------------------------------------------------
# Well-known reason codes
# ---------------------------------------------------------------------------

class ReasonCode:
    """Machine-readable denial reason codes."""

    ALLOWED = "ALLOWED"
    MISSING_PROVENANCE = "MISSING_PROVENANCE"
    MISSING_TRUST_LEVEL = "MISSING_TRUST_LEVEL"
    MISSING_REQUIRED_APPROVALS = "MISSING_REQUIRED_APPROVALS"
    MISSING_SCOPES = "MISSING_SCOPES"
    NO_ALLOWED_CAPABILITIES = "NO_ALLOWED_CAPABILITIES"
    PRIVILEGE_ESCALATION = "PRIVILEGE_ESCALATION"
    RISK_DATA_SENSITIVITY_DENIED = "RISK_DATA_SENSITIVITY_DENIED"
    DELEGATION_CHAIN_TOO_LONG = "DELEGATION_CHAIN_TOO_LONG"
    EVALUATION_ERROR = "EVALUATION_ERROR"
    CAPABILITY_DENYLIST = "CAPABILITY_DENYLIST"
    COMPLIANCE_VIOLATION = "COMPLIANCE_VIOLATION"


# ---------------------------------------------------------------------------
# PolicyResult model
# ---------------------------------------------------------------------------


class PolicyResult(BaseModel):
    """Result of policy evaluation for an intent.

    Fields
    ------
    allowed
        Whether the intent is permitted to proceed.
    reason_code
        Machine-readable denial (or allow) reason code.
    reason
        Human-readable description of the policy decision.
    conditions
        Conditions that must be met before execution may proceed.
        Present even when ``allowed=True`` (e.g. audit-only conditions).
    required_approvals
        List of approver IDs or roles that must approve before execution.
    allowed_capabilities
        Subset of the evaluated candidate capabilities that passed all
        policy checks.  Empty when ``allowed=False``.
    evaluation_notes
        Ordered list of human-readable notes produced during evaluation.
        Mirrors ``PolicyDecisionSummary.policy_notes`` for integration with
        the legacy policy path.
    metadata
        Arbitrary additional metadata produced during evaluation.
    """

    allowed: bool = Field(description="Whether the intent is permitted.")
    reason_code: str = Field(
        default=ReasonCode.ALLOWED,
        description="Machine-readable reason code.",
    )
    reason: str = Field(
        default="",
        description="Human-readable description of the policy decision.",
    )
    conditions: list[str] = Field(
        default_factory=list,
        description="Conditions that must be met before execution.",
    )
    required_approvals: list[str] = Field(
        default_factory=list,
        description="Required approver IDs or roles.",
    )
    allowed_capabilities: list[CapabilityDescriptor] = Field(
        default_factory=list,
        description="Candidate capabilities that passed all policy checks.",
    )
    evaluation_notes: list[str] = Field(
        default_factory=list,
        description="Ordered evaluation notes for debugging.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary additional metadata.",
    )

    @classmethod
    def deny(
        cls,
        reason_code: str,
        reason: str,
        *,
        evaluation_notes: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "PolicyResult":
        """Factory for a denial result."""
        return cls(
            allowed=False,
            reason_code=reason_code,
            reason=reason,
            evaluation_notes=evaluation_notes or [],
            metadata=metadata or {},
        )

    @classmethod
    def allow(
        cls,
        allowed_capabilities: list[CapabilityDescriptor],
        *,
        conditions: list[str] | None = None,
        required_approvals: list[str] | None = None,
        evaluation_notes: list[str] | None = None,
    ) -> "PolicyResult":
        """Factory for an allow result."""
        return cls(
            allowed=True,
            reason_code=ReasonCode.ALLOWED,
            reason="Policy evaluation passed.",
            allowed_capabilities=allowed_capabilities,
            conditions=conditions or [],
            required_approvals=required_approvals or [],
            evaluation_notes=evaluation_notes or [],
        )


# ---------------------------------------------------------------------------
# PolicyEngineInterface ABC
# ---------------------------------------------------------------------------


class PolicyEngineInterface(ABC):
    """Abstract base class for SIP policy engines.

    Concrete implementations must:

    1. Accept a ``NormalizedIntent`` and a list of ``CapabilityDescriptor``
       candidates (externally supplied – the engine must never perform
       discovery itself).
    2. Return a ``PolicyResult`` with ``allowed`` reflecting whether any
       safe execution path exists.
    3. **Fail closed**: if evaluation cannot complete for any reason, the
       implementation must return ``PolicyResult.deny(...)`` rather than
       raising an exception or returning ``allowed=True``.
    4. Never mutate the inputs.
    """

    @abstractmethod
    def evaluate(
        self,
        normalized_intent: "sip.core.normalized_intent.NormalizedIntent",  # type: ignore[name-defined]
        candidates: list[CapabilityDescriptor],
    ) -> PolicyResult:
        """Evaluate policy for the given intent against the candidate capabilities.

        Args:
            normalized_intent: The canonical internal intent to evaluate.
            candidates: Externally supplied candidate capabilities to filter.

        Returns:
            A ``PolicyResult``.  Must never raise; fail closed on errors.
        """
        ...
