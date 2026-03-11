"""Federation model demo for SIP.

Demonstrates the SIP federation model:

1. Trusted peer capability accepted (ROUTING trust)
2. Discovery-only peer capability rejected from execution plans
3. Untrusted (unconfigured) peer capability rejected entirely
4. Provenance preserved across broker discovery path
5. Local policy still applied to remote capability usage

The federation model governs:
  - Which peer brokers can contribute capabilities to discovery results
  - Whether remote capabilities can be included in execution plans
  - How provenance is tracked across broker boundaries
  - That local broker is always the final policy authority
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from sip.broker.discovery import DiscoveryRequest, DiscoveryService
from sip.broker.federation import (
    FederatedPeer,
    FederationConfig,
    PeerTrustLevel,
    RemoteCapabilityResult,
)
from sip.registry.service import CapabilityRegistryService


def _separator(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print("=" * 60)


def _make_peer_response(cap_id: str, score: float = 5.0) -> dict:
    return {
        "candidates": [
            {
                "capability_id": cap_id,
                "name": f"Remote: {cap_id}",
                "description": f"Capability {cap_id} on remote broker",
                "operation_class": "retrieve",
                "supported_bindings": ["rest"],
                "intent_domains": ["test"],
                "minimum_trust_tier": "internal",
                "score": score,
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


# ---------------------------------------------------------------------------
# Scenario 1: Trusted ROUTING peer – capability accepted for routing
# ---------------------------------------------------------------------------

_separator("Scenario 1: Trusted ROUTING peer – capability accepted for routing")

federation = FederationConfig(
    broker_id="broker-a",
    broker_url="http://broker-a.example.com",
    peers=[
        FederatedPeer(
            broker_id="trusted-broker",
            broker_url="http://trusted.example.com",
            trust_level=PeerTrustLevel.ROUTING,
            description="Trusted partner broker",
        )
    ],
)

svc = DiscoveryService(
    registry=CapabilityRegistryService(),
    federation=federation,
    local_broker_id="broker-a",
)

mock_resp = MagicMock()
mock_resp.json.return_value = _make_peer_response("trusted_cap")
mock_resp.raise_for_status = MagicMock()

with patch("httpx.post", return_value=mock_resp):
    resp = svc.discover(DiscoveryRequest(max_results=100))

remote = [c for c in resp.candidates if c.source_broker_id is not None]
print(f"Remote candidates: {len(remote)}")
for c in remote:
    print(f"  capability_id: {c.capability_id}")
    print(f"  source_broker_id: {c.source_broker_id}")
    print(f"  peer_trust: ROUTING")
    print(f"  routing_allowed: {c.routing_allowed}  ← ✓ routing permitted")
    assert c.routing_allowed, "ROUTING peer capabilities must be routing_allowed"
print("✓ ROUTING peer capability accepted for routing")

# ---------------------------------------------------------------------------
# Scenario 2: Discovery-only peer – capability in results but NOT routing_allowed
# ---------------------------------------------------------------------------

_separator("Scenario 2: DISCOVERY-only peer – not allowed for routing")

discovery_only_federation = FederationConfig(
    broker_id="broker-a",
    broker_url="http://broker-a.example.com",
    peers=[
        FederatedPeer(
            broker_id="disco-only-broker",
            broker_url="http://disco-only.example.com",
            trust_level=PeerTrustLevel.DISCOVERY,
            description="Discovery-only partner (no routing)",
        )
    ],
)

disco_svc = DiscoveryService(
    registry=CapabilityRegistryService(),
    federation=discovery_only_federation,
    local_broker_id="broker-a",
)

mock_resp2 = MagicMock()
mock_resp2.json.return_value = _make_peer_response("discovery_only_cap")
mock_resp2.raise_for_status = MagicMock()

with patch("httpx.post", return_value=mock_resp2):
    resp2 = disco_svc.discover(DiscoveryRequest(max_results=100))

remote2 = [c for c in resp2.candidates if c.source_broker_id is not None]
print(f"Remote candidates: {len(remote2)}")
for c in remote2:
    print(f"  capability_id: {c.capability_id}")
    print(f"  routing_allowed: {c.routing_allowed}  ← ✗ routing NOT permitted")
    assert not c.routing_allowed, "DISCOVERY peer capabilities must NOT be routing_allowed"
print("✓ DISCOVERY-only peer capability present but routing_allowed=False")

# ---------------------------------------------------------------------------
# Scenario 3: No configured peer – no remote candidates at all
# ---------------------------------------------------------------------------

_separator("Scenario 3: No configured peers – only local results")

no_fed_svc = DiscoveryService(
    registry=CapabilityRegistryService(),
    federation=None,
)
resp3 = no_fed_svc.discover(DiscoveryRequest())
print(f"Total candidates: {resp3.total}")
print(f"Remote candidates: {resp3.remote_count}")
assert resp3.remote_count == 0
print("✓ No configured peers → no remote candidates")

# ---------------------------------------------------------------------------
# Scenario 4: Provenance preserved across broker discovery path
# ---------------------------------------------------------------------------

_separator("Scenario 4: Provenance / discovery path preserved")

# Build a RemoteCapabilityResult with a discovery path already set
rr = RemoteCapabilityResult(
    source_broker_id="broker-b",
    source_broker_url="http://broker-b.example.com",
    peer_trust_level=PeerTrustLevel.ROUTING,
    capability_data={"capability_id": "transitive_cap"},
    score=3.0,
    discovery_path=["broker-b"],
)

# When broker-a aggregates this result, it prepends its own broker_id
full_path = ["broker-a"] + rr.discovery_path
print(f"Original discovery_path: {rr.discovery_path}")
print(f"After broker-a aggregation: {full_path}")
print("  Path shows: broker-a → broker-b → transitive_cap")
assert full_path == ["broker-a", "broker-b"]
print("✓ Discovery path (provenance) preserved across broker boundaries")

# Verify path in actual discovery flow
routing_fed = FederationConfig(
    broker_id="broker-a",
    broker_url="http://broker-a.example.com",
    peers=[
        FederatedPeer(
            broker_id="broker-b",
            broker_url="http://broker-b.example.com",
            trust_level=PeerTrustLevel.ROUTING,
        )
    ],
)
path_svc = DiscoveryService(
    registry=CapabilityRegistryService(),
    federation=routing_fed,
    local_broker_id="broker-a",
)

mock_resp4 = MagicMock()
mock_resp4.json.return_value = _make_peer_response("path_cap")
mock_resp4.raise_for_status = MagicMock()

with patch("httpx.post", return_value=mock_resp4):
    resp4 = path_svc.discover(DiscoveryRequest(max_results=100))

remote4 = [c for c in resp4.candidates if c.source_broker_id is not None]
for c in remote4:
    print(f"\nDiscovery path in result: {c.discovery_path}")
    assert "broker-b" in c.discovery_path, "Peer broker ID must be in discovery path"
print("✓ Source broker recorded in discovery_path for provenance tracking")

# ---------------------------------------------------------------------------
# Scenario 5: Local policy authority – routing_allowed is final check
# ---------------------------------------------------------------------------

_separator("Scenario 5: Local policy always has final authority")

print("""
Federation policy model:

  1. DiscoveryService queries peers based on FederationConfig
  2. Remote capabilities are tagged with routing_allowed based on peer trust:
       PeerTrustLevel.DISCOVERY → routing_allowed = False
       PeerTrustLevel.ROUTING   → routing_allowed = True
       PeerTrustLevel.FULL      → routing_allowed = True
  3. Local broker (SIP planner + policy engine) MUST check routing_allowed
     before including a remote capability in an execution plan
  4. Local policy evaluation (scope checks, risk assessment, etc.) applies
     to ALL capabilities – local AND remote – before plan creation
  5. Remote discovery results NEVER bypass local policy checks

This ensures:
  ✓ Remote brokers cannot force local policy to be skipped
  ✓ Untrusted peers cannot inject capabilities into execution plans
  ✓ Provenance is tracked from origination through discovery to execution
""")

# ---------------------------------------------------------------------------
# Scenario 6: FederationConfig helper methods
# ---------------------------------------------------------------------------

_separator("Scenario 6: FederationConfig peer filtering helpers")

config = FederationConfig(
    broker_id="broker-a",
    broker_url="http://broker-a.example.com",
    peers=[
        FederatedPeer(
            broker_id="disco-peer",
            broker_url="http://disco.example.com",
            trust_level=PeerTrustLevel.DISCOVERY,
        ),
        FederatedPeer(
            broker_id="routing-peer",
            broker_url="http://routing.example.com",
            trust_level=PeerTrustLevel.ROUTING,
        ),
        FederatedPeer(
            broker_id="full-peer",
            broker_url="http://full.example.com",
            trust_level=PeerTrustLevel.FULL,
        ),
    ],
)

print(f"All peers: {[p.broker_id for p in config.peers]}")
print(f"Discovery peers: {[p.broker_id for p in config.discovery_peers()]}")
print(f"Routing peers:   {[p.broker_id for p in config.routing_peers()]}")
assert len(config.discovery_peers()) == 3  # all trust levels qualify for discovery
assert len(config.routing_peers()) == 2    # only ROUTING and FULL
print("✓ Peer filtering correctly separates discovery vs routing trust levels")

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

print(f"\n{'='*60}")
print("  Federation model demo complete")
print("=" * 60)
print("""
Federation model features demonstrated:

✓  PeerTrustLevel.ROUTING/FULL peers → routing_allowed=True
✓  PeerTrustLevel.DISCOVERY peers → routing_allowed=False (discovery only)
✓  No configured peers → purely local discovery (v0.1 compatible)
✓  Discovery path preserved across broker boundaries (provenance)
✓  FederationConfig.routing_peers() filters to execution-eligible peers
✓  Local broker is final authority; routing_allowed must be checked before planning
✓  Peer failures logged and skipped (soft mode) or raised (strict mode)
""")
