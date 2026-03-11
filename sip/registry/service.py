"""Capability registry service.

Provides high-level operations for registering, querying, and matching
capabilities. Uses deterministic, rule-based matching — no LLM calls.
"""

from __future__ import annotations

from sip.envelope.models import BindingType, OperationClass, TrustLevel
from sip.registry.models import CapabilityDescriptor
from sip.registry.storage import InMemoryCapabilityStore, JsonFileCapabilityStore

# Trust level ordering used for compatibility checks
_TRUST_ORDER = {
    TrustLevel.PUBLIC: 0,
    TrustLevel.INTERNAL: 1,
    TrustLevel.PRIVILEGED: 2,
    TrustLevel.ADMIN: 3,
}

# Union type for supported stores
_CapabilityStore = InMemoryCapabilityStore | JsonFileCapabilityStore


class CapabilityRegistryService:
    """High-level registry service for SIP capabilities.

    All matching is deterministic: based on intent name/domain, operation class,
    binding preference, and trust compatibility.

    Args:
        store: Optional storage backend.  Defaults to an ``InMemoryCapabilityStore``.
               Pass a ``JsonFileCapabilityStore`` instance to enable persistence.
    """

    def __init__(self, store: _CapabilityStore | None = None) -> None:
        self._store = store or InMemoryCapabilityStore()

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, capability: CapabilityDescriptor) -> None:
        """Register a capability. Overwrites if capability_id already exists."""
        self._store.put(capability)

    def unregister(self, capability_id: str) -> bool:
        """Remove a capability. Returns True if it was present."""
        return self._store.delete(capability_id)

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def get_by_id(self, capability_id: str) -> CapabilityDescriptor | None:
        """Retrieve a capability by its unique ID."""
        return self._store.get(capability_id)

    def list_all(self) -> list[CapabilityDescriptor]:
        """Return all registered capabilities."""
        return self._store.list_all()

    def count(self) -> int:
        """Return the total number of registered capabilities."""
        return self._store.count()

    # ------------------------------------------------------------------
    # Search and filter
    # ------------------------------------------------------------------

    def search_by_name(self, query: str) -> list[CapabilityDescriptor]:
        """Return capabilities whose name or capability_id contains query (case-insensitive)."""
        q = query.lower()
        return [
            cap
            for cap in self._store.list_all()
            if q in cap.name.lower() or q in cap.capability_id.lower()
        ]

    def search_by_domain(self, domain: str) -> list[CapabilityDescriptor]:
        """Return capabilities that serve the given intent domain."""
        d = domain.lower()
        return [
            cap
            for cap in self._store.list_all()
            if any(d in cd.lower() for cd in cap.intent_domains)
        ]

    def filter_by_binding(self, binding: BindingType) -> list[CapabilityDescriptor]:
        """Return capabilities that support the given binding type."""
        return [
            cap
            for cap in self._store.list_all()
            if binding in cap.supported_bindings
        ]

    def filter_by_trust_tier(
        self, max_trust: TrustLevel
    ) -> list[CapabilityDescriptor]:
        """Return capabilities whose minimum_trust_tier is ≤ max_trust."""
        max_order = _TRUST_ORDER.get(max_trust, 0)
        return [
            cap
            for cap in self._store.list_all()
            if _TRUST_ORDER.get(cap.minimum_trust_tier, 0) <= max_order
        ]

    # ------------------------------------------------------------------
    # Ranked matching
    # ------------------------------------------------------------------

    def find_matches(
        self,
        intent_name: str,
        intent_domain: str,
        operation_class: OperationClass,
        actor_trust: TrustLevel,
        preferred_binding: BindingType | None = None,
        candidate_ids: list[str] | None = None,
        max_results: int = 5,
    ) -> list[tuple[CapabilityDescriptor, float]]:
        """Return ranked (capability, score) pairs for the given intent.

        Scoring algorithm (deterministic, additive):
          +3.0  intent_name exactly matches capability_id
          +2.0  intent_name appears in capability_id or name (substring)
          +2.0  intent_domain matches one of the capability's domains exactly
          +1.0  intent_domain appears in one of the capability's domains
          +2.0  operation_class matches capability operation_class
          +1.5  preferred_binding is in capability supported_bindings
          +0.5  capability is in candidate_ids (caller hint)
          - inf capability requires higher trust than actor has (excluded)

        Args:
            intent_name: Machine-readable intent name from the envelope.
            intent_domain: Functional domain from the envelope.
            operation_class: Operation class from the envelope.
            actor_trust: Trust level of the requesting actor.
            preferred_binding: Optional preferred binding type.
            candidate_ids: Optional list of preferred capability IDs.
            max_results: Maximum number of results to return.

        Returns:
            List of (CapabilityDescriptor, score) tuples, sorted descending by score.
        """
        actor_trust_order = _TRUST_ORDER.get(actor_trust, 0)
        candidates = self._store.list_all()
        scored: list[tuple[CapabilityDescriptor, float]] = []

        for cap in candidates:
            # Exclude capabilities that require higher trust than actor has
            if _TRUST_ORDER.get(cap.minimum_trust_tier, 0) > actor_trust_order:
                continue

            score = 0.0
            has_name_or_domain_signal = False

            # Intent name matching
            if intent_name.lower() == cap.capability_id.lower():
                score += 3.0
                has_name_or_domain_signal = True
            elif (
                intent_name.lower() in cap.capability_id.lower()
                or intent_name.lower() in cap.name.lower()
            ):
                score += 2.0
                has_name_or_domain_signal = True

            # Domain matching
            domains_lower = [d.lower() for d in cap.intent_domains]
            if intent_domain.lower() in domains_lower:
                score += 2.0
                has_name_or_domain_signal = True
            elif any(intent_domain.lower() in d for d in domains_lower):
                score += 1.0
                has_name_or_domain_signal = True

            # Only continue scoring if there's at least one name/domain signal
            if not has_name_or_domain_signal:
                continue

            # Operation class matching
            if cap.operation_class == operation_class:
                score += 2.0

            # Binding preference
            if preferred_binding and preferred_binding in cap.supported_bindings:
                score += 1.5

            # Caller hint
            if candidate_ids and cap.capability_id in candidate_ids:
                score += 0.5

            if score > 0:
                scored.append((cap, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:max_results]
