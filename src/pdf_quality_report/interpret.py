"""Interpret existing quality-report results without changing decisions."""

from __future__ import annotations

import re

from .models import CheckResult, NoiseLayoutSignals, QualityReport

ALL_PASS_MESSAGE = (
    "No warnings or hard failures found. The normalized blocks look structurally usable for the next step. "
    "This does not prove complete or semantically correct extraction."
)

_VERY_SHORT_DETAIL_RE = re.compile(r"^(?P<id>[^:]+): very short text: (?P<text>.+)$")
_DUPLICATE_RE = re.compile(r"^duplicate normalized text across blocks: (?P<ids>.+)$")
_REPEATED_VALUE_RE = re.compile(r"^repeated text value (?P<text>.+) appears in block IDs: (?P<ids>.+)$")
_DETAIL_COUNT_RE = re.compile(r"^(?P<name>[a-z_]+)=(?P<count>\d+)$")
_SIGNAL_ID_RE = re.compile(r"^(?P<id>[^:]+):")
_SIGNAL_DETAIL_RE = re.compile(r"^(?P<id>[^:]+): type=(?P<type>[^,]+), text=(?P<text>.+)$")
_NUMERIC_LIKE_RE = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$")
_LABEL_LIKE_RE = re.compile(r"^\([A-Za-z0-9]+\)$")


def interpret_quality_report(report: QualityReport) -> list[str]:
    """Return deterministic human-readable interpretation bullets."""
    if report.hard_failures == 0 and report.warnings == 0:
        return [ALL_PASS_MESSAGE]

    bullets: list[str] = []
    for result in report.results:
        if result.status == "PASS":
            continue
        bullets.extend(_interpret_result(result, report.noise_layout_signals))

    bullets.extend(_interpret_noise_layout_signals(report.noise_layout_signals))

    return bullets


def _interpret_result(result: CheckResult, signals: NoiseLayoutSignals) -> list[str]:
    if result.name == "Text Usefulness":
        return _interpret_text_usefulness(result)
    if result.name == "Content vs Noise Ratio":
        return _interpret_content_vs_noise(result, signals)
    if result.name == "BBox Sanity":
        return [_interpret_bbox_sanity(result)]
    return [_interpret_generic_result(result)]


def _interpret_content_vs_noise(result: CheckResult, signals: NoiseLayoutSignals) -> list[str]:
    counts = _detail_counts(result.details)
    content_count = counts.get("content_candidate_blocks")
    layout_count = counts.get("secondary_or_noise_blocks")
    if content_count is None or layout_count is None:
        bullets = [
            f"{result.name} is {result.status}: {result.summary}.",
            "Possible layout or noise elements can include headers, footers, images, or separators and "
            "should be reviewed.",
        ]
        layout_example = _layout_non_body_examples(signals)
        if layout_example:
            bullets.append(layout_example)
        return bullets

    bullets = [
        f"{result.name} is {result.status}: "
        f"The report treats {content_count} {_plural(content_count, 'block')} as possible main document text. "
        f"The report treats {layout_count} {_plural(layout_count, 'block')} as possible layout or noise elements."
    ]
    layout_example = _layout_non_body_examples(signals)
    if layout_example:
        bullets.append(layout_example)
    return bullets


def _interpret_bbox_sanity(result: CheckResult) -> str:
    examples = _detail_examples(result.details)
    suffix = f" Examples: {examples}." if examples else ""
    return f"{result.name} is {result.status}: {result.summary}. Bounding-box provenance should be reviewed.{suffix}"


def _interpret_text_usefulness(result: CheckResult) -> list[str]:
    numeric_examples, label_examples, duplicate_examples, duplicate_group_count = _text_usefulness_examples(
        result.details
    )
    very_short_count = len(_very_short_text_by_id(result.details))
    if not very_short_count and not duplicate_group_count:
        bullets = [f"{result.name} is {result.status}: {result.summary}."]
    else:
        bullets = [
            f"{result.name} is {result.status}: This report found "
            f"{very_short_count} very short extracted text {_plural(very_short_count, 'value')} "
            f"and {duplicate_group_count} repeated-text {_plural(duplicate_group_count, 'group')}."
        ]
        bullets.append(
            "These findings come from extracted text blocks. Quoted values are the actual extracted text values, "
            "and block IDs show where they came from in the normalized output."
        )
    if very_short_count:
        bullets.append("In this report, very short means normalized text with 3 characters or fewer.")
    if numeric_examples:
        bullets.append(
            f"Very short numeric fragments such as {_format_quoted_examples(numeric_examples)} "
            "are common in chart ticks, figure labels, or repeated headers, footers, or page labels."
        )
    if label_examples:
        bullets.append(
            f"Short label fragments such as {_format_quoted_examples(label_examples)} "
            "are common in subfigure labels or other layout labels."
        )
    if duplicate_group_count:
        bullets.append(_duplicate_text_bullet(duplicate_group_count, duplicate_examples))
    if len(bullets) == 1:
        examples = _detail_examples(result.details)
        if examples:
            bullets.append(f"Examples: {examples}.")
    return bullets


def _interpret_generic_result(result: CheckResult) -> str:
    examples = _detail_examples(result.details)
    suffix = f" Examples: {examples}." if examples else ""
    return f"{result.name} is {result.status}: {result.summary}.{suffix}"


def _interpret_noise_layout_signals(signals: NoiseLayoutSignals) -> list[str]:
    bullets: list[str] = []
    if any(
        (
            signals.table_marker_artifacts,
            signals.running_furniture_blocks,
            signals.visual_anchor_blocks,
            signals.ambiguous_image_blocks,
        )
    ):
        bullets.append(
            "Layout/noise signals point to headers, footers, images, labels, or other non-main-text elements "
            "that may need review before reuse."
        )

    table_ids = _signal_ids(signals.table_marker_artifacts)
    if table_ids:
        bullets.append(
            f"Table-marker artifacts: {len(table_ids)} signal(s), including {_format_id_examples(table_ids)}."
        )

    ambiguous_ids = _signal_ids(signals.ambiguous_image_blocks)
    if ambiguous_ids:
        bullets.extend(_ambiguous_image_bullets(signals.ambiguous_image_blocks))
    return bullets


def _detail_examples(details: list[str], limit: int = 2) -> str:
    return "; ".join(details[:limit])


def _text_usefulness_examples(details: list[str]) -> tuple[list[str], list[str], list[str], int]:
    numeric_examples: list[str] = []
    label_examples: list[str] = []
    short_text_by_id = _very_short_text_by_id(details)
    duplicate_groups = _duplicate_id_groups(details)
    duplicate_examples = _repeated_value_examples(short_text_by_id, duplicate_groups, limit=3)

    for text in short_text_by_id.values():
        if _NUMERIC_LIKE_RE.fullmatch(text) and text not in numeric_examples:
            numeric_examples.append(text)
        elif _LABEL_LIKE_RE.fullmatch(text) and text not in label_examples:
            label_examples.append(text)

    return numeric_examples[:3], label_examples[:3], duplicate_examples, len(duplicate_groups)


def _detail_counts(details: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for detail in details:
        match = _DETAIL_COUNT_RE.match(detail)
        if match:
            counts[match.group("name")] = int(match.group("count"))
    return counts


def _leading_count(text: str) -> int | None:
    first_token = text.split(maxsplit=1)[0] if text else ""
    return int(first_token) if first_token.isdigit() else None


def _layout_non_body_examples(signals: NoiseLayoutSignals) -> str | None:
    bullets: list[str] = []
    furniture_records = _signal_records(signals.running_furniture_blocks)
    furniture_ids = [record["id"] for record in furniture_records]
    explicit_furniture_ids = [
        record["id"] for record in furniture_records if record["type"] in {"header", "footer"}
    ]
    if explicit_furniture_ids and len(explicit_furniture_ids) == len(furniture_ids):
        bullets.append(
            f"{len(furniture_ids)} {_plural(len(furniture_ids), 'block')} "
            f"{_plural_verb(len(furniture_ids))} typed as {_furniture_type_label(furniture_records)}: "
            f"{_format_id_examples(furniture_ids)}."
        )
    elif furniture_ids:
        bullets.append(
            f"{len(furniture_ids)} {_plural(len(furniture_ids), 'block')} "
            f"{_plural_verb(len(furniture_ids))} flagged as header/footer-like: {_format_id_examples(furniture_ids)}."
        )

    image_records = _signal_records(signals.visual_anchor_blocks)
    image_ids = [record["id"] for record in image_records]
    explicit_image_ids = [record["id"] for record in image_records if record["type"] == "image"]
    if explicit_image_ids and len(explicit_image_ids) == len(image_ids):
        bullets.append(
            f"{len(image_ids)} {_plural(len(image_ids), 'block')} "
            f"{_plural_verb(len(image_ids))} typed as image: {_format_id_examples(image_ids)}."
        )
    elif image_ids:
        bullets.append(
            f"{len(image_ids)} image/figure-related {_plural(len(image_ids), 'block')}: "
            f"{_format_id_examples(image_ids)}."
        )

    if not bullets:
        return None
    return " ".join(bullets)


def _ambiguous_image_bullets(details: list[str]) -> list[str]:
    bullets: list[str] = []
    for record in _signal_records(details):
        if record["type"] == "image" and record["text"] == "<empty>":
            bullets.append(
                f"Block ID {record['id']} is an image block with no extracted text context."
            )
        else:
            bullets.append(
                f"Block ID {record['id']} is flagged as an image block without enough extracted context."
            )
    return bullets


def _signal_ids(details: list[str]) -> list[str]:
    ids: list[str] = []
    for detail in details:
        match = _SIGNAL_ID_RE.match(detail)
        if match:
            ids.append(match.group("id"))
    return ids


def _signal_records(details: list[str]) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for detail in details:
        match = _SIGNAL_DETAIL_RE.match(detail)
        if match:
            records.append(match.groupdict())
            continue
        id_match = _SIGNAL_ID_RE.match(detail)
        if id_match:
            records.append({"id": id_match.group("id"), "type": "", "text": ""})
    return records


def _furniture_type_label(records: list[dict[str, str]]) -> str:
    types = {record["type"] for record in records}
    if types == {"header"}:
        return "headers"
    if types == {"footer"}:
        return "footers"
    return "headers/footers"


def _very_short_text_by_id(details: list[str]) -> dict[str, str]:
    examples: dict[str, str] = {}
    for detail in details:
        short_match = _VERY_SHORT_DETAIL_RE.match(detail)
        if short_match:
            examples[short_match.group("id")] = _unquote(short_match.group("text"))
    return examples


def _duplicate_id_groups(details: list[str]) -> list[tuple[list[str], str | None]]:
    groups: list[tuple[list[str], str | None]] = []
    for detail in details:
        repeated_value_match = _REPEATED_VALUE_RE.match(detail)
        if repeated_value_match:
            groups.append(
                (
                    [block_id.strip() for block_id in repeated_value_match.group("ids").split(",")],
                    _unquote(repeated_value_match.group("text")),
                )
            )
            continue
        duplicate_match = _DUPLICATE_RE.match(detail)
        if duplicate_match:
            groups.append(([block_id.strip() for block_id in duplicate_match.group("ids").split(",")], None))
    return groups


def _repeated_value_examples(
    short_text_by_id: dict[str, str],
    duplicate_groups: list[tuple[list[str], str | None]],
    *,
    limit: int,
) -> list[str]:
    examples: list[str] = []
    for group, recorded_value in duplicate_groups:
        if recorded_value is not None:
            examples.append(f"Repeated text value {recorded_value!r} appears in block IDs {_format_id_examples(group)}")
            if len(examples) == limit:
                break
            continue
        values = [short_text_by_id.get(block_id) for block_id in group]
        if not values or any(value is None for value in values):
            continue
        unique_values = set(values)
        if len(unique_values) != 1:
            continue
        value = next(iter(unique_values))
        examples.append(f"Repeated text value {value!r} appears in block IDs {_format_id_examples(group)}")
        if len(examples) == limit:
            break
    if examples:
        return examples
    return [
        f"Repeated text appears in block IDs {_format_id_examples(group)}"
        for group, _recorded_value in duplicate_groups[:limit]
    ]


def _duplicate_text_bullet(duplicate_group_count: int, duplicate_examples: list[str]) -> str:
    if duplicate_examples:
        return (
            f"Repeated text appears in {duplicate_group_count} group(s). "
            f"Examples: {_format_sentence_list(duplicate_examples)}."
        )
    return (
        f"Repeated text appears in {duplicate_group_count} group(s), "
        "but repeated values are not in the detail strings."
    )


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] == "'":
        return value[1:-1]
    return value


def _format_quoted_examples(examples: list[str]) -> str:
    return _format_phrase_list([repr(example) for example in examples])


def _format_id_examples(examples: list[str]) -> str:
    return _format_phrase_list(examples)


def _format_phrase_list(items: list[str]) -> str:
    if len(items) <= 2:
        return " and ".join(items)
    return f"{', '.join(items[:-1])}, and {items[-1]}"


def _format_sentence_list(items: list[str]) -> str:
    return "; ".join(items)


def _plural(count: int, noun: str) -> str:
    return noun if count == 1 else f"{noun}s"


def _plural_verb(count: int) -> str:
    return "is" if count == 1 else "are"
