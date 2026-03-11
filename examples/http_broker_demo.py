"""HTTP broker demo – submit an intent via the SIP broker HTTP API.

This example shows:
  1. How to start the SIP broker FastAPI application.
  2. How to build and submit an IntentEnvelope as a JSON HTTP request.
  3. How to read the structured broker response.

Run this script directly (it starts an in-process test server):

    python examples/http_broker_demo.py

To run against a live broker server, set BROKER_URL to the server base URL
and call _submit_via_http() instead of _submit_in_process().

Equivalent curl commands are shown at the bottom of this file.
"""

from __future__ import annotations

import json

from sip.envelope.models import (
    ActorDescriptor,
    ActorType,
    BindingType,
    DesiredOutcome,
    IntentEnvelope,
    IntentPayload,
    OperationClass,
    ProtocolBinding,
    TargetDescriptor,
    TargetType,
    TrustLevel,
)

# ---------------------------------------------------------------------------
# Build the intent envelope
# ---------------------------------------------------------------------------

envelope = IntentEnvelope(
    actor=ActorDescriptor(
        actor_id="demo-agent-001",
        actor_type=ActorType.AI_AGENT,
        name="Demo Agent",
        trust_level=TrustLevel.INTERNAL,
        scopes=["sip:knowledge:read"],
    ),
    target=TargetDescriptor(target_type=TargetType.CAPABILITY),
    intent=IntentPayload(
        intent_name="retrieve_document",
        intent_domain="knowledge_management",
        operation_class=OperationClass.RETRIEVE,
        natural_language_hint="Retrieve the latest architecture document.",
        parameters={"query": "approved architecture document", "collection": "architecture"},
    ),
    desired_outcome=DesiredOutcome(
        summary="Retrieve the approved architecture document.",
        success_criteria=["Document content returned", "Document ID present in response"],
    ),
    protocol_bindings=[
        ProtocolBinding(binding_type=BindingType.RAG),
        ProtocolBinding(binding_type=BindingType.REST),
    ],
)


# ---------------------------------------------------------------------------
# Submit via in-process TestClient (no server required)
# ---------------------------------------------------------------------------


def _submit_in_process() -> None:
    """Use FastAPI's TestClient to call the broker without a running server."""
    from fastapi.testclient import TestClient

    import sip.broker.service as svc
    from sip.broker.service import app
    from sip.policy.engine import PolicyEngine
    from sip.registry.bootstrap import seed_registry
    from sip.registry.service import CapabilityRegistryService

    # Wire up a seeded broker
    registry = CapabilityRegistryService()
    seed_registry(registry)
    svc._broker = svc.BrokerService(
        registry=registry,
        policy_engine=PolicyEngine(enforce_approval_policy=False),
    )

    client = TestClient(app)

    print("=== Submitting intent to POST /sip/intents ===")
    print(f"Envelope intent_id: {envelope.intent_id}")
    print()

    response = client.post("/sip/intents", json=envelope.model_dump(mode="json"))

    print(f"HTTP status: {response.status_code}")
    print()
    print("=== Response body ===")
    print(json.dumps(response.json(), indent=2))


# ---------------------------------------------------------------------------
# Submit via live HTTP server (requires running broker)
# ---------------------------------------------------------------------------


def _submit_via_http(broker_url: str = "http://localhost:8000") -> None:
    """Submit the envelope to a running broker server using httpx."""
    import httpx

    print(f"=== Submitting intent to {broker_url}/sip/intents ===")
    with httpx.Client() as client:
        response = client.post(
            f"{broker_url}/sip/intents",
            json=envelope.model_dump(mode="json"),
            timeout=10.0,
        )
    print(f"HTTP status: {response.status_code}")
    print()
    print("=== Response body ===")
    print(json.dumps(response.json(), indent=2))


# ---------------------------------------------------------------------------
# Health check demo
# ---------------------------------------------------------------------------


def _health_check_in_process() -> None:
    from fastapi.testclient import TestClient

    import sip.broker.service as svc
    from sip.broker.service import app
    from sip.registry.bootstrap import seed_registry
    from sip.registry.service import CapabilityRegistryService

    registry = CapabilityRegistryService()
    seed_registry(registry)
    svc._broker = svc.BrokerService(registry=registry)

    client = TestClient(app)
    response = client.get("/healthz")
    print("=== GET /healthz ===")
    print(json.dumps(response.json(), indent=2))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    _health_check_in_process()
    print()
    _submit_in_process()

# ---------------------------------------------------------------------------
# Equivalent curl commands (for reference)
# ---------------------------------------------------------------------------
#
# Start the broker server:
#   uvicorn sip.broker.service:app --host 0.0.0.0 --port 8000
#
# Health check:
#   curl -s http://localhost:8000/healthz | python -m json.tool
#
# Submit an intent:
#   curl -s -X POST http://localhost:8000/sip/intents \
#     -H 'Content-Type: application/json' \
#     -d @<(python -c "
#       from sip.envelope.models import *
#       import json
#       e = IntentEnvelope(
#         actor=ActorDescriptor(actor_id='cli-user', actor_type=ActorType.HUMAN,
#                               name='CLI User', trust_level=TrustLevel.INTERNAL,
#                               scopes=['sip:knowledge:read']),
#         target=TargetDescriptor(target_type=TargetType.CAPABILITY),
#         intent=IntentPayload(intent_name='retrieve_document',
#                              intent_domain='knowledge_management',
#                              operation_class=OperationClass.RETRIEVE),
#         desired_outcome=DesiredOutcome(summary='Get document'),
#       )
#       print(json.dumps(e.model_dump(mode='json')))
#     ") | python -m json.tool
#
# Submit with trusted identity headers:
#   curl -s -X POST http://localhost:8000/sip/intents \
#     -H 'Content-Type: application/json' \
#     -H 'X-Actor-Id: gateway-actor-99' \
#     -H 'X-Actor-Name: API Gateway User' \
#     -H 'X-Trust-Level: privileged' \
#     -H 'X-Scopes: sip:knowledge:read,sip:network:read' \
#     -d '...' | python -m json.tool
#   (Requires SIP_TRUSTED_IDENTITY_HEADERS=true in broker environment)
