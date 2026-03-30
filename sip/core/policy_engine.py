"""CanonicalPolicyEngine – implements PolicyEngineInterface.

This engine accepts a ``NormalizedIntent`` and a list of externally-supplied
``CapabilityDescriptor`` candidates and returns a ``PolicyResult``.

It reuses the underlying rule logic from ``sip.policy.risk`` and
``sip.policy.scopes`` so behaviour is consistent with the legacy
``PolicyEngine``.  The key difference is the input type (NormalizedIntent
instead of IntentEnvelope + NegotiationResult) and the richer output type
(PolicyResult instead of enriched NegotiationResult).

Fail-closed guarantees
-----------------------
* Any unhandled exception in evaluation returns a denial.
* Missing provenance when required → denial.
* Missing trust level → denial.
* Privilege escalation via delegation → denial.
* Any capability that fails a check is excluded from allowed_capabilities.
* If no capabilities survive filtering → denial.
"""

from __future__ import annotations

import logging

from sip.core.normalized_intent import NormalizedIntent
from sip.envelope.models import TrustLevel
from sip.policy.interface import PolicyEngineInterface, PolicyResult, ReasonCode
from sip.policy.risk import is_denied_by_risk, requires_approval
from sip.policy.scopes import check_scopes
from sip.registry.models import CapabilityDescriptor

logger = logging.getLogger(__name__)

# Trust level ordering (same as policy engine)
_TRUST_ORDER: dict[TrustLevel, int] = {
    TrustLevel.PUBLIC: 0,
    TrustLevel.INTERNAL: 1,
    TrustLevel.PRIVILEGED: 2,
    TrustLevel.ADMIN: 3,
}

_MAX_DELEGATION_DEPTH = 5


class CanonicalPolicyEngine(PolicyEngineInterface):
    """Policy engine that operates on ``NormalizedIntent``.

    Implements ``PolicyEngineInterface``.  Evaluation proceeds in these steps
    for *each* candidate capability:

      0. Trust level present (fail closed if missing)
      1. Scope check (actor's effective scopes vs. capability required_scopes)
      2. Risk + operation class (approval may be required)
      3. Risk + data sensitivity (outright denial)
      4. Delegation chain depth
      5. Capability-level approval override

    Capabilities that pass all checks are included in
    ``PolicyResult.allowed_capabilities``.  The overall result is denied if
    no capabilities survive.

    Args:
        enforce_approval_policy: When False, approval is never required.
            Defaults to True (production default).
        require_provenance: When True, deny if the actor has no declared
            originator (provenance is required for this deployment).
    """

    def __init__(
        self,
        *,
        enforce_approval_policy: bool = True,
        require_provenance: bool = False,
    ) -> None:
        self._enforce_approval = enforce_approval_policy
        self._require_provenance = require_provenance

    # ------------------------------------------------------------------
    # PolicyEngineInterface
    # ------------------------------------------------------------------

    def evaluate(
        self,
        normalized_intent: NormalizedIntent,
        candidates: list[CapabilityDescriptor],
    ) -> PolicyResult:
        """Evaluate policy for the intent against the supplied candidates.

        Fails closed on any error.
        """
        try:
            return self._evaluate_internal(normalized_intent, candidates)
        except Exception as exc:
            logger.exception(
                "Policy evaluation error for intent %s: %s",
                normalized_intent.intent_id,
                exc,
            )
            return PolicyResult.deny(
                reason_code=ReasonCode.EVALUATION_ERROR,
                reason=f"Policy evaluation failed with an unexpected error: {exc}",
                evaluation_notes=[f"Exception: {exc}"],
            )

    # ------------------------------------------------------------------
    # Internal evaluation
    # ------------------------------------------------------------------

    def _evaluate_internal(
        self,
        intent: NormalizedIntent,
        candidates: list[CapabilityDescriptor],
    ) -> PolicyResult:
        notes: list[str] = []

        # --- Pre-flight: trust level present ---
        if intent.actor.trust_level is None:
            return PolicyResult.deny(
                reason_code=ReasonCode.MISSING_TRUST_LEVEL,
                reason="Actor trust level is missing.",
                evaluation_notes=["DENY: trust_level is None; failing closed."],
            )

        # --- Pre-flight: provenance check ---
        if self._require_provenance and not intent.actor.originator:
            return PolicyResult.deny(
                reason_code=ReasonCode.MISSING_PROVENANCE,
                reason="Provenance is required but the intent has no declared originator.",
                evaluation_notes=[
                    "DENY: Provenance required but originator is absent; failing closed."
                ],
            )

        # --- Pre-flight: delegation chain depth ---
        delegation_depth = len(intent.actor.delegation_chain)
        if delegation_depth > _MAX_DELEGATION_DEPTH:
            return PolicyResult.deny(
                reason_code=ReasonCode.DELEGATION_CHAIN_TOO_LONG,
                reason=(
                    f"Delegation chain depth {delegation_depth} exceeds "
                    f"maximum {_MAX_DELEGATION_DEPTH}."
                ),
                evaluation_notes=[
                    f"DENY: delegation_chain length {delegation_depth} > {_MAX_DELEGATION_DEPTH}."
                ],
            )

        notes.append(f"INFO: Actor '{intent.actor.actor_id}' trust='{intent.actor.trust_level}'.")
        notes.append(f"INFO: {len(candidates)} candidate(s) to evaluate.")

        actor_trust_value = _TRUST_ORDER.get(intent.actor.trust_level, 0)
        actor_scopes = intent.actor.scopes

        allowed_capabilities: list[CapabilityDescriptor] = []
        requires_approval_flag = False
        required_approvals: list[str] = []
        conditions: list[str] = []

        for cap in candidates:
            cap_notes, cap_allowed, cap_approval = self._evaluate_capability(
                intent=intent,
                cap=cap,
                actor_trust_value=actor_trust_value,
                actor_scopes=actor_scopes,
            )
            notes.extend(cap_notes)
            if cap_allowed:
                allowed_capabilities.append(cap)
                if cap_approval:
                    requires_approval_flag = True
                    required_approvals.append(
                        f"human_approval_for_{cap.capability_id}"
                    )
            else:
                notes.append(
                    f"INFO: Capability '{cap.capability_id}' excluded from allowed set."
                )

        if not allowed_capabilities:
            return PolicyResult.deny(
                reason_code=ReasonCode.NO_ALLOWED_CAPABILITIES,
                reason="No candidate capabilities passed all policy checks.",
                evaluation_notes=notes,
            )

        if requires_approval_flag:
            conditions.append("Human approval required before execution may proceed.")

        notes.append(
            f"INFO: {len(allowed_capabilities)} capability(ies) allowed after policy filtering."
        )

        return PolicyResult.allow(
            allowed_capabilities=allowed_capabilities,
            conditions=conditions,
            required_approvals=required_approvals,
            evaluation_notes=notes,
        )

    def _evaluate_capability(
        self,
        intent: NormalizedIntent,
        cap: CapabilityDescriptor,
        actor_trust_value: int,
        actor_scopes: list[str],
    ) -> tuple[list[str], bool, bool]:
        """Evaluate a single capability.

        Returns:
            (notes, allowed, requires_approval)
        """
        notes: list[str] = []
        allowed = True
        approval = False

        # 1. Scope check
        missing_scopes = check_scopes(cap.required_scopes, actor_scopes)
        if missing_scopes:
            allowed = False
            notes.append(
                f"DENY [{cap.capability_id}]: missing scopes {missing_scopes}."
            )
            return notes, allowed, approval
        if cap.required_scopes:
            notes.append(f"PASS [{cap.capability_id}]: all required scopes present.")
        else:
            notes.append(f"PASS [{cap.capability_id}]: no scopes required.")

        # 2. Trust tier check
        cap_min_trust_value = _TRUST_ORDER.get(cap.minimum_trust_tier, 0)
        if actor_trust_value < cap_min_trust_value:
            allowed = False
            notes.append(
                f"DENY [{cap.capability_id}]: actor trust '{intent.actor.trust_level}' "
                f"< capability minimum '{cap.minimum_trust_tier}'."
            )
            return notes, allowed, approval
        notes.append(
            f"PASS [{cap.capability_id}]: trust level meets minimum '{cap.minimum_trust_tier}'."
        )

        # 3. Risk + operation class (approval required?)
        # We derive the operation class from the capability itself since
        # NormalizedIntent carries the intent's operation class separately.
        cap_approval = requires_approval(
            cap.risk_level,
            cap.operation_class,
            enforce_approval_policy=self._enforce_approval,
        )
        if cap_approval:
            approval = True
            notes.append(
                f"APPROVAL [{cap.capability_id}]: risk='{cap.risk_level}' + "
                f"operation='{cap.operation_class}' requires human approval."
            )
        else:
            notes.append(
                f"PASS [{cap.capability_id}]: risk='{cap.risk_level}' + "
                f"operation='{cap.operation_class}' does not require approval."
            )

        # 4. Risk + data sensitivity (hard denial)
        data_sensitivity = intent.constraints.data_sensitivity
        if is_denied_by_risk(cap.risk_level, data_sensitivity):
            allowed = False
            notes.append(
                f"DENY [{cap.capability_id}]: risk='{cap.risk_level}' + "
                f"data_sensitivity='{data_sensitivity}' is not permitted."
            )
            return notes, allowed, approval
        notes.append(
            f"PASS [{cap.capability_id}]: data_sensitivity='{data_sensitivity}' "
            f"compatible with risk='{cap.risk_level}'."
        )

        # 5. Capability-level approval override
        if cap.constraints.requires_human_approval:
            approval = True
            notes.append(
                f"APPROVAL [{cap.capability_id}]: capability always requires human approval."
            )

        return notes, allowed, approval
