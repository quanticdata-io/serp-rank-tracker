"""``serp-rank`` command line."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, TextIO

from ._version import __version__
from .api import QuanticDataClient, QuanticDataError
from .export import FORMATS, format_from_path, write_rows
from .models import SearchSettings
from .store import Movement, Store
from .tracker import Tracker, read_keywords

DEFAULT_DB = "ranks.db"
ENGINES = ("google", "bing", "duckduckgo")
DEVICES = ("desktop", "mobile", "ios", "android")


def _depth(value: str) -> int:
    number = int(value)
    if not 1 <= number <= 100:
        raise argparse.ArgumentTypeError("depth must be between 1 and 100")
    return number


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="serp-rank",
        description="Track a domain's search positions for a list of keywords, with SQLite history.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    track = sub.add_parser("track", help="search each keyword now and store the result")
    track.add_argument("keywords", nargs="*", help="keywords (or use --keywords-file)")
    track.add_argument("-d", "--domain", required=True, help="domain to look for, e.g. example.com")
    track.add_argument("-k", "--keywords-file", help="file with one keyword per line ('-' = stdin)")
    track.add_argument("--db", default=DEFAULT_DB, help=f"SQLite history file (default {DEFAULT_DB})")
    track.add_argument("-e", "--engine", choices=ENGINES, default="google")
    track.add_argument("-c", "--country", help="two-letter country code, e.g. us")
    track.add_argument("-l", "--lang", help="interface language, e.g. en")
    track.add_argument("--location", help='search from this place, e.g. "Austin, Texas, United States"')
    track.add_argument("--device", choices=DEVICES, default="desktop")
    track.add_argument(
        "--depth", type=_depth, default=10, help="organic results to look through, 1-100 (default 10)"
    )
    track.add_argument(
        "--no-subdomains", action="store_true", help="do not count blog.example.com as example.com"
    )
    track.add_argument("--delay", type=float, default=0.0, help="seconds between searches (default 0)")
    track.add_argument("-o", "--output", help="also write this run's checks to a file (.csv/.json/.jsonl)")
    track.add_argument("-q", "--quiet", action="store_true", help="no per-keyword lines on stderr")

    report = sub.add_parser(
        "report", help="latest position per keyword and the movement since the check before"
    )
    report.add_argument("--db", default=DEFAULT_DB)
    report.add_argument("-d", "--domain", help="only this domain")
    report.add_argument("-f", "--format", choices=("table", "csv", "json"), default="table")

    export = sub.add_parser("export", help="every stored check as CSV, JSON or JSONL")
    export.add_argument("--db", default=DEFAULT_DB)
    export.add_argument("-o", "--output", help="output file (default stdout)")
    export.add_argument("-f", "--format", choices=FORMATS, help="default: from the file extension, else csv")
    export.add_argument("-d", "--domain", help="only this domain")
    export.add_argument("--keyword", help="only this keyword")
    export.add_argument("--since", help="only checks at or after this ISO date, e.g. 2026-11-01")
    return parser


def _open_out(path: str | None) -> TextIO:
    if not path or path == "-":
        return sys.stdout
    return open(path, "w", encoding="utf-8", newline="")


def _keywords(args: argparse.Namespace) -> list[str]:
    lines: list[str] = list(args.keywords)
    if args.keywords_file:
        if args.keywords_file == "-":
            lines += sys.stdin.read().splitlines()
        else:
            lines += Path(args.keywords_file).read_text(encoding="utf-8").splitlines()
    return read_keywords(lines)


def cmd_track(args: argparse.Namespace, client: QuanticDataClient | None = None) -> int:
    keywords = _keywords(args)
    if not keywords:
        print("serp-rank: no keywords (pass them as arguments or with --keywords-file)", file=sys.stderr)
        return 2
    settings = SearchSettings(
        engine=args.engine,
        country=args.country,
        lang=args.lang,
        location=args.location,
        device=args.device,
        depth=args.depth,
    )
    owns_client = client is None
    client = client or QuanticDataClient()
    checks = []
    try:
        tracker = Tracker(client, args.domain, settings, subdomains=not args.no_subdomains, delay=args.delay)
        with Store(args.db) as store:
            for check in tracker.run(keywords):
                store.add(check)
                checks.append(check)
                if not args.quiet:
                    where = f"#{check.position}" if check.position else f"not in top {check.organic_count}"
                    aio = " | AI Overview cites it" if check.ai_overview_cites_domain else ""
                    print(f"{check.keyword}: {where}{aio}", file=sys.stderr)
    finally:
        if owns_client:
            client.close()
    for failure in tracker.failures:
        print(f"serp-rank: {failure.keyword}: {failure.error.message}", file=sys.stderr)
    if args.output:
        out = _open_out(args.output)
        try:
            write_rows((c.as_row() for c in checks), out, format_from_path(args.output))
        finally:
            if out is not sys.stdout:
                out.close()
    print(f"serp-rank: stored {len(checks)} check(s) in {args.db}", file=sys.stderr)
    return 1 if tracker.failures else 0


def _movement_row(m: Movement) -> dict[str, Any]:
    latest, previous = m.latest, m.previous
    return {
        "keyword": latest["keyword"],
        "domain": latest["domain"],
        "engine": latest["engine"],
        "country": latest["country"],
        "location": latest["location"],
        "device": latest["device"],
        "position": latest["position"],
        "previous_position": previous["position"] if previous else None,
        "change": m.change,
        "status": m.status,
        "url": latest["url"],
        "ai_overview": latest["ai_overview"],
        "ai_overview_cites_domain": latest["ai_overview_cites_domain"],
        "checked_at": latest["checked_at"],
        "previous_checked_at": previous["checked_at"] if previous else None,
    }


def _table(rows: list[dict[str, Any]], out: TextIO) -> None:
    headers = ("keyword", "pos", "prev", "change", "status", "AIO", "cited", "where", "checked_at")
    body = []
    for r in rows:
        where = " ".join(str(v) for v in (r["engine"], r["country"], r["location"], r["device"]) if v)
        change = r["change"]
        body.append(
            (
                r["keyword"],
                "-" if r["position"] is None else str(r["position"]),
                "-" if r["previous_position"] is None else str(r["previous_position"]),
                "" if change is None else (f"{change:+d}" if change else "0"),
                r["status"],
                "yes" if r["ai_overview"] else "no",
                "yes" if r["ai_overview_cites_domain"] else "no",
                where,
                r["checked_at"],
            )
        )
    widths = [max(len(h), *(len(row[i]) for row in body)) if body else len(h) for i, h in enumerate(headers)]
    out.write("  ".join(h.ljust(w) for h, w in zip(headers, widths, strict=False)).rstrip() + "\n")
    for row in body:
        out.write("  ".join(v.ljust(w) for v, w in zip(row, widths, strict=False)).rstrip() + "\n")


def cmd_report(args: argparse.Namespace) -> int:
    if not Path(args.db).exists():
        print(f"serp-rank: {args.db} does not exist yet; run 'serp-rank track' first", file=sys.stderr)
        return 2
    with Store(args.db) as store:
        rows = [_movement_row(m) for m in store.movements(domain=args.domain)]
    if args.format == "json":
        json.dump(rows, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    elif args.format == "csv":
        writer = csv.DictWriter(sys.stdout, fieldnames=list(rows[0]) if rows else [], lineterminator="\n")
        if rows:
            writer.writeheader()
            writer.writerows({k: "" if v is None else v for k, v in r.items()} for r in rows)
    else:
        _table(rows, sys.stdout)
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    if not Path(args.db).exists():
        print(f"serp-rank: {args.db} does not exist yet; run 'serp-rank track' first", file=sys.stderr)
        return 2
    fmt = args.format or format_from_path(args.output)
    out = _open_out(args.output)
    try:
        with Store(args.db) as store:
            count = write_rows(
                store.rows(domain=args.domain, keyword=args.keyword, since=args.since), out, fmt
            )
    finally:
        if out is not sys.stdout:
            out.close()
    if args.output:
        print(f"serp-rank: wrote {count} check(s) to {args.output}", file=sys.stderr)
    return 0


def main(argv: Sequence[str] | None = None, *, client: QuanticDataClient | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "track":
            return cmd_track(args, client)
        if args.command == "report":
            return cmd_report(args)
        return cmd_export(args)
    except QuanticDataError as exc:
        print(f"serp-rank: {exc.message}", file=sys.stderr)
        return 2
    except (OSError, ValueError) as exc:
        print(f"serp-rank: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
