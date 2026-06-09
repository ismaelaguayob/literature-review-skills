#!/usr/bin/env python3
"""Convert all PDF and HTML corpus files to Markdown."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from convert_common import DEFAULT_OUTPUT_DIR, PROJECT_CONFIG, convert_with_markitdown, iter_corpus_files, output_path_for


def source_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return "pdf"
    if suffix in {".html", ".htm"}:
        return "html"
    return suffix.lstrip(".")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(PROJECT_CONFIG.get("paths", {}).get("sources_dir", ".")))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--json", action="store_true", help="Print full JSON results instead of summary text")
    args = parser.parse_args()

    root = Path(args.root)
    output_dir = Path(args.output_dir)
    files = iter_corpus_files(root)
    results = []
    for input_path in files:
        out = output_path_for(input_path, output_dir, root)
        results.append(convert_with_markitdown(input_path, out, source_type(input_path), args.force))

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        counts = {}
        for result in results:
            counts[result["status"]] = counts.get(result["status"], 0) + 1
        print(f"Found: {len(files)}")
        for key in ("converted", "skipped", "failed"):
            print(f"{key.capitalize()}: {counts.get(key, 0)}")
        if counts.get("failed"):
            print("\nFailures:")
            for result in results:
                if result["status"] == "failed":
                    print(f"- {result['input']}: {result.get('error', 'unknown error')}")
        print(f"\nOutput directory: {output_dir}")
    return 0 if not any(result["status"] == "failed" for result in results) else 1


if __name__ == "__main__":
    sys.exit(main())
