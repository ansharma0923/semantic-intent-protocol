# SIP Architecture

## 1. Overview

**Semantic Intent Protocol (SIP) is an open, deterministic control-plane protocol for AI agents, services, and infrastructure systems.**

Rather than coupling actors directly to specific APIs or transport protocols, SIP provides a structured control plane that sits above execution systems and below AI agent reasoning layers.

Actors express *what* they want to achieve through an `IntentEnvelope`. The SIP control plane is responsible for discovering the right capability, evaluating policy, and producing a deterministic execution plan. Actual execution is delegated to an external system via a binding adapter — execution systems remain outside the SIP control plane.

AI agents or LLMs may generate or propose `IntentEnvelope` objects, but this happens **outside** the SIP protocol layer. SIP itself does not perform LLM inference. SIP acts as the **deterministic control plane** — the security boundary between AI-generated intent and execution systems — responsible for validation, capability negotiation, authorization, and execution planning.

### Control-Plane Flow

```
AI Agent / Application
        ↓
   IntentEnvelope (SIP)
        ↓
     SIP Broker
  - validation
  - capability negotiation
  - policy / authorization
  - execution planning
        ↓
Execution Systems
REST | gRPC | MCP | A2A | RAG
```

### Ecosystem Positioning

```
LLM / Agent Framework
        ↓
   SIP Intent Layer
        ↓
 Execution Systems / Infrastructure
```

This document describes the conceptual architecture of SIP — the design goals,
system roles, processing pipeline, and component model.

---

## 2. Design Goals

SIP is built around the following core design principles:

- **Semantic interoperability** — Intents are expressed in domain-neutral
  semantic terms rather than API-specific calls, allowing the same intent to be
  routed to different underlying systems.

- **Deterministic execution** — Capability matching, policy evaluation, and
  execution planning are rule-based and produce the same output for the same
  input. There is no probabilistic or ML-based decision making in the control
  path.

- **Separation of intent and execution** — The SIP layer deals exclusively with
  intent resolution and planning. It does not execute requests itself. This
  clean separation makes the protocol composable and testable.

- **Auditability and traceability** — Every intent processed by SIP produces a
  structured audit record. Trace and span IDs flow through the full pipeline,
  enabling end-to-end observability.

- **Safety and policy enforcement** — Policy is evaluated before execution.
  Scope checks, risk classification, data sensitivity rules, and delegation
  depth limits are enforced centrally by the Policy Engine.

---

## 3. System Roles

The SIP ecosystem defines the following roles:

| Role | Description |
|------|-------------|
| **Actor** | The originator of an intent. May be a human user, an AI agent, or an automated service. Actors carry an identity, a trust level, and a set of granted scopes. |
| **SIP Broker** | The central coordinator. Receives `IntentEnvelope` objects, orchestrates the processing pipeline, and returns an `ExecutionPlan` or a denial. Also exposes an HTTP API as one transport surface. |
| **Capability Provider** | A system that can fulfill an intent. Providers register capabilities with the registry and are targeted by execution plans. |
| **Capability Registry** | The authoritative store of available capabilities and their descriptors. Used during negotiation to discover and rank candidates. Supports both in-memory and file-backed JSON persistence. |
| **Execution System** | The external runtime that carries out the execution plan. May be a REST API, a gRPC service, an MCP tool host, an A2A agent, or a RAG pipeline. |
| **Identity Gateway** | An optional external API gateway, reverse proxy, or service mesh that authenticates callers and injects trusted identity headers before requests reach the SIP broker. Authentication always occurs outside SIP. |

---

## 4. Architectural Layers

SIP operates as a protocol layer that sits above concrete execution systems.
The SIP intent layer is responsible for semantic resolution, policy, and
planning. The execution layer is responsible for carrying out operations.

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

The SIP layer has no direct dependency on any particular transport protocol.
New execution systems can be integrated by adding a binding adapter without
modifying the core protocol.

---

## 5. SIP Processing Pipeline

The following describes the lifecycle of an intent as it passes through the
SIP Broker:

```
IntentEnvelope
→ envelope validation
→ capability discovery
→ negotiation
→ policy evaluation
→ execution planning
→ binding translation
→ execution by external system
→ audit logging
```

1. **Envelope validation** — The incoming `IntentEnvelope` is checked for
   structural completeness and required fields.
2. **Capability discovery** — The registry is queried for candidates that match
   the intent's name, domain, operation class, and binding preferences.
3. **Negotiation** — Candidates are ranked by a deterministic scoring model and
   a `NegotiationResult` is produced.
4. **Policy evaluation** — The Policy Engine checks scopes, risk level, data
   sensitivity, and delegation depth against the negotiation result.
5. **Execution planning** — If policy allows, an `ExecutionPlan` is produced
   that grounds the intent's parameters against the selected capability's input
   schema.
6. **Binding translation** — An adapter translates the `ExecutionPlan` into a
   protocol-specific payload (HTTP request, gRPC message, etc.).
7. **Execution by external system** — The payload is handed off to the
   execution system. This step is outside the SIP control plane.
8. **Audit logging** — An `AuditRecord` capturing the full decision trail is
   persisted.

---

## 5a. Intent Provenance

When AI agents mediate user requests — translating natural language into structured `IntentEnvelope` objects — the broker cannot assume that the submitting actor and the original requester are the same entity. SIP defines an optional `provenance` block in the `IntentEnvelope` that records the full chain of intent mediation, enabling the policy engine to consider the originator's authority alongside the submitting actor's authority.

### Separation of Concerns

- **Authentication** occurs outside SIP at the transport or gateway layer. The SIP broker treats the identity presented in the `IntentEnvelope` as pre-verified.
- **Authorization** occurs inside the SIP Policy Engine, which evaluates scopes, trust levels, risk rules, and delegation chain constraints.
- **Intent provenance** ensures that delegated requests cannot silently escalate privileges. When an AI agent submits an intent on behalf of a user, the originator's constrained authority is preserved in the provenance block, and the policy engine enforces that the final action is authorized for both the submitting actor and the originator.

> **Provenance trust:** The broker accepts provenance claims at the same trust level as the submitting actor's authenticated identity. Verifying that `provenance.originator` accurately represents the actual originating entity is a deployment concern: systems should ensure that only trusted, authenticated agents are permitted to populate the provenance block, and that the `authority_scope` they declare does not exceed the scopes they were themselves granted on behalf of the originator. Cryptographic attestation of provenance claims is outside the scope of SIP v0.1.

### Intent Mediation Flow

```
Originator
    │  (user or originating system generates the request)
    ↓
Agent Mediation
    │  (AI agent translates NL to structured IntentEnvelope;
    │   populates provenance.originator and authority_scope)
    ↓
Submitting Actor
    │  (agent submits IntentEnvelope to SIP broker)
    ↓
SIP Broker
    │  (envelope validation, capability discovery, negotiation)
    ↓
Policy Evaluation
    │  (checks: submitting actor scopes + trust level,
    │            originator scopes + trust level,
    │            authority_scope bounds,
    │            delegation chain depth and expiry)
    ↓
ExecutionPlan
    │  (produced only if both principals are authorized)
    ↓
Execution System
    (REST | gRPC | MCP | A2A | RAG)
```

This model prevents intent laundering, where a low-privilege originator causes a more trusted agent to submit an intent that the originator was not permitted to perform directly. See [security-model.md](security-model.md) for the full threat model and mitigation details.

---

## 6. Core Components

### IntentEnvelope

The root protocol object. Carries all information needed to resolve and plan
an intent: actor identity and trust level, semantic intent payload (name,
domain, operation class, parameters), desired outcome, constraints (time
budget, cost budget, determinism level), trust block (scopes, delegation
chain), optional provenance block (originator, delegation chain, authority
scope), protocol binding preferences, and negotiation hints.

### Capability Registry

An authoritative store of `CapabilityDescriptor` objects. Supports
registration, retrieval by ID, and deterministic matching by intent name,
domain, operation class, binding type, and trust level. The storage backend
is replaceable.

Two storage backends are provided out of the box:

- **`InMemoryCapabilityStore`** – fast, ephemeral; suitable for development and testing.
- **`JsonFileCapabilityStore`** – file-backed JSON persistence; capabilities are saved to disk and reloaded on startup.  The default file path is `data/capabilities.json`, configurable via the `SIP_CAPABILITIES_FILE` environment variable.  Bootstrap capabilities from seed data if no file exists yet.

### Negotiation Engine

Queries the registry and ranks matching capabilities by a deterministic,
additive scoring model. Produces a `NegotiationResult` with ordered
candidates. At least one semantic signal (name or domain) must match for a
capability to be considered.

### Policy Engine

Evaluates a fixed set of rules before execution is permitted:
- **Scope check** — The actor must hold all required scopes.
- **Risk and operation class** — High-risk write or execute operations may
  require explicit human approval.
- **Risk and data sensitivity** — Critical risk combined with restricted data
  is denied.
- **Delegation depth** — Unbounded delegation chains are prevented.
- **Provenance validation** — When a `provenance` block is present, the policy
  engine checks that the submitted intent's scopes do not exceed the
  originator's `authority_scope`, that the effective trust level is the lower of
  the submitting actor's and the originator's, and that any `delegation_expiry`
  has not passed. Delegation must never increase authority.

Policy decisions are always deterministic and rule-based.

### Execution Planner

Consumes a `NegotiationResult` and produces an `ExecutionPlan` that
identifies the target provider, binding, endpoint, and grounded parameter
set. Records which policy checks passed and whether human approval is
required before execution.

### Translator Adapters

Each adapter translates an `ExecutionPlan` into a binding-specific payload:

| Binding | Payload |
|---------|---------|
| REST | HTTP method, path, headers, body, query parameters |
| gRPC | Service name, method name, request message, metadata |
| MCP | Tool name, tool arguments, execution contract |
| A2A | Agent task type, target agent, task payload, delegation context |
| RAG | Collection, retrieval query, filters, result contract |

Adapters produce deterministic payloads. They do not perform execution.

### Broker Service

Orchestrates the full processing pipeline: envelope validation, capability
negotiation, policy evaluation, execution planning, and audit record
generation.

The broker exposes an HTTP interface built with FastAPI:

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/healthz` | Liveness / readiness check. Returns status and capability count. |
| `POST` | `/sip/intents` | Submit an `IntentEnvelope` for processing. Returns a structured broker response. |
| `GET`  | `/capabilities` | List registered capabilities (legacy path). |
| `GET`  | `/sip/capabilities` | List all registered capabilities as full descriptors. |
| `GET`  | `/sip/capabilities/{id}` | Retrieve a capability by its unique ID. |
| `POST` | `/sip/capabilities/discover` | Submit a `DiscoveryRequest` and receive ranked capability candidates. |

**HTTP status codes returned by `POST /sip/intents`:**

| Code | Condition |
|------|-----------|
| `200` | Intent processed; execution plan created. |
| `202` | Intent processed; approval required before execution. |
| `400` | Envelope validation failed. |
| `403` | Policy denied the intent. |
| `422` | Malformed request body; cannot be parsed as an `IntentEnvelope`. |
| `500` | Unexpected internal error. |

**HTTP status codes returned by capability discovery endpoints:**

| Code | Condition |
|------|-----------|
| `200` | Success (discovery may have zero candidates). |
| `400` | Invalid discovery request. |
| `404` | Capability not found (`GET /sip/capabilities/{id}`). |
| `500` | Unexpected internal error. |

The HTTP API is **one transport surface** for the SIP broker — it is not the
protocol definition itself.  All SIP semantics, policy evaluation, provenance
tracking, and audit behaviour are identical regardless of transport.

### Identity Adapter

The `sip.broker.identity` module provides optional external identity
integration for the HTTP API.  When enabled (via `SIP_TRUSTED_IDENTITY_HEADERS=true`),
the adapter reads the following headers and uses them to override the actor
fields from the request body:

| Header | SIP field |
|--------|-----------|
| `X-Actor-Id` | `ActorDescriptor.actor_id` |
| `X-Actor-Type` | `ActorDescriptor.actor_type` |
| `X-Actor-Name` | `ActorDescriptor.name` |
| `X-Trust-Level` | `ActorDescriptor.trust_level` |
| `X-Scopes` | `ActorDescriptor.scopes` (comma-separated) |

**Precedence rule:** trusted external identity headers override conflicting
actor identity fields from the request body.  Overrides are logged at INFO
level.

**Security requirement:** This feature is designed exclusively for deployments
where the broker is behind a trusted gateway, reverse proxy, or service mesh
that strips and re-injects these headers after authenticating the caller.  See
[security-model.md](security-model.md) for security guidance.  Authentication
remains entirely external to SIP.

### Observability

Every processed intent produces a structured `AuditRecord` capturing the
actor, intent, selected capability, binding, policy result, approval state,
and outcome. Trace and span IDs propagate through the entire pipeline to
support distributed tracing and end-to-end auditability.

---

## 7. Control Plane vs Execution Plane

SIP operates exclusively as a **control plane**. It resolves intents,
evaluates policy, and produces execution plans, but it does not carry out
operations itself.

Execution is delegated to an **execution plane** consisting of external
systems targeted by binding adapters.

```
┌──────────────────────────────┐
│     Control Plane (SIP)      │
│                              │
│   IntentEnvelope             │
│   Negotiation                │
│   Policy                     │
│   ExecutionPlan              │
└──────────────┬───────────────┘
               │ binding payload
┌──────────────▼───────────────┐
│      Execution Plane         │
│                              │
│   REST                       │
│   gRPC                       │
│   MCP                        │
│   A2A                        │
│   RAG                        │
└──────────────────────────────┘
```

This separation means that SIP can be adopted incrementally. Existing
services remain unchanged; they are simply registered as capabilities and
targeted by execution plans.

---

## 8. Binding Adapter Model

A binding adapter is a stateless translator that converts an `ExecutionPlan`
into the payload format expected by a specific execution system. Each adapter
is responsible for one binding type (REST, gRPC, MCP, A2A, or RAG).

Adapters read the execution plan's target, binding, and grounded parameters,
and produce a self-contained payload that an executor can submit directly to
the target system without further interpretation.

Adding support for a new execution system requires implementing a new adapter
against the common adapter interface. No changes to the broker, policy engine,
or negotiation engine are required.

---

## 9. Observability Model

SIP provides structured observability at every stage of the processing
pipeline:

- **Trace ID** — A unique identifier assigned to each `IntentEnvelope`
  submission. Propagated through all pipeline stages.
- **Span IDs** — Individual spans are created for negotiation, policy
  evaluation, and execution planning, enabling per-stage latency
  measurement.
- **Structured logging** — Log entries are emitted at each pipeline stage
  with consistent fields (trace ID, actor, intent, capability, binding,
  policy outcome).
- **Audit records** — A durable `AuditRecord` is written after each
  processed intent, capturing the full decision trail for compliance and
  post-hoc analysis.

The observability model is designed to support both real-time monitoring and
retrospective audit requirements.

---

## 10. Reference Implementation Layout

The reference implementation is organized as follows:

```
sip/
  envelope/         # IntentEnvelope models and validation
  extensions.py     # Protocol extension key validation (x_ / vendor. rules)
  registry/         # CapabilityDescriptor and registry service
                    #   storage.py: InMemoryCapabilityStore + JsonFileCapabilityStore
  negotiation/      # Capability matcher, planner, result models
  translator/       # Binding adapters (REST, gRPC, MCP, A2A, RAG)
  policy/           # Policy engine, scopes, risk classification
  observability/    # Tracing, audit records, structured logging
  broker/           # Broker service and HTTP interface
                    #   service.py: BrokerService + FastAPI app
                    #   identity.py: external identity header adapter
                    #   discovery.py: DiscoveryService with peer federation
                    #   federation.py: FederationConfig, FederatedPeer, PeerTrustLevel
data/
  capabilities.json # Default persistent capability storage (created at runtime)
examples/
  http_broker_demo.py              # HTTP broker usage and curl examples
  persistent_registry_demo.py     # Registry persistence save/reload demo
  external_identity_demo.py       # Identity header mapping demo
  protocol_extensions_demo.py     # Extension fields on core protocol objects
  capability_discovery_api_demo.py # Capability discovery HTTP API demo
  distributed_brokers_demo.py     # Multi-broker peer discovery demo
  federation_demo.py              # Federation trust levels demo
```

---

## 11. Protocol Extension Points

All core SIP protocol objects support an optional `extensions` field for
carrying vendor or application-specific metadata without modifying the core
protocol schema.

**Extension key rules:**

| Format | Example | Description |
|--------|---------|-------------|
| `x_<name>` | `x_routing_hint` | Custom / vendor-local extension |
| `<vendor>.<name>` | `acme.priority` | Namespace-qualified extension |

**Rules:**
- Extension keys must use one of the two formats above.
- Reserved core field names (e.g. `intent_id`, `actor`, `trace_id`) cannot be used as extension keys.
- Unknown extensions are always preserved and never cause protocol failures.
- Extensions must not override core protocol semantics.
- All validation is enforced at object construction time via Pydantic validators.

**Objects that support extensions:**

| Object | Field |
|--------|-------|
| `IntentEnvelope` | `extensions` |
| `CapabilityDescriptor` | `extensions` |
| `NegotiationResult` | `extensions` |
| `ExecutionPlan` | `extensions` |
| `AuditRecord` | `extensions` |

**Backward compatibility:** All existing code that does not populate `extensions` continues to work unchanged. The field defaults to an empty dict.

---

## 12. Capability Discovery API

The broker exposes three capability discovery endpoints:

### `GET /sip/capabilities`

Returns the full list of registered capabilities as JSON-serialized `CapabilityDescriptor` objects.

### `GET /sip/capabilities/{capability_id}`

Returns a single capability by its unique ID. Returns `404` if not found.

### `POST /sip/capabilities/discover`

Accepts a `DiscoveryRequest` JSON body and returns a `DiscoveryResponse` with ranked capability candidates.

**`DiscoveryRequest` fields (all optional):**

| Field | Type | Description |
|-------|------|-------------|
| `intent_name` | string | Machine-readable intent name to match |
| `intent_domain` | string | Functional domain to filter by |
| `operation_class` | enum | Operation class to match |
| `preferred_bindings` | list[BindingType] | Preferred binding types |
| `candidate_capabilities` | list[string] | Hint: preferred capability IDs |
| `trust_level` | TrustLevel | Trust level of requesting actor |
| `max_results` | int (1–100) | Maximum candidates to return (default 5) |
| `include_remote` | bool | Include peer broker candidates (default true) |

**`DiscoveryResponse` fields:**

| Field | Type | Description |
|-------|------|-------------|
| `candidates` | list[DiscoveryCandidate] | Ranked candidates, best first |
| `total` | int | Total candidates returned |
| `local_count` | int | Number of local candidates |
| `remote_count` | int | Number of remote (peer) candidates |
| `peers_queried` | list[string] | Broker IDs of peers queried |
| `peers_failed` | list[string] | Broker IDs of peers that failed |

Each `DiscoveryCandidate` includes `capability_id`, `name`, `score`,
`source_broker_id` (null for local), `routing_allowed`, and `discovery_path`.

---

## 13. Distributed Brokers

The `DiscoveryService` (`sip/broker/discovery.py`) provides optional peer broker
federation when a `FederationConfig` is injected.

### Peer discovery flow:

1. `DiscoveryService.discover(request)` is called.
2. Local registry is queried using `CapabilityRegistryService.find_matches`.
3. For each configured peer, an HTTP `POST /sip/capabilities/discover` is sent.
4. Remote results are tagged with the source broker's ID, URL, and trust level.
5. Local and remote candidates are aggregated deterministically.

### Aggregation rules:

- When `prefer_local=True` (default), local candidates appear before remote candidates.
- Remote candidates are sorted by `(trust_level DESC, score DESC, broker_id ASC)`.
- When `prefer_local=False`, all candidates are sorted by score, with local candidates winning ties.
- The final list is trimmed to `max_results`.

### Error handling:

- **Soft mode** (`strict_mode=False`, default): peer failures are logged and skipped.
- **Strict mode** (`strict_mode=True`): any peer failure raises `RuntimeError`.

---

## 14. Federation Model

The federation model is implemented in `sip/broker/federation.py`.

### Core concepts:

| Concept | Description |
|---------|-------------|
| `FederatedPeer` | Describes a trusted peer broker: ID, URL, trust level |
| `PeerTrustLevel` | `DISCOVERY`, `ROUTING`, or `FULL` |
| `FederationConfig` | Broker identity + list of trusted peers + policy flags |
| `RemoteCapabilityResult` | A capability returned by a peer, with source provenance |

### Trust levels:

| Level | Discovery | Routing | Description |
|-------|-----------|---------|-------------|
| `DISCOVERY` | ✓ | ✗ | Peer capabilities appear in results but cannot be routed |
| `ROUTING` | ✓ | ✓ | Peer capabilities may be included in execution plans |
| `FULL` | ✓ | ✓ | Fully trusted peer |

The `routing_allowed` flag on each `DiscoveryCandidate` reflects the peer's trust level. The local broker's planner and policy engine **must** check `routing_allowed` before including a remote capability in an execution plan.

### Provenance preservation:

Remote capability results carry a `discovery_path` list that records the broker IDs through which the capability was discovered. This enables end-to-end provenance tracking across broker boundaries.

### Policy boundary:

The local broker is always the final policy authority. Remote discovery results do not bypass local policy evaluation. The `routing_allowed` flag is a pre-filter; local scope, risk, and sensitivity checks still apply to all capabilities — local and remote — before execution planning proceeds.


---

## 9. Production Control Plane (v0.2)

This section documents the production-grade evolution of SIP introduced in v0.2. All changes are **additive and backward compatible** — existing behaviour is preserved.

### 9.1 Canonical Internal Model: NormalizedIntent

`NormalizedIntent` (`sip.core.normalized_intent`) is a new internal model that provides a stable, version-independent view of an actor's intent inside the pipeline. It is never exposed on the wire; `IntentEnvelope` remains the external protocol object.

The `from_envelope(envelope)` adapter converts an `IntentEnvelope` into a `NormalizedIntent`. The adapter **fails closed**: any missing critical field (intent_id, correlation_id, actor identity, goal) raises `ValueError`.

Key fields:
- `intent_id` / `correlation_id` / `schema_version`
- `actor` (NormalizedActor with originator + delegation_chain)
- `tenant`, `goal`, `constraints`, `required_capabilities`
- `risk_level`, `compliance_requirements`, `data_sensitivity`, `jurisdiction`
- `preferred_execution_mode`, `trust_requirements`
- `raw_request` (full envelope snapshot for audit)
- `metadata`

### 9.2 Pluggable Policy Engine Interface

`PolicyEngineInterface` (`sip.policy.interface`) is a new ABC that defines the canonical policy evaluation contract:

```python
def evaluate(normalized_intent, candidates) -> PolicyResult
```

`PolicyResult` fields:
- `allowed` (bool)
- `reason_code` (machine-readable, from `ReasonCode`)
- `reason` (human-readable)
- `conditions` (pre-execution conditions)
- `required_approvals` (approver IDs / roles)
- `allowed_capabilities` (filtered candidate list)
- `evaluation_notes`

`CanonicalPolicyEngine` (`sip.core.policy_engine`) implements the interface. It evaluates each candidate capability through:
1. Trust level present (fail closed)
2. Provenance present (when `require_provenance=True`)
3. Delegation chain depth (max 5)
4. Scope check per capability
5. Trust tier check per capability
6. Risk + operation class (approval required?)
7. Risk + data sensitivity (hard denial)
8. Capability-level approval override

The existing `PolicyEngine` in `sip.policy.engine` is **unchanged**.

### 9.3 ExecutionType Abstraction

`ExecutionType` enum (`sip.negotiation.planner`) provides protocol-agnostic execution type labels, separate from the wire-level `BindingType`:

| ExecutionType | Meaning |
|---|---|
| `mcp_tool` | Model Context Protocol tool call |
| `rest_api` | HTTP REST API |
| `grpc_service` | gRPC service call |
| `a2a_agent` | Agent-to-agent delegation |
| `internal_skill` | Internal system skill |
| `manual_step` | Human action required |

`ExecutionPlan` is extended (v0.2) with: `execution_type`, `preconditions`, `guard_conditions`, `fallback_behavior` (default: `fail_closed`), `expected_outputs`, `selection_basis`. All new fields have defaults for backward compatibility.

### 9.4 DeterministicPlanner

`DeterministicPlanner` (`sip.core.deterministic_planner`) is a new planner that:
- Accepts `NormalizedIntent`, `PolicyResult`, and externally-supplied `candidates`
- **Never performs discovery**
- Only considers `PolicyResult.allowed_capabilities`
- Applies stable tie-breaking: `(provider_id, capability_id)` ascending sort
- **Fails closed** if no safe plan can be produced (`FailClosedError`)

### 9.5 Extended AuditRecord (v0.2)

`AuditRecord` is extended with optional fields (all default to safe values):
- `correlation_id` – trace/correlation ID
- `normalized_intent_id` – ID of the NormalizedIntent
- `policy_reason_code` – machine-readable policy reason
- `selection_basis` – explanation of capability selection
- `expected_execution_path` – ordered step names
- `pre_execution_denial` – True when record captures a denial

### 9.6 Fail-Closed Logic

`sip.core.fail_closed` provides explicit fail-closed check functions:
- `check_policy_decision_present` – deny if result is None
- `check_policy_allowed` – deny if policy denied
- `check_provenance_present` – deny if required but missing
- `check_trust_level_present` – deny if trust level missing
- `check_allowed_capabilities_present` – deny if no capabilities pass
- `check_required_approvals_met` – deny if approvals unsatisfied
- `check_no_deterministic_plan_possible` – deny if plan is None

All checks raise `FailClosedError` which wraps a `StructuredDenial` with `reason_code`, `reason`, and `required_actions`.

### 9.7 SIPPipeline and DecisionBundle

`SIPPipeline` (`sip.core.pipeline`) orchestrates the canonical 7-stage pipeline:

```
IntentEnvelope + candidate_capabilities
         ↓
1. Intent ingestion
2. Intent normalization (→ NormalizedIntent)
3. Envelope validation (existing validator)
4. Policy evaluation (CanonicalPolicyEngine)
5. Deterministic planning (DeterministicPlanner)
6. Audit record generation (always, including on denial)
7. DecisionBundle output
```

`DecisionBundle` (`sip.core.decision_bundle`) is the output:
- `normalized_intent`
- `policy_result`
- `execution_plan` (None when denied)
- `audit_record` (**always present**)
- `denied` / `allowed` flags

### 9.8 SIP Does NOT

- Perform capability discovery (discovery is external, e.g. ADP)
- Execute capabilities
- Rank or score providers
- Make probabilistic decisions

### 9.9 Backward Compatibility

- `BrokerService` and `process_intent` are **unchanged**
- `IntentEnvelope`, `CapabilityDescriptor`, `NegotiationResult`, `ExecutionPlan`, `AuditRecord` are **extended** with optional fields only
- All 358 existing tests continue to pass
- `SIPPipeline` is a new, independent entry point

