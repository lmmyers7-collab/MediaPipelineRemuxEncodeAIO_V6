# Code Map

This map lists the concrete files and behavior reviewed. Line numbers refer to the observed source at review time.

## Local API Command Path

`src/mediapipeline/desktop/api/handler.py`

- Lines 98-113 read the POST body, validate the route payload, and optionally record validation-failure journal payloads.
- Lines 114-117 convert unexpected route exceptions into sanitized 500 route exception responses.
- Lines 139-146 serialize all API responses with `json.dumps(..., allow_nan=False)` and convert non-strict JSON responses into route exceptions.
- Lines 147-153 record command journal entries only when the payload is not suppressed and the response status is recordable.

`src/mediapipeline/desktop/api/handler_policy.py`

- Lines 55-57 build generic route-exception payloads.
- Lines 64-77 build validation-failure command-result payloads.
- Lines 80-88 suppress validation-failure journaling for unjournaled and secret-transfer route metadata.
- Lines 91-92 only allow journal recording for statuses below 400.

`src/mediapipeline/desktop/api/server.py`

- Lines 92-96 create a `ThreadingHTTPServer`, keep request threads non-daemon, and run the server thread as daemon.
- Lines 102-120 stop the local API, cancel watchers, shut down the server, close the socket, and join the server thread.
- Lines 151-163 refresh the state database root and call the command journal recorder.

`src/mediapipeline/desktop/local_api_main.py`

- Lines 255-266 construct the main local API with a persisted command journal at `RunLogs/local_api_command_history.json`.

`src/mediapipeline/desktop/api/read_payloads_status.py`

- Lines 128-129 expose command history through `/api/commands`.

## Command Journal Policy And Persistence

`src/mediapipeline/desktop/api/command_journal.py`

- Lines 23-28 define the journal as a bounded command-result journal that stores summaries, not full command payloads.
- Lines 30-43 initialize bounded capacity and load persisted entries.
- Lines 45-64 record only command-result payloads, insert newest first, enforce capacity, save, mirror to SQLite, and roll back in-memory mutation only when an exception escapes.
- Lines 66-68 return the bounded command history mapping.
- Lines 70-79 load JSON history best-effort and sanitize loaded entries.
- Lines 81-124 save JSON atomically with temp file, `fsync`, `os.replace`, and retry on `PermissionError`; non-strict save errors are logged and swallowed.
- Lines 126-134 mirror to SQLite best-effort and swallow mirror failures.

`src/mediapipeline/desktop/api/command_journal_policy.py`

- Lines 11-16 define schemas and bounds: command history schema, command-result schema, dictionary/list/text/depth limits.
- Lines 18-28 define sensitive evidence terms including `join_blob`, token, secret, password, and auth/credential terms.
- Lines 31-32 restrict journaled payloads to `desktop_command_result.v1`.
- Lines 61-84 redact sensitive keyed values and recursively bound nested evidence.
- Lines 90-111 summarize command results into bounded evidence fields.
- Lines 118-125 construct bounded command history output.
- Lines 128-152 sanitize loaded entries from disk.

## Strict API Contracts And Mutation Confirmations

`src/mediapipeline/contracts/api_commands.py`

- Lines 17-25 define permissive base payloads and strict payloads with `extra="forbid"`.
- Lines 105-109 require strict `confirm_apply` typing for queue file override series apply.
- Lines 140-144 require strict `confirm_save` typing for settings save patch.
- Lines 156-158 require strict `confirm_save` typing for settings wizard save.
- Lines 167-171 require strict schedule save/preview booleans.
- Lines 188-212 require strict booleans for rename apply, including `confirm_apply`.
- Lines 222-229 require strict network lifecycle confirmation models.
- Lines 414-485 map command routes to concrete payload contracts.
- Lines 492-499 validate route payloads through the selected Pydantic model.

Facade-level mutation confirmation checks:

- `src/mediapipeline/core/rename/facade.py` lines 104-107 reject rename apply unless `confirm_apply is True`.
- `src/mediapipeline/core/orchestration/settings_patch_facade.py` lines 166-169 reject settings save unless `confirm_save is True`.
- `src/mediapipeline/core/schedule/facade.py` lines 119-123 reject schedule save unless `confirm_save is True`; lines 162-172 lock duplicate schedule saves.
- `src/mediapipeline/core/api/commands_file_overrides.py` lines 291-295 reject series apply unless `confirm_apply is True`.
- `src/mediapipeline/core/network/facade.py` lines 1463-1471 require `confirm_create is True` before creating a join blob.
- `src/mediapipeline/core/network/facade.py` lines 1562-1571 require `confirm_import is True` before importing a cluster join.

## Duplicate-Command And Active Process Protection

`src/mediapipeline/core/processes/guard_facade.py`

- Lines 29-40 acquire the shared process launch lock non-blocking and return a duplicate-launch block message on contention.
- Lines 62-103 aggregate active-work blockers before process launch or close.

`src/mediapipeline/core/processes/pipeline_facade.py`

- Lines 71-99 validate pipeline start inputs before launch.
- Lines 99-105 acquire the process launch lock and reject active work before starting a new process.

`src/mediapipeline/core/processes/audit_facade.py`

- Lines 31-62 acquire the shared process launch lock and reject active work before starting audit.

`src/mediapipeline/core/processes/active_jobs.py`

- Lines 239-246 treat unverifiable PID identity as not safe to ignore.
- Lines 272-324 convert malformed records, missing PIDs, live PIDs, and unverifiable PID identity into close blockers.

## Close Readiness And Backend Shutdown

`src/mediapipeline/core/processes/guard_policy.py`

- Lines 8-14 define active and non-blocking states plus the snapshot-unavailable warning.
- Lines 17-43 compute close-readiness fields and fail closed for block messages, active states, unexpected states, or unavailable snapshots.
- Lines 46-50 treat fresh pipeline progress as active unless stopped/completed/inactive.
- Lines 53-57 treat fresh audit progress as active unless completed/failed/inactive.

`src/mediapipeline/core/processes/guard_facade.py`

- Lines 50-60 expose close-readiness through active-work blockers and watcher mapping.
- Lines 62-103 check stale launch guard cleanup, related processes, final-library promotion, queue source scan, schedule watcher, ActiveJobs, pipeline progress, and audit progress.
- Lines 130-148 fail closed on final-library/queue scan inspection errors.
- Lines 150-168 fail closed on ActiveJobs read errors.
- Lines 170-183 fail closed on progress read errors.
- Lines 186-199 fail closed on audit read errors.
- Lines 202-217 block close while the schedule-stop watcher is armed or inspectable only with errors.

`src/mediapipeline/core/api/commands_process.py`

- Lines 55-69 schedule backend shutdown after the response using a timer callback.
- Lines 165-184 perform confirmed-force cleanup of spawned and related processes.
- Lines 186-224 compute backend shutdown behavior: unavailable callback, readiness exception, unsafe without force, unsafe with force cleanup, and safe shutdown.

`src/mediapipeline/core/api/command_results.py`

- Lines 194-202 return a structured shutdown-unavailable command result.
- Lines 205-214 shape unsafe-readiness data.
- Lines 217-257 return blocked, forced, or safe backend shutdown command results.

## Tauri Close Path

`apps/desktop/tauri/src-tauri/src/close_readiness.rs`

- Lines 7-17 define the close-readiness response contract.
- Lines 37-56 call `/api/backend/close-readiness`, require schema `desktop_close_readiness.v1`, and reject malformed responses.
- Lines 59-90 format bounded close warnings and watcher details.
- Lines 93-115 format watcher status lines.

`apps/desktop/tauri/src-tauri/src/backend_process.rs`

- Lines 50-73 define safe-only and confirmed-force shutdown modes and outcomes.
- Lines 111-148 perform backend shutdown; safe-only preserves blocked/failed outcomes, while confirmed force falls through to process-tree termination when needed.
- Lines 168-190 make the close request decision: safe readiness allows safe close; unsafe or readiness error requires user confirmation; cancellation denies close.
- Lines 475-480 add `"force_active_work_shutdown": true` only for confirmed force.
- Lines 484-497 parse backend shutdown results and treat `ok: false` as blocked.
- Lines 500-512 POST `/api/backend/shutdown`.

`apps/desktop/tauri/src-tauri/src/lib.rs`

- Lines 105-129 handle main-window close. Deny prevents close, safe close only exits after safe shutdown is requested, and confirmed force exits after forced shutdown attempt.
- Lines 130-142 call safe-only shutdown for destroyed and app exit events.

## WebView And Diagnostics Trust

`apps/desktop/webview/static/assets/app.js`

- Lines 399-422 implement WebView backend shutdown. The WebView path blocks if commands are in flight or lifecycle shutdown is unavailable, confirms shutdown, and posts a safe shutdown request without force.
- Lines 423-433 append local command history rows when shutdown fetch fails.

`apps/desktop/webview/static/assets/app/lifecycle.js`

- Lines 909-934 render close handoff status, only enable the guardrail handoff when close-readiness is safe, and direct users to Close Readiness, ActiveJobs, Progress, Run Logs, and Last Stderr when unsafe.

`apps/desktop/webview/static/assets/commandHistory.js`

- Lines 238-334 render command evidence resolution rows and warn that command-stream visibility is not success.
- Lines 507-528 append local command results with a 20-entry cap.
- Lines 530-545 convert backend journal entries to UI rows.
- Lines 549-567 merge local and backend rows by `command|result|message`.
- Lines 744-793 render owner/live-state handoff and read-first mutation guardrail messaging.
- Lines 874-887 label command detail source as local pending result or backend journal.

`apps/desktop/webview/static/assets/commandHistory/formatters.js`

- Lines 55-72 include local/journal source in compact evidence.
- Lines 122-150 map commands to owner surfaces and diagnostics targets.
- Lines 154-161 classify issue level by command evidence.

`apps/desktop/webview/static/assets/commandHistory/diagnostics.js`

- Lines 20-34 prioritize issue rows.
- Lines 47-81 include command caveats and mutation guardrail summary lines.
- Lines 179-201 allowlist diagnostics targets.
- Lines 205-240 choose diagnostics actions based on command, owner, and evidence state.

`apps/desktop/webview/static/assets/diagnosticsView.js`

- Lines 1848-1880 implement diagnostics target open requests and append success/failure command history rows.
- Lines 627-633 state that missing diagnostics evidence is not success at the real-media boundary.
- Lines 750-790 expose ActiveJobs, progress, and run-log diagnostics targets.
- Lines 1090-1093 warn that active work should be checked before exiting.
