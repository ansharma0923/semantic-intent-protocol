# SIP Python SDK

The `sip.sdk` module provides a clean, stable public API surface for building
Python applications that use the Semantic Intent Protocol.

## What is the SIP Python SDK?

The SIP Python SDK is the official Python library for interacting with the
Semantic Intent Protocol. It sits on top of the SIP reference implementation
and provides:

- **Protocol models** — typed Pydantic models for every SIP object
- **Builders** — convenience constructors for common objects
- **Serialization helpers** — convert objects to dict/JSON and back
- **HTTP clients** — submit intents and query capabilities from a broker
- **Provenance helpers** — work with identity, delegation, and scope sets
- **Custom exceptions** — clean, predictable error hierarchy

---

## Installation

```bash
pip install semantic-intent-protocol
```

For HTTP client support (`BrokerClient`, `CapabilityDiscoveryClient`), install
`httpx` as well:

```bash
pip install semantic-intent-protocol httpx
```

Or install with the optional `[http]` extra:

```bash
pip install "semantic-intent-protocol[http]"
```

---

## Public imports

All public SDK symbols are importable from `sip.sdk`:

```python
from sip.sdk import (
    # Protocol models
    IntentEnvelope,
    CapabilityDescriptor,
    NegotiationResult,
    ExecutionPlan,
    AuditRecord,

    # Enums
    ActorType, BindingType, DataSensitivity, DeterminismLevel,
    MessageType, OperationClass, Priority, TargetType, TrustLevel,

    # Builders
    build_actor, build_intent_envelope, build_provenance,
    build_target, build_protocol_binding,

    # Serialization
    to_dict, to_json,
    parse_intent_envelope, parse_capability_descriptor,
    parse_execution_plan, parse_negotiation_result, parse_audit_record,

    # HTTP clients
    BrokerClient, CapabilityDiscoveryClient,

    # Validation
    validate_envelope,

    # Provenance helpers
    apply_identity_headers_to_envelope,
    compute_effective_scope_set,
    summarize_provenance,
    merge_identity_context,

    # Exceptions
    SIPError, SIPValidationError, SIPClientError, SIPHTTPError,
)
```

---

## Creating an IntentEnvelope

The simplest way to create an `IntentEnvelope` is with the builder helpers:

```python
from sip.sdk import build_actor, build_intent_envelope

actor = build_actor(
    actor_id="my-service",
    name="My Service",
    actor_type="service",          # or ActorType.SERVICE
    trust_level="internal",        # or TrustLevel.INTERNAL
    scopes=["sip:knowledge:read"],
)

envelope = build_intent_envelope(
    actor=actor,
    intent_name="retrieve_document",
    intent_domain="knowledge_management",
    operation_class="retrieve",    # or OperationClass.RETRIEVE
    outcome_summary="Retrieve the SIP architecture document.",
    intent_parameters={"document_id": "arch-doc-001"},
)

print(envelope.intent_id)       # UUID
print(envelope.sip_version)     # "0.1"
print(envelope.actor.actor_id)  # "my-service"
```

You can also construct models directly using Pydantic:

```python
from sip.sdk import (
    ActorDescriptor, ActorType, IntentEnvelope, IntentPayload,
    DesiredOutcome, TargetDescriptor, TargetType, OperationClass, TrustLevel,
)

envelope = IntentEnvelope(
    actor=ActorDescriptor(
        actor_id="my-service",
        actor_type=ActorType.SERVICE,
        name="My Service",
        trust_level=TrustLevel.INTERNAL,
        scopes=["sip:knowledge:read"],
    ),
    target=TargetDescriptor(target_type=TargetType.CAPABILITY),
    intent=IntentPayload(
        intent_name="retrieve_document",
        intent_domain="knowledge_management",
        operation_class=OperationClass.RETRIEVE,
    ),
    desired_outcome=DesiredOutcome(
        summary="Retrieve the architecture document.",
    ),
)
```

---

## Validating objects

```python
from sip.sdk import validate_envelope

result = validate_envelope(envelope)
if result.valid:
    print("Envelope is valid")
else:
    for error in result.errors:
        print(f"  Error: {error}")
```

---

## Serializing and deserializing

```python
from sip.sdk import to_dict, to_json, parse_intent_envelope

# Serialize to dict (JSON-safe types)
d = to_dict(envelope)
print(type(d))              # dict

# Serialize to JSON string
json_str = to_json(envelope, indent=2)
print(type(json_str))       # str

# Deserialize from JSON string
restored = parse_intent_envelope(json_str)
assert restored.intent_id == envelope.intent_id

# Deserialize from dict
restored2 = parse_intent_envelope(d)
assert restored2.intent_id == envelope.intent_id
```

Parse helpers are available for all major model types:

```python
from sip.sdk import (
    parse_intent_envelope,
    parse_capability_descriptor,
    parse_execution_plan,
    parse_negotiation_result,
    parse_audit_record,
)
```

---

## Using the BrokerClient

```python
from sip.sdk import BrokerClient, build_actor, build_intent_envelope
from sip.sdk.errors import SIPHTTPError, SIPClientError

client = BrokerClient("http://localhost:8000")

# Health check
health = client.health()
print(health["status"])          # "ok"
print(health["capabilities"])    # number of registered capabilities

# Submit an intent
actor = build_actor("my-svc", "My Service", scopes=["sip:knowledge:read"])
envelope = build_intent_envelope(
    actor=actor,
    intent_name="retrieve_document",
    intent_domain="knowledge_management",
    operation_class="retrieve",
    outcome_summary="Get the document.",
)

try:
    result = client.submit_intent(envelope)
    print(result["action_taken"])    # e.g. "plan_created"
    print(result["outcome"])         # e.g. "success"
except SIPHTTPError as exc:
    print(f"HTTP {exc.status_code}: {exc.response_body}")
except SIPClientError as exc:
    print(f"Client error: {exc}")
```

You can also submit from a dict or JSON string:

```python
# From a dict
result = client.submit_intent_dict(to_dict(envelope))

# From a JSON string
result = client.submit_intent_json(to_json(envelope))
```

---

## Using the CapabilityDiscoveryClient

```python
from sip.sdk import CapabilityDiscoveryClient
from sip.broker.discovery import DiscoveryRequest

client = CapabilityDiscoveryClient("http://localhost:8000")

# List all capabilities
caps = client.list_capabilities()
for cap in caps:
    print(f"{cap.capability_id}: {cap.name}")

# Get a specific capability
cap = client.get_capability("sip.knowledge.retrieve")
print(cap.description)

# Discover capabilities for a query
response = client.discover_capabilities(
    DiscoveryRequest(
        intent_name="retrieve_document",
        intent_domain="knowledge_management",
        max_results=5,
    )
)
print(f"Found {response.total} candidates")
for candidate in response.candidates:
    print(f"  {candidate.capability_id} (score: {candidate.score:.2f})")
```

---

## Working with provenance

Provenance captures the delegation chain from the original human to the
current submitting actor. The policy engine uses this for anti-laundering
checks.

```python
from sip.sdk import build_actor, build_intent_envelope, build_provenance
from sip.sdk.helpers import compute_effective_scope_set, summarize_provenance

# Agent acting on behalf of a user
agent = build_actor(
    actor_id="my-agent",
    name="My Agent",
    actor_type="ai_agent",
    scopes=["sip:knowledge:read", "sip:data:write", "sip:admin:*"],
)

# User only granted a subset of scopes
provenance = build_provenance(
    originator="user-alice",
    submitted_by="my-agent",
    delegation_chain=["user-alice"],
    delegation_purpose="Automated workflow",
    authority_scope=["sip:knowledge:read"],  # subset of agent's scopes
)

envelope = build_intent_envelope(
    actor=agent,
    intent_name="retrieve_document",
    intent_domain="knowledge_management",
    operation_class="retrieve",
    outcome_summary="Get the document.",
    provenance=provenance,
)

# The effective scope set is the intersection
effective = compute_effective_scope_set(envelope)
print(effective)   # frozenset({'sip:knowledge:read'})
                   # 'sip:data:write' and 'sip:admin:*' are excluded

# Human-readable summary
summary = summarize_provenance(envelope)
print(summary["originator"])         # "user-alice"
print(summary["delegation_depth"])   # 1
```

---

## Error handling

The SDK raises typed exceptions for all error conditions:

| Exception | When raised |
|-----------|-------------|
| `SIPError` | Base class for all SIP SDK errors |
| `SIPValidationError` | Object fails validation (`.errors` contains details) |
| `SIPClientError` | Client configuration or transport error |
| `SIPHTTPError` | Non-2xx HTTP response (`.status_code`, `.response_body`) |

```python
from sip.sdk.errors import SIPError, SIPValidationError, SIPHTTPError, SIPClientError

try:
    client.submit_intent(envelope)
except SIPValidationError as exc:
    for e in exc.errors:
        print(f"Validation: {e}")
except SIPHTTPError as exc:
    print(f"HTTP {exc.status_code}: {exc.response_body}")
except SIPClientError as exc:
    print(f"Client: {exc}")
except SIPError as exc:
    print(f"SIP error: {exc}")
```

---

## Example code snippets

See the `examples/` directory for runnable examples:

- `examples/sdk_basic_usage.py` — building, validating, and serializing envelopes
- `examples/sdk_provenance_demo.py` — provenance and identity helpers
- `examples/sdk_broker_client_demo.py` — submitting intents to a broker
- `examples/sdk_capability_discovery_demo.py` — discovering capabilities

---

## Module structure

```
sip/sdk/
├── __init__.py          # Public API surface (all re-exports)
├── models.py            # Model re-exports from internal modules
├── errors.py            # SIPError, SIPValidationError, SIPHTTPError, SIPClientError
├── serialization.py     # to_dict, to_json, parse_* helpers
├── builders.py          # build_actor, build_intent_envelope, build_provenance, ...
├── clients.py           # BrokerClient, CapabilityDiscoveryClient
└── helpers.py           # apply_identity_headers_to_envelope, compute_effective_scope_set, ...
```

Internal implementation modules in `sip/envelope/`, `sip/registry/`,
`sip/negotiation/`, `sip/policy/`, `sip/observability/`, `sip/broker/`, and
`sip/translator/` remain available for direct use but are considered internal.
The `sip.sdk` namespace is the recommended public interface.

---

## Protocol Vector Compatibility

The Python SDK must pass all tests in [`tests/protocol_vectors/`](../tests/protocol_vectors/). These tests load the canonical JSON fixtures from [`protocol-vectors/`](../protocol-vectors/) and verify that:

1. Each vector parses without errors into the corresponding protocol model.
2. Round-trip serialization (`to_dict` → `parse_*`) produces an object equal to the original.
3. All required fields are preserved.

```bash
pytest tests/protocol_vectors/ -v
```

See [`docs/governance.md`](governance.md) for the full SDK compatibility expectations.
