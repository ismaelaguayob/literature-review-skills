---
name: literature-synthesis-analysis
description: Produce traceable, configurable literature synthesis from a machine-readable corpus; build source-level findings, emergent categories, taxonomies, cross-source conclusions, APA citations, and curated review outputs from a project YAML and BibTeX file.
---

# Literature Synthesis Analysis

Use this skill after retrieval and corpus conversion. Do not search for new sources. Work from configured `paths.machine_dir`, the configured `.bib`, source files, and any optional synthesis lenses named in `literature-review.yaml`.

When adapting project configuration or when the user shares a working hypothesis, read `references/project_configuration.md`. Use the hypothesis to guide initial synthesis dimensions, but store actual taxonomy proposals, category definitions, and conclusions in `review-state/` or `outputs/`, not in `literature-review.yaml`.

## Workflow

1. Build an inventory with `.agents/skills/literature-synthesis-analysis/scripts/inventory_sources.py`.
2. Add stable trace anchors with `.agents/skills/literature-synthesis-analysis/scripts/add_trace_anchors.py` when sources lack anchors.
3. For small corpora, create intermediate synthesis files manually with `.agents/skills/literature-synthesis-analysis/scripts/make_intermediate_template.py`.
4. For medium or large corpora, use `.agents/skills/literature-synthesis-analysis/scripts/run_source_synthesis_llm.py`: it sends source groups or long-source segments to the configured direct LLM provider, expects structured JSON, and renders Markdown.
5. Validate rendered outputs with `.agents/skills/literature-synthesis-analysis/scripts/validate_source_syntheses.py`. This only verifies structure, links, and anchor existence.
6. The principal agent reads source-level syntheses, audits trace quality, and deep-dives into highlighted or suspicious source passages as needed.
7. While consolidating, propose emergent categories. Do not require the user to know the taxonomy in advance.
8. Use `.agents/skills/literature-synthesis-analysis/scripts/make_curation_workspace.py` to create the curation workspace: `review-state/research-brief.md`, `review-state/corpus-outlook.yaml`, `outputs/analysis/curated/corpus-outlook.md`, and `outputs/analysis/curated/narrative-review.qmd`.
9. Build the corpus outlook first. It must classify every source as included, peripheral, discarded, or uncategorized; a source may have multiple thematic, methodological, evidence, source-type, and research-use categories. Do not delete irrelevant sources; keep them in the discarded/irrelevant group with a rationale.
10. Write the final narrative review as a publishable English Quarto/Markdown paper. Use the outlook and validated source syntheses as the main substrate, but deep-dive into machine-readable sources when a source is important, a summary is shallow, or trace support is suspicious.
11. Before finalizing the narrative review, verify that every cited BibTeX key exists in the configured `.bib` file and that narrative citations use Quarto syntax correctly.

## Direct LLM Source Synthesis

Use from the project root:

```bash
python3 .agents/skills/literature-synthesis-analysis/scripts/run_source_synthesis_llm.py \
  --dry-run

python3 .agents/skills/literature-synthesis-analysis/scripts/run_source_synthesis_llm.py \
  --workers 4
```

The runner groups duplicate/companion machine-readable files by `bib_key`, prompts the configured LLM with project configuration plus exact source metadata and source text, writes structured JSON under `source-json/`, and renders one Markdown+YAML synthesis per source group under `source-syntheses/`. Long sources can be split into segment-level tasks when `synthesis.source_llm.split_long_sources` is enabled.

OpenRouter is the default direct provider. Configure `apis.openrouter` and `synthesis.source_llm` in `literature-review.yaml`; put the secret in `.env` as `OPENROUTER_API_KEY`.

The direct LLM compresses the corpus; it does not replace the principal agent. The principal agent must audit that cited anchors actually support the adjacent claim before writing the final synthesis.

The previous Codex sub-agent runner is deprecated and is intentionally not installed under `.agents/skills/`.

## Category Discovery

Treat categories as analysis outputs. Useful dimensions often include source type, thematic category, method, geography, unit of analysis, theory family, evidence type, and measurement approach, but the final taxonomy should emerge from the corpus. Examples from one project might be organizational reports, journal articles, conference papers, data sovereignty, digital sovereignty, algorithmic sovereignty, or data colonialism; another project should develop its own categories.

## Curated Outputs

The curation phase has two products:

1. `corpus-outlook`: a systematic research map for navigating the corpus by emergent categories, themes, methods, evidence/data types, source types, geographies, and research uses. It should be useful even before the final paper exists.
2. `narrative-review.qmd`: a publishable, human-written scholarly narrative in English that answers the research questions and objectives in `review-state/research-brief.md`.

Use Quarto/Pandoc citation syntax in the final paper. Parenthetical citations use brackets: `... [@bibkey]`. Narrative citations use bare keys in prose: `@roberts_digital_2024 argues that ...`, never `[@roberts_digital_2024] argues that ...`. Multiple parenthetical citations use semicolons: `... [@key1; @key2]`. The QMD frontmatter should point to the configured BibTeX file so citations and bibliography render automatically.

Avoid writing the final paper like a report. Prefer connected prose, an explicit thesis, careful transitions, and citations that support the claims. A strong first draft should move from the research problem to conceptual clarification, then to the corpus map, cross-source mechanisms/tensions, implications for the configured research task, limitations, and conclusion. Do not overuse bullet lists, formulaic contrasts, or repetitive scaffolding language.

## Traceability

Use stable anchors inserted into machine-readable Markdown:

```markdown
<a id="trace-source-stem-0001"></a>
```

Evidence links in analysis files should use Markdown links to anchored machine-readable files plus an APA 7 citation. When page numbers are unreliable, anchor links are the standard trace reference.

## References

- Use `references/synthesis_schema.md` for configurable schemas and curated synthesis guidance.
- Use `references/citation_rules.md` for APA 7 and traceability rules.
- Use `references/project_configuration.md` when adjusting setup or deciding where analytical state belongs.
- Use project-specific lenses only when configured or clearly relevant.
