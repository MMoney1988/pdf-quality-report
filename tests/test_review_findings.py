from __future__ import annotations

import json
from pathlib import Path

from pdf_quality_report.checks import run_quality_checks
from pdf_quality_report.review_findings import main, render_review_findings_markdown


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
    if block_type == "image":
        block["base64"] = None
        block["content"] = {"text": "", "spans": []}
    if block_type == "table":
        block["data_grid"] = [["A", "B"], ["1", "2"]]
    return block


def _render(blocks: list[dict]) -> str:
    report = run_quality_checks({"metadata": {"source": "test"}, "blocks": blocks})
    return render_review_findings_markdown(report, blocks)


def test_all_pass_document_renders_empty_findings_summary() -> None:
    markdown = _render([_valid_block("p6-texts-48")])

    assert "# Review Findings" in markdown
    assert "- decision: GO" in markdown
    assert "- review_findings: 0" in markdown
    assert "_No WARN or FAIL findings._" in markdown


def test_warn_detail_renders_as_finding_with_source_context() -> None:
    block = _valid_block("p6-texts-48", text="A")

    markdown = _render([block])

    assert "### Text Usefulness (WARN)" in markdown
    assert "#### Finding 1" in markdown
    assert "- Detail: p6-texts-48: very short text: 'A'" in markdown
    assert "p6-texts-48 | page=6 | type=paragraph | bbox=[1.0, 2.0, 3.0, 4.0]" in markdown
    assert "text='A'" in markdown


def test_fail_detail_renders_as_finding_with_source_context() -> None:
    block = _valid_block("p6-texts-48")
    del block["bbox"]

    markdown = _render([block])

    assert "- decision: BLOCK" in markdown
    assert "### Required Field Coverage (FAIL)" in markdown
    assert "- Detail: p6-texts-48: missing block field: bbox" in markdown
    assert "p6-texts-48 | page=6 | type=paragraph" in markdown


def test_metric_only_warning_becomes_single_check_level_finding() -> None:
    body = _valid_block("p6-texts-48")
    header = _valid_block("p6-texts-45", "header", text="Running header")

    markdown = _render([body, header])

    assert "### Content vs Noise Ratio (WARN)" in markdown
    assert "- review_findings: 1" in markdown
    assert "- content_candidate_blocks=1" in markdown
    assert "- secondary_or_noise_blocks=1" in markdown
    assert "- Detail: Check summary: 1 content-like block(s), 1 secondary/noise candidate block(s)" in markdown


def test_metric_like_lines_do_not_inflate_review_findings_count() -> None:
    image = _valid_block("p6-pictures-4", "image")

    markdown = _render([image])

    assert "- text_bearing_blocks=0" in markdown
    assert "- non_empty_text_blocks=0" in markdown
    assert "- Detail: text_bearing_blocks=0" not in markdown
    assert "- review_findings: 4" in markdown


def test_repeated_text_detail_enriches_multiple_block_ids() -> None:
    first = _valid_block("p12-texts-601", text="0.5")
    second = _valid_block("p12-texts-608", text="0.5")

    markdown = _render([first, second])

    assert "repeated text value '0.5' appears in block IDs: p12-texts-601, p12-texts-608" in markdown
    assert "p12-texts-601 | page=6 | type=paragraph" in markdown
    assert "p12-texts-608 | page=6 | type=paragraph" in markdown
    assert markdown.index("p12-texts-601 | page=6") < markdown.index("p12-texts-608 | page=6")


def test_same_block_referenced_by_multiple_details_is_rendered_deterministically() -> None:
    block = _valid_block("p6-texts-48")
    block["bbox"] = [10.0, 20.0, 5.0, 30.0]
    block["provenance"]["raw_docling_bbox"] = {
        "l": 10.0,
        "b": 20.0,
        "r": 999.0,
        "t": 30.0,
        "coord_origin": "BOTTOMLEFT",
    }

    markdown = _render([block])

    assert markdown == _render([block])
    assert markdown.count("p6-texts-48 | page=6 | type=paragraph") >= 2


def test_unmatched_block_reference_does_not_crash() -> None:
    report = run_quality_checks({"metadata": {"source": "test"}, "blocks": [_valid_block("p6-texts-48")]})
    replaced_result = report.results[0].__class__(
        "Required Field Coverage",
        "FAIL",
        "synthetic failure",
        ["p99-texts-999: synthetic issue"],
    )
    synthetic_report = report.__class__(
        report.total_blocks,
        hard_failures=1,
        warnings=report.warnings,
        results=[replaced_result, *report.results[1:]],
        noise_layout_signals=report.noise_layout_signals,
    )

    markdown = render_review_findings_markdown(synthetic_report, [_valid_block("p6-texts-48")])

    assert "p99-texts-999: synthetic issue" in markdown
    assert "referenced block ID was not found in normalized blocks" in markdown


def test_supporting_layout_signals_are_rendered_without_increasing_finding_count() -> None:
    body = _valid_block("p6-texts-48")
    footer = _valid_block("p6-texts-45", "footer", text="Footer")

    markdown = _render([body, footer])

    assert "- review_findings: 1" in markdown
    assert "## Supporting Layout Signals" in markdown
    assert "### running_furniture_blocks" in markdown
    assert "p6-texts-45: type=footer, text='Footer'" in markdown


def test_cli_writes_review_findings_markdown(tmp_path: Path) -> None:
    input_path = tmp_path / "normalized_blocks.json"
    output_path = tmp_path / "review_findings.md"
    input_path.write_text(
        json.dumps({"metadata": {"source": "test"}, "blocks": [_valid_block("p6-texts-48")]}),
        encoding="utf-8",
    )

    assert main(["--input", str(input_path), "--output", str(output_path)]) == 0

    assert output_path.exists()
    assert "# Review Findings" in output_path.read_text(encoding="utf-8")


def test_cli_out_alias_writes_review_findings_markdown(tmp_path: Path) -> None:
    input_path = tmp_path / "normalized_blocks.json"
    output_path = tmp_path / "review_findings.md"
    input_path.write_text(
        json.dumps({"metadata": {"source": "test"}, "blocks": [_valid_block("p6-texts-48", text="A")]}),
        encoding="utf-8",
    )

    assert main(["--input", str(input_path), "--out", str(output_path)]) == 0

    assert "### Text Usefulness (WARN)" in output_path.read_text(encoding="utf-8")


def test_cli_invalid_json_root_returns_one(tmp_path: Path) -> None:
    input_path = tmp_path / "normalized_blocks.json"
    output_path = tmp_path / "review_findings.md"
    input_path.write_text(json.dumps([]), encoding="utf-8")

    assert main(["--input", str(input_path), "--output", str(output_path)]) == 1
    assert not output_path.exists()


def test_cli_smoke_exports_example_pages(tmp_path: Path) -> None:
    for page in ("page_006", "page_012"):
        input_path = Path("examples/mdpi_pdf_elements") / page / "normalized_blocks.json"
        output_path = tmp_path / f"{page}_review_findings.md"

        assert main(["--input", str(input_path), "--output", str(output_path)]) == 0

        markdown = output_path.read_text(encoding="utf-8")
        assert "# Review Findings" in markdown
        assert "## Summary" in markdown
