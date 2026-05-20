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
        "content": {
            "text": (
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
    if block_type == "image":
        block["base64"] = None
        block["content"] = {"text": "", "spans": []}
    return block


def _table_block(
    block_id: str,
    *,
    text: str = "| A | B |\n| --- | --- |\n| 1 | 2 |",
    data_grid: list[list[str]] | None = None,
) -> dict:
    block = _valid_block(block_id, "table")
    block["content"]["text"] = text
    block["data_grid"] = data_grid if data_grid is not None else [["A", "B"], ["1", "2"]]
    return block


def test_quality_checks_pass_hard_checks_and_warn_for_noise() -> None:
    body = _valid_block("p6-texts-48")
    header = _valid_block("p6-texts-45", "header")
    header["content"]["text"] = "Running header"
    header["reading_order_index"] = 1

    report = run_quality_checks({"metadata": {"source": "test"}, "blocks": [body, header]})

    statuses = {result.name: result.status for result in report.results}
    assert statuses["Required Field Coverage"] == "PASS"
    assert statuses["Table Output Structure Signals"] == "PASS"
    assert statuses["Provenance Completeness"] == "PASS"
    assert statuses["BBox Sanity"] == "PASS"
    assert statuses["Content vs Noise Ratio"] == "WARN"
    assert statuses["Text Extraction Health"] == "PASS"
    assert report.hard_failures == 0
    assert report.warnings == 1
    assert report.decision == "REVIEW"


def test_table_output_structure_passes_without_table_blocks() -> None:
    report = run_quality_checks({"metadata": {"source": "test"}, "blocks": [_valid_block("p6-texts-48")]})

    table_check = next(result for result in report.results if result.name == "Table Output Structure Signals")
    assert table_check.status == "PASS"
    assert table_check.summary == "no table-labeled blocks found"
    assert "table_blocks=0" in table_check.details
    assert "table_blocks=0; no table-labeled blocks found" in table_check.details


def test_table_output_structure_passes_for_structured_data_grid() -> None:
    report = run_quality_checks({"metadata": {"source": "test"}, "blocks": [_table_block("p6-tables-1")]})

    table_check = next(result for result in report.results if result.name == "Table Output Structure Signals")
    assert table_check.status == "PASS"
    assert table_check.summary == "table-labeled blocks include visible structure signals"
    assert "table_blocks=1" in table_check.details
    assert "structured_grid_blocks=1" in table_check.details


def test_table_output_structure_accepts_optional_rows_signal() -> None:
    table = _table_block("p6-tables-1", text="A B C", data_grid=[])
    table["content"]["rows"] = [["A", "B"], ["1", "2"]]

    report = run_quality_checks({"metadata": {"source": "test"}, "blocks": [table]})

    table_check = next(result for result in report.results if result.name == "Table Output Structure Signals")
    assert table_check.status == "PASS"
    assert "structured_grid_blocks=1" in table_check.details


def test_table_output_structure_warns_for_plain_text_only_without_hard_failure() -> None:
    table = _table_block(
        "p6-tables-1",
        text="This table-labeled block appears as one plain paragraph without obvious columns.",
        data_grid=[],
    )

    report = run_quality_checks({"metadata": {"source": "test"}, "blocks": [table]})

    table_check = next(result for result in report.results if result.name == "Table Output Structure Signals")
    assert table_check.status == "WARN"
    assert "plain_text_only_blocks=1" in table_check.details
    assert any("plain text only and no obvious row/column structure signal" in detail for detail in table_check.details)
    assert report.hard_failures == 0
    assert report.decision == "REVIEW"


def test_table_output_structure_warns_for_inconsistent_grid_widths() -> None:
    table = _table_block("p6-tables-1", data_grid=[["A", "B"], ["1"]])

    report = run_quality_checks({"metadata": {"source": "test"}, "blocks": [table]})

    table_check = next(result for result in report.results if result.name == "Table Output Structure Signals")
    assert table_check.status == "WARN"
    assert "inconsistent_grid_blocks=1" in table_check.details
    assert "p6-tables-1: table data_grid has inconsistent row widths: 1, 2" in table_check.details
    assert report.hard_failures == 0


def test_table_output_structure_passes_for_text_structure_signal() -> None:
    table = _table_block("p6-tables-1", text="A\tB\n1\t2", data_grid=[])

    report = run_quality_checks({"metadata": {"source": "test"}, "blocks": [table]})

    table_check = next(result for result in report.results if result.name == "Table Output Structure Signals")
    assert table_check.status == "PASS"
    assert "text_structure_signal_blocks=1" in table_check.details


def test_table_output_structure_does_not_replace_required_field_failures() -> None:
    table = _table_block("p6-tables-1")
    del table["data_grid"]

    report = run_quality_checks({"metadata": {"source": "test"}, "blocks": [table]})

    required = next(result for result in report.results if result.name == "Required Field Coverage")
    table_check = next(result for result in report.results if result.name == "Table Output Structure Signals")
    assert required.status == "FAIL"
    assert "p6-tables-1: table missing data_grid" in required.details
    assert table_check.status == "PASS"
    assert table_check.status != "FAIL"
    assert report.hard_failures == 1


def test_quality_checks_fail_missing_required_field() -> None:
    block = _valid_block("p6-texts-48")
    del block["bbox"]

    report = run_quality_checks({"metadata": {"source": "test"}, "blocks": [block]})

    required = next(result for result in report.results if result.name == "Required Field Coverage")
    assert required.status == "FAIL"
    assert any("missing block field: bbox" in detail for detail in required.details)
    assert report.hard_failures == 2
    assert report.decision == "BLOCK"


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


def test_text_extraction_health_passes_when_text_is_available() -> None:
    report = run_quality_checks({"metadata": {"source": "test"}, "blocks": [_valid_block("p6-texts-48")]})

    health = next(result for result in report.results if result.name == "Text Extraction Health")
    assert health.status == "PASS"
    assert health.summary == "extracted text availability checks passed"
    assert "text_bearing_blocks=1" in health.details
    assert "non_empty_text_blocks=1" in health.details
    assert "empty_text_blocks=0" in health.details
    assert "image_blocks=0" in health.details
    assert "empty_text_block_ratio=0.000" in health.details


def test_text_extraction_health_warns_without_hard_failure() -> None:
    image = _valid_block("p6-pictures-4", "image")

    report = run_quality_checks({"metadata": {"source": "test"}, "blocks": [image]})

    health = next(result for result in report.results if result.name == "Text Extraction Health")
    assert health.status == "WARN"
    assert "text_bearing_blocks=0" in health.details
    assert "non_empty_text_blocks=0" in health.details
    assert "empty_text_blocks=0" in health.details
    assert "total_text_chars=0" in health.details
    assert "image_blocks=1" in health.details
    assert "empty_text_block_ratio=0.000" in health.details
    assert "no_text_bearing_blocks: document has blocks but no text-bearing blocks" in health.details
    assert "low_text_coverage: total_text_chars=0 below threshold=40" in health.details
    assert any(
        "document contains image blocks while extracted text remains very limited" in detail
        for detail in health.details
    )
    assert health.status != "FAIL"
    assert report.hard_failures == 0
    assert report.decision == "REVIEW"


def test_text_extraction_health_warns_when_text_bearing_blocks_are_empty_without_body_failures() -> None:
    header = _valid_block("p6-texts-45", "header")
    header["content"]["text"] = ""

    report = run_quality_checks({"metadata": {"source": "test"}, "blocks": [header]})

    health = next(result for result in report.results if result.name == "Text Extraction Health")
    text_usefulness = next(result for result in report.results if result.name == "Text Usefulness")
    assert health.status == "WARN"
    assert text_usefulness.status == "PASS"
    assert "text_bearing_blocks=1" in health.details
    assert "non_empty_text_blocks=0" in health.details
    assert "no_non_empty_text_blocks: text-bearing blocks contain no extracted text" in health.details
    assert health.status != "FAIL"
    assert report.hard_failures == 0
    assert report.decision == "REVIEW"


def test_text_extraction_health_warns_for_empty_text_ratio() -> None:
    empty_body = _valid_block("p6-texts-49")
    empty_body["content"]["text"] = ""
    filled_body = _valid_block("p6-texts-50")
    filled_body["content"]["text"] = (
        "Enough extracted text to avoid the low-text threshold for this specific ratio case."
    )

    report = run_quality_checks({"metadata": {"source": "test"}, "blocks": [empty_body, filled_body]})

    health = next(result for result in report.results if result.name == "Text Extraction Health")
    assert health.status == "PASS"
    assert "empty_text_block_ratio=0.500" in health.details

    second_empty_body = _valid_block("p6-texts-51")
    second_empty_body["content"]["text"] = ""
    report = run_quality_checks(
        {"metadata": {"source": "test"}, "blocks": [empty_body, second_empty_body, filled_body]}
    )

    health = next(result for result in report.results if result.name == "Text Extraction Health")
    text_usefulness = next(result for result in report.results if result.name == "Text Usefulness")
    assert health.status == "WARN"
    assert text_usefulness.status == "FAIL"
    assert "empty_text_block_ratio=0.667" in health.details
    assert any("high_empty_text_block_ratio" in detail for detail in health.details)
    assert health.status != "FAIL"
    assert report.hard_failures == 1


def test_text_extraction_health_warns_when_document_has_no_blocks() -> None:
    report = run_quality_checks({"metadata": {"source": "test"}, "blocks": []})

    health = next(result for result in report.results if result.name == "Text Extraction Health")
    assert health.status == "WARN"
    assert health.summary == "document has no blocks to evaluate"
    assert "no_blocks: document has no blocks to evaluate" in health.details
    assert report.hard_failures == 0


def test_markdown_report_contains_required_sections() -> None:
    table_marker = _valid_block("p12-texts-109")
    table_marker["content"]["text"] = "+"
    report = run_quality_checks({"metadata": {"source": "test"}, "blocks": [table_marker]})

    markdown = render_markdown_report(report)

    assert "# PDF Parser Output Quality Report" in markdown
    assert "## Summary" in markdown
    assert "- decision: REVIEW" in markdown
    assert "## Interpretation" in markdown
    assert "Why REVIEW?" in markdown
    assert "Warnings are decision-level findings" in markdown
    assert "## Noise / Layout Signals" in markdown
    assert "## Check Results" in markdown
    assert "## Recommended Review Actions" in markdown
    assert markdown.index("## Summary") < markdown.index("## Interpretation")
    assert markdown.index("## Interpretation") < markdown.index("## Noise / Layout Signals")
    assert markdown.index("## Noise / Layout Signals") < markdown.index("## Check Results")
    assert "table_marker_artifacts: 1" in markdown
    assert "## Required Field Coverage" in markdown
    assert "## Table Output Structure Signals" in markdown
    assert "## Text Usefulness" in markdown
    assert "## Text Extraction Health" in markdown
    assert "Table Output Structure Signals checks whether table-labeled normalized blocks contain visible" in markdown
    assert "Text Extraction Health checks extracted-text availability, not extracted-text correctness." in markdown


def test_cli_writes_quality_report(tmp_path: Path) -> None:
    uif_path = tmp_path / "uif.json"
    report_path = tmp_path / "quality_report.md"
    uif_path.write_text(json.dumps({"metadata": {}, "blocks": [_valid_block("p6-texts-48")]}), encoding="utf-8")

    assert main(["--input", str(uif_path), "--output", str(report_path)]) == 0

    assert report_path.exists()
    report_text = report_path.read_text(encoding="utf-8")
    assert "hard_failures: 0" in report_text
    assert "decision: GO" in report_text
    assert "This does not prove complete or semantically correct extraction" in report_text


def test_cli_exits_zero_when_only_text_extraction_health_warns(tmp_path: Path) -> None:
    uif_path = tmp_path / "uif.json"
    report_path = tmp_path / "quality_report.md"
    block = _valid_block("p6-unknown-1", "unknown")
    block["content"]["text"] = ""
    uif_path.write_text(json.dumps({"metadata": {}, "blocks": [block]}), encoding="utf-8")

    assert main(["--input", str(uif_path), "--output", str(report_path)]) == 0

    report_text = report_path.read_text(encoding="utf-8")
    assert "hard_failures: 0" in report_text
    assert "decision: REVIEW" in report_text
    assert "## Text Extraction Health" in report_text
    assert "no_text_bearing_blocks: document has blocks but no text-bearing blocks" in report_text


def test_cli_exits_zero_when_only_table_output_structure_warns(tmp_path: Path) -> None:
    uif_path = tmp_path / "uif.json"
    report_path = tmp_path / "quality_report.md"
    table = _table_block(
        "p6-tables-1",
        text="This table-labeled block appears as one plain paragraph without obvious columns.",
        data_grid=[],
    )
    uif_path.write_text(json.dumps({"metadata": {}, "blocks": [table]}), encoding="utf-8")

    assert main(["--input", str(uif_path), "--output", str(report_path)]) == 0

    report_text = report_path.read_text(encoding="utf-8")
    assert "hard_failures: 0" in report_text
    assert "decision: REVIEW" in report_text
    assert "## Table Output Structure Signals" in report_text
    assert "plain text only and no obvious row/column structure signal" in report_text
