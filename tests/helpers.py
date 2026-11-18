from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx

from serp_rank_tracker import QuanticDataClient

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return data


def payload(name: str) -> dict[str, Any]:
    body = load(name)
    result: dict[str, Any] = body["payload"]
    return result


Handler = Callable[[httpx.Request], httpx.Response]


def make_client(handler: Handler, *, sleeps: list[float] | None = None) -> QuanticDataClient:
    record = sleeps if sleeps is not None else []
    return QuanticDataClient(
        "qd_test_key",
        base_url="https://api.test/v1",
        transport=httpx.MockTransport(handler),
        sleep=record.append,
    )


def fixture_by_query(mapping: dict[str, str], seen: list[dict[str, Any]] | None = None) -> Handler:
    """Answers each search with the fixture registered for its query."""

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if seen is not None:
            seen.append(body)
        name = mapping.get(body.get("query", ""))
        if name is None:
            return httpx.Response(400, json=load("error_400.json"))
        return httpx.Response(200, json=load(name))

    return handler
