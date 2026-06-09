"""Shared Springer Nature search helpers."""

from __future__ import annotations

import os
import re
from typing import Any

from shared.api_utils import request_json


METADATA_URL = "https://api.springernature.com/meta/v2/json"
OPENACCESS_URL = "https://api.springernature.com/openaccess/json"


def springer_query(query: str, from_year: int | None, to_year: int | None, raw: bool = False) -> str:
    if raw or ":" in query or re.search(r"\b(?:AND|OR|NOT)\b", query):
        base = query
    else:
        escaped = query.replace('"', r"\"")
        base = f'keyword:"{escaped}"'
    if from_year and to_year and from_year == to_year:
        base += f" year:{from_year}"
    return base


def authors_from(record: dict[str, Any]) -> list[str]:
    authors = []
    for creator in record.get("creators") or []:
        if isinstance(creator, dict) and creator.get("creator"):
            authors.append(str(creator["creator"]))
        elif isinstance(creator, str):
            authors.append(creator)
    return authors


def url_from(record: dict[str, Any], prefer_pdf: bool = False) -> tuple[str | None, str | None]:
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
    if prefer_pdf and pdf_url:
        return pdf_url, pdf_url
    return url, pdf_url


def normalize(record: dict[str, Any], query: str, source: str) -> dict[str, Any]:
    publication_date = record.get("publicationDate") or record.get("onlineDate") or record.get("printDate") or ""
    doi = record.get("doi")
    url, pdf_url = url_from(record, prefer_pdf=source == "springer-openaccess")
    abstract = record.get("abstract")
    if isinstance(abstract, dict):
        abstract = " ".join(str(value) for value in abstract.values() if value)
    return {
        "source": source,
        "query": query,
        "id": doi or record.get("identifier"),
        "title": record.get("title"),
        "authors": authors_from(record),
        "year": publication_date[:4] or None,
        "doi": doi,
        "url": url or (f"https://doi.org/{doi}" if doi else None),
        "pdf_url": pdf_url,
        "abstract": abstract,
        "venue": record.get("publicationName"),
        "publisher": record.get("publisher"),
        "type": record.get("contentType") or record.get("genre"),
        "citation_count": None,
        "is_open_access": source == "springer-openaccess" or str(record.get("openaccess")).lower() == "true",
        "source_quality_signals": {
            "publisher_springer": True,
            "open_access_full_text": bool(pdf_url) if source == "springer-openaccess" else False,
            "has_doi": bool(doi),
        },
    }


def search_springer(
    *,
    endpoint: str,
    source: str,
    query: str,
    limit: int,
    from_year: int | None,
    to_year: int | None,
    raw_query: bool,
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    springer_config = config.get("apis", {}).get("springer", {})
    if source == "springer-openaccess":
        api_key_env = springer_config.get("openaccess_api_key_env") or springer_config.get("api_key_env") or "SPRINGER_OPENACCESS_API_KEY"
    else:
        api_key_env = springer_config.get("metadata_api_key_env") or springer_config.get("api_key_env") or "SPRINGER_METADATA_API_KEY"
    api_key = os.environ.get(api_key_env)
    if not api_key:
        return [{"source": source, "query": query, "title": None, "error": f"missing {api_key_env}"}]
    params = {
        "q": springer_query(query, from_year, to_year, raw_query),
        "api_key": api_key,
        "p": str(max(1, min(limit, 100))),
        "s": "1",
    }
    headers = {
        "Accept": "application/json",
        "User-Agent": os.environ.get("RESEARCH_USER_AGENT", config.get("retrieval", {}).get("user_agent", "literature-review/0.1")),
    }
    data = request_json(endpoint, provider="springer", config=config, params=params, headers=headers)
    records = data.get("records", []) if isinstance(data, dict) else []
    return [normalize(record, query, source) for record in records if record.get("title")]
