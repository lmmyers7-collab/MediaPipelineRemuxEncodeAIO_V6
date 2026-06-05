# WebView settings/patchReview.js

## Current Strain

- Approximate size: 1,871 lines, about 122 symbol matches.
- Risk level: medium-high.
- Mixed concerns: final-library promotion rule editor, patch summary,
  settings builder guidance, persisted-key display, effective intent summary,
  HandBrake-style preview summary, and result-line rendering.

## Ideal Split

- `assets/settings/finalLibraryPromotion.js`: promotion rule rows, controls,
  payload collection, and guidance.
- `assets/settings/patchSummary.js`: changed/unknown key summaries and patch
  result formatting.
- `assets/settings/effectiveIntent.js`: effective intent and active preset
  summaries.
- `assets/settings/handbrakePreview.js`: HandBrake-style display-only preview.
- `assets/settings/resultRender.js`: reusable result lines and status text.

## Extraction Order

1. Extract display formatters.
2. Extract patch summary helpers.
3. Extract final-library promotion rule helpers.
4. Extract effective intent/preview summaries.
5. Move DOM renderers in the smallest possible chunks.

## Validation

- Settings workspace static tests.
- Settings patch evidence smoke.
- Local API settings Preview/Save tests if payload collection changes.

## Must Not Change

Backend remains authoritative for Preview/Save; WebView must keep strict
`confirm_save` boundaries and must not perform filesystem or config writes.

