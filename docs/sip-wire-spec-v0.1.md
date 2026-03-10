# Semantic Intent Protocol (SIP) — Wire-Level Specification v0.1

**Status:** Working Draft  
**Version:** 0.1  
**Date:** 2025  
**Repository:** semantic-intent-protocol

---

## Table of Contents

1. [Overview](#1-overview)
2. [Terminology](#2-terminology)
3. [Architectural Model](#3-architectural-model)
4. [Protocol Objects](#4-protocol-objects)
   - 4.1 [IntentEnvelope](#41-intentenvelope)
   - 4.2 [CapabilityDescriptor](#42-capabilitydescriptor)
   - 4.3 [NegotiationResult](#43-negotiationresult)
   - 4.4 [ExecutionPlan](#44-executionplan)
   - 4.5 [AuditRecord](#45-auditrecord)
5. [Capability Discovery](#5-capability-discovery)
6. [Policy and Trust Model](#6-policy-and-trust-model)
7. [Execution Bindings](#7-execution-bindings)
8. [Observability and Auditability](#8-observability-and-auditability)
9. [Determinism Requirements](#9-determinism-requirements)
10. [Versioning](#10-versioning)
11. [Example End-to-End Flow](#11-example-end-to-end-flow)

---

## 1. Overview

### 1.1 Purpose

The Semantic Intent Protocol (SIP) is an open semantic interoperability protocol for AI agents and software systems. SIP defines how systems express semantic intent, negotiate capabilities, enforce trust and policy, and translate requests into deterministic execution through existing execution protocols.

SIP addresses a structural problem in modern distributed systems: as the number of AI agents, microservices, and tool integrations grows, systems increasingly depend on ad hoc schema coupling, direct natural-language execution, or implicit capability assumptions. These approaches do not compose well and do not provide the auditability, safety, and determinism required for production use.

### 1.2 What SIP Is

SIP is an **intent negotiation and execution planning protocol**. It specifies:

- The structure of a semantic intent expression (`IntentEnvelope`).
- How capability providers describe what they can do (`CapabilityDescriptor`).
- How a broker selects a capability and binding for an intent (`NegotiationResult`).
- How policy is evaluated before execution (`PolicyDecisionSummary`).
- How a deterministic execution plan is produced (`ExecutionPlan`).
- How execution intent is translated to a concrete execution protocol payload (Binding Translation).
- How every intent is recorded for audit (`AuditRecord`).

### 1.3 What SIP Is Not

SIP is not a transport protocol. It does not define how bytes are carried over a network. SIP sits **above** existing execution protocols (REST, gRPC, MCP, A2A, RAG) and standardizes semantic negotiation, not transport.

SIP is not a natural-language processing system. Natural language is permitted only as an annotation or audit hint (`natural_language_hint`). It is never executed directly.

SIP is not an LLM orchestration framework. No machine-learning inference is performed within the SIP processing pipeline.

### 1.4 Problem SIP Solves

| Problem | SIP Response |
|---|---|
| Schema coupling between callers and services | Capability registry with structured matching |
| Direct natural-language execution by AI agents | Natural language is annotation only; all execution is deterministic |
| No standard trust or policy layer for agent calls | Structured `TrustBlock` and `PolicyEngine` with explicit decisions |
| No standard audit trail for AI-initiated actions | `AuditRecord` generated for every processed intent |
| Protocol fragmentation (REST vs gRPC vs MCP vs A2A) | Unified intent layer with binding-specific adapters |

### 1.5 Positioning

```
┌──────────────────────────────────────────────────┐
│              Actors (Humans, AI Agents,           │
│              Services, Systems)                   │
└────────────────────┬─────────────────────────────┘
                     │  IntentEnvelope
                     ▼
┌──────────────────────────────────────────────────┐
│           SIP Intent Layer                        │
│  • Envelope validation                            │
│  • Capability registry + negotiation              │
│  • Policy engine                                  │
│  • Execution planning                             │
│  • Binding translation                            │
│  • Audit logging                                  │
└───────┬──────────┬──────────┬──────────┬──────────┘
        │          │          │          │
        ▼          ▼          ▼          ▼
      REST        gRPC       MCP        A2A        RAG
  (HTTP/S)  (Protocol  (Tool    (Agent    (Retrieval
             Buffers)   Calls)   Tasks)    Systems)
```

The SIP intent layer is protocol-agnostic. A single `IntentEnvelope` can be translated to any supported execution binding without changing the actor-facing interface.

---

## 2. Terminology

The following terms have specific meanings in this specification.

**IntentEnvelope**  
The root SIP protocol object. Carries a semantic intent from an actor to a target, including trust, constraints, context, and binding preferences. The `IntentEnvelope` is the unit of work presented to the SIP broker.

**CapabilityDescriptor**  
A structured description of a capability registered with the SIP capability registry. Describes what the capability does, the domains it serves, its operation class, required permissions, supported bindings, and risk level.

**NegotiationResult**  
The output of the SIP negotiation engine. Contains ranked capability candidates, the selected capability and binding, and a policy decision summary.

**ExecutionPlan**  
A deterministic execution plan produced after negotiation and policy evaluation. Contains grounded parameters, binding-specific target information, execution steps, and a trace reference. The `ExecutionPlan` is the input to a binding translator adapter.

**AuditRecord**  
An immutable record of a processed intent, generated by the broker after every pipeline execution regardless of outcome. Contains actor identity, intent metadata, capability selection, policy decision, and outcome summary.

**Binding**  
The execution protocol used to carry out an `ExecutionPlan`. Supported bindings are `rest`, `grpc`, `mcp`, `a2a`, and `rag`. A binding translates the abstract plan into protocol-specific payloads.

**Capability Provider**  
An entity that registers one or more `CapabilityDescriptor` objects with the SIP registry. A provider is identified by a `provider_id` and may expose capabilities across multiple domains.

**Actor**  
The entity that originates an `IntentEnvelope`. Actors are classified by type (`human`, `ai_agent`, `service`, `system`) and trust level (`public`, `internal`, `privileged`, `admin`).

**Policy Decision**  
The outcome of evaluating an intent against SIP policy rules for a selected capability. A policy decision produces one of three outcomes: `allow`, `deny`, or `require_approval`.

**Operation Class**  
A high-level classification of the operation expressed by an intent. SIP defines six operation classes: `read`, `write`, `execute`, `analyze`, `retrieve`, `delegate`.

**Trust Level**  
An ordered trust tier assigned to an actor. In ascending order: `public` < `internal` < `privileged` < `admin`. Capabilities declare a `minimum_trust_tier`; actors must meet or exceed it.

**Scope**  
A permission string that an actor must hold to invoke a capability. Scopes follow a dot-separated naming convention (e.g., `sip:knowledge:read`). Capabilities declare `required_scopes`; actors declare held `scopes`.

**Delegation Chain**  
An ordered list of actor identifiers representing the chain of trust delegation. Used to detect and limit proxy forwarding depth. Maximum chain depth is 5 hops.

**Determinism Level**  
An execution requirement set by the actor in the `Constraints` block. Values: `strict` (same input → same output), `bounded` (non-deterministic within defined bounds), `advisory` (best-effort). Default is `strict`.

**Grounded Parameters**  
Parameters from the `IntentEnvelope` that have been matched against the capability's input schema. Required fields absent from the envelope are marked with a `<REQUIRED:field_name>` placeholder.

**Plan ID**  
A unique identifier for an `ExecutionPlan`, generated at planning time. Enables correlation of execution artifacts back to the plan that produced them.

**Trace ID**  
A distributed trace identifier propagated from the `IntentEnvelope` through all downstream objects. Enables end-to-end correlation of intent, negotiation, execution, and audit records.

---

## 3. Architectural Model

### 3.1 SIP Processing Pipeline

Every `IntentEnvelope` submitted to a SIP broker passes through the following ordered pipeline stages:

```
IntentEnvelope
    │
    ▼
[1] Envelope Validation
    │  Validates envelope structure and field constraints.
    │  Rejects malformed envelopes before processing.
    │
    ▼
[2] Capability Discovery
    │  Queries the capability registry.
    │  Scores candidates using deterministic matching rules.
    │  Produces a ranked candidate list.
    │
    ▼
[3] Negotiation
    │  Selects the best matching capability.
    │  Determines compatible bindings.
    │  Sets requires_clarification if no clear winner exists.
    │
    ▼
[4] Policy Evaluation
    │  Evaluates scope requirements.
    │  Evaluates risk level against operation class.
    │  Evaluates data sensitivity.
    │  Evaluates delegation chain depth.
    │  Produces: allow | deny | require_approval
    │
    ▼
[5] Execution Planning
    │  Grounds parameters against capability input schema.
    │  Selects deterministic target (capability + provider + binding).
    │  Constructs ordered execution steps.
    │  Produces ExecutionPlan.
    │
    ▼
[6] Audit Record Generation
    │  Records actor identity, intent metadata, capability selection,
    │  policy decision, and outcome.
    │  Written to append-only audit log.
    │
    ▼
[7] Binding Translation (optional at broker; required before execution)
    │  Translates ExecutionPlan to binding-specific payload
    │  (REST HTTP request, gRPC message, MCP tool call,
    │   A2A agent task, RAG retrieval specification).
    │
    ▼
[8] Deterministic Execution System
       (REST endpoint, gRPC service, MCP tool, A2A agent, retrieval index)
```

### 3.2 Component Responsibilities

| Component | Responsibility |
|---|---|
| **Broker** | Orchestrates the full pipeline. Entry point for intent processing. |
| **Envelope Validator** | Validates `IntentEnvelope` fields and structural constraints. |
| **Capability Registry** | Stores and retrieves `CapabilityDescriptor` objects. |
| **Capability Matcher** | Scores and ranks capabilities against an intent. |
| **Policy Engine** | Evaluates policy rules; returns enriched `NegotiationResult`. |
| **Execution Planner** | Produces `ExecutionPlan` from a `NegotiationResult`. |
| **Audit Logger** | Generates and persists `AuditRecord` objects. |
| **Binding Adapters** | Translate `ExecutionPlan` to protocol-specific payloads. |

### 3.3 Layer Separation

The intent layer is strictly separated from the execution layer. The intent layer ends at the `ExecutionPlan` and `TranslationResult`. Actual execution against the target system (invoking the REST endpoint, calling the gRPC method, running the MCP tool) occurs outside the SIP protocol boundary.

This separation ensures:
- SIP can be adopted without modifying existing execution infrastructure.
- Audit records and policy decisions are generated before execution, not after.
- Execution can be deferred, approved, and replayed from a plan without re-running negotiation.

---

## 4. Protocol Objects

This section defines the primary protocol objects used in SIP v0.1. All objects are defined using JSON Schema-compatible types. The reference implementation uses Pydantic v2 for validation.

### 4.1 IntentEnvelope

The `IntentEnvelope` is the root SIP protocol object. It carries a structured semantic intent from an actor to a target system.

**Field Reference**

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `sip_version` | string | no | `"0.1"` | SIP protocol version. |
| `message_type` | enum | no | `"intent_request"` | SIP message type classification. |
| `intent_id` | string (UUID) | no | auto-generated | Unique identifier for this intent. |
| `trace_id` | string (UUID) | no | auto-generated | Distributed trace identifier. |
| `span_id` | string (UUID) | no | auto-generated | Current span within the trace. |
| `timestamp` | string (ISO 8601) | no | now (UTC) | Time of envelope creation. |
| `actor` | ActorDescriptor | yes | — | The originating actor. |
| `target` | TargetDescriptor | yes | — | The intended target. |
| `intent` | IntentPayload | yes | — | The semantic intent payload. |
| `desired_outcome` | DesiredOutcome | yes | — | The actor's desired outcome. |
| `constraints` | Constraints | no | defaults | Execution constraints. |
| `context` | ContextBlock | no | defaults | Contextual information. |
| `capability_requirements` | array[CapabilityRequirement] | no | `[]` | Explicit capability requirements. |
| `trust` | TrustBlock | no | defaults | Trust and credential block. |
| `protocol_bindings` | array[ProtocolBinding] | no | `[]` | Acceptable bindings in preference order. |
| `negotiation` | NegotiationHints | no | defaults | Hints to guide capability negotiation. |
| `integrity` | IntegrityBlock | no | defaults | Integrity and provenance metadata. |

**Nested Object: ActorDescriptor**

| Field | Type | Required | Description |
|---|---|---|---|
| `actor_id` | string | yes | Unique identifier for the actor. |
| `actor_type` | enum | yes | `human`, `ai_agent`, `service`, `system`. |
| `name` | string | yes | Human-readable actor name. |
| `trust_level` | enum | no (default: `internal`) | `public`, `internal`, `privileged`, `admin`. |
| `scopes` | array[string] | no | Permission scopes held by this actor. |

**Nested Object: TargetDescriptor**

| Field | Type | Required | Description |
|---|---|---|---|
| `target_type` | enum | yes | `capability`, `agent`, `service`, `registry`, `broadcast`. |
| `target_id` | string | no | Specific target identifier. |
| `namespace` | string | no | Optional namespace or domain qualifier. |

**Nested Object: IntentPayload**

| Field | Type | Required | Description |
|---|---|---|---|
| `intent_name` | string | yes | Machine-readable intent name (e.g., `retrieve_document`). |
| `intent_domain` | string | yes | Functional domain (e.g., `knowledge_management`). |
| `operation_class` | enum | yes | `read`, `write`, `execute`, `analyze`, `retrieve`, `delegate`. |
| `natural_language_hint` | string | no | Annotation for logging only. Never executed. |
| `parameters` | object | no | Structured parameters for the intent. |

**Nested Object: Constraints**

| Field | Type | Required | Description |
|---|---|---|---|
| `time_budget_ms` | integer | no | Maximum allowed execution time in milliseconds. |
| `cost_budget` | number | no | Maximum allowed cost in abstract cost units. |
| `allowed_actions` | array[string] | no | Explicit list of permitted action types. |
| `forbidden_actions` | array[string] | no | Explicit list of forbidden action types. |
| `data_sensitivity` | enum | no (default: `internal`) | `public`, `internal`, `confidential`, `restricted`. |
| `determinism_required` | enum | no (default: `strict`) | `strict`, `bounded`, `advisory`. |
| `priority` | enum | no (default: `normal`) | `low`, `normal`, `high`, `critical`. |

**Nested Object: TrustBlock**

| Field | Type | Required | Description |
|---|---|---|---|
| `declared_trust_level` | enum | no (default: `internal`) | Declared trust level of this envelope. |
| `delegation_chain` | array[string] | no | Ordered list of actor IDs in the delegation chain. |
| `token_reference` | string | no | Reference to an external auth token (not the token itself). |

**Message Type Enumeration**

| Value | Description |
|---|---|
| `intent_request` | A semantic intent submitted for processing. |
| `intent_response` | Response to an intent request. |
| `capability_query` | Query for available capabilities. |
| `capability_response` | Response to a capability query. |
| `negotiation_result` | Result of capability negotiation. |
| `execution_plan` | A produced execution plan. |
| `audit_record` | An audit log entry. |

**Example IntentEnvelope**

```json
{
  "sip_version": "0.1",
  "message_type": "intent_request",
  "intent_id": "3f7a2c1e-84b5-4d6a-9f0e-2c1d8e7f3a5b",
  "trace_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "span_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
  "timestamp": "2025-06-01T14:32:00.000Z",
  "actor": {
    "actor_id": "svc-knowledge-agent-01",
    "actor_type": "ai_agent",
    "name": "Knowledge Retrieval Agent",
    "trust_level": "internal",
    "scopes": ["sip:knowledge:read"]
  },
  "target": {
    "target_type": "capability",
    "target_id": null,
    "namespace": "knowledge_management"
  },
  "intent": {
    "intent_name": "retrieve_document",
    "intent_domain": "knowledge_management",
    "operation_class": "retrieve",
    "natural_language_hint": "Find the architecture overview document",
    "parameters": {
      "query": "architecture overview",
      "output_format": "json",
      "max_results": 5
    }
  },
  "desired_outcome": {
    "summary": "Retrieve the architecture overview document from the knowledge base",
    "output_format": "json",
    "success_criteria": ["document returned", "metadata included"]
  },
  "constraints": {
    "time_budget_ms": 5000,
    "cost_budget": null,
    "allowed_actions": [],
    "forbidden_actions": [],
    "data_sensitivity": "internal",
    "determinism_required": "strict",
    "priority": "normal"
  },
  "context": {
    "session_id": "sess-20250601-0042",
    "user_locale": "en-US",
    "environment": "production",
    "additional": {}
  },
  "capability_requirements": [],
  "trust": {
    "declared_trust_level": "internal",
    "delegation_chain": [],
    "token_reference": null
  },
  "protocol_bindings": [
    {
      "binding_type": "rag",
      "endpoint": null,
      "metadata": {}
    },
    {
      "binding_type": "rest",
      "endpoint": null,
      "metadata": {}
    }
  ],
  "negotiation": {
    "candidate_capabilities": [],
    "allow_fallback": true,
    "max_candidates": 5
  },
  "integrity": {
    "schema_version": "0.1",
    "signed": false,
    "signature_reference": null
  }
}
```

---

### 4.2 CapabilityDescriptor

A `CapabilityDescriptor` fully describes a capability that can be registered, discovered, and invoked through SIP. Providers register descriptors with the capability registry.

**Field Reference**

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `capability_id` | string | yes | — | Unique capability identifier (e.g., `retrieve_document`). |
| `name` | string | yes | — | Human-readable capability name. |
| `description` | string | yes | — | What this capability does. |
| `provider` | ProviderMetadata | yes | — | Provider identification and contact. |
| `intent_domains` | array[string] | yes | — | Functional domains this capability serves. |
| `input_schema` | SchemaReference | yes | — | Shape or reference for the input schema. |
| `output_schema` | SchemaReference | yes | — | Shape or reference for the output schema. |
| `operation_class` | enum | yes | — | Operation class this capability implements. |
| `risk_level` | enum | no | `low` | `low`, `medium`, `high`, `critical`. |
| `required_scopes` | array[string] | no | `[]` | Permission scopes required to invoke. |
| `minimum_trust_tier` | enum | no | `internal` | Minimum actor trust level. |
| `supported_bindings` | array[enum] | yes | — | Supported execution bindings. |
| `execution` | ExecutionMetadata | no | defaults | Execution characteristics. |
| `constraints` | CapabilityConstraints | no | defaults | Operational constraints. |
| `examples` | array[CapabilityExample] | no | `[]` | Example invocations. |
| `tags` | array[string] | no | `[]` | Searchable tags. |

**Nested Object: ProviderMetadata**

| Field | Type | Required | Description |
|---|---|---|---|
| `provider_id` | string | yes | Unique provider identifier. |
| `provider_name` | string | yes | Human-readable provider name. |
| `contact` | string | no | Contact email or URL. |
| `version` | string | no (default: `1.0.0`) | Provider's capability version. |
| `documentation_url` | string | no | URL to capability documentation. |

**Nested Object: SchemaReference**

| Field | Type | Required | Description |
|---|---|---|---|
| `schema_id` | string | no | External schema identifier (e.g., JSON Schema `$id`). |
| `description` | string | no | Human-readable description of the schema. |
| `properties` | object | no | Simplified property-name → type description map. |
| `required_fields` | array[string] | no | List of required field names. |

**Nested Object: ExecutionMetadata**

| Field | Type | Required | Description |
|---|---|---|---|
| `average_latency_ms` | integer | no | Expected average execution latency in milliseconds. |
| `idempotent` | boolean | no (default: `true`) | Whether the capability is idempotent. |
| `supports_dry_run` | boolean | no (default: `false`) | Whether dry-run mode is supported. |
| `max_retries` | integer | no (default: `3`) | Recommended maximum retry count. |

**Nested Object: CapabilityConstraints**

| Field | Type | Required | Description |
|---|---|---|---|
| `rate_limit_per_minute` | integer | no | Maximum invocations per minute. |
| `requires_human_approval` | boolean | no (default: `false`) | Whether human approval is always required. |
| `allowed_environments` | array[string] | no | Allowed deployment environments. |

**Example CapabilityDescriptor**

```json
{
  "capability_id": "retrieve_document",
  "name": "Retrieve Document",
  "description": "Retrieves a document from the knowledge base by query or identifier.",
  "provider": {
    "provider_id": "knowledge-service",
    "provider_name": "Enterprise Knowledge Service",
    "contact": "platform-team@example.com",
    "version": "1.2.0",
    "documentation_url": "https://docs.example.com/capabilities/retrieve-document"
  },
  "intent_domains": ["knowledge_management"],
  "input_schema": {
    "schema_id": "urn:sip:schema:retrieve-document-input:0.1",
    "description": "Input parameters for document retrieval",
    "properties": {
      "query": "string",
      "output_format": "string",
      "max_results": "integer",
      "collection": "string"
    },
    "required_fields": ["query"]
  },
  "output_schema": {
    "schema_id": "urn:sip:schema:retrieve-document-output:0.1",
    "description": "Retrieved document list with metadata",
    "properties": {
      "documents": "array",
      "total": "integer",
      "metadata": "object"
    },
    "required_fields": []
  },
  "operation_class": "retrieve",
  "risk_level": "low",
  "required_scopes": ["sip:knowledge:read"],
  "minimum_trust_tier": "internal",
  "supported_bindings": ["rag", "rest"],
  "execution": {
    "average_latency_ms": 120,
    "idempotent": true,
    "supports_dry_run": false,
    "max_retries": 3
  },
  "constraints": {
    "rate_limit_per_minute": 300,
    "requires_human_approval": false,
    "allowed_environments": ["production", "staging"]
  },
  "examples": [
    {
      "name": "Basic query",
      "description": "Retrieve documents matching a free-text query.",
      "parameters": {
        "query": "architecture overview",
        "max_results": 5
      },
      "expected_output_summary": "List of up to 5 matching documents with metadata."
    }
  ],
  "tags": ["knowledge", "retrieval", "documents", "rag"]
}
```

---

### 4.3 NegotiationResult

A `NegotiationResult` is the output of the SIP negotiation engine. It contains the ranked candidate capabilities, the selected capability and binding, and the policy decision.

**Field Reference**

| Field | Type | Description |
|---|---|---|
| `intent_id` | string | ID of the originating `IntentEnvelope`. |
| `ranked_candidates` | array[RankedCandidate] | All evaluated candidates, sorted by score descending. |
| `selected_capability` | CapabilityDescriptor or null | The capability selected for execution, if any. |
| `selection_rationale` | string | Explanation of why the selected capability was chosen. |
| `requires_clarification` | boolean | Whether clarification from the actor is needed. |
| `clarification_questions` | array[string] | Questions to ask the actor when clarification is required. |
| `allowed_bindings` | array[enum] | Compatible and policy-allowed bindings for the selected capability. |
| `selected_binding` | enum or null | The binding selected for execution. |
| `policy_decision` | PolicyDecisionSummary | Summary of policy evaluation. |

**Nested Object: RankedCandidate**

| Field | Type | Description |
|---|---|---|
| `capability` | CapabilityDescriptor | The candidate capability. |
| `score` | number | Matching score (higher is better). |
| `rationale` | string | Human-readable explanation of the ranking. |

**Nested Object: PolicyDecisionSummary**

| Field | Type | Description |
|---|---|---|
| `allowed` | boolean | Whether policy permits this negotiation to proceed. |
| `requires_approval` | boolean | Whether human approval is required before execution. |
| `denied_scopes` | array[string] | Scopes that were required but not held by the actor. |
| `policy_notes` | array[string] | Human-readable notes from each policy rule evaluation. |

**Example NegotiationResult**

```json
{
  "intent_id": "3f7a2c1e-84b5-4d6a-9f0e-2c1d8e7f3a5b",
  "ranked_candidates": [
    {
      "capability": { "capability_id": "retrieve_document", "..." : "..." },
      "score": 7.5,
      "rationale": "exact intent name match; domain match; operation class match; supports preferred binding 'rag'; score=7.5"
    },
    {
      "capability": { "capability_id": "search_knowledge_base", "...": "..." },
      "score": 5.5,
      "rationale": "domain match; operation class match; supports preferred binding 'rag'; score=5.5"
    }
  ],
  "selected_capability": {
    "capability_id": "retrieve_document",
    "name": "Retrieve Document",
    "..." : "..."
  },
  "selection_rationale": "exact intent name match; domain match; operation class match; supports preferred binding 'rag'; score=7.5",
  "requires_clarification": false,
  "clarification_questions": [],
  "allowed_bindings": ["rag", "rest"],
  "selected_binding": "rag",
  "policy_decision": {
    "allowed": true,
    "requires_approval": false,
    "denied_scopes": [],
    "policy_notes": [
      "PASS: All required scopes granted: ['sip:knowledge:read'].",
      "PASS: risk_level='low' + operation='retrieve' does not require approval.",
      "PASS: data_sensitivity='internal' is compatible with risk_level='low'.",
      "PASS: Delegation chain depth 0 is within limits."
    ]
  }
}
```

---

### 4.4 ExecutionPlan

An `ExecutionPlan` is the deterministic execution plan produced by the SIP planner after negotiation and policy evaluation. It is ready to be passed to a binding translator adapter.

**Field Reference**

| Field | Type | Description |
|---|---|---|
| `plan_id` | string (UUID) | Unique plan identifier, auto-generated. |
| `intent_id` | string | ID of the originating `IntentEnvelope`. |
| `selected_capability` | CapabilityDescriptor | The capability selected for execution. |
| `selected_binding` | enum | The binding selected for execution. |
| `deterministic_target` | object | Binding-specific deterministic target information. |
| `grounded_parameters` | object | Fully resolved parameters for execution. |
| `execution_steps` | array[ExecutionStep] | Ordered list of execution steps. |
| `policy_checks_passed` | array[PolicyCheckRecord] | Policy checks that were passed. |
| `approval_required` | boolean | Whether human approval is required before execution. |
| `trace` | TraceMetadata | Trace metadata for distributed correlation. |

**Nested Object: ExecutionStep**

| Field | Type | Description |
|---|---|---|
| `step_index` | integer | Zero-based step index. |
| `step_name` | string | Short descriptive name (e.g., `invoke_retrieve_document`). |
| `description` | string | What this step does. |
| `capability_id` | string | Capability invoked in this step. |
| `binding` | enum | Binding used for this step. |
| `parameters` | object | Grounded parameters for this step. |
| `depends_on` | array[integer] | Step indices this step depends on. |

**Nested Object: PolicyCheckRecord**

| Field | Type | Description |
|---|---|---|
| `check_name` | string | Name of the policy check (e.g., `trust_level`). |
| `result` | string | Result of the check (`passed`, `failed`). |
| `notes` | string | Human-readable notes. |

**Nested Object: TraceMetadata**

| Field | Type | Description |
|---|---|---|
| `trace_id` | string | Distributed trace identifier (from `IntentEnvelope`). |
| `span_id` | string | Current span identifier. |
| `parent_span_id` | string or null | Parent span identifier, if any. |
| `intent_id` | string | ID of the originating intent. |

**Nested Object: deterministic_target**

The `deterministic_target` object provides the binding-specific target information. Its structure is standardized as follows:

| Field | Type | Description |
|---|---|---|
| `capability_id` | string | Capability to be invoked. |
| `provider_id` | string | Provider of the capability. |
| `binding_type` | string | Binding type (e.g., `rag`, `rest`). |
| `endpoint` | string | Target endpoint URI, or a `<ENDPOINT:provider/capability>` placeholder if not yet resolved. |

**Example ExecutionPlan**

```json
{
  "plan_id": "9e2f1a7b-3c4d-5e6f-7a8b-9c0d1e2f3a4b",
  "intent_id": "3f7a2c1e-84b5-4d6a-9f0e-2c1d8e7f3a5b",
  "selected_capability": {
    "capability_id": "retrieve_document",
    "name": "Retrieve Document",
    "...": "..."
  },
  "selected_binding": "rag",
  "deterministic_target": {
    "capability_id": "retrieve_document",
    "provider_id": "knowledge-service",
    "binding_type": "rag",
    "endpoint": "<ENDPOINT:knowledge-service/retrieve_document>"
  },
  "grounded_parameters": {
    "query": "architecture overview",
    "output_format": "json",
    "max_results": 5
  },
  "execution_steps": [
    {
      "step_index": 0,
      "step_name": "invoke_retrieve_document",
      "description": "Invoke 'Retrieve Document' via rag binding for intent 'retrieve_document'.",
      "capability_id": "retrieve_document",
      "binding": "rag",
      "parameters": {
        "query": "architecture overview",
        "output_format": "json",
        "max_results": 5
      },
      "depends_on": []
    }
  ],
  "policy_checks_passed": [
    {
      "check_name": "trust_level",
      "result": "passed",
      "notes": "Actor trust 'internal' meets capability minimum 'internal'."
    },
    {
      "check_name": "operation_class_match",
      "result": "passed",
      "notes": "Intent operation class 'retrieve' matches capability 'retrieve'."
    }
  ],
  "approval_required": false,
  "trace": {
    "trace_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "span_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
    "parent_span_id": null,
    "intent_id": "3f7a2c1e-84b5-4d6a-9f0e-2c1d8e7f3a5b"
  }
}
```

---

### 4.5 AuditRecord

An `AuditRecord` is an immutable log entry generated for every `IntentEnvelope` processed by the SIP broker, regardless of outcome. Audit records must be written to an append-only log in production deployments.

**Field Reference**

| Field | Type | Description |
|---|---|---|
| `audit_id` | string (UUID) | Unique audit record identifier, auto-generated. |
| `timestamp` | string (ISO 8601) | When this record was created (UTC). |
| `trace_id` | string | Distributed trace identifier. |
| `intent_id` | string | ID of the processed intent. |
| `actor_id` | string | ID of the originating actor. |
| `actor_type` | string | Type of the originating actor. |
| `intent_name` | string | Machine-readable intent name. |
| `intent_domain` | string | Functional domain of the intent. |
| `operation_class` | string | Operation class. |
| `selected_capability_id` | string or null | ID of the capability selected, if any. |
| `selected_binding` | string or null | Binding selected for execution, if any. |
| `action_taken` | enum | Action taken: `plan_created`, `plan_rejected`, `approval_requested`, `clarification_requested`, `policy_denied`, `validation_failed`. |
| `policy_allowed` | boolean | Whether policy permitted the action. |
| `approval_state` | string | One of: `not_required`, `pending`, `approved`, `denied`. |
| `outcome_summary` | enum | `success`, `pending_approval`, `needs_clarification`, `denied`, `error`. |
| `notes` | string | Additional notes or error messages. |

**Example AuditRecord**

```json
{
  "audit_id": "c4d5e6f7-a8b9-0c1d-2e3f-4a5b6c7d8e9f",
  "timestamp": "2025-06-01T14:32:01.421Z",
  "trace_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "intent_id": "3f7a2c1e-84b5-4d6a-9f0e-2c1d8e7f3a5b",
  "actor_id": "svc-knowledge-agent-01",
  "actor_type": "ai_agent",
  "intent_name": "retrieve_document",
  "intent_domain": "knowledge_management",
  "operation_class": "retrieve",
  "selected_capability_id": "retrieve_document",
  "selected_binding": "rag",
  "action_taken": "plan_created",
  "policy_allowed": true,
  "approval_state": "not_required",
  "outcome_summary": "success",
  "notes": ""
}
```

---

## 5. Capability Discovery

### 5.1 Overview

Capability discovery is the process by which the SIP broker queries the capability registry to find capabilities that can satisfy a given `IntentEnvelope`. Discovery is always deterministic: the same intent and registry state must produce the same ranked result.

### 5.2 Matching Criteria

Capabilities are scored against an intent using the following additive scoring rules:

| Criterion | Condition | Score |
|---|---|---|
| **Intent name — exact** | `intent_name` equals `capability_id` (case-insensitive) | +3.0 |
| **Intent name — partial** | `intent_name` appears in `capability_id` or `name` | +2.0 |
| **Domain — exact** | `intent_domain` appears in capability's `intent_domains` (exact, case-insensitive) | +2.0 |
| **Domain — partial** | `intent_domain` is a substring of any domain in `intent_domains`; only applies if exact match did not score | +1.0 |
| **Operation class** | `operation_class` matches capability's `operation_class` | +2.0 |
| **Preferred binding** | The actor's first preferred binding is in `supported_bindings` | +1.5 |
| **Candidate hint** | The capability ID is in the actor's `candidate_capabilities` list | +0.5 |
| **Trust exclusion** | Actor trust level is below `minimum_trust_tier` | Excluded |

Total scores are floating-point. Capabilities are sorted by score descending. The top `max_candidates` are returned.

### 5.3 Candidate Selection Logic

After scoring, the negotiation engine applies the following selection logic:

1. **No candidates**: `requires_clarification = true`. A clarification question is generated.
2. **Exactly one candidate**: Selected automatically.
3. **Multiple candidates — clear winner**: If the score gap between first and second is ≥ 1.0, the first is selected.
4. **Multiple candidates — ambiguous, fallback allowed**: If the gap is < 1.0 but `allow_fallback = true`, the top candidate is selected with a note about the ambiguity.
5. **Multiple candidates — ambiguous, no fallback**: `requires_clarification = true`. Candidate IDs are listed in the clarification question.

### 5.4 Binding Selection

After a capability is selected, the preferred binding is determined as follows:

1. Use the first `protocol_bindings` entry from the envelope whose `binding_type` is in the capability's `supported_bindings`.
2. If no match, use the first `capability_requirements` entry with a `preferred_binding` that is in `supported_bindings`.
3. If still no match, use the first element of the capability's `supported_bindings`.

### 5.5 Determinism Guarantee

Capability matching MUST be deterministic. The same `IntentEnvelope` and capability registry state MUST always produce the same `NegotiationResult`. Implementations MUST NOT use probabilistic or ML-based scoring in the capability matching pipeline.

---

## 6. Policy and Trust Model

### 6.1 Overview

The SIP policy engine evaluates every intent against a set of policy rules before an `ExecutionPlan` is produced. Policy evaluation is deterministic, rule-based, and occurs after capability selection but before execution planning.

### 6.2 Policy Outcomes

Every policy evaluation produces one of three outcomes:

| Outcome | Description |
|---|---|
| `allow` | The intent is permitted to proceed to execution. |
| `deny` | The intent is rejected. No execution plan is produced. |
| `require_approval` | The intent is permitted but requires human approval before the execution plan is acted upon. |

### 6.3 Policy Rules

Policy rules are evaluated in order. A `deny` at any step stops further evaluation.

**Rule 1: Scope Validation**

The actor must hold all scopes listed in the capability's `required_scopes`. If any required scope is missing:

- `allowed = false`
- `denied_scopes` is populated with the missing scope names.
- Processing stops.

**Rule 2: Risk Level and Operation Class**

If the capability's `risk_level` is `high` or `critical`, and the operation class is `write` or `execute`:

- `requires_approval = true`

This rule is subject to the `SIP_REQUIRE_APPROVAL_HIGH_RISK` configuration flag. When set to `false` (non-production environments), this rule does not apply.

**Rule 3: Risk Level and Data Sensitivity**

If the capability's `risk_level` is `critical` AND the envelope's `data_sensitivity` is `restricted`:

- `allowed = false`

**Rule 4: Delegation Chain Depth**

The `trust.delegation_chain` must not exceed 5 elements. If the chain depth is greater than 5:

- `allowed = false`

**Rule 5: Capability-Level Approval Override**

If the capability's `constraints.requires_human_approval` is `true`:

- `requires_approval = true` (regardless of other rules)

### 6.4 Trust Levels

Trust levels are ordered: `public` < `internal` < `privileged` < `admin`. Capabilities declare a `minimum_trust_tier`. Actors that do not meet the minimum trust tier are excluded from matching entirely (before scoring).

### 6.5 Scope Naming Convention

Scopes follow a colon-separated naming convention:

```
sip:<domain>:<operation>
```

Examples:
- `sip:knowledge:read` — read access to knowledge domain capabilities
- `sip:booking:write` — write access to booking domain capabilities
- `sip:network:execute` — execution access to network operations
- `sip:agent:delegate` — permission to delegate to other agents

### 6.6 Policy Note Format

The policy engine records a human-readable note for each rule evaluation. Note prefixes:

- `PASS:` — Rule passed.
- `DENY:` — Rule resulted in denial.
- `APPROVAL REQUIRED:` — Rule triggered approval requirement.

These notes appear verbatim in `NegotiationResult.policy_decision.policy_notes` and in `AuditRecord.notes`.

---

## 7. Execution Bindings

### 7.1 Overview

Execution bindings translate an `ExecutionPlan` into a protocol-specific payload. Each binding is implemented as an adapter. The adapter does not execute the request; it produces a structured payload ready for transmission by the caller.

SIP v0.1 defines five binding types.

### 7.2 REST Binding

Translates an `ExecutionPlan` into an HTTP request specification.

**Payload fields:**

| Field | Type | Description |
|---|---|---|
| `method` | string | HTTP method (`GET`, `POST`, `PUT`, `PATCH`, `DELETE`). |
| `url` | string | Target URL, constructed from the endpoint and capability ID. |
| `headers` | object | HTTP headers, including `Content-Type` and `X-SIP-Trace-ID`. |
| `body` | object or null | Request body (for write operations). |
| `query_params` | object | Query string parameters (for read operations). |
| `trace` | object | Trace metadata block. |

Operation class to HTTP method mapping:

| Operation Class | HTTP Method |
|---|---|
| `read`, `retrieve`, `analyze` | `GET` |
| `write` | `POST` |
| `execute` | `POST` |
| `delegate` | `POST` |

### 7.3 gRPC Binding

Translates an `ExecutionPlan` into a gRPC call specification.

**Payload fields:**

| Field | Type | Description |
|---|---|---|
| `service_name` | string | gRPC service name (derived from provider and capability). |
| `method_name` | string | gRPC method name (derived from capability ID). |
| `request_message` | object | Protobuf-compatible request message. |
| `metadata` | object | gRPC metadata, including trace headers. |
| `trace` | object | Trace metadata block. |

### 7.4 MCP Binding

Translates an `ExecutionPlan` into a Model Context Protocol tool call.

**Payload fields:**

| Field | Type | Description |
|---|---|---|
| `tool_name` | string | MCP tool name (capability ID). |
| `tool_arguments` | object | Tool argument map. |
| `execution_contract` | object | Expected output schema and constraints. |
| `trace` | object | Trace metadata block. |

### 7.5 A2A Binding

Translates an `ExecutionPlan` into an agent-to-agent task delegation.

**Payload fields:**

| Field | Type | Description |
|---|---|---|
| `task_type` | string | Agent task type (capability ID). |
| `target_agent` | string | Target agent identifier (provider ID). |
| `task_payload` | object | Task parameters. |
| `delegation_context` | object | Delegation chain and trust context. |
| `trace` | object | Trace metadata block. |

### 7.6 RAG Binding

Translates an `ExecutionPlan` into a retrieval query specification.

**Payload fields:**

| Field | Type | Description |
|---|---|---|
| `collection` | string | Data source or collection name. |
| `retrieval_query` | string | Structured retrieval query string. |
| `filters` | object | Key-value filters to apply. |
| `result_contract` | object | Expected result format and constraints. |
| `trace` | object | Trace metadata block. |

**Retrieval query derivation:** The query string is constructed from parameters in this order of precedence: `query` parameter → `text` parameter → `topic` parameter → concatenation of all string-valued parameters.

**Collection derivation:** Derived from the `collection` or `source` parameter, or defaults to `<capability_id_with_hyphens>-store`.

**Example RAG translated payload:**

```json
{
  "collection": "retrieve-document-store",
  "retrieval_query": "architecture overview",
  "filters": {
    "max_results": 5
  },
  "result_contract": {
    "output_format": "json",
    "max_results": 5,
    "include_metadata": true,
    "output_schema": "Retrieved document list with metadata"
  },
  "trace": {
    "trace_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "span_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
    "intent_id": "3f7a2c1e-84b5-4d6a-9f0e-2c1d8e7f3a5b"
  }
}
```

### 7.7 Binding Adapter Interface

All binding adapters implement a common interface:

```
translate(plan: ExecutionPlan) → TranslationResult
```

`TranslationResult` contains:

| Field | Type | Description |
|---|---|---|
| `binding_type` | enum | The binding type produced. |
| `payload` | object | The binding-specific payload. |
| `metadata` | object | Adapter metadata (capability ID, provider ID, etc.). |

Adapters MUST validate that the `ExecutionPlan`'s `selected_binding` matches their own `binding_type` before translation.

---

## 8. Observability and Auditability

### 8.1 Trace Identifiers

Every `IntentEnvelope` carries two trace identifiers:

- **`trace_id`**: A distributed trace identifier that propagates through the entire pipeline and into all downstream records. Enables correlation across the intent, negotiation result, execution plan, translated payload, and audit record.
- **`span_id`**: Identifies the current span within the trace. Enables hierarchical trace trees when a single trace involves multiple intents (e.g., A2A delegation).

Trace identifiers are UUIDs generated by the actor at envelope creation time. In multi-agent workflows, the `trace_id` is shared across all intents in the same logical operation, while `span_id` values differ per intent.

### 8.2 Audit Record Generation

The broker generates an `AuditRecord` for every processed intent, regardless of outcome. Records are generated as follows:

| Pipeline Outcome | `action_taken` | `outcome_summary` |
|---|---|---|
| Execution plan created successfully | `plan_created` | `success` |
| Policy denied | `policy_denied` | `denied` |
| Approval required | `approval_requested` | `pending_approval` |
| No capability matched | `clarification_requested` | `needs_clarification` |
| Envelope validation failed | `validation_failed` | `error` |

### 8.3 Audit Log Requirements

In production deployments, audit logs MUST be:

- **Append-only**: Records must not be modified or deleted.
- **Complete**: Every broker invocation must produce exactly one `AuditRecord`.
- **Correlated**: Each record must contain `trace_id` and `intent_id`.
- **Immutable**: The `AuditRecord` schema uses a frozen model; no field mutation is permitted after creation.

### 8.4 Structured Logging

In addition to `AuditRecord` persistence, the SIP broker emits structured log events at each pipeline stage. Log entries carry `trace_id` and `intent_id` fields to enable log aggregation and pipeline tracing.

---

## 9. Determinism Requirements

SIP v0.1 imposes strict determinism requirements on the protocol pipeline. These requirements exist to ensure that execution is predictable, reproducible, and safe for audit.

### 9.1 No Direct Natural Language Execution

Natural language input MUST NOT be executed directly. The `natural_language_hint` field in `IntentPayload` is an annotation field for logging and auditing purposes only. It MUST NOT be passed to an execution system as a directive.

### 9.2 Deterministic Capability Matching

Capability matching MUST be deterministic. Given the same `IntentEnvelope` and the same capability registry state:

- The ranked candidate list MUST be identical.
- The selected capability MUST be identical.
- The selected binding MUST be identical.

Scoring MUST be computed using the defined additive scoring rules only. No probabilistic, ML-based, or heuristic scoring is permitted.

### 9.3 Reproducible Execution Plans

Given the same `NegotiationResult` and the same `IntentEnvelope`, the `ExecutionPlan` produced by the planner MUST be identical (excepting the auto-generated `plan_id`). Grounded parameters, execution steps, and deterministic target information MUST all be derivable from the inputs without randomness.

### 9.4 Policy Before Execution

Policy MUST be evaluated before an `ExecutionPlan` is produced. An execution plan MUST NOT be produced for an intent whose policy decision is `deny`. An execution plan MAY be produced for an intent whose policy decision is `require_approval`, but the `approval_required` field MUST be set to `true`.

### 9.5 Schema-Grounded Parameters

Parameters in an `ExecutionPlan` MUST be grounded against the capability's input schema. Required fields absent from the envelope MUST be marked with `<REQUIRED:field_name>` placeholders rather than being silently omitted or inferred.

---

## 10. Versioning

### 10.1 Protocol Version Field

Every `IntentEnvelope` carries a `sip_version` field. In SIP v0.1, the value of this field MUST be `"0.1"`.

```json
{
  "sip_version": "0.1",
  ...
}
```

### 10.2 Version Semantics

SIP protocol versions follow a `<major>.<minor>` numbering scheme.

| Change Type | Version Behavior |
|---|---|
| New optional field added to an existing object | Minor increment (e.g., `0.1` → `0.2`) |
| Existing field semantics changed | Major increment (e.g., `0.1` → `1.0`) |
| Field removed | Major increment |
| New required field added to an existing object | Major increment |
| New object type added (additive) | Minor increment |

### 10.3 Incompatibility Handling

A SIP broker MUST reject envelopes whose `sip_version` it does not support. When rejecting for version incompatibility, the broker MUST:

- Set `action_taken = validation_failed` in the `AuditRecord`.
- Set `outcome_summary = error`.
- Include a descriptive message in `notes` identifying the version mismatch.

### 10.4 CapabilityDescriptor Schema Versioning

`CapabilityDescriptor` objects carry a version field in their `ProviderMetadata` (`provider.version`). This version identifies the provider's capability implementation version and is independent of the SIP protocol version.

The `IntegrityBlock` embedded in `IntentEnvelope` also carries a `schema_version` field (default `"0.1"`), which identifies the version of the SIP envelope schema used to construct the object.

---

## 11. Example End-to-End Flow

This section provides a complete walkthrough of SIP processing for an enterprise knowledge retrieval intent.

### 11.1 Scenario

**Actor:** An AI agent (`ai_agent`) with `internal` trust and scope `sip:knowledge:read` requests the retrieval of an architecture overview document from an enterprise knowledge base.

**Target:** A capability-type target in the `knowledge_management` domain.

**Desired Outcome:** Return up to 5 documents matching "architecture overview" in JSON format.

---

### 11.2 Step 1: IntentEnvelope

The actor constructs and submits the following `IntentEnvelope` to the SIP broker:

```json
{
  "sip_version": "0.1",
  "message_type": "intent_request",
  "intent_id": "3f7a2c1e-84b5-4d6a-9f0e-2c1d8e7f3a5b",
  "trace_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "span_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
  "timestamp": "2025-06-01T14:32:00.000Z",
  "actor": {
    "actor_id": "svc-knowledge-agent-01",
    "actor_type": "ai_agent",
    "name": "Knowledge Retrieval Agent",
    "trust_level": "internal",
    "scopes": ["sip:knowledge:read"]
  },
  "target": {
    "target_type": "capability",
    "target_id": null,
    "namespace": "knowledge_management"
  },
  "intent": {
    "intent_name": "retrieve_document",
    "intent_domain": "knowledge_management",
    "operation_class": "retrieve",
    "natural_language_hint": "Find the architecture overview document",
    "parameters": {
      "query": "architecture overview",
      "output_format": "json",
      "max_results": 5
    }
  },
  "desired_outcome": {
    "summary": "Retrieve architecture overview documents from the knowledge base",
    "output_format": "json",
    "success_criteria": ["documents returned", "metadata included"]
  },
  "constraints": {
    "time_budget_ms": 5000,
    "data_sensitivity": "internal",
    "determinism_required": "strict",
    "priority": "normal"
  },
  "context": {
    "session_id": "sess-20250601-0042",
    "user_locale": "en-US",
    "environment": "production"
  },
  "trust": {
    "declared_trust_level": "internal",
    "delegation_chain": [],
    "token_reference": null
  },
  "protocol_bindings": [
    { "binding_type": "rag", "endpoint": null, "metadata": {} },
    { "binding_type": "rest", "endpoint": null, "metadata": {} }
  ],
  "negotiation": {
    "candidate_capabilities": [],
    "allow_fallback": true,
    "max_candidates": 5
  },
  "integrity": {
    "schema_version": "0.1",
    "signed": false
  }
}
```

---

### 11.3 Step 2: Capability Discovery and NegotiationResult

The broker validates the envelope, queries the capability registry, and produces the following `NegotiationResult`:

**Scoring:**

| Capability | Intent Name | Domain | Op Class | Binding | Score |
|---|---|---|---|---|---|
| `retrieve_document` | exact (+3.0) | exact (+2.0) | exact (+2.0) | rag (+1.5) | **8.5** |
| `search_knowledge_base` | no match (+0.0) | exact (+2.0) | exact (+2.0) | rag (+1.5) | **5.5** |

Score gap: 8.5 − 5.5 = 3.0 ≥ 1.0 → clear winner selected.

```json
{
  "intent_id": "3f7a2c1e-84b5-4d6a-9f0e-2c1d8e7f3a5b",
  "ranked_candidates": [
    {
      "capability": { "capability_id": "retrieve_document", "name": "Retrieve Document" },
      "score": 8.5,
      "rationale": "exact intent name match; domain match; operation class match; supports preferred binding 'rag'; score=8.5"
    },
    {
      "capability": { "capability_id": "search_knowledge_base", "name": "Search Knowledge Base" },
      "score": 5.5,
      "rationale": "domain match; operation class match; supports preferred binding 'rag'; score=5.5"
    }
  ],
  "selected_capability": { "capability_id": "retrieve_document", "name": "Retrieve Document" },
  "selection_rationale": "exact intent name match; domain match; operation class match; supports preferred binding 'rag'; score=8.5",
  "requires_clarification": false,
  "clarification_questions": [],
  "allowed_bindings": ["rag", "rest"],
  "selected_binding": "rag",
  "policy_decision": {
    "allowed": true,
    "requires_approval": false,
    "denied_scopes": [],
    "policy_notes": [
      "PASS: All required scopes granted: ['sip:knowledge:read'].",
      "PASS: risk_level='low' + operation='retrieve' does not require approval.",
      "PASS: data_sensitivity='internal' is compatible with risk_level='low'.",
      "PASS: Delegation chain depth 0 is within limits."
    ]
  }
}
```

---

### 11.4 Step 3: ExecutionPlan

The planner produces the following `ExecutionPlan`:

```json
{
  "plan_id": "9e2f1a7b-3c4d-5e6f-7a8b-9c0d1e2f3a4b",
  "intent_id": "3f7a2c1e-84b5-4d6a-9f0e-2c1d8e7f3a5b",
  "selected_capability": {
    "capability_id": "retrieve_document",
    "name": "Retrieve Document",
    "provider": {
      "provider_id": "knowledge-service",
      "provider_name": "Enterprise Knowledge Service"
    },
    "operation_class": "retrieve",
    "risk_level": "low",
    "required_scopes": ["sip:knowledge:read"],
    "supported_bindings": ["rag", "rest"]
  },
  "selected_binding": "rag",
  "deterministic_target": {
    "capability_id": "retrieve_document",
    "provider_id": "knowledge-service",
    "binding_type": "rag",
    "endpoint": "<ENDPOINT:knowledge-service/retrieve_document>"
  },
  "grounded_parameters": {
    "query": "architecture overview",
    "output_format": "json",
    "max_results": 5
  },
  "execution_steps": [
    {
      "step_index": 0,
      "step_name": "invoke_retrieve_document",
      "description": "Invoke 'Retrieve Document' via rag binding for intent 'retrieve_document'.",
      "capability_id": "retrieve_document",
      "binding": "rag",
      "parameters": {
        "query": "architecture overview",
        "output_format": "json",
        "max_results": 5
      },
      "depends_on": []
    }
  ],
  "policy_checks_passed": [
    {
      "check_name": "trust_level",
      "result": "passed",
      "notes": "Actor trust 'internal' meets capability minimum 'internal'."
    },
    {
      "check_name": "operation_class_match",
      "result": "passed",
      "notes": "Intent operation class 'retrieve' matches capability 'retrieve'."
    }
  ],
  "approval_required": false,
  "trace": {
    "trace_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "span_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
    "parent_span_id": null,
    "intent_id": "3f7a2c1e-84b5-4d6a-9f0e-2c1d8e7f3a5b"
  }
}
```

---

### 11.5 Step 4: Translated RAG Binding Payload

The RAG adapter translates the `ExecutionPlan` into a retrieval specification:

```json
{
  "collection": "retrieve-document-store",
  "retrieval_query": "architecture overview",
  "filters": {
    "max_results": 5
  },
  "result_contract": {
    "output_format": "json",
    "max_results": 5,
    "include_metadata": true,
    "output_schema": "Retrieved document list with metadata"
  },
  "trace": {
    "trace_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "span_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
    "intent_id": "3f7a2c1e-84b5-4d6a-9f0e-2c1d8e7f3a5b"
  }
}
```

This payload is ready to be submitted to a retrieval index (e.g., a vector store, a document search service, or a RAG pipeline).

---

### 11.6 Step 5: AuditRecord

The broker writes the following `AuditRecord` to the audit log:

```json
{
  "audit_id": "c4d5e6f7-a8b9-0c1d-2e3f-4a5b6c7d8e9f",
  "timestamp": "2025-06-01T14:32:01.421Z",
  "trace_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "intent_id": "3f7a2c1e-84b5-4d6a-9f0e-2c1d8e7f3a5b",
  "actor_id": "svc-knowledge-agent-01",
  "actor_type": "ai_agent",
  "intent_name": "retrieve_document",
  "intent_domain": "knowledge_management",
  "operation_class": "retrieve",
  "selected_capability_id": "retrieve_document",
  "selected_binding": "rag",
  "action_taken": "plan_created",
  "policy_allowed": true,
  "approval_state": "not_required",
  "outcome_summary": "success",
  "notes": ""
}
```

---

### 11.7 Summary

The complete flow demonstrates:

1. The actor expresses a semantic intent without coupling to a specific service endpoint or schema.
2. SIP discovers and ranks capabilities deterministically from the registry.
3. Policy is evaluated before any execution plan is produced.
4. A grounded, deterministic execution plan is produced with a traceable plan ID.
5. The abstract plan is translated to a concrete RAG retrieval payload.
6. An immutable audit record is written capturing the actor, intent, capability, policy outcome, and final disposition.

The entire pipeline — from `IntentEnvelope` submission to `AuditRecord` creation — executes without any natural-language processing, ML inference, or probabilistic decision-making.

---

*End of SIP Wire-Level Specification v0.1*
