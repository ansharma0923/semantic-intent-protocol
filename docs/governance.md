# SIP Protocol Governance

This document defines the governance model for the Semantic Intent Protocol (SIP), including versioning policy, compatibility guarantees, extension rules, protocol change processes, and SDK expectations.

---

## Overview

The Semantic Intent Protocol (SIP) is a deterministic control plane protocol for AI agents and software systems, designed to be stable, deterministic, and implementable across multiple languages and runtimes. Governance ensures that the protocol evolves predictably without breaking existing implementations.

SIP governance is organized around three principles:

1. **Stability first** — backward-incompatible changes require a new major version, extensive review, and a migration path.
2. **Determinism is non-negotiable** — all protocol objects and processing rules must produce identical results for identical inputs, regardless of the SDK language or version.
3. **Explicit trust** — all changes to trust, scope, or policy semantics are treated as security-sensitive and require security review.

---

## Versioning Policy

SIP uses **semantic versioning** (`MAJOR.MINOR.PATCH`) for the protocol specification:

| Component | Change type | When to increment |
|-----------|-------------|-------------------|
| `MAJOR`   | Breaking    | Removing or renaming a required field; changing a field type; changing policy semantics in a backward-incompatible way |
| `MINOR`   | Additive    | Adding a new optional field; adding a new enum value; adding a new well-known scope or message type |
| `PATCH`   | Fix         | Clarifying documentation; fixing an obvious specification error that does not change protocol behavior |

### Current Version

The current protocol version is **v0.1** (pre-1.0). During v0.x, MINOR increments may include breaking changes that are clearly documented with a migration guide. Once the protocol reaches v1.0, full semantic versioning guarantees apply.

### Version Field

Every `IntentEnvelope` carries a `sip_version` field. Brokers **must** reject envelopes whose `sip_version` they do not support with HTTP `400 Bad Request` and an informative error message.

---

## Protocol Compatibility Guarantees

### What is guaranteed

- All fields present in a released version remain parseable in all subsequent MINOR and PATCH versions of the same MAJOR series.
- Optional fields added in a MINOR release must be safely ignored by implementations that do not recognize them.
- Enum values added in a MINOR release must be safely handled (e.g., by treating unknown values as equivalent to a defined default) by implementations that do not recognize them.
- The behavior of the policy engine for any combination of fields valid in version `N` must be identical in version `N.x`.

### What is not guaranteed

- Experimental fields prefixed with `x_` or vendor-namespaced extensions (`<vendor>.<name>`) have no compatibility guarantees between protocol versions.
- Fields marked `deprecated` in the specification may be removed in the next MAJOR version.

---

## Extension Namespace Rules

Extensions allow implementers to attach additional data to protocol objects without modifying the protocol specification.

### Allowed formats

Extension keys on `IntentEnvelope`, `CapabilityDescriptor`, `NegotiationResult`, `ExecutionPlan`, and `AuditRecord` must follow one of these formats:

| Format | Example | Use case |
|--------|---------|----------|
| `x_<name>` | `x_routing_hint` | Experimental or implementation-specific extensions |
| `<vendor>.<name>` | `acme.priority_boost` | Vendor-specific extensions |

### Prohibited formats

- Extensions **must not** use names that match or shadow any core protocol field (e.g., `intent_id`, `actor`, `policy_decision`).
- Extensions **must not** use the reserved `sip.` prefix (e.g., `sip.custom_field` is invalid).
- Numeric or whitespace-only keys are not permitted.

### Processing rules

- Brokers and SDKs **must** preserve unknown extensions when passing objects through the pipeline.
- Brokers **must not** make policy decisions based on the presence or absence of extensions unless those extensions are explicitly defined in the protocol specification.
- Extensions do not affect determinism requirements.

---

## Protocol Change Process

### Minor additions (new optional fields, new enum values)

1. Open a proposal issue on the SIP repository with the `protocol-change` label.
2. Reference the [wire spec](sip-wire-spec-v0.1.md) section(s) that would be affected.
3. Provide at least one concrete use case and a proposed JSON schema diff.
4. Allow at least **14 days** for community review.
5. The change requires approval from at least **two** core maintainers.
6. Update the wire spec, add a protocol vector, and update all existing SDKs in the same PR.

### Breaking changes (new MAJOR version)

1. Follow all steps for minor additions.
2. Provide a **migration guide** describing how existing implementations must adapt.
3. Allow at least **30 days** for community review.
4. Maintain the previous MAJOR version's reference implementation for at least **6 months** after the new MAJOR version is released.
5. Requires approval from **all** core maintainers.

### Security-sensitive changes

Any change that affects:
- trust levels or trust level semantics
- scope validation rules
- policy engine evaluation logic
- provenance or anti-laundering checks

requires a **security review** (see [Security Review Requirements](#security-review-requirements)) in addition to the standard protocol change process.

---

## Reference Implementation Policy

The Python implementation in the `sip/` directory is the **authoritative reference implementation** for SIP v0.1.

### What the reference implementation defines

- The canonical behavior of the policy engine.
- The canonical behavior of provenance and anti-laundering checks.
- The canonical serialization format for all protocol objects.
- The canonical behavior of the broker HTTP API.

### Deviations

If an SDK or alternative broker implementation behaves differently from the reference implementation for a given input, the reference implementation is correct and the alternative must be fixed.

Exception: differences in performance, logging, observability, and deployment configuration are explicitly not governed by this policy.

---

## SDK Compatibility Expectations

All SDKs (Python, Go, or future languages) must satisfy the following compatibility requirements:

### Required capabilities

1. **Parse all protocol vectors** — Every SDK must be able to deserialize all JSON files in `protocol-vectors/` into the corresponding protocol model without errors.
2. **Round-trip equality** — Serializing a parsed vector back to a dict/map and re-parsing it must produce an object equal to the original.
3. **Correct field mapping** — All JSON field names must exactly match the SIP specification. No renaming or aliasing of required fields.
4. **Null/optional field handling** — Optional fields that are absent or `null` in the wire format must not cause parse errors.
5. **Extension preservation** — Unknown extension keys must be preserved when an object is passed through the SDK.

### Testing requirements

Every SDK must include:
- A test suite that runs against all protocol vectors in `protocol-vectors/`.
- Round-trip serialization tests for each protocol object type.

See:
- Python tests: [`tests/protocol_vectors/`](../tests/protocol_vectors/)
- Go tests: [`sdk/go/tests/`](../sdk/go/tests/)

### Versioning

SDKs follow their own semantic versioning independently of the protocol version. However:
- An SDK's `MAJOR` version must be bumped when it drops support for a protocol MAJOR version.
- An SDK must clearly document which protocol versions it supports in its README or package metadata.

---

## Security Review Requirements

The following types of changes require a dedicated security review before merging:

| Change type | Reason |
|-------------|--------|
| Changes to scope validation logic | May allow unauthorized capability access |
| Changes to provenance / anti-laundering checks | May allow privilege escalation |
| New trust levels or trust level semantics | Affects all policy decisions |
| Changes to the delegation depth limit | May enable unbounded delegation chains |
| New HTTP endpoints or authentication mechanisms | Expands the attack surface |
| Changes to extension key validation | May allow injection of shadow fields |

### Security review process

1. Tag the PR with the `security-review` label.
2. The security review must be performed by at least one maintainer who did **not** author the change.
3. The review must explicitly confirm that the change does not weaken any of the following guarantees:
   - **Scope containment** — a delegated actor cannot acquire scopes not held by the originator.
   - **Determinism** — policy evaluation is fully deterministic and cannot be influenced by extension fields.
   - **Auditability** — every intent processed by the broker produces an immutable audit record.
   - **Anti-laundering** — the delegation chain in the provenance block is verified, not just preserved.

---

## Related Documents

- [SIP Wire Specification v0.1](sip-wire-spec-v0.1.md)
- [Protocol Vectors README](../protocol-vectors/README.md)
- [Security Model](security-model.md)
- [Architecture Overview](architecture.md)
- [Python SDK Reference](python-sdk.md)
- [Go SDK](../sdk/go/)
