"""Command-line entry point for study-finder.

Downloads raw **toteutus** (implementation) JSON from opintopolku.fi
(konfo-backend External API) and writes one file per toteutus into an output
directory. There is no normalization — the raw API responses are the product.

A koulutus (programme) is only used to discover its toteutukset; the koulutus
object itself is not saved.

Examples
--------
Fetch one toteutus by oid (toteutus '…17…', or every toteutus of a koulutus
'…13…')::

    python -m study_finder --oid 1.2.246.562.17.00000000000000003821

Fetch all toteutukset of the first N ICT programmes (default 1)::

    python -m study_finder --limit 1

Fetch every ICT toteutus from universities of applied sciences + universities::

    python -m study_finder --koulutustyyppi amk,yo --all --out-dir data/toteutukset
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

import requests

from . import api
from .client import KonfoClient
from .config import ICT_KOULUTUSALA


def _format_duration(seconds: float) -> str:
    """Render a duration as a compact human string, e.g. "2m 30s"."""
    seconds = int(round(max(seconds, 0)))
    if seconds < 60:
        return f"{seconds}s"
    minutes, secs = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m {secs}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m"


def _toteutukset_with_parent(koulutus: dict) -> list[dict]:
    """Embedded toteutukset, each with the parent koulutus attached under
    ``"koulutus"`` so degree-level info (koulutusala, koulutustyyppi,
    tutkintonimike, ...) is preserved. The parent's own ``toteutukset`` list is
    stripped to avoid duplication.
    """
    parent = {k: v for k, v in koulutus.items() if k != "toteutukset"}
    return [{**t, "koulutus": parent} for t in api.toteutukset(koulutus)]


def _toteutukset_for_oid(client: KonfoClient, oid: str) -> list[dict]:
    """Toteutus objects for a single oid (toteutus oid, or all of a koulutus)."""
    if ".17." in oid:  # already a toteutus oid — embed its parent koulutus
        return [api.get_toteutus(client, oid, with_koulutus=True)]
    koulutus = api.get_koulutus(client, oid, with_toteutukset=True)
    return _toteutukset_with_parent(koulutus)


def _toteutukset_for_koulutukset(client: KonfoClient, koulutus_oids: list[str]) -> list[dict]:
    """Collect toteutus objects across many koulutus oids, with progress + ETA."""
    objects: list[dict] = []
    total = len(koulutus_oids)

    avg_delay = (client.config.throttle_min_seconds + client.config.throttle_max_seconds) / 2
    if total > 1:
        print(
            f"Estimated time: ~{_format_duration(total * avg_delay)} "
            f"(~{avg_delay:.0f}s/request; cached programmes are instant).",
            flush=True,
        )

    start = time.monotonic()
    for i, oid in enumerate(koulutus_oids, 1):
        koulutus = api.get_koulutus(client, oid, with_toteutukset=True)
        objects.extend(_toteutukset_with_parent(koulutus))
        if total > 1:
            elapsed = time.monotonic() - start
            eta = elapsed / i * (total - i)  # rolling average over completed items
            print(
                f"\r  [{i}/{total}] programmes, {len(objects)} toteutukset, "
                f"elapsed {_format_duration(elapsed)}, ETA {_format_duration(eta)}      ",
                end="",
                flush=True,
            )
    if total > 1:
        print()
    return objects


def _write_toteutukset(objects: list[dict], out_dir: Path) -> int:
    """Write each toteutus to ``out_dir/<oid>.json``. Returns the count written."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    for obj in objects:
        oid = obj.get("oid")
        if not oid:
            continue
        (out_dir / f"{oid}.json").write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
        written += 1
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="study_finder", description="Download raw toteutus (implementation) JSON from opintopolku.fi"
    )
    parser.add_argument(
        "--oid",
        help="Fetch by oid: a toteutus '…17…' (that one), or a koulutus '…13…' (all its toteutukset). Overrides search.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=1,
        help="Number of programmes to fetch from ICT search (default: 1 — safe for testing). Ignored with --all.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Fetch ALL matching programmes (paginates through every result; ignores --limit).",
    )
    parser.add_argument("--keyword", help="Optional free-text search keyword.")
    parser.add_argument(
        "--koulutusala",
        default=ICT_KOULUTUSALA,
        help="Field-of-study filter (default: ICT). Pass empty string to disable.",
    )
    parser.add_argument(
        "--koulutustyyppi",
        help="Education-type filter, comma-separated, e.g. 'amk,yo' "
        "(universities of applied sciences + universities).",
    )
    parser.add_argument(
        "--out-dir", default="data/toteutukset", help="Output directory; one <oid>.json file per toteutus."
    )
    parser.add_argument("--no-cache", action="store_true", help="Bypass the on-disk raw response cache.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging.")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )

    client = KonfoClient(use_cache=not args.no_cache)

    try:
        if args.oid:
            print(f"Fetching toteutukset for: {args.oid}", flush=True)
            objects = _toteutukset_for_oid(client, args.oid)
        else:
            print("Searching for matching programmes…", flush=True)
            koulutus_oids, total = api.search_oids(
                client,
                koulutusala=args.koulutusala or None,
                koulutustyyppi=args.koulutustyyppi,
                keyword=args.keyword,
                max_results=None if args.all else args.limit,
            )
            scope = "all" if args.all else f"limit={args.limit}"
            print(f"Search matched {total} programmes; fetching {len(koulutus_oids)} ({scope}).", flush=True)
            objects = _toteutukset_for_koulutukset(client, koulutus_oids)
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "?"
        if status == 404 and args.oid:
            print(
                f"Error: no programme found for oid {args.oid} (HTTP 404).\n"
                "Check the oid — koulutus oids look like '1.2.246.562.13.…' and "
                "toteutus oids like '1.2.246.562.17.…'.",
                file=sys.stderr,
            )
        else:
            print(f"Error: API request failed (HTTP {status}).", file=sys.stderr)
        return 1
    except RuntimeError as exc:  # raised by the client after retries are exhausted
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    written = _write_toteutukset(objects, Path(args.out_dir))
    print(f"Wrote {written} toteutus file(s) to {args.out_dir}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
