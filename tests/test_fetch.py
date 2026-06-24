"""Offline tests for the fetch pipeline (no live network)."""

from __future__ import annotations

import json
from pathlib import Path

import responses

from study_finder import api
from study_finder.cli import _format_duration, main
from study_finder.client import KonfoClient
from study_finder.config import DEFAULT_CONFIG, Config

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


# -- helpers -------------------------------------------------------------
def test_format_duration():
    assert _format_duration(0) == "0s"
    assert _format_duration(45) == "45s"
    assert _format_duration(90) == "1m 30s"
    assert _format_duration(3661) == "1h 1m"
    assert _format_duration(-5) == "0s"


def test_delay_seconds_within_configured_range(tmp_path):
    cfg = Config(cache_dir=tmp_path, throttle_min_seconds=2.0, throttle_max_seconds=10.0)
    client = KonfoClient(config=cfg, use_cache=False)
    for _ in range(50):
        assert 2.0 <= client._delay_seconds() <= 10.0


def test_delay_seconds_disabled_when_zero(tmp_path):
    cfg = Config(cache_dir=tmp_path, throttle_min_seconds=0.0, throttle_max_seconds=0.0)
    client = KonfoClient(config=cfg, use_cache=False)
    assert client._delay_seconds() == 0.0


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


# -- CLI end to end (mocked HTTP) ---------------------------------------
@responses.activate
def test_cli_writes_one_file_per_toteutus_from_koulutus(tmp_path):
    koulutus = _load("koulutus.json")
    toteutus_oid = koulutus["toteutukset"][0]["oid"]
    responses.add(
        responses.GET,
        f"{DEFAULT_CONFIG.base_url}/external/koulutus/{koulutus['oid']}",
        json=koulutus,
        status=200,
    )
    out_dir = tmp_path / "toteutukset"
    # koulutus oid -> one request, so no throttle sleep; --no-cache avoids writing data/raw
    rc = main(["--oid", koulutus["oid"], "--out-dir", str(out_dir), "--no-cache"])

    assert rc == 0
    files = sorted(p.name for p in out_dir.glob("*.json"))
    assert files == [f"{toteutus_oid}.json"]  # only the toteutus, named by its oid
    obj = json.loads((out_dir / f"{toteutus_oid}.json").read_text(encoding="utf-8"))
    assert obj["oid"] == toteutus_oid
    assert "metadata" in obj  # raw toteutus preserved
    # parent koulutus is embedded so degree-level info (koulutusala) is kept...
    assert obj["koulutus"]["oid"] == koulutus["oid"]
    assert "koulutusala" in obj["koulutus"]["metadata"]
    # ...but the parent's own toteutukset list is stripped to avoid duplication
    assert "toteutukset" not in obj["koulutus"]


@responses.activate
def test_cli_fetches_toteutus_oid_directly(tmp_path):
    toteutus_oid = "1.2.246.562.17.00000000000000003821"
    responses.add(
        responses.GET,
        f"{DEFAULT_CONFIG.base_url}/external/toteutus/{toteutus_oid}",
        json={"oid": toteutus_oid, "metadata": {"kuvaus": {"fi": "x"}}},
        status=200,
    )
    out_dir = tmp_path / "toteutukset"
    rc = main(["--oid", toteutus_oid, "--out-dir", str(out_dir), "--no-cache"])

    assert rc == 0
    assert (out_dir / f"{toteutus_oid}.json").exists()


@responses.activate
def test_cli_404_returns_exit_code_1(tmp_path):
    oid = "1.2.246.562.13.99999999999999999999"
    responses.add(responses.GET, f"{DEFAULT_CONFIG.base_url}/external/koulutus/{oid}", status=404)
    rc = main(["--oid", oid, "--out-dir", str(tmp_path / "out"), "--no-cache"])
    assert rc == 1
