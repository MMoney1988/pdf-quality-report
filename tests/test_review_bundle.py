from __future__ import annotations

import json
from pathlib import Path

from pdf_quality_report.review_bundle import BUNDLE_FILES, export_review_bundle, main


def _valid_block(block_id: str, block_type: str = "paragraph", text: str | None = None) -> dict:
    block = {
        "id": block_id,
        "type": block_type,
        "page_number": 6,
        "bbox": [1.0, 2.0, 3.0, 4.0],
        "relationships": [],
        "reading_order_index": 0,
        "content": {
            "text": text
            if text is not None
            else (
                "Useful extracted text with enough characters for deterministic health checks. "
                "This sentence keeps ordinary valid fixtures above the image-text warning threshold."
            ),
            "spans": [],
        },
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
    if block_type == "heading":
        block["level"] = 1
    if block_type == "table":
        block["data_grid"] = [["A", "B"], ["1", "2"]]
    return block


def _write_document(path: Path, blocks: list[dict]) -> None:
    path.write_text(json.dumps({"metadata": {"source": "test"}, "blocks": blocks}), encoding="utf-8")


def test_export_review_bundle_creates_expected_files(tmp_path: Path) -> None:
    input_path = tmp_path / "normalized_blocks.json"
    output_dir = tmp_path / "bundle"
    _write_document(input_path, [_valid_block("p6-texts-48")])

    result = export_review_bundle(input_path, output_dir)

    assert set(result.files) == set(BUNDLE_FILES)
    assert {path.name for path in output_dir.iterdir()} == set(BUNDLE_FILES)
    assert result.decision == "GO"


def test_bundle_readme_contains_file_list_and_summary_without_absolute_input_path(tmp_path: Path) -> None:
    input_path = tmp_path / "normalized_blocks.json"
    output_dir = tmp_path / "bundle"
    _write_document(input_path, [_valid_block("p6-texts-48", text="A")])

    export_review_bundle(input_path, output_dir)

    readme = (output_dir / "README.md").read_text(encoding="utf-8")
    assert "- decision: REVIEW" in readme
    assert "- total_blocks: 1" in readme
    assert "- warnings:" in readme
    assert "- hard_failures: 0" in readme
    assert "`quality_report.md`" in readme
    assert "`review_findings.md`" in readme
    assert "`chunk_records.jsonl`" in readme
    assert str(input_path) not in readme


def test_quality_report_and_review_findings_share_decision(tmp_path: Path) -> None:
    input_path = tmp_path / "normalized_blocks.json"
    output_dir = tmp_path / "bundle"
    _write_document(input_path, [_valid_block("p6-texts-48", text="A")])

    export_review_bundle(input_path, output_dir)

    quality_report = (output_dir / "quality_report.md").read_text(encoding="utf-8")
    review_findings = (output_dir / "review_findings.md").read_text(encoding="utf-8")
    assert "- decision: REVIEW" in quality_report
    assert "- decision: REVIEW" in review_findings


def test_chunk_records_jsonl_and_chunk_review_share_chunk_ids(tmp_path: Path) -> None:
    input_path = tmp_path / "normalized_blocks.json"
    output_dir = tmp_path / "bundle"
    _write_document(input_path, [_valid_block("p6-texts-48")])

    export_review_bundle(input_path, output_dir)

    records = [
        json.loads(line)
        for line in (output_dir / "chunk_records.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    chunk_review = (output_dir / "chunk_review.md").read_text(encoding="utf-8")
    assert records
    assert records[0]["doc_id"] in chunk_review


def test_block_report_still_writes_bundle_and_returns_zero_from_cli(tmp_path: Path) -> None:
    input_path = tmp_path / "normalized_blocks.json"
    output_dir = tmp_path / "bundle"
    block = _valid_block("p6-texts-48")
    block["bbox"] = [10.0, 20.0, 5.0, 30.0]
    block["provenance"]["raw_docling_bbox"] = {
        "l": 10.0,
        "b": 20.0,
        "r": 5.0,
        "t": 30.0,
        "coord_origin": "BOTTOMLEFT",
    }
    _write_document(input_path, [block])

    assert main(["--input", str(input_path), "--output-dir", str(output_dir)]) == 0

    assert (output_dir / "quality_report.md").exists()
    assert "- decision: BLOCK" in (output_dir / "quality_report.md").read_text(encoding="utf-8")


def test_invalid_json_root_returns_one_and_writes_no_bundle_files(tmp_path: Path) -> None:
    input_path = tmp_path / "normalized_blocks.json"
    output_dir = tmp_path / "bundle"
    input_path.write_text(json.dumps([]), encoding="utf-8")

    assert main(["--input", str(input_path), "--output-dir", str(output_dir)]) == 1

    assert not output_dir.exists()


def test_non_list_blocks_returns_one_and_preserves_existing_directory(tmp_path: Path) -> None:
    input_path = tmp_path / "normalized_blocks.json"
    output_dir = tmp_path / "bundle"
    output_dir.mkdir()
    unrelated = output_dir / "notes.txt"
    unrelated.write_text("keep me", encoding="utf-8")
    input_path.write_text(json.dumps({"metadata": {}, "blocks": "not-a-list"}), encoding="utf-8")

    assert main(["--input", str(input_path), "--output-dir", str(output_dir)]) == 1

    assert unrelated.read_text(encoding="utf-8") == "keep me"
    assert not any((output_dir / filename).exists() for filename in BUNDLE_FILES)


def test_existing_known_files_are_overwritten_and_unrelated_files_are_preserved(tmp_path: Path) -> None:
    input_path = tmp_path / "normalized_blocks.json"
    output_dir = tmp_path / "bundle"
    output_dir.mkdir()
    unrelated = output_dir / "notes.txt"
    unrelated.write_text("keep me", encoding="utf-8")
    (output_dir / "quality_report.md").write_text("old content", encoding="utf-8")
    _write_document(input_path, [_valid_block("p6-texts-48")])

    export_review_bundle(input_path, output_dir)

    assert unrelated.read_text(encoding="utf-8") == "keep me"
    assert "old content" not in (output_dir / "quality_report.md").read_text(encoding="utf-8")
    assert set(BUNDLE_FILES).issubset({path.name for path in output_dir.iterdir()})


def test_output_dir_existing_file_returns_one(tmp_path: Path) -> None:
    input_path = tmp_path / "normalized_blocks.json"
    output_path = tmp_path / "bundle"
    output_path.write_text("not a directory", encoding="utf-8")
    _write_document(input_path, [_valid_block("p6-texts-48")])

    assert main(["--input", str(input_path), "--output-dir", str(output_path)]) == 1
    assert output_path.read_text(encoding="utf-8") == "not a directory"


def test_cli_out_dir_alias_writes_bundle(tmp_path: Path) -> None:
    input_path = tmp_path / "normalized_blocks.json"
    output_dir = tmp_path / "bundle"
    _write_document(input_path, [_valid_block("p6-texts-48")])

    assert main(["--input", str(input_path), "--out-dir", str(output_dir)]) == 0

    assert (output_dir / "README.md").exists()


def test_cli_smoke_exports_example_pages(tmp_path: Path) -> None:
    for page in ("page_006", "page_012"):
        input_path = Path("examples/mdpi_pdf_elements") / page / "normalized_blocks.json"
        output_dir = tmp_path / f"{page}_bundle"

        assert main(["--input", str(input_path), "--output-dir", str(output_dir)]) == 0

        assert set(BUNDLE_FILES).issubset({path.name for path in output_dir.iterdir()})
        assert "# PQR Review Bundle" in (output_dir / "README.md").read_text(encoding="utf-8")
