#!/usr/bin/env python3
"""Search Springer Nature Metadata API and print normalized JSON."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


PROJECT_ROOT = Path.cwd()
SCRIPT_DIR = Path(__file__).resolve().parent
for candidate in (PROJECT_ROOT, SCRIPT_DIR):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from search_springer_common import METADATA_URL, search_springer  # noqa: E402
from shared.api_utils import load_env  # noqa: E402
from shared.project_config import load_config  # noqa: E402


PROJECT_CONFIG = load_config()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", required=True)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--from-year", type=int)
    parser.add_argument("--to-year", type=int)
    parser.add_argument("--raw-query", action="store_true")
    args = parser.parse_args()
    load_env()
    try:
        results = search_springer(
            endpoint=METADATA_URL,
            source="springer-metadata",
            query=args.query,
            limit=args.limit,
            from_year=args.from_year,
            to_year=args.to_year,
            raw_query=args.raw_query,
            config=PROJECT_CONFIG,
        )
    except Exception as exc:
        results = [{"source": "springer-metadata", "query": args.query, "title": None, "error": str(exc)}]
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
