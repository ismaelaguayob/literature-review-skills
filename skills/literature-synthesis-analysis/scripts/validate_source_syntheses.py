#!/usr/bin/env python3
"""Validate source-agent synthesis files mechanically and prepare semantic audit cues."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from common import PROJECT_CONFIG


LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
CLAIM_RE = re.compile(r"(?im)(^\s*[-0-9.]*\s*(?:\*\*)?Claim(?:\*\*)?\s*:)")


def required_sections() -> list[str]:
    sections = PROJECT_CONFIG.get("synthesis", {}).get("intermediate_sections", [])
    return [str(section) for section in sections] or [
        "Thesis",
        "Key Concepts and Definitions",
        "Categories Suggested by This Source",
        "Mechanisms, Arguments, or Findings",
        "Evidence and Traceable Notes",
        "Implications for the Review",
    ]


def frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}
    output = {}
    for line in text[4:end].splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            output[key.strip()] = value.strip().strip("'\"")
    return output


def resolve_link(path: Path, link: str) -> Path:
    target, _, _anchor = link.partition("#")
    target_path = Path(target)
    if target_path.is_absolute():
        return target_path
    return (path.parent / target_path).resolve()


def link_status(path: Path, link: str) -> tuple[str, str]:
    if "://" in link or link.startswith("#"):
        return "external_or_local_anchor", ""
    target, _, anchor = link.partition("#")
    if not target:
        return "local_anchor", ""
    resolved = resolve_link(path, link)
    if not resolved.exists():
        return "missing_file", str(resolved)
    if anchor:
        body = resolved.read_text(encoding="utf-8", errors="replace")
        if f'id="{anchor}"' not in body:
            return "missing_anchor", str(resolved)
    return "ok", str(resolved)


def validate_file(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    meta = frontmatter(text)
    missing_sections = [
        section for section in required_sections()
        if not re.search(rf"^## {re.escape(section)}\s*$", text, re.MULTILINE)
    ]
    links = LINK_RE.findall(text)
    bad_links = []
    trace_links = []
    for link in links:
        status, resolved = link_status(path, link)
        if status not in {"ok", "external_or_local_anchor", "local_anchor"}:
            bad_links.append({"link": link, "status": status, "resolved": resolved})
        if "#trace-" in link:
            trace_links.append(link)

    evidence_notes = len(CLAIM_RE.findall(text))
    semantic_audit = [
        {
            "trace": link,
            "instruction": "Principal agent must verify that the anchor content supports the adjacent claim, not only that the anchor exists.",
        }
        for link in trace_links
    ]
    return {
        "file": str(path),
        "frontmatter_present": bool(meta),
        "missing_frontmatter_fields": [
            key for key in ("source_group_id", "title", "relevance_to_review", "confidence", "needs_deeper_review")
            if key not in meta
        ],
        "missing_sections": missing_sections,
        "bad_links": bad_links,
        "evidence_notes": evidence_notes,
        "trace_links": len(trace_links),
        "semantic_audit": semantic_audit,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("dir", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--min-evidence-notes", type=int, default=int(PROJECT_CONFIG.get("synthesis", {}).get("source_llm", {}).get("min_evidence_notes", 4)))
    args = parser.parse_args()

    reports = [validate_file(path) for path in sorted(args.dir.glob("*.md"))]
    failures = []
    for report in reports:
        if (
            not report["frontmatter_present"]
            or report["missing_frontmatter_fields"]
            or report["missing_sections"]
            or report["bad_links"]
            or report["evidence_notes"] < args.min_evidence_notes
        ):
            failures.append(report)

    payload = {
        "files": len(reports),
        "failures": len(failures),
        "reports": reports,
        "semantic_validation_note": "This script validates structure, local file links, and anchor existence. It does not validate claim-anchor correspondence; the principal agent must audit the semantic_audit traces.",
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"files": payload["files"], "failures": payload["failures"]}, ensure_ascii=False, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
