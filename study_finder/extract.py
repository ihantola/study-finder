"""Normalize raw koulutus/toteutus JSON into flat, analysis-ready records.

The grain of the output is one row per (koulutus, toteutus). Career-relevant
fields live in ``metadata``:
- ``osaamistavoitteet`` (learning goals) — on both entities; toteutus preferred
- ``kuvaus`` (description) — on both entities
- ``ammattinimikkeet`` (job titles) — on toteutus
- ``asiasanat`` (keywords) — on toteutus
- ``osaamisalat`` (specialisations) — on toteutus
- ``tutkintonimike`` (degree title) — on koulutus
- ``koulutusala`` (field of study) — on koulutus
- ``opintojenLaajuusNumero`` + unit (credits) — on koulutus/toteutus
- ``lisatiedot`` (titled additional-info sections) — on koulutus

Note: the konfo-backend API has no dedicated "uramahdollisuudet" (career
opportunities), "tyollistyminen" (employment) or "jatko-opinnot" (further
study) fields. Career signal comes from job titles + keywords + specialisations
+ learning goals, and occasionally from free-text in ``lisatiedot``/``kuvaus``.
"""

from __future__ import annotations

import html
import re
from typing import Any

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def strip_html(text: str) -> str:
    """Remove HTML tags and collapse whitespace from a description blob."""
    if not text:
        return ""
    text = _TAG_RE.sub(" ", text)
    text = html.unescape(text)
    return _WS_RE.sub(" ", text).strip()


def pick_lang(block: Any, languages: tuple[str, ...]) -> str:
    """Pick a string from a ``{"fi": ..., "en": ..., "sv": ...}`` block.

    Returns the first language present in ``languages`` priority order, then any
    remaining value, then "". HTML is stripped from the chosen text.
    """
    if not isinstance(block, dict) or not block:
        return ""
    for lang in languages:
        if block.get(lang):
            return strip_html(str(block[lang]))
    # fall back to any non-empty value
    for value in block.values():
        if value:
            return strip_html(str(value))
    return ""


def terms_by_lang(items: Any, languages: tuple[str, ...]) -> str:
    """Join ``[{"kieli": ..., "arvo": ...}]`` lists (e.g. ammattinimikkeet).

    Picks the first language in priority order that has any values; falls back
    to all values if none match.
    """
    if not isinstance(items, list) or not items:
        return ""
    for lang in languages:
        matched = [
            str(it.get("arvo", "")).strip()
            for it in items
            if isinstance(it, dict) and it.get("kieli") == lang and it.get("arvo")
        ]
        if matched:
            return "; ".join(matched)
    allvals = [str(it.get("arvo", "")).strip() for it in items if isinstance(it, dict) and it.get("arvo")]
    return "; ".join(allvals)


def koodi_names(value: Any, languages: tuple[str, ...]) -> str:
    """Resolve konfo "koodi" objects to a readable string.

    The external API wraps classified values as ``{"koodiUri": ..., "nimi":
    {"fi": ..., "sv": ..., "en": ...}}`` (e.g. ``tutkintonimike``), sometimes in
    a list. Returns the localized ``nimi`` value(s), joined with "; ". Falls back
    to treating ``value`` itself as a multilingual block.
    """
    if isinstance(value, list):
        names = [koodi_names(item, languages) for item in value]
        return "; ".join(name for name in names if name)
    if isinstance(value, dict) and "nimi" in value:
        return pick_lang(value["nimi"], languages)
    return pick_lang(value, languages)


def eqf_level(value: Any) -> str:
    """Extract the numeric EQF level from the koodi object(s), e.g. "7"."""
    if isinstance(value, list):
        value = value[0] if value else None
    if isinstance(value, dict):
        uri = str(value.get("koodiUri", ""))
        match = re.search(r"(\d+)", uri)
        return match.group(1) if match else ""
    match = re.search(r"(\d+)", str(value or ""))
    return match.group(1) if match else ""


def osaamisalat_names(items: Any, languages: tuple[str, ...]) -> str:
    """Join specialisation (osaamisala) names.

    Two shapes exist: korkeakoulu specialisations carry ``nimi`` directly;
    vocational (amm) ones carry the name under ``koodi.nimi``.
    """
    if not isinstance(items, list):
        return ""
    names = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = pick_lang(item.get("nimi"), languages) or koodi_names(item.get("koodi"), languages)
        if name:
            names.append(name)
    return "; ".join(names)


def lisatiedot_text(items: Any, languages: tuple[str, ...]) -> str:
    """Flatten titled additional-info sections (``lisatiedot``).

    Each item is ``{"otsikko": <koodi>, "teksti": <multilingual HTML>}``. Renders
    as ``Heading: text`` sections joined by " | ".
    """
    if not isinstance(items, list):
        return ""
    parts = []
    for item in items:
        if not isinstance(item, dict):
            continue
        heading = koodi_names(item.get("otsikko"), languages)
        body = pick_lang(item.get("teksti"), languages)
        if body:
            parts.append(f"{heading}: {body}" if heading else body)
    return " | ".join(parts)


def extent(metadata: dict[str, Any], languages: tuple[str, ...]) -> str:
    """Format the study extent, e.g. "210 opintopistettä"."""
    num = metadata.get("opintojenLaajuusNumero")
    if num is None:
        return ""
    amount = str(int(num)) if isinstance(num, float) and num.is_integer() else str(num)
    unit = koodi_names(metadata.get("opintojenLaajuusyksikko"), languages)
    return f"{amount} {unit}".strip()


def normalize(
    koulutus: dict[str, Any],
    toteutus: dict[str, Any] | None,
    languages: tuple[str, ...] = ("fi", "en", "sv"),
) -> dict[str, str]:
    """Flatten a koulutus (+ optional toteutus) into a single record."""
    k_md = koulutus.get("metadata", {}) or {}
    t_md = (toteutus or {}).get("metadata", {}) or {}

    # learning goals & description: prefer the more specific toteutus text
    learning_goals = pick_lang(t_md.get("osaamistavoitteet"), languages) or pick_lang(
        k_md.get("osaamistavoitteet"), languages
    )
    description = pick_lang(t_md.get("kuvaus"), languages) or pick_lang(k_md.get("kuvaus"), languages)

    return {
        "koulutus_oid": koulutus.get("oid", ""),
        "toteutus_oid": (toteutus or {}).get("oid", ""),
        "nimi": pick_lang(koulutus.get("nimi"), languages),
        "koulutustyyppi": koulutus.get("koulutustyyppi", ""),
        "tutkintonimike": koodi_names(k_md.get("tutkintonimike"), languages),
        "organisaatio": pick_lang((koulutus.get("organisaatio") or {}).get("nimi"), languages),
        "eqf": eqf_level(koulutus.get("eqf")),
        "field_of_study": koodi_names(k_md.get("koulutusala"), languages),
        "credits": extent(k_md, languages) or extent(t_md, languages),
        "description": description,
        "learning_goals": learning_goals,
        "specializations": osaamisalat_names(t_md.get("osaamisalat"), languages),
        "job_titles": terms_by_lang(t_md.get("ammattinimikkeet"), languages),
        "keywords": terms_by_lang(t_md.get("asiasanat"), languages),
        "additional_info": lisatiedot_text(k_md.get("lisatiedot"), languages)
        or lisatiedot_text(t_md.get("lisatiedot"), languages),
    }
