"""SDK Capability Discovery Demo.

Demonstrates the SIP Python SDK's CapabilityDiscoveryClient for
querying capabilities from a running SIP broker.

NOTE: This example requires a running SIP broker. Start one with:
    uvicorn sip.broker.service:app --reload

If no broker is running, the example will print a connection error and exit.

Run this example:
    python examples/sdk_capability_discovery_demo.py
"""

from __future__ import annotations

import sys

from sip.broker.discovery import DiscoveryRequest
from sip.sdk import CapabilityDiscoveryClient
from sip.sdk.errors import SIPClientError, SIPHTTPError

BROKER_URL = "http://localhost:8000"


def main() -> None:
    print("=== SIP Python SDK – Capability Discovery Demo ===\n")
    print(f"Broker URL: {BROKER_URL}\n")

    client = CapabilityDiscoveryClient(BROKER_URL)

    # -----------------------------------------------------------------
    # 1. List all capabilities
    # -----------------------------------------------------------------
    print("1. Listing all registered capabilities...")
    try:
        caps = client.list_capabilities()
        print(f"   Found {len(caps)} capabilities:")
        for cap in caps:
            bindings = [b.value for b in cap.supported_bindings]
            print(f"   - {cap.capability_id}: {cap.name} [{', '.join(bindings)}]")
    except (SIPHTTPError, SIPClientError) as exc:
        print(f"   ERROR: {exc}")
        print("\nThe broker is not running. Start it with:")
        print("    uvicorn sip.broker.service:app --reload")
        sys.exit(1)

    if not caps:
        print("   No capabilities registered. Nothing to demonstrate further.")
        sys.exit(0)

    # -----------------------------------------------------------------
    # 2. Get a specific capability by ID
    # -----------------------------------------------------------------
    first_cap_id = caps[0].capability_id
    print(f"\n2. Getting capability '{first_cap_id}'...")
    try:
        cap = client.get_capability(first_cap_id)
        print(f"   capability_id:   {cap.capability_id}")
        print(f"   name:            {cap.name}")
        print(f"   description:     {cap.description}")
        print(f"   operation_class: {cap.operation_class.value}")
        print(f"   risk_level:      {cap.risk_level.value}")
        print(f"   required_scopes: {cap.required_scopes}")
    except SIPHTTPError as exc:
        print(f"   HTTP error {exc.status_code}: {exc.response_body}")
    except SIPClientError as exc:
        print(f"   Client error: {exc}")

    # -----------------------------------------------------------------
    # 3. Discover capabilities with a query
    # -----------------------------------------------------------------
    print("\n3. Discovering capabilities for intent 'retrieve_document'...")
    try:
        disc_req = DiscoveryRequest(
            intent_name="retrieve_document",
            intent_domain="knowledge_management",
            max_results=5,
        )
        response = client.discover_capabilities(disc_req)
        print(f"   Total candidates found: {response.total}")
        print(f"   Local candidates:       {response.local_count}")
        print(f"   Remote candidates:      {response.remote_count}")
        for i, candidate in enumerate(response.candidates, 1):
            print(f"\n   Candidate {i}:")
            print(f"     capability_id: {candidate.capability_id}")
            print(f"     name:          {candidate.name}")
            print(f"     score:         {candidate.score:.3f}")
            print(f"     bindings:      {candidate.supported_bindings}")
    except SIPHTTPError as exc:
        print(f"   HTTP error {exc.status_code}: {exc.response_body}")
    except SIPClientError as exc:
        print(f"   Client error: {exc}")

    # -----------------------------------------------------------------
    # 4. Open-ended discovery (no filters)
    # -----------------------------------------------------------------
    print("\n4. Open-ended capability discovery (no filters)...")
    try:
        response = client.discover_capabilities()
        print(f"   Total candidates returned: {response.total}")
    except (SIPHTTPError, SIPClientError) as exc:
        print(f"   ERROR: {exc}")

    print("\n=== Capability discovery demo complete. ===")


if __name__ == "__main__":
    main()
