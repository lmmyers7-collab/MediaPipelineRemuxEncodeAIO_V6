# Phase 4: Queue/Rename Contract Decomposition

Status: execute after Phase 3 route-domain extraction

## Purpose

Decompose the remaining long queue and rename contract tests. The specific
problem is `test_local_api_queue_and_rename_preview_contracts`, which is a
multi-domain contract test that should not survive the split as a large method
under a new filename.

This phase happens after the route-domain move so the queue and rename owners
are already separate.

## Target Outcomes

The queue module should own queue preview, queue open, priority, strategy,
file override, source-scope, and command-journal route behavior.

The rename module should own rename preview, browse, clean-filename,
apply-readiness, apply confirmation, undo confirmation, media-root injection,
library-profile-root authority, and active-work blocking.

## Decomposition Strategy

1. Open the current `test_local_api_queue_and_rename_preview_contracts` method.
2. Split setup from assertions.
3. Identify route calls and group them by route prefix.
4. Add or update rows in `ASSERTION_MIGRATION_LEDGER.md` for each route or
   assertion block.
5. Move queue-prefixed assertions to `test_application_facade_local_api_queue.py`.
6. Move rename-prefixed assertions to `test_application_facade_local_api_rename.py`.
7. Extract shared setup only if it is genuinely shared and clear.
8. Prefer several smaller tests over one parameterized route matrix when route
   behavior differs materially.

## Suggested Queue Tests

- `test_queue_route_contracts_are_exposed_with_expected_effect_metadata`
- `test_queue_read_routes_preserve_source_scope`
- `test_queue_open_routes_use_backend_allowlisted_targets`
- `test_queue_priority_routes_are_journaled_when_mutating`
- `test_queue_strategy_route_records_command_history`
- `test_queue_file_override_preview_is_read_only`

## Suggested Rename Tests

- `test_rename_preview_route_uses_backend_policy_and_scope`
- `test_rename_browse_route_reports_native_picker_payload`
- `test_rename_clean_filename_preview_is_read_only`
- `test_rename_apply_requires_boolean_confirm_apply`
- `test_rename_undo_requires_boolean_confirm_apply`
- `test_rename_routes_inject_backend_media_roots`
- `test_rename_routes_reject_active_work_without_mutation`

## Assertion Style

Use explicit assertions for safety-critical route fields:

- `schema_version`
- `ok`
- `command`
- `route`
- `data`
- `effects`
- `requires_confirmation`
- `confirm_apply`
- `confirm_save`
- `journaled`
- source/root scope fields
- mutation/side-effect counters

Do not hide strict confirmation assertions in a helper named only
`assert_success`. Confirmation checks should be visible at the call site.

## Phase Validation

```powershell
$py = ".\apps\desktop\runtime\Python\python.exe"
& $py -m unittest tests.python.desktop.test_application_facade_local_api_queue -q
& $py -m unittest tests.python.desktop.test_application_facade_local_api_rename -q
& $py -m unittest discover -s tests\python\desktop -p "test_application_facade_local_api*.py" -q
```

If queue or rename route behavior changes during this phase, stop and reclassify
the change as a route behavior change under `VALIDATION_LADDER_RUNBOOK.md`.

## Exit Criteria

- No queue/rename test method is a broad cross-domain contract blob.
- Queue and rename failures report the owning route domain directly.
- Strict confirmation behavior remains pinned.
- Command-journal behavior remains pinned.
- Source/root scope behavior remains pinned.
- The Phase 4 section of `ASSERTION_MIGRATION_LEDGER.md` has no pending rows
  for the decomposed queue/rename contract blocks.
