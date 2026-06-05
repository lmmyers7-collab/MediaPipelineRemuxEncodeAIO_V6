# ops/pipeline/engine/config/config_schema.ps1

## Current Strain

- Approximate size: 1,546 lines, 68 functions.
- Risk level: high.
- Mixed concerns: key ordering, array/library override keys, default values,
  video/audio/subtitle/rename choice registries, coercion, range validation,
  path-shape validation, library profile override validation, and full schema
  validation.

## Ideal Split

- `ops/pipeline/engine/config/schema_keys.ps1`: ordered, required, array, and override-key
  registries.
- `ops/pipeline/engine/config/default_values.ps1`: default config map and default helper
  functions.
- `ops/pipeline/engine/config/choice_registry.ps1`: enum-like names and resolver helpers.
- `ops/pipeline/engine/config/library_overrides.ps1`: library override map and validation.
- `ops/pipeline/engine/config/schema_validation.ps1`: path, range, cross-field, and full
  schema validators.
- Keep `config_schema.ps1` as the public compatibility loader initially.

## Extraction Order

1. Extract static key and choice getters.
2. Extract default-value builders.
3. Extract low-level coercion and range validators.
4. Extract library-profile override validators.
5. Leave `Test-MediaPipelineConfigSchema` as the last wrapper to shrink.

## Validation

- `ops/pipeline/tests/Unit/Invoke-ConfigKeyRegistryChecks.ps1`
- Runtime config resolution checks.
- Python config contract tests and generated schema `--check`.
- Settings Preview/Save route tests.

## Must Not Change

Config key names, order, defaults, compatibility aliases, validation severity,
and profile/config-driven audio, subtitle, route, and publish policy.

