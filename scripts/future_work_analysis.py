"""Future-work / future-skills analysis over the downloaded toteutus corpus.

Redoes the AI/LLM/agent × (future-)work reference extraction AND adds a broader
pass: every forward-looking ("future work / future skills") statement, tagged by
topic so we can see what is mentioned as a future skill *besides* AI/LLM/agent.

Reads:  data/toteutukset/*.json   (raw toteutus, parent koulutus embedded)
Writes (new files; never overwrites existing analysis):
    analysis/future-work-references.csv
    analysis/future-work-references.json
    analysis/future-work-summary.md

Run:  python scripts/future_work_analysis.py
"""

from __future__ import annotations

import csv
import html
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

DATA_DIR = Path("data/toteutukset")
OUT_DIR = Path("analysis")
LANGS = ("fi", "sv", "en")

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")
_SENT = re.compile(r"(?<=[.!?])\s+|\n+")


def strip_html(text: str) -> str:
    return _WS.sub(" ", html.unescape(_TAG.sub(" ", text or ""))).strip()


def sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT.split(strip_html(text)) if len(s.strip()) >= 40]


# --- term sets (lowercased substring match; fi / sv / en) -------------------
FUTURE_CUES = (
    "tulevaisuu", "tulevaisuudessa", "tulevat ", "muuttuva työ", "työelämän muut",
    "työelämän tarpe", "työelämän vaatim", "kysytyim", "kasvava ala", "nouseva",
    "huomisen", "framtid", "framtida", "framtidens",
    "future", "emerging", "tomorrow", "next-generation", "next generation",
    "evolving", "future-proof", "of the future", "in demand", "increasingly",
    "changing working life", "changing world of work",
)

AI_TERMS = (
    "tekoäly", "koneoppi", "syväoppi", "neuroverko", "kielimalli", "generatiiv",
    "ohjelmistoagent", "tekoälyn", "tekoälyä",
    "artificial intelligence", " ai ", "(ai)", "ai-", "machine learning",
    "deep learning", "neural network", "large language model", " llm", "gpt",
    "generative", "intelligent agent", "software agent", "agentic",
)

# Non-AI future-skill topic buckets.
TOPICS: dict[str, tuple[str, ...]] = {
    "Sustainability / green": (
        "kestäv", "vastuullis", "ympäristö", "ekologi", "hiilineutraa", "ilmasto",
        "kiertotalous", "green", "sustainab", "environmental", "climate", "circular econom",
    ),
    "Data & analytics": (
        "data-analy", "datatiede", "big data", "data scien", "analytiik", "analytics",
        "tietojohtam", "datankäsittel",
    ),
    "Cybersecurity": ("kyberturv", "tietoturv", "cyber", "cybersecurity", "information security"),
    "Cloud / DevOps": ("pilvipalvel", "pilviteknolog", "cloud", "devops", "kontti", "container", "kubernetes"),
    "Robotics / automation": ("robotiik", "robotti", "automaatio", "robotic", "automation"),
    "IoT": ("esineiden internet", "internet of things", "iot", "teollinen internet"),
    "Software / programming": (
        "ohjelmoint", "ohjelmistokehit", "ohjelmistotuotan", "full stack", "full-stack",
        "software develop", "programming", "web develop", "mobiilikehit", "pelinkehit", "game develop",
    ),
    "Digitalisation": ("digitalisaa", "digitaalis", "digital transform", "digiosaam", "digitization", "digitalization"),
    "Entrepreneurship / business": ("yrittäj", "liiketoimin", "entrepreneur", "business", "kaupallis"),
    "Transversal / soft skills": (
        "vuorovaikutus", "viestintätaid", "tiimity", "ryhmätyö", "ongelmanratkais", "jatkuva oppim",
        "elinikäin", "itseohjautuv", "kriittinen ajattelu", "luovuus", "communication skill",
        "teamwork", "collaborat", "problem-solving", "problem solving", "lifelong learning",
        "critical thinking", "creativity", "adaptab", "self-direct",
    ),
    "Internationalisation": ("kansainväli", "monikulttuur", "international", "global", "cross-cultural"),
    "Ethics / responsibility": ("eettis", "etiikka", "ethic", "responsib"),
}


def level_of(koulutustyyppi: str) -> str:
    k = koulutustyyppi or ""
    if k.startswith("amk-opinto") or k.startswith("yo-opinto") or k.startswith("kk-opinto"):
        return "Korkeakoulu (kurssi/kokonaisuus)"
    if k.startswith("amk"):
        return "AMK"
    if k in {"yo", "kandi", "maisteri", "kandi-ja-maisteri", "tohtori"} or k.startswith("yo"):
        return "Yliopisto (tutkinto)"
    if k.startswith("amm"):
        return "Ammatillinen"
    return "Muu"


def pick_lang(block, lang):
    return block.get(lang) if isinstance(block, dict) else None


def doc_texts(doc: dict):
    """Yield (lang, text) from the toteutus and its embedded koulutus."""
    md = doc.get("metadata") or {}
    kmd = (doc.get("koulutus") or {}).get("metadata") or {}
    opetus = md.get("opetus") or {}
    blocks = [md.get("kuvaus"), md.get("osaamistavoitteet"), kmd.get("kuvaus"), kmd.get("osaamistavoitteet")]
    for li in (opetus.get("lisatiedot") or []) + (kmd.get("lisatiedot") or []):
        if isinstance(li, dict):
            blocks.append(li.get("teksti"))
    for block in blocks:
        for lang in LANGS:
            val = pick_lang(block, lang)
            if val:
                yield lang, val


def topics_in(text_l: str) -> list[str]:
    return [name for name, terms in TOPICS.items() if any(t in text_l for t in terms)]


def main() -> None:
    files = sorted(DATA_DIR.glob("*.json"))
    if not files:
        raise SystemExit(f"No data in {DATA_DIR}/ — run the downloader first.")

    rows = []
    seen: set[tuple[str, str]] = set()  # (oid, sentence) dedupe per document
    for path in files:
        doc = json.loads(path.read_text(encoding="utf-8"))
        oid = doc.get("oid", path.stem)
        level = level_of(doc.get("koulutustyyppi", ""))
        org = pick_lang((doc.get("organisaatio") or {}).get("nimi"), "fi") or pick_lang(
            (doc.get("organisaatio") or {}).get("nimi"), "en"
        ) or ""
        url = f"https://opintopolku.fi/konfo/fi/toteutus/{oid}"
        for lang, raw in doc_texts(doc):
            for sent in sentences(raw):
                low = sent.lower()
                if not any(c in low for c in FUTURE_CUES):
                    continue  # only forward-looking statements
                key = (oid, sent)
                if key in seen:
                    continue
                seen.add(key)
                mentions_ai = any(t in low for t in AI_TERMS)
                topics = topics_in(low)
                rows.append(
                    {
                        "oid": oid,
                        "level": level,
                        "language": lang,
                        "mentions_ai": int(mentions_ai),
                        "topics": "; ".join(topics),
                        "non_ai_only": int(bool(topics) and not mentions_ai),
                        "organisation": strip_html(org),
                        "url": url,
                        "quote": sent,
                    }
                )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cols = ["oid", "level", "language", "mentions_ai", "non_ai_only", "topics", "organisation", "url", "quote"]
    with (OUT_DIR / "future-work-references.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    (OUT_DIR / "future-work-references.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    _write_summary(rows, len(files))
    print(f"Scanned {len(files)} toteutukset → {len(rows)} forward-looking references.")
    print(f"  with AI/LLM/agent: {sum(r['mentions_ai'] for r in rows)}")
    print(f"  non-AI topic-tagged: {sum(r['non_ai_only'] for r in rows)}")
    print(f"Wrote analysis/future-work-references.{{csv,json}} and future-work-summary.md")


def _write_summary(rows: list[dict], n_files: int) -> None:
    total = len(rows)
    ai = [r for r in rows if r["mentions_ai"]]
    non_ai = [r for r in rows if not r["mentions_ai"]]
    docs_ai = {r["oid"] for r in ai}
    docs_total = {r["oid"] for r in rows}

    # topic frequencies among non-AI future references (count distinct docs)
    topic_docs: dict[str, set] = defaultdict(set)
    topic_quotes: dict[str, list] = defaultdict(list)
    for r in non_ai:
        for t in r["topics"].split("; "):
            if t:
                topic_docs[t].add(r["oid"])
                if len(topic_quotes[t]) < 2:
                    topic_quotes[t].append(r)
    lang_counts = Counter(r["language"] for r in rows)
    level_counts = Counter(r["level"] for r in rows)

    lines = []
    lines.append("# Future-work / future-skills references (re-run)\n")
    lines.append(
        "Forward-looking statements in the ICT toteutus corpus — sentences that "
        "use a *future cue* (tulevaisuus / framtid / future / emerging / in demand / "
        "changing working life …). Each is tagged whether it mentions **AI/LLM/agent** "
        "and which other future-skill **topics** it names. Counts are occurrences "
        "(sentence × document, de-duplicated per document).\n"
    )
    lines.append(
        f"- Corpus: **{n_files}** toteutukset; **{total}** forward-looking references "
        f"in **{len(docs_total)}** documents.\n"
        f"- Mention AI/LLM/agent: **{len(ai)}** references ({len(docs_ai)} documents).\n"
        f"- Do **not** mention AI: **{len(non_ai)}** references — these are where "
        "*other* future skills surface.\n"
    )

    lines.append("\n## What is named as a future skill **besides** AI/LLM/agent\n")
    lines.append("Distinct documents whose forward-looking text names each topic (AI excluded):\n")
    lines.append("| Topic | documents |\n|---|---|")
    for topic, docs in sorted(topic_docs.items(), key=lambda kv: -len(kv[1])):
        lines.append(f"| {topic} | {len(docs)} |")
    lines.append("")

    lines.append("\n## Example non-AI future-skill quotes\n")
    for topic, docs in sorted(topic_docs.items(), key=lambda kv: -len(kv[1])):
        lines.append(f"**{topic}** ({len(docs)} docs)")
        for r in topic_quotes[topic]:
            q = r["quote"]
            q = (q[:240] + "…") if len(q) > 240 else q
            lines.append(f"- _{r['language']}_ “{q}” — [{r['oid']}]({r['url']})")
        lines.append("")

    lines.append("\n## Forward-looking references by language / level\n")
    lines.append("| | count |\n|---|---|")
    for lang in LANGS:
        lines.append(f"| lang: {lang} | {lang_counts.get(lang, 0)} |")
    for lvl, c in level_counts.most_common():
        lines.append(f"| level: {lvl} | {c} |")
    lines.append("")
    lines.append(
        "\n> Method: regex over toteutus + embedded koulutus free text "
        "(`kuvaus`, `osaamistavoitteet`, `opetus.lisatiedot`), summative layer only. "
        "Term lists are in `scripts/future_work_analysis.py`; tune and re-run.\n"
    )
    (OUT_DIR / "future-work-summary.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
