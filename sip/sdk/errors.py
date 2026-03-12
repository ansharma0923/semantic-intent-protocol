"""SDK-level exception classes for the SIP Python SDK.

These exceptions provide a clean error surface for SDK consumers, wrapping
lower-level validation and HTTP errors in a predictable hierarchy.
"""

from __future__ import annotations


class SIPError(Exception):
    """Base exception for all SIP SDK errors."""


class SIPValidationError(SIPError):
    """Raised when a SIP object fails validation.

    Attributes:
        errors: List of human-readable validation error messages.
    """

    def __init__(self, message: str, errors: list[str] | None = None) -> None:
        super().__init__(message)
        self.errors: list[str] = errors or []

    def __str__(self) -> str:
        if self.errors:
            return f"{super().__str__()}: {'; '.join(self.errors)}"
        return super().__str__()


class SIPClientError(SIPError):
    """Raised for generic client-side errors (e.g. invalid arguments, missing config)."""


class SIPHTTPError(SIPClientError):
    """Raised when an HTTP request to a SIP server returns an error response.

    Attributes:
        status_code: The HTTP status code returned by the server.
        response_body: The raw response body as a string, if available.
    """

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_body: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body

    def __str__(self) -> str:
        parts = [super().__str__()]
        if self.status_code is not None:
            parts.append(f"status={self.status_code}")
        return " ".join(parts)


__all__ = [
    "SIPError",
    "SIPValidationError",
    "SIPClientError",
    "SIPHTTPError",
]
