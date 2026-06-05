# app/contracts/stages.py

## Current Strain

- Approximate size: 707 lines, 48 definitions.
- Risk level: medium.
- Mixed concerns: stage request/result contracts, stage names, mutation intent
  fields, validation helpers, schema metadata, and enabled dispatcher contract
  assumptions.

## Ideal Split

- `app/contracts/stage_base.py`: shared envelope, status, and error models.
- `app/contracts/stage_probe.py`: probe-stage request/result models.
- `app/contracts/stage_decide.py`: decide-stage request/result models.
- `app/contracts/stage_mutation.py`: modeled but disabled mutation-capable
  stages and intent fields.
- Keep `stages.py` as public contract aggregator for schema generation.

## Extraction Order

1. Extract shared base models.
2. Extract read-only probe/decide models.
3. Extract disabled mutation-stage models.
4. Keep schema generation output byte-for-byte stable or explain drift.

## Validation

- Stage contract tests.
- `ops/scripts/dev/generate_stage_schema.py --check`
- Pipeline map generation check.

## Must Not Change

Schema version, read-only enabled stage behavior, disabled mutation stage
posture, and JSON schema compatibility.

