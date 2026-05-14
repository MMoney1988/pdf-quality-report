# PQR portfolio visuals

Presentation-oriented copies of the canonical documentation assets in [`../`](..).

## Boundary

- **Canonical** ([`../pqr_pipeline.svg`](../pqr_pipeline.svg), [`../pqr_before_after.svg`](../pqr_before_after.svg), [`../sample_report.html`](../sample_report.html)) explains what PQR does. Prefer these for technical accuracy and stable references in the repo.
- **Portfolio** (this folder) uses the same facts with framing suited to README embeds, proposals, and screenshots. It must not overclaim beyond the [publication policy](../publication_policy.md) and the root README.

## Files

| File | Role |
|------|------|
| `pqr_pipeline_portfolio.svg` | Pipeline diagram with portfolio footer strip and unique SVG ids (safe next to other SVGs on one page). |
| `pqr_before_after_portfolio.svg` | Before/after comparison with the same treatment. |
| `sample_report_portfolio.html` | Browser-openable sample with top chrome; same checks as canonical sample. |

## Optional PNG thumbnails

Raster exports are not committed here (binary churn). To add thumbnails locally, convert the portfolio SVGs with [resvg](https://github.com/linebender/resvg), Inkscape, or `rsvg-convert`, then attach in proposals as needed.
