"""Trace ID helpers for SIP observability."""

from __future__ import annotations

from uuid import uuid4


def new_trace_id() -> str:
    """Generate a new random trace ID."""
    return str(uuid4())


def new_span_id() -> str:
    """Generate a new random span ID."""
    return str(uuid4())


def child_span_id() -> str:
    """Generate a span ID for a child span (same format as span_id for now)."""
    return str(uuid4())
