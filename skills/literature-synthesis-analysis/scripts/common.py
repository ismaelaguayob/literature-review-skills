"""Shared helpers for literature synthesis scripts."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = Path.cwd()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from shared.project_config import bib_path, load_config, path_from_config  # noqa: E402


PROJECT_CONFIG = load_config()
BIB_PATH = bib_path(PROJECT_CONFIG)
MACHINE_DIR = path_from_config(PROJECT_CONFIG, "machine_dir")
INTERMEDIATE_DIR = path_from_config(PROJECT_CONFIG, "analysis_intermediate_dir")
CURATED_DIR = path_from_config(PROJECT_CONFIG, "analysis_curated_dir")


def clean_bib_value(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip().strip("{}")
    value = re.sub(r"}\s+and\s+{", " and ", value)
    value = value.replace("{{", "").replace("}}", "")
    value = value.replace("{", "").replace("}", "")
    value = value.replace("\\&", "&")
    value = value.replace('\\"u', "ü").replace("{\\\"u}", "ü")
    value = _replace_latex_accents(value)
    value = value.replace("$", "")
    value = re.sub(r"\\textbar\{\}", "|", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip() or None


def _replace_latex_accents(value: str) -> str:
    replacements = {
        "\\'a": "á",
        "\\'e": "é",
        "\\'i": "í",
        "\\'o": "ó",
        "\\'u": "ú",
        "\\`a": "à",
        "\\`e": "è",
        "\\`i": "ì",
        "\\`o": "ò",
        "\\`u": "ù",
        '\\"a': "ä",
        '\\"e': "ë",
        '\\"i': "ï",
        '\\"o': "ö",
        '\\"u': "ü",
        "\\~n": "ñ",
    }
    for source, target in replacements.items():
        value = value.replace(source, target)
    return value


def parse_bib_entries(path: Path = BIB_PATH) -> dict[str, dict]:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    starts = list(re.finditer(r"^@(\w+)\{([^,]+),", text, re.MULTILINE))
    entries: dict[str, dict] = {}
    for index, match in enumerate(starts):
        start = match.start()
        end = starts[index + 1].start() if index + 1 < len(starts) else len(text)
        block = text[start:end]
        fields = {}
        for field_match in re.finditer(r"^\s*([A-Za-z]+)\s*=\s*(.+?)\s*,?\s*$", block, re.MULTILINE):
            raw_value = field_match.group(2).strip()
            fields[field_match.group(1).lower()] = clean_bib_value(raw_value)
        entries[match.group(2)] = {
            "key": match.group(2),
            "entry_type": match.group(1),
            **fields,
        }
    return entries


def parse_metadata(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}
    metadata = {}
    for line in text[4:end].splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip()
    return metadata


def body_text(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            return text[end + 5 :]
    return text


def slugify(value: str, max_length: int = 90) -> str:
    value = value.lower()
    value = value.replace("ü", "u").replace("ö", "o").replace("ä", "a").replace("é", "e")
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value[:max_length].strip("-") or "source"


def apa_author(author_field: str | None) -> str:
    if not author_field:
        return "Unknown"
    authors = [part.strip() for part in author_field.split(" and ") if part.strip()]
    family_names = []
    for author in authors:
        if "," in author:
            family_names.append(author.split(",", 1)[0].strip("{} "))
        elif _looks_like_corporate_author(author):
            family_names.append(author.strip("{} "))
        else:
            family_names.append(author.split()[-1].strip("{} "))
    if len(family_names) == 1:
        return family_names[0]
    if len(family_names) == 2:
        return f"{family_names[0]} & {family_names[1]}"
    return f"{family_names[0]} et al."


def _looks_like_corporate_author(author: str) -> bool:
    words = author.split()
    if len(words) <= 1:
        return False
    corporate_markers = {
        "Agency",
        "Bank",
        "BCG",
        "Commission",
        "Community",
        "Consulting",
        "Department",
        "Eurostat",
        "Foundation",
        "Group",
        "Institute",
        "International",
        "OECD",
        "Organization",
        "Publishing",
        "University",
        "World",
    }
    return any(word.strip("{} ") in corporate_markers for word in words)


def apa_citation(entry: dict | None) -> str:
    if not entry:
        return "(Unknown, n.d.)"
    return f"({apa_author(entry.get('author'))}, {entry.get('year', 'n.d.')})"


def apa_reference(entry: dict | None) -> str:
    if not entry:
        return "Unknown. (n.d.)."
    author = clean_bib_value(entry.get("author")) or "Unknown"
    year = entry.get("year", "n.d.")
    title = clean_bib_value(entry.get("title")) or "Untitled"
    container = entry.get("journal") or entry.get("publisher") or entry.get("institution")
    doi = entry.get("doi")
    reference = f"{author}. ({year}). {title}."
    if container:
        reference += f" {container}."
    if doi:
        reference += f" https://doi.org/{doi.replace('https://doi.org/', '')}"
    return reference


def machine_sources() -> list[Path]:
    return sorted(MACHINE_DIR.glob("*.md"))


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
