# app/kernel/config_keys.py

## Current Strain

- Approximate size: 470 lines.
- Risk level: medium.
- Mixed concerns: registered config keys, grouped key sets, compatibility
  aliases, generated/schema ordering, and cross-language drift guard data.

## Ideal Split

- `app/kernel/config_key_groups.py`: grouped key sets by domain.
- `app/kernel/config_key_aliases.py`: compatibility aliases and legacy names.
- `app/kernel/config_key_order.py`: canonical ordered key list.
- Keep `config_keys.py` as the compatibility re-export and single import target.

## Extraction Order

1. Extract alias sets.
2. Extract domain key groups.
3. Extract ordered list after Python and PowerShell order checks are green.

## Validation

- Python config key tests.
- PowerShell config key registry checks.
- Generated config schema check.

## Must Not Change

Canonical names, aliases, ordering, and Python/PowerShell key parity.

