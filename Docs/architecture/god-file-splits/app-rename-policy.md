# app/rename/policy.py

## Current Strain

- Approximate size: 748 lines, 48 definitions.
- Risk level: medium-high.
- Mixed concerns: cleaning policy parsing, rename request patching, preview
  counts, apply guard result DTOs, configured-root authority, undo manifest
  root selection, filename preview, filter catalog, and plan kwargs.

## Ideal Split

- `app/rename/cleaning_policy.py`: cleaning policy from config/resolved values,
  staged policy detection, and remove-term parsing.
- `app/rename/preview_policy.py`: preview counts, warnings, and selected-row
  helpers.
- `app/rename/apply_results.py`: confirmation, busy, blocker, exception, and
  success result DTOs.
- `app/rename/path_authority.py`: configured roots, authority fields, outside
  root detection, and undo manifest roots.
- `app/rename/filename_preview.py`: clean filename preview and filter catalog.

## Extraction Order

1. Extract cleaning policy helpers.
2. Extract preview count helpers.
3. Extract apply result DTO constructors.
4. Extract path authority helpers after root-boundary tests are pinned.
5. Extract plan kwargs last.

## Validation

- Rename planner tests.
- Local API rename strict-confirmation tests.
- Rename browser smoke.
- Rename safety inventory checks.

## Must Not Change

Literal `confirm_apply: true` guard, configured-root boundary, undo manifest
state-root placement, no unexpected filesystem mutation, and rename cleaning
policy semantics.

