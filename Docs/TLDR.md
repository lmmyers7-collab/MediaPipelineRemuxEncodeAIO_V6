# MediaPipelineRemuxEncodeAIO V6 TLDR

For code/AI work, read `CURRENT_PROJECT_STATE.md`, `..\V6_SPLIT_NOTES.md`, and `..\OPEN_WORK_CHECKLIST.md` before old audits, handoff files, or historical checklists. For documentation cleanup context, see `..\DOCS_HOUSEKEEPING_AUDIT.md`, `..\DOCS_HOUSEKEEPING_CHECKLIST.md`, and `ARCHIVED_MD_INDEX.md`.

## What This Is

MediaPipelineRemuxEncodeAIO V6 is the active WebView-first split from the V5 transition workspace. It remains a portable Windows-first operator console for a personal Plex-style media library. It routes files through remux or encode, cleans up subtitles, normalizes incompatible audio, audits the library, manages queue priority, schedules runs, parks completed outputs when publishing is not safe, and drains parked outputs later.

It is not a cloud service, metadata scraper, acquisition tool, or multi-user commercial platform.

## Daily Use

From the bundle root:

1. Run `Start-MediaPipelineRemuxEncodeAIO-ApiAndBrowser.bat` for the backend-served WebView.
2. Use `Start-MediaPipelineRemuxEncodeAIO-TauriPreview.bat` when validating the native WebView2 shell.
3. Use the WebView for Start Continuous, Run Once, Pause, Stop, Kill + Quit, Refresh Queue, Audit, CSV Rerun, Reports Clear Retry Blockers, and Publish Parked Outputs after the relevant validation gates pass.
4. Use **Maintenance -> Pending Publish** to inspect parked outputs, sidecars, manifest state, missing payloads, and orphan payload files before draining.
5. Use the standalone **Rename** tab for pre/post file renaming. TV mode supports selected-order season numbering; Movie mode shows scrubbed/pipeline predictions, per-row final names, forced pipeline-name sidecars, selectable built-in scrub filters, custom negative terms, an Apply Readiness ledger, explicit large-batch render-cap wording before backend-owned apply, and an Apply Outcome Review after backend results are available.
6. Use **Settings -> Video / Audio / Subtitles** to adjust routing profile, size guard, encode presets, audio passthrough/transcode policy, and subtitle conversion behavior.
7. Use `Setup-MediaPipelineRemuxEncodeAIO.bat` when changing config paths or major settings.
8. Use `Verify-MediaPipelineRemuxEncodeAIO-Environment.bat` when moving machines or troubleshooting missing tools.

## Tauri/WebView2 Shell

The V6 folder no longer carries the removed desktop shell. The local API/WebView path is active here, with V5 retained externally as the rollback/fallback workspace until V6 package-mode and real-media validation are complete.

From the bundle root:

```powershell
.\Start-MediaPipelineRemuxEncodeAIO-TauriPreview.bat -CheckOnly
.\Start-MediaPipelineRemuxEncodeAIO-TauriPreview.bat
```

Use `-InstallNodePackages` the first time the preview dependencies need to be installed.

Preview/build/release checks prove shell and package readiness only. Before treating WebView as a daily-driver path, run the observational checklist in `sample-validation/V5_REAL_MEDIA_VALIDATION_PLAYBOOK.md` against a small known media batch and compare Queue, Completed, Diagnostics, and Pending Publish evidence.

To create a timestamped run worksheet before a sample batch:

```powershell
.\New-RealMediaValidationWorksheet.ps1 `
  -SamplePath "D:\Samples\Movie.mkv" "\\SERVER\TV\Show\S01E01.mkv" `
  -SampleCategory "h264-remux-safe,subtitle-bearing" `
  -ExpectedRoute "remux,remux-plus-srt" `
  -QueueSnapshotPath "E:\Videos\Scratch\State\Progress\queue_snapshot.json" `
  -Shell "WebView preview"
```

The worksheet helper writes Markdown evidence only under `Docs\RealMediaValidationRuns` by default. It can prefill sample category, expected route, and Queue Evidence rows from an existing queue snapshot, and includes a WebView pilot-evidence-packet capture table. It does not launch the app, process media, save settings, rename files, publish outputs, drain pending publish, mutate queue state, or touch source/output/scratch paths.

The WebView Home Cross-Page Context panel includes a backend-owned Sample Validation Record flow. It shows backend-authored readiness guidance, stale-evidence reconciliation, a read-only real-media pilot plan, a real-media validation audit roll-up, a real-media policy-alignment roll-up, an operator sample execution checklist, generated pilot worksheet evidence from `Docs\RealMediaValidationRuns`, preview-time pilot evidence packet, preview-time append-readiness/manual-check gaps, and a manual Acceptance Checklist before append. The generated worksheet panel lists bounded Markdown worksheet rows, sample rows, pilot packet rows, and whether the currently selected sample appears in a generated worksheet. The validation audit condenses readiness, reconciliation, worksheets, category coverage, policy alignment, evidence gaps, pilot runbook, and cutover posture into one conservative status. Policy alignment maps saved Settings media-policy readiness to the H.264 remux, subtitle-to-SRT, audio routing, encode/size, and deferred-publish pilot categories before any pilot evidence is trusted. The execution checklist separates before-launch sample/policy checks, the backend-owned Launch boundary, post-run Completed/Diagnostics/Pending Publish proof, and evidence-record steps. The pilot evidence packet summarizes the proposed sample's Queue route proof, Completed output/sidecar proof, Diagnostics/run-log proof, Pending Publish posture, playback/subtitle/audio/size proof, stop conditions, and safe next action before an evidence note is recorded. The Home Real-Media Validation Worksheet now also carries Sample Validation posture beside Queue, Completed, Pending Publish, Diagnostics, and Settings evidence. Launch mirrors that worksheet in a read-only Real-Media Sample Proof Handoff, includes generated-worksheet and Sample Validation record checkpoints showing whether the selected sample has matching worksheet/record evidence, mirrors saved policy alignment against the selected/representative Queue route, and also mirrors the sample execution checklist at the start surface, so the operator sees both the post-run proof chain and the specific before/during/after sample-run checklist before starting a small sample. These panels can append evidence-only JSONL notes under `State\Validation`, but they do not mark anything accepted, clear failures, publish files, rewrite manifests/sidecars, launch work, scan arbitrary media folders, or touch media.

The WebView Launch page also includes a compact `Start Decision Summary` directly above the Pipeline Start controls. It rolls up Launch readiness, timing/schedule posture, backend preflight, Queue Launch Decision, Settings/policy state, Launch Scope Reconciliation, real-media proof, sample execution checklist, and recent Launch command evidence before the operator presses Start. It is read-only and cannot launch, save settings, drain, publish, rename, rewrite queue state, or touch media; backend start routes remain final authority.

The WebView Launch page now includes an `Active Media Policy Boundary` under Saved Settings Trust. It shows the saved subtitle/container, audio, and pending-publish/source-safety policy that Launch would use now, then compares any staged Settings Changes JSON candidate and marks it as not launch-active until backend Preview Patch, Save Patch, and reload/refresh succeed.

The WebView Settings page now includes an `Effective Policy Trust` panel inside Patch Preview. It states that the launch-active source of truth is the saved backend config, treats visible builder values and Changes JSON as inactive candidates, checks whether Preview/Save evidence matches the current JSON, and gives the next safe operator action before any settings change is trusted.

The WebView Launch backend preflight now includes a `Continuous schedule-stop watcher` row. Normal scheduled WebView `continuous` starts can arm a backend watcher that writes the regular stop flag at the schedule boundary when a current window end is reported. `Ignore Schedule` is still a high-review bypass and does not arm that watcher.

The WebView Schedule and Launch pages now also display the current backend watcher state from `/api/schedule`, including idle/armed/completed/canceled/stop-requested/error status, PID, deadline, message, and errors. This is read-only visibility; only backend launch/control logic can arm the watcher or write stop flags.

Close-readiness now treats an armed schedule-stop watcher as active work. If the watcher is armed, closing the WebView/Tauri shell should show a warning rather than looking safe, because shutting down the local API would remove the future stop-at-schedule-boundary guard.

Diagnostics and Backend Lifecycle now receive that watcher state as structured evidence in close-readiness and shutdown command history. A blocked shutdown should show watcher status, PID, deadline, stop-request state, and a safe next step rather than only a generic active-work warning.

`Test-WebViewBrowserLifecycleSmoke.ps1` now validates that path in Chrome/Edge against the real backend-served WebView. It proves watcher-armed shutdown stays disabled without confirmation/backend POST, terminal `stop_requested` watcher evidence is visible without blocking safe close, and safe close-readiness posts only the backend-owned shutdown command after confirmation.

`Test-LocalApiLifecycleContractSmoke.ps1` validates the same backend route contract without Chrome/Edge. It starts temporary token-protected local API instances, checks safe and watcher-blocked `/api/backend/close-readiness` payloads, verifies `/api/backend/shutdown` token enforcement, and exercises direct shutdown POSTs only against temporary test backends.

The native Tauri close prompt also consumes the structured watcher evidence. If the schedule-stop watcher is armed, the prompt should show watcher status, PID, deadline, stop-request state, bounded message/error text, and warn that closing the backend removes the in-process stop-at-schedule-boundary guard.

The WebView Pending Publish page now carries active display-filter scope into Drain Action Confidence, Drain Decision Checklist, and Publish Button Guard. If rows are hidden by text/status/investigation filters, the guard states that backend Publish Parked Outputs still sees all parked pending state, not only the visible table subset.

The WebView Rename page now includes an `Apply Outcome Review` under Last Apply Result. It summarizes backend `rename.apply` result status, selected scope, applied rows, media/sidecar operations, undo manifest evidence, warnings/errors, local Paths textarea update evidence, and the backend-only mutation boundary. It is read-only and cannot rename, undo, retry, delete, rewrite sidecars, or touch files.

Queue and Pending Publish now also include explicit `Backend Launch Scope Preview` and `Backend Drain Scope Preview` panels. These summarize loaded rows, visible filtered rows, selected-row boundaries, backend route authority, recent command evidence, and durable drain/preflight evidence so the operator can see exactly what the backend will evaluate versus what the table is merely showing. They are read-only and cannot launch, drain, publish, rename, save, rewrite state, delete files, or touch media.

Queue Launch Decision, Completed Output Acceptance, and Pending Publish Drain Decision summaries now lead with daily-use handoff wording. They state the operator outcome, where the real action belongs, and that filters, selected rows, proof boards, recovery dry-runs, and row caps do not narrow backend launch/drain scope, accept outputs, delete files, rerun jobs, repair manifests, or publish files.

The WebView Completed page now includes a read-only `Real-Media Output Proof` ladder for the selected completed row. It compares output/sidecar proof, route/size/media decisions, Pending Publish/drain posture, Diagnostics/runtime evidence, Sample Validation handoff evidence, and mutation boundaries before trusting a sample, but it cannot accept, rerun, drain, repair, publish, delete, rewrite manifests, append validation records, or touch media.

The WebView Diagnostics page now includes an `Owning Page Evidence Handoff` panel that points flagged Queue, Completed, and Pending Publish rows back to their owning page before launch, rerun, drain, cleanup, or acceptance decisions. Its `Go To Owner Row` control is local UI selection only; file opens and mutation commands stay backend-owned on the owning page. Diagnostics also includes an API Contract `Contract Safety Review` that reads `/api/contract` and classifies auth, mutation, shell-open, preview/dry-run, read-only, completeness, and frontend ownership boundaries without posting command routes.

The WebView Diagnostics page also includes a `First Response Checklist` near the top of the page. It summarizes refresh payload health, close-readiness/active work, ActiveJobs/progress evidence, state artifact read order, recent command issues, owning-page handoffs, log/malformed-state clues, and the mutation decision boundary. Rows are selectable and explain why the gate matters, what evidence was used, and where to inspect next. The checklist is read-only and cannot launch, drain, save settings, rename, repair, delete, publish, clear state, open arbitrary paths, or touch media.

Queue, Completed, and Pending Publish selected-row details now include combined review plans when multiple warning signals overlap. The plans tell the operator which evidence to read first, which owner pages to cross-check, and which action should stay blocked or reviewed before launch, rerun, drain, cleanup, or acceptance. This is presentation-only WebView guidance; it does not move mutation authority into the frontend.

Queue, Completed, and Pending Publish now also show a compact `Selected Row At A Glance` strip above the longer details. It summarizes the selected row's trust/status, route/output/drain proof, primary concern, safe next step, current filter visibility, and backend authority boundary. These strips are read-only and cannot launch, rerun, drain, repair, reconcile, rename, publish, delete, rewrite manifests, or touch media.

The browser-backed WebView smoke tests share common Chrome/Edge discovery, generated CDP runner setup, bounded timeout/failure reporting, JSON result parsing, and bounded browser termination. A failing smoke should include the runner return code plus bounded stdout/stderr and the browser-side exception detail, while browser stdout/stderr is not left as an undrained pipe. The shared runner retries once only for a no-output Windows native runner crash (`3221226505` / `-1073740791`) or no-output CDP WebSocket open transient; real assertion output is not retried away.

## New User / Deployable Package

Keep your normal V6 folder personal while V5 remains the known-good external fallback. V6 can keep your live config at:

- `Pipeline\MediaPipeline_config_chatgpt.psd1`

When you want a clean new-user package, run:

```powershell
.\Build-MediaPipelineRemuxEncodeAIO-Release.ps1 -Zip
```

The WebView Maintenance surface exposes the same release builder under **Maintenance -> Release Package**. Use **Plan Only** for a dry run; use **Build Package** after confirming destination/options.

For a verified engineering handoff package:

```powershell
.\Build-MediaPipelineRemuxEncodeAIO-Release.ps1 -Zip -Verify -IncludeTests
```

Default release behavior:

- strips `Pipeline\MediaPipeline_config_chatgpt.psd1`
- includes `Pipeline\MediaPipeline_config_template.psd1`
- includes the release builder and release self-test scripts
- excludes logs, app state, run logs, config backups, Python bytecode, assistant metadata, and dev-only checklist docs
- excludes local Tauri/WebView2 build artifacts such as `node_modules`, `src-tauri\gen`, and Rust `target`
- excludes optional tool bulk such as `ffplay.exe`, MKVToolNix GUI/diagnostic utilities, tool docs, and examples
- writes `release_manifest.json`
- release self-test validates the manifest and fails default packages that accidentally include live config, run logs/state, or optional tool bulk

Use `-IncludeOptionalTools` or `-IncludeToolDocs` only for a fuller maintenance package. Use `-KeepPersonalConfig` only for a private backup or machine-to-machine mirror.

## Important Paths

- Local API/WebView app: `DesktopApp\mediapipeline_desktop_app`
- Backend pipeline: `Pipeline\MediaPipeline_chatgpt.ps1`
- Config wizard: `Pipeline\Setup-MediaPipeline_chatgpt.ps1`
- Live config: `Pipeline\MediaPipeline_config_chatgpt.psd1`
- New-user template: `Pipeline\MediaPipeline_config_template.psd1`
- Pipeline modules: `Pipeline\Modules`
- Tests: `Pipeline\Tests`
- Bundled PowerShell: `Pipeline\PowerShell-7.6.0-win-x64\pwsh.exe`
- Bundled Python: `DesktopApp\Runtime\Python\python.exe`
- Bundled tools: `Pipeline\Tools`

## Runtime State

Most runtime state lives under `LocalBase\State`:

- `State\Progress`: progress JSON, queue snapshot, pipeline events
- `State\Pipeline`: pause, stop, and rescan control flags
- `State\ActiveJobs`: desktop launch records
- `State\Completed`: completed jobs manifest
- `State\Failures`: failure markers, artifacts, reports, clear manifests
- `State\PendingServerPush`: parked outputs waiting for publish

Legacy paths directly under `LocalBase` are migrated when possible.

The desktop **Maintenance -> Pending Publish** tab is the quickest way to inspect `State\PendingServerPush` without opening manifest JSON by hand.

## Behavior Worth Knowing

- Queue preview is pipeline-authored and uses `-EmitQueuePlan`.
- Priority markers are `!` and `[NOW]`; `!` is preferred.
- Deferred publish parks verified outputs locally and drains them later.
- Routing defaults to Plex Direct/Stream. H.264 sources that are already Plex-compatible can remux/copy by default instead of being encoded only because they are small release files.
- Encode growth checks support advisory, strict, and off modes.
- Output sidecars, pending manifests, and structured events carry route reason and route-plan metadata.
- Folder-level `mediapipeline.folder.json` sidecars can override routing, audio, and subtitle policy for a show/season/movie folder after validation.
- Output destination low-space parking is not counted as a real processing failure.
- BDPGS OCR is optional and depends on PgsToSrt plus tessdata.
- Audio policy supports named passthrough profiles, transcode codec/bitrate, downmix mode, max channels, default language preferences, and explicit no-audio opt-in.
- The V6 WebView Settings workspace exposes backend-authored media-policy readiness rows for saved route/size, subtitle, audio, pending publish, and source-preservation posture; this is read-only and does not replace backend Preview/Save or Launch validation.
- The V6 WebView Settings patch editor shows a Staged Media Policy Delta comparing current saved values against the local Changes JSON candidate across routing, video, subtitles, audio, publish safety, runtime, and network posture before backend Preview/Save; Launch unsaved-settings warnings echo that status while still using saved backend settings only.
- The V6 WebView Settings patch editor shows a Backend Preview / Save Result handoff with selectable row details, so operators can inspect whether backend preview/save evidence matches the current staged Changes JSON, including warnings, errors, redacted diff, risk summary, backup path, and reload proof before trusting a config edit.
- The V6 WebView Completed page has a manual Backend Publish Reconciliation panel. It asks the backend to correlate Completed Manifest rows with current Pending Publish rows and the latest durable drain summary, but it remains read-only and cannot mark done, repair, drain, publish, rewrite manifests, or touch media.
- Reports Clear Retry Blockers is constrained to backend failure markers, writes a clear manifest, and moves marker JSON out of the active marker folder so the next queue build can retry those sources.
- Kill + Quit verifies process-tree termination and clears known runtime control/progress artifacts.

## Fast Checks

```powershell
.\Verify-MediaPipelineRemuxEncodeAIO-Environment.bat
.\Pipeline\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File .\Test-MediaPipelineRemuxEncodeAIO-Release.ps1
.\Pipeline\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File .\Pipeline\Tests\Invoke-ReliabilityRegressionChecks.ps1
.\Pipeline\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File .\Pipeline\Tests\Invoke-ToolIntegrationChecks.ps1
```

`Invoke-ReliabilityRegressionChecks.ps1` is the active V6 compatibility wrapper: it runs WebView/backend checks by default and only runs archived legacy desktop-shell checks when explicitly invoked with `-RunLegacyDesktopChecks`.

Use `Start-MediaPipelineRemuxEncodeAIO-LocalApi.bat` or `Start-MediaPipelineRemuxEncodeAIO-ApiAndBrowser.bat` when the WebView will not open and you need backend import/startup errors to stay visible.

For operator terminology, see `Docs/operator/OPERATOR_GLOSSARY.md`. For the ordered validation ladder (what to run before treating WebView as a production path), see `Docs/testing/VALIDATION_LADDER_RUNBOOK.md`. When investigating a pipeline failure, start with `Docs/operator/FAILURE_TRIAGE_WORKSHEET.md` to capture evidence before taking recovery actions.

For browser/Tauri backend work, use `Start-MediaPipelineRemuxEncodeAIO-LocalApi.bat`. It starts the token-protected localhost API without opening the browser or native shell.

For the WebView command-evidence runtime smoke, run:

```powershell
.\SmokeTests\Test-WebViewCommandEvidenceSmoke.ps1
```

This starts a temporary local API, evaluates backend-served WebView JavaScript with mocked DOM state, and verifies shared command owner/issue evidence across daily-use panels. It also verifies selected-command owner live-state handoff against cached Queue/Completed/Pending Publish evidence and Pending Publish drain guard state before retry guidance. It does not launch, process media, publish, rename, save settings, mutate queue state, or touch source/output/scratch paths.

For the WebView rename readiness smoke, run:

```powershell
.\SmokeTests\Test-WebViewRenameReadinessSmoke.ps1
```

This evaluates the Rename WebView assets in Node with mocked DOM state and verifies Apply Readiness for a ready single-row scope, 260-row render-cap disclosure, and a blocked duplicate-target scope. It does not call `rename.apply`, rename files, save settings, process media, mutate queue state, or touch source/output/scratch paths.

For the browser-backed Rename smoke, run:

```powershell
.\SmokeTests\Test-WebViewBrowserRenameSmoke.ps1
```

This starts a temporary local API, opens the real backend-served WebView page in installed Chrome/Edge headless, clicks Rename preview rows and Check Applicable Rows, verifies Apply Readiness, verifies 260-row render-cap disclosure, and verifies duplicate-target apply blocking does not call `rename.apply`. It skips cleanly if Chrome/Edge is unavailable and does not process media, launch pipeline commands, publish, save settings, mutate queue state, or touch source/output/scratch paths.

For the WebView selected-row detail runtime smoke, run:

```powershell
.\SmokeTests\Test-WebViewRowDetailSmoke.ps1
```

This starts a temporary local API, evaluates backend-served WebView JavaScript with mocked DOM selected-row state, and verifies Queue, Completed, and Pending Publish row detail plus diagnostics handoff text, including adversarial blocked/missing/do-not-drain rows. It does not launch, process media, publish, rename, save settings, mutate queue state, or touch source/output/scratch paths.

For the WebView schedule smoke, run:

```powershell
.\SmokeTests\Test-WebViewScheduleSmoke.ps1
```

This evaluates Schedule WebView assets in Node with mocked DOM state and verifies Schedule Coverage Review, selected day detail, weekly status legend, the backend-owned Schedule Editor, staged clear behavior, preview/save command routing, and app-state-write result copy. It does not start pipeline commands, override schedule gates, mutate queue state, touch media files, or write app state from the frontend; schedule saves remain backend-owned and confirmed.

For the browser-backed Schedule editor smoke, run:

```powershell
.\SmokeTests\Test-WebViewBrowserScheduleSmoke.ps1
```

This starts a temporary local API, opens the real backend-served WebView in installed Chrome/Edge headless, drives Schedule Editor preview/save controls, verifies the confirmed backend app-state write is limited to schedule keys, verifies command-history ownership, and verifies Launch timing trust refreshes from the saved schedule payload. It skips cleanly if Chrome/Edge is unavailable and does not process media, launch pipeline commands, publish, rename files, save settings, mutate queue state, or touch source/output/scratch paths.

For the browser-backed backend lifecycle smoke, run:

```powershell
.\SmokeTests\Test-WebViewBrowserLifecycleSmoke.ps1
```

This starts temporary local API instances, opens the real backend-served WebView in installed Chrome/Edge headless, verifies watcher-armed close-readiness disables backend shutdown without confirmation/backend POST, verifies terminal stop-requested watcher evidence stays visible without blocking safe close, and verifies safe close-readiness posts the backend-owned shutdown request only after confirmation. It skips cleanly if Chrome/Edge is unavailable and does not process media, launch pipeline commands, publish, rename files, save settings, mutate queue state, drain pending publish, or touch source/output/scratch paths.

For the browser-free local API lifecycle contract smoke, run:

```powershell
.\SmokeTests\Test-LocalApiLifecycleContractSmoke.ps1
```

This starts temporary token-protected local API instances and validates close-readiness plus backend-shutdown route contracts for safe and watcher-blocked states. The safe state can request shutdown; the watcher-blocked state must return a backend-authored failure instead of scheduling shutdown. It does not open a browser, process media, launch pipeline commands, publish, rename files, save settings, mutate queue state, drain pending publish, or touch source/output/scratch paths.

For the browser-free local API Maintenance dry-run contract smoke, run:

```powershell
.\SmokeTests\Test-LocalApiMaintenanceDryRunContractSmoke.ps1
```

This starts a temporary token-protected local API and executes only the backend-owned Maintenance release/backfill dry-run POST routes. It validates token enforcement, command history, no release manifest/zip output, no completed-manifest rewrite, and unchanged temp source/output bytes.

For the browser-free local API Sample Validation contract smoke, run:

```powershell
.\SmokeTests\Test-LocalApiSampleValidationContractSmoke.ps1
```

This starts a temporary token-protected local API and exercises only the sample-validation preview/append/read routes plus the allowlisted diagnostics tail for the validation log. It validates strict JSON handling, token enforcement, current-backend-evidence preview, command history, and temp-only validation-log writes without accepting outputs, clearing failures, publishing, launching, probing media, or touching source/output/scratch paths.

For the browser-backed high-risk row smoke, run:

```powershell
.\SmokeTests\Test-WebViewBrowserHighRiskSmoke.ps1
```

This starts a temporary local API, opens the real backend-served WebView page in installed Chrome/Edge headless, and validates injected plus backend-produced blocked Queue, broken Completed, and do-not-drain Pending Publish selected-row guidance. It skips cleanly if Chrome/Edge is unavailable and does not launch, process media, publish, rename, save settings, mutate queue state, or touch source/output/scratch paths.

For the browser-backed diagnostics handoff smoke, run:

```powershell
.\SmokeTests\Test-WebViewBrowserDiagnosticsHandoffSmoke.ps1
```

This starts a temporary local API, opens the real backend-served WebView page in installed Chrome/Edge headless, clicks actual Queue/Completed/Pending table rows, verifies selected-row investigation signals/current-filter visibility, verifies text/status/investigation table filters warn when blocked/warning rows are hidden, verifies local clear-filter buttons restore selected-row visibility, clicks read-only diagnostics bridge, bounded tail, and allowlisted open controls, validates Diagnostics ActiveJobs active/malformed row detail plus stale runtime-progress guidance, validates Diagnostics State Artifact Summary read-order/artifact detail, validates selected-row detail plus diagnostics.open command-result feedback, verifies Diagnostics `Go To Owner Row` handoff navigation for Queue, Completed, and Pending Publish without backend commands, and verifies the API Contract Safety Review summary/detail from `/api/contract`. It skips cleanly if Chrome/Edge is unavailable and does not launch, process media, publish, rename, save settings, mutate queue state, post command routes from the contract safety panel, or touch source/output/scratch paths.

For the browser-backed Pending Publish drain guard smoke, run:

```powershell
.\SmokeTests\Test-WebViewBrowserPendingDrainGuardSmoke.ps1
```

This starts a temporary local API, opens the real backend-served WebView page in installed Chrome/Edge headless, injects a backend-shaped blocked recovery dry-run result, verifies the final Publish Button Guard refreshes immediately, clicks `Publish Parked Outputs`, and proves the blocked click records local `frontend_guard` evidence without posting `/api/pipeline/start` or asking for confirmation. It skips cleanly if Chrome/Edge is unavailable and does not launch, process media, drain pending publish, publish, rename, save settings, mutate queue state, or touch source/output/scratch paths.

For the browser-backed Completed/Pending proof smoke, run:

```powershell
.\SmokeTests\Test-WebViewBrowserCompletedPendingProofSmoke.ps1
```

This starts a temporary local API, opens the real backend-served WebView page in installed Chrome/Edge headless, verifies Completed-to-Pending proof detail for exact completed-output to pending-destination overlap, verifies selected Pending row Completed Manifest correlation, verifies the Completed saved-policy reconciliation and Sample Validation handoff checkpoints, verifies missing-output-without-proof blocker detail, and confirms same-leaf proof remains duplicate-title guidance rather than publish proof. It skips cleanly if Chrome/Edge is unavailable and does not append validation records, launch, process media, drain pending publish, publish, rename, save settings, mutate queue state, or touch source/output/scratch paths.

For the browser-backed large daily-table smoke, run:

```powershell
.\SmokeTests\Test-WebViewBrowserLargeTableSmoke.ps1
```

This starts a temporary local API, opens the real backend-served WebView page in installed Chrome/Edge headless, injects 260-row Queue, Completed, and Pending Publish payloads, verifies the 250-row render cap, verifies filter warnings when blocked/warning rows are hidden, verifies Queue Launch Decision, Completed Output Acceptance, and Pending Publish Drain Decision daily-use handoff wording plus scope boundaries, verifies hidden selected-row detail and Selected Row At A Glance strips remain visible, and proves no mutation routes are posted. It skips cleanly if Chrome/Edge is unavailable and does not launch, process media, drain pending publish, publish, rerun, rename, save settings, mutate queue state, or touch source/output/scratch paths.

Queue, Completed, and Pending Publish selected-row details also explain which focused investigation views include the row and why. These signals are read-only operator guidance; backend commands remain the only path for launch, rerun, repair, drain, publish, or filesystem mutation.

Selected-row details also show whether the active text/status/investigation filters are hiding the selected row. Clear-filter buttons reset only local display filters; they do not change backend launch, rerun, cleanup, recovery, drain, publish, manifest, payload, or filesystem scope.

For the browser-backed Maintenance/Reports smoke, run:

```powershell
.\SmokeTests\Test-WebViewBrowserMaintenanceReportsSmoke.ps1
```

This starts a temporary local API, opens the real backend-served WebView page in installed Chrome/Edge headless, verifies Maintenance health/readiness, release dry-run result rendering, completed-manifest backfill dry-run result rendering, dry-run history, Reports failure/audit triage, selected-row details, and read-only Launch/Diagnostics handoff navigation. It skips cleanly if Chrome/Edge is unavailable and does not launch, process media, run audit, run CSV rerun, execute release packaging, rewrite completed manifests, publish, rename, save settings, mutate queue state, or touch source/output/scratch paths.

For the browser-backed Sample Validation smoke, run:

```powershell
.\SmokeTests\Test-WebViewBrowserSampleValidationSmoke.ps1
```

This starts a temporary local API, opens the real backend-served WebView page in installed Chrome/Edge headless, verifies Home Sample Validation pilot checkpoint/attention/readiness/reconciliation text plus the real-media validation audit and policy-alignment roll-ups, verifies the Completed saved-policy reconciliation handoff before Preview/Append, fills manual acceptance-checklist items, executes only the backend-owned Preview Record route, verifies current-evidence plus append-readiness/manual-check gap rendering, and confirms no append or mutation routes are posted. It skips cleanly if Chrome/Edge is unavailable and does not append validation records, accept outputs, clear failures, launch, process media, run audit, run CSV rerun, drain pending publish, publish, rename, save settings, mutate queue state, or touch source/output/scratch paths.

For the browser-backed Home live-state smoke, run:

```powershell
.\SmokeTests\Test-WebViewBrowserHomeLiveStateSmoke.ps1
```

This starts a temporary local API with generated temporary media state, generated active-progress state, a generated ActiveJobs record, and a generated command journal, opens the real backend-served WebView page in installed Chrome/Edge headless, verifies Daily-Driver Checklist, Operator Readiness, Active Work, Live Progress Details/Evidence, Diagnostics runtime progress, Command Results, Sample Validation posture, and the Real-Media Validation Worksheet handoff, and confirms rendering sends no POST routes. It skips cleanly if Chrome/Edge is unavailable and does not append validation records, accept outputs, clear failures, launch, process media, run audit, run CSV rerun, drain pending publish, publish, rename, save settings, mutate queue state, or touch source/output/scratch paths.

For the browser-backed Launch/Queue readiness smoke, run:

```powershell
.\SmokeTests\Test-WebViewBrowserLaunchQueueReadinessSmoke.ps1
```

This starts a temporary local API with generated temporary media state and generated launch command history, opens the real backend-served WebView page in installed Chrome/Edge headless, verifies Launch preflight, Launch Scope Reconciliation, Launch Real-Media Sample Proof Handoff, Queue Launch Decision, Schedule guidance/timing trust, close-readiness, launch command-review correlation, and confirms no POST routes are sent. It skips cleanly if Chrome/Edge is unavailable and does not launch, process media, run audit, run CSV rerun, drain pending publish, publish, rename, save settings, mutate queue state, or touch source/output/scratch paths.

For the browser-backed layout-manager smoke, run:

```powershell
.\SmokeTests\Test-WebViewBrowserLayoutManagerSmoke.ps1
```

This starts a temporary local API with generated temporary media state, opens the real backend-served WebView page in installed Chrome/Edge headless, enters customize mode, and verifies representative Queue, Completed, Settings, Diagnostics, Launch, and Reports tab/subtab/subsection boxes expose independent customize bars and draggable handles. It skips cleanly if Chrome/Edge is unavailable and does not launch, process media, run audit, run CSV rerun, drain pending publish, publish, rename, save settings, mutate queue state, post mutation routes, or touch source/output/scratch paths.

For the browser-backed Network smoke, run:

```powershell
.\SmokeTests\Test-WebViewBrowserNetworkSmoke.ps1
```

This starts a temporary local API, opens the real backend-served WebView page in installed Chrome/Edge headless, verifies read-only Network readiness, renders backend-authored runtime state-file evidence, renders persisted worker rows, selects state-file and worker detail, and verifies local worker filters warn when active/problem rows are hidden. It skips cleanly if Chrome/Edge is unavailable and does not start/stop coordinator or workers, process media, launch pipeline commands, publish, rename, save settings, mutate queue state, or touch source/output/scratch paths.

For the browser-backed Live telemetry smoke, run:

```powershell
.\SmokeTests\Test-WebViewBrowserTelemetrySmoke.ps1
```

This starts a temporary local API, opens the real backend-served WebView page in installed Chrome/Edge headless, verifies zero-percent NVENC remains visible without duplicate idle wording, verifies top-level GPU telemetry can synthesize a GPU detail row, and verifies CPU/RAM-only fallback wording. It uses fixture telemetry; it does not sample the local GPU, process media, launch pipeline commands, publish, rename, save settings, mutate queue state, or touch source/output/scratch paths.

For the WebView Settings/Launch media-policy handoff smoke, run:

```powershell
.\SmokeTests\Test-WebViewSettingsLaunchPolicySmoke.ps1
```

This uses generated temporary state and validates read-only WebView visibility only. It does not launch pipeline work, process media, publish, rename, save settings, or mutate source/output/scratch paths.

For the same WebView Settings/Launch handoff against the current saved config, run:

```powershell
.\SmokeTests\Test-WebViewSettingsLaunchLiveConfigSmoke.ps1
```

This starts a temporary local API, reads the current config, and reports backend media-policy readiness. It is still read-only and does not launch work, save settings, publish, rename, or process media.

For the WebView Settings Preview/Save evidence smoke against a generated temporary config, run:

```powershell
.\SmokeTests\Test-WebViewSettingsPatchEvidenceSmoke.ps1
```

This proves backend Preview Patch, denied Save Patch, confirmed Save Patch, reload evidence, and command history without touching the current saved config or media.

For the browser-backed Settings-to-Launch smoke, run:

```powershell
.\SmokeTests\Test-WebViewBrowserSettingsLaunchSmoke.ps1
```

This starts a temporary local API, opens the real backend-served WebView in installed Chrome/Edge headless, drives Settings and Launch controls, verifies staged settings patch handoff and Settings-to-Launch intent, verifies selectable Launch Risk Handoff proof-chain detail, verifies Launch intent exposes Queue display-scope evidence when filters hide blocked rows, verifies Preview Patch is called, cancels Save Patch, confirms the cancellation is visible, and verifies Save Patch is not posted. It skips cleanly if Chrome/Edge is unavailable and does not save settings, process media, launch pipeline commands, publish, rename files, mutate queue state, or touch source/output/scratch paths.

For a full catalog of smoke wrappers, scope limits, and what smokes do not prove, see `Docs/testing/WEBVIEW_SMOKE_TEST_CATALOG.md`.
