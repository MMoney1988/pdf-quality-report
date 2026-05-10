# Minimal PDF Quality Report

## Summary
- total_blocks: 8
- hard_failures: 0
- warnings: 1
- decision: REVIEW

## Interpretation
Derived from recorded checks and diagnostic signals. This explains the report decision; it does not add new checks or change the decision.

- Content vs Noise Ratio is WARN: 6 body-text candidate block(s) and 2 layout/non-body block(s) were found.
- Layout/non-body examples: 2 header/footer-like block(s) (p6-texts-58 and p6-texts-59).
- Diagnostic layout signals are present and do not change the decision.

## Noise / Layout Signals
Diagnostic signals only; these do not add hard failures or warnings.

- table_marker_artifacts: 0
- running_furniture_blocks: 2
- visual_anchor_blocks: 0
- ambiguous_image_blocks: 0

Details:
- running_furniture: p6-texts-58: type=header, text='Technologies 2019 , 7 , 65'
- running_furniture: p6-texts-59: type=header, text='6 of 19'

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
