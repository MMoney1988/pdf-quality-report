# Minimal PDF Quality Report

## Summary
- total_blocks: 82
- hard_failures: 0
- warnings: 2

## Noise / Layout Signals
Diagnostic signals only; these do not add hard failures or warnings.

- table_marker_artifacts: 0
- running_furniture_blocks: 2
- visual_anchor_blocks: 1
- ambiguous_image_blocks: 1

Details:
- running_furniture: p12-texts-555: type=header, text='Technologies 2019 , 7 , 65'
- running_furniture: p12-texts-556: type=header, text='12 of 19'
- visual_anchor: p12-pictures-14: type=image, text=<empty>
- ambiguous_image: p12-pictures-14: type=image, text=<empty>

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

79 content-like block(s), 3 secondary/noise candidate block(s)

- total_blocks=82
- content_candidate_blocks=79
- secondary_or_noise_blocks=3
- type_distribution={'caption': 1, 'header': 2, 'heading': 1, 'image': 1, 'paragraph': 77}

## Text Usefulness
WARN

28 text usefulness warning(s)

- p12-texts-581: very short text: '111'
- p12-texts-601: very short text: '0.5'
- p12-texts-605: very short text: '225'
- p12-texts-604: very short text: '225'
- p12-texts-602: very short text: '25'
- p12-texts-603: very short text: '175'
- p12-texts-606: very short text: '275'
- p12-texts-607: very short text: '(a)'
- p12-texts-608: very short text: '0.5'
- p12-texts-610: very short text: '.02'
- p12-texts-611: very short text: '01'
- p12-texts-612: very short text: '75'
- p12-texts-613: very short text: '125'
- p12-texts-614: very short text: '175'
- p12-texts-615: very short text: '225'
- p12-texts-618: very short text: '125'
- p12-texts-619: very short text: '175'
- p12-texts-621: very short text: '325'
- p12-texts-616: very short text: '275'
- p12-texts-617: very short text: '325'
- p12-texts-622: very short text: '(c)'
- p12-texts-623: very short text: '(d)'
- duplicate normalized text across blocks: p12-texts-601, p12-texts-608
- duplicate normalized text across blocks: p12-texts-603, p12-texts-614, p12-texts-619
- duplicate normalized text across blocks: p12-texts-604, p12-texts-605, p12-texts-615
- duplicate normalized text across blocks: p12-texts-606, p12-texts-616
- duplicate normalized text across blocks: p12-texts-613, p12-texts-618
- duplicate normalized text across blocks: p12-texts-617, p12-texts-621
