# SIP Architecture

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        SIP Layer                             │
│                                                              │
│  IntentEnvelope  →  Broker  →  NegotiationResult            │
│                         │                                    │
│                     Registry                                 │
│                     PolicyEngine                             │
│                     ExecutionPlanner                         │
│                         │                                    │
│                     ExecutionPlan                            │
│                         │                                    │
│                     Translator Adapters                      │
│                         │                                    │
└─────────────────────────┼───────────────────────────────────┘
                          │
        ┌─────────────────┼──────────────────────┐
        ↓                 ↓                        ↓
    REST API          gRPC Service           MCP Tool
    (HTTP)            (Protocol Buffers)     (Model Context)
                          ↓
                    A2A Agent Task
                    RAG Retrieval
```

## Components

### IntentEnvelope

The root protocol object. Carries all information needed to process an intent:
- Actor identity and trust level
- Semantic intent payload (name, domain, operation class, parameters)
- Desired outcome
- Constraints (time budget, cost budget, determinism level)
- Trust block (scopes, delegation chain)
- Protocol binding preferences
- Negotiation hints

### Capability Registry

An in-memory store (replaceable with a persistent backend) that holds
`CapabilityDescriptor` objects. The registry supports:
- Registration and retrieval by ID
- Deterministic matching by intent name, domain, operation class, binding, trust

### Negotiation Engine

The `CapabilityMatcher` queries the registry and produces a `NegotiationResult`
with ranked candidates. Scoring is deterministic and additive:
- Exact intent name match: +3.0
- Partial name match: +2.0
- Exact domain match: +2.0
- Partial domain match: +1.0
- Operation class match: +2.0
- Preferred binding match: +1.5
- Candidate hint: +0.5

At least one name or domain signal is required for a capability to be considered.

### Policy Engine

The `PolicyEngine` evaluates four rules:
1. **Scope check** – Actor must hold all required scopes.
2. **Risk + operation** – High-risk write/execute may require human approval.
3. **Risk + sensitivity** – Critical risk + restricted data is denied.
4. **Delegation depth** – Prevents unbounded delegation chains (max 5).

Policy decisions are always deterministic and rule-based. No ML involved.

### Execution Planner

The `ExecutionPlanner` takes a `NegotiationResult` and produces an `ExecutionPlan`:
- Grounds parameters from the envelope against the capability's input schema
- Builds a deterministic target (endpoint, provider, binding)
- Creates execution steps
- Records policy checks passed
- Sets `approval_required` flag

### Translator Adapters

Each adapter translates an `ExecutionPlan` into a binding-specific payload:

| Adapter | Output |
|---------|--------|
| `RestAdapter` | HTTP method, path, headers, body, query params |
| `GrpcAdapter` | Service name, method name, request message, metadata |
| `McpAdapter` | Tool name, tool arguments, execution contract |
| `A2aAdapter` | Agent task type, target agent, task payload, delegation context |
| `RagAdapter` | Collection, retrieval query, filters, result contract |

Adapters **do not** execute — they produce deterministic payloads for executors.

### Broker Service

The `BrokerService` orchestrates the full pipeline:
1. Validate the envelope
2. Match capabilities (negotiation)
3. Evaluate policy
4. Create execution plan
5. Generate audit record

The broker also exposes an optional FastAPI HTTP interface.

### Observability

Every processed intent produces an `AuditRecord` containing:
- Actor, intent, capability, binding, policy result, approval state, outcome

Structured logging helpers use the standard library `logging` module.
Trace and span IDs flow through the entire pipeline.

## Data Flow

```
1. Actor creates IntentEnvelope
2. Broker validates envelope (sip.envelope.validator)
3. Broker calls matcher.match(envelope) → NegotiationResult
4. Broker calls policy_engine.evaluate(envelope, negotiation) → enriched NegotiationResult
5. If allowed: broker calls planner.plan(envelope, negotiation) → ExecutionPlan
6. Broker creates AuditRecord
7. Optional: adapter.translate(plan) → binding-specific payload
8. Payload handed to executor (outside SIP scope in v0.1)
```

## Package Structure

```
sip/
  __init__.py
  envelope/         # IntentEnvelope models and validation
  registry/         # CapabilityDescriptor, registry service, storage, bootstrap
  negotiation/      # Matcher, planner, result models
  translator/       # Base adapter + REST, gRPC, MCP, A2A, RAG adapters
  policy/           # Engine, scopes, approvals, risk
  observability/    # Tracing, audit, logging
  broker/           # BrokerService, pipeline handlers, FastAPI app
```
