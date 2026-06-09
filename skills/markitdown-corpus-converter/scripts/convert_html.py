#!/usr/bin/env python3
"""Convert one HTML file to saved Markdown with MarkItDown."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from convert_common import DEFAULT_OUTPUT_DIR, convert_with_markitdown, output_path_for


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="HTML file to convert")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--output", help="Explicit output .md path")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    input_path = Path(args.input)
    if input_path.suffix.lower() not in {".html", ".htm"}:
        print(json.dumps({"status": "failed", "input": args.input, "error": "input is not HTML"}, indent=2))
        return 1
    output_path = Path(args.output) if args.output else output_path_for(input_path, Path(args.output_dir))
    result = convert_with_markitdown(input_path, output_path, "html", args.force)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] != "failed" else 1


if __name__ == "__main__":
    sys.exit(main())
