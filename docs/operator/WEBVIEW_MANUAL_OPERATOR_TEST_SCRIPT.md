# WebView Manual Operator Test Script

Date: 2026-07-19

Step-by-step manual validation script for the Tauri/WebView2 preview shell. Covers all 13 WebView pages. This script does not launch the pipeline, process media, save settings, rename files, drain pending publish, or touch source/output/scratch paths.

---

## Prerequisites

Before starting:

1. Start the local API:
   ```
   .\ops\scripts\dev\start-local-api.bat
   ```
2. Start the Tauri/WebView2 preview:
   ```
   .\ops\scripts\dev\start-tauri-preview.bat
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
- **Automatic refresh boundary**: configured read-only GET routes such as health,
  snapshot, telemetry, commands, and Run Monitor may poll. No automatic refresh
  may issue a POST or turn supporting/stale evidence into current authority.

### Accessibility and responsive pass

Perform this pass with keyboard only and with NVDA or Windows Narrator. Use a
disposable synthetic state root or an already authorized safe fixture when a
state transition is needed; this script does not authorize starting real media
or using personal production paths.

1. Test both themes. Every focused interactive control must have a clearly
   visible indicator whose boundary is distinguishable from adjacent colors.
2. At desktop width, 768 CSS pixels, 390 CSS pixels, and 320 CSS pixels, verify
   that the page itself does not scroll horizontally. Repeat representative
   Current Work detail at 200% and 400% browser zoom.
3. Turn on reduced motion in Windows and confirm selection/focus changes do not
   depend on animation.
4. Navigate between Queue, Launch, Current Work, Completed, Pending Publish,
   Reports, and back. Focus must land on the destination heading or the exact
   selected-file/proof target, then restore to a useful prior target on return.
5. With two identical leaf filenames from different parent paths, confirm the
   screen reader announces the full distinguishable identity and never merges
   the rows.
6. During an automatic refresh, confirm the selected row and focused control
   remain stable, including an active-worker button and an exact terminal-proof
   button. An unchanged accepted-workload row must retain its exact DOM/focus
   target and must not trigger a new focus event. The screen reader must not
   re-announce the row or the whole page.
7. For meaningful synthetic transitions, confirm one concise announcement for
   a new current file, failure/review, parked output, stop requested, and run
   completion. Also exercise active → quiet → the same file active again;
   both genuine activations must be announced once. Routine 15-second refreshes
   must remain quiet.
8. At 768 CSS pixels and narrower, confirm every stacked Audio and Subtitle
   track cell retains a visible `Track`, `Source`, `Planned action`, or
   `Current / final evidence` label after the table header is visually clipped.

---

## Page 1: Home

**Navigate to**: click `Home` in the sidebar.

### Verify — Current Work run summary
- "Run Once · Backend Queue" is the primary current-work heading.
- Run lifecycle, start/end time, run-scoped counts, freshness/age, active-worker
  count, Stop After Current state, and backend authority are visible.
- Stop After Current is available only during current active work and continues
  to use the existing backend confirmation. Force Stop remains visually
  subordinate and exceptional.
- Refresh issues `GET /api/run-monitor`; it must not reconstruct current state
  from Queue rows, logs, route labels, or stale `/api/snapshot` progress.

### Verify — Accepted file master list
- The default folded view shows the first 20 verified cleaned filenames as
  noninteractive preview rows and does not put preview rows in the Tab order.
  Here, verification may come from the production Queue naming plan or, for an
  eligible saved legacy terminal item, from exact job-correlated
  Completed/Pending output evidence. When either authority exists, the raw
  release filename is not the primary folded-row label.
- The count states how many files are shown out of the full accepted workload.
  Activate **Show all N files** (the **Open file selection** disclosure) and
  confirm the expanded view contains every accepted file exactly once,
  independent of Queue filters, pagination, selected rows, or render limits.
- Each expanded row leads with its backend-projected effective filename and
  retains the raw source path as secondary accessible identity evidence.
  Duplicate cleaned names show distinguishable parent context. Run-wide
  position, lifecycle, current stage, route summary, and selected/current text
  cues appear only in the opened selection view or its accessible name, not as
  folded-preview clutter.
- An unresolved legacy item with neither verified Queue-plan naming evidence nor
  exact terminal output proof must keep its accepted label and identify the
  evidence as legacy/unknown. The WebView must not clean that label itself or
  borrow a name from the current Queue snapshot.
- Completed, failed, skipped, blocked, review, parked, current, and queued rows
  remain together when another file becomes active.
- Exactly one file button is in the Tab order. Arrow Up/Down and Home/End move
  roving focus and selection; Enter/Space select without changing backend state.
- Activate the disclosure again and confirm collapse focus returns to the
  disclosure button, the first-20 preview returns, and the selected file detail
  is preserved. Reopen it and confirm focus/selection still identify the exact
  backend job.
- Long names wrap as readable filename/context text in the opened view. Identical
  leaf names from different parents remain distinguishable visually and in
  accessible names.
- With two different files active concurrently, both rows and worker buttons
  expose their parent context and active text. The accepted list does not claim
  that multiple rows are the one singular `aria-current` item.

### Verify — Native Tauri reopen with legacy terminal evidence

Use a disposable synthetic state root or an already authorized read-only saved
run. Do not start media processing for this check.

1. Load a completed or parked Backend Queue Run Once record that predates
   `display_name_evidence` but whose monitor item contains exact terminal output
   evidence and an exact same-job Completed or Pending Publish reference.
2. Close and reopen the native Tauri preview. On Home, confirm the folded list
   still shows **Showing first 20 of N** and **Show all N files**.
3. Confirm the expected terminal filenames are the primary accepted-workload
   labels after reopen and the old raw release leaves are not primary list
   labels. Select a row and confirm its unchanged raw source path remains
   available in detail as secondary identity evidence.
4. Confirm API evidence reports the immutable stored label separately as
   `accepted_display_name`, the effective label as `display_name`, and
   `display_name_basis=terminal_output`. The durable Run Monitor file must be
   byte-for-byte unchanged by this read-only check.
5. When the fixture is already loaded in the native shell, the Windows UI
   Automation probe may assert the native WebView2 surface directly:

   ```powershell
   .\apps\desktop\tauri\Test-TauriShell-WebViewUiAutomationProbe.ps1 -HomeOnly -ExpectedHomeNames @('Clean Movie (2026).mkv') -RejectedHomeNames @('Raw.Release.Name.2026.mkv')
   ```

   Passing browser-hosted synthetic tests alone is not evidence for this step;
   verify the native Tauri window and its WebView2 accessibility tree.

### Verify — Selected file detail
- Planned, Executed, and Final route/reason are separately labelled and shown
  only when their matching backend authority exists.
- The canonical stage timeline distinguishes probe, copy, audio, subtitles,
  encode/remux, mux, verification, sidecars, publish/park, and final evidence.
- Audio and subtitle tables enumerate each track, language, source properties,
  policy action, progress/result, and evidence. Missing evidence says unknown or
  awaiting backend evidence, never “pending.”
- Output size, scratch/working/published/parked/intended paths, sidecars,
  manifests/failure references, recovery owner, retryability, and next action
  appear when backend evidence provides them.
- Terminal proof buttons select and focus the exact Completed/Pending/Reports
  proof by stable key or exact artifact path. If it is not loaded, the handoff
  lands honestly on the destination heading rather than matching a filename.

### Verify — Freshness and announcements
- Stale, future-dated, unavailable, partial, or contradictory evidence suppresses
  current file/stage/route/worker/percentage claims together.
- Historical disclosure is labelled "Last known — not current" and includes
  timestamp/age. It does not select an active file.
- Confirm the single Current Work live status announces meaningful transitions
  once and does not announce every panel on refresh.

### Verify — Sample Validation Record (cross-page context panel)
- Panel visible under cross-page context.
- Operator Sample Execution Checklist is visible and selectable.
- Selecting the Completed proof row shows owner page, backend evidence, operator proof, unsafe-if-ignored text, and the read-only execution guardrail.
- Preview button is present but does not auto-click.
- "Append" button visible; should NOT fire automatically.
- If you click Preview: observe a POST to `/api/sample-validation/preview`. No files are written.

### Pass criteria
- No automatic POST calls on load.
- Current claims come only from the exact backend Run Monitor projection.
- Effective names come only from verified Queue-plan evidence or exact
  job-correlated terminal evidence; accepted labels and durable membership are
  not rewritten.
- Selection, focus, run membership, and terminal rows survive refresh.
- Routine monitoring requires no Diagnostics visit.

---

## Page 2: Telemetry

**Navigate to**: click `Telemetry` in the sidebar.

### Verify — Active Jobs table
- Table loads with current or empty active jobs.
- Each row shows job status, shell, mode, PID if active.

### Verify — Supporting telemetry boundary
- Hardware, ActiveJobs, FFmpeg/log-tail, and legacy progress evidence is clearly
  secondary to Home Current Work.
- Supporting evidence attaches to a file only with exact backend job
  correlation and never becomes stage authority.
- Stage/File/ETA links return to the selected Current Work file detail; the
  hardware link stays on Telemetry.

### Pass criteria
- Polling GET calls only on load.
- No POST calls triggered by browsing.
- Telemetry cannot repopulate a stale active Current Work timeline.

---

## Page 3: Queue

**Navigate to**: click `Queue` in the sidebar.

### Verify — Table loads
- Queue rows appear (or empty state shown).
- Text filter, status filter, investigation filter are visible.

### Verify — Row selection
- Click any row. Selected-row detail panel appears on the right.
- Detail shows source path, route decision, priority status.
- Predictive fields are labelled "Planned route" and "Planned reason."
- "Open Source File" and "Open Source Folder" buttons are visible.

### Verify — Open buttons (shell-open only)
- Click "Open Source File". Observe a POST to `/api/queue/open` with `target: "source_file"`. No file read happens in the frontend.
- File manager should open to the source file location.

### Verify — Filter behavior
- Apply a text filter. Verify the table filters without clearing selection.
- Verify: if your selected row is hidden by a filter, the detail panel shows a "this row is hidden by the active filter" warning.

### Verify — Large-table render cap
- If 250+ rows exist: verify a render-cap disclosure note appears. The note must state that "backend launch scope is not narrowed to visible rows."
- Tab enters the Queue table once rather than once per row. Arrow Up/Down moves
  roving focus; Enter/Space selects. The selected row's File override button is
  the only row action added to the Tab order.

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

Added Launch Scope Reconciliation, Launch Real-Media Sample Proof Handoff, Launch Sample Execution Checklist, and Launch Start Decision Summary verification steps to Page 7: Launch. These panels were added during the real-media proof handoff work and were absent from the original manual script.

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
- Click "Save" (if testing). Observe POST to `/api/settings/preview-patch`, then POST to `/api/settings/save-patch` with matching `review_confirmation` and `confirm_save: true`. Backend backs up before writing.
- After save: a reload POST to `/api/settings/reload` fires. Backend reloads in-memory state.

### Verify — Settings-to-Launch handoff
- Staged changes that are not yet saved show as "not launch-active" in the Active Media Policy Boundary on the Launch page.

### Verify — Backend Preview / Save Result panel
- After Preview: panel shows backend diff, warnings, risk summary.
- All detail is read-only.

### Pass criteria
- No automatic config write.
- Preview always fires before Save is enabled.
- Save requires backend preview `review_confirmation` plus `confirm_save` at the backend layer (verify both in DevTools request body).

---

## Native-only evidence recipes

These checks remain `manual_native_only` in
`docs/generated/WEBVIEW_TOUCHPOINT_LEDGER.json` until the actual Windows or
Tauri outcome is captured. A browser route stub, a mocked picker result, or a
source-code reference is not a pass for these checks.

Use one evidence root created beneath `%TEMP%` for the whole run. The backend
configuration, `LocalBase`, state, logs, source fixture, output fixture, and
WebView2 user-data folder must all resolve beneath that root. Stop if the
Settings overview or startup evidence resolves any personal, live-library,
network-share, or production scratch path. Keep all pipeline, publish, drain,
rename apply, cleanup, network lifecycle, and settings-save controls unused.

For every recipe, record: timestamp and Windows build; app commit/package;
temporary evidence-root path; control ID or accessible name; exact prerequisite;
selected/opened target; command ID and final status; screenshot or UIA output;
console/backend error text on failure; source/output fixture hashes before and
after; operator; and disposition (`passed`, `failed`, or `blocked`). Store the
record with the active audit evidence rather than in a personal path.

### NATIVE-01 — Windows file and folder pickers

Owner: Desktop/WebView QA.

Prerequisites:

1. Start the backend and WebView/Tauri shell with the isolated configuration
   described above. Create one empty folder and one harmless media-named fixture
   file beneath the temporary source fixture; do not copy real media.
2. Confirm no active work and capture the fixture hashes and current Settings
   candidate JSON.

Procedure and success criteria:

1. In Settings, activate one authored folder `Browse` badge. Verify a genuine
   Windows folder dialog appears. Select the temporary folder. The exact folder
   is staged in the intended field, `/api/path-picker/browse` or
   `/api/settings/browse-path` records success, and no Settings save occurs.
2. Activate the picker again and cancel. The prior staged value must remain and
   the result must say canceled rather than success.
3. On Launch, activate `pipeline-single-file-browse-button`, select the harmless
   temporary fixture, and verify only the single-file field is staged. No
   `/api/pipeline/start` request may occur. Repeat and cancel.
4. On Rename, test file and folder browse only. Selected temporary paths may be
   staged, but Preview, Apply, and Undo must remain unused.
5. Confirm the fixture hashes and source/output file counts are unchanged.

Failure capture: record dialog absence, wrong initial directory, cancellation
reported as success, a returned path outside the evidence root, wrong-field
staging, any automatic save/start/preview/apply request, or any changed hash.

### NATIVE-02 — Explorer and associated-application outcomes

Owner: Desktop/Windows integration QA.

Prerequisites: use only a backend fixture whose allowlisted open target resolves
to the temporary folder or harmless temporary file. Capture the target path and
hash first. Do not use a Queue row or diagnostic target backed by a personal or
live-library path.

Procedure and success criteria:

1. Activate an allowlisted `Open Folder` control. Verify Windows Explorer opens
   the exact temporary folder and the command result names the same allowlisted
   target. Closing Explorer must not change backend state.
2. Where an `Open File` outcome is applicable, activate it only for the harmless
   temporary fixture. Verify Windows reports the actual associated-application
   outcome honestly: opened, association prompt, or actionable failure. A
   browser POST success alone is insufficient.
3. Rename or move the fixture inside the evidence root, repeat the open action,
   and verify the UI reports the missing-target failure rather than claiming an
   external application opened. Restore the fixture only within the evidence
   root.
4. Confirm no file content, queue state, settings, or media lifecycle state
   changed.

Failure capture: record the OS window title/process, command result, selected
target, screenshot, backend/console error, and before/after hashes. Treat an
unobservable external outcome as `blocked`, not passed.

### NATIVE-03 — Pipeline Log secondary window

Owner: Tauri shell QA.

Prerequisites: Windows UI Automation, the Tauri toolchain, no active work, an
isolated backend configuration, and an isolated WebView2 folder. Set
`MEDIAPIPELINE_APPDATA_ROOT` and `WEBVIEW2_USER_DATA_FOLDER` to directories
beneath the temporary evidence root before launching. The probe must report the
same WebView2 root; otherwise stop.

Run the native probe from the repository root:

```powershell
.\apps\desktop\tauri\Test-TauriShell-WebViewUiAutomationProbe.ps1 -ExpectedWebView2UserDataFolder $env:WEBVIEW2_USER_DATA_FOLDER
```

Success criteria:

1. `Open Log Window` creates a distinct native window titled `Pipeline Log`.
2. UI Automation exposes `Follow`, `Pipeline Log display mode`, and `Refresh
   Now`; changing mode and refreshing updates the secondary content without a
   backend mutation POST.
3. Closing the Pipeline Log window destroys or hides only its distinct native
   handle. The main shell remains visible, navigable, and connected.
4. Closing the main shell afterward passes close-readiness and exact-process
   cleanup. No unowned process is terminated.

Failure capture: preserve the probe JSON, stdout/stderr log paths, inspected UIA
rows, both native window handles, content-accessibility blocker, close outcome,
and exact-process cleanup result. If the secondary WebView2 provider still does
not expose descendants or independent close remains unverified, retain the
ledger status as blocked/manual-native-only.

### NATIVE-04 — genuine shell failure paths

Owner: Tauri release QA.

Using only the isolated evidence root, separately exercise a missing/denied
temporary target, a canceled picker, an unavailable file association, and a
secondary-window open/close failure if it can be induced without changing
machine policy. Success means the UI stays responsive, reports the exact owning
failure and next action, writes no secret/raw personal path to shared evidence,
and cleans up only processes launched by the test. Do not change Windows-wide
permissions, default applications, network state, or playback-device settings
for this recipe; if those conditions are not already available, record them as
blocked prerequisites.

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
   - Any route not listed by the active `/api/contract` response or `docs/inventories/API_ROUTE_INVENTORY.md`

5. Verify that no JavaScript errors appear in the browser console related to unhandled rejections or missing backend responses.

---

## Smoke Tests vs. Manual Test

This script is for human observation. Automated equivalents:

| Page | Automated smoke |
|---|---|
| Current Work deterministic states/accessibility/responsive | `test_webview_browser_run_monitor_smoke.py` |
| Native Tauri Home/reopen name evidence | `Test-TauriShell-WebViewUiAutomationProbe.ps1 -HomeOnly` plus `test_tauri_shell_scaffold.py` |
| Backend Queue Run Once full journey | `Test-WebViewBrowserQueueLaunchCompletedSmoke.ps1` |
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

See `docs/testing/WEBVIEW_SMOKE_TEST_CATALOG.md` for the full catalog.

---

## See Also

- Mutation boundary: `docs/architecture/LOCAL_API_EVIDENCE_MUTATION_MATRIX.md`
- Historical mutation review: `docs/archive/docs-housekeeping/2026-05-20-review/archive-historical/docs/archive/completed-audits/WEBVIEW_APIPOST_MUTATION_REVIEW.md`
- No-touch boundaries: `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`
- Smoke test catalog: `docs/testing/WEBVIEW_SMOKE_TEST_CATALOG.md`
- Failure triage: `docs/operator/FAILURE_TRIAGE_WORKSHEET.md`
