# WebView reportsView.js

## Current Strain

- Approximate size: 1,822 lines, about 124 symbol matches.
- Risk level: medium.
- Mixed concerns: reports tabs, open-target command history, key path rows,
  failure preview rendering, failure marker clear payloads, retry state,
  dependency/audit report previews, and command result handling.

## Ideal Split

- `assets/reports/tabs.js`: Reports tab navigation.
- `assets/reports/openHistory.js`: report open target labels and history lines.
- `assets/reports/failures.js`: failure preview rows, classification, marker
  clear payloads, and retry state.
- `assets/reports/audit.js`: audit report preview rendering.
- `assets/reports/dependency.js`: dependency report preview rendering.
- Keep `reportsView.js` as page coordinator.

## Extraction Order

1. Extract tab and open-history helpers.
2. Extract failure preview pure helpers.
3. Extract marker-clear payload helpers.
4. Extract audit/dependency render helpers.

## Validation

- Reports/Maintenance WebView static tests.
- Command contract tests for marker-clear commands if payloads move.
- Browser smoke for reports page when rendering changes.

## Must Not Change

Failure marker clear remains backend-owned; Reports must not directly mutate
files or marker state.

