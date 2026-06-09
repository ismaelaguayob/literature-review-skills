#!/usr/bin/env python3
"""Search OpenAlex works and print normalized JSON."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = Path.cwd()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from shared.project_config import load_config  # noqa: E402

API_URL = "https://api.openalex.org/works"
PROJECT_CONFIG = load_config()
SELECT = ",".join(
    [
        "id",
        "doi",
        "title",
        "display_name",
        "publication_year",
        "authorships",
        "primary_location",
        "type",
        "cited_by_count",
        "abstract_inverted_index",
        "open_access",
    ]
)


def load_env(path: str = ".env") -> None:
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def request_json(url: str, headers: dict[str, str], retries: int = 4) -> dict:
    for attempt in range(retries):
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code in {429, 500, 502, 503, 504} and attempt < retries - 1:
                time.sleep(2**attempt)
                continue
            raise


def invert_abstract(index: dict | None) -> str | None:
    if not index:
        return None
    words: list[tuple[int, str]] = []
    for word, positions in index.items():
        for pos in positions:
            words.append((pos, word))
    return " ".join(word for _, word in sorted(words))


def normalize(item: dict, query: str) -> dict:
    authors = []
    for authorship in item.get("authorships", []):
        author = authorship.get("author") or {}
        if author.get("display_name"):
            authors.append(author["display_name"])
    location = item.get("primary_location") or {}
    source = location.get("source") or {}
    oa = item.get("open_access") or {}
    return {
        "source": "openalex",
        "query": query,
        "id": item.get("id"),
        "title": item.get("title") or item.get("display_name"),
        "authors": authors,
        "year": item.get("publication_year"),
        "doi": (item.get("doi") or "").replace("https://doi.org/", "") or None,
        "url": item.get("id"),
        "pdf_url": location.get("pdf_url") or oa.get("oa_url"),
        "abstract": invert_abstract(item.get("abstract_inverted_index")),
        "venue": source.get("display_name"),
        "type": item.get("type"),
        "citation_count": item.get("cited_by_count"),
        "is_open_access": oa.get("is_oa"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", required=True)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--from-year", type=int)
    parser.add_argument("--to-year", type=int)
    parser.add_argument("--type", dest="work_type", help="OpenAlex work type, e.g. article|book")
    parser.add_argument("--open-access", action="store_true")
    args = parser.parse_args()

    load_env()
    params = {
        "search": args.query,
        "per-page": str(max(1, min(args.limit, 200))),
        "select": SELECT,
    }
    api_key = os.environ.get("OPENALEX_API_KEY")
    if api_key:
        params["api_key"] = api_key
    filters = []
    if args.from_year and args.to_year:
        filters.append(f"publication_year:{args.from_year}-{args.to_year}")
    elif args.from_year:
        filters.append(f"publication_year:>{args.from_year - 1}")
    elif args.to_year:
        filters.append(f"publication_year:<{args.to_year + 1}")
    if args.work_type:
        filters.append(f"type:{args.work_type}")
    if args.open_access:
        filters.append("is_oa:true")
    if filters:
        params["filter"] = ",".join(filters)

    headers = {}
    user_agent = os.environ.get("RESEARCH_USER_AGENT", PROJECT_CONFIG.get("retrieval", {}).get("user_agent", "literature-review/0.1"))
    if user_agent:
        headers["User-Agent"] = user_agent

    url = API_URL + "?" + urllib.parse.urlencode(params)
    data = request_json(url, headers)
    results = [normalize(item, args.query) for item in data.get("results", [])]
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
