from __future__ import annotations

import json
from pathlib import Path

from pdf_quality_report.to_markdown import (
    blocks_to_markdown,
    convert_uif_to_markdown,
    main,
)

INVALID_FOOTNOTE_MARKER = "[" + "^" + "]:"


def _block(block_id: str, block_type: str = "paragraph", text: str = "Some text.", **kwargs) -> dict:
    block = {
        "id": block_id,
        "type": block_type,
        "page_number": 6,
        "bbox": [1.0, 2.0, 3.0, 4.0],
        "relationships": [],
        "reading_order_index": 0,
        "content": {"text": text, "spans": []},
        "provenance": {
            "parser_backend": "docling",
            "docling_schema": "DoclingDocument",
            "docling_document_version": "1.10.0",
            "raw_docling_ref": "#/texts/1",
            "raw_docling_label": "text",
            "raw_docling_bbox": {"l": 1.0, "b": 2.0, "r": 3.0, "t": 4.0, "coord_origin": "BOTTOMLEFT"},
            "bbox_coord_origin": "BOTTOMLEFT",
            "bbox_unit": "pt",
            "source_pdf": "sample.pdf",
            "source_pdf_hash": "abc123",
        },
    }
    block.update(kwargs)
    return block


def test_paragraph_becomes_plain_text() -> None:
    blocks = [_block("p6-texts-60", text="This is a paragraph.")]
    md = blocks_to_markdown(blocks, include_source_refs=False)
    assert "This is a paragraph." in md
    assert md.strip() == "This is a paragraph."


def test_heading_gets_hash_prefix() -> None:
    blocks = [_block("p6-texts-62", "heading", "4. Problem Definition", level=1)]
    md = blocks_to_markdown(blocks, include_source_refs=False)
    assert "# 4. Problem Definition" in md


def test_heading_level_2() -> None:
    blocks = [_block("p6-texts-62", "heading", "4.1 Sub Section", level=2)]
    md = blocks_to_markdown(blocks, include_source_refs=False)
    assert "## 4.1 Sub Section" in md


def test_list_item_gets_dash_prefix() -> None:
    blocks = [_block("p6-texts-70", "list_item_text", "First item in a list.")]
    md = blocks_to_markdown(blocks, include_source_refs=False)
    assert "- First item in a list." in md


def test_caption_gets_italic() -> None:
    blocks = [_block("p6-texts-80", "caption", "Figure 1. Overview.")]
    md = blocks_to_markdown(blocks, include_source_refs=False)
    assert "*Figure 1. Overview.*" in md


def test_footnote_gets_deterministic_id() -> None:
    blocks = [_block("p6-texts-123", "footnote", "Footnote text.")]
    md = blocks_to_markdown(blocks, include_source_refs=False)
    assert md.strip() == "[^p6-texts-123]: Footnote text."
    assert INVALID_FOOTNOTE_MARKER not in md


def test_footnote_without_usable_id_renders_plain_text() -> None:
    missing_id = _block("p6-texts-123", "footnote", "Fallback footnote text.")
    missing_id.pop("id")
    blocks = [
        missing_id,
        _block("", "footnote", "Fallback footnote text."),
        _block("unknown", "footnote", "Fallback footnote text."),
    ]

    for block in blocks:
        md = blocks_to_markdown([block], include_source_refs=False)
        assert md.strip() == "Fallback footnote text."
        assert INVALID_FOOTNOTE_MARKER not in md
        assert "[^unknown]:" not in md


def test_header_footer_filtered_by_default() -> None:
    blocks = [
        _block("p6-texts-58", "header", "Technologies 2019, 7, 65"),
        _block("p6-texts-60", text="Real content here."),
        _block("p6-texts-59", "footer", "6 of 19"),
    ]
    md = blocks_to_markdown(blocks, include_source_refs=False)
    assert "Technologies" not in md
    assert "6 of 19" not in md
    assert "Real content here." in md


def test_header_footer_included_when_requested() -> None:
    blocks = [
        _block("p6-texts-58", "header", "Technologies 2019, 7, 65"),
        _block("p6-texts-60", text="Real content here."),
    ]
    md = blocks_to_markdown(blocks, include_noise=True, include_source_refs=False)
    assert "Technologies" in md


def test_short_fragments_skipped_by_default() -> None:
    blocks = [
        _block("p12-texts-601", text="0.5"),
        _block("p12-texts-607", text="(a)"),
        _block("p6-texts-60", text="Real content here."),
    ]
    md = blocks_to_markdown(blocks, include_source_refs=False)
    assert "0.5" not in md
    assert "(a)" not in md
    assert "Real content here." in md


def test_short_fragments_included_when_requested() -> None:
    blocks = [
        _block("p12-texts-601", text="0.5"),
        _block("p6-texts-60", text="Real content here."),
    ]
    md = blocks_to_markdown(blocks, include_source_refs=False, skip_short_fragments=False)
    assert "0.5" in md


def test_source_refs_added_as_html_comments() -> None:
    blocks = [_block("p6-texts-60", text="Content block.")]
    md = blocks_to_markdown(blocks, include_source_refs=True)
    assert "<!-- p6-texts-60 | page 6 | paragraph -->" in md
    assert "Content block." in md


def test_unknown_block_type_renders_plain_text_with_source_ref() -> None:
    blocks = [_block("p6-equations-1", "equation", "E = mc^2")]
    md = blocks_to_markdown(blocks, include_source_refs=True)
    assert "<!-- p6-equations-1 | page 6 | equation -->" in md
    assert "E = mc^2" in md


def test_image_block_becomes_comment() -> None:
    block = _block("p6-pictures-4", "image", "")
    block["base64"] = None
    md = blocks_to_markdown([block], include_source_refs=True)
    assert "<!-- image: p6-pictures-4, page 6 -->" in md


def test_page_separator_between_pages() -> None:
    blocks = [
        _block("p6-texts-60", text="Page six content.", page_number=6),
        _block("p7-texts-70", text="Page seven content.", page_number=7),
    ]
    md = blocks_to_markdown(blocks, include_source_refs=True)
    assert "---" in md
    assert "Page six content." in md
    assert "Page seven content." in md


def test_front_matter_from_metadata() -> None:
    doc = {
        "metadata": {
            "source_type": "pdf",
            "source_identifier": "test.pdf",
            "parser_backend": "docling",
        },
        "blocks": [_block("p6-texts-60", text="Content.")],
    }
    md = convert_uif_to_markdown(doc, include_source_refs=False)
    assert md.startswith("---\n")
    assert "source_type: pdf" in md
    assert "source_identifier: test.pdf" in md
    assert "Content." in md


def test_empty_blocks_produce_empty_output() -> None:
    md = blocks_to_markdown([], include_source_refs=False)
    assert md == ""


def test_non_list_blocks_are_handled_cleanly() -> None:
    doc = {"metadata": {}, "blocks": {"not": "a list"}}
    md = convert_uif_to_markdown(doc, include_source_refs=False)
    assert md == ""


def test_cli_writes_markdown_file(tmp_path: Path) -> None:
    uif_path = tmp_path / "blocks.json"
    output_path = tmp_path / "output.md"
    doc = {
        "metadata": {"source_type": "pdf"},
        "blocks": [_block("p6-texts-60", text="CLI test content.")],
    }
    uif_path.write_text(json.dumps(doc), encoding="utf-8")

    result = main(["--input", str(uif_path), "--output", str(output_path)])

    assert result == 0
    assert output_path.exists()
    text = output_path.read_text(encoding="utf-8")
    assert "CLI test content." in text
    assert "---" in text  # front matter


def test_cli_out_alias_writes_markdown_file(tmp_path: Path) -> None:
    uif_path = tmp_path / "blocks.json"
    output_path = tmp_path / "output.md"
    doc = {
        "metadata": {"source_type": "pdf"},
        "blocks": [_block("p6-texts-60", text="CLI alias content.")],
    }
    uif_path.write_text(json.dumps(doc), encoding="utf-8")

    result = main(["--input", str(uif_path), "--out", str(output_path)])

    assert result == 0
    assert output_path.exists()
    assert "CLI alias content." in output_path.read_text(encoding="utf-8")


def test_cli_no_source_refs_flag(tmp_path: Path) -> None:
    uif_path = tmp_path / "blocks.json"
    output_path = tmp_path / "output.md"
    doc = {
        "metadata": {},
        "blocks": [_block("p6-texts-60", text="No refs test.")],
    }
    uif_path.write_text(json.dumps(doc), encoding="utf-8")

    result = main(["--input", str(uif_path), "--output", str(output_path), "--no-source-refs"])

    assert result == 0
    text = output_path.read_text(encoding="utf-8")
    assert "<!--" not in text
    assert "No refs test." in text


def test_cli_exports_page_012_example(tmp_path: Path) -> None:
    input_path = Path("examples/mdpi_pdf_elements/page_012/normalized_blocks.json")
    output_path = tmp_path / "page_012.md"

    result = main(["--input", str(input_path), "--output", str(output_path)])

    assert result == 0
    text = output_path.read_text(encoding="utf-8")
    assert "<!-- p12-texts-" in text
    assert "page 12" in text
