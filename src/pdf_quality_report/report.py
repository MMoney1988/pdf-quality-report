"""Render minimal PDF quality reports from normalized block JSON."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .checks import run_quality_checks
from .interpret import interpret_quality_report
from .models import CheckResult, NoiseLayoutSignals, QualityReport

INTERPRETATION_NOTE = (
    "Derived from recorded checks and diagnostic signals. "
    "This explains the report decision; it does not add new checks or change the decision."
)


def render_markdown_report(report: QualityReport) -> str:
    """Render a minimal Markdown report for humans."""
    lines = [
        "# Minimal PDF Quality Report",
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
    for result in report.results:
        lines.extend(_render_check_result(result))
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
    """CLI entrypoint for the minimal quality report."""
    parser = argparse.ArgumentParser(description="Create a minimal Markdown quality report from normalized block JSON.")
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
        INTERPRETATION_NOTE,
        "",
    ]
    lines.extend(f"- {bullet}" for bullet in interpret_quality_report(report))
    lines.append("")
    return lines


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


def _render_noise_layout_signals(signals: NoiseLayoutSignals) -> list[str]:
    lines = [
        "## Noise / Layout Signals",
        "Diagnostic signals only; these do not add hard failures or warnings.",
        "",
        f"- table_marker_artifacts: {len(signals.table_marker_artifacts)}",
        f"- running_furniture_blocks: {len(signals.running_furniture_blocks)}",
        f"- visual_anchor_blocks: {len(signals.visual_anchor_blocks)}",
        f"- ambiguous_image_blocks: {len(signals.ambiguous_image_blocks)}",
        "",
    ]
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


if __name__ == "__main__":
    raise SystemExit(main())
