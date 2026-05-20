# Export Chunk Review Markdown

## What this does

Renders chunk records as human-readable Markdown for review.

This export step comes after conversion. It reads `normalized_blocks.json`, builds the same chunk records as
`pdf_quality_report.chunk`, and writes a Markdown review sheet with chunk IDs, pages, block IDs, section paths,
citation-style display strings, BBox reference counts, and text previews.

Use it when you want to inspect chunk structure without opening JSONL directly.

## What this does not do

No OCR. No table reconstruction. No embeddings. No vector store. No retrieval pipeline. No LLM answer generation.
This export does not approve, reject, correct, or score chunks.

## Command

```bash
python -m pdf_quality_report.chunk_review \
  --input examples/mdpi_pdf_elements/page_006/normalized_blocks.json \
  --output /tmp/page_006_chunk_review.md
```

```bash
pdf-quality-chunk-review \
  --input examples/mdpi_pdf_elements/page_006/normalized_blocks.json \
  --output /tmp/page_006_chunk_review.md
```

## Output

The export writes a Markdown review sheet with:

- summary counts for chunks, pages, characters, and distinct nearest headings
- one section per chunk
- citation-style display strings
- extracted section paths
- page numbers and block IDs
- BBox reference counts
- deterministic text previews

Previews are literal excerpts from chunk text. The Markdown is for review. It is not a replacement for
`pdf-quality-markdown`, not a retrieval artifact, and should not be treated as final document content.

## When to use it

Use this after the quality report and chunk-record export when you need a quick human-readable view of chunk structure
and source context.
