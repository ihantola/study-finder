"""Normalize raw koulutus/toteutus JSON into flat, analysis-ready records.

The grain of the output is one row per (koulutus, toteutus). Career-relevant
fields live in ``metadata``:
- ``osaamistavoitteet`` (learning goals) — on both entities; toteutus preferred
- ``kuvaus`` (description) — on both entities
- ``ammattinimikkeet`` (job titles) — on toteutus
- ``asiasanat`` (keywords) — on toteutus
- ``tutkintonimike`` (degree title) — on koulutus
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
        "tutkintonimike": terms_by_lang(k_md.get("tutkintonimike"), languages)
        or pick_lang(k_md.get("tutkintonimike"), languages),
        "organisaatio": pick_lang((koulutus.get("organisaatio") or {}).get("nimi"), languages),
        "eqf": str(koulutus.get("eqf", "")),
        "description": description,
        "learning_goals": learning_goals,
        "job_titles": terms_by_lang(t_md.get("ammattinimikkeet"), languages),
        "keywords": terms_by_lang(t_md.get("asiasanat"), languages),
    }
