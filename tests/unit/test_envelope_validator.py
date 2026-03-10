"""Unit tests for IntentEnvelope validation."""

from __future__ import annotations

from sip.envelope.models import (
    ActorDescriptor,
    ActorType,
    BindingType,
    Constraints,
    DataSensitivity,
    DesiredOutcome,
    DeterminismLevel,
    IntentEnvelope,
    IntentPayload,
    OperationClass,
    ProtocolBinding,
    TargetDescriptor,
    TargetType,
    TrustLevel,
)
from sip.envelope.validator import ValidationResult, validate_envelope


def _make_envelope(
    operation_class: OperationClass = OperationClass.RETRIEVE,
    trust_level: TrustLevel = TrustLevel.INTERNAL,
    allowed_actions: list[str] | None = None,
    forbidden_actions: list[str] | None = None,
    bindings: list[BindingType] | None = None,
    time_budget_ms: int | None = None,
    cost_budget: float | None = None,
    determinism: DeterminismLevel = DeterminismLevel.STRICT,
    data_sensitivity: DataSensitivity = DataSensitivity.INTERNAL,
) -> IntentEnvelope:
    constraints = Constraints(
        allowed_actions=allowed_actions or [],
        forbidden_actions=forbidden_actions or [],
        time_budget_ms=time_budget_ms,
        cost_budget=cost_budget,
        determinism_required=determinism,
        data_sensitivity=data_sensitivity,
    )
    protocol_bindings = (
        [ProtocolBinding(binding_type=b) for b in bindings]
        if bindings
        else []
    )
    return IntentEnvelope(
        actor=ActorDescriptor(
            actor_id="validator-test",
            actor_type=ActorType.SERVICE,
            name="Validator Test",
            trust_level=trust_level,
        ),
        target=TargetDescriptor(target_type=TargetType.CAPABILITY),
        intent=IntentPayload(
            intent_name="test_intent",
            intent_domain="test_domain",
            operation_class=operation_class,
        ),
        desired_outcome=DesiredOutcome(summary="Test"),
        constraints=constraints,
        protocol_bindings=protocol_bindings,
    )


class TestEnvelopeValidator:
    def test_valid_envelope_passes(self) -> None:
        envelope = _make_envelope()
        result = validate_envelope(envelope)
        assert result.valid is True
        assert result.errors == []

    def test_valid_write_with_internal_trust(self) -> None:
        envelope = _make_envelope(
            operation_class=OperationClass.WRITE,
            trust_level=TrustLevel.INTERNAL,
        )
        result = validate_envelope(envelope)
        assert result.valid is True

    def test_write_with_public_trust_is_denied(self) -> None:
        envelope = _make_envelope(
            operation_class=OperationClass.WRITE,
            trust_level=TrustLevel.PUBLIC,
        )
        result = validate_envelope(envelope)
        assert result.valid is False
        assert any("trust" in e.lower() for e in result.errors)

    def test_execute_with_public_trust_is_denied(self) -> None:
        envelope = _make_envelope(
            operation_class=OperationClass.EXECUTE,
            trust_level=TrustLevel.PUBLIC,
        )
        result = validate_envelope(envelope)
        assert result.valid is False

    def test_conflicting_allowed_and_forbidden_actions(self) -> None:
        envelope = _make_envelope(
            allowed_actions=["read", "write"],
            forbidden_actions=["write"],
        )
        result = validate_envelope(envelope)
        assert result.valid is False
        assert any("appear" in e.lower() or "conflict" in e.lower() or "both" in e.lower() for e in result.errors)

    def test_no_conflict_when_allowed_and_forbidden_are_disjoint(self) -> None:
        envelope = _make_envelope(
            allowed_actions=["read"],
            forbidden_actions=["write"],
        )
        result = validate_envelope(envelope)
        assert result.valid is True

    def test_rest_binding_is_valid(self) -> None:
        envelope = _make_envelope(bindings=[BindingType.REST])
        result = validate_envelope(envelope)
        assert result.valid is True

    def test_all_valid_bindings(self) -> None:
        for bt in BindingType:
            envelope = _make_envelope(bindings=[bt])
            result = validate_envelope(envelope)
            assert result.valid is True, f"Binding {bt} failed: {result.errors}"

    def test_advisory_determinism_with_write_generates_warning(self) -> None:
        envelope = _make_envelope(
            operation_class=OperationClass.WRITE,
            trust_level=TrustLevel.INTERNAL,
            determinism=DeterminismLevel.ADVISORY,
        )
        result = validate_envelope(envelope)
        assert result.valid is True
        assert len(result.warnings) > 0
        assert any("advisory" in w.lower() for w in result.warnings)

    def test_result_add_error_sets_invalid(self) -> None:
        result = ValidationResult(valid=True)
        result.add_error("Something failed")
        assert result.valid is False
        assert "Something failed" in result.errors

    def test_result_add_warning_does_not_invalidate(self) -> None:
        result = ValidationResult(valid=True)
        result.add_warning("Something is suspicious")
        assert result.valid is True
        assert "Something is suspicious" in result.warnings


class TestValidatorCleanup:
    """Ensure removed dead checks are truly gone and remaining checks still work."""

    def test_unsupported_sip_version_fails(self) -> None:
        """Version check must still detect unknown versions."""
        envelope = _make_envelope()
        # model_copy to override the frozen field
        bad_version_envelope = envelope.model_copy(update={"sip_version": "99.0"})
        result = validate_envelope(bad_version_envelope)
        assert result.valid is False
        assert any("sip_version" in e or "Unsupported" in e for e in result.errors)

    def test_declared_trust_exceeds_actor_trust_is_warning(self) -> None:
        """Declared trust > actor trust must generate a warning, not an error."""
        from sip.envelope.models import TrustBlock
        envelope = _make_envelope(trust_level=TrustLevel.INTERNAL)
        # admin declared but actor is only internal
        envelope_elevated = envelope.model_copy(
            update={"trust": TrustBlock(declared_trust_level=TrustLevel.ADMIN)}
        )
        result = validate_envelope(envelope_elevated)
        assert result.valid is True
        assert len(result.warnings) > 0
        assert any("declared_trust_level" in w for w in result.warnings)

    def test_action_conflict_detected(self) -> None:
        envelope = _make_envelope(
            allowed_actions=["action_x", "action_y"],
            forbidden_actions=["action_y"],
        )
        result = validate_envelope(envelope)
        assert result.valid is False
        assert any("action_y" in e for e in result.errors)
