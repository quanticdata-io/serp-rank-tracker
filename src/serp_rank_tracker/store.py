"""SQLite history of checks, with movement between the two latest checks."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import COLUMNS, Check

SCHEMA = """
CREATE TABLE IF NOT EXISTS checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    checked_at TEXT NOT NULL,
    keyword TEXT NOT NULL,
    domain TEXT NOT NULL,
    engine TEXT NOT NULL,
    country TEXT,
    lang TEXT,
    location TEXT,
    device TEXT NOT NULL,
    position INTEGER,
    url TEXT,
    display_link TEXT,
    title TEXT,
    all_positions TEXT NOT NULL,
    organic_count INTEGER NOT NULL,
    depth INTEGER NOT NULL,
    ai_overview INTEGER NOT NULL,
    ai_overview_cites_domain INTEGER NOT NULL,
    featured_snippet INTEGER NOT NULL,
    featured_snippet_domain INTEGER NOT NULL,
    people_also_ask INTEGER NOT NULL,
    from_cache INTEGER NOT NULL,
    search_url TEXT
);
CREATE INDEX IF NOT EXISTS checks_series ON checks (domain, keyword, engine, country, location, device);
"""

_BOOL_COLUMNS = frozenset(
    {"ai_overview", "ai_overview_cites_domain", "featured_snippet", "featured_snippet_domain", "from_cache"}
)
#: Columns that identify one tracked series (same keyword, searched the same way).
SERIES = ("domain", "keyword", "engine", "country", "lang", "location", "device")


@dataclass
class Movement:
    """Latest check of a series compared with the one before it."""

    latest: dict[str, Any]
    previous: dict[str, Any] | None

    @property
    def change(self) -> int | None:
        """Positive = moved up. ``None`` when either check has no position."""
        if self.previous is None:
            return None
        now, before = self.latest["position"], self.previous["position"]
        if now is None or before is None:
            return None
        return int(before) - int(now)

    @property
    def status(self) -> str:
        if self.previous is None:
            return "new"
        now, before = self.latest["position"], self.previous["position"]
        if now is None and before is None:
            return "not ranking"
        if now is None:
            return "lost"
        if before is None:
            return "entered"
        change = self.change or 0
        return "up" if change > 0 else "down" if change < 0 else "same"


def _decode(row: sqlite3.Row) -> dict[str, Any]:
    data = {k: row[k] for k in COLUMNS}
    data["all_positions"] = json.loads(data["all_positions"] or "[]")
    for key in _BOOL_COLUMNS:
        data[key] = bool(data[key])
    return data


class Store:
    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        self._db = sqlite3.connect(self.path)
        self._db.row_factory = sqlite3.Row
        self._db.executescript(SCHEMA)

    def close(self) -> None:
        self._db.close()

    def __enter__(self) -> Store:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def add(self, check: Check) -> None:
        row = check.as_row()
        row["all_positions"] = json.dumps(row["all_positions"])
        for key in _BOOL_COLUMNS:
            row[key] = int(row[key])
        names = ", ".join(COLUMNS)
        marks = ", ".join(f":{c}" for c in COLUMNS)
        with self._db:
            self._db.execute(f"INSERT INTO checks ({names}) VALUES ({marks})", row)

    def add_many(self, checks: Iterable[Check]) -> int:
        count = 0
        for check in checks:
            self.add(check)
            count += 1
        return count

    def rows(
        self, *, domain: str | None = None, keyword: str | None = None, since: str | None = None
    ) -> Iterator[dict[str, Any]]:
        """Every stored check, oldest first, optionally filtered."""
        clauses, args = [], []
        if domain:
            clauses.append("domain = ?")
            args.append(domain)
        if keyword:
            clauses.append("keyword = ?")
            args.append(keyword)
        if since:
            clauses.append("checked_at >= ?")
            args.append(since)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        cursor = self._db.execute(f"SELECT * FROM checks {where} ORDER BY checked_at, id", args)
        for row in cursor:
            yield _decode(row)

    def movements(self, *, domain: str | None = None) -> list[Movement]:
        """One :class:`Movement` per series, sorted by keyword."""
        series: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
        for row in self.rows(domain=domain):
            series.setdefault(tuple(row[k] for k in SERIES), []).append(row)
        result = [
            Movement(latest=checks[-1], previous=checks[-2] if len(checks) > 1 else None)
            for checks in series.values()
        ]
        result.sort(key=lambda m: (m.latest["domain"], m.latest["keyword"], m.latest["engine"]))
        return result
