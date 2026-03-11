"""Protocol extension support for SIP.

SIP objects support an optional ``extensions`` field for carrying additional
metadata that is not part of the core protocol.  Extension keys must follow
one of these naming conventions:

* ``x_<name>``   – custom / vendor-local extension  (e.g. ``x_my_field``)
* ``<vendor>.<name>`` – namespace-qualified extension (e.g. ``acme.priority``)

Reserved core field names may **not** be used as extension keys.  This ensures
that extensions can never silently override core protocol semantics.

Unknown extensions are always preserved and ignored during processing; they
never cause protocol failures.
"""

from __future__ import annotations

import re
from typing import Any

# ---------------------------------------------------------------------------
# Reserved core fields
# ---------------------------------------------------------------------------

#: Complete set of field names that are part of SIP core protocol objects.
#: Extension keys must not shadow any of these names.
RESERVED_CORE_FIELDS: frozenset[str] = frozenset(
    {
        # IntentEnvelope
        "sip_version",
        "message_type",
        "intent_id",
        "trace_id",
        "span_id",
        "timestamp",
        "actor",
        "target",
        "intent",
        "desired_outcome",
        "constraints",
        "context",
        "capability_requirements",
        "trust",
        "protocol_bindings",
        "negotiation",
        "integrity",
        "provenance",
        # CapabilityDescriptor
        "capability_id",
        "name",
        "description",
        "provider",
        "intent_domains",
        "input_schema",
        "output_schema",
        "operation_class",
        "risk_level",
        "required_scopes",
        "minimum_trust_tier",
        "supported_bindings",
        "execution",
        "examples",
        "tags",
        # NegotiationResult
        "ranked_candidates",
        "selected_capability",
        "selection_rationale",
        "requires_clarification",
        "clarification_questions",
        "allowed_bindings",
        "selected_binding",
        "policy_decision",
        # ExecutionPlan
        "plan_id",
        "grounded_parameters",
        "execution_steps",
        "policy_checks_passed",
        "approval_required",
        "trace",
        "provenance_summary",
        "deterministic_target",
        # AuditRecord
        "audit_id",
        "actor_id",
        "actor_type",
        "intent_name",
        "intent_domain",
        "selected_capability_id",
        "selected_binding",
        "action_taken",
        "policy_allowed",
        "approval_state",
        "outcome_summary",
        "notes",
        "originator",
        "submitting_actor",
        "delegation_chain",
        # Shared
        "extensions",
    }
)

# ---------------------------------------------------------------------------
# Extension key format rules
# ---------------------------------------------------------------------------

#: Valid extension key pattern:  "x_anything" OR "vendor.name" style
_EXTENSION_KEY_RE = re.compile(
    r"^(x_[a-z0-9_]+|[a-z][a-z0-9_]*\.[a-z0-9_.]+)$",
    re.IGNORECASE,
)


def validate_extension_keys(extensions: dict[str, Any]) -> dict[str, Any]:
    """Validate that extension keys follow the SIP extension key convention.

    Rules enforced:

    1. Extension keys must use ``x_<name>`` or ``<vendor>.<name>`` format.
    2. Extension keys must not shadow reserved core field names.

    Args:
        extensions: The extension dict to validate.

    Returns:
        The validated extensions dict (unchanged if valid).

    Raises:
        ValueError: If any key violates the naming rules.
    """
    for key in extensions:
        if key in RESERVED_CORE_FIELDS:
            raise ValueError(
                f"Extension key '{key}' is a reserved SIP core field name "
                "and cannot be used as an extension key."
            )
        if not _EXTENSION_KEY_RE.match(key):
            raise ValueError(
                f"Extension key '{key}' is invalid.  "
                "Extension keys must use 'x_<name>' or '<vendor>.<name>' format "
                "(e.g. 'x_my_field' or 'acme.priority')."
            )
    return extensions
