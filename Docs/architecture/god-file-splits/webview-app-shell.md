# WebView app.js

## Current Strain

- Approximate size: 1,641 lines, about 130 symbol matches.
- Risk level: medium-high.
- Mixed concerns: topbar rendering, close-readiness display, Tauri lifecycle
  alerts, backend shutdown request handling, row open actions, refresh metadata,
  Home readiness, daily-driver rows, dependency digest, and compatibility
  exports.

## Ideal Split

- `assets/app/topbar.js`: brand/version, activity, event ticker, and refresh
  time labels.
- `assets/app/closeReadiness.js`: close-readiness formatting, watcher lines,
  warnings, and shutdown rejection messages.
- `assets/app/tauriLifecycle.js`: Tauri backend lifecycle event normalization
  and alert rendering.
- `assets/app/rowOpenActions.js`: shared open-action groups.
- `assets/app/homeReadiness.js`: Home readiness/daily-driver/dependency rows.
- Keep `app.js` as bootstrap and page refresh coordinator.

## Extraction Order

1. Extract topbar display helpers.
2. Extract row open action helpers.
3. Extract Home readiness builders.
4. Extract close-readiness helpers with lifecycle tests pinned.
5. Extract Tauri lifecycle rendering.

## Validation

- WebView lifecycle smoke.
- Home live-state smoke.
- Tauri check-only when lifecycle bridge behavior is touched.
- Command evidence smoke if shutdown/result text changes.

## Must Not Change

Close readiness must fail safe, backend shutdown must remain disabled when
unsafe, and Tauri lifecycle handling must remain event-only from the WebView.

