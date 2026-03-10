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
Actor → Intent Envelope → SIP Broker → Execution Plan → Deterministic Execution
```

An intent envelope expresses **what** is desired, not **how** to achieve it. SIP negotiates **which capability** should satisfy the intent, evaluates **policy and trust**, and produces a **deterministic execution plan** that is handed to the appropriate execution protocol adapter.

Natural language can be included in the envelope as an annotation for auditing and observability, but it is **never executed directly**.

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

SIP is a **semantic negotiation and translation layer** that makes existing systems interoperable through structured intent expression.

## Current Status

SIP v0.1 is in private development. The Python reference implementation in this repository demonstrates the core protocol objects, capability registry, negotiation engine, policy engine, and execution adapters.

The protocol specification is at v0.1 and should be considered a working draft.
