#!/usr/bin/env python3
"""Create an intermediate synthesis template for a source."""

from __future__ import annotations

import argparse
from pathlib import Path

from common import INTERMEDIATE_DIR, PROJECT_CONFIG, apa_citation, apa_reference, parse_bib_entries, parse_metadata, slugify


def template_for(config: dict) -> str:
    sections = config.get("synthesis", {}).get("intermediate_sections", [])
    section_blocks = []
    for section in sections:
        if section == "Evidence and Traceable Notes":
            section_blocks.append(
                """## Evidence and Traceable Notes
- Claim:
  Evidence:
  Citation: {apa_citation}
  Trace:
"""
            )
        elif section == "Categories Suggested by This Source":
            dimensions = config.get("synthesis", {}).get("category_dimensions", [])
            rows = "\n".join(f"- {dimension}:" for dimension in dimensions)
            section_blocks.append(f"## Categories Suggested by This Source\n{rows}\n")
        else:
            section_blocks.append(f"## {section}\n")
    body = "\n".join(section_blocks).rstrip()
    return """# Source Synthesis: {title}

## Identification
- APA 7: {apa_reference}
- In-text citation: {apa_citation}
- BibTeX key: `{bib_key}`
- Source kind: `{source_kind}`
- Source file: `{source_path}`
- Machine-readable file: `{machine_file}`
- Segment/section: {segment}
- Synthesis lens: {lens_name}

## Status
- Coverage: Draft
- Confidence:
- Notes on extraction quality:

""" + body + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("machine_file", type=Path)
    parser.add_argument("--segment", default="Whole source")
    parser.add_argument("--output-dir", default=str(INTERMEDIATE_DIR))
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    meta = parse_metadata(args.machine_file)
    entries = parse_bib_entries()
    entry = entries.get(meta.get("bib_key"))
    title = meta.get("bib_title") or args.machine_file.stem
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{slugify(meta.get('bib_key') or title)}.md"
    if out.exists() and not args.force:
        print(f"Skipped existing template: {out}")
        return 0
    out.write_text(
        template_for(PROJECT_CONFIG).format(
            title=title,
            apa_reference=apa_reference(entry),
            apa_citation=apa_citation(entry),
            bib_key=meta.get("bib_key", ""),
            source_kind=meta.get("source_kind", "unknown"),
            source_path=meta.get("source_path", ""),
            machine_file=args.machine_file.as_posix(),
            segment=args.segment,
            lens_name=PROJECT_CONFIG.get("synthesis", {}).get("lens_name", "General literature synthesis"),
        ),
        encoding="utf-8",
    )
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
