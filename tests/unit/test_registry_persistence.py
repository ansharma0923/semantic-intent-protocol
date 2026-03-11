"""Unit tests for capability registry persistence (JsonFileCapabilityStore)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sip.envelope.models import BindingType, OperationClass, TrustLevel
from sip.registry.bootstrap import seed_registry
from sip.registry.models import (
    CapabilityDescriptor,
    ProviderMetadata,
    RiskLevel,
    SchemaReference,
)
from sip.registry.service import CapabilityRegistryService
from sip.registry.storage import JsonFileCapabilityStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_cap(cap_id: str = "test_cap") -> CapabilityDescriptor:
    return CapabilityDescriptor(
        capability_id=cap_id,
        name=f"Test {cap_id}",
        description="A test capability.",
        provider=ProviderMetadata(provider_id="prov", provider_name="Provider"),
        intent_domains=["test_domain"],
        input_schema=SchemaReference(description="Input"),
        output_schema=SchemaReference(description="Output"),
        operation_class=OperationClass.READ,
        risk_level=RiskLevel.LOW,
        required_scopes=[],
        minimum_trust_tier=TrustLevel.INTERNAL,
        supported_bindings=[BindingType.REST],
    )


# ---------------------------------------------------------------------------
# Tests: JsonFileCapabilityStore
# ---------------------------------------------------------------------------


class TestJsonFileCapabilityStore:
    def test_empty_store_on_missing_file(self, tmp_path: Path) -> None:
        store = JsonFileCapabilityStore(file_path=tmp_path / "caps.json")
        assert store.count() == 0

    def test_put_creates_file(self, tmp_path: Path) -> None:
        path = tmp_path / "caps.json"
        store = JsonFileCapabilityStore(file_path=path)
        store.put(_make_cap("cap1"))
        assert path.exists()

    def test_save_load_roundtrip(self, tmp_path: Path) -> None:
        """Capabilities saved to disk must be reloadable."""
        path = tmp_path / "caps.json"
        store1 = JsonFileCapabilityStore(file_path=path)
        cap = _make_cap("roundtrip_cap")
        store1.put(cap)

        # Reload from the same file
        store2 = JsonFileCapabilityStore(file_path=path)
        loaded = store2.get("roundtrip_cap")
        assert loaded is not None
        assert loaded.capability_id == cap.capability_id
        assert loaded.name == cap.name
        assert loaded.operation_class == cap.operation_class

    def test_multiple_capabilities_roundtrip(self, tmp_path: Path) -> None:
        path = tmp_path / "caps.json"
        store1 = JsonFileCapabilityStore(file_path=path)
        for i in range(5):
            store1.put(_make_cap(f"cap_{i}"))

        store2 = JsonFileCapabilityStore(file_path=path)
        assert store2.count() == 5
        for i in range(5):
            assert store2.get(f"cap_{i}") is not None

    def test_delete_persists(self, tmp_path: Path) -> None:
        path = tmp_path / "caps.json"
        store = JsonFileCapabilityStore(file_path=path)
        store.put(_make_cap("cap1"))
        store.put(_make_cap("cap2"))
        store.delete("cap1")

        store2 = JsonFileCapabilityStore(file_path=path)
        assert store2.get("cap1") is None
        assert store2.get("cap2") is not None

    def test_clear_persists(self, tmp_path: Path) -> None:
        path = tmp_path / "caps.json"
        store = JsonFileCapabilityStore(file_path=path)
        store.put(_make_cap("cap1"))
        store.clear()

        store2 = JsonFileCapabilityStore(file_path=path)
        assert store2.count() == 0

    def test_explicit_save_and_reload(self, tmp_path: Path) -> None:
        path = tmp_path / "caps.json"
        store = JsonFileCapabilityStore(file_path=path)
        # Directly manipulate internal state to bypass auto-save
        cap = _make_cap("manual_cap")
        store._store[cap.capability_id] = cap
        store.save()

        store2 = JsonFileCapabilityStore(file_path=path)
        assert store2.get("manual_cap") is not None

    def test_reload_replaces_in_memory_state(self, tmp_path: Path) -> None:
        path = tmp_path / "caps.json"
        store = JsonFileCapabilityStore(file_path=path)
        store.put(_make_cap("cap1"))

        # Write a different capability directly to file
        cap2 = _make_cap("cap2")
        path.write_text(
            json.dumps([cap2.model_dump(mode="json")], indent=2), encoding="utf-8"
        )

        store.reload()
        assert store.get("cap1") is None
        assert store.get("cap2") is not None

    def test_file_path_property(self, tmp_path: Path) -> None:
        path = tmp_path / "sub" / "caps.json"
        store = JsonFileCapabilityStore(file_path=path)
        assert store.file_path == path

    def test_nested_directory_created(self, tmp_path: Path) -> None:
        path = tmp_path / "a" / "b" / "c" / "caps.json"
        store = JsonFileCapabilityStore(file_path=path)
        store.put(_make_cap())
        assert path.exists()

    def test_file_content_is_valid_json_list(self, tmp_path: Path) -> None:
        path = tmp_path / "caps.json"
        store = JsonFileCapabilityStore(file_path=path)
        store.put(_make_cap("cap1"))
        raw = json.loads(path.read_text())
        assert isinstance(raw, list)
        assert len(raw) == 1
        assert raw[0]["capability_id"] == "cap1"


# ---------------------------------------------------------------------------
# Tests: CapabilityRegistryService with JsonFileCapabilityStore
# ---------------------------------------------------------------------------


class TestRegistryServiceWithPersistence:
    def test_registry_uses_file_store(self, tmp_path: Path) -> None:
        path = tmp_path / "caps.json"
        store = JsonFileCapabilityStore(file_path=path)
        registry = CapabilityRegistryService(store=store)
        registry.register(_make_cap("persistent_cap"))
        assert path.exists()
        assert registry.get_by_id("persistent_cap") is not None

    def test_registry_reloads_on_startup(self, tmp_path: Path) -> None:
        path = tmp_path / "caps.json"

        # First instance saves
        store1 = JsonFileCapabilityStore(file_path=path)
        registry1 = CapabilityRegistryService(store=store1)
        registry1.register(_make_cap("reload_cap"))

        # Second instance reloads from file
        store2 = JsonFileCapabilityStore(file_path=path)
        registry2 = CapabilityRegistryService(store=store2)
        assert registry2.get_by_id("reload_cap") is not None

    def test_seeded_registry_persisted_and_reloaded(self, tmp_path: Path) -> None:
        path = tmp_path / "caps.json"

        store1 = JsonFileCapabilityStore(file_path=path)
        registry1 = CapabilityRegistryService(store=store1)
        seed_registry(registry1)
        count_before = registry1.count()

        store2 = JsonFileCapabilityStore(file_path=path)
        registry2 = CapabilityRegistryService(store=store2)
        assert registry2.count() == count_before

    def test_env_var_configures_file_path(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        path = tmp_path / "env_caps.json"
        monkeypatch.setenv("SIP_CAPABILITIES_FILE", str(path))
        store = JsonFileCapabilityStore()  # no explicit path
        store.put(_make_cap("env_cap"))
        assert path.exists()
