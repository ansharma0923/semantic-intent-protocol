"""Broker federation demo for SIP.

Demonstrates two in-process SIP brokers (Broker A and Broker B) with federation:

1. Broker A registers local capabilities (knowledge domain)
2. Broker B registers remote capabilities (analytics domain)
3. Broker A is configured with Broker B as a ROUTING-trusted federation peer
4. Broker A's DiscoveryService queries Broker B and aggregates results
5. The merged discovery response shows local + remote candidates with provenance

No running servers are required — federation HTTP calls are mocked with the
same response format the real HTTP API produces.

Run:
    python examples/end_to_end_demo/broker_federation_demo.py
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from sip.broker.discovery import DiscoveryRequest, DiscoveryService
from sip.broker.federation import (
    FederatedPeer,
    FederationConfig,
    PeerTrustLevel,
)
from sip.registry.bootstrap import seed_registry
from sip.registry.models import (
    CapabilityDescriptor,
    ProviderMetadata,
    RiskLevel,
    SchemaReference,
)
from sip.registry.service import CapabilityRegistryService
from sip.envelope.models import BindingType, OperationClass


def _separator(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print("=" * 60)


def _make_broker_b_response() -> dict:
    """Simulate Broker B returning its analytics capabilities."""
    return {
        "candidates": [
            {
                "capability_id": "analytics.summarize_report",
                "name": "Summarize Report",
                "description": "Summarizes a report document into key insights.",
                "operation_class": "analyze",
                "supported_bindings": ["rest"],
                "intent_domains": ["analytics", "knowledge_management"],
                "minimum_trust_tier": "internal",
                "score": 7.5,
                "source_broker_id": None,
                "source_broker_url": None,
                "routing_allowed": True,
                "discovery_path": [],
                "extensions": {},
            },
            {
                "capability_id": "analytics.generate_insights",
                "name": "Generate Insights",
                "description": "Generates data-driven insights from structured data.",
                "operation_class": "analyze",
                "supported_bindings": ["rest", "grpc"],
                "intent_domains": ["analytics"],
                "minimum_trust_tier": "internal",
                "score": 6.0,
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


def demo_setup_brokers() -> None:
    """Show the broker setup and capability registration."""
    _separator("Broker Setup")

    # --- Broker A (local) ---
    registry_a = CapabilityRegistryService()
    seed_registry(registry_a)
    local_count = registry_a.count()
    print(f"Broker A registered {local_count} local capabilities (knowledge domain)")
    for cap in registry_a.list_all()[:3]:
        print(f"  {cap.capability_id}: {cap.name}")
    if local_count > 3:
        print(f"  ... and {local_count - 3} more")

    # --- Broker B (remote peer) ---
    registry_b = CapabilityRegistryService()
    b_caps = [
        CapabilityDescriptor(
            capability_id="analytics.summarize_report",
            name="Summarize Report",
            description="Summarizes a report document into key insights.",
            provider=ProviderMetadata(
                provider_id="analytics-provider",
                provider_name="Analytics Corp",
            ),
            intent_domains=["analytics", "knowledge_management"],
            operation_class=OperationClass.ANALYZE,
            risk_level=RiskLevel.LOW,
            required_scopes=["sip:analytics:read"],
            minimum_trust_tier="internal",
            supported_bindings=[BindingType.REST],
            input_schema=SchemaReference(description="Report document input"),
            output_schema=SchemaReference(description="Summary output"),
        ),
        CapabilityDescriptor(
            capability_id="analytics.generate_insights",
            name="Generate Insights",
            description="Generates data-driven insights from structured data.",
            provider=ProviderMetadata(
                provider_id="analytics-provider",
                provider_name="Analytics Corp",
            ),
            intent_domains=["analytics"],
            operation_class=OperationClass.ANALYZE,
            risk_level=RiskLevel.LOW,
            required_scopes=["sip:analytics:read"],
            minimum_trust_tier="internal",
            supported_bindings=[BindingType.REST, BindingType.GRPC],
            input_schema=SchemaReference(description="Structured data input"),
            output_schema=SchemaReference(description="Insights output"),
        ),
    ]
    for cap in b_caps:
        registry_b.register(cap)
    print(f"\nBroker B registered {registry_b.count()} capabilities (analytics domain)")
    for cap in registry_b.list_all():
        print(f"  {cap.capability_id}: {cap.name}")


def demo_federation_discovery() -> None:
    """Demonstrate Broker A discovering capabilities from Broker B."""
    _separator("Federation: Broker A discovers Broker B capabilities")

    # Set up Broker A with Broker B as a ROUTING-trusted federation peer
    registry_a = CapabilityRegistryService()
    seed_registry(registry_a)

    federation = FederationConfig(
        broker_id="broker-a",
        broker_url="http://broker-a.example.com",
        peers=[
            FederatedPeer(
                broker_id="broker-b",
                broker_url="http://broker-b.example.com",
                trust_level=PeerTrustLevel.ROUTING,
                description="Analytics team broker (ROUTING trust)",
            )
        ],
    )

    discovery_svc = DiscoveryService(
        registry=registry_a,
        federation=federation,
        local_broker_id="broker-a",
    )

    # Mock the HTTP call to Broker B
    mock_resp = MagicMock()
    mock_resp.json.return_value = _make_broker_b_response()
    mock_resp.raise_for_status = MagicMock()

    print("Issuing discovery query: intent_domain=knowledge_management")
    with patch("httpx.post", return_value=mock_resp):
        response = discovery_svc.discover(
            DiscoveryRequest(
                intent_domain="knowledge_management",
                max_results=20,
            )
        )

    print(f"\nDiscovery results:")
    print(f"  total candidates:  {response.total}")
    print(f"  local candidates:  {response.local_count}")
    print(f"  remote candidates: {response.remote_count}")
    print(f"  peers queried:     {response.peers_queried}")

    print("\nAll candidates:")
    for candidate in response.candidates:
        source = candidate.source_broker_id or "broker-a (local)"
        routing = "✓ routing" if candidate.routing_allowed else "✗ discovery only"
        print(f"  [{source}]  {candidate.capability_id}  score={candidate.score:.2f}  {routing}")


def demo_discovery_trust_levels() -> None:
    """Show how PeerTrustLevel controls routing eligibility."""
    _separator("Federation trust levels: ROUTING vs DISCOVERY")

    registry = CapabilityRegistryService()

    # ROUTING trust — remote capabilities eligible for execution plans
    routing_federation = FederationConfig(
        broker_id="broker-a",
        broker_url="http://broker-a.example.com",
        peers=[
            FederatedPeer(
                broker_id="trusted-peer",
                broker_url="http://trusted.example.com",
                trust_level=PeerTrustLevel.ROUTING,
            )
        ],
    )
    routing_svc = DiscoveryService(
        registry=registry,
        federation=routing_federation,
        local_broker_id="broker-a",
    )
    mock_routing = MagicMock()
    mock_routing.json.return_value = _make_broker_b_response()
    mock_routing.raise_for_status = MagicMock()

    with patch("httpx.post", return_value=mock_routing):
        resp_routing = routing_svc.discover(DiscoveryRequest(max_results=100))

    remote_routing = [c for c in resp_routing.candidates if c.source_broker_id]
    print("ROUTING trust peer:")
    for c in remote_routing:
        print(f"  {c.capability_id}  routing_allowed={c.routing_allowed}  ← eligible for plans")

    # DISCOVERY trust — remote capabilities visible but NOT eligible for execution plans
    disco_federation = FederationConfig(
        broker_id="broker-a",
        broker_url="http://broker-a.example.com",
        peers=[
            FederatedPeer(
                broker_id="discovery-only-peer",
                broker_url="http://disco.example.com",
                trust_level=PeerTrustLevel.DISCOVERY,
            )
        ],
    )
    disco_svc = DiscoveryService(
        registry=registry,
        federation=disco_federation,
        local_broker_id="broker-a",
    )
    mock_disco = MagicMock()
    mock_disco.json.return_value = _make_broker_b_response()
    mock_disco.raise_for_status = MagicMock()

    with patch("httpx.post", return_value=mock_disco):
        resp_disco = disco_svc.discover(DiscoveryRequest(max_results=100))

    remote_disco = [c for c in resp_disco.candidates if c.source_broker_id]
    print("\nDISCOVERY trust peer:")
    for c in remote_disco:
        print(f"  {c.capability_id}  routing_allowed={c.routing_allowed}  ← NOT eligible for plans")


def demo_provenance_tracking() -> None:
    """Show how discovery path is preserved for audit."""
    _separator("Federation: Provenance tracking via discovery_path")

    registry = CapabilityRegistryService()
    federation = FederationConfig(
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
    svc = DiscoveryService(
        registry=registry,
        federation=federation,
        local_broker_id="broker-a",
    )

    mock_resp = MagicMock()
    mock_resp.json.return_value = _make_broker_b_response()
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.post", return_value=mock_resp):
        response = svc.discover(DiscoveryRequest(max_results=100))

    remote = [c for c in response.candidates if c.source_broker_id]
    print("Remote candidates with discovery_path (provenance):")
    for c in remote:
        print(f"  {c.capability_id}")
        print(f"    source_broker_id: {c.source_broker_id}")
        print(f"    discovery_path:   {c.discovery_path}")
        print(f"    (path shows the broker hop chain for audit purposes)")


def main() -> None:
    print("=== SIP Broker Federation Demo ===\n")
    print("This demo shows two in-process brokers with federation discovery.")
    print("Broker A discovers and aggregates capabilities from Broker B.\n")

    demo_setup_brokers()
    demo_federation_discovery()
    demo_discovery_trust_levels()
    demo_provenance_tracking()

    _separator("Summary")
    print("""
Federation model features demonstrated:

✓  Broker A registers local capabilities (knowledge domain)
✓  Broker B registers remote capabilities (analytics domain)
✓  ROUTING trust peers: remote capabilities eligible for execution plans
✓  DISCOVERY trust peers: remote capabilities visible but not routable
✓  Aggregated results show local_count + remote_count
✓  source_broker_id identifies which broker provided each capability
✓  discovery_path tracks the full hop chain for provenance auditing
✓  Local broker is always the final policy authority
""")
    print("=== Demo complete. ===")


if __name__ == "__main__":
    main()
