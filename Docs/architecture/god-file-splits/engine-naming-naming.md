# ops/pipeline/engine/naming/naming.ps1

## Current Strain

- Approximate size: 1,362 lines, 44 functions.
- Risk level: medium-high.
- Mixed concerns: movie title cleanup, rename filter policy, TV parsing,
  episode title extraction, Plex destination plan construction, rename override
  application, and TV rename suggestions.

## Ideal Split

- `ops/pipeline/engine/naming/movie_cleanup.ps1`: movie normalization, title case, and
  rename-filter term removal.
- `ops/pipeline/engine/naming/tv_parsing.ps1`: season/episode/folder parsing and TV
  candidate extraction.
- `ops/pipeline/engine/naming/destination_plan.ps1`: Plex movie/TV destination plans and
  relative path helpers.
- `ops/pipeline/engine/naming/rename_overrides.ps1`: rename override final names and
  sidecar paths.
- Keep `naming.ps1` as public compatibility loader until callers are moved.

## Extraction Order

1. Extract movie filter catalog/default helpers.
2. Extract TV parsing helpers with existing naming unit checks.
3. Extract destination plan builders.
4. Extract rename override application last.

## Validation

- Naming support checks.
- Rename planner and rename safety tests.
- Real-media rename-output safety validation if destination plans change.

## Must Not Change

Plex destination naming, configured rename cleaning policy, sidecar name
sanitization, TV season/episode inference, and rename override evidence.

