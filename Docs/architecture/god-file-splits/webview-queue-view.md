# WebView queueView.js

## Current Strain

- Approximate size: 1,728 lines, about 88 symbol matches.
- Risk level: medium-high.
- Mixed concerns: queue payload state, scan polling, source inventory evidence,
  breakdown/runtime/validation/collision panels, excluded rows, diagnostics
  actions, filter scope, table scroll restoration, row rendering, and many
  compatibility exports.

## Ideal Split

- `assets/queue/scan.js`: scan status, polling, and source inventory evidence.
- `assets/queue/breakdown.js`: breakdown/runtime/validation/collision panels.
- `assets/queue/excludedRows.js`: excluded row rendering and detail helpers.
- `assets/queue/filterScope.js`: current filter scope and legend state.
- `assets/queue/refresh.js`: refresh/render orchestration.
- Keep `queueView.js` as the page coordinator and public export surface.

## Extraction Order

1. Extract scan/source inventory helpers.
2. Extract breakdown/runtime/validation/collision pure line builders.
3. Extract excluded-row rendering.
4. Move filter scope helpers.
5. Keep table ownership in existing `queue/table.js` and avoid duplication.

## Validation

- `npm run webview:check`
- Queue static tests.
- Launch/Queue browser readiness smoke.
- Queue large-table smoke if rendering changes.

## Must Not Change

Backend queue scope must remain authoritative; WebView filters must stay local
display filters and must not imply backend launch scope changes.

