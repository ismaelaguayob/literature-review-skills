# Synthesis Schema

The concrete intermediate sections are configured in `literature-review.yaml` under `synthesis.intermediate_sections`. Treat this file as a reference for what high-quality synthesis should contain, not as a fixed taxonomy.

## Intermediate Source Synthesis

Use this structure for source-level or section/chapter-level files.

```markdown
# Source Synthesis: <Short Title>

## Identification
- APA 7:
- In-text citation:
- BibTeX key:
- Source kind:
- Source file:
- Machine-readable file:
- Segment/section:
- Synthesis lens:

## Status
- Coverage:
- Confidence:
- Notes on extraction quality:

## Thesis

## Key Concepts and Definitions

## Categories Suggested by This Source
- source_type:
- thematic_category:
- methodological_approach:
- measurement_approach:

## Mechanisms, Arguments, or Findings

## Tensions and Trade-offs

## Evidence and Traceable Notes
- Claim:
  Evidence:
  Citation:
  Trace:

## Implications for the Review

## Open Questions
```

## Measurement Artifact Synthesis

Use this shape when `source_kind: measurement_stocktake` or when a source proposes indicators, dimensions, maturity models, typologies, benchmarks, or operational variables.

```markdown
# Measurement Artifact Synthesis: <Short Title>

## Identification

## Measurement Purpose

## Unit of Analysis

## Dimensions and Subdimensions

## Indicators / Categories / Levels

## Scoring or Maturity Logic

## Data Requirements

## Portability to the Current Review

## Risks, Biases, and Missing Dimensions

## Traceable Evidence
```

## Corpus Outlook

Use this structure for `outputs/analysis/curated/corpus-outlook.md`. The corresponding structured state lives in `review-state/corpus-outlook.yaml`.

```markdown
# Corpus Outlook: <Configured Topic>

## Purpose

## Coverage

## Emergent Thematic Categories

## Source-Type Map

## Methodological Map

## Evidence/Data Map

## Research Uses

## Reading Pathways

## Discarded or Irrelevant Sources
```

Every source must appear in the outlook state. A source may belong to multiple categories. Irrelevant or out-of-scope papers should be marked as discarded with a rationale, not silently removed.

## Narrative Review

Use `outputs/analysis/curated/narrative-review.qmd` for the final publishable product. This should be a scholarly narrative in English, not a robotic report. It should answer the questions and objectives in `review-state/research-brief.md`, use the corpus outlook as an organizing map, cite claims with exact BibTeX keys, and include a generated bibliography through Quarto/Pandoc.

A strong first draft should make an explicit argument. It should introduce the research problem, clarify the central concepts, map the corpus through emergent categories, synthesize mechanisms and tensions across sources, and translate the findings into implications for the configured research task. Use source syntheses as compressed evidence, but deep-dive into machine-readable sources for pivotal claims or weak traces.

Quarto/Pandoc citation syntax:

```markdown
Digital sovereignty debates often frame infrastructure and regulatory capacity as coupled problems [@example2024].

@example2024 argues that regional capacity depends on institutional coordination.

Several sources converge on this point [@example2024; @another2022].
```

Do not write narrative citations as `[@example2024] argues that ...`; Quarto treats bracketed citations as parenthetical. In prose, use the bare key form: `@example2024 argues that ...`.

## Category Practice

Do not force categories at the start of the project. Use intermediate synthesis to propose and revise them. A mature curated output should explain why the final categories are useful, which sources belong to each category, where sources overlap, and which sources resist the taxonomy.

If a taxonomy is still a working hypothesis, store it in `review-state/taxonomy-proposal.yaml` or a curated analysis draft, not in `literature-review.yaml`.

## Direct LLM Synthesis Practice

For corpora that exceed the principal agent's useful context window, use the direct LLM runner to compress the corpus into structured source-level JSON and rendered Markdown. The runner should not search the web or edit shared analytical state.

Recommended sequence:

1. Insert or refresh trace anchors.
2. Run `run_source_synthesis_llm.py --dry-run` to inspect task count without spending tokens.
3. Run `run_source_synthesis_llm.py --workers 4` with conservative concurrency first.
4. Validate rendered Markdown outputs with `validate_source_syntheses.py`.
5. Principal agent audits semantic support for core sources and suspicious traces.
6. Principal agent writes the curated synthesis from validated intermediate outputs.

Parallelism changes waiting time more than total token cost. Running many source requests at once can be faster, but it concentrates API usage and failures into one burst. Use high concurrency only when rate limits, quota, and local process load are acceptable.
