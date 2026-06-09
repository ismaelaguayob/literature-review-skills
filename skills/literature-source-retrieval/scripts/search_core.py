#!/usr/bin/env python3
"""Search CORE works and print normalized JSON."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path.cwd()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from shared.api_utils import load_env, request_json  # noqa: E402
from shared.project_config import load_config  # noqa: E402


API_URL = "https://api.core.ac.uk/v3/search/works"
PROJECT_CONFIG = load_config()


def core_query(query: str, from_year: int | None, to_year: int | None) -> str:
    filters = []
    if from_year:
        filters.append(f"yearPublished>={from_year}")
    if to_year:
        filters.append(f"yearPublished<={to_year}")
    if not filters:
        return query
    return f"({query}) AND " + " AND ".join(filters)


def author_names(item: dict[str, Any]) -> list[str]:
    names = []
    for author in item.get("authors") or []:
        if isinstance(author, dict) and author.get("name"):
            names.append(str(author["name"]))
        elif isinstance(author, str):
            names.append(author)
    return names


def identifier_url(item: dict[str, Any]) -> str | None:
    for identifier in item.get("identifiers") or []:
        value = identifier.get("identifier") if isinstance(identifier, dict) else str(identifier)
        if value and value.startswith(("http://", "https://")):
            return value
    source_urls = item.get("sourceFulltextUrls") or []
    return item.get("downloadUrl") or (source_urls[0] if source_urls else None)


def normalize(item: dict[str, Any], query: str) -> dict[str, Any]:
    doi = item.get("doi")
    url = identifier_url(item)
    full_text = item.get("fullText")
    journals = item.get("journals")
    venue = journals[0] if isinstance(journals, list) and journals else journals
    if isinstance(venue, dict):
        venue = venue.get("title") or ", ".join(str(value) for value in venue.values() if value)
    return {
        "source": "core",
        "query": query,
        "id": item.get("id"),
        "title": item.get("title"),
        "authors": author_names(item),
        "year": item.get("yearPublished"),
        "doi": doi,
        "url": url or (f"https://doi.org/{doi}" if doi else None),
        "pdf_url": item.get("downloadUrl"),
        "abstract": item.get("abstract"),
        "venue": venue,
        "publisher": item.get("publisher"),
        "type": item.get("documentType") or item.get("type"),
        "citation_count": item.get("citationCount"),
        "is_open_access": True,
        "source_quality_signals": {
            "open_access_full_text": bool(full_text or item.get("downloadUrl")),
            "has_doi": bool(doi),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", required=True)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--from-year", type=int)
    parser.add_argument("--to-year", type=int)
    parser.add_argument("--offset", type=int, default=0)
    args = parser.parse_args()

    load_env()
    headers = {
        "Accept": "application/json",
        "User-Agent": os.environ.get("RESEARCH_USER_AGENT", PROJECT_CONFIG.get("retrieval", {}).get("user_agent", "literature-review/0.1")),
    }
    api_key = os.environ.get(PROJECT_CONFIG.get("apis", {}).get("core", {}).get("api_key_env", "CORE_API_KEY"))
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    params = {
        "q": core_query(args.query, args.from_year, args.to_year),
        "limit": str(max(1, min(args.limit, 100))),
        "offset": str(max(0, args.offset)),
    }
    try:
        data = request_json(API_URL, provider="core", config=PROJECT_CONFIG, params=params, headers=headers)
        rows = data.get("results") or data.get("data") or [] if isinstance(data, dict) else []
        results = [normalize(item, args.query) for item in rows if isinstance(item, dict) and item.get("title")]
    except Exception as exc:
        results = [{"source": "core", "query": args.query, "title": None, "error": str(exc)}]
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
