"""Storage backends for the capability registry.

Provides two implementations:

* ``InMemoryCapabilityStore`` – fast, ephemeral store for development and testing.
* ``JsonFileCapabilityStore``  – file-backed store that persists capabilities to a
  JSON file and reloads them on startup.  Suitable for single-process production
  deployments that do not require a database.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from sip.registry.models import CapabilityDescriptor

logger = logging.getLogger(__name__)

# Default path used by JsonFileCapabilityStore when no path is supplied and the
# environment variable SIP_CAPABILITIES_FILE is not set.
_DEFAULT_CAPABILITIES_FILE = Path("data/capabilities.json")


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


class JsonFileCapabilityStore(InMemoryCapabilityStore):
    """File-backed capability store that persists capabilities to a JSON file.

    On construction the store attempts to load existing capabilities from
    ``file_path``.  If the file does not exist the store starts empty (or
    optionally with a seed set supplied at construction).

    Every write operation (``put`` / ``delete`` / ``clear``) immediately
    flushes the current state to disk, keeping the file consistent.

    The file path can be overridden at runtime via the environment variable
    ``SIP_CAPABILITIES_FILE``.

    Args:
        file_path: Path to the JSON file.  Defaults to
            ``$SIP_CAPABILITIES_FILE`` or ``data/capabilities.json``.
    """

    def __init__(self, file_path: str | Path | None = None) -> None:
        super().__init__()
        if file_path is None:
            env_path = os.getenv("SIP_CAPABILITIES_FILE")
            self._path = Path(env_path) if env_path else _DEFAULT_CAPABILITIES_FILE
        else:
            self._path = Path(file_path)
        self._load()

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Load capabilities from the JSON file into the in-memory store."""
        if not self._path.exists():
            logger.debug("Capability file not found at %s; starting with empty store.", self._path)
            return
        try:
            raw = self._path.read_text(encoding="utf-8")
            records: list[dict] = json.loads(raw)
            for record in records:
                cap = CapabilityDescriptor.model_validate(record)
                self._store[cap.capability_id] = cap
            logger.info(
                "Loaded %d capabilities from %s", len(self._store), self._path
            )
        except Exception:
            # Log and continue with an empty store rather than crashing on startup.
            # This is intentional: a missing or corrupted capabilities file should
            # not prevent the broker from starting.  Operators should monitor logs
            # and restore the file from backup if needed.
            logger.exception("Failed to load capabilities from %s", self._path)

    def _save(self) -> None:
        """Flush the current in-memory state to the JSON file."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            payload = [
                cap.model_dump(mode="json") for cap in self._store.values()
            ]
            self._path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            logger.debug("Saved %d capabilities to %s", len(self._store), self._path)
        except Exception:
            logger.exception("Failed to save capabilities to %s", self._path)

    # ------------------------------------------------------------------
    # Override mutating methods to flush after each write
    # ------------------------------------------------------------------

    def put(self, capability: CapabilityDescriptor) -> None:
        super().put(capability)
        self._save()

    def delete(self, capability_id: str) -> bool:
        removed = super().delete(capability_id)
        if removed:
            self._save()
        return removed

    def clear(self) -> None:
        super().clear()
        self._save()

    # ------------------------------------------------------------------
    # Extra persistence API
    # ------------------------------------------------------------------

    def save(self) -> None:
        """Explicitly flush the current state to disk.

        Normally not needed because writes auto-flush, but useful when
        bootstrapping from seed data or after batch imports.
        """
        self._save()

    def reload(self) -> None:
        """Re-read the file from disk, replacing the current in-memory state."""
        self._store.clear()
        self._load()

    @property
    def file_path(self) -> Path:
        """Return the path of the backing JSON file."""
        return self._path
