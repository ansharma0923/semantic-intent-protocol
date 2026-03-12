# SIP End-to-End Demo

This demo shows the full SIP stack working together across Python SDK, Go SDK, broker HTTP API,
and broker federation.

---

## Architecture

```
User / AI Agent
      ↓
Python SDK (build_intent_envelope)
      ↓
Broker A  (BrokerService in-process or HTTP)
  ├── CapabilityMatcher
  ├── PolicyEngine
  ├── ExecutionPlanner
  └── DiscoveryService ──→ Broker B (federated peer)
                               └── Remote Capabilities
      ↓
NegotiationResult + ExecutionPlan + AuditRecord
```

---

## Components

| Component | File | Description |
|-----------|------|-------------|
| Python client demo | `python_client_demo.py` | Build → submit → print results |
| Broker federation demo | `broker_federation_demo.py` | Broker A discovers caps from Broker B |
| Go federation demo | `sdk/go/examples/federation_demo.go` | Go SDK + broker HTTP API |

---

## How to Run

### Step 1 — Install dependencies

```bash
pip install -e ".[dev]"
```

### Step 2 — Python in-process demo (no server required)

```bash
python examples/end_to_end_demo/python_client_demo.py
```

Expected output includes:
- `NegotiationResult` with selected capability and ranked candidates
- `ExecutionPlan` with binding type and grounded parameters
- `AuditRecord` with outcome, actor ID, and trace ID
- Provenance details (originator, delegation chain)

### Step 3 — Broker federation demo

```bash
python examples/end_to_end_demo/broker_federation_demo.py
```

This script starts two in-process broker instances (Broker A and Broker B), registers
distinct capabilities in each, and has Broker A discover capabilities from Broker B
via the federation model.

Expected output includes:
- Local capabilities from Broker A
- Remote capabilities from Broker B
- Aggregated discovery result with `source_broker_id` metadata

### Step 4 — Start Broker A (live HTTP, optional)

```bash
uvicorn sip.broker.service:app --host 127.0.0.1 --port 8000 --reload
```

### Step 5 — Start Broker B (live HTTP, optional)

```bash
SIP_BROKER_PORT=8001 uvicorn sip.broker.service:app --host 127.0.0.1 --port 8001 --reload
```

### Step 6 — Go client demo (dry-run, no server required)

```bash
cd sdk/go/examples
go run federation_demo.go -dry-run
```

To submit to a running broker:

```bash
cd sdk/go/examples
go run federation_demo.go -broker http://localhost:8000
```

### Step 7 — Observe federation discovery

When both brokers are running, Broker A will automatically query Broker B during
capability discovery if they are configured as federation peers.

---

## Protocol Flow (Python client demo)

```
1. build_actor()             →  ActorDescriptor
2. build_provenance()        →  ProvenanceBlock
3. build_intent_envelope()   →  IntentEnvelope (validated)
4. broker.handle(envelope)   →  BrokerResult
   a. validate_envelope      →  ValidationResult
   b. discover capabilities  →  DiscoveryResponse
   c. rank candidates        →  NegotiationResult
   d. evaluate policy        →  PolicyDecision
   e. create plan            →  ExecutionPlan
   f. record audit           →  AuditRecord
5. Print all results
```

---

## Protocol Flow (Federation demo)

```
Broker A                       Broker B
   |                               |
   |── DiscoveryRequest ──────────→|
   |                               | (query local registry)
   |←── DiscoveryResponse ─────────|
   |                               |
   | aggregate + tag with          |
   | source_broker_id              |
   |                               |
   | return merged results         |
   |  (local + remote candidates)  |
```

---

## Key Protocol Objects

| Object | What it shows |
|--------|---------------|
| `IntentEnvelope` | Full structured intent from actor |
| `NegotiationResult` | Ranked capability candidates, selected capability |
| `ExecutionPlan` | Deterministic plan with binding, endpoint, parameters |
| `AuditRecord` | Immutable audit log entry (outcome, actor, trace) |
| `DiscoveryResponse` | Aggregated local + federated candidates |

---

## Related Files

- `examples/federation_demo.py` — standalone federation model scenarios
- `examples/sdk_basic_usage.py` — core Python SDK walkthrough
- `examples/http_broker_demo.py` — broker HTTP API demo
- `sdk/go/examples/basic_usage.go` — Go SDK basic usage
- `docs/quickstart.md` — getting started guide
- `docs/examples-walkthrough.md` — guided examples index
