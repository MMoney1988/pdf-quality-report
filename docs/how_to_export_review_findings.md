# Export Review Findings

Renders WARN and FAIL quality-check details as a human-reviewable Markdown findings list.

Use it after creating normalized blocks when you want a compact review artifact that points reviewers to the
checks, details, and source blocks that may need inspection.

This export reads `normalized_blocks.json`, runs the existing quality checks, and writes `review_findings.md`.
It does not add new checks or change the quality-report decision.

## Command

```bash
python -m pdf_quality_report.review_findings \
  --input examples/mdpi_pdf_elements/page_012/normalized_blocks.json \
  --output /tmp/page_012_review_findings.md
```

If the package entry point is installed:

```bash
pdf-quality-review-findings \
  --input examples/mdpi_pdf_elements/page_012/normalized_blocks.json \
  --output /tmp/page_012_review_findings.md
```

`--out` is available as a short alias for `--output`.

## What The Output Contains

The Markdown includes:

- summary counts for decision, warnings, hard failures, and review findings
- one section for each WARN or FAIL check
- check details copied from the quality report
- source context when a block ID can be matched to the normalized blocks
- supporting layout signals when present

`review_findings` counts WARN/FAIL detail items, or one check-level item when a warning or failure only has
metric-style details. It is not the number of WARN/FAIL checks.

Source context is best-effort because current check details are text lines. If a detail does not name a block ID, the
finding is still shown without block-level enrichment.

The command exits with `0` when the Markdown file is written successfully, even if review findings exist. Input or
output errors return `1`.

## What This Does Not Do

- It is not a workflow system or task tracker.
- It does not add new parser-output checks.
- It does not correct, approve, or remove blocks.
- It does not create a JSON findings contract.
- It does not validate OCR accuracy, table reconstruction, parser correctness, or downstream readiness.

The output is a static review aid. The quality report remains the decision source.
