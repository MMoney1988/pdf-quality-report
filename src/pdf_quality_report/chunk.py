"""Export normalized block JSON as provenance-preserving chunk records."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from json import JSONDecodeError
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "chunk_record_v0"
DEFAULT_MAX_CHARS = 1800
SHORT_TEXT_THRESHOLD = 3

CONTENT_TYPES = {"heading", "paragraph", "list_item_text", "caption", "footnote", "table"}
NOISE_TYPES = {"header", "footer"}


class ChunkExportError(Exception):
    """Base exception for chunk-record export failures."""


class InvalidChunkInputError(ChunkExportError):
    """Raised when normalized block JSON cannot be used for chunk export."""


@dataclass(frozen=True)
class NormalizedDocument:
    """Loaded normalized block document."""

    metadata: dict[str, Any]
    blocks: list[dict[str, Any]]


@dataclass(frozen=True)
class ChunkOptions:
    """Options for building chunk records."""

    max_chars: int = DEFAULT_MAX_CHARS
    include_noise: bool = False
    include_short: bool = False


@dataclass(frozen=True)
class _ExportBlock:
    block: dict[str, Any]
    block_id: str
    block_type: str
    page_number: int | None
    reading_order_index: int | None
    input_index: int
    text: str


@dataclass(frozen=True)
class ChunkRecord:
    """JSON-serializable chunk record with source provenance."""

    doc_id: str
    text: str
    meta: dict[str, Any]

    def to_json(self) -> dict[str, Any]:
        """Return the JSON object shape written to JSONL."""
        return {
            "doc_id": self.doc_id,
            "text": self.text,
            "meta": self.meta,
        }


def load_normalized_blocks(path: Path) -> NormalizedDocument:
    """Load normalized block JSON from disk.

    Args:
        path: Path to `normalized_blocks.json`.

    Returns:
        A normalized document with metadata and blocks.

    Raises:
        InvalidChunkInputError: If the JSON root is invalid or `blocks` is not a list.
    """
    try:
        raw_document = json.loads(path.read_text(encoding="utf-8"))
    except JSONDecodeError as exc:
        raise InvalidChunkInputError(f"input JSON is invalid: {exc.msg}") from exc
    except OSError as exc:
        raise ChunkExportError(f"could not read input file: {exc}") from exc

    if not isinstance(raw_document, dict):
        raise InvalidChunkInputError("input JSON root must be an object")

    metadata = raw_document.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}

    blocks = raw_document.get("blocks")
    if not isinstance(blocks, list):
        raise InvalidChunkInputError("top-level field `blocks` must be a list")

    return NormalizedDocument(metadata=metadata, blocks=[block for block in blocks if isinstance(block, dict)])


def build_chunk_records(document: NormalizedDocument, options: ChunkOptions | None = None) -> list[ChunkRecord]:
    """Build chunk records from a normalized document.

    Args:
        document: Loaded normalized document.
        options: Chunking and filtering options.

    Returns:
        Chunk records ready to write as JSONL.

    Raises:
        InvalidChunkInputError: If option values are invalid.
    """
    resolved_options = options or ChunkOptions()
    if resolved_options.max_chars < 1:
        raise InvalidChunkInputError("max_chars must be at least 1")

    source_identifier = _source_identifier(document)
    source_pdf_hash = _source_pdf_hash(document)
    records: list[ChunkRecord] = []
    current_blocks: list[_ExportBlock] = []
    current_heading: str | None = None
    current_heading_block_id: str | None = None

    for block in _export_blocks(document.blocks, resolved_options):
        if block.block_type == "heading":
            _append_record(
                records,
                current_blocks,
                section_heading=current_heading,
                section_heading_block_id=current_heading_block_id,
                source_identifier=source_identifier,
                source_pdf_hash=source_pdf_hash,
            )
            current_blocks = []
            current_heading = block.text
            current_heading_block_id = block.block_id

        if _would_exceed_max_chars(current_blocks, block, resolved_options.max_chars):
            _append_record(
                records,
                current_blocks,
                section_heading=current_heading,
                section_heading_block_id=current_heading_block_id,
                source_identifier=source_identifier,
                source_pdf_hash=source_pdf_hash,
            )
            current_blocks = []

        current_blocks.append(block)

    _append_record(
        records,
        current_blocks,
        section_heading=current_heading,
        section_heading_block_id=current_heading_block_id,
        source_identifier=source_identifier,
        source_pdf_hash=source_pdf_hash,
    )
    return records


def write_chunk_records_jsonl(records: Sequence[ChunkRecord], path: Path) -> None:
    """Write chunk records as JSON Lines.

    Args:
        records: Chunk records to write.
        path: Output path for `.jsonl`.

    Raises:
        ChunkExportError: If the output file cannot be written.
    """
    lines = [json.dumps(record.to_json(), ensure_ascii=False) for record in records]
    text = "\n".join(lines)
    if text:
        text += "\n"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    except OSError as exc:
        raise ChunkExportError(f"could not write output file: {exc}") from exc


def export_chunk_records(input_path: Path, output_path: Path, options: ChunkOptions | None = None) -> list[ChunkRecord]:
    """Load normalized blocks, build chunk records, and write JSONL output."""
    document = load_normalized_blocks(input_path)
    records = build_chunk_records(document, options)
    write_chunk_records_jsonl(records, output_path)
    return records


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint for chunk-record export."""
    parser = argparse.ArgumentParser(
        description="Export normalized block JSON as provenance-preserving chunk records.",
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
        help="Path where output .jsonl file should be written.",
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
        export_chunk_records(
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


def _export_blocks(blocks: list[dict[str, Any]], options: ChunkOptions) -> list[_ExportBlock]:
    export_blocks = [
        export_block
        for index, block in enumerate(blocks)
        if (export_block := _to_export_block(block, index, options)) is not None
    ]
    return sorted(
        export_blocks,
        key=lambda block: (
            block.page_number if block.page_number is not None else 10**12,
            block.reading_order_index if block.reading_order_index is not None else 10**12,
            block.input_index,
        ),
    )


def _to_export_block(block: dict[str, Any], input_index: int, options: ChunkOptions) -> _ExportBlock | None:
    block_type = str(block.get("type", "unknown"))
    if block_type == "image":
        return None
    if block_type in NOISE_TYPES and not options.include_noise:
        return None
    if block_type not in CONTENT_TYPES and not (options.include_noise and block_type in NOISE_TYPES):
        return None

    text = _content_text(block).strip()
    if not text:
        return None
    if not options.include_short and block_type != "heading" and len(text) <= SHORT_TEXT_THRESHOLD:
        return None

    return _ExportBlock(
        block=block,
        block_id=_block_id(block, input_index),
        block_type=block_type,
        page_number=_int_or_none(block.get("page_number")),
        reading_order_index=_int_or_none(block.get("reading_order_index")),
        input_index=input_index,
        text=text,
    )


def _append_record(
    records: list[ChunkRecord],
    blocks: list[_ExportBlock],
    *,
    section_heading: str | None,
    section_heading_block_id: str | None,
    source_identifier: str,
    source_pdf_hash: str,
) -> None:
    if not blocks:
        return

    chunk_id = f"chunk-{blocks[0].block_id}"
    records.append(
        ChunkRecord(
            doc_id=chunk_id,
            text=_joined_text(blocks),
            meta={
                "schema_version": SCHEMA_VERSION,
                "chunk_id": chunk_id,
                "block_ids": [block.block_id for block in blocks],
                "page_numbers": _page_numbers(blocks),
                "section_heading": section_heading,
                "section_heading_block_id": section_heading_block_id,
                "source_identifier": source_identifier,
                "source_pdf_hash": source_pdf_hash,
                "bbox_refs": [_bbox_ref(block) for block in blocks],
            },
        )
    )


def _would_exceed_max_chars(current_blocks: list[_ExportBlock], next_block: _ExportBlock, max_chars: int) -> bool:
    if not current_blocks:
        return False
    return len(_joined_text([*current_blocks, next_block])) > max_chars


def _joined_text(blocks: Sequence[_ExportBlock]) -> str:
    return "\n\n".join(block.text for block in blocks)


def _page_numbers(blocks: Sequence[_ExportBlock]) -> list[int]:
    return sorted({block.page_number for block in blocks if block.page_number is not None})


def _bbox_ref(block: _ExportBlock) -> dict[str, Any]:
    return {
        "block_id": block.block_id,
        "page_number": block.page_number,
        "bbox": block.block.get("bbox"),
    }


def _content_text(block: dict[str, Any]) -> str:
    content = block.get("content")
    if not isinstance(content, dict):
        return ""
    text = content.get("text")
    return text if isinstance(text, str) else ""


def _source_identifier(document: NormalizedDocument) -> str:
    metadata_value = document.metadata.get("source_identifier")
    if isinstance(metadata_value, str) and metadata_value:
        return metadata_value
    for block in document.blocks:
        provenance = block.get("provenance")
        if isinstance(provenance, dict):
            value = provenance.get("source_pdf")
            if isinstance(value, str) and value:
                return value
    return "unknown"


def _source_pdf_hash(document: NormalizedDocument) -> str:
    metadata_value = document.metadata.get("source_pdf_hash")
    if isinstance(metadata_value, str) and metadata_value:
        return metadata_value
    for block in document.blocks:
        provenance = block.get("provenance")
        if isinstance(provenance, dict):
            value = provenance.get("source_pdf_hash")
            if isinstance(value, str) and value:
                return value
    return "unknown"


def _block_id(block: dict[str, Any], input_index: int) -> str:
    raw_id = block.get("id")
    if isinstance(raw_id, str) and raw_id.strip():
        return raw_id.strip()
    return f"block-{input_index}"


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":
    raise SystemExit(main())
