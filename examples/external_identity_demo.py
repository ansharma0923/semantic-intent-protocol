"""External identity demo – map trusted HTTP headers into SIP actor context.

This example demonstrates:
  1. How the SIP broker reads externally authenticated identity from HTTP headers.
  2. The precedence rule: trusted headers override body-provided actor fields.
  3. The security configuration flag (SIP_TRUSTED_IDENTITY_HEADERS).
  4. End-to-end: submitting an intent with identity headers via the HTTP API.

Run this script directly:

    python examples/external_identity_demo.py

Security note:
    Trusted identity header mapping is designed for use behind a trusted
    API gateway, reverse proxy, or service mesh that strips and re-injects
    these headers after authenticating the caller.  Do NOT enable this in
    deployments where the broker is directly accessible by untrusted clients.
    See docs/security-model.md for details.
"""

from __future__ import annotations

import json
import os

from sip.broker.identity import (
    HEADER_ACTOR_ID,
    HEADER_ACTOR_NAME,
    HEADER_ACTOR_TYPE,
    HEADER_SCOPES,
    HEADER_TRUST_LEVEL,
    map_identity_headers,
)
from sip.envelope.models import ActorDescriptor, ActorType, TrustLevel

# ---------------------------------------------------------------------------
# Part 1 – Direct identity mapping utility demo
# ---------------------------------------------------------------------------

print("=== Part 1: Identity mapping utility (sip.broker.identity) ===")
print()

# Simulate what comes in from the request body
body_actor = ActorDescriptor(
    actor_id="anonymous-client",
    actor_type=ActorType.AI_AGENT,
    name="Unknown Agent",
    trust_level=TrustLevel.PUBLIC,
    scopes=[],
)

# Simulate headers injected by the API gateway after authentication
gateway_headers = {
    HEADER_ACTOR_ID: "svc-account-ai-ops-42",
    HEADER_ACTOR_TYPE: "service",
    HEADER_ACTOR_NAME: "AI Ops Service Account",
    HEADER_TRUST_LEVEL: "internal",
    HEADER_SCOPES: "sip:knowledge:read,sip:network:read",
}

print("Body-provided actor:")
print(f"  actor_id:    {body_actor.actor_id}")
print(f"  actor_type:  {body_actor.actor_type.value}")
print(f"  name:        {body_actor.name}")
print(f"  trust_level: {body_actor.trust_level.value}")
print(f"  scopes:      {body_actor.scopes}")
print()
print("Gateway identity headers:")
for k, v in gateway_headers.items():
    print(f"  {k}: {v}")
print()

# When trusted=False (default, safe), headers are ignored
ignored_actor = map_identity_headers(body_actor, gateway_headers, trusted=False)
print("Result with trusted=False (default – headers ignored):")
print(f"  actor_id: {ignored_actor.actor_id}  ← unchanged")
print()

# When trusted=True (explicit or via env var), headers override
mapped_actor = map_identity_headers(body_actor, gateway_headers, trusted=True)
print("Result with trusted=True (headers applied – override body actor):")
print(f"  actor_id:    {mapped_actor.actor_id}")
print(f"  actor_type:  {mapped_actor.actor_type.value}")
print(f"  name:        {mapped_actor.name}")
print(f"  trust_level: {mapped_actor.trust_level.value}")
print(f"  scopes:      {mapped_actor.scopes}")
print()

# Precedence rule check
assert mapped_actor.actor_id == "svc-account-ai-ops-42", "Header must override body actor_id"
assert mapped_actor.trust_level == TrustLevel.INTERNAL, "Header must override body trust_level"
assert set(mapped_actor.scopes) == {"sip:knowledge:read", "sip:network:read"}
print("✓ Precedence rule verified: trusted headers override body-provided actor fields")
print()

# ---------------------------------------------------------------------------
# Part 2 – End-to-end via HTTP API (in-process)
# ---------------------------------------------------------------------------

print("=== Part 2: End-to-end via HTTP API (in-process TestClient) ===")
print()

from fastapi.testclient import TestClient

import sip.broker.service as svc
from sip.broker.service import app
from sip.envelope.models import (
    DesiredOutcome,
    IntentEnvelope,
    IntentPayload,
    OperationClass,
    ProtocolBinding,
    TargetDescriptor,
    TargetType,
)
from sip.policy.engine import PolicyEngine
from sip.registry.bootstrap import seed_registry
from sip.registry.service import CapabilityRegistryService

# Wire up seeded broker (approval disabled for demo)
registry = CapabilityRegistryService()
seed_registry(registry)
svc._broker = svc.BrokerService(
    registry=registry,
    policy_engine=PolicyEngine(enforce_approval_policy=False),
)

# Build minimal envelope body (body actor has no scopes / low trust)
envelope_body = IntentEnvelope(
    actor=ActorDescriptor(
        actor_id="raw-client",
        actor_type=ActorType.AI_AGENT,
        name="Raw Client",
        trust_level=TrustLevel.INTERNAL,
        scopes=["sip:knowledge:read"],
    ),
    target=TargetDescriptor(target_type=TargetType.CAPABILITY),
    intent=IntentPayload(
        intent_name="retrieve_document",
        intent_domain="knowledge_management",
        operation_class=OperationClass.RETRIEVE,
    ),
    desired_outcome=DesiredOutcome(summary="Retrieve a document"),
)

# Enable trusted identity headers for this demo
os.environ["SIP_TRUSTED_IDENTITY_HEADERS"] = "true"

client = TestClient(app)

print("Submitting intent with identity headers (trusted mapping enabled)...")
response = client.post(
    "/sip/intents",
    json=envelope_body.model_dump(mode="json"),
    headers={
        "x-actor-id": "gateway-actor-99",
        "x-actor-name": "API Gateway Verified User",
        "x-trust-level": "internal",
        "x-scopes": "sip:knowledge:read",
    },
)

body = response.json()
print(f"HTTP status: {response.status_code}")
print()
print("Audit record actor_id:", body["audit_record"]["actor_id"])
assert body["audit_record"]["actor_id"] == "gateway-actor-99", "Gateway header must be applied"
print("✓ Audit record reflects gateway-injected actor_id")
print()
print("Full response:")
print(json.dumps(body, indent=2))

# Clean up env var
del os.environ["SIP_TRUSTED_IDENTITY_HEADERS"]

print()
print("Demo complete.")
