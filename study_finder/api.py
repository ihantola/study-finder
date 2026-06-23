"""Endpoint functions over :class:`~study_finder.client.KonfoClient`.

Paths were confirmed against the live API:
- ``/search/koulutukset``  — search programmes (supports the ``koulutusala`` filter)
- ``/koulutus/{oid}``      — one programme; carries a ``toteutukset`` list
- ``/toteutus/{oid}``      — one institution-specific implementation
"""

from __future__ import annotations

from typing import Any

from .client import KonfoClient
from .config import ICT_KOULUTUSALA


def search_koulutukset(
    client: KonfoClient,
    *,
    koulutusala: str | None = ICT_KOULUTUSALA,
    keyword: str | None = None,
    size: int = 20,
    page: int = 1,
    lng: str = "fi",
) -> dict[str, Any]:
    """Search programmes. Returns the raw ``{total, hits, filters}`` payload."""
    params: dict[str, Any] = {"size": size, "page": page, "lng": lng}
    if koulutusala:
        params["koulutusala"] = koulutusala
    if keyword:
        params["keyword"] = keyword
    return client.get_json("/search/koulutukset", params)


def get_koulutus(client: KonfoClient, oid: str, lng: str = "fi") -> dict[str, Any]:
    """Fetch a single programme (koulutus) by oid."""
    return client.get_json(f"/koulutus/{oid}", {"lng": lng})


def get_toteutus(client: KonfoClient, oid: str, lng: str = "fi") -> dict[str, Any]:
    """Fetch a single implementation (toteutus) by oid."""
    return client.get_json(f"/toteutus/{oid}", {"lng": lng})


def toteutus_oids(koulutus: dict[str, Any]) -> list[str]:
    """Extract the toteutus oids linked from a koulutus payload."""
    oids: list[str] = []
    for item in koulutus.get("toteutukset", []) or []:
        if isinstance(item, dict) and item.get("oid"):
            oids.append(item["oid"])
        elif isinstance(item, str):
            oids.append(item)
    return oids
