from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from serp_rank_tracker import SearchSettings, Store, Tracker, check_from_payload, read_keywords
from serp_rank_tracker.cli import main
from serp_rank_tracker.models import Check

from .helpers import fixture_by_query, make_client, payload

QUERIES = {
    "what is a sitemap xml": "google_sitemap_xml.json",
    "best burr grinder": "synthetic_rich_blocks.json",
}
NEW_YORK = "New York, New York, United States"


def _check(position: int | None, at: str, keyword: str = "k") -> Check:
    check = check_from_payload(
        payload("synthetic_rich_blocks.json"),
        keyword=keyword,
        domain="example.com",
        settings=SearchSettings(),
        checked_at=at,
    )
    check.position = position
    return check


def test_read_keywords() -> None:
    assert read_keywords(["a", "", "# note", " b ", "a"]) == ["a", "b"]


def test_store_round_trip_and_movement(tmp_path: Path) -> None:
    with Store(tmp_path / "r.db") as store:
        store.add(_check(5, "2026-11-01T00:00:00Z"))
        store.add(_check(2, "2026-11-08T00:00:00Z"))
        store.add(_check(None, "2026-11-08T00:00:00Z", keyword="gone"))
        rows = list(store.rows())
        assert len(rows) == 3
        assert rows[0]["all_positions"] == [2, 3]
        assert rows[0]["ai_overview"] is True
        assert len(list(store.rows(since="2026-11-05"))) == 2
        moves = {m.latest["keyword"]: m for m in store.movements()}
    assert moves["k"].change == 3
    assert moves["k"].status == "up"
    assert moves["gone"].status == "new"
    assert moves["gone"].change is None


@pytest.mark.parametrize(
    ("before", "now", "status"),
    [(3, 3, "same"), (2, 6, "down"), (None, 4, "entered"), (4, None, "lost"), (None, None, "not ranking")],
)
def test_movement_status(tmp_path: Path, before: int | None, now: int | None, status: str) -> None:
    with Store(tmp_path / "r.db") as store:
        store.add(_check(before, "2026-11-01T00:00:00Z"))
        store.add(_check(now, "2026-11-02T00:00:00Z"))
        assert store.movements()[0].status == status


def test_tracker_records_failures_and_continues() -> None:
    answer = fixture_by_query(QUERIES)

    def handler(request: httpx.Request) -> httpx.Response:
        if json.loads(request.content)["query"] == "fails":
            return httpx.Response(500, json={"type": "error", "message": "unavailable"})
        return answer(request)

    tracker = Tracker(make_client(handler), "https://www.example.com/", SearchSettings(country="us"))
    checks = list(tracker.run(["best burr grinder", "fails"]))
    assert [c.position for c in checks] == [2]
    assert [f.keyword for f in tracker.failures] == ["fails"]


def test_tracker_delay_between_searches() -> None:
    sleeps: list[float] = []
    tracker = Tracker(make_client(fixture_by_query(QUERIES)), "example.com", delay=1.5, sleep=sleeps.append)
    list(tracker.run(["best burr grinder", "what is a sitemap xml"]))
    assert sleeps == [1.5]


def test_tracker_rejects_non_domain() -> None:
    with pytest.raises(ValueError, match="Not a domain"):
        Tracker(make_client(fixture_by_query({})), "localhost")


def test_cli_track_report_export(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = tmp_path / "ranks.db"
    keywords = tmp_path / "kw.txt"
    keywords.write_text("# tracked\nwhat is a sitemap xml\nbest burr grinder\n", encoding="utf-8")
    seen: list[dict[str, Any]] = []
    client = make_client(fixture_by_query(QUERIES, seen))
    out = tmp_path / "run.jsonl"
    common = ["-d", "webnode.com", "--db", str(db), "-c", "us", "-l", "en", "--location", NEW_YORK]
    assert main(["track", *common, "-k", str(keywords), "--depth", "20", "-o", str(out)], client=client) == 0
    assert seen[0] == {
        "query": "what is a sitemap xml",
        "engine": "google",
        "num": 20,
        "country": "us",
        "lang": "en",
        "location": NEW_YORK,
    }
    err = capsys.readouterr().err
    assert "what is a sitemap xml: #7" in err
    assert "best burr grinder: not in top 4" in err
    lines = out.read_text(encoding="utf-8").splitlines()
    assert json.loads(lines[0])["all_positions"] == [7, 8]

    assert main(["track", *common, "what is a sitemap xml", "--depth", "20", "-q"], client=client) == 0
    capsys.readouterr()

    assert main(["report", "--db", str(db), "-f", "json"]) == 0
    report = {r["keyword"]: r for r in json.loads(capsys.readouterr().out)}
    assert report["what is a sitemap xml"]["status"] == "same"
    assert report["what is a sitemap xml"]["previous_position"] == 7
    assert report["best burr grinder"]["status"] == "new"

    assert main(["report", "--db", str(db)]) == 0
    assert capsys.readouterr().out.splitlines()[0].startswith("keyword")

    assert main(["report", "--db", str(db), "-f", "csv"]) == 0
    assert capsys.readouterr().out.startswith("keyword,")

    export = tmp_path / "all.csv"
    assert main(["export", "--db", str(db), "-o", str(export), "--keyword", "what is a sitemap xml"]) == 0
    rows = list(csv.DictReader(io.StringIO(export.read_text(encoding="utf-8"))))
    assert len(rows) == 2
    assert rows[0]["all_positions"] == "7;8"
    assert rows[0]["ai_overview"] == "true"

    assert main(["export", "--db", str(db), "-f", "json"]) == 0
    assert len(json.loads(capsys.readouterr().out)) == 3


def test_cli_input_error_stops(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    client = make_client(fixture_by_query({}))
    assert main(["track", "-d", "example.com", "unknown", "--db", str(tmp_path / "r.db")], client=client) == 2
    assert "Missing required field" in capsys.readouterr().err


def test_cli_failure_exit_code(tmp_path: Path) -> None:
    client = make_client(lambda r: httpx.Response(500, json={"type": "error", "message": "unavailable"}))
    assert main(["track", "-d", "example.com", "a", "--db", str(tmp_path / "r.db"), "-q"], client=client) == 1


def test_cli_no_keywords_and_missing_db(tmp_path: Path) -> None:
    client = make_client(fixture_by_query({}))
    assert main(["track", "-d", "example.com", "--db", str(tmp_path / "r.db")], client=client) == 2
    assert main(["report", "--db", str(tmp_path / "missing.db")]) == 2
    assert main(["export", "--db", str(tmp_path / "missing.db")]) == 2


def test_depth_bounds() -> None:
    with pytest.raises(SystemExit):
        main(["track", "-d", "example.com", "a", "--depth", "101"])
