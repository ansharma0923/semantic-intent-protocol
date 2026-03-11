"""Protocol extensions demo for SIP.

Demonstrates how the SIP extension mechanism works:

1. Creating an IntentEnvelope with custom extension fields
2. Showing that unknown extensions are preserved through serialization/deserialization
3. Showing that invalid extension keys are rejected
4. Showing that reserved core field names cannot be used as extensions
5. Extensions on CapabilityDescriptor, NegotiationResult, and AuditRecord
"""

from __future__ import annotations

import json

from pydantic import ValidationError

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
from sip.negotiation.results import NegotiationResult
from sip.observability.audit import ActionTaken, AuditRecord, OutcomeSummary
from sip.registry.models import (
    CapabilityDescriptor,
    ProviderMetadata,
    SchemaReference,
)


def _separator(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print("=" * 60)


# ---------------------------------------------------------------------------
# 1. IntentEnvelope with extensions
# ---------------------------------------------------------------------------

_separator("1. IntentEnvelope with extension fields")

envelope = IntentEnvelope(
    actor=ActorDescriptor(
        actor_id="agent-demo",
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
    ),
    desired_outcome=DesiredOutcome(summary="Get the architecture doc"),
    protocol_bindings=[ProtocolBinding(binding_type=BindingType.REST)],
    # Custom extensions: use "x_" prefix or "vendor.key" style
    extensions={
        "x_routing_hint": "us-east-1",
        "x_request_source": "gateway",
        "acme.priority": "high",
        "org.demo.internal_ref": "REQ-1234",
    },
)

print(f"Envelope intent_id: {envelope.intent_id}")
print(f"Extensions: {json.dumps(envelope.extensions, indent=2)}")

# ---------------------------------------------------------------------------
# 2. Extensions preserved through serialization round-trip
# ---------------------------------------------------------------------------

_separator("2. Extensions preserved through serialization round-trip")

# Serialize to JSON
envelope_json = envelope.model_dump_json(indent=2)

# Deserialize back
restored_envelope = IntentEnvelope.model_validate_json(envelope_json)

print(f"Original extensions:  {envelope.extensions}")
print(f"Restored extensions:  {restored_envelope.extensions}")
assert envelope.extensions == restored_envelope.extensions
print("✓ Extensions preserved exactly after round-trip")

# ---------------------------------------------------------------------------
# 3. Invalid extension keys are rejected
# ---------------------------------------------------------------------------

_separator("3. Invalid extension keys are rejected")

invalid_cases = [
    ("plain_key", "plain_key"),          # no x_ prefix, no vendor.
    ("UPPER_CASE", "UPPER_CASE"),        # uppercase without valid structure
]

for label, key in invalid_cases:
    try:
        IntentEnvelope(
            actor=envelope.actor,
            target=envelope.target,
            intent=envelope.intent,
            desired_outcome=envelope.desired_outcome,
            extensions={key: "value"},
        )
        print(f"  ✗ Expected rejection for key '{key}' – was incorrectly accepted")
    except ValidationError as exc:
        print(f"  ✓ Key '{key}' correctly rejected: {exc.errors()[0]['msg'][:80]}")

# ---------------------------------------------------------------------------
# 4. Reserved core field names cannot be used as extension keys
# ---------------------------------------------------------------------------

_separator("4. Reserved core field names rejected as extension keys")

reserved_cases = ["intent_id", "actor", "trace_id", "sip_version"]

for field_name in reserved_cases:
    try:
        IntentEnvelope(
            actor=envelope.actor,
            target=envelope.target,
            intent=envelope.intent,
            desired_outcome=envelope.desired_outcome,
            extensions={field_name: "override"},
        )
        print(f"  ✗ Expected rejection for reserved field '{field_name}'")
    except ValidationError as exc:
        print(f"  ✓ Reserved field '{field_name}' correctly rejected")

# ---------------------------------------------------------------------------
# 5. CapabilityDescriptor with extensions
# ---------------------------------------------------------------------------

_separator("5. CapabilityDescriptor with extensions")

cap = CapabilityDescriptor(
    capability_id="retrieve_document",
    name="Retrieve Document",
    description="Retrieves documents from the knowledge base",
    provider=ProviderMetadata(provider_id="kb-service", provider_name="Knowledge Base"),
    intent_domains=["knowledge_management"],
    input_schema=SchemaReference(
        description="Document query",
        properties={"document_id": "string"},
        required_fields=["document_id"],
    ),
    output_schema=SchemaReference(description="Document content"),
    operation_class=OperationClass.RETRIEVE,
    supported_bindings=[BindingType.REST],
    extensions={
        "x_sla_tier": "gold",
        "x_region": "us-east-1",
        "acme.feature_flags": ["fast_path", "cache_enabled"],
    },
)

print(f"Capability: {cap.capability_id}")
print(f"Extensions: {json.dumps(cap.extensions, indent=2)}")
print("✓ Capability extensions accepted and stored")

# ---------------------------------------------------------------------------
# 6. NegotiationResult with extensions
# ---------------------------------------------------------------------------

_separator("6. NegotiationResult with extensions")

result = NegotiationResult(
    intent_id=envelope.intent_id,
    extensions={
        "x_match_strategy": "strict_domain",
        "x_confidence": 0.97,
    },
)
print(f"NegotiationResult extensions: {result.extensions}")
print("✓ NegotiationResult extensions accepted")

# ---------------------------------------------------------------------------
# 7. AuditRecord with extensions
# ---------------------------------------------------------------------------

_separator("7. AuditRecord with extensions")

audit = AuditRecord(
    trace_id=envelope.trace_id,
    intent_id=envelope.intent_id,
    actor_id=envelope.actor.actor_id,
    actor_type=envelope.actor.actor_type.value,
    intent_name=envelope.intent.intent_name,
    intent_domain=envelope.intent.intent_domain,
    operation_class=envelope.intent.operation_class.value,
    action_taken=ActionTaken.PLAN_CREATED,
    policy_allowed=True,
    outcome_summary=OutcomeSummary.SUCCESS,
    extensions={
        "x_compliance_tag": "SOC2",
        "org.internal.ticket": "INC-9999",
    },
)
print(f"AuditRecord extensions: {audit.extensions}")
print("✓ AuditRecord extensions accepted")

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

_separator("Summary")

print("""
SIP Protocol Extension Points:

✓  Extensions are optional on all core protocol objects
✓  Extension keys must use 'x_<name>' or '<vendor>.<name>' format
✓  Invalid extension keys (plain names) are rejected at validation time
✓  Reserved core field names cannot be redefined in extensions
✓  Unknown extensions are preserved exactly through serialization round-trips
✓  Extensions never affect core protocol semantics or processing
✓  Backward compatibility: objects without extensions work identically to v0.1
""")
