from __future__ import annotations

from pdf_quality_report.interpret import interpret_quality_report
from pdf_quality_report.models import CheckResult, NoiseLayoutSignals, QualityReport


def _report(
    results: list[CheckResult],
    *,
    signals: NoiseLayoutSignals | None = None,
    total_blocks: int = 1,
) -> QualityReport:
    return QualityReport(
        total_blocks=total_blocks,
        hard_failures=sum(1 for result in results if result.status == "FAIL"),
        warnings=sum(1 for result in results if result.status == "WARN"),
        results=results,
        noise_layout_signals=signals or NoiseLayoutSignals(),
    )


def test_all_pass_interpretation_has_short_caveat() -> None:
    report = _report([CheckResult("BBox Sanity", "PASS", "all bboxes sane")])

    bullets = interpret_quality_report(report)

    assert len(bullets) == 1
    assert "No warnings or hard failures found" in bullets[0]
    assert "structurally usable for the next step" in bullets[0]
    assert "does not prove complete or semantically correct extraction" in bullets[0]
    assert report.decision == "GO"


def test_content_vs_noise_warn_gets_conservative_explanation() -> None:
    report = _report(
        [
            CheckResult(
                "Content vs Noise Ratio",
                "WARN",
                "6 content-like block(s), 2 secondary/noise candidate block(s)",
                ["content_candidate_blocks=6", "secondary_or_noise_blocks=2"],
            )
        ],
        signals=NoiseLayoutSignals(
            running_furniture_blocks=[
                "p6-texts-58: type=header, text='Technologies 2019 , 7 , 65'",
                "p6-texts-59: type=header, text='6 of 19'",
            ],
        ),
    )

    bullets = interpret_quality_report(report)

    assert any("The report treats 6 blocks as possible main document text" in bullet for bullet in bullets)
    assert any("The report treats 2 blocks as possible layout or noise elements" in bullet for bullet in bullets)
    assert any("2 blocks are typed as headers: p6-texts-58 and p6-texts-59" in bullet for bullet in bullets)
    assert not any("content-like" in bullet for bullet in bullets)
    assert not any("secondary/noise candidate" in bullet for bullet in bullets)
    assert report.decision == "REVIEW"


def test_text_usefulness_warn_splits_short_and_duplicate_examples() -> None:
    report = _report(
        [
            CheckResult(
                "Text Usefulness",
                "WARN",
                "6 text usefulness warning(s)",
                [
                    "p12-texts-601: very short text: '0.5'",
                    "p12-texts-608: very short text: '0.5'",
                    "p12-texts-605: very short text: '225'",
                    "p12-texts-604: very short text: '225'",
                    "p12-texts-615: very short text: '225'",
                    "p12-texts-607: very short text: '(a)'",
                    "duplicate normalized text across blocks: p12-texts-601, p12-texts-608",
                    "duplicate normalized text across blocks: p12-texts-604, p12-texts-605, p12-texts-615",
                    "duplicate normalized text across blocks: p12-texts-613, p12-texts-618",
                ],
            )
        ]
    )

    bullets = interpret_quality_report(report)

    assert any(
        "Text Usefulness is WARN: This report found 6 very short extracted text values and 3 repeated-text groups"
        in bullet
        for bullet in bullets
    )
    assert any("Quoted values are the actual extracted text values" in bullet for bullet in bullets)
    assert any("very short means normalized text with 3 characters or fewer" in bullet for bullet in bullets)
    assert any("Very short numeric fragments such as '0.5' and '225'" in bullet for bullet in bullets)
    assert any("Short label fragments such as '(a)'" in bullet for bullet in bullets)
    assert any("Repeated text appears in 3 group(s)" in bullet for bullet in bullets)
    assert any(
        "Repeated text value '0.5' appears in block IDs p12-texts-601 and p12-texts-608" in bullet
        for bullet in bullets
    )
    assert any(
        "Repeated text value '225' appears in block IDs p12-texts-604, p12-texts-605, and p12-texts-615" in bullet
        for bullet in bullets
    )


def test_text_usefulness_duplicate_falls_back_to_ids_when_value_is_not_available() -> None:
    report = _report(
        [
            CheckResult(
                "Text Usefulness",
                "WARN",
                "1 text usefulness warning(s)",
                ["duplicate normalized text across blocks: p12-texts-700, p12-texts-701"],
            )
        ]
    )

    bullets = interpret_quality_report(report)

    assert any("Repeated text appears in 1 group(s)" in bullet for bullet in bullets)
    assert any("p12-texts-700 and p12-texts-701" in bullet for bullet in bullets)


def test_bbox_failure_gets_failure_explanation_without_decision_change() -> None:
    report = _report(
        [
            CheckResult(
                "BBox Sanity",
                "FAIL",
                "1 bbox issue(s)",
                ["p6-texts-48: bbox coordinates are not increasing"],
            )
        ]
    )

    bullets = interpret_quality_report(report)

    assert any("BBox Sanity is FAIL" in bullet for bullet in bullets)
    assert any("Bounding-box provenance should be reviewed" in bullet for bullet in bullets)
    assert any("bbox coordinates are not increasing" in bullet for bullet in bullets)
    assert report.decision == "BLOCK"


def test_non_empty_noise_signals_explain_review_without_hard_failure() -> None:
    report = _report(
        [
            CheckResult(
                "Content vs Noise Ratio",
                "WARN",
                "1 content-like block(s), 1 secondary/noise candidate block(s)",
            )
        ],
        signals=NoiseLayoutSignals(
            running_furniture_blocks=["p6-texts-58: type=header, text='Header'"],
            visual_anchor_blocks=["p6-pictures-4: type=image, text=<empty>"],
            ambiguous_image_blocks=["p6-pictures-4: type=image, text=<empty>"],
        ),
    )

    bullets = interpret_quality_report(report)

    assert any("Layout/noise signals point to headers, footers, images, labels" in bullet for bullet in bullets)
    assert any("1 block is typed as headers: p6-texts-58" in bullet for bullet in bullets)
    assert any("1 block is typed as image: p6-pictures-4" in bullet for bullet in bullets)
    assert any(
        "Block ID p6-pictures-4 is an image block with no extracted text context" in bullet for bullet in bullets
    )
    assert not any("table marker artifact" in bullet for bullet in bullets)
    assert report.decision == "REVIEW"


def test_interpretation_is_deterministic_for_identical_input() -> None:
    report = _report(
        [
            CheckResult(
                "Text Usefulness",
                "WARN",
                "1 text usefulness warning(s)",
                ["p12-texts-601: very short text: '0.5'"],
            )
        ]
    )

    assert interpret_quality_report(report) == interpret_quality_report(report)
