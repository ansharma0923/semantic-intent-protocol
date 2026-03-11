# Semantic Intent Protocol (SIP) — Core Protocol Specification v0.1

This document is the normative protocol specification for SIP v0.1. All protocol semantics, message structures, validation rules, and processing requirements are defined here.

**Status**: Working Draft  
**Version**: 0.1  
**Date**: 2026

---

## 1. Overview

### 1.1 Purpose

SIP (Semantic Intent Protocol) is a semantic interoperability protocol for AI agents and software
systems. It standardises how systems express semantic intent, negotiate capabilities, apply trust
and policy controls, and translate requests into deterministic execution through existing protocols
such as REST, gRPC, MCP, A2A, and retrieval systems.

### 1.2 Scope

This document specifies the SIP v0.1 protocol objects, message types, validation rules, and
processing semantics. It covers the `IntentEnvelope`, `CapabilityDescriptor`, negotiation
algorithm, policy evaluation, execution planning, and audit logging.

### 1.3 Core Principles

1. **Intent ≠ Execution** – The intent layer is always separate from the execution layer.
2. **Determinism is non-negotiable** – Every execution plan must be fully specified and reproducible.
3. **Trust is explicit** – Every intent carries a trust level, scopes, and delegation chain.
4. **Policy is always evaluated** – No execution proceeds without a policy decision.
5. **Auditability is built in** – Every processed intent produces an audit record.

### 1.4 Architectural Model

```
Actor → IntentEnvelope → SIP Broker → ExecutionPlan → Deterministic Execution
```

The SIP broker accepts an `IntentEnvelope`, discovers matching capabilities, evaluates policy,
produces an `ExecutionPlan`, and generates an `AuditRecord`. The execution plan is handed to the
appropriate execution binding adapter.

### 1.5 Relationship to Existing Protocols

SIP does not replace REST, gRPC, MCP, A2A, or any other execution protocol. SIP provides a
semantic negotiation and translation layer that sits above these protocols and delegates actual
execution to them.

### 1.6 Conformance

A system claiming SIP v0.1 compliance MUST satisfy the following requirements:

- It MUST accept and validate `IntentEnvelope` objects as defined in this specification.
- It MUST perform deterministic capability matching as defined in this specification.
- It MUST evaluate policy before producing an `ExecutionPlan`.
- It MUST produce an `AuditRecord` for every processed intent.
- It MUST support at least one execution binding.

### 1.7 Encoding

SIP protocol objects are defined using JSON-compatible schemas. JSON is the canonical encoding for
SIP v0.1 examples and interoperability. Implementations MAY use other encodings (such as
MessagePack or Protocol Buffers) internally, but the specification examples and interchange format
are canonicalized in JSON.

---

## 2. Broker Responsibilities

A SIP broker is the central processing component responsible for:

- Validating `IntentEnvelope` objects upon receipt.
- Discovering capabilities from the registered capability set.
- Performing deterministic negotiation to select the appropriate capability.
- Invoking policy evaluation before any execution plan is produced.
- Producing an `ExecutionPlan` that is fully specified and reproducible.
- Generating an `AuditRecord` for every processed intent.

---

## 3. Message Types

SIP defines the following message types (`MessageType` enum):

| Message Type | Description |
|---|---|
| `intent_request` | An actor submitting a semantic intent |
| `intent_response` | Response to an intent request |
| `capability_query` | Query for available capabilities |
| `capability_response` | Response to a capability query |
| `negotiation_result` | Result of capability negotiation |
| `execution_plan` | A deterministic execution plan |
| `audit_record` | An immutable audit log entry |

---

## 4. IntentEnvelope

The `IntentEnvelope` is the root protocol object for all SIP `intent_request` messages.

### 4.1 Required Fields

| Field | Type | Description |
|---|---|---|
| `sip_version` | string | SIP protocol version (currently `"0.1"`) |
| `message_type` | MessageType | Must be `intent_request` for intent submissions |
| `intent_id` | UUID string | Unique identifier for this intent |
| `trace_id` | UUID string | Distributed trace identifier |
| `span_id` | UUID string | Current span identifier |
| `timestamp` | ISO 8601 datetime | When the envelope was created (UTC) |
| `actor` | ActorDescriptor | The originating actor |
| `target` | TargetDescriptor | The intended target |
| `intent` | IntentPayload | The semantic intent |
| `desired_outcome` | DesiredOutcome | What the actor wants as a result |

### 4.2 Optional Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `constraints` | Constraints | defaults | Execution constraints |
| `context` | ContextBlock | defaults | Session and environment context |
| `capability_requirements` | list[CapabilityRequirement] | [] | Required capabilities |
| `trust` | TrustBlock | defaults | Trust and credential block |
| `protocol_bindings` | list[ProtocolBinding] | [] | Preferred execution bindings |
| `negotiation` | NegotiationHints | defaults | Negotiation hints |
| `integrity` | IntegrityBlock | defaults | Integrity metadata |
| `provenance` | ProvenanceBlock | null | Intent provenance chain (optional for backward compatibility) |

### 4.3 ActorDescriptor

| Field | Type | Description |
|---|---|---|
| `actor_id` | string | Unique actor identifier |
| `actor_type` | ActorType | `human`, `ai_agent`, `service`, `system` |
| `name` | string | Human-readable name |
| `trust_level` | TrustLevel | `public`, `internal`, `privileged`, `admin` |
| `scopes` | list[string] | Granted permission scopes |

### 4.4 IntentPayload

| Field | Type | Description |
|---|---|---|
| `intent_name` | string | Machine-readable intent name |
| `intent_domain` | string | Functional domain (e.g. `knowledge_management`) |
| `operation_class` | OperationClass | `read`, `write`, `execute`, `analyze`, `retrieve`, `delegate` |
| `natural_language_hint` | string? | Human-readable hint (audit only, never executed) |
| `parameters` | dict | Structured intent parameters |

### 4.5 Constraints

| Field | Type | Default | Description |
|---|---|---|---|
| `time_budget_ms` | int? | null | Max execution time (ms); must be ≥ 0 |
| `cost_budget` | float? | null | Max cost in abstract units; must be ≥ 0 |
| `allowed_actions` | list[string] | [] | Explicitly permitted action types |
| `forbidden_actions` | list[string] | [] | Explicitly forbidden action types |
| `data_sensitivity` | DataSensitivity | `internal` | Max data sensitivity level |
| `determinism_required` | DeterminismLevel | `strict` | Required determinism level |
| `priority` | Priority | `normal` | Execution priority |

### 4.6 ProvenanceBlock

The `ProvenanceBlock` enables authorization decisions to consider the full chain of intent mediation rather than only the final submitting actor. All fields are optional within the block; the block itself is optional in the `IntentEnvelope` for SIP v0.1 backward compatibility. Existing envelopes without a `provenance` field remain valid.

| Field | Type | Description |
|---|---|---|
| `originator` | string? | Identifier of the entity that originally generated the request or intent (e.g. a user ID or agent ID). |
| `submitted_by` | string? | Identifier of the actor that submitted this `IntentEnvelope` to the SIP broker. If omitted, the `actor.actor_id` is assumed to be the submitter. |
| `delegation_chain` | list[string] | Ordered list of actor identifiers representing each delegation hop from the originator to the submitting actor. |
| `on_behalf_of` | string? | The principal on whose behalf the submitting actor is acting, if different from the originator. |
| `delegation_purpose` | string? | Human-readable description of why delegation occurred (audit only). |
| `delegation_expiry` | ISO 8601 datetime? | Optional expiry timestamp after which this delegated authority is no longer valid. Expired delegations must be rejected by the policy engine. |
| `authority_scope` | list[string]? | The set of scopes that the originator authorized for this delegated action. The policy engine must enforce that the submitted intent does not request scopes outside this set. |

When the `provenance` block is present, the policy engine must validate the full provenance in addition to the submitting actor's trust context. See Section 8, rules 6–8 for the provenance-specific policy evaluation rules.

---

## 5. CapabilityDescriptor

Describes a registered capability.

### 5.1 Fields

| Field | Type | Description |
|---|---|---|
| `capability_id` | string | Unique capability identifier |
| `name` | string | Human-readable name |
| `description` | string | What the capability does |
| `provider` | ProviderMetadata | Provider information |
| `intent_domains` | list[string] | Functional domains served |
| `input_schema` | SchemaReference | Input shape or schema reference |
| `output_schema` | SchemaReference | Output shape or schema reference |
| `operation_class` | OperationClass | Operation class implemented |
| `risk_level` | RiskLevel | `low`, `medium`, `high`, `critical` |
| `required_scopes` | list[string] | Permission scopes required |
| `minimum_trust_tier` | TrustLevel | Minimum trust level required |
| `supported_bindings` | list[BindingType] | Supported execution protocols |
| `execution` | ExecutionMetadata | Execution characteristics |
| `constraints` | CapabilityConstraints | Operational constraints |
| `examples` | list[CapabilityExample] | Example invocations |
| `tags` | list[string] | Searchable tags |

---

## 6. Validation Rules

The following rules are enforced by `validate_envelope()` in addition to Pydantic structural
validation:

| Rule | Condition | Severity |
|---|---|---|
| SIP version | `sip_version` must be in `{"0.1"}` | Error |
| Operation class | Must be a valid `OperationClass` value | Error |
| Trust level | Actor and declared trust levels must be valid | Error |
| Determinism | `determinism_required` must be valid | Error |
| Binding types | All binding types must be valid | Error |
| Time budget | `time_budget_ms` must be ≥ 0 | Error |
| Cost budget | `cost_budget` must be ≥ 0 | Error |
| Action conflicts | `allowed_actions` ∩ `forbidden_actions` must be empty | Error |
| Write/execute trust | Write or execute operations require ≥ `internal` trust | Error |
| Advisory determinism | Write/execute with `advisory` determinism | Warning |

---

## 7. Negotiation Semantics

### 7.1 Matching Algorithm

The `CapabilityMatcher` uses additive scoring:

1. At least one name or domain signal must be present (otherwise capability is excluded).
2. Exact intent name = capability ID: +3.0
3. Partial name match: +2.0
4. Exact domain match: +2.0
5. Partial domain match: +1.0
6. Operation class match: +2.0
7. Preferred binding match: +1.5
8. Candidate hint: +0.5
9. Trust too low: excluded entirely

### 7.2 Selection Logic

- If no candidates: `requires_clarification = True`
- If 1 candidate: selected automatically
- If multiple: selected if score gap ≥ 1.0 OR `allow_fallback = True`
- Otherwise: `requires_clarification = True`

---

## 8. Policy Evaluation

Policy rules are evaluated in order. First failure wins.

1. **Scope check** – Actor must hold all required scopes.
2. **Risk + operation** – `(HIGH|CRITICAL, WRITE|EXECUTE)` requires approval.
3. **Risk + sensitivity** – `(CRITICAL, RESTRICTED)` is denied.
4. **Delegation depth** – Chain length > 5 is denied.
5. **Capability override** – `requires_human_approval = true` always requires approval.
6. **Provenance scope check** *(when `provenance` block is present)* – The submitted intent must not request scopes outside the `authority_scope` granted by the originator. If any required capability scope is absent from `authority_scope`, the request is denied.
7. **Originator trust check** *(when `provenance.originator` is present)* – The effective trust level for authorization is the lower of the submitting actor's `trust_level` and the originator's resolved trust level. A delegated intent cannot gain a higher trust level than the originator possessed.
8. **Delegation expiry** *(when `provenance.delegation_expiry` is present)* – If the current timestamp is past `delegation_expiry`, the request is denied.

> **Rule: Delegation must never increase authority.** A delegated intent cannot gain additional scopes or a higher trust level than the originator possessed. Any delegation step that would expand authority must be rejected.

---

## 9. Binding Types

| Binding | Description |
|---|---|
| `rest` | HTTP/REST endpoint |
| `grpc` | gRPC service method |
| `mcp` | Model Context Protocol tool |
| `a2a` | Agent-to-Agent task |
| `rag` | Retrieval-Augmented Generation query |

---

## 10. Trust Levels

Trust levels are ordered:

`public` < `internal` < `privileged` < `admin`

Write and execute operations require at minimum `internal` trust.
The `delegate_agent_task` capability requires `privileged` trust.

---

## 11. Scope Format

SIP scopes follow the format: `sip:{domain}:{action}`

Examples:
- `sip:knowledge:read`
- `sip:booking:write`
- `sip:network:read`
- `sip:network:execute`
- `sip:agent:delegate`
- `sip:admin`

---

## 12. Natural Language Constraints

**Natural language is never executed directly in SIP.**

The `natural_language_hint` field in `IntentPayload` exists solely for:
- Human-readable logging and debugging
- Audit records
- Developer documentation of intent

It MUST NOT be parsed, interpreted, or executed by any SIP component.

---

## 13. Versioning

This is SIP protocol version `0.1`. Breaking changes will increment the major version.
The `sip_version` field in `IntentEnvelope` identifies the protocol version.
Brokers MUST reject envelopes with unrecognized versions.

### 13.1 Forward Compatibility

Implementations MUST ignore unknown optional fields in protocol objects. This is required to allow
forward-compatible minor protocol evolution without breaking existing consumers.
