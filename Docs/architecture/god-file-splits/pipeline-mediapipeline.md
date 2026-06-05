# ops/pipeline/entrypoints/MediaPipeline.ps1

## Current Strain

- Approximate size: 1,198 lines, 3 named functions.
- Risk level: high.
- Main strain: one large processing entrypoint carries file processing,
  worker-result handling, process-stage sequencing, and publish/drain-adjacent
  behavior.

## Ideal Split

- `ops/pipeline/engine/process/file_processor.ps1`: per-file processing orchestration.
- `ops/pipeline/engine/process/worker_result.ps1`: child result serialization and parent
  result parsing.
- `ops/pipeline/engine/process/stage_context.ps1`: read-only context assembly for probe,
  decide, process, and publish phases.
- Publish and pending-publish calls should remain in `ops/pipeline/engine/publish/`, not in
  new `Pipeline/Modules` files.
- Keep `ops/pipeline/entrypoints/MediaPipeline.ps1` as the legacy entry script that dot-sources
  the new engine modules.

## Extraction Order

1. Extract worker result field and child-result writer helpers.
2. Extract read-only per-file context builders.
3. Extract phase dispatch shells without moving mutation logic.
4. Move processing orchestration only after tests pin existing job lifecycle.

## Validation

- Full release self-test.
- Process and queue PowerShell unit checks.
- Pending-publish safety checks.
- Real-media remux, encode, subtitle, audio, and deferred publish/drain samples.

## Must Not Change

Source files must remain copied to scratch, source mutation must remain
forbidden by default, pending publish must park unsafe final output, and worker
results must remain compatible with existing parent/child process handling.

