from __future__ import annotations

import json
from pathlib import Path

from pdf_quality_report.chunk import (
    ChunkOptions,
    NormalizedDocument,
    build_chunk_records,
    main,
    write_chunk_records_jsonl,
)


def _block(
    block_id: str,
    block_type: str = "paragraph",
    text: str = "Useful text.",
    *,
    page_number: int = 6,
    reading_order_index: int = 0,
    bbox: list[float] | None = None,
    level: int | None = None,
) -> dict:
    block = {
        "id": block_id,
        "type": block_type,
        "page_number": page_number,
        "bbox": bbox or [1.0, 2.0, 3.0, 4.0],
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
    if level is not None:
        block["level"] = level
    return block


def _document(blocks: list[dict], metadata: dict | None = None) -> NormalizedDocument:
    return NormalizedDocument(
        metadata=metadata
        or {
            "source_identifier": "sample.pdf",
            "source_pdf_hash": "abc123",
        },
        blocks=blocks,
    )


def _json_lines(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_jsonl_record_contains_required_shape(tmp_path: Path) -> None:
    records = build_chunk_records(_document([_block("p6-texts-62", "heading", "4. Problem Definition")]))
    output_path = tmp_path / "chunks.jsonl"

    write_chunk_records_jsonl(records, output_path)

    line = _json_lines(output_path)[0]
    assert set(line) == {"doc_id", "text", "meta"}
    assert line["doc_id"] == "chunk-p6-texts-62"
    assert line["text"] == "4. Problem Definition"
    assert line["meta"]["schema_version"] == "chunk_record_v1"
    assert line["meta"]["chunk_id"] == line["doc_id"]


def test_paragraphs_are_grouped_under_nearest_heading() -> None:
    records = build_chunk_records(
        _document(
            [
                _block("p6-texts-62", "heading", "4. Problem Definition", reading_order_index=1),
                _block("p6-texts-63", "paragraph", "First paragraph.", reading_order_index=2),
                _block("p6-texts-64", "paragraph", "Second paragraph.", reading_order_index=3),
            ]
        )
    )

    assert len(records) == 1
    assert records[0].text == "4. Problem Definition\n\nFirst paragraph.\n\nSecond paragraph."
    assert records[0].meta["section_heading"] == "4. Problem Definition"
    assert records[0].meta["section_heading_block_id"] == "p6-texts-62"
    assert records[0].meta["section_path"] == ["4. Problem Definition"]
    assert records[0].meta["section_path_block_ids"] == ["p6-texts-62"]
    assert records[0].meta["block_ids"] == ["p6-texts-62", "p6-texts-63", "p6-texts-64"]


def test_nested_headings_create_section_path() -> None:
    records = build_chunk_records(
        _document(
            [
                _block("p6-texts-62", "heading", "4. Problem Definition", level=1, reading_order_index=1),
                _block("p6-texts-63", "paragraph", "Root paragraph.", reading_order_index=2),
                _block("p6-texts-64", "heading", "4.1 Architecture", level=2, reading_order_index=3),
                _block("p6-texts-65", "paragraph", "Nested paragraph.", reading_order_index=4),
                _block("p6-texts-66", "heading", "4.1.1 Detail", level=3, reading_order_index=5),
                _block("p6-texts-67", "paragraph", "Deep paragraph.", reading_order_index=6),
            ]
        )
    )

    assert [record.meta["section_path"] for record in records] == [
        ["4. Problem Definition"],
        ["4. Problem Definition", "4.1 Architecture"],
        ["4. Problem Definition", "4.1 Architecture", "4.1.1 Detail"],
    ]
    assert records[2].meta["section_path_block_ids"] == ["p6-texts-62", "p6-texts-64", "p6-texts-66"]


def test_heading_level_field_takes_precedence_over_regex() -> None:
    records = build_chunk_records(
        _document(
            [
                _block("p6-texts-62", "heading", "4. Problem Definition", level=1, reading_order_index=1),
                _block("p6-texts-63", "heading", "4.1 Looks Nested But Is Top Level", level=1, reading_order_index=2),
                _block("p6-texts-64", "paragraph", "Paragraph.", reading_order_index=3),
            ]
        )
    )

    assert records[1].meta["section_path"] == ["4.1 Looks Nested But Is Top Level"]


def test_numbered_heading_regex_fallback_sets_nested_levels() -> None:
    records = build_chunk_records(
        _document(
            [
                _block("p6-texts-62", "heading", "4. Problem Definition", reading_order_index=1),
                _block("p6-texts-63", "heading", "4.1 Architecture", reading_order_index=2),
                _block("p6-texts-64", "heading", "4.1.2 Detail", reading_order_index=3),
                _block("p6-texts-65", "paragraph", "Paragraph.", reading_order_index=4),
            ]
        )
    )

    assert records[-1].meta["section_path"] == [
        "4. Problem Definition",
        "4.1 Architecture",
        "4.1.2 Detail",
    ]


def test_unnumbered_heading_defaults_to_level_one() -> None:
    records = build_chunk_records(
        _document(
            [
                _block("p6-texts-62", "heading", "4. Problem Definition", level=1, reading_order_index=1),
                _block("p6-texts-63", "heading", "Unnumbered Heading", reading_order_index=2),
                _block("p6-texts-64", "paragraph", "Paragraph.", reading_order_index=3),
            ]
        )
    )

    assert records[1].meta["section_path"] == ["Unnumbered Heading"]


def test_chunk_without_heading_context_gets_empty_section_path() -> None:
    records = build_chunk_records(_document([_block("p6-texts-63", "paragraph", "Paragraph.")]))

    assert records[0].meta["section_heading"] is None
    assert records[0].meta["section_heading_block_id"] is None
    assert records[0].meta["section_path"] == []
    assert records[0].meta["section_path_block_ids"] == []
    assert records[0].meta["citation"] == "sample.pdf, p.6"


def test_long_sections_split_only_at_block_boundaries() -> None:
    records = build_chunk_records(
        _document(
            [
                _block("p6-texts-62", "heading", "Section", reading_order_index=1),
                _block("p6-texts-63", "paragraph", "Alpha words", reading_order_index=2),
                _block("p6-texts-64", "paragraph", "Beta words", reading_order_index=3),
            ]
        ),
        ChunkOptions(max_chars=25),
    )

    assert [record.meta["block_ids"] for record in records] == [
        ["p6-texts-62", "p6-texts-63"],
        ["p6-texts-64"],
    ]
    assert records[0].text == "Section\n\nAlpha words"
    assert records[0].meta["section_path"] == ["Section"]
    assert records[1].text == "Beta words"
    assert records[1].meta["section_heading"] == "Section"
    assert records[1].meta["section_path"] == ["Section"]


def test_blocks_are_sorted_by_page_reading_order_then_input_order() -> None:
    records = build_chunk_records(
        _document(
            [
                _block("p7-texts-2", "paragraph", "Third.", page_number=7, reading_order_index=1),
                _block("p6-texts-2", "paragraph", "Second.", page_number=6, reading_order_index=2),
                _block("p6-texts-1", "paragraph", "First.", page_number=6, reading_order_index=1),
                _block("p7-texts-3", "paragraph", "Fourth.", page_number=7, reading_order_index=1),
            ]
        )
    )

    assert len(records) == 1
    assert records[0].text == "First.\n\nSecond.\n\nThird.\n\nFourth."
    assert records[0].meta["block_ids"] == ["p6-texts-1", "p6-texts-2", "p7-texts-2", "p7-texts-3"]


def test_chunk_output_is_deterministic_for_same_input() -> None:
    document = _document(
        [
            _block("p6-texts-62", "heading", "Section", reading_order_index=1),
            _block("p6-texts-63", "paragraph", "First paragraph.", reading_order_index=2),
            _block("p6-texts-64", "paragraph", "Second paragraph.", reading_order_index=3),
        ]
    )

    first = [record.to_json() for record in build_chunk_records(document)]
    second = [record.to_json() for record in build_chunk_records(document)]

    assert first == second


def test_single_block_over_max_chars_remains_own_chunk() -> None:
    long_text = "This paragraph is intentionally longer than the limit."

    records = build_chunk_records(
        _document([_block("p6-texts-63", "paragraph", long_text)]),
        ChunkOptions(max_chars=10),
    )

    assert len(records) == 1
    assert records[0].text == long_text
    assert records[0].meta["block_ids"] == ["p6-texts-63"]


def test_provenance_fields_are_preserved() -> None:
    records = build_chunk_records(
        _document(
            [
                _block("p6-texts-62", "heading", "Section", page_number=6, reading_order_index=1),
                _block(
                    "p7-texts-70",
                    "paragraph",
                    "Continued text.",
                    page_number=7,
                    reading_order_index=2,
                    bbox=[5.0, 6.0, 7.0, 8.0],
                ),
            ],
            metadata={"source_identifier": "article.pdf", "source_pdf_hash": "hash-123"},
        )
    )

    meta = records[0].meta
    assert meta["block_ids"] == ["p6-texts-62", "p7-texts-70"]
    assert meta["page_numbers"] == [6, 7]
    assert meta["source_identifier"] == "article.pdf"
    assert meta["source_pdf_hash"] == "hash-123"
    assert meta["section_path"] == ["Section"]
    assert meta["section_path_block_ids"] == ["p6-texts-62"]
    assert meta["citation"] == "article.pdf, pp.6-7, §Section"
    assert meta["bbox_refs"] == [
        {"block_id": "p6-texts-62", "page_number": 6, "bbox": [1.0, 2.0, 3.0, 4.0]},
        {"block_id": "p7-texts-70", "page_number": 7, "bbox": [5.0, 6.0, 7.0, 8.0]},
    ]


def test_header_footer_and_image_are_filtered_by_default() -> None:
    image = _block("p6-pictures-4", "image", "", reading_order_index=3)
    records = build_chunk_records(
        _document(
            [
                _block("p6-texts-58", "header", "Running header", reading_order_index=1),
                _block("p6-texts-60", "paragraph", "Body text.", reading_order_index=2),
                image,
                _block("p6-texts-59", "footer", "6 of 19", reading_order_index=4),
            ]
        )
    )

    assert len(records) == 1
    assert records[0].text == "Body text."
    assert records[0].meta["block_ids"] == ["p6-texts-60"]


def test_include_noise_includes_header_and_footer_text_but_not_images() -> None:
    image = _block("p6-pictures-4", "image", "ignored image text", reading_order_index=3)
    records = build_chunk_records(
        _document(
            [
                _block("p6-texts-58", "header", "Running header", reading_order_index=1),
                _block("p6-texts-60", "paragraph", "Body text.", reading_order_index=2),
                image,
                _block("p6-texts-59", "footer", "6 of 19", reading_order_index=4),
            ]
        ),
        ChunkOptions(include_noise=True),
    )

    assert len(records) == 1
    assert records[0].text == "Running header\n\nBody text.\n\n6 of 19"
    assert records[0].meta["block_ids"] == ["p6-texts-58", "p6-texts-60", "p6-texts-59"]


def test_short_non_heading_fragments_are_filtered_by_default() -> None:
    records = build_chunk_records(
        _document(
            [
                _block("p12-texts-601", "paragraph", "0.5", reading_order_index=1),
                _block("p12-texts-602", "heading", "8", reading_order_index=2),
                _block("p12-texts-603", "paragraph", "Long enough text.", reading_order_index=3),
            ]
        )
    )

    assert len(records) == 1
    assert records[0].text == "8\n\nLong enough text."
    assert "p12-texts-601" not in records[0].meta["block_ids"]


def test_include_short_includes_short_fragments() -> None:
    records = build_chunk_records(
        _document([_block("p12-texts-601", "paragraph", "0.5")]),
        ChunkOptions(include_short=True),
    )

    assert len(records) == 1
    assert records[0].text == "0.5"


def test_table_exports_only_existing_content_text() -> None:
    table_without_text = _block("p6-tables-2", "table", "", reading_order_index=2)
    table_without_text["data"] = [["This should not be reconstructed"]]
    records = build_chunk_records(
        _document(
            [
                _block("p6-tables-1", "table", "| A | B |\n| - | - |", reading_order_index=1),
                table_without_text,
            ]
        )
    )

    assert len(records) == 1
    assert records[0].text == "| A | B |\n| - | - |"
    assert records[0].meta["block_ids"] == ["p6-tables-1"]


def test_citation_formats_non_contiguous_page_ranges() -> None:
    records = build_chunk_records(
        _document(
            [
                _block("p6-texts-62", "heading", "Section", page_number=6, reading_order_index=1),
                _block("p7-texts-63", "paragraph", "Continued.", page_number=7, reading_order_index=2),
                _block("p9-texts-64", "paragraph", "Later.", page_number=9, reading_order_index=3),
            ],
            metadata={"source_identifier": "article.pdf", "source_pdf_hash": "hash-123"},
        )
    )

    assert records[0].meta["citation"] == "article.pdf, pp.6-7, 9, §Section"


def test_cli_out_alias_writes_chunk_records(tmp_path: Path) -> None:
    input_path = tmp_path / "blocks.json"
    output_path = tmp_path / "chunks.jsonl"
    document = {
        "metadata": {"source_identifier": "sample.pdf", "source_pdf_hash": "abc123"},
        "blocks": [_block("p6-texts-60", "paragraph", "CLI alias content.")],
    }
    input_path.write_text(json.dumps(document), encoding="utf-8")

    result = main(["--input", str(input_path), "--out", str(output_path)])

    assert result == 0
    lines = _json_lines(output_path)
    assert len(lines) == 1
    assert lines[0]["text"] == "CLI alias content."


def test_invalid_json_root_returns_exit_code_1(tmp_path: Path, capsys) -> None:
    input_path = tmp_path / "bad.json"
    output_path = tmp_path / "chunks.jsonl"
    input_path.write_text("[]", encoding="utf-8")

    result = main(["--input", str(input_path), "--output", str(output_path)])

    assert result == 1
    assert "Error: input JSON root must be an object" in capsys.readouterr().err
    assert not output_path.exists()


def test_non_list_blocks_returns_exit_code_1(tmp_path: Path, capsys) -> None:
    input_path = tmp_path / "bad.json"
    output_path = tmp_path / "chunks.jsonl"
    input_path.write_text(json.dumps({"metadata": {}, "blocks": {"not": "a list"}}), encoding="utf-8")

    result = main(["--input", str(input_path), "--out", str(output_path)])

    assert result == 1
    assert "Error: top-level field `blocks` must be a list" in capsys.readouterr().err
    assert not output_path.exists()


def test_cli_exports_page_006_and_page_012_examples(tmp_path: Path) -> None:
    for page in ("page_006", "page_012"):
        input_path = Path(f"examples/mdpi_pdf_elements/{page}/normalized_blocks.json")
        output_path = tmp_path / f"{page}_chunks.jsonl"

        result = main(["--input", str(input_path), "--output", str(output_path)])

        assert result == 0
        lines = _json_lines(output_path)
        assert lines
        assert all(line["meta"]["schema_version"] == "chunk_record_v1" for line in lines)
        assert all(line["doc_id"] == line["meta"]["chunk_id"] for line in lines)
