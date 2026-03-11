"""External identity integration for the SIP broker HTTP API.

SIP itself never performs authentication.  Authentication is the responsibility
of the caller's infrastructure (API gateway, service mesh, reverse proxy, etc.).

This module provides a thin adapter that reads externally authenticated identity
claims from HTTP request headers and maps them into SIP ``ActorDescriptor`` and
trust context fields.

**Security notice:**
  Header-based identity mapping is only safe when the SIP broker is deployed
  *behind* a trusted gateway, API proxy, or service mesh that strips and
  re-injects these headers after authenticating the caller.  Do **not** expose
  the broker directly to untrusted clients with this feature enabled.

Configuration
-------------
Set ``SIP_TRUSTED_IDENTITY_HEADERS=true`` (or ``1`` / ``yes``) in the
environment to enable trusted header mapping.  When disabled (the default),
all identity headers are silently ignored.

Supported headers
-----------------
``X-Actor-Id``   → ``ActorDescriptor.actor_id``
``X-Actor-Type`` → ``ActorDescriptor.actor_type``  (must be a valid ActorType)
``X-Actor-Name`` → ``ActorDescriptor.name``
``X-Trust-Level``→ ``ActorDescriptor.trust_level`` (must be a valid TrustLevel)
``X-Scopes``     → ``ActorDescriptor.scopes``       (comma-separated list)

Precedence rule
---------------
When trusted identity header mapping is enabled and a header is present, the
header value **overrides** the corresponding field from the request body.  This
is logged at INFO level to maintain a clear audit trail.
"""

from __future__ import annotations

import logging
import os

from sip.envelope.models import ActorDescriptor, ActorType, TrustLevel

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_ENV_VAR = "SIP_TRUSTED_IDENTITY_HEADERS"


def is_trusted_identity_enabled() -> bool:
    """Return ``True`` when trusted identity header mapping is enabled.

    Reads the ``SIP_TRUSTED_IDENTITY_HEADERS`` environment variable.
    Accepted truthy values: ``1``, ``true``, ``yes`` (case-insensitive).
    """
    return os.getenv(_ENV_VAR, "false").lower() in ("1", "true", "yes")


# ---------------------------------------------------------------------------
# Header constants
# ---------------------------------------------------------------------------

HEADER_ACTOR_ID = "x-actor-id"
HEADER_ACTOR_TYPE = "x-actor-type"
HEADER_ACTOR_NAME = "x-actor-name"
HEADER_TRUST_LEVEL = "x-trust-level"
HEADER_SCOPES = "x-scopes"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def map_identity_headers(
    actor: ActorDescriptor,
    headers: dict[str, str],
    *,
    trusted: bool | None = None,
) -> ActorDescriptor:
    """Apply externally authenticated identity headers to an ``ActorDescriptor``.

    If trusted identity header mapping is disabled (default), the original
    ``actor`` is returned unchanged.

    When enabled, each present header overrides the corresponding field.  An
    INFO log entry is emitted for every override to maintain an audit trail.

    Args:
        actor:   The actor from the request body envelope.
        headers: HTTP request headers (keys must be lower-cased).
        trusted: Explicit override for the enabled/disabled flag.  Useful in
                 tests.  When ``None`` (default) the environment variable is
                 consulted.

    Returns:
        A new ``ActorDescriptor`` (or the original if nothing changed).
    """
    if trusted is None:
        trusted = is_trusted_identity_enabled()

    if not trusted:
        return actor

    updates: dict = {}

    actor_id = headers.get(HEADER_ACTOR_ID, "").strip()
    if actor_id and actor_id != actor.actor_id:
        logger.info(
            "Identity override: actor_id '%s' → '%s' (from %s)",
            actor.actor_id,
            actor_id,
            HEADER_ACTOR_ID,
        )
        updates["actor_id"] = actor_id

    actor_type_raw = headers.get(HEADER_ACTOR_TYPE, "").strip()
    if actor_type_raw:
        try:
            actor_type = ActorType(actor_type_raw)
            if actor_type != actor.actor_type:
                logger.info(
                    "Identity override: actor_type '%s' → '%s' (from %s)",
                    actor.actor_type,
                    actor_type,
                    HEADER_ACTOR_TYPE,
                )
                updates["actor_type"] = actor_type
        except ValueError:
            logger.warning(
                "Ignoring invalid %s header value '%s'; must be one of %s.",
                HEADER_ACTOR_TYPE,
                actor_type_raw,
                [t.value for t in ActorType],
            )

    actor_name = headers.get(HEADER_ACTOR_NAME, "").strip()
    if actor_name and actor_name != actor.name:
        logger.info(
            "Identity override: name '%s' → '%s' (from %s)",
            actor.name,
            actor_name,
            HEADER_ACTOR_NAME,
        )
        updates["name"] = actor_name

    trust_level_raw = headers.get(HEADER_TRUST_LEVEL, "").strip()
    if trust_level_raw:
        try:
            trust_level = TrustLevel(trust_level_raw)
            if trust_level != actor.trust_level:
                logger.info(
                    "Identity override: trust_level '%s' → '%s' (from %s)",
                    actor.trust_level,
                    trust_level,
                    HEADER_TRUST_LEVEL,
                )
                updates["trust_level"] = trust_level
        except ValueError:
            logger.warning(
                "Ignoring invalid %s header value '%s'; must be one of %s.",
                HEADER_TRUST_LEVEL,
                trust_level_raw,
                [t.value for t in TrustLevel],
            )

    scopes_raw = headers.get(HEADER_SCOPES, "").strip()
    if scopes_raw:
        scopes = [s.strip() for s in scopes_raw.split(",") if s.strip()]
        if scopes and set(scopes) != set(actor.scopes):
            logger.info(
                "Identity override: scopes %s → %s (from %s)",
                actor.scopes,
                scopes,
                HEADER_SCOPES,
            )
            updates["scopes"] = scopes

    if not updates:
        return actor

    return actor.model_copy(update=updates)
