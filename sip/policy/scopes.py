"""Scope definitions and scope checking for SIP policy enforcement."""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Well-known SIP scopes
# ---------------------------------------------------------------------------

# Read-only access to knowledge and documents
SCOPE_KNOWLEDGE_READ = "sip:knowledge:read"
# Write access to knowledge and documents
SCOPE_KNOWLEDGE_WRITE = "sip:knowledge:write"

# Read customer data
SCOPE_CUSTOMER_READ = "sip:customer:read"
# Write customer data
SCOPE_CUSTOMER_WRITE = "sip:customer:write"

# Network operations – read/diagnose
SCOPE_NETWORK_READ = "sip:network:read"
# Network operations – execute/configure
SCOPE_NETWORK_EXECUTE = "sip:network:execute"

# Booking and reservation
SCOPE_BOOKING_WRITE = "sip:booking:write"

# Agent delegation / A2A
SCOPE_AGENT_DELEGATE = "sip:agent:delegate"

# Admin / privileged operations
SCOPE_ADMIN = "sip:admin"


def check_scopes(required: list[str], granted: list[str]) -> list[str]:
    """Return the list of required scopes that are NOT granted.

    Scope hierarchy: ``sip:admin`` implicitly grants all other SIP scopes.
    This allows an admin actor to invoke any capability without needing to
    enumerate every individual scope.

    Args:
        required: Scopes required by the capability.
        granted: Scopes granted to the actor.

    Returns:
        List of missing (denied) scopes. Empty list means all scopes granted.
    """
    granted_set = set(granted)
    # Admin scope grants all sip: sub-scopes
    if SCOPE_ADMIN in granted_set:
        return []
    return [scope for scope in required if scope not in granted_set]
