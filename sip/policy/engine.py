"""SIP Policy Engine.

Evaluates an IntentEnvelope + NegotiationResult against policy rules and
produces an enriched NegotiationResult with a detailed policy decision.

Policy evaluation is deterministic and rule-based — no ML or probabilistic
decisions are made here.
"""

from __future__ import annotations

import os

from sip.envelope.models import IntentEnvelope, TrustLevel
from sip.negotiation.results import NegotiationResult, PolicyDecisionSummary
from sip.policy.risk import is_denied_by_risk, requires_approval
from sip.policy.scopes import check_scopes

# Trust level ordering (shared with validator but kept local to avoid circular imports)
_TRUST_ORDER = {
    TrustLevel.PUBLIC: 0,
    TrustLevel.INTERNAL: 1,
    TrustLevel.PRIVILEGED: 2,
    TrustLevel.ADMIN: 3,
}


class PolicyEngine:
    """Evaluates SIP policy for an intent + negotiation result.

    Policy rules applied (in order):
      0. Provenance / anti-laundering: when a ProvenanceBlock is present,
         compute the effective scope set as the intersection of actor scopes,
         originator scopes (if known via authority_scope), and authority_scope.
         Deny if the capability requires a scope outside the effective set.
         Also deny if the originator's declared trust level is lower than
         the minimum trust tier required by the capability (privilege
         escalation via delegation is not permitted).
      1. Scope check: actor must hold all scopes required by the capability.
      2. Risk + operation class: high-risk write/execute may require approval.
      3. Risk + data sensitivity: critical risk + restricted data is denied.
      4. Delegation depth: prevents unbounded delegation chains.

    The ``enforce_approval_policy`` flag can be set to False in non-production
    environments (e.g. via ``SIP_REQUIRE_APPROVAL_HIGH_RISK=false``).
    """

    _MAX_DELEGATION_DEPTH = 5

    def __init__(self, enforce_approval_policy: bool | None = None) -> None:
        if enforce_approval_policy is None:
            env_val = os.getenv("SIP_REQUIRE_APPROVAL_HIGH_RISK", "true").lower()
            self._enforce_approval = env_val in ("1", "true", "yes")
        else:
            self._enforce_approval = enforce_approval_policy

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_effective_scopes(
        actor_scopes: list[str],
        authority_scope: list[str] | None,
    ) -> set[str]:
        """Return the effective scope set for a delegated intent.

        The effective set is the intersection of the actor's scopes and the
        authority_scope granted by the delegating principal.  If no
        authority_scope is specified the actor's full scope set is used.
        """
        effective = set(actor_scopes)
        if authority_scope is not None:
            effective &= set(authority_scope)
        return effective

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(
        self,
        envelope: IntentEnvelope,
        negotiation: NegotiationResult,
    ) -> NegotiationResult:
        """Evaluate policy and return an enriched NegotiationResult.

        The returned result has an updated ``policy_decision`` with:
          - ``allowed``: whether the intent is permitted to proceed
          - ``requires_approval``: whether human approval is required
          - ``denied_scopes``: scopes that were required but not held
          - ``policy_notes``: human-readable notes on each policy decision

        Args:
            envelope: The intent being evaluated.
            negotiation: The negotiation result to enrich.

        Returns:
            A new NegotiationResult with an updated policy decision.
        """
        if negotiation.selected_capability is None:
            # Nothing to evaluate without a selected capability
            return negotiation

        cap = negotiation.selected_capability
        notes: list[str] = []
        denied_scopes: list[str] = []
        allowed = True
        approval_required = False

        # --- 0. Provenance / anti-laundering checks ---
        prov = envelope.provenance
        if prov is not None:
            # Compute effective scopes (intersection of actor + authority_scope)
            effective_scopes = self._compute_effective_scopes(
                list(envelope.actor.scopes),
                prov.authority_scope,
            )

            # Check required capability scopes against the effective set
            missing_via_provenance = [
                s for s in cap.required_scopes if s not in effective_scopes
            ]
            if missing_via_provenance:
                denied_scopes = missing_via_provenance
                allowed = False
                notes.append(
                    f"DENY: Effective delegated scope set does not include "
                    f"required scopes: {missing_via_provenance}. "
                    "Delegation cannot grant more authority than the originator holds."
                )
            else:
                if cap.required_scopes:
                    notes.append(
                        f"PASS: All required scopes present in effective delegated "
                        f"scope set: {cap.required_scopes}."
                    )
                else:
                    notes.append(
                        "PASS: No scopes required; provenance scope check skipped."
                    )

            # Privilege-escalation check: originator trust must be >= capability minimum
            if allowed and prov.originator is not None:
                # We use the actor's trust level as a proxy for the originator's
                # trust when we don't have a separate originator registry entry.
                # The declared_trust_level in the TrustBlock represents what the
                # envelope claims; if the originator is explicitly named we use
                # the actor's trust_level (the submitting agent must not have
                # escalated).
                #
                # For a full implementation the originator's trust level would be
                # looked up from a registry. Here we apply a conservative rule:
                # the capability's minimum_trust_tier must not exceed what the
                # declared_trust_level claims for the envelope (which must already
                # be <= actor trust per validator).
                #
                # Defaulting to 0 (PUBLIC) is intentionally safe: if a trust level
                # is somehow absent from _TRUST_ORDER it is treated as the lowest
                # tier, which means it will be denied rather than accidentally
                # granted elevated access.
                originator_trust_value = _TRUST_ORDER.get(
                    envelope.trust.declared_trust_level, 0
                )
                cap_min_trust_value = _TRUST_ORDER.get(cap.minimum_trust_tier, 0)
                if originator_trust_value < cap_min_trust_value:
                    allowed = False
                    notes.append(
                        f"DENY: Originator declared trust level "
                        f"'{envelope.trust.declared_trust_level}' is below the "
                        f"capability minimum trust tier '{cap.minimum_trust_tier}'. "
                        "Privilege escalation via delegation is not permitted."
                    )
                else:
                    notes.append(
                        f"PASS: Originator trust level "
                        f"'{envelope.trust.declared_trust_level}' meets capability "
                        f"minimum trust tier '{cap.minimum_trust_tier}'."
                    )
        else:
            # No provenance – use full actor scopes (backward-compatible path)
            notes.append("INFO: No provenance block; using actor scopes directly.")

        # --- 1. Scope check ---
        # When provenance is present we already checked the effective scope set
        # in step 0; if that check passed we run a belt-and-suspenders scope
        # check here using the same effective set to ensure denied_scopes is
        # always populated.  When there is no provenance this is the primary
        # (and only) scope check, using the actor's full scope set directly.
        # We skip this step only when step 0 already denied the request.
        if allowed:
            actor_scopes = list(envelope.actor.scopes)
            scopes_to_check = (
                list(
                    self._compute_effective_scopes(
                        actor_scopes,
                        prov.authority_scope if prov else None,
                    )
                )
                if prov
                else actor_scopes
            )
            missing_scopes = check_scopes(cap.required_scopes, scopes_to_check)
            if missing_scopes:
                if not denied_scopes:
                    denied_scopes = missing_scopes
                allowed = False
                notes.append(
                    f"DENY: Actor is missing required scopes: {missing_scopes}."
                )
            else:
                if cap.required_scopes:
                    notes.append(f"PASS: All required scopes granted: {cap.required_scopes}.")
                else:
                    notes.append("PASS: No scopes required.")

        # --- 2. Risk + operation class ---
        if allowed:
            approval = requires_approval(
                cap.risk_level,
                cap.operation_class,
                enforce_approval_policy=self._enforce_approval,
            )
            if approval:
                approval_required = True
                notes.append(
                    f"APPROVAL REQUIRED: risk_level='{cap.risk_level}' + "
                    f"operation='{cap.operation_class}' requires human approval."
                )
            else:
                notes.append(
                    f"PASS: risk_level='{cap.risk_level}' + "
                    f"operation='{cap.operation_class}' does not require approval."
                )

        # --- 3. Risk + data sensitivity ---
        if allowed:
            data_sensitivity = envelope.constraints.data_sensitivity
            if is_denied_by_risk(cap.risk_level, data_sensitivity):
                allowed = False
                notes.append(
                    f"DENY: risk_level='{cap.risk_level}' with "
                    f"data_sensitivity='{data_sensitivity}' is not permitted."
                )
            else:
                notes.append(
                    f"PASS: data_sensitivity='{data_sensitivity}' is compatible "
                    f"with risk_level='{cap.risk_level}'."
                )

        # --- 4. Delegation chain depth ---
        delegation_depth = len(envelope.trust.delegation_chain)
        if delegation_depth > self._MAX_DELEGATION_DEPTH:
            allowed = False
            notes.append(
                f"DENY: Delegation chain depth {delegation_depth} exceeds "
                f"maximum allowed {self._MAX_DELEGATION_DEPTH}."
            )
        else:
            notes.append(f"PASS: Delegation chain depth {delegation_depth} is within limits.")

        # --- 5. Capability-level approval override ---
        if allowed and cap.constraints.requires_human_approval:
            approval_required = True
            notes.append(
                "APPROVAL REQUIRED: Capability always requires human approval."
            )

        policy_decision = PolicyDecisionSummary(
            allowed=allowed,
            requires_approval=approval_required,
            denied_scopes=denied_scopes,
            policy_notes=notes,
        )

        return negotiation.model_copy(update={"policy_decision": policy_decision})
