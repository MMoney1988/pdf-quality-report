# PDF Parser Output Quality Report

## Summary
- total_blocks: 8
- hard_failures: 0
- warnings: 1
- decision: REVIEW

## Interpretation
Why REVIEW? The hard structure checks passed, but warning check needs review in this report: Content vs Noise Ratio. Warnings are decision-level findings. Noise / Layout Signals provide supporting evidence and are counted separately.

- Content vs Noise Ratio is WARN: The report treats 6 blocks as possible main document text. The report treats 2 blocks as possible layout or noise elements.
- 2 blocks are typed as headers: p6-texts-58 and p6-texts-59.
- Layout/noise signals point to headers, footers, images, labels, or other non-main-text elements that may need review before reuse.

## Noise / Layout Signals
These signals identify page-layout elements that may need review before reusing the extracted text. They are supporting evidence and are counted separately from warning checks.

- table_marker_artifacts: 0
- running_furniture_blocks: 2
- visual_anchor_blocks: 0
- ambiguous_image_blocks: 0

Details:
- running_furniture: p6-texts-58: type=header, text='Technologies 2019 , 7 , 65'
- running_furniture: p6-texts-59: type=header, text='6 of 19'

## Check Results
Each section below is a separate check.

- Required Field Coverage checks whether required JSON fields are present.
- Provenance Completeness checks whether source, page, and bounding-box metadata is present.
- BBox Sanity checks whether bounding boxes look structurally valid.
- Content vs Noise Ratio checks how much extracted content looks like main text versus layout/noise.
- Text Usefulness flags very short or repeated text fragments.

## Required Field Coverage
PASS

all required fields present

## Provenance Completeness
PASS

provenance checks passed

## BBox Sanity
PASS

all bboxes sane

## Content vs Noise Ratio
WARN

6 content-like block(s), 2 secondary/noise candidate block(s)

- total_blocks=8
- content_candidate_blocks=6
- secondary_or_noise_blocks=2
- type_distribution={'header': 2, 'heading': 1, 'paragraph': 5}

## Text Usefulness
PASS

text usefulness checks passed

## Recommended Review Actions
Because the decision is REVIEW, inspect layout/noise signals before using this output for Markdown export, RAG ingestion preparation, or manual extraction.
If the listed items are expected chart labels, headers, footers, or figure labels, keep, exclude, or describe them according to the downstream use case. If they point to missing or incorrect content, adjust extraction before reuse.
The report identifies parser-output findings; it does not automatically fix, remove, or approve blocks.
