"""In-memory storage backend for the capability registry."""

from __future__ import annotations

from sip.registry.models import CapabilityDescriptor


class InMemoryCapabilityStore:
    """Thread-safe, in-memory store for CapabilityDescriptors.

    This store is suitable for development, testing, and single-process
    deployments. For production multi-process deployments, replace with a
    persistent or distributed backend.
    """

    def __init__(self) -> None:
        self._store: dict[str, CapabilityDescriptor] = {}

    def put(self, capability: CapabilityDescriptor) -> None:
        """Store or replace a capability by its capability_id."""
        self._store[capability.capability_id] = capability

    def get(self, capability_id: str) -> CapabilityDescriptor | None:
        """Return a capability by ID, or None if not found."""
        return self._store.get(capability_id)

    def delete(self, capability_id: str) -> bool:
        """Remove a capability by ID. Returns True if it existed."""
        if capability_id in self._store:
            del self._store[capability_id]
            return True
        return False

    def list_all(self) -> list[CapabilityDescriptor]:
        """Return all stored capabilities."""
        return list(self._store.values())

    def count(self) -> int:
        """Return the number of stored capabilities."""
        return len(self._store)

    def clear(self) -> None:
        """Remove all capabilities from the store."""
        self._store.clear()
