from __future__ import annotations

import httpx
import pytest
import respx

from scraper.config import HttpSettings
from scraper.fetcher import FetchError, Fetcher


class _FakeClock:
    """A monotonic clock for deterministic delay tests."""

    def __init__(self) -> None:
        self.now = 0.0
        self.sleep_calls: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleep_calls.append(seconds)
        self.now += seconds


def _settings(**overrides) -> HttpSettings:
    return HttpSettings(
        user_agent="test/1.0",
        delay_seconds=overrides.get("delay_seconds", 0.0),
        retries=overrides.get("retries", 2),
        timeout_seconds=overrides.get("timeout_seconds", 5.0),
        follow_redirects=True,
    )


@respx.mock
def test_fetch_returns_body_on_200():
    respx.get("https://example.com/page").mock(
        return_value=httpx.Response(200, text="<html>ok</html>")
    )
    with Fetcher(_settings()) as f:
        assert f.fetch("https://example.com/page") == "<html>ok</html>"


@respx.mock
def test_user_agent_is_sent():
    route = respx.get("https://example.com/").mock(return_value=httpx.Response(200, text=""))
    with Fetcher(_settings()) as f:
        f.fetch("https://example.com/")
    assert route.calls[0].request.headers["user-agent"] == "test/1.0"


@respx.mock
def test_4xx_does_not_retry():
    route = respx.get("https://example.com/x").mock(
        return_value=httpx.Response(404, text="missing")
    )
    clock = _FakeClock()
    with Fetcher(_settings(retries=3), sleeper=clock.sleep, monotonic=clock.monotonic) as f:
        with pytest.raises(httpx.HTTPStatusError):
            f.fetch("https://example.com/x")
    assert route.call_count == 1


@respx.mock
def test_5xx_is_retried_and_eventually_succeeds():
    respx.get("https://example.com/y").mock(
        side_effect=[
            httpx.Response(503, text=""),
            httpx.Response(502, text=""),
            httpx.Response(200, text="finally"),
        ]
    )
    clock = _FakeClock()
    with Fetcher(_settings(retries=3), sleeper=clock.sleep, monotonic=clock.monotonic) as f:
        assert f.fetch("https://example.com/y") == "finally"
    # Two backoffs between the three attempts (0.5s then 1.0s).
    assert clock.sleep_calls == [0.5, 1.0]


@respx.mock
def test_429_is_retried_like_5xx():
    respx.get("https://example.com/z").mock(
        side_effect=[
            httpx.Response(429, text=""),
            httpx.Response(200, text="ok"),
        ]
    )
    clock = _FakeClock()
    with Fetcher(_settings(retries=2), sleeper=clock.sleep, monotonic=clock.monotonic) as f:
        assert f.fetch("https://example.com/z") == "ok"


@respx.mock
def test_repeated_5xx_raises_fetch_error():
    respx.get("https://example.com/w").mock(return_value=httpx.Response(503))
    clock = _FakeClock()
    with Fetcher(_settings(retries=2), sleeper=clock.sleep, monotonic=clock.monotonic) as f:
        with pytest.raises(FetchError, match="after 3 attempts"):
            f.fetch("https://example.com/w")


@respx.mock
def test_network_error_is_retried_and_then_raised():
    respx.get("https://example.com/n").mock(side_effect=httpx.ConnectError("no route"))
    clock = _FakeClock()
    with Fetcher(_settings(retries=2), sleeper=clock.sleep, monotonic=clock.monotonic) as f:
        with pytest.raises(FetchError):
            f.fetch("https://example.com/n")
    # 3 attempts -> 2 backoffs
    assert clock.sleep_calls == [0.5, 1.0]


@respx.mock
def test_polite_delay_is_enforced_between_requests():
    respx.get("https://example.com/a").mock(return_value=httpx.Response(200, text="a"))
    respx.get("https://example.com/b").mock(return_value=httpx.Response(200, text="b"))
    clock = _FakeClock()
    with Fetcher(_settings(delay_seconds=1.0), sleeper=clock.sleep, monotonic=clock.monotonic) as f:
        f.fetch("https://example.com/a")
        clock.now += 0.3  # caller did 0.3s of work between requests
        f.fetch("https://example.com/b")
    # First fetch: no delay (no prior request).
    # Second fetch: 0.7s of delay still owed (1.0 - 0.3 elapsed).
    assert clock.sleep_calls == [pytest.approx(0.7, rel=1e-6)]


@respx.mock
def test_delay_is_skipped_when_enough_time_has_passed():
    respx.get("https://example.com/a").mock(return_value=httpx.Response(200, text="a"))
    respx.get("https://example.com/b").mock(return_value=httpx.Response(200, text="b"))
    clock = _FakeClock()
    with Fetcher(_settings(delay_seconds=0.5), sleeper=clock.sleep, monotonic=clock.monotonic) as f:
        f.fetch("https://example.com/a")
        clock.now += 2.0
        f.fetch("https://example.com/b")
    assert clock.sleep_calls == []
