"""Offline tests for normalization and the API client (no live network)."""

from __future__ import annotations

import json
from pathlib import Path

import responses

from study_finder import api
from study_finder.client import KonfoClient
from study_finder.config import Config
from study_finder.extract import (
    eqf_level,
    extent,
    koodi_names,
    lisatiedot_text,
    normalize,
    osaamisalat_names,
    pick_lang,
    strip_html,
    terms_by_lang,
)

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


def test_koodi_names_resolves_external_koodi_objects():
    value = [
        {"koodiUri": "tutkintonimikekk_110#2", "nimi": {"fi": "filosofian maisteri", "en": "Master of Science"}},
    ]
    assert koodi_names(value, ("fi", "en")) == "filosofian maisteri"
    assert koodi_names(value, ("en", "fi")) == "Master of Science"
    assert koodi_names(None, ("fi",)) == ""
    # also tolerates a bare multilingual block
    assert koodi_names({"fi": "Suomi"}, ("fi",)) == "Suomi"


def test_eqf_level_extracts_number():
    assert eqf_level([{"koodiUri": "eqf_7", "nimi": {"fi": "Taso 7"}}]) == "7"
    assert eqf_level({"koodiUri": "eqf_6"}) == "6"
    assert eqf_level(None) == ""


def test_osaamisalat_names_handles_both_shapes():
    kk = [{"nimi": {"fi": "Ohjelmistotuotanto", "en": "Software"}}]
    amm = [{"koodi": {"koodiUri": "osaamisala_1", "nimi": {"fi": "Ohjelmistokehittäjä"}}}]
    assert osaamisalat_names(kk, ("fi",)) == "Ohjelmistotuotanto"
    assert osaamisalat_names(amm, ("fi",)) == "Ohjelmistokehittäjä"
    assert osaamisalat_names(None, ("fi",)) == ""


def test_lisatiedot_text_renders_titled_sections():
    items = [
        {
            "otsikko": {"koodiUri": "x_03", "nimi": {"fi": "Uramahdollisuudet"}},
            "teksti": {"fi": "<p>Työllistyy asiantuntijaksi.</p>"},
        }
    ]
    assert lisatiedot_text(items, ("fi",)) == "Uramahdollisuudet: Työllistyy asiantuntijaksi."
    assert lisatiedot_text([], ("fi",)) == ""


def test_extent_formats_credits():
    md = {
        "opintojenLaajuusNumero": 120.0,
        "opintojenLaajuusyksikko": {"koodiUri": "u_2", "nimi": {"fi": "opintopistettä"}},
    }
    assert extent(md, ("fi",)) == "120 opintopistettä"
    assert extent({}, ("fi",)) == ""


# -- normalization -------------------------------------------------------
def test_normalize_merges_koulutus_and_toteutus():
    koulutus = _load("koulutus.json")
    toteutus = api.toteutukset(koulutus)[0]
    rec = normalize(koulutus, toteutus, languages=("fi", "en", "sv"))

    assert rec["koulutus_oid"] == "1.2.246.562.13.00000000000000002744"
    assert rec["toteutus_oid"] == "1.2.246.562.17.00000000000000008103"
    assert rec["koulutustyyppi"] == "yo"
    assert rec["organisaatio"] == "Aalto-yliopisto"
    assert rec["tutkintonimike"] == "filosofian maisteri"
    assert rec["eqf"] == "7"
    # toteutus text is preferred over koulutus text
    assert rec["learning_goals"] == "Toteutuksen osaamistavoitteet."
    # career signals come from the toteutus
    assert rec["job_titles"] == "äänisuunnittelija; konsultti"
    assert rec["keywords"] == "tekninen psykoakustiikka; kuulo"
    assert rec["specializations"] == "Äänentutkimus"
    # koulutus-level context fields
    assert rec["field_of_study"] == "Tietojenkäsittely ja tietoliikenne (ICT)"
    assert rec["credits"] == "120 opintopistettä"
    assert rec["additional_info"] == "Uramahdollisuudet: Valmistuneet työllistyvät asiantuntijatehtäviin."


def test_normalize_without_toteutus_falls_back_to_koulutus():
    koulutus = _load("koulutus.json")
    rec = normalize(koulutus, None, languages=("fi",))
    assert rec["toteutus_oid"] == ""
    assert rec["learning_goals"] == "Yleiset osaamistavoitteet."
    assert rec["job_titles"] == ""  # only on toteutus


# -- client / api (mocked HTTP) -----------------------------------------
@responses.activate
def test_client_fetches_and_caches(tmp_path):
    cfg = Config(cache_dir=tmp_path, throttle_min_seconds=0.0, throttle_max_seconds=0.0)
    koulutus = _load("koulutus.json")
    responses.add(
        responses.GET,
        f"{cfg.base_url}/external/koulutus/{koulutus['oid']}",
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


@responses.activate
def test_search_oids_paginates(tmp_path):
    cfg = Config(cache_dir=tmp_path, throttle_min_seconds=0.0, throttle_max_seconds=0.0)
    url = f"{cfg.base_url}/external/search/koulutukset"
    # total=3, two pages of size 2
    responses.add(responses.GET, url, json={"total": 3, "hits": [{"oid": "a"}, {"oid": "b"}]}, status=200)
    responses.add(responses.GET, url, json={"total": 3, "hits": [{"oid": "c"}]}, status=200)
    client = KonfoClient(config=cfg)

    oids, total = api.search_oids(client, koulutustyyppi="amk,yo", page_size=2)
    assert total == 3
    assert oids == ["a", "b", "c"]
    assert len(responses.calls) == 2


@responses.activate
def test_search_oids_respects_max_results(tmp_path):
    cfg = Config(cache_dir=tmp_path, throttle_min_seconds=0.0, throttle_max_seconds=0.0)
    url = f"{cfg.base_url}/external/search/koulutukset"
    responses.add(responses.GET, url, json={"total": 100, "hits": [{"oid": "a"}, {"oid": "b"}]}, status=200)
    client = KonfoClient(config=cfg)

    oids, total = api.search_oids(client, max_results=1, page_size=2)
    assert oids == ["a"]
    assert total == 100
    assert len(responses.calls) == 1  # stopped after first page


def test_toteutukset_extraction():
    koulutus = _load("koulutus.json")
    embedded = api.toteutukset(koulutus)
    assert len(embedded) == 1
    assert embedded[0]["oid"] == "1.2.246.562.17.00000000000000008103"


def test_delay_seconds_within_configured_range(tmp_path):
    cfg = Config(cache_dir=tmp_path, throttle_min_seconds=2.0, throttle_max_seconds=10.0)
    client = KonfoClient(config=cfg, use_cache=False)
    for _ in range(50):
        assert 2.0 <= client._delay_seconds() <= 10.0


def test_delay_seconds_disabled_when_zero(tmp_path):
    cfg = Config(cache_dir=tmp_path, throttle_min_seconds=0.0, throttle_max_seconds=0.0)
    client = KonfoClient(config=cfg, use_cache=False)
    assert client._delay_seconds() == 0.0
