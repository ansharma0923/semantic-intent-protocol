---
name: Protocol Change Proposal
about: Propose a change to the SIP protocol specification
title: "[Protocol] "
labels: protocol-proposal
assignees: ''
---

## Summary

Short description of the proposed change.

## Motivation

Why is this change needed? What problem does it solve or what capability does it enable?

## Proposed Design

Explain the protocol change clearly. Include:

- Which protocol objects are affected (`IntentEnvelope`, `CapabilityDescriptor`, `NegotiationResult`, `ExecutionPlan`, `AuditRecord`, or other)
- How the wire format would change (reference [docs/sip-wire-spec-v0.1.md](../../docs/sip-wire-spec-v0.1.md))
- Any new fields, types, or behaviors introduced

## Compatibility

Is this change backward compatible with existing SIP v0.1 implementations?

- [ ] Fully backward compatible
- [ ] Backward compatible with a deprecation path
- [ ] Breaking change — requires a new protocol version

Explain your reasoning.

## Security Impact

Does this change affect any of the following? Describe the impact for each that applies.

- **Provenance** — actor identity, delegation chain, or trust level handling
- **Policy enforcement** — scope validation, risk evaluation, or approval flow
- **Capability negotiation** — matching, ranking, or selection logic
- **Federation behavior** — cross-broker routing or trust propagation

> If this proposal introduces security-sensitive changes, consider discussing
> privately via [SECURITY.md](../../SECURITY.md) before opening a public issue.

## Protocol Specification Impact

Identify which documents or protocol objects would need to change:

- [ ] `docs/sip-wire-spec-v0.1.md`
- [ ] `docs/security-model.md`
- [ ] `docs/capability-model.md`
- [ ] `docs/governance.md`
- [ ] `protocol-vectors/` (canonical test fixtures)
- [ ] Other: <!-- list here -->

## Alternatives Considered

Describe any alternative designs you considered and why you prefer the proposed approach.

## Additional Notes

Any other context, references, or open questions for maintainers.
