#!/usr/bin/env python3
"""Print active, candidate, and rejected keyword terms."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = Path.cwd()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from shared.project_config import load_config, load_keyword_ledger  # noqa: E402


def terms(rows: list[dict]) -> list[str]:
    return [str(row.get("term")) for row in rows if row.get("term")]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="literature-review.yaml")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    ledger = load_keyword_ledger(load_config(args.config))
    if args.json:
        print(json.dumps(ledger, ensure_ascii=False, indent=2))
        return 0
    for section in ("active", "candidates", "rejected"):
        print(f"## {section.title()}")
        for term in terms(ledger.get(section, [])):
            print(f"- {term}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
