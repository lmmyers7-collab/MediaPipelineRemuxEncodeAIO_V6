# WebView settings/policyImpact.js

## Current Strain

- Approximate size: 1,479 lines, about 100 symbol matches.
- Risk level: medium-high.
- Mixed concerns: settings media-policy parsing, route height boundaries,
  language gap checks, active media policy rows, effective policy trust rows,
  changed-entry comparison, summary lines, detail lines, and rendering.

## Ideal Split

- `assets/settings/policyValues.js`: list/bool/number parsing and route height
  boundary helpers.
- `assets/settings/mediaPolicyRows.js`: active policy rows and status helpers.
- `assets/settings/effectivePolicyTrust.js`: effective policy trust rows,
  detail lines, and summary lines.
- `assets/settings/policyDelta.js`: changed-entry and unknown-entry comparison.
- Keep render orchestration in `policyImpact.js` until child modules are stable.

## Extraction Order

1. Extract scalar/list parsers.
2. Extract height boundary helpers.
3. Extract active policy row builders.
4. Extract effective trust row builders.
5. Extract delta comparison helpers.

## Validation

- Settings policy static tests.
- Settings Launch policy browser smoke.
- Backend settings risk/policy tests if mirrored text changes.

## Must Not Change

Policy impact remains read-only and display-only. Backend settings metadata and
Preview/Save remain the source of truth.

