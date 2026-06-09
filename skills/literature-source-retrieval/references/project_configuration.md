# Project Configuration Guide

Use this guide whenever installing the skills in a new repository or adapting them to a new literature review.

## File Responsibilities

`literature-review.yaml` is operational configuration. It should answer: how should scripts run for this project?

Put here:

- project name, slug, description, and configured BibTeX path;
- path conventions for sources, machine-readable outputs, retrieval outputs, analysis outputs, keyword ledger, and review state;
- retrieval defaults such as year range, API result limit, User-Agent, core terms, modifier terms, exclusion terms, and default queries;
- API behavior such as enabled providers, retry/throttle settings, cache settings, and API-key environment-variable names;
- synthesis defaults such as lens name, category dimensions to consider, intermediate sections, and findings sections.

Do not put here:

- substantive hypotheses that still need to be tested;
- long conceptual frameworks;
- proposed taxonomies with definitions and evidence;
- paper-by-paper findings;
- notes from conversations with the user;
- generated literature review prose.

`literature-keywords.yaml` is retrieval memory. It should contain search vocabulary and its status.

Put here:

- `active`: terms currently trusted for search expansion or scoring;
- `candidates`: terms suggested by the agent, user, or retrieval results but not yet accepted;
- `rejected`: terms that were considered and rejected, with a short reason;
- `query_templates`: reusable query shapes.

`review-state/` is structured analytical state. Use it for evolving hypotheses, taxonomy drafts, category proposals, codebooks, inclusion/exclusion decisions, and project-specific notes that should remain machine-readable but are not script configuration.

`outputs/` is generated research work. Use it for retrieval reports, intermediate source syntheses, findings maps, curated reviews, and final taxonomies.

## How Codex Should Adapt Config

When installing or adapting the kit, Codex should:

1. Inspect existing files: `.bib`, `sources/`, README/project notes, and any user-provided research question.
2. Set `project.bib_path` to the exact local filename, preserving case.
3. Keep `retrieval.core_terms` short: 3-8 central constructs that define the review.
4. Put useful but secondary signals in `retrieval.modifier_terms`: methods, evidence types, data sources, regions, units of analysis, or measurement vocabulary.
5. Put uncertain or exploratory vocabulary in `literature-keywords.yaml` under `candidates`, not in `core_terms`.
6. Set `retrieval.default_queries` to 5-10 high-value starting queries.
7. Configure `synthesis.category_dimensions` as prompts for analysis, not a fixed taxonomy.
8. Move any detailed hypothesis or taxonomy proposal to `review-state/*.yaml` or `outputs/analysis/curated/*.md`.
9. Run `scripts/doctor_config.py` after editing config.

## Good Config Shape

```yaml
project:
  name: AI Adoption
  slug: ai-adoption
  description: Literature review on firm-level AI adoption and measurement.
  bib_path: AI adoption.bib

retrieval:
  core_terms:
    - AI adoption
    - artificial intelligence adoption
    - firm-level AI adoption
    - AI diffusion
  modifier_terms:
    - measurement
    - taxonomy
    - maturity model
    - online data
    - firm websites
    - job postings
    - patents
  default_queries:
    - firm-level AI adoption measurement
    - AI adoption taxonomy firms
    - identifying AI adopters online data

apis:
  springer:
    metadata_api_key_env: SPRINGER_METADATA_API_KEY
    openaccess_api_key_env: SPRINGER_OPENACCESS_API_KEY
    min_interval_seconds: 1.0
    retries: 4
    cache: true
  semantic_scholar:
    min_interval_seconds: 1.0
    retries: 4
    throttle_scope: project
    cache: true

synthesis:
  lens_name: Firm-level AI adoption measurement
  category_dimensions:
    - source_type
    - thematic_category
    - methodological_approach
    - measurement_approach
    - unit_of_analysis
  source_llm:
    provider: openrouter
    model: google/gemini-2.5-flash
    workers: 4
    requests_per_minute: 20
    split_long_sources: true
```

## Bad Config Smell

If `literature-review.yaml` has a large block like `taxonomy_proposal`, `current_hypothesis`, `proposed_categories`, or many detailed definitions, move that content out of config. Use `review-state/taxonomy-proposal.yaml` for structured drafts or `outputs/analysis/curated/taxonomy-proposal.md` for prose.
