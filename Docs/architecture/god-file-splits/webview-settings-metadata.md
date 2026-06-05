# WebView settingsMetadata.js

## Current Strain

- Approximate size: 668 lines.
- Risk level: medium.
- Mixed concerns: settings labels, choices, advanced fallback keys, field
  sections, page layout metadata, and browser-side compatibility metadata.

## Ideal Split

- `assets/settings/metadata/labels.js`: field and persisted-key labels.
- `assets/settings/metadata/choices.js`: choice labels and choice help.
- `assets/settings/metadata/layout.js`: page/section ordering and visibility.
- `assets/settings/metadata/advanced.js`: advanced fallback keys and display
  classification.
- Keep `settingsMetadata.js` as the namespace aggregator.

## Extraction Order

1. Extract labels.
2. Extract choices.
3. Extract layout metadata.
4. Extract advanced fallback metadata after Settings tests pin output.

## Validation

- Metadata contract tests.
- Settings WebView static tests.
- Public contract/global export checks.

## Must Not Change

Backend field metadata remains canonical; frontend metadata remains compatibility
and display support only.

