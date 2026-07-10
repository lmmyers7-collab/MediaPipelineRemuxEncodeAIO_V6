# Schedule, watch, launch, and lifecycle review

Review ID: `CSW-2026-07-09-SCHEDULE`  
Date: 2026-07-09  
Scope: read-only audit of the Schedule WebView, schedule/watch Local API paths, launch guards, control/close lifecycle, and focused tests. No schedule, watcher, mutation route, or test that starts a watcher was run.

## Executive assessment

The Schedule tab correctly acts as a backend-facing editor and evidence surface, not as a scheduler or process controller. The only Schedule mutations available to the WebView are backend preview/save requests; the backend alone parses windows, enforces strict `confirm_save`, persists the two schedule keys, evaluates schedule gates, serializes launch commands, manages the continuous stop watcher, and determines close readiness. Watch-folder auto-launches use that same guarded backend pipeline-start facade as manual launches.

No P0 or P1 issue was found. One P2 recovery gap was found: watch-folder debounce, deduplication, baseline, and pending-work state are memory-only. A backend restart resets them to a fresh baseline, so a stable detection that was waiting for an allowed window or still in debounce can be lost without a recovery indication. This can miss unattended intake, but does not weaken source-media or duplicate-launch safety.

## Workflow traces

### 1. Load and refresh

1. The shared refresh loads `GET /api/schedule` and `GET /api/watch-folders/status` together ([app.js:921-922](../../../apps/desktop/webview/static/assets/app.js#L921-L922)).
2. The read-route registry binds these to backend payload builders ([routes_read.py:43-44](../../../src/mediapipeline/desktop/api/routes_read.py#L43-L44)). Schedule reads `get_schedule_workspace()` ([read_payloads_workspace.py:50-51](../../../src/mediapipeline/desktop/api/read_payloads_workspace.py#L50-L51)); watch status only calls `get_watch_folder_state()` and returns an explicit error payload if unavailable ([read_payloads_status.py:77-88](../../../src/mediapipeline/desktop/api/read_payloads_status.py#L77-L88)).
3. `renderSchedule()` renders backend-supplied state, timing, warnings, watcher state, and editor data ([scheduleView.js:1682-1742](../../../apps/desktop/webview/static/assets/scheduleView.js#L1682-L1742)). `renderWatchFolderStatus()` renders backend scanner evidence only ([scheduleView.js:294-308](../../../apps/desktop/webview/static/assets/scheduleView.js#L294-L308)).

### 2. Create, update, enable, and disable

1. The page stages `enabled` plus seven `day_windows` strings locally; it does not persist them ([scheduleView.js:1024-1035](../../../apps/desktop/webview/static/assets/scheduleView.js#L1024-L1035)). The markup tells operators that preview validates before a save can write app state ([page-schedule.html:29-43](../../../apps/desktop/webview/static/partials/page-schedule.html#L29-L43)).
2. Preview posts the draft to `/api/schedule/preview` ([scheduleView.js:1480-1508](../../../apps/desktop/webview/static/assets/scheduleView.js#L1480-L1508)). The API simply delegates to the backend facade ([commands_schedule.py:6-11](../../../src/mediapipeline/core/api/commands_schedule.py#L6-L11)), where parsing rejects malformed times and midnight-crossing windows ([policy.py:137-167](../../../src/mediapipeline/core/schedule/policy.py#L137-L167)).
3. Save remains disabled unless the exact current draft has a successful preview ([scheduleView.js:1133-1140](../../../apps/desktop/webview/static/assets/scheduleView.js#L1133-L1140), [scheduleView.js:1200-1219](../../../apps/desktop/webview/static/assets/scheduleView.js#L1200-L1219)). After an operator confirmation, it posts `confirm_save: true` ([scheduleView.js:1511-1569](../../../apps/desktop/webview/static/assets/scheduleView.js#L1511-L1569)).
4. The backend independently requires literal Boolean `true`, serializes saves with a non-blocking lock, revalidates the request, and writes only `schedule_enabled` and `schedule_grid` ([facade.py:119-149](../../../src/mediapipeline/core/schedule/facade.py#L119-L149)). App-state save merges unrelated keys and atomically writes the normalized document ([app_state.py:60-93](../../../src/mediapipeline/core/schedule/app_state.py#L60-L93)).

### 3. Watch-folder state and decision

1. Watch folders are disabled by default; their default action is `enqueue_only`, and the default is to respect schedule windows ([config.py:1001-1006](../../../src/mediapipeline/contracts/config.py#L1001-L1006)).
2. The Local API starts the manager only after listener/bootstrap availability ([local_api_main.py:367-395](../../../src/mediapipeline/desktop/local_api_main.py#L367-L395)). A disabled setting or worker role returns an idle/no-scan state ([manager.py:339-369](../../../src/mediapipeline/desktop/watch/manager.py#L339-L369)).
3. Scanner behavior is backend-owned: bounded per-root scans reject overlap, stable-file debounce is enforced, and a bounded fired registry suppresses duplicate detections ([manager.py:237-296](../../../src/mediapipeline/desktop/watch/manager.py#L237-L296), [scanner.py:107-205](../../../src/mediapipeline/desktop/watch/scanner.py#L107-L205)).
4. An `enqueue_and_launch` watch request is a backend `once` launch. It normally preserves the schedule gate; only an explicit configuration setting sends `schedule_override=ignore` ([manager.py:487-511](../../../src/mediapipeline/desktop/watch/manager.py#L487-L511)). Rejections remain observable as `pending_work` plus `last_refusal` ([manager.py:537-543](../../../src/mediapipeline/desktop/watch/manager.py#L537-L543)).

### 4. Schedule trigger to launch decision

1. The process facade evaluates schedule state before it acquires launch authority or spawns a process ([pipeline_facade.py:103-113](../../../src/mediapipeline/core/processes/pipeline_facade.py#L103-L113)).
2. `validate` and pending-publish drain are intentionally unscheduled; disabled schedules permit normal modes. A closed window blocks ordinary starts unless an explicit `run_once` or `ignore` override is supplied ([schedule_policy.py:153-194](../../../src/mediapipeline/core/processes/schedule_policy.py#L153-L194)).
3. An enabled, in-window continuous start fails closed if the backend stop watcher is unavailable ([schedule_policy.py:172-178](../../../src/mediapipeline/core/processes/schedule_policy.py#L172-L178)). When a boundary exists, the backend arms the watcher only after the child PID exists ([pipeline_facade.py:41-67](../../../src/mediapipeline/core/processes/pipeline_facade.py#L41-L67), [pipeline_facade.py:135-153](../../../src/mediapipeline/core/processes/pipeline_facade.py#L135-L153)).
4. At the boundary the watcher writes the backend stop flag, reporting either `stop_requested` or an explicit error ([stop_watcher.py:180-225](../../../src/mediapipeline/core/schedule/stop_watcher.py#L180-L225)).

### 5. Collision handling: manual launch, pause/stop, and close

1. Manual and watch starts converge at `start_pipeline_process()` ([application/facade.py:163-165](../../../src/mediapipeline/desktop/application/facade.py#L163-L165)); a shared non-blocking process-launch lock blocks concurrent start commands ([guard_facade.py:35-54](../../../src/mediapipeline/core/processes/guard_facade.py#L35-L54)). The start route rechecks live related processes and progress after acquiring the lock ([pipeline_facade.py:107-124](../../../src/mediapipeline/core/processes/pipeline_facade.py#L107-L124)).
2. Pause, stop, rescan, and kill remain backend-only control commands with a separate command lock; stop writes the stop flag rather than letting Schedule manipulate it ([control_facade.py:108-183](../../../src/mediapipeline/core/processes/control_facade.py#L108-L183)).
3. Close readiness checks related processes, active work, and an armed schedule watcher ([guard_facade.py:56-107](../../../src/mediapipeline/core/processes/guard_facade.py#L56-L107), [guard_facade.py:219-237](../../../src/mediapipeline/core/processes/guard_facade.py#L219-L237)). An unsafe shutdown is rejected unless literal `force_active_work_shutdown: true` is sent; force cleanup is backend-owned ([commands_process.py:280-318](../../../src/mediapipeline/core/api/commands_process.py#L280-L318)).

### 6. Restart, missed-window, stale-timer, and recovery behavior

- Persisted schedule configuration survives a backend restart through app state; loading defaults safely to enforcement off when no state is available ([app_state.py:32-58](../../../src/mediapipeline/core/schedule/app_state.py#L32-L58)).
- The continuous schedule-stop watcher is intentionally process-local. Its generation check prevents an old canceled/replaced timer thread from overwriting the current watcher state ([stop_watcher.py:80-105](../../../src/mediapipeline/core/schedule/stop_watcher.py#L80-L105), [stop_watcher.py:129-136](../../../src/mediapipeline/core/schedule/stop_watcher.py#L129-L136)). Local API shutdown cancels it and stops the watch manager ([server.py:135-153](../../../src/mediapipeline/desktop/api/server.py#L135-L153)).
- Rejected watch launches retry while the same manager remains alive because `pending_work` causes another dispatch attempt ([manager.py:457-485](../../../src/mediapipeline/desktop/watch/manager.py#L457-L485)). That recovery is not durable across a backend restart; see the P2 finding.

## Findings

### P0 — none

No source-mutation, uncontrolled launch, or unsafe-close defect was found in the reviewed scheduling paths.

### P1 — none

No frontend-owned scheduling/lifecycle policy, schedule-gate bypass without an explicit override, or duplicate manual/watch launch path was found.

### P2

#### CSW-2026-07-09-SCHEDULE-001 — Watch-folder pending work and debounce state are lost across backend restart

Evidence:

- The manager stores baseline signatures, snapshots, stability observations, fired entries, recent detections, and `pending_work` only as instance fields ([manager.py:123-129](../../../src/mediapipeline/desktop/watch/manager.py#L123-L129)).
- Its first cycle after a new manager instance unconditionally resets that state to a current filesystem baseline and returns without dispatching prior candidates ([manager.py:417-432](../../../src/mediapipeline/desktop/watch/manager.py#L417-L432)).
- A schedule-gate refusal otherwise correctly retains `pending_work` and `last_refusal` in memory ([manager.py:537-543](../../../src/mediapipeline/desktop/watch/manager.py#L537-L543)). The configuration’s operator-facing contract promises retries while the window is closed ([watch_fields.py:56-60](../../../src/mediapipeline/core/config/metadata_parts/watch_fields.py#L56-L60)).

Impact: if a stable file is detected while the schedule is closed, but the Local API restarts before the next successful retry, the new manager baselines the file and drops the pending retry. The same loss occurs for a file that was in the debounce interval when the process restarts. The Schedule page then shows a normal new baseline rather than an explicit missed/recovery state. This can silently miss unattended intake; it does not start extra work or affect source-media safety.

Recommendation: persist a narrow, versioned watch recovery journal under the runtime state root containing only candidate identity (canonical path plus stat fingerprint), detection/debounce timestamps, launch/refusal result, and pending status. On startup, reconcile that journal before recording a new baseline, retry only still-valid pending entries through the existing guarded launch facade, and expose recovery/discard reason in `desktop_watch_folders.v1`. Do not auto-launch arbitrary pre-existing root contents merely because a watcher restarted.

Required regression coverage: restart after (a) a detection during debounce, (b) a schedule-gate refusal with pending work, and (c) a successful launch; assert one recovery attempt at most, no duplicate PID/start, invalidated file handling, a visible recovery outcome, and preserved manual-launch collision behavior.

### P3 — none

No lower-severity correctness or disclosure defect was found beyond the recovery gap above.

## No-finding coverage

- **Frontend authority:** Schedule has only local staging plus the two documented schedule POSTs; watch state is labelled backend-owned in the page ([page-schedule.html:72-108](../../../apps/desktop/webview/static/partials/page-schedule.html#L72-L108)). The editor explicitly separates unsaved/previewed drafts from saved/current launch trust ([scheduleView.js:1143-1164](../../../apps/desktop/webview/static/assets/scheduleView.js#L1143-L1164)).
- **Safe defaults and explicit validation:** schedule enforcement defaults off ([app_state.py:32-38](../../../src/mediapipeline/core/schedule/app_state.py#L32-L38)); enabled zero-window and always-on schedules produce backend warnings ([policy.py:218-228](../../../src/mediapipeline/core/schedule/policy.py#L218-L228)); malformed input cannot save ([facade.py:128-145](../../../src/mediapipeline/core/schedule/facade.py#L128-L145)).
- **Duplicate-command/launch protection:** save and launch each have non-blocking locks ([facade.py:162-181](../../../src/mediapipeline/core/schedule/facade.py#L162-L181), [guard_facade.py:35-54](../../../src/mediapipeline/core/processes/guard_facade.py#L35-L54)); launch also checks active process/progress state after the lock is held.
- **Scope disclosure and observable state:** Schedule exposes current window, selected mode/override, watcher state, warnings, roots, reachability, pending work, last launch, and last refusal ([scheduleView.js:153-204](../../../apps/desktop/webview/static/assets/scheduleView.js#L153-L204), [scheduleView.js:1604-1668](../../../apps/desktop/webview/static/assets/scheduleView.js#L1604-L1668)). Watch settings/load/scan errors become degraded/error state rather than an implied successful launch ([manager.py:218-228](../../../src/mediapipeline/desktop/watch/manager.py#L218-L228), [manager.py:460-485](../../../src/mediapipeline/desktop/watch/manager.py#L460-L485)).
- **Disabled versus active behavior:** disabled/worker watch configuration does no scan; coordinator/network configurations retain enqueue-only behavior ([manager.py:339-369](../../../src/mediapipeline/desktop/watch/manager.py#L339-L369), [manager.py:487-500](../../../src/mediapipeline/desktop/watch/manager.py#L487-L500)). An armed stop watcher blocks normal close even if other state appears idle.
- **Stale timer protection:** watcher generation prevents stale timer callbacks from modifying replacement state; errors are explicit in the watcher mapping ([stop_watcher.py:129-136](../../../src/mediapipeline/core/schedule/stop_watcher.py#L129-L136), [stop_watcher.py:228-265](../../../src/mediapipeline/core/schedule/stop_watcher.py#L228-L265)).

## Test and contract assessment

Inspected coverage is strong for the active in-process behavior:

- Schedule read/preview/save, strict confirmation, invalid-time rejection, and preservation of unrelated state: [test_application_facade_schedule.py:18-163](../../../tests/python/desktop/test_application_facade_schedule.py#L18-L163).
- Schedule gate choices and continuous watcher availability: [test_facade_process_schedule_policy.py:24-199](../../../tests/python/desktop/test_facade_process_schedule_policy.py#L24-L199) and [test_application_facade_process_launch.py:985-1028](../../../tests/python/desktop/test_application_facade_process_launch.py#L985-L1028).
- Stop-boundary request, cancellation, stale-generation defense, and error state: [test_schedule_stop_watcher.py:119-279](../../../tests/python/desktop/test_schedule_stop_watcher.py#L119-L279).
- Watch disabled/worker behavior, debounce, once-launch, explicit schedule bypass, refusal retry, settings reload recovery, root derivation, and scan timeout: [test_watch_folder_manager.py:72-204](../../../tests/python/desktop/test_watch_folder_manager.py#L72-L204), [test_watch_folder_manager.py:307-441](../../../tests/python/desktop/test_watch_folder_manager.py#L307-L441).
- Launch-lock/active-work behavior and the preservation of an existing watcher when a second start is blocked: [test_application_facade_process_launch.py:1793-1999](../../../tests/python/desktop/test_application_facade_process_launch.py#L1793-L1999).
- Armed-watcher close/shutdown rejection and explicit forced cleanup: [test_application_facade_close_readiness.py:447-480](../../../tests/python/desktop/test_application_facade_close_readiness.py#L447-L480), [test_application_facade_local_api_lifecycle.py:170-299](../../../tests/python/desktop/test_application_facade_local_api_lifecycle.py#L170-L299).
- Schedule static/browser rendering and frontend mutation-boundary assertions: [test_webview_schedule_smoke.py:530-591](../../../tests/webview/test_webview_schedule_smoke.py#L530-L591), [test_webview_browser_schedule_smoke.py:459](../../../tests/webview/test_webview_browser_schedule_smoke.py#L459), [test_webview_frontend_mutation_boundary.py:489-526](../../../tests/webview/test_webview_frontend_mutation_boundary.py#L489-L526).

The contract inventory agrees with the route ownership: schedule reads are non-mutating, preview is non-mutating, and save is the sole schedule app-state writer ([API_ROUTE_INVENTORY.md:79-80](../../inventories/API_ROUTE_INVENTORY.md#L79-L80), [API_ROUTE_INVENTORY.md:273-276](../../inventories/API_ROUTE_INVENTORY.md#L273-L276)).

The material coverage gap is restart recovery for watch candidates/pending retries. Existing tests exercise rejection-to-success while one manager instance remains live ([test_watch_folder_manager.py:163-204](../../../tests/python/desktop/test_watch_folder_manager.py#L163-L204)), but do not construct a new manager after a pending detection/refusal. Tests were deliberately not executed because the requested audit prohibited starting watchers or schedules.

## Coordinator handoff

Prioritize `CSW-2026-07-09-SCHEDULE-001` as a P2 reliability fix in the watch/state ownership area. Keep the existing central launch facade and schedule policy unchanged; add durable recovery evidence around the watch manager rather than a frontend timer, a second launch path, or automatic processing of all pre-existing files. The implementation owner should coordinate with the runtime-state/observability owner because the recovery journal needs bounded retention, atomic writes, startup reconciliation, and an operator-visible status. Targeted temp-directory unit/API tests should be sufficient; no real-media validation is required unless the change extends beyond watch-state recovery into media policy or source movement.

## Limits

- This was a static, read-only review. I did not execute tests, start Local API/Tauri, enable a schedule, start a watcher, invoke any schedule/watch mutation route, or process media.
- I traced the Schedule WebView, Local API, app facade, watch manager/scanner, process launch/control/guard layers, relevant contracts/inventories, generated summaries, and focused tests. I did not make source, test, config, inventory, generated-document, or change-packet changes.
- The worktree contained extensive pre-existing unrelated modifications. They were not inspected as change candidates or incorporated into this review.
