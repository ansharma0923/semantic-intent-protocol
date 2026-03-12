"""Tests for public SDK imports from sip.sdk."""

from __future__ import annotations


class TestPublicImports:
    """Verify that all documented public symbols are importable from sip.sdk."""

    def test_error_classes_importable(self) -> None:
        from sip.sdk import SIPClientError, SIPError, SIPHTTPError, SIPValidationError

        assert issubclass(SIPClientError, SIPError)
        assert issubclass(SIPHTTPError, SIPClientError)
        assert issubclass(SIPValidationError, SIPError)

    def test_envelope_models_importable(self) -> None:
        from sip.sdk import (
            ActorDescriptor,
            IntentEnvelope,
            ProvenanceBlock,
        )

        assert IntentEnvelope is not None
        assert ActorDescriptor is not None
        assert ProvenanceBlock is not None

    def test_envelope_enums_importable(self) -> None:
        from sip.sdk import (
            ActorType,
            BindingType,
            OperationClass,
            TrustLevel,
        )

        assert ActorType.SERVICE.value == "service"
        assert BindingType.REST.value == "rest"
        assert TrustLevel.INTERNAL.value == "internal"
        assert OperationClass.RETRIEVE.value == "retrieve"

    def test_registry_models_importable(self) -> None:
        from sip.sdk import (
            CapabilityDescriptor,
            RiskLevel,
        )

        assert CapabilityDescriptor is not None
        assert RiskLevel.LOW.value == "low"

    def test_negotiation_models_importable(self) -> None:
        from sip.sdk import (
            ExecutionPlan,
            NegotiationResult,
        )

        assert NegotiationResult is not None
        assert ExecutionPlan is not None

    def test_observability_models_importable(self) -> None:
        from sip.sdk import ActionTaken, AuditRecord, OutcomeSummary

        assert AuditRecord is not None
        assert ActionTaken.PLAN_CREATED.value == "plan_created"
        assert OutcomeSummary.SUCCESS.value == "success"

    def test_discovery_models_importable(self) -> None:
        from sip.sdk import DiscoveryRequest, DiscoveryResponse

        assert DiscoveryRequest is not None
        assert DiscoveryResponse is not None

    def test_federation_models_importable(self) -> None:
        from sip.sdk import (
            FederationConfig,
        )

        assert FederationConfig is not None

    def test_validation_importable(self) -> None:
        from sip.sdk import validate_envelope

        assert callable(validate_envelope)

    def test_serialization_importable(self) -> None:
        from sip.sdk import (
            parse_intent_envelope,
            to_dict,
            to_json,
        )

        assert callable(to_dict)
        assert callable(to_json)
        assert callable(parse_intent_envelope)

    def test_builders_importable(self) -> None:
        from sip.sdk import (
            build_actor,
            build_intent_envelope,
        )

        assert callable(build_actor)
        assert callable(build_intent_envelope)

    def test_clients_importable(self) -> None:
        from sip.sdk import BrokerClient, CapabilityDiscoveryClient

        assert BrokerClient is not None
        assert CapabilityDiscoveryClient is not None

    def test_helpers_importable(self) -> None:
        from sip.sdk import (
            apply_identity_headers_to_envelope,
            compute_effective_scope_set,
            summarize_provenance,
        )

        assert callable(apply_identity_headers_to_envelope)
        assert callable(compute_effective_scope_set)
        assert callable(summarize_provenance)

    def test_all_exports_present(self) -> None:
        """Verify __all__ is defined and non-empty."""
        import sip.sdk as sdk

        assert hasattr(sdk, "__all__")
        assert len(sdk.__all__) > 30  # sanity check
