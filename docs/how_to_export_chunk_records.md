# Export Chunk Records

## What this does

Converts `normalized_blocks.json` into JSONL chunk records.

This export step comes after conversion. It does not read PDFs directly. It reads normalized blocks that already contain
text, block IDs, page numbers, bounding boxes, and source provenance.

Use it when you want a compact reviewable artifact that preserves source references for downstream review or
retrieval-oriented preparation.

## What this does not do

No OCR. No table reconstruction. No embeddings. No vector store. No retrieval pipeline. No LLM answer generation.

## Command

```bash
python -m pdf_quality_report.chunk \
  --input examples/mdpi_pdf_elements/page_006/normalized_blocks.json \
  --output /tmp/page_006_chunks.jsonl
```

```bash
pdf-quality-chunk \
  --input examples/mdpi_pdf_elements/page_006/normalized_blocks.json \
  --output /tmp/page_006_chunks.jsonl
```

## Output

The export writes one JSON object per line. Each record contains:

- `doc_id`, equal to the stable chunk ID
- `text`, joined from one or more normalized text blocks
- `meta.schema_version`, currently `chunk_record_v0`
- `meta.block_ids`, `meta.page_numbers`, and `meta.bbox_refs`
- `meta.section_heading` and `meta.section_heading_block_id` when a heading applies
- `meta.source_identifier` and `meta.source_pdf_hash`

By default, headers, footers, images, empty text, and very short non-heading fragments are skipped. Tables are exported
only when the normalized table block already has `content.text`.

## When to use it

Use this after the quality report if the normalized blocks are structurally usable and you need source-preserving chunk
records for review or retrieval-oriented preparation.
