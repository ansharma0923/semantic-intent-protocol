# Contributing to Semantic Intent Protocol (SIP)

Thank you for your interest in contributing to SIP. Before contributing,
please read the [README](README.md), the [protocol documentation](docs/),
and the [governance document](docs/governance.md) to understand the project's
design goals and constraints.

---

## Ways to Contribute

- **Bug reports** — Open a GitHub issue with a clear reproduction case.
- **Documentation improvements** — Fixes, clarifications, and additions to
  `docs/` or inline docstrings.
- **Examples** — New or improved runnable examples in `examples/`.
- **SDK improvements** — Enhancements to the Python SDK (`sip/`) or Go SDK
  (`sdk/go/`) that do not change protocol semantics.
- **Tests** — Additional unit or functional tests that improve coverage.
- **Protocol proposals** — Proposals for changes to protocol semantics,
  the wire format, or the security model (see below).

---

## Using Issue Templates

When opening a GitHub issue, please select the appropriate template:

- **Bug Report** — Use this template for runtime errors, unexpected behavior,
  test failures, or any reproducible defect in the SIP implementation or SDKs.
  Include steps to reproduce, your environment, and any relevant logs.

- **Feature Request** — Use this template for proposed improvements to the
  Python SDK, Go SDK, broker, tooling, or documentation that do not change
  protocol semantics.

- **Protocol Change Proposal** — Use this template when proposing changes to
  the SIP protocol specification, including the wire format
  ([docs/sip-wire-spec-v0.1.md](docs/sip-wire-spec-v0.1.md)), the security
  model, capability negotiation semantics, or protocol vectors. Protocol
  proposals require a governance review before any implementation work begins.
  See [docs/governance.md](docs/governance.md) for the full process.

> For security vulnerabilities, **do not** open a public issue.
> Follow the private disclosure process described in [SECURITY.md](SECURITY.md).

---

## Pull Request Process

1. **Fork** the repository and create a feature branch from `main`.
2. **Write tests** for any new behavior or bug fix where appropriate.
3. **Ensure all tests pass** before submitting:
   ```bash
   make test
   ```
4. **Run the linter** to confirm no style issues:
   ```bash
   make lint
   ```
5. **Submit a pull request** against `main` with a clear description of the
   change and its motivation. Reference any related issues.

Pull requests are reviewed by maintainers. Please allow reasonable time for
review. Maintainers may request changes or clarification before merging.

---

## Protocol Change Guidance

Changes that affect any of the following require a governance review and
**must not** be made through implementation-only pull requests:

- Protocol semantics or the `IntentEnvelope` wire format
- The security model (trust levels, scopes, delegation, risk policy)
- Protocol vectors or canonical test fixtures
- Backward or forward compatibility guarantees
- The `sip-wire-spec-v0.1.md` or `security-model.md` documents

To propose a protocol change, open a GitHub issue clearly labelled as a
protocol proposal and include a written rationale. Discuss the proposal
with maintainers before implementing it. See [docs/governance.md](docs/governance.md)
for the full governance process.

---

## Developer Expectations

- **Backward compatibility** — Preserve compatibility with existing
  protocol vectors and SDK interfaces wherever possible. Breaking changes
  require explicit versioning and governance approval.
- **Determinism** — SIP is a deterministic control plane. Contributions
  must not introduce non-deterministic behavior in validation, negotiation,
  policy evaluation, or planning.
- **Provenance and security guarantees** — Do not weaken existing trust,
  scope, or audit properties. All execution paths must remain auditable.
- **No LLM calls in protocol logic** — All matching, negotiation, and
  policy evaluation must remain rule-based and deterministic.

---

## Licensing

By contributing to this repository, you agree that your contributions will
be licensed under the [Apache License 2.0](LICENSE).
