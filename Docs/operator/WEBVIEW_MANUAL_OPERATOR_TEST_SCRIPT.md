# WebView Manual Operator Test Script

Date: 2026-06-02

Step-by-step manual validation script for the Tauri/WebView2 preview shell. Covers all 13 WebView pages. This script does not launch the pipeline, process media, save settings, rename files, drain pending publish, or touch source/output/scratch paths.

---

## Prerequisites

Before starting:

1. Start the local API:
   ```
   .\scripts\dev\start-local-api.bat
   ```
2. Start the Tauri/WebView2 preview:
   ```
   .\scripts\dev\start-tauri-preview.bat
   ```
3. Confirm the top bar shows a green/active state pill (not "Connecting" or "Error").
4. Open browser DevTools → Network tab. Filter by XHR/Fetch. You will use this to confirm which routes are called during each page browse.
5. Do not have any real media processing jobs running during this test. The test is read-only observation only.

---

## Global Checks (Apply to Every Page)

Before moving to each page, verify:

- **No spontaneous POST calls**: page load must not trigger any `apiPost` call automatically. Only explicit operator button clicks may trigger POST routes.
- **No raw filesystem paths in UI**: no field should display a resolved path that the frontend computed independently. Paths shown in the WebView come from backend state.
- **No "launch", "start", "apply", "drain", "rename", or "save" on page load**: these actions must be explicit and operator-initiated.
- **Topbar refresh health indicator**: should poll `GET /api/health` at the configured interval. This is the only automatic polling that runs.

---

## Page 1: Home

**Navigate to**: click `Home` in the sidebar.

### Verify — Metrics grid
- Pipeline state, Queue count, Processed count, Failed count are visible.
- Values update when you click the Refresh button.

### Verify — Operator Readiness panel
- "Operator Readiness" heading visible.
- Readiness text is backend-authored (not frontend-computed).
- Status badge shows a result (Checking / Ready / Review).

### Verify — Daily-Driver Checklist
- Table visible with Area, Status, Evidence, Next Step columns.
- Rows are read-only — no buttons in the table rows.
- Footer legend reads: "Daily-driver checklist rows are read-only and do not launch, repair, drain, save, rename, or mutate files."

### Verify — Sample Validation Record (cross-page context panel)
- Panel visible under cross-page context.
- Operator Sample Execution Checklist is visible and selectable.
- Selecting the Completed proof row shows owner page, backend evidence, operator proof, unsafe-if-ignored text, and the read-only execution guardrail.
- Preview button is present but does not auto-click.
- "Append" button visible; should NOT fire automatically.
- If you click Preview: observe a POST to `/api/sample-validation/preview`. No files are written.

### Pass criteria
- No automatic POST calls on load.
- All panels show backend-served content.
- No launch/repair/drain controls present.

---

## Page 2: Live

**Navigate to**: click `Live` in the sidebar.

### Verify — Active Jobs table
- Table loads with current or empty active jobs.
- Each row shows job status, shell, mode, PID if active.

### Verify — Progress view
- Progress text and events are displayed from backend.
- No mutation buttons in this panel.

### Pass criteria
- Polling GET calls only on load.
- No POST calls triggered by browsing.

---

## Page 3: Queue

**Navigate to**: click `Queue` in the sidebar.

### Verify — Table loads
- Queue rows appear (or empty state shown).
- Text filter, status filter, investigation filter are visible.

### Verify — Row selection
- Click any row. Selected-row detail panel appears on the right.
- Detail shows source path, route decision, priority status.
- "Open Source File" and "Open Source Folder" buttons are visible.

### Verify — Open buttons (shell-open only)
- Click "Open Source File". Observe a POST to `/api/queue/open` with `target: "source_file"`. No file read happens in the frontend.
- File manager should open to the source file location.

### Verify — Filter behavior
- Apply a text filter. Verify the table filters without clearing selection.
- Verify: if your selected row is hidden by a filter, the detail panel shows a "this row is hidden by the active filter" warning.

### Verify — Large-table render cap
- If 250+ rows exist: verify a render-cap disclosure note appears. The note must state that "backend launch scope is not narrowed to visible rows."

### Verify — Backend Launch Scope Preview panel
- Scroll to the Backend Launch Scope Preview panel.
- Verify the panel shows: loaded row count, visible filtered row count, selected-row boundary note, backend launch route (`POST /api/pipeline/start`), and recent backend start command evidence.
- Apply a display filter that hides some rows. Verify the scope preview updates to show a lower visible-row count while the loaded-row count stays the same.
- Verify the panel states that backend launch scope is not narrowed to visible rows.
- Confirm: the panel does not post any route; it is read-only evidence only.

### Verify — No launch controls
- There must be no "Start Pipeline", "Launch", or "Run" button on the Queue page. These live only on the Launch page.

### Pass criteria
- All POST calls are `queue/open` only and triggered by explicit clicks.
- No process-launch calls triggered from Queue.
- Backend Launch Scope Preview is visible, read-only, and correctly disclaims its non-mutation status.

---

## Page 4: Completed

**Navigate to**: click `Completed` in the sidebar.

### Verify — Table and row detail
- Completed rows appear.
- Select a row: detail panel shows output file, route, size, sidecar status.

### Verify — Open buttons
- "Open Output Folder", "Open Sidecar", "Open Source Folder" trigger `/api/completed/open`. Confirm no raw path is resolved by the frontend.

### Verify — Real-Media Output Proof ladder
- Select a completed row with output and sidecar.
- Verify the Real-Media Output Proof ladder panel is visible (read-only).
- Ladder rows compare output/sidecar proof, route/size decisions, Pending Publish posture.
- Confirm: "cannot accept, rerun, drain, repair, publish, delete, rewrite manifests, or touch media."

### Verify — Backend Publish Reconciliation
- Click the "Refresh" button in the Publish Reconciliation panel.
- Observe a GET to `/api/publish-reconciliation`. No POST call.
- Panel shows correlation of Completed rows vs. Pending Publish rows vs. drain summary.
- Confirm the panel footer says it "cannot mark done, repair, drain, publish, rewrite manifests, or touch media."

### Verify — Route Agreement panel
- Visible when a row is selected.
- Read-only — no action buttons.

### Pass criteria
- Only `completed/open` POSTs on button click; all other interaction is GET-only.
- Reconciliation panel is read-only.

---

## Page 5: Pending Publish

**Navigate to**: click `Pending Publish` in the sidebar.

### Verify — Table and row detail
- Pending rows appear (parked, missing-payload, etc.).
- Select a row: detail panel shows local_file, destination, manifest state, route reason.

### Verify — Open buttons
- "Open Local File", "Open Destination Folder", "Open Manifest" trigger `/api/pending-publish/open`.

### Verify — Drain Action Confidence and filter scope
- Verify the Drain Action Confidence panel reflects the current active filter state.
- Apply a status filter that hides some rows. The Drain Action Confidence panel must update to state that "backend Publish Parked Outputs sees all parked state, not only the visible subset."

### Verify — Publish Button Guard
- The Publish Parked Outputs button is gated.
- If recovery-plan blockers exist: button must be blocked. Verify clicking it does NOT post to `/api/pipeline/start`. Check DevTools network: no POST call should appear.

### Verify — Backend Drain Scope Preview panel
- Scroll to the Backend Drain Scope Preview panel.
- Verify the panel shows: loaded parked row count, visible filtered row count, selected-row boundary note, backend drain route (`POST /api/pipeline/start` with `mode: drain_pending_pushes`), durable drain summary, and recent drain command evidence.
- Apply a display filter that hides some rows. Verify the scope preview updates to show a lower visible-row count while the loaded-row count stays the same.
- Verify the panel states that backend drain scope is not narrowed to visible rows.
- Confirm: the panel does not post any route; it is read-only evidence only.

### Verify — Recovery Plan (dry-run only)
- Click "Recovery Plan (Selected)" or "Recovery Plan (All)". Observe POST to `/api/pending-publish/recovery-plan`.
- Result is a read-only plan. No drain, no repair, no file moves triggered.

### Pass criteria
- Publish Button Guard blocks premature drain.
- All automatic interactions are GET-only.
- Recovery plan is dry-run only.
- Backend Drain Scope Preview is visible, read-only, and correctly disclaims its non-mutation status.

---

## Page 6: Rename

**Navigate to**: click `Rename` in the sidebar.

### Verify — Rename table loads
- TV or Movie rows appear based on mode selector.
- Predicted final names shown in the table.

### Verify — Browse source paths
- Click "Browse Files" or "Browse Folder". Observe POST to `/api/rename/browse`.
- A native Windows picker should open. Canceling should return without changing staged paths.
- Selecting files or a folder should stage paths into the Rename path list only. It must not preview, apply, rename, move, delete, or touch media.

### Verify — Apply Readiness ledger
- Panel shows blockers (if any) before apply is allowed.
- If any blocker is present: Apply button must be grayed out or disabled.

### Verify — Render-cap disclosure
- If 250+ rows in scope: verify "250 of N rows shown" disclosure. This must state that the backend applies to all in scope, not only visible rows.

### Verify — Preview
- Click "Preview Rename". Observe POST to `/api/rename/preview`. No files are renamed.
- Preview results appear in the table as predicted final names.

### Verify — Apply does not fire on browse
- Do NOT click Apply during this test. Verify that Apply is NOT called automatically.
- If you do click Apply intentionally (for testing only): observe POST to `/api/rename/apply` with `confirm_apply: true`. The backend rebuilds the plan independently and does not use the frontend-submitted table state.

### Pass criteria
- No rename occurs during browse or preview.
- Apply Readiness ledger correctly blocks apply when blockers exist.

---

## Page 7: Launch

**Navigate to**: click `Launch` in the sidebar.

### Verify — Launch Readiness panel
- Preflight rows visible (backend-authored checks).
- If any blocker: "Start Pipeline" button must be blocked or show a warning.

### Verify — Active Media Policy Boundary
- Panel shows saved subtitle/container, audio, and pending-publish/source-safety policy.
- Any "staged settings candidate" (from Settings) appears as "not launch-active until saved."
- This panel is read-only.

### Verify — Pipeline start (for test only — optional)
- If testing start: click "Run Once". Observe POST to `/api/pipeline/start` with `mode: "once"`. Confirm mode is correct.
- Do not start continuous mode during this manual test unless intentionally validating pipeline behavior.

### Verify — Launch Scope Reconciliation panel
- Panel visible below the Active Media Policy Boundary.
- Rows compare the launch scope against the operator's current Queue/Completed/Pending evidence.
- This panel is read-only — no buttons post to backend routes.
- Confirm: footer or legend states "Launch Scope Reconciliation is read-only and does not accept, save, drain, publish, rename, or touch media."

### Verify — Launch Real-Media Sample Proof Handoff
- Panel visible when sample validation worksheet evidence is loaded.
- Shows generated worksheet evidence and Sample Validation record evidence for the selected real-media sample.
- Proof ladder rows compare the selected sample's route/output/log/publish/media proof with what Launch sees.
- This panel is read-only — no POST routes triggered by browsing.
- If a Sample Validation record matches the selected sample: the record posture (current/stale/review) and first-matching-record detail appear here.
- Confirm: no "accept", "append", or "drain" buttons in this panel.

### Verify — Launch Sample Execution Checklist
- Panel shows the backend-authored operator sample execution checklist mirrored from Home.
- Checklist rows are selectable and show evidence hints for pre/during/post-run evidence steps.
- This panel is read-only — selecting rows does not trigger any POST.

### Verify — Launch Start Decision Summary
- Panel visible at the top of the Launch controls (above or near the Pipeline Start button).
- Rolls up: Launch Readiness, timing/schedule posture, backend preflight, Queue Launch Decision, Settings/policy state, Launch Scope Reconciliation, real-media proof, sample execution checklist, and recent Launch command evidence.
- Selectable rows allow inspection of the highest-severity signal before pressing Start.
- This panel is read-only — does not post routes, reserve locks, or initiate launch.

### Verify — Control flags (pause, stop, rescan)
- These buttons trigger POST to `/api/pipeline/control`. Each must show confirmation before firing (if guardrails are implemented).

### Pass criteria
- Active Media Policy Boundary is read-only.
- Launch Readiness blocks start when preflight fails.
- Launch Scope Reconciliation, Real-Media Sample Proof Handoff, Sample Execution Checklist, and Start Decision Summary panels are all read-only on browse — no automatic POST calls triggered.

---

### Freshness Note — 2026-05-15 (CLN3-014)

Added Launch Scope Reconciliation, Launch Real-Media Sample Proof Handoff, Launch Sample Execution Checklist, and Launch Start Decision Summary verification steps to Page 7: Launch. These panels were added during the V5 real-media proof handoff work and were absent from the original manual script.

---

## Page 8: Audit / Reports

**Navigate to**: click `Audit / Reports` in the sidebar.

### Verify — Reports and audit results
- Audit CSV preview loads via GET.
- Priority CSV visible if applicable.
- Failure markers and failure reports visible.

### Verify — No accidental audit start
- "Start Audit" button is present on the Launch page, not here. This page is read-only.

### Pass criteria
- No POST calls on browse.
- All data served from read endpoints.

---

## Page 9: Schedule

**Navigate to**: click `Schedule` in the sidebar.

### Verify — Schedule grid
- Weekly schedule grid displayed with current saved schedule.
- Days/blocks visible.

### Verify — Block detail
- Select a day block: detail panel shows start/stop times, active/inactive.

### Verify — Schedule editor (for test only — optional)
- Modify a block, click "Preview". Observe POST to `/api/schedule/preview`. No schedule written.
- If testing save: click "Save Schedule". Observe POST to `/api/schedule/save` with `confirm_save: true`.

### Pass criteria
- Schedule grid is read-only unless operator explicitly edits.
- Preview fires before any save.

---

## Page 10: Network

**Navigate to**: click `Network` in the sidebar.

### Verify — Network readiness (read-only)
- Coordinator/worker status shown from persisted state.
- No "Start Coordinator", "Stop Worker", or "Add Worker" buttons should be present or active.

### Verify — Worker rows
- Worker detail visible when a row is selected.
- All information is read-only.

### Verify — Worker filter warnings
- Apply a filter that hides active or problem workers.
- Verify a warning appears: "active or problem workers are hidden by the current filter."

### Pass criteria
- No lifecycle mutation controls present.
- All data is GET-served.

---

## Page 11: Maintenance

**Navigate to**: click `Maintenance` in the sidebar.

### Verify — Environment probe
- Click "Check Environment". Observe GET to `/api/maintenance`. Returns tool availability without repairing or installing.

### Verify — Release dry-run
- Click "Plan Only". Observe POST to `/api/maintenance/release-dry-run`. No release folder or zip is written.
- Result shows what would be included/excluded.

### Verify — Backfill dry-run
- Click "Scan Sidecars (Dry Run)". Observe POST to `/api/maintenance/completed-backfill-dry-run`. No manifest is written.

### Pass criteria
- All maintenance actions that write are gated behind explicit confirmation.
- Dry-run calls produce read-only plans.

---

## Page 12: Diagnostics

**Navigate to**: click `Diagnostics` in the sidebar.

### Verify — Diagnostics panel loads
- Recent events, errors, and log tail visible.
- State summary panel shows artifact health.

### Verify — Open target buttons
- "Open Run Logs", "Open Config Folder", etc. trigger POST to `/api/diagnostics/open` with specific `target` keys.
- Confirm: only allowlisted targets are exposed. No arbitrary path input field should be visible.

### Verify — Bounded tail
- "Read Tail" for a target: observe GET to `/api/diagnostics/tail` with `target` and `max_bytes`. Confirm `max_bytes` is capped at 256 KB.

### Verify — Owning Page Evidence Handoff
- Panel shows flagged Queue, Completed, Pending Publish rows pointing back to their owning page.
- "Go To Owner Row" is local UI selection — no backend call triggered.

### Pass criteria
- No arbitrary path accepted.
- Tail is bounded.
- Go To Owner Row is local-only.

---

## Page 13: Settings

**Navigate to**: click `Settings` in the sidebar.

### Verify — Read-only overview
- Media policy readiness rows visible (saved route/size, subtitle, audio, publish safety, runtime posture).
- These rows are read-only and do not replace backend Preview/Save.

### Verify — Settings builder
- Modify a field. Observe that changes accumulate locally as a "Changes JSON candidate."
- No automatic save. No POST call on typing.

### Verify — Preview Patch
- Click "Preview". Observe POST to `/api/settings/preview-patch`. Returns redacted diff. No config written.

### Verify — Save Patch
- Click "Save" (if testing). Observe POST to `/api/settings/save-patch` with `confirm_save: true`. Backend backs up before writing.
- After save: a reload POST to `/api/settings/reload` fires. Backend reloads in-memory state.

### Verify — Settings-to-Launch handoff
- Staged changes that are not yet saved show as "not launch-active" in the Active Media Policy Boundary on the Launch page.

### Verify — Backend Preview / Save Result panel
- After Preview: panel shows backend diff, warnings, risk summary.
- All detail is read-only.

### Pass criteria
- No automatic config write.
- Preview always fires before Save is enabled.
- Save requires `confirm_save` at the backend layer (verify in DevTools request body).

---

## End-of-Run Mutation Boundary Confirmation

After completing all 13 pages:

1. Open browser DevTools → Network tab.
2. Review all POST calls made during the session.
3. Verify that no POST calls were made automatically (without explicit operator button click).
4. Verify that no POST calls were made to:
   - `/api/rename/apply` (unless you intentionally tested Apply)
   - `/api/pipeline/start` with mode `continuous` (unless intentionally testing)
   - `/api/pending-publish/open` with a raw path (target must be an allowlisted key)
   - Any route not listed by the active `/api/contract` response or `Docs/inventories/API_ROUTE_INVENTORY.md`

5. Verify that no JavaScript errors appear in the browser console related to unhandled rejections or missing backend responses.

---

## Smoke Tests vs. Manual Test

This script is for human observation. Automated equivalents:

| Page | Automated smoke |
|---|---|
| Queue / Completed / Pending (row detail) | `Test-WebViewRowDetailSmoke.ps1` |
| Command history | `Test-WebViewCommandEvidenceSmoke.ps1` |
| Rename readiness | `Test-WebViewRenameReadinessSmoke.ps1` |
| Settings/Launch policy | `Test-WebViewSettingsLaunchPolicySmoke.ps1` |
| Settings patch evidence | `Test-WebViewSettingsPatchEvidenceSmoke.ps1` |
| High-risk rows | `Test-WebViewBrowserHighRiskSmoke.ps1` |
| Diagnostics handoff | `Test-WebViewBrowserDiagnosticsHandoffSmoke.ps1` |
| Pending drain guard | `Test-WebViewBrowserPendingDrainGuardSmoke.ps1` |
| Large table | `Test-WebViewBrowserLargeTableSmoke.ps1` |
| Rename (browser) | `Test-WebViewBrowserRenameSmoke.ps1` |
| Network (browser) | `Test-WebViewBrowserNetworkSmoke.ps1` |
| Telemetry (browser) | `Test-WebViewBrowserTelemetrySmoke.ps1` |
| Settings/Launch (browser) | `Test-WebViewBrowserSettingsLaunchSmoke.ps1` |
| Schedule | `Test-WebViewScheduleSmoke.ps1` |
| Real-media evidence | `Test-WebViewRealMediaEvidenceSmoke.ps1` |

See `Docs/testing/WEBVIEW_SMOKE_TEST_CATALOG.md` for the full catalog.

---

## See Also

- Mutation boundary: `Docs/architecture/LOCAL_API_EVIDENCE_MUTATION_MATRIX.md`
- Historical mutation review: `Docs/archive/docs-housekeeping/2026-05-20-review/archive-historical/Docs/archive/completed-audits/WEBVIEW_APIPOST_MUTATION_REVIEW.md`
- No-touch boundaries: `Docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`
- Smoke test catalog: `Docs/testing/WEBVIEW_SMOKE_TEST_CATALOG.md`
- Failure triage: `Docs/operator/FAILURE_TRIAGE_WORKSHEET.md`
