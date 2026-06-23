"""Command-line entry point for study-finder.

Examples
--------
Fetch a SINGLE programme by oid (best for a quick test — one degree only)::

    python -m study_finder --oid 1.2.246.562.13.00000000000000002744

Fetch the first N ICT programmes from search (defaults to 1, so it never
crawls the whole catalogue unless you raise --limit)::

    python -m study_finder --limit 1
    python -m study_finder --limit 20 --out data/processed/ict.csv
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from . import api
from .client import KonfoClient
from .config import DEFAULT_CONFIG, ICT_KOULUTUSALA
from .extract import normalize
from .storage import write_csv


def _build_records(client: KonfoClient, koulutus_oids: list[str], languages) -> list[dict]:
    records: list[dict] = []
    for oid in koulutus_oids:
        # One request per degree: ?toteutukset=true embeds the implementations,
        # each with full metadata, so no per-toteutus calls are needed.
        koulutus = api.get_koulutus(client, oid, with_toteutukset=True)
        implementations = api.toteutukset(koulutus)
        if not implementations:
            records.append(normalize(koulutus, None, languages))
            continue
        for toteutus in implementations:
            records.append(normalize(koulutus, toteutus, languages))
    return records


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="study_finder", description="Extract CS/ICT study-programme data from opintopolku.fi"
    )
    parser.add_argument("--oid", help="Fetch a single koulutus (degree) by oid. Overrides search.")
    parser.add_argument(
        "--limit",
        type=int,
        default=1,
        help="Number of programmes to fetch from ICT search (default: 1 — safe for testing).",
    )
    parser.add_argument("--keyword", help="Optional free-text search keyword.")
    parser.add_argument(
        "--koulutusala",
        default=ICT_KOULUTUSALA,
        help="Field-of-study filter (default: ICT). Pass empty string to disable.",
    )
    parser.add_argument(
        "--lang",
        default=",".join(DEFAULT_CONFIG.languages),
        help="Comma-separated language priority for text fields (default: fi,en,sv).",
    )
    parser.add_argument("--out", default="data/processed/ict_programmes.csv", help="Output CSV path.")
    parser.add_argument("--no-cache", action="store_true", help="Bypass the on-disk raw response cache.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging.")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )

    languages = tuple(part.strip() for part in args.lang.split(",") if part.strip())
    primary_lang = languages[0] if languages else "fi"
    client = KonfoClient(use_cache=not args.no_cache)

    if args.oid:
        koulutus_oids = [args.oid]
        print(f"Fetching single degree: {args.oid}")
    else:
        result = api.search_koulutukset(
            client,
            koulutusala=args.koulutusala or None,
            keyword=args.keyword,
            size=args.limit,
            lng=primary_lang,
        )
        total = result.get("total", 0)
        hits = result.get("hits", [])[: args.limit]
        koulutus_oids = [h["oid"] for h in hits if h.get("oid")]
        print(f"ICT search matched {total} programmes; fetching {len(koulutus_oids)} (limit={args.limit}).")

    records = _build_records(client, koulutus_oids, languages)

    out_path = write_csv(records, Path(args.out))
    print(f"Wrote {len(records)} row(s) to {out_path}")
    if records:
        first = records[0]
        print("\nSample row:")
        for key in ("nimi", "koulutustyyppi", "tutkintonimike", "job_titles", "keywords"):
            print(f"  {key}: {first.get(key, '')[:100]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
