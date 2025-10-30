"""
HTTP utilities shared by API clients.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Union

import requests
from requests import Response
from requests.adapters import HTTPAdapter
from requests.auth import HTTPBasicAuth
from urllib3.util.retry import Retry

try:
    from requests_aws4auth import AWS4Auth
except ImportError:  # pragma: no cover - optional dependency
    AWS4Auth = None  # type: ignore

from .exceptions import APIClientError, APINotFoundError, APIRateLimitError


class HTTPClient:
    """
    Thin wrapper around requests.Session with retries and error mapping.
    """

    def __init__(
        self,
        base_url: str,
        *,
        auth_token: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
        aws_sigv4: Optional[Dict[str, Union[str, None]]] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        retry = Retry(
            total=max_retries,
            read=max_retries,
            connect=max_retries,
            backoff_factor=backoff_factor,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET", "POST"),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self.session.headers.update({"Accept": "application/json"})
        if auth_token:
            self.session.headers.update({"Authorization": f"Bearer {auth_token}"})
        self.session_auth = None
        if username and password and not aws_sigv4:
            self.session_auth = HTTPBasicAuth(username, password)
        self.aws_auth = None
        if aws_sigv4 and AWS4Auth is not None:
            access_key = aws_sigv4.get("access_key")
            secret_key = aws_sigv4.get("secret_key")
            region = aws_sigv4.get("region")
            service = aws_sigv4.get("service") or "execute-api"
            if access_key and secret_key and region:
                self.aws_auth = AWS4Auth(access_key, secret_key, region, service)  # type: ignore[arg-type]
        if self.session_auth is not None:
            self.session.auth = self.session_auth

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Any] = None,
    ) -> Any:
        """
        Perform an HTTP request and return decoded JSON.
        """
        url = f"{self.base_url}/{path.lstrip('/')}"
        try:
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                json=json,
                timeout=self.timeout,
                auth=self.aws_auth or self.session_auth,
            )
        except requests.RequestException as exc:
            raise APIClientError(str(exc)) from exc

        self._raise_for_status(response)
        if not response.content:
            return None
        content_type = response.headers.get("Content-Type", "").lower()
        if "application/json" not in content_type:
            raise APIClientError(
                f"Unexpected content type '{content_type or 'unknown'}' from API response."
            )
        try:
            return response.json()
        except ValueError as exc:
            raise APIClientError("Failed to parse JSON response from API.") from exc

    def _raise_for_status(self, response: Response) -> None:
        """
        Map HTTP errors to custom exceptions.
        """
        if 200 <= response.status_code < 300:
            return
        status = response.status_code
        message = f"API request failed with status {status}"
        if status == 404:
            raise APINotFoundError(message, status_code=status)
        if status == 429:
            raise APIRateLimitError(message, status_code=status)
        raise APIClientError(message, status_code=status)
