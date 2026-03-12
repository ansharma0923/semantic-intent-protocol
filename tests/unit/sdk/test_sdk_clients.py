"""Tests for SDK HTTP client classes (BrokerClient and CapabilityDiscoveryClient).

These tests use httpx's mock transport to avoid requiring a live server.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from sip.sdk import (
    BrokerClient,
    CapabilityDiscoveryClient,
    build_actor,
    build_intent_envelope,
)
from sip.sdk.errors import SIPClientError, SIPHTTPError, SIPValidationError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_envelope() -> object:
    actor = build_actor(
        actor_id="client-test",
        name="Client Test",
        scopes=["sip:knowledge:read"],
    )
    return build_intent_envelope(
        actor=actor,  # type: ignore[arg-type]
        intent_name="retrieve_document",
        intent_domain="knowledge_management",
        operation_class="retrieve",
        outcome_summary="Get document.",
    )


def _mock_response(status_code: int, body: object) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = body
    resp.text = json.dumps(body)
    resp.url = "http://test-server"
    return resp


# ---------------------------------------------------------------------------
# BrokerClient tests
# ---------------------------------------------------------------------------


class TestBrokerClient:
    def test_health_returns_dict(self) -> None:
        client = BrokerClient("http://test-server")
        mock_resp = _mock_response(200, {"status": "ok", "capabilities": 5})

        with patch("httpx.get", return_value=mock_resp) as mock_get:
            result = client.health()

        assert result["status"] == "ok"
        assert result["capabilities"] == 5
        mock_get.assert_called_once()

    def test_health_passes_correct_url(self) -> None:
        client = BrokerClient("http://my-broker:9000")
        mock_resp = _mock_response(200, {"status": "ok"})

        with patch("httpx.get", return_value=mock_resp) as mock_get:
            client.health()

        call_args = mock_get.call_args
        assert "http://my-broker:9000/healthz" in call_args[0]

    def test_health_raises_sip_http_error_on_500(self) -> None:
        client = BrokerClient("http://test-server")
        mock_resp = _mock_response(500, {"error": "internal"})

        with patch("httpx.get", return_value=mock_resp):
            with pytest.raises(SIPHTTPError) as exc_info:
                client.health()

        assert exc_info.value.status_code == 500

    def test_submit_intent_returns_dict(self) -> None:
        client = BrokerClient("http://test-server")
        expected_response = {
            "status": "ok",
            "action_taken": "plan_created",
            "outcome": "success",
        }
        mock_resp = _mock_response(200, expected_response)
        envelope = _make_envelope()

        with patch("httpx.post", return_value=mock_resp) as mock_post:
            result = client.submit_intent(envelope)  # type: ignore[arg-type]

        assert result["action_taken"] == "plan_created"
        mock_post.assert_called_once()

    def test_submit_intent_posts_to_correct_endpoint(self) -> None:
        client = BrokerClient("http://my-broker:9000")
        mock_resp = _mock_response(200, {"status": "ok"})
        envelope = _make_envelope()

        with patch("httpx.post", return_value=mock_resp) as mock_post:
            client.submit_intent(envelope)  # type: ignore[arg-type]

        call_args = mock_post.call_args
        assert "http://my-broker:9000/sip/intents" in call_args[0]

    def test_submit_intent_raises_on_403(self) -> None:
        client = BrokerClient("http://test-server")
        mock_resp = _mock_response(403, {"error": "policy_denied"})
        envelope = _make_envelope()

        with patch("httpx.post", return_value=mock_resp):
            with pytest.raises(SIPHTTPError) as exc_info:
                client.submit_intent(envelope)  # type: ignore[arg-type]

        assert exc_info.value.status_code == 403

    def test_submit_intent_dict_validates_first(self) -> None:
        client = BrokerClient("http://test-server")
        with pytest.raises(SIPValidationError):
            client.submit_intent_dict({"bad": "data"})

    def test_submit_intent_json_validates_first(self) -> None:
        client = BrokerClient("http://test-server")
        with pytest.raises(SIPValidationError):
            client.submit_intent_json('{"not": "an_envelope"}')

    def test_submit_intent_json_invalid_json_raises(self) -> None:
        client = BrokerClient("http://test-server")
        with pytest.raises(SIPValidationError):
            client.submit_intent_json("{ bad json !}")

    def test_base_url_trailing_slash_stripped(self) -> None:
        client = BrokerClient("http://test-server/")
        mock_resp = _mock_response(200, {"status": "ok"})

        with patch("httpx.get", return_value=mock_resp) as mock_get:
            client.health()

        url = mock_get.call_args[0][0]
        assert not url.startswith("http://test-server//")

    def test_custom_headers_sent(self) -> None:
        client = BrokerClient(
            "http://test-server",
            headers={"X-Actor-Id": "my-actor"},
        )
        mock_resp = _mock_response(200, {"status": "ok"})

        with patch("httpx.get", return_value=mock_resp) as mock_get:
            client.health()

        sent_headers = mock_get.call_args[1]["headers"]
        assert sent_headers.get("X-Actor-Id") == "my-actor"

    def test_transport_error_raises_sip_client_error(self) -> None:
        import httpx

        client = BrokerClient("http://test-server")
        with patch("httpx.get", side_effect=httpx.ConnectError("refused")):
            with pytest.raises(SIPClientError):
                client.health()


# ---------------------------------------------------------------------------
# CapabilityDiscoveryClient tests
# ---------------------------------------------------------------------------


class TestCapabilityDiscoveryClient:
    _DESCRIPTOR = {
        "capability_id": "sip.knowledge.retrieve",
        "name": "Document Retrieval",
        "description": "Retrieve a document from the knowledge base.",
        "provider": {
            "provider_id": "knowledge-provider",
            "provider_name": "Knowledge Provider",
        },
        "intent_domains": ["knowledge_management"],
        "operation_class": "retrieve",
        "risk_level": "low",
        "supported_bindings": ["rest"],
        "input_schema": {},
        "output_schema": {},
    }

    _DISCOVERY_CANDIDATE = {
        "capability_id": "sip.knowledge.retrieve",
        "name": "Document Retrieval",
        "description": "Retrieve a document from the knowledge base.",
        "operation_class": "retrieve",
        "supported_bindings": ["rest"],
        "intent_domains": ["knowledge_management"],
        "minimum_trust_tier": "internal",
        "score": 0.9,
        "source_broker_id": None,
        "source_broker_url": None,
        "routing_allowed": True,
    }

    def test_list_capabilities_returns_list(self) -> None:
        client = CapabilityDiscoveryClient("http://test-server")
        mock_resp = _mock_response(200, [self._DESCRIPTOR])

        with patch("httpx.get", return_value=mock_resp):
            caps = client.list_capabilities()

        assert len(caps) == 1
        assert caps[0].capability_id == "sip.knowledge.retrieve"

    def test_list_capabilities_empty_list(self) -> None:
        client = CapabilityDiscoveryClient("http://test-server")
        mock_resp = _mock_response(200, [])

        with patch("httpx.get", return_value=mock_resp):
            caps = client.list_capabilities()

        assert caps == []

    def test_get_capability_by_id(self) -> None:
        client = CapabilityDiscoveryClient("http://test-server")
        mock_resp = _mock_response(200, self._DESCRIPTOR)

        with patch("httpx.get", return_value=mock_resp) as mock_get:
            cap = client.get_capability("sip.knowledge.retrieve")

        assert cap.capability_id == "sip.knowledge.retrieve"
        url = mock_get.call_args[0][0]
        assert "sip.knowledge.retrieve" in url

    def test_get_capability_404_raises(self) -> None:
        client = CapabilityDiscoveryClient("http://test-server")
        mock_resp = _mock_response(404, {"error": "not_found"})

        with patch("httpx.get", return_value=mock_resp):
            with pytest.raises(SIPHTTPError) as exc_info:
                client.get_capability("nonexistent")

        assert exc_info.value.status_code == 404

    def test_discover_capabilities_with_none(self) -> None:
        client = CapabilityDiscoveryClient("http://test-server")
        response_body = {
            "candidates": [self._DISCOVERY_CANDIDATE],
            "total": 1,
        }
        mock_resp = _mock_response(200, response_body)

        with patch("httpx.post", return_value=mock_resp):
            resp = client.discover_capabilities()

        assert resp.total == 1
        assert len(resp.candidates) == 1

    def test_discover_capabilities_with_request(self) -> None:
        from sip.broker.discovery import DiscoveryRequest

        client = CapabilityDiscoveryClient("http://test-server")
        response_body = {
            "candidates": [],
            "total": 0,
        }
        mock_resp = _mock_response(200, response_body)
        req = DiscoveryRequest(intent_name="retrieve_document")

        with patch("httpx.post", return_value=mock_resp) as mock_post:
            resp = client.discover_capabilities(req)

        assert resp.total == 0
        mock_post.assert_called_once()

    def test_discover_capabilities_with_dict(self) -> None:
        client = CapabilityDiscoveryClient("http://test-server")
        response_body = {"candidates": [], "total": 0}
        mock_resp = _mock_response(200, response_body)

        with patch("httpx.post", return_value=mock_resp):
            resp = client.discover_capabilities({"intent_name": "retrieve_document"})

        assert resp.total == 0

    def test_discover_capabilities_invalid_dict_raises(self) -> None:
        client = CapabilityDiscoveryClient("http://test-server")
        with pytest.raises(SIPValidationError):
            # passing something that cannot be validated as DiscoveryRequest
            client.discover_capabilities({"unknown_field_that_breaks": True, "max_results": "not-an-int"})
