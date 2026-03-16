# Semantic Intent Protocol (SIP) – Overview

## What is SIP?

**Semantic Intent Protocol (SIP) is an open, deterministic control-plane protocol for AI agents, services, and infrastructure systems.**

SIP provides a standardized, machine-interpretable intent layer that enables interoperability between AI agents, tools, and execution systems. It converts semantic intent into validated, authorized execution plans before actions are executed in external systems. SIP sits above execution protocols (REST, gRPC, MCP, A2A, RAG) and below AI agent reasoning layers, providing a structured negotiation, authorization, and planning layer between them.

SIP complements AI frameworks, APIs, and execution runtimes — it does not replace them.

## The Problem SIP Solves

Modern software systems face three compounding integration challenges:

1. **API explosion** – Every system exposes its own API with its own schema, authentication, and error model. Integrating N systems requires N integration points that each need to be maintained.

2. **Schema coupling** – Systems are tightly coupled to the schemas of the APIs they call. Any schema change breaks consumers.

3. **LLM ambiguity** – Natural language is expressive and accessible, but it is too ambiguous and unpredictable for direct execution in production systems. You cannot safely hand an LLM response directly to a payment API.

## SIP's Answer

SIP provides a **deterministic control plane** that converts semantic intent into validated, authorized execution plans before anything is executed:

```
AI Agent / Software System
  → IntentEnvelope
  → SIP Control Plane (validation, negotiation, authorization, planning)
  → ExecutionPlan
  → external execution system (REST, gRPC, MCP, A2A, RAG)
```

An intent envelope expresses **what** is desired, not **how** to achieve it. SIP negotiates **which capability** should satisfy the intent, evaluates **policy and trust**, and produces a **deterministic execution plan** that is handed to the appropriate execution protocol adapter.

Natural language can be included in the envelope as an annotation for auditing and observability, but it is **never executed directly**.

## Role of AI Agents and LLMs

AI agents or LLMs may generate or propose `IntentEnvelope` objects, but this happens **outside** the SIP protocol layer. SIP itself does not perform LLM inference. SIP acts as a **deterministic control plane** responsible for validation, capability negotiation, authorization, and execution planning. The separation ensures that non-deterministic AI reasoning is kept outside the security boundary, while SIP enforces deterministic, auditable control over what actually executes.

## Core Principles

1. **Intent ≠ Execution** – The intent layer is always separate from the execution layer.
2. **Determinism is non-negotiable** – Every execution plan must be fully specified and reproducible.
3. **Trust is explicit** – Every intent carries trust level, scopes, and delegation chain.
4. **Policy is always evaluated** – No execution proceeds without a policy decision.
5. **Auditability is built in** – Every processed intent produces an audit record.

## What SIP Is Not

- SIP is **not** a replacement for REST, gRPC, MCP, or any other execution protocol.
- SIP is **not** an LLM or AI inference engine.
- SIP is **not** an agent framework.
- SIP is **not** a workflow engine or task scheduler.
- SIP is **not** a messaging queue or event bus.
- SIP is **not** a direct execution engine — it produces plans that external systems carry out.
- The HTTP API is **one transport surface** for SIP — it is not the protocol definition itself.

## Where SIP Fits

SIP complements rather than replaces existing categories:

| Category | Relationship to SIP |
|---|---|
| AI agent frameworks | May create or propose `IntentEnvelope` objects submitted to SIP |
| Workflow engines | May receive `ExecutionPlan` results to trigger downstream steps |
| Tool invocation protocols (MCP, A2A) | Serve as execution bindings that SIP delegates to |
| REST / gRPC APIs | Execution targets that SIP produces plans for |
| Retrieval systems (RAG) | Execution binding for knowledge retrieval intents |

## Current Status

SIP v0.1 is the initial reference release of the deterministic control plane protocol. The Python reference implementation in this repository demonstrates all core protocol capabilities.

### SIP v0.1 includes:

- **Core protocol objects** – `IntentEnvelope`, `CapabilityDescriptor`, `ExecutionPlan`, `AuditRecord`, and all supporting models.
- **Capability registry** – In-memory and **file-backed JSON persistence** for capability descriptors.  Capabilities can be saved to disk and reloaded on startup (`data/capabilities.json` by default, configurable via `SIP_CAPABILITIES_FILE`).
- **Broker HTTP API** – A FastAPI-based HTTP interface exposing:
  - `POST /sip/intents` – submit an `IntentEnvelope` and receive a structured broker response.
  - `GET /healthz` – liveness / readiness check.
  - `GET /capabilities` – list registered capabilities.
- **External identity integration** – Support for mapping externally authenticated identity claims (from trusted HTTP headers such as `X-Actor-Id`, `X-Actor-Type`, `X-Trust-Level`, `X-Scopes`) into SIP actor and trust context.  Authentication remains external to SIP; SIP only maps pre-verified claims.
- **Policy engine** – Deterministic scope, risk, data sensitivity, and delegation chain evaluation.
- **Provenance and intent laundering protections** – Optional `ProvenanceBlock` on each envelope enforces that delegated authority cannot exceed the originator's authority.
- **Negotiation engine** – Deterministic capability matching and ranking.
- **Execution adapters** – REST, gRPC, MCP, A2A, and RAG translation adapters.
- **Observability** – Structured audit records, tracing, and logging at every pipeline stage.

### Protocol evolution (current):

The following capabilities have been added to evolve the SIP reference implementation beyond v0.1 while preserving backward compatibility:

- **Protocol extension points** – All core protocol objects (`IntentEnvelope`, `CapabilityDescriptor`, `NegotiationResult`, `ExecutionPlan`, `AuditRecord`) now support an optional `extensions` field for carrying vendor or application-specific metadata.  Extension keys must use `x_<name>` or `<vendor>.<name>` format.  Unknown extensions are always preserved and never affect core protocol processing.  See `sip/extensions.py` for validation rules.

- **Capability discovery API** – New HTTP endpoints for structured capability discovery:
  - `GET /sip/capabilities` – list all registered capabilities as full descriptors.
  - `GET /sip/capabilities/{id}` – retrieve a capability by its unique ID.
  - `POST /sip/capabilities/discover` – submit a `DiscoveryRequest` and receive ranked capability candidates.  Supports filtering by `intent_name`, `intent_domain`, `operation_class`, `preferred_bindings`, `trust_level`, and more.

- **Distributed brokers** – The `DiscoveryService` supports optional peer broker federation.  When a `FederationConfig` is provided, the service forwards discovery requests to configured peer brokers via HTTP and aggregates local and remote candidates deterministically.  Local capabilities are preferred by default.  Peer failures are handled gracefully (soft mode) or cause fast-fail (strict mode).

- **Federation model** – A trust-aware multi-broker model built on `FederationConfig` and `FederatedPeer`.  Three peer trust levels control capability visibility:
  - `PeerTrustLevel.DISCOVERY` – remote capabilities appear in discovery results but are not eligible for routing.
  - `PeerTrustLevel.ROUTING` – remote capabilities may be included in execution plans.
  - `PeerTrustLevel.FULL` – peer is fully trusted for discovery, routing, and execution delegation metadata.
  Remote capabilities are tagged with source broker provenance.  Local broker is always the final policy authority.

The protocol specification is at v0.1 and should be considered a working draft open for community feedback.

---

## Ecosystem Capabilities

### Protocol Vectors

Canonical JSON fixtures for all core SIP protocol objects are available in [`protocol-vectors/`](../protocol-vectors/). These serve as the ground truth for validating implementations across languages and runtimes. Every SDK must be able to parse and round-trip all vectors without data loss.

### Interoperability Tests

Distributed broker interoperability tests are available in [`tests/interoperability/`](../tests/interoperability/). These tests verify:
- Local and remote capability discovery across multiple brokers
- Deterministic result aggregation
- Graceful handling of unavailable peers
- Provenance preservation across broker boundaries
- Policy enforcement on remote capabilities

### Go SDK

A Go language SDK implementing all core SIP protocol types and HTTP client support is available in [`sdk/go/`](../sdk/go/). The Go SDK is compatible with the canonical protocol vectors.

### Governance

The protocol governance model—including versioning policy, extension namespace rules, compatibility guarantees, and security review requirements—is documented in [`docs/governance.md`](governance.md).

