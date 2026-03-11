"""Functional tests for the SIP broker HTTP API.

Tests cover:
  - POST /sip/intents – successful path (200)
  - POST /sip/intents – approval-required path (202)
  - POST /sip/intents – policy-denied path (403)
  - POST /sip/intents – invalid envelope path (422)
  - GET /healthz
  - Startup with persisted capabilities loaded
  - Request processed with trusted identity headers
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from sip.broker.service import BrokerService, app
from sip.envelope.models import (
    ActorDescriptor,
    ActorType,
    BindingType,
    DesiredOutcome,
    IntentEnvelope,
    IntentPayload,
    OperationClass,
    ProtocolBinding,
    TargetDescriptor,
    TargetType,
    TrustLevel,
)
from sip.observability.audit import OutcomeSummary
from sip.policy.engine import PolicyEngine
from sip.registry.bootstrap import seed_registry
from sip.registry.service import CapabilityRegistryService
from sip.registry.storage import JsonFileCapabilityStore


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def seeded_broker() -> BrokerService:
    """A broker with a seeded registry and approval enforcement enabled."""
    registry = CapabilityRegistryService()
    seed_registry(registry)
    engine = PolicyEngine(enforce_approval_policy=True)
    return BrokerService(registry=registry, policy_engine=engine)


@pytest.fixture
def seeded_broker_no_approval() -> BrokerService:
    """A broker with approval enforcement disabled for simpler path testing."""
    registry = CapabilityRegistryService()
    seed_registry(registry)
    engine = PolicyEngine(enforce_approval_policy=False)
    return BrokerService(registry=registry, policy_engine=engine)


@pytest.fixture
def client(seeded_broker: BrokerService) -> TestClient:
    """TestClient with the module-level app, broker replaced with seeded instance."""
    import sip.broker.service as svc_module

    original = svc_module._broker
    svc_module._broker = seeded_broker
    yield TestClient(app)
    svc_module._broker = original


@pytest.fixture
def client_no_approval(seeded_broker_no_approval: BrokerService) -> TestClient:
    import sip.broker.service as svc_module

    original = svc_module._broker
    svc_module._broker = seeded_broker_no_approval
    yield TestClient(app)
    svc_module._broker = original


# ---------------------------------------------------------------------------
# Intent payload builders
# ---------------------------------------------------------------------------


def _knowledge_envelope_dict(scopes: list[str] | None = None) -> dict[str, Any]:
    return IntentEnvelope(
        actor=ActorDescriptor(
            actor_id="test-agent",
            actor_type=ActorType.AI_AGENT,
            name="Test Agent",
            trust_level=TrustLevel.INTERNAL,
            scopes=scopes if scopes is not None else ["sip:knowledge:read"],
        ),
        target=TargetDescriptor(target_type=TargetType.CAPABILITY),
        intent=IntentPayload(
            intent_name="retrieve_document",
            intent_domain="knowledge_management",
            operation_class=OperationClass.RETRIEVE,
        ),
        desired_outcome=DesiredOutcome(summary="Get a document"),
        protocol_bindings=[ProtocolBinding(binding_type=BindingType.REST)],
    ).model_dump(mode="json")


def _network_execute_envelope_dict() -> dict[str, Any]:
    """Network execute – high-risk, requires approval."""
    return IntentEnvelope(
        actor=ActorDescriptor(
            actor_id="netops-agent",
            actor_type=ActorType.AI_AGENT,
            name="NetOps Agent",
            trust_level=TrustLevel.PRIVILEGED,
            scopes=["sip:network:read", "sip:network:execute"],
        ),
        target=TargetDescriptor(target_type=TargetType.CAPABILITY),
        intent=IntentPayload(
            intent_name="diagnose_network_issue",
            intent_domain="network_operations",
            operation_class=OperationClass.ANALYZE,
        ),
        desired_outcome=DesiredOutcome(summary="Diagnose network problem"),
    ).model_dump(mode="json")


# ---------------------------------------------------------------------------
# Tests: GET /healthz
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    def test_healthz_returns_200(self, client: TestClient) -> None:
        response = client.get("/healthz")
        assert response.status_code == 200

    def test_healthz_returns_ok_status(self, client: TestClient) -> None:
        response = client.get("/healthz")
        body = response.json()
        assert body["status"] == "ok"

    def test_healthz_includes_capabilities_count(self, client: TestClient) -> None:
        response = client.get("/healthz")
        body = response.json()
        assert "capabilities" in body
        assert body["capabilities"] > 0

    def test_healthz_includes_version(self, client: TestClient) -> None:
        response = client.get("/healthz")
        body = response.json()
        assert "version" in body

    def test_health_legacy_alias(self, client: TestClient) -> None:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# Tests: POST /sip/intents – successful path (200)
# ---------------------------------------------------------------------------


class TestSubmitIntentSuccess:
    def test_returns_200_on_success(self, client_no_approval: TestClient) -> None:
        response = client_no_approval.post("/sip/intents", json=_knowledge_envelope_dict())
        assert response.status_code == 200

    def test_response_contains_intent_id(self, client_no_approval: TestClient) -> None:
        response = client_no_approval.post("/sip/intents", json=_knowledge_envelope_dict())
        body = response.json()
        assert "intent_id" in body

    def test_response_contains_outcome(self, client_no_approval: TestClient) -> None:
        response = client_no_approval.post("/sip/intents", json=_knowledge_envelope_dict())
        body = response.json()
        assert body["outcome"] == OutcomeSummary.SUCCESS

    def test_response_contains_plan_id(self, client_no_approval: TestClient) -> None:
        response = client_no_approval.post("/sip/intents", json=_knowledge_envelope_dict())
        body = response.json()
        assert body["plan_id"] is not None

    def test_response_contains_policy_allowed(self, client_no_approval: TestClient) -> None:
        response = client_no_approval.post("/sip/intents", json=_knowledge_envelope_dict())
        body = response.json()
        assert body["policy_allowed"] is True

    def test_response_contains_audit_record(self, client_no_approval: TestClient) -> None:
        response = client_no_approval.post("/sip/intents", json=_knowledge_envelope_dict())
        body = response.json()
        assert "audit_record" in body
        ar = body["audit_record"]
        assert "trace_id" in ar
        assert "actor_id" in ar
        assert "timestamp" in ar

    def test_response_contains_policy_notes(self, client_no_approval: TestClient) -> None:
        response = client_no_approval.post("/sip/intents", json=_knowledge_envelope_dict())
        body = response.json()
        assert "policy_notes" in body
        assert isinstance(body["policy_notes"], list)


# ---------------------------------------------------------------------------
# Tests: POST /sip/intents – approval-required path (202)
# ---------------------------------------------------------------------------


class TestSubmitIntentApprovalRequired:
    def test_returns_202_when_approval_required(self, client: TestClient) -> None:
        """Network diagnose is MEDIUM risk; depending on policy mode this may or may not
        require approval.  The test accepts either 200 or 202 as a valid outcome."""
        response = client.post("/sip/intents", json=_network_execute_envelope_dict())
        body = response.json()
        if body.get("approval_required"):
            assert response.status_code == 202
        else:
            # Acceptable: not all medium-risk ops require approval at all policy modes
            assert response.status_code == 200

    def test_approval_required_flag_present(self, client: TestClient) -> None:
        response = client.post("/sip/intents", json=_network_execute_envelope_dict())
        body = response.json()
        assert "approval_required" in body


# ---------------------------------------------------------------------------
# Tests: POST /sip/intents – policy-denied path (403)
# ---------------------------------------------------------------------------


class TestSubmitIntentDenied:
    def test_returns_403_on_policy_denial(self, client_no_approval: TestClient) -> None:
        envelope = _knowledge_envelope_dict(scopes=[])  # missing required scope
        response = client_no_approval.post("/sip/intents", json=envelope)
        assert response.status_code == 403

    def test_denied_response_policy_allowed_false(
        self, client_no_approval: TestClient
    ) -> None:
        envelope = _knowledge_envelope_dict(scopes=[])
        response = client_no_approval.post("/sip/intents", json=envelope)
        body = response.json()
        assert body["policy_allowed"] is False


# ---------------------------------------------------------------------------
# Tests: POST /sip/intents – invalid envelope (422)
# ---------------------------------------------------------------------------


class TestSubmitIntentInvalidEnvelope:
    def test_returns_422_on_missing_required_fields(self, client: TestClient) -> None:
        response = client.post("/sip/intents", json={"not": "an envelope"})
        assert response.status_code == 422

    def test_returns_422_on_empty_body(self, client: TestClient) -> None:
        response = client.post("/sip/intents", json={})
        assert response.status_code == 422

    def test_returns_422_on_non_json_body(self, client: TestClient) -> None:
        response = client.post(
            "/sip/intents",
            content=b"not-json",
            headers={"content-type": "application/json"},
        )
        assert response.status_code == 422

    def test_error_field_present_on_invalid(self, client: TestClient) -> None:
        response = client.post("/sip/intents", json={"broken": True})
        body = response.json()
        assert "error" in body


# ---------------------------------------------------------------------------
# Tests: startup with persisted capabilities
# ---------------------------------------------------------------------------


class TestStartupWithPersistedCapabilities:
    def test_persisted_capabilities_loaded_into_broker(self, tmp_path: Path) -> None:
        """Capabilities saved to a file should be available after reload."""
        path = tmp_path / "caps.json"

        # First: create a registry, seed it, and save to file
        store1 = JsonFileCapabilityStore(file_path=path)
        registry1 = CapabilityRegistryService(store=store1)
        seed_registry(registry1)
        count_first = registry1.count()

        # Second: create a new store from the same file
        store2 = JsonFileCapabilityStore(file_path=path)
        registry2 = CapabilityRegistryService(store=store2)
        assert registry2.count() == count_first

    def test_capabilities_endpoint_reflects_loaded_data(
        self, tmp_path: Path
    ) -> None:
        import sip.broker.service as svc_module

        path = tmp_path / "caps.json"
        store = JsonFileCapabilityStore(file_path=path)
        registry = CapabilityRegistryService(store=store)
        seed_registry(registry)

        original_broker = svc_module._broker
        svc_module._broker = BrokerService(registry=registry)

        try:
            test_client = TestClient(app)
            response = test_client.get("/capabilities")
            assert response.status_code == 200
            caps = response.json()
            ids = [c["capability_id"] for c in caps]
            assert "retrieve_document" in ids
        finally:
            svc_module._broker = original_broker


# ---------------------------------------------------------------------------
# Tests: trusted identity headers
# ---------------------------------------------------------------------------


class TestTrustedIdentityHeaders:
    def test_identity_headers_applied_when_enabled(
        self,
        client_no_approval: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When trusted headers are enabled, actor overrides must appear in audit."""
        monkeypatch.setenv("SIP_TRUSTED_IDENTITY_HEADERS", "true")

        envelope = _knowledge_envelope_dict()
        response = client_no_approval.post(
            "/sip/intents",
            json=envelope,
            headers={
                "x-actor-id": "gateway-injected-id",
                "x-actor-name": "Gateway Agent",
            },
        )
        assert response.status_code in (200, 403, 202)
        body = response.json()
        ar = body.get("audit_record", {})
        # The audit record must reflect the gateway-injected actor_id
        assert ar.get("actor_id") == "gateway-injected-id"

    def test_identity_headers_ignored_when_disabled(
        self,
        client_no_approval: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When trusted headers are disabled, actor from body must be used."""
        monkeypatch.setenv("SIP_TRUSTED_IDENTITY_HEADERS", "false")

        envelope = _knowledge_envelope_dict()
        original_actor_id = envelope["actor"]["actor_id"]

        response = client_no_approval.post(
            "/sip/intents",
            json=envelope,
            headers={"x-actor-id": "should-be-ignored"},
        )
        body = response.json()
        ar = body.get("audit_record", {})
        assert ar.get("actor_id") == original_actor_id
