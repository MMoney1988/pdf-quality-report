from __future__ import annotations

import json
from pathlib import Path

from pdf_quality_report.checks import run_quality_checks
from pdf_quality_report.report import main, render_markdown_report


def _valid_block(block_id: str, block_type: str = "paragraph") -> dict:
    block = {
        "id": block_id,
        "type": block_type,
        "page_number": 6,
        "bbox": [1.0, 2.0, 3.0, 4.0],
        "relationships": [],
        "reading_order_index": 0,
        "content": {"text": "Useful text", "spans": []},
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
    if block_type == "image":
        block["base64"] = None
        block["content"] = {"text": "", "spans": []}
    return block


def test_quality_checks_pass_hard_checks_and_warn_for_noise() -> None:
    body = _valid_block("p6-texts-48")
    header = _valid_block("p6-texts-45", "header")
    header["content"]["text"] = "Running header"
    header["reading_order_index"] = 1

    report = run_quality_checks({"metadata": {"source": "test"}, "blocks": [body, header]})

    statuses = {result.name: result.status for result in report.results}
    assert statuses["Required Field Coverage"] == "PASS"
    assert statuses["Provenance Completeness"] == "PASS"
    assert statuses["BBox Sanity"] == "PASS"
    assert statuses["Content vs Noise Ratio"] == "WARN"
    assert report.hard_failures == 0
    assert report.warnings == 1


def test_quality_checks_fail_missing_required_field() -> None:
    block = _valid_block("p6-texts-48")
    del block["bbox"]

    report = run_quality_checks({"metadata": {"source": "test"}, "blocks": [block]})

    required = next(result for result in report.results if result.name == "Required Field Coverage")
    assert required.status == "FAIL"
    assert any("missing block field: bbox" in detail for detail in required.details)
    assert report.hard_failures == 2


def test_quality_checks_fail_malformed_top_level_types() -> None:
    report = run_quality_checks({"metadata": "not-an-object", "blocks": "not-a-list"})

    required = next(result for result in report.results if result.name == "Required Field Coverage")
    assert required.status == "FAIL"
    assert "top-level field `metadata` must be an object" in required.details
    assert "top-level field `blocks` must be a list" in required.details
    assert report.hard_failures == 1


def test_quality_checks_fail_invalid_bbox_coordinates() -> None:
    block = _valid_block("p6-texts-48")
    block["bbox"] = [10.0, 20.0, 5.0, 30.0]
    block["provenance"]["raw_docling_bbox"] = {
        "l": 10.0,
        "b": 20.0,
        "r": 5.0,
        "t": 30.0,
        "coord_origin": "BOTTOMLEFT",
    }

    report = run_quality_checks({"metadata": {"source": "test"}, "blocks": [block]})

    bbox = next(result for result in report.results if result.name == "BBox Sanity")
    assert bbox.status == "FAIL"
    assert any("bbox coordinates are not increasing" in detail for detail in bbox.details)


def test_noise_layout_signals_capture_table_furniture_and_images() -> None:
    table_marker = _valid_block("p12-texts-109")
    table_marker["content"]["text"] = "+"
    footer = _valid_block("p12-texts-120", "footer")
    footer["content"]["text"] = "11"
    image = _valid_block("p6-pictures-4", "image")

    report = run_quality_checks({"metadata": {"source": "test"}, "blocks": [table_marker, footer, image]})

    signals = report.noise_layout_signals
    assert signals.table_marker_artifacts == ["p12-texts-109: type=paragraph, text='+'"]
    assert signals.running_furniture_blocks == ["p12-texts-120: type=footer, text='11'"]
    assert signals.visual_anchor_blocks == ["p6-pictures-4: type=image, text=<empty>"]
    assert signals.ambiguous_image_blocks == ["p6-pictures-4: type=image, text=<empty>"]
    assert report.hard_failures == 0


def test_markdown_report_contains_required_sections() -> None:
    table_marker = _valid_block("p12-texts-109")
    table_marker["content"]["text"] = "+"
    report = run_quality_checks({"metadata": {"source": "test"}, "blocks": [table_marker]})

    markdown = render_markdown_report(report)

    assert "# Minimal PDF Quality Report" in markdown
    assert "## Summary" in markdown
    assert "## Noise / Layout Signals" in markdown
    assert "table_marker_artifacts: 1" in markdown
    assert "## Required Field Coverage" in markdown
    assert "## Text Usefulness" in markdown


def test_cli_writes_quality_report(tmp_path: Path) -> None:
    uif_path = tmp_path / "uif.json"
    report_path = tmp_path / "quality_report.md"
    uif_path.write_text(json.dumps({"metadata": {}, "blocks": [_valid_block("p6-texts-48")]}), encoding="utf-8")

    assert main(["--input", str(uif_path), "--output", str(report_path)]) == 0

    assert report_path.exists()
    assert "hard_failures: 0" in report_path.read_text(encoding="utf-8")
