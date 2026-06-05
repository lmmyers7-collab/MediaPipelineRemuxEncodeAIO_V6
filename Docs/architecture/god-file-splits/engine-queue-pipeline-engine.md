# ops/pipeline/engine/queue/pipeline_engine.ps1

## Current Strain

- Approximate size: 848 lines, 12 functions.
- Risk level: high.
- Mixed concerns: engine plans, queue phase invocation, process entry
  execution, queue snapshots, pipeline rounds/runs, preflight blocks, snapshot
  row shaping, and snapshot writes.

## Ideal Split

- `ops/pipeline/engine/queue/engine_plan.ps1`: engine plan construction and queue-entry
  progress extraction.
- `ops/pipeline/engine/queue/phase_executor.ps1`: phase plan invocation and queue-entry
  processing.
- `ops/pipeline/engine/queue/snapshot_rows.ps1`: excluded row and snapshot row builders.
- `ops/pipeline/engine/queue/snapshot_store.ps1`: snapshot write/read boundary.
- Keep `pipeline_engine.ps1` as the high-level run loop.

## Extraction Order

1. Extract snapshot row builders.
2. Extract preflight block builder.
3. Extract snapshot write helper.
4. Extract phase executor after process lifecycle tests cover current behavior.

## Validation

- Pipeline queue engine checks.
- Process lifecycle and duplicate-start tests.
- Queue/Launch WebView readiness smoke when snapshot DTOs change.

## Must Not Change

Duplicate-command protections, queue snapshot evidence, runnable entry counts,
and pipeline round/continuous-mode behavior.

