# SIP Protocol Vectors

This directory contains **canonical JSON protocol fixtures** for the Semantic Intent Protocol (SIP) v0.1.

Protocol vectors are normative reference examples of correctly-formed SIP protocol objects. They serve as the ground truth for validating implementations across different languages and runtimes.

## Purpose

Protocol vectors exist to:

1. **Define correct protocol behavior** — Each vector is a well-formed, validated example of a core SIP object that conforms to the [SIP wire spec v0.1](../docs/sip-wire-spec-v0.1.md).
2. **Enable cross-SDK compatibility testing** — Every SDK (Python, Go, or others) must be able to parse these vectors and produce identical output when serialized back to JSON.
3. **Document realistic usage** — Vectors include realistic field values, examples with extensions, and examples with provenance/delegation chains.
4. **Protect protocol stability** — Changes that break vector parsing signal backward-incompatible protocol changes and must follow the [governance process](../docs/governance.md).

## Vectors

| File | Protocol Object | Description |
|------|----------------|-------------|
| `intent-envelope-basic.json` | `IntentEnvelope` | Minimal valid intent envelope with no provenance |
| `intent-envelope-with-provenance.json` | `IntentEnvelope` | Intent envelope with full provenance block and extensions |
| `capability-descriptor-basic.json` | `CapabilityDescriptor` | Complete capability descriptor for knowledge retrieval |
| `negotiation-result-basic.json` | `NegotiationResult` | Result of capability negotiation with ranked candidates |
| `execution-plan-basic.json` | `ExecutionPlan` | Deterministic execution plan for a RAG retrieval step |
| `audit-record-basic.json` | `AuditRecord` | Immutable audit record for a successfully processed intent |

## How SDKs Should Use These Vectors

### 1. Parse and Validate

Each SDK must be able to deserialize all vectors into the corresponding protocol objects without errors:

```python
# Python SDK
from sip.sdk.serialization import parse_intent_envelope
import json, pathlib

vector = json.loads(pathlib.Path("protocol-vectors/intent-envelope-basic.json").read_text())
envelope = parse_intent_envelope(vector)  # Must not raise
```

```go
// Go SDK
import "github.com/ansharma0923/semantic-intent-protocol/sdk/go/sip"
import "encoding/json"

data, _ := os.ReadFile("protocol-vectors/intent-envelope-basic.json")
var env sip.IntentEnvelope
json.Unmarshal(data, &env) // Must not error
```

### 2. Round-Trip Equality

After parsing a vector, serializing back to JSON (with keys sorted by field name) must produce a dict equal to the original vector. This confirms that no data is lost or transformed during parsing.

### 3. Test Suite Integration

Protocol vector tests are located in:

- Python: [`tests/protocol_vectors/`](../tests/protocol_vectors/)
- Go: [`sdk/go/tests/`](../sdk/go/tests/)

Run Python vector tests:

```bash
pytest tests/protocol_vectors/ -v
```

Run Go SDK tests:

```bash
cd sdk/go && go test ./tests/... -v
```

## SIP v0.1 Compatibility

All vectors in this directory are canonical examples for **SIP v0.1** compatibility. An implementation is considered v0.1 compatible if it can:

1. Parse all vectors without validation errors.
2. Preserve all required fields during round-trip serialization.
3. Correctly handle optional fields (`null` values, empty arrays, missing provenance).
4. Accept extensions using the `x_<name>` or `<vendor>.<name>` key format.

See [`docs/governance.md`](../docs/governance.md) for the versioning policy and backward-compatibility guarantees.
