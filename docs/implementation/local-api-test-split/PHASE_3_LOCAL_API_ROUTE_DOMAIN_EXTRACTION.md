# Phase 3: Local API Route Domain Extraction

Status: execute after Web static extraction passes

## Purpose

Move the remaining Local API route tests out of the old god-file and into
domain-owned modules. This phase should make route failures point directly to
the owning backend domain.

## Target Modules And Method Mapping

### HTTP / Transport / Security

Target file:

- `tests/python/desktop/test_application_facade_local_api_http.py`

Move:

- `test_local_api_server_suppresses_client_disconnect_tracebacks`
- `test_browser_index_uses_http_only_cookie_without_rendering_token`
- `test_browser_index_render_failure_does_not_set_auth_cookie`
- `test_local_api_rejects_query_string_tokens`
- `test_local_api_rejects_invalid_host_and_cross_origin_posts`
- `test_local_api_options_reflects_allowed_origin_and_security_headers`
- `test_local_api_no_token_requires_loopback_and_explicit_env`
- `test_local_api_request_threads_are_not_daemonized`
- `test_local_api_health_failure_returns_json_error_envelope`
- `test_local_api_send_json_rejects_nonfinite_response_payload`
- `test_local_api_rejects_wrong_json_content_type_without_command_journal_entry`
- `test_local_api_health_is_public_and_snapshot_requires_token`

### Lifecycle / Shutdown

Target file:

- `tests/python/desktop/test_application_facade_local_api_lifecycle.py`

Move:

- `test_local_api_close_readiness_is_unsafe_when_workspace_is_unresolved`
- `test_local_api_shutdown_blocks_when_workspace_is_unresolved`
- `test_local_api_shutdown_blocks_when_active_jobs_block_close`
- `test_local_api_shutdown_blocks_when_schedule_stop_watcher_is_armed`
- `test_local_api_shutdown_force_cleanup_invokes_backend_owned_process_cleanup`
- `test_local_api_shutdown_force_cleanup_ignores_non_boolean_truthy_values`
- `test_local_api_shutdown_logs_close_readiness_exceptions`
- `test_local_api_shutdown_logs_callback_failures_after_response`
- `test_local_api_shutdown_logs_timer_start_failures`

### Process Commands

Target file:

- `tests/python/desktop/test_application_facade_local_api_process_commands.py`

Move:

- `test_local_api_process_commands_require_token_before_side_effects`
- `test_local_api_rejects_invalid_command_payload_before_side_effects`
- `test_local_api_route_exception_is_recorded_in_command_journal`
- `test_local_api_scheduled_continuous_start_arms_backend_stop_watcher`

### Diagnostics

Target file:

- `tests/python/desktop/test_application_facade_local_api_diagnostics.py`

Move:

- `test_local_api_diagnostics_tail_reads_allowlisted_file`
- `test_local_api_diagnostics_state_summary_reads_backend_allowlist`

### Network

Target file:

- `tests/python/desktop/test_application_facade_local_api_network.py`

Move:

- `test_local_api_network_lifecycle_dry_run_does_not_write_command_journal`

### Repair / Reconcile

Target file:

- `tests/python/desktop/test_application_facade_local_api_repair.py`

Move:

- `test_local_api_repair_reconcile_dry_run_routes_return_schema_and_suppress_journal`

### Settings

Either move into an existing settings API test if one exists after Phase 3, or
create:

- `tests/python/desktop/test_application_facade_local_api_settings.py`

Move:

- `test_local_api_settings_reload_failure_is_logged`

### Queue

Target file:

- `tests/python/desktop/test_application_facade_local_api_queue.py`

Move:

- `test_local_api_queue_state_routes_are_contracted_journaled_and_source_scoped`
- `test_local_api_queue_priority_clear_all_clears_entire_manifest`
- `test_local_api_queue_priority_read_fails_closed_when_manifest_is_corrupt`
- `test_local_api_queue_priority_bulk_accepts_manual_order_positions`
- `test_local_api_file_override_clear_fields_preserves_save_and_full_clear`
- `test_local_api_file_override_validates_current_payload_fields`
- `test_local_api_file_override_effective_read_reports_match_sources_and_library_defaults`
- `test_local_api_file_override_revalidates_merged_route_video_edits`
- `test_local_api_file_override_route_preview_is_read_only_and_validates_proposals`
- `test_local_api_file_override_route_video_persistence_validation_and_effective_metadata`

### Rename

Target file:

- `tests/python/desktop/test_application_facade_local_api_rename.py`

Move:

- `test_rename_browse_resolves_dropped_folder_paths_without_dialog`
- `test_rename_clean_filename_preview_get_route_uses_backend_cleaner_without_command_journal`
- `test_rename_clean_filename_preview_rejects_invalid_query_json_without_command_journal`
- `test_rename_filter_settings_persist_and_feed_saved_preview_policy`
- `test_local_api_rename_apply_rejects_absent_or_false_confirmation_without_mutation`
- `test_local_api_rename_apply_blocks_active_work_without_mutation`
- `test_local_api_injects_rename_media_roots_and_requires_outside_root_confirmation`
- `test_local_api_injects_library_profile_roots_for_rename_authority`
- `test_local_api_rename_undo_uses_backend_root_and_strict_confirmation`

## Move Order

Use this order so broad route infrastructure is stable before high-risk command
routes move:

1. HTTP / transport / auth.
2. Diagnostics.
3. Network.
4. Repair/reconcile.
5. Settings.
6. Lifecycle / shutdown.
7. Process commands.
8. Queue.
9. Rename.

Queue and rename move last because they contain the longest and most
mutation-sensitive Local API route contracts.

## Step Plan For Each Domain

For each target module:

1. Create the module with imports from `application_facade_test_support.py`.
2. Create a domain-specific `unittest.TestCase` class with a descriptive name,
   such as `LocalApiHttpTests` or `LocalApiRenameRouteTests`.
3. Add or update the matching row in `ASSERTION_MIGRATION_LEDGER.md`.
4. Move one test method at a time.
5. Run the new module and the old module after each group.
6. Remove the method from the old module only after the moved copy passes.
7. Mark the ledger row resolved with the target class, target method, and
   validation command.
8. Confirm direct invocation works:

   ```powershell
   .\apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_application_facade_local_api_http -q
   ```

## Guardrails

- Keep strict JSON confirmation checks exactly as strict as before.
- Keep command-journal assertions in the same domain as the route under test.
- Do not collapse many route tests into one parameterized test if doing so makes
  failure triage harder.
- Prefer small domain setup helpers over broad global fixtures.
- Do not change route implementation code in this phase.
- If a moved test exposes a route bug, stop and create a separate fix plan.

## Phase Validation

After each target module:

```powershell
$py = ".\apps\desktop\runtime\Python\python.exe"
& $py -m unittest tests.python.desktop.<target_module> -q
& $py -m unittest tests.python.desktop.test_application_facade_local_api -q
```

Replace `<target_module>` with the module under migration, such as
`test_application_facade_local_api_http`.

After the full phase:

```powershell
$py = ".\apps\desktop\runtime\Python\python.exe"
& $py -m unittest discover -s tests\python\desktop -p "test_application_facade_local_api*.py" -q
& $py -m unittest discover -s tests\python\desktop -p "test_application_facade*.py" -q
```

## Exit Criteria

- The old Local API file no longer owns HTTP, lifecycle, process command,
  diagnostics, network, repair, settings, queue, or rename route domains.
- Each new domain module can be run independently.
- Test discovery does not duplicate methods.
- Route mutation guardrails remain visible in test names and assertions.
- The Phase 3 section of `ASSERTION_MIGRATION_LEDGER.md` has no pending rows
  for moved Local API methods.
