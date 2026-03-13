# SIP Quickstart Guide

Welcome to the **Semantic Intent Protocol (SIP)**. This guide gets you from zero to a working SIP integration in minutes.

---

## What SIP Does

SIP is a **deterministic control plane protocol** that sits between intent-producing systems (AI agents, software systems) and the execution systems that carry out the work.

The basic mental model:

1. An AI agent or software system proposes an `IntentEnvelope`
2. SIP validates and authorizes it
3. SIP returns a `NegotiationResult` and `ExecutionPlan`
4. External systems execute the action

```
AI Agent / Software System
       ↓
 IntentEnvelope  ← structured, typed intent
       ↓
  SIP Control Plane  ← validates, negotiates capability, enforces policy
       ↓
  ExecutionPlan   ← deterministic, fully specified plan
       ↓
  external execution system (REST / gRPC / MCP / A2A / RAG)
```

**Key guarantees:**

- Natural language is never executed — it may appear as an audit annotation only.
- Every execution plan is deterministic and reproducible.
- Every processed intent produces an immutable audit record.
- Trust, scopes, and delegation chain are explicit on every envelope.

---

## Installation

### Prerequisites

- Python 3.11 or later
- (Optional) Go 1.21+ for the Go SDK

### Install the Python SDK

```bash
# Clone the repository
git clone https://github.com/ansharma0923/semantic-intent-protocol
cd semantic-intent-protocol

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate        # Linux / macOS
# .venv\Scripts\activate         # Windows

# Install in development mode (includes all extras)
pip install -e ".[dev]"
```

### Run the examples

```bash
python examples/sdk_basic_usage.py
python examples/knowledge_retrieval.py
python examples/restaurant_booking.py
```

---

## Creating an IntentEnvelope

An `IntentEnvelope` is the root SIP protocol object. It carries a semantic intent from an actor to a target capability.

```python
from sip.sdk import (
    ActorType,
    BindingType,
    OperationClass,
    TrustLevel,
    build_actor,
    build_intent_envelope,
    build_protocol_binding,
    build_provenance,
    validate_envelope,
    to_json,
)

# 1. Create the actor (who is making this request)
actor = build_actor(
    actor_id="my-ai-agent",
    name="My AI Agent",
    actor_type=ActorType.AI_AGENT,
    trust_level=TrustLevel.INTERNAL,
    scopes=["sip:knowledge:read"],
)

# 2. (Optional) Create a provenance block for delegation tracing
provenance = build_provenance(
    originator="user-alice",
    submitted_by="my-ai-agent",
    delegation_chain=["user-alice"],
    delegation_purpose="Automated knowledge retrieval",
    authority_scope=["sip:knowledge:read"],
)

# 3. Assemble the IntentEnvelope
envelope = build_intent_envelope(
    actor=actor,
    intent_name="retrieve_document",
    intent_domain="knowledge_management",
    operation_class=OperationClass.RETRIEVE,
    outcome_summary="Retrieve the SIP architecture document.",
    target_id="sip.knowledge.retrieve",
    intent_parameters={"document_id": "arch-doc-001"},
    natural_language_hint="Get me the architecture document",
    provenance=provenance,
)

# 4. Validate it
result = validate_envelope(envelope)
assert result.valid, result.errors

# 5. Serialize to JSON
json_str = to_json(envelope, indent=2)
print(json_str)
```

See `examples/sdk_basic_usage.py` for a complete walkthrough.

---

## Submitting an Intent to the Broker

### Start the broker

```bash
make broker
# → http://127.0.0.1:8000/docs
```

Or start it directly:

```bash
uvicorn sip.broker.service:app --host 127.0.0.1 --port 8000 --reload
```

### Submit using the Python BrokerClient

```python
from sip.sdk import BrokerClient
from sip.sdk.errors import SIPHTTPError

client = BrokerClient("http://localhost:8000")

# Health check
health = client.health()
print(f"Broker status: {health['status']}  capabilities: {health['capabilities']}")

# Submit the envelope
try:
    response = client.submit_intent(envelope)
    print(f"Outcome:      {response['outcome']}")
    print(f"Action taken: {response['action_taken']}")
    print(f"Plan ID:      {response['plan_id']}")
except SIPHTTPError as exc:
    print(f"HTTP {exc.status_code}: {exc.response_body}")
```

### In-process broker (no server required)

For testing and demos you can run the broker entirely in-process:

```python
from sip.broker.service import BrokerService
from sip.registry.bootstrap import build_seeded_registry

broker = BrokerService(registry=build_seeded_registry())
result = broker.handle(envelope)

print(result.negotiation_result.selected_capability.capability_id)
print(result.execution_plan.selected_binding)
print(result.audit_record.outcome_summary)
```

See `examples/end_to_end_demo/python_client_demo.py` for a full demo.

---

## Capability Discovery

SIP brokers expose a REST API for listing and querying registered capabilities.

### List all capabilities

```python
from sip.sdk import CapabilityDiscoveryClient

discovery = CapabilityDiscoveryClient("http://localhost:8000")
caps = discovery.list_capabilities()
for cap in caps:
    print(f"{cap.capability_id}: {cap.name}  (risk={cap.risk_level.value})")
```

### Semantic discovery query

```python
from sip.sdk import DiscoveryRequest

request = DiscoveryRequest(
    intent_name="retrieve_document",
    intent_domain="knowledge_management",
    max_results=5,
)
response = discovery.discover(request)
print(f"Found {response.total} candidates")
for candidate in response.candidates:
    print(f"  {candidate.capability_id}  score={candidate.score:.2f}")
```

See `examples/sdk_capability_discovery_demo.py` for more discovery patterns.

---

## Federated Brokers

SIP brokers can discover capabilities across peer brokers using the federation model.
A `FederationConfig` defines which peer brokers to query and how much to trust their results:

| Trust Level | Discovery | Routing |
|-------------|-----------|---------|
| `DISCOVERY` | ✓         | ✗       |
| `ROUTING`   | ✓         | ✓       |
| `FULL`      | ✓         | ✓       |

```python
from sip.broker.federation import FederationConfig, FederatedPeer, PeerTrustLevel
from sip.broker.service import BrokerService
from sip.registry.service import CapabilityRegistryService

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

broker = BrokerService(
    registry=CapabilityRegistryService(),
    federation=federation,
)
```

See the [end-to-end demo](../examples/end_to_end_demo/demo_overview.md) and
`examples/federation_demo.py` for a complete multi-broker walkthrough.

---

## Next Steps

| Resource | Description |
|----------|-------------|
| [docs/architecture.md](architecture.md) | Full system architecture |
| [docs/python-sdk.md](python-sdk.md) | Complete Python SDK reference |
| [docs/security-model.md](security-model.md) | Trust, scopes, and policy |
| [docs/examples-walkthrough.md](examples-walkthrough.md) | Guided examples walkthrough |
| [examples/end_to_end_demo/](../examples/end_to_end_demo/demo_overview.md) | End-to-end multi-SDK demo |
| [sdk/go/](../sdk/go/) | Go SDK |
