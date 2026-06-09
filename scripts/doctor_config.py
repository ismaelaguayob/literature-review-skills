#!/usr/bin/env python3
"""Diagnose common project configuration problems."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from shared.project_config import load_config, yaml_load  # noqa: E402


ANALYTIC_KEYS = {
    "taxonomy_proposal",
    "proposed_taxonomy",
    "current_hypothesis",
    "hypothesis",
    "proposed_categories",
    "category_definitions",
    "findings",
    "conclusions",
    "paper_notes",
}


def nested_keys(data: Any, prefix: str = "") -> list[str]:
    if not isinstance(data, dict):
        return []
    keys = []
    for key, value in data.items():
        path = f"{prefix}.{key}" if prefix else str(key)
        keys.append(path)
        keys.extend(nested_keys(value, path))
    return keys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="literature-review.yaml")
    args = parser.parse_args()

    config_path = Path(args.config)
    raw = yaml_load(config_path)
    config = load_config(config_path)
    warnings: list[str] = []

    if not config_path.exists():
        warnings.append(f"missing config file: {config_path}")

    bib_path = Path(config.get("project", {}).get("bib_path", ""))
    if not bib_path.exists():
        close = [path.name for path in Path(".").glob("*.bib")]
        extra = f" Existing .bib files: {', '.join(close)}." if close else ""
        warnings.append(f"configured bib_path does not exist: {bib_path}.{extra}")

    for key in ("sources_dir", "machine_dir", "retrieval_intermediate_dir", "analysis_intermediate_dir", "review_state_dir"):
        value = config.get("paths", {}).get(key)
        if not value:
            warnings.append(f"missing paths.{key}")

    core_terms = config.get("retrieval", {}).get("core_terms", [])
    modifier_terms = config.get("retrieval", {}).get("modifier_terms", [])
    if len(core_terms) > 10:
        warnings.append("retrieval.core_terms has more than 10 terms; consider moving secondary/exploratory terms to modifier_terms or literature-keywords.yaml candidates")
    if len(core_terms) == 0:
        warnings.append("retrieval.core_terms is empty; add 3-8 central constructs for better scoring and query generation")
    if len(modifier_terms) == 0:
        warnings.append("retrieval.modifier_terms is empty; add methods, evidence types, units, regions, or measurement vocabulary")

    raw_key_paths = nested_keys(raw)
    for path in raw_key_paths:
        leaf = path.rsplit(".", 1)[-1]
        if leaf in ANALYTIC_KEYS:
            warnings.append(f"{path} looks like analytical state; move it to review-state/ or outputs/analysis/")

    category_dimensions = config.get("synthesis", {}).get("category_dimensions", [])
    if len(category_dimensions) == 0:
        warnings.append("synthesis.category_dimensions is empty; add category prompts such as source_type, thematic_category, methodology, unit_of_analysis")

    source_llm = config.get("synthesis", {}).get("source_llm", {})
    if not isinstance(source_llm, dict):
        warnings.append("synthesis.source_llm should be a mapping")
    else:
        workers = int(source_llm.get("workers", 0) or 0)
        if workers <= 0:
            warnings.append("synthesis.source_llm.workers should be at least 1")
        if workers > 8:
            warnings.append("synthesis.source_llm.workers is above 8; high concurrency should be an explicit cost/rate-limit decision")
        if not source_llm.get("model"):
            warnings.append("synthesis.source_llm.model is empty")
        if source_llm.get("provider") != "openrouter":
            warnings.append("synthesis.source_llm.provider is not openrouter; verify the runner supports the configured provider")

    semantic = config.get("apis", {}).get("semantic_scholar", {})
    if isinstance(semantic, dict):
        min_interval = float(semantic.get("min_interval_seconds", 0) or 0)
        if min_interval < 0.5:
            warnings.append("apis.semantic_scholar.min_interval_seconds is below 0.5; this may trigger 429 rate limits")

    openrouter = config.get("apis", {}).get("openrouter", {})
    if not isinstance(openrouter, dict) or not openrouter.get("api_key_env"):
        warnings.append("apis.openrouter.api_key_env is missing")

    if warnings:
        print("Configuration warnings:")
        for warning in warnings:
            print(f"- {warning}")
        return 1
    print("Configuration looks good.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
