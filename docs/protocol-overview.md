# SIP Protocol Overview

## Problem

AI systems today lack a standardized, machine-interpretable way to express intent across agents, tools, services, and execution environments.

Modern software architectures face three compounding integration challenges:

1. **API proliferation** — Every system exposes its own API, schema, and authentication model. Each new integration requires custom coupling code. As the number of agents and services grows, the number of point-to-point integrations grows with it.

2. **Schema coupling** — Systems are tightly coupled to the specific schemas of the APIs they invoke. A schema change in a downstream system can silently break callers that had no way to validate intent before the call.

3. **Natural language ambiguity** — Large language models can express intent in natural language, but natural language is too ambiguous, inconsistent, and unpredictable for safe direct execution in production systems. Something must sit between the model's output and the execution system's input.

---

## Why Existing Approaches Are Fragmented

Several categories of tooling address parts of this problem, but none address it completely:

| Category | What it does | What it leaves out |
|---|---|---|
| REST / gRPC APIs | Define how to call a system | Do not express intent semantically; require caller to know the exact schema |
| Tool-calling protocols (MCP, A2A) | Standardize how agents invoke tools | Do not provide policy, trust, authorization, or provenance |
| Agent frameworks (LangChain, AutoGen, etc.) | Orchestrate agent workflows | Do not standardize the intent message or the control plane |
| Workflow engines | Schedule and sequence tasks | Receive execution specifications, not semantic intents |

The result is a fragmented ecosystem where every team builds their own thin layer between an AI agent's intent and the execution system, with inconsistent trust models, no standard audit trail, and no shared vocabulary.

---

## What SIP Standardizes

**Semantic Intent Protocol (SIP) provides a standardized, machine-interpretable intent layer for AI agents, services, and execution environments.**

SIP standardizes:

1. **The intent message structure** — A portable `IntentEnvelope` that any actor (AI agent, service, human workflow) can produce and any SIP-aware broker can consume.

2. **The control plane behavior** — A deterministic pipeline that validates, matches, authorizes, and plans every intent before any external system is touched.

3. **The protocol objects** — `IntentEnvelope`, `CapabilityDescriptor`, `NegotiationResult`, `ExecutionPlan`, and `AuditRecord` are defined as versioned, schema-backed objects.

4. **The trust and authorization model** — Every intent carries explicit trust level, scopes, and delegation chain. Policy is always evaluated deterministically.

5. **The audit contract** — Every processed intent produces an immutable `AuditRecord`, regardless of outcome.

---

## Core Flow

```
┌─────────────────────────────────┐
│   Actor (AI Agent / Service)    │
│                                 │
│  Produces an IntentEnvelope     │
│  carrying:                      │
│  - who is making the request    │
│  - what they want               │
│  - trust, scopes, provenance    │
│  - preferred bindings           │
└────────────────┬────────────────┘
                 │ IntentEnvelope
                 ▼
┌─────────────────────────────────┐
│         SIP Broker              │
│                                 │
│  1. Validation                  │
│     - schema and type checks    │
│     - required field checks     │
│                                 │
│  2. Capability Negotiation      │
│     - score and rank candidates │
│     - select best match         │
│                                 │
│  3. Policy Evaluation           │
│     - scope sufficiency         │
│     - trust tier check          │
│     - risk assessment           │
│     - approval gating           │
│                                 │
│  4. Execution Planning          │
│     - produce ExecutionPlan     │
│     - ground parameters         │
│     - record AuditRecord        │
└────────────────┬────────────────┘
                 │ ExecutionPlan + AuditRecord
                 ▼
┌─────────────────────────────────┐
│       Execution Systems         │
│                                 │
│  REST | gRPC | MCP | A2A | RAG  │
└─────────────────────────────────┘
```

**Key principle:** SIP produces a plan. It does not execute the plan. External adapters translate the plan into actual API calls, gRPC requests, RAG queries, or agent-to-agent messages.

**Natural language is never executed directly.** It may appear as a human-readable hint in the envelope for audit annotation, but it has no operational effect on the broker's behavior.

---

## Why Deterministic Control Plane Matters

Many integration problems in AI systems arise from non-determinism and ambiguity in the control path:

- An LLM might select different tools on different runs for the same intent.
- There is no consistent mechanism to enforce authorization before tool invocation.
- Audit trails are ad hoc and inconsistent across systems.

SIP's control plane is **fully deterministic**:

- Given the same `IntentEnvelope` and the same capability registry, the broker will always produce the same `ExecutionPlan`.
- Policy decisions are rule-based and reproducible.
- No LLM calls occur within the SIP broker. All matching and planning is algorithmic.

This determinism makes SIP suitable for production infrastructure, regulated environments, and any context where reproducibility and auditability are required.

---

## How SIP Complements Agent Frameworks and APIs

SIP is **not a replacement** for agent frameworks, APIs, or tool-calling protocols. It is a control-plane layer that sits between them:

```
┌──────────────────────────────┐
│  LLM / Agent Framework       │
│  (LangChain, AutoGen, etc.)  │
│                              │
│  Produces intent expressions │
└──────────────┬───────────────┘
               │ produces IntentEnvelope
               ▼
┌──────────────────────────────┐
│  SIP Intent Layer            │
│  (broker + control plane)    │
│                              │
│  Validates, authorizes, plans│
└──────────────┬───────────────┘
               │ ExecutionPlan
               ▼
┌──────────────────────────────┐
│  Execution Systems           │
│  REST | gRPC | MCP | A2A     │
│  RAG | Infrastructure APIs   │
└──────────────────────────────┘
```

| Category | Relationship to SIP |
|---|---|
| AI agent frameworks | May produce or translate intents into `IntentEnvelope` objects |
| Tool invocation protocols (MCP, A2A) | Serve as execution bindings that SIP delegates to |
| REST / gRPC APIs | Execution targets described by `CapabilityDescriptor` objects |
| Workflow engines | May receive `ExecutionPlan` results as inputs to downstream workflow steps |
| Retrieval systems (RAG) | An execution binding for knowledge retrieval intents |

---

## Why SIP Is Useful in Enterprise and Infrastructure Environments

Enterprise and infrastructure environments have requirements that generic agent frameworks do not address:

| Requirement | How SIP addresses it |
|---|---|
| Authorization before action | Policy engine evaluates every intent; no execution proceeds without a pass |
| Audit trail | Every processed intent produces an immutable `AuditRecord` |
| Delegation and provenance | `ProvenanceBlock` records originator, delegation chain, and authority scope |
| Risk gating | High-risk capabilities require explicit approval before plan execution |
| Schema decoupling | Actors express intent by name; SIP resolves to the correct capability |
| Federation | Brokers can discover and route to peer brokers in distributed deployments |

---

## Example SIP Message Structure

The following is a representative `IntentEnvelope` for a knowledge retrieval intent:

```json
{
  "sip_version": "0.1",
  "message_type": "intent_request",
  "intent_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "trace_id": "b2c3d4e5-f6a7-8901-bcde-f01234567891",
  "actor": {
    "actor_id": "research-agent-01",
    "actor_type": "ai_agent",
    "name": "Research Assistant",
    "trust_level": "internal",
    "scopes": ["sip.knowledge.read"]
  },
  "target": {
    "target_type": "capability",
    "namespace": "knowledge_management"
  },
  "intent": {
    "intent_name": "retrieve_document",
    "intent_domain": "knowledge_management",
    "operation_class": "retrieve",
    "natural_language_hint": "Find documents about Q4 2023 financial results",
    "parameters": {
      "query": "Q4 2023 financial results",
      "top_k": 5,
      "format": "json"
    }
  },
  "desired_outcome": {
    "summary": "Return the top-5 most relevant documents for the query",
    "output_format": "json"
  },
  "constraints": {
    "time_budget_ms": 3000,
    "determinism_required": "strict"
  },
  "protocol_bindings": [
    { "binding_type": "rag" }
  ]
}
```

The broker validates this envelope, matches it to the `sip.knowledge.retrieve` capability, checks that the actor holds the `sip.knowledge.read` scope, and produces an `ExecutionPlan` ready for the RAG adapter. The originating agent never directly invokes the retrieval system.

---

## Further Reading

- [docs/architecture.md](architecture.md) — Detailed component architecture and data flow
- [docs/sip-wire-spec-v0.1.md](sip-wire-spec-v0.1.md) — Normative wire format specification
- [docs/capability-model.md](capability-model.md) — Capability descriptors and registry
- [docs/security-model.md](security-model.md) — Trust, scopes, policy, and audit
- [schema/](../schema/) — Formal JSON Schemas for all protocol objects
- [protocol-vectors/](../protocol-vectors/) — Canonical JSON examples for all protocol objects
- [docs/quickstart.md](quickstart.md) — Getting started guide
