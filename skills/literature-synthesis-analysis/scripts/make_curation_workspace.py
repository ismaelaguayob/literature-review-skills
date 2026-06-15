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
    title = (
        PROJECT_CONFIG.get("synthesis", {}).get("paper_title")
        or PROJECT_CONFIG.get("synthesis", {}).get("curated_title")
        or PROJECT_CONFIG.get("project", {}).get("name", "Narrative Review")
    )
    bibliography = relative_bib_path(qmd_path)
    return f"""---
title: "{title}"
format:
  html:
    theme: journal
    toc: true
    toc-depth: 3
    number-sections: true
    comments:
      hypothesis: true
    title-block-banner: true
bibliography: "{bibliography}"
execute:
  warning: false
  message: false
---

<!--
Drafting instructions for the principal agent:

- Write a publishable scholarly narrative in English, not a bullet-heavy report.
- Answer the questions, objectives, and hypotheses in `review-state/research-brief.md`.
- Use `review-state/corpus-outlook.yaml` and `outputs/analysis/curated/corpus-outlook.md` as the systematic map of the corpus.
- Use source-level syntheses as compressed evidence, but deep-dive into machine-readable sources for pivotal claims, shallow summaries, or suspicious traces.
- Make the argument explicit: define the problem, organize the literature into emergent categories, synthesize mechanisms and tensions, and explain implications for the configured research task.
- Use exact BibTeX keys from `{bibliography}`.
- Quarto narrative citations use bare keys in prose: `@roberts_digital_2024 argues that ...`.
- Quarto parenthetical citations use brackets: `... [@roberts_digital_2024]`.
- Multiple parenthetical citations use semicolons: `... [@key1; @key2]`.
-->

# Introduction

State the central research problem, the paper's thesis, and why the review matters. Do not merely describe the corpus.

# Conceptual Framework

Develop the main concepts, distinctions, and debates that structure the review. Use narrative citations when naming specific authors or sources in prose.

# Corpus and Method

Explain the scope of the corpus, source types, inclusion logic, and how the systematic outlook was produced. Keep this concise and transparent.

# Mapping the Literature

Organize sources by emergent themes, source types, methods, evidence types, geographies, or research uses. Every central category should be traceable to the curated outlook.

# Synthesis and Argument

Develop the main findings as connected prose. Compare literatures, identify convergences and tensions, and make explicit what the corpus allows the paper to claim.

# Implications for the Research Task

Translate the synthesis into implications for the configured research objective, measurement task, policy question, theoretical contribution, or empirical design.

# Limitations and Future Research

Name corpus limitations, ambiguous evidence, discarded/peripheral areas, and questions that require further reading or empirical work.

# Conclusion

Return to the paper's thesis and state the review's contribution.

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

- Write the final narrative as a publishable English Quarto paper, not as a robotic report.
- Use exact BibTeX keys from the configured `.bib` file.
- Narrative citations in Quarto use bare keys in prose, for example: `@roberts_digital_2024 argues that ...`.
- Parenthetical citations use brackets, for example: `... [@roberts_digital_2024]`.
- Multiple parenthetical citations use semicolons, for example: `... [@key1; @key2]`.
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
