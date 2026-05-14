# PDF Parser Output Quality Report

## Summary
- total_blocks: 82
- hard_failures: 0
- warnings: 2
- decision: REVIEW

## Interpretation
Why REVIEW? The hard structure checks passed, but warning checks need review in this report: Content vs Noise Ratio and Text Usefulness. Warnings are decision-level findings. Noise / Layout Signals provide supporting evidence and are counted separately.

- Content vs Noise Ratio is WARN: The report treats 79 blocks as possible main document text. The report treats 3 blocks as possible layout or noise elements.
- 2 blocks are typed as headers: p12-texts-555 and p12-texts-556. 1 block is typed as image: p12-pictures-14.
- Text Usefulness is WARN: This report found 22 very short extracted text values and 6 repeated-text groups.
- These findings come from extracted text blocks. Quoted values are the actual extracted text values, and block IDs show where they came from in the normalized output.
- In this report, very short means normalized text with 3 characters or fewer.
- Very short numeric fragments such as '111', '0.5', and '225' are common in chart ticks, figure labels, or repeated headers, footers, or page labels.
- Short label fragments such as '(a)', '(c)', and '(d)' are common in subfigure labels or other layout labels.
- Repeated text appears in 6 group(s). Examples: Repeated text value '0.5' appears in block IDs p12-texts-601 and p12-texts-608; Repeated text value '175' appears in block IDs p12-texts-603, p12-texts-614, and p12-texts-619; Repeated text value '225' appears in block IDs p12-texts-604, p12-texts-605, and p12-texts-615.
- Layout/noise signals point to headers, footers, images, labels, or other non-main-text elements that may need review before reuse.
- Block ID p12-pictures-14 is an image block with no extracted text context.

## Noise / Layout Signals
These signals identify page-layout elements that may need review before reusing the extracted text. They are supporting evidence and are counted separately from warning checks.

- table_marker_artifacts: 0
- running_furniture_blocks: 2
- visual_anchor_blocks: 1
- ambiguous_image_blocks: 1

The same image block can appear in both `visual_anchor_blocks` and `ambiguous_image_blocks`: `visual_anchor_blocks` counts image blocks, while `ambiguous_image_blocks` flags image blocks with no extracted text context.

Details:
- running_furniture: p12-texts-555: type=header, text='Technologies 2019 , 7 , 65'
- running_furniture: p12-texts-556: type=header, text='12 of 19'
- visual_anchor: p12-pictures-14: type=image, text=<empty>
- ambiguous_image: p12-pictures-14: type=image, text=<empty>

## Check Results
Each section below is a separate check.

- Required Field Coverage checks whether required JSON fields are present.
- Provenance Completeness checks whether source, page, and bounding-box metadata is present.
- BBox Sanity checks whether bounding boxes look structurally valid.
- Content vs Noise Ratio checks how much extracted content looks like main text versus layout/noise.
- Text Usefulness flags very short or repeated text fragments.
- Text Extraction Health checks extracted-text availability, not extracted-text correctness.

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
- repeated text value '0.5' appears in block IDs: p12-texts-601, p12-texts-608
- repeated text value '175' appears in block IDs: p12-texts-603, p12-texts-614, p12-texts-619
- repeated text value '225' appears in block IDs: p12-texts-604, p12-texts-605, p12-texts-615
- repeated text value '275' appears in block IDs: p12-texts-606, p12-texts-616
- repeated text value '125' appears in block IDs: p12-texts-613, p12-texts-618
- repeated text value '325' appears in block IDs: p12-texts-617, p12-texts-621

## Text Extraction Health
PASS

extracted text availability checks passed

- text_bearing_blocks=81
- non_empty_text_blocks=81
- empty_text_blocks=0
- total_text_chars=4482
- image_blocks=1
- empty_text_block_ratio=0.000

## Recommended Review Actions
Because the decision is REVIEW, inspect short/repeated text fragments and layout/noise signals before using this output for Markdown export, RAG ingestion preparation, or manual extraction.
If the listed items are expected chart labels, headers, footers, or figure labels, keep, exclude, or describe them according to the downstream use case. If they point to missing or incorrect content, adjust extraction before reuse.
The report identifies parser-output findings; it does not automatically fix, remove, or approve blocks.
