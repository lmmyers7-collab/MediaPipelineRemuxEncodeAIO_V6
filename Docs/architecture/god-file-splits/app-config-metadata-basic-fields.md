# app/config/metadata_parts/basic_fields.py

## Current Strain

- Approximate size: 476 lines.
- Risk level: low-medium.
- Mixed concerns: static basic-page settings metadata, display grouping,
  defaults, help text, and override/display classification.

## Ideal Split

- `app/config/metadata_parts/basic_paths.py`: source/output/tool path fields.
- `app/config/metadata_parts/basic_processing.py`: route and processing fields.
- `app/config/metadata_parts/basic_media_policy.py`: audio, subtitle, and
  publish-relevant basic fields.
- Keep `basic_fields.py` as an ordered aggregator.

## Extraction Order

1. Split path fields first.
2. Split processing fields.
3. Split media policy fields.
4. Keep final tuple ordering covered by metadata contract tests.

## Validation

- Metadata contract tests.
- Settings builder coverage tests.
- Config-key registry checks when persisted keys are touched.

## Must Not Change

Field order, persisted keys, backend-owned metadata authority, labels, defaults,
help text, and Library Profiles override eligibility.

