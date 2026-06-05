# ops/pipeline/engine/paths/output_path_planning.ps1

## Current Strain

- Approximate size: 1,151 lines, 36 functions.
- Risk level: high.
- Mixed concerns: library profile lookup, library override layers, runtime
  effective settings evidence, output container evidence, size/publish/
  verification evidence, selected output roots, path boundary checks, and
  capability preflight.

## Ideal Split

- `ops/pipeline/engine/paths/library_profiles.ps1`: profile map, profile lookup, selected
  profile ID, and source-root matching.
- `ops/pipeline/engine/paths/effective_settings.ps1`: runtime/global/library layer
  construction and source attribution.
- `ops/pipeline/engine/paths/output_evidence.ps1`: output container, size guard, publish,
  and verification evidence builders.
- `ops/pipeline/engine/paths/path_capability.ps1`: root-boundary and capability checks.
- Keep `Get-OutputPaths` in the parent until consumers are stable.

## Extraction Order

1. Extract pure evidence builders.
2. Extract runtime layer constructors.
3. Extract library profile lookup and override maps.
4. Extract path capability helpers after boundary tests are pinned.

## Validation

- Library profile routing checks.
- Path boundary guard checks.
- Release package policy checks.
- Real-media publish/final-placement validation after any behavior movement.

## Must Not Change

Library profile selection, output root selection, same-disk warning posture,
pending-publish parking conditions, and final output path construction.

