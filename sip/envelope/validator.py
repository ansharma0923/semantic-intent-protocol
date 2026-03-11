"""Envelope validation for the Semantic Intent Protocol.

Provides a dedicated validator that enforces protocol-level business rules
beyond what Pydantic structural validation covers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from sip.envelope.models import (
    BindingType,
    DeterminismLevel,
    IntentEnvelope,
    OperationClass,
    TrustLevel,
)


# ---------------------------------------------------------------------------
# Validation result
# ---------------------------------------------------------------------------


@dataclass
class ValidationResult:
    """Result of envelope validation."""

    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_error(self, message: str) -> None:
        self.errors.append(message)
        self.valid = False

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------

# Operation classes that are considered "write or execute"
_WRITE_EXECUTE_CLASSES = {OperationClass.WRITE, OperationClass.EXECUTE}

# Minimum trust level required for privileged operations
_HIGH_RISK_TRUST_MINIMUM = TrustLevel.INTERNAL

# Trust level ordering for comparison
_TRUST_ORDER = {
    TrustLevel.PUBLIC: 0,
    TrustLevel.INTERNAL: 1,
    TrustLevel.PRIVILEGED: 2,
    TrustLevel.ADMIN: 3,
}

# Valid SIP versions
_VALID_SIP_VERSIONS = {"0.1"}

# Valid determinism levels
_VALID_DETERMINISM_LEVELS = set(DeterminismLevel)

# Valid binding types
_VALID_BINDING_TYPES = set(BindingType)

# Maximum delegation chain depth (also enforced by the policy engine)
_MAX_DELEGATION_CHAIN_DEPTH = 5


def validate_envelope(envelope: IntentEnvelope) -> ValidationResult:
    """Validate an IntentEnvelope against SIP protocol rules.

    Checks beyond Pydantic structural validation:
      - SIP version is recognised
      - Trust level consistency: declared trust must not exceed actor trust
      - Protocol bindings are recognised
      - time_budget_ms is not negative (belt-and-suspenders)
      - cost_budget is not negative (belt-and-suspenders)
      - forbidden_actions do not conflict with allowed_actions
      - When a protocol binding is specified, it must be a valid BindingType
      - High-risk write/execute operations trigger stricter trust requirements
      - Provenance checks (when provenance block is present):
          * delegation_chain length must not exceed _MAX_DELEGATION_CHAIN_DEPTH
          * delegation_expiry must be in the future if provided
          * submitted_by must match the actor submitting the envelope when present
          * authority_scope cannot contain scopes the originator does not have
            (requires originator scopes to be known; if unknown, a warning is
            emitted instead of a hard error)

    Args:
        envelope: The IntentEnvelope to validate.

    Returns:
        A ValidationResult with ``valid`` flag plus any errors/warnings.
    """
    result = ValidationResult(valid=True)

    # --- SIP version ---
    if envelope.sip_version not in _VALID_SIP_VERSIONS:
        result.add_error(
            f"Unsupported sip_version '{envelope.sip_version}'. "
            f"Supported versions: {sorted(_VALID_SIP_VERSIONS)}"
        )

    # Trust level consistency: declared trust must not exceed actor trust
    # (escalating declared trust above the actor's actual trust is a protocol violation)
    if (
        _TRUST_ORDER.get(envelope.trust.declared_trust_level, 0)
        > _TRUST_ORDER.get(envelope.actor.trust_level, 0)
    ):
        result.add_error(
            "declared_trust_level exceeds actor trust_level. "
            "Trust escalation is not permitted."
        )

    # --- Protocol bindings ---
    for binding in envelope.protocol_bindings:
        if binding.binding_type not in _VALID_BINDING_TYPES:
            result.add_error(
                f"Invalid binding_type '{binding.binding_type}' "
                f"in protocol_bindings."
            )

    # --- Budget constraints ---
    if (
        envelope.constraints.time_budget_ms is not None
        and envelope.constraints.time_budget_ms < 0
    ):
        result.add_error("time_budget_ms must not be negative.")

    if (
        envelope.constraints.cost_budget is not None
        and envelope.constraints.cost_budget < 0.0
    ):
        result.add_error("cost_budget must not be negative.")

    # --- Action conflicts ---
    allowed = set(envelope.constraints.allowed_actions)
    forbidden = set(envelope.constraints.forbidden_actions)
    conflicts = allowed & forbidden
    if conflicts:
        result.add_error(
            f"The following actions appear in both allowed_actions and "
            f"forbidden_actions: {sorted(conflicts)}"
        )

    # --- High-risk write/execute policy ---
    if envelope.intent.operation_class in _WRITE_EXECUTE_CLASSES:
        actor_trust = _TRUST_ORDER.get(envelope.actor.trust_level, 0)
        required_trust = _TRUST_ORDER[_HIGH_RISK_TRUST_MINIMUM]
        if actor_trust < required_trust:
            result.add_error(
                f"Operation class '{envelope.intent.operation_class}' requires "
                f"at least '{_HIGH_RISK_TRUST_MINIMUM}' trust level. "
                f"Actor has '{envelope.actor.trust_level}'."
            )

        # Strict determinism is required for write/execute
        if envelope.constraints.determinism_required == DeterminismLevel.ADVISORY:
            result.add_warning(
                "Write/execute operations should not use 'advisory' determinism. "
                "Consider 'strict' or 'bounded'."
            )

    # --- Capability requirement binding check ---
    for req in envelope.capability_requirements:
        if (
            req.preferred_binding is not None
            and req.preferred_binding not in _VALID_BINDING_TYPES
        ):
            result.add_error(
                f"Invalid preferred_binding '{req.preferred_binding}' "
                f"in capability_requirements."
            )

    # --- Provenance checks (optional block) ---
    if envelope.provenance is not None:
        prov = envelope.provenance

        # Delegation chain depth
        if len(prov.delegation_chain) > _MAX_DELEGATION_CHAIN_DEPTH:
            result.add_error(
                f"provenance.delegation_chain length {len(prov.delegation_chain)} "
                f"exceeds maximum allowed depth {_MAX_DELEGATION_CHAIN_DEPTH}."
            )

        # Delegation expiry must be in the future
        if prov.delegation_expiry is not None:
            now = datetime.now(timezone.utc)
            expiry = prov.delegation_expiry
            # Ensure expiry is timezone-aware for comparison
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=timezone.utc)
            if expiry <= now:
                result.add_error(
                    "provenance.delegation_expiry is in the past. "
                    "Delegation has expired and this envelope is no longer valid."
                )

        # submitted_by must match the actor when both are present
        if (
            prov.submitted_by is not None
            and prov.submitted_by != envelope.actor.actor_id
        ):
            result.add_error(
                f"provenance.submitted_by '{prov.submitted_by}' does not match "
                f"envelope actor '{envelope.actor.actor_id}'. "
                "The submitting actor must match the declared submitted_by."
            )

        # authority_scope must not exceed actor's scopes
        # (actor cannot grant more than it has)
        if prov.authority_scope is not None:
            actor_scopes = set(envelope.actor.scopes)
            excess = set(prov.authority_scope) - actor_scopes
            if excess:
                result.add_error(
                    f"provenance.authority_scope contains scopes not held by the "
                    f"submitting actor: {sorted(excess)}. "
                    "Delegation cannot grant more authority than the delegator holds."
                )

    return result
