# V5 UI Implementation — Stage 12 (Claude)

**Owner:** Claude  
**Depends on:** Stages 1–11 verified green.  
**Design authority:** `Docs/DesktopApp/docs/V5_UI_DESIGN_REFERENCE.md`  
**Validation:** `DesktopApp/Runtime/Python/python.exe -m pytest tests/ --tb=line -q` — must report 1183 passed 0 failed after every task.

---

## Goal

Replace the Dashboard (`data-page-panel="home"`) with a minimal daily-driver control surface. The operator should be able to do everything they need for a routine session without leaving this page. Advanced evidence panels move behind the existing Advanced gate.

---

## Design constraints

1. **Evidence before action.** Status strip and queue snapshot appear above the action buttons.
2. **One screen, five panels.** Every daily-driver task is reachable without scrolling (status strip, run controls, queue snapshot, quick actions, recently completed).
3. **Advanced gate for everything else.** The nine existing evidence/diagnostic panels drop below the five daily-driver panels, wrapped in `data-advanced`.
4. **No navigation on Start.** The guarded start stays on the dashboard — no page jump to Launch.

---

## Architecture notes (from codebase audit)

### Hard Kill
`kill_related_pipeline_processes(resolved)` in `service_process_kill.py` (line 129) discovers and kills running pipeline processes via psutil name-matching. It requires only `resolved` — no `proc` handle. The service wrapper is `self.service.kill_related_pipeline_processes(resolved)` (line 245 of `service_processes.py`). This works in both Tkinter and standalone-backend modes.

### Guarded Start
`pipelineLaunchPreflightLines(request)` in `launchView.js` (line 3694) builds a preflight summary from already-cached settings/readiness data. It is currently scoped inside the IIFE. It needs one new export: `window.pipelineLaunchPreflightLines = pipelineLaunchPreflightLines`. The dashboard start uses defaults `{ mode: "once", sleep_seconds: 30, show_config: false, show_console: false, schedule_override: "" }` and posts to `/api/pipeline/start`.

### Schedule Toggle
`lastSchedule` in `scheduleView.js` (line 2) holds the last-loaded schedule payload. The payload includes `enabled` (boolean) and `grid` (dict). The toggle re-POSTs to `/api/schedule/save` with `{ enabled: !lastSchedule.enabled, grid: lastSchedule.grid || {}, confirm_save: true }`. No backend change needed — the backend already reads `grid` and `enabled` independently (line 125 of `facade_schedule.py`).

### Pending Count
The pending publish payload (`/api/pending-publish`) has a `count` field and `rows` array. Pending count is `payload.count ?? payload.rows?.length ?? 0`.

### Queue Snapshot
The queue payload already populates a `queue-summary` pre element on the Queue page. The dashboard reuses the same backend text by calling `setText("home-queue-snapshot", queueSummaryLines(queue))` — or a short equivalent. See `queueView.js` for the existing `queue-summary` renderer.

### Recently Completed
The completed payload has a `rows` array of objects with `name`, `route`, and `completed_at` (or `finished` / `at`) fields. Last 5 rows are sliced and rendered into a compact table.

---

## Task 0 — Backend: Hard Kill action

**Files:** `application/facade_process_control_policy.py`, `application/facade_process_control.py`

### 0A — Policy update

**File:** `application/facade_process_control_policy.py`

```python
# Before
PIPELINE_CONTROL_ACTIONS = frozenset({"pause", "stop", "rescan"})
PIPELINE_CONTROL_ACTION_ERROR = "Action must be pause, stop, or rescan."

# After
PIPELINE_CONTROL_ACTIONS = frozenset({"pause", "stop", "rescan", "kill"})
PIPELINE_CONTROL_ACTION_ERROR = "Action must be pause, stop, rescan, or kill."
```

### 0B — Facade handler

**File:** `application/facade_process_control.py`

Add an `elif normalized == "kill":` branch immediately after the `elif normalized == "rescan":` block, before the outer `except`:

```python
elif normalized == "kill":
    method = getattr(self.service, "kill_related_pipeline_processes", None)
    if not callable(method):
        raise RuntimeError("Kill control service is not available.")
    messages = method(resolved)
    message = (
        "; ".join(messages)
        if messages
        else "No active pipeline processes found to kill."
    )
    flag_path = None
```

The existing `return CommandResult(...)` at lines 69–76 already handles `flag_path = None` cleanly via `pipeline_control_success_data(normalized, flag_path)` which calls `str(flag_path or "")`.

**Verification:**
```powershell
# Policy file
Select-String -Path "DesktopApp\mediapipeline_desktop_app\application\facade_process_control_policy.py" `
  -Pattern '"kill"'
# Must return 1 result

# Facade file
Select-String -Path "DesktopApp\mediapipeline_desktop_app\application\facade_process_control.py" `
  -Pattern 'kill_related_pipeline_processes'
# Must return 1 result
```

**Test impact:** Existing tests cover `pause`, `stop`, and `rescan` only. Adding `kill` is additive — 1183 passed unchanged.

---

## Task 1 — CSS: New home-page components

**File:** `assets/styles.css`

Add two rules. Insert immediately after the `.empty-state::before` block.

### 1A — Start check result block

```css
.home-start-result {
  background: var(--grey-800);
  border: 1px solid var(--grey-700);
  border-radius: var(--radius-sm);
  padding: var(--space-3) var(--space-4);
  font-size: var(--text-sm);
  color: var(--grey-200);
  white-space: pre-wrap;
  word-break: break-word;
  margin-top: var(--space-3);
}

.home-start-result[data-check-state="pass"] {
  border-color: var(--green-600);
}

.home-start-result[data-check-state="fail"] {
  border-color: var(--red-600);
}
```

### 1B — Compact home table

```css
.home-compact-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--text-sm);
}

.home-compact-table th {
  text-align: left;
  color: var(--grey-400);
  font-weight: 400;
  padding: var(--space-1) var(--space-2);
  border-bottom: 1px solid var(--grey-700);
}

.home-compact-table td {
  padding: var(--space-1) var(--space-2);
  color: var(--grey-200);
  border-bottom: 1px solid var(--grey-800);
  max-width: 28ch;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
```

**Verification:**
```powershell
(Select-String -Path "DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\styles.css" `
  -Pattern '\.home-start-result|\.home-compact-table').Count
# Must be >= 2
```

---

## Task 2 — HTML: Rebuild the home page

**File:** `ui_web/static/index.html`

Replace the entire `<section class="page is-visible" data-page-panel="home">` block (lines 51–716) with the structure below.

### Rules
- Keep all existing DOM IDs that tests reference. IDs that move from prominent positions to the advanced section still exist — tests find them regardless of position.
- New IDs introduced: `home-pending-count`, `home-network-role`, `home-pipeline-start-button`, `home-start-check-result`, `home-confirm-start-button`, `home-queue-snapshot`, `home-schedule-toggle-button`, `home-schedule-toggle-status`, `home-drain-button`, `home-recent-completed-tbody`.
- `processed-count` and `failed-count` move into the advanced section (they are still in the DOM for any test that checks them).

### New structure

```html
      <section class="page is-visible" data-page-panel="home">

        <!-- ═══ DAILY DRIVER: STATUS STRIP ═══ -->
        <div class="metric-grid">
          <section class="metric">
            <span class="metric-label">Pipeline</span>
            <strong id="pipeline-state">...</strong>
          </section>
          <section class="metric">
            <span class="metric-label">Queue</span>
            <strong id="queue-count">0 / 0</strong>
          </section>
          <section class="metric">
            <span class="metric-label">Pending</span>
            <strong id="home-pending-count">0</strong>
          </section>
          <section class="metric">
            <span class="metric-label">Role</span>
            <strong id="home-network-role">standalone</strong>
          </section>
        </div>

        <!-- ═══ DAILY DRIVER: QUEUE SNAPSHOT ═══ -->
        <section class="panel" data-panel-type="evidence">
          <div class="panel-heading">
            <h2>Queue Snapshot</h2>
            <strong id="home-queue-snapshot-status">No data</strong>
          </div>
          <pre id="home-queue-snapshot" class="text-block compact-text-block">No queue data loaded.</pre>
          <div class="action-row action-row-left">
            <button type="button" class="secondary-button" data-cross-page-target="queue">Full Queue →</button>
          </div>
        </section>

        <!-- ═══ DAILY DRIVER: RUN CONTROLS ═══ -->
        <section class="panel" data-panel-type="interactive">
          <div class="panel-heading">
            <h2>Run Controls</h2>
            <strong id="control-readiness-status">Not loaded</strong>
          </div>
          <div class="action-row action-row-left">
            <button type="button" id="home-pipeline-start-button" class="primary-button">Start Pipeline</button>
            <button type="button" class="secondary-button" data-control-action="pause">Pause / Resume</button>
            <button type="button" class="danger-button" data-control-action="stop" data-confirm-command="true">Stop After Current</button>
            <button type="button" class="danger-button" data-control-action="kill" data-confirm-command="true">Hard Kill</button>
          </div>
          <pre id="home-start-check-result" class="home-start-result" style="display:none"></pre>
          <div class="action-row action-row-left" id="home-confirm-start-row" style="display:none">
            <button type="button" id="home-confirm-start-button" class="primary-button">Confirm Start</button>
            <button type="button" id="home-cancel-start-button" class="secondary-button">Cancel</button>
          </div>
          <p id="control-status" class="note"></p>
          <pre id="control-history" class="text-block compact-text-block">No pipeline control command history loaded.</pre>
          <pre id="status-summary" class="text-block compact-text-block" style="display:none">No status loaded.</pre>
          <pre id="control-readiness" class="text-block compact-text-block" style="display:none">No pipeline control readiness loaded.</pre>
        </section>

        <!-- ═══ DAILY DRIVER: QUICK ACTIONS ═══ -->
        <section class="panel" data-panel-type="interactive">
          <div class="panel-heading">
            <h2>Quick Actions</h2>
            <strong id="home-quick-actions-status">Ready</strong>
          </div>
          <div class="action-row action-row-left">
            <button type="button" id="home-drain-button" class="danger-button" data-confirm-command="true">Publish Parked Outputs</button>
            <button type="button" id="home-schedule-toggle-button" class="secondary-button">Enable Schedule</button>
            <button type="button" class="secondary-button" data-cross-page-target="pending">Review Pending →</button>
          </div>
          <p id="home-schedule-toggle-status" class="note">Schedule enforcement: loading…</p>
        </section>

        <!-- ═══ DAILY DRIVER: RECENTLY COMPLETED ═══ -->
        <section class="panel" data-panel-type="evidence">
          <div class="panel-heading">
            <h2>Recently Completed</h2>
            <strong id="home-recent-completed-status">No data</strong>
          </div>
          <div class="table-wrap">
            <table class="home-compact-table">
              <thead>
                <tr>
                  <th scope="col">File</th>
                  <th scope="col">Route</th>
                  <th scope="col">Finished</th>
                </tr>
              </thead>
              <tbody id="home-recent-completed-tbody">
                <tr><td colspan="3">No completed files loaded.</td></tr>
              </tbody>
            </table>
          <div class="empty-state" data-empty-state="hidden" style="display:none">
            <span class="empty-state-label">No data loaded</span>
            <span class="empty-state-hint">Refresh to load data from the backend.</span>
          </div>
          </div>
          <div class="action-row action-row-left">
            <button type="button" class="secondary-button" data-cross-page-target="completed">Full Completed →</button>
          </div>
        </section>

        <!-- ═══ ADVANCED GATE: existing panels below ═══ -->
        <div data-advanced>

          <!-- Metric detail (kept for any test references) -->
          <div class="metric-grid">
            <section class="metric">
              <span class="metric-label">Processed</span>
              <strong id="processed-count">0</strong>
            </section>
            <section class="metric">
              <span class="metric-label">Failed</span>
              <strong id="failed-count">0</strong>
            </section>
          </div>

          <section class="panel" data-panel-type="evidence">
            <div class="panel-heading">
              <h2>System Readiness</h2>
              <strong id="home-readiness-status">Checking</strong>
            </div>
            <pre id="home-readiness-summary" class="text-block compact-text-block">No backend readiness data loaded yet.</pre>
          </section>

          <section class="panel" data-panel-type="evidence">
            <div class="panel-heading">
              <h2>Readiness Checklist</h2>
              <strong id="daily-driver-status">Not evaluated</strong>
            </div>
            <pre id="daily-driver-summary" class="text-block compact-text-block">No daily-driver readiness checklist loaded.</pre>
            <div class="table-wrap detail-table-wrap">
              <table>
                <thead>
                  <tr>
                    <th scope="col">Area</th>
                    <th scope="col">Status</th>
                    <th scope="col">Evidence</th>
                    <th scope="col">Next Step</th>
                  </tr>
                </thead>
                <tbody id="daily-driver-rows">
                  <tr><td colspan="4">No daily-driver readiness rows loaded.</td></tr>
                </tbody>
              </table>
            <div class="empty-state" data-empty-state="hidden" style="display:none">
              <span class="empty-state-label">No data loaded</span>
              <span class="empty-state-hint">Refresh to load data from the backend.</span>
            </div>
            </div>
            <p id="daily-driver-legend" class="note table-legend">Daily-driver checklist rows are read-only and do not launch, repair, drain, save, rename, or mutate files.</p>
          </section>

          <section class="panel" data-panel-type="evidence">
            <div class="panel-heading">
              <h2>Current Run</h2>
              <strong id="home-active-work-status">Checking</strong>
            </div>
            <pre id="home-active-work-summary" class="text-block compact-text-block">No active-work data loaded yet.</pre>
          </section>

          <section class="panel" data-panel-type="evidence">
            <div class="panel-heading">
              <h2>Run Progress</h2>
              <strong id="progress-detail-status">No details</strong>
            </div>
            <div class="table-wrap detail-table-wrap">
              <table>
                <thead>
                  <tr>
                    <th scope="col">Field</th>
                    <th scope="col">Value</th>
                  </tr>
                </thead>
                <tbody id="progress-detail-rows">
                  <tr><td colspan="2">No progress details loaded.</td></tr>
                </tbody>
              </table>
            <div class="empty-state" data-empty-state="hidden" style="display:none">
              <span class="empty-state-label">No data loaded</span>
              <span class="empty-state-hint">Refresh to load data from the backend.</span>
            </div>
            </div>
            <div class="panel-heading panel-subheading">
              <h3>Progress Proof</h3>
              <strong id="progress-evidence-status">Not loaded</strong>
            </div>
            <pre id="progress-evidence-summary" class="text-block compact-text-block">No progress evidence loaded.</pre>
            <div class="table-wrap detail-table-wrap">
              <table>
                <thead>
                  <tr>
                    <th scope="col">Checkpoint</th>
                    <th scope="col">Posture</th>
                    <th scope="col">Evidence</th>
                    <th scope="col">Safe Next Step</th>
                  </tr>
                </thead>
                <tbody id="progress-evidence-rows">
                  <tr><td colspan="4">No progress evidence rows loaded.</td></tr>
                </tbody>
              </table>
            <div class="empty-state" data-empty-state="hidden" style="display:none">
              <span class="empty-state-label">No data loaded</span>
              <span class="empty-state-hint">Refresh to load data from the backend.</span>
            </div>
            </div>
            <p id="progress-evidence-legend" class="note table-legend">Progress evidence rows: no selectable rows.</p>
            <pre id="progress-evidence-detail" class="text-block compact-text-block">No progress evidence row selected.</pre>
          </section>

          <section class="panel" data-panel-type="evidence">
            <div class="panel-heading">
              <h2>Settings Health</h2>
              <strong id="home-settings-trust-status">Not loaded</strong>
            </div>
            <pre id="home-settings-trust-summary" class="text-block compact-text-block">No saved settings trust summary loaded.</pre>
          </section>

          <section class="panel" data-panel-type="evidence">
            <div class="panel-heading">
              <h2>Tool Status</h2>
              <strong id="home-external-dependencies-status">Not loaded</strong>
            </div>
            <pre id="home-external-dependencies-summary" class="text-block compact-text-block">No external dependency evidence loaded.</pre>
          </section>

          <section class="panel" data-panel-type="interactive">
            <div class="panel-heading">
              <h2>Runtime Files</h2>
              <strong id="home-runtime-open-status">Idle</strong>
            </div>
            <div class="action-row action-row-left wrap-actions">
              <button type="button" class="secondary-button" data-open-diagnostics="active_jobs">Active Jobs</button>
              <button type="button" class="secondary-button" data-open-diagnostics="run_logs">Run Logs</button>
              <button type="button" class="secondary-button" data-open-diagnostics="last_stderr_log">Last Stderr</button>
              <button type="button" class="secondary-button" data-open-diagnostics="queue_snapshot">Queue Snapshot</button>
              <button type="button" class="secondary-button" data-open-diagnostics="pending_publish">Pending Publish</button>
              <button type="button" class="secondary-button" data-open-diagnostics="completed_manifest">Completed Manifest</button>
            </div>
            <p class="note">Open requests use the backend diagnostics allowlist. The WebView never sends arbitrary filesystem paths.</p>
          </section>

          <section class="panel" data-panel-type="evidence">
            <div class="panel-heading">
              <h2>Recent Events</h2>
              <strong id="pipeline-events-status">No events</strong>
            </div>
            <div class="table-wrap detail-table-wrap">
              <table>
                <thead>
                  <tr>
                    <th scope="col">Time</th>
                    <th scope="col">Type</th>
                    <th scope="col">Details</th>
                  </tr>
                </thead>
                <tbody id="pipeline-event-rows">
                  <tr><td colspan="3">No pipeline events loaded.</td></tr>
                </tbody>
              </table>
            <div class="empty-state" data-empty-state="hidden" style="display:none">
              <span class="empty-state-label">No data loaded</span>
              <span class="empty-state-hint">Refresh to load data from the backend.</span>
            </div>
            </div>
          </section>

          <section class="panel" data-panel-type="evidence">
            <div class="panel-heading">
              <h2>Recent Commands</h2>
              <strong id="command-status">No commands</strong>
            </div>
            <pre id="command-summary" class="text-block compact-text-block">No command result summary loaded.</pre>
            <div class="table-wrap command-table-wrap">
              <table>
                <thead>
                  <tr>
                    <th scope="col">Time</th>
                    <th scope="col">Command</th>
                    <th scope="col">Owner</th>
                    <th scope="col">Issue</th>
                    <th scope="col">Result</th>
                    <th scope="col">Message</th>
                  </tr>
                </thead>
                <tbody id="command-rows">
                  <tr><td colspan="6">No command results yet.</td></tr>
                </tbody>
              </table>
            <div class="empty-state" data-empty-state="hidden" style="display:none">
              <span class="empty-state-label">No data loaded</span>
              <span class="empty-state-hint">Refresh to load data from the backend.</span>
            </div>
            </div>
            <p id="command-table-legend" class="note table-legend">Command result rows: no selectable rows.</p>
            <pre id="command-detail" class="text-block compact-text-block">No command row selected.</pre>
            <div id="command-diagnostics-actions" class="action-row action-row-left wrap-actions"></div>
          </section>

          <section class="panel" data-panel-type="interactive">
            <div class="panel-heading">
              <h2>Pipeline Overview</h2>
              <strong id="cross-page-context-status">Not loaded</strong>
            </div>
            <pre id="cross-page-context-summary" class="text-block compact-text-block">No queue/completed/pending context loaded yet.</pre>
            <div data-advanced>
              <div class="panel-heading panel-subheading">
                <h3>Conflict Summary</h3>
                <strong id="cross-page-conflict-status">Not loaded</strong>
              </div>
              <div class="table-wrap detail-table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th scope="col">Signal</th>
                      <th scope="col">Scope</th>
                      <th scope="col">Evidence</th>
                      <th scope="col">Next Action</th>
                    </tr>
                  </thead>
                  <tbody id="cross-page-conflict-rows">
                    <tr><td colspan="4">No cross-page conflict rows loaded.</td></tr>
                  </tbody>
                </table>
              <div class="empty-state" data-empty-state="hidden" style="display:none">
                <span class="empty-state-label">No data loaded</span>
                <span class="empty-state-hint">Refresh to load data from the backend.</span>
              </div>
              </div>
              <p id="cross-page-conflict-legend" class="note table-legend">Cross-page conflict rows: no selectable rows.</p>
              <div class="panel-heading panel-subheading">
                <h3>Evidence Correlation</h3>
                <strong id="cross-page-sample-status">Not loaded</strong>
              </div>
              <div class="table-wrap detail-table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th scope="col">Sample</th>
                      <th scope="col">Proof Strength</th>
                      <th scope="col">Evidence</th>
                      <th scope="col">Next Step</th>
                    </tr>
                  </thead>
                  <tbody id="cross-page-sample-rows">
                    <tr><td colspan="4">No sample evidence correlation rows loaded.</td></tr>
                  </tbody>
                </table>
              <div class="empty-state" data-empty-state="hidden" style="display:none">
                <span class="empty-state-label">No data loaded</span>
                <span class="empty-state-hint">Refresh to load data from the backend.</span>
              </div>
              </div>
              <p id="cross-page-sample-legend" class="note table-legend">Sample evidence rows: no selectable rows.</p>
              <div class="panel-heading panel-subheading">
                <h3>Validation Template</h3>
                <strong id="cross-page-validation-template-status">Not loaded</strong>
              </div>
              <pre id="cross-page-validation-template" class="text-block compact-text-block">No sample validation template loaded.</pre>
              <div class="panel-heading panel-subheading">
                <h3>Validation Worksheet</h3>
                <strong id="cross-page-real-media-status">Not loaded</strong>
              </div>
              <pre id="cross-page-real-media-summary" class="text-block compact-text-block">No real-media validation worksheet loaded.</pre>
              <div class="table-wrap detail-table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th scope="col">Checkpoint</th>
                      <th scope="col">Posture</th>
                      <th scope="col">Evidence</th>
                      <th scope="col">Operator Next Check</th>
                    </tr>
                  </thead>
                  <tbody id="cross-page-real-media-rows">
                    <tr><td colspan="4">No real-media validation worksheet rows loaded.</td></tr>
                  </tbody>
                </table>
              <div class="empty-state" data-empty-state="hidden" style="display:none">
                <span class="empty-state-label">No data loaded</span>
                <span class="empty-state-hint">Refresh to load data from the backend.</span>
              </div>
              </div>
              <p id="cross-page-real-media-legend" class="note table-legend">Real-media validation worksheet rows: no selectable rows.</p>
              <pre id="cross-page-real-media-detail" class="text-block compact-text-block">No real-media validation worksheet row selected.</pre>
              <div class="panel-heading panel-subheading">
                <h3>Validation Record</h3>
                <strong id="sample-validation-status">Not loaded</strong>
              </div>
              <pre id="sample-validation-summary" class="text-block compact-text-block">No backend-owned sample validation record is loaded.</pre>
              <div class="panel-heading panel-subheading">
                <h3>Evidence Handoff</h3>
                <strong id="sample-validation-completed-packet-status">Not loaded</strong>
              </div>
              <pre id="sample-validation-completed-packet-summary" class="text-block compact-text-block">No selected Completed evidence packet handoff loaded.</pre>
              <div class="table-wrap detail-table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th scope="col">Checkpoint</th>
                      <th scope="col">Posture</th>
                      <th scope="col">Evidence</th>
                      <th scope="col">Operator Action</th>
                    </tr>
                  </thead>
                  <tbody id="sample-validation-completed-packet-rows">
                    <tr><td colspan="4">No selected Completed evidence packet rows loaded.</td></tr>
                  </tbody>
                </table>
              <div class="empty-state" data-empty-state="hidden" style="display:none">
                <span class="empty-state-label">No data loaded</span>
                <span class="empty-state-hint">Refresh to load data from the backend.</span>
              </div>
              </div>
              <p id="sample-validation-completed-packet-legend" class="note table-legend">Completed evidence handoff rows are read-only and do not append validation records, accept output, rerun, drain, publish, repair, save settings, rename, rewrite manifests, or touch media.</p>
              <pre id="sample-validation-completed-packet-detail" class="text-block compact-text-block">No selected Completed evidence packet row selected.</pre>
              <pre id="sample-validation-completed-packet-markdown" class="text-block compact-text-block">No copyable Completed evidence packet loaded.</pre>
              <div class="panel-heading panel-subheading">
                <h3>Evidence Gaps</h3>
                <strong id="sample-validation-gap-status">Not loaded</strong>
              </div>
              <pre id="sample-validation-gap-summary" class="text-block compact-text-block">No real-media evidence-gap summary is loaded.</pre>
              <div class="table-wrap detail-table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th scope="col">Checkpoint</th>
                      <th scope="col">Status</th>
                      <th scope="col">Owner</th>
                      <th scope="col">Required</th>
                      <th scope="col">Missing Evidence</th>
                    </tr>
                  </thead>
                  <tbody id="sample-validation-gap-rows">
                    <tr><td colspan="5">No real-media evidence-gap rows loaded.</td></tr>
                  </tbody>
                </table>
              <div class="empty-state" data-empty-state="hidden" style="display:none">
                <span class="empty-state-label">No data loaded</span>
                <span class="empty-state-hint">Refresh to load data from the backend.</span>
              </div>
              </div>
              <p id="sample-validation-gap-legend" class="note table-legend">Real-media evidence-gap rows are read-only guidance.</p>
              <pre id="sample-validation-gap-detail" class="text-block compact-text-block">No real-media evidence-gap row selected.</pre>
              <div class="panel-heading panel-subheading">
                <h3>Pilot Runbook</h3>
                <strong id="sample-validation-runbook-status">Not loaded</strong>
              </div>
              <pre id="sample-validation-runbook-summary" class="text-block compact-text-block">No real-media pilot runbook is loaded.</pre>
              <div class="table-wrap detail-table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th scope="col">Step</th>
                      <th scope="col">Status</th>
                      <th scope="col">Owner</th>
                      <th scope="col">Required</th>
                      <th scope="col">Safe Next Action</th>
                    </tr>
                  </thead>
                  <tbody id="sample-validation-runbook-rows">
                    <tr><td colspan="5">No real-media pilot runbook rows loaded.</td></tr>
                  </tbody>
                </table>
              <div class="empty-state" data-empty-state="hidden" style="display:none">
                <span class="empty-state-label">No data loaded</span>
                <span class="empty-state-hint">Refresh to load data from the backend.</span>
              </div>
              </div>
              <p id="sample-validation-runbook-legend" class="note table-legend">Real-media pilot runbook rows are read-only guidance.</p>
              <pre id="sample-validation-runbook-detail" class="text-block compact-text-block">No real-media pilot runbook row selected.</pre>
              <pre id="sample-validation-runbook-markdown" class="text-block compact-text-block">No copyable real-media pilot runbook Markdown loaded.</pre>
              <div class="panel-heading panel-subheading">
                <h3>Cutover Gate</h3>
                <strong id="sample-validation-cutover-status">Not loaded</strong>
              </div>
              <pre id="sample-validation-cutover-summary" class="text-block compact-text-block">No WebView cutover gate evidence loaded.</pre>
              <div class="table-wrap detail-table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th scope="col">Checkpoint</th>
                      <th scope="col">Status</th>
                      <th scope="col">Required</th>
                      <th scope="col">Evidence</th>
                    </tr>
                  </thead>
                  <tbody id="sample-validation-cutover-rows">
                    <tr><td colspan="4">No WebView cutover gate rows loaded.</td></tr>
                  </tbody>
                </table>
              <div class="empty-state" data-empty-state="hidden" style="display:none">
                <span class="empty-state-label">No data loaded</span>
                <span class="empty-state-hint">Refresh to load data from the backend.</span>
              </div>
              </div>
              <p id="sample-validation-cutover-legend" class="note table-legend">WebView cutover gate rows are read-only evidence.</p>
              <pre id="sample-validation-cutover-detail" class="text-block compact-text-block">No WebView cutover gate row selected.</pre>
              <div class="panel-heading panel-subheading">
                <h3>Sample Guide</h3>
                <strong id="sample-validation-sample-set-status">Not loaded</strong>
              </div>
              <pre id="sample-validation-sample-set-summary" class="text-block compact-text-block">No representative real-media sample guidance loaded.</pre>
              <div class="table-wrap detail-table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th scope="col">Category</th>
                      <th scope="col">Status</th>
                      <th scope="col">Required</th>
                      <th scope="col">Evidence</th>
                    </tr>
                  </thead>
                  <tbody id="sample-validation-sample-set-rows">
                    <tr><td colspan="4">No representative sample-set rows loaded.</td></tr>
                  </tbody>
                </table>
              <div class="empty-state" data-empty-state="hidden" style="display:none">
                <span class="empty-state-label">No data loaded</span>
                <span class="empty-state-hint">Refresh to load data from the backend.</span>
              </div>
              </div>
              <p id="sample-validation-sample-set-legend" class="note table-legend">Representative sample-set rows are read-only guidance.</p>
              <pre id="sample-validation-sample-set-detail" class="text-block compact-text-block">No representative sample-set row selected.</pre>
              <div class="action-row action-row-left wrap-actions">
                <button type="button" id="sample-validation-use-sample-set-category-button" class="secondary-button">Use Selected Category</button>
              </div>
              <div class="panel-heading panel-subheading">
                <h3>Category Summary</h3>
                <strong id="sample-validation-category-summary-status">Not loaded</strong>
              </div>
              <pre id="sample-validation-category-summary" class="text-block compact-text-block">No pilot category validation summary loaded.</pre>
              <div class="table-wrap detail-table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th scope="col">Category</th>
                      <th scope="col">Posture</th>
                      <th scope="col">Current Evidence</th>
                      <th scope="col">Next Action</th>
                    </tr>
                  </thead>
                  <tbody id="sample-validation-category-summary-rows">
                    <tr><td colspan="4">No pilot category validation summary rows loaded.</td></tr>
                  </tbody>
                </table>
              <div class="empty-state" data-empty-state="hidden" style="display:none">
                <span class="empty-state-label">No data loaded</span>
                <span class="empty-state-hint">Refresh to load data from the backend.</span>
              </div>
              </div>
              <p id="sample-validation-category-summary-legend" class="note table-legend">Pilot category validation rows are read-only and cannot launch, append, or mutate media.</p>
              <pre id="sample-validation-category-summary-detail" class="text-block compact-text-block">No pilot category validation row selected.</pre>
              <div class="panel-heading panel-subheading">
                <h3>Sample Checklist</h3>
                <strong id="sample-validation-execution-status">Not loaded</strong>
              </div>
              <pre id="sample-validation-execution-summary" class="text-block compact-text-block">No backend-authored sample execution checklist is loaded.</pre>
              <div class="table-wrap detail-table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th scope="col">Phase</th>
                      <th scope="col">Check</th>
                      <th scope="col">Status</th>
                      <th scope="col">Owner</th>
                      <th scope="col">Required</th>
                    </tr>
                  </thead>
                  <tbody id="sample-validation-execution-rows">
                    <tr><td colspan="5">No sample execution checklist rows loaded.</td></tr>
                  </tbody>
                </table>
              <div class="empty-state" data-empty-state="hidden" style="display:none">
                <span class="empty-state-label">No data loaded</span>
                <span class="empty-state-hint">Refresh to load data from the backend.</span>
              </div>
              </div>
              <p id="sample-validation-execution-legend" class="note table-legend">Sample execution checklist rows are read-only guidance.</p>
              <pre id="sample-validation-execution-detail" class="text-block compact-text-block">No sample execution checklist row selected.</pre>
              <div class="panel-heading panel-subheading">
                <h3>Pilot Worksheets</h3>
                <strong id="sample-validation-worksheet-status">Not loaded</strong>
              </div>
              <pre id="sample-validation-worksheet-summary" class="text-block compact-text-block">No generated worksheet evidence loaded.</pre>
              <div class="table-wrap detail-table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th scope="col">Worksheet</th>
                      <th scope="col">Status</th>
                      <th scope="col">Samples</th>
                      <th scope="col">Packet Rows</th>
                      <th scope="col">Selected Match</th>
                    </tr>
                  </thead>
                  <tbody id="sample-validation-worksheet-rows">
                    <tr><td colspan="5">No generated pilot worksheet rows loaded.</td></tr>
                  </tbody>
                </table>
              <div class="empty-state" data-empty-state="hidden" style="display:none">
                <span class="empty-state-label">No data loaded</span>
                <span class="empty-state-hint">Refresh to load data from the backend.</span>
              </div>
              </div>
              <p id="sample-validation-worksheet-legend" class="note table-legend">Generated worksheet rows are read-only Markdown evidence.</p>
              <pre id="sample-validation-worksheet-detail" class="text-block compact-text-block">No generated worksheet row selected.</pre>
              <div class="form-grid">
                <label>
                  Operator decision
                  <select id="sample-validation-decision">
                    <option value="hold_review">Hold for review</option>
                    <option value="accepted">Accept Selected Sample</option>
                    <option value="rerun_backend">Rerun through backend</option>
                    <option value="fallback_tk">Fallback to Tk for this sample</option>
                  </select>
                </label>
                <label>
                  Pilot category
                  <select id="sample-validation-category">
                    <option value="">General / not categorized</option>
                    <option value="h264-remux-safe">H.264 remux / direct-play copy</option>
                    <option value="subtitle-srt-generation">Preferred-language subtitle to SRT</option>
                    <option value="audio-routing">Audio routing / default language</option>
                    <option value="encode-size-policy">Encode and size policy</option>
                    <option value="deferred-publish">Deferred publish / final placement</option>
                  </select>
                </label>
                <label class="full-field">
                  Operator notes
                  <textarea id="sample-validation-notes" rows="3" spellcheck="true" placeholder="Optional notes from Plex playback, subtitle/audio inspection, size review, or pending-publish verification."></textarea>
                </label>
              </div>
              <div class="option-panel">
                <div class="option-panel-heading">
                  <strong>Acceptance Checklist</strong>
                  <span id="sample-validation-check-status">Auto evidence plus manual checks</span>
                </div>
                <div class="option-grid option-grid-compact">
                  <label class="check-row"><input id="sample-validation-check-queue-route" type="checkbox" data-sample-validation-check="queue_route_checked"> Queue route / remux decision</label>
                  <label class="check-row"><input id="sample-validation-check-completed-output" type="checkbox" data-sample-validation-check="completed_output_checked"> Completed output exists</label>
                  <label class="check-row"><input id="sample-validation-check-sidecar-manifest" type="checkbox" data-sample-validation-check="sidecar_manifest_checked"> Sidecar / manifest checked</label>
                  <label class="check-row"><input id="sample-validation-check-size-growth" type="checkbox" data-sample-validation-check="size_growth_checked"> Size growth acceptable</label>
                  <label class="check-row"><input id="sample-validation-check-diagnostics" type="checkbox" data-sample-validation-check="diagnostics_checked"> Diagnostics / run logs checked</label>
                  <label class="check-row"><input id="sample-validation-check-subtitle" type="checkbox" data-sample-validation-check="subtitle_checked"> Subtitle behavior checked</label>
                  <label class="check-row"><input id="sample-validation-check-audio" type="checkbox" data-sample-validation-check="audio_checked"> Audio behavior checked</label>
                  <label class="check-row"><input id="sample-validation-check-pending-publish" type="checkbox" data-sample-validation-check="pending_publish_checked"> Pending Publish checked or not applicable</label>
                </div>
                <div class="action-row action-row-left wrap-actions">
                  <button type="button" id="sample-validation-clear-checks-button" class="secondary-button">Clear Manual Checks</button>
                </div>
                <p class="note">Loaded Queue, Completed, Pending Publish, and Diagnostics evidence can pre-check matching items. Manual checks only affect the evidence note sent to Preview/Append; they do not accept output, launch work, or mutate media.</p>
              </div>
              <div class="panel-heading panel-subheading">
                <h3>Acceptance Gate</h3>
                <strong id="sample-validation-acceptance-gate-status">Not loaded</strong>
              </div>
              <pre id="sample-validation-acceptance-gate-summary" class="text-block compact-text-block">No sample-validation acceptance gate loaded.</pre>
              <div class="table-wrap detail-table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th scope="col">Gate</th>
                      <th scope="col">Status</th>
                      <th scope="col">Evidence</th>
                      <th scope="col">Safe Next Action</th>
                    </tr>
                  </thead>
                  <tbody id="sample-validation-acceptance-gate-rows">
                    <tr><td colspan="4">No sample-validation acceptance gate rows loaded.</td></tr>
                  </tbody>
                </table>
              <div class="empty-state" data-empty-state="hidden" style="display:none">
                <span class="empty-state-label">No data loaded</span>
                <span class="empty-state-hint">Refresh to load data from the backend.</span>
              </div>
              </div>
              <p id="sample-validation-acceptance-gate-legend" class="note table-legend">Acceptance gate rows are read-only guidance and do not append validation records or mutate media.</p>
              <pre id="sample-validation-acceptance-gate-detail" class="text-block compact-text-block">No sample-validation acceptance gate row selected.</pre>
              <div class="panel-heading panel-subheading">
                <h3>Accepted Records</h3>
                <strong id="sample-validation-record-review-status">Not loaded</strong>
              </div>
              <pre id="sample-validation-record-review-summary" class="text-block compact-text-block">No accepted sample-validation record proof review loaded.</pre>
              <div class="table-wrap detail-table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th scope="col">Proof Area</th>
                      <th scope="col">Status</th>
                      <th scope="col">Evidence</th>
                      <th scope="col">Safe Next Action</th>
                    </tr>
                  </thead>
                  <tbody id="sample-validation-record-review-rows">
                    <tr><td colspan="4">No accepted sample-validation record proof rows loaded.</td></tr>
                  </tbody>
                </table>
              <div class="empty-state" data-empty-state="hidden" style="display:none">
                <span class="empty-state-label">No data loaded</span>
                <span class="empty-state-hint">Refresh to load data from the backend.</span>
              </div>
              </div>
              <p id="sample-validation-record-review-legend" class="note table-legend">Accepted record proof rows are read-only and cannot accept output or mutate media.</p>
              <pre id="sample-validation-record-review-detail" class="text-block compact-text-block">No accepted sample-validation record proof row selected.</pre>
              <div class="action-row action-row-left wrap-actions">
                <button type="button" id="sample-validation-preview-button" class="secondary-button">Preview Record</button>
                <button type="button" id="sample-validation-append-button" class="secondary-button">Append Validation Record</button>
                <button type="button" class="secondary-button" data-open-diagnostics="sample_validation_log">Open Validation Log</button>
                <button type="button" class="secondary-button" data-cross-page-target="diagnostics">Review Diagnostics</button>
              </div>
              <pre id="sample-validation-result" class="text-block compact-text-block">Preview or append a backend-owned validation record after selecting a real sample row.</pre>
              <div class="table-wrap detail-table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th scope="col">Created</th>
                      <th scope="col">Decision</th>
                      <th scope="col">Category</th>
                      <th scope="col">Current Evidence</th>
                      <th scope="col">Gap</th>
                      <th scope="col">Sample</th>
                      <th scope="col">Proof</th>
                    </tr>
                  </thead>
                  <tbody id="sample-validation-records">
                    <tr><td colspan="7">No sample validation records loaded.</td></tr>
                  </tbody>
                </table>
              <div class="empty-state" data-empty-state="hidden" style="display:none">
                <span class="empty-state-label">No data loaded</span>
                <span class="empty-state-hint">Refresh to load data from the backend.</span>
              </div>
              </div>
              <p id="sample-validation-legend" class="note table-legend">Sample validation records are operator evidence only.</p>
              <pre id="sample-validation-detail" class="text-block compact-text-block">No sample validation record selected.</pre>
              <div class="action-row action-row-left wrap-actions">
                <button type="button" class="secondary-button" data-cross-page-target="queue">Review Queue</button>
                <button type="button" class="secondary-button" data-cross-page-target="completed">Review Completed</button>
                <button type="button" class="secondary-button" data-cross-page-target="pending">Review Pending Publish</button>
                <button type="button" class="secondary-button" data-cross-page-target="diagnostics">Review Diagnostics</button>
              </div>
              <p class="note">This panel correlates already-loaded backend payloads only. It does not start, repair, rerun, drain, delete, or rewrite files.</p>
            </div><!-- end inner data-advanced (SV sub-panels) -->
          </section>

        </div><!-- end outer data-advanced (9 panels) -->

      </section>
```

**Verification:**
```powershell
# New daily-driver IDs present
Select-String -Path "DesktopApp\mediapipeline_desktop_app\ui_web\static\index.html" `
  -Pattern 'home-pending-count|home-network-role|home-pipeline-start-button|home-confirm-start-button|home-drain-button|home-schedule-toggle-button|home-recent-completed-tbody'
# Must return 7 results

# Old IDs still in DOM (test compatibility)
Select-String -Path "DesktopApp\mediapipeline_desktop_app\ui_web\static\index.html" `
  -Pattern 'id="processed-count"|id="failed-count"|id="daily-driver-rows"|id="progress-detail-rows"'
# Must return 4 results
```

---

## Task 3 — JS: launchView.js updates

**File:** `assets/launchView.js`

### 3A — Add kill to control maps

```javascript
// controlActionLabels (line 10) — add kill entry:
const controlActionLabels = {
  pause: "Pause / Resume",
  rescan: "Rescan",
  stop: "Stop After Current",
  kill: "Hard Kill",
};

// controlConfirmMessages (line 16) — add kill entry:
const controlConfirmMessages = {
  rescan: "Request a queue rescan flag for the running pipeline?",
  stop: "Request Stop After Current for the running pipeline?",
  kill: "Force-kill the active pipeline process tree immediately? The current file will be aborted. This cannot be undone.",
};
```

### 3B — Add home button IDs to the launch busy list

```javascript
// launchCommandButtonIds (line 21) — add home-drain-button:
const launchCommandButtonIds = [
  "pipeline-start-button",
  "pending-drain-button",
  "audit-start-button",
  "rerun-start-button",
  "home-drain-button",
  "home-pipeline-start-button",
  "home-confirm-start-button",
];
```

### 3C — Export preflight helper

Add at the bottom of `launchView.js`, alongside the other `window.*` exports:

```javascript
window.pipelineLaunchPreflightLines = pipelineLaunchPreflightLines;
```

**Verification:**
```powershell
Select-String -Path "DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\launchView.js" `
  -Pattern '"kill"'
# Must return >= 2 (labels + confirms)

Select-String -Path "DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\launchView.js" `
  -Pattern 'window\.pipelineLaunchPreflightLines'
# Must return 1
```

---

## Task 4 — JS: scheduleView.js updates

**File:** `assets/scheduleView.js`

Add two exports at the bottom of `scheduleView.js`, alongside the existing `window.*` exports:

```javascript
window.getLastSchedule = () => lastSchedule;
window.scheduleToggleSave = scheduleToggleSave;
```

Add the `scheduleToggleSave` function just before the exports block:

```javascript
async function scheduleToggleSave() {
  const schedule = lastSchedule;
  if (!schedule || schedule.enabled === undefined) {
    return { ok: false, message: "Schedule not yet loaded. Refresh first." };
  }
  const newEnabled = !Boolean(schedule.enabled);
  const grid = (schedule && typeof schedule.grid === "object" && schedule.grid !== null)
    ? schedule.grid
    : {};
  try {
    const result = await apiPost("/api/schedule/save", {
      enabled: newEnabled,
      grid,
      confirm_save: true,
    });
    if (result && result.ok !== false) {
      // Optimistically update cached state so the toggle button reflects immediately
      lastSchedule = { ...schedule, enabled: newEnabled };
    }
    return result || { ok: false, message: "No result from schedule save." };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return { ok: false, message };
  }
}
```

**Verification:**
```powershell
Select-String -Path "DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\scheduleView.js" `
  -Pattern 'window\.getLastSchedule|window\.scheduleToggleSave'
# Must return 2
```

---

## Task 5 — JS: app.js additions

**File:** `assets/app.js`

Add the following home-view rendering and init functions. Insert them near the existing `renderHomeReadiness` function block (around line 396). Then wire each into `refreshAllNow` and the `DOMContentLoaded` handler.

### 5A — Functions to add

```javascript
// ── Home: pending count metric ──────────────────────────────────────
function renderHomePendingCount(pending) {
  const count = Number(pending?.count ?? (Array.isArray(pending?.rows) ? pending.rows.length : 0));
  setText("home-pending-count", String(count));
}

// ── Home: network role metric ────────────────────────────────────────
function renderHomeNetworkRole(settings) {
  const role = String(settings?.network_mode || settings?.role || "standalone").toLowerCase();
  setText("home-network-role", role);
}

// ── Home: queue snapshot ─────────────────────────────────────────────
function renderHomeQueueSnapshot(queue) {
  const summary = queue?.summary || queue?.queue_summary || "";
  const count = queue?.count ?? (Array.isArray(queue?.rows) ? queue.rows.length : 0);
  const status = count > 0 ? `${count} items` : "Empty";
  setText("home-queue-snapshot-status", status);
  setText(
    "home-queue-snapshot",
    summary || (count === 0 ? "Queue is empty." : `${count} items in queue. Refresh for details.`),
  );
}

// ── Home: recently completed ─────────────────────────────────────────
function renderHomeRecentCompleted(completed) {
  const tbody = byId("home-recent-completed-tbody");
  if (!tbody) return;
  const rows = Array.isArray(completed?.rows) ? completed.rows : [];
  const recent = rows.slice(-5).reverse();
  const count = rows.length;
  setText("home-recent-completed-status", count > 0 ? `${count} total` : "None");
  if (!recent.length) {
    tbody.innerHTML = '<tr><td colspan="3">No completed files loaded.</td></tr>';
    return;
  }
  tbody.innerHTML = recent.map((r) => {
    const name = String(r.name || r.output_name || r.file || "").split(/[\\/]/).pop() || "—";
    const route = String(r.route || r.kind || "—");
    const finished = String(r.completed_at || r.finished_at || r.at || "—").slice(0, 16);
    return `<tr><td title="${name}">${name}</td><td>${route}</td><td>${finished}</td></tr>`;
  }).join("");
}

// ── Home: guarded start ──────────────────────────────────────────────
function initHomeGuardedStart() {
  const startBtn = byId("home-pipeline-start-button");
  const confirmBtn = byId("home-confirm-start-button");
  const cancelBtn = byId("home-cancel-start-button");
  const resultEl = byId("home-start-check-result");
  const confirmRow = byId("home-confirm-start-row");
  if (!startBtn || !confirmBtn || !cancelBtn || !resultEl || !confirmRow) return;

  const defaultRequest = {
    mode: "once",
    sleep_seconds: 30,
    show_config: false,
    show_console: false,
    schedule_override: "",
  };

  function resetStartButton() {
    startBtn.textContent = "Start Pipeline";
    startBtn.disabled = false;
    resultEl.style.display = "none";
    resultEl.removeAttribute("data-check-state");
    confirmRow.style.display = "none";
  }

  startBtn.addEventListener("click", () => {
    startBtn.textContent = "Checking…";
    startBtn.disabled = true;
    confirmRow.style.display = "none";

    // Build preflight lines from cached data (no API call needed)
    const preflightFn = typeof window.pipelineLaunchPreflightLines === "function"
      ? window.pipelineLaunchPreflightLines
      : null;
    const lines = preflightFn
      ? preflightFn(defaultRequest)
      : ["Preflight check not available — launch view not loaded yet."];

    const hasBlocker = lines.some((l) =>
      /warning|blocked|error|missing|not available|no .*found/i.test(String(l))
    );

    resultEl.textContent = lines.join("\n");
    resultEl.dataset.checkState = hasBlocker ? "fail" : "pass";
    resultEl.style.display = "block";

    if (!hasBlocker) {
      confirmRow.style.display = "flex";
    }
    startBtn.textContent = "Start Pipeline";
    startBtn.disabled = false;
  });

  cancelBtn.addEventListener("click", resetStartButton);

  confirmBtn.addEventListener("click", async () => {
    confirmBtn.disabled = true;
    startBtn.disabled = true;
    resultEl.textContent = "Starting pipeline…";
    try {
      const result = await apiPost("/api/pipeline/start", defaultRequest);
      if (typeof appendCommandResult === "function") appendCommandResult(result);
      resultEl.textContent = result?.message || "Pipeline start command sent.";
      resultEl.dataset.checkState = result?.ok !== false ? "pass" : "fail";
      if ((result?.refresh_hint || "") === "snapshot" && typeof refreshAll === "function") {
        await refreshAll();
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      resultEl.textContent = `Start failed: ${message}`;
      resultEl.dataset.checkState = "fail";
    } finally {
      confirmRow.style.display = "none";
      confirmBtn.disabled = false;
      startBtn.disabled = false;
    }
  });
}

// ── Home: schedule toggle ────────────────────────────────────────────
function renderHomeScheduleToggle(schedule) {
  const btn = byId("home-schedule-toggle-button");
  const note = byId("home-schedule-toggle-status");
  if (!btn) return;
  const enabled = Boolean(schedule?.enabled);
  btn.textContent = enabled ? "Disable Schedule" : "Enable Schedule";
  if (note) {
    note.textContent = `Schedule enforcement: ${enabled ? "On" : "Off"}`;
  }
}

function initHomeScheduleToggle() {
  const btn = byId("home-schedule-toggle-button");
  const note = byId("home-schedule-toggle-status");
  if (!btn) return;
  btn.addEventListener("click", async () => {
    const toggleFn = typeof window.scheduleToggleSave === "function"
      ? window.scheduleToggleSave
      : null;
    if (!toggleFn) {
      if (note) note.textContent = "Schedule toggle not available — schedule view not loaded.";
      return;
    }
    btn.disabled = true;
    if (note) note.textContent = "Saving…";
    try {
      const result = await toggleFn();
      if (note) note.textContent = result?.message || "Schedule updated.";
      // Refresh toggle label from updated cache
      const updatedSchedule = typeof window.getLastSchedule === "function"
        ? window.getLastSchedule()
        : null;
      if (updatedSchedule) renderHomeScheduleToggle(updatedSchedule);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      if (note) note.textContent = `Schedule toggle failed: ${message}`;
    } finally {
      btn.disabled = false;
    }
  });
}

// ── Home: drain button ───────────────────────────────────────────────
function initHomeDrainButton() {
  const btn = byId("home-drain-button");
  if (!btn) return;
  btn.addEventListener("click", () => {
    if (typeof startPendingPublishDrain === "function") {
      startPendingPublishDrain();
    }
  });
}
```

### 5B — Wire renders into refreshAllNow

In `refreshAllNow`, add these calls alongside the existing render calls (after the `pending publish` and `schedule` blocks):

```javascript
  if (values["pending publish"]) renderHomePendingCount(values["pending publish"]);
  if (values["network workers"] || values.settings) renderHomeNetworkRole(values.settings || getLastSettings());
  if (values.queue) renderHomeQueueSnapshot(values.queue);
  if (values.completed) renderHomeRecentCompleted(values.completed);
  if (values.schedule) renderHomeScheduleToggle(values.schedule);
```

### 5C — Wire inits into DOMContentLoaded

In the `DOMContentLoaded` handler, add after `initAdvancedToggle()`:

```javascript
  initHomeGuardedStart();
  initHomeScheduleToggle();
  initHomeDrainButton();
```

**Verification:**
```powershell
Select-String -Path "DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\app.js" `
  -Pattern 'renderHomePendingCount|renderHomeNetworkRole|renderHomeQueueSnapshot|renderHomeRecentCompleted|initHomeGuardedStart|initHomeScheduleToggle|initHomeDrainButton'
# Must return 7 results (one per function name, across definitions + call sites)
```

---

## Completion checklist

- [ ] Task 0 — `"kill"` in `PIPELINE_CONTROL_ACTIONS` frozenset; `kill_related_pipeline_processes` branch in `request_pipeline_control`.
- [ ] Task 1 — `.home-start-result` and `.home-compact-table` rules in `styles.css`.
- [ ] Task 2 — Home page rebuilt with 5 daily-driver panels + `data-advanced` wrapper over 9 legacy panels. New IDs present. Old IDs still in DOM.
- [ ] Task 3 — `kill` in `controlActionLabels` and `controlConfirmMessages`; `home-drain-button` and `home-pipeline-start-button` in `launchCommandButtonIds`; `window.pipelineLaunchPreflightLines` exported.
- [ ] Task 4 — `scheduleToggleSave` function added and exported; `window.getLastSchedule` exported.
- [ ] Task 5 — All 7 home functions added to `app.js`; render calls wired into `refreshAllNow`; init calls wired into `DOMContentLoaded`.
- [ ] Test suite — `1183 passed 0 failed`. New DOM IDs do not appear in existing assertions. Kill backend change is additive. No existing JS IDs removed from DOM.

---

## What is not in scope

- A `home-pipeline-start-button` conflict with `pipeline-start-button` on Launch page. They are different IDs and different handlers. The Launch page keeps its full form-driven flow.
- The `startPendingPublishDrain` function referenced in Task 5C is defined in `launchView.js` and exposed to `app.js` scope via the existing module pattern — it is not redefined here.
- Per-route icons or colours in the Recently Completed table.
- A manual light/dark toggle (deferred, not this stage).
