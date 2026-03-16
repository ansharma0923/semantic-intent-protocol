"""Schema validation tests for the Semantic Intent Protocol.

These tests validate that every canonical protocol vector in protocol-vectors/
conforms to the corresponding JSON Schema in schema/.

They ensure that:
1. Protocol vectors are valid according to the formal schemas.
2. The schemas and implementation stay aligned.
3. New implementations can use the schemas to validate compatibility.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

# Root directory of the repository
ROOT_DIR = Path(__file__).parent.parent.parent

# Directories
SCHEMA_DIR = ROOT_DIR / "schema"
VECTORS_DIR = ROOT_DIR / "protocol-vectors"

# ---------------------------------------------------------------------------
# Canonical enum values shared across multiple SIP schemas.
# These constants are the authoritative source for cross-schema consistency
# tests. If the protocol adds new bindings or trust levels, update these
# constants and the corresponding schema files together.
# ---------------------------------------------------------------------------

#: Execution protocol bindings defined by SIP v0.1.
CANONICAL_BINDINGS: frozenset[str] = frozenset({"rest", "grpc", "mcp", "a2a", "rag"})

#: Actor trust tiers defined by SIP v0.1.
CANONICAL_TRUST_LEVELS: frozenset[str] = frozenset({"public", "internal", "privileged", "admin"})


def _load_schema(filename: str) -> dict:
    """Load a JSON Schema file."""
    path = SCHEMA_DIR / filename
    assert path.exists(), f"Schema not found: {path}"
    return json.loads(path.read_text(encoding="utf-8"))


def _load_vector(filename: str) -> dict:
    """Load a protocol vector JSON file."""
    path = VECTORS_DIR / filename
    assert path.exists(), f"Protocol vector not found: {path}"
    return json.loads(path.read_text(encoding="utf-8"))


def _validate(instance: dict, schema: dict) -> None:
    """Validate an instance against a schema, raising AssertionError on failure."""
    validator = jsonschema.Draft202012Validator(schema)
    errors = list(validator.iter_errors(instance))
    if errors:
        messages = "\n".join(
            f"  [{e.json_path}] {e.message}" for e in errors
        )
        pytest.fail(f"Schema validation failed:\n{messages}")


# ---------------------------------------------------------------------------
# IntentEnvelope schemas
# ---------------------------------------------------------------------------


class TestIntentEnvelopeSchemaValidation:
    """Validate IntentEnvelope protocol vectors against the schema."""

    schema_file = "sip-intent-envelope.schema.json"

    def test_schema_file_exists(self) -> None:
        assert (SCHEMA_DIR / self.schema_file).exists()

    def test_intent_envelope_basic_is_valid(self) -> None:
        schema = _load_schema(self.schema_file)
        vector = _load_vector("intent-envelope-basic.json")
        _validate(vector, schema)

    def test_intent_envelope_with_provenance_is_valid(self) -> None:
        schema = _load_schema(self.schema_file)
        vector = _load_vector("intent-envelope-with-provenance.json")
        _validate(vector, schema)

    def test_schema_rejects_missing_required_fields(self) -> None:
        """A document missing required top-level fields must fail validation."""
        schema = _load_schema(self.schema_file)
        incomplete = {
            "sip_version": "0.1",
            "message_type": "intent_request",
            # Missing: intent_id, actor, target, intent, desired_outcome
        }
        validator = jsonschema.Draft202012Validator(schema)
        errors = list(validator.iter_errors(incomplete))
        assert len(errors) > 0, "Expected validation errors for incomplete document"

    def test_schema_rejects_invalid_message_type(self) -> None:
        """message_type must be one of the allowed enum values."""
        schema = _load_schema(self.schema_file)
        vector = _load_vector("intent-envelope-basic.json")
        vector["message_type"] = "not_a_valid_type"
        validator = jsonschema.Draft202012Validator(schema)
        errors = list(validator.iter_errors(vector))
        assert len(errors) > 0, "Expected validation error for invalid message_type"

    def test_schema_rejects_invalid_trust_level(self) -> None:
        """actor.trust_level must be one of the allowed enum values."""
        schema = _load_schema(self.schema_file)
        vector = _load_vector("intent-envelope-basic.json")
        vector["actor"]["trust_level"] = "superuser"
        validator = jsonschema.Draft202012Validator(schema)
        errors = list(validator.iter_errors(vector))
        assert len(errors) > 0, "Expected validation error for invalid trust_level"

    def test_schema_rejects_invalid_operation_class(self) -> None:
        """intent.operation_class must be one of the allowed enum values."""
        schema = _load_schema(self.schema_file)
        vector = _load_vector("intent-envelope-basic.json")
        vector["intent"]["operation_class"] = "unknown_operation"
        validator = jsonschema.Draft202012Validator(schema)
        errors = list(validator.iter_errors(vector))
        assert len(errors) > 0, "Expected validation error for invalid operation_class"


# ---------------------------------------------------------------------------
# CapabilityDescriptor schema
# ---------------------------------------------------------------------------


class TestCapabilityDescriptorSchemaValidation:
    """Validate CapabilityDescriptor protocol vectors against the schema."""

    schema_file = "sip-capability-descriptor.schema.json"

    def test_schema_file_exists(self) -> None:
        assert (SCHEMA_DIR / self.schema_file).exists()

    def test_capability_descriptor_basic_is_valid(self) -> None:
        schema = _load_schema(self.schema_file)
        vector = _load_vector("capability-descriptor-basic.json")
        _validate(vector, schema)

    def test_schema_rejects_invalid_risk_level(self) -> None:
        """risk_level must be one of the allowed enum values."""
        schema = _load_schema(self.schema_file)
        vector = _load_vector("capability-descriptor-basic.json")
        vector["risk_level"] = "extreme"
        validator = jsonschema.Draft202012Validator(schema)
        errors = list(validator.iter_errors(vector))
        assert len(errors) > 0, "Expected validation error for invalid risk_level"

    def test_schema_rejects_invalid_binding(self) -> None:
        """supported_bindings items must be one of the allowed enum values."""
        schema = _load_schema(self.schema_file)
        vector = _load_vector("capability-descriptor-basic.json")
        vector["supported_bindings"] = ["unknown_binding"]
        validator = jsonschema.Draft202012Validator(schema)
        errors = list(validator.iter_errors(vector))
        assert len(errors) > 0, "Expected validation error for invalid binding"

    def test_schema_rejects_missing_required_fields(self) -> None:
        """A document missing required fields must fail validation."""
        schema = _load_schema(self.schema_file)
        incomplete = {
            "capability_id": "sip.test",
            "name": "Test",
            # Missing: description, intent_domains, operation_class, risk_level,
            #          required_scopes, minimum_trust_tier, supported_bindings
        }
        validator = jsonschema.Draft202012Validator(schema)
        errors = list(validator.iter_errors(incomplete))
        assert len(errors) > 0, "Expected validation errors for incomplete document"


# ---------------------------------------------------------------------------
# NegotiationResult schema
# ---------------------------------------------------------------------------


class TestNegotiationResultSchemaValidation:
    """Validate NegotiationResult protocol vectors against the schema."""

    schema_file = "sip-negotiation-result.schema.json"

    def test_schema_file_exists(self) -> None:
        assert (SCHEMA_DIR / self.schema_file).exists()

    def test_negotiation_result_basic_is_valid(self) -> None:
        schema = _load_schema(self.schema_file)
        vector = _load_vector("negotiation-result-basic.json")
        _validate(vector, schema)

    def test_schema_rejects_score_out_of_range(self) -> None:
        """Candidate score must be between 0.0 and 1.0."""
        schema = _load_schema(self.schema_file)
        vector = _load_vector("negotiation-result-basic.json")
        vector["ranked_candidates"][0]["score"] = 1.5
        validator = jsonschema.Draft202012Validator(schema)
        errors = list(validator.iter_errors(vector))
        assert len(errors) > 0, "Expected validation error for score > 1.0"

    def test_schema_rejects_invalid_selected_binding(self) -> None:
        """selected_binding must be one of the allowed enum values or null."""
        schema = _load_schema(self.schema_file)
        vector = _load_vector("negotiation-result-basic.json")
        vector["selected_binding"] = "telnet"
        validator = jsonschema.Draft202012Validator(schema)
        errors = list(validator.iter_errors(vector))
        assert len(errors) > 0, "Expected validation error for invalid selected_binding"


# ---------------------------------------------------------------------------
# ExecutionPlan schema
# ---------------------------------------------------------------------------


class TestExecutionPlanSchemaValidation:
    """Validate ExecutionPlan protocol vectors against the schema."""

    schema_file = "sip-execution-plan.schema.json"

    def test_schema_file_exists(self) -> None:
        assert (SCHEMA_DIR / self.schema_file).exists()

    def test_execution_plan_basic_is_valid(self) -> None:
        schema = _load_schema(self.schema_file)
        vector = _load_vector("execution-plan-basic.json")
        _validate(vector, schema)

    def test_schema_rejects_empty_execution_steps(self) -> None:
        """execution_steps must have at least one step."""
        schema = _load_schema(self.schema_file)
        vector = _load_vector("execution-plan-basic.json")
        vector["execution_steps"] = []
        validator = jsonschema.Draft202012Validator(schema)
        errors = list(validator.iter_errors(vector))
        assert len(errors) > 0, "Expected validation error for empty execution_steps"

    def test_schema_rejects_invalid_policy_check_result(self) -> None:
        """policy_checks_passed[].result must be one of the allowed enum values."""
        schema = _load_schema(self.schema_file)
        vector = _load_vector("execution-plan-basic.json")
        vector["policy_checks_passed"][0]["result"] = "unknown"
        validator = jsonschema.Draft202012Validator(schema)
        errors = list(validator.iter_errors(vector))
        assert len(errors) > 0, "Expected validation error for invalid policy check result"


# ---------------------------------------------------------------------------
# AuditRecord schema
# ---------------------------------------------------------------------------


class TestAuditRecordSchemaValidation:
    """Validate AuditRecord protocol vectors against the schema."""

    schema_file = "sip-audit-record.schema.json"

    def test_schema_file_exists(self) -> None:
        assert (SCHEMA_DIR / self.schema_file).exists()

    def test_audit_record_basic_is_valid(self) -> None:
        schema = _load_schema(self.schema_file)
        vector = _load_vector("audit-record-basic.json")
        _validate(vector, schema)

    def test_schema_rejects_invalid_action_taken(self) -> None:
        """action_taken must be one of the allowed enum values."""
        schema = _load_schema(self.schema_file)
        vector = _load_vector("audit-record-basic.json")
        vector["action_taken"] = "unknown_action"
        validator = jsonschema.Draft202012Validator(schema)
        errors = list(validator.iter_errors(vector))
        assert len(errors) > 0, "Expected validation error for invalid action_taken"

    def test_schema_rejects_invalid_outcome_summary(self) -> None:
        """outcome_summary must be one of the allowed enum values."""
        schema = _load_schema(self.schema_file)
        vector = _load_vector("audit-record-basic.json")
        vector["outcome_summary"] = "unknown_outcome"
        validator = jsonschema.Draft202012Validator(schema)
        errors = list(validator.iter_errors(vector))
        assert len(errors) > 0, "Expected validation error for invalid outcome_summary"

    def test_schema_rejects_missing_required_fields(self) -> None:
        """A document missing required fields must fail validation."""
        schema = _load_schema(self.schema_file)
        incomplete = {
            "audit_id": "some-id",
            "timestamp": "2024-01-15T10:00:05Z",
            # Missing many required fields
        }
        validator = jsonschema.Draft202012Validator(schema)
        errors = list(validator.iter_errors(incomplete))
        assert len(errors) > 0, "Expected validation errors for incomplete document"


# ---------------------------------------------------------------------------
# Cross-schema consistency
# ---------------------------------------------------------------------------


class TestSchemaCrossConsistency:
    """Tests that verify consistency properties across multiple schemas."""

    def test_all_schema_files_are_valid_json(self) -> None:
        """Every schema file in schema/ must be valid JSON."""
        schema_files = list(SCHEMA_DIR.glob("*.json"))
        assert len(schema_files) > 0, "No schema files found in schema/"
        for schema_path in schema_files:
            try:
                json.loads(schema_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                pytest.fail(f"Schema file {schema_path.name} is not valid JSON: {exc}")

    def test_all_schema_files_have_required_fields(self) -> None:
        """Every schema must have $schema, $id, title, and description."""
        schema_files = list(SCHEMA_DIR.glob("*.json"))
        for schema_path in schema_files:
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            for field in ("$schema", "$id", "title", "description"):
                assert field in schema, (
                    f"Schema {schema_path.name} is missing required meta-field '{field}'"
                )

    def test_binding_enums_are_consistent(self) -> None:
        """The allowed binding values must be the same across all schemas."""
        envelope_schema = _load_schema("sip-intent-envelope.schema.json")
        pb = envelope_schema["$defs"]["ProtocolBinding"]["properties"]["binding_type"]["enum"]
        assert set(pb) == CANONICAL_BINDINGS, f"ProtocolBinding enum mismatch: {pb}"

        cap_schema = _load_schema("sip-capability-descriptor.schema.json")
        sb = cap_schema["properties"]["supported_bindings"]["items"]["enum"]
        assert set(sb) == CANONICAL_BINDINGS, f"CapabilityDescriptor binding enum mismatch: {sb}"

        exec_schema = _load_schema("sip-execution-plan.schema.json")
        eb = exec_schema["properties"]["selected_binding"]["enum"]
        assert set(eb) == CANONICAL_BINDINGS, f"ExecutionPlan binding enum mismatch: {eb}"

    def test_trust_level_enums_are_consistent(self) -> None:
        """The allowed trust level values must be the same across all schemas."""
        envelope_schema = _load_schema("sip-intent-envelope.schema.json")
        tl = envelope_schema["$defs"]["ActorDescriptor"]["properties"]["trust_level"]["enum"]
        assert set(tl) == CANONICAL_TRUST_LEVELS, f"ActorDescriptor trust_level enum mismatch: {tl}"

        cap_schema = _load_schema("sip-capability-descriptor.schema.json")
        mt = cap_schema["properties"]["minimum_trust_tier"]["enum"]
        assert set(mt) == CANONICAL_TRUST_LEVELS, f"CapabilityDescriptor trust tier enum mismatch: {mt}"
