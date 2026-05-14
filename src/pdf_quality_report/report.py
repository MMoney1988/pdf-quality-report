"""Render PDF parser-output quality reports from normalized block JSON."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .checks import run_quality_checks
from .interpret import interpret_quality_report
from .models import CheckResult, NoiseLayoutSignals, QualityReport

CHECK_RESULT_EXPLANATIONS = (
    "Each section below is a separate check.",
    "Required Field Coverage checks whether required JSON fields are present.",
    "Provenance Completeness checks whether source, page, and bounding-box metadata is present.",
    "BBox Sanity checks whether bounding boxes look structurally valid.",
    "Content vs Noise Ratio checks how much extracted content looks like main text versus layout/noise.",
    "Text Usefulness flags very short or repeated text fragments.",
    "Text Extraction Health checks extracted-text availability, not extracted-text correctness.",
)


def render_markdown_report(report: QualityReport) -> str:
    """Render a Markdown report for humans."""
    lines = [
        "# PDF Parser Output Quality Report",
        "",
        "## Summary",
        f"- total_blocks: {report.total_blocks}",
        f"- hard_failures: {report.hard_failures}",
        f"- warnings: {report.warnings}",
        f"- decision: {report.decision}",
        "",
    ]
    lines.extend(_render_interpretation(report))
    lines.extend(_render_noise_layout_signals(report.noise_layout_signals))
    lines.extend(_render_check_results_intro())
    for result in report.results:
        lines.extend(_render_check_result(result))
    lines.extend(_render_recommended_review_actions(report))
    return "\n".join(lines).rstrip() + "\n"


def load_uif_document(path: Path) -> dict[str, Any]:
    """Load a normalized block document from JSON."""
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError("Input JSON root must be an object")
    return document


def write_quality_report(uif_json_path: Path, output_path: Path) -> QualityReport:
    """Run checks for normalized block JSON and write a Markdown report."""
    report = run_quality_checks(load_uif_document(uif_json_path))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown_report(report), encoding="utf-8")
    return report


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint for the quality report."""
    parser = argparse.ArgumentParser(description="Create a Markdown quality report from normalized block JSON.")
    parser.add_argument(
        "--input",
        "--uif-json",
        dest="input_path",
        required=True,
        type=Path,
        help="Path to normalized block JSON.",
    )
    parser.add_argument(
        "--output",
        "--out",
        dest="output_path",
        required=True,
        type=Path,
        help="Path where quality_report.md should be written.",
    )
    args = parser.parse_args(argv)

    report = write_quality_report(args.input_path, args.output_path)
    return 1 if report.hard_failures else 0


def _render_interpretation(report: QualityReport) -> list[str]:
    lines = [
        "## Interpretation",
        _interpretation_intro(report),
        "",
    ]
    lines.extend(f"- {bullet}" for bullet in interpret_quality_report(report))
    lines.append("")
    return lines


def _interpretation_intro(report: QualityReport) -> str:
    if report.decision == "GO":
        return (
            "Why GO? The current checks found no warnings or hard failures. "
            "This does not prove complete or semantically correct extraction."
        )
    if report.decision == "BLOCK":
        failure_names = _status_names(report.results, "FAIL")
        return (
            f"Why BLOCK? The report found hard failures in {_format_names(failure_names)}. "
            "Fix hard failures before reusing this parser output."
        )
    warning_names = _status_names(report.results, "WARN")
    return (
        f"Why REVIEW? The hard structure checks passed, but {_plural(len(warning_names), 'warning check')} "
        f"{_needs_verb(len(warning_names))} review in this report: {_format_names(warning_names)}. "
        "Warnings are decision-level findings. Noise / Layout Signals provide supporting evidence and are counted "
        "separately."
    )


def _render_check_result(result: CheckResult) -> list[str]:
    lines = [
        f"## {result.name}",
        result.status,
        "",
        result.summary,
    ]
    if result.details:
        lines.append("")
        lines.extend(f"- {detail}" for detail in result.details)
    lines.append("")
    return lines


def _render_check_results_intro() -> list[str]:
    lines = [
        "## Check Results",
        CHECK_RESULT_EXPLANATIONS[0],
        "",
    ]
    lines.extend(f"- {explanation}" for explanation in CHECK_RESULT_EXPLANATIONS[1:])
    lines.append("")
    return lines


def _render_noise_layout_signals(signals: NoiseLayoutSignals) -> list[str]:
    lines = [
        "## Noise / Layout Signals",
        "These signals identify page-layout elements that may need review before reusing the extracted text. "
        "They are supporting evidence and are counted separately from warning checks.",
        "",
        f"- table_marker_artifacts: {len(signals.table_marker_artifacts)}",
        f"- running_furniture_blocks: {len(signals.running_furniture_blocks)}",
        f"- visual_anchor_blocks: {len(signals.visual_anchor_blocks)}",
        f"- ambiguous_image_blocks: {len(signals.ambiguous_image_blocks)}",
        "",
    ]
    overlapping_image_ids = sorted(
        set(_signal_ids(signals.visual_anchor_blocks)) & set(_signal_ids(signals.ambiguous_image_blocks))
    )
    if overlapping_image_ids:
        lines.extend(
            [
                "The same image block can appear in both `visual_anchor_blocks` and `ambiguous_image_blocks`: "
                "`visual_anchor_blocks` counts image blocks, while `ambiguous_image_blocks` flags image blocks "
                "with no extracted text context.",
                "",
            ]
        )
    details = [
        *[f"table_marker_artifact: {detail}" for detail in signals.table_marker_artifacts],
        *[f"running_furniture: {detail}" for detail in signals.running_furniture_blocks],
        *[f"visual_anchor: {detail}" for detail in signals.visual_anchor_blocks],
        *[f"ambiguous_image: {detail}" for detail in signals.ambiguous_image_blocks],
    ]
    if details:
        lines.append("Details:")
        lines.extend(f"- {detail}" for detail in details)
        lines.append("")
    return lines


def _render_recommended_review_actions(report: QualityReport) -> list[str]:
    lines = ["## Recommended Review Actions"]
    if report.decision == "GO":
        lines.extend(
            [
                "The current checks did not find warnings or hard failures. Review the output for semantic correctness "
                "before downstream use.",
                "The report identifies parser-output findings; it does not prove complete document understanding.",
            ]
        )
    elif report.decision == "BLOCK":
        lines.extend(
            [
                "Fix the hard failures before using this parser output for Markdown export, RAG ingestion preparation, "
                "or manual extraction.",
                "The report identifies parser-output findings; it does not automatically fix, remove, or approve "
                "blocks.",
            ]
        )
    else:
        review_targets = _review_targets(report)
        lines.extend(
            [
                f"Because the decision is REVIEW, inspect {review_targets} before using this output for Markdown "
                "export, "
                "RAG ingestion preparation, or manual extraction.",
                "If the listed items are expected chart labels, headers, footers, or figure labels, keep, exclude, "
                "or describe them according to the downstream use case. If they point to missing or incorrect content, "
                "adjust extraction before reuse.",
                "The report identifies parser-output findings; it does not automatically fix, remove, or approve "
                "blocks.",
            ]
        )
    lines.append("")
    return lines


def _review_targets(report: QualityReport) -> str:
    warning_names = set(_status_names(report.results, "WARN"))
    targets: list[str] = []
    if "Text Usefulness" in warning_names:
        targets.append("short/repeated text fragments")
    if "Text Extraction Health" in warning_names:
        targets.append("extracted-text availability")
    if "Content vs Noise Ratio" in warning_names or any(
        (
            report.noise_layout_signals.table_marker_artifacts,
            report.noise_layout_signals.running_furniture_blocks,
            report.noise_layout_signals.visual_anchor_blocks,
            report.noise_layout_signals.ambiguous_image_blocks,
        )
    ):
        targets.append("layout/noise signals")
    if not targets:
        targets.append("the listed warning details")
    return _format_names(targets)


def _status_names(results: list[CheckResult], status: str) -> list[str]:
    return [result.name for result in results if result.status == status]


def _signal_ids(details: list[str]) -> list[str]:
    ids: list[str] = []
    for detail in details:
        block_id = detail.split(":", maxsplit=1)[0]
        if block_id:
            ids.append(block_id)
    return ids


def _format_names(names: list[str]) -> str:
    if not names:
        return "none"
    if len(names) <= 2:
        return " and ".join(names)
    return f"{', '.join(names[:-1])}, and {names[-1]}"


def _plural(count: int, noun: str) -> str:
    return noun if count == 1 else f"{noun}s"


def _needs_verb(count: int) -> str:
    return "needs" if count == 1 else "need"


if __name__ == "__main__":
    raise SystemExit(main())
