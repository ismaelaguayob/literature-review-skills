# Retrieval Notes

## Project Configuration

Read `literature-review.yaml` before searching. The important fields are:

- `project.bib_path`
- `paths.retrieval_intermediate_dir`
- `paths.retrieval_curated_dir`
- `paths.keyword_ledger`
- `retrieval.core_terms`
- `retrieval.modifier_terms`
- `retrieval.default_queries`
- `retrieval.sources.enabled`
- `retrieval.from_year`
- `retrieval.user_agent`
- `apis`

`literature-keywords.yaml` is the working search memory. Keep `active`, `candidates`, and `rejected` separate.

If the user explains a working hypothesis during setup, translate only its operational implications into config: a few core terms, modifier terms, default queries, and synthesis category dimensions. Store the hypothesis itself in `review-state/` or an analysis output.

After editing config, run:

```bash
python3 scripts/doctor_config.py --config literature-review.yaml
```

## Environment

Load API settings from the project `.env`.

Preferred variables:

```bash
SEMANTIC_API_KEY=...
OPENALEX_API_KEY=...
SPRINGER_METADATA_API_KEY=...
SPRINGER_OPENACCESS_API_KEY=...
OPENROUTER_API_KEY=...       # used by synthesis, not retrieval
CROSSREF_MAILTO=...
RESEARCH_USER_AGENT=project-slug-lit-review/0.1 (mailto:you@example.org)
```

Optional:

```bash
SEMANTIC_SCHOLAR_API_KEY=...  # fallback name
OPENALEX_MAILTO=...
CROSSREF_API_KEY=...          # only for Crossref Plus
CORE_API_KEY=...              # CORE works without this, but it is honored if set
```

Do not print API keys. If `CROSSREF_MAILTO` is missing, ask the user to add it before heavy Crossref use.

## Commands

Initialize or inspect keywords:

```bash
python3 .agents/skills/literature-source-retrieval/scripts/init_keywords.py --config literature-review.yaml
python3 .agents/skills/literature-source-retrieval/scripts/show_keywords.py --config literature-review.yaml
```

All API sources, Markdown output:

```bash
python3 .agents/skills/literature-source-retrieval/scripts/discover_sources.py \
  --config literature-review.yaml \
  --query "configured topic measurement" \
  --query "configured topic conceptual framework" \
  --limit 10 \
  --save \
  --update-keywords \
  --run-name topic-measurement
```

If `--query` is omitted, `discover_sources.py` uses `retrieval.default_queries`; if those are empty, it generates queries from active keywords and `query_templates`.

Single API:

```bash
python3 .agents/skills/literature-source-retrieval/scripts/search_openalex.py --query "topic conceptual framework" --limit 10
python3 .agents/skills/literature-source-retrieval/scripts/search_semantic.py --query "topic governance" --limit 10
python3 .agents/skills/literature-source-retrieval/scripts/search_core.py --query "topic open access" --limit 10
python3 .agents/skills/literature-source-retrieval/scripts/search_springer_metadata.py --query "topic measurement" --limit 10
python3 .agents/skills/literature-source-retrieval/scripts/search_springer_openaccess.py --query "topic" --limit 10
python3 .agents/skills/literature-source-retrieval/scripts/search_crossref.py --query "topic measurement" --limit 10
python3 .agents/skills/literature-source-retrieval/scripts/search_arxiv.py --query "topic" --limit 10
```

Citation/reference tracing:

```bash
python3 .agents/skills/literature-source-retrieval/scripts/trace_citations.py --query "Seed paper title" --provider all --relation citations --limit 20 --save
python3 .agents/skills/literature-source-retrieval/scripts/trace_citations.py --doi "10.xxxx/example" --provider openalex --relation references --limit 20 --save
python3 .agents/skills/literature-source-retrieval/scripts/trace_citations.py --doi "10.xxxx/example" --provider core --relation references --limit 20 --save
python3 .agents/skills/literature-source-retrieval/scripts/trace_citations.py --doi "10.xxxx/example" --provider springer-metadata --relation references --limit 20 --save
```

`trace_citations.py` is strongest with Semantic Scholar and OpenAlex. Crossref can expose deposited references but not citing-work lists. CORE may expose parsed references when full-text parsing succeeded, but not a reliable citing-work list. Springer Metadata/OpenAccess is mainly a seed metadata/full-text availability lookup in this workflow; it should not be treated as a citation graph.

## Classification

Classify with judgment, not only script scores.

Core signals:

- directly defines or operationalizes the project construct;
- proposes dimensions, typologies, indicators, mechanisms, categories, or measurement frameworks;
- is foundational, frequently cited, or clearly central to the current research question;
- substantially changes the emerging taxonomy or conceptual map.

Peripheral signals:

- useful background, neighboring theory, regional context, methods, evidence, or comparison;
- relevant but not central to the planned synthesis;
- important genealogy source that frames the field.

Discarded signals:

- duplicate of existing corpus;
- weak relation after abstract/title inspection;
- marketing content without conceptual or empirical value;
- no reliable metadata or inaccessible record;
- too generic for the configured review scope.

## Keyword Ledger Practice

Script suggestions should usually enter `candidates`, not `active`. Promote terms when they improve recall/precision, name an emergent theme, capture a recurring method/source type, or help search a newly identified subfield. Reject broad or misleading terms with a short reason.

Curated retrieval outputs should include a short "Keyword updates" section with promoted, candidate, and rejected terms.

## API Cautions

Semantic Scholar:

- Use header `x-api-key`.
- Use non-hyphenated query terms when possible.
- Request compact fields first.

OpenAlex:

- Use `api_key` when available.
- Use `per-page` up to 200 for bulk, but keep exploratory searches small.
- Use entity IDs, not ambiguous names, for author/institution filtering.

Crossref:

- Use `mailto` and an identifying `User-Agent` for polite pool.
- Use `rows` for result count and `query.bibliographic` for general bibliographic search.
- Back off on 429 and avoid concurrent heavy Crossref requests.

CORE:

- No authentication is required for basic use.
- Best for open-access full text discovery and downloadable records.
- Metadata can be noisy; verify publisher, DOI, and duplicate status.

Springer Nature:

- Requires Springer API keys. Use `SPRINGER_METADATA_API_KEY` for Metadata API and `SPRINGER_OPENACCESS_API_KEY` for OpenAccess API.
- Use Metadata API for publisher-indexed discovery and OpenAccess API for full-text availability.
- Keyword queries are useful complements to OpenAlex/Semantic Scholar, not a replacement for cross-index deduplication.

arXiv:

- Use `export.arxiv.org/api/query`.
- Use `search_query=all:<term>` unless a fielded query is needed.
- Respect modest request rates.

Native web search:

- Prefer source pages, DOI landing pages, publisher pages, institutional PDFs, SSRN/arXiv pages, and official reports.
- Add native results manually to the curated Markdown using the same normalized fields.
