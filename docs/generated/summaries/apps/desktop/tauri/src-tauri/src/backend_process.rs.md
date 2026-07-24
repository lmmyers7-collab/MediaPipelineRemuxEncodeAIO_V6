---
file: apps/desktop/tauri/src-tauri/src/backend_process.rs
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: Rust
pipeline_stage: n/a
token_priority: medium
owner_domain: shell
last_modified: 2026-07-23
last_reviewed: 2026-06-04
sha256: fe20e1fc98a527f298bb38d3e800e3af56feaa765d1f8076a4f4d1e732567169
---
# `apps/desktop/tauri/src-tauri/src/backend_process.rs`

**Purpose:** Rust implementation for backend process; exposes backend_shutdown_request_body, BackendBootstrap, BackendOutputLogEvent.

**Public symbols:** `backend_shutdown_request_body`, `BackendBootstrap`, `BackendOutputLogEvent`, `BackendOutputLogLimiter`, `BackendProcess`, `BackendProcessExit`, `BackendShutdownMode`, `BackendShutdownOutcome`, `BackendShutdownResponse`, `bootstrap_error`, `bounded_backend_output_preview`, `BoundedOutputLine`, `ChildExitWait`, `ChildPoll`, `close_request_decision`, `CloseRequestDecision`, `drop`, `elapsed`, `emit_backend_output_event`, `emit_backend_output_line`, `find_closing_quote`, `flush_backend_output_limiter`, `health_check`, `inspect_managed_child`, `isolated_python_module_bootstrap`, `ManagedChildProcess`, `new`, `new_backend_shutdown_command_id`, `observe`, `parse_backend_shutdown_outcome`, `path_value_end`, `poll`, `push_bootstrap_stdout_context`, `read_backend_bootstrap`, `read_bounded_physical_line`
**HTTP routes:** `/api/backend/shutdown`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths apps/desktop/tauri/src-tauri/src/backend_process.rs`._
