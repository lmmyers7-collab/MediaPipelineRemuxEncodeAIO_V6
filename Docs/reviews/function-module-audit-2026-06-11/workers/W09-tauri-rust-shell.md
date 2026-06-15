# Worker Review: W09-tauri-rust-shell

## Scope
- Assigned domain: tauri-rust-shell
- Assigned files: 24
- Explicit exclusions: none; coverage is partial where noted below.

## Coverage Ledger

| File | Symbols reviewed | Coverage | Notes |
|---|---:|---|---|
| `apps/desktop/launchers/Launch-MediaPipelineRemuxEncodeAIO-ApiAndBrowser.ps1` | 2 | reviewed-static | Summary read; source scanned for Python resolution, backend start, health polling, and browser launch. |
| `apps/desktop/launchers/Launch-MediaPipelineRemuxEncodeAIO-LocalApi.bat` | 0 | reviewed-static | Summary read; batch source scanned for Python resolution and local API launch path. |
| `apps/desktop/tauri/Launch-MediaPipelineRemuxEncodeAIO-TauriPreview.ps1` | 6 | reviewed-static | Summary read; source scanned for tool resolution, CheckOnly behavior, and process launch. |
| `apps/desktop/tauri/src-tauri/src/backend_contract.rs` | 1 | partial | Summary read; static scan covered token-leak checks and asset-fragment validation, but not every literal fragment branch line-by-line. |
| `apps/desktop/tauri/src-tauri/src/backend_contract/formatting.rs` | 2 | reviewed-static | Summary read; symbol inventory/static scan only. |
| `apps/desktop/tauri/src-tauri/src/backend_contract/health.rs` | 1 | reviewed-static | Summary read; health schema/capability validation scanned. |
| `apps/desktop/tauri/src-tauri/src/backend_contract/route_contract.rs` | 1 | reviewed-static | Summary read; route contract validation scanned. |
| `apps/desktop/tauri/src-tauri/src/backend_contract/routes.rs` | 0 | reviewed-static | Summary read; required route constant set scanned. |
| `apps/desktop/tauri/src-tauri/src/backend_contract/types.rs` | 3 | reviewed-static | Summary read; DTO shape scanned. |
| `apps/desktop/tauri/src-tauri/src/backend_lifecycle_monitor.rs` | 7 | reviewed-static | Summary read; lifecycle monitor loop/event emission scanned. |
| `apps/desktop/tauri/src-tauri/src/backend_process.rs` | 55 | reviewed | Summary read; full source reviewed for backend spawn, bootstrap parsing, shutdown, token redaction, stdout/stderr drains, and tests. |
| `apps/desktop/tauri/src-tauri/src/close_readiness.rs` | 5 | reviewed | Summary read; full source reviewed for close-readiness schema, warnings, watcher evidence, and bounded display. |
| `apps/desktop/tauri/src-tauri/src/debug_webview.rs` | 7 | reviewed | Summary read; full source reviewed for debug auth capture path constraints and debug-only autolaunch scripts. |
| `apps/desktop/tauri/src-tauri/src/dialogs.rs` | 12 | reviewed-static | Summary read; static scan covered path resolution/dialog helpers. |
| `apps/desktop/tauri/src-tauri/src/http_helpers.rs` | 5 | reviewed | Summary read; full source reviewed for HTTP request construction, response caps, and status handling. |
| `apps/desktop/tauri/src-tauri/src/lib.rs` | 31 | reviewed | Summary read; full source reviewed for setup, window close handling, backend shutdown calls, and bootstrap script generation. |
| `apps/desktop/tauri/src-tauri/src/main.rs` | 1 | reviewed-static | Summary read; entrypoint delegation scanned. |
| `apps/desktop/tauri/src-tauri/src/single_instance_guard.rs` | 6 | reviewed | Summary read; full source reviewed for Windows mutex acquisition and handle cleanup. |
| `apps/desktop/tauri/Test-TauriShell-Launch.ps1` | 11 | reviewed-static | Summary read; source scanned for process cleanup and launch/test harness behavior. |
| `apps/desktop/tauri/Test-TauriShell-PG1ActiveClose.ps1` | 17 | reviewed-static | Summary read; source scanned for source path, ActiveJobs lookup, close prompt, and process cleanup. |
| `apps/desktop/tauri/Test-TauriShell-PG2SampleValidationAppend.ps1` | 15 | reviewed-static | Summary read; source scanned for sample-validation append harness, log polling, and process cleanup. |
| `apps/desktop/tauri/Test-TauriShell-PG2WebViewLaunch.ps1` | 15 | reviewed-static | Summary read; source scanned for WebView launch harness, ActiveJobs lookup, and process cleanup. |
| `apps/desktop/tauri/Test-TauriShell-Prereqs.ps1` | 4 | reviewed-static | Summary read; prerequisite checks scanned. |
| `apps/desktop/tauri/Test-TauriShell-WebViewUiAutomationProbe.ps1` | 10 | reviewed-static | Summary read; UI automation probe process cleanup scanned. |

## Findings

| ID | Severity | File | Symbol | Problem | Suggested validation |
|---|---|---|---|---|---|
| W09-001 | P1 | `apps/desktop/tauri/src-tauri/src/lib.rs`; `apps/desktop/tauri/src-tauri/src/backend_process.rs` | `WindowEvent::CloseRequested`; `BackendProcess::shutdown` | The shell exits even if the final safe-only backend shutdown request is blocked after the pre-close readiness check. | Add a unit/integration test where `close_request_decision` first allows safe close but `/api/backend/shutdown` returns `ok:false`, and assert the Tauri close is prevented or the operator is re-prompted instead of exiting. |
| W09-002 | P3 | `apps/desktop/tauri/Test-TauriShell-PG1ActiveClose.ps1`; `Test-TauriShell-PG2WebViewLaunch.ps1`; `Test-TauriShell-PG2SampleValidationAppend.ps1` | script parameters `ActiveJobsDir`; `SampleValidationLog` | PG validation harnesses default to hardcoded `E:\Videos\Scratch\State\...` paths, coupling tests to one machine's live-style runtime state unless the caller overrides them. | Add a harness self-check that derives state paths from the launched backend/config or requires explicit isolated state paths; run PG scripts against a temp LocalBase fixture. |

## Detailed Findings

### W09-001: Close request can exit after safe-only backend shutdown is blocked
- Severity: P1
- File: `apps/desktop/tauri/src-tauri/src/lib.rs:108`; `apps/desktop/tauri/src-tauri/src/backend_process.rs:115`
- Symbol: `WindowEvent::CloseRequested`; `BackendProcess::shutdown`
- Evidence: `close_request_decision` can return `AllowSafe`, then the close handler calls `shutdown_backend_state(window, BackendShutdownMode::SafeOnly)` and unconditionally calls `window.app_handle().exit(0)` at `lib.rs:118`. Inside `BackendProcess::shutdown`, if `/api/backend/shutdown` returns `BackendShutdownOutcome::Blocked`, the SafeOnly path logs the block and returns at `backend_process.rs:117-123` without terminating or taking the child.
- Impact: A close-readiness state change between the pre-close check and the shutdown POST can still close the Tauri shell while leaving backend/pipeline work running or orphaned. This crosses the release-critical close-readiness boundary and can mislead the operator into thinking the app-owned backend was safely stopped.
- Suggested fix: Make `shutdown_backend_state` report `Requested`, `Blocked`, or `Failed`; when SafeOnly shutdown is blocked, call `api.prevent_close()` and surface the close-readiness message instead of exiting. Keep force-close behavior explicit.
- Suggested tests: Unit-test `BackendProcess::shutdown` outcome propagation and a close-event test/double where the first readiness request is safe but shutdown returns `ok:false`; add a Tauri shell PG close smoke covering the race.

### W09-002: PG scripts default to machine-specific runtime state paths
- Severity: P3
- File: `apps/desktop/tauri/Test-TauriShell-PG1ActiveClose.ps1:11`; `apps/desktop/tauri/Test-TauriShell-PG2WebViewLaunch.ps1:10`; `apps/desktop/tauri/Test-TauriShell-PG2SampleValidationAppend.ps1:13`
- Symbol: script parameters `ActiveJobsDir`; `SampleValidationLog`
- Evidence: The PG scripts default `ActiveJobsDir` to `E:\Videos\Scratch\State\ActiveJobs` and `SampleValidationLog` to `E:\Videos\Scratch\State\Validation\sample_validation_log.jsonl`.
- Impact: A validation run can silently inspect or wait on the wrong state root on a clean machine, or couple test evidence to the operator's live-style scratch tree. That creates false confidence in close/launch/sample-validation results and makes failures environment-specific.
- Suggested fix: Require explicit state-root/log parameters for these PG scripts, or derive them from the launched backend's effective config/health response and fail closed when the state root is not isolated for the test.
- Suggested tests: Add static tests that reject hardcoded drive-root defaults in PG validation scripts and an integration run using a temp LocalBase/state root.

## Test Coverage Gaps
- No local Tauri build, Rust test suite, or PG shell smoke was run during this review-only pass.
- No adversarial test currently proves the close handler prevents exit when shutdown is blocked after an initially safe close-readiness check.
- PG scripts need coverage proving they do not accidentally bind validation to a machine-specific runtime state root.

## Boundary Risks
- W09-001 is a close-readiness boundary risk. It does not mutate source media directly, but it can orphan or hide active backend work during shutdown.
- W09-002 is validation-evidence risk rather than production behavior risk.

## Files With No Findings
- Reviewed/static-reviewed files not named in findings had no evidence-based findings in this time-boxed pass.

## Incomplete Coverage
- `backend_contract.rs` contains a long WebView asset-fragment validation body; this review scanned token leakage, required close-readiness/shutdown/media-policy fragments, and request authorization behavior but did not line-review every fragment assertion.
- Static-reviewed launcher/test files were scanned for process/filesystem/auth/path risks but were not line-reviewed for every branch.
