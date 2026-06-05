# ops/pipeline/engine/queue/local_worker_slots.ps1

## Current Strain

- Approximate size: 782 lines, 29 functions.
- Risk level: high.
- Mixed concerns: mutex naming, atomic JSON writes, claim-store lifecycle,
  stale claim repair, child process launch, worker progress snapshots, active
  job writes, stop handling, and parent counter updates.

## Ideal Split

- `ops/pipeline/engine/queue/worker_mutex.ps1`: stable hash, mutex names, and protected
  invocation.
- `ops/pipeline/engine/queue/worker_claim_store.ps1`: layout, claim-store read/write, claim,
  update, release, and repair.
- `ops/pipeline/engine/queue/worker_process.ps1`: child argument construction, process
  launch, stop, and process liveness checks.
- `ops/pipeline/engine/queue/worker_progress.ps1`: progress snapshots, active-job writes,
  and parent counter updates.

## Extraction Order

1. Extract JSON/atomic write and mutex helpers.
2. Extract claim-store layout and read/write.
3. Extract child-process argument/launch helpers.
4. Extract stop/progress/counter update behavior last.

## Validation

- Local worker slot unit coverage.
- Native process cleanup checks.
- Adversarial force-kill during encode check if process behavior changes.

## Must Not Change

Worker claim exclusivity, stale claim repair, active-job evidence, process-tree
cleanup, and parent counter updates.

