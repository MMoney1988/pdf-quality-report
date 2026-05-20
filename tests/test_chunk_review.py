from __future__ import annotations

import json
from pathlib import Path

from pdf_quality_report.chunk import ChunkRecord
from pdf_quality_report.chunk_review import main, render_chunk_review_markdown


def _record(
    chunk_id: str,
    text: str = "Useful chunk text.",
    *,
    page_numbers: list[int] | None = None,
    section_path: list[str] | None = None,
    block_ids: list[str] | None = None,
    bbox_refs: list[dict] | None = None,
    citation: str | None = None,
) -> ChunkRecord:
    resolved_page_numbers = page_numbers if page_numbers is not None else [6]
    resolved_section_path = section_path if section_path is not None else ["4. Problem Definition"]
    resolved_block_ids = block_ids if block_ids is not None else ["p6-texts-62", "p6-texts-63"]
    return ChunkRecord(
        doc_id=chunk_id,
        text=text,
        meta={
            "schema_version": "chunk_record_v1",
            "chunk_id": chunk_id,
            "block_ids": resolved_block_ids,
            "page_numbers": resolved_page_numbers,
            "section_heading": resolved_section_path[-1] if resolved_section_path else None,
            "section_heading_block_id": "p6-texts-62" if resolved_section_path else None,
            "section_path": resolved_section_path,
            "section_path_block_ids": ["p6-texts-62"] if resolved_section_path else [],
            "citation": citation if citation is not None else "sample.pdf, p.6, §4. Problem Definition",
            "source_identifier": "sample.pdf",
            "source_pdf_hash": "abc123",
            "bbox_refs": bbox_refs
            or [
                {"block_id": resolved_block_ids[0], "page_number": resolved_page_numbers[0], "bbox": [1, 2, 3, 4]},
                {"block_id": resolved_block_ids[-1], "page_number": resolved_page_numbers[0], "bbox": [5, 6, 7, 8]},
            ],
        },
    )


def _block(
    block_id: str,
    block_type: str = "paragraph",
    text: str = "Useful text.",
    *,
    page_number: int = 6,
    reading_order_index: int = 0,
) -> dict:
    return {
        "id": block_id,
        "type": block_type,
        "page_number": page_number,
        "bbox": [1.0, 2.0, 3.0, 4.0],
        "relationships": [],
        "reading_order_index": reading_order_index,
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
            "source_pdf": "fallback.pdf",
            "source_pdf_hash": "fallback-hash",
        },
    }


def _normalized_document(blocks: list[dict]) -> dict:
    return {
        "metadata": {"source_identifier": "sample.pdf", "source_pdf_hash": "abc123"},
        "blocks": blocks,
    }


def test_empty_chunk_review_has_stable_summary() -> None:
    markdown = render_chunk_review_markdown([])

    assert markdown.startswith("# Chunk Review")
    assert "- **Chunks:** 0" in markdown
    assert "- **Pages covered:** none" in markdown
    assert "- **Total characters:** 0" in markdown
    assert "- **Distinct nearest headings:** 0" in markdown
    assert "_No chunks exported._" in markdown


def test_chunk_review_renders_core_record_metadata() -> None:
    markdown = render_chunk_review_markdown([_record("chunk-p6-texts-62")])

    assert "### chunk-p6-texts-62" in markdown
    assert "**Citation:** sample.pdf, p.6, §4. Problem Definition" in markdown
    assert "**Section path:** 4. Problem Definition" in markdown
    assert "**Pages:** 6" in markdown
    assert "**Blocks:** p6-texts-62, p6-texts-63" in markdown
    assert "**Characters:** 18" in markdown
    assert "**BBox refs:** 2" in markdown
    assert "> Useful chunk text." in markdown


def test_chunk_review_renders_nested_section_path() -> None:
    markdown = render_chunk_review_markdown(
        [
            _record(
                "chunk-p6-texts-70",
                section_path=["4. Problem Definition", "4.1 Architecture", "4.1.2 Detail"],
                citation="sample.pdf, p.6, §4.1.2 Detail",
            )
        ]
    )

    assert "**Section path:** 4. Problem Definition -> 4.1 Architecture -> 4.1.2 Detail" in markdown


def test_chunk_review_handles_missing_citation() -> None:
    markdown = render_chunk_review_markdown([_record("chunk-p6-texts-62", citation="")])

    assert "**Citation:** none" in markdown


def test_chunk_review_preserves_record_order_and_separators() -> None:
    markdown = render_chunk_review_markdown(
        [
            _record("chunk-p6-texts-62", "First."),
            _record("chunk-p6-texts-64", "Second."),
        ]
    )

    assert markdown.index("### chunk-p6-texts-62") < markdown.index("### chunk-p6-texts-64")
    assert "\n---\n\n### chunk-p6-texts-64" in markdown


def test_chunk_review_preview_is_deterministically_truncated() -> None:
    long_text = "A" * 210

    markdown = render_chunk_review_markdown([_record("chunk-p6-texts-62", long_text)])

    assert f"> {'A' * 200}..." in markdown
    assert f"> {'A' * 201}" not in markdown


def test_chunk_review_prefixes_multiline_preview_as_blockquote() -> None:
    markdown = render_chunk_review_markdown([_record("chunk-p6-texts-62", "First line.\n\nSecond line.")])

    assert "> First line.\n>\n> Second line." in markdown


def test_chunk_review_handles_missing_section_path() -> None:
    markdown = render_chunk_review_markdown(
        [
            _record(
                "chunk-p6-texts-60",
                section_path=[],
                block_ids=["p6-texts-60"],
                citation="sample.pdf, p.6",
            )
        ]
    )

    assert "**Section path:** none" in markdown
    assert "**Citation:** sample.pdf, p.6" in markdown


def test_chunk_review_output_is_deterministic() -> None:
    records = [_record("chunk-p6-texts-62"), _record("chunk-p6-texts-64", "Second.")]

    assert render_chunk_review_markdown(records) == render_chunk_review_markdown(records)


def test_cli_writes_chunk_review_markdown(tmp_path: Path) -> None:
    input_path = tmp_path / "blocks.json"
    output_path = tmp_path / "chunk_review.md"
    input_path.write_text(
        json.dumps(
            _normalized_document(
                [
                    _block("p6-texts-62", "heading", "4. Problem Definition", reading_order_index=1),
                    _block("p6-texts-63", "paragraph", "Paragraph text.", reading_order_index=2),
                ]
            )
        ),
        encoding="utf-8",
    )

    result = main(["--input", str(input_path), "--output", str(output_path)])

    assert result == 0
    markdown = output_path.read_text(encoding="utf-8")
    assert "### chunk-p6-texts-62" in markdown
    assert "**Citation:** sample.pdf, p.6, §4. Problem Definition" in markdown


def test_cli_out_alias_writes_chunk_review_markdown(tmp_path: Path) -> None:
    input_path = tmp_path / "blocks.json"
    output_path = tmp_path / "chunk_review.md"
    input_path.write_text(json.dumps(_normalized_document([_block("p6-texts-60")])), encoding="utf-8")

    result = main(["--input", str(input_path), "--out", str(output_path)])

    assert result == 0
    assert output_path.exists()


def test_cli_options_are_passed_to_chunk_builder(tmp_path: Path) -> None:
    input_path = tmp_path / "blocks.json"
    output_path = tmp_path / "chunk_review.md"
    input_path.write_text(
        json.dumps(
            _normalized_document(
                [
                    _block("p6-texts-58", "header", "Header", reading_order_index=1),
                    _block("p6-texts-59", "paragraph", "0.5", reading_order_index=2),
                    _block("p6-texts-60", "paragraph", "Body text.", reading_order_index=3),
                ]
            )
        ),
        encoding="utf-8",
    )

    result = main(
        [
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--max-chars",
            "50",
            "--include-noise",
            "--include-short",
        ]
    )

    assert result == 0
    markdown = output_path.read_text(encoding="utf-8")
    assert "> Header" in markdown
    assert "> 0.5" in markdown


def test_invalid_json_root_returns_exit_code_1(tmp_path: Path, capsys) -> None:
    input_path = tmp_path / "bad.json"
    output_path = tmp_path / "chunk_review.md"
    input_path.write_text("[]", encoding="utf-8")

    result = main(["--input", str(input_path), "--output", str(output_path)])

    assert result == 1
    assert "Error: input JSON root must be an object" in capsys.readouterr().err
    assert not output_path.exists()


def test_non_list_blocks_returns_exit_code_1(tmp_path: Path, capsys) -> None:
    input_path = tmp_path / "bad.json"
    output_path = tmp_path / "chunk_review.md"
    input_path.write_text(json.dumps({"metadata": {}, "blocks": {"not": "a list"}}), encoding="utf-8")

    result = main(["--input", str(input_path), "--output", str(output_path)])

    assert result == 1
    assert "Error: top-level field `blocks` must be a list" in capsys.readouterr().err
    assert not output_path.exists()


def test_cli_exports_page_006_and_page_012_examples(tmp_path: Path) -> None:
    for page in ("page_006", "page_012"):
        input_path = Path(f"examples/mdpi_pdf_elements/{page}/normalized_blocks.json")
        output_path = tmp_path / f"{page}_chunk_review.md"

        result = main(["--input", str(input_path), "--output", str(output_path)])

        assert result == 0
        markdown = output_path.read_text(encoding="utf-8")
        assert markdown.startswith("# Chunk Review")
        assert "## Chunks" in markdown
        assert "### chunk-" in markdown
