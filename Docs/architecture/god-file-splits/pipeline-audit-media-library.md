# ops/pipeline/entrypoints/Audit-MediaLibrary.ps1

## Current Strain

- Approximate size: 1,471 lines, 37 functions.
- Risk level: medium-high.
- Mixed concerns: native command execution, ffprobe/tag helpers, subtitle
  compatibility checks, sidecar SRT validation, audio default/fidelity policy,
  result shaping, library lookup naming, and per-file audit issue generation.

## Ideal Split

- `ops/pipeline/engine/audit/native_commands.ps1`: executable resolution, process tree
  cleanup, and native command invocation.
- `ops/pipeline/engine/audit/probe_fields.ps1`: tag, stream tag, disposition, and default
  stream helpers.
- `ops/pipeline/engine/audit/subtitle_audit.ps1`: TX3G/BDPGS/VobSub/SRT compatibility and
  sidecar validation.
- `ops/pipeline/engine/audit/audio_audit.ps1`: preferred audio language, commentary
  detection, fidelity ranking, and default candidate selection.
- `ops/pipeline/engine/audit/result_builder.ps1`: result DTO, issue appending, and final
  per-file audit assembly.
- `ops/pipeline/engine/audit/library_lookup.ps1`: movie/TV lookup title helpers.

## Extraction Order

1. Extract native command helpers.
2. Extract probe field helpers.
3. Extract subtitle audit helpers.
4. Extract audio audit helpers.
5. Extract result builders and leave the per-file audit function last.

## Validation

- Audit score/policy checks.
- Tool integration checks if native command behavior moves.
- Subtitle/audio real-media validation if audit expectations affect operator
  acceptance decisions.

## Must Not Change

Audit remains diagnostic, source media is not mutated, subtitle/audio evidence
labels stay compatible with WebView/Reports consumers, and native process
cleanup remains bounded.

