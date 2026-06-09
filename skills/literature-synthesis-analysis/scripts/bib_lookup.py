#!/usr/bin/env python3
"""Lookup BibTeX metadata and approximate APA references."""

from __future__ import annotations

import argparse
import json

from common import apa_citation, apa_reference, parse_bib_entries


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--key")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    entries = parse_bib_entries()
    if args.key:
        entry = entries.get(args.key)
        result = {
            "entry": entry,
            "apa_citation": apa_citation(entry),
            "apa_reference": apa_reference(entry),
        }
        print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else result["apa_reference"])
        return 0 if entry else 1

    for key, entry in entries.items():
        print(f"{key}: {apa_reference(entry)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
