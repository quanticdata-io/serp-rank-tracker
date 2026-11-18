"""Check a few keywords for a domain, store them, then print what moved.

    export QUANTICDATA_API_KEY=qd_live_your_key
    python examples/weekly_report.py example.com

Each run costs one search per keyword (see https://quanticdata.io/pricing/).
"""

from __future__ import annotations

import sys

from serp_rank_tracker import QuanticDataClient, SearchSettings, Store, Tracker

KEYWORDS = ["what is a sitemap xml", "how does robots.txt work"]


def main(domain: str) -> None:
    settings = SearchSettings(country="us", lang="en", location="Austin, Texas, United States", depth=20)
    with QuanticDataClient() as client, Store("ranks.db") as store:
        tracker = Tracker(client, domain, settings, delay=1.0)
        for check in tracker.run(KEYWORDS):
            store.add(check)
        for failure in tracker.failures:
            print(f"failed: {failure.keyword}: {failure.error.message}", file=sys.stderr)
        for move in store.movements(domain=tracker.domain):
            print(f"{move.latest['keyword']}: {move.latest['position']} ({move.status})")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "example.com")
