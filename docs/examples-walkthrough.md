# SIP Examples Walkthrough

This document walks through every runnable example in the `examples/` directory and the end-to-end
demo in `examples/end_to_end_demo/`.  For each example you will find:

- **Purpose** — what the example demonstrates
- **File** — path to the script
- **How to run** — command to execute
- **Expected output** — what you should see

---

## Prerequisites

```bash
# Install the package in development mode
pip install -e ".[dev]"
```

---

## SDK Examples

### Basic Intent Example

**Purpose:** Demonstrates the complete lifecycle of a single `IntentEnvelope` using the Python SDK:
build an actor, build a target, build provenance, assemble an envelope, validate it, serialize to
JSON, and round-trip deserialize.

**File:** `examples/sdk_basic_usage.py`

**How to run:**

```bash
python examples/sdk_basic_usage.py
```

**Expected output:**

```
=== SIP Python SDK – Basic Usage ===

1. Building an actor...
   actor_id:    my-ai-agent
   actor_type:  ai_agent
   trust_level: internal
   scopes:      ['sip:knowledge:read', 'sip:data:write']

2. Building a target...
...
6. Validating the envelope...
   valid:  True
   No validation errors.
...
=== Example complete. ===
```

---

### SDK Provenance Example

**Purpose:** Shows how to build and attach a `ProvenanceBlock` that records the originator,
submitted-by actor, delegation chain, and authority scope.  Demonstrates that provenance
is preserved through serialization and deserialization.

**File:** `examples/sdk_provenance_demo.py`

**How to run:**

```bash
python examples/sdk_provenance_demo.py
```

---

## Broker API Example

**Purpose:** Demonstrates submitting an `IntentEnvelope` to the SIP broker over HTTP.  The example
runs an in-process FastAPI TestClient so no running server is required.

**File:** `examples/http_broker_demo.py`

**How to run:**

```bash
python examples/http_broker_demo.py
```

**Expected output:**

```
=== GET /healthz ===
{
  "status": "ok",
  "version": "0.1",
  "capabilities": 8
}

=== Submitting intent to POST /sip/intents ===
Envelope intent_id: <uuid>

HTTP status: 200

=== Response body ===
{
  "intent_id": "...",
  "outcome": "success",
  "action_taken": "plan_created",
  "plan_id": "...",
  "policy_allowed": true,
  "audit_record": { ... }
}
```

---

### SDK Broker Client Demo

**Purpose:** Demonstrates using `BrokerClient` and `CapabilityDiscoveryClient` from `sip.sdk`.
Shows health check, intent submission, and capability listing.

**File:** `examples/sdk_broker_client_demo.py`

**How to run:**

```bash
python examples/sdk_broker_client_demo.py
```

---

## Capability Discovery Example

**Purpose:** Shows how to query the capability registry using the discovery API.
Demonstrates listing all capabilities, fetching a single capability by ID, and
issuing a semantic discovery request.

**File:** `examples/sdk_capability_discovery_demo.py`

**How to run:**

```bash
python examples/sdk_capability_discovery_demo.py
```

**Expected output:**

```
=== Capability Discovery Demo ===
Listed 8 capabilities
  sip.knowledge.retrieve  score=None
  sip.booking.restaurant  score=None
  ...

Discovery query: retrieve_document / knowledge_management
  Found 1 candidates
  sip.knowledge.retrieve  score=10.00
```

**File:** `examples/capability_discovery_api_demo.py`

Run against the live broker HTTP API for the REST endpoint version.

---

## Federation Example

**Purpose:** Demonstrates the SIP federation model.  Shows how broker trust levels
(`DISCOVERY`, `ROUTING`, `FULL`) control which remote capabilities appear in discovery results
and whether they are eligible for execution plan routing.

**File:** `examples/federation_demo.py`

**How to run:**

```bash
python examples/federation_demo.py
```

**Expected output:**

```
============================================================
  Scenario 1: Trusted ROUTING peer – capability accepted for routing
============================================================
Remote candidates: 1
  capability_id: trusted_cap
  routing_allowed: True  ← ✓ routing permitted
✓ ROUTING peer capability accepted for routing

============================================================
  Scenario 2: DISCOVERY-only peer – not allowed for routing
============================================================
Remote candidates: 1
  routing_allowed: False  ← ✗ routing NOT permitted
✓ DISCOVERY-only peer capability present but routing_allowed=False
...
```

---

## Domain Scenario Examples

These examples demonstrate complete intent flows for real-world scenarios.

### Knowledge Retrieval

**File:** `examples/knowledge_retrieval.py`  
**Intent:** `retrieve_document` / `knowledge_management`  
**Binding:** RAG  
**How to run:** `python examples/knowledge_retrieval.py`

Shows a read intent flowing through the broker: matching, policy approval, plan creation, and audit.

### Restaurant Booking

**File:** `examples/restaurant_booking.py`  
**Intent:** `book_table` / `restaurant_booking`  
**Binding:** REST  
**How to run:** `python examples/restaurant_booking.py`

Shows a write intent.  Demonstrates that high-risk write operations may require explicit approval
before the execution plan proceeds.

### Network Troubleshooting

**File:** `examples/network_troubleshooting.py`  
**Intent:** `diagnose_network_issue` / `network_operations`  
**Binding:** REST  
**How to run:** `python examples/network_troubleshooting.py`

Shows a diagnostic intent with elevated trust requirements.

### Multi-Agent Collaboration

**File:** `examples/multi_agent_collaboration.py`  
**Intent:** `collaborate_on_task` / `agent_collaboration`  
**Binding:** A2A  
**How to run:** `python examples/multi_agent_collaboration.py`

Shows an agent-to-agent delegation with a full provenance chain.

---

## Persistent Registry Demo

**Purpose:** Shows how capabilities can be saved to a JSON file and reloaded on broker restart.

**File:** `examples/persistent_registry_demo.py`  
**How to run:** `python examples/persistent_registry_demo.py`

---

## Protocol Extensions Demo

**Purpose:** Demonstrates the `extensions` field for attaching vendor-specific or application-specific
metadata to an `IntentEnvelope` or `CapabilityDescriptor`.

**File:** `examples/protocol_extensions_demo.py`  
**How to run:** `python examples/protocol_extensions_demo.py`

---

## External Identity Demo

**Purpose:** Shows how to map external authentication headers (e.g., from an API gateway) onto the
actor identity in an `IntentEnvelope` using `X-Actor-Id`, `X-Trust-Level`, and `X-Scopes` headers.

**File:** `examples/external_identity_demo.py`  
**How to run:** `python examples/external_identity_demo.py`

---

## End-to-End Demo

The `examples/end_to_end_demo/` directory contains a multi-component demo showing the full SIP
stack: Python SDK, Go SDK, broker HTTP API, and broker federation working together.

| Component | File |
|-----------|------|
| Demo overview and architecture | `examples/end_to_end_demo/demo_overview.md` |
| Python client demo | `examples/end_to_end_demo/python_client_demo.py` |
| Broker federation demo | `examples/end_to_end_demo/broker_federation_demo.py` |
| Go federation demo | `sdk/go/examples/federation_demo.go` |

**How to run the full demo:**

```bash
# Python in-process demo (no server required)
python examples/end_to_end_demo/python_client_demo.py

# Broker federation demo (two in-process brokers)
python examples/end_to_end_demo/broker_federation_demo.py

# Go dry-run demo (no server required)
cd sdk/go/examples
go run federation_demo.go -dry-run
```

See [examples/end_to_end_demo/demo_overview.md](../examples/end_to_end_demo/demo_overview.md) for
the full architecture diagram and step-by-step instructions.
