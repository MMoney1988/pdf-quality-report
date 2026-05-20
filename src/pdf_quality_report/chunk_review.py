"""Render chunk records as human-readable review Markdown."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from pdf_quality_report.chunk import (
    DEFAULT_MAX_CHARS,
    ChunkExportError,
    ChunkOptions,
    ChunkRecord,
    build_chunk_records,
    load_normalized_blocks,
)

PREVIEW_CHARS = 200


def render_chunk_review_markdown(records: Sequence[ChunkRecord]) -> str:
    """Render chunk records as Markdown for human review.

    Args:
        records: Chunk records created by `build_chunk_records`.

    Returns:
        Markdown review document.
    """
    lines = [
        "# Chunk Review",
        "",
        "## Summary",
        "",
        f"- **Chunks:** {len(records)}",
        f"- **Pages covered:** {_pages_covered(records)}",
        f"- **Total characters:** {sum(len(record.text) for record in records)}",
        f"- **Distinct nearest headings:** {_section_count(records)}",
        "",
        "## Chunks",
        "",
    ]

    if not records:
        lines.append("_No chunks exported._")
        lines.append("")
        return "\n".join(lines)

    for index, record in enumerate(records):
        if index:
            lines.extend(["---", ""])
        lines.extend(_chunk_lines(record))

    return "\n".join(lines).rstrip() + "\n"


def export_chunk_review_markdown(
    input_path: Path,
    output_path: Path,
    options: ChunkOptions | None = None,
) -> list[ChunkRecord]:
    """Build chunk records and write a Markdown review document.

    Args:
        input_path: Path to a normalized blocks JSON file.
        output_path: Path where the review Markdown should be written.
        options: Chunk export options passed through to `build_chunk_records`.

    Returns:
        The chunk records rendered into the Markdown review document.
    """
    document = load_normalized_blocks(input_path)
    records = build_chunk_records(document, options)
    markdown = render_chunk_review_markdown(records)
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown, encoding="utf-8")
    except OSError as exc:
        raise ChunkExportError(f"could not write output file: {exc}") from exc
    return records


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint for chunk review Markdown export."""
    parser = argparse.ArgumentParser(
        description="Render chunk records as human-readable review Markdown.",
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
        help="Path where output .md file should be written.",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=DEFAULT_MAX_CHARS,
        help=f"Maximum chunk size in characters. Splits only at block boundaries. Default: {DEFAULT_MAX_CHARS}.",
    )
    parser.add_argument(
        "--include-noise",
        action="store_true",
        default=False,
        help="Include header/footer text blocks in output.",
    )
    parser.add_argument(
        "--include-short",
        action="store_true",
        default=False,
        help="Include very short non-heading text fragments.",
    )
    args = parser.parse_args(argv)

    try:
        export_chunk_review_markdown(
            args.input_path,
            args.output_path,
            ChunkOptions(
                max_chars=args.max_chars,
                include_noise=args.include_noise,
                include_short=args.include_short,
            ),
        )
    except ChunkExportError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


def _chunk_lines(record: ChunkRecord) -> list[str]:
    meta = record.meta
    lines = [
        f"### {record.doc_id}",
        "",
        f"**Citation:** {_meta_text(meta.get('citation'))}",
        f"**Section path:** {_section_path(meta.get('section_path'))}",
        f"**Pages:** {_page_numbers(meta.get('page_numbers'))}",
        f"**Blocks:** {_block_ids(meta.get('block_ids'))}",
        f"**Characters:** {len(record.text)}",
        f"**BBox refs:** {_bbox_ref_count(meta.get('bbox_refs'))}",
        "",
        "**Preview:**",
        "",
        *_preview_lines(record.text),
        "",
    ]
    return lines


def _pages_covered(records: Sequence[ChunkRecord]) -> str:
    pages = sorted(
        {
            page
            for record in records
            for page in _list_value(record.meta.get("page_numbers"))
            if isinstance(page, int)
        }
    )
    return _format_number_list(pages)


def _section_count(records: Sequence[ChunkRecord]) -> int:
    sections = {
        section
        for record in records
        if isinstance((section := record.meta.get("section_heading")), str) and section
    }
    return len(sections)


def _section_path(value: object) -> str:
    path = [item for item in _list_value(value) if isinstance(item, str) and item]
    if not path:
        return "none"
    return " -> ".join(path)


def _page_numbers(value: object) -> str:
    pages = [page for page in _list_value(value) if isinstance(page, int)]
    return _format_number_list(pages)


def _block_ids(value: object) -> str:
    block_ids = [block_id for block_id in _list_value(value) if isinstance(block_id, str) and block_id]
    if not block_ids:
        return "none"
    return ", ".join(block_ids)


def _bbox_ref_count(value: object) -> int:
    return len(_list_value(value))


def _preview_lines(text: str) -> list[str]:
    preview = _preview_text(text)
    if not preview:
        return [">"]
    return [f"> {line}" if line else ">" for line in preview.splitlines()]


def _preview_text(text: str) -> str:
    normalized = text.strip()
    if len(normalized) <= PREVIEW_CHARS:
        return normalized
    return f"{normalized[:PREVIEW_CHARS].rstrip()}..."


def _format_number_list(values: Sequence[int]) -> str:
    unique_values = sorted(set(values))
    if not unique_values:
        return "none"
    return ", ".join(str(value) for value in unique_values)


def _meta_text(value: object) -> str:
    if isinstance(value, str) and value:
        return value
    return "none"


def _list_value(value: object) -> list[object]:
    return value if isinstance(value, list) else []


if __name__ == "__main__":
    raise SystemExit(main())
