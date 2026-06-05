# WebView domHelpers.js

## Current Strain

- Approximate size: 793 lines, about 53 symbol matches.
- Risk level: low-medium.
- Mixed concerns: DOM lookup helpers, table rendering helpers, status mapping,
  filtering, text formatting, safe HTML, and compatibility globals used across
  many page modules.

## Ideal Split

- `assets/dom/query.js`: ID/query helpers.
- `assets/dom/text.js`: safe text, escaping, formatting, and truncation.
- `assets/dom/status.js`: status state and class mapping helpers.
- `assets/dom/table.js`: row/cell/table rendering primitives.
- `assets/dom/filtering.js`: generic filter helpers.
- Keep `domHelpers.js` as namespace aggregator until callers move.

## Extraction Order

1. Extract pure text/escaping helpers.
2. Extract query helpers.
3. Extract filtering helpers.
4. Extract table helpers after table-heavy smokes are stable.

## Validation

- WebView static tests.
- Large-table browser smoke.
- Public contract/global export checks.

## Must Not Change

Shared helper names, namespace exports, escaping safety, row filtering semantics,
and script-order assumptions.

