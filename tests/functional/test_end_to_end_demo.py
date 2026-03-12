"""Functional tests for the end-to-end demo scripts.

Tests ensure that:
- python_client_demo.py runs without errors and produces valid output
- broker_federation_demo.py runs without errors and produces valid output
- SDK clients produce valid envelopes
- Federation discovery aggregates local and remote candidates

These tests exercise the complete SIP pipeline as demonstrated in the demo.
"""

from __future__ import annotations

import importlib.util
import sys
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest

from sip.broker.discovery import DiscoveryRequest, DiscoveryService
from sip.broker.federation import FederatedPeer, FederationConfig, PeerTrustLevel
from sip.broker.service import BrokerService
from sip.observability.audit import OutcomeSummary
from sip.policy.engine import PolicyEngine
from sip.registry.bootstrap import build_seeded_registry, seed_registry
from sip.registry.service import CapabilityRegistryService
from sip.sdk import (
    ActorType,
    BindingType,
    OperationClass,
    TrustLevel,
    build_actor,
    build_intent_envelope,
    build_provenance,
    validate_envelope,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_remote_caps_response() -> dict:
    """Return a minimal mock discovery response from a peer broker."""
    return {
        "candidates": [
            {
                "capability_id": "remote.analytics.cap",
                "name": "Remote Analytics Capability",
                "description": "A remote analytics capability",
                "operation_class": "analyze",
                "supported_bindings": ["rest"],
                "intent_domains": ["analytics"],
                "minimum_trust_tier": "internal",
                "score": 6.0,
                "source_broker_id": None,
                "source_broker_url": None,
                "routing_allowed": True,
                "discovery_path": [],
                "extensions": {},
            }
        ],
        "total": 1,
        "local_count": 1,
        "remote_count": 0,
        "peers_queried": [],
        "peers_failed": [],
    }


# ---------------------------------------------------------------------------
# Tests: SDK produces valid envelopes
# ---------------------------------------------------------------------------


class TestSDKProducesValidEnvelopes:
    def test_build_actor_and_envelope(self) -> None:
        actor = build_actor(
            actor_id="test-agent",
            name="Test Agent",
            actor_type=ActorType.AI_AGENT,
            trust_level=TrustLevel.INTERNAL,
            scopes=["sip:knowledge:read"],
        )
        envelope = build_intent_envelope(
            actor=actor,
            intent_name="retrieve_document",
            intent_domain="knowledge_management",
            operation_class=OperationClass.RETRIEVE,
            outcome_summary="Retrieve a test document.",
        )
        result = validate_envelope(envelope)
        assert result.valid, f"Envelope validation failed: {result.errors}"

    def test_envelope_with_provenance(self) -> None:
        actor = build_actor(
            actor_id="demo-agent",
            name="Demo Agent",
            actor_type=ActorType.AI_AGENT,
            trust_level=TrustLevel.INTERNAL,
            scopes=["sip:knowledge:read"],
        )
        provenance = build_provenance(
            originator="user-alice",
            submitted_by="demo-agent",
            delegation_chain=["user-alice"],
            authority_scope=["sip:knowledge:read"],
        )
        envelope = build_intent_envelope(
            actor=actor,
            intent_name="retrieve_document",
            intent_domain="knowledge_management",
            operation_class=OperationClass.RETRIEVE,
            outcome_summary="Retrieve with provenance.",
            provenance=provenance,
        )
        result = validate_envelope(envelope)
        assert result.valid
        assert envelope.provenance is not None
        assert envelope.provenance.originator == "user-alice"
        assert envelope.provenance.delegation_chain == ["user-alice"]


# ---------------------------------------------------------------------------
# Tests: Python client demo flow (inline, no subprocess)
# ---------------------------------------------------------------------------


class TestPythonClientDemoFlow:
    """Test the full pipeline demonstrated in python_client_demo.py."""

    def _run_demo_pipeline(self) -> dict:
        """Run the python_client_demo flow and return key results."""
        actor = build_actor(
            actor_id="demo-agent-001",
            name="Demo AI Agent",
            actor_type=ActorType.AI_AGENT,
            trust_level=TrustLevel.INTERNAL,
            scopes=["sip:knowledge:read"],
        )
        provenance = build_provenance(
            originator="user-alice",
            submitted_by="demo-agent-001",
            delegation_chain=["user-alice"],
            delegation_purpose="Automated knowledge retrieval",
            authority_scope=["sip:knowledge:read"],
        )
        envelope = build_intent_envelope(
            actor=actor,
            intent_name="retrieve_document",
            intent_domain="knowledge_management",
            operation_class=OperationClass.RETRIEVE,
            outcome_summary="Retrieve the SIP architecture document.",
            target_id="sip.knowledge.retrieve",
            intent_parameters={"document_id": "arch-doc-001"},
            provenance=provenance,
        )

        broker = BrokerService(
            registry=build_seeded_registry(),
            policy_engine=PolicyEngine(enforce_approval_policy=False),
        )
        result = broker.handle(envelope)
        return {
            "result": result,
            "envelope": envelope,
            "provenance": provenance,
        }

    def test_broker_result_has_audit_record(self) -> None:
        data = self._run_demo_pipeline()
        assert data["result"].audit_record is not None

    def test_audit_record_outcome_is_success(self) -> None:
        data = self._run_demo_pipeline()
        assert data["result"].audit_record.outcome_summary == OutcomeSummary.SUCCESS

    def test_audit_record_preserves_provenance(self) -> None:
        data = self._run_demo_pipeline()
        audit = data["result"].audit_record
        assert audit.originator == "user-alice"
        assert audit.submitting_actor == "demo-agent-001"
        assert "user-alice" in audit.delegation_chain

    def test_negotiation_result_has_candidates(self) -> None:
        data = self._run_demo_pipeline()
        neg = data["result"].negotiation_result
        assert neg is not None
        assert len(neg.ranked_candidates) > 0

    def test_negotiation_result_has_selected_capability(self) -> None:
        data = self._run_demo_pipeline()
        neg = data["result"].negotiation_result
        assert neg.selected_capability is not None
        assert neg.selected_capability.capability_id is not None

    def test_execution_plan_created(self) -> None:
        data = self._run_demo_pipeline()
        plan = data["result"].execution_plan
        assert plan is not None
        assert plan.plan_id is not None

    def test_execution_plan_has_steps(self) -> None:
        data = self._run_demo_pipeline()
        plan = data["result"].execution_plan
        assert len(plan.execution_steps) > 0

    def test_execution_plan_selected_binding(self) -> None:
        data = self._run_demo_pipeline()
        plan = data["result"].execution_plan
        assert plan.selected_binding is not None

    def test_policy_allowed(self) -> None:
        data = self._run_demo_pipeline()
        assert data["result"].audit_record.policy_allowed is True


# ---------------------------------------------------------------------------
# Tests: Federation discovery
# ---------------------------------------------------------------------------


class TestFederationDiscovery:
    """Test the federation discovery demonstrated in broker_federation_demo.py."""

    def _make_federation_service(
        self, trust_level: PeerTrustLevel
    ) -> DiscoveryService:
        registry = CapabilityRegistryService()
        seed_registry(registry)
        federation = FederationConfig(
            broker_id="broker-a",
            broker_url="http://broker-a.example.com",
            peers=[
                FederatedPeer(
                    broker_id="broker-b",
                    broker_url="http://broker-b.example.com",
                    trust_level=trust_level,
                )
            ],
        )
        return DiscoveryService(
            registry=registry,
            federation=federation,
            local_broker_id="broker-a",
        )

    def test_routing_peer_candidates_are_routing_allowed(self) -> None:
        svc = self._make_federation_service(PeerTrustLevel.ROUTING)
        mock_resp = MagicMock()
        mock_resp.json.return_value = _make_remote_caps_response()
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.post", return_value=mock_resp):
            response = svc.discover(DiscoveryRequest(max_results=100))

        remote = [c for c in response.candidates if c.source_broker_id]
        assert len(remote) > 0
        for c in remote:
            assert c.routing_allowed is True

    def test_discovery_peer_candidates_are_not_routing_allowed(self) -> None:
        svc = self._make_federation_service(PeerTrustLevel.DISCOVERY)
        mock_resp = MagicMock()
        mock_resp.json.return_value = _make_remote_caps_response()
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.post", return_value=mock_resp):
            response = svc.discover(DiscoveryRequest(max_results=100))

        remote = [c for c in response.candidates if c.source_broker_id]
        assert len(remote) > 0
        for c in remote:
            assert c.routing_allowed is False

    def test_aggregated_response_counts_local_and_remote(self) -> None:
        registry = CapabilityRegistryService()
        seed_registry(registry)
        local_count = registry.count()

        svc = self._make_federation_service(PeerTrustLevel.ROUTING)
        mock_resp = MagicMock()
        mock_resp.json.return_value = _make_remote_caps_response()
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.post", return_value=mock_resp):
            response = svc.discover(DiscoveryRequest(max_results=100))

        assert response.remote_count == 1
        assert response.total == local_count + 1

    def test_remote_candidate_has_source_broker_id(self) -> None:
        svc = self._make_federation_service(PeerTrustLevel.ROUTING)
        mock_resp = MagicMock()
        mock_resp.json.return_value = _make_remote_caps_response()
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.post", return_value=mock_resp):
            response = svc.discover(DiscoveryRequest(max_results=100))

        remote = [c for c in response.candidates if c.source_broker_id]
        assert len(remote) > 0
        for c in remote:
            assert c.source_broker_id == "broker-b"

    def test_remote_candidate_discovery_path_contains_peer_id(self) -> None:
        svc = self._make_federation_service(PeerTrustLevel.ROUTING)
        mock_resp = MagicMock()
        mock_resp.json.return_value = _make_remote_caps_response()
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.post", return_value=mock_resp):
            response = svc.discover(DiscoveryRequest(max_results=100))

        remote = [c for c in response.candidates if c.source_broker_id]
        for c in remote:
            assert "broker-b" in c.discovery_path

    def test_no_federation_returns_only_local(self) -> None:
        registry = CapabilityRegistryService()
        seed_registry(registry)
        svc = DiscoveryService(registry=registry, federation=None)
        response = svc.discover(DiscoveryRequest(max_results=100))
        assert response.remote_count == 0
        assert response.total == registry.count()


# ---------------------------------------------------------------------------
# Tests: Demo scripts run via importlib (smoke tests)
# ---------------------------------------------------------------------------


class TestDemoScriptsRun:
    """Verify that demo scripts can be executed without unhandled exceptions."""

    def test_python_client_demo_runs(self, capsys: pytest.CaptureFixture) -> None:
        """python_client_demo.py should run to completion without errors."""
        import examples.end_to_end_demo.python_client_demo as demo  # noqa: F401

        demo.main()
        captured = capsys.readouterr()
        assert "Demo complete." in captured.out
        assert "NegotiationResult" in captured.out
        assert "ExecutionPlan" in captured.out
        assert "AuditRecord" in captured.out

    def test_broker_federation_demo_runs(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """broker_federation_demo.py should run to completion without errors."""
        import examples.end_to_end_demo.broker_federation_demo as demo  # noqa: F401

        mock_resp = MagicMock()
        mock_resp.json.return_value = _make_remote_caps_response()
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.post", return_value=mock_resp):
            demo.main()

        captured = capsys.readouterr()
        assert "Demo complete." in captured.out
        assert "Federation" in captured.out
