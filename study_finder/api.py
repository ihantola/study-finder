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
    keyword: str | None = None,
    size: int = 20,
    page: int = 1,
    lng: str = "fi",
) -> dict[str, Any]:
    """Search programmes. Returns the raw ``{total, hits}`` payload."""
    params: dict[str, Any] = {"size": size, "page": page, "lng": lng}
    if koulutusala:
        params["koulutusala"] = koulutusala
    if keyword:
        params["keyword"] = keyword
    return client.get_json("/external/search/koulutukset", params)


def get_koulutus(client: KonfoClient, oid: str, *, with_toteutukset: bool = True) -> dict[str, Any]:
    """Fetch a single programme (koulutus) by oid.

    With ``with_toteutukset`` (the default) the response embeds the linked
    toteutukset, each with full ``metadata`` — no separate toteutus calls
    needed. The external endpoint returns all languages; selection happens at
    normalization time.
    """
    params = {"toteutukset": "true"} if with_toteutukset else None
    return client.get_json(f"/external/koulutus/{oid}", params)


def get_toteutus(client: KonfoClient, oid: str) -> dict[str, Any]:
    """Fetch a single implementation (toteutus) by oid."""
    return client.get_json(f"/external/toteutus/{oid}")


def toteutukset(koulutus: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the embedded toteutus objects from a koulutus payload.

    Requires the koulutus to have been fetched with ``with_toteutukset=True``.
    Only dict entries (i.e. embedded objects, not bare oids) are returned.
    """
    return [t for t in (koulutus.get("toteutukset") or []) if isinstance(t, dict)]
