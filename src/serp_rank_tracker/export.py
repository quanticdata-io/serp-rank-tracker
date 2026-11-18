"""CSV, JSON and JSONL writers for stored checks."""

from __future__ import annotations

import csv
import json
from collections.abc import Iterable, Mapping
from typing import Any, TextIO

from .models import COLUMNS

FORMATS = ("csv", "json", "jsonl")


def format_from_path(path: str | None, default: str = "csv") -> str:
    if path:
        suffix = path.rsplit(".", 1)[-1].lower() if "." in path else ""
        if suffix in FORMATS:
            return suffix
    return default


def _csv_value(value: Any) -> Any:
    if isinstance(value, list):
        return ";".join(str(v) for v in value)
    if isinstance(value, bool):
        return "true" if value else "false"
    return "" if value is None else value


def write_rows(rows: Iterable[Mapping[str, Any]], out: TextIO, fmt: str) -> int:
    count = 0
    if fmt == "csv":
        writer = csv.DictWriter(out, fieldnames=list(COLUMNS), lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: _csv_value(row.get(k)) for k in COLUMNS})
            count += 1
    elif fmt == "jsonl":
        for row in rows:
            out.write(json.dumps({k: row.get(k) for k in COLUMNS}, ensure_ascii=False) + "\n")
            count += 1
    elif fmt == "json":
        items = [{k: row.get(k) for k in COLUMNS} for row in rows]
        json.dump(items, out, ensure_ascii=False, indent=2)
        out.write("\n")
        count = len(items)
    else:
        raise ValueError(f"Unknown format {fmt!r}; use one of {', '.join(FORMATS)}")
    return count
