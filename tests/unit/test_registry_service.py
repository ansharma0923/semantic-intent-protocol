"""Unit tests for the capability registry service."""

from __future__ import annotations

import pytest

from sip.envelope.models import BindingType, OperationClass, TrustLevel
from sip.registry.bootstrap import build_seeded_registry, seed_registry
from sip.registry.models import (
    CapabilityDescriptor,
    ProviderMetadata,
    RiskLevel,
    SchemaReference,
)
from sip.registry.service import CapabilityRegistryService
from sip.registry.storage import InMemoryCapabilityStore


def make_capability(
    capability_id: str = "test_cap",
    operation_class: OperationClass = OperationClass.READ,
    bindings: list[BindingType] | None = None,
    trust_tier: TrustLevel = TrustLevel.INTERNAL,
    domains: list[str] | None = None,
) -> CapabilityDescriptor:
    return CapabilityDescriptor(
        capability_id=capability_id,
        name=f"Test {capability_id}",
        description="A test capability.",
        provider=ProviderMetadata(provider_id="test_provider", provider_name="Test Provider"),
        intent_domains=domains or ["test_domain"],
        input_schema=SchemaReference(description="Input"),
        output_schema=SchemaReference(description="Output"),
        operation_class=operation_class,
        risk_level=RiskLevel.LOW,
        required_scopes=[],
        minimum_trust_tier=trust_tier,
        supported_bindings=bindings or [BindingType.REST],
    )


class TestInMemoryCapabilityStore:
    def test_put_and_get(self) -> None:
        store = InMemoryCapabilityStore()
        cap = make_capability("cap1")
        store.put(cap)
        assert store.get("cap1") is cap

    def test_get_missing_returns_none(self) -> None:
        store = InMemoryCapabilityStore()
        assert store.get("missing") is None

    def test_delete_existing(self) -> None:
        store = InMemoryCapabilityStore()
        cap = make_capability("cap1")
        store.put(cap)
        assert store.delete("cap1") is True
        assert store.get("cap1") is None

    def test_delete_missing_returns_false(self) -> None:
        store = InMemoryCapabilityStore()
        assert store.delete("missing") is False

    def test_list_all(self) -> None:
        store = InMemoryCapabilityStore()
        store.put(make_capability("a"))
        store.put(make_capability("b"))
        assert len(store.list_all()) == 2

    def test_count(self) -> None:
        store = InMemoryCapabilityStore()
        assert store.count() == 0
        store.put(make_capability("a"))
        assert store.count() == 1

    def test_clear(self) -> None:
        store = InMemoryCapabilityStore()
        store.put(make_capability("a"))
        store.clear()
        assert store.count() == 0


class TestRegistryService:
    def test_register_and_get(self) -> None:
        registry = CapabilityRegistryService()
        cap = make_capability("cap1")
        registry.register(cap)
        assert registry.get_by_id("cap1") is cap

    def test_unregister(self) -> None:
        registry = CapabilityRegistryService()
        registry.register(make_capability("cap1"))
        assert registry.unregister("cap1") is True
        assert registry.get_by_id("cap1") is None

    def test_list_all(self) -> None:
        registry = CapabilityRegistryService()
        registry.register(make_capability("a"))
        registry.register(make_capability("b"))
        assert registry.count() == 2

    def test_search_by_name(self) -> None:
        registry = CapabilityRegistryService()
        registry.register(make_capability("retrieve_document"))
        registry.register(make_capability("book_table"))
        results = registry.search_by_name("retrieve")
        assert len(results) == 1
        assert results[0].capability_id == "retrieve_document"

    def test_search_by_domain(self) -> None:
        registry = CapabilityRegistryService()
        registry.register(make_capability("cap1", domains=["knowledge_management"]))
        registry.register(make_capability("cap2", domains=["booking"]))
        results = registry.search_by_domain("knowledge")
        assert len(results) == 1

    def test_filter_by_binding(self) -> None:
        registry = CapabilityRegistryService()
        registry.register(make_capability("rest_cap", bindings=[BindingType.REST]))
        registry.register(make_capability("grpc_cap", bindings=[BindingType.GRPC]))
        results = registry.filter_by_binding(BindingType.REST)
        assert all(BindingType.REST in cap.supported_bindings for cap in results)

    def test_filter_by_trust_tier(self) -> None:
        registry = CapabilityRegistryService()
        registry.register(make_capability("public_cap", trust_tier=TrustLevel.PUBLIC))
        registry.register(make_capability("priv_cap", trust_tier=TrustLevel.PRIVILEGED))
        # Internal trust actor should see public and internal, not privileged
        results = registry.filter_by_trust_tier(TrustLevel.INTERNAL)
        ids = [r.capability_id for r in results]
        assert "public_cap" in ids
        assert "priv_cap" not in ids

    def test_find_matches_exact_name(self) -> None:
        registry = CapabilityRegistryService()
        registry.register(make_capability("retrieve_document", domains=["knowledge_management"]))
        registry.register(make_capability("book_table", domains=["booking"]))
        ranked = registry.find_matches(
            intent_name="retrieve_document",
            intent_domain="knowledge_management",
            operation_class=OperationClass.READ,
            actor_trust=TrustLevel.INTERNAL,
        )
        assert len(ranked) >= 1
        assert ranked[0][0].capability_id == "retrieve_document"

    def test_find_matches_excludes_higher_trust(self) -> None:
        registry = CapabilityRegistryService()
        registry.register(
            make_capability("priv_cap", trust_tier=TrustLevel.PRIVILEGED, domains=["admin"])
        )
        ranked = registry.find_matches(
            intent_name="priv_cap",
            intent_domain="admin",
            operation_class=OperationClass.READ,
            actor_trust=TrustLevel.INTERNAL,
        )
        assert all(r[0].capability_id != "priv_cap" for r in ranked)

    def test_find_matches_prefers_preferred_binding(self) -> None:
        registry = CapabilityRegistryService()
        cap_rest = make_capability("cap_rest", bindings=[BindingType.REST], domains=["test"])
        cap_grpc = make_capability("cap_grpc", bindings=[BindingType.GRPC], domains=["test"])
        registry.register(cap_rest)
        registry.register(cap_grpc)
        ranked = registry.find_matches(
            intent_name="cap",
            intent_domain="test",
            operation_class=OperationClass.READ,
            actor_trust=TrustLevel.INTERNAL,
            preferred_binding=BindingType.REST,
        )
        # cap_rest should score higher due to binding preference
        ids = [r[0].capability_id for r in ranked]
        rest_idx = ids.index("cap_rest") if "cap_rest" in ids else -1
        grpc_idx = ids.index("cap_grpc") if "cap_grpc" in ids else -1
        if rest_idx >= 0 and grpc_idx >= 0:
            assert rest_idx < grpc_idx


class TestRegistryBootstrap:
    def test_seeded_registry_has_capabilities(self) -> None:
        registry = build_seeded_registry()
        assert registry.count() > 0

    def test_seeded_registry_contains_expected_capabilities(self) -> None:
        registry = build_seeded_registry()
        expected = [
            "retrieve_document",
            "search_knowledge_base",
            "summarize_document",
            "reserve_table",
            "diagnose_network_issue",
            "collect_device_telemetry",
            "summarize_for_customer",
            "delegate_agent_task",
        ]
        for cap_id in expected:
            assert registry.get_by_id(cap_id) is not None, f"Missing: {cap_id}"

    def test_seed_registry_is_idempotent(self) -> None:
        registry = CapabilityRegistryService()
        seed_registry(registry)
        count1 = registry.count()
        seed_registry(registry)
        count2 = registry.count()
        assert count1 == count2
