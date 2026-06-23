# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A CLI tool that extracts CS/ICT study-programme data from Finland's
opintopolku.fi via its open `konfo-backend` API, normalizing the
career-relevant fields into a CSV for analysis.

## Commands

```bash
# Setup
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt        # runtime + dev (test/lint) tooling

# Tests (fully offline — saved fixtures + mocked HTTP via `responses`)
pytest                                       # all tests
pytest tests/test_extract.py::test_normalize_merges_koulutus_and_toteutus  # single test

# Lint / format
ruff check .
ruff format .

# Run against the live API (defaults to ONE programme — see "Politeness")
python -m study_finder --oid <koulutus-oid>  # single degree by oid
python -m study_finder --limit 1             # first N ICT programmes from search
python -m study_finder --help                # all flags
```

## Architecture

Pipeline package `study_finder/`, layered so each module has one job. Data flows:
**search/fetch (api) → cache (client) → flatten (extract) → CSV (storage)**,
orchestrated by `cli.py`.

- `config.py` — `Config` dataclass; every field is overridable via env var
  (loaded from `.env`). Defines `ICT_KOULUTUSALA`, the koodisto URI used as the
  default field-of-study filter.
- `client.py` — `KonfoClient`, the only module that does HTTP. Owns politeness
  (throttle, retry/backoff) and an on-disk raw-response cache keyed by URL hash
  under `data/raw/`. Cache hits short-circuit before any network call.
- `api.py` — thin endpoint functions over `KonfoClient` (`search_koulutukset`,
  `get_koulutus`, `get_toteutus`, `toteutus_oids`). No business logic.
- `extract.py` — pure functions (no I/O) that flatten raw JSON into records.
  This is the most test-covered module.
- `storage.py` — writes records to CSV via pandas.
- `cli.py` / `__main__.py` — argparse entry point wiring the pipeline together.

### Data model (critical to understand before editing `extract.py`)

The API has two linked entities; both are needed for a complete record:

- `koulutus` — the programme. Has a `toteutukset[]` list of linked oids.
- `toteutus` — an institution-specific implementation, with the richest
  career fields.

Output grain is **one row per (koulutus, toteutus)**. Career-relevant fields
live under `metadata`. The full verified mapping is in
[`docs/field-map.md`](docs/field-map.md) — keep it in sync when field handling
changes. Key points the extraction logic depends on:

- `osaamistavoitteet` (learning goals) and `kuvaus` (description) exist on both
  entities; `extract.normalize` **prefers the toteutus value** and falls back
  to koulutus.
- `ammattinimikkeet` (job titles) and `asiasanat` (keywords) — the strongest
  career signals — exist **only on toteutus**.
- Multilingual text is `{"fi":..., "sv":..., "en":...}` and contains **HTML**.
  `pick_lang` selects by priority order and strips HTML; term lists like
  `ammattinimikkeet` are `[{"kieli","arvo"}]` handled by `terms_by_lang`.

### API specifics

- Base URL is `https://opintopolku.fi/konfo-backend`. The
  `konfo-backend.opintopolku.fi` host in some docs does **not** resolve.
- Endpoints: `/search/koulutukset`, `/koulutus/{oid}`, `/toteutus/{oid}`.
  Treat Swagger (`/konfo-backend/swagger`) as source of truth for any new path.

## Conventions / gotchas

- **Politeness is a hard requirement**: the client sends a generic
  `User-Agent`/`Caller-Id` and **never a personal email**. `--limit` defaults to
  1 so a test never crawls the full catalogue — preserve that safety default.
- Keep `extract.py` pure (no network/disk) so tests stay offline; route all
  HTTP through `KonfoClient`.
- Tests must not hit the live API — use the fixtures in `tests/fixtures/` and
  the `responses` library to mock HTTP.
- `data/raw/` (cache) and `data/processed/` (output) are gitignored.
- Python 3.10+; modules use `from __future__ import annotations`.
