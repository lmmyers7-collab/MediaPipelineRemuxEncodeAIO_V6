# WebView networkView.js

## Current Strain

- Approximate size: 1,449 lines, about 103 symbol matches.
- Risk level: medium-high.
- Mixed concerns: read-only network state display, worker rows, lifecycle
  handoff evidence, close-readiness context, command-contract design-only
  evidence, runtime state metadata, and selected-row rendering.

## Ideal Split

- `assets/network/workers.js`: worker row normalization and rendering.
- `assets/network/lifecycleHandoff.js`: lifecycle gate rows, status, and detail
  lines.
- `assets/network/stateFiles.js`: runtime state file metadata display.
- `assets/network/contractEvidence.js`: design-only contract evidence rows.
- `assets/network/selection.js`: selected worker/gate state.
- Keep `networkView.js` as page coordinator.

## Extraction Order

1. Extract worker row helpers.
2. Extract runtime state metadata helpers.
3. Extract contract evidence helpers.
4. Extract lifecycle handoff rows after read-only boundary tests are pinned.

## Validation

- Network read-only WebView tests.
- Local API Network contract tests.
- Browser no-mutation smoke for Network.

## Must Not Change

Network page remains read-only. No coordinator/worker lifecycle command route
or WebView control may be added by a split.

