"""Export static review bundles from normalized block JSON."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from .checks import run_quality_checks
from .chunk import (
    ChunkExportError,
    ChunkRecord,
    build_chunk_records,
    load_normalized_blocks,
)
from .chunk_review import render_chunk_review_markdown
from .report import load_uif_document, render_markdown_report
from .review_findings import render_review_findings_markdown
from .to_markdown import convert_uif_to_markdown

BUNDLE_FILES = (
    "README.md",
    "quality_report.md",
    "review_findings.md",
    "output.md",
    "chunk_records.jsonl",
    "chunk_review.md",
)


class ReviewBundleExportError(Exception):
    """Raised when a review bundle cannot be exported."""


@dataclass(frozen=True)
class ReviewBundleResult:
    """Result metadata for a written review bundle."""

    output_dir: Path
    files: tuple[str, ...]
    decision: str
    total_blocks: int
    warnings: int
    hard_failures: int


def export_review_bundle(input_path: Path, output_dir: Path) -> ReviewBundleResult:
    """Build and write all static review bundle artifacts.

    Args:
        input_path: Path to a normalized blocks JSON file.
        output_dir: Directory where bundle files should be written.

    Returns:
        Result metadata for the written bundle.
    """
    if output_dir.exists() and not output_dir.is_dir():
        raise ReviewBundleExportError("output directory path exists and is not a directory")

    bundle = _build_bundle(input_path)
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        for filename, content in bundle.files.items():
            (output_dir / filename).write_text(content, encoding="utf-8")
    except OSError as exc:
        raise ReviewBundleExportError(f"could not write bundle output: {exc}") from exc

    return ReviewBundleResult(
        output_dir=output_dir,
        files=tuple(bundle.files),
        decision=bundle.decision,
        total_blocks=bundle.total_blocks,
        warnings=bundle.warnings,
        hard_failures=bundle.hard_failures,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint for review bundle export."""
    parser = argparse.ArgumentParser(
        description="Export a static PQR review bundle from normalized block JSON.",
    )
    parser.add_argument(
        "--input",
        dest="input_path",
        required=True,
        type=Path,
        help="Path to normalized block JSON.",
    )
    parser.add_argument(
        "--output-dir",
        "--out-dir",
        dest="output_dir",
        required=True,
        type=Path,
        help="Directory where review bundle files should be written.",
    )
    args = parser.parse_args(argv)

    try:
        export_review_bundle(args.input_path, args.output_dir)
    except (ReviewBundleExportError, ChunkExportError, OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


@dataclass(frozen=True)
class _BundleContent:
    files: dict[str, str]
    decision: str
    total_blocks: int
    warnings: int
    hard_failures: int


def _build_bundle(input_path: Path) -> _BundleContent:
    document = load_uif_document(input_path)
    normalized_document = load_normalized_blocks(input_path)
    report = run_quality_checks(document)
    chunk_records = build_chunk_records(normalized_document)
    chunk_jsonl = _chunk_records_jsonl(chunk_records)
    payloads = {
        "README.md": _bundle_readme(
            total_blocks=report.total_blocks,
            warnings=report.warnings,
            hard_failures=report.hard_failures,
            decision=report.decision,
            chunk_count=len(chunk_records),
        ),
        "quality_report.md": render_markdown_report(report),
        "review_findings.md": render_review_findings_markdown(report, normalized_document.blocks),
        "output.md": convert_uif_to_markdown(document),
        "chunk_records.jsonl": chunk_jsonl,
        "chunk_review.md": render_chunk_review_markdown(chunk_records),
    }
    files = {filename: payloads[filename] for filename in BUNDLE_FILES}
    return _BundleContent(
        files=files,
        decision=report.decision,
        total_blocks=report.total_blocks,
        warnings=report.warnings,
        hard_failures=report.hard_failures,
    )


def _chunk_records_jsonl(chunk_records: Sequence[ChunkRecord]) -> str:
    lines = [json.dumps(record.to_json(), ensure_ascii=False) for record in chunk_records]
    text = "\n".join(lines)
    return f"{text}\n" if text else ""


def _bundle_readme(
    *,
    total_blocks: int,
    warnings: int,
    hard_failures: int,
    decision: str,
    chunk_count: int,
) -> str:
    lines = [
        "# PQR Review Bundle",
        "",
        "This is a static review bundle generated from normalized parser output.",
        "",
        "## Summary",
        "",
        f"- decision: {decision}",
        f"- total_blocks: {total_blocks}",
        f"- warnings: {warnings}",
        f"- hard_failures: {hard_failures}",
        f"- chunks: {chunk_count}",
        "",
        "## Files",
        "",
        "- `quality_report.md`: deterministic quality report with GO/REVIEW/BLOCK decision.",
        "- `review_findings.md`: WARN/FAIL details with source context when available.",
        "- `output.md`: clean Markdown export from normalized blocks.",
        "- `chunk_records.jsonl`: provenance-preserving chunk records.",
        "- `chunk_review.md`: human-reviewable Markdown view of chunk records.",
        "",
        "## Boundaries",
        "",
        "- This bundle does not approve, correct, or remove parser-output blocks.",
        "- This bundle is not a workflow system, task tracker, dashboard, ZIP package, or manifest schema.",
        "- This bundle does not validate OCR accuracy, table reconstruction, parser correctness, or downstream "
        "readiness.",
        "- The export exits successfully when bundle files are written, even if the report decision is REVIEW or "
        "BLOCK.",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
