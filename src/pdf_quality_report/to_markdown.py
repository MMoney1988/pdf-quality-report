"""Convert normalized block JSON to clean Markdown for downstream review."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

# Block types that carry meaningful text content for downstream use.
CONTENT_TYPES = {"heading", "paragraph", "list_item_text", "caption", "footnote", "table"}

# Block types filtered out by default (repeating page furniture).
NOISE_TYPES = {"header", "footer"}

# Very short text blocks are likely chart labels or layout artifacts.
SHORT_TEXT_THRESHOLD = 3


def blocks_to_markdown(
    blocks: list[dict[str, Any]],
    *,
    include_noise: bool = False,
    include_source_refs: bool = True,
    skip_short_fragments: bool = True,
) -> str:
    """Convert a list of normalized blocks to Markdown.

    Args:
        blocks: List of normalized block dicts.
        include_noise: If True, include header/footer blocks (default: filter them).
        include_source_refs: If True, add HTML comments with page/block provenance.
        skip_short_fragments: If True, skip very short text blocks (chart labels etc.).

    Returns:
        Clean Markdown string for downstream review or RAG ingestion preparation.
    """
    lines: list[str] = []
    current_page: int | None = None

    for block in blocks:
        block_type = str(block.get("type", "unknown"))
        block_id = str(block.get("id", "unknown"))
        page_number = block.get("page_number")

        # Filter noise blocks unless explicitly requested.
        if not include_noise and block_type in NOISE_TYPES:
            continue

        # Filter image blocks — they have no text content for Markdown.
        if block_type == "image":
            if include_source_refs:
                lines.append(f"<!-- image: {block_id}, page {page_number} -->")
                lines.append("")
            continue

        text = _content_text(block)
        normalized = text.strip()

        # Skip very short fragments (chart axis labels, sub-figure markers).
        if skip_short_fragments and len(normalized) <= SHORT_TEXT_THRESHOLD:
            continue

        # Skip empty text blocks.
        if not normalized:
            continue

        # Page separator comment.
        if include_source_refs and page_number != current_page:
            if current_page is not None:
                lines.append("---")
                lines.append("")
            current_page = page_number

        # Source reference comment.
        if include_source_refs:
            lines.append(f"<!-- {block_id} | page {page_number} | {block_type} -->")

        # Convert block to Markdown by type.
        if block_type == "heading":
            level = block.get("level", 1)
            prefix = "#" * min(max(level, 1), 6)
            lines.append(f"{prefix} {normalized}")
        elif block_type == "list_item_text":
            lines.append(f"- {normalized}")
        elif block_type == "caption":
            lines.append(f"*{normalized}*")
        elif block_type == "footnote":
            footnote_id = _footnote_id(block.get("id"))
            if footnote_id:
                lines.append(f"[^{footnote_id}]: {normalized}")
            else:
                lines.append(normalized)
        elif block_type == "table":
            # Tables already store Markdown in content.text.
            lines.append(normalized)
        elif block_type in NOISE_TYPES:
            # Only reached when include_noise=True.
            lines.append(f"> {normalized}")
        else:
            # paragraph and any unknown type — plain text.
            lines.append(normalized)

        lines.append("")

    return "\n".join(lines).rstrip() + "\n" if lines else ""


def convert_uif_to_markdown(uif_document: dict[str, Any], **kwargs: Any) -> str:
    """Convert a full normalized block document to Markdown.

    Extracts metadata into YAML front matter, then converts blocks.
    """
    metadata = uif_document.get("metadata", {})
    blocks = uif_document.get("blocks", [])
    if not isinstance(blocks, list):
        blocks = []

    front_matter = _build_front_matter(metadata)
    body = blocks_to_markdown(blocks, **kwargs)

    if front_matter and body:
        return front_matter + "\n" + body
    return front_matter + body


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint for Markdown conversion."""
    parser = argparse.ArgumentParser(
        description="Convert normalized block JSON to clean Markdown.",
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
        "--include-noise",
        action="store_true",
        default=False,
        help="Include header/footer blocks in output.",
    )
    parser.add_argument(
        "--no-source-refs",
        action="store_true",
        default=False,
        help="Omit source reference comments.",
    )
    parser.add_argument(
        "--include-short",
        action="store_true",
        default=False,
        help="Include very short text fragments (chart labels etc.).",
    )
    args = parser.parse_args(argv)

    document = json.loads(args.input_path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        print("Error: Input JSON root must be an object")
        return 1

    markdown = convert_uif_to_markdown(
        document,
        include_noise=args.include_noise,
        include_source_refs=not args.no_source_refs,
        skip_short_fragments=not args.include_short,
    )
    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    args.output_path.write_text(markdown, encoding="utf-8")
    return 0


def _content_text(block: dict[str, Any]) -> str:
    content = block.get("content")
    if not isinstance(content, dict):
        return ""
    text = content.get("text")
    return text if isinstance(text, str) else ""


def _footnote_id(raw_id: Any) -> str | None:
    if not isinstance(raw_id, str):
        return None
    footnote_id = raw_id.strip()
    if not footnote_id or footnote_id.lower() == "unknown":
        return None
    return footnote_id


def _build_front_matter(metadata: Any) -> str:
    """Build YAML front matter from metadata dict."""
    if not isinstance(metadata, dict) or not metadata:
        return ""
    lines = ["---"]
    for key, value in metadata.items():
        if isinstance(value, list):
            lines.append(f"{key}:")
            for item in value:
                lines.append(f"  - {item}")
        else:
            lines.append(f"{key}: {value}")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
