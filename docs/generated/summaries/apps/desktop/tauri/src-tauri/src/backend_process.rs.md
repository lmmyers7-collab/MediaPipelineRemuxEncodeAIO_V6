---
file: apps/desktop/tauri/src-tauri/src/backend_process.rs
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Rust
pipeline_stage: n/a
token_priority: medium
owner_domain: shell
last_modified: 2026-07-20
last_reviewed: 2026-06-04
sha256: 9a1a1d8bda42b0b2c7435a0e33cfd73bf5b6ad940694f3e8fc4e6c12363e18c5
---
# `apps/desktop/tauri/src-tauri/src/backend_process.rs`

**Purpose:** Rust implementation for backend process; exposes backend_shutdown_request_body, BackendBootstrap, BackendProcess.

**Public symbols:** `backend_shutdown_request_body`, `BackendBootstrap`, `BackendProcess`, `BackendProcessExit`, `BackendShutdownMode`, `BackendShutdownOutcome`, `BackendShutdownResponse`, `bootstrap_error`, `ChildExitWait`, `ChildPoll`, `close_request_decision`, `CloseRequestDecision`, `drop`, `elapsed`, `find_closing_quote`, `health_check`, `inspect_managed_child`, `ManagedChildProcess`, `parse_backend_shutdown_outcome`, `path_value_end`, `poll`, `push_bootstrap_stdout_context`, `python_path_with_src_root`, `read_backend_bootstrap`, `redact_assignment_marker`, `redact_bearer_marker`, `redact_bootstrap_stdout`, `redact_json_string_field`, `redact_unc_paths`, `redact_validation_detail`, `redact_windows_user_paths`, `request_backend_shutdown`, `resolve_shutdown_with_child`, `shutdown`, `shutdown_backend_state`
**HTTP routes:** `/api/backend/shutdown`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths apps/desktop/tauri/src-tauri/src/backend_process.rs`._
