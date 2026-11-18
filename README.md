# SERP Rank Tracker

Track where a domain ranks in Google, Bing or DuckDuckGo for a list of keywords, by country, language, city and device, and keep every check in a local SQLite file. Each check also records whether the page showed a Google AI Overview and whether that overview cites the domain, plus featured snippet and People Also Ask presence. `report` shows what moved since the previous check; `export` writes the history to CSV, JSON or JSONL.

[![CI](https://github.com/quanticdata-io/serp-rank-tracker/actions/workflows/ci.yml/badge.svg)](https://github.com/quanticdata-io/serp-rank-tracker/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Searches go through the [QuanticData SERP API](https://quanticdata.io/docs/) (`POST /v1/scraper/serp`), so you need an API key. Everything else (matching, history, movement, export) runs on your machine and stores nothing anywhere else.

## Install

The package is not on PyPI. Install it from source (Python 3.10 or later):

```bash
pip install git+https://github.com/quanticdata-io/serp-rank-tracker
```

or from a clone, for development:

```bash
git clone https://github.com/quanticdata-io/serp-rank-tracker
cd serp-rank-tracker
pip install -e .
```

The command is `serp-rank` (also `python -m serp_rank_tracker`). The only dependency is `httpx`.

## Quickstart

```bash
export QUANTICDATA_API_KEY=qd_live_your_key        # PowerShell: $env:QUANTICDATA_API_KEY = "qd_live_your_key"

cat > keywords.txt <<'EOF'
# one keyword per line
what is a sitemap xml
how does robots.txt work
EOF

serp-rank track -d wikipedia.org -k keywords.txt -c us -l en \
  --location "New York, New York, United States" --depth 20
```

```text
what is a sitemap xml: #5
how does robots.txt work: #2
serp-rank: stored 2 check(s) in ranks.db
```

Run the same command again later (by hand, from cron or from a scheduled CI job) and compare. This is the output of two runs a few seconds apart on 18 November 2026, so nothing moved (and the second run was served from the API cache):

```bash
serp-rank report
```

```text
keyword                   pos  prev  change  status  AIO  cited  where                                                checked_at
how does robots.txt work  2    2     0       same    yes  no     google us New York, New York, United States desktop  2026-11-18T13:53:07Z
what is a sitemap xml     5    5     0       same    yes  no     google us New York, New York, United States desktop  2026-11-18T13:53:06Z
```

Positions are found even when Google gives only its click address: `en.wikipedia.org › wiki › Sitemaps` at #5 counts for `wikipedia.org`.

```bash
serp-rank export -o history.csv
```

## What is recorded

One row per keyword per run. The columns, in this order, are the same in SQLite, CSV, JSON and JSONL:

| Column | Meaning |
| --- | --- |
| `checked_at` | UTC time of the check |
| `keyword`, `domain` | What was searched and which domain was looked for |
| `engine`, `country`, `lang`, `location`, `device` | How it was searched (see options) |
| `position` | 1-based position of the domain's first organic result, empty when it was not found within `depth` |
| `url` | That result's URL, when the engine gave it (see Limits) |
| `display_link`, `title` | That result's display link and title |
| `all_positions` | Every position held by the domain (`;`-separated in CSV) |
| `organic_count` | Organic results the engine returned |
| `depth` | Organic results asked for |
| `ai_overview` | The page showed an AI Overview |
| `ai_overview_cites_domain` | The domain is among the overview's references |
| `featured_snippet`, `featured_snippet_domain` | A featured snippet was shown, and it is the domain's |
| `people_also_ask` | Number of People Also Ask questions |
| `from_cache` | The API served the search from its 24-hour cache |
| `search_url` | The engine URL that was searched |

`report` adds, per series (same keyword, domain, engine, country, language, location and device): `previous_position`, `change` (positive means up) and `status`, one of `new`, `up`, `down`, `same`, `entered`, `lost`, `not ranking`.

## Commands and options

```text
serp-rank track  [KEYWORD ...] -d DOMAIN [options]
serp-rank report [--db FILE] [-d DOMAIN] [-f table|csv|json]
serp-rank export [--db FILE] [-o FILE] [-f csv|json|jsonl] [-d DOMAIN] [--keyword K] [--since DATE]
```

`track`:

| Option | Meaning |
| --- | --- |
| `KEYWORD ...` | Keywords on the command line |
| `-d, --domain` | Domain to look for (`example.com`; a URL is accepted and reduced to its host, `www.` is ignored). Required |
| `-k, --keywords-file` | One keyword per line, `#` comments and blank lines skipped, duplicates removed; `-` reads stdin |
| `--db` | SQLite file (default `ranks.db`, created on first use) |
| `-e, --engine` | `google` (default), `bing` or `duckduckgo` |
| `-c, --country` | Country code passed to the API, for example `us` |
| `-l, --lang` | Interface language, for example `en` |
| `--location` | Search from this place, for example `"Austin, Texas, United States"`. Set it when you compare runs: Google ranks by city |
| `--device` | `desktop` (default), `mobile`, `ios` or `android` |
| `--depth` | Organic results to look through, 1 to 100 (default 10). Sent as `num`; for Google the API fetches and merges consecutive pages |
| `--no-subdomains` | Count only the exact domain (by default `blog.example.com` counts for `example.com`) |
| `--delay` | Seconds to wait between searches (default 0) |
| `-o, --output` | Also write this run's rows to a `.csv`, `.json` or `.jsonl` file |
| `-q, --quiet` | No per-keyword lines on stderr |

Exit codes: `0` every keyword was checked, `1` some keywords failed (they are listed on stderr and the others are stored), `2` a usage, key, balance or input error stopped the run.

`report` prints the latest check of each series and the one before it. `export` writes every stored check, oldest first; the format comes from `--format`, else from the file extension, else CSV.

Environment: `QUANTICDATA_API_KEY` (required for `track`), `QUANTICDATA_API_BASE` (default `https://api.quanticdata.io/v1`).

## Python

```python
from serp_rank_tracker import QuanticDataClient, SearchSettings, Store, Tracker

settings = SearchSettings(country="us", lang="en", location="Austin, Texas, United States", depth=20)
with QuanticDataClient() as client, Store("ranks.db") as store:  # reads QUANTICDATA_API_KEY
    tracker = Tracker(client, "example.com", settings, delay=1.0)
    for check in tracker.run(["what is a sitemap xml", "how does robots.txt work"]):
        store.add(check)
        print(check.keyword, check.position, check.ai_overview_cites_domain)
    for move in store.movements(domain="example.com"):
        print(move.latest["keyword"], move.status, move.change)
```

`check_from_payload(payload, keyword=..., domain=..., settings=...)` turns any `/scraper/serp` payload you already have into a `Check`, without a network call. More in [`examples/`](examples/).

## How it calls QuanticData

One request per keyword per run, `POST https://api.quanticdata.io/v1/scraper/serp` with `Authorization: Bearer $QUANTICDATA_API_KEY` and a body built only from documented fields:

```json
{"query": "what is a sitemap xml", "engine": "google", "num": 20, "country": "us", "lang": "en",
 "location": "New York, New York, United States"}
```

A trimmed answer, as returned on 18 November 2026 (click addresses shortened):

```json
{
  "type": "response",
  "message": "SERP successful",
  "payload": {
    "search_metadata": {
      "status": "Success", "engine": "google", "path": "http", "from_cache": true,
      "search_url": "https://www.google.com/search?q=what%20is%20a%20sitemap%20xml&gl=us&hl=en&uule=...",
      "paging": {"requested_num": 20, "page_size": 10, "pages_planned": 2, "pages_fetched": 2, "results_merged": 17}
    },
    "search_parameters": {"engine": "google", "q": "what is a sitemap xml", "device": "desktop", "country": "us", "language": "en", "page": 1},
    "organic": [
      {"rank": 1, "title": "What is an XML sitemap and why should you have one? - Yoast",
       "link": "https://www.google.com/url?q=...", "display_link": "yoast.com › SEO blog › Technical SEO"},
      {"rank": 3, "title": "Free Online Sitemap Generator | XML Sitemaps for Google and Bing",
       "link": "https://www.xml-sitemaps.com/", "display_link": "www.xml-sitemaps.com", "source": "xml-sitemaps.com"}
    ],
    "ai_overview": "An XML sitemap is a structured text file written in Extensible Markup Language (XML) that lists ...",
    "ai_overview_references": [],
    "people_also_ask": [],
    "featured_snippet": null,
    "pagination": {"current": 1, "next": null, "available_pages": [1, 2], "has_next": false}
  }
}
```

Errors are reported as typed exceptions: 400 `InputError` (the message names the parameter; the run stops), 401 `AuthenticationError`, 402 `PaymentRequiredError`, 429 `RateLimitError`. A 429 is retried up to twice, after `Retry-After` when it is 60 seconds or less; the API documents that a 429 is never billed. A 5xx is not retried. Identical searches within 24 hours are served from the API cache at no charge (`from_cache`), so running the same keywords twice in a day does not show new movement. Each search is billed per success; see [pricing](https://quanticdata.io/pricing/).

## Limits

- **Positions are what one search saw.** Results vary by location, device, personalisation and time of day. Fix `--location` and `--device` for a series and compare like with like; do not read one-place moves as a trend.
- **Ranking URL can be missing.** Google often links results through its own click address and the API then has no direct URL. The domain is still found from the result's `source` or `display_link`, and `display_link` is stored, but `url` stays empty for that row.
- **Organic results only.** Ads, local packs, shopping and video carousels are not counted as positions.
- **AI Overview citation depends on the references the API returns.** `ai_overview` is set from the overview text; `ai_overview_cites_domain` is set only when `ai_overview_references` lists the domain. On the searches checked while writing this tool, `ai_overview_references` came back empty even when an overview was shown, so treat `false` there as "not known to cite", not as "does not cite". The parsing of those references is tested against a synthetic fixture.
- **Depth.** Up to 100 results per search; the engine may return fewer when it runs out.
- **Bing and DuckDuckGo** return fewer rich blocks; AI Overview fields apply to Google.
- The SQLite file is local. To keep history from scheduled CI runs, commit or upload `ranks.db` as an artifact between runs.

## Running against the real API

Tests never call the network. To try the tool against the real API, set `QUANTICDATA_API_KEY` in your environment (create a key on the API keys page of the [QuanticData dashboard](https://quanticdata.io/)) and run the Quickstart. Each keyword costs one search.

## Responsible use

Track keywords for sites you own or are entitled to analyse, keep the volume proportionate, and respect the terms that apply to you. Search results are third-party content: do not republish them wholesale. The tool collects no personal data beyond what appears in public search results; do not use it to profile people.

## Development

```bash
uv venv && uv pip install -e . --group dev      # or: pip install -e . pytest pytest-cov mypy ruff
ruff check . && ruff format --check . && mypy && pytest
```

Tests run against `httpx.MockTransport` with responses recorded from the real API (sanitised) in `tests/fixtures/`. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE)
