"""
Custom exceptions for API clients.
"""
from __future__ import annotations


class APIClientError(RuntimeError):
    """
    Generic API client error.
    """

    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class APIRateLimitError(APIClientError):
    """
    Raised when the API indicates that a rate limit has been hit.
    """


class APINotFoundError(APIClientError):
    """
    Raised when a requested resource is not found.
    """
