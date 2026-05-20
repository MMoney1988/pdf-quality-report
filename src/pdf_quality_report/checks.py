"""Run minimal quality checks on normalized block documents."""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from typing import Any, cast

from .models import CheckResult, CheckStatus, NoiseLayoutSignals, QualityReport

BBOX_LENGTH = 4
BBOX_X0_INDEX = 0
BBOX_Y0_INDEX = 1
BBOX_X1_INDEX = 2
BBOX_Y1_INDEX = 3
BBOX_TOLERANCE = 0.0001
SHORT_TEXT_THRESHOLD = 3
LOW_TEXT_CHAR_THRESHOLD = 40
IMAGE_LOW_TEXT_CHAR_THRESHOLD = 120
EMPTY_TEXT_BLOCK_RATIO_THRESHOLD = 0.5
SHORT_TABLE_TEXT_THRESHOLD = 20

TEXT_BODY_TYPES = {"heading", "paragraph", "list_item_text", "caption", "footnote", "table"}
TEXT_BEARING_TYPES = TEXT_BODY_TYPES | {"header", "footer"}
SECONDARY_OR_NOISE_TYPES = {"header", "footer", "image", "separator_line"}
RUNNING_FURNITURE_TYPES = {"header", "footer"}
TABLE_MARKER_TEXTS = {"+", "|"}

REQUIRED_TOP_LEVEL_FIELDS = ("metadata", "blocks")
REQUIRED_BLOCK_FIELDS = ("id", "type", "page_number", "bbox", "relationships", "reading_order_index")
REQUIRED_PROVENANCE_FIELDS = (
    "parser_backend",
    "docling_schema",
    "docling_document_version",
    "raw_docling_ref",
    "raw_docling_label",
    "raw_docling_bbox",
    "bbox_coord_origin",
    "bbox_unit",
    "source_pdf",
)


def run_quality_checks(uif_document: dict[str, Any]) -> QualityReport:
    """Run the v0 checks on a normalized block document."""
    blocks = _blocks(uif_document)
    results = [
        check_required_field_coverage(uif_document),
        check_table_output_structure(blocks),
        check_provenance_completeness(blocks),
        check_bbox_sanity(blocks),
        check_content_vs_noise_ratio(blocks),
        check_text_usefulness(blocks),
        check_text_extraction_health(blocks),
    ]
    return QualityReport(
        total_blocks=len(blocks),
        hard_failures=sum(1 for result in results if result.status == "FAIL"),
        warnings=sum(1 for result in results if result.status == "WARN"),
        results=results,
        noise_layout_signals=collect_noise_layout_signals(blocks),
    )


def collect_noise_layout_signals(blocks: list[dict[str, Any]]) -> NoiseLayoutSignals:
    """Collect diagnostic layout/noise signals without changing check status."""
    table_marker_artifacts: list[str] = []
    running_furniture_blocks: list[str] = []
    visual_anchor_blocks: list[str] = []
    ambiguous_image_blocks: list[str] = []

    for index, block in enumerate(blocks):
        block_id = _block_id(block, index)
        block_type = str(block.get("type", "unknown"))
        normalized_text = _normalize_text(_content_text(block))

        if block_type in RUNNING_FURNITURE_TYPES:
            running_furniture_blocks.append(_signal_detail(block_id, block_type, normalized_text))
        if block_type in TEXT_BODY_TYPES and normalized_text in TABLE_MARKER_TEXTS:
            table_marker_artifacts.append(_signal_detail(block_id, block_type, normalized_text))
        if block_type == "image":
            visual_anchor_blocks.append(_signal_detail(block_id, block_type, normalized_text))
            if _is_ambiguous_image_block(block):
                ambiguous_image_blocks.append(_signal_detail(block_id, block_type, normalized_text))

    return NoiseLayoutSignals(
        table_marker_artifacts=table_marker_artifacts,
        running_furniture_blocks=running_furniture_blocks,
        visual_anchor_blocks=visual_anchor_blocks,
        ambiguous_image_blocks=ambiguous_image_blocks,
    )


def check_required_field_coverage(uif_document: dict[str, Any]) -> CheckResult:
    """Check whether required top-level and block fields are present."""
    details: list[str] = []
    for detail in _top_level_structure_issues(uif_document):
        details.append(detail)

    raw_blocks = uif_document.get("blocks")
    blocks = raw_blocks if isinstance(raw_blocks, list) else []
    for index, raw_block in enumerate(blocks):
        if not isinstance(raw_block, dict):
            details.append(f"block[{index}]: block must be an object")
            continue
        block = raw_block
        block_id = _block_id(block, index)
        missing = [field_name for field_name in REQUIRED_BLOCK_FIELDS if field_name not in block]
        details.extend(f"{block_id}: missing block field: {field_name}" for field_name in missing)
        details.extend(_missing_type_specific_fields(block, block_id))

    status: CheckStatus = "FAIL" if details else "PASS"
    summary = "all required fields present" if not details else f"{len(details)} required field issue(s)"
    return CheckResult("Required Field Coverage", status, summary, details)


def check_provenance_completeness(blocks: list[dict[str, Any]]) -> CheckResult:
    """Check whether Docling provenance is present and traceable."""
    failures: list[str] = []
    warnings: list[str] = []
    for index, block in enumerate(blocks):
        block_id = _block_id(block, index)
        provenance = block.get("provenance")
        if not isinstance(provenance, dict):
            failures.append(f"{block_id}: missing provenance object")
            continue
        for field_name in REQUIRED_PROVENANCE_FIELDS:
            if not provenance.get(field_name):
                failures.append(f"{block_id}: missing provenance field: {field_name}")
        if provenance.get("source_pdf_hash") in (None, "", "pending"):
            warnings.append(f"{block_id}: source_pdf_hash is pending or missing")

    status: CheckStatus
    if failures:
        status = "FAIL"
    elif warnings:
        status = "WARN"
    else:
        status = "PASS"
    summary = _summary_from_issues("provenance", failures, warnings)
    return CheckResult("Provenance Completeness", status, summary, [*failures, *warnings])


def check_table_output_structure(blocks: list[dict[str, Any]]) -> CheckResult:
    """Check visible table-output structure signals without judging table correctness."""
    table_blocks = [
        (index, block)
        for index, block in enumerate(blocks)
        if str(block.get("type", "unknown")) == "table"
    ]
    counts = Counter[str]()
    warnings: list[str] = []

    for index, block in table_blocks:
        block_id = _block_id(block, index)
        text = _content_text(block)
        normalized_text = _normalize_text(text)
        grid = _table_grid_signal(block)
        has_grid_signal = _has_non_empty_grid(grid)
        has_alternate_structured_signal = _has_alternate_table_structure_signal(block)
        has_text_structure_signal = _has_table_text_structure_signal(text)

        if has_grid_signal:
            counts["structured_grid_blocks"] += 1
        if has_alternate_structured_signal:
            counts["alternate_structure_signal_blocks"] += 1
        if has_text_structure_signal:
            counts["text_structure_signal_blocks"] += 1

        row_widths = _row_widths(grid)
        if len(set(row_widths)) > 1:
            counts["inconsistent_grid_blocks"] += 1
            warnings.append(
                f"{block_id}: table data_grid has inconsistent row widths: {_format_int_values(row_widths)}"
            )

        has_any_structure_signal = has_grid_signal or has_alternate_structured_signal or has_text_structure_signal
        if not normalized_text and not has_any_structure_signal:
            counts["empty_or_short_table_text_blocks"] += 1
            warnings.append(f"{block_id}: table block has no structured table signal and no markdown text")
        elif not has_any_structure_signal and len(normalized_text) <= SHORT_TABLE_TEXT_THRESHOLD:
            counts["empty_or_short_table_text_blocks"] += 1
            warnings.append(
                f"{block_id}: table block has very short table text and no obvious row/column structure signal "
                f"(chars={len(normalized_text)})"
            )
        elif not has_any_structure_signal:
            counts["plain_text_only_blocks"] += 1
            warnings.append(
                f"{block_id}: table block has plain text only and no obvious row/column structure signal "
                f"(chars={len(normalized_text)})"
            )
        elif has_grid_signal and not normalized_text:
            counts["empty_or_short_table_text_blocks"] += 1
            warnings.append(f"{block_id}: table block has structured grid signal but empty markdown content.text")

    details = [
        f"table_blocks={len(table_blocks)}",
        f"structured_grid_blocks={counts['structured_grid_blocks']}",
        f"alternate_structure_signal_blocks={counts['alternate_structure_signal_blocks']}",
        f"text_structure_signal_blocks={counts['text_structure_signal_blocks']}",
        f"plain_text_only_blocks={counts['plain_text_only_blocks']}",
        f"empty_or_short_table_text_blocks={counts['empty_or_short_table_text_blocks']}",
        f"inconsistent_grid_blocks={counts['inconsistent_grid_blocks']}",
    ]
    if not table_blocks:
        return CheckResult(
            "Table Output Structure Signals",
            "PASS",
            "no table-labeled blocks found",
            [*details, "table_blocks=0; no table-labeled blocks found"],
        )
    if warnings:
        return CheckResult(
            "Table Output Structure Signals",
            "WARN",
            f"{len(warnings)} table output structure warning(s)",
            [*details, *warnings],
        )
    return CheckResult(
        "Table Output Structure Signals",
        "PASS",
        "table-labeled blocks include visible structure signals",
        details,
    )


def check_bbox_sanity(blocks: list[dict[str, Any]]) -> CheckResult:
    """Check bbox shape, ordering, units, origin, and raw Docling consistency."""
    details: list[str] = []
    for index, block in enumerate(blocks):
        block_id = _block_id(block, index)
        bbox = block.get("bbox")
        if not _is_valid_bbox_list(bbox):
            details.append(f"{block_id}: bbox must be four finite numbers")
            continue
        bbox_values = cast(list[int | float], bbox)
        x0, y0, x1, y1 = [float(value) for value in bbox_values]
        if x0 >= x1 or y0 >= y1:
            details.append(f"{block_id}: bbox coordinates are not increasing")

        provenance = _dict_or_empty(block.get("provenance"))
        if provenance.get("bbox_coord_origin") not in {"BOTTOMLEFT", "TOPLEFT"}:
            details.append(f"{block_id}: unknown bbox_coord_origin")
        if provenance.get("bbox_unit") != "pt":
            details.append(f"{block_id}: unknown bbox_unit")
        details.extend(_raw_bbox_consistency_issues(block_id, bbox, provenance.get("raw_docling_bbox")))

    status: CheckStatus = "FAIL" if details else "PASS"
    summary = "all bboxes sane" if not details else f"{len(details)} bbox issue(s)"
    return CheckResult("BBox Sanity", status, summary, details)


def check_content_vs_noise_ratio(blocks: list[dict[str, Any]]) -> CheckResult:
    """Report content-like blocks versus secondary or likely noisy blocks."""
    type_counts = Counter(str(block.get("type", "unknown")) for block in blocks)
    content_count = sum(type_counts[block_type] for block_type in TEXT_BODY_TYPES)
    noise_count = sum(type_counts[block_type] for block_type in SECONDARY_OR_NOISE_TYPES)
    total = len(blocks)
    details = [
        f"total_blocks={total}",
        f"content_candidate_blocks={content_count}",
        f"secondary_or_noise_blocks={noise_count}",
        f"type_distribution={dict(sorted(type_counts.items()))}",
    ]
    if total == 0:
        return CheckResult("Content vs Noise Ratio", "WARN", "document has no blocks", details)
    status: CheckStatus = "WARN" if noise_count else "PASS"
    summary = f"{content_count} content-like block(s), {noise_count} secondary/noise candidate block(s)"
    return CheckResult("Content vs Noise Ratio", status, summary, details)


def check_text_usefulness(blocks: list[dict[str, Any]]) -> CheckResult:
    """Check for empty, duplicate, and suspiciously short text-bearing blocks."""
    failures: list[str] = []
    warnings: list[str] = []
    normalized_text_to_ids: dict[str, list[str]] = defaultdict(list)

    for index, block in enumerate(blocks):
        block_id = _block_id(block, index)
        block_type = str(block.get("type", "unknown"))
        if block_type not in TEXT_BEARING_TYPES:
            continue
        text = _content_text(block)
        normalized_text = _normalize_text(text)
        if not normalized_text and block_type in TEXT_BODY_TYPES:
            failures.append(f"{block_id}: empty body text")
            continue
        if normalized_text:
            normalized_text_to_ids[normalized_text].append(block_id)
        if normalized_text and len(normalized_text) <= SHORT_TEXT_THRESHOLD:
            warnings.append(f"{block_id}: very short text: {normalized_text!r}")

    duplicate_groups = sorted((sorted(ids), text) for text, ids in normalized_text_to_ids.items() if len(ids) > 1)
    warnings.extend(
        f"repeated text value {text!r} appears in block IDs: {', '.join(ids)}"
        for ids, text in duplicate_groups
    )

    status: CheckStatus
    if failures:
        status = "FAIL"
    elif warnings:
        status = "WARN"
    else:
        status = "PASS"
    summary = _summary_from_issues("text usefulness", failures, warnings)
    return CheckResult("Text Usefulness", status, summary, [*failures, *warnings])


def check_text_extraction_health(blocks: list[dict[str, Any]]) -> CheckResult:
    """Check extracted-text availability without judging text correctness."""
    total_blocks = len(blocks)
    text_bearing_blocks = 0
    non_empty_text_blocks = 0
    total_text_chars = 0
    image_blocks = 0

    for block in blocks:
        block_type = str(block.get("type", "unknown"))
        if block_type == "image":
            image_blocks += 1
        if block_type not in TEXT_BEARING_TYPES:
            continue
        text_bearing_blocks += 1
        normalized_text = _normalize_text(_content_text(block))
        if normalized_text:
            non_empty_text_blocks += 1
            total_text_chars += len(normalized_text)

    empty_text_blocks = text_bearing_blocks - non_empty_text_blocks
    empty_text_block_ratio = empty_text_blocks / text_bearing_blocks if text_bearing_blocks else 0.0
    details = [
        f"text_bearing_blocks={text_bearing_blocks}",
        f"non_empty_text_blocks={non_empty_text_blocks}",
        f"empty_text_blocks={empty_text_blocks}",
        f"total_text_chars={total_text_chars}",
        f"image_blocks={image_blocks}",
        f"empty_text_block_ratio={empty_text_block_ratio:.3f}",
    ]

    warnings: list[str] = []
    if total_blocks == 0:
        warnings.append("no_blocks: document has no blocks to evaluate")
    if total_blocks > 0 and text_bearing_blocks == 0:
        warnings.append("no_text_bearing_blocks: document has blocks but no text-bearing blocks")
    if text_bearing_blocks > 0 and non_empty_text_blocks == 0:
        warnings.append("no_non_empty_text_blocks: text-bearing blocks contain no extracted text")
    if total_blocks > 0 and total_text_chars < LOW_TEXT_CHAR_THRESHOLD:
        warnings.append(
            f"low_text_coverage: total_text_chars={total_text_chars} below threshold={LOW_TEXT_CHAR_THRESHOLD}"
        )
    if image_blocks > 0 and total_text_chars < IMAGE_LOW_TEXT_CHAR_THRESHOLD:
        warnings.append(
            "image_low_text_coverage: document contains image blocks while extracted text remains very limited "
            f"(total_text_chars={total_text_chars} below threshold={IMAGE_LOW_TEXT_CHAR_THRESHOLD})"
        )
    if text_bearing_blocks > 0 and empty_text_block_ratio > EMPTY_TEXT_BLOCK_RATIO_THRESHOLD:
        warnings.append(
            "high_empty_text_block_ratio: "
            f"empty_text_block_ratio={empty_text_block_ratio:.3f} "
            f"above threshold={EMPTY_TEXT_BLOCK_RATIO_THRESHOLD:.3f}"
        )

    if warnings:
        summary = (
            "document has no blocks to evaluate"
            if total_blocks == 0
            else f"{len(warnings)} text extraction health warning(s)"
        )
        return CheckResult("Text Extraction Health", "WARN", summary, [*details, *warnings])
    return CheckResult("Text Extraction Health", "PASS", "extracted text availability checks passed", details)


def _blocks(uif_document: dict[str, Any]) -> list[dict[str, Any]]:
    raw_blocks = uif_document.get("blocks", [])
    return [block for block in raw_blocks if isinstance(block, dict)] if isinstance(raw_blocks, list) else []


def _top_level_structure_issues(uif_document: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    for field_name in REQUIRED_TOP_LEVEL_FIELDS:
        if field_name not in uif_document:
            issues.append(f"missing top-level field: {field_name}")

    if "metadata" in uif_document and not isinstance(uif_document.get("metadata"), dict):
        issues.append("top-level field `metadata` must be an object")
    if "blocks" in uif_document and not isinstance(uif_document.get("blocks"), list):
        issues.append("top-level field `blocks` must be a list")
    return issues


def _missing_type_specific_fields(block: dict[str, Any], block_id: str) -> list[str]:
    block_type = block.get("type")
    issues: list[str] = []
    if block_type == "heading" and "level" not in block:
        issues.append(f"{block_id}: heading missing level")
    if block_type in TEXT_BEARING_TYPES:
        content = block.get("content")
        if not isinstance(content, dict) or "text" not in content:
            issues.append(f"{block_id}: text-bearing block missing content.text")
    if block_type == "image" and "base64" not in block:
        issues.append(f"{block_id}: image missing base64 placeholder")
    if block_type == "table":
        if "data_grid" not in block:
            issues.append(f"{block_id}: table missing data_grid")
        content = block.get("content")
        if not isinstance(content, dict) or "text" not in content:
            issues.append(f"{block_id}: table missing markdown content.text")
    return issues


def _is_valid_bbox_list(value: Any) -> bool:
    if not isinstance(value, list) or len(value) != BBOX_LENGTH:
        return False
    return all(isinstance(item, int | float) and math.isfinite(float(item)) for item in value)


def _raw_bbox_consistency_issues(block_id: str, bbox: Any, raw_bbox: Any) -> list[str]:
    if not _is_valid_bbox_list(bbox):
        return []
    bbox_values = cast(list[int | float], bbox)
    if not isinstance(raw_bbox, dict):
        return [f"{block_id}: missing raw_docling_bbox object"]
    expected = [
        raw_bbox.get("l"),
        raw_bbox.get("b"),
        raw_bbox.get("r"),
        raw_bbox.get("t"),
    ]
    if not _is_valid_bbox_list(expected):
        return [f"{block_id}: raw_docling_bbox is incomplete"]
    expected_values = cast(list[int | float], expected)
    if any(
        abs(float(actual) - float(wanted)) > BBOX_TOLERANCE
        for actual, wanted in zip(bbox_values, expected_values, strict=True)
    ):
        return [f"{block_id}: bbox does not match raw_docling_bbox"]
    return []


def _content_text(block: dict[str, Any]) -> str:
    content = block.get("content")
    if not isinstance(content, dict):
        return ""
    text = content.get("text")
    return text if isinstance(text, str) else ""


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _table_grid_signal(block: dict[str, Any]) -> list[list[str]]:
    for value in (
        block.get("data_grid"),
        _dict_or_empty(block.get("content")).get("data_grid"),
        _dict_or_empty(block.get("content")).get("rows"),
        block.get("rows"),
    ):
        grid = _coerce_grid(value)
        if grid:
            return grid
    return []


def _coerce_grid(value: Any) -> list[list[str]]:
    if not isinstance(value, list):
        return []
    rows: list[list[str]] = []
    for row in value:
        if isinstance(row, list):
            rows.append([_cell_text(cell) for cell in row])
    return rows


def _cell_text(value: Any) -> str:
    if isinstance(value, dict):
        text = value.get("text")
        return text if isinstance(text, str) else ""
    return str(value) if value is not None else ""


def _has_non_empty_grid(grid: list[list[str]]) -> bool:
    return any(cell.strip() for row in grid for cell in row)


def _has_alternate_table_structure_signal(block: dict[str, Any]) -> bool:
    content = _dict_or_empty(block.get("content"))
    return (
        _has_non_empty_cells(block.get("cells"))
        or _has_non_empty_cells(content.get("cells"))
        or _has_non_empty_html(block.get("html"))
        or _has_non_empty_html(content.get("html"))
    )


def _has_non_empty_cells(value: Any) -> bool:
    if not isinstance(value, list):
        return False
    return any(_cell_text(cell).strip() for cell in value)


def _has_non_empty_html(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _has_table_text_structure_signal(text: str) -> bool:
    if "\t" in text or "|" in text:
        return True
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) < 2:
        return False
    column_counts = [len(re.split(r"\s{2,}", line)) for line in lines]
    return min(column_counts) > 1 and len(set(column_counts)) == 1


def _row_widths(grid: list[list[str]]) -> list[int]:
    return [len(row) for row in grid if row]


def _format_int_values(values: list[int]) -> str:
    return ", ".join(str(value) for value in sorted(set(values)))


def _block_id(block: dict[str, Any], index: int) -> str:
    raw_id = block.get("id")
    return raw_id if isinstance(raw_id, str) and raw_id else f"block[{index}]"


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _signal_detail(block_id: str, block_type: str, normalized_text: str) -> str:
    if normalized_text:
        return f"{block_id}: type={block_type}, text={normalized_text!r}"
    return f"{block_id}: type={block_type}, text=<empty>"


def _is_ambiguous_image_block(block: dict[str, Any]) -> bool:
    base64_payload = block.get("base64")
    relationships = block.get("relationships")
    has_text = bool(_normalize_text(_content_text(block)))
    has_payload = isinstance(base64_payload, str) and bool(base64_payload.strip())
    has_relationships = isinstance(relationships, list) and bool(relationships)
    return not has_text and not has_payload and not has_relationships


def _summary_from_issues(label: str, failures: list[str], warnings: list[str]) -> str:
    if failures:
        return f"{len(failures)} {label} failure(s), {len(warnings)} warning(s)"
    if warnings:
        return f"{len(warnings)} {label} warning(s)"
    return f"{label} checks passed"
