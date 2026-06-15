# Citation and Traceability Rules

## APA 7

Use APA 7 in prose and findings. Generate citations from the configured BibTeX file in `literature-review.yaml` when possible.

Examples:

- Parenthetical: `(Mügge, 2024)`
- Narrative: `Mügge (2024) argues...`
- Multiple authors: `(Yew et al., 2026)`
- No author or institutional/web item: use the title/institution from the BibTeX metadata.

## Evidence Links

Every substantive claim in intermediate outputs should include at least one traceable evidence link.

Preferred format:

```markdown
Claim text (Author, Year). [Evidence](../../machine-readable/markitdown/file.md#trace-id)
```

Use page numbers only when reliable. If page numbers are not reliable, the anchor link is the standard trace.

## Character Ranges

When an anchor covers too much text or the source structure is noisy, add a character range after the link:

```markdown
Trace: `machine-readable/markitdown/file.md`, anchor `trace-id`, chars 12030-12680.
```

## Bibliography Consistency

Do not invent bibliographic metadata. Use:

- `bib_key`
- `bib_title`
- `bib_entry_type`
- source metadata block in machine-readable files
- the configured BibTeX file

## Quarto / Pandoc Citations

Final narrative reviews are written as `.qmd` files and should use exact BibTeX keys from the configured `.bib` file.

Examples:

```markdown
Parenthetical citation: The literature frames sovereignty as relational capacity [@roberts_digital_2024].

Narrative citation: @roberts_digital_2024 argues that sovereignty depends on institutional and infrastructural conditions.

Multiple parenthetical citations: This point appears across several debates [@roberts_digital_2024; @example2025].
```

Do not write narrative citations as `[@roberts_digital_2024] argues that ...`. Brackets create a parenthetical citation; narrative citations must use the bare key form in prose.
