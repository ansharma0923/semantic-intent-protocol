"""SIP Policy Engine.

Evaluates an IntentEnvelope + NegotiationResult against policy rules and
produces an enriched NegotiationResult with a detailed policy decision.

Policy evaluation is deterministic and rule-based — no ML or probabilistic
decisions are made here.
"""

from __future__ import annotations

import os

from sip.envelope.models import IntentEnvelope
from sip.negotiation.results import NegotiationResult, PolicyDecisionSummary
from sip.policy.risk import is_denied_by_risk, requires_approval
from sip.policy.scopes import check_scopes


class PolicyEngine:
    """Evaluates SIP policy for an intent + negotiation result.

    Policy rules applied (in order):
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

        # --- 1. Scope check ---
        actor_scopes = list(envelope.actor.scopes)
        missing_scopes = check_scopes(cap.required_scopes, actor_scopes)
        if missing_scopes:
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
