#!/usr/bin/env python3
"""Search arXiv and print normalized JSON."""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET


API_URL = "https://export.arxiv.org/api/query"
NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}


def request_xml(url: str, retries: int = 4) -> ET.Element:
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                return ET.fromstring(response.read())
        except urllib.error.HTTPError as exc:
            if exc.code in {429, 500, 502, 503, 504} and attempt < retries - 1:
                time.sleep(2**attempt)
                continue
            raise


def text(node: ET.Element, path: str) -> str | None:
    found = node.find(path, NS)
    if found is None or found.text is None:
        return None
    return " ".join(found.text.split())


def normalize(entry: ET.Element, query: str) -> dict:
    links = entry.findall("atom:link", NS)
    url = None
    pdf_url = None
    for link in links:
        href = link.attrib.get("href")
        if link.attrib.get("rel") == "alternate":
            url = href
        if link.attrib.get("title") == "pdf" or link.attrib.get("type") == "application/pdf":
            pdf_url = href
    authors = []
    for author in entry.findall("atom:author", NS):
        name = text(author, "atom:name")
        if name:
            authors.append(name)
    categories = [cat.attrib.get("term") for cat in entry.findall("atom:category", NS) if cat.attrib.get("term")]
    entry_id = text(entry, "atom:id")
    return {
        "source": "arxiv",
        "query": query,
        "id": entry_id.rsplit("/", 1)[-1] if entry_id else None,
        "title": text(entry, "atom:title"),
        "authors": authors,
        "year": (text(entry, "atom:published") or "")[:4] or None,
        "doi": text(entry, "arxiv:doi"),
        "url": url or entry_id,
        "pdf_url": pdf_url,
        "abstract": text(entry, "atom:summary"),
        "venue": "arXiv",
        "type": ", ".join(categories),
        "published": text(entry, "atom:published"),
        "updated": text(entry, "atom:updated"),
    }


def arxiv_query(raw: str) -> str:
    if ":" in raw or " AND " in raw or " OR " in raw:
        return raw
    terms = [term for term in raw.replace("-", " ").split() if term]
    return "+AND+".join(f"all:{urllib.parse.quote(term)}" for term in terms)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", required=True)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--sort-by", default="relevance", choices=["relevance", "lastUpdatedDate", "submittedDate"])
    parser.add_argument("--sort-order", default="descending", choices=["ascending", "descending"])
    args = parser.parse_args()

    params = {
        "search_query": arxiv_query(args.query),
        "start": "0",
        "max_results": str(max(1, min(args.limit, 100))),
        "sortBy": args.sort_by,
        "sortOrder": args.sort_order,
    }
    url = API_URL + "?" + urllib.parse.urlencode(params, safe=":+")
    root = request_xml(url)
    results = [normalize(entry, args.query) for entry in root.findall("atom:entry", NS)]
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
