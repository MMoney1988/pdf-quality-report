# Export Clean Markdown

## What this does

Converts `normalized_blocks.json` into clean Markdown.

This export step comes after conversion. It does not read PDFs directly. It reads `normalized_blocks.json`, which
already contains text blocks, page numbers, block types, and source provenance.

Use it after the quality report when the normalized blocks are structurally usable and you want a reviewable Markdown
artifact for downstream work.

## What this does not do

No OCR. No table reconstruction. No RAG pipeline.

## Command

```bash
python -m pdf_quality_report.to_markdown \
  --input examples/mdpi_pdf_elements/page_012/normalized_blocks.json \
  --output /tmp/page_012.md
```

```bash
pdf-quality-markdown \
  --input examples/mdpi_pdf_elements/page_012/normalized_blocks.json \
  --output /tmp/page_012.md
```

## Output

The export includes YAML front matter, headings and paragraphs, source comments, filtered noise, and deterministic footnotes.
Source comments are HTML comments that keep block/page context without changing the visible Markdown text. Filtered noise
means headers, footers, and very short layout fragments are skipped by default. Footnotes use stable block IDs when
possible, so repeated exports stay deterministic.

## When to use it

Use this after the quality report if the normalized blocks are structurally usable.
