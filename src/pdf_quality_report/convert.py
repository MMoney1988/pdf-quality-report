"""Convert exported Docling JSON into normalized block JSON.

This module consumes a DoclingDocument JSON export and emits a small
``metadata + blocks`` JSON shape that can be checked by the quality report.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

BBOX_Y1_INDEX = 3
HASH_CHUNK_SIZE = 1024 * 1024


TEXT_TYPE_MAP = {
    "section_header": "heading",
    "text": "paragraph",
    "list_item": "list_item_text",
    "page_header": "header",
    "page_footer": "footer",
    "caption": "caption",
    "footnote": "footnote",
}


@dataclass(frozen=True)
class ConversionContext:
    """Shared provenance fields for a single Docling conversion."""

    docling_schema: str | None
    docling_document_version: str | None
    source_pdf: str
    source_pdf_hash: str


def convert_docling_document(
    docling_document: dict[str, Any],
    *,
    pages: set[int] | None = None,
    source_pdf: str | None = None,
    source_pdf_hash: str | None = None,
) -> dict[str, Any]:
    """Convert a DoclingDocument dict into normalized block JSON."""
    origin = _dict_or_empty(docling_document.get("origin"))
    source_identifier = source_pdf or origin.get("filename") or docling_document.get("name") or "unknown"
    resolved_source_hash = source_pdf_hash or "pending"
    context = ConversionContext(
        docling_schema=docling_document.get("schema_name"),
        docling_document_version=docling_document.get("version"),
        source_pdf=source_identifier,
        source_pdf_hash=resolved_source_hash,
    )

    blocks: list[dict[str, Any]] = []
    blocks.extend(_convert_texts(docling_document, pages=pages, context=context))
    blocks.extend(_convert_tables(docling_document, pages=pages, context=context))
    blocks.extend(_convert_pictures(docling_document, pages=pages, context=context))

    sorted_blocks = _sort_blocks(blocks)
    for index, block in enumerate(sorted_blocks):
        block["reading_order_index"] = index

    return {
        "metadata": {
            "uif_profile": "docling_minimal_scratch_v1",
            "source_type": "pdf",
            "source_identifier": source_identifier,
            "source_pdf_hash": resolved_source_hash,
            "parser_backend": "docling",
            "docling_schema": context.docling_schema,
            "docling_document_version": context.docling_document_version,
            "docling_origin_binary_hash": origin.get("binary_hash"),
            "bbox_unit": "pt",
            "bbox_coord_origin": "BOTTOMLEFT",
            "reading_order_strategy": "page_then_top_desc_left_asc",
            "page_filter": sorted(pages) if pages else None,
        },
        "blocks": sorted_blocks,
    }


def _convert_texts(
    docling_document: dict[str, Any],
    *,
    pages: set[int] | None,
    context: ConversionContext,
) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for text_obj in docling_document.get("texts", []):
        if not isinstance(text_obj, dict):
            continue
        prov = _first_provenance(text_obj)
        if not prov or not _page_is_in_scope(prov.get("page_no"), pages):
            continue

        raw_label = str(text_obj.get("label") or "text")
        uif_type = TEXT_TYPE_MAP.get(raw_label, "paragraph")
        block = _base_block(
            context,
            source_obj=text_obj,
            uif_type=uif_type,
            prov=prov,
        )
        block["content"] = {"text": text_obj.get("text") or "", "spans": []}
        if uif_type == "heading":
            block["level"] = _infer_heading_level(text_obj.get("text") or "")
        blocks.append(block)
    return blocks


def _convert_tables(
    docling_document: dict[str, Any],
    *,
    pages: set[int] | None,
    context: ConversionContext,
) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for table_obj in docling_document.get("tables", []):
        if not isinstance(table_obj, dict):
            continue
        prov = _first_provenance(table_obj)
        if not prov or not _page_is_in_scope(prov.get("page_no"), pages):
            continue

        data_grid = _extract_table_grid(table_obj)
        block = _base_block(
            context,
            source_obj=table_obj,
            uif_type="table",
            prov=prov,
        )
        block["content"] = {"text": _table_grid_to_markdown(data_grid), "spans": []}
        block["data_grid"] = data_grid
        blocks.append(block)
    return blocks


def _convert_pictures(
    docling_document: dict[str, Any],
    *,
    pages: set[int] | None,
    context: ConversionContext,
) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for picture_obj in docling_document.get("pictures", []):
        if not isinstance(picture_obj, dict):
            continue
        prov = _first_provenance(picture_obj)
        if not prov or not _page_is_in_scope(prov.get("page_no"), pages):
            continue

        block = _base_block(
            context,
            source_obj=picture_obj,
            uif_type="image",
            prov=prov,
        )
        block["content"] = None
        block["base64"] = None
        blocks.append(block)
    return blocks


def _base_block(
    context: ConversionContext,
    *,
    source_obj: dict[str, Any],
    uif_type: str,
    prov: dict[str, Any],
) -> dict[str, Any]:
    raw_bbox = _dict_or_empty(prov.get("bbox"))
    page_number = _int_page_number(prov.get("page_no"))
    return {
        "id": _uif_id_from_ref(source_obj.get("self_ref"), page_number),
        "type": uif_type,
        "page_number": page_number,
        "bbox": _bbox_to_output_list(raw_bbox),
        "relationships": [],
        "provenance": {
            "parser_backend": "docling",
            "docling_schema": context.docling_schema,
            "docling_document_version": context.docling_document_version,
            "raw_docling_ref": source_obj.get("self_ref"),
            "raw_docling_label": source_obj.get("label"),
            "raw_docling_charspan": prov.get("charspan"),
            "raw_docling_bbox": raw_bbox,
            "bbox_coord_origin": raw_bbox.get("coord_origin"),
            "bbox_unit": "pt",
            "source_pdf": context.source_pdf,
            "source_pdf_hash": context.source_pdf_hash,
        },
    }


def _first_provenance(source_obj: dict[str, Any]) -> dict[str, Any] | None:
    prov_list = source_obj.get("prov")
    if not isinstance(prov_list, list) or not prov_list:
        return None
    first = prov_list[0]
    return first if isinstance(first, dict) else None


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _int_page_number(value: Any) -> int:
    if value is None:
        raise ValueError("Docling provenance is missing page_no")
    return int(value)


def _page_is_in_scope(page_number: Any, pages: set[int] | None) -> bool:
    if page_number is None:
        return False
    return pages is None or int(page_number) in pages


def _bbox_to_output_list(raw_bbox: dict[str, Any]) -> list[float]:
    """Return [x0, y0, x1, y1] while preserving origin details in provenance."""
    left = float(raw_bbox.get("l", 0.0))
    right = float(raw_bbox.get("r", 0.0))
    top = float(raw_bbox.get("t", 0.0))
    bottom = float(raw_bbox.get("b", 0.0))
    return [left, bottom, right, top]


def _uif_id_from_ref(self_ref: Any, page_number: Any) -> str:
    ref = str(self_ref or "unknown").strip("#/")
    safe_ref = re.sub(r"[^a-zA-Z0-9]+", "-", ref).strip("-").lower()
    return f"p{int(page_number)}-{safe_ref}" if page_number is not None else safe_ref


def _infer_heading_level(text: str) -> int:
    match = re.match(r"^\s*(\d+(?:\.\d+)*)(?:\.)?", text)
    if not match:
        return 1
    return min(max(len(match.group(1).split(".")), 1), 6)


def _extract_table_grid(table_obj: dict[str, Any]) -> list[list[str]]:
    data = table_obj.get("data")
    if not isinstance(data, dict):
        return []
    grid = data.get("grid")
    if not isinstance(grid, list):
        return []

    text_grid: list[list[str]] = []
    for row in grid:
        if not isinstance(row, list):
            continue
        text_grid.append([str(cell.get("text", "")) if isinstance(cell, dict) else "" for cell in row])
    return text_grid


def _table_grid_to_markdown(data_grid: list[list[str]]) -> str:
    if not data_grid:
        return ""
    column_count = max((len(row) for row in data_grid), default=0)
    if column_count == 0:
        return ""

    rows = [row + [""] * (column_count - len(row)) for row in data_grid]
    header = rows[0]
    lines = [
        f"| {' | '.join(header)} |",
        f"| {' | '.join(['---'] * column_count)} |",
    ]
    for row in rows[1:]:
        lines.append(f"| {' | '.join(row)} |")
    return "\n".join(lines)


def _sort_blocks(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(blocks, key=_block_sort_key)


def _block_sort_key(block: dict[str, Any]) -> tuple[int, float, float, str]:
    raw_bbox = block.get("bbox")
    bbox = raw_bbox if isinstance(raw_bbox, list) else [0.0, 0.0, 0.0, 0.0]
    x0 = float(bbox[0]) if len(bbox) > 0 else 0.0
    y1 = float(bbox[BBOX_Y1_INDEX]) if len(bbox) > BBOX_Y1_INDEX else 0.0
    return (int(block.get("page_number", 0)), -y1, x0, str(block.get("id", "")))


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(HASH_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_pages(raw_pages: str | None) -> set[int] | None:
    if not raw_pages:
        return None
    pages = {int(raw.strip()) for raw in raw_pages.split(",") if raw.strip()}
    return pages or None


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint for the converter."""
    parser = argparse.ArgumentParser(description="Convert exported Docling JSON to normalized block JSON.")
    parser.add_argument(
        "--input",
        "--docling-json",
        dest="input_path",
        required=True,
        type=Path,
        help="Path to exported DoclingDocument JSON.",
    )
    parser.add_argument(
        "--output",
        "--out",
        dest="output_path",
        required=True,
        type=Path,
        help="Path where the normalized block JSON should be written.",
    )
    parser.add_argument("--pages", help="Optional comma-separated 1-based page numbers, for example: 6 or 6,7.")
    parser.add_argument(
        "--source-pdf",
        type=Path,
        help="Optional source PDF path for identifier and SHA-256 provenance.",
    )
    args = parser.parse_args(argv)

    docling_document = json.loads(args.input_path.read_text(encoding="utf-8"))
    if not isinstance(docling_document, dict):
        raise ValueError("Docling JSON root must be an object")
    source_pdf = args.source_pdf.name if args.source_pdf else None
    source_pdf_hash = _sha256_file(args.source_pdf) if args.source_pdf else None
    uif_document = convert_docling_document(
        docling_document,
        pages=_parse_pages(args.pages),
        source_pdf=source_pdf,
        source_pdf_hash=source_pdf_hash,
    )

    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    args.output_path.write_text(json.dumps(uif_document, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
