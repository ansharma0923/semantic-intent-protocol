# SIP Protocol Specification v0.1

**Status**: Working Draft  
**Version**: 0.1  
**Date**: 2024

---

## 1. Introduction

This document specifies the Semantic Intent Protocol (SIP) v0.1 protocol objects,
message types, validation rules, and processing semantics.

SIP is a semantic interoperability protocol. It defines how actors express intent,
how capabilities are described and discovered, how intent is negotiated, how policy
is enforced, and how intent is translated into deterministic execution.

---

## 2. Message Types

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

## 3. IntentEnvelope

The `IntentEnvelope` is the root protocol object for all SIP `intent_request` messages.

### 3.1 Required Fields

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

### 3.2 Optional Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `constraints` | Constraints | defaults | Execution constraints |
| `context` | ContextBlock | defaults | Session and environment context |
| `capability_requirements` | list[CapabilityRequirement] | [] | Required capabilities |
| `trust` | TrustBlock | defaults | Trust and credential block |
| `protocol_bindings` | list[ProtocolBinding] | [] | Preferred execution bindings |
| `negotiation` | NegotiationHints | defaults | Negotiation hints |
| `integrity` | IntegrityBlock | defaults | Integrity metadata |

### 3.3 ActorDescriptor

| Field | Type | Description |
|---|---|---|
| `actor_id` | string | Unique actor identifier |
| `actor_type` | ActorType | `human`, `ai_agent`, `service`, `system` |
| `name` | string | Human-readable name |
| `trust_level` | TrustLevel | `public`, `internal`, `privileged`, `admin` |
| `scopes` | list[string] | Granted permission scopes |

### 3.4 IntentPayload

| Field | Type | Description |
|---|---|---|
| `intent_name` | string | Machine-readable intent name |
| `intent_domain` | string | Functional domain (e.g. `knowledge_management`) |
| `operation_class` | OperationClass | `read`, `write`, `execute`, `analyze`, `retrieve`, `delegate` |
| `natural_language_hint` | string? | Human-readable hint (audit only, never executed) |
| `parameters` | dict | Structured intent parameters |

### 3.5 Constraints

| Field | Type | Default | Description |
|---|---|---|---|
| `time_budget_ms` | int? | null | Max execution time (ms); must be ≥ 0 |
| `cost_budget` | float? | null | Max cost in abstract units; must be ≥ 0 |
| `allowed_actions` | list[string] | [] | Explicitly permitted action types |
| `forbidden_actions` | list[string] | [] | Explicitly forbidden action types |
| `data_sensitivity` | DataSensitivity | `internal` | Max data sensitivity level |
| `determinism_required` | DeterminismLevel | `strict` | Required determinism level |
| `priority` | Priority | `normal` | Execution priority |

---

## 4. CapabilityDescriptor

Describes a registered capability.

### 4.1 Fields

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

## 5. Validation Rules

The following rules are enforced by `validate_envelope()` in addition to
Pydantic structural validation:

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

## 6. Negotiation Semantics

### 6.1 Matching Algorithm

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

### 6.2 Selection Logic

- If no candidates: `requires_clarification = True`
- If 1 candidate: selected automatically
- If multiple: selected if score gap ≥ 1.0 OR `allow_fallback = True`
- Otherwise: `requires_clarification = True`

---

## 7. Policy Evaluation

Policy rules are evaluated in order. First failure wins.

1. **Scope check** – Actor must hold all required scopes.
2. **Risk + operation** – `(HIGH|CRITICAL, WRITE|EXECUTE)` requires approval.
3. **Risk + sensitivity** – `(CRITICAL, RESTRICTED)` is denied.
4. **Delegation depth** – Chain length > 5 is denied.
5. **Capability override** – `requires_human_approval = true` always requires approval.

---

## 8. Binding Types

| Binding | Description |
|---|---|
| `rest` | HTTP/REST endpoint |
| `grpc` | gRPC service method |
| `mcp` | Model Context Protocol tool |
| `a2a` | Agent-to-Agent task |
| `rag` | Retrieval-Augmented Generation query |

---

## 9. Trust Levels

Trust levels are ordered:

`public` < `internal` < `privileged` < `admin`

Write and execute operations require at minimum `internal` trust.
The `delegate_agent_task` capability requires `privileged` trust.

---

## 10. Scope Format

SIP scopes follow the format: `sip:{domain}:{action}`

Examples:
- `sip:knowledge:read`
- `sip:booking:write`
- `sip:network:read`
- `sip:network:execute`
- `sip:agent:delegate`
- `sip:admin`

---

## 11. Natural Language Constraints

**Natural language is never executed directly in SIP.**

The `natural_language_hint` field in `IntentPayload` exists solely for:
- Human-readable logging and debugging
- Audit records
- Developer documentation of intent

It must not be parsed, interpreted, or executed by any SIP component.

---

## 12. Versioning

This is SIP protocol version `0.1`. Breaking changes will increment the major version.
The `sip_version` field in `IntentEnvelope` identifies the protocol version.
Brokers must reject envelopes with unrecognized versions.
