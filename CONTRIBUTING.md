# Contributing

Thanks for helping improve the tracker.

## Setup

```bash
git clone https://github.com/quanticdata-io/serp-rank-tracker
cd serp-rank-tracker
uv venv && uv pip install -e . --group dev
```

Plain pip works too: `pip install -e . pytest pytest-cov mypy ruff`.

## Checks

CI runs these on Python 3.10 to 3.13, on Ubuntu and Windows:

```bash
ruff check .
ruff format --check .
mypy
pytest
```

## Ground rules

- Tests never call the QuanticData API or a search engine. Use `httpx.MockTransport` through `tests/helpers.py`.
- Fixtures in `tests/fixtures/` are real API answers with Google click addresses shortened to `redacted-N` and billing fields removed, or synthetic files whose name starts with `synthetic_` and whose `_comment` says what they stand for. Never commit a key, and use `example.com`-style domains for anything invented.
- The tool sends only parameters documented for `POST /scraper/serp` at https://quanticdata.io/docs/.
- The output columns (`serp_rank_tracker.models.COLUMNS`) are a public contract: adding a column is a minor release, renaming or removing one is a major release. A new column also needs a SQLite migration in `store.py`.
- User-facing changes need a CHANGELOG entry under "Unreleased".

## Fixing a wrong position

1. Export the check with `serp-rank export -f json --keyword "..."` and save the raw API answer for that search (remove any key and shorten click addresses).
2. Add it under `tests/fixtures/` with a failing test in `tests/test_models.py`.
3. Fix `domains.py` or `models.py` until the whole suite passes.
