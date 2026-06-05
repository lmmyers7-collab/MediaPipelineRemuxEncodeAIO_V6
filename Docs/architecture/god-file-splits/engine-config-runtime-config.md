# ops/pipeline/engine/config/runtime_config.ps1

## Current Strain

- Approximate size: 590 lines.
- Risk level: high.
- Mixed concerns: runtime config resolution, defaults, config file discovery,
  profile merge behavior, validation handoff, and compatibility fallbacks.

## Ideal Split

- `ops/pipeline/engine/config/runtime_paths.ps1`: config path discovery and app/root
  resolution.
- `ops/pipeline/engine/config/runtime_merge.ps1`: profile/default/live config merge rules.
- `ops/pipeline/engine/config/runtime_validation.ps1`: validation handoff and error shaping.
- Keep `runtime_config.ps1` as the public resolver.

## Extraction Order

1. Extract path discovery helpers.
2. Extract merge helpers.
3. Extract validation result shaping.
4. Keep public resolver signature unchanged.

## Validation

- Runtime config resolution checks.
- Config key registry checks.
- Release environment verification.

## Must Not Change

Live config precedence, profile defaults, compatibility fallback behavior, and
settings persistence boundaries.

