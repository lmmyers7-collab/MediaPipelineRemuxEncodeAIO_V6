# app/config/metadata_parts/field_definitions.py

## Current Strain

- Approximate size: 924 lines.
- Risk level: medium.
- Mixed concerns: combined field ordering, field enrichment, scope taxonomy,
  value types, advanced visibility, display sections, rule taxonomy, and
  strictness classification.

## Ideal Split

- `app/config/metadata_parts/field_registry.py`: combined ordered field tuple.
- `app/config/metadata_parts/field_scope.py`: scope, override group, and
  designation helpers.
- `app/config/metadata_parts/field_display.py`: display section, advanced
  visibility, taxonomy, and strictness helpers.
- Keep `field_definitions.py` as the public aggregator.

## Extraction Order

1. Extract display/taxonomy enrichment helpers.
2. Extract scope/override helpers.
3. Extract registry aggregation only after import consumers are checked.

## Validation

- Metadata contract tests.
- Settings Library Profiles tests.
- Active docs/reference checks if generated inventories cite metadata fields.

## Must Not Change

Public field order, metadata shape, override eligibility, display taxonomy, and
generated Settings behavior.

