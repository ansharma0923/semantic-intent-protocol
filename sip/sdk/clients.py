"""HTTP client classes for the SIP Python SDK.

Provides synchronous Python clients for the SIP broker HTTP API and the
capability discovery HTTP API.

Example::

    from sip.sdk.clients import BrokerClient, CapabilityDiscoveryClient

    broker = BrokerClient("http://localhost:8000")
    health = broker.health()

    discovery = CapabilityDiscoveryClient("http://localhost:8000")
    caps = discovery.list_capabilities()

Both clients use ``httpx`` for HTTP calls (already a dev dependency of the
project). If you need to test these clients without a live server, you can
use ``httpx``'s transport mocking features.

Custom exceptions are raised for client errors:

* ``SIPHTTPError`` – non-2xx HTTP response
* ``SIPClientError`` – configuration or transport error
* ``SIPValidationError`` – response body fails model validation
"""

from __future__ import annotations

import logging
from typing import Any

from sip.broker.discovery import DiscoveryRequest, DiscoveryResponse
from sip.envelope.models import IntentEnvelope
from sip.registry.models import CapabilityDescriptor
from sip.sdk.errors import SIPClientError, SIPHTTPError, SIPValidationError
from sip.sdk.serialization import (
    parse_capability_descriptor,
    parse_discovery_response,
    parse_intent_envelope,
    to_json,
)

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 30.0  # seconds


def _get_httpx() -> Any:
    """Return the httpx module, raising SIPClientError if unavailable."""
    try:
        import httpx  # type: ignore[import]

        return httpx
    except ImportError as exc:
        raise SIPClientError(
            "The 'httpx' package is required for HTTP client support. "
            "Install it with: pip install httpx"
        ) from exc


def _raise_for_status(response: Any) -> None:
    """Raise ``SIPHTTPError`` for non-2xx responses."""
    if response.status_code >= 400:
        try:
            body = response.text
        except Exception:
            body = None
        raise SIPHTTPError(
            f"HTTP {response.status_code} from {response.url}",
            status_code=response.status_code,
            response_body=body,
        )


class BrokerClient:
    """Synchronous HTTP client for the SIP broker API.

    Args:
        base_url: Base URL of the SIP broker (e.g. ``"http://localhost:8000"``).
        timeout: Request timeout in seconds (default: 30.0).
        headers: Optional extra HTTP headers to include in every request.

    Example::

        from sip.sdk.clients import BrokerClient
        from sip.sdk.builders import build_actor, build_intent_envelope

        client = BrokerClient("http://localhost:8000")
        actor = build_actor("my-svc", "My Service", scopes=["sip:knowledge:read"])
        envelope = build_intent_envelope(
            actor=actor,
            intent_name="retrieve_document",
            intent_domain="knowledge_management",
            operation_class="retrieve",
            outcome_summary="Get the architecture document.",
        )
        result = client.submit_intent(envelope)
    """

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = _DEFAULT_TIMEOUT,
        headers: dict[str, str] | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._headers: dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if headers:
            self._headers.update(headers)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get(self, path: str) -> Any:
        httpx = _get_httpx()
        url = f"{self._base_url}{path}"
        try:
            resp = httpx.get(url, headers=self._headers, timeout=self._timeout)
        except Exception as exc:
            raise SIPClientError(f"GET {url} failed: {exc}") from exc
        _raise_for_status(resp)
        return resp

    def _post(self, path: str, body: str) -> Any:
        httpx = _get_httpx()
        url = f"{self._base_url}{path}"
        try:
            resp = httpx.post(url, content=body, headers=self._headers, timeout=self._timeout)
        except Exception as exc:
            raise SIPClientError(f"POST {url} failed: {exc}") from exc
        _raise_for_status(resp)
        return resp

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def health(self) -> dict[str, Any]:
        """Call the ``/healthz`` endpoint.

        Returns:
            A dict with at minimum ``{"status": "ok"}``.

        Raises:
            SIPHTTPError: If the server returns a non-2xx response.
            SIPClientError: If the request cannot be sent.
        """
        resp = self._get("/healthz")
        data: dict[str, Any] = resp.json()
        return data

    def submit_intent(self, envelope: IntentEnvelope) -> dict[str, Any]:
        """Submit an ``IntentEnvelope`` to the broker.

        Args:
            envelope: A validated ``IntentEnvelope`` instance.

        Returns:
            The broker response as a plain dictionary.

        Raises:
            SIPHTTPError: If the server returns a non-2xx response.
            SIPClientError: If the request cannot be sent.
        """
        body = to_json(envelope)
        resp = self._post("/sip/intents", body)
        result: dict[str, Any] = resp.json()
        return result

    def submit_intent_dict(self, envelope_dict: dict[str, Any]) -> dict[str, Any]:
        """Submit an intent envelope supplied as a plain dictionary.

        The dict is validated as an ``IntentEnvelope`` before submission.

        Args:
            envelope_dict: A dictionary representation of an ``IntentEnvelope``.

        Returns:
            The broker response as a plain dictionary.

        Raises:
            SIPValidationError: If the dict fails ``IntentEnvelope`` validation.
            SIPHTTPError: If the server returns a non-2xx response.
            SIPClientError: If the request cannot be sent.
        """
        envelope = parse_intent_envelope(envelope_dict)
        return self.submit_intent(envelope)

    def submit_intent_json(self, envelope_json: str) -> dict[str, Any]:
        """Submit an intent envelope supplied as a JSON string.

        The JSON is validated as an ``IntentEnvelope`` before submission.

        Args:
            envelope_json: A JSON string representation of an ``IntentEnvelope``.

        Returns:
            The broker response as a plain dictionary.

        Raises:
            SIPValidationError: If the JSON fails ``IntentEnvelope`` validation.
            SIPHTTPError: If the server returns a non-2xx response.
            SIPClientError: If the request cannot be sent.
        """
        envelope = parse_intent_envelope(envelope_json)
        return self.submit_intent(envelope)


class CapabilityDiscoveryClient:
    """Synchronous HTTP client for the SIP capability discovery API.

    Args:
        base_url: Base URL of the SIP broker that exposes the discovery API.
        timeout: Request timeout in seconds (default: 30.0).
        headers: Optional extra HTTP headers to include in every request.

    Example::

        from sip.sdk.clients import CapabilityDiscoveryClient
        from sip.broker.discovery import DiscoveryRequest

        client = CapabilityDiscoveryClient("http://localhost:8000")
        caps = client.list_capabilities()
        cap = client.get_capability("sip.knowledge.retrieve")
        results = client.discover_capabilities(
            DiscoveryRequest(intent_name="retrieve_document")
        )
    """

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = _DEFAULT_TIMEOUT,
        headers: dict[str, str] | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._headers: dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if headers:
            self._headers.update(headers)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get(self, path: str) -> Any:
        httpx = _get_httpx()
        url = f"{self._base_url}{path}"
        try:
            resp = httpx.get(url, headers=self._headers, timeout=self._timeout)
        except Exception as exc:
            raise SIPClientError(f"GET {url} failed: {exc}") from exc
        _raise_for_status(resp)
        return resp

    def _post(self, path: str, body: str) -> Any:
        httpx = _get_httpx()
        url = f"{self._base_url}{path}"
        try:
            resp = httpx.post(url, content=body, headers=self._headers, timeout=self._timeout)
        except Exception as exc:
            raise SIPClientError(f"POST {url} failed: {exc}") from exc
        _raise_for_status(resp)
        return resp

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list_capabilities(self) -> list[CapabilityDescriptor]:
        """Return all capabilities registered with the broker.

        Returns:
            A list of ``CapabilityDescriptor`` instances.

        Raises:
            SIPHTTPError: If the server returns a non-2xx response.
            SIPClientError: If the request cannot be sent.
            SIPValidationError: If the response fails model validation.
        """
        resp = self._get("/sip/capabilities")
        raw_list: list[dict[str, Any]] = resp.json()
        try:
            return [parse_capability_descriptor(item) for item in raw_list]
        except SIPValidationError:
            raise
        except Exception as exc:
            raise SIPValidationError(
                f"Failed to parse capability list response: {exc}"
            ) from exc

    def get_capability(self, capability_id: str) -> CapabilityDescriptor:
        """Return a single capability by its ID.

        Args:
            capability_id: The capability identifier.

        Returns:
            A validated ``CapabilityDescriptor``.

        Raises:
            SIPHTTPError: If the server returns a non-2xx response (including 404).
            SIPClientError: If the request cannot be sent.
            SIPValidationError: If the response fails model validation.
        """
        resp = self._get(f"/sip/capabilities/{capability_id}")
        return parse_capability_descriptor(resp.json())

    def discover_capabilities(
        self, request: DiscoveryRequest | dict[str, Any] | None = None
    ) -> DiscoveryResponse:
        """Discover capabilities matching a semantic query.

        Args:
            request: A ``DiscoveryRequest`` instance, a plain dictionary, or
                     ``None`` for an open-ended query that returns all candidates.

        Returns:
            A ``DiscoveryResponse`` with ranked candidates.

        Raises:
            SIPHTTPError: If the server returns a non-2xx response.
            SIPClientError: If the request cannot be sent.
            SIPValidationError: If the request or response fails model validation.
        """
        if request is None:
            disc_req = DiscoveryRequest()
        elif isinstance(request, dict):
            try:
                disc_req = DiscoveryRequest.model_validate(request)
            except Exception as exc:
                raise SIPValidationError(
                    f"Invalid discovery request: {exc}"
                ) from exc
        else:
            disc_req = request

        body = to_json(disc_req)
        resp = self._post("/sip/capabilities/discover", body)
        return parse_discovery_response(resp.json())


__all__ = [
    "BrokerClient",
    "CapabilityDiscoveryClient",
]
