# Operator Glossary

Plain-language definitions of recurring terms in the MediaPipelineRemuxEncodeAIO V6 operator interface, documentation, and Diagnostics output.

---

## A

### ActiveJobs
A folder (`State\ActiveJobs\`) containing JSON records for each running or recently-launched pipeline, audit, or rerun process. The desktop app and WebView Home use these records to show what launched, when, where its logs are, and whether it finished. Do not delete records while a job is active. **Why it matters**: stale or missing ActiveJobs records make close-readiness and process-state harder to trust.

### Active Media Policy Boundary
The Launch page section that separates saved launch-active settings (the current PSD1 config that will govern the next run) from staged patch changes that have not yet been saved. Prevents operators from confusing what will actually run with what is still pending a save. Subtitle policy, audio policy, pending-publish candidates, and source-delete flags all appear in the Active Media Policy Boundary so an operator can confirm the saved posture before start.

### Apply Readiness (Rename)
A read-only pre-apply ledger in the WebView Rename page that shows whether the current checked/selected rename scope is safe to submit: no blocked rows, no duplicate targets, no existing-destination collisions. Apply Readiness is a frontend guard — the backend still validates independently and owns the final rename.

---

## B

### Backend-Owned
An action or state that only the Python/PowerShell backend may execute or decide. The WebView cannot resolve filesystem paths, start processes, move files, write config, or drain pending publish directly — it forwards requests with allowlisted parameters and the backend validates and executes. Mutation guardrails in the WebView block premature user actions; they are not a replacement for backend validation.

### Backend Scope
The set of rows, files, or manifests the backend will evaluate when a command is issued — regardless of what is currently visible in the WebView table. Display filters, render caps, and selected rows change the WebView's presentation but do not change backend scope. The Queue Backend Launch Scope Preview and Pending Backend Drain Scope Preview panels make this boundary explicit by showing loaded-row count versus visible-row count alongside the backend route authority.

### Backend-Owned Command
A POST route that causes the backend to execute a mutation (launch, drain, rename, settings save, shutdown). Contrast with read-only routes (GET) and preview routes (POST with no state change). All backend-owned commands require allowlisted parameters; the backend validates and re-executes independently of frontend state.

### Bounded-Health-Check
The effect classification for `GET /api/maintenance`. It runs existing environment/tool probes read-only and does not repair, write, or change anything. Not to be confused with a full real-media validation.

### Browser-Backed Smoke
A WebView smoke test that launches an installed Chrome or Edge browser headlessly and drives the real backend-served WebView page through Chrome DevTools Protocol (CDP). Browser-backed smokes test actual browser rendering, real JavaScript execution, and DOM interaction against a live temporary local API. Contrast with Node-based smokes, which evaluate backend-served JavaScript in Node without a real browser. There are 16 browser-backed smoke wrappers. All skip cleanly when Chrome/Edge is not installed.

---

## C

### CDP (Chrome DevTools Protocol)
The protocol used by browser-backed smoke tests to drive Chrome or Edge headlessly. The smoke runner (`webview_browser_smoke_support.py`) launches the browser on a free local port and communicates through CDP for page navigation, JavaScript injection, DOM queries, and element interaction. CDP is used in testing only and does not appear in production operator workflows.

### Close Readiness
The backend's authoritative answer to "is it safe to close the app right now?" Served by `GET /api/backend/close-readiness`. The Tauri shell checks this before closing the WebView window and issues shutdown via `POST /api/backend/shutdown` only when safe is confirmed. Close Readiness is unknown — not safe — when the pipeline is actively processing.

### Command Journal
An in-memory bounded FIFO log of recent POST command route results, kept by the local API. Displayed in WebView Command History and Diagnostics. Resets when the backend restarts. Not a durable audit log — it is session context for the current operator.

### Completed Manifest
`State\Completed\completed_jobs.jsonl`. The durable record of all successfully finished jobs: source path, output path, route reason, sidecar paths, audio/subtitle decisions, size. The WebView Completed page reads this. Do not delete it manually — rebuild only via `Backfill-CompletedManifest`.

### Continuous Schedule-Stop Watcher
A backend-owned monitor that tracks whether a continuous pipeline run should stop when its scheduled window closes. The watcher is armed when a continuous run starts; it issues a stop signal when the current time falls outside the configured schedule window. Visible in the Launch preflight as a readiness evidence row. An `Ignore Schedule` continuous start is flagged as a high-review intentional bypass. Does not fire during `run_once` starts or when schedule gates are not active.

---

## D

### Deferred Publish / Parked Output
When `DeferredPublish` is enabled and the output destination is not available (e.g., network share is down), the pipeline parks the finished output locally under `State\PendingServerPush\` instead of failing. The output is safe locally; it has not reached its final destination yet. See also: **Pending Publish**, **Drain**.

### Diagnostics Target
An allowlisted key name accepted by `POST /api/diagnostics/open` and `GET /api/diagnostics/tail`. The backend resolves the real filesystem path from the key; the WebView never passes raw paths. Examples: `last_stderr_log`, `queue_snapshot`, `active_jobs`. Full list in `Docs/operator/DIAGNOSTICS_READ_ONLY_TARGETS_RUNBOOK.md`.

### Direct Play
Plex terminology for a file the Plex Media Server can stream to a client without transcoding. H.264 video with compatible audio and subtitle tracks is typically Direct Play capable. The pipeline's remux path targets this. Files that require encoding may or may not be Direct Play after encode depending on the selected profile.

### Do Not Drain
A Pending Publish row classification that means the backend has determined it is unsafe to include this row in a drain operation. Reasons include unreadable manifests, missing payloads, missing sidecars, and orphan payloads. The WebView Publish Button Guard blocks drain when Do Not Drain rows are present.

### Display Filter
A local WebView table control (text, status, or investigation filter) that changes which rows are shown in the table. Display filters do not change backend scope — the backend still acts on all rows in its own state. Filter warnings appear when blocked or review rows are hidden by an active filter; these are not dismissed automatically. See also: **Backend Scope**, **Render Cap**.

### Drain
The act of publishing parked pending outputs to their final destination. Triggered by `POST /api/pipeline/start` with mode `drain_pending_pushes`. The backend validates each row, checks for Do Not Drain conditions, runs Robocopy, updates manifests, and records a drain summary. The WebView Pending Publish page shows the result.

---

## E

### Encode
Processing a video file through FFmpeg with a configured encoder (NVENC or CPU) to produce a new output file with a different codec or bitrate.

### Evidence-Only Panel
A read-only WebView panel that presents backend-served or cached state without issuing any mutation command. Evidence-only panels help the operator review state before deciding to launch, drain, rename, or append a validation note. Examples: Queue Backend Launch Scope Preview, Pending Backend Drain Scope Preview, Launch Start Decision Summary, Real-Media Output Proof ladder, Sample Validation Readiness. None of these panels can cause a backend mutation by themselves. Distinguished from remux (which copies streams). Encoding is slower, changes file size, and may lose quality if misconfigured.

---

## F

### Failure Marker
A file in `State\Failures\Markers\` written by the pipeline when a job fails permanently or needs operator review. The queue service reads markers to exclude the same source from future runs. Reports > Clear Retry Blockers previews and confirms backend marker cleanup so the source can be re-queued without touching media files.

---

## M

### Manifest (Pending Publish)
A JSON file in each `State\PendingServerPush\<batch>\` folder that describes one parked output: source path, output path, destination, sidecar paths, and state. The backend uses this to validate and plan drain operations. An unreadable or invalid-contract manifest is a Do Not Drain condition.

### Mutation Guardrail
A WebView-side block that prevents a destructive backend command from being submitted when pre-conditions are not met. Examples: Publish Button Guard (blocks drain when evidence is incomplete), Apply Readiness (blocks rename when blocked rows or duplicate targets exist), Settings save-readiness (blocks save when the patch has critical blockers). Mutation guardrails are local checks — the backend always re-validates independently.

---

## O

### Operator Evidence
Information an operator records manually or via the Sample Validation Record flow to document that a real-media run produced expected results. Operator evidence is not automatic acceptance — it does not clear failures, drain pending publish, update manifests, or mark jobs complete. See also: Sample Validation Record.

### Orphan Payload
A file under `State\PendingServerPush\<batch>\` that has no corresponding row in that batch's manifest. The WebView Pending Publish page flags orphan payloads as a Do Not Drain condition and advises checking Diagnostics before acting.

---

## P

### Parked Output
See **Deferred Publish**.

### Pending Publish
The state and UI page covering outputs that have been parked locally but not yet published to their final destination. Accessible under `State\PendingServerPush\` and via `GET /api/pending-publish`. The WebView Pending Publish page provides recovery dry-run, drain decision checklist, publish button guard, and selected-row diagnostics.

### Priority Marker
A string in the source file name or folder name (`!` or `[NOW]`) that causes the pipeline to process that file ahead of others in the queue. `!` is preferred over `[NOW]` per `PriorityMarkers` config.

### Publish Reconciliation
A backend-authored read-only correlation snapshot returned by `GET /api/publish-reconciliation`. It correlates Completed Manifest rows, current Pending Publish rows, and the latest durable pending-drain summary into a single evidence view. Accessible as a manual panel in the Completed page. Cannot mark jobs done, repair manifests, drain, delete, or touch media files. Use it to confirm that parked outputs have a matching Completed record and to investigate unexpected gaps between completed and published state.

---

## R

### Read-Only (WebView)
A WebView panel or action that presents data without issuing any mutation command to the backend.

### Render Cap
The maximum number of table rows the WebView renders for performance. Currently 250 rows. When more rows are loaded than the cap allows, a disclosure note appears stating that backend scope is not narrowed to the visible subset. Blocked or review rows beyond the cap may be hidden from view but are still within backend scope. See also: **Display Filter**, **Backend Scope**. Read-only panels fetch GET routes or display already-loaded payload data. They do not write config, launch processes, rename files, drain pending publish, or touch media.

### Remux
Processing a video file by copying its existing audio, video, and subtitle streams into a new container without re-encoding. Faster than encode, lossless for quality, but only available when existing streams are already compatible. The pipeline prefers remux over encode when the source meets Direct Play compatibility criteria.

### Recovery Plan (Pending Publish)
A backend-authored dry-run plan for a pending publish batch, returned by `POST /api/pending-publish/recovery-plan`. It describes what the drain would do, what it would skip, and what is blocking. No files are moved, drained, or changed. Use the recovery plan to review before triggering drain.

### Route Decision
The pipeline's per-file determination of whether to remux or encode, and why. Captured in the queue snapshot, completed manifest, and output sidecar. The route reason field explains which policy triggered the decision (e.g., size guard, profile, codec mismatch).

---

## S

### Selected Row
The WebView table row whose detail panel is currently shown on the right side of the page. Selecting a row is a local UI operation; it does not change backend scope, priority, or action state. The backend does not know which row the operator has selected — it acts on its own full snapshot when a command is issued. Selected-row detail in the Queue Backend Launch Scope Preview and Pending Backend Drain Scope Preview panels is labeled as a display-context note, not a scope-narrowing action.

### Sample Validation Record
An operator evidence record (`sample_validation_record.v1`) appended to `State\Validation\sample_validation_log.jsonl` via `POST /api/sample-validation/append`. Captures source, output, route, proof strength, and operator decision for one sample run. Does not mark jobs complete or clear failures. Visible in Diagnostics as `sample_validation_log`.

### Scratch
The temporary working area used by the pipeline during encode or remux. Files in scratch are in-progress. Scratch paths are config-defined. Do not delete scratch contents while the pipeline is running.

### Sidecar
A small JSON file written alongside a completed output (`<output>.mediapipeline.json`) or alongside a source/folder (`mediapipeline.folder.json`). Output sidecars carry route reason, audio/subtitle decisions, and size metadata. Folder sidecars can override routing or audio/subtitle policy for a folder.

### Stale Runtime State
Runtime files (queue snapshot, progress JSON, ActiveJobs, completed manifest) that were written by a previous session and have not been refreshed by a current run. The WebView Queue and Completed pages show snapshot age metadata. Stale state is not an error on its own, but it means the displayed data may not reflect the most recent reality.

---

## T

### Tauri / WebView2 Shell
The native V6 shell that wraps the Python backend in a Tauri/WebView2 window. The WebView remains a control and evidence surface; backend routes retain authority for filesystem mutation, settings save, launch, stop, rename apply, and pending-publish drain.

### V5 External Fallback
The separate V5 workspace retained outside this V6 folder for rollback if a V6 operator flow has not passed validation. V6 no longer carries the removed legacy desktop shell.

---

## V

### Validation Ladder
The ordered set of checks from quick syntax/unit tests up through real-media validation. Each rung proves a different layer: docs-only changes need only the release self-test; WebView JS changes need smoke tests; real-media routing changes need a sample run with route/output/sidecar evidence. See `Docs/testing/VALIDATION_LADDER_RUNBOOK.md`.

---

## Q

### Queue Route Proof
Evidence from the Queue page showing that a specific source file's route decision (remux or encode), route reason, media type, and source root are visible and match the operator's intent before a sample run. Queue route proof is the first link in the real-media acceptance chain: Queue → Completed → Pending Publish. A Queue row is not acceptance proof by itself — it shows what the pipeline decided for the source, not what the output looks like.

---

## Real-Media Proof Chain

How Queue, Completed, and Pending Publish evidence relate. No single panel alone proves real-media acceptance:

| Panel | What it proves | Does NOT prove |
|---|---|---|
| **Queue** (route proof) | Pipeline route decision, route reason, media type, blocked/excluded state for a source | That the output was produced, that it is correct, or that it was published |
| **Completed** (output proof) | A Completed Manifest entry exists for the source/output pair; sidecar/manifest fields are correct; size growth is explained; route agreement is confirmed | That Pending Publish was drained, that the file reached its destination, or that Sample Validation accepted it |
| **Pending Publish** (posture) | Parked output state, drain guard status, recovery dry-run plan | That the completed output is correct, that drain will succeed, or that Sample Validation has reviewed the output |

The full proof chain requires all three panels to agree **and** a Sample Validation record to document the operator's conclusion. The Completed Real-Media Output Proof ladder on the Completed page rolls all three into one view, but reading the ladder does not replace the operator's independent inspection.

---

## Addendum — 2026-05-15 (CLN4-026)

Added scope-related terms: **Backend Scope**, **Backend-Owned Command**, **Display Filter**, **Evidence-Only Panel**, **Render Cap**, **Selected Row**.

```
Task ID: CLN4-026
Files inspected: Docs\operator\OPERATOR_GLOSSARY.md, Docs\operator\WEBVIEW_SCOPE_PREVIEW_OPERATOR_GUIDE.md
Files changed: Docs\operator\OPERATOR_GLOSSARY.md (6 new scope terms added)
Validation: Select-String -Path Docs\operator\OPERATOR_GLOSSARY.md -Pattern "Backend Scope|Display Filter|Render Cap|Selected Row|Evidence-Only Panel"
Findings: All 6 terms were absent; each is now defined with cross-references.
Open questions: None.
Risk: Low — documentation only.
```

### Safe Next Action
A backend-authored recommendation in the Sample Validation evidence packet and readiness payload that tells the operator what to do before appending a validation record. Values: `inspect_and_append` (all checks visible), `inspect_before_append` (optional check missing), `wait_for_completion` (run not done), `review_before_append` (discrepancy found). The backend does not block append if the operator proceeds anyway — the recommendation is guidance only.

### Stop Condition
A specific state that blocks a planned action: e.g., the Publish Button Guard's stop condition is a "Do Not Drain" row being present; the Sample Validation append readiness stop condition is a hard error in the preview payload. Stop conditions appear as named blocking reasons in their respective panels so the operator knows which specific issue to resolve.

---

## See Also

- Operator copy vocabulary: `Docs/operator/TERMINOLOGY_CONSISTENCY_GUIDE.md`
- Diagnostics targets: `Docs/operator/DIAGNOSTICS_READ_ONLY_TARGETS_RUNBOOK.md`
- Runtime artifact paths: `Docs/inventories/RUNTIME_ARTIFACT_INVENTORY.md`
- API route mutation risk: `Docs/architecture/LOCAL_API_EVIDENCE_MUTATION_MATRIX.md`
- No-touch boundaries: `Docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`
- Evidence packet field reference: `Docs/sample-validation/SAMPLE_VALIDATION_PAYLOAD_SCHEMA_REFERENCE.md`
- Operator record guide: `Docs/sample-validation/SAMPLE_VALIDATION_RECORD_OPERATOR_GUIDE.md`

---

## Addendum — 2026-05-15 (CLN3-020, CLN3-021)

Added:
- **Queue Route Proof** entry (CLN3-020)
- **Real-Media Proof Chain** section — explains that Queue, Completed, and Pending Publish each prove one link and none alone is acceptance proof (CLN3-021)
- **Safe Next Action** entry (CLN3-020)
- **Stop Condition** entry (CLN3-020)
- Fixed **Browser-Backed Smoke** wrapper count from 11 to 15 (CLN3-013)

```
Task IDs: CLN3-020, CLN3-021
Files changed: Docs\operator\OPERATOR_GLOSSARY.md (Queue route proof, Real-Media Proof Chain, Safe Next Action, Stop Condition entries added; Browser-Backed Smoke count corrected)
Validation: Select-String -Path Docs\operator\OPERATOR_GLOSSARY.md -Pattern "Queue route proof|Completed output|Pending Publish posture|stop condition"
Risk: Low — documentation only.
```
