# WebView queue/fileOverrides.drawer.js

## Current Strain

- Approximate size: 2,437 lines, about 159 symbol matches.
- Risk level: medium.
- Mixed concerns: drawer local state, route choices, selector normalization,
  language rules, inherited defaults, saved/effective policy evidence, form
  signatures, use-inherited buttons, command button state, API payloads, and
  rendering.

## Ideal Split

- `assets/queue/fileOverrides/selectors.js`: language lists, exact-track
  selectors, selector stream indexes, and rule normalization.
- `assets/queue/fileOverrides/defaults.js`: library defaults, inherited hints,
  and effective source labels.
- `assets/queue/fileOverrides/policyEvidence.js`: saved policy and backend
  effective evidence display helpers.
- `assets/queue/fileOverrides/formState.js`: signature, dirty-state, control
  enablement, and use-inherited state.
- `assets/queue/fileOverrides/payloads.js`: command payload construction.
- `assets/queue/fileOverrides/render.js`: drawer DOM rendering.

## Extraction Order

1. Extract pure selector/language helpers.
2. Extract default/evidence label helpers.
3. Extract form signature and state helpers.
4. Extract payload construction.
5. Move DOM rendering in small chunks after static coverage is stable.

## Validation

- WebView static tests for Queue file overrides.
- Queue file override browser smoke.
- Local API command contract tests when payloads are touched.
- No-mutation browser boundary tests.

## Must Not Change

The WebView must remain staging/display only. Backend owns file override writes,
media policy, track resolution, and route preview authority.

