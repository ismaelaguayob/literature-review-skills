#!/usr/bin/env python3
"""Collect configured findings sections from intermediate syntheses."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from common import INTERMEDIATE_DIR, PROJECT_CONFIG


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", default=str(INTERMEDIATE_DIR))
    parser.add_argument("--output", default=str(INTERMEDIATE_DIR / "findings-map.md"))
    args = parser.parse_args()

    sections = PROJECT_CONFIG.get("synthesis", {}).get("findings_sections", ["Thesis", "Implications for the Review"])
    rows = ["# Findings Map", ""]
    for path in sorted(Path(args.dir).glob("*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        rows.append(f"## {path.stem}")
        rows.append("")
        rows.append(f"- File: `{path}`")
        for section in sections:
            match = re.search(rf"## {re.escape(section)}\n+(.*?)(?=\n## |\Z)", text, re.S)
            if match:
                rows.append(f"- {section}: " + " ".join(match.group(1).split())[:1000])
        rows.append("")
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(rows), encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
