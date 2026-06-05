# WebView launchView.js

## Current Strain

- Approximate size: 2,141 lines, about 173 symbol matches.
- Risk level: medium-high.
- Mixed concerns: tab navigation, pipeline controller state, command busy
  guards, close-readiness rendering, single-file controls, scope/mode presets,
  launch request construction, control-command confirmation, startup banner,
  and command result handling.

## Ideal Split

- `assets/launch/controllerState.js`: pipeline activity, stuck detection,
  pause/stop state, and controller status DTOs.
- `assets/launch/commandButtons.js`: button gates, busy state, disabled reasons,
  and control confirmation.
- `assets/launch/scopeControls.js`: mode/scope preset synchronization and
  single-file visibility.
- `assets/launch/startRequest.js`: request collection and preflight matching.
- `assets/launch/statusRender.js`: controller status, startup banner, and
  result messaging.
- Keep `launchView.js` as page coordinator and compatibility export owner.

## Extraction Order

1. Extract display-only status helpers.
2. Extract button gating and busy-state helpers.
3. Extract mode/scope controls.
4. Extract request builders only after command contract tests pin payloads.

## Validation

- Launch/Queue readiness browser smoke.
- Local API command contract tests.
- WebView command evidence smoke.
- Close-readiness and lifecycle tests if shutdown/control text changes.

## Must Not Change

Backend owns launch, stop, close-readiness, and duplicate-command guards.
WebView controls must not bypass backend command routes.

