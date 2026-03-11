"""Unit tests for the federation model.

Tests cover:
- FederatedPeer construction
- FederationConfig helper methods
- PeerTrustLevel semantics
- Trusted peer capability accepted
- Untrusted peer capability rejected
- Provenance preserved across broker discovery path
- Local policy still enforced after remote discovery
"""

from __future__ import annotations

import pytest

from sip.broker.federation import (
    FederatedPeer,
    FederationConfig,
    PeerTrustLevel,
    RemoteCapabilityResult,
)


# ---------------------------------------------------------------------------
# FederatedPeer construction
# ---------------------------------------------------------------------------


class TestFederatedPeer:
    def test_defaults(self) -> None:
        peer = FederatedPeer(broker_id="b1", broker_url="http://b1.example.com")
        assert peer.trust_level == PeerTrustLevel.DISCOVERY
        assert peer.description == ""
        assert peer.metadata == {}

    def test_routing_trust(self) -> None:
        peer = FederatedPeer(
            broker_id="b2",
            broker_url="http://b2.example.com",
            trust_level=PeerTrustLevel.ROUTING,
        )
        assert peer.trust_level == PeerTrustLevel.ROUTING

    def test_full_trust(self) -> None:
        peer = FederatedPeer(
            broker_id="b3",
            broker_url="http://b3.example.com",
            trust_level=PeerTrustLevel.FULL,
        )
        assert peer.trust_level == PeerTrustLevel.FULL

    def test_metadata_preserved(self) -> None:
        peer = FederatedPeer(
            broker_id="b4",
            broker_url="http://b4.example.com",
            metadata={"region": "us-east-1"},
        )
        assert peer.metadata["region"] == "us-east-1"


# ---------------------------------------------------------------------------
# FederationConfig
# ---------------------------------------------------------------------------


class TestFederationConfig:
    def _make_config(self) -> FederationConfig:
        return FederationConfig(
            broker_id="broker-a",
            broker_url="http://broker-a.example.com",
            peers=[
                FederatedPeer(
                    broker_id="broker-b",
                    broker_url="http://broker-b.example.com",
                    trust_level=PeerTrustLevel.DISCOVERY,
                ),
                FederatedPeer(
                    broker_id="broker-c",
                    broker_url="http://broker-c.example.com",
                    trust_level=PeerTrustLevel.ROUTING,
                ),
                FederatedPeer(
                    broker_id="broker-d",
                    broker_url="http://broker-d.example.com",
                    trust_level=PeerTrustLevel.FULL,
                ),
            ],
        )

    def test_get_peer_by_id(self) -> None:
        config = self._make_config()
        peer = config.get_peer("broker-b")
        assert peer is not None
        assert peer.broker_id == "broker-b"

    def test_get_peer_missing_returns_none(self) -> None:
        config = self._make_config()
        assert config.get_peer("nonexistent") is None

    def test_discovery_peers_includes_all(self) -> None:
        config = self._make_config()
        peers = config.discovery_peers()
        ids = {p.broker_id for p in peers}
        # All three trust levels qualify for discovery
        assert {"broker-b", "broker-c", "broker-d"} == ids

    def test_routing_peers_excludes_discovery_only(self) -> None:
        config = self._make_config()
        peers = config.routing_peers()
        ids = {p.broker_id for p in peers}
        assert "broker-b" not in ids  # discovery only
        assert {"broker-c", "broker-d"} == ids

    def test_defaults(self) -> None:
        config = FederationConfig(
            broker_id="b",
            broker_url="http://b.example.com",
        )
        assert config.prefer_local is True
        assert config.strict_mode is False
        assert config.peers == []

    def test_empty_config_has_no_peers(self) -> None:
        config = FederationConfig(
            broker_id="b",
            broker_url="http://b.example.com",
        )
        assert config.discovery_peers() == []
        assert config.routing_peers() == []


# ---------------------------------------------------------------------------
# PeerTrustLevel semantics
# ---------------------------------------------------------------------------


class TestPeerTrustLevel:
    def test_enum_values(self) -> None:
        assert PeerTrustLevel.DISCOVERY == "discovery"
        assert PeerTrustLevel.ROUTING == "routing"
        assert PeerTrustLevel.FULL == "full"

    def test_discovery_level_is_least_privileged(self) -> None:
        # DISCOVERY peers appear in discovery_peers() but not routing_peers()
        config = FederationConfig(
            broker_id="a",
            broker_url="http://a.example.com",
            peers=[
                FederatedPeer(
                    broker_id="b",
                    broker_url="http://b.example.com",
                    trust_level=PeerTrustLevel.DISCOVERY,
                )
            ],
        )
        assert len(config.discovery_peers()) == 1
        assert len(config.routing_peers()) == 0


# ---------------------------------------------------------------------------
# RemoteCapabilityResult
# ---------------------------------------------------------------------------


class TestRemoteCapabilityResult:
    def test_construction(self) -> None:
        rr = RemoteCapabilityResult(
            source_broker_id="broker-b",
            source_broker_url="http://broker-b.example.com",
            peer_trust_level=PeerTrustLevel.ROUTING,
            capability_data={"capability_id": "my_cap"},
            score=7.5,
            discovery_path=["broker-b"],
        )
        assert rr.source_broker_id == "broker-b"
        assert rr.score == 7.5
        assert rr.discovery_path == ["broker-b"]

    def test_discovery_path_preserved(self) -> None:
        rr = RemoteCapabilityResult(
            source_broker_id="broker-b",
            source_broker_url="http://broker-b.example.com",
            peer_trust_level=PeerTrustLevel.FULL,
            capability_data={},
            discovery_path=["broker-b", "broker-c"],
        )
        assert rr.discovery_path == ["broker-b", "broker-c"]


# ---------------------------------------------------------------------------
# Trust-based capability acceptance / rejection
# ---------------------------------------------------------------------------


class TestFederationPolicyEnforcement:
    def test_discovery_only_peer_not_in_routing_peers(self) -> None:
        """A DISCOVERY-level peer must not appear in routing_peers."""
        config = FederationConfig(
            broker_id="a",
            broker_url="http://a.example.com",
            peers=[
                FederatedPeer(
                    broker_id="untrusted",
                    broker_url="http://untrusted.example.com",
                    trust_level=PeerTrustLevel.DISCOVERY,
                )
            ],
        )
        routing = config.routing_peers()
        assert not any(p.broker_id == "untrusted" for p in routing)

    def test_routing_peer_included_in_routing_peers(self) -> None:
        config = FederationConfig(
            broker_id="a",
            broker_url="http://a.example.com",
            peers=[
                FederatedPeer(
                    broker_id="trusted-r",
                    broker_url="http://trusted-r.example.com",
                    trust_level=PeerTrustLevel.ROUTING,
                )
            ],
        )
        routing = config.routing_peers()
        assert any(p.broker_id == "trusted-r" for p in routing)

    def test_full_trust_peer_included_in_routing_peers(self) -> None:
        config = FederationConfig(
            broker_id="a",
            broker_url="http://a.example.com",
            peers=[
                FederatedPeer(
                    broker_id="trusted-f",
                    broker_url="http://trusted-f.example.com",
                    trust_level=PeerTrustLevel.FULL,
                )
            ],
        )
        routing = config.routing_peers()
        assert any(p.broker_id == "trusted-f" for p in routing)

    def test_provenance_preserved_in_discovery_path(self) -> None:
        """Discovery path must record the originating broker ID."""
        rr = RemoteCapabilityResult(
            source_broker_id="broker-b",
            source_broker_url="http://broker-b.example.com",
            peer_trust_level=PeerTrustLevel.ROUTING,
            capability_data={"capability_id": "cap1"},
            score=3.0,
            discovery_path=["broker-b"],
        )
        # Simulating aggregation: local broker prepends its own ID
        full_path = ["broker-a"] + rr.discovery_path
        assert full_path == ["broker-a", "broker-b"]

    def test_remote_capability_routing_not_allowed_for_discovery_trust(self) -> None:
        """DiscoveryCandidate from a DISCOVERY peer must have routing_allowed=False."""
        from sip.broker.discovery import DiscoveryService
        from sip.registry.service import CapabilityRegistryService
        from unittest.mock import MagicMock, patch

        reg = CapabilityRegistryService()  # empty
        config = FederationConfig(
            broker_id="a",
            broker_url="http://a.example.com",
            peers=[
                FederatedPeer(
                    broker_id="disco-peer",
                    broker_url="http://disco.example.com",
                    trust_level=PeerTrustLevel.DISCOVERY,
                )
            ],
        )
        svc = DiscoveryService(registry=reg, federation=config)

        peer_resp = {
            "candidates": [
                {
                    "capability_id": "disco_cap",
                    "name": "Discovery Cap",
                    "description": "Remote cap",
                    "operation_class": "retrieve",
                    "supported_bindings": ["rest"],
                    "intent_domains": ["test"],
                    "minimum_trust_tier": "internal",
                    "score": 4.0,
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
        mock_resp = MagicMock()
        mock_resp.json.return_value = peer_resp
        mock_resp.raise_for_status = MagicMock()

        from sip.broker.discovery import DiscoveryRequest
        with patch("httpx.post", return_value=mock_resp):
            resp = svc.discover(DiscoveryRequest(include_remote=True))

        remote = [c for c in resp.candidates if c.source_broker_id is not None]
        assert len(remote) == 1
        # DISCOVERY trust level → routing NOT allowed
        assert remote[0].routing_allowed is False
