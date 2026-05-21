"""HTTP fetcher with polite delay, retries, and User-Agent."""

from __future__ import annotations

import logging
import time
from typing import Protocol

import httpx

from scraper.config import HttpSettings

__all__ = ["Fetcher", "FetchError", "Sleeper"]

log = logging.getLogger(__name__)


class FetchError(RuntimeError):
    """Raised when a URL cannot be fetched after all retry attempts."""


class Sleeper(Protocol):
    def __call__(self, seconds: float) -> None: ...


class Fetcher:
    """Synchronous httpx wrapper. Use as a context manager.

    A polite delay is enforced between any two requests, regardless of which
    URL they target. Transient failures (network errors, 5xx, 429) are
    retried with exponential backoff capped by ``http.retries``.
    """

    def __init__(
        self,
        settings: HttpSettings,
        client: httpx.Client | None = None,
        sleeper: Sleeper = time.sleep,
        monotonic: callable = time.monotonic,
    ) -> None:
        self._settings = settings
        self._sleep = sleeper
        self._monotonic = monotonic
        self._owns_client = client is None
        self._client = client or httpx.Client(
            headers={"User-Agent": settings.user_agent},
            timeout=settings.timeout_seconds,
            follow_redirects=settings.follow_redirects,
        )
        self._last_request_at: float | None = None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> Fetcher:
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def fetch(self, url: str) -> str:
        self._respect_delay()
        last_exc: Exception | None = None
        attempts = self._settings.retries + 1
        for attempt in range(attempts):
            try:
                response = self._client.get(url)
            except httpx.RequestError as exc:
                last_exc = exc
                log.warning(
                    "Network error fetching %s (attempt %d/%d): %s",
                    url, attempt + 1, attempts, exc,
                )
            else:
                self._last_request_at = self._monotonic()
                status = response.status_code
                if 200 <= status < 300:
                    return response.text
                if _is_retryable_status(status):
                    last_exc = httpx.HTTPStatusError(
                        f"Server returned {status}",
                        request=response.request,
                        response=response,
                    )
                    log.warning(
                        "Retryable %d for %s (attempt %d/%d)",
                        status, url, attempt + 1, attempts,
                    )
                else:
                    # Non-retryable (4xx other than 429): bail immediately.
                    response.raise_for_status()

            if attempt + 1 < attempts:
                self._sleep(_backoff_seconds(attempt))

        raise FetchError(
            f"Failed to fetch {url} after {attempts} attempts"
        ) from last_exc

    def _respect_delay(self) -> None:
        if self._last_request_at is None or self._settings.delay_seconds <= 0:
            return
        elapsed = self._monotonic() - self._last_request_at
        remaining = self._settings.delay_seconds - elapsed
        if remaining > 0:
            self._sleep(remaining)


def _is_retryable_status(code: int) -> bool:
    return code == 429 or 500 <= code < 600


def _backoff_seconds(attempt: int) -> float:
    # 0 -> 0.5s, 1 -> 1s, 2 -> 2s, 3 -> 4s ...
    return 0.5 * (2**attempt)
