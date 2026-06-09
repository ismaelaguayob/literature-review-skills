#!/usr/bin/env python3
"""Search Crossref works and print normalized JSON."""

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

API_URL = "https://api.crossref.org/works"
PROJECT_CONFIG = load_config()


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


def first(value):
    if isinstance(value, list) and value:
        return value[0]
    return value


def date_parts(item: dict) -> str | None:
    parts = (((item.get("issued") or {}).get("date-parts") or [[]])[0])
    if not parts:
        return None
    return "-".join(str(part) for part in parts)


def normalize(item: dict, query: str) -> dict:
    authors = []
    for author in item.get("author", []) or []:
        name = " ".join(part for part in [author.get("given"), author.get("family")] if part)
        if name:
            authors.append(name)
    links = item.get("link") or []
    pdf_url = None
    for link in links:
        if "pdf" in (link.get("content-type") or "").lower():
            pdf_url = link.get("URL")
            break
    return {
        "source": "crossref",
        "query": query,
        "id": item.get("DOI"),
        "title": first(item.get("title")),
        "authors": authors,
        "year": (date_parts(item) or "")[:4] or None,
        "doi": item.get("DOI"),
        "url": item.get("URL"),
        "pdf_url": pdf_url,
        "abstract": item.get("abstract"),
        "venue": first(item.get("container-title")),
        "publisher": item.get("publisher"),
        "type": item.get("type"),
        "citation_count": item.get("is-referenced-by-count"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", required=True)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--from-year", type=int)
    parser.add_argument("--to-year", type=int)
    parser.add_argument("--type", dest="work_type")
    parser.add_argument("--has-abstract", action="store_true")
    args = parser.parse_args()

    load_env()
    params = {
        "query.bibliographic": args.query,
        "rows": str(max(1, min(args.limit, 100))),
    }
    mailto = os.environ.get("CROSSREF_MAILTO")
    if mailto:
        params["mailto"] = mailto

    filters = []
    if args.from_year:
        filters.append(f"from-pub-date:{args.from_year}")
    if args.to_year:
        filters.append(f"until-pub-date:{args.to_year}")
    if args.work_type:
        filters.append(f"type:{args.work_type}")
    if args.has_abstract:
        filters.append("has-abstract:1")
    if filters:
        params["filter"] = ",".join(filters)

    headers = {
        "User-Agent": os.environ.get("RESEARCH_USER_AGENT", PROJECT_CONFIG.get("retrieval", {}).get("user_agent", "literature-review/0.1"))
    }
    plus_key = os.environ.get("CROSSREF_API_KEY")
    if plus_key:
        headers["Crossref-Plus-API-Token"] = f"Bearer {plus_key}"

    url = API_URL + "?" + urllib.parse.urlencode(params)
    data = request_json(url, headers)
    items = data.get("message", {}).get("items", [])
    results = [normalize(item, args.query) for item in items]
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
