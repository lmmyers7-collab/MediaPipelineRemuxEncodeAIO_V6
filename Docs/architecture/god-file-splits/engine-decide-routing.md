# ops/pipeline/engine/decide/routing.ps1

## Current Strain

- Approximate size: 1,360 lines, 28 functions.
- Risk level: high.
- Mixed concerns: route hints, codec normalization, Plex compatibility,
  route-profile selection, size/bitrate policy, remux-safe codec policy,
  decision trace construction, and route-plan metadata.

## Ideal Split

- `ops/pipeline/engine/decide/codec_policy.ps1`: codec normalization, Plex copy candidacy,
  remux-safe codec predicates.
- `ops/pipeline/engine/decide/size_policy.ps1`: size guard modes, threshold modes,
  resolution/bitrate bucket selection, encode-output size policy.
- `ops/pipeline/engine/decide/profile_selection.ps1`: routing profile names, profile values,
  active hints, and route-plan metadata lookup.
- `ops/pipeline/engine/decide/route_plan.ps1`: action-set, trace-entry, and route-plan
  constructors.
- Keep `ops/pipeline/engine/decide/routing.ps1` as the orchestrator/export surface until all
  callers move.

## Extraction Order

1. Move pure constructors and codec normalization without changing call sites.
2. Move profile and hint readers behind same-named wrappers.
3. Move size/bitrate policy helpers and characterize current outputs.
4. Move codec/remux predicates after route-policy tests pin exact decisions.
5. Shrink `routing.ps1` to orchestration plus compatibility exports.

## Validation

- `ops/pipeline/tests/Unit/Invoke-MediaRouteSelectionChecks.ps1`
- Decision contract tests under `tests/decide/`
- Reliability regression wrapper.
- Real-media validation for one remux sample and one encode/size-policy sample.

## Must Not Change

Route decisions, threshold semantics, bitrate fallback behavior, Plex
compatibility scoring, output container choice, and any evidence text consumed
by Queue/Launch/Completed surfaces.

