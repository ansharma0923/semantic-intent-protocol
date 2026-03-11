"""Distributed brokers demo for SIP.

Demonstrates broker-to-broker capability discovery using the SIP federation model.

In this demo:
  - Broker A owns local capabilities (knowledge management)
  - Broker B owns remote capabilities (network operations)
  - Broker A is configured with Broker B as a trusted ROUTING peer
  - A discovery request on Broker A finds capabilities from both brokers

This demo uses FastAPI TestClient and mocking, so no actual HTTP servers
are required.  The mocking simulates what Broker B would return when queried.

Key concepts shown:
  - FederationConfig with a FederatedPeer
  - DiscoveryService with peer forwarding
  - Aggregation of local + remote candidates (local first by default)
  - Remote capabilities tagged with source broker metadata
  - routing_allowed flag based on peer trust level
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from sip.broker.discovery import DiscoveryRequest, DiscoveryService
from sip.broker.federation import FederatedPeer, FederationConfig, PeerTrustLevel
from sip.registry.bootstrap import seed_registry
from sip.registry.service import CapabilityRegistryService


def _separator(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print("=" * 60)


# ---------------------------------------------------------------------------
# Set up Broker A (local)
# ---------------------------------------------------------------------------

_separator("Setting up Broker A (local)")

registry_a = CapabilityRegistryService()
seed_registry(registry_a)  # Broker A has knowledge + network capabilities

print(f"Broker A: {registry_a.count()} local capabilities")
for cap in registry_a.list_all():
    print(f"  - {cap.capability_id}")

# ---------------------------------------------------------------------------
# Set up Broker B (remote peer)
# The response is simulated – in reality Broker B would run at broker_url
# ---------------------------------------------------------------------------

_separator("Configuring Broker B as a trusted ROUTING peer")

_BROKER_B_RESPONSE = {
    "candidates": [
        {
            "capability_id": "remote_ml_inference",
            "name": "ML Inference",
            "description": "Run machine learning inference on broker B",
            "operation_class": "analyze",
            "supported_bindings": ["rest", "grpc"],
            "intent_domains": ["machine_learning", "analytics"],
            "minimum_trust_tier": "internal",
            "score": 6.5,
            "source_broker_id": None,
            "source_broker_url": None,
            "routing_allowed": True,
            "discovery_path": [],
            "extensions": {"x_model_version": "v2"},
        },
        {
            "capability_id": "remote_data_pipeline",
            "name": "Data Pipeline",
            "description": "Execute an ETL data pipeline on broker B",
            "operation_class": "execute",
            "supported_bindings": ["rest"],
            "intent_domains": ["data_engineering"],
            "minimum_trust_tier": "internal",
            "score": 4.0,
            "source_broker_id": None,
            "source_broker_url": None,
            "routing_allowed": True,
            "discovery_path": [],
            "extensions": {},
        },
    ],
    "total": 2,
    "local_count": 2,
    "remote_count": 0,
    "peers_queried": [],
    "peers_failed": [],
}

federation = FederationConfig(
    broker_id="broker-a",
    broker_url="http://broker-a.example.com",
    prefer_local=True,
    peers=[
        FederatedPeer(
            broker_id="broker-b",
            broker_url="http://broker-b.example.com",
            trust_level=PeerTrustLevel.ROUTING,
            description="Analytics and ML capabilities broker",
        )
    ],
)

print(f"Federation config: broker_id={federation.broker_id}")
print(f"Peers configured:")
for p in federation.peers:
    print(f"  - {p.broker_id} ({p.trust_level}) at {p.broker_url}")

# ---------------------------------------------------------------------------
# Create DiscoveryService with federation
# ---------------------------------------------------------------------------

svc = DiscoveryService(
    registry=registry_a,
    federation=federation,
    local_broker_id="broker-a",
)

# ---------------------------------------------------------------------------
# Scenario 1: Discover with no filters (all capabilities from both brokers)
# ---------------------------------------------------------------------------

_separator("Scenario 1: Discover all capabilities (local + remote)")

mock_resp = MagicMock()
mock_resp.json.return_value = _BROKER_B_RESPONSE
mock_resp.raise_for_status = MagicMock()

with patch("httpx.post", return_value=mock_resp) as mock_post:
    resp = svc.discover(DiscoveryRequest(max_results=100, include_remote=True))

print(f"Total candidates: {resp.total}")
print(f"Local candidates: {resp.local_count}")
print(f"Remote candidates: {resp.remote_count}")
print(f"Peers queried: {resp.peers_queried}")
print(f"Peers failed: {resp.peers_failed}")
print(f"\nCandidates (local first):")
for c in resp.candidates:
    source = c.source_broker_id or "broker-a (local)"
    routing = "✓ routing" if c.routing_allowed else "✗ discovery-only"
    path = " → ".join(c.discovery_path) if c.discovery_path else "local"
    ext_str = f"  extensions={c.extensions}" if c.extensions else ""
    print(
        f"  [{routing:20s}] {c.capability_id:30s}  "
        f"from={source}{ext_str}"
    )

assert resp.remote_count == 2, f"Expected 2 remote candidates, got {resp.remote_count}"
assert resp.local_count > 0, "Expected local candidates"

# Verify local comes before remote
local_indices = [i for i, c in enumerate(resp.candidates) if c.source_broker_id is None]
remote_indices = [i for i, c in enumerate(resp.candidates) if c.source_broker_id is not None]
if local_indices and remote_indices:
    assert max(local_indices) < min(remote_indices), "Local must precede remote"
    print(f"\n✓ Local candidates appear before remote candidates (prefer_local=True)")

# ---------------------------------------------------------------------------
# Scenario 2: Targeted discovery by domain
# ---------------------------------------------------------------------------

_separator("Scenario 2: Discover 'machine learning' capabilities")

with patch("httpx.post", return_value=mock_resp):
    resp2 = svc.discover(
        DiscoveryRequest(
            intent_domain="machine_learning",
            max_results=10,
            include_remote=True,
        )
    )

print(f"Candidates for domain='machine_learning':")
for c in resp2.candidates:
    source = c.source_broker_id or "local"
    print(f"  - {c.capability_id:30s}  score={c.score:.1f}  from={source}")

# ---------------------------------------------------------------------------
# Scenario 3: Peer unavailable – soft mode (logged and skipped)
# ---------------------------------------------------------------------------

_separator("Scenario 3: Peer unavailable (soft mode – skip and continue)")

with patch("httpx.post", side_effect=ConnectionError("Connection refused")):
    resp3 = svc.discover(DiscoveryRequest(max_results=100, include_remote=True))

print(f"Total candidates: {resp3.total} (local only)")
print(f"Peers failed: {resp3.peers_failed}")
assert "broker-b" in resp3.peers_failed
print("✓ Peer failure logged and skipped; local capabilities still returned")

# ---------------------------------------------------------------------------
# Scenario 4: Strict mode raises on peer failure
# ---------------------------------------------------------------------------

_separator("Scenario 4: Peer unavailable (strict mode – raises error)")

strict_federation = FederationConfig(
    broker_id="broker-a",
    broker_url="http://broker-a.example.com",
    strict_mode=True,
    peers=[
        FederatedPeer(
            broker_id="broker-b",
            broker_url="http://broker-b.example.com",
            trust_level=PeerTrustLevel.ROUTING,
        )
    ],
)
strict_svc = DiscoveryService(
    registry=registry_a,
    federation=strict_federation,
)

try:
    with patch("httpx.post", side_effect=ConnectionError("Connection refused")):
        strict_svc.discover(DiscoveryRequest())
    print("✗ Expected RuntimeError not raised")
except RuntimeError as exc:
    print(f"✓ Strict mode raised RuntimeError: {exc}")

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

print(f"\n{'='*60}")
print("  Distributed Brokers demo complete")
print("=" * 60)
print("""
Distributed broker patterns demonstrated:

✓  FederationConfig defines trusted peer brokers with trust levels
✓  DiscoveryService queries local registry + all configured peers
✓  Remote capabilities are tagged with source_broker_id and source_broker_url
✓  prefer_local=True (default) ensures local candidates appear first
✓  Peer failures are logged and skipped (soft mode)
✓  strict_mode=True causes discovery to fail fast on peer unavailability
✓  routing_allowed flag reflects peer trust level (ROUTING/FULL → True)
✓  Results are deterministically ordered
""")
