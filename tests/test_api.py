from __future__ import annotations

import json

import httpx
import pytest

from serp_rank_tracker import (
    AuthenticationError,
    InputError,
    PaymentRequiredError,
    QuanticDataClient,
    QuanticDataError,
    RateLimitError,
)

from .helpers import load, make_client


def test_sends_bearer_key_and_json_body() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=load("google_sitemap_xml.json"))

    with make_client(handler) as client:
        result = client.search({"query": "what is a sitemap xml", "num": 20})
    assert result["search_parameters"]["q"] == "what is a sitemap xml"
    request = seen[0]
    assert request.method == "POST"
    assert str(request.url) == "https://api.test/v1/scraper/serp"
    assert request.headers["authorization"] == "Bearer qd_test_key"
    assert json.loads(request.content) == {"query": "what is a sitemap xml", "num": 20}


def test_missing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("QUANTICDATA_API_KEY", raising=False)
    with pytest.raises(AuthenticationError):
        QuanticDataClient()


def test_key_and_base_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QUANTICDATA_API_KEY", "qd_test_env")
    monkeypatch.setenv("QUANTICDATA_API_BASE", "http://127.0.0.1:9/v1/")
    with QuanticDataClient() as client:
        assert client.base_url == "http://127.0.0.1:9/v1"


def test_400_is_an_input_error() -> None:
    client = make_client(lambda r: httpx.Response(400, json=load("error_400.json")))
    with pytest.raises(InputError, match="Missing required field: query"):
        client.search({})


@pytest.mark.parametrize(("status", "error"), [(401, AuthenticationError), (402, PaymentRequiredError)])
def test_account_errors(status: int, error: type[QuanticDataError]) -> None:
    client = make_client(lambda r: httpx.Response(status, json={"type": "error", "message": "no"}))
    with pytest.raises(error):
        client.search({"query": "q"})


def test_429_is_retried_after_retry_after() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, json=load("error_429.json"), headers={"Retry-After": "3"})
        return httpx.Response(200, json=load("bing_python_http_client.json"))

    sleeps: list[float] = []
    client = make_client(handler, sleeps=sleeps)
    assert client.search({"query": "q"})["organic"]
    assert sleeps == [3.0]
    assert calls["n"] == 2


def test_429_gives_up_after_max_retries() -> None:
    sleeps: list[float] = []
    client = make_client(lambda r: httpx.Response(429, json=load("error_429.json")), sleeps=sleeps)
    with pytest.raises(RateLimitError):
        client.search({"query": "q"})
    assert sleeps == [5.0, 5.0]


def test_long_retry_after_is_not_waited() -> None:
    sleeps: list[float] = []
    client = make_client(
        lambda r: httpx.Response(429, json=load("error_429.json"), headers={"Retry-After": "600"}),
        sleeps=sleeps,
    )
    with pytest.raises(RateLimitError) as info:
        client.search({"query": "q"})
    assert info.value.retry_after == 600.0
    assert sleeps == []


def test_5xx_is_not_retried() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(500, json={"type": "error", "message": "Scraper unavailable"})

    with pytest.raises(QuanticDataError, match="HTTP 500"):
        make_client(handler).search({"query": "q"})
    assert calls["n"] == 1


def test_connection_error_is_retried_then_reported() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    sleeps: list[float] = []
    with pytest.raises(QuanticDataError, match="Could not reach"):
        make_client(handler, sleeps=sleeps).search({"query": "q"})
    assert len(sleeps) == 2
