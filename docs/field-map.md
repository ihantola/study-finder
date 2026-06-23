# konfo-backend field map (verified against the live API)

Base URL: `https://opintopolku.fi/konfo-backend`
(The `konfo-backend.opintopolku.fi` host in some docs does **not** resolve.)

Verified on 2026-06-23 with the ICT field-of-study filter
`koulutusala=kansallinenkoulutusluokitus2016koulutusalataso1_06` (352 matches).

## Endpoints

| Purpose | Path | Notes |
| --- | --- | --- |
| Search programmes | `GET /search/koulutukset` | params: `koulutusala`, `keyword`, `size`, `page`, `lng`. Returns `{total, hits[], filters}`. |
| One programme | `GET /koulutus/{oid}` | param: `lng`. Carries a `toteutukset[]` list. |
| One implementation | `GET /toteutus/{oid}` | param: `lng`. Has the richest career fields. |

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
| `tutkintonimike` | koulutus | `metadata.tutkintonimike` | Degree title |
| `eqf` / `nqf` | koulutus | `eqf`, `nqf` | Qualification framework level |
| linked implementations | koulutus | `toteutukset[].oid` | How to reach toteutukset |

The README hypothesis ("learning goals live on toteutus") is confirmed: they
exist on both, but the toteutus text is the institution-specific one we prefer.

Dedicated `tyollistyminen` / `jatkoopintomahdollisuudet` fields were **not**
present in the sampled programme; the career signal comes from
`ammattinimikkeet` + `asiasanat` + `osaamistavoitteet`.
