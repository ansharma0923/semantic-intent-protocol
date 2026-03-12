"""SDK Provenance Demo.

Demonstrates the SIP Python SDK's provenance and identity helpers:
- Building a provenance block
- Computing the effective scope set
- Summarizing provenance
- Applying identity headers to an envelope

Run this example:
    python examples/sdk_provenance_demo.py
"""

from __future__ import annotations

from sip.sdk import (
    build_actor,
    build_intent_envelope,
    build_provenance,
)
from sip.sdk.helpers import (
    apply_identity_headers_to_envelope,
    compute_effective_scope_set,
    summarize_provenance,
)


def main() -> None:
    print("=== SIP Python SDK – Provenance Demo ===\n")

    # -----------------------------------------------------------------
    # 1. Create an agent acting on behalf of a user
    # -----------------------------------------------------------------
    print("1. Creating agent actor with delegated authority...")
    agent = build_actor(
        actor_id="workflow-agent",
        name="Workflow Agent",
        actor_type="ai_agent",
        trust_level="internal",
        scopes=["sip:knowledge:read", "sip:data:write", "sip:admin:audit"],
    )
    print(f"   Actor scopes: {agent.scopes}")

    # -----------------------------------------------------------------
    # 2. Build a provenance block (delegation from user to agent)
    # -----------------------------------------------------------------
    print("\n2. Building provenance (user → agent delegation)...")
    provenance = build_provenance(
        originator="user-alice",
        submitted_by="workflow-agent",
        delegation_chain=["user-alice"],
        on_behalf_of="user-alice",
        delegation_purpose="Automated data retrieval workflow",
        # The user only granted a subset of scopes
        authority_scope=["sip:knowledge:read", "sip:data:write"],
    )
    print(f"   originator:       {provenance.originator}")
    print(f"   submitted_by:     {provenance.submitted_by}")
    print(f"   delegation_chain: {provenance.delegation_chain}")
    print(f"   authority_scope:  {provenance.authority_scope}")

    # -----------------------------------------------------------------
    # 3. Build envelope with provenance
    # -----------------------------------------------------------------
    print("\n3. Building envelope with provenance...")
    envelope = build_intent_envelope(
        actor=agent,
        intent_name="retrieve_document",
        intent_domain="knowledge_management",
        operation_class="retrieve",
        outcome_summary="Retrieve the quarterly report on behalf of Alice.",
        provenance=provenance,
    )
    print(f"   envelope.intent_id: {envelope.intent_id}")
    print(f"   envelope.provenance.originator: {envelope.provenance.originator}")  # type: ignore[union-attr]

    # -----------------------------------------------------------------
    # 4. Compute the effective scope set
    # -----------------------------------------------------------------
    print("\n4. Computing effective scope set...")
    effective = compute_effective_scope_set(envelope)
    print(f"   Agent scopes:     {sorted(agent.scopes)}")
    print(f"   Authority scope:  {sorted(provenance.authority_scope or [])}")
    print(f"   Effective scopes: {sorted(effective)}")
    # The effective scopes are the intersection:
    # agent has 'sip:admin:audit', but authority_scope doesn't grant it
    print(f"   'sip:admin:audit' excluded: {'sip:admin:audit' not in effective}")

    # -----------------------------------------------------------------
    # 5. Summarize provenance
    # -----------------------------------------------------------------
    print("\n5. Provenance summary...")
    summary = summarize_provenance(envelope)
    for key, value in summary.items():
        print(f"   {key}: {value}")

    # -----------------------------------------------------------------
    # 6. Envelope without provenance
    # -----------------------------------------------------------------
    print("\n6. Envelope without provenance...")
    simple_actor = build_actor(
        actor_id="simple-svc",
        name="Simple Service",
        scopes=["sip:knowledge:read"],
    )
    simple_envelope = build_intent_envelope(
        actor=simple_actor,
        intent_name="retrieve_document",
        intent_domain="knowledge_management",
        operation_class="retrieve",
        outcome_summary="Retrieve a document.",
    )
    no_prov_summary = summarize_provenance(simple_envelope)
    print(f"   provenance summary (no block): {no_prov_summary}")  # → {}

    no_prov_scopes = compute_effective_scope_set(simple_envelope)
    print(f"   effective scopes (no block):   {sorted(no_prov_scopes)}")

    # -----------------------------------------------------------------
    # 7. Apply identity headers
    # -----------------------------------------------------------------
    print("\n7. Applying identity headers (trusted gateway scenario)...")
    # Simulate headers injected by an API gateway after authenticating the request
    gateway_headers = {
        "x-actor-id": "gateway-verified-agent",
        "x-actor-name": "Gateway Verified Agent",
        "x-trust-level": "privileged",
        "x-scopes": "sip:knowledge:read,sip:data:write",
    }
    updated = apply_identity_headers_to_envelope(simple_envelope, gateway_headers, trusted=True)
    print(f"   original actor_id: {simple_envelope.actor.actor_id}")
    print(f"   updated actor_id:  {updated.actor.actor_id}")
    print(f"   updated trust:     {updated.actor.trust_level.value}")
    print(f"   updated scopes:    {updated.actor.scopes}")

    print("\n=== Provenance demo complete. ===")


if __name__ == "__main__":
    main()
