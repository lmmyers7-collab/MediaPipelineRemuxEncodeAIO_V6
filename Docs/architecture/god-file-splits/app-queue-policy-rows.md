# app/queue/policy_parts/rows.py

## Current Strain

- Approximate size: 829 lines, 35 definitions.
- Risk level: medium-high.
- Mixed concerns: queue row keys, record-to-row conversion, file override
  artifact annotation, stream metadata summaries, open targets, operator status
  and guidance, trust fields, route evidence, runtime outcomes, preview rows,
  and warnings.

## Ideal Split

- `app/queue/policy_parts/row_identity.py`: row keys, normalized path keys, and
  open targets.
- `app/queue/policy_parts/track_metadata.py`: stream/track metadata extraction.
- `app/queue/policy_parts/file_override_rows.py`: file override artifact
  annotation.
- `app/queue/policy_parts/operator_guidance.py`: status, guidance, and trust
  fields.
- `app/queue/policy_parts/route_evidence.py`: route summaries and evidence.
- `app/queue/policy_parts/runtime_outcomes.py`: runtime outcome application.

## Extraction Order

1. Extract path/key and scalar helpers.
2. Extract track metadata helpers.
3. Extract route evidence helpers.
4. Extract operator guidance and trust fields.
5. Extract preview-row assembly last.

## Validation

- Queue facade/policy tests.
- Local API queue preview tests.
- Launch/Queue WebView readiness smoke if row fields change.

## Must Not Change

Queue row keys, route evidence, selected-row identity, file override markers,
operator guidance, and runtime outcome matching.

