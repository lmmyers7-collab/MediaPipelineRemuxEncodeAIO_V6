# WebView progressView.js

## Current Strain

- Approximate size: 1,269 lines, about 74 symbol matches.
- Risk level: medium.
- Mixed concerns: progress DTO normalization, status labels, timeline grouping,
  progress bars, run facts, queue/current item evidence, timestamp formatting,
  and Home/Progress rendering.

## Ideal Split

- `assets/progress/normalization.js`: DTO normalization and scalar helpers.
- `assets/progress/statusLabels.js`: status state, labels, and class mapping.
- `assets/progress/timeline.js`: grouped timeline row builders.
- `assets/progress/bars.js`: progress bar row builders and renderers.
- `assets/progress/homeFacts.js`: Home run facts and current item evidence.
- Keep `progressView.js` as render coordinator until callers are moved.

## Extraction Order

1. Extract status label helpers.
2. Extract timestamp/scalar normalization.
3. Extract progress bar builders.
4. Extract timeline builders.
5. Extract DOM rendering in small chunks.

## Validation

- Home live-state smoke.
- Progress/static WebView tests.
- Browser large-table smoke if timeline/table rendering changes.

## Must Not Change

Progress evidence must remain read-only and must not imply backend queue scope
or processing decisions.

