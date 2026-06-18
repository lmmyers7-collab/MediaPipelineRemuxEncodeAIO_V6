# UI Responsiveness Audit

Date: 2026-06-17
Change packet: MP-CHANGE-2026-0617-006
Scope: WebView/static UI, Local API routes used by the UI, command journal, duplicate-command handling, queue, settings, libraries, rename, publish/pending-publish, diagnostics/logs, startup/bootstrap, and error/status patterns.
Mode: Report-only audit. No UI or backend behavior changes were made.

## Executive Summary

The promoted WebView UI has strong responsiveness foundations on the highest-risk workflows. Pipeline start, pending-publish drain, backend shutdown, rename apply, settings patch save/preview, queue file overrides, completed final-library promotion, pending recovery plans, diagnostics Tdarr matrix actions, maintenance jobs, and metrics source commands all have some combination of confirmation, in-flight state, disabled controls, status text, command-history evidence, or stale-state guards.

No confirmed Critical responsiveness gap was found in source-mutating media workflows. The strongest remaining risk is High: Network lifecycle and join/test/discovery commands update status text but do not appear to use a local in-flight lock or disabled state, so double-clicks can submit overlapping lifecycle requests and create operator distrust even if backend preconditions later block unsafe work.

The main Medium findings are incomplete busy/disabled/stale-state handling on secondary command surfaces: queue priority/manual order/strategy, schedule preview/save, report/audit utility commands, settings-library wrapper status, sample validation buttons, optional refresh failure visibility, and long POST timeout/progress behavior. These are mostly trust and ambiguity issues rather than direct media safety issues.

## Methodology

- Read required entry docs first: AGENTS.md, docs/CURRENT_PROJECT_STATE.md, docs/OPEN_WORK_CHECKLIST.md, and docs/generated/PROJECT_INDEX.md.
- Used generated summaries before full source reads. Several relevant summaries were `token_priority: medium` and `(unparsed)`, so targeted source reads were necessary.
- Scanned `apps/desktop/webview/static/` partials for user actions and DOM state hooks.
- Traced WebView route calls through `apiGet`, `apiPost`, and action handlers.
- Checked backend route registry and command journal behavior in `src/mediapipeline/core/api/commands.py`, `src/mediapipeline/desktop/api/routes_command.py`, `src/mediapipeline/desktop/api/handler.py`, `src/mediapipeline/desktop/api/command_journal.py`, and `src/mediapipeline/desktop/api/command_journal_policy.py`.
- Checked CSS and markup for hover, focus, disabled, aria-live, role=status, and aria-busy patterns.
- Did not run browser automation or live Local API workflows; this is a static/source-backed responsiveness audit.

## Findings

### 1. UI Action Inventory

| Area | User actions identified | Primary files/functions/routes | Current feedback behavior | Missing or weak state | Severity |
|---|---|---|---|---|---|
| Startup/bootstrap and global refresh | Initial app load, Refresh, per-page refresh buttons, health/close-readiness pills, topbar activity | `app.js::refreshAll`, `app.js::refreshAllNow`, `app/refresh.js`, GET `/api/health`, `/api/snapshot`, `/api/backend/close-readiness`, `/api/commands`, `/api/contract` | Refresh has in-flight queueing, disabled refresh button, aria-busy, topbar activity, and refresh-health failures. Snapshot is required. | Manual refresh queued state is subtle; optional panel failures are mostly topbar/title level and can leave stale panel data visually credible. | Medium |
| Launch controls | Pipeline start, pending-publish drain, audit start, CSV rerun start, pause/rescan/stop/kill, file browse, mode/scope presets | `launchView.js`, `launch/commandButtons.js`, POST `/api/pipeline/start`, `/api/pipeline/control`, `/api/audit/start`, `/api/rerun/start`, `/api/pipeline/browse-file` | Strong guard coverage: confirmation, `launchCommandInFlight`, `controlCommandInFlight`, browse busy state, disabled buttons, status/detail, command history. | Audit policy/ignore/export helpers on Launch do not share the same busy lock. | Medium for helpers only |
| Queue scan and display controls | Scan sources, page filters, table selection, row open actions | `queueView.js`, `queue/openActions.js`, POST `/api/queue/scan`, `/api/queue/open` | Queue scan has `queueScanInFlight`, loading screen, aria-busy, disabled scan button, progress/status, command history. Open actions have busy guard. | Good coverage for scan/open. | Low |
| Queue priority and strategy | Promote/demote/hold selected, bulk movie/TV promote, clear priority manifest, manual order moves/save, apply strategy | `queueView.js::sendQueuePriority`, `sendQueuePriorityBulk`, `clearQueuePriorityManifest`, `saveQueueManualOrderPositions`, `applyQueueStrategy`; POST `/api/queue/priority`, `/api/queue/strategy` | Status text, confirmation for clear/bulk, command result, optimistic displayed update after ok, scan stale-state pause. | No write-specific in-flight lock/disabled state; overlapping priority/manual/strategy POSTs can race refreshes and stale local order. | Medium |
| Queue file overrides | Open drawer, route preview, save/clear override, clear field, series preview/apply | `queue/fileOverrides.drawer.api.js`, `queue/fileOverrides.drawer.series.js`, POST `/api/queue/file-overrides*` | Strong guard coverage: shared `foCommandInFlight`, disabled buttons, status, command result, route preview gate, preview fingerprint for series apply. | Good coverage. | Low |
| Settings patch screens | Validate, reload, browse path, preview patch, save patch, final-library settings preview/save | `settingsView.js`, POST `/api/settings/validate`, `/api/settings/reload`, `/api/settings/browse-path`, `/api/settings/preview-patch`, `/api/settings/save-patch` | Strong guard coverage: `settingsCommandInFlight`, disabled command buttons, stale preview request IDs, confirmation, command history, error status. | Good coverage. | Low |
| Library management | Add/delete profile, defaults/reset, build patch, preview profile patch, save profile patch, route-map selectors | `settingsLibraries.js`, delegated `settingsView.previewSettingsPatch/saveSettingsPatch`, GET `/api/libraries/route-map` | Staged-editor actions give immediate local status; preview/save delegates to guarded settings routes. | Library wrapper status says preview/save "finished" after delegate returns even if backend result was blocked or failed in shared settings detail. | Medium |
| Schedule | Load current, preview schedule, save schedule, clear week, allow all, day/block edits | `scheduleView.js::previewScheduleEditor`, `saveScheduleEditor`; POST `/api/schedule/preview`, `/api/schedule/save` | Save requires current successful preview signature; confirmation before save; status/detail and command history on result/error. | No preview/save in-flight lock or disabled state; overlapping preview/save clicks can produce confusing stale result ordering. | Medium |
| Rename | Browse files/folder, drag/drop, preview, check applicable, apply filesystem rename | `renameView.js`, POST `/api/rename/browse`, `/api/rename/preview`, `/api/rename/apply` | Strong guard coverage: `renameBrowseInFlight`, `renamePreviewInFlight`, `renameApplyInFlight`, commandBusy disables controls, stale preview guard, confirmation dialog, result dialog, progress slots. | Good coverage. | Low |
| Pending publish | Filter triage, refresh evidence, show blockers, drain bridge, recovery-plan selected/all, open evidence | `pendingPublishView.js`, `pendingPublishView.recovery.js`, `pendingPublishView.diagnostics.js`, POST `/api/pending-publish/recovery-plan`, `/api/pending-publish/open`, Launch drain via `/api/pipeline/start` | Recovery/open have in-flight guards and disabled buttons; drain delegates to Launch guard; progress and confidence evidence are live. | Good coverage. | Low |
| Completed/publish | Current output refresh, final-library promote/pause/resume, reconciliation refresh, open completed evidence | `app/refresh.js::refreshCurrentOutputStatus`, `completed/promotionCommands.js`, `completedView.evidence.js`, POST `/api/final-library-promotion/*`, GET `/api/publish-reconciliation` | Strong command guard and disabled buttons for promotion; reconciliation has busy flag; current output refresh disables button. | Good coverage. | Low |
| Reports and diagnostics | Failure marker clear, audit start, score policy save/reset, ignore/export, diagnostics open/tail, Tdarr matrix audit/rerun/open | `reportsView.js`, `diagnosticsView.js`, POST `/api/failures/clear`, `/api/audit/*`, `/api/diagnostics/*` | Diagnostics open and Tdarr matrix actions have explicit busy guards. Reports audit start has a busy flag. Failure clear and audit utility actions have status/detail and command history. | Report/audit utility actions and failure clear lack shared disabled/busy state; audit start busy does not appear to disable buttons. | Medium |
| Network | Coordinator/worker dry-runs, start/stop, join blob create/copy/import, discover, test connection, role setup | `networkView.js::runNetworkLifecycleCommand`, `createNetworkJoinBlob`, `importNetworkJoinBlob`, `discoverNetworkCoordinators`, `runNetworkWorkerTestConnection`; POST `/api/network/*` | Confirmation, route availability disabled state, status text, detailed result. Backend confirmed lifecycle commands are strict-journaled. | No local in-flight lock/disabled state found for lifecycle, join, discovery, or test commands; overlapping requests can confuse lifecycle/job-state trust. | High |
| Maintenance and metrics | Health check, change ledger refresh, release dry-run/build, backfill dry-run, dependency atlas, add metrics source, backfill metrics | `maintenanceView.js`, `metricsView.js`, POST `/api/maintenance/*`, `/api/metrics/*` | Strong guard coverage: in-flight flags, disabled controls, status/progress text, command history. | Good coverage. | Low |
| Sample validation | Use sample category, clear checks, preview record, append record | `crossPageContextView.sampleValidation.js`, POST `/api/sample-validation/preview`, `/api/sample-validation/append` | In-flight flag, status text, append confirmation, command history for append. | Buttons remain enabled and duplicate clicks silently return; preview result is not appended to command history. | Medium |
| Shared UI preferences | Theme, evidence mode, layout customization sync between browser/Tauri | `app.js::persistSharedUiPreferencesNow`, GET/POST `/api/ui-preferences` | Debounced persistence with in-flight/pending queue; intentionally non-blocking. | Backend sync errors are swallowed with no user-facing diagnostics. | Low |

### 2. Missing Feedback By Severity

| Issue | User action | Affected files/functions/routes | Current feedback behavior | Missing state | Severity | Recommended implementation strategy | Validation needed |
|---|---|---|---|---|---|---|---|
| RSP-001 | Network dry-run/start/stop, join blob, join cluster, discover coordinator, worker test | `networkView.js::runNetworkLifecycleCommand`, `createNetworkJoinBlob`, `importNetworkJoinBlob`, `discoverNetworkCoordinators`, `runNetworkWorkerTestConnection`; `/api/network/*` | Status text and confirmation exist; route availability disables unavailable buttons. | In-flight guard, disabled state, aria-busy, duplicate-click rejection, stale result token. | High | Add `networkCommandInFlight` keyed by route/action. Disable all network command buttons during active command, keep dry-run/status reads visible, append duplicate rejection to command history for lifecycle commands. | Browser smoke double-click each network command; assert one POST, visible busy state, restored controls, command history entry on success/error. |
| RSP-002 | Queue priority, bulk priority, clear manifest, manual order save/move, apply strategy | `queueView.js::sendQueuePriority*`, `clearQueuePriorityManifest`, `saveQueueManualOrderPositions`, `applyQueueStrategy`; `/api/queue/priority`, `/api/queue/strategy` | Status text, confirmation for destructive-ish queue state resets, optimistic update after ok, refresh after ok. | Write lock, disabled toolbar, aria-busy, stale write token across refresh. | Medium | Add shared `queueStateWriteInFlight` for priority/manual/strategy. Disable related controls, keep selection stable, and ignore stale responses if a newer write starts. | Unit/DOM smoke double-click priority and strategy; assert one request or explicit busy rejection; assert selector resets only from latest response. |
| RSP-003 | Schedule preview/save | `scheduleView.js::previewScheduleEditor`, `saveScheduleEditor`; `/api/schedule/preview`, `/api/schedule/save` | Preview signature gates save; save confirmation; command history and error result. | In-flight lock and disabled Preview/Save buttons. | Medium | Add `scheduleCommandInFlight`, disable preview/save/load/clear controls while POST is active, and tag preview responses with request signature before rendering. | Double-click preview/save in a stubbed slow API; assert single active request, current preview required, stale result not accepted. |
| RSP-004 | Reports failure clear and audit utility commands | `reportsView.js::requestFailureMarkerClear`, `saveReportAuditScorePolicy`, `ignoreSelectedAuditRows`, `exportAuditRerunCsv`, `startReportAuditFromForm`; `/api/failures/clear`, `/api/audit/*` | Status/detail and command history exist; audit start has a busy flag. | Shared busy lock/disabled state for utility buttons; audit start button disabled during busy. | Medium | Add `reportsCommandInFlight` per command family and disable selected action groups. Keep diagnostic open/tail controls available. | Slow API smoke for failure clear/export/ignore/audit start; assert duplicate click shows Busy and does not submit second POST. |
| RSP-005 | Library profile preview/save | `settingsLibraries.js::previewLibraryProfiles`, `saveLibraryProfiles`; delegated `/api/settings/preview-patch`, `/api/settings/save-patch` | Delegates to guarded Settings command handlers; local status says "finished" after delegate returns. | Propagation of backend ok/blocked/error to library status. | Medium | Have delegated settings commands return the command result or expose last command result, then render Library status from actual result severity. | Stub settings preview/save to return blocked/error; assert Library panel says blocked/error, not just finished. |
| RSP-006 | Sample validation preview/append | `crossPageContextView.sampleValidation.js::previewSampleValidationRecord`, `appendSampleValidationRecord`; `/api/sample-validation/*` | In-flight flag, status text, append confirmation, append command history. | Disabled state, aria-busy, duplicate-click message, preview command-history evidence. | Medium | Disable Preview/Append while `sampleValidationInFlight`; show "Already running"; append preview results to command history or a local bounded history. | Double-click preview/append; assert visible busy state and no silent no-op. |
| RSP-007 | Long or hung POST requests | `apiClient.js::apiPost`; all command routes unless caller passes timeout | Some callers set status/progress and a few pass route timeouts; default POST timeout is unlimited. | Timeout, heartbeat/progress, cancel/retry path for long commands. | Medium | Set conservative default POST timeout or require explicit `timeoutMs: 0` for known long operations. Long operations should poll progress and render retry-safe guidance. | Inject hung POST in browser smoke; assert command exits to error/retry state instead of staying busy forever. |
| RSP-008 | Global refresh optional failures | `app.js::refreshAllNow`, `app/refresh.js::renderRefreshHealth`; optional GET routes | Refresh-health records optional failures; snapshot failure is prominent. | Per-panel stale state markers when optional GET fails. | Medium | Store per-payload `fetched_at` and failure metadata; render stale/error banners in affected panels while preserving last good data. | Stub `/api/queue` or `/api/pending-publish` failure; assert affected panel shows stale/error and last successful timestamp. |
| RSP-009 | Shared UI preferences | `app.js::persistSharedUiPreferencesNow`, `restoreSharedUiPreferences`; `/api/ui-preferences` | Non-blocking sync with debounce and pending queue. | User-visible failure/diagnostic trail when sync repeatedly fails. | Low | Count consecutive preference sync failures and expose a non-blocking Diagnostics/Layout Editor status. | Stub `/api/ui-preferences` failure; assert operator can continue and diagnostics shows sync degraded. |
| RSP-010 | Dynamic action accessibility polish | Dynamic buttons across queue/manual/report/network/library/sample surfaces | Global CSS has hover/focus/disabled states; many static controls have aria-live/role/aria-pressed. | Consistent aria-busy/aria-disabled and focus restoration on all dynamic command buttons. | Low | Add a small command-button helper that sets disabled, aria-disabled, aria-busy, previous label, and focus restoration consistently. | Axe/browser smoke on dynamic command dialogs/drawers; keyboard-only path through queue, network, reports, sample validation. |

### 3. Backend Operations Likely To Feel Slow

| Operation | Routes/functions | Why it may feel slow | Existing UI feedback | Recommended improvement |
|---|---|---|---|---|
| Initial refresh/bootstrap | `refreshAllNow`, many GET routes | 20+ backend reads plus render work; optional reads can time out. | Refresh button disabled, topbar activity, refresh-health. | Per-panel stale markers and first-load skeletons for large panels. |
| Queue source scan | `/api/queue/scan`, queue-plan dry run | Filesystem scan and backend queue curation. | Strong scan busy/loading/progress feedback. | Keep as is; add explicit completion toast/status with changed row count. |
| Pipeline start/audit/rerun/pending drain | `/api/pipeline/start`, `/api/audit/start`, `/api/rerun/start` | Process launch, preflight, locks, pending drain checks. | Strong Launch busy states and command detail. | Keep as is; ensure started job appears in live run strip within one refresh interval. |
| Rename preview/apply | `/api/rename/preview`, `/api/rename/apply` | Path validation and filesystem rename. | Strong busy/confirm/result coverage. | Keep as is; consider progress updates if large batch apply expands. |
| Completed current output refresh | `/api/completed?limit=all&force_refresh=true&proof=live`, `/api/final-library-promotion/status` | Destination existence proof over completed history. | Button disabled and status text. | Show row-count/proof-count while loading if this grows. |
| Final-library promotion | `/api/final-library-promotion/promote-queue`, `/pause`, `/resume` | File movement/promotion orchestration. | Strong command lock and status. | Keep as is; verify progress bars during large promotion. |
| Settings validate/preview/save | `/api/settings/validate`, `/api/settings/preview-patch`, `/api/settings/save-patch` | Schema validation, path/tool checks, backup writes. | Strong busy and stale preview guards. | Return result to Library wrapper so local status is accurate. |
| Network lifecycle/discovery/join | `/api/network/*` | Network IO, lifecycle provider checks, strict journaling. | Status text and confirmation. | Add local command lock, disabled state, and stale response token. |
| Maintenance release/build/backfill/atlas | `/api/maintenance/*` | Release packaging, scans, generated artifacts. | Strong busy/progress states. | Keep as is; validate long timeout behavior. |
| Diagnostics Tdarr matrix | `/api/diagnostics/tdarr-matrix*` | Matrix audit, proof-pack, cleanup/archive/delete utilities. | Strong busy guards. | Keep as is; make cleanup/delete completion highly visible. |

### 4. Places Where UI Can Double-submit Or Race

| Surface | Evidence | Risk | Severity | Mitigation |
|---|---|---|---|---|
| Network lifecycle/join/discovery/test | No `InFlight`/busy flag found in `networkView.js`; commands set status and call `apiPost`. | Overlapping lifecycle requests or stale status results. | High | `networkCommandInFlight` plus disabled/aria-busy controls and latest-response token. |
| Queue priority/manual/strategy | `queueView.js` sends POSTs and refreshes without a shared write lock. | Multiple priority writes or strategy apply responses can interleave. | Medium | Shared queue-state write lock and stale-response ignore. |
| Schedule preview/save | No in-flight flag in `scheduleView.js`. | Preview/save double-click can produce confusing result ordering. | Medium | `scheduleCommandInFlight`; disable controls during POST. |
| Reports audit utilities/failure clear | Status-only POST handlers; audit start has busy flag but no observed button disabling. | Duplicate marker clear/export/ignore/score-policy submissions. | Medium | Shared reports command lock by command family. |
| Sample validation | In-flight flag silently returns while buttons stay enabled. | Double-click appears ignored; user may not trust append state. | Medium | Disable buttons and show "Already running." |
| Refresh vs command completion | `refreshAll` queues manual refresh and drops automatic while in-flight. | Mostly controlled; queued state is not very visible. | Low | Show "Refresh queued" in refresh-health/title when manual refresh queues. |

### 5. Places Where UI Hides Backend Failure

| Surface | Affected files/functions/routes | Current behavior | Hidden failure pattern | Severity | Recommendation |
|---|---|---|---|---|---|
| Library profile wrapper | `settingsLibraries.js::previewLibraryProfiles`, `saveLibraryProfiles` | Always sets "Library preview/save command finished" after delegated command returns. | Backend blocked/error result may only be visible in shared Settings patch detail. | Medium | Return/decorate delegated result and mirror severity in Library status. |
| Shared UI preferences | `app.js::persistSharedUiPreferencesNow`, `restoreSharedUiPreferences`; `/api/ui-preferences` | Catches and ignores errors by design. | Cross-surface layout/theme sync can fail silently. | Low | Non-blocking degraded sync indicator in Diagnostics/Layout Editor after repeated failures. |
| Queue strategy load | `queueView.js::loadQueueStrategy` | Catches and silently ignores API failure. | Selector can keep old/default strategy without explicit stale marker. | Low | Set strategy status to "Unavailable" with last known active value. |
| File override effective/tracks load | `queue/fileOverrides.drawer.api.js` | Falls back to track load or generic "could not be loaded." | Effective-policy read failure can be easy to miss after save. | Low | Promote effective reload failure to command detail and drawer status tone warning. |
| Optional refresh reads | `app.js::refreshAllNow` | Failures roll up into refresh-health. | Individual panels can continue showing last data without local stale banner. | Medium | Per-panel stale metadata and last-success timestamp. |
| Sample validation preview | `crossPageContextView.sampleValidation.js` | Preview errors update local result only; no command-history entry. | Preview failure may be lost after refresh/navigation. | Low | Append preview results/errors to command history or a local preview history. |

### 6. Recommended Implementation Strategy Per Issue

| Issue | Strategy | Validation |
|---|---|---|
| RSP-001 | Add a Network command coordinator with route/action key, disabled/aria-busy button groups, duplicate rejection, and stale-response token. Keep backend lifecycle strict journaling unchanged. | Browser/API mock double-click tests for dry-run, confirmed start/stop, join, discovery, and test connection. |
| RSP-002 | Add queue-state write coordinator for priority/manual order/strategy. Disable related controls, preserve selection, and only render the latest response. | Targeted WebView smoke with slow `/api/queue/priority` and `/api/queue/strategy`. |
| RSP-003 | Add schedule command busy flag, disable Preview/Save/Load/Clear during POST, and keep signature checks on response. | Slow preview/save tests; stale preview cannot enable save. |
| RSP-004 | Add reports command busy lock by action family, disable relevant buttons, and render busy rejection in command history. | Failure clear/export/ignore/start double-click tests. |
| RSP-005 | Return last delegated Settings command result to Library wrapper and render Library status from actual severity. | Stub blocked preview/save and assert Library status mirrors blocked/error. |
| RSP-006 | Disable Sample Validation Preview/Append while in-flight, set aria-busy, and record preview results. | Double-click preview/append and keyboard activation smoke. |
| RSP-007 | Require explicit timeout policy per POST. Add progress polling for known long jobs and retry guidance for timeout. | Hung POST smoke and long-operation smoke. |
| RSP-008 | Add per-panel stale metadata from `refreshFailure` and show panel-level stale/error banners. | Stub optional GET failures and verify stale labels. |
| RSP-009 | Add non-blocking UI preference sync degradation evidence after repeated failures. | Stub sync failure and verify Diagnostics status. |
| RSP-010 | Centralize command button busy/disabled/aria/focus handling. | Keyboard-only and accessibility smoke across dynamic controls. |

## Roadmap

1. High priority: implement RSP-001 Network command in-flight guard first. This is the only High finding because it affects lifecycle/job-state trust.
2. Medium priority: implement shared write coordinators for Queue, Schedule, and Reports utility commands.
3. Medium priority: fix hidden/ambiguous failure reporting for Library delegated settings commands and optional refresh stale panels.
4. Medium priority: define default POST timeout/progress policy so hung command routes do not leave controls busy forever.
5. Low priority: standardize dynamic button aria-busy/disabled/focus restoration and add UI preference sync degradation evidence.

## Validation Recommendations

- Add WebView smoke tests that stub slow Local API POST responses and double-click each command family.
- Add a refresh-staleness smoke that forces one optional GET route to fail while snapshot succeeds.
- Add keyboard-only tests for Network, Queue priority/manual order, Schedule, Reports, and Sample Validation.
- Add command-history assertions for every failed or duplicate command rejection.
- For media-policy-adjacent flows, rerun the existing higher validation ladder if implementation touches queue state, file overrides, rename, pending publish, final-library promotion, FFmpeg, subtitles, audio, or source/scratch/output movement.

## Open Questions

- Should Network lifecycle controls be blocked locally for all network commands, or only for same role/action route keys?
- Should `apiPost` gain a global default timeout, or should each route explicitly declare timeout/progress behavior from the command contract?
- Should optional refresh failures become panel-level banners immediately, or only after N consecutive failures to avoid transient noise?
- Should preview-only command results, such as Sample Validation preview and schedule preview, always enter command history?
- Should Library profile preview/save status be a wrapper around Settings patch status or move to first-class backend result rendering?

## Appendix

### Source Evidence Highlights

- `apiClient.js`: GET defaults to 30000 ms timeout; POST defaults to no timeout unless a caller passes `timeoutMs`.
- `app.js`: `refreshAll` has in-flight/queued behavior; `refreshAllNow` uses `Promise.allSettled` and marks only snapshot as required.
- `app/refresh.js`: refresh buttons use disabled and aria-busy states; refresh-health summarizes failures.
- `launchView.js` and `launch/commandButtons.js`: launch/control/browse flows use `launchCommandInFlight`, `controlCommandInFlight`, and `pipelineFileBrowseInFlight`.
- `renameView.js`: rename browse, preview, and apply use separate in-flight flags and a combined command-busy disable path.
- `settingsView.js`: settings commands use `settingsCommandInFlight`, disabled command buttons, stale preview request IDs, and command history.
- `queue/fileOverrides.drawer.api.js` and `.series.js`: file override save/clear/series flows use `foCommandInFlight`, disabled buttons, and preview fingerprints.
- `completed/promotionCommands.js`: final-library promotion uses `commandInFlight` and disables promote/pause/resume.
- `pendingPublishView.recovery.js`: recovery-plan dry runs use `pendingRecoveryPlanInFlight` and disabled buttons.
- `diagnosticsView.js`: diagnostics open and Tdarr matrix actions use explicit busy guards.
- `maintenanceView.js` and `metricsView.js`: long-running utility commands use in-flight flags and disabled controls.
- `networkView.js`: lifecycle/join/discovery/test functions set status and call routes, but no local in-flight flag or busy disable was found in the targeted scan.
- `src/mediapipeline/core/api/commands.py`: canonical command route registry includes all WebView POST routes audited here.
- `src/mediapipeline/desktop/api/handler.py`: strict JSON response handling records command payloads and route exceptions into the command journal.
- `src/mediapipeline/desktop/api/command_journal.py`: command journal is bounded, locked, persisted to JSON, and mirrored to SQLite when configured.
- `src/mediapipeline/desktop/api/command_journal_policy.py`: journal entries redact sensitive fields such as tokens, secrets, passwords, credentials, and join blobs.

### Audit Limitations

- Static/source audit only; no live WebView browser session, no real Local API server run, and no real media workflows were executed.
- The repository worktree was already heavily dirty before this report, so line-level blame and generated summary freshness were treated cautiously.
- Backend duplicate/precondition behavior was inferred from route contracts and command handlers where read; this report focuses on perceived UI responsiveness, not backend safety proof.
- No generated summaries were refreshed because this report-only task did not edit source files and the worktree contains substantial pre-existing generated-summary churn.
