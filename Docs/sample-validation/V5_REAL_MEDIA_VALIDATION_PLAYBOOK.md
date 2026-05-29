# V5/V6 Real-Media Validation Playbook

Purpose: prove that the WebView/Tauri path is safe enough for daily operator trust on real files without changing media policy, bypassing backend commands, or weakening the backend-owned safety boundary. In this V6 folder, the legacy desktop shell has been removed; V5 remains the external rollback/fallback workspace.

This playbook is observational. It does not add a new processing mode. All media mutation remains owned by the existing Python/PowerShell backend.

## Validation Tier Summary

| Tier | What it proves | Does NOT prove |
|---|---|---|
| **UI smoke** (non-browser: `Test-WebViewCommandEvidenceSmoke`, `Test-WebViewRowDetailSmoke`, `Test-WebViewRenameReadinessSmoke`, etc.) | WebView JavaScript renders correctly, operator-facing text is present, boundary guards fire | FFmpeg behavior, real route decisions, actual subtitle/audio output |
| **Browser smoke** (`Test-WebViewBrowserHighRiskSmoke`, `Test-WebViewBrowserDiagnosticsHandoffSmoke`, `Test-WebViewBrowserLargeTableSmoke`, `Test-WebViewBrowserMaintenanceReportsSmoke`, `Test-WebViewBrowserRenameSmoke`, `Test-WebViewBrowserSettingsLaunchSmoke`) | UI interactions work under real browser rendering, large table caps are disclosed, readiness checks block correctly, Maintenance/Reports triage renders, mutation routes are not called | No real media; no pipeline executed |
| **Release self-test** (`scripts\release\test.ps1`) | Package layout, Python/PS syntax, unit tests, environment verifier, Tauri prereqs | FFmpeg, subtitle, audio, size policy, pending publish on real files |
| **Backend route smoke** (`Test-WebViewRealMediaEvidenceSmoke`, `Test-LocalApiSampleValidationContractSmoke`) | Backend-served WebView assets agree with fixture Queue/Completed/Pending state, route evidence renders for known source/output, sample-validation preview/append/read/tail contracts expose current-backend-evidence checks | Real encode or remux was not run; fixture data only |
| **Real-media proof** (this playbook) | A real file ran through the pipeline, output exists, route/audio/subtitle/size/pending-publish evidence is coherent and explained | Does not guarantee all future files will behave the same way |

Complete all tiers in order before treating WebView as a daily-driver shell.

## Validation Boundary

The following checks are useful but are not real-media proof by themselves:

- Tauri prerequisite `-CheckOnly`
- Tauri build checker
- Tauri launch smoke
- release self-test
- WebView refresh success
- clean Diagnostics panels with no visible recent errors
- Maintenance release/backfill dry runs
- Queue preview alone

Real-media proof requires at least one small known sample run where these agree:

- Queue route decision and route reason
- subtitle and audio decision evidence
- FFmpeg/run log evidence
- Completed output and sidecar proof
- size-growth explanation
- Pending Publish state or durable drain summary
- no fresh failure marker for the same source/output

## Sample Batch

Use a tiny batch before trusting unattended WebView operation. Recommended categories:

| Sample category | What it exercises | Minimum evidence to capture |
|---|---|---|
| Low-bitrate H.264, compatible audio/subtitles | Remux-safe copy path; should not encode | Route reason = remux/copy; source size ≈ output size; no encode log |
| H.264 with strict profile or size-guard trigger | Encode path for a known reason | Route reason = encode; FFmpeg encode log in `last_stderr_log`; output size within policy |
| File with TX3G embedded subtitles | TX3G → SRT conversion when enabled | `completed_manifest` sidecar field; SRT present in output container or alongside |
| File with ASS/SSA subtitles | ASS/SSA → SRT conversion or drop | `completed_manifest` audio/subtitle decision; SRT present or drop confirmed by settings |
| File with PGS/BDPGS subtitles | OCR path if enabled; keep-original if not | `last_stderr_log` for OCR tool invocation; SRT produced or original track preserved |
| Multi-audio track file | Passthrough/transcode/channel-cap behavior | Completed row audio decision evidence; channel count visible in output |
| Network output destination (if network mode is active) | Robocopy transfer + pending parked/drained state | Pending Publish row + drain summary; Completed output proof |
| Deferred-publish case | Parking + drain lifecycle | Pending Publish → Recovery dry-run → Drain result → durable `pending_drain_summary.json` |

Keep the sample small enough that deleting/rebuilding outputs for testing is low risk. You do not need all categories on every validation run — choose the ones that match your active settings.

## Pre-Run Checklist

| Check | Expected Evidence | Where To Inspect |
|---|---|---|
| External fallback is identified | V5 fallback workspace is available if V6 validation fails | Operator-maintained V5 folder |
| WebView backend refresh works | Home Daily-Driver Checklist has no required payload failures | WebView Home |
| Close readiness is understood | Active work status is visible and explains whether closing is safe | WebView Home / Diagnostics |
| Saved settings posture is visible | Settings risk/trust summaries show routing, subtitle, audio, file-safety, and publish posture | WebView Home / Settings / Launch |
| Queue route evidence is visible | Queue row shows route, route reason, media type, source root, operator guidance, and blocked/excluded status | WebView Queue |
| Queue backend scope boundary is understood | Backend Launch Scope Preview panel shows loaded-row count vs. visible-filtered-row count; confirms backend launch scope is not narrowed to the visible table subset; any filter warnings for hidden blocked/review rows are investigated before starting | WebView Queue |
| Pending Publish scope boundary is understood | Backend Drain Scope Preview panel shows parked-row count vs. visible-filtered-row count; confirms backend drain scope is not narrowed to visible rows; filter warnings for hidden blocked/review rows are investigated before drain | WebView Pending Publish |
| Launch path is backend-owned | Launch preflight, command review, sample-execution checklist, selected-sample generated worksheet evidence, and selected-sample validation-record reconciliation show backend validation and command history before start | WebView Launch |
| Sample validation readiness is explained | Home Sample Validation Record and the Home Real-Media Validation Worksheet show backend readiness, required evidence counts, blockers/review rows, current backend evidence, real-media pilot checkpoint counts, pilot attention rows, the operator sample execution checklist, and safe next action before append | WebView Home |
| Historical sample records are reconciled | Home Sample Validation Record shows whether recent accepted/review records still match current Queue, Completed, Pending Publish, and Diagnostics evidence | WebView Home |

Do not continue if required backend reads fail, close-readiness is unknown during active work, or Settings reports critical errors.

## During The Run

| Evidence | What Good Looks Like | Failure Meaning |
|---|---|---|
| ActiveJobs | One backend launch record with expected target, pid/log paths, and state | Missing/stale ActiveJobs makes process state harder to trust |
| Progress | Current file/stage/percent updates while work is active | Progress alone is not output proof |
| Last Stderr / Run Logs | FFmpeg command/result evidence matches the route decision | Route/log mismatch means review before accepting output |
| Queue runtime history | Fresh runtime outcome appears for the same source after completion/failure | Stale runtime history is context only |
| Close Readiness | Remains unsafe while processing; returns safe after backend is done | Safe too early would be a process lifecycle bug |

Use Diagnostics before repeating Start if a launch command fails. Do not press Start again until command detail, backend preflight, diagnostics targets, and owner page state agree on the cause.

## Exact Evidence To Capture Per Sample

Record these fields for each sample file. Use the Home Validation Log Template, a manual note, or a generated worksheet.

To create a timestamped worksheet before a run:

```powershell
.\scripts\operator\New-RealMediaValidationWorksheet.ps1 `
  -SamplePath "D:\Samples\Movie.mkv" "\\SERVER\TV\Show\S01E01.mkv" `
  -SampleCategory "h264-remux-safe,subtitle-bearing" `
  -ExpectedRoute "remux,remux-plus-srt" `
  -QueueSnapshotPath "E:\Videos\Scratch\State\Progress\queue_snapshot.json" `
  -Shell "WebView preview"
```

The worksheet generator writes Markdown evidence only under `Docs\RealMediaValidationRuns` by default. It can prefill sample category/expected-route columns, copy matching Queue route evidence from an existing queue snapshot, and create a WebView pilot-evidence-packet capture table that mirrors the Home Sample Validation preview result. It does not launch the app, process media, probe FFmpeg, rename files, save settings, publish outputs, drain pending publish, mutate queue state, or touch source/output/scratch media. Generated worksheets may contain personal paths and are excluded from clean release packages.

The WebView Home Sample Validation Record readback is also evidence-only. Its backend readiness, current-evidence preview, pilot-plan checkpoint counts, pilot attention rows, operator sample execution checklist, generated worksheet list, preview-time pilot evidence packet, next required action, and reconciliation lines are useful preflight guidance for recording or reviewing validation notes. The generated worksheet panel reads bounded Markdown evidence from `Docs\RealMediaValidationRuns`, shows whether the selected sample appears in a worksheet, and lists captured sample/pilot-packet rows. Launch repeats that generated-worksheet match as a `Generated worksheet evidence` checkpoint in the Real-Media Sample Proof Handoff, then repeats recent Sample Validation record matching/reconciliation as a `Sample Validation record evidence` checkpoint. The start surface can show whether the selected sample already has worksheet context and whether a historical validation note is still current, stale, or review against backend evidence before any backend-owned start action. The execution checklist is the quick sequence to follow around one sample: choose the source, verify saved policy, launch only through backend-owned Launch, check Completed/Diagnostics/Pending Publish proof, then preview/append evidence. The pilot evidence packet is the quick post-run proof summary to copy into the worksheet before appending a note. The Home Real-Media Validation Worksheet repeats that Sample Validation posture beside Queue, Completed, Pending Publish, Diagnostics, and Settings proof so the operator can see whether the sample note is current, stale, blocked, or still needs a pilot run. These panels do not accept output, clear failures, repair manifests, drain Pending Publish, launch work, scan arbitrary output shares, or replace the manual proof checks below.

Run `.\SmokeTests\Test-LocalApiSampleValidationContractSmoke.ps1` when changing sample-validation contracts. It starts a temporary token-protected local API and validates preview/append/read/tail behavior, strict JSON handling, current-backend-evidence warnings, diagnostics tail allowlisting, command history, and temp-only validation-log writes. It does not probe FFmpeg, process media, publish files, accept outputs, clear failures, or touch source/output/scratch paths.

Run `.\SmokeTests\Test-WebViewBrowserHomeLiveStateSmoke.ps1` when changing Home daily-use panels. It starts a temporary local API with generated temporary media state and a generated command journal, then verifies Daily-Driver Checklist, Operator Readiness, Active Work, Command Results, Sample Validation posture, and the Real-Media Validation Worksheet handoff in Chrome/Edge without sending POST routes. It still does not prove FFmpeg, Plex playback, or real media output quality.

Run `.\SmokeTests\Test-WebViewBrowserLaunchQueueReadinessSmoke.ps1` when changing Launch, Queue launch-decision, Launch Scope Reconciliation, Launch real-media proof handoff, Launch generated worksheet evidence, Launch Sample Validation record evidence, Launch sample execution checklist, Schedule timing/guidance, close-readiness, or launch command-review surfaces. It starts a temporary local API with generated temporary media state, generated launch command history, and a temporary validation record, then verifies the real backend-served WebView can render Launch readiness/timing trust, Launch Scope Reconciliation, Launch selected-sample worksheet matching, Launch selected-sample validation-record matching/reconciliation, Launch sample execution guidance, backend `GET /api/launch/preflight`, Queue Launch Decision, Schedule guidance/timing trust, close-readiness, and launch command-review correlation without sending POST routes. It still does not submit `pipeline.start`, process media, or prove real FFmpeg/Plex output.

The WebView Completed page also has a `Real-Media Output Proof` board for the selected completed row. Use it as a quick read-only ladder across Completed output/sidecar proof, route/size/media decisions, Pending Publish/drain posture, Diagnostics/runtime signals, Sample Validation handoff evidence, and mutation boundaries. It is a navigation and evidence aid only; it does not replace opening the output, checking playback, reading the relevant log/manifest lines, or recording manual sample evidence.

| Evidence field | Where to find it | Notes |
|---|---|---|
| Source path | Queue row `source` | Exact path from queue plan |
| Source size (bytes) | Completed row source size | From `completed_manifest` size fields |
| Output path | Completed row `output` | Exact path |
| Output size (bytes) | Completed row output size | From `completed_manifest` size fields |
| Route reason | Completed row route decision | Remux / copy / encode + reason code |
| Encoder used | Completed row encoder evidence | NVENC / CPU / passthrough |
| Sidecar path | Completed row sidecar field | MKS, SRT, or original track |
| `completed_manifest` entry | Tail `completed_manifest` via Diagnostics | Full row including source/output/audio/subtitle/route |
| `last_stderr_log` FFmpeg lines | Tail `last_stderr_log` via Diagnostics | Look for `ffmpeg` invocation, codec, channel, subtitle |
| Pending Publish row (if deferred) | Pending Publish selected-row | Drain status, payload path, diagnostic severity |
| Drain summary (if drained) | Pending Publish Last Drain Summary panel | `pending_drain_summary.json` counts and statuses |
| Failure marker (should be absent) | Diagnostics `latest_failure_json` | If present: stage, error code, source path |

## Post-Run Proof

| Check | Expected Evidence | WebView Location |
|---|---|---|
| Completed row exists | The processed source/output appears in Completed | Completed |
| Output exists | Output proof is present and no missing-output issue is shown | Completed Output Acceptance |
| Sidecar agrees | Sidecar/manifest consistency has no mismatch or stale-path issue | Completed Manifest Consistency |
| Route reason is explainable | Route decision/evidence explains remux vs encode and encoder/audio/subtitle decisions | Completed row detail |
| Proof ladder is coherent | Real-Media Output Proof rows do not disagree across output/sidecar, route/size/media, pending/drain, diagnostics/runtime, Sample Validation handoff, and operator-boundary evidence | Completed Real-Media Output Proof |
| Size growth is explainable | Growth over 5% is absent, or route/audio/subtitle evidence explains it | Completed Size Growth Evidence |
| Pending Publish is coherent | If deferred publish parked output, Pending Publish row is ready or has reviewed diagnostics | Pending Publish |
| Drain proof is durable | After drain, latest drain summary/recent event agrees with Completed output state | Pending Publish / Completed |
| Diagnostics are clean enough | No fresh error/failure marker for the same source/output remains unexplained | Diagnostics |

## Subtitle Proof

Preferred-language subtitle behavior should match current settings:

- TX3G: keep original unless drop setting is enabled; add SRT when conversion setting and container policy allow it.
- ASS/SSA: keep original unless drop setting is enabled; generated SRT should use existing style/negative-filter cleanup behavior.
- BDPGS: keep original unless drop setting is enabled; OCR/SRT output must be validated before mux/publish.
- Unknown language tracks should follow the configured language policy. If the operator expects "probably English", verify that the route evidence reflects that assumption.

If subtitle conversion fails, the expected default is manual review, not silent publish as if SRT was produced.

## Audio Proof

Confirm audio behavior from Completed route evidence and logs:

- passthrough profile used when codec/channels/language are compatible
- transcode path used only when policy requires it
- preferred/default language selection is predictable
- downmix/channel cap is visible when it changes the track
- no-audio output only occurs when explicitly allowed

## Size-Growth Proof

For files that balloon in size:

- Compare source size and output size in Completed.
- Read route reason and encoder evidence before deleting or rerunning.
- Check whether subtitles or audio normalization forced a container/encode path.
- Confirm `SizeGuardMode` and growth limits in Settings.
- In strict mode, growth beyond policy should reject or mark review according to backend policy.
- In advisory mode, growth should be clearly visible for operator decision.

Do not treat a clean release/self-test as evidence that encode size policy worked on a specific file.

## Pending Publish Proof

Deferred publish is trusted only when these agree:

- Pending Publish row has no do-not-drain diagnostic blocker.
- Payload and sidecar paths exist.
- Recovery dry-run says rows are ready or explains blockers.
- Drain command result is visible.
- Durable `pending_drain_summary.json` agrees with recent drain event and remaining parked rows.
- Completed output proof does not report missing output without pending/drain proof.

## Acceptance Criteria

The WebView/Tauri preview can be considered validated for a small daily-driver batch when:

- Home Daily-Driver Checklist has no required refresh failures.
- Queue, Launch, Diagnostics, Completed, and Pending Publish all show coherent evidence for the same sample files.
- No source file was mutated.
- Scratch-copy behavior was used.
- Completed output/sidecar proof is present.
- Oversized outputs are either absent or explained by route evidence and policy.
- Pending publish either drained successfully or clearly parked rows for later drain.
- V5 remains available externally as the rollback workspace.

## Validation Log Template

Home > Cross-Page Context now includes a read-only Validation Log Template. Use it as a manual evidence record for one selected or recent sample row.

The template is not persisted and does not change backend acceptance state. It should be filled from observable evidence only:

| Field | What To Record |
|---|---|
| Sample | selected Queue, Completed, or Pending Publish row used as the trace anchor |
| Proof strength | exact path trace, partial exact proof, filename-only advisory, or no proof |
| Trace keys | source, output, runtime output, pending destination, or parked payload paths shown by the WebView |
| Observed evidence | Queue, Completed, Pending Publish, and Diagnostics matches shown by exact path or advisory filename |
| Route check | whether remux-vs-encode reason and route evidence matched expectations |
| Subtitle check | whether preferred-language SRT/OCR behavior and original-subtitle preservation matched settings |
| Audio check | whether passthrough/transcode/default-language/channel behavior matched settings |
| Output proof | whether Completed output exists and sidecar/manifest points to the current output |
| Size-growth proof | whether size policy result is acceptable or needs review |
| Pending-publish proof | whether parked payload, drain summary, or empty pending state is coherent |
| Diagnostics proof | whether fresh logs/errors/failure markers are absent or explained |
| Operator decision | accept sample, hold for review, rerun through backend-owned controls, or fall back to the external V5 rollback workspace |

Do not convert this manual template into an acceptance button until a backend-owned persisted validation artifact is designed and tested.

## Stop Conditions

Stop WebView daily-driver validation and fall back to the external V5 rollback workspace if any of these occur:

- source file changes unexpectedly
- backend process remains running after close-readiness claims safe
- output is marked complete before publish/parking proof exists
- sidecar points to stale output after rename/publish
- subtitle conversion failure still publishes as success
- encode output exceeds strict size policy without rejection/review
- Pending Publish drain deletes or loses payloads without durable summary
- WebView sends or accepts arbitrary filesystem paths for mutation

## Notes For Future Work

Good future improvements are backend-owned and testable:

- explicit sample-run validation report generated after a known batch
- backend-authored route/subtitle/audio proof rows tied to source path
- persisted progress history instead of recent-event inference
- backend log index for structured search
- optional operator acknowledgement that a sample batch was accepted

Avoid frontend-only acceptance buttons, manual success overrides, or policy changes based only on preview/build checks.

