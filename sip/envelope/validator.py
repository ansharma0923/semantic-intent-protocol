"""Envelope validation for the Semantic Intent Protocol.

Provides a dedicated validator that enforces protocol-level business rules
beyond what Pydantic structural validation covers.
"""

from __future__ import annotations

from dataclasses import dataclass, field

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

    return result
