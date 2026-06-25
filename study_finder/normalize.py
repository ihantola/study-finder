"""Pad each raw toteutus to a fixed schema before it is saved.

The konfo-backend API omits absent fields entirely, so different toteutukset
carry different top-level key sets and different subsets of the koodisto-driven
``metadata.opetus.lisatiedot`` section headings (e.g. "Uramahdollisuudet",
"Jatko-opintomahdollisuudet"). That makes the saved files awkward to analyse:
you cannot tell "this programme has no career section" from "this key happens to
be absent in this file".

This module fills the gap. It pads every toteutus to a **fixed template** —
``TOTEUTUS_TOP_LEVEL_KEYS`` (the observed union of top-level keys) and
``LISATIEDOT_HEADINGS`` (the full koodisto of lisatiedot section headings) — so
every saved file has the same top-level keys and the same set of lisatiedot
headings, in the same order, with **empty** values where the API supplied
nothing.

It is the one deliberate exception to "raw responses are the product": it only
*adds* missing keys/headings (empty) and reorders to the template; it never
overwrites or drops data the API returned. Unknown keys/headings are preserved.

The template is fixed in this file (not derived per run) so even a single
``--oid`` fetch produces the full schema. Extend the constants if the API
introduces a new field or heading.
"""

from __future__ import annotations

# Union of top-level toteutus keys, in the API's natural order. ``koulutus`` is
# the embedded parent we attach ourselves, kept last. Missing keys are padded
# with ``None``.
TOTEUTUS_TOP_LEVEL_KEYS: tuple[str, ...] = (
    "tila",
    "kuuluuOpintokokonaisuuksiin",
    "liitetytOpintojaksot",
    "oppilaitokset",
    "teemakuva",
    "koulutukset",
    "tarjoajat",
    "liitetytOsaamismerkit",
    "modified",
    "koulutusOid",
    "externalId",
    "nimi",
    "oid",
    "kielivalinta",
    "haut",
    "koulutustyyppiPath",
    "timestamp",
    "organisaatio",
    "metadata",
    "formatoituModified",
    "koulutustyyppi",
    "koulutus",
)

# The full koodisto of ``metadata.opetus.lisatiedot`` section headings, in
# koodi order (01..12). Keyed by the exact ``otsikko.koodiUri``. A toteutus that
# omits a section gets a stub with this heading and empty ``teksti``.
LISATIEDOT_HEADINGS: dict[str, dict[str, str]] = {
    "koulutuksenlisatiedot_01#1": {"fi": "Opintojen rakenne", "sv": "Studiernas uppbyggnad", "en": "Structure of studies"},
    "koulutuksenlisatiedot_02#1": {"fi": "Jatko-opintomahdollisuudet", "sv": "Möjlighet till fortsatta studier", "en": "Further study opportunities"},
    "koulutuksenlisatiedot_03#1": {"fi": "Suuntautumisvaihtoehdot", "sv": "Inriktningsalternativ", "en": "Specialisations"},
    "koulutuksenlisatiedot_04#1": {"fi": "Uramahdollisuudet", "sv": "Karriärmöjligheter", "en": "Career opportunities"},
    "koulutuksenlisatiedot_05#1": {"fi": "Yhteistyö muiden toimijoiden kanssa", "sv": "Samarbete med andra aktörer", "en": "Co-operation with other parties"},
    "koulutuksenlisatiedot_06#1": {"fi": "Kansainvälistyminen", "sv": "Internationell verksamhet", "en": "Internationalisation"},
    "koulutuksenlisatiedot_07#1": {"fi": "Opiskeluun liittyvät materiaalikulut", "sv": "Materialkostnader inom studierna", "en": "Material costs relating to studies"},
    "koulutuksenlisatiedot_08#1": {"fi": "Kohderyhmä", "sv": "Målgrupp", "en": "Target group"},
    "koulutuksenlisatiedot_09#1": {"fi": "Koulutuksen antama pätevyys", "sv": "Kompetens som utbildningen ger", "en": "Qualification"},
    "koulutuksenlisatiedot_10#1": {"fi": "Tutkimuksen painopisteet", "sv": "Tyngdpunkter inom forskning", "en": "Research focus"},
    "koulutuksenlisatiedot_11#1": {"fi": "Opinnäytetyö", "sv": "Lärdomsprov", "en": "Thesis"},
    "koulutuksenlisatiedot_12#1": {"fi": "Sisältö", "sv": "Innehåll", "en": "Content"},
}

# Empty multilingual text block, the shape lisatiedot ``teksti`` always takes.
EMPTY_TEKSTI: dict[str, str] = {"fi": "", "sv": "", "en": ""}


def _heading_koodi_uri(item: object) -> str | None:
    """The ``otsikko.koodiUri`` of a lisatiedot item, or ``None``."""
    if not isinstance(item, dict):
        return None
    otsikko = item.get("otsikko")
    return otsikko.get("koodiUri") if isinstance(otsikko, dict) else None


def _normalize_lisatiedot(existing: object) -> list[dict]:
    """Return lisatiedot containing every heading in ``LISATIEDOT_HEADINGS`` (in
    template order, stubbed with empty text when absent), followed by any items
    the template doesn't know about — so no data is ever dropped.
    """
    items = list(existing) if isinstance(existing, list) else []
    by_uri: dict[str, dict] = {}
    for item in items:
        uri = _heading_koodi_uri(item)
        if uri is not None and uri not in by_uri:
            by_uri[uri] = item

    normalized: list[dict] = []
    placed: set[int] = set()
    for uri, nimi in LISATIEDOT_HEADINGS.items():
        item = by_uri.get(uri)
        if item is not None:
            normalized.append(item)
            placed.add(id(item))
        else:
            normalized.append({"otsikko": {"koodiUri": uri, "nimi": dict(nimi)}, "teksti": dict(EMPTY_TEKSTI)})

    # Preserve unknown headings, untyped items, and any duplicate known headings.
    for item in items:
        if id(item) not in placed:
            normalized.append(item)
    return normalized


def normalize_toteutus(toteutus: dict) -> dict:
    """Pad a raw toteutus to the fixed template.

    Returns a new dict with all of ``TOTEUTUS_TOP_LEVEL_KEYS`` present (in
    template order; missing ones ``None``) and every ``LISATIEDOT_HEADINGS``
    section present under ``metadata.opetus.lisatiedot``. Present values are
    never modified; extra keys are kept after the template ones.
    """
    if not isinstance(toteutus, dict):
        return toteutus

    result: dict = {key: toteutus.get(key) for key in TOTEUTUS_TOP_LEVEL_KEYS}
    for key, value in toteutus.items():  # keep anything the template doesn't list
        if key not in result:
            result[key] = value

    metadata = dict(result["metadata"]) if isinstance(result.get("metadata"), dict) else {}
    opetus = dict(metadata["opetus"]) if isinstance(metadata.get("opetus"), dict) else {}
    opetus["lisatiedot"] = _normalize_lisatiedot(opetus.get("lisatiedot"))
    metadata["opetus"] = opetus
    result["metadata"] = metadata
    return result
