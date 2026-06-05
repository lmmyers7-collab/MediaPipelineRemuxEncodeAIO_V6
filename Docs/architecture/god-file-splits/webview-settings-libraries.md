# WebView settingsLibraries.js

## Current Strain

- Approximate size: 1,526 lines, about 127 symbol matches.
- Risk level: medium-high.
- Mixed concerns: backend metadata access, library profile normalization,
  override eligibility, path inheritance evidence, dirty-state tracking,
  profile equivalence, override control rendering, tab state, add/delete/reset
  commands, and DOM collection.

## Ideal Split

- `assets/settings/libraries/metadata.js`: field definitions, override group
  lookup, scope/designation eligibility, and labels.
- `assets/settings/libraries/profiles.js`: normalize profile, defaults,
  comparable profile, and profile equivalence.
- `assets/settings/libraries/pathState.js`: inherited/custom path evidence and
  reset availability.
- `assets/settings/libraries/overrides.js`: override values, state text, and
  control construction.
- `assets/settings/libraries/render.js`: card, tab, command-state, and feedback
  rendering.
- `assets/settings/libraries/collect.js`: DOM-to-profile collection and patch
  payload helpers.

## Extraction Order

1. Extract metadata and scalar helpers.
2. Extract profile normalization/equivalence helpers.
3. Extract path state helpers.
4. Extract override state/control helpers.
5. Extract render/collect functions after static tests pin DOM IDs.

## Validation

- Library Profiles tests.
- Settings Libraries WebView tests.
- Metadata contract tests.
- Settings Preview/Save route tests if payload collection changes.

## Must Not Change

Backend-owned inheritance semantics, explicit override preservation, reset to
global, custom output inheritance, and legacy compatibility shapes.

