# Semantic Intent Protocol (SIP) – Overview

## What is SIP?

SIP (Semantic Intent Protocol) is an open semantic interoperability protocol for AI agents and software systems. It standardizes how systems express semantic intent, negotiate capabilities, apply trust and policy controls, and translate requests into deterministic execution through existing protocols such as REST, gRPC, MCP, A2A, and retrieval systems.

## The Problem SIP Solves

Modern software systems face three compounding integration challenges:

1. **API explosion** – Every system exposes its own API with its own schema, authentication, and error model. Integrating N systems requires N integration points that each need to be maintained.

2. **Schema coupling** – Systems are tightly coupled to the schemas of the APIs they call. Any schema change breaks consumers.

3. **LLM ambiguity** – Natural language is expressive and accessible, but it is too ambiguous and unpredictable for direct execution in production systems. You cannot safely hand an LLM response directly to a payment API.

## SIP's Answer

SIP introduces a structured **intent layer** that sits above existing execution protocols:

```
User or system
  → AI agent / LLM proposes IntentEnvelope
  → SIP broker validates and authorizes the request
  → SIP produces an ExecutionPlan
  → execution occurs through REST, gRPC, MCP, A2A, or RAG bindings
```

An intent envelope expresses **what** is desired, not **how** to achieve it. SIP negotiates **which capability** should satisfy the intent, evaluates **policy and trust**, and produces a **deterministic execution plan** that is handed to the appropriate execution protocol adapter.

Natural language can be included in the envelope as an annotation for auditing and observability, but it is **never executed directly**.

## Role of AI Agents and LLMs

AI agents or LLMs may generate or propose `IntentEnvelope` objects, but this happens **outside** the SIP protocol layer. SIP itself does not perform LLM inference. SIP acts as a **deterministic control layer** responsible for validation, capability negotiation, authorization, and execution planning. The separation ensures that non-deterministic AI reasoning is kept outside the security boundary, while SIP enforces deterministic, auditable control over what actually executes.

## Core Principles

1. **Intent ≠ Execution** – The intent layer is always separate from the execution layer.
2. **Determinism is non-negotiable** – Every execution plan must be fully specified and reproducible.
3. **Trust is explicit** – Every intent carries trust level, scopes, and delegation chain.
4. **Policy is always evaluated** – No execution proceeds without a policy decision.
5. **Auditability is built in** – Every processed intent produces an audit record.

## What SIP Is Not

- SIP is **not** a replacement for REST, gRPC, MCP, or any other execution protocol.
- SIP is **not** an LLM orchestration framework.
- SIP is **not** a workflow engine or task scheduler.
- SIP is **not** a messaging queue or event bus.
- The HTTP API is **one transport surface** for SIP — it is not the protocol definition itself.

SIP is a **semantic negotiation and translation layer** that makes existing systems interoperable through structured intent expression.

## Current Status

SIP v0.1 is the initial reference release. The Python reference implementation in this repository demonstrates all core protocol capabilities.

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

