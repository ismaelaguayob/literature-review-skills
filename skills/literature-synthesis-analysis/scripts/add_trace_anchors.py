#!/usr/bin/env python3
"""Insert stable HTML anchors before headings in machine-readable Markdown."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from common import MACHINE_DIR, machine_sources, slugify


ANCHOR_RE = re.compile(r'^<a id="trace-[^"]+"></a>$')
CORE_HEADING_RE = re.compile(
    r"^(abstract|introduction|conclusion|conclusions|discussion|references|bibliography|"
    r"methodology|methods|literature review|results|findings|analysis|limitations|"
    r"appendix|acknowledgements|model evaluation|reliability and validity)$",
    re.IGNORECASE,
)
NUMBERED_HEADING_RE = re.compile(r"^[0-9]+(?:\.[0-9]+)*\.?\s+[A-Z][A-Za-z0-9 ,:&'’()/.-]{4,}$")
TITLE_CASE_HEADING_RE = re.compile(r"^[A-Z][A-Za-z0-9 ,:&'’()/.-]{8,}$")
TABLE_SEPARATOR_RE = re.compile(r"^\|?[\s:|-]+\|[\s:|.-]+\|?$")
OCR_NOISE_RE = re.compile(r"^(downloaded|from|https?://|doi:?|source:|note:|fig\.|figure\s+\d+)\b", re.IGNORECASE)


def is_table_line(stripped: str) -> bool:
    if TABLE_SEPARATOR_RE.match(stripped):
        return True
    return stripped.startswith("|") or stripped.endswith("|") or stripped.count("|") >= 2


def nearby_line(lines: list[str], index: int, offset: int) -> str:
    target = index + offset
    if target < 0 or target >= len(lines):
        return ""
    return lines[target].strip()


def is_probable_heading(lines: list[str], index: int) -> bool:
    stripped = lines[index].strip()
    if not stripped:
        return False
    # MarkItDown often turns PDF tables and OCR/page fragments into standalone lines.
    # Anchoring those lines pollutes the trace map and makes citations point to table cells,
    # so headings are conservative unless they are explicit Markdown/standard sections.
    if len(stripped) > 140 or stripped.endswith((".", ",", ";")):
        return False
    if is_table_line(stripped) or OCR_NOISE_RE.match(stripped):
        return False
    if len(re.findall(r"[A-Za-z]", stripped)) < 6:
        return False
    if stripped.startswith("#"):
        return True
    if CORE_HEADING_RE.match(stripped) or NUMBERED_HEADING_RE.match(stripped):
        return True

    words = stripped.split()
    previous = nearby_line(lines, index, -1)
    following = nearby_line(lines, index, 1)
    surrounded_by_space = previous == "" or ANCHOR_RE.match(previous) or following == ""
    if 2 <= len(words) <= 12 and surrounded_by_space and TITLE_CASE_HEADING_RE.match(stripped):
        return True
    return False


def anchored_text(path: Path) -> tuple[str, int]:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    stem = slugify(path.stem)
    out = []
    count = 0
    inserted = 0
    for i, line in enumerate(lines):
        previous = out[-1].strip() if out else ""
        if is_probable_heading(lines, i) and not ANCHOR_RE.match(previous):
            count += 1
            out.append(f'<a id="trace-{stem}-{count:04d}"></a>')
            inserted += 1
        out.append(line)
    return "\n".join(out) + ("\n" if text.endswith("\n") else ""), inserted


def process(path: Path, force: bool) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    if "trace-" in text and not force:
        return {"file": str(path), "status": "skipped", "reason": "anchors already present"}
    if force:
        text = "\n".join(line for line in text.splitlines() if not ANCHOR_RE.match(line.strip()))
        path.write_text(text + "\n", encoding="utf-8")
    updated, inserted = anchored_text(path)
    path.write_text(updated, encoding="utf-8")
    return {"file": str(path), "status": "updated", "anchors_inserted": inserted}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", type=Path)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    paths = [args.file] if args.file else machine_sources()
    if not args.file and not args.all:
        parser.error("Use --file PATH or --all")
    for path in paths:
        print(process(path, args.force))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
