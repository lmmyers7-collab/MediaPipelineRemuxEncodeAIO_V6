---
file: apps/desktop/tauri/src-tauri/src/backend_process/tests.rs
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Rust
pipeline_stage: n/a
token_priority: medium
owner_domain: shell
last_modified: 2026-07-23
last_reviewed: 2026-07-11
sha256: 26ef35524e605cdc63a60b384a457108c7db79481db4b9e02278b5e65d0feb7a
---
# `apps/desktop/tauri/src-tauri/src/backend_process/tests.rs`

**Purpose:** Rust implementation for tests; exposes backend_crash_wait_error_remains_monitor_error_not_false_exit, backend_exit_between_health_checks_is_observed_as_exit_not_health, backend_for_child.

**Public symbols:** `backend_crash_wait_error_remains_monitor_error_not_false_exit`, `backend_exit_between_health_checks_is_observed_as_exit_not_health`, `backend_for_child`, `backend_for_child_and_url`, `backend_shutdown_request_body_omits_force_for_safe_only`, `backend_shutdown_response_parser_allows_ok_shutdown`, `backend_shutdown_response_parser_blocks_unsafe_safe_only_shutdown`, `bootstrap_stdout_redacts_personal_and_unc_paths`, `bounded_reader_caps_multimegabyte_unterminated_physical_line`, `bounded_reader_preserves_bootstrap_payload_split_across_small_buffers`, `child_wait_error_after_acknowledgement_is_failed_and_retains_ownership`, `child_wait_error_after_transport_failure_is_not_verified_exit`, `confirmed_force_shutdown_transport_error_retains_running_backend_child`, `descendants_refusing_termination_cannot_report_successful_shutdown`, `elapsed`, `FakeManagedChild`, `FakeWaitClock`, `flooding_output_is_fully_drained_with_rate_limited_content_free_summary`, `killed_backend_process_reports_exit_code_on_windows`, `killed_backend_process_reports_missing_exit_code_on_unix`, `new`, `normal_close_releases_child_only_after_verified_exit`, `poll`, `powershell_literal`, `process_exists`, `safe_only_shutdown_blocked_retains_backend_child`, `safe_only_shutdown_transport_error_allows_exited_backend_child`, `safe_only_shutdown_transport_error_retains_running_backend_child`, `serve_once`, `spawn_child_that_exits`, `spawn_sleeping_child`, `terminate_child_removes_windows_process_tree`, `terminate_tree_and_verify`, `try_take_exited_reports_child_exit_code`, `try_take_exited_reports_no_child_separately`
**State/config identifiers:** `MediaPipeline_config.psd1`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths apps/desktop/tauri/src-tauri/src/backend_process/tests.rs`._
