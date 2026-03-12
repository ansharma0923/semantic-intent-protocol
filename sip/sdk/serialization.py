"""Serialization helpers for the SIP Python SDK.

Provides utilities for converting SIP protocol objects to and from
Python dicts and JSON strings.

Example::

    from sip.sdk.serialization import to_json, to_dict, parse_intent_envelope

    json_str = to_json(envelope)
    restored = parse_intent_envelope(json_str)
    assert restored == envelope
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ValidationError

from sip.broker.discovery import DiscoveryRequest, DiscoveryResponse
from sip.envelope.models import IntentEnvelope
from sip.negotiation.planner import ExecutionPlan
from sip.negotiation.results import NegotiationResult
from sip.observability.audit import AuditRecord
from sip.registry.models import CapabilityDescriptor
from sip.sdk.errors import SIPValidationError

# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------


def to_dict(obj: BaseModel) -> dict[str, Any]:
    """Serialize a Pydantic model to a plain Python dictionary.

    Uses ``mode="json"`` so that values like ``datetime`` and ``Enum``
    instances are converted to their JSON-serializable equivalents.

    Args:
        obj: Any Pydantic ``BaseModel`` instance.

    Returns:
        A plain dictionary suitable for JSON serialization or storage.
    """
    return obj.model_dump(mode="json")


def to_json(obj: BaseModel, *, indent: int | None = None) -> str:
    """Serialize a Pydantic model to a JSON string.

    Args:
        obj: Any Pydantic ``BaseModel`` instance.
        indent: Optional indentation level for pretty-printing.

    Returns:
        A JSON-encoded string.
    """
    return obj.model_dump_json(indent=indent)


# ---------------------------------------------------------------------------
# Typed parse helpers
# ---------------------------------------------------------------------------


def _parse_model(
    model_cls: type[BaseModel],
    data: dict[str, Any] | str,
    *,
    label: str,
) -> Any:
    """Internal helper: parse *data* as *model_cls*, raising SIPValidationError on failure."""
    try:
        if isinstance(data, str):
            raw: dict[str, Any] = json.loads(data)
        else:
            raw = data
        return model_cls.model_validate(raw)
    except (json.JSONDecodeError, ValueError) as exc:
        raise SIPValidationError(f"Failed to parse {label}: {exc}") from exc
    except ValidationError as exc:
        errors = [str(e) for e in exc.errors()]
        raise SIPValidationError(
            f"Validation failed for {label}", errors=errors
        ) from exc


def parse_intent_envelope(data: dict[str, Any] | str) -> IntentEnvelope:
    """Parse an ``IntentEnvelope`` from a dict or JSON string.

    Args:
        data: A Python dictionary or JSON string representing an envelope.

    Returns:
        A validated ``IntentEnvelope`` instance.

    Raises:
        SIPValidationError: If the data is invalid or fails validation.
    """
    return _parse_model(IntentEnvelope, data, label="IntentEnvelope")  # type: ignore[return-value]


def parse_capability_descriptor(data: dict[str, Any] | str) -> CapabilityDescriptor:
    """Parse a ``CapabilityDescriptor`` from a dict or JSON string.

    Args:
        data: A Python dictionary or JSON string.

    Returns:
        A validated ``CapabilityDescriptor`` instance.

    Raises:
        SIPValidationError: If the data is invalid or fails validation.
    """
    return _parse_model(CapabilityDescriptor, data, label="CapabilityDescriptor")  # type: ignore[return-value]


def parse_execution_plan(data: dict[str, Any] | str) -> ExecutionPlan:
    """Parse an ``ExecutionPlan`` from a dict or JSON string.

    Args:
        data: A Python dictionary or JSON string.

    Returns:
        A validated ``ExecutionPlan`` instance.

    Raises:
        SIPValidationError: If the data is invalid or fails validation.
    """
    return _parse_model(ExecutionPlan, data, label="ExecutionPlan")  # type: ignore[return-value]


def parse_negotiation_result(data: dict[str, Any] | str) -> NegotiationResult:
    """Parse a ``NegotiationResult`` from a dict or JSON string.

    Args:
        data: A Python dictionary or JSON string.

    Returns:
        A validated ``NegotiationResult`` instance.

    Raises:
        SIPValidationError: If the data is invalid or fails validation.
    """
    return _parse_model(NegotiationResult, data, label="NegotiationResult")  # type: ignore[return-value]


def parse_audit_record(data: dict[str, Any] | str) -> AuditRecord:
    """Parse an ``AuditRecord`` from a dict or JSON string.

    Args:
        data: A Python dictionary or JSON string.

    Returns:
        A validated ``AuditRecord`` instance.

    Raises:
        SIPValidationError: If the data is invalid or fails validation.
    """
    return _parse_model(AuditRecord, data, label="AuditRecord")  # type: ignore[return-value]


def parse_discovery_request(data: dict[str, Any] | str) -> DiscoveryRequest:
    """Parse a ``DiscoveryRequest`` from a dict or JSON string.

    Args:
        data: A Python dictionary or JSON string.

    Returns:
        A validated ``DiscoveryRequest`` instance.

    Raises:
        SIPValidationError: If the data is invalid or fails validation.
    """
    return _parse_model(DiscoveryRequest, data, label="DiscoveryRequest")  # type: ignore[return-value]


def parse_discovery_response(data: dict[str, Any] | str) -> DiscoveryResponse:
    """Parse a ``DiscoveryResponse`` from a dict or JSON string.

    Args:
        data: A Python dictionary or JSON string.

    Returns:
        A validated ``DiscoveryResponse`` instance.

    Raises:
        SIPValidationError: If the data is invalid or fails validation.
    """
    return _parse_model(DiscoveryResponse, data, label="DiscoveryResponse")  # type: ignore[return-value]


__all__ = [
    "to_dict",
    "to_json",
    "parse_audit_record",
    "parse_capability_descriptor",
    "parse_discovery_request",
    "parse_discovery_response",
    "parse_execution_plan",
    "parse_intent_envelope",
    "parse_negotiation_result",
]
