# konfo-backend field map (verified against the live API)

Base URL: `https://opintopolku.fi/konfo-backend`
(The `konfo-backend.opintopolku.fi` host in some docs does **not** resolve.)

Verified on 2026-06-23 with the ICT field-of-study filter
`koulutusala=kansallinenkoulutusluokitus2016koulutusalataso1_06` (352 matches).

## Endpoints

Only the **External**-tagged endpoints from
[`swagger.yaml`](https://opintopolku.fi/konfo-backend/swagger.yaml) are used:

| Purpose | Path | Notes |
| --- | --- | --- |
| Search programmes | `GET /external/search/koulutukset` | params: `koulutusala`, `keyword` (min 3 chars), `size`, `page`, `lng`. Returns `{total, hits[]}`. |
| One programme | `GET /external/koulutus/{oid}` | pass `?toteutukset=true` to **embed** the implementations (with full `metadata`) in one request. No `lng` param — returns all languages. |
| One implementation | `GET /external/toteutus/{oid}` | standalone implementation fetch (not needed by the pipeline, since toteutukset are embedded above). |

`koulutus` oids look like `1.2.246.562.13.…`; `toteutus` oids like `1.2.246.562.17.…`.

## Where each field lives

Multilingual text is `{"fi": ..., "sv": ..., "en": ...}` and contains **HTML**
(`<p>…`). Term lists are `[{"kieli": "fi", "arvo": "äänisuunnittelija"}, …]`.

| Field | Entity | JSON path | Meaning |
| --- | --- | --- | --- |
| `nimi` | koulutus / hit | `nimi` | Programme name (multilingual) |
| `koulutustyyppi` | koulutus | `koulutustyyppi` | e.g. `yo`, `amk` |
| `osaamistavoitteet` | **toteutus** & koulutus | `metadata.osaamistavoitteet` | Learning goals — toteutus preferred |
| `kuvaus` | **toteutus** & koulutus | `metadata.kuvaus` | Description |
| `ammattinimikkeet` | **toteutus** | `metadata.ammattinimikkeet` | **Job titles** (career signal) |
| `asiasanat` | **toteutus** | `metadata.asiasanat` | Keywords (career signal) |
| `tutkintonimike` | koulutus | `metadata.tutkintonimike` | Degree title — koodi objects (see below) |
| `eqf` / `nqf` | koulutus | `eqf`, `nqf` | Qualification framework level — koodi objects |
| linked implementations | koulutus | `toteutukset[]` | Embedded objects (with `metadata`) when `?toteutukset=true` |

## Value shapes

The External API wraps classified values as **koodi objects** rather than the
flat shapes the internal API uses:

- `tutkintonimike`, `eqf`, `nqf`: `[{"koodiUri": "eqf_7", "nimi": {"fi": ..., "sv": ..., "en": ...}}]`
  — resolved via `extract.koodi_names` / `extract.eqf_level`.
- `ammattinimikkeet`, `asiasanat`: `[{"kieli": "fi", "arvo": "..."}]` — resolved via `extract.terms_by_lang`.
- free text (`kuvaus`, `osaamistavoitteet`, `nimi`): `{"fi": ..., "sv": ..., "en": ...}` with HTML.

The README hypothesis ("learning goals live on toteutus") is confirmed: they
exist on both, but the toteutus text is the institution-specific one we prefer.

Dedicated `tyollistyminen` / `jatkoopintomahdollisuudet` fields were **not**
present in the sampled programme; the career signal comes from
`ammattinimikkeet` + `asiasanat` + `osaamistavoitteet`.
