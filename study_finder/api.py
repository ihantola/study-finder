"""Endpoint functions over :class:`~study_finder.client.KonfoClient`.

Only the **External**-tagged endpoints from the konfo-backend Swagger spec are
used (see https://opintopolku.fi/konfo-backend/swagger.yaml):

- ``/external/search/koulutukset`` — search programmes (supports ``koulutusala``)
- ``/external/koulutus/{oid}``     — one programme; ``toteutukset=true`` embeds
  its implementations (with full metadata) in a single request
- ``/external/toteutus/{oid}``     — one institution-specific implementation
"""

from __future__ import annotations

from typing import Any

from .client import KonfoClient
from .config import ICT_KOULUTUSALA


def search_koulutukset(
    client: KonfoClient,
    *,
    koulutusala: str | None = ICT_KOULUTUSALA,
    koulutustyyppi: str | None = None,
    keyword: str | None = None,
    size: int = 20,
    page: int = 1,
    lng: str = "fi",
) -> dict[str, Any]:
    """Search programmes. Returns the raw ``{total, hits}`` payload.

    ``koulutustyyppi`` is a comma-separated list of education-type codes, e.g.
    ``"amk,yo"`` for universities of applied sciences + universities.
    """
    params: dict[str, Any] = {"size": size, "page": page, "lng": lng}
    if koulutusala:
        params["koulutusala"] = koulutusala
    if koulutustyyppi:
        params["koulutustyyppi"] = koulutustyyppi
    if keyword:
        params["keyword"] = keyword
    return client.get_json("/external/search/koulutukset", params)


def search_oids(
    client: KonfoClient,
    *,
    koulutusala: str | None = ICT_KOULUTUSALA,
    koulutustyyppi: str | None = None,
    keyword: str | None = None,
    lng: str = "fi",
    max_results: int | None = None,
    page_size: int = 100,
) -> tuple[list[str], int]:
    """Page through search results and collect koulutus oids.

    Returns ``(oids, total)`` where ``total`` is the full match count reported by
    the API. Pass ``max_results`` to stop early (e.g. for a quick test).
    """
    oids: list[str] = []
    total = 0
    page = 1
    while True:
        result = search_koulutukset(
            client,
            koulutusala=koulutusala,
            koulutustyyppi=koulutustyyppi,
            keyword=keyword,
            size=page_size,
            page=page,
            lng=lng,
        )
        total = result.get("total", 0)
        hits = result.get("hits", []) or []
        oids.extend(h["oid"] for h in hits if h.get("oid"))
        if max_results is not None and len(oids) >= max_results:
            return oids[:max_results], total
        if not hits or len(oids) >= total:
            break
        page += 1
    return oids, total


def get_koulutus(client: KonfoClient, oid: str, *, with_toteutukset: bool = True) -> dict[str, Any]:
    """Fetch a single programme (koulutus) by oid.

    With ``with_toteutukset`` (the default) the response embeds the linked
    toteutukset, each with full ``metadata`` — so the toteutukset can be pulled
    out without separate per-toteutus calls.
    """
    params = {"toteutukset": "true"} if with_toteutukset else None
    return client.get_json(f"/external/koulutus/{oid}", params)


def get_toteutus(client: KonfoClient, oid: str, *, with_koulutus: bool = False) -> dict[str, Any]:
    """Fetch a single implementation (toteutus) by oid.

    Defaults to the toteutus only; set ``with_koulutus`` to also embed the parent
    programme.
    """
    params = {"koulutus": "true"} if with_koulutus else None
    return client.get_json(f"/external/toteutus/{oid}", params)


def toteutukset(koulutus: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the embedded toteutus objects from a koulutus payload.

    Requires the koulutus to have been fetched with ``with_toteutukset=True``.
    Only dict entries (full embedded objects, not bare oids) are returned.
    """
    return [t for t in (koulutus.get("toteutukset") or []) if isinstance(t, dict)]
