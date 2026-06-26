# Pre-Work And Baseline

Status: required before any test movement

## Purpose

This phase front-loads the work that prevents a mechanical split from losing
assertions, duplicating tests, or hiding baseline failures. Do not move tests
until this phase has passed or until baseline failures are explicitly recorded
as pre-existing.

## Required Reads

Read these before editing:

- `AGENTS.md`
- `docs/DOCS_INDEX.md`
- `docs/architecture/ARCHITECTURE.md`
- `docs/architecture/MODULE_MAP.md`
- `docs/testing/VALIDATION_LADDER_RUNBOOK.md`
- `docs/testing/TEST_COVERAGE_MATRIX.md`
- `docs/generated/summaries/tests/python/desktop/test_application_facade_local_api.py.md`
- `docs/generated/summaries/tests/python/desktop/test_application_facade_web_static.py.md`
- `tests/python/desktop/test_application_facade_local_api.py`
- `tests/python/desktop/test_application_facade_web_static.py`
- `tests/python/desktop/test_application_facade.py`

Use the generated summaries first, but open full source for the three test files
because exact helper behavior, imports, and test names matter.

## Worktree And Change Packet Gate

Before changing files:

1. Run `git status --short`.
2. Identify unrelated dirty files.
3. Create or continue a change packet.
4. Do not absorb unrelated dirty files into the split packet.
5. Record every touched file as work progresses.

This repository often has large dirty worktrees during active remediation work.
That is not a reason to include unrelated files in this split.

## Baseline Inventory

Create a method inventory from the current file before moving anything:

```powershell
@'
import ast
from pathlib import Path

path = Path("tests/python/desktop/test_application_facade_local_api.py")
source = path.read_text(encoding="utf-8")
module = ast.parse(source)
for cls in [node for node in module.body if isinstance(node, ast.ClassDef)]:
    print(f"class {cls.name} line {cls.lineno}-{cls.end_lineno}")
    for item in cls.body:
        if isinstance(item, ast.FunctionDef) and item.name.startswith("test_"):
            print(f"{item.lineno:5}-{item.end_lineno:5} {item.end_lineno - item.lineno + 1:4} {item.name}")
'@ | .\apps\desktop\runtime\Python\python.exe -
```

Record the output in the change packet validation notes or in the phase handoff.
The inventory should prove that the current `LocalApiServerTests` class contains
51 test methods and that `test_local_api_serves_read_only_web_prototype` is the
dominant method.

## Baseline Test Run

Use the bundled Python runtime from the repository root:

```powershell
$py = ".\apps\desktop\runtime\Python\python.exe"
& $py -m unittest tests.python.desktop.test_application_facade_local_api -q
& $py -m unittest tests.python.desktop.test_application_facade_web_static -q
& $py -m unittest discover -s tests\python\desktop -p "test_application_facade*.py" -q
```

Expected result: all pass before refactoring. If a command fails before any
split work, stop and classify the failure:

| Failure type | Action |
|---|---|
| Product/test regression unrelated to split | Record as baseline failure and ask whether to fix first. |
| Environment/runtime missing | Record exact missing prerequisite and continue only if the phase can still be validated later. |
| Flaky timeout | Re-run once, record both outputs, and avoid moving tests until the baseline is understood. |

Do not use a failing baseline as evidence that the split is safe.

## Current Method-To-Domain Inventory

Use this as the starting map. Re-check against source before executing because
the file may have changed.

| Current method | Target domain |
|---|---|
| `test_local_api_server_suppresses_client_disconnect_tracebacks` | HTTP transport |
| `test_browser_index_uses_http_only_cookie_without_rendering_token` | HTTP/static serving |
| `test_browser_index_render_failure_does_not_set_auth_cookie` | HTTP/static serving |
| `test_local_api_rejects_query_string_tokens` | HTTP auth/security |
| `test_local_api_rejects_invalid_host_and_cross_origin_posts` | HTTP auth/security |
| `test_local_api_options_reflects_allowed_origin_and_security_headers` | HTTP/CORS |
| `test_local_api_no_token_requires_loopback_and_explicit_env` | HTTP auth/security |
| `test_local_api_request_threads_are_not_daemonized` | HTTP server lifecycle |
| `test_local_api_health_failure_returns_json_error_envelope` | HTTP JSON envelope |
| `test_local_api_send_json_rejects_nonfinite_response_payload` | HTTP JSON envelope |
| `test_local_api_rejects_wrong_json_content_type_without_command_journal_entry` | HTTP strict JSON / journal guard |
| `test_local_api_health_is_public_and_snapshot_requires_token` | HTTP auth plus snapshot route |
| `test_local_api_close_readiness_is_unsafe_when_workspace_is_unresolved` | lifecycle |
| `test_local_api_shutdown_blocks_when_workspace_is_unresolved` | lifecycle |
| `test_local_api_shutdown_blocks_when_active_jobs_block_close` | lifecycle |
| `test_local_api_shutdown_blocks_when_schedule_stop_watcher_is_armed` | lifecycle |
| `test_local_api_shutdown_force_cleanup_invokes_backend_owned_process_cleanup` | lifecycle |
| `test_local_api_shutdown_force_cleanup_ignores_non_boolean_truthy_values` | lifecycle strict JSON |
| `test_local_api_shutdown_logs_close_readiness_exceptions` | lifecycle logging |
| `test_local_api_shutdown_logs_callback_failures_after_response` | lifecycle logging |
| `test_local_api_shutdown_logs_timer_start_failures` | lifecycle logging |
| `test_local_api_process_commands_require_token_before_side_effects` | process command routes |
| `test_local_api_rejects_invalid_command_payload_before_side_effects` | process command routes |
| `test_local_api_route_exception_is_recorded_in_command_journal` | process command journal |
| `test_local_api_scheduled_continuous_start_arms_backend_stop_watcher` | process command / lifecycle watcher |
| `test_local_api_diagnostics_tail_reads_allowlisted_file` | diagnostics routes |
| `test_local_api_diagnostics_state_summary_reads_backend_allowlist` | diagnostics routes |
| `test_local_api_network_lifecycle_dry_run_does_not_write_command_journal` | network routes |
| `test_local_api_repair_reconcile_dry_run_routes_return_schema_and_suppress_journal` | repair/reconcile routes |
| `test_local_api_settings_reload_failure_is_logged` | settings route/logging |
| `test_rename_browse_resolves_dropped_folder_paths_without_dialog` | rename routes |
| `test_rename_clean_filename_preview_get_route_uses_backend_cleaner_without_command_journal` | rename routes |
| `test_rename_clean_filename_preview_rejects_invalid_query_json_without_command_journal` | rename routes |
| `test_rename_filter_settings_persist_and_feed_saved_preview_policy` | rename/settings routes |
| `test_local_api_queue_state_routes_are_contracted_journaled_and_source_scoped` | queue routes |
| `test_local_api_queue_priority_clear_all_clears_entire_manifest` | queue priority routes |
| `test_local_api_queue_priority_read_fails_closed_when_manifest_is_corrupt` | queue priority routes |
| `test_local_api_queue_priority_bulk_accepts_manual_order_positions` | queue priority routes |
| `test_local_api_file_override_clear_fields_preserves_save_and_full_clear` | queue file overrides |
| `test_local_api_file_override_validates_current_payload_fields` | queue file overrides |
| `test_local_api_file_override_effective_read_reports_match_sources_and_library_defaults` | queue file overrides |
| `test_local_api_file_override_revalidates_merged_route_video_edits` | queue file overrides |
| `test_local_api_file_override_route_preview_is_read_only_and_validates_proposals` | queue file overrides |
| `test_local_api_file_override_route_video_persistence_validation_and_effective_metadata` | queue file overrides |
| `test_local_api_queue_and_rename_preview_contracts` | split between queue and rename |
| `test_local_api_rename_apply_rejects_absent_or_false_confirmation_without_mutation` | rename mutation route |
| `test_local_api_rename_apply_blocks_active_work_without_mutation` | rename mutation route |
| `test_local_api_injects_rename_media_roots_and_requires_outside_root_confirmation` | rename route authority |
| `test_local_api_injects_library_profile_roots_for_rename_authority` | rename route authority |
| `test_local_api_rename_undo_uses_backend_root_and_strict_confirmation` | rename undo route |
| `test_local_api_serves_read_only_web_prototype` | WebView static contracts; split first |

## Assertion Preservation Inventory

Before moving the giant Web prototype test, generate an assertion-target
inventory. It helps prove the split did not lose an entire page or asset
bundle.

```powershell
@'
import ast
from collections import Counter
from pathlib import Path

path = Path("tests/python/desktop/test_application_facade_local_api.py")
source = path.read_text(encoding="utf-8")
module = ast.parse(source)
cls = next(node for node in module.body if isinstance(node, ast.ClassDef) and node.name == "LocalApiServerTests")
fn = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == "test_local_api_serves_read_only_web_prototype")
counts = Counter()
for node in ast.walk(fn):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr.startswith("assert") and len(node.args) >= 2:
        target = node.args[1]
        if isinstance(target, ast.Name):
            counts[target.id] += 1
for target, count in counts.most_common():
    print(f"{count:4} {target}")
'@ | .\apps\desktop\runtime\Python\python.exe -
```

Expected top targets include `html`, `js`, `queue_view_js`,
`settings_view_js`, `launch_view_js`, `diagnostics_view_js`,
`pending_publish_view_js`, `rename_view_js`, and `command_history_js`.

## Stop Conditions

Stop the split and report instead of continuing when:

- baseline tests fail and the failure is not understood;
- moving helpers changes product imports;
- any moved test starts requiring real media, OS dialogs, browser automation, or
  network access that the original test did not require;
- `unittest discover` reports duplicate tests;
- a route mutation test becomes less strict about confirmation fields;
- command-journal assertions are weakened;
- WebView static assertions are moved into a Local API route test only because
  it is convenient;
- the old god-file still attracts new unrelated tests after the split.

## Output Of This Phase

- baseline command results;
- current method inventory;
- assertion-target inventory for the giant Web prototype test;
- confirmed target file list;
- change packet created or selected;
- unrelated dirty files listed separately.
