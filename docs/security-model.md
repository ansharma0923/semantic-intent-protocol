# SIP Security Model

## Design Philosophy

SIP's security model is explicit, layered, and deterministic. There are no
probabilistic security decisions — every policy evaluation is rule-based and
produces a deterministic allow, deny, or require-approval result.

## Intent Provenance

SIP must track the origin and transformation of an intent across agent mediation. When AI agents translate natural-language user requests into structured `IntentEnvelope` objects, the broker cannot assume that the submitting actor and the originating entity are the same. SIP preserves provenance information so that authorization decisions can consider both the submitting actor and the original requester.

The following roles are defined for provenance tracking:

- **originator** — the entity that originally generated the request or intent (e.g. a human user or an automated system initiating the action).
- **submitting_actor** — the actor that submits the `IntentEnvelope` to the SIP broker. This may be an AI agent acting on behalf of the originator.
- **executing_actor** — the capability provider or system that performs execution in response to the approved `ExecutionPlan`.
- **delegated_by** — the actor that delegated the task to another actor in a delegation chain step.

Provenance information is carried in the optional `provenance` block of the `IntentEnvelope`. When present, the policy engine uses provenance to validate that the originator's authority is consistent with the action being requested, and that no delegation step has silently escalated privileges.

## Intent Laundering

Intent laundering is a security risk in which a low-privilege originator causes a more trusted agent or service to submit an `IntentEnvelope` that appears authorized but represents an action the originator was not permitted to perform.

This can occur when:

- agents translate natural-language requests into structured intents, substituting the agent's trust level and scopes in place of the originator's
- trusted agents submit requests on behalf of users without preserving the originator's authority constraints
- delegation chains obscure the origin of authority, making a privileged submission appear legitimate

SIP mitigates this risk by preserving intent provenance and enforcing that delegated authority cannot exceed the authority of the originator. The policy engine must consider both the submitting actor and the originator when evaluating authorization, and any delegation step that would increase the effective authority of the request must be rejected.

> **Note:** Intent laundering is related to identity laundering (the use of stolen or forged credentials to submit requests under a false identity), but occurs at the semantic intent layer rather than the authentication layer. Identity laundering attacks the credential or token; intent laundering attacks the semantic transformation from natural language or low-privilege context into a high-privilege structured intent.

## Authentication Boundary

SIP does not perform authentication itself. Authentication is expected to occur
at the transport or gateway layer, prior to any intent reaching the SIP broker.
Supported authentication mechanisms include:

- OAuth2 / OpenID Connect
- JWT bearer tokens
- mTLS client certificates
- API gateway identity validation

Once authentication succeeds, the resulting identity is mapped into the SIP
`ActorDescriptor` inside the `IntentEnvelope`, including the actor's trust level
and the set of granted scopes. SIP then performs authorization and policy
evaluation using this actor identity exclusively.

### External Identity Integration via Trusted Headers

SIP v0.1 adds optional support for mapping pre-authenticated identity claims
from HTTP request headers into SIP actor and trust context.  This allows an
API gateway or service mesh to inject verified identity after authentication,
without requiring the caller to re-specify it in every request body.

**Supported headers:**

| Header | Maps to |
|--------|---------|
| `X-Actor-Id` | `ActorDescriptor.actor_id` |
| `X-Actor-Type` | `ActorDescriptor.actor_type` |
| `X-Actor-Name` | `ActorDescriptor.name` |
| `X-Trust-Level` | `ActorDescriptor.trust_level` |
| `X-Scopes` | `ActorDescriptor.scopes` (comma-separated) |

**Precedence rule:** when trusted identity headers are enabled and a header is
present, the header value **overrides** the corresponding field from the request
body.  This is logged at INFO level to maintain an audit trail.

**Configuration:** set `SIP_TRUSTED_IDENTITY_HEADERS=true` (or `1` / `yes`) in
the broker's environment to enable header mapping.  The default is `false`
(disabled).

**⚠ Security requirements:**

1. **Trusted deployment only.** Header-based identity mapping is designed
   exclusively for deployments where the SIP broker is behind a trusted API
   gateway, reverse proxy, or service mesh.  The upstream infrastructure must:
   - Strip any client-supplied `X-Actor-*` and `X-Trust-Level` / `X-Scopes`
     headers from incoming requests before forwarding.
   - Re-inject the authenticated identity as headers only after validating
     the caller's credentials.

2. **Do not expose the broker directly to untrusted clients** when this feature
   is enabled.  A malicious client could send arbitrary `X-Actor-Id` or
   `X-Trust-Level` headers to impersonate a more privileged identity.

3. **This feature does not perform authentication.** SIP still does not
   validate tokens, certificates, or any credential.  It only maps
   pre-verified claims provided by the trusted infrastructure.

4. **Audit trail.** Every header override is logged at INFO level, including
   the original body value and the new header value, providing a clear audit
   trail for security review.

## Security Architecture

The following diagram illustrates the separation between the authentication
layer and the SIP authorization layer:

```
Client / Agent
      │
      │  Authentication
      │  (OAuth2 / JWT / mTLS / API Gateway)
      ▼
Authenticated Identity
      │
      ▼
SIP Broker
      │
      ├─ Envelope Validation
      ├─ Capability Negotiation
      ├─ Policy Engine (Authorization)
      │      • scope checks
      │      • trust levels
      │      • risk rules
      │      • delegation chain limits
      │
      ├─ Execution Plan
      └─ Audit Record
      │
      ▼
Execution Systems
   REST | gRPC | MCP | A2A | RAG
```

- Authentication occurs before the SIP broker receives the request. The broker
  assumes the identity presented in the `ActorDescriptor` has already been
  verified by the transport or gateway layer.
- Authorization decisions occur inside the SIP policy engine, which evaluates
  scopes, trust levels, risk rules, and delegation chain constraints.
- Execution systems rely on the execution plan produced by SIP and do not
  re-evaluate policy.

### Authorization Responsibilities of SIP

SIP authorization covers the following:

- **Scope-based access control** — every capability declares the scopes required
  to invoke it; the policy engine denies requests with missing scopes.
- **Trust level enforcement** — operations are gated on the actor's declared
  trust level; the declared level may not exceed the actor's assigned level.
- **Risk-based approval requirements** — high-risk and critical operations may
  require explicit human approval before execution proceeds.
- **Delegation chain control** — delegation depth is bounded to prevent
  unbounded re-delegation cycles.
- **Capability-specific constraints** — allowed and forbidden action lists are
  enforced per intent, and data sensitivity limits are applied.

These decisions are deterministic and rule-based. There is no probabilistic or
heuristic policy evaluation in SIP v0.1.

### Authentication Responsibilities Outside SIP

The following concerns are outside the scope of SIP v0.1:

- Credential verification
- JWT signature validation
- mTLS certificate validation
- Token issuance
- Identity federation

These responsibilities are expected to be handled by identity providers, API
gateways, or service meshes that sit in front of the SIP broker. SIP treats the
identity presented in the `IntentEnvelope` as pre-verified.

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

SIP tracks delegation chains in the trust block and, when present, in the `provenance` block. The following rules apply to all delegation:

- **Originator preservation** — the originator must be recorded and preserved throughout the entire provenance chain; no delegation step may omit or alter the originator.
- **Authority monotonicity** — each delegation step must preserve or reduce authority; **delegation must never increase authority**. A delegated intent cannot gain additional scopes or a higher trust level than the originator possessed.
- **Bounded chain depth** — if the delegation chain exceeds 5 hops, the request is denied to prevent infinite delegation cycles.
- **Optional expiration** — delegated authority may optionally include an expiration timestamp (`delegation_expiry`); expired delegations must be rejected.
- **Dual-principal validation** — policy evaluation must validate that the final action is allowed for both the submitting actor and the originator. If either principal lacks the required authority, the request is denied.

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
- **Originator** — the entity that originally generated the intent (from the provenance block if present)
- **Submitting actor** — the actor that submitted the `IntentEnvelope` to the broker
- **Delegation chain** — the full delegation chain from the provenance block, enabling security teams to trace how an intent moved through agents and services

Including provenance fields in the audit record allows post-hoc analysis of delegation paths and detection of intent laundering attempts.

Audit records must be written to an append-only log in production deployments.

## Threat Model (v0.1)

### In Scope

- Unauthorized scope access (mitigated by scope checking)
- Privilege escalation through delegation (mitigated by delegation depth limit and authority monotonicity)
- **Intent laundering through trusted agent mediation** (mitigated by provenance tracking, scope narrowing, trust level enforcement, delegation chain limits, approval workflows, and immutable audit logging)
- Execution of unsafe operations (mitigated by risk-based approval)
- Ambiguous intent resolution (mitigated by structured intent + negotiation)
- LLM prompt injection via natural language fields (mitigated by never executing NL)

Intent laundering arises when semantic transformations across agents cause privilege escalation that would not have been permitted if the originator submitted the intent directly. An AI agent mediating a user's natural-language request may, intentionally or inadvertently, construct an `IntentEnvelope` that carries the agent's elevated scopes rather than the user's constrained scopes. SIP addresses this threat through:

- **Explicit provenance tracking** — the `provenance` block records the originator separately from the submitting actor.
- **Scope narrowing during delegation** — delegated intents may only use scopes held by the originator; a delegate may not add scopes absent from the originator's grant.
- **Trust level enforcement** — the effective trust level for policy evaluation is the lower of the submitting actor's and the originator's trust levels.
- **Delegation chain limits** — chains exceeding 5 hops are denied; bounded chains reduce the surface for laundering through deep intermediary webs.
- **Approval workflows** — high-risk and critical operations require explicit human approval, providing a manual review gate against laundered escalation.
- **Immutable audit logging** — full provenance including originator, submitting actor, and delegation chain is captured in every audit record for retrospective analysis.

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
7. When using persistent capability registry (`JsonFileCapabilityStore`), restrict read/write permissions on `data/capabilities.json` to the broker process only.
8. If enabling `SIP_TRUSTED_IDENTITY_HEADERS=true`, ensure the SIP broker is not directly reachable by untrusted clients; deploy behind a gateway that strips and re-injects identity headers.
