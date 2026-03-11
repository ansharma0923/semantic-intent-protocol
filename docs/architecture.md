# SIP Architecture

## 1. Overview

The Semantic Intent Protocol (SIP) is a protocol for expressing, routing, and
executing semantic intents across heterogeneous execution environments. Rather
than coupling actors directly to specific APIs or transport protocols, SIP
introduces a structured intent layer that sits above execution systems.

Actors express *what* they want to achieve through an `IntentEnvelope`. The SIP
layer is responsible for discovering the right capability, evaluating policy,
and producing an execution plan. Actual execution is delegated to an external
system via a binding adapter.

AI agents or LLMs may generate or propose `IntentEnvelope` objects, but this
happens **outside** the SIP protocol layer. SIP itself does not perform LLM
inference. SIP acts as a **deterministic control layer** — the security boundary
between AI-generated intent and execution systems — responsible for validation,
capability negotiation, authorization, and execution planning.

```
User
  ↓
AI Agent / LLM
  ↓
IntentEnvelope
  ↓
SIP Broker
  ├─ Envelope Validation
  ├─ Capability Negotiation
  ├─ Policy Evaluation
  └─ ExecutionPlan
  ↓
Execution Systems
  REST | gRPC | MCP | A2A | RAG
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
| `GET`  | `/capabilities` | List all registered capabilities. |

**HTTP status codes returned by `POST /sip/intents`:**

| Code | Condition |
|------|-----------|
| `200` | Intent processed; execution plan created. |
| `202` | Intent processed; approval required before execution. |
| `400` | Envelope validation failed. |
| `403` | Policy denied the intent. |
| `422` | Malformed request body; cannot be parsed as an `IntentEnvelope`. |
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
  registry/         # CapabilityDescriptor and registry service
                    #   storage.py: InMemoryCapabilityStore + JsonFileCapabilityStore
  negotiation/      # Capability matcher, planner, result models
  translator/       # Binding adapters (REST, gRPC, MCP, A2A, RAG)
  policy/           # Policy engine, scopes, risk classification
  observability/    # Tracing, audit records, structured logging
  broker/           # Broker service and HTTP interface
                    #   service.py: BrokerService + FastAPI app
                    #   identity.py: external identity header adapter
data/
  capabilities.json # Default persistent capability storage (created at runtime)
examples/
  http_broker_demo.py          # HTTP broker usage and curl examples
  persistent_registry_demo.py  # Registry persistence save/reload demo
  external_identity_demo.py    # Identity header mapping demo
```

