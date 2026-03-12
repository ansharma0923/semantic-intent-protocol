"""SDK Basic Usage Example.

Demonstrates the core SIP Python SDK features:
- Building protocol objects with builders
- Validating envelopes
- Serializing to dict and JSON
- Round-trip deserialization
- Working with provenance

Run this example:
    python examples/sdk_basic_usage.py
"""

from __future__ import annotations

import json

from sip.sdk import (
    ActorType,
    BindingType,
    OperationClass,
    TrustLevel,
    build_actor,
    build_intent_envelope,
    build_protocol_binding,
    build_provenance,
    build_target,
    parse_intent_envelope,
    to_dict,
    to_json,
    validate_envelope,
)


def main() -> None:
    print("=== SIP Python SDK – Basic Usage ===\n")

    # -----------------------------------------------------------------
    # 1. Build an actor
    # -----------------------------------------------------------------
    print("1. Building an actor...")
    actor = build_actor(
        actor_id="my-ai-agent",
        name="My AI Agent",
        actor_type=ActorType.AI_AGENT,
        trust_level=TrustLevel.INTERNAL,
        scopes=["sip:knowledge:read", "sip:data:write"],
    )
    print(f"   actor_id:    {actor.actor_id}")
    print(f"   actor_type:  {actor.actor_type.value}")
    print(f"   trust_level: {actor.trust_level.value}")
    print(f"   scopes:      {actor.scopes}")

    # -----------------------------------------------------------------
    # 2. Build a target
    # -----------------------------------------------------------------
    print("\n2. Building a target...")
    target = build_target(target_type="capability", target_id="sip.knowledge.retrieve")
    print(f"   target_type: {target.target_type.value}")
    print(f"   target_id:   {target.target_id}")

    # -----------------------------------------------------------------
    # 3. Build a provenance block
    # -----------------------------------------------------------------
    print("\n3. Building provenance...")
    provenance = build_provenance(
        originator="user-alice",
        submitted_by="my-ai-agent",
        delegation_chain=["user-alice"],
        delegation_purpose="Automated knowledge retrieval workflow",
        authority_scope=["sip:knowledge:read"],
    )
    print(f"   originator:       {provenance.originator}")
    print(f"   submitted_by:     {provenance.submitted_by}")
    print(f"   delegation_chain: {provenance.delegation_chain}")

    # -----------------------------------------------------------------
    # 4. Build a protocol binding
    # -----------------------------------------------------------------
    print("\n4. Building a protocol binding...")
    binding = build_protocol_binding(
        binding_type=BindingType.REST,
        endpoint="https://knowledge-api.example.com",
    )
    print(f"   binding_type: {binding.binding_type.value}")
    print(f"   endpoint:     {binding.endpoint}")

    # -----------------------------------------------------------------
    # 5. Build an IntentEnvelope
    # -----------------------------------------------------------------
    print("\n5. Building an IntentEnvelope...")
    envelope = build_intent_envelope(
        actor=actor,
        intent_name="retrieve_document",
        intent_domain="knowledge_management",
        operation_class=OperationClass.RETRIEVE,
        outcome_summary="Retrieve the SIP architecture document.",
        target_type="capability",
        target_id="sip.knowledge.retrieve",
        intent_parameters={"document_id": "arch-doc-001"},
        natural_language_hint="Get me the architecture document",
        provenance=provenance,
        protocol_bindings=[binding],
    )
    print(f"   intent_id:    {envelope.intent_id}")
    print(f"   trace_id:     {envelope.trace_id}")
    print(f"   sip_version:  {envelope.sip_version}")
    print(f"   intent_name:  {envelope.intent.intent_name}")

    # -----------------------------------------------------------------
    # 6. Validate the envelope
    # -----------------------------------------------------------------
    print("\n6. Validating the envelope...")
    result = validate_envelope(envelope)
    print(f"   valid:  {result.valid}")
    if result.errors:
        print(f"   errors: {result.errors}")
    else:
        print("   No validation errors.")

    # -----------------------------------------------------------------
    # 7. Serialize to dict and JSON
    # -----------------------------------------------------------------
    print("\n7. Serializing...")
    d = to_dict(envelope)
    print(f"   to_dict() keys: {sorted(d.keys())}")

    j = to_json(envelope, indent=2)
    print(f"   to_json() length: {len(j)} chars")

    # -----------------------------------------------------------------
    # 8. Round-trip deserialization
    # -----------------------------------------------------------------
    print("\n8. Round-trip deserialization...")
    restored = parse_intent_envelope(j)
    print(f"   intent_id matches: {restored.intent_id == envelope.intent_id}")
    print(f"   actor_id matches:  {restored.actor.actor_id == envelope.actor.actor_id}")
    print(f"   provenance preserved: {restored.provenance is not None}")
    print(f"   originator:           {restored.provenance.originator}")  # type: ignore[union-attr]

    # -----------------------------------------------------------------
    # 9. Inspect the serialized envelope
    # -----------------------------------------------------------------
    print("\n9. Envelope JSON (abbreviated):")
    envelope_dict = json.loads(j)
    print(f"   actor.actor_id: {envelope_dict['actor']['actor_id']}")
    print(f"   actor.actor_type: {envelope_dict['actor']['actor_type']}")
    print(f"   intent.intent_name: {envelope_dict['intent']['intent_name']}")
    print(f"   provenance.originator: {envelope_dict['provenance']['originator']}")

    print("\n=== Example complete. ===")


if __name__ == "__main__":
    main()
