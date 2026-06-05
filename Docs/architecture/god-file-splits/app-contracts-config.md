# app/contracts/config.py

## Current Strain

- Approximate size: 1,380 lines, central Pydantic `Config` model plus helper
  validators.
- Risk level: medium-high.
- Mixed concerns: schema extras, legacy coercion, default factories,
  cross-field validators, choice normalization, library profile coercion, and
  the canonical contract fields.

## Ideal Split

- `app/contracts/config_defaults.py`: tuple/list/default factories and default
  config construction helpers.
- `app/contracts/config_schema_extras.py`: JSON Schema extra builders.
- `app/contracts/config_coercion.py`: bool/list/mapping coercion helpers.
- `app/contracts/config_validators.py`: reusable cross-field validation helpers.
- Keep the `Config` class and field declarations in `app/contracts/config.py`.

## Extraction Order

1. Extract schema-extra helper functions.
2. Extract default factories.
3. Extract reusable coercion helpers.
4. Extract cross-field validation helpers only if error text is fully pinned.

## Validation

- `tests/contract/test_config_contract.py`
- `ops/scripts/dev/generate_config_schema.py --check`
- Desktop settings validation tests.
- PowerShell config-key registry checks for cross-language drift.

## Must Not Change

The `Config` public contract, generated schema, defaults, validation errors,
field aliases, and compatibility with PSD1 import/export.

