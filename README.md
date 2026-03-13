# Semantic Intent Protocol (SIP)

**Semantic Intent Protocol (SIP) is a deterministic control plane protocol for AI agents and software systems.**

SIP converts semantic intent into validated, authorized execution plans before actions are executed in external systems. It sits between AI agents or software systems and the execution systems they interact with, providing a structured negotiation, authorization, and planning layer.

SIP complements AI frameworks, APIs, and execution runtimes by providing a security-aware negotiation and planning layer between them.

> **Status**: Private development, v0.1 working draft.
> Future public open source release planned.

---

## What SIP Is

SIP is a **deterministic control plane protocol** that:

- Sits between AI agents / software systems and execution systems
- Validates and type-checks semantic intent before any action occurs
- Negotiates which registered capability should satisfy the intent
- Enforces scope, trust, risk, and delegation policy deterministically
- Produces a fully specified `ExecutionPlan` — external systems carry out the plan

```
Agents / Systems
      ↓
IntentEnvelope
      ↓
SIP Control Plane
  - validation
  - negotiation
  - authorization
  - planning
      ↓
Execution Systems
  REST | gRPC | MCP | A2A | RAG
```

**Natural language is never executed directly.** It may appear as an audit annotation, but it has no operational effect.

---

## What SIP Is Not

- **Not an LLM or AI model** — SIP contains no inference engine; all logic is rule-based and deterministic.
- **Not an agent framework** — Agent frameworks may propose intents; SIP validates and authorizes them.
- **Not a workflow engine** — SIP does not schedule, sequence, or orchestrate tasks over time.
- **Not a transport replacement** — REST, gRPC, MCP, A2A, and RAG remain the execution transports. SIP sits above them.
- **Not a direct execution engine** — SIP produces plans; external systems execute them.

---

## Where SIP Fits

SIP complements rather than replaces existing categories:

| Category | Relationship to SIP |
|---|---|
| AI agent frameworks | May create or propose `IntentEnvelope` objects submitted to SIP |
| Workflow engines | May receive `ExecutionPlan` results from SIP to trigger downstream steps |
| Tool invocation protocols (MCP, A2A) | Serve as execution bindings that SIP delegates to |
| REST / gRPC APIs | Execution targets that SIP produces plans for |
| Retrieval systems (RAG) | Execution binding for knowledge retrieval intents |

SIP does not compete with these systems — it provides the deterministic control plane layer that sits between intent-producing systems and execution systems.

---

## Why SIP Exists

Modern software systems face three compounding integration problems:

1. **API explosion** — Every system has its own API, schema, and auth model. N systems = N integrations.
2. **Schema coupling** — Systems are tightly coupled to the schemas of APIs they call. Schema changes break consumers.
3. **LLM ambiguity** — Natural language is expressive but too ambiguous and unpredictable for safe direct execution.

SIP's answer is a **deterministic control plane** that sits above existing execution protocols, converting semantic intent into validated, authorized execution plans before any external system is touched.

---

## Architectural Principles

1. **Intent ≠ Execution** — The intent layer is always separate from the execution layer.
2. **Determinism is non-negotiable** — Every execution plan is fully specified and reproducible.
3. **Trust is explicit** — Every intent carries trust level, scopes, and delegation chain.
4. **Policy is always evaluated** — No execution proceeds without a policy decision.
5. **Auditability is built in** — Every processed intent produces an immutable audit record.
6. **No LLM calls in the protocol** — All matching, negotiation, and policy is deterministic and rule-based.

---

## Repository Structure

```
semantic-intent-protocol/
├── sip/                        # Python package
│   ├── envelope/               # IntentEnvelope models and validation
│   ├── registry/               # CapabilityDescriptor, service, storage, bootstrap
│   ├── negotiation/            # Matcher, planner, result models
│   ├── translator/             # REST, gRPC, MCP, A2A, RAG adapters
│   ├── policy/                 # Policy engine, scopes, approvals, risk
│   ├── observability/          # Tracing, audit, logging
│   └── broker/                 # BrokerService, pipeline handlers, FastAPI API
├── tests/
│   ├── unit/                   # Unit tests for each module
│   └── functional/             # End-to-end flow tests
├── examples/                   # Runnable example scripts
├── docs/                       # Protocol documentation
├── pyproject.toml
├── requirements.txt
└── Makefile
```

---

## Quick Start

> **New to SIP?** Start with the [docs/quickstart.md](docs/quickstart.md) guide for a step-by-step walkthrough.

### 1. Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
```

### 2. Install dependencies

```bash
pip install -e ".[dev]"
# or
make install
```

### 3. Run the tests

```bash
pytest tests/ -v
# or
make test
```

### 4. Run the examples

```bash
python examples/knowledge_retrieval.py
python examples/restaurant_booking.py
python examples/network_troubleshooting.py
python examples/multi_agent_collaboration.py
# or
make run-examples
```

### 5. Run the end-to-end demo

```bash
# Python in-process demo (no server required)
python examples/end_to_end_demo/python_client_demo.py

# Broker federation demo (two in-process brokers)
python examples/end_to_end_demo/broker_federation_demo.py

# Go SDK dry-run demo
cd sdk/go/examples && go run federation_demo.go -dry-run
```

See [examples/end_to_end_demo/demo_overview.md](examples/end_to_end_demo/demo_overview.md) for the full demo architecture.

### 6. Start the broker API (optional)

```bash
make broker
# → http://127.0.0.1:8000/docs
```

---

## Python SDK Quick Start

The `sip.sdk` module provides a clean public API for building Python
applications on top of the SIP control plane.

### Install

```bash
pip install semantic-intent-protocol
```

### Import from `sip.sdk`

```python
from sip.sdk import (
    IntentEnvelope,
    CapabilityDescriptor,
    NegotiationResult,
    ExecutionPlan,
    AuditRecord,
    BrokerClient,
    CapabilityDiscoveryClient,
    validate_envelope,
    build_actor,
    build_intent_envelope,
    build_provenance,
    to_dict,
    to_json,
    parse_intent_envelope,
)
```

### Create an envelope

```python
from sip.sdk import build_actor, build_intent_envelope

actor = build_actor(
    actor_id="my-service",
    name="My Service",
    scopes=["sip:knowledge:read"],
)
envelope = build_intent_envelope(
    actor=actor,
    intent_name="retrieve_document",
    intent_domain="knowledge_management",
    operation_class="retrieve",
    outcome_summary="Get the architecture document.",
)
```

### Validate and serialize

```python
from sip.sdk import validate_envelope, to_json, parse_intent_envelope

result = validate_envelope(envelope)
print(result.valid)           # True

json_str = to_json(envelope)
restored = parse_intent_envelope(json_str)
assert restored.intent_id == envelope.intent_id
```

### Submit to a broker

```python
from sip.sdk import BrokerClient
from sip.sdk.errors import SIPHTTPError

client = BrokerClient("http://localhost:8000")
health = client.health()         # {"status": "ok", "capabilities": N}

try:
    result = client.submit_intent(envelope)
    print(result["action_taken"])   # e.g. "plan_created"
except SIPHTTPError as exc:
    print(f"HTTP {exc.status_code}: {exc.response_body}")
```

### Discover capabilities

```python
from sip.sdk import CapabilityDiscoveryClient

discovery = CapabilityDiscoveryClient("http://localhost:8000")
caps = discovery.list_capabilities()
for cap in caps:
    print(f"{cap.capability_id}: {cap.name}")
```

See [docs/python-sdk.md](docs/python-sdk.md) for the full SDK reference.

---

## Example Usage

```python
from sip.broker.service import BrokerService
from sip.envelope.models import (
    ActorDescriptor, ActorType, BindingType, DesiredOutcome,
    IntentEnvelope, IntentPayload, OperationClass,
    ProtocolBinding, TargetDescriptor, TargetType, TrustLevel,
)
from sip.registry.bootstrap import build_seeded_registry

# Build a broker with seeded capabilities
broker = BrokerService(registry=build_seeded_registry())

# Express an intent
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
        parameters={"query": "latest architecture document"},
    ),
    desired_outcome=DesiredOutcome(summary="Retrieve the architecture document"),
    protocol_bindings=[ProtocolBinding(binding_type=BindingType.RAG)],
)

# Process through the broker
result, translation = broker.translate(envelope)

print(result.audit_record.outcome_summary)
print(result.execution_plan.selected_capability.capability_id)
print(translation.payload["retrieval_query"])
```

---

## Core Protocol Objects

| Object | Description |
|---|---|
| `IntentEnvelope` | Root protocol object — carries a semantic intent from actor to target |
| `CapabilityDescriptor` | Describes a registered capability with schema, trust, and binding info |
| `NegotiationResult` | Ranked candidates, selected capability, policy decision |
| `ExecutionPlan` | Deterministic plan ready for adapter translation |
| `AuditRecord` | Immutable audit log entry for every processed intent |

---

## Testing

```bash
# All tests
pytest tests/ -v

# Unit tests only
pytest tests/unit/ -v

# Functional tests only
pytest tests/functional/ -v
```

151 tests, 0 failures in the v0.1 reference implementation.

---

## Documentation

| Document | Description |
|---|---|
| [docs/quickstart.md](docs/quickstart.md) | **Getting started guide** — start here |
| [docs/overview.md](docs/overview.md) | What SIP is and why it exists |
| [docs/architecture.md](docs/architecture.md) | Components, data flow, package structure |
| [docs/sip-wire-spec-v0.1.md](docs/sip-wire-spec-v0.1.md) | Full protocol specification |
| [docs/capability-model.md](docs/capability-model.md) | Capability descriptors and registry |
| [docs/security-model.md](docs/security-model.md) | Trust, scopes, risk, policy, audit |
| [docs/examples-walkthrough.md](docs/examples-walkthrough.md) | Guided walkthrough of all examples |
| [docs/examples.md](docs/examples.md) | Example scenario index |
| [docs/python-sdk.md](docs/python-sdk.md) | Python SDK reference guide |
| [docs/governance.md](docs/governance.md) | Protocol governance, versioning, and compatibility |
| [docs/releases/v0.1.1.md](docs/releases/v0.1.1.md) | v0.1.1 release notes |

## Ecosystem

| Resource | Description |
|---|---|
| [protocol-vectors/](protocol-vectors/) | Canonical JSON fixtures for SIP v0.1 protocol objects |
| [tests/protocol_vectors/](tests/protocol_vectors/) | Python tests validating all protocol vectors |
| [tests/interoperability/](tests/interoperability/) | Multi-broker interoperability tests |
| [sdk/go/](sdk/go/) | Go SDK — types, constructors, and HTTP client |
| [sdk/go/examples/](sdk/go/examples/) | Go SDK usage examples (basic + federation) |
| [examples/end_to_end_demo/](examples/end_to_end_demo/) | End-to-end multi-SDK demo (Python + Go + federation) |

---

## Roadmap

### v0.1 (current)
- IntentEnvelope with full nested model
- CapabilityDescriptor with rich metadata
- In-memory capability registry
- Deterministic capability matching and ranking
- Policy engine (scopes, risk, delegation, sensitivity)
- Execution planner
- REST, gRPC, MCP, A2A, RAG adapters
- BrokerService with full pipeline
- Audit records and structured logging
- 151+ unit and functional tests
- Protocol vectors for cross-SDK compatibility testing
- Broker interoperability tests
- Go SDK with JSON serialization and HTTP client
- 4 runnable example workflows
- Optional FastAPI broker API
- Protocol governance documentation

### v0.2 (planned)
- Envelope signing and verification (integrity block)
- Persistent registry backends (SQLite, Redis)
- Multi-step execution plans (A2A chaining)
- Streaming execution results
- Enhanced scope taxonomy

### v0.3 (planned)
- Public protocol specification release
- Cross-language SDK scaffolding
- Registry federation
- Token validation middleware

---

## License

MIT License. See [LICENSE](LICENSE).

---

## Contributing

This repository is in private development. Contributions are welcome from
authorized collaborators. See the docs for architecture and coding conventions.
