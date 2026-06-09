#!/usr/bin/env python3
"""Run academic API searches, deduplicate results, and print Markdown."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = Path.cwd()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from shared.project_config import (  # noqa: E402
    add_keyword_candidates,
    ensure_keyword_ledger,
    load_config,
    load_keyword_ledger,
    normalize,
    path_from_config,
    retrieval_terms,
)

SEARCH_SCRIPTS = {
    "semantic-scholar": SCRIPT_DIR / "search_semantic.py",
    "openalex": SCRIPT_DIR / "search_openalex.py",
    "core": SCRIPT_DIR / "search_core.py",
    "springer-metadata": SCRIPT_DIR / "search_springer_metadata.py",
    "springer-openaccess": SCRIPT_DIR / "search_springer_openaccess.py",
    "crossref": SCRIPT_DIR / "search_crossref.py",
    "arxiv": SCRIPT_DIR / "search_arxiv.py",
}
DEFAULT_OUTPUT_DIR = Path("outputs/retrieval/intermediate")
STOPWORDS = {
    "about",
    "across",
    "after",
    "against",
    "also",
    "and",
    "are",
    "artificial",
    "between",
    "from",
    "for",
    "into",
    "its",
    "new",
    "not",
    "of",
    "over",
    "the",
    "their",
    "this",
    "through",
    "to",
    "toward",
    "towards",
    "under",
    "with",
    "without",
}


def norm_text(value: str | None) -> str:
    return normalize(value)


def dedupe_key(item: dict) -> str:
    for field in ("doi", "id", "url"):
        value = norm_text(str(item.get(field) or ""))
        if value:
            return f"{field}:{value}"
    return "title:" + norm_text(item.get("title"))


def title_key(item: dict) -> str:
    return norm_text(item.get("title"))


def score_item(item: dict, queries: list[str], config: dict) -> tuple[int, list[str]]:
    haystack = norm_text(" ".join(str(item.get(k) or "") for k in ("title", "abstract", "venue", "type")))
    core_terms, modifier_terms = retrieval_terms(config)
    query_terms = set()
    for query in queries:
        query_terms.update(term for term in norm_text(query).split() if len(term) > 3)

    score = 0
    reasons = []
    if core_terms and any(term in haystack for term in core_terms):
        score += 5
        reasons.append("matches project core terms")
    if modifier_terms and any(term in haystack for term in modifier_terms):
        score += 3
        reasons.append("matches project modifier terms")
    matched_query_terms = sum(1 for term in query_terms if term in haystack)
    if matched_query_terms:
        score += min(4, matched_query_terms)
        reasons.append("matches query vocabulary")
    citations = item.get("citation_count")
    if isinstance(citations, int):
        if citations >= 100:
            score += 2
            reasons.append("high citation count")
        elif citations >= 20:
            score += 1
            reasons.append("moderate citation count")
    try:
        year = int(item.get("year") or 0)
    except ValueError:
        year = 0
    if year >= 2023:
        score += 1
        reasons.append("recent")
    if item.get("doi") or item.get("url"):
        score += 1
    signals = item.get("source_quality_signals") or {}
    if signals.get("open_access_full_text"):
        score += 1
        reasons.append("open-access full text available")
    if signals.get("publisher_springer"):
        score += 1
        reasons.append("Springer Nature indexed")
    if len([source for source in item.get("sources_seen", []) if source]) >= 2:
        score += 2
        reasons.append("found in multiple indexes")
    if not item.get("title"):
        score -= 5
        reasons.append("missing title")
    return score, reasons


def classify(score: int) -> str:
    if score >= 8:
        return "Core"
    if score >= 4:
        return "Peripheral"
    return "Discarded"


def run_script(source: str, query: str, limit: int, from_year: int | None, to_year: int | None, config: dict) -> list[dict]:
    cmd = [sys.executable, str(SEARCH_SCRIPTS[source]), "--query", query, "--limit", str(limit)]
    if source in {"openalex", "crossref", "core", "springer-metadata", "springer-openaccess"}:
        if from_year:
            cmd.extend(["--from-year", str(from_year)])
        if to_year:
            cmd.extend(["--to-year", str(to_year)])
    env = os.environ.copy()
    env.setdefault("RESEARCH_USER_AGENT", config.get("retrieval", {}).get("user_agent", "literature-review/0.1"))
    proc = subprocess.run(cmd, cwd=Path.cwd(), text=True, capture_output=True, check=False, env=env)
    if proc.returncode != 0:
        return [
            {
                "source": source,
                "query": query,
                "title": None,
                "error": proc.stderr.strip() or proc.stdout.strip(),
            }
        ]
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return [{"source": source, "query": query, "title": None, "error": "invalid JSON output"}]


def merge_results(results: list[dict], queries: list[str], config: dict) -> list[dict]:
    merged: dict[str, dict] = {}
    title_seen: dict[str, str] = {}
    for item in results:
        key = dedupe_key(item)
        tkey = title_key(item)
        if tkey and tkey in title_seen:
            key = title_seen[tkey]
        elif tkey:
            title_seen[tkey] = key

        if key not in merged:
            merged[key] = item
            merged[key]["sources_seen"] = [item.get("source")]
            continue

        existing = merged[key]
        source = item.get("source")
        if source and source not in existing["sources_seen"]:
            existing["sources_seen"].append(source)
        for field in ("doi", "url", "pdf_url", "abstract", "venue", "year", "type", "citation_count"):
            if not existing.get(field) and item.get(field):
                existing[field] = item[field]

    output = []
    for item in merged.values():
        score, reasons = score_item(item, queries, config)
        item["score"] = score
        item["reasons"] = reasons
        item["classification"] = classify(score)
        output.append(item)
    def sort_year(row: dict) -> int:
        try:
            return int(row.get("year") or 0)
        except (TypeError, ValueError):
            return 0

    return sorted(
        output,
        key=lambda row: (
            row["classification"] != "Core",
            row["classification"] != "Peripheral",
            -row["score"],
            -sort_year(row),
            norm_text(row.get("title")),
        ),
    )


def configured_queries(config: dict, explicit_queries: list[str] | None) -> list[str]:
    if explicit_queries:
        return explicit_queries
    retrieval = config.get("retrieval", {})
    defaults = [query for query in retrieval.get("default_queries", []) if query]
    if defaults:
        return defaults
    ledger = load_keyword_ledger(config)
    active_terms = [row.get("term") for row in ledger.get("active", []) if row.get("term")]
    templates = ledger.get("query_templates", []) or ["{core_term} literature review"]
    queries = []
    for term in active_terms[:8]:
        for template in templates[:4]:
            queries.append(str(template).format(core_term=term))
    return queries or [config.get("project", {}).get("name", "literature review")]


def configured_sources(config: dict, explicit_sources: list[str] | None) -> list[str]:
    if explicit_sources:
        return explicit_sources
    configured = config.get("retrieval", {}).get("sources", {}).get("enabled")
    if configured:
        return [source for source in configured if source in SEARCH_SCRIPTS]
    return list(SEARCH_SCRIPTS.keys())


def candidate_keywords(items: list[dict], config: dict, limit: int) -> list[dict]:
    existing_core, existing_modifiers = retrieval_terms(config)
    counts: dict[str, int] = {}
    examples: dict[str, str] = {}
    for item in items:
        if item.get("classification") == "Discarded":
            continue
        text = norm_text(" ".join(str(item.get(k) or "") for k in ("title", "abstract")))
        words = [word for word in text.split() if len(word) > 3 and word not in STOPWORDS]
        for size in (1, 2, 3):
            for index in range(0, max(0, len(words) - size + 1)):
                phrase = " ".join(words[index : index + size])
                if phrase in existing_core or phrase in existing_modifiers:
                    continue
                if len(phrase) < 5 or phrase.isdigit():
                    continue
                counts[phrase] = counts.get(phrase, 0) + 1
                examples.setdefault(phrase, item.get("title") or "")
    ranked = sorted(counts.items(), key=lambda row: (-row[1], row[0]))
    candidates = []
    for term, count in ranked[:limit]:
        candidates.append(
            {
                "term": term,
                "source": "retrieval_results",
                "reason": f"appeared in {count} retrieved result text(s)",
                "example_title": examples.get(term),
                "first_seen": dt.datetime.now(dt.timezone.utc).date().isoformat(),
            }
        )
    return candidates


def trim(value: str | None, length: int = 420) -> str:
    if not value:
        return ""
    value = " ".join(str(value).split())
    return value if len(value) <= length else value[: length - 1].rstrip() + "..."


def item_markdown(item: dict) -> str:
    title = item.get("title") or "(missing title)"
    authors = ", ".join((item.get("authors") or [])[:5])
    if item.get("authors") and len(item["authors"]) > 5:
        authors += " et al."
    bits = []
    if authors:
        bits.append(authors)
    if item.get("year"):
        bits.append(str(item["year"]))
    if item.get("venue"):
        bits.append(str(item["venue"]))
    meta = " | ".join(bits)
    ids = []
    if item.get("doi"):
        ids.append(f"DOI: `{item['doi']}`")
    if item.get("url"):
        ids.append(f"[link]({item['url']})")
    if item.get("pdf_url"):
        ids.append(f"[pdf]({item['pdf_url']})")
    reason = "; ".join(item.get("reasons") or ["manual review needed"])
    abstract = trim(item.get("abstract"))
    error = item.get("error")
    lines = [f"- **{title}**"]
    if meta:
        lines.append(f"  {meta}")
    lines.append(f"  Source(s): `{', '.join(item.get('sources_seen') or [item.get('source') or 'unknown'])}` | Score: `{item.get('score', 0)}`")
    if ids:
        lines.append("  " + " | ".join(ids))
    lines.append(f"  Why: {reason}.")
    if abstract:
        lines.append(f"  Abstract/snippet: {abstract}")
    if error:
        lines.append(f"  Retrieval error: `{trim(error, 220)}`")
    return "\n".join(lines)


def render_markdown(items: list[dict], queries: list[str]) -> str:
    lines = ["# Candidate Sources", ""]
    lines.append("Queries: " + "; ".join(f"`{query}`" for query in queries))
    lines.append("")
    for klass in ("Core", "Peripheral", "Discarded"):
        group = [item for item in items if item.get("classification") == klass]
        lines.append(f"## {klass}")
        lines.append("")
        if not group:
            lines.append("_No candidates._")
            lines.append("")
            continue
        for item in group:
            lines.append(item_markdown(item))
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def print_markdown(items: list[dict], queries: list[str]) -> None:
    print(render_markdown(items, queries), end="")


def slugify(value: str, max_length: int = 80) -> str:
    value = norm_text(value)
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value[:max_length].strip("-") or "retrieval"


def save_outputs(items: list[dict], queries: list[str], output_dir: Path, run_name: str | None) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y-%m-%d-%H%M%S")
    stem = run_name or slugify("-".join(queries))
    markdown_path = output_dir / f"{stamp}-{stem}.md"
    json_path = output_dir / f"{stamp}-{stem}.json"
    markdown_path.write_text(render_markdown(items, queries), encoding="utf-8")
    json_path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"markdown": str(markdown_path), "json": str(json_path)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="literature-review.yaml")
    parser.add_argument("--query", action="append")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--source", action="append", choices=sorted(SEARCH_SCRIPTS.keys()))
    parser.add_argument("--from-year", type=int)
    parser.add_argument("--to-year", type=int)
    parser.add_argument("--save", action="store_true", help="Save Markdown and JSON outputs under the configured retrieval intermediate directory")
    parser.add_argument("--output-dir")
    parser.add_argument("--run-name", help="Stable filename stem for saved outputs")
    parser.add_argument("--update-keywords", action="store_true", help="Add suggested terms to the local keyword ledger as candidates")
    args = parser.parse_args()

    config = load_config(args.config)
    ensure_keyword_ledger(config)
    queries = configured_queries(config, args.query)
    limit = args.limit or int(config.get("retrieval", {}).get("default_limit", 10))
    from_year = args.from_year if args.from_year is not None else config.get("retrieval", {}).get("from_year")
    to_year = args.to_year if args.to_year is not None else config.get("retrieval", {}).get("to_year")
    output_dir = Path(args.output_dir) if args.output_dir else path_from_config(config, "retrieval_intermediate_dir")
    selected = configured_sources(config, args.source)
    raw_results = []
    for query in queries:
        for source in selected:
            raw_results.extend(run_script(source, query, limit, from_year, to_year, config))
    merged = merge_results(raw_results, queries, config)
    print_markdown(merged, queries)
    if args.save:
        paths = save_outputs(merged, queries, output_dir, args.run_name)
        print("\nSaved outputs:")
        print(f"- Markdown: {paths['markdown']}")
        print(f"- JSON: {paths['json']}")
    if args.update_keywords:
        suggestion_limit = int(config.get("retrieval", {}).get("keyword_suggestion_limit", 30))
        ledger_path, added = add_keyword_candidates(config, candidate_keywords(merged, config, suggestion_limit))
        print(f"\nKeyword ledger: {ledger_path} ({added} candidate(s) added)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
