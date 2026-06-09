#!/usr/bin/env python3
"""Create the project keyword ledger if it does not exist."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = Path.cwd()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from shared.project_config import ensure_keyword_ledger, load_config  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="literature-review.yaml")
    args = parser.parse_args()
    config = load_config(args.config)
    print(ensure_keyword_ledger(config))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
