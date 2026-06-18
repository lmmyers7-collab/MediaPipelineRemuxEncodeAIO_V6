# Memory Leak Investigation

Date: 2026-06-17

Change packet: `MP-CHANGE-2026-0617-004`

Scope: report-only audit for long-running memory and resource leak risks, with emphasis on 30-day unattended operation. No code behavior was changed.

## Executive summary

This audit did not find a single obviously catastrophic leak path in the promoted WebView/Tauri plus Python backend stack. Several high-value cleanup mechanisms already exist: command history is capped, watch-folder recent detections and fired entries are bounded, diagnostics tails are byte-limited, queue source scans clear active state in `finally`, Local API shutdown stops owned managers, Tauri backend shutdown terminates the child process tree, and Python subprocess stdout/stderr log file handles are closed with context managers.

The strongest long-running risks are concentrated in four areas:

1. Coordinator network-mode state can grow without a durable cap in `InFlightRegistry._worker_stats` and `_failure_ledger`.
2. The WebView app bootstrap installs permanent timers and many DOM/window listeners without a global "already initialized" sentinel, so duplicate script evaluation or duplicate bootstrap would stack polling and handlers.
3. Worker stop behavior can intentionally preserve active jobs and heartbeat/reporting paths after a stop request; this needs explicit ownership and soak proof so it does not retain dispatcher, app, process, and claimed-job state indefinitely.
4. Fire-and-forget cluster-log POSTs spawn one daemon thread per event without a queue or concurrency cap.

The next best step is not speculative refactoring. Add instrumentation and focused stress tests that track RSS, thread count, handle count, browser heap, registry JSON size, worker-stat count, failure-ledger count, and active timer/listener counts across accelerated 30-day-equivalent scenarios.

## Methodology

Required session entry docs were read first:

- `AGENTS.md`
- `docs/CURRENT_PROJECT_STATE.md`
- `docs/OPEN_WORK_CHECKLIST.md`
- `docs/generated/PROJECT_INDEX.md`

Generated summaries were used before opening full source where present. The audit then used targeted searches for:

- `addEventListener`, `removeEventListener`, `setInterval`, `setTimeout`, `clearInterval`
- thread and background-task creation/shutdown
- `Popen`, `Process`, `Start-Process`, `Start-Job`, `WaitForExit`
- queue/list/cache/log growth and explicit caps
- registry, manifest, diagnostics, watch-folder, coordinator, worker, and WebView polling state

No dynamic soak, profiler, browser automation, or real-media run was executed for this report. Findings below are static source-backed risks plus recommended proof.

## Leak-risk inventory

### R1. WebView main bootstrap can stack app polling and page listeners

- Resource type: timer/listener
- Path/symbol: `apps/desktop/webview/static/assets/app.js`; `DOMContentLoaded` bootstrap, `window.setInterval(() => refreshAll(...), AUTOMATIC_REFRESH_INTERVAL_MS)`, many `addEventListener` calls
- Trigger condition: `app.js` is evaluated or bootstrapped more than once in the same WebView document, such as hot reload, partial reload, script reinjection, or an accidental second DOMContentLoaded registration path.
- Expected runtime symptom: increasing `/api/*` polling frequency, duplicate command execution handlers, duplicate refresh rendering, extra network traffic, higher browser CPU, and confusing UI state after long open sessions.
- Severity: high
- Likelihood: medium
- Existing cleanup evidence: `refreshAll()` has `refreshInFlight` and `refreshQueued` coalescing; automatic refreshes return when one is already in flight; `apiClient.js` uses `AbortController` and clears request timeout timers.
- Missing cleanup evidence: the main interval handle is not stored or cleared; there is no global bootstrap sentinel visible around the main DOMContentLoaded body; most listeners installed in the main bootstrap are not removable as a group.
- Test/instrumentation to prove or disprove: add a WebView smoke that loads the page, injects/evaluates `app.js` twice or simulates duplicate bootstrap, then monkey-patches `window.setInterval`, `EventTarget.prototype.addEventListener`, and `apiGet` to assert one automatic refresh interval and one listener set. Run for 30 minutes with heap snapshots and request counts.
- Remediation recommendation: add a single page-lifetime bootstrap guard such as `window.__mediaPipelineAppBootstrapped`; store interval IDs in a lifecycle registry; expose a teardown function for tests and Tauri unload; make duplicate bootstrap a logged no-op.

### R2. UI preference remote refresh interval and visibility/focus listeners are permanent

- Resource type: timer/listener
- Path/symbol: `apps/desktop/webview/static/assets/app.js`; `startSharedUiPreferenceRemoteRefresh()`
- Trigger condition: shared UI preference sync is started and the document remains open for days, or the start function is called again after its interval was externally cleared without removing prior focus/visibility listeners.
- Expected runtime symptom: repeated `/api/settings/ui-preferences` refreshes every 3 seconds for the full WebView lifetime, plus duplicate focus/visibility-triggered refreshes if start is repeated in the same document.
- Severity: medium
- Likelihood: medium
- Existing cleanup evidence: `uiPreferenceRemoteRefreshTimer` guards normal repeated start calls; storage sync also uses an install guard.
- Missing cleanup evidence: no corresponding `stopSharedUiPreferenceRemoteRefresh()`; visibility listener is an inline closure that cannot be removed; interval is not cleared on unload or when the page is hidden for long periods.
- Test/instrumentation to prove or disprove: instrument event listener counts and UI-preference route calls during repeated settings open/close, WebView backgrounding, and synthetic reinitialization. Verify the count stays flat over 24-hour accelerated idle.
- Remediation recommendation: store named listener functions; add stop/teardown; pause or slow remote refresh when `document.hidden`; fold this timer into the central app refresh lifecycle.

### R3. Rename workbench event setup has no visible init guard

- Resource type: listener
- Path/symbol: `apps/desktop/webview/static/assets/renameView.js`; `renameInitWorkbenchEvents()`
- Trigger condition: rename workbench initialization is called more than once in the same page lifetime.
- Expected runtime symptom: duplicate rename preview/apply/browse/drop handling, repeated route calls, unexpected multiple apply attempts, and retained closures over workbench DOM/state.
- Severity: high
- Likelihood: low to medium
- Existing cleanup evidence: adjacent rename cleaning-filter setup has `renameCleaningFilterEventsBound`; dialog close listeners are removed; preview timers are cleared before rescheduling.
- Missing cleanup evidence: no equivalent init-bound flag was found for `renameInitWorkbenchEvents()`; drag/drop and button listeners are installed directly.
- Test/instrumentation to prove or disprove: call `renameInitWorkbenchEvents()` twice in a browser smoke and assert one handler invocation per click/drop/input using counters around `refreshRenamePreview`, `applyRenameWorkbench`, and browse calls.
- Remediation recommendation: add an idempotent init guard matching the cleaning-filter pattern, or use event delegation from a stable root with a single installed listener.

### R4. Worker shutdown can preserve active heartbeat and job state

- Resource type: async task/process/cache
- Path/symbol: `src/mediapipeline/desktop/network/worker_claims.py`; `_heartbeat_thread`; `src/mediapipeline/desktop/network/worker.py`; `shutdown(...)`; `src/mediapipeline/desktop/application/network_lifecycle_provider.py`; `stop_network_worker()`
- Trigger condition: worker stop is requested while a network worker job is active. The provider calls shutdown with `preserve_active_job=active_job`.
- Expected runtime symptom: worker runtime entry, dispatcher, app wrapper, active `ClaimedJob`, heartbeat thread, and active process references remain after "stop" until terminal reporting completes. If the active process or done reporting stalls, memory/thread/process state can survive for days.
- Severity: high
- Likelihood: medium
- Existing cleanup evidence: normal `mark_done()` and `_do_release()` call `_stop_heartbeat()` and clear `_active_job`; active-job watcher calls `dispatcher.mark_done()` and clears `_active_job`/`_active_proc`; runtime entry is popped by `_network_active_job_finished()` after active work completes.
- Missing cleanup evidence: no hard maximum preservation deadline was found; no explicit leak metric proves preserved workers are eventually finalized under coordinator outage, lost result artifact, or hung child process conditions.
- Test/instrumentation to prove or disprove: run a worker job with a child process that ignores stop, then request worker stop. Track thread count, active runtime entries, heartbeat POST attempts, active process PID, and memory for longer than claim timeout. Repeat with coordinator unreachable during done reporting.
- Remediation recommendation: define an ownership contract for preserved active jobs; add a bounded drain deadline and operator-visible state; ensure timeout path kills or releases the active claim and removes the runtime entry after durable pending-done evidence is saved.

### R5. Cluster-log POSTs spawn unbounded daemon threads under event storms

- Resource type: async task/log
- Path/symbol: `src/mediapipeline/desktop/network/worker.py`; `log_cluster_event()`
- Trigger condition: many worker cluster events occur while the coordinator is slow or unreachable.
- Expected runtime symptom: many short-lived daemon threads in flight, retained request payload closures, local warning spam, transient RSS/thread-count spikes, and delayed shutdown if the process is under scheduler pressure.
- Severity: medium
- Likelihood: medium
- Existing cleanup evidence: failures are caught; cluster logging is best-effort; HTTP calls should be bounded by the HTTP timeout path.
- Missing cleanup evidence: no queue, semaphore, thread pool, backpressure, or event coalescing was found; thread count is not exposed in diagnostics.
- Test/instrumentation to prove or disprove: point worker cluster logging at a blackholed coordinator and trigger hundreds of claim/release/malformed/failure events. Assert max `cluster-log-post` threads, RSS, and local log rate remain bounded.
- Remediation recommendation: replace one-thread-per-event with a bounded queue and one sender thread, or use a small executor with drop/coalesce policy for non-critical cluster-log events.

### R6. Coordinator worker statistics are not capped

- Resource type: cache/list
- Path/symbol: `src/mediapipeline/desktop/network/registry.py`; `InFlightRegistry._worker_stats`, `note_worker_seen()`, `claim()`, `heartbeat()`, `complete()`, `save()`, `load()`
- Trigger condition: many unique `worker_id` values contact the coordinator over 30 days, due to worker reinstall, generated IDs, misconfiguration, test clients, or hostile/noisy clients with valid token.
- Expected runtime symptom: growing memory, larger `coordinator_inflight.json`, slower registry save/load, heavier Worker Board payloads, and degraded coordinator responsiveness.
- Severity: high
- Likelihood: medium
- Existing cleanup evidence: worker stat fields are sanitized on load; per-worker values are bounded strings/numbers; active jobs and claimed paths are removed on completion/unclaim.
- Missing cleanup evidence: no maximum number of worker stat entries, TTL pruning by `last_seen`, or persisted compaction was found.
- Test/instrumentation to prove or disprove: simulate 100,000 unique workers calling claim/heartbeat without work. Measure registry JSON size, save/load latency, coordinator RSS, and Worker Board route latency.
- Remediation recommendation: cap worker stats with TTL and maximum entries; keep aggregates for evicted workers; emit diagnostics when pruning occurs.

### R7. Coordinator failure ledger is not capped

- Resource type: cache/list
- Path/symbol: `src/mediapipeline/desktop/network/registry.py`; `InFlightRegistry._failure_ledger`, `complete(success=False)`, `failure_ledger_entries()`, `save()`, `load()`
- Trigger condition: repeated failures across many unique worker/source pairs.
- Expected runtime symptom: growing in-memory ledger and registry JSON, slower coordinator status routes, slower save/load, and increasing diagnostics payload size during long unattended failure runs.
- Severity: high
- Likelihood: medium to high
- Existing cleanup evidence: success removes the failure-ledger entry for that worker/source; failure reason text is bounded; reclaim ledger and late terminal reports are capped at 128 entries.
- Missing cleanup evidence: no maximum failure-ledger entries, TTL, per-source cap, or size budget was found.
- Test/instrumentation to prove or disprove: force failures for many unique source paths and worker IDs. Track `_failure_ledger` length, registry file size, coordinator route latency, and memory after every 1,000 failures.
- Remediation recommendation: add a maximum entry count and TTL; aggregate evicted failures by reason/source library; persist a compact summary rather than every stale worker/source pair.

### R8. Completed-job manifest cache can retain all records for a cache window

- Resource type: cache
- Path/symbol: `src/mediapipeline/core/completed/service.py`; `load_recent_completed_jobs(limit=None)`, `_completed_history_records`
- Trigger condition: any route or maintenance path requests completed history with `limit=None` against a large completed manifest.
- Expected runtime symptom: backend RSS spike and up to 60-second retention of every parsed `CompletedJobRecord`; repeated broad refreshes can produce persistent high memory while the WebView is open.
- Severity: medium
- Likelihood: medium
- Existing cleanup evidence: default limit is 500; cache invalidates by manifest path, proof mode, limit key, mtime, and 60-second TTL; code comments estimate 50,000 jobs at about 20 MB.
- Missing cleanup evidence: no upper bound for `limit=None`; no route-level proof that all WebView/API paths always use bounded limits; no memory test for very large manifests.
- Test/instrumentation to prove or disprove: generate manifests with 50,000, 250,000, and 1,000,000 rows; call each completed-history route with default and all-history modes; track peak RSS, retained records, and latency.
- Remediation recommendation: avoid `limit=None` on interactive routes; stream/export all-history requests; cap cache size by count or bytes; report truncation in the payload.

### R9. Diagnostics directory summaries scan past the advertised limit

- Resource type: file metadata/cache
- Path/symbol: `src/mediapipeline/core/diagnostics/state_summary.py`; `_directory_summary()`, `DIAGNOSTICS_STATE_SUMMARY_DIR_SCAN_LIMIT`
- Trigger condition: diagnostics state summary is requested while allowlisted directories contain very large numbers of files.
- Expected runtime symptom: high CPU and filesystem metadata I/O, slow diagnostics refreshes, delayed WebView polling, and transient memory pressure from path/stat objects. The retained recent-entry list is bounded, but the scan work is not.
- Severity: medium
- Likelihood: medium
- Existing cleanup evidence: recent entries are held in a heap capped at 10; warnings are bounded; file and text summaries use byte limits.
- Missing cleanup evidence: after `scanned > 500`, code marks `large_directory = True` but continues iterating through the whole directory; no time budget or early break was found.
- Test/instrumentation to prove or disprove: create allowlisted diagnostics directories with 10,000, 100,000, and 1,000,000 entries; call `/api/diagnostics/state-summary`; measure wall time, CPU, handle count, and UI refresh impact.
- Remediation recommendation: break after the scan limit, or add a time budget and sampling strategy. If "most recent N" is required, use OS-specific bounded enumeration or make the full scan an explicit maintenance command.

### R10. Process heartbeat watcher threads are untracked

- Resource type: async task/process
- Path/symbol: `src/mediapipeline/core/processes/spawn_runner.py`; active-job completion watcher and heartbeat watcher; `src/mediapipeline/core/processes/lifecycle.py`; active spawned-process registry
- Trigger condition: a launched pipeline process runs for a long time, blocks in `wait()`, or the completion watcher fails before unregistering the process.
- Expected runtime symptom: retained heartbeat watcher threads and `Popen` references in active spawned-process state; close readiness remains blocked; backend RSS and thread count drift upward if launches repeatedly fail to cleanly exit.
- Severity: medium to high
- Likelihood: low to medium
- Existing cleanup evidence: stdout/stderr log handles are closed in `finally`; launch failure kills the process tree; completion watcher unregisters active process in `finally`; heartbeat watcher exits when process is no longer registered or `poll()` reports exit; `kill_active_spawned_processes()` snapshots and unregisters.
- Missing cleanup evidence: heartbeat watcher thread handles are not stored or joined; no diagnostic counter proves zero orphan heartbeat watchers after repeated start/stop/kill cycles.
- Test/instrumentation to prove or disprove: run repeated launch/stop/kill cycles with fake/hung child processes. Track `threading.enumerate()` names, active spawned-process count, open file handles, and close-readiness state after each cycle.
- Remediation recommendation: track heartbeat watcher threads or use one scheduler thread; expose active process registry and watcher counts in diagnostics; assert watcher count returns to baseline after terminal process cleanup.

### R11. PowerShell native process wrappers do not dispose process objects

- Resource type: process/file handle
- Path/symbol: `ops/pipeline/engine/shared/native.ps1`; `Invoke-NativeProcess`; `ops/pipeline/engine/process/ffmpeg_progress.ps1`; `Invoke-FFmpegWithProgress`; related `Start-Process -PassThru` wrappers
- Trigger condition: long-running PowerShell process repeatedly launches FFmpeg, ffprobe, mkvmerge, Subtitle Edit, or other tools over many files.
- Expected runtime symptom: process handles and pipe-related handles can remain until .NET/PowerShell garbage collection, causing gradual handle-count growth during large queues.
- Severity: medium
- Likelihood: medium
- Existing cleanup evidence: native stdout/stderr text builders are bounded by call-site max values; process trees are killed on timeout/stop; `Start-Job` usage removes jobs; audit hash streams dispose explicitly.
- Missing cleanup evidence: no `finally { $proc.Dispose() }` was found in the central native process wrapper after `WaitForExit`; ffmpeg progress stores `$Global:ffmpegProcess` and clears it, but clearing the reference is not the same as disposing the process object.
- Test/instrumentation to prove or disprove: run a PowerShell-only loop of hundreds of short native process launches through `Invoke-NativeProcess`; sample `Get-Process -Id $PID | Select HandleCount, WorkingSet64` before, during, and after forced garbage collection.
- Remediation recommendation: add central `try/finally` disposal for `System.Diagnostics.Process` objects after streams are drained and exit code captured; add a regression smoke that validates handle count returns near baseline.

### R12. Tauri backend pipe reader and lifecycle monitor threads are detached

- Resource type: async task/process
- Path/symbol: `apps/desktop/tauri/src-tauri/src/backend_process.rs`; `spawn_backend_stdout_reader()`, `spawn_pipe_drain()`; `apps/desktop/tauri/src-tauri/src/backend_lifecycle_monitor.rs`; `start_backend_lifecycle_monitor()`
- Trigger condition: backend startup repeatedly fails, the backend process produces long-lived output before bootstrap, or shell setup starts a second lifecycle monitor.
- Expected runtime symptom: detached reader/monitor threads remain until pipe close or backend state disappears; duplicate monitors could emit duplicate lifecycle events and health checks.
- Severity: low to medium
- Likelihood: low
- Existing cleanup evidence: startup failure terminates and waits for the child; stdout/stderr reader threads end when pipes close; backend shutdown takes the child, requests shutdown, waits, kills process tree, then waits; lifecycle monitor exits on `NoChild` or missing backend state.
- Missing cleanup evidence: no stored `JoinHandle` for pipe readers or lifecycle monitor; no explicit singleton guard for lifecycle monitor.
- Test/instrumentation to prove or disprove: repeatedly force backend bootstrap timeout and contract validation failure in Tauri check mode; track process/thread count and duplicate lifecycle events.
- Remediation recommendation: store monitor state or a singleton guard; consider joining reader threads during startup failure tests; add Tauri lifecycle smoke assertions for one monitor and no child process after failure.

### R13. Coordinator cluster log rotation is best-effort

- Resource type: log
- Path/symbol: `src/mediapipeline/desktop/network/coordinator_state.py`; `_append_cluster_log()`, `_cluster_log_max_bytes`
- Trigger condition: coordinator cluster log reaches the configured rotation threshold while rename/delete/replace fails because of file lock, permissions, antivirus, or filesystem error.
- Expected runtime symptom: cluster log continues to grow on disk, diagnostics/open-log operations slow down, and disk pressure can affect unattended operation.
- Severity: medium
- Likelihood: low to medium
- Existing cleanup evidence: coordinator sets `_cluster_log_max_bytes` to 50 MB; append uses file context managers; rotation keeps a backup.
- Missing cleanup evidence: if rotation fails, there is no hard write refusal, truncation fallback, or disk budget enforcement visible in the append path.
- Test/instrumentation to prove or disprove: lock the cluster log file and generate events beyond the rotation threshold. Verify resulting log size, warning evidence, and coordinator responsiveness.
- Remediation recommendation: add a fallback bounded append strategy after rotation failure, such as writing to a new suffix, truncating with explicit warning, or disabling cluster-log appends until manual repair.

### R14. Coordinator queue refresh holds full queue snapshots repeatedly

- Resource type: queue/list/cache
- Path/symbol: `src/mediapipeline/desktop/application/network_lifecycle_provider.py`; `_start_coordinator_queue_refresh_loop()`, `_refresh_coordinator_queue_records()`, `_NetworkRuntimeApp.queue_records`
- Trigger condition: coordinator mode runs for 30 days while source folders contain very large queues or frequent queue changes.
- Expected runtime symptom: repeated allocation of full queue/failure record lists every refresh interval, transient RSS spikes, garbage collector pressure, and route latency during queue swaps.
- Severity: medium
- Likelihood: medium
- Existing cleanup evidence: refresh swaps the app queue list under a lock; old lists become collectible; stop sets the refresh event and joins the provider thread.
- Missing cleanup evidence: no observed maximum queue-record count, no incremental diffing, and no memory instrumentation for repeated large refreshes.
- Test/instrumentation to prove or disprove: run coordinator queue refresh against synthetic queues of 10,000 to 250,000 records for several hours; record RSS, GC stats, refresh duration, and claim latency.
- Remediation recommendation: add queue-size diagnostics and refresh duration metrics; consider incremental queue diffs or paged claims if large queues are expected.

## High-risk scenarios

### 1. Thirty-day coordinator with worker churn

If worker IDs churn and jobs fail across many source paths, `_worker_stats` and `_failure_ledger` can grow for the whole coordinator process and persist through `coordinator_inflight.json`. This is the highest-confidence 30-day memory/state growth concern.

Proof target: after a simulated 30-day equivalent of worker churn, registry entry counts and serialized size must stay below defined budgets, and coordinator save/load plus status routes must remain within operator-acceptable latency.

### 2. WebView left open while bootstrap is duplicated

The normal page lifetime likely has one bootstrap, but there is no visible hard guard. A duplicate app bootstrap would stack the permanent 15-second refresh interval and many button/listener closures.

Proof target: duplicate script/bootstrap tests should show exactly one automatic refresh timer and one handler per control.

### 3. Network worker stopped during active encode

The code intentionally preserves reporting paths for active work. That is operationally reasonable, but a hung child, lost result artifact, or coordinator outage can turn intentional preservation into long-term object retention.

Proof target: after stop-with-active-job, the system must either finish, save durable pending-done evidence, or remove runtime ownership within a bounded deadline.

### 4. Diagnostics against very large runtime directories

Diagnostics summaries keep returned data bounded but can still walk every entry in a large allowlisted directory. During unattended runs, log/state directories can become large enough that diagnostics polling itself becomes a resource problem.

Proof target: diagnostics summary calls must have wall-time and filesystem-operation budgets independent of directory size.

### 5. Large completed manifests and broad UI refresh

The completed manifest cache is safe for ordinary default limits, but `limit=None` can retain all parsed records. This is a memory spike risk for mature libraries with years of completed jobs.

Proof target: completed-history routes should prove bounded memory under worst-case manifest size or explicitly stream/export all-history paths.

## Validation strategy

Recommended instrumentation:

- Backend process: RSS, private bytes if available, thread count, open handle count, active spawned-process count, active watcher count, queue-record count, completed-cache count, registry JSON size.
- WebView: timer count, listener count by target/type, heap snapshots, API request count per route, duplicate handler invocation count.
- Coordinator: `_worker_stats` count, `_failure_ledger` count, `_recent_completions` count, active jobs, save/load duration, `/api/status` and `/api/claim` latency.
- Worker: heartbeat thread status, poll thread status, pending-done state, active child PID, cluster-log queue/thread count.
- PowerShell child process runner: `$PID` handle count and working set before and after high-volume native process launches.

Recommended tests:

1. WebView duplicate bootstrap smoke: instrument timers/listeners, run duplicate init, assert idempotency.
2. WebView idle soak: leave page open for 24 hours or accelerated route mock, assert stable heap and request rate.
3. Coordinator worker-churn stress: generate many unique worker IDs and failed source paths, assert registry caps.
4. Worker active-stop stress: stop worker during active/hung encode with coordinator reachable and unreachable, assert bounded preservation.
5. Cluster-log storm: blackhole coordinator log route and generate high event volume, assert bounded thread count.
6. Completed manifest scale test: load 50,000, 250,000, and 1,000,000 manifest rows through all API/UI paths.
7. Diagnostics huge-directory test: populate allowlisted diagnostic directories and assert summary response time stays bounded.
8. PowerShell process-handle loop: run hundreds of short `Invoke-NativeProcess` calls and assert handle count returns near baseline.
9. Tauri backend failure loop: force bootstrap/contract failures and assert no backend child processes or duplicate monitor events remain.
10. 30-day accelerated unattended profile: run coordinator, worker, WebView polling, queue refresh, diagnostics refresh, and periodic failed jobs with counters persisted every minute.

## Remediation roadmap

Priority 0:

1. Add caps/TTL pruning to `InFlightRegistry._worker_stats` and `_failure_ledger`.
2. Add WebView bootstrap idempotency and central timer/listener lifecycle tracking.
3. Define and enforce a bounded drain deadline for worker stop with active job preservation.

Priority 1:

1. Replace worker cluster-log one-thread-per-event with a bounded sender queue.
2. Cap or stream completed-history all-record paths.
3. Stop diagnostics directory scan at a real limit or add a time budget.
4. Track process heartbeat watcher counts and expose them in diagnostics.

Priority 2:

1. Dispose PowerShell `System.Diagnostics.Process` objects in central wrappers.
2. Add Tauri lifecycle monitor singleton proof and failure-loop smoke.
3. Add queue refresh size/duration telemetry and large-queue budget tests.
4. Add cluster-log rotation failure fallback.

## Existing cleanup evidence worth preserving

- `apps/desktop/webview/static/assets/apiClient.js` clears request timeout timers and uses `AbortController`.
- `apps/desktop/webview/static/assets/app/layoutManager.js` removes drag listeners and deletes hint timers from its `WeakMap`.
- `apps/desktop/webview/static/assets/settingsView.js`, `settingsWizard.js`, and `reportsView.js` use init guards for major event binding paths.
- `apps/desktop/webview/static/assets/diagnosticsView.js` clears Tdarr Matrix background polling on completion or after 240 attempts.
- `src/mediapipeline/desktop/api/server.py` guards repeated `start()` and stops server, scheduler watcher, and watch-folder manager.
- `src/mediapipeline/core/telemetry/service.py` starts one telemetry thread and stops it through `local_api_main.py` shutdown.
- `src/mediapipeline/desktop/api/command_journal.py` caps command entries and uses context-managed atomic JSON writes.
- `src/mediapipeline/desktop/watch/scanner.py` closes `os.scandir()` iterators, caps fired entries at 10,000, and expires them after 24 hours.
- `src/mediapipeline/desktop/watch/manager.py` caps recent detections at 50 and joins the polling thread on stop.
- `src/mediapipeline/core/queue/service.py` clears queue source scan active state in `finally`.
- `src/mediapipeline/core/status/file_io.py` and diagnostics policy code use bounded tail reads.
- `apps/desktop/tauri/src-tauri/src/backend_process.rs` kills and waits for the backend child process on startup failure and shutdown.

## Open questions

- What is the expected upper bound for unique coordinator worker IDs over 30 days?
- What is the expected upper bound for completed manifest rows in a mature operator library?
- Are there supported workflows that evaluate WebView scripts multiple times in one document, such as development reload or Tauri navigation reuse?
- Should worker stop with active job have a hard maximum preservation time, or is indefinite preservation intentional when process work continues?
- Is cluster-log data operational evidence that must be lossless, or can it be lossy under event storms?
- Which API/UI routes, if any, intentionally request `load_recent_completed_jobs(limit=None)`?
- What are acceptable memory, handle-count, and thread-count budgets for a 30-day unattended Windows run?

## Appendix: reviewed surfaces

Primary source surfaces reviewed:

- `apps/desktop/webview/static/assets/app.js`
- `apps/desktop/webview/static/assets/apiClient.js`
- `apps/desktop/webview/static/assets/tauriLifecycleBridge.js`
- `apps/desktop/webview/static/assets/app/layoutManager.js`
- `apps/desktop/webview/static/assets/renameView.js`
- `apps/desktop/webview/static/assets/settingsView.js`
- `apps/desktop/webview/static/assets/settingsWizard.js`
- `apps/desktop/webview/static/assets/reportsView.js`
- `apps/desktop/webview/static/assets/diagnosticsView.js`
- `src/mediapipeline/desktop/api/server.py`
- `src/mediapipeline/desktop/api/command_journal.py`
- `src/mediapipeline/desktop/services.py`
- `src/mediapipeline/core/telemetry/service.py`
- `src/mediapipeline/core/processes/spawn_runner.py`
- `src/mediapipeline/core/processes/lifecycle.py`
- `src/mediapipeline/core/queue/service.py`
- `src/mediapipeline/core/completed/service.py`
- `src/mediapipeline/core/status/file_io.py`
- `src/mediapipeline/core/diagnostics/state_summary.py`
- `src/mediapipeline/desktop/network/coordinator.py`
- `src/mediapipeline/desktop/network/coordinator_lifecycle.py`
- `src/mediapipeline/desktop/network/coordinator_state.py`
- `src/mediapipeline/desktop/network/registry.py`
- `src/mediapipeline/desktop/network/worker.py`
- `src/mediapipeline/desktop/network/worker_claims.py`
- `src/mediapipeline/desktop/application/network_lifecycle_provider.py`
- `src/mediapipeline/desktop/application/schedule_stop_watcher.py`
- `src/mediapipeline/desktop/watch/manager.py`
- `src/mediapipeline/desktop/watch/scanner.py`
- `apps/desktop/tauri/src-tauri/src/backend_process.rs`
- `apps/desktop/tauri/src-tauri/src/backend_lifecycle_monitor.rs`
- `ops/pipeline/engine/shared/native.ps1`
- `ops/pipeline/engine/process/ffmpeg_progress.ps1`
- `ops/pipeline/engine/queue/worker_process.ps1`
- `ops/pipeline/entrypoints/MediaPipeline.ps1`

Limitations:

- Static source audit only; no profiler, heap snapshot, or Windows handle trace was run.
- No 30-day soak, accelerated soak, browser automation, Tauri preview, or real-media validation was run.
- Runtime behavior may differ under operator-specific media libraries, antivirus/file-lock behavior, network latency, and UNC storage behavior.
- Existing generated summaries and the project index were used to target source reads, but this was not a full line-by-line review of every repository file.
