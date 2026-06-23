# study-finder: opintopolku.fi extraction service

## Context

We want a Python service that extracts study-programme data from Finland's
opintopolku.fi via its open **konfo-backend** API, focused on
computer-science / ICT programmes, and pulls out the fields needed to later
analyze **career paths** (employment outlook, further-study options, job
titles, learning goals). The repo today is just a README + requirements files;
there is no code yet. We want to be a polite API citizen (throttle, sane
`User-Agent`, cache responses) **without putting a personal email into
requests**.

Two facts shape the design:
- The data model splits into `koulutus` (the programme) and `toteutus` (an
  institution-specific implementation). Career/learning-goal text is expected
  to live mostly on `toteutus` — this must be verified against live data
  before building extraction.
- The exact API path prefix is not yet confirmed from this environment (DNS to
  the API was unreachable during planning). Candidates are
  `/konfo-backend/search/koulutukset` + `/konfo-backend/koulutus/{oid}` vs. an
  `/external/...` prefix. **Swagger is the source of truth** — Step 0 confirms
  the real paths before anything else is wired up.

## Decisions / defaults (adjustable)

- **CS scope**: start by filtering search to the ICT field of study
  (`koulutusala` level-1 code `06`, koodisto URI
  `kansallinenkoulutusluokitus2016koulutusalataso1_06`), pull the whole field,
  then inspect a sample to find the real CS boundary. Keyword/classification
  refinement is a later step, not v1.
- **Languages**: extraction keeps **all** available languages (`fi`/`sv`/`en`)
  for each text field; analysis picks a language later. No NLP in v1.
- **Scope of v1**: this is an *extraction* service — fetch, normalize, store.
  Actual career-path analysis is out of scope here (the analytical question is
  still being sharpened); we just make sure the career-relevant raw fields land
  in clean storage.
- **Politeness**: a `requests.Session` with a generic `User-Agent`
  (`study-finder/0.1 (+https://github.com/<org>/study-finder)`) and `Caller-Id:
  study-finder` header — no personal email. Throttle between requests, retry
  with backoff, and cache raw JSON so re-runs don't re-hit the API.

## Proposed structure

A `study_finder/` package plus a thin CLI:

```
study_finder/
  __init__.py
  config.py        # base URL, language(s), throttle delay, cache dir — via python-dotenv + defaults
  client.py        # polite requests.Session: headers, throttle, retry/backoff, GET helper + on-disk raw cache
  api.py           # endpoint functions (paths confirmed in Step 0)
  extract.py       # normalize raw koulutus/toteutus JSON -> flat records, multilingual-aware
  storage.py       # save raw JSON to data/raw/, write normalized data to CSV (pandas)
  cli.py           # `python -m study_finder ...` entry points
data/
  raw/             # cached raw API responses (gitignored)
  processed/       # normalized CSVs
tests/
  test_extract.py  # uses `responses` to mock HTTP / fixture JSON
docs/
  field-map.md     # output of Step 0: where each field lives (koulutus vs toteutus)
```

## Implementation steps

### Step 0 — Confirm the API contract (do this first, against live API)
Write a tiny throwaway script (or notebook) that:
1. Fetches the Swagger/OpenAPI doc and confirms the **real paths** for: search
   koulutukset, get koulutus by oid, get toteutus by oid, and how a koulutus
   links to its toteutukset.
2. Runs one ICT search, picks one `oid`, fetches the koulutus and one toteutus.
3. Records — in `docs/field-map.md` — the exact JSON paths and which entity
   holds each career-relevant field:
   `osaamistavoitteet`, `tyollistyminen`/`työllistyminen`,
   `jatko-opintomahdollisuudet`, `tutkintonimike`, `ammattinimikkeet`,
   description (`kuvaus`/`metadata.kuvaus`) blocks, and the multilingual shape
   (`{"fi","sv","en"}`).
Save a couple of sample responses under `data/raw/` to use as test fixtures.
This step replaces guesses with verified field names before any extraction code.

### Step 1 — `config.py` + `client.py`
- `config.py`: dataclass / constants for `BASE_URL`, `LANGUAGES`,
  `THROTTLE_SECONDS` (e.g. 0.5–1.0s), `CACHE_DIR`, all overridable via env
  (`python-dotenv`).
- `client.py`: a `KonfoClient` wrapping `requests.Session`. Sets polite headers
  (generic `User-Agent`, `Caller-Id` — **no email**), sleeps `THROTTLE_SECONDS`
  between calls, retries on 429/5xx with exponential backoff, and a `get_json()`
  that reads/writes a raw-response cache keyed by URL so reruns are free.

### Step 2 — `api.py`
Thin functions over the client, using paths confirmed in Step 0:
- `search_koulutukset(koulutusala=ICT, page, size)` — paginates the full ICT field.
- `get_koulutus(oid)`, `get_toteutus(oid)`.
- `iter_toteutukset_for(koulutus)` — using whatever linking mechanism Step 0 found.

### Step 3 — `extract.py`
- A `pick_lang(value, langs)` helper for the `{"fi","sv","en"}` blocks.
- `normalize_koulutus(...)` / `normalize_toteutus(...)` that flatten the
  verified career-relevant fields into plain dict records, joining a programme
  to its implementation(s). One row per (koulutus, toteutus) is the likely grain.

### Step 4 — `storage.py` + `cli.py`
- `storage.py`: dump raw JSON to `data/raw/`; build a `pandas.DataFrame` from
  normalized records and write `data/processed/ict_programmes.csv`.
- `cli.py`: a command that runs the whole pipeline (search ICT → fetch details
  → normalize → save), with flags for language and sample size.
- Add `data/raw/` (and optionally `data/processed/`) to `.gitignore`.

### Step 5 — Tests
- `tests/test_extract.py`: feed the Step-0 sample JSON through `normalize_*`
  and assert the career fields are extracted and language selection works. Use
  `responses` to mock the client where an HTTP round-trip is needed. No live
  network in tests.

## Files to create
- `study_finder/{__init__,config,client,api,extract,storage,cli}.py`
- `tests/test_extract.py`
- `docs/field-map.md`
- `.gitignore` (add `data/raw/`, `.venv/`, `__pycache__/`)
- Update `README.md` once Step 0 resolves the open data-model questions.

Reuse the already-declared deps: `requests`, `pandas`, `python-dotenv`
(runtime) and `pytest`, `responses`, `ruff`, `jupyter` (dev) — no new
dependencies needed.

## Verification
- **Step 0 is its own verification**: it proves the endpoints and field
  locations are real, not assumed.
- `pytest` passes against the saved sample fixtures (offline).
- End-to-end smoke run: `python -m study_finder <fetch command> --size 20`
  produces `data/processed/ict_programmes.csv` with ~20 rows that contain the
  career-relevant columns populated, and `data/raw/` holds the cached
  responses. Re-running pulls from cache (no new API hits) — confirming the
  polite-client behavior.
- Manual spot-check: open the CSV, confirm a known ICT programme appears with
  sensible learning-goal / employment text.
