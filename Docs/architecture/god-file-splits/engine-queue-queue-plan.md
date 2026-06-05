# ops/pipeline/engine/queue/queue_plan.ps1

## Current Strain

- Approximate size: 1,115 lines, 21 functions.
- Risk level: high.
- Mixed concerns: priority marker parsing, priority manifest reads, queue item
  construction, relative path and TV season/episode parsing, runtime metadata,
  queue strategies, sort implementations, runnable entries, and phase plans.

## Ideal Split

- `ops/pipeline/engine/queue/priority_manifest.ps1`: marker parsing and priority manifest
  reads.
- `ops/pipeline/engine/queue/queue_entries.ps1`: source priority info, relative paths,
  item construction, and runtime metadata.
- `ops/pipeline/engine/queue/strategy_sorting.ps1`: queue strategy selection and sort
  implementations.
- `ops/pipeline/engine/queue/phase_plan.ps1`: runnable entries and phase-plan construction.
- Keep `queue_plan.ps1` as a compatibility import surface at first.

## Extraction Order

1. Extract priority marker and manifest helpers.
2. Extract sort strategies behind unchanged `Invoke-QueueStrategySort`.
3. Extract queue item/record construction.
4. Extract phase planning last.

## Validation

- Pipeline queue engine checks.
- Queue priority Local API tests.
- Queue browser/static tests when WebView evidence fields are affected.

## Must Not Change

Queue launch scope, ManualOrder semantics, priority phase behavior, source
selection, sidecar exclusion, and runtime outcome metadata.

