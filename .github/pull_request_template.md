## Summary

Brief description of the change and its motivation. Reference any related issues (e.g., `Closes #123`).

## Type of Change

- [ ] Bug fix
- [ ] Documentation improvement
- [ ] SDK improvement (Python or Go)
- [ ] Example improvement
- [ ] Protocol proposal

## Testing

Explain how the change was tested:

- [ ] Existing tests pass (`make test`)
- [ ] New tests added for new behavior
- [ ] Manually verified with a runnable example

Describe any specific test scenarios or commands used.

## Checklist

- [ ] All tests pass (`make test`)
- [ ] Linter passes (`make lint`)
- [ ] Documentation updated if needed
- [ ] Protocol behavior is unchanged unless this is an intentional protocol proposal
- [ ] Backward compatibility considered — existing protocol vectors and SDK interfaces are unaffected

## Notes for Maintainers

Optional: any extra context, open questions, or considerations for reviewers.

> **Protocol changes** — If this PR modifies protocol semantics, the wire format,
> the security model, or any protocol vectors, it must be preceded by an approved
> Protocol Change Proposal issue. See [CONTRIBUTING.md](../CONTRIBUTING.md) and
> [docs/governance.md](../docs/governance.md).
