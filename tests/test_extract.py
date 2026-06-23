"""Offline tests for normalization and the API client (no live network)."""

from __future__ import annotations

import json
from pathlib import Path

import responses

from study_finder import api
from study_finder.client import KonfoClient
from study_finder.config import Config
from study_finder.extract import normalize, pick_lang, strip_html, terms_by_lang

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


# -- pure helpers --------------------------------------------------------
def test_strip_html_collapses_and_unescapes():
    assert strip_html("<p>Toteutuksen   kuvaus &amp; lis&auml;tieto.</p>") == "Toteutuksen kuvaus & lisätieto."


def test_pick_lang_respects_priority_and_strips_html():
    block = {"en": "<p>English</p>", "fi": "<p>Suomi</p>"}
    assert pick_lang(block, ("fi", "en")) == "Suomi"
    assert pick_lang(block, ("en", "fi")) == "English"
    assert pick_lang(None, ("fi",)) == ""


def test_terms_by_lang_picks_language_then_falls_back():
    items = [
        {"kieli": "fi", "arvo": "äänisuunnittelija"},
        {"kieli": "fi", "arvo": "konsultti"},
        {"kieli": "en", "arvo": "sound designer"},
    ]
    assert terms_by_lang(items, ("fi",)) == "äänisuunnittelija; konsultti"
    assert terms_by_lang(items, ("en",)) == "sound designer"
    assert terms_by_lang([], ("fi",)) == ""


# -- normalization -------------------------------------------------------
def test_normalize_merges_koulutus_and_toteutus():
    koulutus = _load("koulutus.json")
    toteutus = _load("toteutus.json")
    rec = normalize(koulutus, toteutus, languages=("fi", "en", "sv"))

    assert rec["koulutus_oid"] == "1.2.246.562.13.00000000000000002744"
    assert rec["toteutus_oid"] == "1.2.246.562.17.00000000000000008103"
    assert rec["koulutustyyppi"] == "yo"
    assert rec["organisaatio"] == "Aalto-yliopisto"
    assert rec["tutkintonimike"] == "filosofian maisteri"
    # toteutus text is preferred over koulutus text
    assert rec["learning_goals"] == "Toteutuksen osaamistavoitteet."
    # career signals come from the toteutus
    assert rec["job_titles"] == "äänisuunnittelija; konsultti"
    assert rec["keywords"] == "tekninen psykoakustiikka; kuulo"


def test_normalize_without_toteutus_falls_back_to_koulutus():
    koulutus = _load("koulutus.json")
    rec = normalize(koulutus, None, languages=("fi",))
    assert rec["toteutus_oid"] == ""
    assert rec["learning_goals"] == "Yleiset osaamistavoitteet."
    assert rec["job_titles"] == ""  # only on toteutus


# -- client / api (mocked HTTP) -----------------------------------------
@responses.activate
def test_client_fetches_and_caches(tmp_path):
    cfg = Config(cache_dir=tmp_path, throttle_seconds=0.0)
    koulutus = _load("koulutus.json")
    responses.add(
        responses.GET,
        f"{cfg.base_url}/koulutus/{koulutus['oid']}",
        json=koulutus,
        status=200,
    )
    client = KonfoClient(config=cfg)

    first = api.get_koulutus(client, koulutus["oid"])
    assert first["oid"] == koulutus["oid"]
    # second call is served from cache -> still only one real HTTP call
    second = api.get_koulutus(client, koulutus["oid"])
    assert second == first
    assert len(responses.calls) == 1


def test_toteutus_oids_extraction():
    koulutus = _load("koulutus.json")
    assert api.toteutus_oids(koulutus) == ["1.2.246.562.17.00000000000000008103"]
