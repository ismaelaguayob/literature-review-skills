#!/usr/bin/env python3
"""Segment a machine-readable source for synthesis planning."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from common import body_text, parse_metadata, slugify


def find_anchor_before(text: str, start: int) -> str | None:
    prefix = text[:start]
    matches = list(re.finditer(r'<a id="([^"]+)"></a>', prefix))
    return matches[-1].group(1) if matches else None


def segments(path: Path) -> list[dict]:
    full_text = path.read_text(encoding="utf-8", errors="replace")
    meta = parse_metadata(path)
    body = body_text(path)
    source_kind = meta.get("source_kind", "unknown")
    heading_pattern = re.compile(
        r"(?m)^(?:<a id=\"(?P<anchor>[^\"]+)\"></a>\n)?"
        r"(?P<head>#{1,6}\s+.+|abstract|introduction|conclusion|conclusions|discussion|references|bibliography|"
        r"methodology|methods|literature review|results|findings|analysis|"
        r"[0-9]+\.?\s+[A-Z][A-Za-z ,:&'’()/.-]{4,}|"
        r"[A-Z][A-Za-z ,:&'’()/.-]{8,})$",
        re.IGNORECASE,
    )
    matches = list(heading_pattern.finditer(body))

    if source_kind == "measurement_stocktake":
        preferred = [m for m in matches if re.search(r"(infrastructure|data|talent|governance|maturity|capability|resources)", m.group("head"), re.I)]
    elif source_kind in {"book", "edited_volume"}:
        preferred = [m for m in matches if re.search(r"(chapter|part|contents|preface|introduction|conclusion|^[0-9]+[. ])", m.group("head"), re.I)]
    else:
        preferred = [
            m
            for m in matches
            if re.search(r"^(abstract|introduction|conclusion|discussion|methodology|methods|results|findings|analysis)", m.group("head"), re.I)
            or m.group("head").startswith("#")
        ]

    chosen = preferred or matches[:20]
    output = []
    for idx, match in enumerate(chosen):
        start = match.start()
        end = chosen[idx + 1].start() if idx + 1 < len(chosen) else min(len(body), start + 12000)
        head = re.sub(r"^#+\s+", "", match.group("head")).strip()
        anchor = match.group("anchor") or find_anchor_before(body, start)
        output.append(
            {
                "segment_id": f"{slugify(path.stem)}-{idx + 1:03d}",
                "heading": head[:160],
                "anchor": anchor,
                "start_char": start,
                "end_char": end,
                "trace_link": f"{path.as_posix()}#{anchor}" if anchor else path.as_posix(),
            }
        )
    if not output:
        output.append(
            {
                "segment_id": f"{slugify(path.stem)}-001",
                "heading": "Whole source",
                "anchor": None,
                "start_char": 0,
                "end_char": len(body),
                "trace_link": path.as_posix(),
            }
        )
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("file", type=Path)
    args = parser.parse_args()
    print(json.dumps({"file": str(args.file), "metadata": parse_metadata(args.file), "segments": segments(args.file)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
