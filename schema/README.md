# SIP JSON Schemas

This directory contains the formal JSON Schema definitions for the Semantic Intent Protocol (SIP) v0.1 protocol objects.

## Schemas

| Schema file | Title | Description |
|---|---|---|
| [`sip-intent-envelope.schema.json`](sip-intent-envelope.schema.json) | SIP IntentEnvelope | Root protocol object — carries a semantic intent from an actor to a target |
| [`sip-capability-descriptor.schema.json`](sip-capability-descriptor.schema.json) | SIP CapabilityDescriptor | Describes a registered capability in the broker registry |
| [`sip-negotiation-result.schema.json`](sip-negotiation-result.schema.json) | SIP NegotiationResult | Ranked candidates, selected capability, and policy decision |
| [`sip-execution-plan.schema.json`](sip-execution-plan.schema.json) | SIP ExecutionPlan | Deterministic, fully specified execution plan ready for adapter translation |
| [`sip-audit-record.schema.json`](sip-audit-record.schema.json) | SIP AuditRecord | Immutable audit log entry for every processed intent |

## Purpose

These schemas serve as the **machine-readable normative definition** of the SIP v0.1 wire format.

They are used to:

1. **Validate protocol vectors** — The [`tests/schema_validation/`](../tests/schema_validation/) suite validates all canonical JSON fixtures in [`protocol-vectors/`](../protocol-vectors/) against these schemas.
2. **Guide SDK implementations** — New SDKs in any language should use these schemas to ensure compatibility.
3. **Document the wire format** — The schemas are the authoritative description of every field, type, enum, and constraint in the protocol objects.

## Schema dialect

All schemas use [JSON Schema 2020-12](https://json-schema.org/draft/2020-12/schema).

## How to validate a document against a schema

Using Python (`jsonschema` library):

```python
import json
import jsonschema
from pathlib import Path

schema = json.loads(Path("schema/sip-intent-envelope.schema.json").read_text())
instance = json.loads(Path("protocol-vectors/intent-envelope-basic.json").read_text())

jsonschema.validate(instance, schema)
print("Valid")
```

Using the CLI (`jsonschema` package):

```bash
pip install jsonschema
python -m jsonschema -i protocol-vectors/intent-envelope-basic.json schema/sip-intent-envelope.schema.json
```

## Relationship to protocol vectors

The [`protocol-vectors/`](../protocol-vectors/) directory contains canonical JSON examples for each protocol object.
Every vector must validate against the corresponding schema in this directory.

See [`tests/schema_validation/`](../tests/schema_validation/) for the automated validation tests.

## Alignment with the reference implementation

These schemas are derived from the Python reference implementation in [`sip/`](../sip/).
Key source modules:

- `sip/envelope/models.py` → `sip-intent-envelope.schema.json`
- `sip/registry/models.py` → `sip-capability-descriptor.schema.json`
- `sip/negotiation/models.py` → `sip-negotiation-result.schema.json`
- `sip/negotiation/planner.py` → `sip-execution-plan.schema.json`
- `sip/observability/audit.py` → `sip-audit-record.schema.json`

If the reference implementation is updated, the schemas should be updated to match.

## Versioning

Schema files are versioned by the SIP protocol version (`0.1`).
Breaking changes to schemas require a new minor protocol version (v0.2+).

Extension fields are supported via the `extensions` object on each protocol object.
Extension keys should be namespaced (e.g., `x-acme.priority`).
Keys starting with `x-sip.` are reserved for official protocol use.
