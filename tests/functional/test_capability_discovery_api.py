"""Functional tests for the SIP capability discovery HTTP API.

Tests cover:
- GET /sip/capabilities – list all capabilities
- GET /sip/capabilities/{id} – get capability by ID (200 and 404)
- POST /sip/capabilities/discover – successful discovery
- POST /sip/capabilities/discover – no matches
- POST /sip/capabilities/discover – invalid request (400)
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from sip.broker.service import BrokerService, app
from sip.envelope.models import BindingType, OperationClass, TrustLevel
from sip.registry.bootstrap import seed_registry
from sip.registry.service import CapabilityRegistryService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def seeded_client() -> TestClient:
    """TestClient backed by a seeded broker instance."""
    import sip.broker.service as svc_module

    registry = CapabilityRegistryService()
    seed_registry(registry)
    broker = BrokerService(registry=registry)
    original = svc_module._broker
    svc_module._broker = broker
    yield TestClient(app)
    svc_module._broker = original


@pytest.fixture
def empty_client() -> TestClient:
    """TestClient backed by a broker with an empty registry."""
    import sip.broker.service as svc_module

    registry = CapabilityRegistryService()  # no capabilities
    broker = BrokerService(registry=registry)
    original = svc_module._broker
    svc_module._broker = broker
    yield TestClient(app)
    svc_module._broker = original


# ---------------------------------------------------------------------------
# GET /sip/capabilities
# ---------------------------------------------------------------------------


class TestSipListCapabilities:
    def test_returns_200(self, seeded_client: TestClient) -> None:
        response = seeded_client.get("/sip/capabilities")
        assert response.status_code == 200

    def test_returns_list(self, seeded_client: TestClient) -> None:
        response = seeded_client.get("/sip/capabilities")
        body = response.json()
        assert isinstance(body, list)

    def test_list_is_not_empty_for_seeded_registry(
        self, seeded_client: TestClient
    ) -> None:
        response = seeded_client.get("/sip/capabilities")
        body = response.json()
        assert len(body) > 0

    def test_each_item_has_capability_id(self, seeded_client: TestClient) -> None:
        response = seeded_client.get("/sip/capabilities")
        for item in response.json():
            assert "capability_id" in item

    def test_each_item_has_name(self, seeded_client: TestClient) -> None:
        response = seeded_client.get("/sip/capabilities")
        for item in response.json():
            assert "name" in item

    def test_each_item_has_supported_bindings(self, seeded_client: TestClient) -> None:
        response = seeded_client.get("/sip/capabilities")
        for item in response.json():
            assert "supported_bindings" in item

    def test_each_item_has_extensions_field(self, seeded_client: TestClient) -> None:
        response = seeded_client.get("/sip/capabilities")
        for item in response.json():
            assert "extensions" in item

    def test_empty_registry_returns_empty_list(
        self, empty_client: TestClient
    ) -> None:
        response = empty_client.get("/sip/capabilities")
        assert response.status_code == 200
        assert response.json() == []

    def test_known_capability_present(self, seeded_client: TestClient) -> None:
        response = seeded_client.get("/sip/capabilities")
        ids = [c["capability_id"] for c in response.json()]
        assert "retrieve_document" in ids


# ---------------------------------------------------------------------------
# GET /sip/capabilities/{capability_id}
# ---------------------------------------------------------------------------


class TestSipGetCapabilityById:
    def test_returns_200_for_known_id(self, seeded_client: TestClient) -> None:
        response = seeded_client.get("/sip/capabilities/retrieve_document")
        assert response.status_code == 200

    def test_returns_correct_capability(self, seeded_client: TestClient) -> None:
        response = seeded_client.get("/sip/capabilities/retrieve_document")
        body = response.json()
        assert body["capability_id"] == "retrieve_document"

    def test_returns_full_descriptor(self, seeded_client: TestClient) -> None:
        response = seeded_client.get("/sip/capabilities/retrieve_document")
        body = response.json()
        assert "provider" in body
        assert "supported_bindings" in body
        assert "intent_domains" in body

    def test_returns_404_for_unknown_id(self, seeded_client: TestClient) -> None:
        response = seeded_client.get("/sip/capabilities/nonexistent_cap_xyz")
        assert response.status_code == 404

    def test_404_response_has_error_field(self, seeded_client: TestClient) -> None:
        response = seeded_client.get("/sip/capabilities/nonexistent")
        body = response.json()
        assert "error" in body
        assert body["error"] == "not_found"

    def test_404_response_has_detail_field(self, seeded_client: TestClient) -> None:
        response = seeded_client.get("/sip/capabilities/nonexistent")
        body = response.json()
        assert "detail" in body


# ---------------------------------------------------------------------------
# POST /sip/capabilities/discover
# ---------------------------------------------------------------------------


class TestSipDiscoverCapabilities:
    def test_returns_200_on_valid_request(self, seeded_client: TestClient) -> None:
        response = seeded_client.post(
            "/sip/capabilities/discover",
            json={
                "intent_name": "retrieve_document",
                "intent_domain": "knowledge_management",
                "operation_class": "retrieve",
            },
        )
        assert response.status_code == 200

    def test_response_has_candidates_field(self, seeded_client: TestClient) -> None:
        response = seeded_client.post(
            "/sip/capabilities/discover",
            json={"intent_name": "retrieve_document"},
        )
        body = response.json()
        assert "candidates" in body

    def test_response_has_total_field(self, seeded_client: TestClient) -> None:
        response = seeded_client.post(
            "/sip/capabilities/discover",
            json={"intent_name": "retrieve_document"},
        )
        body = response.json()
        assert "total" in body
        assert isinstance(body["total"], int)

    def test_discover_with_known_intent_returns_matches(
        self, seeded_client: TestClient
    ) -> None:
        response = seeded_client.post(
            "/sip/capabilities/discover",
            json={
                "intent_name": "retrieve_document",
                "intent_domain": "knowledge_management",
                "operation_class": "retrieve",
            },
        )
        body = response.json()
        ids = [c["capability_id"] for c in body["candidates"]]
        assert "retrieve_document" in ids

    def test_discover_with_no_matches_returns_empty_candidates(
        self, seeded_client: TestClient
    ) -> None:
        response = seeded_client.post(
            "/sip/capabilities/discover",
            json={
                "intent_name": "zxqwerty_nonexistent",
                "intent_domain": "zxqwerty_domain",
                "operation_class": "write",
            },
        )
        body = response.json()
        assert body["candidates"] == []
        assert body["total"] == 0

    def test_empty_registry_returns_empty_discovery(
        self, empty_client: TestClient
    ) -> None:
        response = empty_client.post(
            "/sip/capabilities/discover",
            json={"intent_name": "anything"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["candidates"] == []

    def test_max_results_respected(self, seeded_client: TestClient) -> None:
        response = seeded_client.post(
            "/sip/capabilities/discover",
            json={"max_results": 1},
        )
        body = response.json()
        assert len(body["candidates"]) <= 1

    def test_response_candidates_have_score(self, seeded_client: TestClient) -> None:
        response = seeded_client.post(
            "/sip/capabilities/discover",
            json={"intent_name": "retrieve_document"},
        )
        for c in response.json()["candidates"]:
            assert "score" in c

    def test_response_candidates_have_routing_allowed(
        self, seeded_client: TestClient
    ) -> None:
        response = seeded_client.post(
            "/sip/capabilities/discover",
            json={"intent_name": "retrieve_document"},
        )
        for c in response.json()["candidates"]:
            assert "routing_allowed" in c

    def test_invalid_operation_class_returns_400(
        self, seeded_client: TestClient
    ) -> None:
        response = seeded_client.post(
            "/sip/capabilities/discover",
            json={"operation_class": "not_a_valid_op_class"},
        )
        assert response.status_code == 400

    def test_invalid_trust_level_returns_400(
        self, seeded_client: TestClient
    ) -> None:
        response = seeded_client.post(
            "/sip/capabilities/discover",
            json={"trust_level": "super_admin_not_valid"},
        )
        assert response.status_code == 400

    def test_max_results_zero_returns_400(self, seeded_client: TestClient) -> None:
        response = seeded_client.post(
            "/sip/capabilities/discover",
            json={"max_results": 0},
        )
        assert response.status_code == 400

    def test_non_json_body_returns_400(self, seeded_client: TestClient) -> None:
        response = seeded_client.post(
            "/sip/capabilities/discover",
            content=b"not-json",
            headers={"content-type": "application/json"},
        )
        assert response.status_code == 400

    def test_empty_json_body_is_valid_discovery_request(
        self, seeded_client: TestClient
    ) -> None:
        """An empty JSON object {} is a valid discovery request (all fields optional)."""
        response = seeded_client.post("/sip/capabilities/discover", json={})
        assert response.status_code == 200

    def test_peers_queried_empty_for_non_federated_broker(
        self, seeded_client: TestClient
    ) -> None:
        response = seeded_client.post(
            "/sip/capabilities/discover",
            json={"intent_name": "retrieve_document"},
        )
        body = response.json()
        assert body["peers_queried"] == []
        assert body["peers_failed"] == []

    def test_legacy_capabilities_endpoint_still_works(
        self, seeded_client: TestClient
    ) -> None:
        """The legacy GET /capabilities endpoint must still respond."""
        response = seeded_client.get("/capabilities")
        assert response.status_code == 200
