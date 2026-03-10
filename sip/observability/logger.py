"""Structured logging helpers for SIP.

Provides a configured logger that emits structured log records with SIP
trace context attached. All logging uses the standard library ``logging``
module — no third-party logging frameworks required.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any


def get_logger(name: str) -> logging.Logger:
    """Return a named logger for SIP components.

    Respects the ``SIP_LOG_LEVEL`` environment variable (default: INFO).
    If ``SIP_JSON_LOGGING=true``, a JSON formatter is attached.

    Args:
        name: Logger name, typically ``__name__`` of the calling module.

    Returns:
        Configured standard library Logger.
    """
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler()
        log_level = os.getenv("SIP_LOG_LEVEL", "INFO").upper()
        level = getattr(logging, log_level, logging.INFO)
        logger.setLevel(level)
        handler.setLevel(level)

        use_json = os.getenv("SIP_JSON_LOGGING", "false").lower() in ("1", "true", "yes")
        if use_json:
            handler.setFormatter(_JsonFormatter())
        else:
            handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                    datefmt="%Y-%m-%dT%H:%M:%SZ",
                )
            )

        logger.addHandler(handler)
        logger.propagate = False

    return logger


class _JsonFormatter(logging.Formatter):
    """Formats log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        data: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%SZ"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "trace_id"):
            data["trace_id"] = record.trace_id  # type: ignore[attr-defined]
        if hasattr(record, "intent_id"):
            data["intent_id"] = record.intent_id  # type: ignore[attr-defined]
        if record.exc_info:
            data["exception"] = self.formatException(record.exc_info)
        return json.dumps(data)


def log_with_context(
    logger: logging.Logger,
    level: int,
    message: str,
    trace_id: str | None = None,
    intent_id: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """Log a message with optional SIP trace context.

    Args:
        logger: Logger to use.
        level: Logging level (e.g. logging.INFO).
        message: The log message.
        trace_id: Optional trace ID for correlation.
        intent_id: Optional intent ID for correlation.
        extra: Additional fields to include in the log record.
    """
    log_extra: dict[str, Any] = extra or {}
    if trace_id:
        log_extra["trace_id"] = trace_id
    if intent_id:
        log_extra["intent_id"] = intent_id
    logger.log(level, message, extra=log_extra)
