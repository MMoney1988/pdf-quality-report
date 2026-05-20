# Export Review Bundle

Creates a static folder of existing PQR review artifacts from `normalized_blocks.json`.

Use it when you want one handoff folder for human review instead of running each export command separately.

## Command

```bash
python -m pdf_quality_report.review_bundle \
  --input examples/mdpi_pdf_elements/page_012/normalized_blocks.json \
  --output-dir /tmp/page_012_pqr_review_bundle
```

If the package entry point is installed:

```bash
pdf-quality-review-bundle \
  --input examples/mdpi_pdf_elements/page_012/normalized_blocks.json \
  --output-dir /tmp/page_012_pqr_review_bundle
```

`--out-dir` is available as a short alias for `--output-dir`.

## What The Bundle Contains

The output directory contains:

- `README.md`: bundle summary and file guide
- `quality_report.md`: deterministic quality report with GO/REVIEW/BLOCK decision
- `review_findings.md`: WARN/FAIL details with source context when available
- `output.md`: clean Markdown export from normalized blocks
- `chunk_records.jsonl`: provenance-preserving chunk records
- `chunk_review.md`: human-reviewable Markdown view of chunk records

The command overwrites these known bundle files if they already exist. Unrelated files in the output directory are left
untouched.

The bundle does not copy the source PDF or `normalized_blocks.json`.

## Exit Behavior

The command exits with `0` when all bundle files are written, even if the quality-report decision is `REVIEW` or
`BLOCK`. Input or output errors return `1`.

## What This Does Not Do

- It does not add new parser-output checks.
- It does not approve, correct, or remove blocks.
- It does not create a ZIP file or manifest schema.
- It is not a workflow system, task tracker, dashboard, or approval process.
- It does not validate OCR accuracy, table reconstruction, parser correctness, or downstream readiness.
