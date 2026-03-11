"""Capability discovery API demo for SIP.

Demonstrates using the SIP capability discovery HTTP API:

1. GET /sip/capabilities – list all registered capabilities
2. GET /sip/capabilities/{id} – get a specific capability by ID
3. POST /sip/capabilities/discover – discover capabilities for an intent

Run this demo after starting the broker:
    uvicorn sip.broker.service:app --reload

Or run it standalone (uses TestClient, no server required):
    python examples/capability_discovery_api_demo.py
"""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

import sip.broker.service as svc_module
from sip.broker.service import BrokerService, app
from sip.registry.bootstrap import seed_registry
from sip.registry.service import CapabilityRegistryService


def _separator(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print("=" * 60)


def _pretty(data: object) -> str:
    return json.dumps(data, indent=2)


# Set up a seeded broker for the demo
_registry = CapabilityRegistryService()
seed_registry(_registry)
_broker = BrokerService(registry=_registry)
_original_broker = svc_module._broker
svc_module._broker = _broker
client = TestClient(app)

# ---------------------------------------------------------------------------
# 1. List all capabilities
# ---------------------------------------------------------------------------

_separator("1. GET /sip/capabilities – list all capabilities")

response = client.get("/sip/capabilities")
print(f"HTTP {response.status_code}")
capabilities = response.json()
print(f"Total capabilities: {len(capabilities)}")
print("\nCapability IDs:")
for cap in capabilities:
    print(f"  - {cap['capability_id']:30s}  ({cap['operation_class']})")
    if cap.get("extensions"):
        print(f"      extensions: {cap['extensions']}")

# ---------------------------------------------------------------------------
# 2. Get capability by ID
# ---------------------------------------------------------------------------

_separator("2. GET /sip/capabilities/{id} – get capability by ID")

cap_id = "retrieve_document"
response = client.get(f"/sip/capabilities/{cap_id}")
print(f"HTTP {response.status_code}")

if response.status_code == 200:
    cap = response.json()
    print(f"Capability ID:    {cap['capability_id']}")
    print(f"Name:             {cap['name']}")
    print(f"Description:      {cap['description'][:80]}")
    print(f"Operation class:  {cap['operation_class']}")
    print(f"Supported bindings: {cap['supported_bindings']}")
    print(f"Intent domains:   {cap['intent_domains']}")
else:
    print(f"Error: {response.json()}")

# 404 example
_separator("2b. GET /sip/capabilities/{id} – 404 for unknown ID")

response = client.get("/sip/capabilities/nonexistent_cap")
print(f"HTTP {response.status_code}")
print(_pretty(response.json()))

# ---------------------------------------------------------------------------
# 3. Discover capabilities – with matches
# ---------------------------------------------------------------------------

_separator("3. POST /sip/capabilities/discover – discover with matches")

discover_payload = {
    "intent_name": "retrieve_document",
    "intent_domain": "knowledge_management",
    "operation_class": "retrieve",
    "preferred_bindings": ["rest"],
    "trust_level": "internal",
    "max_results": 5,
    "include_remote": False,
}

response = client.post("/sip/capabilities/discover", json=discover_payload)
print(f"HTTP {response.status_code}")
disc = response.json()
print(f"Total candidates: {disc['total']}")
print(f"Local:            {disc['local_count']}")
print(f"Remote:           {disc['remote_count']}")
print(f"Peers queried:    {disc['peers_queried']}")
print("\nCandidates:")
for c in disc["candidates"]:
    source = c.get("source_broker_id") or "local"
    routing = "✓ routing" if c.get("routing_allowed") else "✗ discovery-only"
    print(
        f"  [{routing:20s}] {c['capability_id']:30s}  "
        f"score={c['score']:.1f}  from={source}"
    )

# ---------------------------------------------------------------------------
# 4. Discover capabilities – no matches
# ---------------------------------------------------------------------------

_separator("4. POST /sip/capabilities/discover – no matches")

response = client.post(
    "/sip/capabilities/discover",
    json={
        "intent_name": "zxqwerty_nonexistent",
        "intent_domain": "zxqwerty_domain",
        "operation_class": "write",
    },
)
print(f"HTTP {response.status_code}")
disc = response.json()
print(f"Total candidates: {disc['total']}")
print(f"Candidates: {disc['candidates']}")

# ---------------------------------------------------------------------------
# 5. Discover – invalid request (400)
# ---------------------------------------------------------------------------

_separator("5. POST /sip/capabilities/discover – invalid request (400)")

response = client.post(
    "/sip/capabilities/discover",
    json={"operation_class": "NOT_A_VALID_CLASS"},
)
print(f"HTTP {response.status_code}")
err = response.json()
print(f"Error:  {err['error']}")
print(f"Detail: {err['detail'][:120]}")

# ---------------------------------------------------------------------------
# 6. Empty discovery request (returns all capabilities)
# ---------------------------------------------------------------------------

_separator("6. POST /sip/capabilities/discover – empty request (all caps)")

response = client.post("/sip/capabilities/discover", json={})
print(f"HTTP {response.status_code}")
disc = response.json()
print(f"Total candidates (no filters): {disc['total']}")

# ---------------------------------------------------------------------------
# Restore original broker
# ---------------------------------------------------------------------------
svc_module._broker = _original_broker

print(f"\n{'='*60}")
print("  Capability Discovery API demo complete")
print("=" * 60)
print("""
Endpoints demonstrated:

  GET  /sip/capabilities              – list all registered capabilities
  GET  /sip/capabilities/{id}         – get a capability by ID (200 or 404)
  POST /sip/capabilities/discover     – discover capabilities for an intent

All responses are JSON and use standard SIP model schemas.
""")
