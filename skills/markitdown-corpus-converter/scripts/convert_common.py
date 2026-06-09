"""Shared helpers for MarkItDown corpus conversion scripts."""

from __future__ import annotations

import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT_FOR_IMPORTS = Path.cwd()
if str(PROJECT_ROOT_FOR_IMPORTS) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT_FOR_IMPORTS))

from shared.project_config import bib_path, load_config, path_from_config  # noqa: E402

PROJECT_ROOT = Path.cwd()
PROJECT_CONFIG = load_config()
DEFAULT_OUTPUT_DIR = path_from_config(PROJECT_CONFIG, "machine_dir")
EXCLUDED_DIRS = {".git", ".venv", "skills", "machine-readable", "__pycache__"}
BIB_PATH = bib_path(PROJECT_CONFIG)
OVERRIDES_PATH = Path("skills/markitdown-corpus-converter/references/source_kind_overrides.json")


def markitdown_command() -> list[str]:
    venv_python = PROJECT_ROOT / ".venv" / "bin" / "python"
    if venv_python.exists():
        return [str(venv_python), "-m", "markitdown"]
    return [sys.executable, "-m", "markitdown"]


def safe_stem(path: Path, root: Path = PROJECT_ROOT) -> str:
    try:
        relative = path.resolve().relative_to(root.resolve())
    except ValueError:
        relative = path.name
    if not isinstance(relative, str):
        relative = str(relative)
    without_suffix = str(Path(relative).with_suffix(""))
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", without_suffix)
    safe = safe.replace("/", "__")
    safe = re.sub(r"_+", "_", safe).strip("_")
    return safe or path.stem


def output_path_for(input_path: Path, output_dir: Path, root: Path = PROJECT_ROOT) -> Path:
    return output_dir / f"{safe_stem(input_path, root)}.md"


def clean_bib_value(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip().strip("{}")
    value = value.replace("{{", "").replace("}}", "")
    value = value.replace("\\&", "&")
    value = re.sub(r"\\textbar\{\}", "|", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip() or None


def normalize_for_match(value: str | None) -> str:
    if not value:
        return ""
    value = value.lower()
    value = re.sub(r"\\[a-zA-Z]+", " ", value)
    value = value.replace("ü", "u").replace("ö", "o").replace("ä", "a").replace("é", "e")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def parse_bib_entries(path: Path = BIB_PATH) -> list[dict]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    starts = list(re.finditer(r"^@(\w+)\{([^,]+),", text, re.MULTILINE))
    entries = []
    for index, match in enumerate(starts):
        start = match.start()
        end = starts[index + 1].start() if index + 1 < len(starts) else len(text)
        block = text[start:end]
        fields = {}
        for field_match in re.finditer(r"^\s*([A-Za-z]+)\s*=\s*[\{\"](.+?)[\}\"]\s*,?\s*$", block, re.MULTILINE):
            fields[field_match.group(1).lower()] = clean_bib_value(field_match.group(2))
        attachments = []
        if fields.get("file"):
            attachments = [Path(item).name for item in fields["file"].split(";") if item.strip()]
        entries.append(
            {
                "entry_type": match.group(1),
                "key": match.group(2),
                "title": fields.get("title"),
                "type": fields.get("type"),
                "journal": fields.get("journal"),
                "doi": fields.get("doi"),
                "archiveprefix": fields.get("archiveprefix"),
                "eprint": fields.get("eprint"),
                "attachments": attachments,
            }
        )
    return entries


def load_source_kind_overrides(path: Path = OVERRIDES_PATH) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def infer_source_kind(entry: dict | None, input_path: Path, overrides: dict | None = None) -> str:
    overrides = overrides or {}
    for key in (input_path.name, input_path.as_posix()):
        if key in overrides:
            return overrides[key]
    if entry:
        entry_type = (entry.get("entry_type") or "").lower()
        type_field = normalize_for_match(entry.get("type"))
        journal = entry.get("journal")
        doi = normalize_for_match(entry.get("doi"))
        archiveprefix = normalize_for_match(entry.get("archiveprefix"))
        if "arxiv" in doi or "arxiv" in archiveprefix or "arxiv" in normalize_for_match(input_path.name):
            return "preprint"
        if entry_type == "article" and journal:
            return "journal_article"
        if entry_type == "article":
            return "article"
        if entry_type == "techreport":
            if "discussion paper" in type_field:
                return "discussion_paper"
            return "report"
        if entry_type == "book":
            return "book"
        if entry_type in {"incollection", "inproceedings"}:
            return "book_chapter"
        if entry_type == "misc":
            if "ssrn" in type_field:
                return "working_paper"
            if "arxiv" in normalize_for_match(entry.get("journal")) or "arxiv" in normalize_for_match(input_path.name):
                return "preprint"
            if input_path.suffix.lower() in {".html", ".htm"}:
                return "web_article"
            return "misc"
    if input_path.suffix.lower() in {".html", ".htm"}:
        return "web_article"
    if "stocktake" in normalize_for_match(input_path.name):
        return "measurement_stocktake"
    if "discussion paper" in normalize_for_match(input_path.name):
        return "discussion_paper"
    return "unknown"


def find_bib_entry(input_path: Path, entries: list[dict]) -> dict | None:
    basename = input_path.name
    normalized_name = normalize_for_match(input_path.stem)
    for entry in entries:
        if basename in entry.get("attachments", []):
            return entry
    candidates = []
    for entry in entries:
        title_norm = normalize_for_match(entry.get("title"))
        if title_norm and title_norm in normalized_name:
            candidates.append((len(title_norm), entry))
        elif title_norm:
            title_words = {word for word in title_norm.split() if len(word) > 3}
            name_words = set(normalized_name.split())
            overlap = len(title_words & name_words)
            if title_words and overlap / len(title_words) >= 0.55:
                candidates.append((overlap, entry))
    if candidates:
        return sorted(candidates, key=lambda item: item[0], reverse=True)[0][1]
    return None


def metadata_block(input_path: Path, source_type: str, entry: dict | None = None, overrides: dict | None = None) -> str:
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    lines = [
        "---",
        f"source_path: {input_path.as_posix()}",
        f"source_type: {source_type}",
        f"source_kind: {infer_source_kind(entry, input_path, overrides)}",
    ]
    if entry:
        lines.extend(
            [
                f"bib_key: {entry.get('key')}",
                f"bib_entry_type: {entry.get('entry_type')}",
            ]
        )
        if entry.get("type"):
            lines.append(f"bib_type: {entry.get('type')}")
        if entry.get("title"):
            lines.append(f"bib_title: {entry.get('title')}")
    lines.extend(["converter: markitdown", f"converted_at: {now}", "---", ""])
    return "\n".join(lines) + "\n"


def convert_with_markitdown(input_path: Path, output_path: Path, source_type: str, force: bool = False) -> dict:
    input_path = input_path.resolve()
    bib_entries = parse_bib_entries()
    bib_entry = find_bib_entry(input_path, bib_entries)
    overrides = load_source_kind_overrides()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists() and not force:
        return {
            "status": "skipped",
            "input": str(input_path),
            "output": str(output_path),
            "reason": "output exists",
        }

    cmd = markitdown_command() + [str(input_path)]
    proc = subprocess.run(cmd, text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        return {
            "status": "failed",
            "input": str(input_path),
            "output": str(output_path),
            "error": (proc.stderr or proc.stdout).strip(),
        }

    content = proc.stdout.strip()
    output_path.write_text(metadata_block(input_path, source_type, bib_entry, overrides) + content + "\n", encoding="utf-8")
    return {
        "status": "converted",
        "input": str(input_path),
        "output": str(output_path),
        "chars": len(content),
        "source_kind": infer_source_kind(bib_entry, input_path, overrides),
        "bib_key": bib_entry.get("key") if bib_entry else None,
    }


def iter_corpus_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if path.is_dir():
            continue
        if any(part in EXCLUDED_DIRS for part in path.parts):
            continue
        if path.suffix.lower() in {".pdf", ".html", ".htm"}:
            files.append(path)
    return sorted(files)
