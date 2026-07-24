# Tauri Backend Lifecycle Boundary

Purpose: document the intended lifecycle boundary between the Tauri/WebView2 shell and the Python backend so that future changes do not accidentally cross it.

This is the lifecycle boundary document for the promoted Tauri/WebView2
shell and the validation gates required for future lifecycle or packaging
changes.

---

## Current Boundary

The Tauri shell (`apps/desktop/tauri/src-tauri/src/lib.rs`) owns:

- Spawning the Python backend through an isolated interpreter bootstrap (`python -I -c ...`) that inserts only the resolved release `src` root before running `mediapipeline.desktop.local_api_main`
- Requiring release builds to use `apps/desktop/runtime/Python/python.exe` and to match its byte count and SHA-256 against the exact entry in the root `mediapipeline_release_manifest.v1`; ambient `python` remains available only in debug builds
- Removing inherited `PYTHONPATH`, `PYTHONHOME`, `PYTHONUSERBASE`, and `PYTHONSTARTUP` from the child environment and disabling user-site/safe-path fallbacks
- Reading the bootstrap payload from backend stdout (token + URL, `desktop_local_api_bootstrap.v1` schema)
- Validating backend health via `GET /api/health` before opening WebView2
- Validating the backend route contract via `GET /api/contract` before opening WebView2
- Validating backend-served WebView assets via `GET /` + selected asset paths before opening WebView2
- Holding a per-user Windows single-instance mutex before backend startup so a second Tauri shell does not spawn a second local backend
- Requiring validation harnesses to bind observed shell, backend, WebView2, and backend-reported pipeline processes to the exact `Start-Process` launcher ancestry. Harness cleanup retains PID plus creation time, revalidates both before fallback termination, and refuses global name/baseline-delta cleanup.
- Starting a bounded lifecycle monitor after setup that checks backend process exit and periodically validates `GET /api/health`
- Querying close readiness via `GET /api/backend/close-readiness` when the operator closes the window
- In productized builds only, checking the configured signed updater channel at startup, keeping download/signature verification separate from installation, and obtaining explicit native confirmation for both phases
- Refusing updater installation unless a fresh backend close-readiness response is safe and a second backend-owned `SafeOnly` shutdown check completes; the updater has no force-close path
- Writing bounded native updater recovery evidence under Tauri's app-local data root and reconciling installer handoff against the exact version observed on the next launch
- Enforcing a five-second monotonic total deadline across every loopback backend request's connect, write, and read phases, in addition to per-I/O timeouts and the response-size cap
- Requesting graceful shutdown via `POST /api/backend/shutdown` after close is confirmed
- Terminating the backend process tree if graceful shutdown does not complete within a grace period
- Draining backend stdout/stderr incrementally without `BufRead::lines` so a
  child-controlled physical line retains at most 16 KiB before UTF-8 decoding
  and cannot force an unbounded allocation
- Limiting each backend-output diagnostic preview to 500 characters, emitting
  only a 20-line burst per stream, and replacing later content with
  content-free suppression/overflow counters no more often than every five
  seconds
- Keeping bootstrap discovery lossless within the 16 KiB physical-line bound
  through a capacity-one channel, then explicitly releasing the receiver so
  stdout draining continues during startup validation
- Binding both native WebViews to the exact normalized backend origin with
  `on_navigation`; sibling loopback ports, alternate loopback spellings,
  foreign schemes/hosts, `about:blank`, and `data:` navigations are denied
- Running the token-bearing initialization script only in the top frame when
  `window.location.origin` exactly matches that validated origin, and clearing
  the bootstrap global before returning in every other frame or document

The Python backend (local API) owns:

- All media processing decisions (route, encode, subtitle, audio, publish)
- All queue mutation (launch, pause, stop, rerun, drain, rename apply, settings save)
- All persistent state (completed manifest, pending publish manifest, failure markers, run logs)
- All command journaling and duplicate-command guards
- The full set of Local API routes and their authentication requirements
- Close-readiness evaluation (when it is safe for the shell to shut down)
- The graceful shutdown sequence (flushing state, releasing locks, stopping workers)

The WebView (JavaScript frontend) owns:

- Read-only rendering of backend-served state
- Operator UI (form inputs, selectors, table interactions)
- A read-only Tauri lifecycle event bridge (`tauriLifecycleBridge.js`) that listens only for `mediapipeline://backend-lifecycle`, re-dispatches a DOM event, and renders a warning banner plus Diagnostics recovery guidance
- One separately allowlisted, window-only WebView command bridge (`pipelineLogWindowBridge.js`) that may invoke only `open_pipeline_log_window` to show or focus the backend-served read-only Pipeline Log window; it cannot accept a path or start a process
- Forwarding mutation commands to backend-owned Local API routes via `POST`/authenticated requests
- Non-mutating operator assistance (checklists, handoff panels, readiness summaries)
- Diagnostics open/tail requests via backend-allowlisted keys only

---

## Why This Boundary Matters

### Backend-owned mutation prevents double-execution

If the WebView or Tauri shell duplicated launch, drain, rename, or settings-save logic, the same operation could run twice, corrupt shared state, or produce results that differ from backend-owned commands. Keeping mutation behind Local API routes ensures command journaling, duplicate guards, and backend policy apply consistently.

### Backend-owned close readiness prevents data loss

If the shell decides when it is safe to close without asking the backend, active pipeline work, in-flight drain operations, or in-progress rename batches could be interrupted mid-write. The `GET /api/backend/close-readiness` contract gives the backend authority to report active work, unsafe state, and specific warnings before the shell terminates.

### Backend-owned process lifecycle prevents orphaned workers

The pipeline may spawn or coordinate worker processes. If the shell kills the backend process without a graceful shutdown, workers may continue running, logs may be incomplete, and parked outputs may be left in a partially-written state. The `POST /api/backend/shutdown` → grace-period → force-kill sequence ensures the backend has a chance to clean up.

---

## Production Lifecycle Guardrails

The current promoted lifecycle has production-hardening guardrails for shell
startup, runtime/import provenance, backend health/crash visibility, and
token/devtools static posture.
Default-launcher/package-mode promotion is closed by operator confirmation on
2026-05-30, and representative real-media validation is closed by operator
attestation on 2026-05-28. Future launcher, package, Tauri, or Local API
lifecycle changes still require package/open/close validation. Future
media-policy, FFmpeg, subtitle, audio, publish/drain, source movement, or cleanup
behavior changes still require representative real-media revalidation.

The synthetic Tauri harness ownership gate launches two concurrent disposable
process trees and proves that exact-tree cleanup preserves the unrelated tree
and rejects a creation-time mismatch. That gate does not replace the
representative active-work/real-media close validation required before a
harness cleanup change is trusted around live processing.

### 1. Spawn resilience

- Detect backend process exit before bootstrap payload arrives and report the bounded stdout context to the operator (currently implemented via `MAX_BOOTSTRAP_STDOUT_LINES` / `MAX_BOOTSTRAP_STDOUT_CHARS`).
- Consider whether to attempt one auto-restart before surfacing a fatal error to the operator, or whether restart should require an explicit operator action.

### 2. Health monitoring after open

- Implemented for the Tauri side on 2026-05-19: `backend_lifecycle_monitor.rs` polls every 5 seconds and emits `mediapipeline://backend-lifecycle` after two consecutive health failures.
- The WebView still does its normal refresh/poll reads through the Local API. The Tauri monitor is an outer shell guard, not a replacement for backend-authored evidence or WebView command results.

### 3. Crash recovery notification

- Implemented for the Tauri side on 2026-05-19: the lifecycle monitor checks the managed backend process and emits `mediapipeline://backend-lifecycle` with schema `mediapipeline_backend_lifecycle_event.v1` if the process exits unexpectedly.
- Implemented for the WebView side on 2026-05-19: `tauriLifecycleBridge.js` listens only for that Tauri event and `app.js` renders a top-level lifecycle warning banner plus Diagnostics recovery guidance. The bridge does not call Local API POST routes, open files, invoke shell/process APIs, or mutate media/state.
- The lifecycle bridge remains event-only. `pipelineLogWindowBridge.js` is the distinct narrow exception for direct Tauri invocation: it calls exactly `open_pipeline_log_window`, with no arguments, to create/show/focus a read-only window whose URL is derived from the validated loopback backend URL. Browser-hosted WebView uses `window.open` as a compatibility fallback. Neither path accepts an operator path or owns filesystem, process, pipeline, settings, queue, publish, or media mutation.

### 4. Orphan cleanup on abnormal exit

- If the Tauri shell crashes before issuing `POST /api/backend/shutdown`, the Python backend continues running. On next launch, the backend should detect a stale `ActiveJobs` record and clean it up. Document or verify that this already happens via the existing launch-lock/control-flag cleanup path.
- Verified current backend side: ActiveJobs records are explicit contracts, read paths reconcile definitely-gone tracked PIDs, and reliability checks guard stale ActiveJobs/orphaned status behavior. This remains backend-owned; the Tauri shell does not edit ActiveJobs.

### 5. Multiple window safety

- Implemented on 2026-05-19 and updated for the current shell: the Tauri shell opens one dynamic `main` WebView2 window and acquires `Local\MediaPipelineRemuxEncodeAIO_TauriShell` before backend startup. A second shell instance fails before spawning another backend and reports an explicit operator error: use the existing window or close it before launching another preview shell.

### 6. Token rotation

- The bootstrap token is generated per process start and is not persisted. This is correct behavior. Verify that the token is not logged, stored in environment variables inherited by child processes, or exposed through WebView2 developer tools in the production build.
- Current posture: Tauri does not pass the token through environment variables and does not log it in bounded operator-context errors. Rust reads the backend bootstrap token from stdout, uses it for backend validation requests, and injects it into the WebView through `window.MEDIA_PIPELINE_TAURI_BOOTSTRAP` in the Tauri initialization script. Tauri public index HTML must not contain the bearer token. `Test-TauriShell-ProductionSurface.ps1` statically checks that runtime Rust has no production devtools/debugging flags, no token-adjacent runtime logging, one dynamic main window, the single-instance mutex, an event-only Tauri lifecycle bridge, and the separately allowlisted read-only Pipeline Log window command. Clean-machine PG-3 still requires operator confirmation that developer tools are not present on the target machine.

---

## Lifecycle Diagram (Current)

```
[Tauri shell]
  │
  ├─ acquire single-instance mutex → reject second Tauri shell before backend start
  ├─ verify bundled python.exe against release_manifest.json
  ├─ spawn python -I with a release-src-only local_api_main bootstrap
  │     │
  │     └─ backend writes: desktop_local_api_bootstrap.v1 to stdout
  │
  ├─ read bootstrap (url + token)
  ├─ GET /api/health → validate
  ├─ GET /api/contract → validate route set
  ├─ GET / + asset paths → validate WebView assets
  ├─ open WebView2 at backend url with Tauri initialization-script token bootstrap
  ├─ start lifecycle monitor → emit backend health/crash event for WebView banner
  │
  │   [WebView2 open, operator uses UI]
  │
  │   [productized startup updater branch]
  ├─ check signed channel → if newer: prompt before download
  ├─ download complete package and verify signature → prompt before install
  ├─ GET /api/backend/close-readiness → unsafe/unavailable blocks install
  ├─ POST /api/backend/shutdown in SafeOnly mode → blocked/failed stops install
  ├─ record installer handoff; next launch reconciles exact target version
  │
  │   [operator closes window]
  │
  ├─ GET /api/backend/close-readiness → if active work: prompt operator
  ├─ POST /api/backend/shutdown → require backend acknowledgement
  ├─ wait up to 3 seconds for process exit
  ├─ if acknowledged but still running: terminate process tree
  ├─ if transport/acknowledgement fails: retain backend and block shell close
  └─ shell exits
```

---

## Reference To Existing Implementation

## Durable Lifecycle Evidence (2026-07-10)

- `unknown`, stale, malformed, unavailable, and recovery-in-progress close evidence is unsafe. Neither the WebView nor Tauri may convert an authority failure into a safe close.
- Backend process launches hold an atomic durable lifecycle lease under backend state. The lease carries the command ID, resource claims, child PID, heartbeat, and one-shot recovery descriptor; an ambiguous lease blocks a new launch and shell close.
- Critical lifecycle/media routes persist strict `accepted` evidence before mutation and strict terminal evidence after it. A terminal-journal failure creates an indeterminate marker that blocks close/retry until reconciliation.
- Startup exposes `GET /api/backend/recovery-status` and reconciles lifecycle state before the watch-folder manager starts. Only a proven no-media/plan boundary may auto-resume once; partial or ambiguous media/manifests remain parked.
- A confirmed native force-close still requires backend acknowledgement. Tauri retains a live backend if its shutdown transport fails or the backend declines the request; it does not use transport failure as permission to tree-kill work.

- Tauri shell Rust source: `apps/desktop/tauri/src-tauri/src/lib.rs`
- Native updater lifecycle: `apps/desktop/tauri/src-tauri/src/updater_controller.rs`, schema `tauri_native_updater_event.v1`
- Single-instance guard: `apps/desktop/tauri/src-tauri/src/single_instance_guard.rs`
- Tauri lifecycle WebView bridge: `apps/desktop/webview/static/assets/tauriLifecycleBridge.js`
- Production surface audit: `apps/desktop/tauri/Test-TauriShell-ProductionSurface.ps1`
- Backend lifecycle constants: `MAX_BOOTSTRAP_STDOUT_LINES`, `MAX_BOOTSTRAP_STDOUT_CHARS`, `MAX_BACKEND_RESPONSE_BYTES`, `MAX_CLOSE_READINESS_WARNINGS`, `BACKEND_HEALTH_MONITOR_INTERVAL`, `BACKEND_HEALTH_FAILURE_THRESHOLD`
- Bootstrap schema: `desktop_local_api_bootstrap.v1`
- Health schema: `desktop_backend_health.v1`
- Contract schema: `desktop_local_api_contract.v1`
- Close readiness: `GET /api/backend/close-readiness`, `desktop_close_readiness.v1`
- Shutdown: `POST /api/backend/shutdown`

See also `../CURRENT_PROJECT_STATE.md`, the archived WebView-first split notes, and `../testing/VALIDATION_LADDER_RUNBOOK.md` for the current lifecycle, split, and promotion status. Older transition/parity documents were quarantined under `../archive/docs-housekeeping/2026-05-20-review/`.
