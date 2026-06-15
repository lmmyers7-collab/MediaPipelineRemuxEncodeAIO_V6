# Worker Review: worker-09-tauri-rust-shell

## Scope
- Worker ID: `worker-09-tauri-rust-shell`
- Assigned domain: Tauri/Rust shell.
- Assigned files reviewed: 24.
- Focus areas: backend process lifecycle, close readiness, single-instance guard, event bridge posture, token/log exposure, package-mode paths, launcher/check-script validation gaps, and CSP/security posture where supported by assigned files.
- Review mode: static/function-level audit only. No code fixes, refactors, commits, media processing, Tauri launch, or runtime-state mutation performed.

## Coverage Ledger

| File | Symbols/sections reviewed | Coverage | Notes |
|---|---:|---|---|
| `apps/desktop/launchers/Launch-MediaPipelineRemuxEncodeAIO-ApiAndBrowser.ps1` | 2 | reviewed-static | Summary read; source reviewed for Python resolution, token-dev mode, backend start, health polling, browser launch, and environment restoration. |
| `apps/desktop/launchers/Launch-MediaPipelineRemuxEncodeAIO-LocalApi.bat` | 1 | reviewed-static | Summary read; batch source reviewed for Python resolution order, `PYTHONPATH`, and Local API launch. |
| `apps/desktop/tauri/Launch-MediaPipelineRemuxEncodeAIO-TauriPreview.ps1` | 6 | reviewed-static | Summary read; source reviewed for tool/Python resolution, CheckOnly behavior, package/dev launch path, and path assumptions. |
| `apps/desktop/tauri/src-tauri/src/backend_contract.rs` | 1 | partial-static | Summary read; source reviewed for bootstrap/token checks, close-readiness/shutdown fragments, and asset validation posture. Long fragment matrix was not line-reviewed for every literal. |
| `apps/desktop/tauri/src-tauri/src/backend_contract/formatting.rs` | 2 | reviewed-static | Summary read; list/route preview helpers reviewed. |
| `apps/desktop/tauri/src-tauri/src/backend_contract/health.rs` | 1 | reviewed-static | Summary read; health schema, status, and required capability checks reviewed. |
| `apps/desktop/tauri/src-tauri/src/backend_contract/route_contract.rs` | 1 | reviewed-static | Summary read; route contract validation reviewed. |
| `apps/desktop/tauri/src-tauri/src/backend_contract/routes.rs` | 1 | reviewed-static | Summary read; required route constant reviewed for lifecycle and mutation route coverage. |
| `apps/desktop/tauri/src-tauri/src/backend_contract/types.rs` | 3 | reviewed-static | Summary read; health/contract/route DTO shapes reviewed. |
| `apps/desktop/tauri/src-tauri/src/backend_lifecycle_monitor.rs` | 4 | reviewed-static | Summary read; monitor loop, process-exit detection, health failure threshold, and event emission reviewed. |
| `apps/desktop/tauri/src-tauri/src/backend_process.rs` | 24 | reviewed | Summary read; full runtime source reviewed for spawn/bootstrap, health/contract/WebView validation, shutdown, close decision, pipe drain, token redaction, and process tests. |
| `apps/desktop/tauri/src-tauri/src/close_readiness.rs` | 4 | reviewed | Summary read; full source reviewed for schema validation, warning rendering, watcher detail, and bounded text. |
| `apps/desktop/tauri/src-tauri/src/debug_webview.rs` | 5 | reviewed | Summary read; full source reviewed for debug auth capture constraints and debug-only WebView autolaunch scripts. |
| `apps/desktop/tauri/src-tauri/src/dialogs.rs` | 7 | reviewed-static | Summary read; desktop-root resolution, Python resolution, path bounding, and native close dialog reviewed. |
| `apps/desktop/tauri/src-tauri/src/http_helpers.rs` | 4 | reviewed | Summary read; full source reviewed for backend URL parsing, authorization header construction, response caps, and error previews. |
| `apps/desktop/tauri/src-tauri/src/lib.rs` | 5 | reviewed | Summary read; full runtime source reviewed for setup order, single-instance guard, WebView creation, close handling, shutdown calls, and token bootstrap script. |
| `apps/desktop/tauri/src-tauri/src/main.rs` | 1 | reviewed-static | Summary read; entrypoint delegation reviewed. |
| `apps/desktop/tauri/src-tauri/src/single_instance_guard.rs` | 3 | reviewed | Summary read; full source reviewed for Windows mutex acquisition, duplicate-instance rejection, and handle cleanup. |
| `apps/desktop/tauri/Test-TauriShell-Launch.ps1` | 11 | reviewed-static | Summary read; source reviewed for dev/packaged launch, PID detection, close smoke, and cleanup. |
| `apps/desktop/tauri/Test-TauriShell-PG1ActiveClose.ps1` | 15 | reviewed-static | Summary read; source reviewed for active-work launch, close prompt capture, force-close validation, ActiveJobs lookup, and cleanup. |
| `apps/desktop/tauri/Test-TauriShell-PG2SampleValidationAppend.ps1` | 13 | reviewed-static | Summary read; source reviewed for debug WebView append harness, token capture, sample-validation log polling, and cleanup. |
| `apps/desktop/tauri/Test-TauriShell-PG2WebViewLaunch.ps1` | 14 | reviewed-static | Summary read; source reviewed for debug WebView launch harness, ActiveJobs polling, token capture, and cleanup. |
| `apps/desktop/tauri/Test-TauriShell-Prereqs.ps1` | 3 | reviewed-static | Summary read; prerequisite/layout/toolchain checks reviewed. |
| `apps/desktop/tauri/Test-TauriShell-WebViewUiAutomationProbe.ps1` | 8 | reviewed-static | Summary read; UI automation probe, launch detection, close smoke, and cleanup reviewed. |

## Findings Summary

| ID | Severity | File | Symbol/section | Summary |
|---|---|---|---|---|
| W09-001 | P1 | `apps/desktop/tauri/src-tauri/src/lib.rs`; `apps/desktop/tauri/src-tauri/src/backend_process.rs` | `WindowEvent::CloseRequested`; `BackendProcess::shutdown` | Shell exits even if the final safe-only backend shutdown request is blocked after the pre-close readiness check. |
| W09-002 | P1 | `apps/desktop/tauri/src-tauri/src/backend_process.rs` | `terminate_child` | Force-close fallback kills only the Python backend process, not the backend process tree documented by the lifecycle boundary. |
| W09-003 | P2 | `apps/desktop/tauri/src-tauri/src/lib.rs`; `apps/desktop/tauri/src-tauri/src/http_helpers.rs` | bootstrap URL handling; `request_backend_json` | Bootstrap URL is not restricted to loopback before the shell sends bearer requests and opens WebView2. |
| W09-004 | P3 | PG Tauri scripts | `ActiveJobsDir`; `SampleValidationLog` defaults | PG validation scripts default to machine-specific `E:\Videos\Scratch\State\...` paths. |

## Detailed Findings

### W09-001: Safe close can still exit after backend shutdown is blocked
- Severity: P1
- File: `apps/desktop/tauri/src-tauri/src/lib.rs:102`; `apps/desktop/tauri/src-tauri/src/backend_process.rs:115`
- Symbol/section: `WindowEvent::CloseRequested`; `BackendProcess::shutdown`
- Evidence: The close handler calls `close_request_decision(window)`, and for `AllowSafe` calls `shutdown_backend_state(window, BackendShutdownMode::SafeOnly)` at `lib.rs:108-110`. It then unconditionally calls `window.app_handle().exit(0)` at `lib.rs:118`. In `BackendProcess::shutdown`, if `/api/backend/shutdown` returns `ok:false`, `parse_backend_shutdown_outcome` maps that to `BackendShutdownOutcome::Blocked`; the SafeOnly branch logs and returns at `backend_process.rs:117-123` without taking or terminating the child. `shutdown_backend_state` returns no outcome to the close handler.
- Impact: A state change between the GET close-readiness check and the POST shutdown request can close the Tauri shell while the backend remains running. That violates the close-readiness boundary and can mislead the operator into thinking a safe shutdown completed while active work or schedule-stop state remains in the backend.
- Fix direction: Make `shutdown_backend_state` return a shutdown result. On SafeOnly `Blocked` or request failure, call `api.prevent_close()` and surface the backend refusal instead of exiting. Keep confirmed-force close explicit and separately audited.
- Validation: Add a unit/integration test with a fake backend where close-readiness first reports safe but `/api/backend/shutdown` returns `{"schema_version":"desktop_command_result.v1","ok":false}`. Assert the close is prevented and the backend child is retained. Add a PG close smoke covering this race.

### W09-002: Force-close fallback does not terminate the backend process tree
- Severity: P1
- File: `apps/desktop/tauri/src-tauri/src/backend_process.rs:136`
- Symbol/section: `BackendProcess::shutdown`; `terminate_child`
- Evidence: After a shutdown request is accepted or forced, `BackendProcess::shutdown` waits 3 seconds for the backend process to exit, then logs that it is "terminating process" and calls `terminate_child` at `backend_process.rs:136-142`. `terminate_child` only calls `child.kill()` and `child.wait()` at `backend_process.rs:412-418`. A search of assigned Rust source found no Windows job object, process-tree traversal, or descendant kill fallback; only the PowerShell smoke cleanup helpers use `$Process.Kill($true)`. The lifecycle boundary says the shell terminates the backend process tree if graceful shutdown does not complete within the grace period.
- Impact: If the Python backend is wedged after spawning PowerShell/FFmpeg/helper descendants, the shell's fallback can kill only the Python parent and leave media workers orphaned. This is exactly the failure mode the lifecycle boundary is meant to prevent: incomplete logs, continuing encode/publish work after the shell exits, and stale ActiveJobs evidence.
- Fix direction: Put the backend process in a Windows Job Object with kill-on-job-close semantics, or implement a bounded descendant-process termination path for the backend PID after the graceful shutdown grace period. Keep backend-owned graceful shutdown first; use tree termination only as the fallback.
- Validation: Add a Rust/windows integration test or Tauri smoke fixture where the backend process spawns a long-lived child and ignores shutdown; assert the fallback removes both parent and child. Add PG active-close evidence that descendant media/helper PIDs are gone, not only the direct pipeline PID.

### W09-003: Bootstrap backend URL is not constrained to loopback
- Severity: P2
- File: `apps/desktop/tauri/src-tauri/src/lib.rs:76`; `apps/desktop/tauri/src-tauri/src/http_helpers.rs:17`
- Symbol/section: bootstrap URL handling; `request_backend_json`
- Evidence: The shell parses `backend.url()` and passes it directly to `WebviewUrl::External(url)` at `lib.rs:76-81`. `request_backend_json` accepts any `http` URL, extracts `host` and `port`, resolves it with `to_socket_addrs`, and sends `Authorization: Bearer {token}` to the resolved address at `http_helpers.rs:17-40`. There is no check that the bootstrap URL host is `127.0.0.1`, `localhost`, `::1`, or otherwise loopback. Existing tests cover rejection of `https://127.0.0.1:1`, but not rejection of non-loopback `http://` hosts.
- Impact: If the bootstrap payload is malformed, compromised, or produced by an unexpected Python/runtime path, the shell can validate and open a non-local HTTP origin under the Tauri shell and inject the Tauri bootstrap token into that page. The intended Local API boundary is localhost-only, so the shell should fail closed before sending bearer requests or opening WebView2.
- Fix direction: Validate bootstrap URLs in one place before health/contract requests and WebView creation. Accept only HTTP loopback hosts and explicit ports; reject non-loopback hostnames/IPs and redirects.
- Validation: Add Rust unit tests for `http://example.com:8765`, LAN IPs, and IPv6 non-loopback rejection, plus positive tests for `127.0.0.1`, `localhost`, and `::1`. Add a startup smoke assertion that the emitted backend URL is loopback.

### W09-004: PG scripts default to machine-specific runtime state paths
- Severity: P3
- File: `apps/desktop/tauri/Test-TauriShell-PG1ActiveClose.ps1:11`; `apps/desktop/tauri/Test-TauriShell-PG2WebViewLaunch.ps1:10`; `apps/desktop/tauri/Test-TauriShell-PG2SampleValidationAppend.ps1:13`
- Symbol/section: script parameters `ActiveJobsDir`; `SampleValidationLog`
- Evidence: PG-1 and PG-2 WebView launch default `ActiveJobsDir` to `E:\Videos\Scratch\State\ActiveJobs`; PG-2 Sample Validation Append defaults `SampleValidationLog` to `E:\Videos\Scratch\State\Validation\sample_validation_log.jsonl`. The scripts then wait on those paths for validation evidence.
- Impact: Clean-machine or package-mode validation can inspect the wrong state root or fail due to a path from one operator machine. Worse, a caller can accidentally couple test evidence to live-style runtime state instead of the launched backend's active state root, weakening the trustworthiness of close/launch/sample-validation validation.
- Fix direction: Require explicit isolated state paths for PG scripts, or derive the state root from the launched backend/config and fail closed if it cannot be proven to match the backend under test.
- Validation: Add static tests that reject hardcoded drive-root state defaults in PG scripts. Run PG scripts against a temporary LocalBase/state root and assert the scripts discover or require that root.

## Test Coverage Gaps
- No Rust/Tauri tests or shell smokes were run during this review-only pass.
- No assigned test covers the W09-001 race where close-readiness is safe but the subsequent safe-only shutdown POST is blocked.
- No assigned test proves the Rust shell kills backend descendants after graceful shutdown times out. Existing assigned smoke cleanup uses PowerShell `$Process.Kill($true)` in the harness, not the Rust runtime fallback.
- Existing static production-surface checks cover CSP presence, devtools text, token-adjacent runtime logging, single-instance guard text, and event-only bridge posture, but that script is adjacent support evidence and not in the W09 assignment table.
- PG scripts do not currently prove their validation paths are derived from the launched backend's state root.

## Boundary Risks
- W09-001 and W09-002 are close-readiness/backend lifecycle boundary risks. They do not directly mutate source media, but they can hide active backend/media work during shell shutdown.
- W09-003 is a Local API/security-boundary risk: the shell should not trust or open non-loopback backend origins.
- W09-004 is validation-evidence risk rather than production runtime behavior.

## Files Reviewed With No Findings
- `apps/desktop/launchers/Launch-MediaPipelineRemuxEncodeAIO-ApiAndBrowser.ps1`
- `apps/desktop/launchers/Launch-MediaPipelineRemuxEncodeAIO-LocalApi.bat`
- `apps/desktop/tauri/Launch-MediaPipelineRemuxEncodeAIO-TauriPreview.ps1`
- `apps/desktop/tauri/src-tauri/src/backend_contract.rs`
- `apps/desktop/tauri/src-tauri/src/backend_contract/formatting.rs`
- `apps/desktop/tauri/src-tauri/src/backend_contract/health.rs`
- `apps/desktop/tauri/src-tauri/src/backend_contract/route_contract.rs`
- `apps/desktop/tauri/src-tauri/src/backend_contract/routes.rs`
- `apps/desktop/tauri/src-tauri/src/backend_contract/types.rs`
- `apps/desktop/tauri/src-tauri/src/backend_lifecycle_monitor.rs`
- `apps/desktop/tauri/src-tauri/src/close_readiness.rs`
- `apps/desktop/tauri/src-tauri/src/debug_webview.rs`
- `apps/desktop/tauri/src-tauri/src/dialogs.rs`
- `apps/desktop/tauri/src-tauri/src/main.rs`
- `apps/desktop/tauri/src-tauri/src/single_instance_guard.rs`
- `apps/desktop/tauri/Test-TauriShell-Launch.ps1`
- `apps/desktop/tauri/Test-TauriShell-Prereqs.ps1`
- `apps/desktop/tauri/Test-TauriShell-WebViewUiAutomationProbe.ps1`

## Files Marked Out Of Scope
- `apps/desktop/tauri/Test-TauriShell-ProductionSurface.ps1` - read as supporting evidence for CSP/devtools/token/bridge posture, but not listed in the W09 assignment table.
- `apps/desktop/tauri/Test-TauriShell-Build.ps1` - adjacent Tauri validation script, not listed in the W09 assignment table.
- `apps/desktop/tauri/New-TauriShell-PG3CleanMachineReport.ps1` - adjacent clean-machine reporting script, not listed in the W09 assignment table.
- `apps/desktop/tauri/src-tauri/tauri.conf.json` - read as supporting evidence for CSP posture, but not listed in the W09 assignment table.
- `apps/desktop/webview/static/assets/tauriLifecycleBridge.js` - read as supporting evidence for event-only bridge posture, but belongs to the WebView worker scope.
- `apps/desktop/tauri/package.json`, `apps/desktop/tauri/package-lock.json`, `apps/desktop/tauri/README.md`, `apps/desktop/tauri/src-tauri/Cargo.toml`, and `apps/desktop/tauri/src-tauri/Cargo.lock` - adjacent package/config files, not listed in the W09 assignment table.

## Incomplete Coverage
- Coverage is complete for assigned files at static/function-level review depth.
- Runtime validation is incomplete: no `cargo test`, Tauri build, WebView2 launch, or PG smoke was executed.
- `backend_contract.rs` contains a long literal fragment matrix; this review covered security/lifecycle/media-policy-relevant fragments and request behavior, but did not inspect every WebView fragment assertion for product correctness.
- Static-reviewed PowerShell scripts were audited for lifecycle/security/path risks but not executed and not exhaustively branch-tested.
