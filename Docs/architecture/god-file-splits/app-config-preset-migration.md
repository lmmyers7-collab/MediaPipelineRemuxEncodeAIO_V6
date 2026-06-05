# app/config/preset_migration.py

## Current Strain

- Approximate size: 541 lines.
- Risk level: medium.
- Mixed concerns: preset display adaptation, migration between config shapes,
  HandBrake-style preset section data, compatibility defaults, and conversion
  helpers.

## Ideal Split

- `app/config/preset_migration_models.py`: internal migration DTO helpers.
- `app/config/preset_display_adapter.py`: HandBrake-style display conversion.
- `app/config/preset_compatibility.py`: legacy/current compatibility mapping.
- Keep `preset_migration.py` as a facade for existing imports.

## Extraction Order

1. Extract display-only adapters.
2. Extract compatibility maps.
3. Extract migration DTO helpers.
4. Leave behavior-changing migration calls in the parent until pinned.

## Validation

- Preset policy contract tests.
- Settings preview/static tests.
- Config contract tests.

## Must Not Change

Persisted config keys, display-only HandBrake section semantics, compatibility
with existing presets, and backend Preview/Save authority.

