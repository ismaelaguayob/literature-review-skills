# Literature Review Skills

Reusable Codex skills and scripts for literature review workflows with Zotero/BibTeX:

- retrieve new scholarly and policy sources;
- maintain an evolving YAML keyword ledger;
- convert PDFs/HTML to machine-readable Markdown;
- synthesize sources into traceable findings, emergent categories, and curated reviews.

## Project Files

Each project should have:

- `.agents/skills/`: local Codex skills for this project.
- `shared/`: shared Python helpers used by the skill scripts.
- `scripts/`: project setup and diagnostic scripts.
- `literature-review.yaml`: topic, paths, BibTeX file, retrieval terms, synthesis settings.
- `literature-keywords.yaml`: active, candidate, and rejected keywords.
- `review-state/`: structured analytical state such as the research brief, corpus outlook state, taxonomy drafts, codebooks, and working hypotheses.
- one configured BibTeX file exported from Zotero.
- `sources/` with PDFs/HTML files.

In this repository, `skills/` is the source/development copy. In a project that consumes the toolkit, install those skills under `.agents/skills/`.

## Install In Another Project

From this toolkit repository, run the installer with the target project as the working directory:

```bash
cd ../AI-adoption
python3 ../literature-review-skills/scripts/init_project.py \
  --name "AI Adoption" \
  --bib-path "AI adoption.bib" \
  --core-term "AI adoption" \
  --core-term "artificial intelligence adoption" \
  --core-term "firm-level AI adoption" \
  --core-term "AI diffusion"
```

This creates or updates:

```text
.agents/skills/
shared/
scripts/
literature-review.yaml
literature-keywords.yaml
review-state/
outputs/
machine-readable/
```

If `literature-review.yaml` already exists, the installer will skip rewriting it unless `--force` is used, but it can still install missing skills. Use `--refresh-toolkit` to update `.agents/skills`, `shared`, and `scripts` without rewriting config. Use `--skip-agent-skills` if you only want config/directories.

## Initialize A Project

When already inside a project that has the toolkit files copied:

```bash
python3 scripts/init_project.py \
  --name "My Review Topic" \
  --bib-path references.bib \
  --core-term "main construct" \
  --core-term "related construct"
```

Then check the setup:

```bash
python3 scripts/doctor_config.py
```

## Configuration Boundaries

`literature-review.yaml` is for script and workflow configuration. Keep it short and stable: project identity, exact BibTeX path, path conventions, retrieval terms, enabled providers, API rate/cache settings, direct LLM settings, and synthesis section prompts.

Do not store long hypotheses, proposed taxonomies, category definitions, or paper findings in `literature-review.yaml`. Put those in `review-state/*.yaml` when they are structured working state, or in `outputs/analysis/**/*.md` when they are research outputs.

`review-state/research-brief.md` is the place for the initial research questions, objectives, working hypotheses, scope conditions, and final-writing notes that emerge while Codex helps configure a project.

`literature-keywords.yaml` is the evolving retrieval memory. Use `active` for trusted search vocabulary, `candidates` for terms still being evaluated, and `rejected` for terms that should not be reused.

Secrets live in `.env`, not in YAML. Common keys are `SEMANTIC_API_KEY`, `OPENALEX_API_KEY`, `SPRINGER_METADATA_API_KEY`, `SPRINGER_OPENACCESS_API_KEY`, and `OPENROUTER_API_KEY`. CORE does not require authentication.

## Retrieval

```bash
python3 .agents/skills/literature-source-retrieval/scripts/discover_sources.py \
  --config literature-review.yaml \
  --save \
  --update-keywords
```

Automated outputs go to `paths.retrieval_intermediate_dir`. The agent should write curated retrieval notes to `paths.retrieval_curated_dir`.

Default retrieval providers come from `retrieval.sources.enabled`; arXiv is configured as a targeted provider and can be called with `--source arxiv`.

## Conversion

```bash
python3 .agents/skills/markitdown-corpus-converter/scripts/convert_corpus.py
```

Outputs go to `paths.machine_dir` and include metadata for BibTeX matching and source-kind inference.

## Synthesis

```bash
python3 .agents/skills/literature-synthesis-analysis/scripts/inventory_sources.py
python3 .agents/skills/literature-synthesis-analysis/scripts/add_trace_anchors.py --all
python3 .agents/skills/literature-synthesis-analysis/scripts/run_source_synthesis_llm.py --dry-run
python3 .agents/skills/literature-synthesis-analysis/scripts/run_source_synthesis_llm.py --workers 4
python3 .agents/skills/literature-synthesis-analysis/scripts/validate_source_syntheses.py outputs/analysis/intermediate/<run-name>/source-syntheses
python3 .agents/skills/literature-synthesis-analysis/scripts/make_curation_workspace.py --source-json-dir outputs/analysis/intermediate/<run-name>/source-json
```

The taxonomy should emerge during synthesis. Use `synthesis.category_dimensions` as prompts for categorization, not as a fixed schema. The curation workspace creates `review-state/corpus-outlook.yaml`, `outputs/analysis/curated/corpus-outlook.md`, and `outputs/analysis/curated/narrative-review.qmd`.

For large corpora, use the direct LLM runner to create one structured JSON and one traceable Markdown synthesis per source group or long-source segment. OpenRouter is configured under `apis.openrouter` and `synthesis.source_llm`; cache and rate limiting are enabled from the start. The old Codex sub-agent runner is kept only under `deprecated/` and is not installed into consuming projects.

The final narrative review should be written as a publishable English Quarto document. Use BibTeX keys directly in Markdown/Quarto, for example `[@smith2024]`, `@smith2024`, or `[@smith2024; @lee2023]`; Quarto/Pandoc will render citations and the bibliography from the configured `.bib` file.

## Presets

`presets/ai-sovereignty-ilia/` shows how to configure the generic workflow for the original AI sovereignty and ILIA-oriented project.
