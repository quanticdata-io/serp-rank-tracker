"""Minimal client for the QuanticData SERP endpoint.

Only one documented endpoint is called (see https://quanticdata.io/docs/):

- ``POST /scraper/serp``  one search on Google, Bing or DuckDuckGo, returned as JSON

Every answer uses the envelope ``{"type": "response"|"error", "message": ..., "payload": ...}``.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Mapping
from typing import Any

import httpx

from ._version import __version__

DEFAULT_BASE_URL = "https://api.quanticdata.io/v1"
ENV_API_KEY = "QUANTICDATA_API_KEY"
ENV_API_BASE = "QUANTICDATA_API_BASE"
SERP_PATH = "/scraper/serp"


class QuanticDataError(Exception):
    """The API answered with the error envelope, or could not be reached."""

    def __init__(self, message: str, *, status: int | None = None, payload: Any = None) -> None:
        super().__init__(message)
        self.message = message
        self.status = status
        self.payload = payload

    @property
    def code(self) -> str | None:
        if isinstance(self.payload, Mapping):
            code = self.payload.get("code")
            return code if isinstance(code, str) else None
        return None


class AuthenticationError(QuanticDataError):
    """HTTP 401: missing, unknown, disabled or expired API key."""


class PaymentRequiredError(QuanticDataError):
    """HTTP 402: the free tier and the balance cannot cover the call, or the spend cap is reached."""


class InputError(QuanticDataError):
    """HTTP 400: a parameter broke a rule; the message names it."""


class RateLimitError(QuanticDataError):
    """HTTP 429: rate limit, or the engine blocked every attempt (never billed).

    ``retry_after`` is in seconds when the API sent it.
    """

    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        payload: Any = None,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message, status=status, payload=payload)
        self.retry_after = retry_after


def _retry_after(response: httpx.Response) -> float | None:
    header = response.headers.get("retry-after")
    if header:
        try:
            return max(0.0, float(header))
        except ValueError:
            return None
    return None


class QuanticDataClient:
    """Calls ``POST /scraper/serp`` with retries on 429 and on connection errors.

    A 429 is never billed, so retrying it is safe. A 5xx is not retried: the
    answer is reported to the caller.
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str | None = None,
        timeout: float = 90.0,
        max_retries: int = 2,
        default_retry_wait: float = 5.0,
        max_retry_wait: float = 60.0,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        key = api_key or os.environ.get(ENV_API_KEY, "").strip()
        if not key:
            raise AuthenticationError(
                f"No API key: pass api_key or set {ENV_API_KEY}. "
                "Create one on the API keys page of the QuanticData dashboard."
            )
        self.base_url = (base_url or os.environ.get(ENV_API_BASE) or DEFAULT_BASE_URL).rstrip("/")
        self.max_retries = max_retries
        self.default_retry_wait = default_retry_wait
        self.max_retry_wait = max_retry_wait
        self._sleep = sleep
        self._http = httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            transport=transport,
            headers={
                "Authorization": f"Bearer {key}",
                "User-Agent": f"serp-rank-tracker/{__version__}",
                "Accept": "application/json",
            },
        )

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> QuanticDataClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def search(self, params: Mapping[str, Any]) -> dict[str, Any]:
        """Runs one search and returns the ``payload`` of the answer."""
        attempt = 0
        while True:
            try:
                response = self._http.post(SERP_PATH, json=dict(params))
            except httpx.TransportError as exc:
                if attempt < self.max_retries:
                    attempt += 1
                    self._sleep(min(self.default_retry_wait * attempt, self.max_retry_wait))
                    continue
                raise QuanticDataError(f"Could not reach {self.base_url}: {exc}") from exc
            try:
                return self._handle(response)
            except RateLimitError as exc:
                wait = exc.retry_after if exc.retry_after is not None else self.default_retry_wait
                if attempt < self.max_retries and wait <= self.max_retry_wait:
                    attempt += 1
                    self._sleep(wait)
                    continue
                raise

    @staticmethod
    def _handle(response: httpx.Response) -> dict[str, Any]:
        try:
            body: Any = response.json()
        except ValueError:
            body = None
        envelope = body if isinstance(body, Mapping) else {}
        payload = envelope.get("payload")
        message = str(envelope.get("message") or response.reason_phrase or "Unexpected answer")
        status = response.status_code
        if 200 <= status < 300 and isinstance(payload, Mapping):
            return dict(payload)
        if status == 401:
            raise AuthenticationError(message, status=status, payload=payload)
        if status == 402:
            raise PaymentRequiredError(message, status=status, payload=payload)
        if status == 400:
            raise InputError(message, status=status, payload=payload)
        if status == 429:
            raise RateLimitError(message, status=status, payload=payload, retry_after=_retry_after(response))
        raise QuanticDataError(f"HTTP {status}: {message}", status=status, payload=payload)
