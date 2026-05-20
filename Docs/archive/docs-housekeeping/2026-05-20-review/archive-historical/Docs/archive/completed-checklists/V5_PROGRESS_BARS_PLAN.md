# V5 Progress Bars Plan

Date: 2026-05-17  
Archived: 2026-05-19 after all P1-P7 work items were completed and recorded in the transition current plan.  
Workspace: `MediaPipelineRemuxEncodeAIO_V5`  
Current production shell: CustomTkinter desktop app  
Target surfaces: Tk, WebView/Tauri preview, local API, standalone mode, worker/coordinator mode

## Purpose

Add operator-visible progress bars wherever the backend has trustworthy progress evidence, without moving mutation authority into the frontend and without inventing fake percentages.

Progress bars must be backend-authored or derived from backend-authored runtime files. The WebView may render bars, labels, and stale/review warnings, but it must not decide media policy, queue scope, publish safety, worker lifecycle, or file mutation.

## Design Rules

- Determinate bars require a real numerator/denominator or a real backend percentage.
- Indeterminate bars are allowed for active work with no reliable denominator.
- Stepped bars are allowed for known gate sequences such as startup or health checks.
- Every progress bar needs a label, status, detail, source, and stale/blocked posture where available.
- Standalone and worker mode should share the same progress DTO shape.
- Tk and WebView should consume the same backend progress truth where practical.
- Progress is runtime evidence only. Completed, Pending Publish, sidecars, manifests, logs, and Sample Validation remain the proof surfaces.

## Progress DTO Shape

Each bar should use this shape:

```json
{
  "id": "current_stage",
  "label": "Current stage",
  "mode": "determinate",
  "percent": 42.5,
  "status": "active",
  "detail": "Encode CPU | Movie.mkv",
  "source": "pipeline_progress.json",
  "updated_at": "2026-05-17T00:00:00",
  "stale": false
}
```

Allowed `mode` values:

- `determinate`
- `indeterminate`
- `stepped`

Recommended status values:

- `active`
- `idle`
- `complete`
- `warning`
- `blocked`
- `unknown`

## Work Queue

### P1 - Snapshot Progress Bars

- [x] Add backend-authored `progress_bars` to `desktop_app_snapshot.v1`.
- [x] Build bars from existing `pipeline_progress.json` and `audit_progress.json`.
- [x] Include current encode/remux stage from `CurrentStagePercent`.
- [x] Include total run/queue progress from `CurrentQueueIndex / CurrentQueueTotal`.
- [x] Include publish state when `PushState` or publish-related stages are active.
- [x] Include audit progress from `percent_complete` and `processed_files / total_files`.
- [x] Render the bars in WebView `Run Progress`.
- [x] Keep the old field table as detailed evidence below the bars.
- [x] Add focused tests for the backend DTO and static WebView wiring.

### P2 - Publish Copy Progress

- [x] Add backend instrumentation for immediate publish copy bytes where possible.
- [x] Add backend instrumentation for pending-publish drain copy bytes where possible.
- [x] Distinguish per-file publish progress from total drain progress.
- [x] Use indeterminate mode when copy-byte telemetry is not available.
- [x] Preserve existing pending-publish safety behavior and manifest transaction boundaries.
- [x] Render per-file publish/push copy progress on the Dashboard At A Glance surface without showing total pending-publish progress there.

### P3 - Startup Progress

- [x] Add a startup/checkpoint progress object for local API and Tauri startup.
- [x] Suggested steps: resolve app root, resolve config, verify bundled PowerShell, verify FFmpeg/ffprobe, verify MKVToolNix, resolve state paths, load local API, validate contract, open shell.
- [x] Render startup progress in WebView/Tauri where available.
- [x] Keep startup failures actionable with exact failed step and source.

### P4 - Health Check Progress

- [x] Convert Maintenance health checks into a stepped progress surface.
- [x] Suggested steps: config parse, path reachability, state directory, PowerShell, FFmpeg, ffprobe, MKVToolNix, optional GPU telemetry, subtitle helper, pending-publish path.
- [x] Render progress while health check is running.
- [x] Report partial progress even when a later probe fails.

### P5 - Worker/Coordinator Progress

- [x] Normalize worker heartbeat progress into the shared progress-bar DTO.
- [x] Show worker current job progress, worker health, heartbeat age, and pending done-report posture.
- [x] Keep Network/WebView read-only until lifecycle mutation contracts are designed.
- [x] Support standalone mode with local-only bars and worker mode with local plus remote worker bars.

### P6 - Audit Reports Progress

- [x] Use existing audit `percent_complete` for scan progress.
- [x] Add stepped report-generation progress after scan: classify, write JSON, write CSV, write priority CSV, write text summary.
- [x] Render audit progress on Dashboard, Launch/Audit, Reports, and Diagnostics.

### P7 - Other Useful Progress Bars

- [x] Queue refresh/source scan: indeterminate now, determinate later if scanner emits candidate count.
- [x] Subtitle conversion/OCR: per-track stepped progress for extract, convert/OCR, validate, sidecar write.
- [x] Rename apply: files renamed / total planned.
- [x] Settings save/reload: stepped preview, write backup, write config, reload, validate.
- [x] Release package build: layout, copy, manifest, validate, optional smoke.
- [x] Maintenance backfill: records scanned / records written.
- [x] Completed/Pending inventory refresh: rows scanned / rows loaded when backend can report counts.

## Validation Plan

- Focused backend unit tests for progress bar DTO construction.
- Static WebView tests for `renderProgressBars` wiring.
- Browser smoke later for visible bars in Dashboard/Diagnostics.
- Release self-test after backend/frontend chunks.

## Progress Log

- 2026-05-17: Plan created. First implementation chunk selected: P1 snapshot progress bars using existing backend progress/audit files only.
- 2026-05-17: P1 implemented. `/api/snapshot` now includes backend-authored `progress_bars` for current pipeline stage, run total, publish output state, and audit progress when those source fields exist. WebView `Run Progress` renders the bars above the existing detailed progress table. Focused backend/static tests and the browser Home live-state smoke passed.
- 2026-05-17: P2 implemented. `Copy-FileRobocopy` now polls the robocopy staging file and persists backend-owned `CopyBytesCopied`, `CopyTotalBytes`, `CopyPercent`, copy source/destination, attempt, and timestamp into `pipeline_progress.json`. Immediate publish and pending-publish drain copy paths consume the same telemetry without changing copy/reveal transaction ownership. Pending publish drain now reports `CurrentQueuePhase=pending_push` with a real item index/total, so the WebView can show a per-file `Publish copy` bar and a separate `Pending publish total` bar. Focused Python tests, PowerShell parse checks, contract schema checks, full reliability regression, and release self-test with tool/end-to-end skips passed.
- 2026-05-17: P3 implemented. Local API startup now emits `desktop_startup_progress.v1` checkpoint payloads for app-root/config/path/tool/state/API/server startup work, Tauri launches the backend with startup progress enabled, `/api/health` and the WebView bootstrap can expose the latest startup progress, and WebView backend lifecycle detail renders the startup checkpoint lines. Focused backend/static/Tauri scaffold tests, JS syntax checks, `local_api_main --help`, `DesktopApp\tauri_shell\Test-TauriShell-Build.ps1`, and release self-test with tool/end-to-end skips passed.
- 2026-05-17: P4 implemented. Maintenance health now exposes `desktop_maintenance_health_progress.v1` with a stepped `maintenance_health` progress bar and backend-authored steps for config/path/state readiness, PowerShell, FFmpeg, ffprobe, MKVToolNix, optional GPU telemetry, subtitle helper, and pending-publish path posture. `/api/maintenance/progress` returns the latest progress without running probes, and the WebView Maintenance panel polls it while `/api/maintenance` is running before rendering the final stepped surface from the workspace payload. Focused DTO/API/contract/browser tests, telemetry callback tests, JS syntax checks, `DesktopApp\tauri_shell\Test-TauriShell-Build.ps1`, and the release self-test with tool/end-to-end skips passed.
- 2026-05-17: P5 implemented. `/api/network/workers` now includes `desktop_network_worker_progress.v1` plus shared `progress_bars` for network mode, persisted coordinator worker rows, local worker state, heartbeat/stale posture, and pending done-report warnings. The WebView Workers page renders those bars in the Worker State panel while preserving the read-only lifecycle boundary. Focused backend/static/browser Network tests, JS/Python syntax checks, and the release self-test with tool/end-to-end skips passed.
- 2026-05-17: P6 implemented. `audit_progress.json` now preserves backend-authored report-generation stage fields after scan completion (`report_stage`, `report_step_index`, `report_step_total`, `report_steps`, `report_completed_steps`) while keeping the existing audit `percent_complete` scan progress. `/api/snapshot` now emits both the scan bar and a stepped `Audit reports` bar when report progress exists. The WebView renders audit progress on Dashboard Run Progress, Launch > Audit Mode Start, Reports > Audit Progress, and Diagnostics > Current Progress. Focused backend/static tests, PowerShell parser and serialization checks, browser-backed Maintenance/Reports and Diagnostics smoke tests, JS/Python syntax checks, and the release self-test with tool/end-to-end skips passed.
- 2026-05-17: P7 queue refresh/source scan progress implemented. `/api/queue` now includes backend-authored `desktop_queue_source_scan_progress.v1` via `queue_progress` and shared `progress_bars`, using an indeterminate `queue_source_scan` bar with stale/warning/blocked posture from the queue snapshot and preview warnings. The WebView Queue panel renders the source-scan bar and read-only guardrail summary before the existing queue evidence. Focused queue policy/facade/static tests, JS/Python syntax checks, and browser-backed large-table Queue smoke passed.
- 2026-05-17: P7 subtitle conversion/OCR progress implemented. `pipeline_progress.json` now includes `SubtitleProgress` for current subtitle work with `pipeline_subtitle_progress.v1`, stream kind/index, stage, step index/total, completed steps, cue count, and failure/completion posture. ASS, TX3G, and BDPGS/OCR conversion paths update extract/convert-or-OCR/validate progress, TX3G SRT sidecar publish updates sidecar-write progress, and pipeline sidecar metadata write completes the subtitle bar where applicable. `/api/snapshot` converts this into a shared stepped `subtitle_track` progress bar. PowerShell parser checks, Python compile, subtitle progress serialization, focused snapshot progress test, and `Pipeline\Tests\Invoke-ReliabilityRegressionChecks.ps1` passed.
- 2026-05-17: P7 rename apply progress implemented. Backend `rename.apply` success results now include `desktop_rename_apply_progress.v1` plus a shared determinate `rename_apply` bar showing renamed files versus selected/planned files, unchanged/media/sidecar operation counts, source, and update time. The WebView Rename outcome review renders the bar from backend command data without adding retry, undo, arbitrary path, or frontend filesystem mutation authority. Python/JS syntax checks, focused rename facade/local API tests, and the browser-backed Rename smoke passed.
- 2026-05-17: P7 settings save/reload progress implemented. Backend Settings preview/save/reload command results now include stepped progress evidence for preview, backup write, config write, reload, and loaded-config validation. Save results are marked complete by the Local API only after the existing reload succeeds, while reload failures mark the reload/validate steps blocked. The WebView Settings save-result surface renders the shared progress bar from command data without adding frontend config persistence or policy bypasses. Python/JS syntax checks, focused settings facade/local API tests, browser-backed Settings/Launch smoke, and temp-config settings patch smoke passed.
- 2026-05-17: P7 release package dry-run progress implemented. Backend release dry-run results now include `desktop_release_package_progress.v1` with stepped layout, copy-plan, manifest, validate, and optional-smoke evidence. Because the WebView command remains dry-run only, manifest and smoke steps explicitly report planned/skipped posture instead of claiming artifacts were written. The WebView Maintenance Release Check renders the shared `release_package` progress bar from backend command data. Python/JS syntax checks, focused maintenance policy/facade/local API tests, and the browser-backed Maintenance/Reports smoke passed.
- 2026-05-17: P7 maintenance backfill progress implemented. Completed-manifest backfill dry-run results now include `desktop_maintenance_backfill_progress.v1` with records scanned, records that would be written, records actually written (zero for dry-run), skipped bad-JSON records, and a shared `maintenance_backfill` bar. The WebView Maintenance Manifest Backfill panel renders the bar without adding manifest rewrite authority. Python/JS syntax checks, focused maintenance policy/local API/static tests, and the browser-backed Maintenance/Reports smoke passed.
- 2026-05-17: P7 Completed/Pending inventory refresh progress implemented. Completed preview payloads now include `desktop_completed_inventory_progress.v1` and a shared `completed_inventory` bar for backend loaded manifest rows. Pending Publish preview payloads now include `desktop_pending_publish_inventory_progress.v1` and a shared `pending_inventory` bar for scanned/loaded pending rows. The Completed and Pending Publish WebView panels render those bars without changing table filtering, accept, publish/drain, open, or manifest mutation authority. Python/JS syntax checks, focused completed/local API/static tests, and browser-backed large-table Queue/Completed/Pending smoke passed.
- 2026-05-17: Full DesktopApp test discovery passed after completing P7 (`python -m unittest discover -s DesktopApp\tests -q`, 1200 tests). No unchecked progress-bar plan items remain.
- 2026-05-18: Dashboard per-file push progress follow-up implemented. At A Glance now renders a `Push file` progress bar from the backend-authored `publish_copy` bar when per-file publish-copy telemetry is present, and intentionally does not surface the total pending-publish drain bar there. Focused JS syntax, static WebView, and browser-backed Home live-state smoke tests passed.
