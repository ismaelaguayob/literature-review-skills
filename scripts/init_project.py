#!/usr/bin/env python3
"""Initialize literature review config and directories in a project."""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path


TOOLKIT_ROOT = Path(__file__).resolve().parents[1]
for candidate in (Path.cwd(), TOOLKIT_ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from shared.project_config import DEFAULT_CONFIG, ensure_keyword_ledger, load_config, save_keyword_ledger, yaml_dump  # noqa: E402


def slugify(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value or "literature-review"


def install_agent_skills(toolkit_root: Path, target_root: Path, force: bool = False) -> list[Path]:
    source_dir = toolkit_root / "skills"
    if not source_dir.exists():
        return []
    target_dir = target_root / ".agents" / "skills"
    target_dir.mkdir(parents=True, exist_ok=True)
    installed = []
    for source in sorted(source_dir.iterdir()):
        if not source.is_dir():
            continue
        target = target_dir / source.name
        if target.exists():
            if not force:
                continue
            shutil.rmtree(target)
        shutil.copytree(source, target)
        installed.append(target)
    return installed


def copy_support_dir(toolkit_root: Path, target_root: Path, name: str, force: bool = False) -> Path | None:
    source = toolkit_root / name
    target = target_root / name
    if not source.exists() or source.resolve() == target.resolve():
        return None
    if target.exists():
        if not force:
            return target
        shutil.rmtree(target)
    shutil.copytree(source, target)
    return target


def research_brief_text(name: str) -> str:
    return f"""# Research Brief: {name}

## Research Questions

## Objectives

## Working Hypotheses

## Scope Conditions

## Inclusion Priorities

## Exclusion Criteria

## Notes for the Final Narrative

- Write the final narrative as a publishable English Quarto paper, not as a robotic report.
- Use exact BibTeX keys from the configured `.bib` file.
- Narrative citations in Quarto use bare keys in prose, for example: `@roberts_digital_2024 argues that ...`.
- Parenthetical citations use brackets, for example: `... [@roberts_digital_2024]`.
- Multiple parenthetical citations use semicolons, for example: `... [@key1; @key2]`.
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True, help="Project display name")
    parser.add_argument("--bib-path", default="references.bib")
    parser.add_argument("--core-term", action="append", default=[])
    parser.add_argument("--skip-agent-skills", action="store_true", help="Do not copy bundled skills to .agents/skills")
    parser.add_argument("--refresh-toolkit", action="store_true", help="Overwrite .agents/skills, shared, and scripts without rewriting existing config")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    config_path = Path("literature-review.yaml")
    config_exists = config_path.exists()
    config = load_config(config_path if config_exists else None)
    if config_exists and not args.force:
        print(f"Skipped existing config: {config_path}")
    else:
        config["project"] = dict(DEFAULT_CONFIG["project"])
        config["project"]["name"] = args.name
        config["project"]["slug"] = slugify(args.name)
        config["project"]["description"] = f"Literature review on {args.name}"
        config["project"]["bib_path"] = args.bib_path
        config["retrieval"]["core_terms"] = args.core_term
        config["retrieval"]["default_queries"] = [f"{term} literature review" for term in args.core_term]
        config_path.write_text(yaml_dump(config), encoding="utf-8")
    for key in (
        "sources_dir",
        "machine_dir",
        "retrieval_intermediate_dir",
        "retrieval_curated_dir",
        "analysis_intermediate_dir",
        "analysis_curated_dir",
        "review_state_dir",
    ):
        Path(config["paths"][key]).mkdir(parents=True, exist_ok=True)
    brief_path = Path(config["paths"]["review_state_dir"]) / "research-brief.md"
    if args.force or not brief_path.exists():
        brief_path.write_text(research_brief_text(config["project"]["name"]), encoding="utf-8")
    ledger_path = Path(config["paths"]["keyword_ledger"])
    ensure_keyword_ledger(config)
    if args.force or not ledger_path.exists():
        ledger = {
            "project_slug": config["project"]["slug"],
            "updated_at": None,
            "active": [{"term": term, "source": "seed"} for term in args.core_term],
            "candidates": [],
            "rejected": [],
            "query_templates": [
                "{core_term} measurement",
                "{core_term} indicators",
                "{core_term} conceptual framework",
                "{core_term} literature review",
            ],
        }
        save_keyword_ledger(config, ledger)
    installed = []
    support_dirs = []
    refresh_toolkit = args.force or args.refresh_toolkit
    for dirname in ("shared", "scripts"):
        copied = copy_support_dir(TOOLKIT_ROOT, Path.cwd(), dirname, refresh_toolkit)
        if copied:
            support_dirs.append(copied)
    if not args.skip_agent_skills:
        installed = install_agent_skills(TOOLKIT_ROOT, Path.cwd(), refresh_toolkit)
    print(config_path)
    print(config["paths"]["keyword_ledger"])
    for copied in support_dirs:
        print(copied)
    if installed:
        print(".agents/skills")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
