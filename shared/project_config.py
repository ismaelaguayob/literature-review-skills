"""Project configuration and keyword ledger helpers."""

from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path
from typing import Any


DEFAULT_CONFIG_PATH = Path("literature-review.yaml")


DEFAULT_CONFIG: dict[str, Any] = {
    "project": {
        "name": "Literature Review",
        "slug": "literature-review",
        "description": "Reusable literature review workflow",
        "bib_path": "references.bib",
    },
    "paths": {
        "sources_dir": "sources",
        "machine_dir": "machine-readable/markitdown",
        "retrieval_intermediate_dir": "outputs/retrieval/intermediate",
        "retrieval_curated_dir": "outputs/retrieval/curated",
        "analysis_intermediate_dir": "outputs/analysis/intermediate",
        "analysis_curated_dir": "outputs/analysis/curated",
        "keyword_ledger": "literature-keywords.yaml",
        "review_state_dir": "review-state",
    },
    "retrieval": {
        "from_year": 2019,
        "to_year": None,
        "default_limit": 10,
        "user_agent": "literature-review/0.1",
        "sources": {
            "enabled": [
                "openalex",
                "semantic-scholar",
                "core",
                "springer-metadata",
                "springer-openaccess",
                "crossref",
            ],
            "targeted": ["arxiv"],
        },
        "core_terms": [],
        "modifier_terms": [
            "indicator",
            "index",
            "measurement",
            "measure",
            "typology",
            "framework",
            "maturity",
            "capability",
            "capacity",
            "dependency",
            "infrastructure",
            "governance",
        ],
        "exclusion_terms": [],
        "default_queries": [],
        "keyword_suggestion_limit": 30,
    },
    "apis": {
        "openalex": {
            "min_interval_seconds": 0.2,
            "retries": 4,
            "cache": True,
        },
        "semantic_scholar": {
            "min_interval_seconds": 1.0,
            "retries": 4,
            "throttle_scope": "project",
            "cache": True,
        },
        "crossref": {
            "min_interval_seconds": 0.5,
            "retries": 4,
            "cache": True,
        },
        "springer": {
            "metadata_api_key_env": "SPRINGER_METADATA_API_KEY",
            "openaccess_api_key_env": "SPRINGER_OPENACCESS_API_KEY",
            "min_interval_seconds": 1.0,
            "retries": 4,
            "cache": True,
        },
        "core": {
            "api_key_env": "CORE_API_KEY",
            "min_interval_seconds": 1.0,
            "retries": 4,
            "cache": True,
        },
        "openrouter": {
            "api_key_env": "OPENROUTER_API_KEY",
            "base_url": "https://openrouter.ai/api/v1",
            "min_interval_seconds": 3.0,
            "retries": 3,
            "cache": True,
        },
    },
    "synthesis": {
        "mode": "direct_llm",
        "lens_name": "General literature synthesis",
        "use_measurement_lens": True,
        "curated_title": "Curated Synthesis",
        "category_dimensions": [
            "source_type",
            "thematic_category",
            "methodological_approach",
            "measurement_approach",
        ],
        "intermediate_sections": [
            "Thesis",
            "Key Concepts and Definitions",
            "Categories Suggested by This Source",
            "Mechanisms, Arguments, or Findings",
            "Tensions and Trade-offs",
            "Evidence and Traceable Notes",
            "Implications for the Review",
            "Open Questions",
        ],
        "findings_sections": [
            "Thesis",
            "Categories Suggested by This Source",
            "Implications for the Review",
        ],
        "source_llm": {
            "provider": "openrouter",
            "model": "google/gemini-3.5-flash",
            "temperature": 0,
            "max_output_tokens": 6000,
            "output_mode": "json_schema",
            "workers": 4,
            "requests_per_minute": 20,
            "retries": 3,
            "retry_delay_seconds": 10,
            "max_input_chars": 120000,
            "split_long_sources": True,
            "min_evidence_notes": 4,
            "require_trace_links": True,
            "require_semantic_audit": True,
        },
    },
}


def _simple_yaml_load(text: str) -> dict[str, Any]:
    """Small fallback parser for the simple YAML shape used by this project."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    lines = [
        raw_line.rstrip()
        for raw_line in text.splitlines()
        if raw_line.strip() and not raw_line.lstrip().startswith("#")
    ]

    def indent_of(raw_line: str) -> int:
        return len(raw_line) - len(raw_line.lstrip(" "))

    def parse_block(index: int, indent: int) -> tuple[Any, int]:
        if index >= len(lines):
            return {}, index
        is_list = indent_of(lines[index]) == indent and lines[index].strip().startswith("- ")
        if is_list:
            return parse_list(index, indent)
        return parse_map(index, indent)

    def parse_map(index: int, indent: int) -> tuple[dict[str, Any], int]:
        data: dict[str, Any] = {}
        while index < len(lines):
            raw_line = lines[index]
            current_indent = indent_of(raw_line)
            if current_indent < indent:
                break
            if current_indent > indent:
                index += 1
                continue
            line = raw_line.strip()
            if line.startswith("- ") or ":" not in line:
                break
            key, raw_value = line.split(":", 1)
            key = key.strip()
            raw_value = raw_value.strip()
            if raw_value:
                data[key] = _parse_scalar(raw_value)
                index += 1
                continue
            has_child_block = (
                index + 1 < len(lines)
                and (
                    indent_of(lines[index + 1]) > current_indent
                    or (indent_of(lines[index + 1]) == current_indent and lines[index + 1].strip().startswith("- "))
                )
            )
            if has_child_block:
                data[key], index = parse_block(index + 1, indent_of(lines[index + 1]))
            else:
                data[key] = None
                index += 1
        return data, index

    def parse_list(index: int, indent: int) -> tuple[list[Any], int]:
        data: list[Any] = []
        while index < len(lines):
            raw_line = lines[index]
            current_indent = indent_of(raw_line)
            if current_indent < indent:
                break
            if current_indent > indent:
                index += 1
                continue
            line = raw_line.strip()
            if not line.startswith("- "):
                break
            item_text = line[2:].strip()
            index += 1
            if not item_text:
                if index < len(lines) and indent_of(lines[index]) > current_indent:
                    item, index = parse_block(index, indent_of(lines[index]))
                    data.append(item)
                else:
                    data.append(None)
                continue
            if ":" in item_text and not item_text.startswith(("'", '"')):
                key, raw_value = item_text.split(":", 1)
                item: dict[str, Any] = {key.strip(): _parse_scalar(raw_value.strip()) if raw_value.strip() else None}
                if index < len(lines) and indent_of(lines[index]) > current_indent:
                    child, index = parse_map(index, indent_of(lines[index]))
                    item.update(child)
                data.append(item)
            else:
                data.append(_parse_scalar(item_text))
        return data, index

    parsed, _ = parse_block(0, indent_of(lines[0]) if lines else 0)
    return parsed if isinstance(parsed, dict) else {}


def _parse_scalar(value: str) -> Any:
    if value in {"", "null", "None", "~"}:
        return None
    if value in {"true", "True"}:
        return True
    if value in {"false", "False"}:
        return False
    if value == "[]":
        return []
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(part.strip()) for part in inner.split(",")]
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    try:
        return int(value)
    except ValueError:
        return value


def yaml_load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore

        loaded = yaml.safe_load(text)
        return loaded or {}
    except Exception:
        return _simple_yaml_load(text)


def yaml_dump(data: dict[str, Any]) -> str:
    try:
        import yaml  # type: ignore

        return yaml.safe_dump(data, allow_unicode=True, sort_keys=False)
    except Exception:
        return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    config_path = Path(path) if path else DEFAULT_CONFIG_PATH
    return deep_merge(DEFAULT_CONFIG, yaml_load(config_path))


def path_from_config(config: dict[str, Any], key: str) -> Path:
    return Path(config["paths"][key])


def bib_path(config: dict[str, Any]) -> Path:
    return Path(config["project"]["bib_path"])


def retrieval_terms(config: dict[str, Any]) -> tuple[set[str], set[str]]:
    retrieval = config.get("retrieval", {})
    return (
        {normalize(term) for term in retrieval.get("core_terms", []) if term},
        {normalize(term) for term in retrieval.get("modifier_terms", []) if term},
    )


def normalize(value: str | None) -> str:
    if not value:
        return ""
    value = value.lower()
    value = re.sub(r"https?://(dx\.)?doi\.org/", "", value)
    value = re.sub(r"[^a-z0-9áéíóúñü]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def ensure_keyword_ledger(config: dict[str, Any]) -> Path:
    path = path_from_config(config, "keyword_ledger")
    if path.exists():
        return path
    slug = config["project"]["slug"]
    core_terms = config.get("retrieval", {}).get("core_terms", [])
    active = [{"term": term, "source": "project_config"} for term in core_terms]
    data = {
        "project_slug": slug,
        "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "active": active,
        "candidates": [],
        "rejected": [],
        "query_templates": [
            "{core_term} measurement",
            "{core_term} indicators",
            "{core_term} conceptual framework",
            "{core_term} literature review",
        ],
    }
    path.write_text(yaml_dump(data), encoding="utf-8")
    return path


def load_keyword_ledger(config: dict[str, Any]) -> dict[str, Any]:
    path = ensure_keyword_ledger(config)
    data = yaml_load(path)
    data.setdefault("active", [])
    data.setdefault("candidates", [])
    data.setdefault("rejected", [])
    data.setdefault("query_templates", [])
    return data


def save_keyword_ledger(config: dict[str, Any], ledger: dict[str, Any]) -> Path:
    ledger["project_slug"] = config["project"]["slug"]
    ledger["updated_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    path = path_from_config(config, "keyword_ledger")
    path.write_text(yaml_dump(ledger), encoding="utf-8")
    return path


def keyword_terms(rows: list[dict[str, Any]]) -> set[str]:
    terms = set()
    for row in rows:
        term = normalize(str(row.get("term") or ""))
        if term:
            terms.add(term)
    return terms


def add_keyword_candidates(config: dict[str, Any], candidates: list[dict[str, Any]]) -> tuple[Path, int]:
    ledger = load_keyword_ledger(config)
    active = keyword_terms(ledger.get("active", []))
    rejected = keyword_terms(ledger.get("rejected", []))
    existing_candidates = keyword_terms(ledger.get("candidates", []))
    added = 0
    for candidate in candidates:
        term = normalize(str(candidate.get("term") or ""))
        if not term or term in active or term in rejected or term in existing_candidates:
            continue
        ledger["candidates"].append(candidate)
        existing_candidates.add(term)
        added += 1
    return save_keyword_ledger(config, ledger), added
