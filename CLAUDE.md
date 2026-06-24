# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A CLI tool that downloads CS/ICT **toteutukset** (implementations) from Finland's
opintopolku.fi via its open `konfo-backend` API and saves the **raw JSON**, one
file per toteutus, for later analysis. There is intentionally no normalization
layer — the raw API responses are the product. A koulutus (programme) is fetched
to discover its toteutukset and is embedded into each saved toteutus under a
`koulutus` key (so degree-level info like `koulutusala` is preserved).

## Commands

```bash
# Setup
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt        # runtime + dev (test/lint) tooling

# Tests (fully offline — saved fixtures + mocked HTTP via `responses`)
pytest                                       # all tests
pytest tests/test_fetch.py::test_cli_writes_one_file_per_toteutus_from_koulutus  # single test

# Lint / format
ruff check .
ruff format .

# Run against the live API (defaults to ONE programme — see "Politeness")
python -m study_finder --oid <oid>           # toteutus …17… (that one) or koulutus …13… (all its toteutukset)
python -m study_finder --limit 1             # toteutukset of first N ICT programmes
python -m study_finder --koulutustyyppi amk,yo --all   # every ICT toteutus (paginates)
python -m study_finder --help                # all flags

# Faster iteration: disable the polite delay (default is 2–10s random)
KONFO_THROTTLE_MIN_SECONDS=0 KONFO_THROTTLE_MAX_SECONDS=0 python -m study_finder --limit 2
```

## Architecture

Small package `study_finder/`, layered so each module has one job. Data flows:
**search/fetch koulutus (api) → cache (client) → pull out embedded toteutukset →
write one raw JSON file per toteutus (cli)**.

- `config.py` — `Config` dataclass; every field is overridable via env var
  (loaded from `.env`). Defines `ICT_KOULUTUSALA`, the koodisto URI used as the
  default field-of-study filter.
- `client.py` — `KonfoClient`, the only module that does HTTP. Owns politeness
  (a random per-request delay + retry/backoff) and an on-disk raw-response cache
  keyed by URL hash under `data/raw/`. Cache hits short-circuit before any
  network call (so they skip the delay too).
- `api.py` — thin endpoint functions over `KonfoClient` (`search_koulutukset`,
  `search_oids` which paginates, `get_koulutus`, `get_toteutus`, and
  `toteutukset()` which pulls the embedded toteutus objects out of a koulutus).
  No business logic.
- `cli.py` / `__main__.py` — argparse entry point. Resolves oids (single `--oid`:
  a toteutus saves that one, a koulutus saves all its toteutukset; or a paginated
  search over koulutukset), collects the toteutus objects (each with its parent
  koulutus embedded under a `koulutus` key via `_toteutukset_with_parent`, the
  parent's own `toteutukset` stripped), prints an upfront estimate + live ETA,
  and writes one `<oid>.json` per toteutus to `--out-dir` (default
  `data/toteutukset/`). Turns API/404 errors into a clean message + exit code 1.

There is deliberately **no** extraction/normalization module — the saved JSON is
the raw API response. If you need a flattened/CSV view, build it as a separate
downstream step over the saved JSON rather than re-adding a pipeline here.

### Data model

The API has two linked entities (full verified mapping in
[`docs/field-map.md`](docs/field-map.md)):

- `koulutus` — the programme. Fetched with `?toteutukset=true` so its
  `toteutukset[]` (implementations) are embedded with full `metadata`.
- `toteutus` — an institution-specific implementation, with the richest career
  fields (`ammattinimikkeet`, `asiasanat`, `osaamisalat`, `opetus`,
  `yhteyshenkilot`). Fetched with `?koulutus=true` so its parent is embedded.

Notable fields under `metadata`: `osaamistavoitteet` (learning goals), `kuvaus`,
`ammattinimikkeet` (job titles), `asiasanat`, `osaamisalat`, `opetus` (teaching),
`tutkintonimike`, `koulutusala`, `lisatiedot`. Classified values are **koodi
objects** (`{"koodiUri", "nimi": {fi,sv,en}}`); free text is `{fi,sv,en}` with
HTML; term lists are `[{"kieli","arvo"}]`. There is **no** `uramahdollisuudet` /
`tyollistyminen` / `jatko-opinnot` field — those website sections aren't exposed.

### API specifics

- Base URL is `https://opintopolku.fi/konfo-backend`. The
  `konfo-backend.opintopolku.fi` host in some docs does **not** resolve.
- Use **only `External`-tagged endpoints** from the Swagger spec
  (`/konfo-backend/swagger.yaml`): `/external/search/koulutukset`,
  `/external/koulutus/{oid}`, `/external/toteutus/{oid}`.

## Conventions / gotchas

- **Politeness is a hard requirement**: the client sends a generic
  `User-Agent`/`Caller-Id` and **never a personal email**, and waits a random
  delay (`KONFO_THROTTLE_MIN_SECONDS`..`KONFO_THROTTLE_MAX_SECONDS`, default
  2–10s) between live requests. `--limit` defaults to 1 so a test never crawls
  the full catalogue — preserve that safety default. The site's robots.txt
  declares `crawl-delay: 30` (advisory; our API paths aren't in its Disallow
  list) — keep the default delay conservative and easy to raise toward 30s.
- Route all HTTP through `KonfoClient`; tests must not hit the live API — use the
  fixtures in `tests/fixtures/` and the `responses` library to mock HTTP.
- The whole `data/` dir (cache in `data/raw/`, output in `data/toteutukset/`) is gitignored.
- Python 3.10+; modules use `from __future__ import annotations`.
