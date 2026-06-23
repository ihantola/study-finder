# study-finder

Extract and analyze study programme descriptions and learning goals from
[opintopolku.fi](https://opintopolku.fi), Finland's national study-information
service. The initial focus is on computer-science / ICT related programmes,
though the exact scope is still an open question (see
[Open questions](#open-questions)).

> Status: working extractor. The `study_finder` package fetches and normalizes
> ICT programmes from the live API; see [Usage](#usage). The API contract has
> been verified — see [`docs/field-map.md`](docs/field-map.md).

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

This has now been verified against live data (full mapping in
[`docs/field-map.md`](docs/field-map.md)). The career-relevant fields all live
under `metadata`:

| Field | Lives on | Meaning |
| --- | --- | --- |
| `osaamistavoitteet` | toteutus & koulutus | Learning goals (toteutus preferred) |
| `kuvaus` | toteutus & koulutus | Description |
| `ammattinimikkeet` | toteutus | **Job titles** — the strongest career signal |
| `asiasanat` | toteutus | Keywords |
| `tutkintonimike` | koulutus | Degree title |

Learning goals confirm the earlier hypothesis: they exist on both entities, but
the toteutus text is the institution-specific one we prefer. There are no
dedicated `tyollistyminen` / `jatko-opinnot` fields — the career signal comes
from `ammattinimikkeet` + `asiasanat` + `osaamistavoitteet`.

Content is available in up to three languages (Finnish, Swedish, English) as
`{"fi": ..., "sv": ..., "en": ...}` blocks and contains HTML. The extractor
strips the HTML and picks a language by priority order (default `fi,en,sv`).
Finnish text needs Finnish-aware NLP tooling, so decide which language(s) you
care about before any analysis step.

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

The extractor is a CLI. It defaults to fetching **one** programme so a quick
test never crawls the whole catalogue — raise `--limit` deliberately.

```bash
# Fetch a single programme by oid (best for a quick test). Accepts either a
# koulutus oid (1.2.246.562.13.…) or a toteutus oid (1.2.246.562.17.…):
python -m study_finder --oid 1.2.246.562.13.00000000000000002744

# Fetch the first N programmes from the ICT field of study (default: 1):
python -m study_finder --limit 1
python -m study_finder --limit 20 --out data/processed/ict.csv

# Free-text keyword search within ICT:
python -m study_finder --keyword tietojenkäsittely --limit 5

# Fetch ALL ICT programmes from universities of applied sciences + universities.
# --koulutusala defaults to ICT; --all paginates through every match (~180
# programmes, a few minutes on first run; responses are then cached):
python -m study_finder --koulutustyyppi amk,yo --all --out data/processed/ict_amk_yo.csv
```

Output is a CSV (default `data/processed/ict_programmes.csv`) with one row per
(programme, implementation), including `job_titles`, `keywords`,
`specializations`, `learning_goals`, `description`, `field_of_study`, `credits`
and `additional_info`.

> The konfo-backend API has **no** dedicated "uramahdollisuudet" (career
> opportunities), "työllistyminen" or "jatko-opinnot" field — those website
> sections aren't exposed as structured data. The career signal comes from job
> titles + keywords + specialisations + learning goals (and sometimes free text
> in `additional_info`). See [`docs/field-map.md`](docs/field-map.md).

Useful flags: `--lang fi,en,sv` (text language priority), `--no-cache` (bypass
the cache), `-v` (verbose). Run `python -m study_finder --help` for all options.

### Being a polite API client

The HTTP client (`study_finder/client.py`):

- sends a generic `User-Agent` and `Caller-Id` — **no personal email**,
- throttles between live requests (`KONFO_THROTTLE_SECONDS`, default 0.5s),
- retries transient failures (429 / 5xx) with exponential backoff,
- caches every raw response under `data/raw/`, so re-runs don't re-hit the API.

All of these are configurable via environment variables (see
`study_finder/config.py`), optionally through a `.env` file.

## Running the tests

```bash
pytest
```

Tests are fully offline — they use saved fixtures and mocked HTTP
(`responses`), so they never touch the live API.

## Roadmap

1. ~~**Confirm the data model**~~ — done; see [`docs/field-map.md`](docs/field-map.md).
2. ~~**Extract & store**~~ — done; the CLI normalizes programmes to CSV.
3. **Pull a sample** — fetch the ICT field at a higher `--limit`, inspect ~20
   entries, and let that reveal where the real CS boundary is.
4. **Decide the CS-focus strategy** — see [Open questions](#open-questions).
5. **Analyze** — once the analytical question is sharp enough to test against.

## Open questions

These are genuinely undecided, not decisions waiting to be written down:

- **How to scope "CS related"?** The extractor currently filters by field of
  study (`koulutusala` / ICT), which is broad (~350 programmes, including e.g.
  acoustics). Tighter options still on the table:
  1. Keyword search over titles and descriptions (`--keyword`).
  2. Classify CS-vs-not from the description text.
  Suggested next move: pull the whole ICT field, look at ~20 entries, and let
  the data show where the real boundary is.
- **Which language(s)?** fi / sv / en — the extractor keeps a priority order
  (default `fi,en,sv`); the analysis-time choice still drives NLP tooling.
- **What is the actual analytical question?** "Compare learning goals" is a
  direction, not yet something you can test an answer against. Sharpen this
  before investing in analysis code.

## License

[MIT](LICENSE) © 2026 Petri Ihantola