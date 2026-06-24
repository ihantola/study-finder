# study-finder

Download raw study-programme data from
[opintopolku.fi](https://opintopolku.fi), Finland's national study-information
service, for later analysis. The initial focus is on computer-science / ICT
related programmes, though the exact scope is still an open question (see
[Open questions](#open-questions)).

> Status: working downloader. The `study_finder` package fetches **toteutukset**
> (implementations) from the live API and saves the **raw JSON**, one file per
> toteutus (no normalization — the API responses are the product); see
> [Usage](#usage). The data model is documented in
> [`docs/field-map.md`](docs/field-map.md); how the code fits together is in
> [`docs/architecture.md`](docs/architecture.md).

## Why an API instead of scraping

opintopolku.fi is backed by an open, documented API called **konfo-backend**.
Hitting the API directly is more stable than scraping HTML and returns
structured JSON. Treat the Swagger documentation as the source of truth for
endpoint paths and parameters rather than hardcoding paths that haven't been
verified.

- **Base URL**: `https://opintopolku.fi/konfo-backend`
- Swagger docs: https://opintopolku.fi/konfo-backend/swagger
  (spec: https://opintopolku.fi/konfo-backend/swagger.yaml)

This tool uses **only the `External`-tagged endpoints** from the spec:
`/external/search/koulutukset`, `/external/koulutus/{oid}` and
`/external/toteutus/{oid}`. Fetching a programme with `?toteutukset=true` embeds
its implementations (with full metadata) in a single request.

> Note: the API is served under the main `opintopolku.fi` domain. The
> `konfo-backend.opintopolku.fi` host that appears in some docs does **not**
> resolve.

## Data model

Two entities matter most, and they are separate:

- **`koulutus`** — the programme / qualification itself. Carries a
  `toteutukset[]` list linking to its implementations.
- **`toteutus`** — an institution-specific *implementation* of a programme.

The tool saves the **whole** raw `toteutus` object (every field preserved), with
the parent `koulutus` embedded under a `koulutus` key — so degree-level info is
kept too. The most useful fields (verified against live data, full mapping in
[`docs/field-map.md`](docs/field-map.md)) live under `metadata` (toteutus) or
`koulutus.metadata` (programme):

| Field | Lives on | Meaning |
| --- | --- | --- |
| `osaamistavoitteet` | toteutus & koulutus | Learning goals |
| `kuvaus` | toteutus & koulutus | Description |
| `ammattinimikkeet` | toteutus | Job titles (career signal) |
| `asiasanat` | toteutus | Keywords |
| `osaamisalat` | toteutus | Specialisations |
| `opetus` | toteutus | Teaching: language/format/time, duration, fees, plus `lisatiedot` |
| `yhteyshenkilot` | toteutus | Contacts |
| `tutkintonimike` | koulutus | Degree title |
| `koulutusala` | koulutus | Field of study |
| `lisatiedot` | koulutus | Titled additional-info sections |

There are **no** dedicated `uramahdollisuudet` (career opportunities),
`tyollistyminen` (employment) or `jatko-opinnot` (further study) fields in the
API — those website sections aren't exposed as structured data. The career
signal comes from `ammattinimikkeet` + `asiasanat` + `osaamisalat` +
`osaamistavoitteet` (and occasionally free text in `lisatiedot`).

Text is available in up to three languages as `{"fi": ..., "sv": ..., "en": ...}`
blocks and contains HTML; that is preserved verbatim in the raw output. Finnish
text needs Finnish-aware NLP tooling, so decide which language(s) you care about
before any analysis step.

## Requirements

- Python 3.10+

Dependencies are split into two files:

| File | Purpose |
| --- | --- |
| `requirements.txt` | Runtime dependencies needed to fetch and analyze data |
| `requirements-dev.txt` | Adds testing, linting and notebook tooling |

## Setup

```bash
# Clone and enter the repo
git clone https://github.com/<your-org>/study-finder.git
cd study-finder

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# Install runtime deps...
pip install -r requirements.txt

# ...or install everything for development
pip install -r requirements-dev.txt
```

## Usage

The downloader is a CLI. It defaults to fetching **one** programme so a quick
test never crawls the whole catalogue — raise `--limit` deliberately.

```bash
# Fetch by oid. A toteutus oid (1.2.246.562.17.…) saves that implementation; a
# koulutus oid (1.2.246.562.13.…) saves all of its toteutukset:
python -m study_finder --oid 1.2.246.562.17.00000000000000003821

# Fetch toteutukset of the first N ICT programmes (default: 1):
python -m study_finder --limit 1
python -m study_finder --limit 20 --out-dir data/ict

# Free-text keyword search within ICT:
python -m study_finder --keyword tietojenkäsittely --limit 5

# Fetch every ICT toteutus from universities of applied sciences + universities.
# --koulutusala defaults to ICT; --all paginates through every match (~180
# programmes). With the default 2–10s random delay this takes ~15–20 min on the
# first run; responses are then cached so re-runs are instant:
python -m study_finder --koulutustyyppi amk,yo --all --out-dir data/ict_amk_yo
```

Output is **one JSON file per toteutus**, named `<toteutus-oid>.json`, written to
the output directory (default `data/toteutukset/`). Each file is the raw
`toteutus` object exactly as returned by the API, with its parent programme
embedded under a `koulutus` key (so degree-level info like `koulutusala`,
`koulutustyyppi` and `tutkintonimike` is preserved; the parent's own
`toteutukset` list is stripped to avoid duplication). See
[`docs/field-map.md`](docs/field-map.md) for what lives where.

For multi-programme runs the CLI prints an upfront time estimate and a live
progress line with a refining ETA (e.g. `[42/180] elapsed 4m 12s, ETA 13m 48s`).

Useful flags: `--no-cache` (bypass the cache), `-v` (verbose). Run
`python -m study_finder --help` for all options.

### Being a polite API client

The HTTP client (`study_finder/client.py`):

- sends a generic `User-Agent` and `Caller-Id` — **no personal email**,
- waits a **random delay** between live requests, drawn uniformly from
  `KONFO_THROTTLE_MIN_SECONDS`..`KONFO_THROTTLE_MAX_SECONDS` (default **2–10s**);
  set both to `0` to disable,
- retries transient failures (429 / 5xx) with exponential backoff,
- caches every raw response under `data/raw/`, so re-runs don't re-hit the API.

All of these are configurable via environment variables (see
`study_finder/config.py`), optionally through a `.env` file. For example, to be
extra polite per the site's robots.txt (`crawl-delay: 30`):

```bash
KONFO_THROTTLE_MIN_SECONDS=30 KONFO_THROTTLE_MAX_SECONDS=30 \
  python -m study_finder --koulutustyyppi amk,yo --all
```

## Running the tests

```bash
pytest
```

Tests are fully offline — they use saved fixtures and mocked HTTP
(`responses`), so they never touch the live API.

## Roadmap

1. ~~**Confirm the data model**~~ — done; see [`docs/field-map.md`](docs/field-map.md).
2. ~~**Download & store**~~ — done; the CLI saves raw toteutus JSON, one file each.
3. **Pull a sample** — fetch the ICT field at a higher `--limit`, inspect ~20
   entries, and let that reveal where the real CS boundary is.
4. **Decide the CS-focus strategy** — see [Open questions](#open-questions).
5. **Analyze** — once the analytical question is sharp enough to test against.

## Open questions

These are genuinely undecided, not decisions waiting to be written down:

- **How to scope "CS related"?** The downloader currently filters by field of
  study (`koulutusala` / ICT), which is broad (~350 programmes, including e.g.
  acoustics). Tighter options still on the table:
  1. Keyword search over titles and descriptions (`--keyword`).
  2. Classify CS-vs-not from the description text.
  Suggested next move: pull the whole ICT field, look at ~20 entries, and let
  the data show where the real boundary is.
- **Which language(s)?** fi / sv / en — the raw JSON keeps all three; the
  analysis-time choice still drives NLP tooling.
- **What is the actual analytical question?** "Compare learning goals" is a
  direction, not yet something you can test an answer against. Sharpen this
  before investing in analysis code.

## License

[MIT](LICENSE) © 2026 Petri Ihantola