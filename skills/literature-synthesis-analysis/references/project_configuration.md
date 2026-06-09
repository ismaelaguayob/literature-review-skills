# Project Configuration Guide

Use `literature-review.yaml` for operational configuration, not for finished analysis.

The synthesis skill reads these sections:

- `project.bib_path`
- `paths.machine_dir`
- `paths.analysis_intermediate_dir`
- `paths.analysis_curated_dir`
- `paths.review_state_dir`
- `review-state/research-brief.md`
- `synthesis.lens_name`
- `synthesis.category_dimensions`
- `synthesis.intermediate_sections`
- `synthesis.findings_sections`
- `synthesis.source_llm`

## What Belongs In Config

Use `synthesis.category_dimensions` to tell Codex what kinds of categories to look for. These are prompts for analysis, not the final taxonomy.

Good examples:

```yaml
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
    model: google/gemini-3.5-flash
    workers: 4
    requests_per_minute: 20
    split_long_sources: true
```

`source_llm.workers` controls local parallel task scheduling, while `synthesis.source_llm.requests_per_minute` and `apis.openrouter.min_interval_seconds` control rate limiting. More workers can finish sooner, but increase simultaneous quota use and retry pressure. Keep defaults conservative unless the user explicitly wants a burst.

## What Belongs Outside Config

When Codex develops a specific taxonomy, conceptual model, hypothesis, or categorization of papers, put it outside `literature-review.yaml`:

- `review-state/taxonomy-proposal.yaml` for structured evolving state;
- `review-state/research-brief.md` for research questions, objectives, working hypotheses, scope conditions, inclusion priorities, exclusion criteria, and notes for the final narrative;
- `review-state/corpus-outlook.yaml` for the systematic corpus map and source categorizations;
- `review-state/codebook.yaml` for category definitions;
- `outputs/analysis/intermediate/*.md` for source-level findings;
- `outputs/analysis/curated/corpus-outlook.md` for the readable corpus outlook;
- `outputs/analysis/curated/narrative-review.qmd` for the final publishable narrative review with BibTeX-backed citations.

The user may explain a working hypothesis during setup. Treat that as context for choosing initial search terms and synthesis dimensions, and write the substantive hypothesis, objectives, and questions to `review-state/research-brief.md`, not to `literature-review.yaml` unless they directly change script behavior.

Run `scripts/doctor_config.py` if config starts to look like analysis prose.
