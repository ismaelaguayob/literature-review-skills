---
name: markitdown-corpus-converter
description: Convert a configurable literature review corpus of PDFs and HTML files to machine-readable Markdown with metadata, BibTeX matching, source-kind inference, and stable output paths for downstream synthesis.
---

# MarkItDown Corpus Converter

Use this skill to convert local source documents into Markdown derivatives while preserving original files. The configured `.bib`, source directory, and machine-readable output directory come from `literature-review.yaml`.

## Workflow

1. Inspect `literature-review.yaml`, the configured source directory, and the configured `.bib`.
2. Convert PDFs with `.agents/skills/markitdown-corpus-converter/scripts/convert_pdf.py`.
3. Convert HTML files with `.agents/skills/markitdown-corpus-converter/scripts/convert_html.py`.
4. For whole-corpus conversion, use `.agents/skills/markitdown-corpus-converter/scripts/convert_corpus.py`; by default it reads `paths.sources_dir` and writes to `paths.machine_dir`.
5. After conversion, report counts, failed files, skipped files, and output paths. Flag noisy extraction instead of treating it as clean text.

## Scripts

- `.agents/skills/markitdown-corpus-converter/scripts/convert_pdf.py <input.pdf> [--output-dir machine-readable/markitdown] [--force]`
- `.agents/skills/markitdown-corpus-converter/scripts/convert_html.py <input.html> [--output-dir machine-readable/markitdown] [--force]`
- `.agents/skills/markitdown-corpus-converter/scripts/convert_corpus.py [--root sources] [--output-dir machine-readable/markitdown] [--force]`

Each output starts with metadata: source path, source type, inferred `source_kind`, BibTeX key/type/title when matched, conversion tool, and timestamp.

## Source Kinds

Use source kinds during synthesis to distinguish articles, reports, books, proceedings, web articles, working papers, preprints, and measurement artifacts. For ambiguous cases, use `references/source_kind_overrides.json`; keep overrides explicit rather than hiding project-specific assumptions in code.
