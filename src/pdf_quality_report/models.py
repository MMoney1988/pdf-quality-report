"""Typed models for minimal PDF quality reports."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

CheckStatus = Literal["PASS", "WARN", "FAIL"]
ReportDecision = Literal["GO", "REVIEW", "BLOCK"]


@dataclass(frozen=True)
class CheckResult:
    """Result for a single quality check."""

    name: str
    status: CheckStatus
    summary: str
    details: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class NoiseLayoutSignals:
    """Diagnostic signals for likely layout noise and non-text anchors."""

    table_marker_artifacts: list[str] = field(default_factory=list)
    running_furniture_blocks: list[str] = field(default_factory=list)
    visual_anchor_blocks: list[str] = field(default_factory=list)
    ambiguous_image_blocks: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class QualityReport:
    """Aggregated quality-report result."""

    total_blocks: int
    hard_failures: int
    warnings: int
    results: list[CheckResult]
    noise_layout_signals: NoiseLayoutSignals = field(default_factory=NoiseLayoutSignals)

    @property
    def decision(self) -> ReportDecision:
        """Conservative downstream-use decision derived from check statuses."""
        if self.hard_failures:
            return "BLOCK"
        if self.warnings:
            return "REVIEW"
        return "GO"
