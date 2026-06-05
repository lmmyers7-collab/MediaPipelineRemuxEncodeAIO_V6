# WebView renameView.js

## Current Strain

- Approximate size: 1,689 lines, about 138 symbol matches.
- Risk level: medium-high.
- Mixed concerns: cleaning filter editor, filter catalog loading, filename
  preview, preview/apply request collection, row selection/checking, path
  authority display, table legend, apply scope, and result rendering.

## Ideal Split

- `assets/rename/cleaningFilters.js`: filter state, term parsing, draft save,
  reset, and catalog loading.
- `assets/rename/filenamePreview.js`: clean filename preview request and result
  rendering.
- `assets/rename/selection.js`: selected/checked row state and apply scope.
- `assets/rename/pathEvidence.js`: source/final path lines and authority
  display.
- `assets/rename/applyCommands.js`: preview/apply request collection and result
  handling.
- Keep `renameView.js` as page coordinator and public export owner.

## Extraction Order

1. Extract cleaning filter pure helpers.
2. Extract row selection/checking helpers.
3. Extract path-evidence helpers.
4. Extract filename preview helpers.
5. Extract apply command helpers only after strict-confirmation tests are pinned.

## Validation

- Rename WebView static tests.
- Rename browser smoke.
- Local API rename apply tests.
- Rename safety tests.

## Must Not Change

WebView must never rename directly. Backend `confirm_apply` guard, configured
root authority, and no-mutation preview behavior must remain intact.

