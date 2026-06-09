---
name: literature-source-retrieval
description: Discover, verify, deduplicate, classify, and curate new scholarly or policy sources for a configurable literature review project using local project YAML, a growing keyword ledger, native web search, Semantic Scholar, OpenAlex, CORE, Springer Nature, Crossref, and arXiv APIs.
---

# Literature Source Retrieval

Use this skill to expand a literature review corpus with new candidate sources. The project-specific topic, BibTeX file, search terms, paths, and scoring terms come from `literature-review.yaml`; evolving retrieval vocabulary lives in `literature-keywords.yaml`.

When installing this kit in a new project or modifying `literature-review.yaml`, read `references/project_configuration.md` first. Keep the YAML as operational config; put hypotheses, taxonomy drafts, and paper findings in `review-state/` or `outputs/`.

## Workflow

1. Inspect `literature-review.yaml`, `literature-keywords.yaml`, the configured `.bib`, and existing source filenames.
2. If `literature-keywords.yaml` is missing, create it with `scripts/init_keywords.py`.
3. Use active keywords, configured default queries, user-provided seeds, and newly discovered candidate terms to plan searches.
4. Run `scripts/discover_sources.py` for API discovery. By default it uses `retrieval.sources.enabled` from `literature-review.yaml`; invoke targeted providers such as arXiv with `--source arxiv` when relevant. Use `--update-keywords` during exploratory searches so new terms are added as candidates, not active terms.
5. Use native web search for recent, gray-literature, institutional, or broad discovery, and whenever API results look sparse.
6. Deduplicate by DOI, URL, arXiv ID, Semantic Scholar ID, OpenAlex ID, CORE ID, Springer record metadata, and normalized title.
7. Classify each candidate as `Core`, `Peripheral`, or `Discarded`. Treat script scores as aids; agent judgment decides final classification.
8. Write automated outputs to the configured retrieval intermediate directory and write a separate curated Markdown synthesis to the configured retrieval curated directory.
9. In curated outputs, include retrieval purpose, strongest candidates, existing-corpus matches, sources to add, exclusions/duplicates, and keyword ledger updates.

## Scripts

Run scripts from the project root.

- `.agents/skills/literature-source-retrieval/scripts/init_keywords.py --config literature-review.yaml`
- `.agents/skills/literature-source-retrieval/scripts/show_keywords.py --config literature-review.yaml`
- `.agents/skills/literature-source-retrieval/scripts/discover_sources.py --config literature-review.yaml --query "..." --limit 10 --save --update-keywords`
- `.agents/skills/literature-source-retrieval/scripts/search_semantic.py`, `search_openalex.py`, `search_core.py`, `search_springer_metadata.py`, `search_springer_openaccess.py`, `search_crossref.py`, `search_arxiv.py`
- `.agents/skills/literature-source-retrieval/scripts/trace_semantic_relations.py --query "..." --provider all --relation citations --limit 20 --save`
- `.agents/skills/literature-source-retrieval/scripts/trace_citations.py`: compatibility alias for `trace_semantic_relations.py`

See `references/project_configuration.md` for setup boundaries and `references/retrieval_notes.md` for API settings, command examples, output format, keyword ledger practice, and provider cautions.

## API Configuration

Provider settings live under `apis` in `literature-review.yaml`. Configure API key environment-variable names, retries, cache, and minimum request interval there; put actual secrets only in `.env`. CORE works without authentication, but `CORE_API_KEY` is honored if a project has one. Springer Metadata and OpenAccess use separate keys by default, `SPRINGER_METADATA_API_KEY` and `SPRINGER_OPENACCESS_API_KEY`; OpenRouter is only used by the synthesis skill.

## Keyword Ledger

Keep `active`, `candidates`, and `rejected` distinct. Promote candidate terms to active only when they improve the search strategy or identify a meaningful conceptual, empirical, methodological, regional, or source-type category. Rejected terms should keep a short reason so future searches do not circle back.
