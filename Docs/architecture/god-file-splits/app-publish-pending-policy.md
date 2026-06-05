# app/publish/pending_policy.py

## Current Strain

- Approximate size: 1,197 lines, about 72 definitions.
- Risk level: high.
- Mixed concerns: preview DTOs, row diagnostics, row trust fields, drain
  confidence, recovery plan dry-run payloads, open-target policy, command
  result construction, and error DTOs.

## Ideal Split

- `app/publish/pending_rows.py`: row normalization, diagnostics, trust fields,
  counts, and preview fields.
- `app/publish/pending_drain_confidence.py`: evidence class, confidence rows,
  drain summary status, and confidence payload.
- `app/publish/pending_recovery.py`: recovery plan rows, summaries, and command
  result DTOs.
- `app/publish/pending_open_policy.py`: open-target normalization, path
  selection, and open result DTOs.
- `app/publish/pending_results.py`: shared invalid/unavailable/exception result
  helpers.
- Keep `pending_policy.py` as an import facade during migration.

## Extraction Order

1. Extract open-target helpers.
2. Extract row diagnostics and count helpers.
3. Extract drain-confidence helpers.
4. Extract recovery plan command result helpers.
5. Convert parent module to compatibility exports.

## Validation

- Pending-publish fixture tests.
- Local API pending publish route/contract tests.
- Browser no-mutation smokes for Pending Publish.

## Must Not Change

Pending Publish remains read-only in preview surfaces, drain commands remain
backend-owned, and recovery dry-runs must not mutate manifests or media.

