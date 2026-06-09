#!/usr/bin/env python3
"""Create curation workspace files from source-level synthesis JSON."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path
from typing import Any

from common import CURATED_DIR, INTERMEDIATE_DIR, PROJECT_CONFIG, BIB_PATH


PROJECT_ROOT = Path.cwd()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from shared.project_config import yaml_dump  # noqa: E402


def latest_source_json_dir() -> Path | None:
    candidates = sorted(INTERMEDIATE_DIR.glob("*/source-json"), key=lambda path: path.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def load_source_jsons(source_json_dir: Path) -> list[dict[str, Any]]:
    rows = []
    for path in sorted(source_json_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        data["_json_path"] = path.as_posix()
        rows.append(data)
    return rows


def source_row(data: dict[str, Any]) -> dict[str, Any]:
    categories = data.get("categories_suggested") or []
    return {
        "source_group_id": data.get("source_group_id") or data.get("_json_path"),
        "bib_key": data.get("bib_key"),
        "title": data.get("title"),
        "source_kind": data.get("source_kind"),
        "relevance_to_review": data.get("relevance_to_review", "uncertain"),
        "confidence": data.get("confidence", "low"),
        "status": "uncategorized",
        "assigned_categories": [],
        "suggested_categories": [
            {
                "dimension": item.get("dimension"),
                "category": item.get("category"),
                "rationale": item.get("rationale"),
                "trace": item.get("trace"),
            }
            for item in categories
            if isinstance(item, dict)
        ],
        "methods": [],
        "data_or_evidence_types": [],
        "geographies": [],
        "research_uses": [],
        "rationale": "",
        "key_traces": [
            note.get("trace")
            for note in data.get("evidence_notes", [])
            if isinstance(note, dict) and note.get("trace")
        ][:5],
    }


def build_outlook_state(source_json_dir: Path, rows: list[dict[str, Any]]) -> dict[str, Any]:
    sources = [source_row(row) for row in rows]
    return {
        "project": PROJECT_CONFIG.get("project", {}),
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "generated_from": source_json_dir.as_posix(),
        "status": "draft",
        "instructions": [
            "Every source must remain represented in sources.",
            "Use status included, peripheral, discarded, or uncategorized.",
            "Use assigned_categories as multi-label categories; do not force a single category.",
            "Move irrelevant sources to status discarded with a short rationale instead of deleting them.",
        ],
        "category_dimensions": PROJECT_CONFIG.get("synthesis", {}).get("category_dimensions", []),
        "categories": [
            {
                "id": "uncategorized",
                "label": "Uncategorized / needs review",
                "dimension": "workflow_status",
                "description": "Temporary holding category for sources not yet classified.",
            },
            {
                "id": "discarded_or_irrelevant",
                "label": "Discarded or irrelevant for this task",
                "dimension": "workflow_status",
                "description": "Sources reviewed and excluded from the final narrative, with rationale retained for auditability.",
            },
        ],
        "sources": sources,
        "coverage_check": {
            "total_sources": len(sources),
            "included_or_peripheral_sources": 0,
            "discarded_sources": 0,
            "uncategorized_sources": len(sources),
        },
    }


def markdown_citation(bib_key: str | None) -> str:
    return f" [@{bib_key}]" if bib_key else ""


def render_outlook_markdown(state: dict[str, Any]) -> str:
    lines = [
        "# Corpus Outlook",
        "",
        "## Purpose",
        "",
        "This outlook is a navigational map of the reviewed corpus. It should help a researcher find sources by theme, method, evidence type, source type, and research use.",
        "",
        "## Coverage",
        "",
        f"- Total sources: {state['coverage_check']['total_sources']}",
        f"- Uncategorized sources: {state['coverage_check']['uncategorized_sources']}",
        f"- Discarded sources: {state['coverage_check']['discarded_sources']}",
        "",
        "## Category System",
        "",
        "Revise `review-state/corpus-outlook.yaml` to define emergent categories. Categories should be multi-label and may overlap.",
        "",
        "## Sources Needing Classification",
        "",
    ]
    for source in state.get("sources", []):
        citation = markdown_citation(source.get("bib_key"))
        lines.extend(
            [
                f"### {source.get('title') or source.get('source_group_id')}{citation}",
                "",
                f"- Status: `{source.get('status')}`",
                f"- Relevance: `{source.get('relevance_to_review')}`",
                f"- Source kind: `{source.get('source_kind')}`",
                f"- Suggested categories: {', '.join(item.get('category') or '' for item in source.get('suggested_categories', []) if item.get('category')) or '_none_'}",
                f"- Key traces: {', '.join(source.get('key_traces') or []) or '_none_'}",
                "",
            ]
        )
    lines.extend(
        [
            "## Discarded or Irrelevant Sources",
            "",
            "Keep excluded sources visible here with rationale so filtering decisions remain auditable.",
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def relative_bib_path(qmd_path: Path) -> str:
    try:
        return os.path.relpath(BIB_PATH, qmd_path.parent)
    except ValueError:
        return BIB_PATH.as_posix()


def render_narrative_qmd(qmd_path: Path) -> str:
    title = PROJECT_CONFIG.get("synthesis", {}).get("curated_title") or PROJECT_CONFIG.get("project", {}).get("name", "Narrative Review")
    bibliography = relative_bib_path(qmd_path)
    return f"""---
title: "{title}"
format:
  html:
    toc: true
    toc-depth: 3
    number-sections: true
bibliography: "{bibliography}"
---

# Introduction

# Research Objectives and Questions

# Corpus and Method

# Mapping the Literature

# Findings

# Implications

# Limitations and Future Research

# Conclusion

# References
"""


def research_brief_text() -> str:
    project_name = PROJECT_CONFIG.get("project", {}).get("name", "Literature Review")
    return f"""# Research Brief: {project_name}

## Research Questions

## Objectives

## Working Hypotheses

## Scope Conditions

## Inclusion Priorities

## Exclusion Criteria

## Notes for the Final Narrative
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-json-dir", type=Path, help="Directory created by run_source_synthesis_llm.py")
    parser.add_argument("--outlook-state", type=Path, default=Path("review-state/corpus-outlook.yaml"))
    parser.add_argument("--outlook-markdown", type=Path, default=CURATED_DIR / "corpus-outlook.md")
    parser.add_argument("--narrative-qmd", type=Path, default=CURATED_DIR / "narrative-review.qmd")
    parser.add_argument("--brief", type=Path, default=Path("review-state/research-brief.md"))
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    source_json_dir = args.source_json_dir or latest_source_json_dir()
    if not source_json_dir:
        raise SystemExit(f"No source-json directory found under {INTERMEDIATE_DIR}")
    rows = load_source_jsons(source_json_dir)
    state = build_outlook_state(source_json_dir, rows)

    args.outlook_state.parent.mkdir(parents=True, exist_ok=True)
    args.outlook_markdown.parent.mkdir(parents=True, exist_ok=True)
    args.narrative_qmd.parent.mkdir(parents=True, exist_ok=True)
    args.brief.parent.mkdir(parents=True, exist_ok=True)

    if args.force or not args.outlook_state.exists():
        args.outlook_state.write_text(yaml_dump(state), encoding="utf-8")
    if args.force or not args.outlook_markdown.exists():
        args.outlook_markdown.write_text(render_outlook_markdown(state), encoding="utf-8")
    if args.force or not args.narrative_qmd.exists():
        args.narrative_qmd.write_text(render_narrative_qmd(args.narrative_qmd), encoding="utf-8")
    if args.force or not args.brief.exists():
        args.brief.write_text(research_brief_text(), encoding="utf-8")

    print(args.outlook_state)
    print(args.outlook_markdown)
    print(args.narrative_qmd)
    print(args.brief)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
