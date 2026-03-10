# SIP Security Model

## Design Philosophy

SIP's security model is explicit, layered, and deterministic. There are no
probabilistic security decisions — every policy evaluation is rule-based and
produces a deterministic allow, deny, or require-approval result.

## Layers of Control

### 1. Trust Levels

Every actor carries a declared trust level:

| Level | Description |
|---|---|
| `public` | Unauthenticated or minimally trusted |
| `internal` | Authenticated internal service or user |
| `privileged` | Elevated internal actor with additional privileges |
| `admin` | Administrative actor |

Trust levels are ordered. Write and execute operations require at minimum `internal`.

The `declared_trust_level` in the trust block must not exceed the actor's `trust_level`.
If it does, the lower actor trust level is enforced.

### 2. Scope-Based Access Control

Scopes follow the format `sip:{domain}:{action}`. Each capability declares the
set of scopes an actor must hold to invoke it.

The policy engine checks scopes before any risk evaluation. If any required scope
is missing, the request is denied immediately.

Well-known scopes in v0.1:

| Scope | Description |
|---|---|
| `sip:knowledge:read` | Read knowledge/documents |
| `sip:knowledge:write` | Write knowledge/documents |
| `sip:customer:read` | Read customer data |
| `sip:customer:write` | Write customer data |
| `sip:network:read` | Read/analyze network data |
| `sip:network:execute` | Execute network operations |
| `sip:booking:write` | Create/modify bookings |
| `sip:agent:delegate` | Delegate tasks to other agents |
| `sip:admin` | Administrative operations |

### 3. Risk-Based Decisioning

Each capability has a `risk_level`. Combined with the operation class, the policy
engine determines whether human approval is required:

| Risk Level | WRITE/EXECUTE | READ/ANALYZE/RETRIEVE | DELEGATE |
|---|---|---|---|
| `low` | No approval | No approval | No approval |
| `medium` | No approval | No approval | No approval |
| `high` | **Requires approval** | No approval | No approval |
| `critical` | **Requires approval** | **Requires approval** | **Requires approval** |

The approval policy can be disabled in non-production environments via
`SIP_REQUIRE_APPROVAL_HIGH_RISK=false`.

### 4. Data Sensitivity

The intent envelope's `constraints.data_sensitivity` declares the maximum
sensitivity level of data involved. Combined with capability risk:

| Risk Level | Data Sensitivity | Result |
|---|---|---|
| `critical` | `restricted` | **Denied** |
| Any other combination | Any | Allowed |

### 5. Delegation Chain Control

SIP tracks delegation chains in the trust block. If a chain exceeds 5 hops,
the request is denied to prevent infinite delegation cycles.

### 6. Action Constraints

The `allowed_actions` and `forbidden_actions` fields in `Constraints` provide
explicit control over what types of actions are permitted for a given intent.
These lists must be disjoint — any overlap is a validation error.

## Trust Token References

Tokens (JWT or otherwise) are never stored inline in the envelope. The
`trust.token_reference` field holds a reference (e.g. a token ID or header
name) that the executing system can use to retrieve the token separately.

This design prevents token leakage through audit logs, which capture the full
intent envelope.

## Audit Trail

Every intent processed by the broker produces an immutable `AuditRecord` that
captures:
- Actor identity and type
- Intent name, domain, and operation class
- Selected capability and binding
- Policy decision (allowed/denied, approval state)
- Outcome summary
- Trace ID for correlation

Audit records must be written to an append-only log in production deployments.

## Threat Model (v0.1)

### In Scope

- Unauthorized scope access (mitigated by scope checking)
- Privilege escalation through delegation (mitigated by delegation depth limit)
- Execution of unsafe operations (mitigated by risk-based approval)
- Ambiguous intent resolution (mitigated by structured intent + negotiation)
- LLM prompt injection via natural language fields (mitigated by never executing NL)

### Out of Scope for v0.1

- Cryptographic envelope signing (integrity block is a placeholder)
- mTLS or token validation (assumed to be handled at the transport layer)
- Rate limiting enforcement (declared in capability but not enforced by the broker)
- Multi-tenant isolation (all capabilities are visible to all actors)

## Recommendations for Production Deployment

1. Enforce TLS on all broker API endpoints.
2. Validate JWT tokens at the transport layer before populating actor scopes.
3. Persist audit records to an immutable, tamper-evident log store.
4. Enable `SIP_REQUIRE_APPROVAL_HIGH_RISK=true` in production.
5. Implement envelope signing using the `integrity` block when feasible.
6. Restrict the `sip:admin` scope to a minimum set of administrative actors.
