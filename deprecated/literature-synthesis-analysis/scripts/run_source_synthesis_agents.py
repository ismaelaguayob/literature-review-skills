#!/usr/bin/env python3
"""Run non-interactive Codex source-synthesis agents over source groups."""

from __future__ import annotations

import argparse
import concurrent.futures as futures
import datetime as dt
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from common import PROJECT_CONFIG, apa_citation, apa_reference, body_text, parse_bib_entries, parse_metadata, slugify
from segment_source import segments as source_segments


PROJECT_ROOT = Path.cwd()
DEFAULT_RUN_ROOT = Path(PROJECT_CONFIG["paths"]["analysis_intermediate_dir"])


@dataclass(frozen=True)
class SourceGroup:
    group_id: str
    slug: str
    title: str
    bib_key: str | None
    source_kind: str
    files: tuple[Path, ...]
    segment: dict | None = None


def source_agent_config() -> dict:
    return PROJECT_CONFIG.get("synthesis", {}).get("source_agents", {})


def required_sections() -> list[str]:
    sections = PROJECT_CONFIG.get("synthesis", {}).get("intermediate_sections", [])
    return [str(section) for section in sections] or [
        "Thesis",
        "Key Concepts and Definitions",
        "Categories Suggested by This Source",
        "Mechanisms, Arguments, or Findings",
        "Tensions and Trade-offs",
        "Evidence and Traceable Notes",
        "Implications for the Review",
        "Open Questions",
    ]


def read_yaml_context(config_path: Path) -> str:
    return config_path.read_text(encoding="utf-8", errors="replace")


def frontmatter(path: Path) -> dict[str, str]:
    return parse_metadata(path)


def group_sources(machine_dirs: list[Path], split_long_sources: bool, max_chars: int) -> list[SourceGroup]:
    entries = parse_bib_entries()
    groups: dict[str, list[Path]] = {}
    metadata_by_group: dict[str, dict[str, str]] = {}
    for machine_dir in machine_dirs:
        for path in sorted(machine_dir.glob("*.md")):
            meta = frontmatter(path)
            bib_key = meta.get("bib_key")
            title = meta.get("bib_title") or path.stem
            group_key = f"bib:{bib_key}" if bib_key else f"file:{path.stem}"
            groups.setdefault(group_key, []).append(path)
            metadata_by_group.setdefault(
                group_key,
                {
                    "bib_key": bib_key or "",
                    "title": title,
                    "source_kind": meta.get("source_kind", "unknown"),
                },
            )

    output: list[SourceGroup] = []
    for group_key, files in sorted(groups.items(), key=lambda item: item[0]):
        meta = metadata_by_group[group_key]
        bib_key = meta.get("bib_key") or None
        entry = entries.get(bib_key or "")
        title = (entry or {}).get("title") or meta.get("title") or files[0].stem
        base_slug = slugify(bib_key or title)
        if base_slug == "source":
            base_slug = slugify(title)
        source_kind = meta.get("source_kind", "unknown")
        file_tuple = tuple(files)
        total_chars = sum(len(body_text(path)) for path in file_tuple)
        if split_long_sources and len(file_tuple) == 1 and total_chars > max_chars:
            for index, segment in enumerate(source_segments(file_tuple[0]), start=1):
                output.append(
                    SourceGroup(
                        group_id=f"{group_key}:segment:{index:03d}",
                        slug=f"{base_slug}-segment-{index:03d}",
                        title=f"{title} [{segment.get('heading', 'segment')}]",
                        bib_key=bib_key,
                        source_kind=source_kind,
                        files=file_tuple,
                        segment=segment,
                    )
                )
            continue
        output.append(
            SourceGroup(
                group_id=group_key,
                slug=base_slug,
                title=title,
                bib_key=bib_key,
                source_kind=source_kind,
                files=file_tuple,
            )
        )
    return output


def metadata_json(group: SourceGroup) -> str:
    entries = parse_bib_entries()
    entry = entries.get(group.bib_key or "")
    payload = {
        "group_id": group.group_id,
        "bib_key": group.bib_key,
        "title": group.title,
        "source_kind": group.source_kind,
        "apa_reference": apa_reference(entry),
        "apa_citation": apa_citation(entry),
        "segment": group.segment,
        "files": [
            {
                "path": path.as_posix(),
                "metadata": frontmatter(path),
            }
            for path in group.files
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def prompt_for(group: SourceGroup, output_path: Path, config_path: Path, config_text: str) -> str:
    sections = "\n".join(f"- {section}" for section in required_sections())
    segment_instruction = ""
    if group.segment:
        segment_instruction = f"""
This task is restricted to one long-source segment:
```json
{json.dumps(group.segment, ensure_ascii=False, indent=2)}
```
Use this segment as the main scope. You may inspect nearby context only when necessary to understand the segment.
"""
    return f"""You are a non-interactive Codex sub-agent running inside a literature-review pipeline.

Your only job is to create one source-level or segment-level synthesis file.

Hard constraints:
- Write exactly one Markdown file: `{output_path.as_posix()}`.
- Do not edit any other file.
- Do not create a curated synthesis.
- Do not search the internet.
- Work only from the listed machine-readable source file(s), their metadata, and the project YAML included below.
- If multiple files are listed, they are duplicate/companion artifacts for the same bibliographic source. Analyze them together and explicitly note how they relate.
- Include a YAML frontmatter block followed by Markdown sections.
- Use exact file paths from Source metadata when creating trace links.
- Prefer relative links when possible; absolute links are allowed only if needed.
- Every substantive claim about the source must be supported by at least one trace link to an anchor in the machine-readable file.
- Anchor existence is not enough: the cited anchor must correspond to the claim being made. Choose anchors that actually contain or introduce the evidence.
- If extraction quality is poor, say so and lower confidence rather than inventing details.
- Be detailed. Do not shorten just because a source looks peripheral; part of the task is to reassess relevance from the full text.
- Use the review lens from `{config_path.as_posix()}` and keep the analysis generalizable.
{segment_instruction}
Required YAML frontmatter fields:
```yaml
source_group_id:
bib_key:
title:
source_kind:
relevance_to_review: core|supporting|peripheral|uncertain
recommended_use:
confidence: high|medium|low
needs_deeper_review: true|false
```

Required Markdown sections:
{sections}

For "Evidence and Traceable Notes":
- Provide several evidence notes if the source has enough content.
- Each note must include Claim, Evidence, Citation, and Trace.
- Trace links must be Markdown links to the machine-readable file path plus `#anchor`.
- Prefer anchors that point to section starts; if the relevant text is table-like or OCR-noisy, explain the limitation.

Project YAML:
```yaml
{config_text}
```

Source metadata:
```json
{metadata_json(group)}
```

Now read the source file(s), synthesize the source faithfully, and write `{output_path.as_posix()}`.
"""


def command_for(args: argparse.Namespace, output_last_message: Path) -> list[str]:
    cmd = [
        "codex",
        "exec",
        "-C",
        str(PROJECT_ROOT),
        "--sandbox",
        "workspace-write",
        "-m",
        args.model,
        "-c",
        f'model_reasoning_effort="{args.reasoning_effort}"',
        "--output-last-message",
        str(output_last_message),
        "-",
    ]
    if args.ephemeral:
        cmd.insert(2, "--ephemeral")
    return cmd


def run_one(group: SourceGroup, args: argparse.Namespace, run_dir: Path, config_path: Path, config_text: str) -> dict:
    output_path = run_dir / "source-syntheses" / f"{group.slug}.md"
    log_path = run_dir / "logs" / f"{group.slug}.last-message.txt"
    prompt_path = run_dir / "prompts" / f"{group.slug}.prompt.md"
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path.exists() and not args.force:
        return {"group": group.group_id, "output": str(output_path), "status": "skipped"}

    prompt = prompt_for(group, output_path, config_path, config_text)
    prompt_path.write_text(prompt, encoding="utf-8")
    cmd = command_for(args, log_path)

    attempts = args.retries + 1
    last_error = ""
    for attempt in range(1, attempts + 1):
        proc = subprocess.run(
            cmd,
            input=prompt,
            text=True,
            cwd=PROJECT_ROOT,
            capture_output=True,
            timeout=args.timeout_seconds,
            check=False,
        )
        if proc.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0:
            return {"group": group.group_id, "output": str(output_path), "status": "ok", "attempts": attempt}
        last_error = (proc.stderr or proc.stdout or "").strip()[-4000:]
        if attempt < attempts and args.retry_delay_seconds > 0:
            time.sleep(args.retry_delay_seconds)
    return {
        "group": group.group_id,
        "output": str(output_path),
        "status": "failed",
        "attempts": attempts,
        "error": last_error,
    }


def write_manifest(run_dir: Path, groups: list[SourceGroup], args: argparse.Namespace) -> None:
    manifest = {
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "model": args.model,
        "reasoning_effort": args.reasoning_effort,
        "workers": args.workers,
        "groups": [
            {
                "group_id": group.group_id,
                "slug": group.slug,
                "title": group.title,
                "bib_key": group.bib_key,
                "segment": group.segment,
                "files": [path.as_posix() for path in group.files],
            }
            for group in groups
        ],
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def append_result(run_dir: Path, result: dict) -> None:
    path = run_dir / "results.ndjson"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(result, ensure_ascii=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    agent_config = source_agent_config()
    parser.add_argument("--config", default="literature-review.yaml")
    parser.add_argument("--machine-dir", action="append", help="Machine-readable directory to process. Defaults to configured machine_dir.")
    parser.add_argument("--run-name", help="Output iteration directory name. Defaults to timestamped source-agent run.")
    parser.add_argument("--model", default=agent_config.get("model", "gpt-5.4-mini"))
    parser.add_argument("--reasoning-effort", default=agent_config.get("reasoning_effort", "medium"), choices=["minimal", "low", "medium", "high"])
    parser.add_argument("--workers", type=int, default=int(agent_config.get("workers", 4)))
    parser.add_argument("--retries", type=int, default=int(agent_config.get("retries", 1)))
    parser.add_argument("--retry-delay-seconds", type=int, default=int(agent_config.get("retry_delay_seconds", 30)))
    parser.add_argument("--timeout-seconds", type=int, default=int(agent_config.get("timeout_seconds", 1800)))
    parser.add_argument("--max-chars-per-agent", type=int, default=int(agent_config.get("max_chars_per_agent", 180000)))
    parser.add_argument("--split-long-sources", action=argparse.BooleanOptionalAction, default=bool(agent_config.get("split_long_sources", True)))
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--no-ephemeral", dest="ephemeral", action="store_false")
    parser.add_argument("--dry-run", action="store_true")
    parser.set_defaults(ephemeral=True)
    args = parser.parse_args()

    if args.workers > 8 and not os.environ.get("LIT_REVIEW_ALLOW_HIGH_CONCURRENCY"):
        print(
            "Refusing workers > 8 without LIT_REVIEW_ALLOW_HIGH_CONCURRENCY=1. "
            "High concurrency can trigger rate limits and large quota bursts.",
            file=sys.stderr,
        )
        return 2

    config_path = Path(args.config)
    config_text = read_yaml_context(config_path)
    machine_dirs = [Path(item) for item in args.machine_dir] if args.machine_dir else [Path(PROJECT_CONFIG["paths"]["machine_dir"])]
    groups = group_sources(machine_dirs, args.split_long_sources, args.max_chars_per_agent)

    run_name = args.run_name or dt.datetime.now().strftime("%Y-%m-%d-%H%M%S-source-agents")
    run_dir = DEFAULT_RUN_ROOT / run_name

    if args.dry_run:
        print(json.dumps({"run_dir": str(run_dir), "groups": len(groups)}, ensure_ascii=False, indent=2))
        return 0

    run_dir.mkdir(parents=True, exist_ok=True)
    write_manifest(run_dir, groups, args)

    results: list[dict] = []
    with futures.ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        submitted = [executor.submit(run_one, group, args, run_dir, config_path, config_text) for group in groups]
        for future in futures.as_completed(submitted):
            result = future.result()
            results.append(result)
            append_result(run_dir, result)
            print(json.dumps(result, ensure_ascii=False), flush=True)

    results = sorted(results, key=lambda row: row["group"])
    (run_dir / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    failed = [row for row in results if row["status"] == "failed"]
    print(json.dumps({"run_dir": str(run_dir), "ok": len(results) - len(failed), "failed": len(failed)}, ensure_ascii=False, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
