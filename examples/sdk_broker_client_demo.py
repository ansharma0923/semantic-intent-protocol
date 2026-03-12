"""SDK Broker Client Demo.

Demonstrates the SIP Python SDK's BrokerClient for submitting intents
to a running SIP broker HTTP server.

NOTE: This example requires a running SIP broker. Start one with:
    uvicorn sip.broker.service:app --reload

If no broker is running, the example will print a connection error and exit.

Run this example:
    python examples/sdk_broker_client_demo.py
"""

from __future__ import annotations

import sys

from sip.sdk import (
    BrokerClient,
    build_actor,
    build_intent_envelope,
    build_provenance,
    to_json,
)
from sip.sdk.errors import SIPClientError, SIPHTTPError

BROKER_URL = "http://localhost:8000"


def main() -> None:
    print("=== SIP Python SDK – Broker Client Demo ===\n")
    print(f"Broker URL: {BROKER_URL}\n")

    client = BrokerClient(BROKER_URL)

    # -----------------------------------------------------------------
    # 1. Health check
    # -----------------------------------------------------------------
    print("1. Health check...")
    try:
        health = client.health()
        print(f"   status:       {health.get('status')}")
        print(f"   capabilities: {health.get('capabilities')}")
    except (SIPHTTPError, SIPClientError) as exc:
        print(f"   ERROR: {exc}")
        print("\nThe broker is not running. Start it with:")
        print("    uvicorn sip.broker.service:app --reload")
        sys.exit(1)

    # -----------------------------------------------------------------
    # 2. Build an envelope using builders
    # -----------------------------------------------------------------
    print("\n2. Building an intent envelope...")
    actor = build_actor(
        actor_id="demo-agent",
        name="Demo Agent",
        actor_type="ai_agent",
        trust_level="internal",
        scopes=["sip:knowledge:read"],
    )
    provenance = build_provenance(
        originator="demo-user",
        submitted_by="demo-agent",
        delegation_chain=["demo-user"],
    )
    envelope = build_intent_envelope(
        actor=actor,
        intent_name="retrieve_document",
        intent_domain="knowledge_management",
        operation_class="retrieve",
        outcome_summary="Retrieve the architecture document.",
        intent_parameters={"query": "What is the SIP architecture?"},
        provenance=provenance,
    )
    print(f"   intent_id:   {envelope.intent_id}")
    print(f"   intent_name: {envelope.intent.intent_name}")

    # -----------------------------------------------------------------
    # 3. Submit the intent
    # -----------------------------------------------------------------
    print("\n3. Submitting intent to broker...")
    try:
        result = client.submit_intent(envelope)
        print(f"   action_taken:     {result.get('action_taken')}")
        print(f"   outcome:          {result.get('outcome')}")
        if result.get("capability_id"):
            print(f"   capability_id:    {result.get('capability_id')}")
        if result.get("validation_errors"):
            print(f"   validation errors: {result.get('validation_errors')}")
    except SIPHTTPError as exc:
        print(f"   HTTP error {exc.status_code}: {exc.response_body}")
    except SIPClientError as exc:
        print(f"   Client error: {exc}")

    # -----------------------------------------------------------------
    # 4. Submit via JSON string
    # -----------------------------------------------------------------
    print("\n4. Submitting via JSON string...")
    envelope_json = to_json(envelope)
    try:
        result2 = client.submit_intent_json(envelope_json)
        print(f"   action_taken: {result2.get('action_taken')}")
    except SIPHTTPError as exc:
        print(f"   HTTP error {exc.status_code}: {exc.response_body}")
    except SIPClientError as exc:
        print(f"   Client error: {exc}")

    print("\n=== Broker client demo complete. ===")


if __name__ == "__main__":
    main()
