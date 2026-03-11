# SIP Examples

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
- The intent details
- The negotiation result (selected capability, binding, rationale)
- The policy decision (scopes, risk, approval)
- The execution plan (parameters, steps)
- The translated payload (ready for the executor)
- The audit record

None of the examples make real network calls. The execution payloads are
deterministic specifications ready to hand to actual executors.
