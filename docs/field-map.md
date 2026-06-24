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
| `osaamisalat` | **toteutus** | `metadata.osaamisalat` | Specialisations (career signal); two shapes — see below |
| teaching | **toteutus** | `metadata.opetus` | Language/format/time (koodi lists), duration (`suunniteltuKestoVuodet`/`Kuukaudet`), fees (`maksut`) |
| `yhteyshenkilot` | **toteutus** | `metadata.yhteyshenkilot` | Contacts (`nimi`, `sahkoposti`, ...) |
| provider | **toteutus** | `organisaatio.nimi` | Implementing institution (may differ from koulutus organisaatio) |
| `tutkintonimike` | koulutus | `metadata.tutkintonimike` | Degree title — koodi objects (see below) |
| `koulutusala` | koulutus | `metadata.koulutusala` | Field of study — koodi object |
| credits | koulutus / toteutus | `metadata.opintojenLaajuusNumero` + `…yksikko` | Study extent, e.g. "120 opintopistettä" |
| `lisatiedot` | koulutus | `metadata.lisatiedot[]` | Titled additional-info sections (`{otsikko, teksti}`) |
| `eqf` / `nqf` | koulutus | `eqf`, `nqf` | Qualification framework level — koodi objects |
| linked implementations | koulutus | `toteutukset[]` | Embedded objects (with `metadata`) when `?toteutukset=true` |

## Value shapes

The tool saves these verbatim; this is what consumers of the raw JSON will see.
The External API wraps classified values as **koodi objects**:

- `tutkintonimike`, `eqf`, `nqf`, `koulutusala`, `opetus.opetuskieli/opetustapa/opetusaika`:
  `[{"koodiUri": "eqf_7", "nimi": {"fi": ..., "sv": ..., "en": ...}}]`.
- `ammattinimikkeet`, `asiasanat`: `[{"kieli": "fi", "arvo": "..."}]`.
- `osaamisalat`: two shapes — korkeakoulu items carry `nimi` directly; vocational
  (`amm`) items carry it under `koodi.nimi`.
- `lisatiedot`: `[{"otsikko": <koodi>, "teksti": <multilingual HTML>}]`.
- `opetus`: object with the koodi lists above plus `suunniteltuKestoVuodet/Kuukaudet`
  (duration), `maksut` (`[{maksullisuustyyppi, maksunMaara}]`), and `lisatiedot`.
- free text (`kuvaus`, `osaamistavoitteet`, `nimi`): `{"fi": ..., "sv": ..., "en": ...}` with HTML.

`osaamistavoitteet` and `kuvaus` exist on **both** koulutus and toteutus; the
toteutus value is the institution-specific one.

## No dedicated career fields

There is **no** `uramahdollisuudet` (career opportunities), `tyollistyminen`
(employment) or `jatkoopintomahdollisuudet` (further study) field anywhere in
the konfo-backend API — confirmed against the Swagger spec and a sample of 20
programmes / 217 implementations. The "Uramahdollisuudet" sections visible on
the opintopolku.fi website are not exposed as structured fields. The career
signal therefore comes from `ammattinimikkeet` (job titles) + `asiasanat`
(keywords) + `osaamisalat` (specialisations) + `osaamistavoitteet` (learning
goals), and occasionally from free text in `lisatiedot` / `kuvaus`.
