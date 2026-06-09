#!/usr/bin/env python3
"""Search Semantic Scholar and print normalized JSON."""

from __future__ import annotations

import argparse
import fcntl
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

API_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
PROJECT_CONFIG = load_config()
SEMANTIC_CONFIG = PROJECT_CONFIG.get("apis", {}).get("semantic_scholar", {})
SEMANTIC_MIN_INTERVAL_SECONDS = float(SEMANTIC_CONFIG.get("min_interval_seconds", 1.0))
PROJECT_SLUG = PROJECT_CONFIG.get("project", {}).get("slug", "literature-review")
SEMANTIC_THROTTLE_FILE = Path(
    os.environ.get("SEMANTIC_THROTTLE_FILE", f"/tmp/{PROJECT_SLUG}_semantic_scholar_last_request")
)
SEMANTIC_THROTTLE_LOCK = Path(
    os.environ.get("SEMANTIC_THROTTLE_LOCK", f"/tmp/{PROJECT_SLUG}_semantic_scholar_last_request.lock")
)
FIELDS = ",".join(
    [
        "title",
        "authors",
        "year",
        "abstract",
        "url",
        "externalIds",
        "citationCount",
        "referenceCount",
        "isOpenAccess",
        "openAccessPdf",
        "publicationTypes",
        "venue",
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


def throttle_semantic_scholar() -> None:
    # Semantic Scholar API keys are commonly rate-limited around one request/sec.
    # This shared timestamp keeps separate discovery subprocesses from tripping 429s.
    with SEMANTIC_THROTTLE_LOCK.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            last_request = float(SEMANTIC_THROTTLE_FILE.read_text(encoding="utf-8").strip())
        except (FileNotFoundError, ValueError, OSError):
            last_request = 0.0

        wait_seconds = SEMANTIC_MIN_INTERVAL_SECONDS - (time.time() - last_request)
        if wait_seconds > 0:
            time.sleep(wait_seconds)
        try:
            SEMANTIC_THROTTLE_FILE.write_text(str(time.time()), encoding="utf-8")
        except OSError:
            pass


def retry_delay(exc: urllib.error.HTTPError, attempt: int) -> float:
    retry_after = exc.headers.get("Retry-After")
    if retry_after:
        try:
            return max(float(retry_after), SEMANTIC_MIN_INTERVAL_SECONDS)
        except ValueError:
            pass
    return max(SEMANTIC_MIN_INTERVAL_SECONDS, 2**attempt)


def request_json(url: str, headers: dict[str, str], retries: int = 4) -> dict:
    for attempt in range(retries):
        throttle_semantic_scholar()
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code in {429, 500, 502, 503, 504} and attempt < retries - 1:
                time.sleep(retry_delay(exc, attempt))
                continue
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Semantic Scholar HTTP {exc.code}: {body[:500]}") from exc


def normalize(item: dict, query: str) -> dict:
    external = item.get("externalIds") or {}
    authors = [a.get("name") for a in item.get("authors", []) if a.get("name")]
    pdf = item.get("openAccessPdf") or {}
    return {
        "source": "semantic-scholar",
        "query": query,
        "id": item.get("paperId"),
        "title": item.get("title"),
        "authors": authors,
        "year": item.get("year"),
        "doi": external.get("DOI"),
        "url": item.get("url"),
        "pdf_url": pdf.get("url"),
        "abstract": item.get("abstract"),
        "venue": item.get("venue"),
        "type": ", ".join(item.get("publicationTypes") or []),
        "citation_count": item.get("citationCount"),
        "reference_count": item.get("referenceCount"),
        "is_open_access": item.get("isOpenAccess"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", required=True)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--year", help="Year or range, e.g. 2019-2026")
    parser.add_argument("--open-access-pdf", action="store_true")
    parser.add_argument("--min-citations", type=int)
    args = parser.parse_args()

    load_env()
    key = os.environ.get("SEMANTIC_API_KEY") or os.environ.get("SEMANTIC_SCHOLAR_API_KEY")
    headers = {
        "User-Agent": os.environ.get("RESEARCH_USER_AGENT", PROJECT_CONFIG.get("retrieval", {}).get("user_agent", "literature-review/0.1"))
    }
    if key:
        headers["x-api-key"] = key

    params = {
        "query": args.query.replace("-", " "),
        "limit": str(max(1, min(args.limit, 100))),
        "fields": FIELDS,
    }
    if args.year:
        params["year"] = args.year
    if args.open_access_pdf:
        params["openAccessPdf"] = ""
    if args.min_citations is not None:
        params["minCitationCount"] = str(args.min_citations)

    url = API_URL + "?" + urllib.parse.urlencode(params)
    try:
        retries = int(SEMANTIC_CONFIG.get("retries", 4))
        data = request_json(url, headers, retries=retries)
    except Exception as exc:
        print(
            json.dumps(
                [{"source": "semantic-scholar", "query": args.query, "title": None, "error": str(exc)}],
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    results = [normalize(item, args.query) for item in data.get("data", [])]
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
