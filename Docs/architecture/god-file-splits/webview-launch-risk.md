# WebView launchView.risk.js

## Current Strain

- Approximate size: 1,538 lines, about 77 symbol matches.
- Risk level: medium-high.
- Mixed concerns: settings workspace reads, media-policy value parsing,
  backend risk row normalization, unsaved patch lines, launch settings risk,
  real-media readiness lines, policy patch state, changed-key evaluation, and
  policy boundary rows.

## Ideal Split

- `assets/launch/risk/settingsAccess.js`: settings workspace and config value
  accessors.
- `assets/launch/risk/mediaPolicyValues.js`: bool/list/number parsing and
  height tolerance helpers.
- `assets/launch/risk/riskRows.js`: backend risk row normalization and risk
  summary rows.
- `assets/launch/risk/policyPatch.js`: patch state, changed keys, current and
  candidate values.
- `assets/launch/risk/policyBoundary.js`: boundary rows and status helpers.

## Extraction Order

1. Extract config accessors and scalar parsers.
2. Extract height tolerance helpers.
3. Extract risk row builders.
4. Extract policy patch helpers.
5. Move render/select helpers last.

## Validation

- Launch risk static tests.
- Settings/Launch policy browser smoke.
- Backend settings risk policy tests where mirrored logic is compared.

## Must Not Change

Frontend risk remains advisory. Backend Preview/Save and backend launch
preflight remain authoritative.

