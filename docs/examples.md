# SIP Examples

## Representative Use Cases

This section describes how SIP applies to concrete, real-world scenarios.
Each use case shows the intent, what SIP does, and the resulting execution flow.

---

### Use Case 1: Enterprise Knowledge Retrieval

**Intent:** Retrieve documents about "Q4 2023 financial results" from the enterprise knowledge base.

**What SIP does:**
- Validates the actor holds `sip.knowledge.read` scope
- Matches `retrieve_document` intent to the `sip.knowledge.retrieve` capability
- Confirms trust level (`internal`) meets the capability minimum
- Produces an `ExecutionPlan` with grounded parameters for the RAG adapter

**Execution flow:**

```
Research Agent
   │  IntentEnvelope(intent_name="retrieve_document",
   │                  parameters={"query": "Q4 2023 financial results", "top_k": 5})
   ▼
SIP Broker → NegotiationResult(selected: sip.knowledge.retrieve, binding: rag)
           → ExecutionPlan(grounded_params={"query": "Q4 2023 financial results", "top_k": 5})
   ▼
RAG Adapter (external) → runs the retrieval query
```

See [`examples/knowledge_retrieval.py`](../examples/knowledge_retrieval.py).

---

### Use Case 2: Meeting / Table Booking

**Intent:** Reserve a restaurant table for 4 people at 7pm.

**What SIP does:**
- Validates the actor holds `sip.booking.write` scope
- Matches `reserve_table` intent to the booking capability
- Evaluates risk level (`medium`) — no human approval required for this actor
- Produces an `ExecutionPlan` with a REST POST specification

**Execution flow:**

```
User-facing Agent
   │  IntentEnvelope(intent_name="reserve_table",
   │                  operation_class=create,
   │                  parameters={"party_size": 4, "time": "19:00"})
   ▼
SIP Broker → NegotiationResult(selected: sip.booking.reserve, binding: rest)
           → ExecutionPlan(method=POST, path=/reservations, body={...})
   ▼
REST Adapter (external) → calls the booking API
```

See [`examples/restaurant_booking.py`](../examples/restaurant_booking.py).

---

### Use Case 3: Multi-Agent Coordination

**Intent:** Collect telemetry from an infrastructure system, then produce a customer-facing summary.

**What SIP does:**
- Processes two intents sharing the same `trace_id`
- Step 1: Routes `collect_telemetry` to the monitoring capability via gRPC
- Step 2: Routes `summarize_for_customer` to the reporting capability via A2A
- Each step produces a separate `ExecutionPlan` and `AuditRecord`

**Execution flow:**

```
Orchestrator Agent
   │  Intent 1: collect_telemetry (trace_id=abc123)
   ▼
SIP Broker → ExecutionPlan(binding: grpc) → gRPC monitoring service
   │
   │  Intent 2: summarize_for_customer (trace_id=abc123)
   ▼
SIP Broker → ExecutionPlan(binding: a2a) → Customer-facing summary agent
```

See [`examples/multi_agent_collaboration.py`](../examples/multi_agent_collaboration.py).

---

### Use Case 4: Infrastructure / Operations

**Intent:** Diagnose a reported network connectivity issue.

**What SIP does:**
- Validates `sip.network.read` scope
- Matches `diagnose_network_issue` to the network diagnostics capability
- Enforces `internal` trust minimum (network ops require internal+ trust)
- Produces a gRPC-ready `ExecutionPlan`

**Execution flow:**

```
Ops Agent / Monitoring System
   │  IntentEnvelope(intent_name="diagnose_network_issue",
   │                  operation_class=analyze,
   │                  parameters={"target_host": "db-server-01"})
   ▼
SIP Broker → NegotiationResult(selected: sip.network.diagnose, binding: grpc)
           → ExecutionPlan(service="diagnostics.NetworkService",
                           method="DiagnoseHost",
                           params={"target_host": "db-server-01"})
   ▼
gRPC Adapter (external) → calls the diagnostics service
```

See [`examples/network_troubleshooting.py`](../examples/network_troubleshooting.py).

---

### Use Case 5: Capability Discovery Across Federated Brokers

**Intent:** Discover all capabilities that handle `knowledge_management` intents across a distributed deployment.

**What SIP does:**
- Runs a semantic discovery query on the local broker
- Fans out the query to configured peer brokers via federation
- Aggregates and deduplicates candidates from all sources
- Returns a ranked list of capabilities with provenance (which broker hosts each)

**Execution flow:**

```
Client or Agent
   │  DiscoveryQuery(intent_domain="knowledge_management", operation_class=retrieve)
   ▼
Local SIP Broker → queries local registry
                → queries peer broker A (ROUTING trust)
                → queries peer broker B (ROUTING trust)
   ▼
Aggregated CapabilityList (ranked, with source broker noted)
```

See [`examples/distributed_brokers_demo.py`](../examples/distributed_brokers_demo.py).

---

## Introduction Demo

New to SIP? The shortest path to understanding:

```bash
python examples/public_intro_demo.py
```

This runs the complete SIP flow end-to-end in ~20 lines of code.
See [`examples/public_intro_demo.py`](../examples/public_intro_demo.py).

---

## Quick Start

```python
from sip.broker.service import BrokerService
from sip.envelope.models import *
from sip.registry.bootstrap import seed_registry
from sip.registry.service import CapabilityRegistryService

# Build a seeded registry and broker
registry = CapabilityRegistryService()
seed_registry(registry)
broker = BrokerService(registry=registry)

# Build and submit an intent
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
        parameters={"query": "architecture decisions"},
    ),
    desired_outcome=DesiredOutcome(summary="Retrieve architecture document"),
)

result = broker.handle(envelope)
print(result.audit_record.outcome_summary)  # success
print(result.execution_plan.selected_binding)  # rag
```

## Example 1: Knowledge Retrieval

Retrieves an enterprise document using a RAG or REST binding.

```bash
python examples/knowledge_retrieval.py
```

The example demonstrates:
- Building a `retrieve_document` intent
- RAG binding selection
- Policy allowing a read operation
- Execution plan with grounded parameters
- Audit record generation

## Example 2: Restaurant Booking

Books a restaurant table — a write operation.

```bash
python examples/restaurant_booking.py
```

The example demonstrates:
- Building a `reserve_table` write intent
- REST binding selection
- Scope checking (`sip:booking:write`)
- POST request generation by the REST adapter

## Example 3: Network Troubleshooting

Diagnoses a network issue via gRPC.

```bash
python examples/network_troubleshooting.py
```

The example demonstrates:
- Building a `diagnose_network_issue` analyze intent
- gRPC binding preference
- Fully qualified gRPC service name generation
- Network scope (`sip:network:read`) enforcement

## Example 4: Multi-Agent Collaboration

Two-step orchestration: collect telemetry, then summarize for customer.

```bash
python examples/multi_agent_collaboration.py
```

The example demonstrates:
- Two intents sharing the same trace ID
- A2A binding for agent-to-agent delegation
- Deterministic multi-step orchestration
- Audit log capturing both steps

## Example 6: HTTP Broker Demo

Submits an intent via the SIP broker HTTP API using FastAPI's TestClient (no server required).

```bash
python examples/http_broker_demo.py
```

The example demonstrates:
- Building an `IntentEnvelope` and submitting it to `POST /sip/intents`
- The structured broker response including `audit_record`, `policy_notes`, and `plan_id`
- The `GET /healthz` endpoint response
- Equivalent `curl` commands for use against a live broker server

To start the broker as a standalone HTTP server:

```bash
uvicorn sip.broker.service:app --host 0.0.0.0 --port 8000
```

Then submit an intent with curl:

```bash
curl -s http://localhost:8000/healthz | python -m json.tool
```

## Example 7: Persistent Registry Demo

Saves and reloads capabilities from disk using `JsonFileCapabilityStore`.

```bash
python examples/persistent_registry_demo.py
```

The example demonstrates:
- Creating a `JsonFileCapabilityStore` backed by a JSON file
- Seeding it with the standard SIP capabilities and verifying the file is written
- Reloading capabilities in a fresh store instance
- Adding a custom capability and verifying it persists across restarts

The default capability file path is `data/capabilities.json` (configurable via `SIP_CAPABILITIES_FILE`).

## Example 8: External Identity Demo

Maps trusted HTTP headers into SIP actor context.

```bash
python examples/external_identity_demo.py
```

The example demonstrates:
- Using `map_identity_headers()` from `sip.broker.identity` directly
- The precedence rule: trusted headers override body-provided actor fields
- Enabling trusted header mapping via `SIP_TRUSTED_IDENTITY_HEADERS=true`
- End-to-end: submitting an intent with `X-Actor-Id`, `X-Actor-Name`, `X-Trust-Level`, and `X-Scopes` headers

**Security note:** Trusted identity header mapping is for use behind a trusted gateway or service mesh only. See [security-model.md](security-model.md) for requirements.

## Running All Examples

```bash
make run-examples
```

## Understanding the Output

Each example prints:
- The intent details submitted to the SIP control plane
- The negotiation result (selected capability, binding, rationale)
- The policy decision from the control plane (scopes, risk, approval)
- The execution plan (parameters, steps) — ready to hand to an external execution system
- The translated payload (deterministic specification for the executor)
- The audit record

None of the examples make real network calls. The execution payloads are
deterministic specifications ready to hand to actual execution systems outside SIP.


## Protocol Vectors

The [`protocol-vectors/`](../protocol-vectors/) directory contains canonical JSON examples for all core SIP protocol objects:

```bash
# Inspect a protocol vector
cat protocol-vectors/intent-envelope-basic.json

# Run the Python vector tests
pytest tests/protocol_vectors/ -v
```

These vectors serve as the ground truth for cross-SDK compatibility. See [`protocol-vectors/README.md`](../protocol-vectors/README.md) for details.

## Cross-Broker Discovery

The [`examples/distributed_brokers_demo.py`](../examples/distributed_brokers_demo.py) demonstrates cross-broker capability discovery using the federation model.

The [`tests/interoperability/`](../tests/interoperability/) directory contains integration tests for multi-broker scenarios including remote discovery, peer unavailability handling, provenance preservation, and policy enforcement across brokers:

```bash
pytest tests/interoperability/ -v
```

## Go SDK

The [`sdk/go/`](../sdk/go/) directory provides a Go implementation of SIP protocol types and an HTTP client for the broker API.

Run Go SDK tests:

```bash
cd sdk/go && go test ./tests/... -v
```

Run the basic usage example (dry-run, no broker required):

```bash
cd sdk/go && go run examples/basic_usage.go -dry-run
```
