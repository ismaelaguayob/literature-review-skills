#!/usr/bin/env python3
"""Render structured source-synthesis JSON files to Markdown."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from common import slugify


def yaml_scalar(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value).replace("\n", " ").strip()


def bullet_list(values: list[Any]) -> list[str]:
    if not values:
        return ["_No substantive notes._"]
    return [f"- {value}" for value in values]


def trace_link(value: str | None) -> str:
    if not value:
        return ""
    if value.startswith("[") or "://" in value:
        return value
    return f"[trace]({value})"


def render_markdown(data: dict[str, Any]) -> str:
    lines = [
        "---",
        f"source_group_id: {yaml_scalar(data.get('source_group_id'))}",
        f"bib_key: {yaml_scalar(data.get('bib_key'))}",
        f"title: {yaml_scalar(data.get('title'))}",
        f"source_kind: {yaml_scalar(data.get('source_kind'))}",
        f"relevance_to_review: {yaml_scalar(data.get('relevance_to_review'))}",
        f"recommended_use: {yaml_scalar(data.get('recommended_use'))}",
        f"confidence: {yaml_scalar(data.get('confidence'))}",
        f"needs_deeper_review: {yaml_scalar(data.get('needs_deeper_review'))}",
        "---",
        "",
        f"# {data.get('title') or 'Source Synthesis'}",
        "",
        "## Thesis",
        "",
        str(data.get("thesis") or "_No thesis extracted._"),
        "",
        "## Key Concepts and Definitions",
        "",
        *bullet_list(data.get("key_concepts") or []),
        "",
        "## Categories Suggested by This Source",
        "",
    ]
    categories = data.get("categories_suggested") or []
    if categories:
        for item in categories:
            lines.extend(
                [
                    f"- **{item.get('dimension', 'dimension')} / {item.get('category', 'category')}**",
                    f"  Rationale: {item.get('rationale', '')}",
                    f"  Trace: {trace_link(item.get('trace'))}",
                ]
            )
    else:
        lines.append("_No categories suggested._")
    lines.extend(["", "## Mechanisms, Arguments, or Findings", ""])
    lines.extend(bullet_list(data.get("mechanisms_arguments_findings") or []))
    lines.extend(["", "## Tensions and Trade-offs", ""])
    lines.extend(bullet_list(data.get("tensions_tradeoffs") or []))
    lines.extend(["", "## Evidence and Traceable Notes", ""])
    notes = data.get("evidence_notes") or []
    if notes:
        for index, note in enumerate(notes, start=1):
            lines.extend(
                [
                    f"### Note {index}",
                    "",
                    f"- Claim: {note.get('claim', '')}",
                    f"- Evidence: {note.get('evidence', '')}",
                    f"- Citation: {note.get('citation', '')}",
                    f"- Trace: {trace_link(note.get('trace'))}",
                    f"- Confidence: {note.get('confidence', '')}",
                    "",
                ]
            )
    else:
        lines.extend(["_No traceable evidence notes._", ""])
    lines.extend(["## Implications for the Review", ""])
    lines.extend(bullet_list(data.get("implications_for_review") or []))
    lines.extend(["", "## Open Questions", ""])
    lines.extend(bullet_list(data.get("open_questions") or []))
    for section in data.get("custom_sections") or []:
        heading = section.get("heading")
        if not heading:
            continue
        lines.extend(["", f"## {heading}", "", str(section.get("content") or "")])
        traces = [trace_link(item) for item in section.get("traces", []) if item]
        if traces:
            lines.extend(["", "Traces: " + ", ".join(traces)])
    audit = data.get("semantic_audit") or {}
    lines.extend(["", "## Semantic Audit", ""])
    lines.append(f"- Extraction quality: {audit.get('extraction_quality', 'unknown')}")
    lines.extend(f"- Possible misreading: {item}" for item in audit.get("possible_misreadings") or [])
    lines.extend(f"- Limit: {item}" for item in audit.get("limits") or [])
    return "\n".join(lines).rstrip() + "\n"


def render_file(path: Path, output_dir: Path) -> Path:
    data = json.loads(path.read_text(encoding="utf-8"))
    stem = path.stem
    if stem.endswith(".source"):
        stem = stem[: -len(".source")]
    output_path = output_dir / f"{slugify(stem)}.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown(data), encoding="utf-8")
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path, help="JSON file or directory")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    paths = [args.input] if args.input.is_file() else sorted(args.input.glob("*.json"))
    for path in paths:
        output = render_file(path, args.output_dir)
        print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
