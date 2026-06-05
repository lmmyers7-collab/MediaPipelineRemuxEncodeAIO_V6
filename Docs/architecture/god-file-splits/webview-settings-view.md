# WebView settingsView.js

## Current Strain

- Approximate size: 1,811 lines, about 122 symbol matches.
- Risk level: medium.
- Mixed concerns: Settings page coordination, tab navigation, builder wiring,
  raw config values, metadata-driven field display, preview/save/reload calls,
  validation rendering, and compatibility exports.

## Ideal Split

- `assets/settings/tabs.js`: tab navigation and active pane state.
- `assets/settings/pageState.js`: last settings, dirty state, and reload status.
- `assets/settings/backendCommands.js`: validate, preview, save, and reload
  request wrappers.
- `assets/settings/rawValues.js`: raw config display and redaction helpers.
- `assets/settings/builderCoordinator.js`: child builder orchestration.
- Keep `settingsView.js` as the page coordinator and namespace export owner.

## Extraction Order

1. Extract tab navigation.
2. Extract raw-value display helpers.
3. Extract backend command wrappers without changing payloads.
4. Extract builder coordination after child builder tests are stable.

## Validation

- Settings WebView static tests.
- Settings patch evidence browser smoke.
- Local API settings Preview/Save tests.

## Must Not Change

Backend owns persistence; WebView remains staging/display only and must keep
strict confirmation semantics.

