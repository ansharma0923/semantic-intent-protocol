"""Unit tests for the DiscoveryService and discovery models.

Tests cover:
- DiscoveryRequest validation
- DiscoveryResponse structure
- Local discovery (list, get, discover with matches, discover with no matches)
- Invalid discovery requests
- Peer (remote) discovery aggregation (with mocked HTTP)
- Deterministic ordering
- Peer unavailable behaviour
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from sip.broker.discovery import (
    DiscoveryCandidate,
    DiscoveryRequest,
    DiscoveryResponse,
    DiscoveryService,
)
from sip.broker.federation import (
    FederatedPeer,
    FederationConfig,
    PeerTrustLevel,
)
from sip.envelope.models import BindingType, OperationClass, TrustLevel
from sip.registry.bootstrap import seed_registry
from sip.registry.models import (
    CapabilityDescriptor,
    ProviderMetadata,
    SchemaReference,
)
from sip.registry.service import CapabilityRegistryService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def seeded_registry() -> CapabilityRegistryService:
    reg = CapabilityRegistryService()
    seed_registry(reg)
    return reg


@pytest.fixture
def discovery_service(seeded_registry: CapabilityRegistryService) -> DiscoveryService:
    return DiscoveryService(registry=seeded_registry)


# ---------------------------------------------------------------------------
# DiscoveryRequest validation
# ---------------------------------------------------------------------------


class TestDiscoveryRequestValidation:
    def test_empty_request_is_valid(self) -> None:
        req = DiscoveryRequest()
        assert req.intent_name is None
        assert req.max_results == 5
        assert req.include_remote is True

    def test_max_results_minimum(self) -> None:
        with pytest.raises(Exception):
            DiscoveryRequest(max_results=0)

    def test_max_results_maximum(self) -> None:
        with pytest.raises(Exception):
            DiscoveryRequest(max_results=101)

    def test_full_request_is_valid(self) -> None:
        req = DiscoveryRequest(
            intent_name="retrieve_document",
            intent_domain="knowledge_management",
            operation_class=OperationClass.RETRIEVE,
            preferred_bindings=[BindingType.REST],
            candidate_capabilities=["retrieve_document"],
            trust_level=TrustLevel.INTERNAL,
            max_results=3,
            include_remote=False,
        )
        assert req.intent_name == "retrieve_document"
        assert req.max_results == 3

    def test_operation_class_can_be_none(self) -> None:
        req = DiscoveryRequest(intent_name="foo")
        assert req.operation_class is None


# ---------------------------------------------------------------------------
# Local discovery: list all capabilities
# ---------------------------------------------------------------------------


class TestDiscoverLocal:
    def test_empty_request_returns_all_capabilities(
        self, seeded_registry: CapabilityRegistryService
    ) -> None:
        svc = DiscoveryService(registry=seeded_registry)
        resp = svc.discover(DiscoveryRequest(max_results=100))
        assert resp.total == seeded_registry.count()

    def test_discover_with_intent_name_returns_match(
        self, discovery_service: DiscoveryService
    ) -> None:
        req = DiscoveryRequest(
            intent_name="retrieve_document",
            intent_domain="knowledge_management",
            operation_class=OperationClass.RETRIEVE,
        )
        resp = discovery_service.discover(req)
        assert resp.total > 0
        ids = [c.capability_id for c in resp.candidates]
        assert "retrieve_document" in ids

    def test_discover_with_no_matching_intent_name(
        self, discovery_service: DiscoveryService
    ) -> None:
        req = DiscoveryRequest(
            intent_name="nonexistent_zxqwerty",
            intent_domain="nonexistent_domain_zxqwerty",
            operation_class=OperationClass.WRITE,
        )
        resp = discovery_service.discover(req)
        assert resp.total == 0

    def test_max_results_honoured(
        self, seeded_registry: CapabilityRegistryService
    ) -> None:
        svc = DiscoveryService(registry=seeded_registry)
        resp = svc.discover(DiscoveryRequest(max_results=2))
        assert resp.total <= 2

    def test_local_candidates_have_no_source_broker_id(
        self, discovery_service: DiscoveryService
    ) -> None:
        resp = discovery_service.discover(DiscoveryRequest(max_results=100))
        for c in resp.candidates:
            assert c.source_broker_id is None

    def test_local_candidates_routing_allowed_true(
        self, discovery_service: DiscoveryService
    ) -> None:
        resp = discovery_service.discover(DiscoveryRequest(max_results=100))
        for c in resp.candidates:
            assert c.routing_allowed is True

    def test_response_counts_are_accurate(
        self, discovery_service: DiscoveryService
    ) -> None:
        resp = discovery_service.discover(DiscoveryRequest(max_results=100))
        assert resp.local_count == resp.total
        assert resp.remote_count == 0

    def test_discovery_response_has_no_peer_data_without_federation(
        self, discovery_service: DiscoveryService
    ) -> None:
        resp = discovery_service.discover(DiscoveryRequest())
        assert resp.peers_queried == []
        assert resp.peers_failed == []


# ---------------------------------------------------------------------------
# Peer (distributed broker) discovery
# ---------------------------------------------------------------------------


def _make_peer_response_json(cap_id: str = "remote_cap") -> dict:
    """Build a minimal discovery response as if from a peer broker."""
    return {
        "candidates": [
            {
                "capability_id": cap_id,
                "name": "Remote Capability",
                "description": "A capability on a remote broker",
                "operation_class": "retrieve",
                "supported_bindings": ["rest"],
                "intent_domains": ["knowledge_management"],
                "minimum_trust_tier": "internal",
                "score": 5.0,
                "source_broker_id": None,
                "source_broker_url": None,
                "routing_allowed": True,
                "discovery_path": [],
                "extensions": {},
            }
        ],
        "total": 1,
        "local_count": 1,
        "remote_count": 0,
        "peers_queried": [],
        "peers_failed": [],
    }


@pytest.fixture
def federation_config() -> FederationConfig:
    return FederationConfig(
        broker_id="broker-a",
        broker_url="http://localhost:8000",
        peers=[
            FederatedPeer(
                broker_id="broker-b",
                broker_url="http://localhost:8001",
                trust_level=PeerTrustLevel.ROUTING,
            )
        ],
    )


@pytest.fixture
def federated_discovery_service(
    seeded_registry: CapabilityRegistryService,
    federation_config: FederationConfig,
) -> DiscoveryService:
    return DiscoveryService(
        registry=seeded_registry,
        federation=federation_config,
    )


class TestPeerDiscovery:
    def test_peer_discovery_returns_remote_candidates(
        self,
        federated_discovery_service: DiscoveryService,
    ) -> None:
        peer_resp = _make_peer_response_json("remote_retrieve")
        mock_resp = MagicMock()
        mock_resp.json.return_value = peer_resp
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.post", return_value=mock_resp):
            resp = federated_discovery_service.discover(
                DiscoveryRequest(include_remote=True, max_results=100)
            )

        remote = [c for c in resp.candidates if c.source_broker_id is not None]
        assert len(remote) == 1
        assert remote[0].capability_id == "remote_retrieve"
        assert remote[0].source_broker_id == "broker-b"

    def test_peer_discovery_tags_source_broker_url(
        self,
        federated_discovery_service: DiscoveryService,
    ) -> None:
        peer_resp = _make_peer_response_json()
        mock_resp = MagicMock()
        mock_resp.json.return_value = peer_resp
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.post", return_value=mock_resp):
            resp = federated_discovery_service.discover(
                DiscoveryRequest(include_remote=True, max_results=100)
            )

        remote = [c for c in resp.candidates if c.source_broker_id is not None]
        assert remote[0].source_broker_url == "http://localhost:8001"

    def test_routing_peer_capabilities_are_routing_allowed(
        self,
        federated_discovery_service: DiscoveryService,
    ) -> None:
        peer_resp = _make_peer_response_json()
        mock_resp = MagicMock()
        mock_resp.json.return_value = peer_resp
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.post", return_value=mock_resp):
            resp = federated_discovery_service.discover(
                DiscoveryRequest(include_remote=True, max_results=100)
            )

        remote = [c for c in resp.candidates if c.source_broker_id is not None]
        # Peer is ROUTING trust level → routing_allowed=True
        assert all(c.routing_allowed for c in remote)

    def test_discovery_only_peer_capabilities_not_routing_allowed(
        self,
        seeded_registry: CapabilityRegistryService,
    ) -> None:
        config = FederationConfig(
            broker_id="broker-a",
            broker_url="http://localhost:8000",
            peers=[
                FederatedPeer(
                    broker_id="broker-c",
                    broker_url="http://localhost:8002",
                    trust_level=PeerTrustLevel.DISCOVERY,
                )
            ],
        )
        svc = DiscoveryService(registry=seeded_registry, federation=config)

        peer_resp = _make_peer_response_json()
        mock_resp = MagicMock()
        mock_resp.json.return_value = peer_resp
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.post", return_value=mock_resp):
            resp = svc.discover(DiscoveryRequest(include_remote=True, max_results=100))

        remote = [c for c in resp.candidates if c.source_broker_id is not None]
        assert all(not c.routing_allowed for c in remote)

    def test_include_remote_false_skips_peers(
        self,
        federated_discovery_service: DiscoveryService,
    ) -> None:
        with patch("httpx.post") as mock_post:
            resp = federated_discovery_service.discover(
                DiscoveryRequest(include_remote=False)
            )
            mock_post.assert_not_called()
        assert resp.remote_count == 0

    def test_peer_unavailable_soft_mode_logged_and_skipped(
        self,
        federated_discovery_service: DiscoveryService,
    ) -> None:
        with patch("httpx.post", side_effect=ConnectionError("refused")):
            resp = federated_discovery_service.discover(DiscoveryRequest())
        # Should not raise; failed peers listed
        assert "broker-b" in resp.peers_failed
        assert resp.remote_count == 0

    def test_peer_unavailable_strict_mode_raises(
        self,
        seeded_registry: CapabilityRegistryService,
    ) -> None:
        strict_config = FederationConfig(
            broker_id="broker-a",
            broker_url="http://localhost:8000",
            strict_mode=True,
            peers=[
                FederatedPeer(
                    broker_id="broker-b",
                    broker_url="http://localhost:8001",
                    trust_level=PeerTrustLevel.ROUTING,
                )
            ],
        )
        svc = DiscoveryService(registry=seeded_registry, federation=strict_config)

        with patch("httpx.post", side_effect=ConnectionError("refused")):
            with pytest.raises(RuntimeError, match="unavailable"):
                svc.discover(DiscoveryRequest())

    def test_peers_queried_list_populated(
        self,
        federated_discovery_service: DiscoveryService,
    ) -> None:
        peer_resp = _make_peer_response_json()
        mock_resp = MagicMock()
        mock_resp.json.return_value = peer_resp
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.post", return_value=mock_resp):
            resp = federated_discovery_service.discover(
                DiscoveryRequest(max_results=100)
            )

        assert "broker-b" in resp.peers_queried


# ---------------------------------------------------------------------------
# Deterministic ordering
# ---------------------------------------------------------------------------


class TestDeterministicOrdering:
    def test_local_candidates_first_when_prefer_local(
        self,
        seeded_registry: CapabilityRegistryService,
    ) -> None:
        config = FederationConfig(
            broker_id="broker-a",
            broker_url="http://localhost:8000",
            prefer_local=True,
            peers=[
                FederatedPeer(
                    broker_id="broker-b",
                    broker_url="http://localhost:8001",
                    trust_level=PeerTrustLevel.ROUTING,
                )
            ],
        )
        svc = DiscoveryService(registry=seeded_registry, federation=config)

        peer_resp = _make_peer_response_json(cap_id="remote_cap")
        mock_resp = MagicMock()
        mock_resp.json.return_value = peer_resp
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.post", return_value=mock_resp):
            resp = svc.discover(DiscoveryRequest(max_results=100))

        local = [i for i, c in enumerate(resp.candidates) if c.source_broker_id is None]
        remote = [i for i, c in enumerate(resp.candidates) if c.source_broker_id is not None]
        if local and remote:
            assert max(local) < min(remote), "All local candidates must precede remote ones"
        # There must be at least one remote candidate
        assert len(remote) >= 1

    def test_same_request_gives_same_order(
        self, seeded_registry: CapabilityRegistryService
    ) -> None:
        svc = DiscoveryService(registry=seeded_registry)
        req = DiscoveryRequest(max_results=100)
        resp1 = svc.discover(req)
        resp2 = svc.discover(req)
        assert [c.capability_id for c in resp1.candidates] == [
            c.capability_id for c in resp2.candidates
        ]
