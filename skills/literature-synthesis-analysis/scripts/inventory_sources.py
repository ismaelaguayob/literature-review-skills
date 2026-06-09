#!/usr/bin/env python3
"""List machine-readable sources and their metadata."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from common import machine_sources, parse_metadata


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    rows = []
    for path in machine_sources():
        meta = parse_metadata(path)
        rows.append(
            {
                "machine_file": str(path),
                "source_kind": meta.get("source_kind", "unknown"),
                "bib_key": meta.get("bib_key"),
                "bib_title": meta.get("bib_title"),
                "source_path": meta.get("source_path"),
            }
        )
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0

    print("| Source kind | Bib key | Machine file |")
    print("| --- | --- | --- |")
    for row in rows:
        print(f"| {row['source_kind']} | {row.get('bib_key') or ''} | `{row['machine_file']}` |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
