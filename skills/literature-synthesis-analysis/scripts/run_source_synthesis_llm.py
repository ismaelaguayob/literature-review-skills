#!/usr/bin/env python3
"""Run direct OpenRouter source syntheses over source groups."""

from __future__ import annotations

import argparse
import concurrent.futures as futures
import datetime as dt
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from common import PROJECT_CONFIG, apa_citation, apa_reference, body_text, parse_bib_entries, parse_metadata, slugify
from render_source_synthesis import render_file
from segment_source import segments as source_segments
from source_synthesis_schema import openrouter_response_format


PROJECT_ROOT = Path.cwd()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from shared.api_utils import (  # noqa: E402
    cache_enabled,
    cache_key,
    load_env,
    min_interval_for,
    read_cached_json,
    retries_for,
    throttle,
    write_cached_json,
)


DEFAULT_RUN_ROOT = Path(PROJECT_CONFIG["paths"]["analysis_intermediate_dir"])


@dataclass(frozen=True)
class SourceGroup:
    group_id: str
    slug: str
    title: str
    bib_key: str | None
    source_kind: str
    files: tuple[Path, ...]
    segment: dict[str, Any] | None = None


def source_llm_config() -> dict[str, Any]:
    return PROJECT_CONFIG.get("synthesis", {}).get("source_llm", {})


def required_sections() -> list[str]:
    return PROJECT_CONFIG.get("synthesis", {}).get("intermediate_sections", [])


BASE_RENDERED_SECTIONS = {
    "Thesis",
    "Key Concepts and Definitions",
    "Categories Suggested by This Source",
    "Mechanisms, Arguments, or Findings",
    "Tensions and Trade-offs",
    "Evidence and Traceable Notes",
    "Implications for the Review",
    "Open Questions",
    "Semantic Audit",
}


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
        output.append(SourceGroup(group_key, base_slug, title, bib_key, source_kind, file_tuple))
    return output


def source_payload(group: SourceGroup, max_chars: int) -> dict[str, Any]:
    entries = parse_bib_entries()
    entry = entries.get(group.bib_key or "")
    remaining = max_chars
    files = []
    for path in group.files:
        text = body_text(path)
        if group.segment:
            start = int(group.segment.get("start_char") or 0)
            end = int(group.segment.get("end_char") or len(text))
            text = text[start:end]
        excerpt = text[: max(0, remaining)]
        remaining -= len(excerpt)
        files.append(
            {
                "path": path.as_posix(),
                "metadata": frontmatter(path),
                "text": excerpt,
                "truncated": len(excerpt) < len(text),
            }
        )
        if remaining <= 0:
            break
    return {
        "group_id": group.group_id,
        "bib_key": group.bib_key,
        "title": group.title,
        "source_kind": group.source_kind,
        "apa_reference": apa_reference(entry),
        "apa_citation": apa_citation(entry),
        "segment": group.segment,
        "files": files,
    }


def system_prompt() -> str:
    return (
        "You are a careful literature-review analyst. Return only valid JSON matching the requested schema. "
        "Do not browse. Do not invent bibliographic facts. Every substantive claim about the source must be traceable "
        "to the supplied source text and should include a path#anchor trace when anchors are available."
    )


def user_prompt(group: SourceGroup, max_chars: int) -> str:
    sections = "\n".join(f"- {section}" for section in required_sections())
    custom_sections = [section for section in required_sections() if section not in BASE_RENDERED_SECTIONS]
    custom_section_text = "\n".join(f"- {section}" for section in custom_sections) or "- none"
    config_view = {
        "project": PROJECT_CONFIG.get("project", {}),
        "synthesis": {
            key: value
            for key, value in PROJECT_CONFIG.get("synthesis", {}).items()
            if key not in {"source_llm"}
        },
        "retrieval": {
            key: value
            for key, value in PROJECT_CONFIG.get("retrieval", {}).items()
            if key in {"core_terms", "modifier_terms", "exclusion_terms"}
        },
    }
    payload = source_payload(group, max_chars)
    min_notes = source_llm_config().get("min_evidence_notes", 4)
    return f"""Analyze this source or source segment for a reusable literature-review workflow.

Use the project configuration as the research lens, but infer categories from the source. Do not force fixed categories.
For example, suggest source-type categories, thematic categories, methodological categories, or measurement categories only when the source warrants them.

Required Markdown-equivalent sections to cover in JSON:
{sections}

Requirements:
- Produce at least {min_notes} evidence_notes when the source contains enough usable content.
- Each evidence note must include claim, evidence, citation, trace, and confidence.
- Trace values must use the provided machine-readable file path and an anchor if the relevant text includes one.
- If this is a long-source segment, scope conclusions to the segment and say what remains uncertain.
- Include a semantic_audit that names extraction limits and possible misreadings.
- Put configured sections that are not represented by the base JSON fields into custom_sections. Required custom section headings for this project:
{custom_section_text}
- Keep language concise but substantive.

Project configuration:
```json
{json.dumps(config_view, ensure_ascii=False, indent=2)}
```

Source payload:
```json
{json.dumps(payload, ensure_ascii=False, indent=2)}
```
"""


def configured_runtime(config: dict[str, Any]) -> dict[str, Any]:
    provider = source_llm_config().get("provider", "openrouter")
    rpm = source_llm_config().get("requests_per_minute")
    runtime = json.loads(json.dumps(config))
    if rpm:
        try:
            runtime.setdefault("apis", {}).setdefault(provider, {})["min_interval_seconds"] = max(0.0, 60.0 / float(rpm))
        except (TypeError, ValueError):
            pass
    return runtime


def response_format(output_mode: str) -> dict[str, Any] | None:
    if output_mode == "json_schema":
        return openrouter_response_format()
    if output_mode == "json_object":
        return {"type": "json_object"}
    return None


def parse_json_content(content: str) -> dict[str, Any]:
    content = content.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", content, re.S)
    if fence:
        content = fence.group(1)
    return json.loads(content)


def request_openrouter_compatible_json(
    base_url: str,
    *,
    provider: str,
    config: dict[str, Any],
    api_key: str,
    headers: dict[str, str],
    body: dict[str, Any],
    timeout: int = 180,
) -> dict[str, Any]:
    """Request an OpenAI-compatible chat completion with local cache and throttling."""
    try:
        import httpx
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError(
            "Missing Python dependencies for direct LLM synthesis. Install them with: "
            "pip install openai httpx"
        ) from exc

    endpoint = f"{base_url.rstrip('/')}/chat/completions"
    request_payload = {
        "method": "POST",
        "url": endpoint,
        "body": body,
    }
    key = cache_key(request_payload)
    use_cache = cache_enabled(config, provider)
    if use_cache:
        cached = read_cached_json(provider, key)
        if isinstance(cached, dict):
            return cached

    retries = max(1, retries_for(config, provider))
    min_interval = min_interval_for(config, provider)
    provider_cfg = config.get("apis", {}).get(provider, {}) if isinstance(config.get("apis", {}), dict) else {}
    verify_ssl = bool(provider_cfg.get("verify_ssl", False))
    extra_headers = {
        key: value
        for key, value in headers.items()
        if key.lower() not in {"authorization", "content-type"} and value
    }
    last_error: Exception | None = None
    for attempt in range(retries):
        throttle(provider, min_interval)
        try:
            with httpx.Client(verify=verify_ssl, timeout=timeout) as http_client:
                client = OpenAI(
                    api_key=api_key,
                    base_url=base_url.rstrip("/"),
                    default_headers=extra_headers,
                    http_client=http_client,
                )
                response = client.chat.completions.create(**body)
                data = response.model_dump(mode="json")
                if use_cache:
                    write_cached_json(provider, key, data)
                return data
        except Exception as exc:  # noqa: BLE001 - SDK wraps provider/rate errors heterogeneously.
            last_error = exc
            if attempt >= retries - 1:
                break
            time.sleep(float(2**attempt))
    raise RuntimeError(f"Failed OpenRouter-compatible request after {retries} attempts: {last_error}")


def call_openrouter(group: SourceGroup, output_json: Path, max_chars: int, dry_run: bool) -> dict[str, Any]:
    cfg = source_llm_config()
    provider = cfg.get("provider", "openrouter")
    api_cfg = PROJECT_CONFIG.get("apis", {}).get(provider, {})
    api_key_env = api_cfg.get("api_key_env", "OPENROUTER_API_KEY")
    if dry_run:
        return {
            "source_group_id": group.group_id,
            "title": group.title,
            "dry_run": True,
            "output_json": output_json.as_posix(),
            "chars": sum(len(body_text(path)) for path in group.files),
            "segment": group.segment,
        }
    api_key = os.environ.get(api_key_env)
    if not api_key:
        raise RuntimeError(f"Missing {api_key_env}")
    base_url = api_cfg.get("base_url", "https://openrouter.ai/api/v1").rstrip("/")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": os.environ.get("OPENROUTER_HTTP_REFERER", "https://github.com/literature-review-skills"),
        "X-Title": os.environ.get("OPENROUTER_APP_TITLE", "literature-review-skills"),
    }
    body: dict[str, Any] = {
        "model": cfg.get("model", "google/gemini-3.5-flash"),
        "messages": [
            {"role": "system", "content": system_prompt()},
            {"role": "user", "content": user_prompt(group, max_chars)},
        ],
        "temperature": cfg.get("temperature", 0),
        "max_tokens": cfg.get("max_output_tokens", 6000),
    }
    fmt = response_format(str(cfg.get("output_mode", "json_schema")))
    if fmt:
        body["response_format"] = fmt
    data = request_openrouter_compatible_json(
        base_url,
        provider=provider,
        config=configured_runtime(PROJECT_CONFIG),
        api_key=api_key,
        headers=headers,
        body=body,
        timeout=180,
    )
    content = data["choices"][0]["message"]["content"]
    parsed = parse_json_content(content)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")
    return parsed


def run_one(group: SourceGroup, json_dir: Path, markdown_dir: Path, max_chars: int, dry_run: bool) -> dict[str, Any]:
    output_json = json_dir / f"{group.slug}.json"
    if output_json.exists() and not dry_run:
        markdown_path = render_file(output_json, markdown_dir)
        return {"group_id": group.group_id, "json": output_json.as_posix(), "markdown": markdown_path.as_posix(), "cached_file": True}
    result = call_openrouter(group, output_json, max_chars, dry_run)
    if dry_run:
        return result
    markdown_path = render_file(output_json, markdown_dir)
    return {"group_id": group.group_id, "json": output_json.as_posix(), "markdown": markdown_path.as_posix(), "cached_file": False}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--machine-dir", action="append", type=Path)
    parser.add_argument("--run-name")
    parser.add_argument("--limit", type=int, help="Maximum number of groups to process")
    parser.add_argument("--workers", type=int)
    parser.add_argument("--dry-run", action="store_true", help="Plan tasks without calling OpenRouter")
    args = parser.parse_args()

    load_env()
    cfg = source_llm_config()
    max_chars = int(cfg.get("max_input_chars", 120000))
    machine_dirs = args.machine_dir or [Path(PROJECT_CONFIG["paths"]["machine_dir"])]
    groups = group_sources(machine_dirs, bool(cfg.get("split_long_sources", True)), max_chars)
    if args.limit:
        groups = groups[: args.limit]

    stamp = args.run_name or dt.datetime.now().strftime("%Y-%m-%d-%H%M%S-openrouter")
    run_root = DEFAULT_RUN_ROOT / stamp
    json_dir = run_root / "source-json"
    markdown_dir = run_root / "source-syntheses"
    manifest_path = run_root / "manifest.json"
    workers = max(1, int(args.workers or cfg.get("workers", 4)))

    run_root.mkdir(parents=True, exist_ok=True)
    if args.dry_run:
        results = [run_one(group, json_dir, markdown_dir, max_chars, True) for group in groups]
    else:
        with futures.ThreadPoolExecutor(max_workers=workers) as executor:
            submitted = {
                executor.submit(run_one, group, json_dir, markdown_dir, max_chars, False): group
                for group in groups
            }
            results = []
            for job in futures.as_completed(submitted):
                group = submitted[job]
                try:
                    results.append(job.result())
                except Exception as exc:  # noqa: BLE001 - keep long runs moving and report failed groups.
                    results.append(
                        {
                            "group_id": group.group_id,
                            "title": group.title,
                            "error": type(exc).__name__,
                            "message": str(exc),
                        }
                    )
            results.sort(key=lambda row: row.get("group_id", ""))
    manifest = {
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "mode": "direct_llm",
        "provider": cfg.get("provider", "openrouter"),
        "model": cfg.get("model"),
        "dry_run": args.dry_run,
        "machine_dirs": [path.as_posix() for path in machine_dirs],
        "failures": sum(1 for row in results if row.get("error")),
        "results": results,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
