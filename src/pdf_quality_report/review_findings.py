"""Render quality-check findings as human-reviewable Markdown."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .checks import run_quality_checks
from .models import CheckResult, NoiseLayoutSignals, QualityReport
from .report import load_uif_document

PREVIEW_CHARS = 160
METRIC_DETAIL_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
LEADING_BLOCK_ID_RE = re.compile(r"^([^:\s]+):")


class ReviewFindingsExportError(Exception):
    """Raised when review findings cannot be exported."""


@dataclass(frozen=True)
class _BlockContext:
    block_id: str
    page_number: object
    block_type: str
    bbox: object
    text: str


@dataclass(frozen=True)
class _ReviewFinding:
    check_name: str
    status: str
    detail: str
    block_contexts: list[_BlockContext]


def render_review_findings_markdown(report: QualityReport, blocks: Sequence[dict[str, Any]]) -> str:
    """Render WARN and FAIL check details as Markdown for human review.

    Args:
        report: Quality report created by `run_quality_checks`.
        blocks: Normalized blocks used to enrich findings with source context.

    Returns:
        Markdown review findings document.
    """
    block_lookup = _block_lookup(blocks)
    findings = _review_findings(report.results, block_lookup)
    lines = [
        "# Review Findings",
        "",
        "## Summary",
        "",
        f"- decision: {report.decision}",
        f"- total_blocks: {report.total_blocks}",
        f"- warnings: {report.warnings}",
        f"- hard_failures: {report.hard_failures}",
        f"- review_findings: {len(findings)}",
        "",
        "## Findings",
        "",
    ]

    if not findings:
        lines.extend(
            [
                "_No WARN or FAIL findings._",
                "",
            ]
        )
    else:
        lines.extend(_finding_sections(report.results, findings, block_lookup))

    lines.extend(_supporting_signal_lines(report.noise_layout_signals))
    return "\n".join(lines).rstrip() + "\n"


def export_review_findings_markdown(input_path: Path, output_path: Path) -> QualityReport:
    """Run quality checks and write a Markdown findings document.

    Args:
        input_path: Path to a normalized blocks JSON file.
        output_path: Path where the review findings Markdown should be written.

    Returns:
        The quality report rendered into the findings document.
    """
    try:
        document = load_uif_document(input_path)
    except OSError as exc:
        raise ReviewFindingsExportError(f"could not read input file: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ReviewFindingsExportError(f"invalid input JSON: {exc}") from exc
    except ValueError as exc:
        raise ReviewFindingsExportError(str(exc)) from exc

    report = run_quality_checks(document)
    markdown = render_review_findings_markdown(report, _blocks(document))
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown, encoding="utf-8")
    except OSError as exc:
        raise ReviewFindingsExportError(f"could not write output file: {exc}") from exc
    return report


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint for review findings Markdown export."""
    parser = argparse.ArgumentParser(
        description="Export quality-check findings as human-reviewable Markdown.",
    )
    parser.add_argument(
        "--input",
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
        help="Path where review_findings.md should be written.",
    )
    args = parser.parse_args(argv)

    try:
        export_review_findings_markdown(args.input_path, args.output_path)
    except ReviewFindingsExportError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


def _review_findings(
    results: Sequence[CheckResult],
    block_lookup: dict[str, _BlockContext],
) -> list[_ReviewFinding]:
    findings: list[_ReviewFinding] = []
    for result in results:
        if result.status not in {"WARN", "FAIL"}:
            continue
        finding_details = [detail for detail in result.details if not _is_metric_detail(detail)]
        if not finding_details:
            finding_details = [f"Check summary: {result.summary}"]
        for detail in finding_details:
            contexts = [block_lookup[block_id] for block_id in _referenced_block_ids(detail, block_lookup)]
            findings.append(_ReviewFinding(result.name, result.status, detail, contexts))
    return findings


def _finding_sections(
    results: Sequence[CheckResult],
    findings: Sequence[_ReviewFinding],
    block_lookup: dict[str, _BlockContext],
) -> list[str]:
    lines: list[str] = []
    by_check: dict[str, list[_ReviewFinding]] = {}
    for finding in findings:
        by_check.setdefault(finding.check_name, []).append(finding)

    for result in results:
        check_findings = by_check.get(result.name, [])
        if not check_findings:
            continue
        lines.extend(
            [
                f"### {result.name} ({result.status})",
                "",
                f"Summary: {result.summary}",
                "",
            ]
        )
        context_details = [detail for detail in result.details if _is_metric_detail(detail)]
        if context_details:
            lines.extend(["Context:", ""])
            lines.extend(f"- {detail}" for detail in context_details)
            lines.append("")
        for index, finding in enumerate(check_findings, start=1):
            lines.extend(_finding_lines(index, finding, block_lookup))
        lines.append("")
    return lines


def _finding_lines(
    index: int,
    finding: _ReviewFinding,
    block_lookup: dict[str, _BlockContext],
) -> list[str]:
    lines = [
        f"#### Finding {index}",
        "",
        f"- Status: {finding.status}",
        f"- Detail: {finding.detail}",
    ]
    if finding.block_contexts:
        lines.append("- Source context:")
        lines.extend(f"  - {_block_context_line(context)}" for context in finding.block_contexts)
    elif _has_unmatched_block_reference(finding.detail, block_lookup):
        lines.append("- Source context: referenced block ID was not found in normalized blocks")
    else:
        lines.append("- Source context: not available from this detail")
    lines.append("")
    return lines


def _supporting_signal_lines(signals: NoiseLayoutSignals) -> list[str]:
    groups = [
        ("table_marker_artifacts", signals.table_marker_artifacts),
        ("running_furniture_blocks", signals.running_furniture_blocks),
        ("visual_anchor_blocks", signals.visual_anchor_blocks),
        ("ambiguous_image_blocks", signals.ambiguous_image_blocks),
    ]
    non_empty = [(name, details) for name, details in groups if details]
    if not non_empty:
        return []

    lines = [
        "## Supporting Layout Signals",
        "",
        "These signals are supporting evidence from the quality report. They are not counted as review findings.",
        "",
    ]
    for name, details in non_empty:
        lines.extend([f"### {name}", ""])
        lines.extend(f"- {detail}" for detail in details)
        lines.append("")
    return lines


def _block_lookup(blocks: Sequence[dict[str, Any]]) -> dict[str, _BlockContext]:
    lookup: dict[str, _BlockContext] = {}
    for index, block in enumerate(blocks):
        block_id = _block_id(block, index)
        lookup[block_id] = _BlockContext(
            block_id=block_id,
            page_number=block.get("page_number", "unknown"),
            block_type=str(block.get("type", "unknown")),
            bbox=block.get("bbox", "unknown"),
            text=_content_text(block),
        )
    return lookup


def _block_context_line(context: _BlockContext) -> str:
    return (
        f"{context.block_id} | page={context.page_number} | type={context.block_type} | "
        f"bbox={context.bbox} | text={_preview_text(context.text)!r}"
    )


def _referenced_block_ids(detail: str, block_lookup: dict[str, _BlockContext]) -> list[str]:
    found: list[str] = []
    leading_match = LEADING_BLOCK_ID_RE.match(detail)
    if leading_match:
        leading_id = leading_match.group(1)
        if leading_id in block_lookup:
            found.append(leading_id)

    for block_id in block_lookup:
        if block_id in found:
            continue
        if _contains_block_id(detail, block_id):
            found.append(block_id)
    return found


def _has_unmatched_block_reference(detail: str, block_lookup: dict[str, _BlockContext]) -> bool:
    if _referenced_block_ids(detail, block_lookup):
        return False
    leading_match = LEADING_BLOCK_ID_RE.match(detail)
    return bool(leading_match and _looks_like_block_id(leading_match.group(1)))


def _contains_block_id(detail: str, block_id: str) -> bool:
    pattern = rf"(?<![A-Za-z0-9_-]){re.escape(block_id)}(?![A-Za-z0-9_-])"
    return re.search(pattern, detail) is not None


def _looks_like_block_id(value: str) -> bool:
    return bool(re.match(r"^(?:p\d+-[A-Za-z0-9_-]+-\d+|block\[\d+\])$", value))


def _is_metric_detail(detail: str) -> bool:
    return METRIC_DETAIL_RE.match(detail) is not None


def _blocks(document: dict[str, Any]) -> list[dict[str, Any]]:
    raw_blocks = document.get("blocks", [])
    return [block for block in raw_blocks if isinstance(block, dict)] if isinstance(raw_blocks, list) else []


def _block_id(block: dict[str, Any], index: int) -> str:
    raw_id = block.get("id")
    return raw_id if isinstance(raw_id, str) and raw_id else f"block[{index}]"


def _content_text(block: dict[str, Any]) -> str:
    content = block.get("content")
    if not isinstance(content, dict):
        return ""
    text = content.get("text")
    return text if isinstance(text, str) else ""


def _preview_text(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    if len(normalized) <= PREVIEW_CHARS:
        return normalized
    return f"{normalized[:PREVIEW_CHARS].rstrip()}..."


if __name__ == "__main__":
    raise SystemExit(main())
