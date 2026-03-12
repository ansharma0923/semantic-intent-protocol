"""Identity and provenance helpers for the SIP Python SDK.

Convenience functions for working with actor identity headers and
provenance metadata. These wrap existing implementation modules to
provide a clean, stable public API surface.

Example::

    from sip.sdk.helpers import (
        apply_identity_headers_to_envelope,
        compute_effective_scope_set,
        summarize_provenance,
    )

    updated_envelope = apply_identity_headers_to_envelope(
        envelope, headers, trusted=True
    )
    scopes = compute_effective_scope_set(envelope)
    summary = summarize_provenance(envelope)
"""

from __future__ import annotations

from typing import Any

from sip.broker.identity import map_identity_headers
from sip.envelope.models import (
    ActorDescriptor,
    IntentEnvelope,
    ProvenanceBlock,
)


def apply_identity_headers_to_envelope(
    envelope: IntentEnvelope,
    headers: dict[str, str],
    *,
    trusted: bool | None = None,
) -> IntentEnvelope:
    """Apply externally-authenticated identity headers to an envelope's actor.

    This is the SDK-facing wrapper around :func:`sip.broker.identity.map_identity_headers`.
    When ``trusted`` is ``True`` (or when ``SIP_TRUSTED_IDENTITY_HEADERS`` is set),
    values in the HTTP headers override the actor descriptor fields from the envelope.

    **Security notice:** Only call this with ``trusted=True`` when the envelope
    comes from behind a trusted API gateway or service mesh that injects these
    headers after authenticating the caller. Never expose this to untrusted clients.

    Supported headers (lowercase keys):
    - ``x-actor-id``    → ``actor.actor_id``
    - ``x-actor-type``  → ``actor.actor_type``
    - ``x-actor-name``  → ``actor.name``
    - ``x-trust-level`` → ``actor.trust_level``
    - ``x-scopes``      → ``actor.scopes`` (comma-separated)

    Args:
        envelope: The intent envelope to update.
        headers: HTTP request headers (keys should be lower-cased).
        trusted: If ``True``, apply header overrides. If ``False``, return the
                 envelope unchanged. If ``None``, read from the
                 ``SIP_TRUSTED_IDENTITY_HEADERS`` environment variable.

    Returns:
        A new ``IntentEnvelope`` with the actor updated (if changes were made),
        or the original envelope if no changes were needed.
    """
    updated_actor = map_identity_headers(envelope.actor, headers, trusted=trusted)
    if updated_actor is envelope.actor:
        return envelope
    return envelope.model_copy(update={"actor": updated_actor})


def merge_identity_context(
    actor: ActorDescriptor,
    headers: dict[str, str],
    *,
    trusted: bool | None = None,
) -> ActorDescriptor:
    """Apply identity headers to a standalone ``ActorDescriptor``.

    This is a lower-level alternative to :func:`apply_identity_headers_to_envelope`
    for cases where you have an actor descriptor but not a full envelope.

    Args:
        actor: The actor descriptor to update.
        headers: HTTP request headers (keys should be lower-cased).
        trusted: See :func:`apply_identity_headers_to_envelope`.

    Returns:
        A new ``ActorDescriptor`` (or the original if nothing changed).
    """
    return map_identity_headers(actor, headers, trusted=trusted)


def compute_effective_scope_set(envelope: IntentEnvelope) -> frozenset[str]:
    """Compute the effective scope set for an intent envelope.

    When a ``ProvenanceBlock`` with ``authority_scope`` is present, the effective
    scopes are the intersection of the actor's scopes and the authority scope.
    Otherwise, the actor's scopes are used directly.

    This mirrors the policy engine's anti-laundering scope logic and is useful
    for pre-flight checks before submitting an intent.

    Args:
        envelope: The intent envelope to analyze.

    Returns:
        A frozenset of effective scope strings.
    """
    actor_scopes = frozenset(envelope.actor.scopes)
    prov = envelope.provenance
    if prov is not None and prov.authority_scope is not None:
        authority = frozenset(prov.authority_scope)
        return actor_scopes & authority
    return actor_scopes


def summarize_provenance(envelope: IntentEnvelope) -> dict[str, Any]:
    """Return a human-readable provenance summary for an envelope.

    Produces a plain dictionary suitable for logging or display. Returns
    an empty dict if the envelope has no provenance block.

    Args:
        envelope: The intent envelope to summarize.

    Returns:
        A dictionary with provenance fields, or ``{}`` if no provenance.
    """
    prov: ProvenanceBlock | None = envelope.provenance
    if prov is None:
        return {}
    summary: dict[str, Any] = {
        "originator": prov.originator,
        "submitted_by": prov.submitted_by,
        "delegation_chain": list(prov.delegation_chain),
        "delegation_depth": len(prov.delegation_chain),
    }
    if prov.on_behalf_of is not None:
        summary["on_behalf_of"] = prov.on_behalf_of
    if prov.delegation_purpose is not None:
        summary["delegation_purpose"] = prov.delegation_purpose
    if prov.delegation_expiry is not None:
        summary["delegation_expiry"] = prov.delegation_expiry.isoformat()
    if prov.authority_scope is not None:
        summary["authority_scope"] = list(prov.authority_scope)
    return summary


__all__ = [
    "apply_identity_headers_to_envelope",
    "compute_effective_scope_set",
    "merge_identity_context",
    "summarize_provenance",
]
