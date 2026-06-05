# app/config/library_profiles.py

## Current Strain

- Approximate size: 1,385 lines, 64 definitions.
- Risk level: medium-high.
- Mixed concerns: profile coercion, defaults, path inheritance, override reset,
  effective settings, UI state rows, wizard payload conversion, promotion rules,
  legacy key mirroring, validation, and signatures.

## Ideal Split

- `app/config/library_profile_defaults.py`: default tracking and default
  editor/video/subtitle/audio/media values.
- `app/config/library_profile_normalization.py`: coercion, slugs,
  designation, path inheritance, and legacy override normalization.
- `app/config/library_profile_state.py`: path field state, setting override
  state, and effective settings.
- `app/config/library_profile_wizard.py`: wizard row conversion.
- `app/config/library_profile_promotion.py`: promotion rule generation and
  legacy key mirroring.
- `app/config/library_profile_validation.py`: overlap and raw override
  validation.

## Extraction Order

1. Extract defaults and pure coercion helpers.
2. Extract state/effective settings helpers.
3. Extract wizard conversion.
4. Extract promotion and legacy mirroring.
5. Extract validation last.

## Validation

- Library profile contract tests.
- Settings workspace and metadata tests.
- Config contract/schema checks.
- WebView Settings Library Profiles coverage.

## Must Not Change

Inherited versus explicit override semantics, reset-to-global behavior, legacy
compatibility keys, promotion destination rules, and library-effective-settings
scope.

