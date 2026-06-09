#!/usr/bin/env python3
"""Trace citations or references for a seed paper.

Providers:
- Semantic Scholar: citations and references.
- OpenAlex: citations and references.
- Crossref: references from deposited metadata; citation lists are not available
  through the standard Crossref REST API.
- CORE: references when parsed full-text metadata exposes them; citation lists are
  not available as a reliable citing-work endpoint.
- Springer Nature: metadata/full-text lookup for the seed; citation/reference
  graphs are not available through the configured APIs.
"""

from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = Path.cwd()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from shared.api_utils import request_json as cached_request_json  # noqa: E402
from shared.project_config import load_config, path_from_config  # noqa: E402

SEARCH_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
PAPER_URL = "https://api.semanticscholar.org/graph/v1/paper"
OPENALEX_WORKS_URL = "https://api.openalex.org/works"
CROSSREF_WORKS_URL = "https://api.crossref.org/works"
CORE_SEARCH_WORKS_URL = "https://api.core.ac.uk/v3/search/works"
CORE_WORKS_URL = "https://api.core.ac.uk/v3/works"
SPRINGER_METADATA_URL = "https://api.springernature.com/meta/v2/json"
SPRINGER_OPENACCESS_URL = "https://api.springernature.com/openaccess/json"
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
OPENALEX_SELECT = ",".join(
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
        "referenced_works_count",
        "referenced_works",
        "cited_by_api_url",
        "abstract_inverted_index",
        "open_access",
    ]
)
PROJECT_CONFIG = load_config()
DEFAULT_OUTPUT_DIR = path_from_config(PROJECT_CONFIG, "retrieval_intermediate_dir")
SEMANTIC_CONFIG = PROJECT_CONFIG.get("apis", {}).get("semantic_scholar", {})
SEMANTIC_MIN_INTERVAL_SECONDS = float(SEMANTIC_CONFIG.get("min_interval_seconds", 1.0))
PROJECT_SLUG = PROJECT_CONFIG.get("project", {}).get("slug", "literature-review")
SEMANTIC_THROTTLE_FILE = Path(
    os.environ.get("SEMANTIC_THROTTLE_FILE", f"/tmp/{PROJECT_SLUG}_semantic_scholar_last_request")
)
SEMANTIC_THROTTLE_LOCK = Path(
    os.environ.get("SEMANTIC_THROTTLE_LOCK", f"/tmp/{PROJECT_SLUG}_semantic_scholar_last_request.lock")
)


def default_user_agent() -> str:
    return PROJECT_CONFIG.get("retrieval", {}).get("user_agent", "literature-review/0.1")


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


def semantic_headers() -> dict[str, str]:
    load_env()
    output = {
        "User-Agent": os.environ.get("RESEARCH_USER_AGENT", default_user_agent())
    }
    key = os.environ.get("SEMANTIC_API_KEY") or os.environ.get("SEMANTIC_SCHOLAR_API_KEY")
    if key:
        output["x-api-key"] = key
    return output


def generic_headers() -> dict[str, str]:
    load_env()
    return {"User-Agent": os.environ.get("RESEARCH_USER_AGENT", default_user_agent())}


def throttle_semantic_scholar() -> None:
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


def semantic_retry_delay(exc: urllib.error.HTTPError, attempt: int) -> float:
    retry_after = exc.headers.get("Retry-After")
    if retry_after:
        try:
            return max(float(retry_after), SEMANTIC_MIN_INTERVAL_SECONDS)
        except ValueError:
            pass
    return max(SEMANTIC_MIN_INTERVAL_SECONDS, 2**attempt)


def request_json(url: str, headers: dict[str, str] | None = None, retries: int = 4) -> dict:
    for attempt in range(retries):
        if "semanticscholar.org" in url:
            throttle_semantic_scholar()
        req = urllib.request.Request(url, headers=headers or generic_headers())
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code in {429, 500, 502, 503, 504} and attempt < retries - 1:
                if "semanticscholar.org" in url:
                    time.sleep(semantic_retry_delay(exc, attempt))
                else:
                    time.sleep(2**attempt)
                continue
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {exc.code}: {body[:500]}") from exc


def find_paper_id(query: str) -> str | None:
    params = {"query": query.replace("-", " "), "limit": "1", "fields": "title,year,externalIds"}
    data = request_json(SEARCH_URL + "?" + urllib.parse.urlencode(params), semantic_headers())
    rows = data.get("data", [])
    return rows[0].get("paperId") if rows else None


def normalize_semantic(item: dict, seed: str, relation: str) -> dict:
    paper = item.get("citingPaper") or item.get("citedPaper") or item.get("paper") or item
    external = paper.get("externalIds") or {}
    authors = [a.get("name") for a in paper.get("authors", []) if a.get("name")]
    pdf = paper.get("openAccessPdf") or {}
    return {
        "source": "semantic-scholar",
        "relation": relation,
        "seed": seed,
        "id": paper.get("paperId"),
        "title": paper.get("title"),
        "authors": authors,
        "year": paper.get("year"),
        "doi": external.get("DOI"),
        "url": paper.get("url"),
        "pdf_url": pdf.get("url"),
        "abstract": paper.get("abstract"),
        "venue": paper.get("venue"),
        "type": ", ".join(paper.get("publicationTypes") or []),
        "citation_count": paper.get("citationCount"),
        "reference_count": paper.get("referenceCount"),
        "is_open_access": paper.get("isOpenAccess"),
    }


def clean_doi(value: str | None) -> str | None:
    if not value:
        return None
    return re.sub(r"^https?://(dx\.)?doi\.org/", "", value.strip(), flags=re.I)


def doi_url(value: str) -> str:
    value = clean_doi(value) or value
    return f"https://doi.org/{value}"


def invert_abstract(index: dict | None) -> str | None:
    if not index:
        return None
    words: list[tuple[int, str]] = []
    for word, positions in index.items():
        for pos in positions:
            words.append((pos, word))
    return " ".join(word for _, word in sorted(words))


def normalize_openalex(item: dict, seed: str, relation: str) -> dict:
    authors = []
    for authorship in item.get("authorships", []) or []:
        author = authorship.get("author") or {}
        if author.get("display_name"):
            authors.append(author["display_name"])
    location = item.get("primary_location") or {}
    source = location.get("source") or {}
    oa = item.get("open_access") or {}
    return {
        "source": "openalex",
        "relation": relation,
        "seed": seed,
        "id": item.get("id"),
        "title": item.get("title") or item.get("display_name"),
        "authors": authors,
        "year": item.get("publication_year"),
        "doi": clean_doi(item.get("doi")),
        "url": item.get("id"),
        "pdf_url": location.get("pdf_url") or oa.get("oa_url"),
        "abstract": invert_abstract(item.get("abstract_inverted_index")),
        "venue": source.get("display_name"),
        "type": item.get("type"),
        "citation_count": item.get("cited_by_count"),
        "reference_count": item.get("referenced_works_count"),
        "is_open_access": oa.get("is_oa"),
    }


def first(value):
    if isinstance(value, list) and value:
        return value[0]
    return value


def date_parts(item: dict) -> str | None:
    parts = (((item.get("issued") or {}).get("date-parts") or [[]])[0])
    if not parts:
        return None
    return "-".join(str(part) for part in parts)


def normalize_crossref_work(item: dict, seed: str, relation: str) -> dict:
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
        "relation": relation,
        "seed": seed,
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
        "reference_count": len(item.get("reference") or []),
    }


def normalize_crossref_reference(item: dict, seed: str) -> dict:
    authors = []
    if item.get("author"):
        authors = [str(item.get("author"))]
    return {
        "source": "crossref",
        "relation": "references",
        "seed": seed,
        "id": item.get("DOI") or item.get("doi") or item.get("key"),
        "title": item.get("article-title") or item.get("volume-title") or item.get("unstructured"),
        "authors": authors,
        "year": item.get("year"),
        "doi": item.get("DOI") or item.get("doi"),
        "url": doi_url(item["DOI"]) if item.get("DOI") else None,
        "pdf_url": None,
        "abstract": item.get("unstructured"),
        "venue": item.get("journal-title") or item.get("series-title"),
        "type": "crossref-reference",
        "citation_count": None,
        "reference_count": None,
        "is_open_access": None,
    }


def core_headers() -> dict[str, str]:
    output = generic_headers()
    output["Accept"] = "application/json"
    api_key = os.environ.get(PROJECT_CONFIG.get("apis", {}).get("core", {}).get("api_key_env", "CORE_API_KEY"))
    if api_key:
        output["Authorization"] = f"Bearer {api_key}"
    return output


def core_author_names(item: dict) -> list[str]:
    authors = []
    for author in item.get("authors") or []:
        if isinstance(author, dict) and author.get("name"):
            authors.append(str(author["name"]))
        elif isinstance(author, str):
            authors.append(author)
    return authors


def core_venue(item: dict) -> str | None:
    journals = item.get("journals")
    venue = journals[0] if isinstance(journals, list) and journals else journals
    if isinstance(venue, dict):
        return venue.get("title") or ", ".join(str(value) for value in venue.values() if value)
    return venue


def core_url(item: dict) -> str | None:
    for identifier in item.get("identifiers") or []:
        value = identifier.get("identifier") if isinstance(identifier, dict) else str(identifier)
        if value and value.startswith(("http://", "https://")):
            return value
    source_urls = item.get("sourceFulltextUrls") or []
    return item.get("downloadUrl") or (source_urls[0] if source_urls else None)


def normalize_core_work(item: dict, seed: str, relation: str) -> dict:
    doi = item.get("doi")
    return {
        "source": "core",
        "relation": relation,
        "seed": seed,
        "id": item.get("id"),
        "title": item.get("title"),
        "authors": core_author_names(item),
        "year": item.get("yearPublished"),
        "doi": doi,
        "url": core_url(item) or (doi_url(doi) if doi else None),
        "pdf_url": item.get("downloadUrl"),
        "abstract": item.get("abstract"),
        "venue": core_venue(item),
        "publisher": item.get("publisher"),
        "type": item.get("documentType") or item.get("type"),
        "citation_count": item.get("citationCount"),
        "reference_count": len(item.get("references") or []) if item.get("references") is not None else None,
        "is_open_access": True,
    }


def normalize_core_reference(item: dict, seed: str) -> dict:
    return {
        "source": "core",
        "relation": "references",
        "seed": seed,
        "id": item.get("id") or item.get("coreId") or item.get("doi"),
        "title": item.get("title") or item.get("raw"),
        "authors": item.get("authors") or [],
        "year": item.get("date") or item.get("year"),
        "doi": item.get("doi"),
        "url": doi_url(item["doi"]) if item.get("doi") else None,
        "pdf_url": None,
        "abstract": item.get("raw"),
        "venue": None,
        "type": "core-reference",
        "citation_count": None,
        "reference_count": None,
        "is_open_access": None,
    }


def find_core_work(query: str | None = None, doi: str | None = None) -> dict | None:
    load_env()
    q = f'doi:"{clean_doi(doi) or doi}"' if doi else (query or "")
    params = {"q": q, "limit": "1", "offset": "0"}
    data = cached_request_json(CORE_SEARCH_WORKS_URL, provider="core", config=PROJECT_CONFIG, params=params, headers=core_headers())
    rows = data.get("results") or data.get("data") or [] if isinstance(data, dict) else []
    if not rows:
        return None
    row = rows[0]
    work_id = row.get("id")
    if not work_id:
        return row
    try:
        detail = cached_request_json(f"{CORE_WORKS_URL}/{urllib.parse.quote(str(work_id), safe='')}", provider="core", config=PROJECT_CONFIG, headers=core_headers())
        return detail if isinstance(detail, dict) else row
    except Exception:
        return row


def trace_core(seed: str, relation: str, limit: int, doi: str | None = None) -> list[dict]:
    work = find_core_work(query=None if doi else seed, doi=doi)
    if not work:
        return []
    if relation == "citations":
        return [
            {
                **normalize_core_work(work, seed, relation),
                "error": "CORE exposes citation counts and parsed references, but not a reliable citing-work list through this workflow.",
            }
        ]
    references = work.get("references") or []
    if references:
        return [normalize_core_reference(item, seed) for item in references[:limit] if isinstance(item, dict)]
    return [
        {
            **normalize_core_work(work, seed, relation),
            "error": "No parsed references found for this CORE record.",
        }
    ]


def springer_headers() -> dict[str, str]:
    output = generic_headers()
    output["Accept"] = "application/json"
    return output


def springer_api_key(source: str) -> tuple[str, str | None]:
    springer_config = PROJECT_CONFIG.get("apis", {}).get("springer", {})
    if source == "springer-openaccess":
        env_name = springer_config.get("openaccess_api_key_env") or springer_config.get("api_key_env") or "SPRINGER_OPENACCESS_API_KEY"
    else:
        env_name = springer_config.get("metadata_api_key_env") or springer_config.get("api_key_env") or "SPRINGER_METADATA_API_KEY"
    return env_name, os.environ.get(env_name)


def springer_auth_params(source: str) -> dict[str, str] | dict[str, str | None]:
    env_name, api_key = springer_api_key(source)
    if not api_key:
        raise RuntimeError(f"missing {env_name}")
    return {"api_key": api_key}


def springer_authors(record: dict) -> list[str]:
    authors = []
    for creator in record.get("creators") or []:
        if isinstance(creator, dict) and creator.get("creator"):
            authors.append(str(creator["creator"]))
        elif isinstance(creator, str):
            authors.append(creator)
    return authors


def springer_urls(record: dict) -> tuple[str | None, str | None]:
    url = None
    pdf_url = None
    for entry in record.get("url") or []:
        if not isinstance(entry, dict):
            continue
        value = entry.get("value")
        fmt = (entry.get("format") or "").lower()
        platform = (entry.get("platform") or "").lower()
        if value and not url:
            url = value
        if value and ("pdf" in fmt or "pdf" in platform):
            pdf_url = value
    return url, pdf_url


def normalize_springer_record(record: dict, seed: str, relation: str, source: str) -> dict:
    publication_date = record.get("publicationDate") or record.get("onlineDate") or record.get("printDate") or ""
    doi = record.get("doi")
    url, pdf_url = springer_urls(record)
    abstract = record.get("abstract")
    if isinstance(abstract, dict):
        abstract = " ".join(str(value) for value in abstract.values() if value)
    return {
        "source": source,
        "relation": relation,
        "seed": seed,
        "id": doi or record.get("identifier"),
        "title": record.get("title"),
        "authors": springer_authors(record),
        "year": publication_date[:4] or None,
        "doi": doi,
        "url": url or (doi_url(doi) if doi else None),
        "pdf_url": pdf_url,
        "abstract": abstract,
        "venue": record.get("publicationName"),
        "publisher": record.get("publisher"),
        "type": record.get("contentType") or record.get("genre"),
        "citation_count": None,
        "reference_count": len(record.get("references") or []) if record.get("references") is not None else None,
        "is_open_access": source == "springer-openaccess" or str(record.get("openaccess")).lower() == "true",
    }


def find_springer_record(seed: str, source: str, doi: str | None = None) -> dict | None:
    load_env()
    endpoint = SPRINGER_OPENACCESS_URL if source == "springer-openaccess" else SPRINGER_METADATA_URL
    q = f"doi:{clean_doi(doi) or doi}" if doi else seed
    params = {"q": q, "p": "1", "s": "1", **springer_auth_params(source)}
    data = cached_request_json(endpoint, provider="springer", config=PROJECT_CONFIG, params=params, headers=springer_headers())
    records = data.get("records", []) if isinstance(data, dict) else []
    return records[0] if records else None


def trace_springer(seed: str, relation: str, limit: int, source: str, doi: str | None = None) -> list[dict]:
    record = find_springer_record(seed, source, doi=doi)
    if not record:
        return []
    references = record.get("references") or []
    if relation == "references" and references:
        rows = []
        for item in references[:limit]:
            rows.append(
                {
                    "source": source,
                    "relation": "references",
                    "seed": seed,
                    "id": item.get("doi") if isinstance(item, dict) else None,
                    "title": item.get("title") if isinstance(item, dict) else str(item),
                    "authors": item.get("authors", []) if isinstance(item, dict) else [],
                    "year": item.get("year") if isinstance(item, dict) else None,
                    "doi": item.get("doi") if isinstance(item, dict) else None,
                    "url": doi_url(item["doi"]) if isinstance(item, dict) and item.get("doi") else None,
                    "pdf_url": None,
                    "abstract": item.get("raw") if isinstance(item, dict) else str(item),
                    "venue": None,
                    "type": "springer-reference",
                    "citation_count": None,
                    "reference_count": None,
                    "is_open_access": None,
                }
            )
        return rows
    return [
        {
            **normalize_springer_record(record, seed, relation, source),
            "error": "Springer Metadata/OpenAccess APIs are useful for seed lookup and full-text availability, but do not expose a reliable citation/reference graph in this workflow.",
        }
    ]


def openalex_headers() -> dict[str, str]:
    return generic_headers()


def openalex_params(params: dict[str, str]) -> str:
    load_env()
    api_key = os.environ.get("OPENALEX_API_KEY")
    if api_key:
        params["api_key"] = api_key
    return urllib.parse.urlencode(params)


def find_openalex_work(query: str | None = None, doi: str | None = None) -> dict | None:
    if doi:
        filter_values = [doi_url(doi), clean_doi(doi) or doi]
        for value in filter_values:
            params = {
                "filter": f"doi:{value}",
                "per-page": "1",
                "select": OPENALEX_SELECT,
            }
            data = request_json(OPENALEX_WORKS_URL + "?" + openalex_params(params), openalex_headers())
            rows = data.get("results", [])
            if rows:
                return rows[0]
        params = {
            "search": clean_doi(doi) or doi,
            "per-page": "1",
            "select": OPENALEX_SELECT,
        }
    else:
        params = {
            "search": query or "",
            "per-page": "1",
            "select": OPENALEX_SELECT,
        }
    data = request_json(OPENALEX_WORKS_URL + "?" + openalex_params(params), openalex_headers())
    rows = data.get("results", [])
    return rows[0] if rows else None


def fetch_openalex_by_ids(ids: list[str], limit: int) -> list[dict]:
    ids = [item.rsplit("/", 1)[-1] for item in ids[:limit] if item]
    if not ids:
        return []
    params = {
        "filter": "openalex_id:" + "|".join(ids),
        "per-page": str(max(1, min(len(ids), 200))),
        "select": OPENALEX_SELECT,
    }
    data = request_json(OPENALEX_WORKS_URL + "?" + openalex_params(params), openalex_headers())
    return data.get("results", [])


def trace_openalex(seed: str, relation: str, limit: int, doi: str | None = None) -> list[dict]:
    work = find_openalex_work(query=None if doi else seed, doi=doi)
    if not work:
        return []
    if relation == "citations":
        openalex_id = (work.get("id") or "").rsplit("/", 1)[-1]
        if not openalex_id:
            return []
        params = {
            "filter": f"cites:{openalex_id}",
            "per-page": str(max(1, min(limit, 200))),
            "select": OPENALEX_SELECT,
        }
        data = request_json(OPENALEX_WORKS_URL + "?" + openalex_params(params), openalex_headers())
        return [normalize_openalex(item, seed, relation) for item in data.get("results", [])]

    referenced = work.get("referenced_works") or []
    refs = fetch_openalex_by_ids(referenced, limit)
    return [normalize_openalex(item, seed, relation) for item in refs]


def crossref_headers() -> dict[str, str]:
    output = generic_headers()
    plus_key = os.environ.get("CROSSREF_API_KEY")
    if plus_key:
        output["Crossref-Plus-API-Token"] = f"Bearer {plus_key}"
    return output


def find_crossref_work(query: str | None = None, doi: str | None = None) -> dict | None:
    load_env()
    if doi:
        url = f"{CROSSREF_WORKS_URL}/{urllib.parse.quote(clean_doi(doi) or doi, safe='')}"
        params = {}
    else:
        url = CROSSREF_WORKS_URL
        params = {"query.bibliographic": query or "", "rows": "1"}
    mailto = os.environ.get("CROSSREF_MAILTO")
    if mailto:
        params["mailto"] = mailto
    if params:
        url += "?" + urllib.parse.urlencode(params)
    data = request_json(url, crossref_headers())
    message = data.get("message", {})
    if doi:
        return message
    items = message.get("items") or []
    return items[0] if items else None


def trace_crossref(seed: str, relation: str, limit: int, doi: str | None = None) -> list[dict]:
    if relation == "citations":
        return [
            {
                "source": "crossref",
                "relation": relation,
                "seed": seed,
                "error": "Crossref REST exposes citation counts but not citing-work lists. Use OpenAlex or Semantic Scholar for citations.",
            }
        ]
    work = find_crossref_work(query=None if doi else seed, doi=doi)
    if not work:
        return []
    references = work.get("reference") or []
    if references:
        return [normalize_crossref_reference(item, seed) for item in references[:limit]]
    return [
        {
            **normalize_crossref_work(work, seed, relation),
            "error": "No deposited references found for this Crossref record.",
        }
    ]


def trace_semantic(seed: str, relation: str, limit: int, paper_id: str | None = None) -> list[dict]:
    paper_id = paper_id or find_paper_id(seed)
    if not paper_id:
        return []
    params = {"limit": str(max(1, min(limit, 100))), "fields": FIELDS}
    url = f"{PAPER_URL}/{urllib.parse.quote(paper_id)}/{relation}?" + urllib.parse.urlencode(params)
    data = request_json(url, semantic_headers())
    return [normalize_semantic(item, seed, relation) for item in data.get("data", [])]


def dedupe_results(results: list[dict]) -> list[dict]:
    merged: dict[str, dict] = {}
    for item in results:
        if item.get("error"):
            key = f"error:{item.get('source')}:{item.get('error')}"
        elif item.get("doi"):
            key = "doi:" + norm_text(clean_doi(item.get("doi")))
        elif item.get("id"):
            key = "id:" + norm_text(str(item.get("id")))
        else:
            key = "title:" + norm_text(item.get("title"))
        if key not in merged:
            merged[key] = item
            merged[key]["sources_seen"] = [item.get("source")]
            continue
        existing = merged[key]
        source = item.get("source")
        if source and source not in existing.get("sources_seen", []):
            existing.setdefault("sources_seen", []).append(source)
        for field in ("doi", "url", "pdf_url", "abstract", "venue", "year", "type", "citation_count", "reference_count"):
            if not existing.get(field) and item.get(field):
                existing[field] = item[field]
    return list(merged.values())


def norm_text(value: str | None) -> str:
    if not value:
        return ""
    value = value.lower()
    value = re.sub(r"[^a-z0-9áéíóúñü]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def slugify(value: str, max_length: int = 80) -> str:
    value = norm_text(value)
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value[:max_length].strip("-") or "semantic-relations"


def trim(value: str | None, length: int = 420) -> str:
    if not value:
        return ""
    value = " ".join(str(value).split())
    return value if len(value) <= length else value[: length - 1].rstrip() + "..."


def render_markdown(results: list[dict], seed: str, relation: str, provider: str) -> str:
    lines = [
        "# Citation/Reference Relation Trace",
        "",
        f"Seed: `{seed}`",
        f"Relation: `{relation}`",
        f"Provider: `{provider}`",
        "",
    ]
    if not results:
        lines.append("_No results._")
        return "\n".join(lines) + "\n"

    for item in results:
        title = item.get("title") or "(missing title)"
        authors = ", ".join((item.get("authors") or [])[:5])
        if item.get("authors") and len(item["authors"]) > 5:
            authors += " et al."
        bits = []
        if authors:
            bits.append(authors)
        if item.get("year"):
            bits.append(str(item["year"]))
        if item.get("venue"):
            bits.append(str(item["venue"]))
        ids = []
        if item.get("doi"):
            ids.append(f"DOI: `{item['doi']}`")
        if item.get("url"):
            ids.append(f"[link]({item['url']})")
        if item.get("pdf_url"):
            ids.append(f"[pdf]({item['pdf_url']})")

        lines.append(f"- **{title}**")
        if bits:
            lines.append(f"  {' | '.join(bits)}")
        sources_seen = item.get("sources_seen") or [item.get("source")]
        if sources_seen:
            lines.append(f"  Source(s): `{', '.join(source for source in sources_seen if source)}`")
        if ids:
            lines.append("  " + " | ".join(ids))
        counts = []
        if item.get("citation_count") is not None:
            counts.append(f"citations: `{item['citation_count']}`")
        if item.get("reference_count") is not None:
            counts.append(f"references: `{item['reference_count']}`")
        if item.get("type"):
            counts.append(f"type: `{item['type']}`")
        if counts:
            lines.append("  " + " | ".join(counts))
        if item.get("abstract"):
            lines.append(f"  Abstract/snippet: {trim(item.get('abstract'))}")
        if item.get("error"):
            lines.append(f"  Retrieval error: `{trim(item.get('error'), 220)}`")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def save_outputs(results: list[dict], seed: str, relation: str, provider: str, output_dir: Path, run_name: str | None) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y-%m-%d-%H%M%S")
    stem = run_name or slugify(f"{relation}-{seed}")
    markdown_path = output_dir / f"{stamp}-{stem}.md"
    json_path = output_dir / f"{stamp}-{stem}.json"
    markdown_path.write_text(render_markdown(results, seed, relation, provider), encoding="utf-8")
    json_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"markdown": str(markdown_path), "json": str(json_path)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--paper-id")
    parser.add_argument("--doi", help="Seed DOI. Recommended for OpenAlex/Crossref precision.")
    parser.add_argument("--query", help="Seed title/query used to find a Semantic Scholar paperId")
    parser.add_argument(
        "--provider",
        choices=["semantic-scholar", "openalex", "crossref", "core", "springer-metadata", "springer-openaccess", "all"],
        default="semantic-scholar",
        help="Relation provider. `all` queries every compatible provider and deduplicates.",
    )
    parser.add_argument("--relation", choices=["citations", "references"], default="citations")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--save", action="store_true", help="Save Markdown and JSON outputs under the configured retrieval intermediate directory")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--run-name", help="Stable filename stem for saved outputs")
    args = parser.parse_args()

    if not args.paper_id and not args.query and not args.doi:
        parser.error("Use --paper-id, --doi, or --query")
    seed = args.doi or args.paper_id or args.query or ""

    providers = ["semantic-scholar", "openalex", "crossref", "core", "springer-metadata", "springer-openaccess"] if args.provider == "all" else [args.provider]
    results: list[dict] = []
    try:
        for provider in providers:
            if provider == "semantic-scholar":
                results.extend(trace_semantic(seed, args.relation, args.limit, args.paper_id))
            elif provider == "openalex":
                results.extend(trace_openalex(seed, args.relation, args.limit, args.doi))
            elif provider == "crossref":
                results.extend(trace_crossref(seed, args.relation, args.limit, args.doi))
            elif provider == "core":
                results.extend(trace_core(seed, args.relation, args.limit, args.doi))
            elif provider in {"springer-metadata", "springer-openaccess"}:
                results.extend(trace_springer(seed, args.relation, args.limit, provider, args.doi))
    except Exception as exc:
        results = [{"source": args.provider, "seed": seed, "relation": args.relation, "error": str(exc)}]
        print(json.dumps(results, indent=2))
        if args.save:
            paths = save_outputs(results, seed, args.relation, args.provider, Path(args.output_dir), args.run_name)
            print("\nSaved outputs:")
            print(f"- Markdown: {paths['markdown']}")
            print(f"- JSON: {paths['json']}")
        return 0
    if args.provider == "all":
        results = dedupe_results(results)
    print(json.dumps(results, ensure_ascii=False, indent=2))
    if args.save:
        paths = save_outputs(results, seed, args.relation, args.provider, Path(args.output_dir), args.run_name)
        print("\nSaved outputs:")
        print(f"- Markdown: {paths['markdown']}")
        print(f"- JSON: {paths['json']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
