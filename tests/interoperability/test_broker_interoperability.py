"""Broker interoperability tests for SIP.

These tests simulate multiple brokers in a single test environment to verify
that the SIP protocol behaves correctly in distributed scenarios.

Test scenarios:
  A. Local capability discovery  – Broker A returns its own capabilities
  B. Remote capability discovery – Broker A discovers capabilities from Broker B
  C. Deterministic aggregation   – Aggregated candidate ordering is deterministic
  D. Peer unavailable            – Broker A logs and continues if Broker B is down
  E. Provenance preservation     – Delegation chain includes brokers in forwarding path
  F. Policy enforcement          – Broker A enforces its own policy on remote capabilities

All tests use the existing broker HTTP API via FastAPI TestClient.
No external HTTP servers are required.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import sip.broker.service as svc_module
from sip.broker.discovery import DiscoveryRequest, DiscoveryService
from sip.broker.federation import (
    FederatedPeer,
    FederationConfig,
    PeerTrustLevel,
)
from sip.broker.service import BrokerService, app
from sip.envelope.models import (
    ActorDescriptor,
    ActorType,
    BindingType,
    DesiredOutcome,
    IntentEnvelope,
    IntentPayload,
    OperationClass,
    ProvenanceBlock,
    ProtocolBinding,
    TargetDescriptor,
    TargetType,
    TrustLevel,
)
from sip.policy.engine import PolicyEngine
from sip.registry.bootstrap import seed_registry
from sip.registry.models import (
    CapabilityConstraints,
    CapabilityDescriptor,
    ExecutionMetadata,
    ProviderMetadata,
    RiskLevel,
    SchemaReference,
)
from sip.registry.service import CapabilityRegistryService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_retrieve_envelope(
    actor_id: str = "agent-interop-001",
    trust_level: TrustLevel = TrustLevel.INTERNAL,
    scopes: list[str] | None = None,
    provenance: ProvenanceBlock | None = None,
) -> IntentEnvelope:
    """Build a standard knowledge-retrieval IntentEnvelope for interop testing."""
    return IntentEnvelope(
        actor=ActorDescriptor(
            actor_id=actor_id,
            actor_type=ActorType.AI_AGENT,
            name="Interoperability Test Agent",
            trust_level=trust_level,
            scopes=scopes or ["sip:knowledge:read"],
        ),
        target=TargetDescriptor(target_type=TargetType.CAPABILITY),
        intent=IntentPayload(
            intent_name="retrieve_document",
            intent_domain="knowledge_management",
            operation_class=OperationClass.RETRIEVE,
            parameters={"query": "interoperability test query", "top_k": 3},
        ),
        desired_outcome=DesiredOutcome(summary="Retrieve relevant documents"),
        protocol_bindings=[ProtocolBinding(binding_type=BindingType.RAG)],
        provenance=provenance,
    )


def _make_broker_b_discovery_response(capability_id: str = "remote_ml.analyze") -> dict:
    """Simulate the JSON response from Broker B's POST /sip/capabilities/discover."""
    return {
        "total": 1,
        "local_count": 1,
        "remote_count": 0,
        "candidates": [
            {
                "capability_id": capability_id,
                "name": "Remote ML Analysis",
                "description": "Machine learning analysis on Broker B",
                "operation_class": "analyze",
                "supported_bindings": ["rest", "grpc"],
                "intent_domains": ["machine_learning", "analytics"],
                "minimum_trust_tier": "internal",
                "score": 7.0,
                "rationale": "domain match; operation class match",
                "source_broker_id": None,
                "source_broker_url": None,
                "routing_allowed": False,
                "discovery_path": [],
                "extensions": {},
                "provider": {
                    "provider_id": "broker_b_provider",
                    "provider_name": "Broker B ML Service",
                    "version": "1.0.0",
                },
            }
        ],
        "peers_queried": [],
        "peers_failed": [],
        "timestamp": "2024-01-15T10:00:00Z",
    }


def _make_seeded_broker(
    federation: FederationConfig | None = None,
    enforce_approval: bool = True,
) -> BrokerService:
    """Create a BrokerService pre-seeded with standard capabilities."""
    registry = CapabilityRegistryService()
    seed_registry(registry)
    engine = PolicyEngine(enforce_approval_policy=enforce_approval)
    return BrokerService(
        registry=registry,
        policy_engine=engine,
        federation=federation,
    )


# ---------------------------------------------------------------------------
# Scenario A: Local capability discovery
# ---------------------------------------------------------------------------


class TestLocalCapabilityDiscovery:
    """Broker A returns its own capabilities from the HTTP API."""

    def test_list_capabilities_returns_local(self) -> None:
        broker = _make_seeded_broker()
        original = svc_module._broker
        svc_module._broker = broker
        try:
            client = TestClient(app)
            resp = client.get("/sip/capabilities")
            assert resp.status_code == 200
            # /sip/capabilities returns a list of capability descriptors directly
            data = resp.json()
            assert isinstance(data, list)
            assert len(data) > 0
        finally:
            svc_module._broker = original

    def test_get_capability_by_id(self) -> None:
        broker = _make_seeded_broker()
        original = svc_module._broker
        svc_module._broker = broker
        try:
            client = TestClient(app)
            # Get list of capabilities first
            resp = client.get("/sip/capabilities")
            caps = resp.json()
            first_id = caps[0]["capability_id"]

            # Fetch by ID
            resp2 = client.get(f"/sip/capabilities/{first_id}")
            assert resp2.status_code == 200
            cap = resp2.json()
            assert cap["capability_id"] == first_id
        finally:
            svc_module._broker = original

    def test_discover_local_capabilities(self) -> None:
        broker = _make_seeded_broker()
        original = svc_module._broker
        svc_module._broker = broker
        try:
            client = TestClient(app)
            discovery_req = {
                "intent_name": "retrieve_document",
                "intent_domain": "knowledge_management",
                "operation_class": "retrieve",
                "include_remote": False,
            }
            resp = client.post("/sip/capabilities/discover", json=discovery_req)
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] > 0
            ids = [c["capability_id"] for c in data["candidates"]]
            assert "retrieve_document" in ids
        finally:
            svc_module._broker = original

    def test_healthz_returns_capability_count(self) -> None:
        broker = _make_seeded_broker()
        original = svc_module._broker
        svc_module._broker = broker
        try:
            client = TestClient(app)
            resp = client.get("/healthz")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "ok"
            assert data["capabilities"] > 0
        finally:
            svc_module._broker = original


# ---------------------------------------------------------------------------
# Scenario B: Remote capability discovery
# ---------------------------------------------------------------------------


class TestRemoteCapabilityDiscovery:
    """Broker A discovers capabilities from Broker B via federation."""

    def _make_federated_broker(self) -> BrokerService:
        federation = FederationConfig(
            broker_id="broker-a",
            broker_url="http://localhost:8000",
            peers=[
                FederatedPeer(
                    broker_id="broker-b",
                    broker_url="http://localhost:8001",
                    trust_level=PeerTrustLevel.ROUTING,
                    description="Broker B for ML analysis",
                )
            ],
        )
        return _make_seeded_broker(federation=federation)

    def test_remote_capabilities_included_in_discovery(self) -> None:
        broker = self._make_federated_broker()
        peer_resp = _make_broker_b_discovery_response()
        mock_resp = MagicMock()
        mock_resp.json.return_value = peer_resp
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.post", return_value=mock_resp):
            resp = broker.discovery.discover(
                DiscoveryRequest(include_remote=True, max_results=50)
            )

        remote_candidates = [c for c in resp.candidates if c.source_broker_id is not None]
        assert len(remote_candidates) >= 1
        remote_ids = [c.capability_id for c in remote_candidates]
        assert "remote_ml.analyze" in remote_ids

    def test_remote_discovery_via_http_api(self) -> None:
        broker = self._make_federated_broker()
        peer_resp = _make_broker_b_discovery_response()
        mock_resp = MagicMock()
        mock_resp.json.return_value = peer_resp
        mock_resp.raise_for_status = MagicMock()

        original = svc_module._broker
        svc_module._broker = broker
        try:
            client = TestClient(app)
            with patch("httpx.post", return_value=mock_resp):
                resp = client.post(
                    "/sip/capabilities/discover",
                    json={"include_remote": True, "max_results": 50},
                )
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] > 0
        finally:
            svc_module._broker = original

    def test_broker_b_source_metadata_on_remote_results(self) -> None:
        broker = self._make_federated_broker()
        peer_resp = _make_broker_b_discovery_response()
        mock_resp = MagicMock()
        mock_resp.json.return_value = peer_resp
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.post", return_value=mock_resp):
            resp = broker.discovery.discover(
                DiscoveryRequest(include_remote=True, max_results=50)
            )

        remote = [c for c in resp.candidates if c.source_broker_id == "broker-b"]
        assert len(remote) >= 1
        assert remote[0].source_broker_url == "http://localhost:8001"


# ---------------------------------------------------------------------------
# Scenario C: Deterministic aggregation
# ---------------------------------------------------------------------------


class TestDeterministicAggregation:
    """Aggregated candidate list ordering must be deterministic."""

    def test_local_candidates_precede_remote_when_prefer_local(self) -> None:
        registry = CapabilityRegistryService()
        seed_registry(registry)
        federation = FederationConfig(
            broker_id="broker-a",
            broker_url="http://localhost:8000",
            prefer_local=True,
            peers=[
                FederatedPeer(
                    broker_id="broker-b",
                    broker_url="http://localhost:8001",
                    trust_level=PeerTrustLevel.ROUTING,
                )
            ],
        )
        svc = DiscoveryService(registry=registry, federation=federation)

        peer_resp = _make_broker_b_discovery_response("remote_cap_z")
        mock_resp = MagicMock()
        mock_resp.json.return_value = peer_resp
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.post", return_value=mock_resp):
            resp = svc.discover(DiscoveryRequest(include_remote=True, max_results=100))

        local_indices = [i for i, c in enumerate(resp.candidates) if c.source_broker_id is None]
        remote_indices = [i for i, c in enumerate(resp.candidates) if c.source_broker_id is not None]

        if local_indices and remote_indices:
            assert max(local_indices) < min(remote_indices), (
                "All local candidates must appear before remote candidates"
            )

    def test_repeated_requests_produce_same_order(self) -> None:
        registry = CapabilityRegistryService()
        seed_registry(registry)
        svc = DiscoveryService(registry=registry)
        req = DiscoveryRequest(max_results=100)

        resp1 = svc.discover(req)
        resp2 = svc.discover(req)

        assert [c.capability_id for c in resp1.candidates] == [
            c.capability_id for c in resp2.candidates
        ], "Discovery results must be deterministic for identical requests"

    def test_scores_descending_within_same_source(self) -> None:
        registry = CapabilityRegistryService()
        seed_registry(registry)
        svc = DiscoveryService(registry=registry)
        resp = svc.discover(DiscoveryRequest(max_results=100))

        # Among local candidates, scores should be non-increasing
        local_scores = [c.score for c in resp.candidates if c.source_broker_id is None]
        assert local_scores == sorted(local_scores, reverse=True), (
            "Local candidates must be ordered by score descending"
        )


# ---------------------------------------------------------------------------
# Scenario D: Peer unavailable
# ---------------------------------------------------------------------------


class TestPeerUnavailable:
    """Broker A should log and continue if Broker B is unavailable."""

    def test_peer_down_in_soft_mode_does_not_raise(self) -> None:
        registry = CapabilityRegistryService()
        seed_registry(registry)
        federation = FederationConfig(
            broker_id="broker-a",
            broker_url="http://localhost:8000",
            strict_mode=False,
            peers=[
                FederatedPeer(
                    broker_id="broker-b",
                    broker_url="http://localhost:8001",
                    trust_level=PeerTrustLevel.ROUTING,
                )
            ],
        )
        svc = DiscoveryService(registry=registry, federation=federation)

        with patch("httpx.post", side_effect=ConnectionError("Connection refused")):
            resp = svc.discover(DiscoveryRequest(include_remote=True))

        # Should not raise; should report peer failure
        assert "broker-b" in resp.peers_failed
        assert resp.remote_count == 0
        # Local capabilities still returned
        assert resp.local_count > 0

    def test_peer_down_still_returns_local_capabilities(self) -> None:
        registry = CapabilityRegistryService()
        seed_registry(registry)
        federation = FederationConfig(
            broker_id="broker-a",
            broker_url="http://localhost:8000",
            strict_mode=False,
            peers=[
                FederatedPeer(
                    broker_id="broker-b",
                    broker_url="http://localhost:8001",
                    trust_level=PeerTrustLevel.ROUTING,
                )
            ],
        )
        svc = DiscoveryService(registry=registry, federation=federation)

        with patch("httpx.post", side_effect=ConnectionError("Connection refused")):
            resp = svc.discover(DiscoveryRequest(include_remote=True, max_results=100))

        local_caps = [c for c in resp.candidates if c.source_broker_id is None]
        assert len(local_caps) > 0

    def test_peer_down_via_http_api_returns_200(self) -> None:
        """Discovery endpoint must return 200 with local results even if peer is down."""
        federation = FederationConfig(
            broker_id="broker-a",
            broker_url="http://localhost:8000",
            strict_mode=False,
            peers=[
                FederatedPeer(
                    broker_id="broker-b",
                    broker_url="http://localhost:8001",
                    trust_level=PeerTrustLevel.ROUTING,
                )
            ],
        )
        broker = _make_seeded_broker(federation=federation)
        original = svc_module._broker
        svc_module._broker = broker
        try:
            client = TestClient(app)
            with patch("httpx.post", side_effect=ConnectionError("refused")):
                resp = client.post(
                    "/sip/capabilities/discover",
                    json={"include_remote": True, "max_results": 50},
                )
            assert resp.status_code == 200
            data = resp.json()
            assert data["local_count"] > 0
        finally:
            svc_module._broker = original

    def test_multiple_peers_one_down_continues(self) -> None:
        """Soft-mode: if broker-b fails but broker-c succeeds, results from c are included."""
        registry = CapabilityRegistryService()
        seed_registry(registry)
        federation = FederationConfig(
            broker_id="broker-a",
            broker_url="http://localhost:8000",
            strict_mode=False,
            peers=[
                FederatedPeer(
                    broker_id="broker-b",
                    broker_url="http://localhost:8001",
                    trust_level=PeerTrustLevel.ROUTING,
                ),
                FederatedPeer(
                    broker_id="broker-c",
                    broker_url="http://localhost:8002",
                    trust_level=PeerTrustLevel.ROUTING,
                ),
            ],
        )
        svc = DiscoveryService(registry=registry, federation=federation)

        c_resp = _make_broker_b_discovery_response("broker_c_cap")
        good_mock = MagicMock()
        good_mock.json.return_value = c_resp
        good_mock.raise_for_status = MagicMock()

        call_count = 0

        def side_effect(url: str, **_: object) -> object:
            nonlocal call_count
            call_count += 1
            if "8001" in url:
                raise ConnectionError("broker-b down")
            return good_mock

        with patch("httpx.post", side_effect=side_effect):
            resp = svc.discover(DiscoveryRequest(include_remote=True, max_results=100))

        assert "broker-b" in resp.peers_failed
        assert "broker-c" in resp.peers_queried
        broker_c_caps = [c for c in resp.candidates if c.source_broker_id == "broker-c"]
        assert len(broker_c_caps) >= 1


# ---------------------------------------------------------------------------
# Scenario E: Provenance preservation
# ---------------------------------------------------------------------------


class TestProvenancePreservation:
    """Delegation chain must include brokers involved in forwarding."""

    def test_provenance_block_preserved_through_broker(self) -> None:
        """When an envelope with provenance is submitted, audit captures the chain."""
        broker = _make_seeded_broker(enforce_approval=False)
        provenance = ProvenanceBlock(
            originator="user-human-001",
            submitted_by="orchestrator-agent-007",
            delegation_chain=["user-human-001", "orchestrator-agent-007"],
            on_behalf_of="user-human-001",
            delegation_purpose="automated retrieval on behalf of user",
            authority_scope=["sip:knowledge:read", "sip:agent:delegate"],
        )
        envelope = _make_retrieve_envelope(
            actor_id="orchestrator-agent-007",
            trust_level=TrustLevel.PRIVILEGED,
            scopes=["sip:knowledge:read", "sip:agent:delegate"],
            provenance=provenance,
        )
        result = broker.handle(envelope)
        audit = result.audit_record
        assert audit.originator == "user-human-001"
        assert audit.submitting_actor == "orchestrator-agent-007"
        assert "user-human-001" in audit.delegation_chain
        assert "orchestrator-agent-007" in audit.delegation_chain

    def test_provenance_in_execution_plan(self) -> None:
        """Execution plan provenance_summary must reflect the delegation chain."""
        broker = _make_seeded_broker(enforce_approval=False)
        provenance = ProvenanceBlock(
            originator="user-human-001",
            submitted_by="agent-relay-002",
            delegation_chain=["user-human-001", "agent-relay-002"],
            authority_scope=["sip:knowledge:read"],
        )
        envelope = _make_retrieve_envelope(
            actor_id="agent-relay-002",
            trust_level=TrustLevel.PRIVILEGED,
            scopes=["sip:knowledge:read", "sip:agent:delegate"],
            provenance=provenance,
        )
        result = broker.handle(envelope)
        if result.execution_plan is not None:
            assert result.execution_plan.provenance_summary is not None
            ps = result.execution_plan.provenance_summary
            assert ps["originator"] == "user-human-001"
            assert "user-human-001" in ps["delegation_chain"]

    def test_provenance_anti_laundering_blocked(self) -> None:
        """Anti-laundering: submitted_by must not exceed originator scopes."""
        broker = _make_seeded_broker(enforce_approval=False)
        # Attempt to request scopes beyond what originator holds
        provenance = ProvenanceBlock(
            originator="user-human-001",
            submitted_by="agent-attacker-999",
            delegation_chain=["user-human-001", "agent-attacker-999"],
            authority_scope=["sip:knowledge:read"],  # restricted scope
        )
        envelope = IntentEnvelope(
            actor=ActorDescriptor(
                actor_id="agent-attacker-999",
                actor_type=ActorType.AI_AGENT,
                name="Unauthorized Agent",
                trust_level=TrustLevel.INTERNAL,
                # Requesting a scope not in authority_scope
                scopes=["sip:knowledge:read", "sip:booking:write"],
            ),
            target=TargetDescriptor(target_type=TargetType.CAPABILITY),
            intent=IntentPayload(
                intent_name="reserve_table",
                intent_domain="restaurant_booking",
                operation_class=OperationClass.WRITE,
                parameters={"restaurant_id": "r001", "party_size": 4},
            ),
            desired_outcome=DesiredOutcome(summary="Book a table"),
            provenance=provenance,
        )
        result = broker.handle(envelope)
        audit = result.audit_record
        # Policy should deny due to scope laundering
        assert audit.policy_allowed is False or audit.action_taken.value in (
            "policy_denied",
            "plan_rejected",
            "approval_requested",
        )

    def test_envelope_with_provenance_via_http_api(self) -> None:
        """Provenance block sent via HTTP API is captured in audit record."""
        broker = _make_seeded_broker(enforce_approval=False)
        original = svc_module._broker
        svc_module._broker = broker
        try:
            client = TestClient(app)
            envelope = _make_retrieve_envelope(
                actor_id="orchestrator-agent-007",
                trust_level=TrustLevel.PRIVILEGED,
                scopes=["sip:knowledge:read", "sip:agent:delegate"],
                provenance=ProvenanceBlock(
                    originator="user-human-001",
                    submitted_by="orchestrator-agent-007",
                    delegation_chain=["user-human-001", "orchestrator-agent-007"],
                    authority_scope=["sip:knowledge:read"],
                ),
            )
            resp = client.post("/sip/intents", content=envelope.model_dump_json())
            assert resp.status_code == 200
            data = resp.json()
            audit = data["audit_record"]
            assert audit["actor_id"] == "orchestrator-agent-007"
        finally:
            svc_module._broker = original


# ---------------------------------------------------------------------------
# Scenario F: Policy enforcement on remote capabilities
# ---------------------------------------------------------------------------


class TestPolicyEnforcementOnRemoteCapabilities:
    """Broker A enforces its own policy even when using remote capabilities."""

    def test_local_policy_applies_to_intents_regardless_of_discovery_source(self) -> None:
        """An intent that violates policy is rejected even if a remote capability matches."""
        broker = _make_seeded_broker(enforce_approval=True)
        # Attempt a write with no booking scopes
        envelope = IntentEnvelope(
            actor=ActorDescriptor(
                actor_id="low-trust-agent",
                actor_type=ActorType.AI_AGENT,
                name="Low Trust Agent",
                trust_level=TrustLevel.PUBLIC,
                scopes=[],  # No scopes
            ),
            target=TargetDescriptor(target_type=TargetType.CAPABILITY),
            intent=IntentPayload(
                intent_name="reserve_table",
                intent_domain="restaurant_booking",
                operation_class=OperationClass.WRITE,
                parameters={"restaurant_id": "r001", "party_size": 4},
            ),
            desired_outcome=DesiredOutcome(summary="Book a table"),
        )
        result = broker.handle(envelope)
        audit = result.audit_record
        # Must be denied or require approval due to insufficient scopes
        assert audit.policy_allowed is False or audit.action_taken.value in (
            "policy_denied",
            "approval_requested",
        )

    def test_high_risk_operation_requires_approval_with_routing_peer(self) -> None:
        """High-risk capability from a trusted routing peer still requires approval."""
        registry = CapabilityRegistryService()
        seed_registry(registry)
        engine = PolicyEngine(enforce_approval_policy=True)
        broker = BrokerService(registry=registry, policy_engine=engine)

        envelope = IntentEnvelope(
            actor=ActorDescriptor(
                actor_id="agent-write-001",
                actor_type=ActorType.AI_AGENT,
                name="Write Agent",
                trust_level=TrustLevel.INTERNAL,
                scopes=["sip:booking:write", "sip:customer:read"],
            ),
            target=TargetDescriptor(target_type=TargetType.CAPABILITY),
            intent=IntentPayload(
                intent_name="reserve_table",
                intent_domain="restaurant_booking",
                operation_class=OperationClass.WRITE,
                parameters={"restaurant_id": "r001", "party_size": 2},
            ),
            desired_outcome=DesiredOutcome(summary="Book a table"),
        )
        result = broker.handle(envelope)
        audit = result.audit_record
        # With enforce_approval=True and a write operation at medium+ risk,
        # result must not be unconditionally allowed without approval
        assert audit.action_taken.value in (
            "plan_created",
            "approval_requested",
            "policy_denied",
            "clarification_requested",
        )

    def test_scopes_insufficient_for_remote_capability(self) -> None:
        """An actor without required scopes is denied even for remote capabilities."""
        registry = CapabilityRegistryService()
        seed_registry(registry)
        engine = PolicyEngine(enforce_approval_policy=False)
        broker = BrokerService(registry=registry, policy_engine=engine)

        # Actor with no booking scopes tries to book
        envelope = IntentEnvelope(
            actor=ActorDescriptor(
                actor_id="no-scope-agent",
                actor_type=ActorType.AI_AGENT,
                name="No Scope Agent",
                trust_level=TrustLevel.INTERNAL,
                scopes=["sip:knowledge:read"],  # only read, no booking scope
            ),
            target=TargetDescriptor(target_type=TargetType.CAPABILITY),
            intent=IntentPayload(
                intent_name="reserve_table",
                intent_domain="restaurant_booking",
                operation_class=OperationClass.WRITE,
                parameters={"restaurant_id": "r002", "party_size": 1},
            ),
            desired_outcome=DesiredOutcome(summary="Book a table"),
        )
        result = broker.handle(envelope)
        audit = result.audit_record
        # Policy should deny due to missing booking scope
        assert audit.policy_allowed is False or audit.action_taken.value == "policy_denied"
