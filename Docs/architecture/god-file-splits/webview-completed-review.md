# WebView completedView.review.js

## Current Strain

- Approximate size: 1,702 lines, about 104 symbol matches.
- Risk level: medium-high.
- Mixed concerns: integrity status, workflow lines, healthy-row heuristics,
  benign outcome classification, review board rows, investigation filters,
  size review rows, digest summaries, and rendering.

## Ideal Split

- `assets/completed/review/integrity.js`: integrity status and lines.
- `assets/completed/review/healthSignals.js`: healthy/benign row predicates.
- `assets/completed/review/reviewRows.js`: review row reasons, board rows,
  digest status, and actions.
- `assets/completed/review/investigationFilters.js`: filter labels and matching.
- `assets/completed/review/sizeReview.js`: size delta and size review rows.

## Extraction Order

1. Extract size delta helpers.
2. Extract health/benign predicates.
3. Extract investigation filter helpers.
4. Extract review row builders.
5. Extract render functions last.

## Validation

- Completed row detail smoke.
- Completed/Pending proof smoke.
- Static tests for investigation filters and rendered row status.

## Must Not Change

Review statuses must remain advisory evidence, not backend acceptance or repair
authority.

