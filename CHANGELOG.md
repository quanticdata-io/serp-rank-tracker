# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-11-18

### Added

- `serp-rank` CLI with `track`, `report` and `export` commands.
- Rank checks through `POST /scraper/serp` for Google, Bing and DuckDuckGo, with country, language, location, device and depth (`num`, up to 100).
- Domain matching from `source`, the result link or `display_link`, so results that Google links through its click address are still found; optional exact-domain matching.
- AI Overview presence and citation of the domain, featured snippet presence and ownership, People Also Ask count, API cache flag.
- SQLite history with movement between the two latest checks of each series (`new`, `up`, `down`, `same`, `entered`, `lost`, `not ranking`).
- CSV, JSON and JSONL export of the history or of one run.
- Typed errors for 400, 401, 402 and 429, with retries on 429 after `Retry-After`.
