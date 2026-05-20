# MediaPipelineRemuxEncodeAIO V5 Tauri/WebView2 Transition Current Plan

Date: 2026-05-18  
Workspace: `MediaPipelineRemuxEncodeAIO_V5`  
Backup baseline: `MediaPipelineRemuxEncodeAIO_V4`  
Current production shell: CustomTkinter desktop app  
Target shell: Tauri/WebView2 desktop shell with local Python backend  

## Purpose

This document is the current operating plan for the V5 transition. It replaces the earlier transition groundwork document as the practical planning reference, while preserving that document as historical implementation detail.

The goal is not to keep increasing file count or pursue a theoretical clean architecture. The goal is to move V5 toward a maintainable local-backend architecture that can support both the existing Tk desktop app and a future Tauri/WebView2 frontend without duplicating media-processing logic or weakening operational safety.

The transition is still technically sound, but the project has reached the point where more extraction is not automatically helpful. The next work should emphasize process safety, API contract stability, frontend modularity, import-cycle cleanup, and production failure testing.

## Current Handoff - 2026-05-18

Completed:

- After the transition-review remediation follow-ups, a fresh PG-3 current-handoff package named `MediaPipelineRemuxEncodeAIO_V5_PG3_CurrentHandoff_20260518_140116` was built with `-IncludeTauriPreviewBinary -Verify`.
- The copied-bundle release self-test passed. The package excludes personal live config, source-tree tests, `node_modules`, and Tauri build output while including the packaged Tauri preview executable.
- Copied-bundle package-mode `Test-TauriShell-Launch.ps1 -Mode Packaged -TimeoutSeconds 180 -CloseTimeoutSeconds 30` passed locally with shell PID `34800` and backend PID `29804`.
- Copied-bundle `New-TauriShell-PG3CleanMachineReport.ps1 -PrereqPassed -LaunchPassed` wrote `%TEMP%\pg3_current_handoff_local_dev_boundary_20260518_140116.md` with `Bundle layout mismatches: 0` and `Developer tools detected outside bundle: 8`.
- The post-smoke process sweep found no copied-package Tauri shell, FFmpeg, ffprobe, or MKVToolNix leftovers. One pre-existing user-owned source-workspace Local API backend PID `19176` was left running.
- This is transfer readiness evidence only. PG-3 remains open until the same bundle is copied to a separate clean Windows machine and the prereq, packaged launch, and clean-machine report commands pass with no developer-tool dependency.
- 2026-05-19 preview-shell lifecycle hardening closed: Tauri emits backend health/crash lifecycle events, WebView renders an event-only recovery banner, a per-user Windows mutex rejects second shell instances before backend startup, and `Test-TauriShell-ProductionSurface.ps1` audits devtools/token/single-window/bridge posture. This is source/dev guardrail evidence only and does not replace PG-3 clean-machine proof.

Remaining:

- Copy `MediaPipelineRemuxEncodeAIO_V5_PG3_CurrentHandoff_20260518_140116` to a separate clean Windows machine and run `DesktopApp\tauri_shell\Test-TauriShell-Prereqs.ps1 -CheckOnly`, `DesktopApp\tauri_shell\Test-TauriShell-Launch.ps1 -Mode Packaged -TimeoutSeconds 180 -CloseTimeoutSeconds 30`, and `DesktopApp\tauri_shell\New-TauriShell-PG3CleanMachineReport.ps1 -PrereqPassed -LaunchPassed -OperatorConfirmedNoDeveloperTools`.
- Fill `Docs\RealMediaValidationRuns\real_media_validation_20260518_transition_followup_plan.md` with operator-selected samples and run the real-media validation playbook before WebView/Tauri daily-driver promotion.

## Current Handoff - 2026-05-17

Completed:

- PG-1 live active-close proof remains recorded and validated.
- PG-2 prep was implemented: WebView Launch exposes optional `single_file`, request serialization/preflight coverage exists, and Tauri-served WebView bootstrap now marks `shellSurface=tauri`.
- PG-2 real-media Tauri WebView runtime proof was captured for Spy x Family S01E10: Tauri WebView launched the pipeline, ActiveJobs reached `completed`, output/sidecar/Completed/Pending evidence agreed, and Sample Validation record `sample-8ded8b2aa96d40ecb2634223ed851ef9` was appended with `shell=tauri`.
- Evidence worksheet: `Docs\RealMediaValidationRuns\real_media_validation_20260517_tauri_pg2_webview_launch_spy_x_family.md`.
- Real-media worksheet prep was tightened: `New-RealMediaValidationWorksheet.ps1` now accepts `-QueueSnapshotPath` and can prefill the Queue Evidence table from an existing snapshot before launch without touching media or queue state.
- A queue-backed Tauri WebView pilot was captured for `[Anime Time] Trigun - 002 - Truth of Mistake.mkv`: the worksheet helper matched the existing Queue snapshot row, Tauri WebView launched the single-file pipeline, ActiveJobs reached `completed`, output/sidecar were published, stderr was empty, and Sample Validation record `sample-eae245e62c3f4f5cb7b8b3d1a1bcaf41` was appended with `shell=tauri` and `decision=hold_review`.
- The Trigun queue-backed pilot exposed a real blocker instead of acceptance proof: the Queue snapshot treated the source as TV with a 2.00 GB threshold, but the V5 single-file run logged `isTV=False`, processed it as Movie with an 8.00 GB threshold, wrote a blank sidecar `media_type`, and published to flat `outsource\Trigun 002 Truth of Mistake\` instead of TV/season layout.
- The single-file TV classification blocker was fixed after the pilot: `Resolve-SingleFileMediaKind` now classifies `-SingleFile` paths by configured `SourceTV`/`SourceMovies` roots before falling back to filename patterns, so queue-backed TV files with bare episode numbers no longer default to movie layout.
- Fresh Queue snapshot generation after that fix exposed a second TV planning bug: queue dry-run already-processed checks could call TV destination planning without parsed `TvInfo`. `Build-QueuePlanSnapshotRows` now parses TV info before TV preflight/already-processed checks, and the reliability regression covers that path.
- Post-fix queue-backed Tauri WebView pilots were captured for Trigun S01E03 and S01E04 using a fresh pre-run queue snapshot. Both launched from the Tauri/WebView harness, ActiveJobs reached `completed` with return code `0`, stderr logs were empty, and outputs/sidecars were written to `\\LAYNE-SERVER\Users\Layne\Videos\outsource\TV\Trigun (1998)\Season 01\`.
- The S01E03 post-fix pilot proved TV root classification and TV/season placement, but still showed blank top-level sidecar `media_type`; that traced to `PublishCompletion.ps1` only reading `PlexPlan` from PSObject properties and missing hashtable paths.
- The sidecar `media_type` blocker was fixed: `PublishCompletion.ps1` now reads `PlexPlan` from either hashtables or PSObjects, and the reliability regression asserts `media_type=tv` for hashtable `PlexPlan` writes.
- The S01E04 Tauri/WebView pilot proved the sidecar fix on disk: top-level sidecar `media_type=tv`, route-plan trace `media_type=tv`, 2.00 GB TV threshold, ASS-to-SRT subtitle decision, ENG/JPN AC3 copy decisions, immediate publish, and Sample Validation record `sample-f13ea7be2cf5452a897307ced29ffc02` with category `subtitle-srt-generation`.
- The earlier Trigun post-fix pilots remain supporting hold-review evidence because they predate the later label/count fixes, not because playback is still missing. The two pilot-discovered UI/evidence issues were fixed for future refreshes/appends: Completed preview now treats singleton sidecar decision objects as one-item lists, and the Tauri debug Sample Validation append script derives `sample_label` from the actual source/output path instead of a hardcoded Spy X Family label.
- A follow-up post-fix queue-backed Tauri/WebView pilot was captured for Trigun S01E05 after those UI/evidence fixes. ActiveJobs `E:\Videos\Scratch\State\ActiveJobs\20260517_143458_724362_pipeline_9276_0b1fb13d.json` reached `completed` with return code `0`, pipeline stderr was 0 bytes, output/sidecar were written to `\\LAYNE-SERVER\Users\Layne\Videos\outsource\TV\Trigun (1998)\Season 01\`, and the sidecar preserved `media_type=tv`, route `remux`, route reason `codec_remux_safe`, TV threshold `2.0`, ENG/JPN AC3 copy decisions, and ASS `convertass`.
- The S01E05 pilot proved both future UI/evidence fixes on real output: the Completed preview row reported singleton `subtitle_decision_count=1`, and the Tauri/WebView Sample Validation append record `sample-821bc9f02cdc40059b3720317e741d2e` used the actual source leaf `sample_label=[Anime Time] Trigun - 005 - Hard Puncher.mkv` with `shell=tauri`, category `subtitle-srt-generation`, and decision `hold_review`.
- Operator playback acceptance was recorded on 2026-05-17 for the PG-2 media outputs: Spy x Family S01E10 played correctly with converted subtitles and good audio, and Trigun S01E03/S01E04/S01E05 also played correctly with subtitles and audio good. The queue-backed, post-fix Trigun S01E05 worksheet is now the PG-2 accepted evidence anchor; Spy x Family S01E10 and Trigun S01E03/S01E04 remain supporting evidence because they lack either pre-run Queue proof or have historical pre-fix label/UI evidence issues.
- The worksheet helper was repaired after the evidence template relocation: `New-RealMediaValidationWorksheet.ps1` now prefers `Docs\sample-validation\REAL_MEDIA_VALIDATION_EVIDENCE_TEMPLATE.md` with a legacy root fallback, restoring the real-media worksheet unit tests and PlanOnly generation.
- Release validation was repaired after the Docs reorganization: release self-test now checks `Docs\inventories\SMOKE_TEST_INVENTORY.md`, reliability regression resolves `Docs\architecture\DEPLOYABILITY_CHECKLIST.md` with a legacy fallback, and Tauri scaffold coverage asserts the updated smoke-inventory path.
- A 2026-05-17 PG-3 current-handoff deployable candidate was built from the updated source tree at `C:\Users\lmmye\Documents\Codex\2026-04-20-files-mentioned-by-the-user-ass\MediaPipelineRemuxEncodeAIO_V5_PG3_CurrentHandoff_20260517_151039` with `-IncludeTauriPreviewBinary -Verify`. The copied bundle release self-test passed, package-mode Tauri launch/close passed locally, and the PG-3 report helper showed bundle-layout mismatches `0` with the packaged Tauri executable included. This historical candidate is superseded by the 2026-05-18 current-handoff package.
- The pre-fix Trigun Sample Validation records remain historical evidence with stale `sample_label` text; their source/output/category fields are the authoritative proof fields. The S01E05 post-fix record has the corrected source-leaf label.
- The Queue/probe source-sample hash warning on large files was fixed across source identity, audit probe cache identity, and rerun source identity helpers by forcing tail-seek math to use Int64 offsets instead of PowerShell's Int32 `[math]::Max(0, <large offset>)` overload.
- The large-file hash fix was verified with regression coverage and a non-mutating real UNC probe against `\\LAYNE-SERVER\Video\TV\The Pitt\Season 01\The Pitt - S01E02.mkv` (`2767923896` bytes), which returned a 64-character sample hash without the previous Int32 conversion warning.
- Evidence worksheet: `Docs\RealMediaValidationRuns\real_media_validation_20260517_tauri_queuebacked_trigun02_pilot.md`.
- Evidence worksheets: `Docs\RealMediaValidationRuns\real_media_validation_20260517_tauri_queuebacked_trigun03_postfix_pilot.md` and `Docs\RealMediaValidationRuns\real_media_validation_20260517_tauri_queuebacked_trigun04_sidecar_media_type_pilot.md`.
- Evidence worksheet: `Docs\RealMediaValidationRuns\real_media_validation_20260517_tauri_queuebacked_trigun05_postfix_label_count_pilot.md`.
- PG-3 prep was tightened: `Test-TauriShell-Prereqs.ps1` now accepts the documented `-CheckOnly` flag, `Test-TauriShell-Launch.ps1` can run in package mode without npm/cargo/VsDevCmd, the Rust shell now prefers bundle-relative `DesktopApp` candidates before the baked-in development manifest path, and the release builder has an explicit `-IncludeTauriPreviewBinary` option for PG-3 candidate bundles.
- PG-3 local package-mode proof was captured on the development workstation: Tauri release build now succeeds after wiring the existing `.ico`, a deployable candidate built with `-IncludeTauriPreviewBinary`, release self-test passed against the copied bundle, and `Test-TauriShell-Launch.ps1 -Mode Packaged` passed from that copied bundle.
- PG-3 clean-machine evidence support was added: the copied bundle now includes `New-TauriShell-PG3CleanMachineReport.ps1`, release validation checks the helper, generated clean-machine reports are excluded from deployables, and a fresh copied candidate validated the helper with zero bundle-layout mismatches on this workstation.
- PG-3 execution was rechecked on the development workstation boundary after PG-2 acceptance: the current handoff bundle still contains the packaged Tauri executable and PG-3 helper scripts, copied-bundle `Test-TauriShell-Prereqs.ps1 -CheckOnly` passed, copied-bundle `Test-TauriShell-Launch.ps1 -Mode Packaged -TimeoutSeconds 180 -CloseTimeoutSeconds 30` passed with shell PID `18760` and backend PID `34980`, and `New-TauriShell-PG3CleanMachineReport.ps1 -PrereqPassed -LaunchPassed` wrote `%TEMP%\pg3_current_handoff_local_dev_boundary_20260517.md` with bundle-layout mismatches `0`. The same report detected `8` developer-tool signals outside the bundle on `LAYNE-GAMINGPC`, so this correctly remains non-clean-machine evidence and cannot prove PG-3.
- V5/Tk production-readiness recheck passed after deferring PG-3: `Verify-MediaPipelineRemuxEncodeAIO-Environment.ps1`, reliability regression checks, targeted WebView navigation static tests, and the full unskipped `Test-MediaPipelineRemuxEncodeAIO-Release.ps1` all passed. The release self-test included bundled tool integration and temp end-to-end media smoke checks. The only release-self-test warning was expected for a source/dev folder: `release_manifest.json` is absent, so manifest hygiene checks were skipped.
- The production-readiness recheck exposed one stale test expectation, not a product regression: `DesktopApp\tests\test_webview_navigation_static.py` still expected old nav labels for Completed/Pending. The test now matches the intended concise UI labels `Output` and `Publish`, and the targeted static navigation suite passes.
- Progress-bar planning was completed and archived at `Docs\archive\completed-checklists\V5_PROGRESS_BARS_PLAN.md`. The first implementation chunk was backend-authored snapshot progress bars sourced from existing pipeline/audit progress files, preserving the rule that the frontend renders progress but does not own backend policy or mutation.
- Progress-bar P1 is implemented: `desktop_app_snapshot.v1` now includes backend-authored `progress_bars` for current stage, run total, publish output state, and audit progress. WebView `Run Progress` renders those bars above the existing detail table, and browser smoke coverage verifies the bars render from real backend-served Home/Live state without POST/mutation routes.

Changed files:

- `DesktopApp\mediapipeline_desktop_app\backend_bootstrap.py`
- `DesktopApp\mediapipeline_desktop_app\local_api_main.py`
- `DesktopApp\mediapipeline_desktop_app\api\server.py`
- `DesktopApp\mediapipeline_desktop_app\api\static_files_policy.py`
- `DesktopApp\mediapipeline_desktop_app\application\dto_status.py`
- `DesktopApp\mediapipeline_desktop_app\application\facade_status.py`
- `DesktopApp\mediapipeline_desktop_app\application\facade_status_policy.py`
- `DesktopApp\mediapipeline_desktop_app\models.py`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\index.html`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\app.js`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\progressView.js`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\styles.css`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\launchView.js`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\crossPageContextView.js`
- `DesktopApp\tauri_shell\src-tauri\src\lib.rs`
- `DesktopApp\tauri_shell\src-tauri\tauri.conf.json`
- `DesktopApp\tauri_shell\README.md`
- `DesktopApp\tauri_shell\Test-TauriShell-WebViewUiAutomationProbe.ps1`
- `DesktopApp\tauri_shell\Test-TauriShell-Prereqs.ps1`
- `DesktopApp\tauri_shell\Test-TauriShell-Launch.ps1`
- `DesktopApp\tauri_shell\New-TauriShell-PG3CleanMachineReport.ps1`
- `DesktopApp\tauri_shell\Test-TauriShell-PG2WebViewLaunch.ps1`
- `DesktopApp\tauri_shell\Test-TauriShell-PG2SampleValidationAppend.ps1`
- `DesktopApp\tests\test_api_static_files_policy.py`
- `DesktopApp\tests\test_application_facade.py`
- `DesktopApp\tests\test_backend_bootstrap.py`
- `DesktopApp\tests\test_facade_completed_policy.py`
- `DesktopApp\tests\test_tauri_shell_scaffold.py`
- `DesktopApp\tests\test_webview_browser_home_live_state_smoke.py`
- `DesktopApp\tests\test_webview_browser_launch_queue_readiness_smoke.py`
- `DesktopApp\tests\test_webview_browser_sample_validation_smoke.py`
- `DesktopApp\tests\test_webview_navigation_static.py`
- `DesktopApp\tests\test_real_media_validation_worksheet.py`
- `Pipeline\Modules\Audit.Probe.ps1`
- `Pipeline\MediaPipeline_chatgpt.ps1`
- `Pipeline\Modules\PipelineEngine.ps1`
- `Pipeline\Modules\PathHelpers.ps1`
- `Pipeline\Modules\PublishCompletion.ps1`
- `Pipeline\Modules\RerunSourceIdentity.ps1`
- `Pipeline\Modules\SourceIdentity.ps1`
- `Pipeline\Tests\Invoke-ReliabilityRegressionChecks.ps1`
- `New-RealMediaValidationWorksheet.ps1`
- `Build-MediaPipelineRemuxEncodeAIO-Release.ps1`
- `Test-MediaPipelineRemuxEncodeAIO-Release.ps1`
- `Docs\RealMediaValidationRuns\real_media_validation_20260517_tauri_pg2_webview_launch_spy_x_family.md`
- `Docs\RealMediaValidationRuns\real_media_validation_20260517_tauri_queuebacked_trigun02_pilot.md`
- `Docs\RealMediaValidationRuns\real_media_validation_20260517_tauri_queuebacked_trigun03_postfix_pilot.md`
- `Docs\RealMediaValidationRuns\real_media_validation_20260517_tauri_queuebacked_trigun04_sidecar_media_type_pilot.md`
- `Docs\RealMediaValidationRuns\real_media_validation_20260517_tauri_queuebacked_trigun05_postfix_label_count_pilot.md`
- `Docs\ACTIVE_FIX_CHECKLIST.md`
- `Docs\CURRENT_PROJECT_STATE.md`
- `Docs\archive\completed-checklists\V5_PROGRESS_BARS_PLAN.md`
- `Docs\active-plans\V5_TAURI_TRANSITION_CURRENT_PLAN.md`

Tests:

- `python -m unittest DesktopApp.tests.test_application_facade.LocalApiServerTests.test_local_api_serves_read_only_web_prototype -q`
- `python -m unittest DesktopApp.tests.test_webview_browser_launch_queue_readiness_smoke -q`
- `python -m unittest DesktopApp.tests.test_webview_browser_sample_validation_smoke -q`
- `python -m unittest DesktopApp.tests.test_application_facade.ApplicationFacadeTests.test_facade_snapshot_and_diagnostics_do_not_require_tk_root DesktopApp.tests.test_application_facade.ApplicationFacadeTests.test_snapshot_progress_bars_include_pipeline_publish_and_audit DesktopApp.tests.test_application_facade.ApplicationFacadeTests.test_local_api_static_file_helpers_render_bootstrap_and_assets -q`
- `python -m unittest DesktopApp.tests.test_webview_navigation_static -q`
- `SmokeTests\Test-WebViewBrowserHomeLiveStateSmoke.ps1`
- focused backend/bootstrap/Tauri scaffold tests
- `node --check` for changed WebView assets
- `DesktopApp\tauri_shell\Test-TauriShell-Build.ps1`
- `python -m unittest discover -s DesktopApp\tests -q` (`1190` tests)
- `Test-MediaPipelineRemuxEncodeAIO-Release.ps1 -SkipToolIntegration -SkipEndToEndSmoke`
- `python -m unittest DesktopApp.tests.test_webview_navigation_static -q`
- `Test-MediaPipelineRemuxEncodeAIO-Release.ps1` (unskipped; bundled tool integration and temp end-to-end smoke included)
- PG-3 prep focused checks: PowerShell parser checks for `Test-TauriShell-Prereqs.ps1`, `Test-TauriShell-Launch.ps1`, `Build-MediaPipelineRemuxEncodeAIO-Release.ps1`, and `Test-MediaPipelineRemuxEncodeAIO-Release.ps1`; `python -m unittest DesktopApp.tests.test_tauri_shell_scaffold -q`; `DesktopApp\tauri_shell\Test-TauriShell-Build.ps1`; `DesktopApp\tauri_shell\Test-TauriShell-Prereqs.ps1 -CheckOnly`; `Build-MediaPipelineRemuxEncodeAIO-Release.ps1 -DryRun`; `Test-MediaPipelineRemuxEncodeAIO-Release.ps1 -SkipToolIntegration -SkipEndToEndSmoke`
- PG-3 package-mode checks: `npm run build` from `DesktopApp\tauri_shell`; deployable candidate `MediaPipelineRemuxEncodeAIO_V5_PG3_PackageSmoke_20260517_092600` built with `-IncludeTauriPreviewBinary`; release self-test passed against that copied bundle; `Test-TauriShell-Launch.ps1 -Mode Packaged -TimeoutSeconds 180 -CloseTimeoutSeconds 30` passed from the copied bundle.
- PG-3 report-helper checks: parser checks for `New-TauriShell-PG3CleanMachineReport.ps1`, updated scaffold coverage (`73` tests), non-strict helper run to `%TEMP%` from the source tree, `Build-MediaPipelineRemuxEncodeAIO-Release.ps1 -DryRun`, source release self-test, fresh deployable candidate `MediaPipelineRemuxEncodeAIO_V5_PG3_ReportHelper_20260517_094453` built with `-IncludeTauriPreviewBinary`, copied-bundle release self-test, and copied-bundle helper run to `%TEMP%` showing `Bundle layout mismatches: 0`.
- Worksheet Queue Evidence checks: parser check for `New-RealMediaValidationWorksheet.ps1`, `python -m unittest DesktopApp.tests.test_real_media_validation_worksheet -q` (`6` tests), and `New-RealMediaValidationWorksheet.ps1 -QueueSnapshotPath E:\Videos\Scratch\State\Progress\queue_snapshot.json -PlanOnly` against three real queued paths (`queue_snapshot_sample_matches=3`, no worksheet written).
- Queue-backed Trigun pilot checks: generated worksheet from `E:\Videos\Scratch\State\Progress\queue_snapshot.json` with one matched source, ran `Test-TauriShell-PG2WebViewLaunch.ps1` from the Tauri WebView against the UNC sample, verified ActiveJobs `20260517_100012_033367_pipeline_3476_10160ba2` reached `completed` with return code `0`, verified output/sidecar existence and empty stderr, appended Sample Validation record through `Test-TauriShell-PG2SampleValidationAppend.ps1`, and performed a targeted `State\Failures` search for the Trigun sample with no matching marker found.
- Post-pilot single-file classification fix checks: parser checks for `Pipeline\MediaPipeline_chatgpt.ps1`, `Pipeline\Modules\PathHelpers.ps1`, and `Pipeline\Tests\Invoke-ReliabilityRegressionChecks.ps1`; `Pipeline\Tests\Invoke-ReliabilityRegressionChecks.ps1`; non-mutating real-path probe showing the Trigun UNC path now resolves to `MediaKind=tv`, `Reason=source_tv_root`; and `Test-MediaPipelineRemuxEncodeAIO-Release.ps1 -SkipToolIntegration -SkipEndToEndSmoke`.
- Post-pilot Queue dry-run TV info fix checks: parser checks for `Pipeline\Modules\PipelineEngine.ps1` and `Pipeline\Tests\Invoke-ReliabilityRegressionChecks.ps1`; `Pipeline\Tests\Invoke-ReliabilityRegressionChecks.ps1`; and fresh Queue snapshot `C:\Users\lmmye\AppData\Local\Temp\mediapipeline_queue_postfix2_20260517_102811.json` showing Trigun S01E03/S01E04 rows as TV, unblocked, not excluded, with 2.00 GB threshold route evidence.
- Post-pilot sidecar media-type fix checks: parser checks for `Pipeline\Modules\PublishCompletion.ps1` and `Pipeline\Tests\Invoke-ReliabilityRegressionChecks.ps1`; `Pipeline\Tests\Invoke-ReliabilityRegressionChecks.ps1`; Tauri PG2 WebView launch for Trigun S01E03 proving TV/season output placement; Tauri PG2 WebView launch for Trigun S01E04 proving top-level sidecar `media_type=tv`; and Tauri PG2 Sample Validation append records `sample-07bd8e44e56a4fa8a5091dc4d0487797` and `sample-f13ea7be2cf5452a897307ced29ffc02`.
- Pilot-discovered UI/evidence mismatch fix checks: `python -m unittest DesktopApp.tests.test_facade_completed_policy -q`; `python -m unittest DesktopApp.tests.test_tauri_shell_scaffold -q`; `cargo fmt --check`; and `cargo test` from `DesktopApp\tauri_shell\src-tauri`.
- Post-UI/evidence-fix S01E05 proof checks: generated worksheet from `C:\Users\lmmye\AppData\Local\Temp\mediapipeline_queue_continue_20260517_143036.json` with one matched source; ran `Test-TauriShell-PG2WebViewLaunch.ps1` from the Tauri WebView against Trigun S01E05; verified ActiveJobs `20260517_143458_724362_pipeline_9276_0b1fb13d` reached `completed` with return code `0`; verified output/sidecar existence, sidecar `media_type=tv`, TV threshold `2.0`, AC3 copy audio decisions, ASS `convertass`, pipeline stderr 0 bytes, Completed preview `subtitle_decision_count=1`, and Tauri Sample Validation append record `sample-821bc9f02cdc40059b3720317e741d2e` with corrected sample label.
- PG-2 operator playback acceptance check: user confirmed Spy x Family S01E10 playback worked great with converted subtitles and good audio, and confirmed Trigun S01E03/S01E04/S01E05 playback, subtitles, and audio also looked good. A backend preview for appending a fresh accepted S01E05 `sample_validation_record.v1` was intentionally not appended because the current Diagnostics tail no longer contained the S01E05 run clue (`accepted_ready=false`); the Markdown worksheets now carry the operator playback acceptance while the existing JSONL records remain historical `hold_review` entries.
- Worksheet relocation fix checks: `python -m unittest DesktopApp.tests.test_real_media_validation_worksheet -q` (`6` tests) and `New-RealMediaValidationWorksheet.ps1 -PlanOnly` proving the resolved template path is `Docs\sample-validation\REAL_MEDIA_VALIDATION_EVIDENCE_TEMPLATE.md`.
- Post-S01E05 and final post-release-test process sweeps found no leftover Tauri shell, media pipeline child, FFmpeg, ffprobe, or mkvmerge process. The only matching process was the pre-existing user-owned Local API backend PID `30372` with parent `19992`, which was left running.
- Docs relocation gate checks: parser checks for `Test-MediaPipelineRemuxEncodeAIO-Release.ps1` and `Pipeline\Tests\Invoke-ReliabilityRegressionChecks.ps1`; `Pipeline\Tests\Invoke-ReliabilityRegressionChecks.ps1`; `python -m unittest DesktopApp.tests.test_tauri_shell_scaffold -q` (`73` tests); and final `Test-MediaPipelineRemuxEncodeAIO-Release.ps1 -SkipToolIntegration -SkipEndToEndSmoke` passed. One intermediate full-suite release run hit a transient localhost `ConnectionAbortedError`; the isolated Local API token test passed immediately afterward before the final release self-test passed.
- Historical 2026-05-17 PG-3 current-handoff candidate checks: `Build-MediaPipelineRemuxEncodeAIO-Release.ps1 -DestinationRoot C:\Users\lmmye\Documents\Codex\2026-04-20-files-mentioned-by-the-user-ass\MediaPipelineRemuxEncodeAIO_V5_PG3_CurrentHandoff_20260517_151039 -IncludeTauriPreviewBinary -Verify` passed; copied-bundle `Test-TauriShell-Prereqs.ps1 -CheckOnly` passed; copied-bundle `New-TauriShell-PG3CleanMachineReport.ps1 -PrereqPassed -LaunchPassed` wrote `%TEMP%\pg3_current_handoff_report_20260517_151039.md` with `Bundle layout mismatches: 0` and `Tauri preview binary included: True`; copied-bundle `Test-TauriShell-Launch.ps1 -Mode Packaged -TimeoutSeconds 180 -CloseTimeoutSeconds 30` passed with shell PID `13516` and backend PID `33360`.
- Historical 2026-05-17 PG-3 boundary recheck: copied-bundle `DesktopApp\tauri_shell\Test-TauriShell-Prereqs.ps1 -CheckOnly` passed from `MediaPipelineRemuxEncodeAIO_V5_PG3_CurrentHandoff_20260517_151039`; copied-bundle `DesktopApp\tauri_shell\Test-TauriShell-Launch.ps1 -Mode Packaged -TimeoutSeconds 180 -CloseTimeoutSeconds 30` passed with shell PID `18760` and backend PID `34980`; copied-bundle `New-TauriShell-PG3CleanMachineReport.ps1 -PrereqPassed -LaunchPassed -OutputPath %TEMP%\pg3_current_handoff_local_dev_boundary_20260517.md` reported `Bundle layout mismatches: 0`, `Tauri preview binary included: True`, and `Developer tools detected outside bundle: 8`. The 2026-05-18 current-handoff package now supersedes this candidate.
- Post-boundary-smoke process sweep found no leftover packaged Tauri shell, FFmpeg, ffprobe, or mkvmerge process. The only local API backend process was the pre-existing user-owned source-workspace backend PID `30372`, which was left running.
- Final process sweep after copied-bundle package-mode launch found no leftover packaged Tauri shell, media pipeline child, FFmpeg, ffprobe, or mkvmerge process. The only matching process was the pre-existing user-owned Local API backend PID `30372` with parent `19992`, which was left running.
- Post-fix release self-test: `Test-MediaPipelineRemuxEncodeAIO-Release.ps1 -SkipToolIntegration -SkipEndToEndSmoke` passed after the Queue dry-run, sidecar media-type, Completed singleton-decision, and Tauri debug sample-label fixes.
- Large-file source-sample hash fix checks: parser checks for `Pipeline\Modules\SourceIdentity.ps1`, `Pipeline\Modules\Audit.Probe.ps1`, `Pipeline\Modules\RerunSourceIdentity.ps1`, and `Pipeline\Tests\Invoke-ReliabilityRegressionChecks.ps1`; `Pipeline\Tests\Invoke-ReliabilityRegressionChecks.ps1`; and a non-mutating UNC probe returning a 64-character sample hash for `\\LAYNE-SERVER\Video\TV\The Pitt\Season 01\The Pitt - S01E02.mkv` without the prior Int32 warning.
- Post-hash-fix release self-test: `Test-MediaPipelineRemuxEncodeAIO-Release.ps1 -SkipToolIntegration -SkipEndToEndSmoke` passed after the Int64 sample-hash helper changes.
- V5/Tk production-readiness release gate: `Verify-MediaPipelineRemuxEncodeAIO-Environment.ps1` passed with only optional `zeroconf` absent; `Pipeline\Tests\Invoke-ReliabilityRegressionChecks.ps1` passed with a 600s timeout; `python -m unittest DesktopApp.tests.test_webview_navigation_static -q` passed after updating stale expected nav labels to `Output` and `Publish`; and full unskipped `Test-MediaPipelineRemuxEncodeAIO-Release.ps1` passed, including layout, parser, Python syntax, desktop unit tests, environment verifier, Tauri preview prereqs, reliability regression checks, bundled tool integration checks, and temp end-to-end media smoke checks.
- Final production-readiness process sweep found no leftover Tauri shell, FFmpeg, ffprobe, or mkvmerge process. The only matching process was the pre-existing user-owned Local API backend PID `30372` with parent `19992`, which was left running.

Remaining:

- Historical pre-fix Trigun Sample Validation records still contain stale `sample_label` text from the old Tauri debug append script. Do not treat those labels as authoritative; use source/output/category fields. The post-fix S01E05 record has the corrected source-leaf label.
- If the in-app Sample Validation gate needs a current accepted JSONL record, append a fresh accepted record from Home only while current Queue/Completed/Pending/Diagnostics evidence for the chosen output is loaded and backend preview reports `accepted_ready=true`. Do not rewrite the existing `hold_review` JSONL records.
- PG-3 is blocked in this workspace because it requires a separate clean machine with no development environment. Next operator action is to copy the verified 2026-05-18 deployable candidate `MediaPipelineRemuxEncodeAIO_V5_PG3_CurrentHandoff_20260518_140116` to that clean machine and run `Test-TauriShell-Prereqs.ps1 -CheckOnly`, `Test-TauriShell-Launch.ps1 -Mode Packaged -TimeoutSeconds 180 -CloseTimeoutSeconds 30`, and `New-TauriShell-PG3CleanMachineReport.ps1 -PrereqPassed -LaunchPassed -OperatorConfirmedNoDeveloperTools` from the bundle directory.

Latest queue-backed Tauri WebView pilot checkpoint:

- A one-sample queue-backed pilot was run for `\\LAYNE-SERVER\Users\Layne\Videos\Encode\TV\[Anime Time] Trigun (1998)\[Anime Time] Trigun - 002 - Truth of Mistake.mkv`.
- The worksheet generator prefilled Queue Evidence from `E:\Videos\Scratch\State\Progress\queue_snapshot.json`: route `REMUX (codec check pending)`, reason `source size 0.42 GB is within 2.00 GB threshold; codec probe still required`, route reason code `size_within_threshold`, not blocked, not excluded, root `\\LAYNE-SERVER\Users\Layne\Videos\Encode\TV`.
- Tauri WebView launch harness completed: shell PID `27976`, backend PID `27200`, pipeline PID `3476`, backend URL `http://127.0.0.1:65350`, ActiveJobs record `E:\Videos\Scratch\State\ActiveJobs\20260517_100012_033367_pipeline_3476_10160ba2.json`, `status=completed`, `return_code=0`.
- Output and sidecar exist at `\\LAYNE-SERVER\Users\Layne\Videos\outsource\Trigun 002 Truth of Mistake\Trigun 002 Truth of Mistake.mkv` and `.pipeline.json`; source still exists; stderr log is 0 bytes.
- Sidecar/run-log proof: route `remux`, route reason code `codec_remux_safe`, publish state `published`, publish mode `immediate`, source size `448893613`, output size `449754487` (+0.19%), HEVC 576p source profile, ENG/JPN AC3 6ch copied audio, ASS subtitle stream converted to SRT.
- Blocker found: run log says `SINGLE-FILE MODE: isTV=False` and `[Movie 1/1] TYPE: Movie`; route decision trace uses `media_type: movie` with 8.00 GB threshold, sidecar `media_type` is blank, and output placement is not TV/season layout. This disagrees with the Queue TV-root evidence and with a prior V4 completed row for the same source that placed output under `outsource\TV\Trigun (1998)\Season 01\`.
- Post-pilot fix: `-SingleFile` classification now uses configured source-root boundaries first. A non-mutating probe against the same Trigun UNC source resolves to `MediaKind=tv`, `IsTV=True`, `Reason=source_tv_root`, `Root=\\LAYNE-SERVER\Users\Layne\Videos\Encode\TV`. Follow-up S01E03/S01E04 Tauri/WebView runs proved TV/season placement, and S01E04 proved fixed top-level sidecar `media_type=tv`.
- Sample Validation record `sample-eae245e62c3f4f5cb7b8b3d1a1bcaf41` was appended from inside the Tauri WebView with `shell=tauri` and `decision=hold_review`. The attempted category `tv-parse-review` was omitted by backend validation because it is not one of the known categories.
- Evidence worksheet was updated at `Docs\RealMediaValidationRuns\real_media_validation_20260517_tauri_queuebacked_trigun02_pilot.md`. This is useful real-media evidence, but it is not accepted daily-driver proof until the classification/placement mismatch and manual playback gap are resolved.

Latest post-fix queue-backed Tauri WebView checkpoint:

- Fresh Queue snapshot `C:\Users\lmmye\AppData\Local\Temp\mediapipeline_queue_postfix2_20260517_102811.json` captured Trigun S01E03/S01E04 as TV rows under `\\LAYNE-SERVER\Users\Layne\Videos\Encode\TV`, route `REMUX (codec check pending)`, reason code `size_within_threshold`, not blocked, not excluded, and 2.00 GB TV threshold evidence.
- Trigun S01E03 launched through the Tauri/WebView PG2 harness, ActiveJobs `E:\Videos\Scratch\State\ActiveJobs\20260517_103106_891915_pipeline_31996_ffbb5a92.json` reached `completed` with return code `0`, stderr was empty, and output/sidecar were written to `\\LAYNE-SERVER\Users\Layne\Videos\outsource\TV\Trigun (1998)\Season 01\Trigun (1998) - S01E03.mkv` and `.pipeline.json`.
- S01E03 proved the single-file TV classification fix: run log shows `SINGLE-FILE MODE: isTV=True | mediaKind=tv | reason=source_tv_root`, `[TV 1/1] TV: [Anime Time] Trigun (1998) S01E03`, and route reason `source size 0.50 GB is within 2.00 GB threshold`.
- S01E03 still showed blank top-level sidecar `media_type`; `PublishCompletion.ps1` was then fixed to read `PlexPlan` from hashtable paths as well as PSObject paths.
- Trigun S01E04 launched after the sidecar fix, ActiveJobs `E:\Videos\Scratch\State\ActiveJobs\20260517_103914_007579_pipeline_31312_3b26c59f.json` reached `completed` with return code `0`, stderr was empty, and output/sidecar were written to `\\LAYNE-SERVER\Users\Layne\Videos\outsource\TV\Trigun (1998)\Season 01\Trigun (1998) - S01E04.mkv` and `.pipeline.json`.
- S01E04 proved the sidecar fix: top-level sidecar `media_type=tv`; route-plan decision trace has `media_type=tv`, `threshold_gb=2.0`, HEVC 576p source profile, ENG/JPN AC3 6ch copy decisions, ASS subtitle `convertass`, `source_size=560658892`, `output_size=561667274`, and immediate publish.
- Sample Validation records were appended through the Tauri/WebView harness for S01E03 (`sample-07bd8e44e56a4fa8a5091dc4d0487797`) and S01E04 (`sample-f13ea7be2cf5452a897307ced29ffc02`) with category `subtitle-srt-generation`.
- Trigun S01E05 launched after the Completed singleton-decision and Tauri debug sample-label fixes, ActiveJobs `E:\Videos\Scratch\State\ActiveJobs\20260517_143458_724362_pipeline_9276_0b1fb13d.json` reached `completed` with return code `0`, pipeline stderr was empty, and output/sidecar were written to `\\LAYNE-SERVER\Users\Layne\Videos\outsource\TV\Trigun (1998)\Season 01\Trigun (1998) - S01E05.mkv` and `.pipeline.json`.
- S01E05 proved the UI/evidence fixes on real output: Completed preview reported `subtitle_decision_count=1` for the singleton sidecar subtitle object, and Sample Validation record `sample-821bc9f02cdc40059b3720317e741d2e` used corrected `sample_label=[Anime Time] Trigun - 005 - Hard Puncher.mkv`.
- Manual playback gap closed on 2026-05-17: operator confirmed Trigun S01E03/S01E04/S01E05 playback, subtitles, and audio looked good. S01E05 is the accepted queue-backed post-fix PG-2 worksheet proof. The S01E03/S01E04 Sample Validation labels are historical stale-label records from before the Tauri debug append fix; S01E05 proves the corrected behavior for future appends.

## Executive Verdict

The migration remains on track, but it needs tighter discipline.

Strong decisions already made:

- V4 remains untouched as known-good fallback.
- V5 is the active migration workspace.
- Tk remains the supported production UI until the web/Tauri shell reaches feature parity.
- The local Python backend owns media-affecting behavior.
- The web frontend is not allowed to reimplement FFmpeg, queue, rename, settings, subtitle, pending-publish, or file safety logic.
- Process launch, path layout, rename inference, settings patching, command results, and telemetry are moving behind UI-neutral service/facade boundaries.

Main concern:

- The codebase is approaching over-fragmentation. Several recent splits improved risk isolation, but more micro-splitting could reduce developer velocity and make future debugging harder.

Current health rating:

- Architecture direction: Good.
- Operational safety trend: Improving.
- Maintainability trend: Improving in core service areas, worsening if micro-splitting continues.
- Tauri readiness: Prototype-quality, not production replacement yet.
- Testing: Broad and useful, but still too light on adversarial runtime failure tests.

Housekeeping checkpoint:

- 2026-05-15 cleanup/archive work is complete enough to return focus to transition work. Completed/stale Markdown was moved under `Docs/archive/`, old RunLogs/config backups were archived by date, project Python caches were pruned, routine search now uses `.rgignore`, root onboarding now starts at `AI_AGENT_START_HERE.md`, and smoke wrappers are centralized under `SmokeTests/`.
- `DesktopApp/tauri_shell/src-tauri/target/` was pruned as generated Rust build output; the next Tauri/Rust build will recreate it and may take longer.
- `node_modules/` and `src-tauri/gen/` were intentionally kept so Tauri preview work can continue without reinstalling dependencies.
- Next transition work should resume with real-media validation, WebView parity gaps, diagnostics clarity, and backend-owned command safety. Do not use archived Claude/admin/checklist docs as active marching orders unless a current source-of-truth doc reopens them.

Latest production-UNC real-media retry checkpoint:

- After the media server reset, production UNC roots for Movies, TV, and outsource were reachable again and the environment verifier passed.
- `/api/pipeline/start` now forwards `single_file` into the existing service launch path, so backend-owned WebView/local API starts can actually invoke `-SingleFile <path>` when the command contract advertises that key.
- The WebView Run Controls surface and `/api/contract` are aligned for pipeline control actions: pause, stop, rescan, and kill. This fixes the stale mismatch where the backend policy and WebView exposed `kill` but the command contract omitted it, and where the contract exposed `rescan` without a WebView button.
- A production-config backend-owned `single_file` retry of `Texhnolyze 11 [Bdrip 10 - S24E57.mkv` completed after one transient retry. Final output and sidecar were published to `\\LAYNE-SERVER\Users\Layne\Videos\outsource\TV\Texhnolyze 11 10\Season 24\`, with sidecar route `remux`, route reason `codec_remux_safe`, publish state `published`, HEVC 576p video, JPN AAC 2ch copied audio, no subtitles, source size 275470965, output size 275273320, and growth -0.0717%.
- Worksheet evidence was recorded in `Docs\RealMediaValidationRuns\real_media_validation_real_media_validation_20260516_production_unc_texhnolyze11_backend_start.md`, and a hold-review Sample Validation record was appended as `sample-67e2e7f93bc647a784c8a4802ef82027`.
- The sample remains hold-review, not accepted PG-2 evidence: it was not launched from an actual Tauri window/WebView click, no pre-run Queue row was captured, manual playback was not checked, and the run used backend code from before the ActiveJobs completion watcher below.
- Local API/Tauri process launches now start a daemon ActiveJobs completion watcher after readiness succeeds. Future backend-owned launches should write terminal ActiveJobs status and return code instead of later reconciling successful short runs as `orphaned`.
- Validation passed for targeted process-control/launch/ActiveJobs tests, `Test-TauriShell-Build.ps1`, and the release self-test with tool integration/end-to-end media smoke skipped. No FFmpeg routing, subtitle/audio policy, pending-publish behavior, config persistence, repair/reconcile route, or Tk fallback behavior changed.

Latest production-UNC ActiveJobs watcher checkpoint:

- A second production-config backend-owned `single_file` retry of `Texhnolyze 07 [Bdrip 10 - S24E57.mkv` was launched through a separate temporary local API on port 18766 after the completion watcher fix.
- The run completed successfully with PID 17552, and `E:\Videos\Scratch\State\ActiveJobs\20260517_001351_587098_pipeline_17552_6b97e351.json` reached `status=completed`, `return_code=0`, and no reconcile reason. This proves the new backend process-launch watcher records terminal ActiveJobs state for a short real-media run instead of leaving it to stale/orphan reconciliation.
- Final output and sidecar were published to `\\LAYNE-SERVER\Users\Layne\Videos\outsource\TV\Texhnolyze 07 10\Season 24\`, with sidecar route `remux`, route reason `codec_remux_safe`, publish state `published`, HEVC 576p video, JPN AAC 2ch copied audio, no subtitles, source size 281623813, output size 281427153, and growth -0.0698%.
- The run log shows production config, `-Once -SingleFile`, successful REMUX-AV/REMUX-MUX, `PLEX CHECK` high outlook, final copy to the UNC outsource target, empty stderr, no matching PendingServerPush or failure-marker rows in the targeted state files, and `pipeline_progress.json` returned to `Status=Idle`.
- Worksheet evidence was recorded in `Docs\RealMediaValidationRuns\real_media_validation_20260517_production_unc_texhnolyze07_activejobs_watcher.md`.
- This is still not accepted PG-2 evidence: it was not launched from an actual Tauri window/WebView click, no pre-run Queue row was captured, no `shell=tauri` validation record was appended, and manual playback was not checked. It specifically closes the post-fix ActiveJobs terminal-status proof gap from the prior production-UNC retry.

Latest Tauri pre-window asset-gate checkpoint:

- `Test-TauriShell-Launch.ps1` initially failed before opening the window because the Tauri pre-window WebView asset gate still expected the old inline `renderCrossPageContext({` fragment in `app.js`.
- The WebView refresh path now builds `const crossPageContext = { ... }` and calls `renderCrossPageContext(crossPageContext)`, so the Rust shell gate and its fixture were updated to validate the current split-asset shape instead of the stale inline fragment.
- `Test-TauriShell-Build.ps1` passed after the gate update, including WebView JavaScript syntax checks, Rust `cargo check`, and 19 Rust tests.
- `Test-TauriShell-Launch.ps1` then passed: the shell opened a visible Tauri window, detected backend PID 27716, and closed cleanly without processing media.
- This is a bounded launch/close smoke only. It does not prove PG-1 active-encode close-readiness behavior, PG-2 real-media launch from an actual WebView click, or PG-3 clean-machine install validation.

Latest PG-1 force-close cleanup hardening checkpoint:

- Tauri shell close now sends `force_active_work_shutdown=true` with `/api/backend/shutdown` after the operator confirms closing while close-readiness is unsafe.
- The local API honors that explicit force flag only for unsafe close-readiness responses. It asks the backend service to kill tracked app-owned pipeline/audit/rerun process handles, then also attempts related MediaPipeline process cleanup by command-line identity before scheduling backend shutdown.
- Local API process launches now keep an in-memory registry of active spawned processes until the completion watcher records terminal ActiveJobs state. Force cleanup unregisters killed processes so the completion watcher does not overwrite a `killed` ActiveJobs status with a later generic failure update.
- The unsafe backend shutdown payload now records `forced_active_work_shutdown=true` and `cleanup_messages` when that cleanup path is used, preserving warning visibility for Diagnostics/Command History.
- Targeted validation passed for process spawning, ActiveJobs, local API lifecycle contracts, PG-1 close-readiness scaffold coverage, and the Tauri shell shutdown contract. `Test-TauriShell-Build.ps1` passed, and the bounded `Test-TauriShell-Launch.ps1` launch/close smoke passed after the change.
- This is still not PG-1 proof: no live Tauri-owned active encode/remux job was started and interrupted by pressing the real window close button, and no native confirmation prompt transcript was captured. It closes the backend cleanup path that PG-1 needs before that adversarial run is safe to attempt.

Latest PG-1 live active-close checkpoint:

- Added `DesktopApp\tauri_shell\Test-TauriShell-PG1ActiveClose.ps1`, a manual/real-media validation harness that opens the Tauri preview shell, discovers the Tauri-owned backend URL/token from the served WebView bootstrap, starts exactly one explicit `single_file` pipeline job, waits for unsafe close-readiness, requests a real native window close, captures the native prompt transcript, confirms close, and verifies shell/backend/pipeline cleanup plus terminal ActiveJobs state.
- The first live run against `E:\Videos\Scratch\Encoded\TV\SPY x FAMILY\Season 01\Spy X Family - S01E10 - THE GREAT DODGEBALL PLAN.mkv` exposed a race: force cleanup stopped the process, but the background completion watcher could still write `failed` over the intended `killed` ActiveJobs state.
- The cleanup path now unregisters tracked app-owned processes before force-killing them. That makes the completion watcher skip its terminal update for force-cleaned processes, preserving the `killed` ActiveJobs status.
- The second live run passed: Tauri shell PID 676, backend PID 2344, pipeline PID 30868, close-readiness reason `Shell close blocked because MediaPipeline process PID(s) 30868 are still running from this bundle.`, native prompt title `MediaPipeline active work`, and ActiveJobs record `E:\Videos\Scratch\State\ActiveJobs\20260517_012542_175803_pipeline_30868_ab2597eb.json` reached `status=killed`, `return_code=1`.
- Captured prompt text included the active-work reason, the continuous schedule-stop watcher section (`status: idle`), `Close the MediaPipeline shell anyway?`, and the force-cleanup warning that the backend will stop app-owned pipeline work before shutdown.
- Post-close process sweep found no remaining Tauri shell, test backend, media pipeline child, FFmpeg, or ffprobe process from the run. The pre-existing user-owned local API backend PID 30372 was left untouched.
- Evidence was recorded in `Docs\RealMediaValidationRuns\real_media_validation_20260517_tauri_pg1_active_close.md`. Focused process/lifecycle validation passed after the race fix, and the earlier full desktop unit discovery plus release self-test passed after updating the stale Tauri scaffold assertion.
- This proves the live Tauri-owned active-work close path. It still does not prove the simultaneous `armed watcher + active pipeline child` native prompt in one real-media run; the armed-watcher branches remain covered by scaffold/unit/browser lifecycle tests.

Latest PG-2 WebView single-file launch-prep checkpoint:

- The WebView Launch form now exposes the existing backend `single_file` request key as an optional operator-provided absolute path.
- `collectPipelineStartRequest()` trims the field and includes `single_file` only when nonblank. The WebView still submits only a request payload; backend-owned pipeline validation, routing, logs, ActiveJobs, and output policy remain authoritative.
- Launch preflight text now calls out that single-file launch is a backend-owned boundary, and Launch intent/scope evidence summarizes whether a single-file request is staged without echoing the full operator path into every summary row.
- Browser smoke coverage verifies the field, request serialization, and preflight boundary text while keeping mutation POSTs blocked. Focused validation passed for the read-only WebView prototype test, Launch JS syntax, and Launch/Queue browser readiness smoke.
- Tauri now starts the Python backend with `--shell-surface tauri`, the backend-served WebView bootstrap carries `shellSurface`, and Home Sample Validation requests derive their `shell` value from that bootstrap. This closes the prep gap where a future Tauri-appended Sample Validation record would have incorrectly said `shell: webview`.
- Focused validation also passed for backend bootstrap/static bootstrap tests, Tauri scaffold coverage, Sample Validation browser smoke, and `Test-TauriShell-Build.ps1` after the shell-surface change.
- This is preparatory only. PG-2 remains unproven until an actual Tauri window/WebView click runs a known source file to completion, manual playback/evidence checks are recorded, and a Sample Validation record is appended with `shell: tauri`.

Latest PG-2 Tauri WebView real-media launch checkpoint:

- Added `DesktopApp\tauri_shell\Test-TauriShell-PG2WebViewLaunch.ps1`, which opens the Tauri preview shell, uses a debug-only Tauri WebView automation path to fill the real Launch form, invokes the existing `pipeline-start-button`, waits for a new ActiveJobs terminal record, captures Completed/Pending/Command evidence, and closes the shell cleanly.
- Added `DesktopApp\tauri_shell\Test-TauriShell-PG2SampleValidationAppend.ps1`, which reopens the Tauri preview shell and appends hold-review Sample Validation evidence from inside the served Tauri WebView client. It does not write the validation log directly from PowerShell.
- The PG-2 launch run completed for `E:\Videos\Scratch\Encoded\TV\SPY x FAMILY\Season 01\Spy X Family - S01E10 - THE GREAT DODGEBALL PLAN.mkv`: Tauri shell PID `28984`, backend PID `22836`, pipeline PID `6200`, backend URL `http://127.0.0.1:14725`, WebView bootstrap `shellSurface=tauri`, ActiveJobs record `E:\Videos\Scratch\State\ActiveJobs\20260517_020311_815553_pipeline_6200_6a1a3ab8.json`, `status=completed`, `return_code=0`.
- Output proof: final output and sidecar exist under `\\LAYNE-SERVER\Users\Layne\Videos\outsource\TV\Spy X Family\Season 01\`, route `remux`, route reason `codec_remux_safe`, publish state `published`, source size `728716780`, output size `729439532`, Completed consistency `Consistent`, Pending Publish count `0`, and stderr empty.
- Sample Validation proof: record `sample-8ded8b2aa96d40ecb2634223ed851ef9` was appended with `shell=tauri`, decision `hold_review`, category `h264-remux-safe`, and note marker `pg2-tauri-webview-append-20260517_022016`.
- Evidence was recorded in `Docs\RealMediaValidationRuns\real_media_validation_20260517_tauri_pg2_webview_launch_spy_x_family.md`.
- Validation after the PG-2 work passed: focused bootstrap/WebView/Tauri harness tests, WebView browser Sample Validation and Launch/Queue smokes, `Test-TauriShell-Build.ps1`, full `python -m unittest discover -s DesktopApp\tests -q` (`1190` tests), and `Test-MediaPipelineRemuxEncodeAIO-Release.ps1 -SkipToolIntegration -SkipEndToEndSmoke`.
- Final process sweep found no remaining Tauri shell, PG-2 backend, pipeline child, FFmpeg, or ffprobe process. The pre-existing user-owned local API backend PID `30372` was left untouched.
- This proves the Tauri WebView launch/completion path and the `shell=tauri` Sample Validation evidence path. Operator playback was later accepted on 2026-05-17, but this Spy x Family run remains supporting PG-2 evidence rather than the sole accepted gate proof because no pre-run Queue row was captured for the `single_file` request.

Latest PG-3 clean-machine prep checkpoint:

- `Test-TauriShell-Prereqs.ps1` now accepts the documented `-CheckOnly` flag. The flag is explicitly non-mutating and verifies layout/runtime prerequisites without opening WebView2 or processing media.
- `Test-TauriShell-Launch.ps1` now supports `-Mode Auto`, `-Mode Dev`, and `-Mode Packaged`. `Auto` preserves the development workflow when no packaged executable is present; `Packaged` requires a compiled Tauri executable beside the script, beside `DesktopApp\tauri_shell`, or supplied with `-ExecutablePath`.
- The package-mode launch path does not require Node, npm, cargo, or `VsDevCmd.bat`; those are required only for dev-mode `npm run dev`. This makes the clean-machine proof boundary explicit instead of accidentally proving only a development launch.
- The Rust shell now checks bundle-relative `DesktopApp` candidates from the current executable location before falling back to the compile-time `CARGO_MANIFEST_DIR` development root. This reduces the risk that a packaged executable run on a development workstation silently uses the source workspace.
- `Build-MediaPipelineRemuxEncodeAIO-Release.ps1` now has an explicit `-IncludeTauriPreviewBinary` option. When requested after a Tauri release build, it copies `DesktopApp\tauri_shell\src-tauri\target\release\mediapipeline-tauri-shell.exe` into the deployable bundle as `DesktopApp\tauri_shell\mediapipeline-tauri-shell.exe`; the release manifest and release self-test record/check that packaged executable without copying the generated `src-tauri\target` tree.
- `DesktopApp\tauri_shell\README.md` now documents the PG-3 clean-machine commands: `Test-TauriShell-Prereqs.ps1 -CheckOnly`, `Test-TauriShell-Launch.ps1 -Mode Packaged -TimeoutSeconds 180 -CloseTimeoutSeconds 30`, and `New-TauriShell-PG3CleanMachineReport.ps1` for the operator evidence report.
- This is preparation only. PG-3 remains unproven until a release bundle with a compiled Tauri executable is copied to a separate clean Windows machine, the package-mode smoke passes there, and the operator records OS version, machine name, absence of developer tools, and page-load results.

Latest PG-3 local package-mode checkpoint:

- The first release build attempt produced `src-tauri\target\release\mediapipeline-tauri-shell.exe` but failed the bundling step because `tauri.conf.json` had an empty `bundle.icon` list. The existing `src-tauri\icons\icon.ico` is now wired as the bundle icon, and scaffold coverage keeps that packaging invariant.
- `npm run build` from `DesktopApp\tauri_shell` now passes and produced:
  - `DesktopApp\tauri_shell\src-tauri\target\release\mediapipeline-tauri-shell.exe`
  - `DesktopApp\tauri_shell\src-tauri\target\release\bundle\msi\MediaPipelineRemuxEncodeAIO V5_5.0.0_x64_en-US.msi`
  - `DesktopApp\tauri_shell\src-tauri\target\release\bundle\nsis\MediaPipelineRemuxEncodeAIO V5_5.0.0_x64-setup.exe`
- Default release packaging now omits both `Pipeline\Tests` and `DesktopApp\tests` unless `-IncludeTests` is requested. This fixed the copied-bundle self-test failure where desktop tests were present but pipeline test fixtures were omitted.
- A copied deployable candidate was created at `C:\Users\lmmye\Documents\Codex\2026-04-20-files-mentioned-by-the-user-ass\MediaPipelineRemuxEncodeAIO_V5_PG3_PackageSmoke_20260517_092600` with `-IncludeTauriPreviewBinary`.
- Candidate manifest/layout proof: `tauri_preview_binary_included=true`, `DesktopApp\tauri_shell\mediapipeline-tauri-shell.exe` exists, and `DesktopApp\tauri_shell\src-tauri\target`, `DesktopApp\tauri_shell\node_modules`, `DesktopApp\tests`, and `Pipeline\Tests` are absent.
- `Test-MediaPipelineRemuxEncodeAIO-Release.ps1 -BundleRoot <candidate> -SkipToolIntegration -SkipEndToEndSmoke` passed against the copied bundle.
- `Test-TauriShell-Launch.ps1 -Mode Packaged -TimeoutSeconds 180 -CloseTimeoutSeconds 30` passed from the copied bundle: packaged shell PID `8452`, backend PID `21684`, visible Tauri window detected and closed, and backend cleanup verified.
- Source-folder `Test-MediaPipelineRemuxEncodeAIO-Release.ps1 -SkipToolIntegration -SkipEndToEndSmoke` passed again after the release-builder/test-exclusion and Tauri icon changes.
- Post-smoke process sweep found no remaining package-mode Tauri shell, package backend, FFmpeg, or ffprobe child. The pre-existing user-owned local API backend PID `30372` was left untouched.
- This is local package-mode proof on the development workstation, not PG-3 clean-machine proof. PG-3 remains unproven until the same package-mode commands pass on a separate Windows machine with no development toolchain.

Latest PG-3 report-helper checkpoint:

- Added `DesktopApp\tauri_shell\New-TauriShell-PG3CleanMachineReport.ps1`, an evidence-only helper that writes a Markdown clean-machine report with machine/OS/operator fields, release-manifest posture, bundle-layout checks, developer-tool scan results, prereq/launch pass flags, transcript paths, and strict clean-machine failure conditions.
- The helper is shipped in release bundles and is now covered by release layout validation, release parser checks, and scaffold coverage. It does not start the shell, launch media, call `/api/pipeline/start`, run `MediaPipeline_chatgpt.ps1`, or mutate queue/source/output/scratch state.
- Release packaging now excludes generated `Docs\PG3CleanMachineReports\*` outputs so operator/machine evidence from one validation run is not copied into later deployables.
- A fresh copied deployable candidate was created at `C:\Users\lmmye\Documents\Codex\2026-04-20-files-mentioned-by-the-user-ass\MediaPipelineRemuxEncodeAIO_V5_PG3_ReportHelper_20260517_094453` with `-IncludeTauriPreviewBinary`. Manifest/layout proof showed `tauri_preview_binary_included=true`, the PG-3 helper and packaged executable present, and `Docs\PG3CleanMachineReports`, `src-tauri\target`, `node_modules`, and `DesktopApp\tests` absent.
- `Test-MediaPipelineRemuxEncodeAIO-Release.ps1 -BundleRoot <candidate> -SkipToolIntegration -SkipEndToEndSmoke` passed against that copied bundle.
- Running `New-TauriShell-PG3CleanMachineReport.ps1` from the copied bundle to `%TEMP%` reported `Bundle layout mismatches: 0` and `Tauri preview binary included: True`. It correctly detected developer tools on this workstation, so this remains local support validation only.
- After the Docs relocation and worksheet-helper fixes, a fresh current-handoff candidate was created at `C:\Users\lmmye\Documents\Codex\2026-04-20-files-mentioned-by-the-user-ass\MediaPipelineRemuxEncodeAIO_V5_PG3_CurrentHandoff_20260517_151039` with `-IncludeTauriPreviewBinary -Verify`. Manifest/layout proof showed `tauri_preview_binary_included=true`, `tests_included=false`, `dev_docs_included=false`, `personal_config_included=false`, the packaged executable present, current `Docs\inventories\SMOKE_TEST_INVENTORY.md` and `Docs\sample-validation\REAL_MEDIA_VALIDATION_EVIDENCE_TEMPLATE.md` present, and `node_modules`, `src-tauri\target`, `DesktopApp\tests`, and `Pipeline\Tests` absent.
- Copied-bundle local validation for `MediaPipelineRemuxEncodeAIO_V5_PG3_CurrentHandoff_20260517_151039` passed: release self-test during `-Verify`, `Test-TauriShell-Prereqs.ps1 -CheckOnly`, package-mode `Test-TauriShell-Launch.ps1 -Mode Packaged -TimeoutSeconds 180 -CloseTimeoutSeconds 30`, and `New-TauriShell-PG3CleanMachineReport.ps1` with `Bundle layout mismatches: 0`. The report detected 8 developer tools on this development workstation, so this is historical local support validation only.
- Rechecked the same 2026-05-17 current-handoff bundle from the copied directory after PG-2 acceptance: prereq check still passed, package-mode launch/close smoke passed, and a fresh local boundary report at `%TEMP%\pg3_current_handoff_local_dev_boundary_20260517.md` again showed `Bundle layout mismatches: 0` and `Developer tools detected outside bundle: 8`. This historical candidate was superseded by the 2026-05-18 `MediaPipelineRemuxEncodeAIO_V5_PG3_CurrentHandoff_20260518_140116` package.
- PG-3 remains unproven until the 2026-05-18 copied bundle is run on a separate clean Windows machine and the report is generated there with no developer tools detected.

Latest output-size evidence checkpoint:

- Completed backend DTO rows now expose recorded sidecar `size_policy` metadata: mode, routing profile, route reason, applicable growth limit, ratio, exceeded/enforced status, and backend message.
- WebView Completed and Home daily-driver proof now distinguish `size_policy` exceeded rows from compatibility growth that is within the backend-recorded policy. A +10% output under a compatibility +15% policy is reviewable evidence, not the same as a legacy hardcoded +5% blocker.
- This is evidence-only. It does not change FFmpeg routing, encode/remux policy, size-guard enforcement, settings persistence, Completed manifests, Pending Publish, or filesystem mutation.
- Real-media validation is still required to prove the sidecar policy, Completed row, Diagnostics logs, and actual output size agree for known samples.

Latest repair/reconcile contract checkpoint:

- `/api/contract` now includes design-only repair/reconcile contracts for Completed manifest reconciliation, Completed sidecar metadata repair, Pending Publish manifest repair, and orphan pending payload reconciliation.
- Each contract explicitly declares `mutation_enabled=false`, `frontend_allowed=false`, the candidate future command name, required preconditions, required evidence, `dry_run_contract`, `rollback_contract`, `source_file_policy`, `route_exposure_gates`, rollback/journal expectations, and actions that must not be performed.
- WebView API Contract safety review renders a `Repair/reconcile boundary` row from the backend contract so future UI work sees the boundary before adding buttons.
- This is deliberately non-mutating. It adds no repair routes, no manifest writes, no sidecar writes, no payload moves/deletes, no drain behavior changes, and no media policy changes. Future repair controls must start with backend dry-run diff commands, source-media `would_not_touch` evidence, and atomic rollback/journal tests. Source of truth: `Docs/architecture/REPAIR_RECONCILE_MUTATION_CONTRACT.md`.

Latest Settings path-evidence checkpoint:

- `/api/settings/workspace` now includes backend-authored `tool_path_evidence` for BDPGS OCR.
- WebView Subtitle Settings shows saved-config `BdpgsOcrToolPath` and `BdpgsOcrTessdataPath` resolution, file/folder existence, expected kind, `.dll`/`dotnet` posture, and ready/review/blocked state beside the BDPGS OCR toggles.
- This closes the highest-impact raw-key visibility gap without adding a WebView path picker. Path editing still goes through backend Preview/Save or direct config review, and the WebView does not resolve arbitrary paths or run OCR.

Latest Settings raw-key action-plan checkpoint:

- WebView Settings now includes a read-only `Raw-Key Action Plan` derived from the redacted backend settings workspace, field definitions, existing raw-key triage, and BDPGS OCR path evidence.
- The plan separates unknown schema-drift keys, OCR path evidence, subtitle keyword builder coverage, intentionally excluded network auth secrets, remaining advanced raw keys, and the backend-owned mutation boundary.
- This is display guidance only. It cannot stage Changes JSON, save config, edit secrets, add a path picker, resolve arbitrary paths, run OCR/FFmpeg, launch work, publish/drain, rename, rewrite manifests/sidecars, or touch media.
- Home External Dependency Digest and Diagnostics First Response now consume that same action-plan posture after the Settings workspace is loaded. This makes schema drift, high-review raw keys, and OCR path posture visible while triaging run failures without giving Home or Diagnostics settings-save, secret-edit, path-picker, OCR-run, launch, drain, publish, rename, or media-mutation authority.

Latest Launch pilot-readiness checkpoint:

- Launch now includes a read-only `Pilot Run Readiness` panel between Sample Execution and Backend Launch Preflight.
- The panel joins existing loaded evidence for selected Queue sample, saved Settings policy, backend preflight, pilot category coverage, real-media proof plan, sample execution checklist, Pending Publish posture, post-run proof plan, and mutation boundary into one compact Launch-surface checklist for a real-media pilot.
- This is an operator-trust surface only. It does not alter Start behavior, reserve launch locks, change queue scope, save settings, drain/publish, append Sample Validation records, rename files, or touch source/output/scratch media.
- The Tauri pre-window asset gate now also checks the new pilot-readiness fragments before WebView2 opens, and its stale mocked-asset fixture was corrected to serve the already-required `pendingPublishView.js`.
- Targeted validation passed with `test_application_facade`, `test_webview_real_media_smoke`, the browser-backed `test_webview_browser_launch_queue_readiness_smoke`, and `Test-TauriShell-Build.ps1`.

Latest Completed selected pilot-evidence checkpoint:

- Completed now includes a read-only `Selected Pilot Evidence Packet` between Final Output Trust and Output Acceptance.
- The packet follows the selected Completed row and consolidates output/sidecar proof, route/size/audio/subtitle evidence, Pending Publish/final-placement proof, Diagnostics/runtime context, Sample Validation readiness, manual playback checks, and mutation boundaries into one table plus copyable Markdown checklist for post-run pilot review.
- Completed Real-Media Output Proof and the packet now include `Saved policy reconciliation`, which compares completed route, recorded size policy, audio/subtitle decision signals, and Pending Publish/drain proof against saved policy-alignment categories. This is the post-run companion to Launch's pre-run policy-vs-Queue-route evidence.
- It re-renders from already-loaded Completed, Pending Publish, Sample Validation, and command-history evidence. It adds no API route, no backend mutation, no Sample Validation append, no repair/reconcile control, no publish/drain/rerun control, no settings save, no rename apply, no manifest/sidecar write, and no media policy change.
- Targeted validation covers static WebView assets, selected-row Node smoke, browser-backed Completed/Pending proof rendering, high-risk missing-output states, and command/Pending Publish re-render hooks.

Latest Home completed-evidence handoff checkpoint:

- Home Sample Validation now includes a read-only `Completed Evidence Handoff` panel that reuses the Completed Selected Pilot Evidence Packet helpers.
- The panel shows packet status, selected Completed row, blocked/review/manual counts, saved-policy reconciliation status, selectable proof checkpoints, selected-checkpoint details, and copyable Markdown before the operator previews or appends a Sample Validation record.
- The Acceptance Readiness Gate now has a separate `Saved policy reconciliation` row. It mirrors the Completed packet checkpoint so accepted evidence stays review-only when saved route/size/subtitle/audio/publish policy is not visibly reconciled with the selected completed output.
- This keeps post-run acceptance evidence visible on Home while preserving backend authority. It does not append validation records, accept output, rerun, drain, publish, repair, save settings, rename, rewrite manifests/sidecars, alter media policy, or touch source/output/scratch media.
- Targeted validation covers static WebView assets, real-media smoke static coverage, and the browser-backed Sample Validation smoke.

Latest Home sample-validation acceptance-gate checkpoint:

- Home Sample Validation now includes a read-only `Acceptance Readiness Gate` between the manual checklist and Preview/Append buttons.
- The gate joins selected sample proof, operator decision, required/recommended checklist coverage, Completed Evidence Handoff posture, backend validation-log/readiness/reconciliation state, manual playback/subtitle/audio/size expectations, and backend-only mutation boundaries.
- This is advisory only. It does not block or permit appends, append validation records, accept output, rerun, drain, publish, repair, save settings, rename, rewrite manifests/sidecars, alter media policy, or touch source/output/scratch media. Backend Preview/Append remains authoritative.
- Targeted validation covers static WebView assets, Sample Validation API/static route tests, real-media smoke static coverage, and the browser-backed Sample Validation smoke.

Latest Home accepted-record proof-review checkpoint:

- Home Sample Validation now includes a read-only `Accepted Record Proof Review` after the Acceptance Readiness Gate.
- The review chooses the selected/current accepted sample-validation record when available and turns record identity, Completed output/sidecar proof, size/output-growth proof, subtitle/audio proof, Diagnostics/run-log proof, Pending Publish/final-placement proof, current backend reconciliation, and mutation boundary into selectable rows.
- This helps operators separate current accepted proof from stale historical notes after a real-media pilot. It does not append validation records, accept output, rerun, drain, publish, repair, save settings, rename, rewrite manifests/sidecars, alter media policy, or touch source/output/scratch media.
- Targeted validation covers static WebView assets, Sample Validation API/static route tests, real-media smoke static coverage, and the browser-backed Sample Validation smoke.

Latest Home pilot-category validation summary checkpoint:

- Home Sample Validation now includes a read-only `Pilot Category Validation Summary` after the Real-Media Sample Set Guide.
- The summary groups the same backend-authored sample-set categories by current accepted category records, worksheet-only planning evidence, historical accepted records, stale/review records, and missing/planned coverage.
- This separates "we planned a sample" from "we have a current accepted record for this category" for H.264 remux, preferred-language subtitle SRT generation, audio routing/default language, encode/size policy, and deferred publish/final placement.
- This is display guidance only. It does not launch, append validation records, accept output, rerun, drain, publish, repair, save settings, rename, rewrite manifests/sidecars, alter media policy, or touch source/output/scratch media.
- Targeted validation covers static WebView assets, Sample Validation API/static route tests, real-media smoke static coverage, and the browser-backed Sample Validation smoke.

Latest real-media validation audit checkpoint:

- `/api/sample-validation` now includes a backend-authored `desktop_real_media_validation_audit.v1` payload.
- The audit conservatively rolls readiness, stale-evidence reconciliation, generated worksheet context, representative category coverage, real-media evidence gaps, pilot runbook state, and cutover gate posture into one operator status and row table.
- Home Sample Validation renders the audit in the existing summary area so the operator sees the highest-level validation posture without treating worksheets, old accepted notes, or partial evidence as daily-driver proof.
- This is read-only evidence. It does not launch, append validation records, accept output, rerun, drain, publish, repair, save settings, rename, rewrite manifests/sidecars, alter media policy, probe media, or touch source/output/scratch media.
- Targeted validation covers Sample Validation route contracts, WebView static assets, browser-backed Sample Validation rendering, and Tauri asset/build checks.

Latest real-media policy-alignment checkpoint:

- `/api/sample-validation` now includes a backend-authored `desktop_real_media_policy_alignment.v1` payload.
- The payload reuses saved Settings `settings_media_policy_readiness.v1` evidence and maps it onto the real-media pilot categories: H.264 remux/direct-play, preferred-language subtitle-to-SRT, audio routing/default language, encode/size policy, and deferred publish/final placement.
- The WebView Sample Validation summary renders the policy-alignment posture, and the Real-Media Validation Audit treats policy alignment as required evidence before a pilot looks ready.
- Launch now mirrors that policy alignment at the start surface as `Saved policy vs Queue route` evidence in both Real-Media Sample Proof Handoff and Pilot Run Readiness. It compares selected/representative Queue route text with the saved-policy categories so operators can see when the Queue row proves H.264/remux/size intent and when subtitle/audio/deferred-publish policy still needs post-run evidence.
- This is read-only evidence. It does not change route policy, size guard, subtitle conversion, audio behavior, pending publish, settings persistence, FFmpeg execution, launch, append, repair, rename, manifest writes, or media files.
- Targeted validation includes a risky saved-policy contract test for disabled size guard, disabled/drop-conflicted subtitle conversion, and no-audio allowance, plus browser-backed Launch/Queue coverage that blocks POST routes while rendering the policy-vs-route comparison.

Latest Network lifecycle-handoff checkpoint:

- WebView Network now includes a read-only `Network Lifecycle Handoff` between readiness and evidence rows.
- The handoff combines close-readiness, Network role/auth/path-map configuration, persisted worker claim health, pending done reports, runtime state-file metadata, diagnostics route availability, and the explicit promotion boundary required before lifecycle controls could ever move behind backend-owned commands.
- This keeps the Network page useful for distributed-work triage without creating split-brain lifecycle ownership. It does not start, stop, retry, reclaim, release, abort, save settings, rewrite state, mutate queue/publish/rename workflows, or touch source/output/scratch media.
- Targeted validation covers static WebView assets, the browser-backed Network smoke, the smoke wrapper scaffold check, and the JavaScript syntax check.

Latest Diagnostics first-response detail checkpoint:

- Diagnostics First Response rows are now selectable and render a detail block under the checklist.
- Row detail explains why each gate matters, what evidence was used, and where the operator should inspect next for refresh health, close-readiness, ActiveJobs/progress, state artifacts, external dependencies, Sample Validation policy reconciliation, command issues, owning-page handoff, malformed logs, and the decision boundary.
- Diagnostics First Response now includes `Sample Validation policy reconciliation`. It summarizes saved policy alignment plus Completed saved-policy reconciliation and directs the operator to Home Sample Validation, Completed Selected Pilot Evidence Packet, and Settings media policy before accepted evidence or rerun decisions.
- Completed owning-page handoff detail now also includes `Completed saved-policy reconciliation handoff`, so Diagnostics can navigate to the selected Completed row while telling the operator exactly which policy proof to inspect next.
- This keeps Diagnostics as read-only evidence/navigation. It does not launch, drain, rerun, save settings, rename, repair, delete, publish, clear state, open arbitrary paths, rewrite manifests, or touch source/output/scratch media.
- Targeted validation covers static WebView assets and the browser-backed Diagnostics handoff smoke.

Latest daily-use media-table decision checkpoint:

- Queue Launch Decision, Completed Output Acceptance, and Pending Publish Drain Decision summaries now start with explicit daily-use handoff wording, operator outcome, and scope boundary.
- Queue tells the operator it can only decide whether opening Launch is sensible; Completed tells the operator it supports trust/acceptance review but cannot mark output accepted or clean up files; Pending Publish tells the operator it only decides whether pressing the backend-owned drain button is sensible.
- The summaries now repeat that filters, selected rows, proof boards, recovery dry-runs, and rendered row caps do not narrow backend launch/drain scope, accept outputs, delete files, rerun jobs, repair manifests, or publish files.
- This is WebView text/evidence hardening only. It adds no backend route, no mutation control, no FFmpeg/media policy change, no settings save, no queue mutation, no output acceptance state, no drain behavior change, and no filesystem access.
- Targeted validation covers static WebView asset assertions and the browser-backed large-table smoke against Queue, Completed, and Pending Publish filtered 260-row payloads.

Latest Diagnostics settings handoff checkpoint:

- `/api/diagnostics/state-summary` now includes saved-config BDPGS OCR path evidence when OCR is enabled and the tool/tessdata posture is blocked or needs review.
- Diagnostics State Artifact Summary adds a read-only `settings_bdpgs_ocr_paths` issue row and read-order entry so operators investigating subtitle OCR failures see the Settings owner and safe next action without manually knowing where the OCR paths live.
- This is evidence-only. It does not add repair controls, path pickers, arbitrary filesystem reads, settings writes, OCR execution, subtitle conversion changes, FFmpeg changes, or media mutation.

Latest Maintenance toolchain checkpoint:

- `/api/maintenance` now includes backend-authored `desktop_maintenance_toolchain_evidence.v1` over the existing environment-health rows.
- The evidence classifies PowerShell, ffmpeg, ffprobe, MKVToolNix, optional GPU telemetry, and subtitle helper rows by capability, source, required/optional status, operator status, safe next action, and failure scope.
- WebView Maintenance now renders a dedicated `Toolchain Readiness` panel plus selected-row tool kind/source/capability/failure-scope detail. This is read-only packaging/runtime evidence: it cannot resolve arbitrary tools, edit PATH, install dependencies, launch media jobs, repair files, write packages, rewrite manifests, or mutate media.

Latest Sample Validation runbook checkpoint:

- `/api/sample-validation` now includes backend-authored `desktop_real_media_pilot_runbook.v1`.
- Home Sample Validation renders the runbook as status text, step rows, selected-row detail, and copyable Markdown generated from the already-loaded evidence-gap, sample-set, cutover, pilot-plan, reconciliation, and worksheet payloads.
- This closes the operator handoff between "what proof is missing?" and "what do I do during the next real-media pilot?" without adding export-file writes, launch controls, append controls, publish/drain, settings save, rename, manifest writes, or media mutation.

Latest Sample Validation post-run capture checkpoint:

- Preview/append responses now include backend-authored `desktop_sample_validation_post_run_capture.v1`.
- The WebView Preview Record result shows a post-run capture section plus copyable Markdown for remux-vs-encode decision, Completed proof, Diagnostics/FFmpeg proof, Pending Publish/final placement, subtitle behavior, audio behavior, size posture, and append decision.
- This is evidence capture guidance only. It does not change append authorization, create files, launch work, accept outputs, publish/drain, save settings, rename, rewrite manifests, or mutate media.

Latest selected-row Sample Validation comparison checkpoint:

- Completed, Pending Publish, and Diagnostics selected-row details now consume already-loaded Sample Validation records and reconciliation rows through a shared WebView helper.
- The detail panes show matching validation-record counts, accepted/current/stale/review posture, matched path fields, missing current-evidence fields, and the safe next action for the selected owner row.
- This is frontend-only readback over existing payloads. It adds no route, no JSONL append, no accept/rerun/drain/publish/repair command, no settings save, no rename apply, no manifest/sidecar rewrite, and no source/output/scratch media mutation.

Latest External Dependency Digest checkpoint:

- Home now includes a read-only `External Dependency Digest` that joins loaded Settings BDPGS OCR path evidence, Diagnostics settings handoff rows, and cached Maintenance toolchain evidence.
- Diagnostics first-response now includes an `External dependency readiness` row so OCR/toolchain blockers point operators to Settings > Subtitles or Maintenance before rerun, launch, package, or manual-review decisions.
- Maintenance is deliberately not added to the 4-second global refresh loop because its health endpoint can run helper probes. The digest consumes Maintenance evidence only after the operator opens/runs Maintenance in the current WebView session.
- This is evidence-only. It cannot install tools, edit PATH, save settings, run OCR, launch FFmpeg, drain publish, repair manifests, rewrite sidecars, or mutate media.

Latest WebView cutover-gate checkpoint:

- `/api/sample-validation` now includes backend-authored `desktop_webview_cutover_gate.v1`.
- Home renders a `WebView Cutover Gate` under Sample Validation. It summarizes backend evidence availability, current accepted sample records, required acceptance checks, playback/subtitle/audio/publish checks, generated worksheet context, stale/review history, and pilot-plan posture.
- The gate now publishes an explicit acceptance-evidence boundary and worksheet run/sample counts. Generated worksheets can make pilot context visible, but they cannot count as current accepted records unless the operator also appends an accepted `sample_validation_record.v1` that still reconciles to current backend proof.
- The gate is intentionally conservative. `ready-for-operator-trial` is limited evidence for a supervised WebView trial, not approval to remove Tk or declare production cutover.
- This is evidence-only. It cannot launch work, accept output, mark jobs complete, drain publish, save settings, rename, rewrite manifests/sidecars, or touch source/output/scratch media.

Latest real-media sample-set guide checkpoint:

- `/api/sample-validation` now includes backend-authored `desktop_real_media_sample_set_guide.v1`.
- Home renders a `Real-Media Sample Set Guide` beside the Cutover Gate and Sample Execution Checklist. It recommends a 3-5 file pilot covering H.264 remux/direct-play copy, preferred-language subtitle-to-SRT behavior, audio routing/default language, encode/size policy, and deferred publish/final placement.
- Sample Validation records now support an optional controlled `sample_category` field from the WebView Pilot Category selector. The guide deliberately distinguishes planned worksheet coverage, current accepted validation records, explicit category proof, and older fuzzy label/note/evidence matches. Accepted records with no category remain generic evidence and produce a backend warning during preview/append.
- The guide now states that worksheet rows are planned/context coverage only. Required categories stay planned/review until a matching accepted validation record remains current against backend evidence.
- The Home guide now has an explicit `Use Selected Category` handoff that copies the selected guide row's backend category key into the local Pilot Category selector, and the Sample Validation records table shows record category, current-evidence status, and missing-proof count without requiring row-detail inspection. This is local/display state only; preview/append remains backend-owned evidence and the handoff cannot mutate media or pipeline state.
- Sample Validation record detail now has an explicit `not checked` path when a persisted record has no matching reconciliation row. Browser smoke coverage renders current, stale, no-reconciliation, and empty records-table states and verifies stale rows show missing-proof counts in the table before detail inspection.
- Home Sample Validation now has a backend-authored `Real-Media Evidence Gaps` panel. It converts the existing readiness, reconciliation, worksheet, pilot-plan, cutover-gate, and sample-set guide payloads into a single read-only checklist of missing proof: current backend evidence, selected sample/saved policy, post-run Completed and Diagnostics proof, Pending Publish/final-placement proof, manual playback/subtitle/audio checks, representative category coverage, accepted-record reconciliation, and generated worksheet context. This is gap visibility only and cannot launch, append records, accept outputs, publish/drain, save settings, repair, rename, rewrite manifests, or touch media.
- The guide now also reports accepted/current/stale/review category-record counts per category. Launch mirrors that coverage in the `Real-Media Sample Proof Handoff` and `Start Decision Summary`, leading with current category records and labeling accepted-but-non-current records as historical so a stale/review category record remains visible but does not become ready proof.
- This is evidence-only guidance. It cannot launch work, accept output, append records, publish/drain, save settings, rename, rewrite manifests/sidecars, scan arbitrary media folders, or touch source/output/scratch media.

Latest WebView parity checkpoint:

- Queue now carries an explicit read-only `Backend Launch Scope Preview` panel. It states backend launch route authority, loaded row count, visible filtered row count, selected-row boundary, cached backend preflight evidence, and recent backend start command evidence so the operator can see exactly what the backend will evaluate versus what the table is showing. Queue display filters, selected rows, and render caps remain display-context only and do not narrow launch scope. The large-table browser smoke verifies the panel boundary wording and confirms no mutation POSTs.
- Pending Publish now carries an equivalent read-only `Backend Drain Scope Preview` panel. It states backend drain route authority, parked row count, visible filtered row count, selected-row boundary, durable drain summary, and recent drain command evidence. Pending Publish display filters, selected rows, and render caps remain display-context only and do not narrow drain scope. The Pending Drain Guard browser smoke verifies the panel boundary wording and confirms no `/api/pipeline/start` POST is sent before the guarded click.
- Home Sample Validation now includes a backend-authored `Operator Sample Execution Checklist` in `/api/sample-validation`. The checklist separates before-launch sample/policy checks, backend-owned Launch boundary proof, post-run Completed/Diagnostics/Pending Publish checks, and evidence-record steps, with selectable WebView detail for backend evidence, operator proof, unsafe-if-ignored text, and guardrails. It is read-only guidance: it cannot launch, accept, publish, rename, save settings, rewrite manifests/sidecars, or touch source/output/scratch media.
- Sample Validation preview/append payloads now include a backend-authored `desktop_sample_validation_evidence_packet.v1`. It turns the proposed sample record, current backend evidence, and append-readiness result into a route/output/log/publish/playback-subtitle-audio-size proof packet with stop conditions and guardrails before an evidence note is recorded. It is preview guidance only and cannot mark jobs complete, accept outputs, clear failures, drain Pending Publish, rewrite manifests/sidecars, launch work, save settings, rename files, or touch media.
- `/api/sample-validation` now also includes backend-authored `desktop_real_media_worksheet_runs.v1` generated worksheet evidence from `Docs\RealMediaValidationRuns`. Home renders a `Generated Pilot Worksheets` panel with worksheet status, bounded sample rows, bounded pilot-packet rows, selected-sample match evidence, safe next action, and a read-only guardrail. This gives the operator worksheet context without appending evidence, accepting outputs, launching work, draining Pending Publish, saving settings, renaming, scanning arbitrary media folders, or touching source/output/scratch media.
- Launch now carries that generated worksheet context into the `Real-Media Sample Proof Handoff`. The new `Generated worksheet evidence` checkpoint uses the same Home worksheet matching helper to show whether the selected real-media sample has a matching worksheet run, plus worksheet status, run/sample/packet-row counts, first matching worksheet detail, and a read-only start-surface guardrail. It does not add routes, start work, append validation records, accept outputs, publish/drain, save settings, rename, rewrite manifests/sidecars, scan arbitrary media folders, or touch media.
- Launch also carries recent Sample Validation record context into the same proof handoff. The new `Sample Validation record evidence` checkpoint uses Home record/reconciliation helpers to show whether the selected real-media sample has a matching validation record, whether that record is current/stale/review against backend evidence, and the first matching record detail. It is read-only correlation over the already-loaded `/api/sample-validation` payload and cannot append records, start work, accept outputs, publish/drain, save settings, rename, rewrite manifests/sidecars, or touch media.
- Launch now mirrors that same sample execution checklist at the actual start surface. The new read-only Launch table shows the before-launch, backend Launch boundary, post-run proof, and evidence-record rows beside Launch preflight/scope evidence, but still cannot POST, start work, accept output, append validation records, publish/drain, save settings, rename, rewrite manifests/sidecars, or touch media.
- Launch now labels its Real-Media Sample Proof Handoff as pre-run intent context. It can prove selected intent, saved policy posture, backend preflight, worksheet/sample-validation context, and checklist status before Start, but it explicitly points the operator back to Completed, Pending Publish, Diagnostics, playback, and Sample Validation for finished-output proof after the run.
- Launch now includes a compact read-only `Start Decision Summary` directly above the Pipeline Start controls. It rolls up Launch readiness, timing/schedule posture, backend preflight, Queue Launch Decision, Settings/policy state, Launch Scope Reconciliation, real-media proof, sample execution checklist, and recent Launch command evidence before the operator presses Start. It cannot POST, reserve locks, launch work, save settings, drain, publish, rename, rewrite queue state, or touch media; backend start routes remain final authority.
- Command Results and Diagnostics command triage now include a central read-only `Owner page live state handoff`. Selected commands compare backend row keys, paths, selected sources, and representative command rows against already-loaded Queue, Completed, Pending Publish, Launch, Settings, Rename, or Diagnostics state. Pending Publish drain failures now show cached pending-row match evidence plus Publish Button Guard state before retry guidance. This is cached frontend evidence only and does not add retry, launch, drain, save, rename, repair, delete, publish, manifest-write, diagnostics allowlist, or media mutation authority.
- Schedule now includes `Schedule Coverage Review`, selectable weekly day details, a backend-owned Schedule Editor, a `SmokeTests/Test-WebViewScheduleSmoke.ps1` Node-backed smoke, and a `SmokeTests/Test-WebViewBrowserScheduleSmoke.ps1` Chrome/Edge-backed smoke. The page summarizes payload health, enforcement, current-window decision, weekly allowed-hour coverage, warnings, all-day/no-window day posture, and the backend-owned save boundary. The editor stages local day-window text, previews backend parsing/changed-days, and saves only `schedule_enabled`/`schedule_grid` through confirmed backend app-state routes; the browser smoke verifies the real backend-served editor, Schedule-owned command history, persisted app-state keys, save-result feedback after refresh, and Launch timing trust from the refreshed schedule payload. The Schedule page still cannot launch work, override schedule gates, mutate queue/media state, or directly arm the watcher.
- `/api/schedule` now exposes read-only backend `continuous_watcher` state. Schedule Coverage Review, Schedule Timing Trust, and Launch readiness show whether the watcher is idle, armed, completed, canceled, stop-requested, unavailable, or failed, including PID/deadline/error evidence when present. This closes the operator visibility gap without moving watcher lifecycle or stop-flag writes into the WebView.
- Close-readiness now blocks while the backend schedule-stop watcher is armed, even if the current snapshot appears idle. This keeps the Tauri/WebView shell from treating shutdown as safe when shutdown would cancel the future stop-at-window-end guard.
- Close-readiness and backend shutdown warning command results now carry structured `continuous_watcher` evidence. WebView Close Readiness, Backend Lifecycle, and command history can show watcher status, PID, deadline, stop-request state, and watcher-specific "do not retry shutdown blindly" guidance.
- `Test-WebViewBrowserLifecycleSmoke.ps1` now validates that lifecycle behavior in real Chrome/Edge rendering. It proves armed watcher state disables the WebView backend shutdown button, records only a local warning without prompting or posting, and that a safe close-readiness state posts only the backend-owned `/api/backend/shutdown` request after confirmation.
- `Test-LocalApiLifecycleContractSmoke.ps1` now validates the browser-free local API lifecycle contract for safe and watcher-blocked close-readiness, `/api/backend/shutdown` token enforcement, safe shutdown info payloads, and watcher-blocked failure payloads against temporary test backends. This gives the Tauri/WebView transition a fast backend route gate without requiring Chrome/Edge.
- The native Tauri close prompt now parses the same structured watcher evidence and shows watcher status, PID, deadline, stop-request state, bounded watcher message/error text, and the fact that closing the local backend removes the in-process stop-at-schedule-boundary guard. Tauri startup asset validation also verifies the backend-served WebView contains the Backend Lifecycle panel and guarded shutdown path before opening WebView2.
- Launch backend preflight now includes a backend-authored `Continuous schedule-stop watcher` row. It surfaces current schedule-window timing evidence, reports backend watcher readiness for normal scheduled WebView `continuous` starts, and marks `Ignore Schedule` continuous starts as high-review intentional bypasses. Backend start arms the watcher only after the process launches and only when a current schedule stop boundary is available.
- Completed now carries local filter-scope evidence into the Output Acceptance checklist. When Completed text/status/investigation filters are active, the checklist shows visible/hidden loaded-manifest-row counts, hidden blocked/review counts, and repeats that backend action scope for rerun, cleanup, reconciliation, diagnostics, and manifest authority is not narrowed to the visible WebView table subset. Completed filter changes refresh this evidence immediately, and the browser-backed Large Table smoke verifies the hidden broken-row acceptance boundary without posting start, rerun, queue-open, completed-open, pending-open, settings-save, rename, or publish mutation routes.
- Queue now carries local filter-scope evidence into the Launch Decision Checklist, and Launch's Saved Settings vs Launch Intent checklist echoes the same Queue display-scope boundary at the actual start-decision surface. Queue also has a dedicated read-only `Backend Launch Scope Preview` panel that summarizes loaded rows, visible filtered rows, selected-row boundary, backend `/api/pipeline/start` authority, cached backend preflight, and recent backend start evidence. When Queue text/status/investigation filters are active, the checklists and scope preview show visible/hidden loaded-row counts, hidden blocked/review counts, and repeat that backend Launch scope is not narrowed to the visible WebView table subset. Queue filter changes refresh this evidence immediately, and the browser-backed Large Table plus Launch/Queue smokes verify the hidden blocked-row launch-scope boundary without posting start, rerun, queue-open, settings-save, rename, or publish mutation routes.
- Launch now includes a selectable read-only Launch Scope Reconciliation table. It joins the selected Launch mode/override, Queue payload, Queue display filter scope, Queue Launch Decision, cached Pipeline backend preflight, close-readiness/active-work posture, Schedule/override scope, recent Launch command evidence, and backend-authority boundary into one pre-start checklist. Queue filter changes and backend preflight refreshes rerender the reconciliation, but it cannot launch, save settings, rewrite queue state, drain, publish, rename, delete, or touch media files.
- Pending Publish now carries local filter-scope evidence into Drain Action Confidence, Drain Decision Checklist, Publish Button Guard, and a dedicated read-only `Backend Drain Scope Preview` panel. The scope preview summarizes loaded parked rows, visible filtered rows, selected-row boundary, backend `drain_pending_pushes` authority, dry-run recovery evidence, durable drain summary, and recent drain command/event evidence. When status/text/investigation filters are active, the page shows visible/hidden parked-row counts, hidden blocked/review counts, and repeats that display filters do not narrow backend drain scope. Filter changes refresh the guard and scope preview immediately, and the browser-backed Pending Drain Guard and Large Table smokes verify this read-only boundary without posting `/api/pipeline/start`.
- Pending Publish now also includes a read-only `Post-Drain Trust Review`. It is intentionally separate from the pre-drain button guard: after a drain, it correlates current parked rows, durable drain summary, recent backend drain events/logs, Completed output proof, Sample Validation deferred-publish posture, and latest drain-command evidence before the operator trusts a sample, accepts validation evidence, retries publish, or reruns sources. It cannot drain, repair, publish, mark complete, append validation records, or touch media.
- Queue, Completed, and Pending Publish now include a compact read-only `Selected Row At A Glance` strip above long selected-row detail text. The strip repeats selected row identity, trust/status, route/output/drain proof, primary concern, safe next step, current filter visibility, and the backend authority boundary. It gives the operator a fast answer before reading the full detail block, but cannot launch, rerun, drain, repair, reconcile, save settings, rename, publish, delete, rewrite manifests, or touch media.
- Rename now includes a read-only `Apply Outcome Review` under Last Apply Result. It converts backend `rename.apply` command results into checkpoints for backend result, selected scope, applied rows, media/sidecar operations, undo manifest evidence, warnings/errors, local Paths textarea update evidence, and the backend-only mutation boundary. It improves post-apply trust without adding retry/undo controls or moving filesystem mutation into WebView.
- Diagnostics now includes a read-only `First Response Checklist` before deeper drilldowns. It rolls refresh payload health, close-readiness/active work, ActiveJobs/progress posture, State Artifact read order, recent command issues, owning-page handoffs, log/malformed-state clues, and mutation guardrails into a single operator triage sequence. It uses already-loaded backend payloads only and cannot launch, drain, save settings, rename, repair, delete, publish, clear state, open arbitrary paths, or touch media.
- Settings Patch Preview now includes a read-only `Effective Policy Trust` panel. It separates launch-active saved backend config from inactive WebView builder/Changes JSON candidates, summarizes saved media-policy readiness, staged patch activity, preview/save signature evidence, staged policy-delta attention, and the backend-only mutation boundary, and exposes selectable detail rows before the operator trusts or saves a settings change.
- Launch now includes a selectable read-only `Active Media Policy Boundary` under Saved Settings Trust. It compares launch-active saved subtitle/container, audio, and pending-publish/source-safety policy against staged Changes JSON candidates and states that staged candidates are not launch-active until backend Preview Patch, Save Patch, and settings reload/refresh succeed. The Settings-to-Launch intent detail now surfaces this boundary for unsaved patches, while the browser-backed Settings/Launch smoke verifies staged subtitle contradiction, staged audio review, and staged pending-publish/source-safety review without posting Save Patch or Launch commands.
- Launch Risk Handoff rows are now selectable and show proof-chain detail for each saved-settings risk: evidence source, operator proof requirement, and mutation boundary. The browser-backed Settings/Launch smoke now clicks the remux/encode size posture row and verifies that source/output size proof still requires a real Completed sample before unattended trust.
- Completed now includes a read-only `Real-Media Output Proof` board. It joins selected Completed output/sidecar evidence, route/size/media decision evidence, Pending Publish/drain proof, Diagnostics/runtime signals, Sample Validation handoff guidance, and the operator mutation boundary into one selectable proof ladder before a real-media sample is trusted. The board refreshes when Pending Publish payloads refresh, but it cannot accept, rerun, drain, repair, delete, publish, append validation records, rewrite manifests/sidecars, save settings, rename, or touch media.
- Completed's Real-Media Output Proof board now includes a `Launch-to-output transition` checkpoint. It separates Launch pre-run proof from post-run verification and tells the operator to compare command history, Completed row, Pending Publish, Run Logs, Last Stderr, playback, and Sample Validation before accepting or rerunning a sample.
- Completed now includes a compact read-only `Final Output Trust Walkthrough` after the proof ladder. It turns the selected Completed row into an ordered operator path: Completed Manifest row, output/sidecar on disk, Pending Publish/drain final-placement proof, Plex/media policy proof, Diagnostics/log proof, and Sample Validation evidence boundary. It is final read-order guidance only and cannot accept, repair, rerun, drain, publish, delete, save settings, rename, rewrite manifests/sidecars, or touch media.
- Diagnostics now includes an `Owning Page Evidence Handoff` panel. It turns loaded Queue, Completed, and Pending Publish review rows into a read-only table that tells the operator which page owns the next review step, why the row is flagged, which backend allowlisted Diagnostics targets support the evidence, and which backend-selected row open-target names exist on the owning page. The panel can use `Go To Owner Row` to navigate to Queue, Completed, or Pending Publish and locally select the already-loaded row for inspection. It deliberately cannot POST, launch, rerun, drain, repair, rewrite, move, delete, publish, accept, or open arbitrary filesystem paths; row file/folder opens remain on Queue, Completed, and Pending Publish using row keys plus target names.
- Diagnostics owning-page handoff now gives Completed rows a direct `Final Output Trust Walkthrough` map. Missing output/sidecar rows point the operator to step 2, pending/drain/final-placement evidence to step 3, Plex/media route/size/audio/subtitle evidence to step 4, runtime/log evidence to step 5, and sample-validation/acceptance evidence to step 6. The `Go To Owner Row` action still performs local selection only and now selects the mapped Completed final-trust step when the helper is loaded, otherwise it falls back to explicit walkthrough guidance.
- Completed/Pending proof and backend publish reconciliation now separate final-placement conflicts from no-proof missing outputs. A missing Completed output that still has exact Pending Publish evidence is labeled `missing output still parked`; a missing output with exact durable drain-summary evidence is labeled `missing output with drain proof`; a missing output with neither remains blocked as `missing output without pending proof`. This is evidence-only routing for operator review and does not add repair, reconcile, rerun, cleanup, drain, publish, manifest-write, or media mutation authority.
- Command Results and Diagnostics command triage now reuse that Completed/Pending final-placement proof when a selected command is a pending-publish, drain, publish, or missing-output context. The command detail, diagnostics evidence correlation, and failure-resolution checklist show cached proof rows, still-pending counts, drain-proof counts, no-proof blockers, and a read-first order back to Completed/Pending proof before another drain, rerun, cleanup, or publish retry. This is evidence-only and does not add command-history retry controls or any filesystem/media mutation authority.
- `Test-WebViewBrowserHighRiskSmoke.ps1` now starts a temporary local API, launches installed Chrome/Edge headless through Chrome DevTools Protocol, loads the real backend-served WebView page, and verifies blocked Queue, broken Completed, and do-not-drain Pending Publish selected-row guidance in an actual browser runtime. It covers both injected fixture rows and backend-produced high-risk rows from on-disk Queue, Completed, Pending Publish, and runtime-event state; it does not post mutation commands, launch pipeline work, drain pending publish, rename, save settings, or touch media.
- `Test-WebViewBrowserDiagnosticsHandoffSmoke.ps1` now starts a temporary local API, launches installed Chrome/Edge headless through Chrome DevTools Protocol, loads the real backend-served WebView page, clicks actual Queue/Completed/Pending table rows for backend-produced risk rows, verifies selected-row investigation signals, combined row review plans, and current-filter visibility, verifies text/status/investigation table filters warn when blocked/warning rows are hidden before launch/rerun/publish decisions, verifies local clear-filter buttons restore selected-row visibility, verifies Diagnostics First Response saved-policy reconciliation detail, then clicks diagnostics bridge, bounded tail, backend-allowlisted open controls, and Diagnostics `Go To Owner Row` controls for Queue, Completed, and Pending Publish. It also verifies generated active/malformed ActiveJobs table rows, selected ActiveJobs detail/action guidance, and stale runtime-progress guidance. It verifies selected-row details, filter guardrails, tail output, local owner-row navigation feedback, and `diagnostics.open` command-result feedback without posting mutation commands.
- `Test-WebViewBrowserPendingDrainGuardSmoke.ps1` now starts a temporary local API, launches installed Chrome/Edge headless, renders backend-produced pending publish state, injects a backend-shaped blocked recovery dry-run result, verifies the Publish Button Guard refreshes immediately from that recovery evidence, then clicks `Publish Parked Outputs` and proves the blocked click records local `frontend_guard` evidence without posting `/api/pipeline/start` or asking for confirmation. The underlying WebView now refreshes the final guard after recovery-plan renders and command-history changes, so the last action gate does not lag behind the decision checklist.
- `Test-WebViewBrowserCompletedPendingProofSmoke.ps1` now starts a temporary local API, launches installed Chrome/Edge headless, renders backend-produced Completed and Pending Publish state, selects the Completed Real-Media Output Proof ladder, verifies the Completed Sample Validation handoff checkpoint, selects the Completed-to-Pending output proof board, verifies exact completed-output to pending-destination overlap detail, selects a Pending Publish row to verify Completed Manifest correlation and the Pending Publish `deferred-publish` Sample Validation handoff, then injects a missing-output Completed row with no pending proof and verifies blocker detail. The proof details explicitly state same-leaf matches are duplicate-title hints only and that the panels cannot append validation records, accept, repair, rerun, drain, cleanup, delete, publish, rewrite manifests, or touch media files.
- Browser-backed WebView smokes now share `DesktopApp\tests\webview_browser_smoke_support.py` for Chrome/Edge discovery, free-port allocation, bounded subprocess failure output, process-result assertions, and the generated Node/CDP runner prelude. The shared prelude owns payload loading, browser debug-endpoint polling, page WebSocket discovery, CDP client setup, console/error collection, and rich browser exception capture. The individual smoke files keep only scenario-specific scripts, ready conditions, payload shape, timeouts, and mutation guardrails. Failures now report return code plus bounded stdout/stderr consistently, and CDP runtime-evaluation errors preserve exception description/value/detail text so broken selectors or WebView exceptions are easier to diagnose from the Python failure alone.
- `New-RealMediaValidationWorksheet.ps1` now creates timestamped Markdown evidence worksheets from `Docs\sample-validation\REAL_MEDIA_VALIDATION_EVIDENCE_TEMPLATE.md`, optionally prefilling sample paths, sample categories, expected routes, operator, shell, machine, and workspace. It has a `-PlanOnly` JSON mode, includes a WebView pilot-evidence-packet capture table, writes only Markdown evidence, and does not launch the app, process media, probe FFmpeg, rename files, save settings, publish outputs, drain pending publish, mutate queue state, or touch source/output/scratch media. Generated worksheets default to `Docs\RealMediaValidationRuns`; release packaging now excludes generated worksheets while keeping the folder README so personal paths and operator notes do not leak into clean deployable packages.
- Diagnostics tail payloads now include backend-authored evidence for operator posture, line counts, error/warning/active/state clue counts, highlighted issue/warning/process/state lines, and safe next action. The WebView renders that evidence beside the raw bounded tail, so `Last Stderr` and other allowlisted files are easier to interpret before any retry, close, rerun, drain, or publish decision.
- The `SmokeTests/` browser-smoke validation ladder now includes `Test-WebViewBrowserNetworkSmoke.ps1` and `Test-WebViewBrowserTelemetrySmoke.ps1`. These expose existing real-browser tests for read-only Network runtime state-file evidence, worker visibility/filter guardrails, and Live telemetry/NVENC `0%` visibility without adding lifecycle controls, live GPU sampling, or media mutation.
- Queue, Completed, and Pending Publish now show read-only table-filter summaries, status selectors, and investigation views. Queue views include launch blockers, runtime failed, deferred checks, priority, encode/remux, and TV parse review. Completed views include missing output, size growth, sidecar issues, runtime failed, encode/remux, and route review. Pending Publish views include do-not-drain, missing payload, invalid manifest, missing sidecars, orphan payload, and ready-to-drain. The summaries count visible status mix and explicitly warn when the current text/status/investigation filter hides blocked/warning review rows. Filtering stays display-only and does not change backend launch scope, completed history, pending drain scope, recovery plans, manifests, payloads, or publish commands.
- Selected Queue, Completed, and Pending Publish row details now include an "Investigation view matches" block that explains exactly which focused views would include that row and why, while repeating that these views are display-only and cannot launch, rerun, repair, drain, rewrite manifests, publish, or mutate files.
- Selected row details now also show quick signals and current-filter visibility, including the exact active text/status/investigation filter hiding the selected row. Queue, Completed, and Pending Publish each gained a clear-filter button that resets local display filters only and leaves backend launch, manifest, rerun, cleanup, recovery, drain, payload, and publish scopes unchanged.
- `Test-WebViewRowDetailSmoke.ps1` now starts a temporary local API, fetches backend-served Queue, Completed, Pending Publish, diagnostics bridge, and DOM helper assets, evaluates them with mocked selected-row DOM state, and verifies that Queue, Completed, and Pending Publish selected-row detail panes render real-media trace, operator trust summary, diagnostics handoff, combined read-first/cross-check/decision plans, and diagnostics guidance text without issuing mutation commands. It also runs adversarial selected-row variants for blocked TV parse/runtime failure, missing Completed output/sidecar with size growth, and unreadable Pending Publish manifest/do-not-drain recovery so high-risk rows cannot silently render as ready-looking.
- The row-detail smoke now directly checks Pending Publish Sample Validation handoff wording for ready-looking and blocked rows, including the rule that missing-payload, invalid/unreadable-manifest, orphan-payload, diagnostic-error, and other blocked/degraded parked-output evidence must stay hold/review rather than accepted.
- The row-detail smoke now also directly checks Completed/Pending path-evidence correlation using UNC-style paths, mixed slash/backslash paths, Unicode filenames, exact destination/source matches, durable drain summary matches, and same-leaf duplicate-title hints. Exact normalized paths remain proof-strength evidence; same-leaf rows remain review-only.
- Shared command evidence formatting now backs Settings command history, Rename apply history, Launch start history, and Pending Publish drain/open/recovery-plan history. Page-specific histories keep their local detail suffixes, but status, local/journal source, owner page, issue level, and bounded backend message text now come from the global command-history helper so local snippets do not drift from Command Results/Diagnostics interpretation.
- Shared command evidence formatting now also backs Queue open, Completed open, Diagnostics open, Reports open, Network diagnostics open, Maintenance dry-run, pipeline control, and backend lifecycle histories. The WebView keeps page-specific detail counts/targets, but all compact command snippets now share the same backend result/source/owner/issue/message interpretation.
- `Test-WebViewCommandEvidenceSmoke.ps1` now starts a temporary local API, fetches backend-served WebView JavaScript, evaluates it with mocked DOM state, injects fixture command history, and verifies that Queue, Completed, Pending Publish, Diagnostics, Reports, Network, Maintenance, Launch control, backend lifecycle, Rename, Settings, and Launch histories render shared command owner/issue evidence without issuing mutation commands.
- Diagnostics State Artifact Summary now includes a backend-owned `Backend Read Order` triage. `/api/diagnostics/state-summary` returns operator posture, operator counts, summary lines, and ordered triage rows with read-first/open-next allowlist targets, reason, safe next action, recovery stage, and unsafe-if-ignored text. The WebView renders those rows with selectable detail and backend-allowlisted read/open actions only. The generic Diagnostics Tail/Open controls now expose `sample_validation_log`, and JSONL schema detection recognizes both `schema_version` and `schema` so sample-validation records report `sample_validation_record.v1` correctly.
- Home now includes a backend-owned `Sample Validation Record` flow. The WebView builds a proposed `sample_validation_record.v1` from already-loaded sample evidence, previews it through `/api/sample-validation/preview`, appends it through `/api/sample-validation/append`, and reads recent records from `/api/sample-validation`. The read payload now includes backend-authored log posture, decision/proof/check/evidence counts, latest-record summary, pilot checkpoint counts, pilot attention rows, next required pilot action, and safe next action, while Home shows proposed evidence coverage before preview/append. Preview and append results now also include `desktop_sample_validation_current_evidence.v1`, so an accepted sample can be marked stale before recording if current Completed/Diagnostics proof no longer matches. Records are written only to `State\Validation\sample_validation_log.jsonl`, are visible through Diagnostics as `sample_validation_log`, and command history classifies append results under `Home / Validation` with the validation log as the related diagnostics artifact. The record remains operator evidence only: it does not mark jobs complete, clear failures, drain pending publish, rewrite manifests/sidecars, launch work, or mutate media files.
- `Test-WebViewBrowserSampleValidationSmoke.ps1` now drives the real backend-served Home Sample Validation panel in Chrome/Edge headless. It verifies the backend-authored real-media pilot plan, readiness/reconciliation summary, preview-only current-evidence result, and Pending Publish review warning while proving that no append, launch, audit, rerun, drain, publish, rename, settings-save, queue mutation, or media-path mutation route is posted.
- The Sample Validation browser smoke now explicitly proves Real-Media Sample Set row selection is review-only and does not auto-apply the Pilot Category selector. It then verifies both H.264 and deferred-publish category handoffs require the explicit `Use Selected Category` button before the preview request carries the controlled category key.
- `Test-WebViewBrowserHomeLiveStateSmoke.ps1` now drives the real backend-served Home, Live Progress, and Diagnostics runtime-progress surfaces in Chrome/Edge headless against generated temporary media state, generated active-progress state, a generated ActiveJobs record, and a generated command journal. It verifies Daily-Driver Checklist, Operator Readiness, Active Work, Live Progress Details percent/current-item/route fields, selectable Progress Evidence Current Item and ActiveJobs rows, Diagnostics runtime progress summary, Command Results, Sample Validation posture, and the Real-Media Validation Worksheet handoff while proving that live-state rendering sends no POST routes and cannot append validation records, launch work, drain, publish, rename, save settings, mutate queue state, or touch media.
- `Test-WebViewBrowserLaunchQueueReadinessSmoke.ps1` now drives the real backend-served Launch, Queue, and Schedule readiness surfaces in Chrome/Edge headless against generated temporary media state plus generated launch command history and a temporary Sample Validation record. It verifies Launch readiness/timing trust, Launch Scope Reconciliation, the Launch Start Decision Summary, Launch generated-worksheet match evidence, Launch Sample Validation record match/reconciliation evidence, backend `GET /api/launch/preflight`, Queue Launch Decision, Schedule guidance/timing trust, close-readiness, and launch command-review correlation while proving that readiness rendering sends no POST routes and cannot start work, drain, publish, rename, save settings, mutate queue state, or touch media.
- `/api/sample-validation` now also returns backend-authored `desktop_sample_validation_readiness.v1` data. Home shows required evidence counts, blockers, review rows, and safe next action before the existing validation-log history so a real-media note is not presented as ready unless Queue, Completed, Diagnostics, Pending Publish, Settings, and validation-log evidence are coherent enough to record. The readiness payload is read-only and cannot accept output, repair state, publish, rename, save settings, launch work, or touch media.
- `/api/sample-validation` now also returns backend-authored `desktop_sample_validation_reconciliation.v1` data. Home compares recent validation records against bounded current Queue, Completed, Pending Publish, and RunLogs evidence and labels historical records as current, review, stale, or unknown. Accepted exact/partial-path records become stale when current Completed proof no longer contains the recorded source/output. This is read-only historical evidence comparison and does not scan arbitrary output shares, accept output, repair state, publish, rename, save settings, launch work, or touch media.
- A fixture-backed WebView real-media evidence smoke test now starts the real local API against temporary sample state, serves the real WebView index/assets, and verifies a TV sample across Queue, Completed, Pending Publish, Diagnostics, Settings, Commands, and Contract payloads without issuing mutation commands. The `SmokeTests/Test-WebViewRealMediaEvidenceSmoke.ps1` wrapper makes this available as a quick operator/developer gate while explicitly stating that it does not process media, launch pipeline commands, publish, rename, save settings, or modify source/output/scratch media. This is still not FFmpeg proof, but it closes the gap between static asset checks and real-media operator validation.
- The Tauri shell now validates backend-served WebView assets before opening the window. After backend health and route-contract checks, Rust fetches `/`, `/assets/app.js`, and `/assets/crossPageContextView.js` and verifies bootstrap injection plus critical Home/Settings/Diagnostics/real-media worksheet fragments. Missing/stale static assets now fail startup before a blank or partially broken WebView opens; the live Tauri launch/close smoke passed after this gate was added.
- `Test-WebViewSettingsPatchEvidenceSmoke.ps1` now starts a temporary local API against a generated temporary PSD1, validates backend-served Settings preview/save result-panel assets, runs backend Preview Patch, verifies Save Patch is denied without `confirm_save`, runs confirmed Save Patch, verifies reload/workspace evidence, and checks command history without using the current saved config or touching media.
- Home Cross-Page Context now includes a selectable `Real-Media Validation Worksheet` that joins selected/recent sample identity, Queue route/remux-vs-encode evidence, Completed output/sidecar/size proof, Pending Publish/final-destination posture, Diagnostics run clues, saved route/size/subtitle/audio/pending-publish policy posture, Sample Validation readiness/reconciliation/pilot posture, and acceptance-boundary guidance into one read-only handoff for known sample testing. It uses already-loaded backend payloads only and does not save, accept, repair, rerun, drain, delete, publish, rename, rewrite manifests, or touch media files.
- Completed now includes a selectable `Queue / Completed Route Agreement` panel that compares the loaded Completed manifest preview against current Queue payloads for completed-source/current-queue exact overlaps, route mismatches, reason mismatches, same-filename duplicate-title hints, route-proof coverage, and aggregate agreement status. This is read-only correlation only; launch, rerun, repair, reconcile, drain, delete, manifest writes, and media policy remain backend-owned.
- Pending Publish now includes an action-level `Publish Button Guard` above `Publish Parked Outputs`. The guard converts the existing drain decision checklist into local click behavior: `Do not drain`, `Evidence incomplete`, and `Not evaluated` states are recorded as warning command results without POSTing to the backend, while allowed/review attempts get a stronger confirmation message with row counts, issue counts, missing-payload evidence, durable drain summary status, and latest drain command evidence. The backend `/api/pipeline/start` drain path remains authoritative.
- Network now includes a selectable read-only Network Evidence Checklist that joins role/settings posture, close-readiness lifecycle boundary, `/api/network/workers` contract coverage, persisted worker rows, local worker recovery state, diagnostics targets, and mutation boundaries. Stale wording that said worker-board data was not exposed has been corrected to persisted-worker-state visibility while keeping live dispatcher lifecycle rows Tk-owned.
- Diagnostics now includes a Backend Lifecycle handoff that joins close-readiness, active-work state, warnings, local lifecycle command history, and the existing token-protected backend shutdown command. The WebView shutdown button remains disabled unless the loaded close-readiness payload reports safe, and unknown/active-work attempts are recorded as local warning command results instead of posting shutdown.
- Settings now includes a read-only Active Media Policy Handoff that joins visible builder state for routing profile, size guard, growth limits, movie/TV thresholds, H.264 copy/remux precision, remux-safe codecs, video encoder/tuning/legacy flags, container/subtitle mux posture, TX3G/BDPGS/ASS original preservation, audio default/passthrough/no-audio policy, and pending-publish recovery posture. Launch Risk Handoff now surfaces the matching saved H.264 copy, route/size/encoder, container, and original-subtitle evidence before backend-owned start actions.
- Settings Patch Preview now includes a read-only Staged Media Policy Delta that compares current saved values against the current local Changes JSON candidate across routing/size, video, subtitle/container preservation, audio predictability, publish/source safety, runtime guardrails, and network/worker posture. Launch unsaved-settings warnings now echo that staged delta status and the first local review row while still stating that Launch uses saved backend settings only. This closes the gap between visible builder state and manually edited staged JSON without adding any frontend-owned save, launch, FFmpeg, publish, rename, or filesystem mutation authority.
- Rename now includes a read-only Apply Readiness ledger immediately before backend apply. It turns the current checked/selected scope into explicit checkpoints for backend preview availability, selected_sources scope, blocked rows, duplicate targets, existing destination collisions, warnings/matches, TV order or movie scrub review, sidecar/force/override impact, and the backend-only mutation boundary. Empty-path and preview-error states now clear stale preview rows before recomputing selection/readiness evidence. The WebView apply handler now stops duplicate-target/existing-destination readiness blockers before confirmation/backend POST, while backend `/api/rename/apply` remains authoritative. `test_webview_rename_readiness_smoke.py` covers ready and duplicate-target scopes in Node, and `Test-WebViewBrowserRenameSmoke.ps1` verifies the same Rename row-click/readiness/no-post behavior in installed Chrome/Edge headless without issuing mutation commands.
- Settings now includes a read-only Backend Preview / Save Result handoff that ties the current staged Changes JSON signature to the latest backend Preview Patch and Save Patch results. It shows whether preview/save evidence is fresh, stale, missing, failed, saved, and reloaded, and the Tauri pre-window asset gate now verifies this handoff before opening the WebView2 shell.
- Launch Command Review now provides backend-allowlisted Diagnostics retry guidance for selected pipeline/audit/CSV rerun start commands, including read-first/open-next targets and action buttons for Last Stderr, Run Logs, Active Jobs, Queue Snapshot, State, Latest Failure, Audit Reports, and Failed Reports as appropriate.
- Launch Command Review now correlates recent pipeline/audit/CSV rerun command results with cached Backend Launch Preflight, submitted Launch intent, and Queue Launch Decision evidence. Failed Start responses also include the same read-only correlation block inline, so the operator can tell whether a failure was predicted by checklist evidence or whether backend/runtime state changed after the cached checks.
- Queue now consumes the cached pipeline target from Launch's backend-authored `GET /api/launch/preflight` payload and adds it to the Launch Decision Checklist, so backend blockers such as schedule gates, process locks, active work, service availability, saved-settings posture, path posture, and runtime-prep boundaries are visible from Queue before the operator switches to Launch. Launch also exposes read-only manual backend-preflight refresh and last-refresh/fetch-failure evidence that Queue echoes in its detail panel.
- Launch now consumes backend-authored `desktop_launch_preflight.v1` from `GET /api/launch/preflight` and renders selectable pipeline/audit/CSV rerun checks for normalized request data, schedule gates, launch-lock availability, active-work state, service availability, path posture, safety modes, and runtime-prep boundaries without journaling commands or mutating runtime state.
- Launch now includes a selectable Saved Settings vs Launch Intent checklist that joins backend launch authority, saved-settings posture, staged unsaved Settings JSON, selected start mode/override, close-readiness, schedule gate, Launch Risk Handoff rows, and recent launch/settings command evidence before backend-owned start buttons.
- Diagnostics now includes a selectable Command Failure Resolution Checklist that turns recent backend command warnings/errors into an ordered read-only path through latest issue, owning page, refresh target, diagnostics tails/opens, visible log correlation, allowlisted evidence coverage, Pending Publish special handling, and mutation boundaries before any retry from the owning page.
- Queue now includes a selectable Launch Decision Checklist that combines backend launch authority, queue payload state, snapshot freshness, blocked/invalid rows, runtime/deferred-check context, completed/excluded proof, selected-row sample evidence, recent launch command history, diagnostics read order, and backend-only start boundaries before the operator opens Launch.
- Pending Publish now includes a selectable Drain Decision Checklist immediately before `Publish Parked Outputs`, combining parked-row state, recovery dry-run results, latest drain command evidence, durable drain summary/event agreement, Completed/output proof, diagnostics read order, backend-only mutation boundaries, and severity-colored final status before a drain decision.
- Completed now includes a selectable Output Acceptance Checklist that combines selected output/sidecar proof, size/route proof, pending-publish proof, recent Completed/Pending command evidence, diagnostics read order, and mutation boundaries before rerun/delete/reprocess decisions.
- Completed now includes a selectable Size Growth Evidence handoff that joins oversized-output rows, unknown size comparisons, route/encoder evidence, pending-publish proof posture, diagnostics order, and settings-policy boundaries without adding repair, rerun, cleanup, drain, delete, manifest-write, or policy mutation authority.
- Home now includes a selectable Progress Evidence board that separates active runtime evidence from output/publish proof by summarizing snapshot state, close-readiness, ActiveJobs, current item, route/queue fields, control flags, recent events, audit progress, and proof boundaries.
- Settings now includes a selectable Save Review board that separates staged patch state, schema drift, critical/high safety blockers, policy review items, backend command evidence, and backend-owned persistence boundaries before Save Patch.
- Launch now includes a read-only Launch Command Review board that groups recent pipeline, audit, and CSV rerun start commands by flow, issue level, refresh handoff, and safe next step while selecting rows into the existing global Command Results and Diagnostics drilldown.
- Diagnostics now includes a Command Owner Impact board that groups warning/error command results by owning page, and Home Command Results now shows owner/issue columns directly before drilldown.
- Queue, Completed, and Pending Publish now include dense selectable review digest rows under their Operator Review Boards, so high-risk rows can be selected directly and handed off to existing detail/diagnostics panels without adding mutation authority.
- Home now includes a read-only Daily-Driver Checklist that rolls refresh timing, close-readiness, saved settings, Queue, Completed, Pending Publish, Diagnostics, recent command issues, schedule/launch posture, and Network visibility into one operator-trust table.
- Diagnostics now includes a read-only Investigation Trail that combines Close Readiness, refresh failures, State Artifact Summary issues, recent command issues, Queue/Completed/Pending review rows, malformed/stale clues, and ordered read-first/open-next backend allowlisted actions into one operator investigation path.
- Settings now includes a read-only Launch Impact Handoff for staged Changes JSON, and Launch preflights warn when the same WebView session has touched unsaved effective settings changes or invalid Changes JSON. This clarifies that Launch uses saved backend settings until backend Save Patch succeeds and refresh/reload completes.
- Queue, Completed, and Pending Publish now include read-only Operator Review Boards that gather the first rows to inspect across backend severity, trust state, runtime history, blocked/invalid queue state, output growth, manifest/sidecar consistency, do-not-drain pending rows, recovery class, and safe next action without adding any WebView mutation authority.
- Queue, Completed, and Pending Publish now carry backend-authored available-open-target evidence in their preview payloads. Selected-row details disclose the exact row-key/target boundary for source, output, sidecar, manifest, payload, destination, and source-folder opens, while the pages show aggregate target counts. The WebView still sends only backend-owned row keys and allowlisted target names; it never resolves arbitrary filesystem paths.
- Settings Audio now exposes the existing backend `AudioTranscodeAutoBitrateByChannels` key, and the audio/subtitle builders show structured routing summaries for languages, SRT/OCR conversion, original-subtitle preservation, passthrough profile, transcode codec/bitrate, downmix, and channel cap decisions before backend preview/save.
- Backend settings risk preview now flags empty audio/subtitle language lists, disabled TX3G/BDPGS SRT generation, empty custom audio codec lists, custom/lossless audio passthrough, forced stereo downmix, and low channel caps so high-impact Plex compatibility choices are visible before save.
- Command Results now has Pending Publish-specific command triage for recovery dry-runs, publish drains, and backend-selected opens, including a summary digest, selected-command risk breakdown, representative row evidence, safe next action, and grouped read-first/open-next Diagnostics actions.
- Pending Publish now has a backend-owned dry-run recovery-plan command exposed through `/api/pending-publish/recovery-plan`; the WebView can plan all rows or the selected row, display planned recovery actions and safety evidence, and show recovery-plan command history without draining, repairing, rewriting, moving, deleting, or publishing files.
- Pending Publish row-key normalization now preserves empty-field separators, so orphan payload rows remain addressable by backend-selected open and recovery-plan commands.
- Queue, Completed, and Pending Publish rows now carry backend-authored trust-state contracts with primary concern, safe next action, unsafe-if-ignored text, proof summary, and recommended Diagnostics targets; WebView daily-use pages prefer those backend fields and show aggregate backend trust-state counts.
- Maintenance health rows now carry backend-authored operator status, required/optional status, dry-run impact, safe next action, unsafe-if-ignored text, and recommended Diagnostics targets; the WebView table is selectable and shows row-level trust detail without adding repair or write actions.
- Maintenance release/backfill dry-run result panels now include an explicit dry-run trust summary so operators can see that WebView actions remain backend-owned dry runs and should not have created packages, zips, manifests, or completed-manifest rewrites.
- Settings now has a dedicated Pending Publish / Recovery Patch Builder that groups deferred publish, remote staging cleanup, transient retry limits, stale cleanup age, robocopy timeout/flags, output reserve, disk estimate, integrity checks, and stability checks into one operator workflow while still staging existing backend-owned config keys.
- Backend settings risk preview now flags pending-publish monitoring requirements, remote staging cleanup, high transient retry limits, and short copy timeouts so unsafe recovery/publish patches are visible before save.
- Queue, Completed, and Pending Publish selected-row details now share an Operator Trust Summary pattern with trust state, primary concern, evidence to compare, read-first/open-next diagnostics order, safe next action, unsafe action, and owning-page boundaries.
- Queue, Completed, and Pending Publish diagnostics action strips now group bounded backend Tail reads before shell Open actions while preserving backend allowlisted target keys.
- Diagnostics log rows, ActiveJobs rows, and State Artifact Summary rows now show an explicit read-first/open-next action plan, so operators inspect bounded backend text before shell-opening folders/files when a failure or stale runtime state is being triaged.
- Diagnostics action grouping remains read-only and still calls only backend allowlisted open/tail commands; no queue, publish, settings, rename, process, or media mutation authority moved into the WebView.
- Queue, Completed, Pending Publish, Reports Failure/Audit, and Command Result details now share Diagnostics handoff text with primary target, suggested order, evidence, safe action, and non-mutating guardrails.
- Reports Failure/Audit and Command Result rows now expose backend allowlisted diagnostics action strips without adding repair, rerun, publish, or filesystem mutation controls.
- Queue, Queue Excluded, Completed, Pending Publish, Rename, Command Results, Reports Failure/Audit, Network Worker, Diagnostics State Artifact, Diagnostics Log, ActiveJobs, and API Contract tables now share selectable-row helpers instead of copied click-only row behavior.
- The high-use WebView tables now expose visible status legends, selected-row visibility, ARIA selected state, Enter/Space selection, and Up/Down adjacent-row navigation.
- The change is presentation-only and does not move mutation authority out of backend-owned open/apply/launch routes.

## Current Snapshot

As of the latest transition checkpoint:

- Desktop Python package contains about 288 Python files.
- `application` contains 59 Python files.
- `api` contains 30 Python files.
- The largest remaining Python hotspots are:
  - `DesktopApp\mediapipeline_desktop_app\views\network_tab.py`
  - `DesktopApp\mediapipeline_desktop_app\network\coordinator.py`
  - `DesktopApp\mediapipeline_desktop_app\network\worker.py`
  - `DesktopApp\mediapipeline_desktop_app\config_schema.py`
  - `DesktopApp\mediapipeline_desktop_app\app.py`
- The web frontend has been split into cohesive screen modules, with `app.js` now acting as a compact shell/refresh coordinator:
  - `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\app.js`
  - `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\apiClient.js`
  - `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\domHelpers.js`
  - `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\formatters.js`
  - `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\commandHistory.js`
  - `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\completedView.js`
  - `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\queueView.js`
  - `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\pendingPublishView.js`
  - `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\renameLabels.js`
  - `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\renameHistoryView.js`
  - `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\renameView.js`
  - `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\settingsOverview.js`
  - `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\settingsCommandHistory.js`
  - `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\settingsMetadata.js`
  - `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\settingsView.js`
  - `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\diagnosticsTailView.js`
  - `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\diagnosticsStateSummaryView.js`
  - `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\diagnosticsView.js`
  - `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\reportsView.js`
  - `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\scheduleView.js`
  - `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\maintenanceView.js`
  - `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\telemetryView.js`
  - `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\progressView.js`
  - `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\launchReadinessView.js`
  - `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\launchHistoryView.js`
  - `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\launchView.js`
- The latest frontend consolidation moved Settings page state, structured builders, patch summary, and backend-mediated settings actions into `settingsView.js`; the shell script is now about 238 lines.
- The Settings page read-only grouped operational overview has been extracted into `settingsOverview.js`, leaving `settingsView.js` focused on settings rows, patch builders, and backend settings commands.
- The Settings command-history renderer has been extracted into `settingsCommandHistory.js`, preserving existing validate/reload/preview/save command visibility while keeping settings patch/save behavior in backend-owned command paths.
- Settings builder metadata, impact groups, impact hints, and choice labels now live in `settingsMetadata.js`, leaving `settingsView.js` responsible for stateful rendering and backend command submission rather than large static tables.
- The WebView shell now has a dedicated read-only Network page that renders backend-owned network role/coordinator/worker settings, local API contract summary, and existing diagnostics open actions without adding new mutation routes.
- WebView diagnostics and the Network page can now open the backend-allowlisted `cluster.log` through the existing diagnostics-open command contract.
- A practical Tk-versus-WebView daily-use parity matrix now exists in `Docs\architecture\TAURI_WEBVIEW_PARITY_MATRIX.md`, and the WebView inventory/report pages now provide actionable empty-state and row-detail guidance for queue, completed history, pending publish, failures, and audit rows.
- WebView launch and pending-publish drain panels now render backend command messages, warnings, errors, result data, and submitted requests inline instead of relying on raw JSON dumps or command history alone.
- Launch readiness and pipeline/audit/rerun start-command history rendering now live in `launchReadinessView.js` and `launchHistoryView.js`; backend launch, audit, rerun, pending-drain, and control commands remain in `launchView.js`.
- Launch readiness now also consumes the saved settings workspace so invalid/critical saved settings surface as a settings issue and lower-risk saved settings surface as review before start actions.
- Backend rename previews now include preview-source and confidence metadata, and the WebView Rename page renders confidence/status summaries plus selected-row explanations without moving rename mutation logic into the frontend.
- Rename status/confidence labeling and `rename.apply` command-history rendering now live in `renameLabels.js` and `renameHistoryView.js`; backend preview/apply requests, selected-source scoping, overrides, and path ordering remain in `renameView.js`.
- Backend rename previews now also include change-kind, source/destination parent, destination-existence, and sidecar-count metadata, allowing the WebView to audit what a checked/selected batch will do before apply.
- Backend rename apply results now include selected, renamed, unchanged, media-operation, sidecar-operation, and sidecar-move counts, and the WebView Rename page renders a Last Apply Result panel with undo manifest and row outcomes.
- Backend rename previews now include aggregate confidence/source/change-kind counts, and the WebView Rename page renders a preview-wide Review Board so TV/movie batches can be evaluated before applying selected-source filesystem changes.
- The WebView Rename page now includes scoped bulk final-name override tools for checked, selected, and all-applicable preview rows, with backend-preview rebuilds before any apply.
- Backend rename previews now expose an active template and template catalog, and the WebView Rename page can request backend-owned TV standard, TV no-episode-title, and movie standard templates.
- The WebView Home page now includes an operator-readiness strip summarizing backend snapshot availability, refresh failures, close-readiness, pipeline state, and a concrete next step.
- The WebView Home page now includes an active-work summary that surfaces existing snapshot progress, current route/queue position, Diagnostics ActiveJobs summaries, recent event hints, and close-readiness guidance without adding new process controls.
- The WebView Home page now includes command-result summary/detail rendering for the existing command journal/local-result stream, making backend warnings, errors, result data, and submitted requests inspectable without opening raw logs first.
- The WebView command-result stream now classifies owner page, issue level, refresh target, suggested next action, and diagnostics handoff for warnings/errors while keeping retry, drain, rename, save, launch, and open actions page-specific and backend-owned.
- The WebView Home page now includes pipeline-control readiness guidance that explains when Pause/Resume, Rescan, and Stop After Current are meaningful while keeping control-flag writes backend-owned.
- The WebView Home page now includes recent pipeline-control command history from the existing command-history stream so pause, rescan, and stop-after-current outcomes remain visible near the controls after refresh.
- The WebView Home page now includes runtime-artifact quick opens for Active Jobs, Run Logs, Last Stderr, Queue Snapshot, Pending Publish, and Completed Manifest through the existing backend diagnostics allowlist.
- The WebView Live page now makes NVENC present-but-idle telemetry explicit and keeps a visible 0% baseline/dot so an idle encoder does not look like a missing graph.
- The WebView Live page now includes a telemetry-readiness summary that explains sample freshness, stale sampler data, CPU/RAM-only mode, missing GPU rows, and NVENC idle state from the existing `/api/telemetry` payload.
- The WebView Diagnostics page now includes a triage summary that groups errors, warnings, active-work hints, and malformed/stale runtime-state clues with concrete next steps.
- The existing Diagnostics payload now includes additive structured ActiveJobs rows, and the WebView Diagnostics page renders a selectable ActiveJobs detail table for launch id, status, pid, logs, cwd, return code, and contract issues.
- The WebView Diagnostics page now renders a structured runtime-progress table from the existing `/api/snapshot` payload, showing pipeline and audit progress fields beside Close Readiness and ActiveJobs without opening raw state files first.
- The WebView Diagnostics page now renders a structured log triage table from the existing `/api/diagnostics` payload, grouping recent errors, events, warnings, ActiveJobs summaries, pipeline log tail, and launch logs by source, severity, timestamp, and selectable full-line detail.
- The WebView Diagnostics command-history text now includes owner page and issue level for each command result, so backend warnings/errors can be traced back to the owning page before opening raw logs.
- The WebView Diagnostics log triage table now supports local search and severity filtering, keeping noisy long-running diagnostics payloads usable without adding backend log reads or arbitrary path access.
- The WebView Diagnostics page now includes a read-only artifact drilldown summary and suggested open buttons that map existing diagnostics text to backend-allowlisted open targets for ActiveJobs, state/progress, run logs, launch logs, queue snapshots, pending publish, failure reports, and cluster logs.
- The local API now exposes read-only `/api/diagnostics/tail`, and the WebView Diagnostics page can read a bounded text tail from known diagnostics targets without accepting frontend filesystem paths.
- The WebView Diagnostics artifact drilldown now offers read-tail buttons for matched file-backed diagnostics artifacts such as Last Stderr, Queue Snapshot, Latest Failure Report, and Cluster Log, while folder-backed artifacts remain open-only.
- The WebView Diagnostics allowlisted tail reader now lives in `diagnosticsTailView.js`, preserving backend-owned target-key reads while keeping `diagnosticsView.js` focused on triage, ActiveJobs, logs, artifact matching, and diagnostics-open history.
- The local API now exposes read-only `/api/diagnostics/state-summary`, and the WebView Diagnostics page can summarize backend-selected runtime artifacts, small JSON/JSONL state, text/log warning hints, and recent directory entries without accepting frontend filesystem paths.
- Diagnostics state-summary rows now include backend-authored operator status, guidance, recovery stage, unsafe-if-ignored explanation, and recommended allowlisted open/tail targets, and the WebView Diagnostics page renders a State Artifact Recovery checklist that keeps Close Readiness authoritative while explaining which artifacts are ready, review-worthy, blocked, unavailable, or unknown.
- The WebView Diagnostics state-artifact summary renderer now lives in `diagnosticsStateSummaryView.js`, preserving backend-owned target selection and bounded parsing while keeping `diagnosticsView.js` focused on triage, ActiveJobs, logs, artifact matching, and diagnostics-open history.
- The WebView Diagnostics log triage detail now explains likely owning artifacts, selected-row next steps, deduplicated backend-allowlisted Open/Read actions, conservative fallback actions for unmatched error/warning/active rows, and state-artifact operational meaning so warning/error recovery is easier without adding arbitrary path access or repair controls.
- The WebView Queue, Completed, and Pending Publish pages now include read-only Workflow Next Step panels that tie page validation, selected-row review, diagnostics artifacts, and cross-page ownership together before launch, rerun, repair, or drain decisions.
- The Home cross-page context panel now includes an operator investigation order so Diagnostics, Pending Publish, Completed, Queue, and Launch are presented in a safer sequence when loaded payloads show conflicts.
- Queue workflow guidance now points stale/blocked/empty states to Queue Snapshot, Active Jobs, Last Stderr, Completed exclusions, Pending Publish, or Launch without adding queue mutation controls.
- Completed workflow guidance now points missing outputs, size growth, sidecar issues, stale manifests, and warnings to Completed diagnostics, Pending Publish, Last Stderr, Queue, or normal new-work review without adding repair/reconcile controls.
- Pending Publish workflow guidance now points do-not-drain rows, invalid manifests, missing payloads, sidecar issues, warnings, empty pending roots, and drain-ready states to Pending diagnostics, Completed, Queue, or backend-owned Publish Parked Outputs without changing drain semantics.
- Queue, Completed, and Pending Publish selected-row details now include issue digests that separate primary issues, proof fields, and safe next actions before launch, rerun, cleanup, or drain decisions while preserving backend ownership of all mutation.
- Queue, Completed, and Pending Publish selected-row diagnostics now include a shared `Review in Diagnostics` bridge. It switches to Diagnostics and selects a high-priority allowlisted target without opening Explorer, reading file tails, mutating queue state, draining pending publish, or touching media files.
- The WebView Diagnostics API Contract panel now renders a filterable route table with method, auth, effect, response schema, request/query keys, allowed targets, and backend-owned mutation guardrail detail instead of a raw route text dump.
- The WebView Diagnostics page now includes recent diagnostics-open command history from the existing command-history stream so allowlisted artifact-open results remain visible after refresh.
- The WebView Network page now includes a read-only readiness summary that combines existing settings, local API contract, snapshot, and close-readiness payloads, and explicitly states that coordinator/worker lifecycle plus live worker-board data remain Tk-owned during the transition.
- The WebView Network page now includes recent network diagnostics-open command history so run-log, cluster-log, ActiveJobs, config, and state-folder open results remain visible on the owning page after refresh.
- The local API now exposes read-only `/api/network/workers`, and the WebView Network page renders persisted coordinator in-flight rows, idle worker stats, worker crash/done state, and state-file paths without adding coordinator/worker start-stop authority.
- The WebView Network page now renders selectable persisted worker-row details for current file, progress, heartbeat, speed, job, and extra row fields while keeping coordinator/worker lifecycle controls out of the WebView.
- The WebView Network page now includes local status/search filters for persisted worker rows, so active, idle, stale/offline/failed, and unknown worker rows can be narrowed without opening raw state files.
- The WebView Completed page now surfaces completed-manifest route reasons plus bounded audio/subtitle decision previews, matching the operator detail available in the Tk shell without adding repair mutations.
- The WebView Completed page now surfaces output-integrity guidance for no-history, unavailable, warning, review-needed, and healthy completed-history states using the existing `/api/completed` payload.
- The WebView Completed page now surfaces backend-owned route, publish-state, health, media-type, audio/subtitle decision-total, unknown-size, and output-growth counts, including rows over +5% output growth, without changing remux/encode routing policy.
- The WebView Completed page now surfaces recent completed-row open command history from the existing command-history stream so output, sidecar, and source-folder open results remain visible after refresh.
- The WebView Completed page now surfaces backend-owned completed-manifest file age/status and aged-history guidance so old history is visible without implying repair/reconcile authority in the frontend.
- The WebView Completed page now surfaces backend-authored per-row operator status, severity, guidance, and review flags, plus aggregate operator status/severity counts, so missing-output and oversized-output rows are easier to triage without adding repair/reconcile controls.
- The WebView Completed page now surfaces backend-authored route-decision summary and evidence lines for route, reason, encoder/GPU, size delta, publish state, output health, and bounded audio/subtitle decision context.
- The WebView Completed page now surfaces backend-owned manifest consistency status, issue counts, size buckets, missing sidecar/output mismatch/stale sidecar checks, and per-row consistency guidance without adding repair/reconcile mutation controls.
- The WebView Queue page now surfaces queue-snapshot provenance, source roots, source candidate counts, runnable count, priority count, and completed/blocked exclusions from the existing backend queue snapshot.
- The WebView Queue page now surfaces read-only queue-readiness guidance for unavailable, no-candidate, empty, warning, priority-ready, and ready queue previews without adding queue mutation controls.
- The WebView Queue page now surfaces backend-owned route, route-reason, phase, media-type, source-root, TV-season, priority-reason, invalid-row, and visible-size breakdowns, making queue snapshot risk easier to review before Launch while preserving read-only WebView ownership.
- The WebView Queue page now supports backend-selected selected-row opens for source file, source folder, and source root through `/api/queue/open`, with command history beside the queue detail while preserving read-only queue ownership.
- The WebView Queue page now surfaces backend-owned queue snapshot file age/status and produced-time age/status, with stale-snapshot refresh guidance before Launch.
- The WebView Queue page now surfaces backend-authored per-row operator status, severity, guidance, and review flags, plus aggregate operator status/severity counts, so blocked, priority, missing-route, and ready rows are distinguishable before Launch.
- The WebView Queue page now surfaces backend-authored route-decision summary and evidence lines for route, reason, block state, media/phase, priority, TV parse, source size, queue position, and source last-write context.
- The WebView Queue page now surfaces backend-owned completed-collision aggregate guidance for source candidate versus runnable-row gaps, including explicit disclosure that row-level excluded-file detail is not yet persisted in the queue snapshot contract.
- The WebView Pending Publish page now surfaces a drain-readiness summary that distinguishes empty, unavailable, review-before-drain, warning, and ready-to-drain states from the existing `/api/pending-publish` payload before the operator presses Publish Parked Outputs.
- The WebView Pending Publish page now surfaces backend-owned risk counts for ready rows, issue rows, orphan payloads, invalid/unreadable manifests, missing sidecars, route/state distribution, and per-row issue summaries before drain.
- The WebView Pending Publish page now surfaces backend-owned recovery classes, recovery actions, and evidence fields so row recovery does not depend on frontend inference from raw diagnostic status strings.
- The WebView Pending Publish page now surfaces recent backend-authored `publish_drained` pipeline events from the existing snapshot payload, including status, route, sidecar count, and output leaf summaries after Publish Parked Outputs.
- The PowerShell pending-publish drain path now writes a durable `pending_drain_summary.json` artifact under state `Progress`, and the WebView Pending Publish page surfaces it as a Last Drain Summary with manifest-attempt counts, statuses, skipped/deferred/stopped state, route counts, and remaining manifest count.
- The WebView Pending Publish page now surfaces recent pending-drain command history from the existing command-history stream, preserving local drain results that the persisted backend journal records under the generic pipeline-start command.
- The WebView Pending Publish page now surfaces recent pending-row open command history from the existing command-history stream so manifest, local payload, destination, and source-folder open results remain visible after refresh.
- The WebView Queue, Completed, and Pending Publish pages now include read-only validation checklists that aggregate already-loaded backend freshness, runtime, output/sidecar, size-growth, and drain-risk signals into explicit operator next steps while preserving backend ownership of launch, rerun, repair, reconcile, drain, and publish actions.
- The WebView Queue, Completed, and Pending Publish selected-row detail panes now begin with read-only review checklists that classify the selected row, identify blockers or review reasons, and state safe next actions before showing raw row fields.
- The WebView Queue and Completed selected-row detail panes now include Diagnostics Cross-Links that call existing backend-allowlisted diagnostics open/tail targets for queue snapshots, completed manifests, run logs, stderr, latest failure reports, Active Jobs, and Pending Publish context; Pending Publish selected-row guidance now states the diagnostic order for common row states.
- The WebView Maintenance page now surfaces recent release and completed-manifest backfill dry-run command history from the same command-history stream, preserving backend dry-run results after refresh.
- The WebView Maintenance page now surfaces read-only readiness guidance that separates required missing health checks from optional warnings before release-package and completed-manifest backfill dry runs.
- The WebView Settings page now surfaces a local patch-impact summary that groups staged config changes by file safety, routing/size, encoder/GPU, subtitles, audio, and publish/network/runtime impact before the backend-owned preview/save commands run.
- The WebView Settings page now surfaces a local Save Readiness checklist that classifies staged patches and flags unknown keys, source deletion, disabled stability/integrity checks, no-audio output, raw FFmpeg flags, partial-download extensions, subtitle drop/convert conflicts, empty language lists, custom audio codec gaps, forced stereo, MP4 container review, NetworkRole changes, and deferred-publish monitoring before backend preview/save.
- The WebView Settings page now surfaces recent validate, reload, preview, and save command history from the existing command-history stream so settings outcomes remain visible after refresh.
- The WebView Home, Launch, and Settings pages now surface a read-only Saved Settings Trust summary that groups active saved risk, validation state, source/output/scratch safety, deferred publish, remux/encode routing, encoder flags, subtitle routing, audio routing, and operator next action from `/api/settings/workspace`.
- The WebView Settings page now includes a video-detail patch builder for NVENC preset/quality, H.264 remux limits, remux-safe codecs, CPU fallback CRF/preset/priority/thread caps, and legacy extra flags without moving FFmpeg command ownership into the frontend.
- The WebView Settings page now includes a file-safety/publish patch builder for source/output/scratch paths, free-space reserves, deferred publish, stability checks, and cleanup keys, with guidance that the pipeline should copy sources to scratch and backend preview/save remains authoritative.
- The WebView Settings file-safety/publish builder now also stages existing discovery/transfer/recovery keys for valid media extensions, robocopy flags, integrity checks, TV folder layout, and pre-encode disk estimate multiplier, while keeping source deletion unexposed and settings save backend-owned.
- The WebView Settings runtime builder now stages log retention days, and backend risk preview now flags disabled stability/integrity checks, partial-download extensions, high robocopy thread counts, and low disk-estimate multipliers.
- The WebView Settings page now includes a non-secret Network patch builder for role, coordinator, worker, path-map, and per-worker override settings, while excluding auth tokens and runtime lifecycle controls from WebView ownership.
- The WebView Settings page now includes a queue/reprocess patch builder for priority markers, processed-index refresh, minimum pipeline version, and `ReprocessAll`, while keeping queue mutation and processing starts backend-owned.
- The WebView Settings page now includes a runtime/diagnostics patch builder for logging, subprocess timeout ceilings, scan cadence, transient retry limits, and PATH tool-fallback settings without adding WebView process lifecycle ownership.
- The WebView Settings subtitle and audio builders now call out original-track preservation, preferred-language SRT routing, TX3G/BDPGS/ASS drop consequences, no-audio risk, empty codec/language lists, forced stereo, and lossless passthrough compatibility before staging a patch.
- The WebView Home page now includes a Daily-Driver Checklist that summarizes refresh payload health, close-readiness, saved settings, Queue, Completed, Pending Publish, Diagnostics, recent command issues, schedule/launch posture, and Network visibility with refresh duration evidence.
- The WebView Home Command Results table now shows owner page and issue level for each command, and Diagnostics now groups command warnings/errors by owning page in a Command Owner Impact board that selects the latest related command for existing drilldown/evidence views.
- The WebView Queue, Completed, and Pending Publish pages now include dense selectable review digest tables that surface the highest-risk rows below each Operator Review Board and reuse the existing selected-row detail/diagnostics handoff paths.
- The WebView Launch page now includes page-level launch readiness that combines snapshot state, close-readiness, schedule state, refresh issues, and active-work guidance before backend-owned launch commands are submitted.
- The WebView Launch page now surfaces local preflight summaries for pipeline, audit, and CSV rerun forms, including schedule override, visible-console/config flags, audit-root presence, CSV path presence, and the copy/keep/park rerun safety policy before backend command submission.
- The WebView Launch page now classifies saved settings as ready, review, or blocked in pipeline/CSV rerun preflights, with continuous-mode guidance when saved settings are not clean, while preserving backend launch validation as authoritative.
- The WebView Launch page now surfaces recent pipeline, audit, and CSV rerun start history from the existing command-history stream so start outcomes remain visible after refresh.
- The WebView Reports page now surfaces combined report triage for latest report-path presence, snapshot warnings, failure classifications, audit buckets, and read-only next-step guidance without adding rerun/export mutation controls.
- The WebView Reports page now surfaces recent report-related diagnostics-open command history so latest report and report-root open outcomes remain visible on the owning page after refresh.
- The WebView Schedule page now surfaces launch guidance that explains allowed/outside-window state, WebView continuous-mode schedule-stop limitations, schedule overrides, and unscheduled validate/publish modes using the existing `/api/schedule` payload, and it now has backend-owned schedule preview/save routes for schedule grid edits only.
- The WebView Rename page now surfaces batch-safety guidance that explains checked-row apply scope, TV path-order dependence, sidecar/force settings, override counts, and blocked/warning row counts while keeping rename filesystem mutation backend-owned.
- The WebView Rename page now surfaces a Selection Audit panel that summarizes the exact checked/selected scope, statuses, rename/case-only/unchanged actions, sidecar moves, force-through-pipeline rows, duplicate destinations, warnings, and errors before apply.
- The WebView Rename page now surfaces a Last Apply Result panel populated by backend command data and command history, including selected/applied/renamed/unchanged counts, operation counts, undo manifest, and row outcomes.
- The WebView Rename page now surfaces recent rename-apply command history from the existing command-history stream so selected-row filesystem mutation results remain visible after refresh.
- The WebView Rename page now supports checked-row batch apply through the existing backend `selected_sources` contract, while preserving backend plan rebuild, confirmation, lock, and transactional apply ownership.
- The WebView Rename page now supports local path-order controls for moving checked paths and natural-sorting the Paths textarea before rerunning backend preview, which keeps TV episode numbering order explicit without touching files.
- The WebView Rename page now surfaces a preview-wide Review Board built from backend aggregate confidence, preview-source, and change-kind counts, with duplicate-target, sidecar, override, force-pipeline, and TV/movie review guidance before apply.
- The WebView Rename page now surfaces scoped bulk final-name override tools that stage find/replace, prefix, suffix, use-pipeline-name, force-on, force-off, and clear-override changes for checked, selected, or all-applicable rows before rebuilding backend preview.
- The WebView Rename page now surfaces backend-owned template selection; TV no-episode-title suppresses the backend's confident episode title output while preserving existing default behavior.
- The WebView shell refresh loop now coalesces overlapping interval/manual refresh requests so slow backend reads cannot stack multiple concurrent render batches.
- The latest backend-boundary confidence chunk added tests for unresolved close-readiness, unauthenticated process-command blocking, route effect/auth invariants, and Tauri close-readiness token/schema handling.
- The local API JSON body reader now rejects negative `Content-Length` values before reading, and static asset resolution verifies the resolved path remains under the asset root.
- The latest API cleanup consolidated route contracts into `contract_read.py` and `contract_command.py`, removing the tiny route-contract leaf modules while preserving public route constants and schemas.
- The latest network cleanup extracted Windows Firewall/netsh subprocess handling from the Network tab into a tested `network\firewall.py` helper.
- Worker crash-state file persistence has been extracted into `network\worker_state.py` while preserving `WorkerDispatcher` crash-recovery policy.
- Worker crash-recovery cleanup now routes corrupt/missing-job-id/successful-report state removal through the guarded cleanup helper, so unlink failures do not crash worker startup.
- Worker coordinator HTTP GET/POST helpers have been extracted into `network\http_json.py` with bounded response reads, token header preservation, query encoding, and explicit timeout tests.
- Coordinator query parsing and Content-Length validation have been extracted into `network\coordinator_http.py` while keeping job-claiming/done/heartbeat policy in `coordinator.py`.
- Network-tab coordinator health/auth probes have been extracted into `network\probe.py`, leaving the Tk view with background-thread scheduling and rendering.
- Coordinator cluster-log line formatting has been extracted into `network\cluster_log.py`, leaving append/rotation and event emission in `CoordinatorDispatcher`.
- Coordinator cluster-log append now guards path resolution, line formatting, and unexpected `/api/log` append failures so best-effort diagnostics cannot unwind coordinator control flow.
- Network-tab coordinator share-block formatting has been extracted into `network\share_block.py`, leaving textbox and clipboard UI behavior in the view.
- Network-tab and mDNS LAN IPv4 selection now share `network\local_ip.py`, keeping the operator share address and advertised coordinator address on the same policy.
- Worker source path map parsing/rewrite policy has been extracted into `network\path_map.py`, while preserving `WorkerDispatcher` compatibility wrappers and hot-swap behavior.
- Worker coordinator URL validation has been extracted into `network\coordinator_url.py`, while preserving the historical `worker._validate_coordinator_url` alias.
- Worker poll wait clamping has been extracted into `network\poll_policy.py`, while preserving `WorkerDispatcher._resolve_wait_seconds()`.
- Coordinator config/retry policies have been extracted into `network\coordinator_policy.py`, while preserving coordinator methods and retry constants. Invalid coordinator port and heartbeat settings now fall back to documented defaults instead of crashing startup or disabling stale-job recovery.
- Coordinator encode-config snapshot and `WorkerConfigOverrides` application policy has been extracted into `network\encode_config_snapshot.py`, while preserving the dispatcher wrapper.
- Coordinator prior-failure matching has been extracted into `network\failure_policy.py`, while preserving the dispatcher wrapper and case-insensitive exact-source behavior.
- Coordinator worker identity validation, display-name cleanup, and cluster-log field clipping have been extracted into `network\identity.py`, while preserving compatibility constants and HTTP response behavior.
- Worker claim-response to synthetic queue-record construction has been extracted into `network\worker_record.py`, while preserving `worker._make_queue_record` compatibility.
- Worker `/api/done` payload construction has been extracted into `network\worker_done.py`, while preserving crash-recovery, clean-release, completion, and terminal-failure retry semantics.
- Worker dispatcher-level completion/release tests now verify terminal failure and clean release payloads after state cleanup.
- Worker claim-record construction failures now emit a coordinator cluster-log event so the cross-machine operator view shows why a claimed job did not start locally.
- Coordinator queue-removal scheduling failures after terminal done reports and worker heartbeat progress snapshot failures now log diagnostic context; terminal done-report queue removal is logged as scheduled only after Tk accepts the callback, heartbeat snapshot read failures warn with job context before sending safe 0% progress, and accepted worker done/release reports no longer create pending retry state if local cleanup fails afterward.
- Network worker/coordinator silent exception paths now log status-callback failures, reclaimed-job abort scheduling failures, inflight-state save failures, queue-removal scheduling failures, and unreadable HTTP error bodies.
- Worker shutdown and auth-error poll-loop cluster-log events now use the same safe best-effort wrapper as other lifecycle-sensitive worker diagnostics.
- Network token regeneration now logs app-state persistence/live hot-swap failures, coordinator queue refresh failures log their exception context, and operator status text no longer implies failed actions are safely saved/applied.
- Network tab asynchronous UI handoffs now route through a shared recovery helper, so coordinator URL tests, discovery, status/auth probes, queue refresh recovery, worker-board polling, and firewall actions use one bounded logging and fallback path.
- mDNS discovery now logs advertiser startup/cleanup failures, async discovery thread-start failures, and async callback exceptions, with tests that do not require the optional Zeroconf package.
- ActiveJobs reconciliation now logs and returns explicit diagnostics for malformed runtime records instead of silently skipping them.
- ActiveJobs update/repair now logs when a corrupt record is repaired during process completion.
- ActiveJobs close-readiness and reconciliation now distinguish stale PID reuse from true active work when process identity can be inspected, while still failing closed when identity cannot be verified.
- Close-readiness now fails closed if related MediaPipeline process inspection, fresh pipeline progress, or fresh audit progress cannot be verified.
- Close-readiness verification exceptions now log through the service logger for related-process, ActiveJobs, pipeline-progress, and audit-progress checks.
- Pending-publish preview now flags duplicate manifest references to the same parked payload or server destination before a drain is attempted.
- Pending-publish Open commands now report scan failures as scan failures instead of misclassifying them as missing selected rows.
- Pause/stop/rescan control flag reads now log unreadable flag files instead of silently falling back to filesystem mtime.
- The web Diagnostics page now exposes additional existing backend-allowlisted open-location actions for config file, ActiveJobs, queue snapshot, completed manifest, last stdout/stderr logs, and failure markers.
- The web Diagnostics page now also exposes the backend-allowlisted Workspace open action, and static tests verify frontend controls cover local API command allowlists for diagnostics, completed rows, pending rows, pipeline controls, launch modes, and schedule overrides.
- Web Rename selected-row override/apply controls and Pending Publish row details are now rendered in their owning pages instead of wrong page sections, with static-page placement coverage and a page-scoped ID ownership gate.
- A Web/Tauri route-coverage test now verifies every local API read/command contract path is referenced by the static web assets or the Tauri shell lifecycle code.
- The web Reports page now exposes backend-allowlisted Open actions for latest failure/audit report files and report-root folders through `/api/diagnostics/open`; the frontend sends target keys only, never arbitrary paths.
- The web Pending Publish page now exposes backend-row-keyed Open actions for parked payloads, manifests, destination folders, and source folders through `/api/pending-publish/open`; the backend rescans and chooses the path from the matching pending row.
- Tauri Rust shell compile verification passed with `%USERPROFILE%\.cargo\bin\cargo.exe check` from `DesktopApp\tauri_shell\src-tauri`.
- The Tauri shell now validates `/api/contract` before opening the WebView, requiring current method/path/auth route triples so stale backends fail startup instead of opening a broken shell; a drift test compares the Rust route list to the Python local API contract.
- Backend health capabilities now include the command surfaces used by the WebView, including diagnostics open, completed/pending open, rename apply, settings save/reload, and backend shutdown.
- The Tauri build checker now syntax-checks all static WebView JavaScript assets with `node --check` before running the Rust compile check.
- Tauri prerequisite and build checker scripts passed with bundled PowerShell from `Pipeline\PowerShell-7.6.0-win-x64\pwsh.exe`.
- Tauri launch/close smoke passed after the startup contract and JavaScript syntax gates: the WebView window opened, the Python local API backend was detected, window close completed, and backend cleanup was verified.
- Release self-test child-script execution is now bounded. Nested PowerShell checks drain stdout/stderr asynchronously, enforce explicit timeouts, and terminate child process trees on timeout.
- Setup `-ValidateOnly` source/output/scratch path probes are now bounded. Slow or disconnected UNC roots are reported as validation failures instead of hanging the setup validator.
- Full release self-test with tool integration and end-to-end smoke skipped now completes without hanging. It currently fails for the real environment reason: `SourceMovies`, `SourceTV`, and `Outsource` under `\\LAYNE-SERVER` timed out during bounded availability probes.
- The root release self-test now passes without `-SkipToolIntegration` or `-SkipEndToEndSmoke`; bundled FFmpeg/ffprobe/subtitle integration and temp-workspace deferred-publish smoke are wired into the release gate.
- The full desktop unit suite recently passed:
  - 989 tests passing after the current WebView, Local API, lifecycle, network hotspot stabilization, structured encoding/audio gate, and read-only Network page parity coverage.
- Current release/self-test gates are structurally healthy, but the local environment gate is red until the configured UNC media roots respond within the validation timeout.
- Import analysis previously found three circular dependency groups:
  - Tk shell / app bootstrap / network UI cycle.
  - Rename controller / rename table controller cycle. Addressed by replacing owner type imports with a local protocol.
  - Settings controller / settings form controller cycle. Addressed by replacing owner type imports with a local protocol.

## Target Architecture

The intended end state remains:

```text
Tauri/WebView2 desktop shell
  -> bundled web frontend
    -> local Python API on 127.0.0.1
      -> UI-neutral application facade
        -> cohesive backend services
          -> PowerShell pipeline orchestration
            -> FFmpeg / ffprobe / MKVToolNix / PgsToSrt
```

The important boundary is not the number of files. The important boundary is ownership:

- Tauri owns native window lifecycle, backend startup, backend shutdown, and desktop packaging.
- Web frontend owns rendering, form input, view state, table filtering, and operator interactions.
- Python API owns route auth, schema responses, command result payloads, and frontend/backend transport.
- Application facade owns UI-neutral commands and query DTOs.
- Python services own local state, path resolution, process launch, diagnostics, rename planning, settings persistence, queue snapshots, pending publish views, and operator safety guards.
- PowerShell owns the actual long-running media pipeline, FFmpeg command construction, subtitle/audio routing, queue execution, scratch processing, publish/drain behavior, audit/remediation, and completed sidecars/manifests.

## Non-Negotiable Invariants

These must stay true through the transition:

- Never mutate source media as part of normal processing.
- Always copy to scratch before processing pipeline jobs.
- Source deletion must remain explicit, opt-in, and safely guarded.
- Frontends must not construct raw FFmpeg, PowerShell, or file-mutation commands.
- Media-affecting commands must require local API token auth.
- Tauri must not replace Tk as the supported shell until daily workflows reach feature parity.
- Any behavior change to subtitle, audio, remux, encode, publish, or queue semantics must be intentional and separately documented.
- Telemetry must distinguish unavailable data from real zero values.
- Rename apply must stay backend-owned and transaction-aware.
- Pending publish must remain recoverable after interruption.
- Process launch must avoid subprocess pipe deadlocks and must record enough runtime state for recovery.

## What Is Working Well

### Backend Boundary

The backend-boundary work is real, not cosmetic. The current split lets the Tk shell and local API use the same service/facade layer for many operations. This directly supports the Tauri transition.

Preserve this direction.

### Process Runner Direction

The captured subprocess runner now uses `communicate()` with explicit timeouts and kill handling. That eliminates a major deadlock class for short subprocess calls.

Preserve this pattern and expand tests around failure paths.

### Command Result Pattern

The local API command-result payload and bounded command journal are useful. They give the future web UI a consistent way to show operator feedback without needing to scrape logs.

Preserve this pattern, but do not over-split every command into tiny files.

### Tauri Shell Conservatism

The Tauri shell currently starts the Python backend, reads a bootstrap payload, validates health, drains backend stdout/stderr, passes a token, checks close readiness, and shuts the backend down on window close.

This is the right level of conservatism for a prototype shell.

### V4 Preservation

Keeping V4 as a working fallback is the most important project-risk reducer. Do not blur V4 and V5 responsibilities.

## What Is Starting To Drift

### Micro-Module Proliferation

Some extracted modules are now very thin pass-through wrappers. This is useful only when the wrapper forms a stable ownership boundary. It is harmful when it creates navigation overhead without reducing coupling.

Examples of areas to stop splitting further for now:

- `service_paths.py` compatibility layer and related path helpers.
- `service_processes.py` compatibility layer and process helper wrappers.
- `service_status.py` compatibility layer and readers.
- `service_rename.py` compatibility layer and rename helpers.
- Tiny `facade_*_policy.py` files that only shape one row or forward one call.
- Tiny `api\contract_*` and `api\command_payloads_*` files that require opening several files to understand one route.

### Facade Inheritance Stack

`MediaPipelineApplicationFacade` is now a large mixin composition. That is better than a 2,000-line facade class, but it risks becoming hard to trace.

Do not add mixins by reflex. New facade pieces should map to real user-visible domains:

- process control
- queue
- rename
- settings
- diagnostics
- pending publish
- maintenance
- audit
- completed outputs

Avoid one-method facade mixins unless they are temporary compatibility adapters.

### Web Frontend God Script

The web frontend is at risk of becoming the new monolith. `app.js` already owns many views and behaviors.

Before adding substantial new web UI, split by frontend ownership:

- `apiClient.js`
- `state.js`
- `commands.js`
- `views/queueView.js`
- `views/renameView.js`
- `views/settingsView.js`
- `views/diagnosticsView.js`
- `views/pendingPublishView.js`
- `views/homeView.js`
- `formatters.js`

This split should remain frontend-only. It must not move backend policy into JavaScript.

### Test Shape

The test suite is broad, but some tests and reliability checks assert implementation structure. That helps during extraction, but it can freeze accidental architecture.

Shift new tests toward observable contracts:

- API request/response behavior.
- process lifecycle outcomes.
- file state after failure.
- command result payloads.
- recovery behavior after malformed or stale runtime files.

## Areas That Should Stop Being Refactored Right Now

Do not continue extracting these unless fixing a specific bug:

- path helper micro-splits
- process service micro-splits
- status reader micro-splits
- rename helper micro-splits
- config schema micro-splits
- PowerShell subtitle/audio/routing logic
- pending publish semantics
- working Tk controller methods that are stable and covered

Reason:

These areas have already received enough decomposition to reduce immediate risk. More splitting now would mostly increase cognitive overhead. The next gains should come from tests, cycle cleanup, and frontend/backend parity.

## Areas That Still Need Cleanup

### Network Mode

Network mode remains the largest unresolved structure problem. It has large files, import cycles, and mixed UI/coordinator/worker responsibilities.

Risk:

- hard to debug
- hard to test
- likely to regress during Tauri transition
- unclear ownership between view, coordinator, registry, worker, persistence, and protocol

Recommended direction:

- Keep standalone mode as supported default.
- Treat network mode as experimental until refactored.
- Split only around real ownership:
  - protocol contracts
  - registry persistence
  - coordinator runtime
  - worker runtime
  - network diagnostics/presentation
  - Tk network view

### Web Frontend Modularization

The web UI needs a frontend-module split before it receives much more feature work.

Risk:

- Tauri migration recreates the Tk monolith in JavaScript.
- view state becomes hard to reason about.
- frontend bugs become difficult to isolate.

Recommended direction:

- Split `app.js` by screen and utility responsibility.
- Keep one shared `apiClient`.
- Keep one shared app state object.
- Keep DTO interpretation thin and render-focused.

### API Contract Consolidation

The API route-contract leaf files have been consolidated. The boundary is correct, and the route contract is now easier to audit from `contract_read.py`, `contract_command.py`, and `contract.py`.

Current direction:

- Keep route contract definitions grouped into:
  - `api\contract_read.py`
  - `api\contract_command.py`
  - `api\contract.py`
- Do not split route contracts back into one-file-per-domain leaves.
- Defer command/read payload consolidation unless tests show a real navigation or ownership problem.
- Keep route registration simple and searchable.
- Preserve public JSON schema versions during consolidation.

### Import Cycles

The current cycles are tolerable but should not harden.

Priority cycles:

- `controllers.rename_controller` and `controllers.rename_table_controller`. Fixed for the type-import edge by adding `RenameTableOwner`.
- `controllers.settings_controller` and `controllers.settings_form_controller`. Fixed for the type-import edge by adding `SettingsFormOwner`.
- Tk shell/network/app bootstrap cycle.

Recommended direction:

- Use narrow callback protocols or event methods instead of importing peer controllers.
- Move shared table/form helper code into one clearly owned helper module only if it avoids a cycle.
- Do not solve cycles by introducing many tiny indirection files.

## Process Lifecycle Hardening Plan

This is the highest-value next work because it reduces real-world stuck-process and unsafe-shutdown risk.

### Goals

- Verify Tauri close behavior with active backend and active PowerShell jobs.
- Verify backend shutdown does not orphan child processes silently.
- Verify ActiveJobs state is reconciled when the backend or shell exits unexpectedly.
- Verify stale progress/control files do not mislead the UI.
- Verify command routes surface clear failures.

### Required Tests

Add tests for:

- backend killed while PowerShell child remains alive
- Tauri close-readiness blocked by active pipeline
- forced Tauri close while pipeline process exists
- stale ActiveJobs record with dead PID
- malformed ActiveJobs JSON
- PID reuse or unverifiable PID identity
- progress file exists but is stale
- progress file exists but JSON is malformed
- stop/pause/rescan command route while no backend process is active

### Implementation Rules

- Do not change FFmpeg behavior during lifecycle hardening.
- Do not change PowerShell pipeline semantics unless a lifecycle bug requires it.
- Prefer explicit state records and clear operator warnings over hidden cleanup.
- Keep all destructive cleanup guarded and logged.

## Local API Stabilization Plan

### Goals

- Make the API stable enough for both Tk-adjacent preview and Tauri frontend use.
- Avoid route proliferation without contract discipline.
- Preserve backend ownership of all media-affecting commands.

### Required API Properties

- localhost bind only by default
- token required for command routes
- token required for sensitive read routes
- public health route only
- schema version on every structured response
- command result envelope for all mutations
- clear warnings/errors fields for operator UI
- no arbitrary file open route
- no arbitrary command route
- no raw path mutation from frontend

### Recommended Route Domains

- `/api/health`
- `/api/snapshot`
- `/api/telemetry`
- `/api/diagnostics/*`
- `/api/queue/*`
- `/api/pending-publish/*`
- `/api/rename/*`
- `/api/settings/*`
- `/api/process/*`
- `/api/maintenance/*`

### Routes To Avoid

Avoid generic routes like:

- `/api/run`
- `/api/open-path`
- `/api/write-file`
- `/api/delete`
- `/api/powershell`
- `/api/ffmpeg`

Those routes would undermine the backend ownership model.

## Frontend Migration Plan

### Current Frontend Role

The current web frontend should be treated as a preview shell, not the source of truth.

It may:

- render backend state
- collect form inputs
- call allowlisted API commands
- filter tables locally
- show recent command results
- show diagnostics summaries

It must not:

- infer final media routes independently
- construct FFmpeg arguments
- construct PowerShell arguments
- decide subtitle/audio policy
- write settings directly
- rename files directly
- decide pending publish state
- delete files

### Frontend Refactor Order

1. Extract `apiClient.js`. Done.
2. Extract shared helpers. Partly done: DOM helpers, formatters, and command-history state are extracted.
3. Extract queue view. Done.
4. Extract pending publish view. Done.
5. Extract rename view. Done.
6. Extract settings view. Done: overview, structured builders, patch preview/save, reload, and settings-specific event wiring are extracted.
7. Extract diagnostics view. Done except close-readiness, which intentionally remains in shell-level `app.js`.
8. Extract command-result panel. Done via `commandHistory.js`.
9. Add lightweight smoke tests for page load and key API calls.

### Frontend Done Criteria

- App loads in browser and Tauri shell.
- No backend policy logic exists in JS.
- Tables handle empty, loading, error, and stale data states.
- Telemetry graph displays valid zero values.
- Command failures are visible without opening log folders manually.
- Rename preview/apply uses backend-selected rows and backend validation.
- Settings save/preview uses backend patch API only.

## Tauri Shell Plan

### Current Shell Status

The shell is useful for preview. It is not yet the default launcher.

Current positives:

- starts backend with bundled Python
- captures bootstrap payload
- validates backend health
- passes token
- drains stdout/stderr
- checks close readiness
- asks for confirmation on unsafe close

Current hardening needs:

- better failure UI if backend startup fails
- explicit log path display on backend startup failure
- process-tree cleanup validation
- packaged-runtime path verification
- active-work close tests
- installer/release package tests

### Shell Ownership

Tauri should own:

- native window
- startup
- shutdown request
- backend process handle
- packaged path resolution
- update/install shell behavior later

Tauri should not own:

- media pipeline policy
- queue state
- settings interpretation
- rename logic
- pending publish behavior
- telemetry interpretation beyond rendering

## PowerShell Boundary Plan

PowerShell remains appropriate for the long-running pipeline. Do not rewrite the pipeline into Python during the UI transition.

PowerShell should continue to own:

- FFmpeg command construction
- ffprobe media analysis used by actual processing
- remux/encode decisioning
- subtitle extraction/conversion
- audio selection/transcoding
- scratch processing
- publish/drain
- sidecar and manifest writes
- audit/remediation
- route metadata

Python should own:

- UI-neutral state presentation
- launch/control of PowerShell
- settings editing and validation frontend
- diagnostics aggregation
- Tauri API surface
- rename standalone tool
- release package helpers

Boundary risk:

- Some policy exists in both Python and PowerShell for preview and validation. This is acceptable only when Python previews clearly call PowerShell helpers or share a documented contract. Avoid maintaining parallel naming/routing/subtitle rules in two languages.

## Testing Strategy

### Keep

- Full desktop unit suite.
- Release self-test.
- Reliability regression checks.
- Focused tests around path layout, rename, process launch, settings patch, and API contracts.

### Improve

Add black-box contract tests instead of more structure tests.

High-priority new tests:

| ID | Scenario | Expected Behavior |
|---|---|---|
| PROC-TAURI-01 | Tauri/backend close requested during active pipeline | close readiness blocks or warns clearly |
| PROC-ORPHAN-01 | Backend dies while child process remains | ActiveJobs records surface orphan/recovery state |
| PROC-PID-01 | ActiveJobs PID is dead, reused, or unverifiable | dead/reused records are orphaned; unverifiable records keep blocking close |
| API-AUTH-01 | Command route without token | 401 response |
| API-AUTH-02 | Public health route without token | ok response |
| API-CMD-01 | process command returns warning/error | command journal records bounded summary |
| RENAME-TXN-01 | sidecar locked during batch rename | no silent partial success; rollback or explicit partial failure |
| PUBLISH-INT-01 | pending publish interrupted mid-copy | next scan shows recoverable state |
| TELEMETRY-00 | NVENC utilization is 0% | graph remains visible and shows zero, not unavailable |
| SETTINGS-PATCH-01 | malformed patch payload | backend rejects with command-result error |
| WEB-LOAD-01 | web UI starts against local API | renders shell and first snapshot without console crash |

### Reduce

Avoid adding new tests that only assert:

- exact helper filenames
- exact internal module names
- exact mixin count
- extraction-specific wrapper existence

Those tests protect refactor mechanics but can lock in poor structure.

## Documentation Strategy

Use docs by role:

- `V5_TAURI_TRANSITION_CURRENT_PLAN.md`: current transition control plan.
- `archive/historical-reviews/TAURI_WEBVIEW2_TRANSITION_GROUNDWORK.md`: historical groundwork and detailed extraction ledger.
- `REMEDIATION_CHANGELOG.md`: chronological chunk log.
- `archive/historical-reviews/GUI_FRAMEWORK_DECISION_AND_MIGRATION_PLAN.md`: framework decision record.
- `TLDR.md`: operator-facing quick guide.
- `README_MediaPipelineRemuxEncodeAIO.md`: deployable bundle overview.

Do not turn the current transition plan into another extraction ledger. Keep it focused on direction, risk, gates, and next steps.

## Refactor Decision Rules

Before creating a new module, answer yes to at least one:

- Does this isolate a side effect such as subprocess, file I/O, state persistence, or OS integration?
- Does this create a stable API/facade boundary used by both Tk and Tauri/web?
- Does this remove an import cycle?
- Does this make a high-risk behavior independently testable?
- Does this separate frontend rendering from backend policy?
- Does this reduce a file that is genuinely too large and mixed-responsibility?

If the answer is only "this makes the file shorter," do not split it.

Before consolidating modules, answer yes to at least one:

- Are the modules only pass-through wrappers?
- Do they always change together?
- Does understanding one feature require opening too many tiny files?
- Are tests asserting module names rather than behavior?
- Does consolidation improve searchability without mixing responsibilities?

## Recommended Phase Order

### Phase 1: Stop Micro-Splitting And Lock Current Safety Baseline

Goal:

- Prevent architecture drift while preserving recent gains.

Tasks:

- Mark this document as the active transition plan.
- Stop further path/process/status/rename micro-extractions.
- Keep compatibility facades intact.
- Confirm full desktop tests still pass.
- Confirm release self-test executes bounded checks before major changes. A local environment failure is acceptable when configured UNC media roots are unavailable, but hangs/orphaned child processes are not.

Risk:

- Low.

### Phase 2: Process Lifecycle And Tauri Shutdown Hardening

Goal:

- Reduce real-world risk from stuck jobs, orphaned processes, stale runtime artifacts, and unsafe shell close.

Tasks:

- Add lifecycle failure tests.
- Validate Tauri close-readiness under active work.
- Validate backend shutdown and child-process behavior.
- Improve startup failure diagnostics if needed.
- Verify ActiveJobs stale/orphan handling.

Risk:

- Medium, because process control touches live operations.

### Phase 3: Local API Contract Stabilization

Goal:

- Make the API easier to reason about before expanding web/Tauri feature coverage.

Tasks:

- Consolidate overly granular API contract files by domain.
- Preserve route schemas and response shapes.
- Add API auth and command-result contract tests.
- Keep command routes allowlisted.

Risk:

- Medium, mostly from route wiring regressions.

### Phase 4: Web Frontend Modularization

Goal:

- Prevent `app.js` from becoming the new god file.

Tasks:

- Extract API client.
- Extract shared state.
- Extract screen modules.
- Keep behavior identical.
- Add browser/Tauri smoke tests.

Risk:

- Medium, mostly frontend regression risk.

### Phase 5: Import Cycle Cleanup

Goal:

- Improve maintainability without changing behavior.

Tasks:

- Break rename controller/table cycle.
- Break settings controller/form cycle.
- Defer network/app cycle until network cleanup.

Risk:

- Low to medium.

### Phase 6: Network Mode Decomposition

Goal:

- Reduce the biggest remaining Tk/network architectural hotspot.

Tasks:

- Separate network protocol, persistence, runtime, and UI concerns.
- Add coordinator/worker recovery tests.
- Keep standalone mode unaffected.

Risk:

- Medium to high if network mode is actively used.

### Phase 7: Tauri Feature Parity

Goal:

- Move from preview shell to viable daily shell.

Tasks:

- Queue view parity.
- Rename tool parity.
- Settings builder parity.
- Diagnostics parity.
- Pending publish parity.
- Process controls parity.
- Maintenance/release helper parity.

Risk:

- Medium.

### Phase 8: Release Packaging And Cutover

Goal:

- Decide when Tauri becomes default.

Tasks:

- Package Tauri shell with bundled Python/PowerShell/toolchain.
- Validate clean-machine launch.
- Validate no developer path dependency.
- Validate logs and diagnostics are discoverable.
- Keep Tk launcher as fallback for at least one release cycle.

Risk:

- High if rushed.

## Current Prioritized Backlog

| Priority | Work Item | Why It Matters | Status |
|---|---|---|---|
| P0 | Keep V4 untouched | Guarantees fallback | Active invariant |
| P0 | Stop low-value micro-splitting | Prevents architecture drag | Start now |
| P0 | Full tests after each risky chunk | Prevents silent migration breakage | Active |
| P1 | Process lifecycle hardening | Reduces orphan/stuck-job risk | In progress; ActiveJobs close-readiness guard added |
| P1 | Tauri close-readiness tests | Prevents unsafe shell shutdown | Expanded; source-level token/schema/safe-to-close checks added |
| P1 | API auth/command contract tests | Protects future frontend | Expanded; unresolved close-readiness, process auth, effect/auth invariants, and Web/Tauri route coverage covered |
| P1 | Web frontend module split | Prevents new frontend monolith | Mostly complete; shell `app.js` is about 238 lines with screen modules extracted |
| P2 | API contract file consolidation | Reduces navigation overhead | Done for route contracts; payload files deferred |
| P2 | Rename/settings import cycle cleanup | Reduces controller coupling | Done for owner type-import edges |
| P2 | Network subsystem cleanup | Largest remaining structural hotspot | Started; firewall, worker-state, worker HTTP, coordinator HTTP, probe, cluster-log, share-block, path-map, coordinator-URL, poll-policy, coordinator-policy, encode-config, failure-policy, worker-identity, worker-record, worker-done, shared diagnostics, Network tab async handoff guardrails, and coordinator save-failure propagation added |
| P3 | Tauri feature parity expansion | Moves toward daily shell | Started; Rename selected-row controls and Pending Publish detail placement fixed; Rust shell `cargo check`, prereq checker, build checker, and launch/close smoke passed |
| P3 | Packaging/cutover | Final adoption step | Last |

## Migration Gates

### Gate A: Backend Safety

Pass criteria:

- process launch tests pass
- shutdown tests pass
- ActiveJobs stale/orphan tests pass
- command-result failures are visible
- no new raw subprocess execution pattern is introduced

### Gate B: API Stability

Pass criteria:

- schema-versioned responses
- token behavior tested
- command routes allowlisted
- no arbitrary file/command routes
- Tk and web paths use same backend services

### Gate C: Web Frontend Maintainability

Pass criteria:

- `app.js` split into cohesive modules
- no business policy duplication in JavaScript
- major views handle loading/error/empty states
- smoke tests validate browser load

### Gate D: Tauri Daily-Use Readiness

Pass criteria:

- starts from clean bundle
- backend startup failures are actionable
- close readiness works
- diagnostics are visible
- process controls work
- queue, rename, settings, diagnostics, pending publish, and maintenance views are usable

### Gate E: Default Shell Cutover

Pass criteria:

- Tauri shell has daily workflow parity
- release package validates on clean Windows machine
- Tk launcher remains as fallback
- operator docs explain both launch paths
- no known media safety regression remains open

## WebView Promotion Gate

This gate defines the explicit blocking criteria that must all pass before Tauri graduates from **preview shell** to **daily driver**. It is separate from the Migration Gates (A–E), which track structural readiness. The Promotion Gate tracks operator-proven runtime safety for real work on real media.

None of these criteria are satisfied by static checks, `cargo check`, JavaScript syntax passes, or smoke tests against fixture data. Each requires live or adversarial evidence from the actual Tauri/WebView shell on the operator workstation.

### PG-1: Close-Readiness Adversarial Test

**What must be proven:**

- The backend is launched through the Tauri shell (not a standalone local API run).
- A real pipeline encode job is started and is actively running.
- While the job is running, the Tauri window close button is pressed.
- The Tauri shell must return `unsafe` from `close-readiness` and must display the watcher/active-work confirmation prompt.
- Clicking **Force Close** in that prompt must record a warning and must not silently orphan the PowerShell child process — the child must be confirmed terminated or handed off.

**Done looks like:**

- `Test-TauriShell-Launch.ps1` includes an active-work close-readiness assertion that passes.
- Or a separate adversarial smoke run records the prompt text and confirms no orphaned `pwsh.exe` process remains after close.

**Current status:** Proven for live active-work close. `DesktopApp\tauri_shell\Test-TauriShell-PG1ActiveClose.ps1` opened the Tauri preview shell, started a real single-file pipeline child through the Tauri-owned backend, captured the native active-work close prompt, confirmed close, verified no Tauri-owned shell/backend/pipeline child remained, and recorded ActiveJobs `status=killed`. Evidence is in `Docs\RealMediaValidationRuns\real_media_validation_20260517_tauri_pg1_active_close.md`.

---

### PG-2: Real-Media Validation Through the Tauri Shell

**What must be proven:**

- At least one known source file (e.g., an H.264 remux sample) is run start-to-finish using the Tauri shell as the launcher — not the Tk app, not a bare Python local API.
- The Tauri shell starts the backend, the operator launches the pipeline from the WebView, and the job completes.
- The resulting Completed output, sidecar, manifest, and (if applicable) Pending Publish entry all agree with the expected route, size policy, and subtitle/audio decisions.
- A Sample Validation evidence record is appended through the WebView Home panel.

**Done looks like:**

- A completed real-media validation worksheet (`Docs\RealMediaValidationRuns\`) with Tauri shell noted as the launch surface.
- The worksheet's pilot-evidence-packet rows show route, output, sidecar, size, Diagnostics, and Pending Publish as proven.
- Sample Validation record in `State\Validation\sample_validation_log.jsonl` with `shell: tauri`.

**Current status:** Proven for the promotion gate, with a conservative evidence caveat. The accepted PG-2 anchor is the queue-backed, post-fix Trigun S01E05 Tauri/WebView run: the WebView launch path completed the selected source end-to-end, ActiveJobs reached `status=completed` with return code `0`, output/sidecar/Completed evidence agreed, the run proved TV classification, sidecar `media_type=tv`, subtitle conversion, audio copy decisions, and corrected WebView evidence labels/counts, and the operator confirmed playback, subtitles, and audio on 2026-05-17. Evidence is in `Docs\RealMediaValidationRuns\real_media_validation_20260517_tauri_queuebacked_trigun05_postfix_label_count_pilot.md`. Spy x Family S01E10 and Trigun S01E03/S01E04 remain supporting evidence because they lack either pre-run Queue proof or have historical pre-fix label/UI evidence issues. Existing JSONL records remain historical `hold_review`; append a fresh current accepted record only when backend preview reports `accepted_ready=true`.

---

### PG-3: Clean-Machine Install Validation

**What must be proven:**

- The release bundle (deployable package) is copied to a machine that has no development environment: no Visual Studio, no Rust toolchain, no Poetry/pip environment, no Claude Code workspace.
- The Tauri launcher starts without referencing any developer path (e.g., `%USERPROFILE%\.cargo`, `DesktopApp\tauri_shell\src-tauri\target`, a local Python `venv`).
- The bundled Python runtime, bundled PowerShell, bundled FFmpeg/ffprobe, and bundled MKVToolNix all resolve correctly.
- The WebView window opens, the backend serves the expected routes, and at minimum the Home, Launch, Queue, Diagnostics, and Settings pages load without console errors.

**Done looks like:**

- `Test-TauriShell-Prereqs.ps1 -CheckOnly` passes on the clean machine from the bundle directory.
- `Test-TauriShell-Launch.ps1 -Mode Packaged` (bounded, non-media-processing) passes on the clean machine without Node, npm, cargo, or Visual Studio build tools.
- `New-TauriShell-PG3CleanMachineReport.ps1` records the clean-machine report from the copied bundle with no bundle-layout mismatches and no developer tools detected outside the bundle.
- A brief operator note documents the clean-machine test: OS version, machine name, and confirmation that no developer tools were present.

**Current status:** Not yet proven. The prereq and launch scripts are now aligned with the clean-machine proof boundary (`-CheckOnly` accepted, package-mode launch available, and bundle-relative `DesktopApp` resolution preferred before the baked-in development root). A local copied-bundle package-mode launch smoke passed on the development workstation, and the copied-bundle report helper validated bundle layout with zero mismatches, but a true clean-machine test still has not been documented because it requires a separate Windows machine with no development environment.

---

### Promotion Gate Summary

| Gate | ID | Status |
|---|---|---|
| Close-readiness adversarial test (active encode → unsafe + no orphan) | PG-1 | Proven for live active-work close; combined armed-watcher + active-child prompt still scaffold/browser covered |
| Real-media run through Tauri shell with worksheet evidence | PG-2 | Proven via queue-backed Trigun S01E05 post-fix Tauri/WebView run plus operator playback/subtitle/audio acceptance; existing JSONL records remain historical `hold_review` until a fresh current accepted append is made |
| Clean-machine install validation from release bundle | PG-3 | Not proven; local package-mode copied-bundle smoke and report-helper layout validation passed |

All three must be marked **Proven** before Tauri becomes the default launcher. Partial evidence (e.g., fixture-only smoke, Tk-shell sample run, dev-machine prereq check) does not satisfy these criteria. The gate is intentionally conservative: a single proven run per criterion is sufficient to unlock the next phase, but any regression resets the relevant item.

---

## Known Risks

### Architecture Astronautics

Risk:

- The project gains many small files without becoming easier to debug.

Mitigation:

- Use this document's refactor decision rules.
- Consolidate thin pass-through modules after contracts stabilize.

### Split Brain Between Tk And Web

Risk:

- Tk and web paths diverge and produce different behavior.

Mitigation:

- Both shells must call the same facade/service commands.
- Frontend-only code must remain render/input focused.

### Incomplete Tauri Lifecycle Ownership

Risk:

- Shell closes but backend or PowerShell child process remains in an ambiguous state.

Mitigation:

- Add lifecycle tests.
- Keep close-readiness strict.
- Surface active work and log paths clearly.

### Overfitted Tests

Risk:

- Tests freeze helper-file names and make necessary consolidation painful.

Mitigation:

- Add behavior tests.
- Avoid new structure-only tests except for critical packaging invariants.

### Network Mode Drag

Risk:

- Experimental network code remains large and cyclic, slowing future development.

Mitigation:

- Keep standalone as supported default.
- Refactor network mode as a separate phase.

## Cutover Position

Do not make Tauri the default launcher yet.

The correct current position is:

- Tk desktop app: supported production shell.
- Local API: active backend-boundary platform.
- Web frontend: preview UI under active development.
- Tauri shell: preview shell for validating desktop packaging/lifecycle.
- V4: backup/fallback.
- V5: active transition workspace.

## Definition Of Done For The Transition

The transition is not done when the Tauri shell opens. It is done when:

- The Tauri shell can perform the normal daily operator workflow.
- The backend survives and reports failures clearly during interrupted jobs.
- Rename, queue, settings, diagnostics, pending publish, audit, and maintenance workflows have parity.
- No frontend duplicates pipeline business logic.
- Packaging works without development-environment assumptions.
- Tests cover real runtime failure modes.
- Tk remains available as fallback for at least one stable release cycle.

## Immediate Next Chunk Recommendation

Current checkpoint:

- Full desktop unit discovery: 989 tests passing.
- Tauri build checker: passed with WebView JavaScript `node --check` and Rust `cargo check` after the latest lifecycle/diagnostics changes.
- Tauri launch/close smoke: passed, including backend detection and cleanup.
- Release self-test: passed without tool-integration or end-to-end smoke skips.
- WebView/Tauri diagnostics parity: `cluster.log` is now an allowlisted diagnostics-open target and is exposed in both Network and Diagnostics pages.
- WebView daily-use parity pass: queue/completed/pending/failure/audit screens now show operator next-step guidance when empty or unselected, and the parity matrix is linked from the docs index.
- WebView launch feedback: pipeline, audit, CSV rerun, and pending-publish drain actions now preserve backend warnings/errors inline beside the action that produced them.
- Web/Tauri route coverage: every Python local API read/command contract route is referenced by static assets or Tauri lifecycle code.
- Web command allowlist coverage: diagnostics, completed-row, pending-row, pipeline control, launch mode, and schedule override controls expose the backend allowlists.
- Startup compatibility: Tauri validates health plus `/api/contract` method/path/auth triples before opening the WebView.
- Runtime safety: close-readiness fails closed for unverifiable related process, ActiveJobs, pipeline progress, and audit progress state, and logs verification exceptions.
- Runtime recovery: stale ActiveJobs records whose PID was reused by a clearly unrelated process are now reconciled as orphaned instead of blocking close forever.
- Local API safety: malformed negative request lengths are rejected before body reads, and static assets are resolved under the asset root.
- Network config safety: malformed coordinator port and heartbeat settings fall back to documented defaults with warnings, and operator share text follows the same valid port range.
- Backend lifecycle diagnostics: shutdown still fails closed when close-readiness verification fails, and now logs the underlying exception for the operator diagnostics trail.
- Backend lifecycle coverage: scheduled shutdown callback failures are now covered so future Tauri lifecycle refactors cannot silently hide failed backend shutdown callbacks.
- Settings patch safety: same-value Local API settings patches no longer create diffs, backups, or dirty-state saves.
- Command-history safety: loaded Local API command history rows are sanitized to the same bounded summary shape as newly recorded command results.
- Tauri lifecycle safety: shell backend HTTP responses are capped before parsing to prevent malformed local responses from causing unbounded memory growth.
- Web client diagnostics: non-JSON backend failures now surface bounded response text or HTTP status instead of a generic JSON parse error.
- Web refresh safety: shared browser GET requests now use an `AbortController` timeout so one hung backend read cannot permanently wedge refresh coalescing; POST commands remain timeout-free by default unless a caller opts in.
- Web rename parity: browser-side rename row keys now use deterministic lowercasing while backend-selected apply remains the filesystem mutation authority.
- Local API startup diagnostics: public `/api/health` failures now return a logged JSON error envelope instead of escaping the handler guard.
- Web bootstrap safety: `index.html` must contain the backend bootstrap placeholder or the Local API returns a clear startup error.
- Local API error safety: route/static exception responses now bound error text before returning it to the WebView.
- Local API response integrity: WebView API responses now reject non-finite JSON and fall back to a logged strict 500 envelope.
- Local API command-history integrity: command journal saves now reject non-finite JSON and clean up temp files on serialization failure.
- Local API request integrity: WebView request bodies now reject non-standard JSON constants such as `NaN` and `Infinity`.
- Process launch safety: if a child process starts but ActiveJobs launch recording or readiness verification fails, the app now stops that just-started process instead of leaving an untracked PowerShell pipeline running.
- Network failure visibility: worker done/release report failures now surface through the operator-facing worker status callback instead of being log-only.
- Worker heartbeat visibility: active worker heartbeat POST failures and coordinator reclaim responses now surface through the operator-facing worker status callback before the existing abort/recovery path continues.
- Coordinator stale-report visibility: unknown worker done/release reports now leave coordinator-side cluster-log events before returning the existing `404 not_found` response.
- Coordinator auth-token diagnostics: generated or hot-rotated coordinator tokens are no longer logged as persisted when app-state persistence fails; the warning now makes clear the token is active only for the current run.
- Network tab UI handoff diagnostics: coordinator health, worker auth, coordinator URL test, coordinator discovery, and Windows Firewall background probes now log `root.after(...)` scheduling failures instead of dying silently during Tk teardown or UI disruption.
- WebView refresh render safety: unexpected refresh/render exceptions now update the activity line and refresh-health pill instead of leaving a stale shell with only a console-side failure.
- Tauri backend shutdown diagnostics: graceful `/api/backend/shutdown` request failures are now written to shell stderr before the existing wait/kill cleanup path continues.
- Tauri backend bootstrap diagnostics: backend stdout disconnection before bootstrap is now reported separately from bootstrap timeout, making immediate backend crashes easier to distinguish from slow startup.
- WebView completed-open gating: completed-row open buttons now disable during `/api/completed/open` requests to avoid duplicate shell-open commands from rapid clicks.
- WebView rename-preview gating: rename Preview now disables during `/api/rename/preview` requests and ignores stale responses superseded by newer preview requests.
- WebView settings-preview gating: settings patch preview now reports stale results when the patch JSON changes before the backend preview response returns.
- WebView maintenance-refresh coalescing: maintenance health reads now serialize with a one-shot queued follow-up instead of allowing overlapping `/api/maintenance` renders.
- WebView launch-command gating: pipeline start, pending-publish drain, audit start, and CSV rerun start now share a busy guard so the shell does not submit overlapping start commands.
- WebView pipeline-control gating: Pause/Resume, Rescan, and Stop After Current now keep explicit in-flight state so duplicate toggle-like control submissions are rejected.
- WebView settings-command serialization: settings validate, reload, preview, and save commands now share a busy guard so the shell cannot show mixed-state settings results.
- WebView maintenance dry-run serialization: release package dry-run and completed-manifest backfill dry-run now share a busy guard while normal maintenance health refresh remains independent.
- WebView rename apply guard: selected-row rename apply now rejects while a preview request is active so stale row predictions cannot be applied after the operator changes inputs.
- WebView rename apply serialization: selected-row rename apply now also tracks apply-in-flight state and keeps preview/apply buttons synchronized during backend mutation.
- WebView open-command guards: diagnostics/report, completed-row, and pending-publish open commands now keep explicit in-flight state instead of relying only on disabled buttons.
- WebView Network page parity: the Tauri/WebView shell now has a dedicated read-only Network page wired to existing settings, local API contract, and diagnostics-open surfaces without creating split-brain coordinator/worker mutation controls.
- WebView cluster-log parity: the diagnostics-open contract now exposes `cluster_log`, resolved by the backend to the app-root `cluster.log`, and both Network and Diagnostics pages expose buttons for it.
- WebView inventory/report guidance: queue, completed, pending publish, failure, and audit views now explain empty/unselected states with concrete operator next steps instead of generic “no rows” text.
- WebView launch command feedback: launch/drain panels now use shared command-result formatting so blocked starts, warning-severity starts, and backend error lists are visible without opening Diagnostics.
- Local API settings diagnostics: settings reload exceptions, including post-save reload failures, now leave server-side log entries, and reload error payloads are bounded before returning to the WebView.
- Tauri backend HTTP diagnostics: non-200 backend responses now include a bounded body preview in shell errors instead of reporting only the HTTP status line.
- Tauri backend termination diagnostics: forced backend termination after the graceful shutdown window now logs the timeout path and any kill/wait errors.
- Backend launch serialization: pipeline start, audit start, and CSV rerun start now share a facade-level nonblocking launch lock around active-work verification and process start.
- Backend pipeline-control serialization: pause, stop, and rescan control flag writes now share a facade-level nonblocking control lock.
- Backend maintenance dry-run serialization: release-package dry-run and completed-manifest backfill dry-run now share a facade-level nonblocking maintenance lock around synchronous dry-run service calls.
- Backend rename apply serialization: selected rename apply now holds a facade-level nonblocking lock from backend plan rebuild through filesystem mutation.
- Backend settings save serialization: settings patch save now holds a facade-level nonblocking lock from backend patch candidate construction through PSD1 save.
- Coordinator UI visibility: live worker-board scheduling/snapshot failures now log and show a board warning instead of leaving stale state silently.
- Crash recovery safety: coordinator in-flight registry load now skips malformed persisted rows transactionally instead of partially mutating live recovery state.
- Coordinator startup safety: HTTP bind failures now raise after logging so the UI cannot mark a non-listening coordinator as active.
- Coordinator shutdown safety: `/api/claim` now honors the draining `accepting_claims=false` state and refuses fresh work during teardown.
- Worker claim safety: if a claimed job cannot be converted into a local queue record, the worker now releases the claim immediately instead of waiting for stale-heartbeat reclaim.
- Worker recovery safety: worker done/release paths now clear crash-recovery state only after the coordinator accepts the report.
- Worker recovery precision: failed worker terminal reports now persist exact pending `/api/done` payloads and crash recovery retries those payloads before falling back to crash-failed reporting.
- Network diagnostics: worker/coordinator HTTP JSON helpers now report invalid success-body JSON and HTTP error bodies with URL context and bounded previews.
- Network probe diagnostics: coordinator health probe failures now normalize unreachable coordinator and HTTP error details before they reach Network tab status text.
- Network auth probe diagnostics: worker-auth probe HTTP failures now use status-code-aware details for 401 and other HTTP errors, and unreachable coordinators use bounded reachability text.
- Local API diagnostics durability: command history now writes through unique fsynced temp files and atomic replace so WebView operator feedback survives interruption more reliably.
- Runtime diagnostics: malformed pipeline progress, audit progress, and event files now log the exact file path that failed validation or parsing.
- Command-history diagnostics: failed cleanup of temporary command-journal files after save failures is now logged instead of silently ignored.
- Diagnostics visibility: optional diagnostics path lookup failures now log backend context while preserving the existing missing-path command result contract.
- Settings diagnostics: redacted diff generation now logs PSD1 serializer failures before using the existing JSON fallback.
- Network durability diagnostics: failed cleanup of temporary coordinator in-flight registry and worker crash-recovery state files after save failures is now logged.
- Network worker startup: malformed `WorkerPollIntervalSecs` now warns and falls back to the default instead of crashing worker startup, too-small values warn and clamp to 5 seconds, and worker crash-state cleanup failures are operator-visible warnings.
- Network view handoff diagnostics: coordinator URL test, mDNS discovery, firewall check, and firewall add-rule background operations now log failed Tk scheduling attempts.
- Network tab probe startup diagnostics: coordinator URL/status/auth probes, worker-board polling, coordinator status polling, and firewall operations now log daemon-thread startup failures and restore visible UI state where possible.
- Network tab clipboard diagnostics: coordinator token, regenerated token, coordinator address, share-block copy, and worker-token paste failures now leave warning logs instead of escaping silently from button callbacks.
- Network tab queue-refresh scheduling diagnostics: coordinator auto-refresh and delayed refresh-button re-enable scheduling failures now warn and keep the operator pointed at manual Refresh Queue recovery.
- mDNS registration failure cleanup: failed coordinator mDNS registration now clears partial Zeroconf state and does not mark coordinator advertisement active.
- Coordinator queue-removal logging accuracy: terminal done-report queue removal now logs as scheduled only after Tk accepts the callback, and scheduling failures warn that the queue record may remain claimable until removed.
- Worker heartbeat snapshot diagnostics: progress snapshot read failures now warn with job context and continue by sending a safe 0% heartbeat.
- Worker accepted-report cleanup separation: coordinator-accepted done/release reports no longer save pending retry payloads if local worker-state cleanup fails afterward.
- Worker crash-recovery cleanup guardrails: accepted crash-recovery done reports and retried pending done reports now use the accepted-report cleanup helper so cleanup failures warn instead of aborting startup.
- Worker accepted-cleanup diagnostic accuracy: worker-state cleanup now returns success/failure so accepted-report cleanup logs contextual no-pending-retry guidance for real cleanup failures.
- Worker crash-recovery state anomaly diagnostics: missing crash-recovery job ids and malformed pending done reports now warn before cleanup or fallback recovery.
- Worker crash-state save diagnostics: failed `worker_state.json` saves now update worker status and emit a `worker_state_save_failed` cluster event because restart recovery may miss the active job.
- Pending done-report save diagnostics: failed pending done/release retry saves now update worker status and emit a `pending_done_save_failed` cluster event because restart retry may miss the report.
- Pending retry log accuracy: failed done/release reports now distinguish saved pending retries from retry-payload save failures.
- Coordinator in-flight save diagnostics: failed coordinator in-flight registry saves after claim, release, and done-report bookkeeping now emit best-effort `inflight_save_failed` cluster events.
- Local coordinator in-flight save diagnostics: failed local coordinator claim/release in-flight registry saves now emit best-effort `inflight_save_failed` cluster events.
- Missing local-completion save diagnostics: failed registry saves after reclaimed/duplicate local completion now emit best-effort `inflight_save_failed` cluster events without emitting misleading completion events.
- Shutdown in-flight save diagnostics: failed final coordinator in-flight registry saves during shutdown now emit best-effort `inflight_save_failed` cluster events.
- Stale-reaper in-flight save diagnostics: failed periodic coordinator in-flight registry saves in the stale-job reaper now warn explicitly and emit best-effort `inflight_save_failed` cluster events.
- Stale-reclaim cluster-log guardrails: stale-job reaper reclaim diagnostics now use the safe coordinator cluster-log wrapper so diagnostic failures do not skip registry persistence.
- Worker terminal-report log accuracy: done/release logs now distinguish coordinator-accepted reports from reports saved for pending retry after POST failure.
- Worker internal-release log accuracy: internal release logs now distinguish coordinator-accepted reports from reports saved for pending retry after POST failure.
- Worker cluster-log POST diagnostics: failed best-effort cluster-log POSTs now warn locally with event context instead of disappearing at DEBUG level.
- Coordinator cluster-log timestamp diagnostics: `/api/log` now warns if the worker timestamp side-channel cannot be preserved before falling back to coordinator receive time only.
- Coordinator oversized-request response diagnostics: failed attempts to send the 413 body-size rejection now warn that the client may not receive the response.
- Coordinator malformed-length response diagnostics: failed attempts to send the malformed `Content-Length` 400 response now warn that the client may not receive the response.
- Coordinator body-read diagnostics: accepted bounded request bodies now warn and stop dispatch if the socket read itself fails.
- Coordinator JSON response send diagnostics: normal coordinator JSON response send failures now warn with status before preserving the existing exception behavior.
- Coordinator OPTIONS response send diagnostics: preflight response send failures now warn before preserving the existing exception behavior.
- Worker claim-failure diagnostics: worker claim poll failures now warn once per distinct error text while repeated identical failures stay at DEBUG, with bounded warning/debug/status previews.
- Worker heartbeat POST diagnostics: worker heartbeat POST failures now warn once per distinct error text while repeated identical failures stay at DEBUG, with bounded warning/debug/status previews.
- Shared network diagnostic policy: worker diagnostics and Network tab operator failure paths now use a common bounded diagnostic preview helper instead of local ad hoc truncation.
- mDNS service-resolution diagnostics: discovered service records that fail resolution now warn and continue the scan instead of disappearing at DEBUG level.
- Firewall check exit-status diagnostics: nonzero `netsh` firewall-check exits now return a warning with the manual check command instead of reporting a missing rule.
- Firewall add-rule output diagnostics: nonzero add-rule exits now include bounded `netsh` stdout/stderr detail with the manual command.
- Network tab coordinator discovery startup failures now log warning diagnostics in addition to the visible status-line failure.
- Network tab live hot-swap diagnostics: discovered coordinator URL and pasted worker auth-token hot-swap failures now log while preserving field updates.
- Network tab open diagnostics: RunLogs and cluster-log open failures now leave logs in addition to messagebox feedback.
- Network controller lifecycle diagnostics: dispatcher shutdown failures and worker poll-status UI post failures now log instead of being suppressed.
- Network heartbeat contract safety: worker heartbeat progress is now finite-validated and clamped to 0..100 before it reaches coordinator state.
- Network state integrity: coordinator in-flight registry and worker crash-recovery state writes now reject non-finite JSON instead of emitting `NaN`/`Infinity`.
- Network HTTP contract integrity: outbound worker/coordinator JSON POST bodies now reject non-finite values before any network request is sent.
- Coordinator response integrity: coordinator JSON responses now reject non-finite payloads and fall back to a strict logged 500 JSON envelope.
- Network input integrity: coordinator request bodies, worker HTTP responses, network state files, and JSON-backed network settings now reject non-standard JSON constants.
- mDNS discovery diagnostics: service-resolution failures, Zeroconf close failures during discovery cleanup, and async discovery thread-start failures are now logged instead of being swallowed or surfacing as low-context thread errors.
- Coordinator cluster-log diagnostics: failed best-effort cluster-log rotation now warns while preserving append behavior.
- Network local-IP consistency: Network tab display and mDNS advertising now use the same RFC-1918 priority and UDP fallback policy.
- Coordinator shutdown diagnostics: HTTP shutdown/close, mDNS stop, stale-reaper join, and final in-flight registry save failures now warn instead of being silently suppressed.
- Coordinator shutdown active-count lookup failures now warn and continue teardown instead of blocking HTTP/reaper/mDNS cleanup.
- Coordinator shutdown cluster-log failures now warn and continue HTTP/reaper/mDNS teardown plus final in-flight registry persistence.
- Coordinator claim-handoff cluster-log failures now warn and still return the successful claim response after the claim is recorded.
- Coordinator reclaimed-heartbeat cluster-log failures now warn and still return the `reclaimed` heartbeat response so workers abort promptly.
- Coordinator terminal done cluster-log failures now warn and still save final in-flight state, run queue-removal policy, and return the worker `ok` response.
- Coordinator startup cluster-log failures now warn without aborting startup after HTTP, stale-reaper, and mDNS startup have completed.
- Coordinator auth-token rotation cluster-log failures now warn without undoing or failing a live token update after persistence succeeds.
- Coordinator HTTP startup cleanup now closes a partially-created server and clears `_http_server` if the serving thread cannot start.
- Coordinator reaper startup cleanup now tears down a partially-started HTTP server if stale-reaper startup fails after HTTP startup.
- Worker poll-thread startup failures now log the coordinator URL, clear the thread reference, and raise a clear `RuntimeError` instead of escaping as an uncontextualized thread error.
- Coordinator mDNS advertisement startup failures now warn with manual-URL fallback guidance instead of staying debug-only.
- Network controller UI diagnostics: dispatcher fallback status, coordinator-button refresh, and coordinator notice update failures now warn instead of being silently suppressed.
- Worker cluster-log dispatch guard: failure to start the best-effort background cluster-log POST thread now warns without interrupting worker control flow.
- Worker heartbeat progress sanitization: malformed, non-finite, and out-of-range local progress snapshots are bounded before heartbeat JSON is sent.
- Network protocol numeric contract hardening: numeric strings that coerce to non-finite or negative values are rejected at DTO parse boundaries.
- Coordinator retry-hint diagnostics: active-count lookup failures now warn before falling back to the existing idle retry hint.
- In-flight registry numeric state hardening: persisted and claim-time numeric state now rejects or sanitizes non-finite and negative worker/job metrics.
- Coordinator claim size estimate guard: malformed queue-record estimated sizes now warn and fall back to `0.0` before HTTP/local claim handling continues.
- Process lifecycle shutdown cleanup diagnostics: taskbar reset, Tk poll cancellation, and `root.quit()` cleanup failures now warn while shutdown continues.
- Status server stop diagnostics: legacy status server shutdown and close failures now warn while UI state is cleared.
- Status server strict JSON telemetry: non-finite snapshot telemetry is converted to `null` before legacy status JSON is encoded.
- Settings structured control diagnostics: encoder flag/audio passthrough widget state update failures now warn instead of leaving stale controls silently.
- Source path-map entry diagnostics: malformed individual WorkerSourcePathMap entries now warn while valid mappings continue to load.
- Status server pause-flag diagnostics: remote status polling now warns when pause flag checks fail instead of silently reporting unpaused.
- Retry-hint policy diagnostics: invalid retry active-count inputs now warn once at the policy boundary while coordinator registry failures avoid duplicate warning cascades.
- mDNS cleanup visibility: coordinator advertisement and discovery close/unregister failures now warn instead of being debug-only.
- Coordinator health fallback diagnostics: `/api/health` heartbeat-timeout lookup failures now warn before returning the existing 5-minute fallback.
- Worker hostname fallback diagnostics: worker hostname lookup failures now warn before using the existing `worker` fallback name.
- Local IP fallback diagnostics: hostname and UDP-route IP detection failures now warn before falling back.
- Coordinator reaper interval fallback diagnostics: stale-job reaper cadence fallback now warns when heartbeat-timeout lookup fails.
- Cluster-log size inspection diagnostics: failed `cluster.log` size checks now warn while best-effort append continues.
- Coordinator invalid-request diagnostics: invalid `/api/done`, `/api/heartbeat`, and `/api/log` bodies now warn with endpoint context while still returning the existing 400 response.
- Coordinator request-identifier diagnostics: invalid `/api/done` and `/api/heartbeat` worker/job identifiers, plus missing `/api/log` event names, now warn before returning the existing 400 response.
- Coordinator cluster-log field sanitization diagnostics: `/api/log` now warns when worker/job identifiers are stripped or oversized event/message fields are truncated before append.
- Worker heartbeat cleanup diagnostics: worker shutdown/release now warns if the heartbeat thread does not exit within the existing bounded join.
- Worker heartbeat-start recovery: if a claimed worker job cannot start its heartbeat thread, the worker now logs, updates status, emits a cluster event, and releases the claim immediately instead of waiting for coordinator stale-timeout recovery.
- Worker claim-handoff recovery: unexpected failures after a successful worker claim now log, update status, and release the claim instead of killing the poll loop with an active job.
- Worker claim-preparation recovery: malformed claimed responses and source path-map failures now log, surface cluster events when possible, and release the claim immediately instead of waiting for stale timeout.
- Worker malformed-claim diagnostics now bound parse-reason text before warnings, cluster-log messages, and release status text.
- Worker unstartable-claim release diagnostics now bound release-reason and release-POST exception text before failed-release warnings/status while preserving release payloads.
- Worker cluster-log failure diagnostics now bound exception text for POST failures, thread-start failures, and safe-wrapper failures.
- Worker status callback failure diagnostics now bound exception text so UI callback failures cannot flood worker logs.
- Worker reclaimed-abort scheduling diagnostics now bound UI handoff exception text without dumping full tracebacks.
- Worker heartbeat-start failure diagnostics now bound thread-start exception text before log, status, and cluster-log reporting.
- Worker claimed-job schedule failure diagnostics now bound UI handoff exception text before log and status reporting while still releasing the claim.
- Worker claim-handoff failure diagnostics now bound unexpected post-claim exception text before log and status reporting while still releasing the claim.
- Worker claim-record diagnostics now bound QueueRecord build exception text before log, cluster-log, and release-reason reporting while still releasing the claim.
- Worker done/release POST failure diagnostics now bound coordinator exception text before worker logs and operator status while preserving pending retry save behavior.
- Worker poll-thread shutdown diagnostics: worker shutdown now warns if the poll thread remains alive after the existing bounded join.
- Local coordinator runtime diagnostics: local coordinator encode claims/releases now survive in-flight registry save failures with warnings, and malformed local heartbeat telemetry logs without aborting the active job.
- Coordinator claim-rejection diagnostics: missing or invalid `/api/claim` worker IDs now warn before returning the existing 400 response.
- Worker-board endpoint failure diagnostics: `/api/workers` snapshot failures now return a logged JSON 500 envelope instead of unwinding the request handler.
- Worker-board runtime-stat sanitization: active and idle worker snapshots now sanitize malformed in-memory worker stats/progress with warnings instead of failing the entire board.
- Worker crash-recovery cluster-log guardrails: successful crash-recovery done reports now still clear worker state if the follow-up cluster-log event fails.
- Worker crash-recovery cluster-log diagnostics now use the shared worker safe wrapper for orphaned-job and pending done-report recovery events.
- Worker crash-recovery POST failure diagnostics now bound pending done-retry and crash-failed report exception text while preserving retained retry state.
- Worker-board UI render isolation: worker-board controller snapshot and row-render failures now log without clearing existing rows or blocking other valid rows.
- Worker lifecycle controller guardrails: malformed completion-event rows are skipped, completion report build/submit crashes fail closed without leaving stale UI active-job state, post-launch UI failures no longer misreport running encodes as failed, and reclaimed-job abort falls back to synchronous process-tree kill if background scheduling fails.
- Coordinator claim/done/heartbeat state-failure guardrails: claim, done, release, and heartbeat registry failures now return logged JSON 500 responses; successful claims are released immediately if post-claim retry-policy lookup fails before the worker receives the claim.
- Worker cluster-log control-flow isolation: best-effort worker cluster-log failures now warn without blocking path-map handling, claim record release, job handoff, heartbeat reclaim aborts, completion reporting, or clean release reporting.
- Coordinator cluster-log append guardrails: best-effort coordinator diagnostics now warn without escaping if cluster-log path resolution, line formatting, or the `/api/log` append call fails unexpectedly.
- Worker shutdown/auth cluster-log guardrails: best-effort worker diagnostics now warn without interrupting shutdown release or the auth-error poll loop.
- Worker auth probe failure details are normalized so Network tab auth checks use explicit 401, HTTP error, and reachability details.
- HTTP JSON error-body previews are bounded so large coordinator error responses do not flood worker/coordinator diagnostics.
- Worker poll auth-error classification now requires a structured HTTP 401 status prefix so unrelated error bodies mentioning 401 remain ordinary poll errors.

The previous WebView command-ordering chunk is now substantially complete:

- duplicate WebView launch, control, settings, maintenance, rename, open, and preview/apply submissions are guarded;
- backend Local API process launch, process control, maintenance dry-run, rename apply, and settings save mutation paths have facade-level nonblocking locks;
- full desktop discovery is green at 989 tests.

The process lifecycle failure-test chunk is substantially complete:

- ActiveJobs close-readiness now has focused coverage for live, dead, malformed, unverifiable, and PID-reuse records.
- Tauri close-readiness source coverage now verifies that active-work warnings include backend reason/state details.
- Local API scheduled shutdown-callback failures now have async coverage that verifies callback execution and exception logging.
- Runtime progress/audit/event malformed-file diagnostics now include exact paths.
- Focused ActiveJobs, facade close-readiness, Local API shutdown, process spawn-runner, status reader, and Tauri source tests are green.

The network durability diagnostics pass has started:

- Coordinator in-flight registry and worker crash-recovery state temp cleanup failures are now logged.
- Worker poll interval parsing is now policy-backed and malformed config falls back safely with warnings.
- Worker crash-state cleanup failures are now warnings because stale state can affect restart recovery.
- Worker crash-state save failures now reach the operator status channel and cluster log because restart recovery may miss the active job.
- Pending done-report save failures now reach the operator status channel and cluster log because restart retry may miss the terminal report.
- Failed terminal-report logs now avoid saying a pending retry was saved when the retry-payload save failed.
- Coordinator in-flight registry save failures now reach cluster-log diagnostics after claim, release, and done-report bookkeeping.
- Coordinator in-flight registry write failures now propagate from the registry save helper after temp-file cleanup, so accepted claim/release/done state transitions actually reach the coordinator's `inflight_save_failed` diagnostics.
- Local coordinator in-flight registry save failures now reach cluster-log diagnostics after local claim and release.
- Missing local-completion registry save failures now reach cluster-log diagnostics without creating a false completion event.
- Shutdown in-flight registry save failures now reach cluster-log diagnostics during coordinator teardown.
- Stale-reaper in-flight registry save failures now reach cluster-log diagnostics during periodic progress/reclaim persistence.
- Stale reclaim cluster-log failures no longer prevent the reaper from saving reclaimed state.
- Stale done/release report cluster-log failures no longer prevent the coordinator from returning the existing `404 not_found` or `403 forbidden` responses.
- Coordinator shutdown cluster-log failures no longer prevent teardown or the final in-flight registry save.
- Coordinator claim-handoff cluster-log failures no longer prevent the worker from receiving a successfully recorded claim response.
- Coordinator reclaimed-heartbeat cluster-log failures no longer prevent the worker from receiving the abort signal.
- Coordinator terminal done cluster-log failures no longer prevent final save or worker acknowledgement after completed/failed reports.
- Coordinator startup cluster-log failures no longer leave a ready coordinator treated as failed startup.
- Coordinator auth-token rotation cluster-log failures no longer make a completed live token update look failed.
- Worker crash-recovery cluster-log failures now use the shared safe-wrapper warning path while preserving accepted-report cleanup.
- Coordinator health probe failure details are normalized so Network tab status avoids raw socket exception text.
- Network tab background handoff failures are now covered for coordinator URL tests, mDNS discovery, and firewall operations.
- Network tab background probe thread-start failures are now covered for coordinator URL/status/auth probes, worker-board polling, coordinator status polling, and firewall actions.
- Network tab clipboard failures are now covered for coordinator token copy, regenerated-token copy, coordinator address copy, share-block copy, and worker-token paste actions.
- Network tab queue-refresh scheduling failures are now covered for startup auto-refresh scheduling, delayed re-enable scheduling, and fallback UI update failures.
- Network tab coordinator discovery startup failure logging is now covered so failed mDNS discovery launch does not remain status-line only.
- Network tab live hot-swap failures are now covered for discovered coordinator URL and pasted auth-token paths.
- Network tab open-diagnostic failures are now covered for RunLogs and cluster-log actions.
- Network controller dispatcher shutdown and worker-status UI post failures are now covered in controller tests.
- Network heartbeat progress coercion is now covered at the protocol and in-flight registry boundaries.
- Network state strict-JSON persistence is now covered for coordinator in-flight state and worker pending done-report state.
- Network HTTP strict-JSON payloads are now covered so non-finite POST bodies fail before `urlopen()`.
- Coordinator strict-JSON response fallback is now covered for non-finite response payloads.
- Network strict-JSON reads are now covered for HTTP responses, coordinator request bodies, worker state, and JSON-backed network settings.
- Local API strict-JSON response fallback is now covered for non-finite WebView response payloads.
- Local API command-journal strict-JSON saves are now covered for non-finite in-memory history cleanup.
- Local API strict request JSON parsing is now covered for non-finite constants.
- WebView Network page static coverage is now covered for page placement, asset loading, script ordering, settings rows, contract summary wiring, and refresh-loop render wiring.
- mDNS discovery cleanup and async thread-start failures are now covered without requiring a real Zeroconf install or network scan.
- Coordinator cluster-log rotation failures are now covered so a stuck or locked rotation target does not remain invisible.
- Shared local-IP policy is now covered for RFC-1918 priority, invalid address filtering, and UDP fallback behavior.
- Coordinator shutdown failures are now covered for HTTP server teardown, mDNS cleanup, stuck stale-reaper joins, and final registry save failures.
- Network controller UI update failures are now covered for dispatcher fallback status, coordinator-button refresh, and coordinator notice widgets.
- Worker cluster-log thread start failures are now covered so diagnostics dispatch cannot interrupt worker control flow.
- Worker heartbeat progress sanitization is now covered for non-finite, over-100, and negative snapshot values.
- Network protocol numeric contract hardening is now covered for non-finite numeric strings and negative retry/size/timing values.
- Coordinator retry-hint fallback diagnostics are now covered when active-count lookup fails.
- In-flight registry numeric state hardening is now covered for bad estimated sizes and malformed worker throughput metrics.
- Coordinator claim size estimate guarding is now covered for malformed queue-record estimates.
- Process lifecycle shutdown cleanup diagnostics are now covered for taskbar reset, poll cancellation, and root quit failures.
- Status server stop diagnostics are now covered for shutdown and close failures.
- Status server strict JSON telemetry is now covered for nested `NaN`/`Infinity` values.
- Settings structured control diagnostics are now covered for encoder flag, audio codec, and auxiliary codec widget state failures.
- Worker source path-map entry diagnostics are now covered so one malformed mapping does not disappear silently while later valid mappings still load.
- Retry-hint policy diagnostics are now covered for invalid helper inputs without changing coordinator registry-failure fallback behavior.
- mDNS startup/cleanup visibility is now covered at warning level for coordinator advertisement startup failures, advertisement unregister/close failures, discovery close failures, and async discovery thread-start failures.
- Coordinator health fallback diagnostics are now covered so heartbeat timeout lookup failures do not disappear behind the health endpoint fallback.
- Worker hostname fallback diagnostics are now covered so network worker identity fallback is visible.
- Local IP fallback diagnostics are now covered for hostname lookup failure and UDP route detection failure.
- Coordinator reaper interval fallback diagnostics are now covered so stale-job reaper cadence fallback is visible when heartbeat-timeout lookup fails.
- Cluster-log size inspection diagnostics are now covered so failed size checks do not silently suppress rotation decisions.
- Coordinator invalid-request diagnostics are now covered for `/api/done`, `/api/heartbeat`, and `/api/log` invalid-body rejections without logging raw request bodies.
- Coordinator request-identifier diagnostics are now covered for rejected done/heartbeat identifiers and missing cluster-log event names.
- Coordinator cluster-log field sanitization diagnostics are now covered for stripped worker/job identifiers and truncated event/message fields.
- Worker heartbeat cleanup diagnostics are now covered so stuck heartbeat threads do not disappear silently after a bounded join.
- Worker heartbeat-start recovery is now covered so a claimed job is released if the heartbeat thread cannot start.
- Worker claim-handoff recovery is now covered so unexpected post-claim failures release the job instead of leaving it active until stale timeout.
- Worker claim-preparation recovery is now covered so malformed claimed response bodies and source path-map exceptions release the job immediately instead of leaving it claimed until stale timeout.
- Worker malformed-claim diagnostic bounding is now covered so long parse reasons do not flood warnings, cluster-log messages, or status text.
- Worker unstartable-claim release diagnostic bounding is now covered so long record-build/path-map reasons and release-POST failures do not flood failed-release warnings or operator status.
- Worker cluster-log failure diagnostic bounding is now covered for POST failure, daemon-thread startup failure, and safe-wrapper failure warnings.
- Worker status callback failure diagnostic bounding is now covered for long callback exception text.
- Worker reclaimed-abort scheduling diagnostic bounding is now covered for long UI callback queue exception text.
- Worker heartbeat-start diagnostic bounding is now covered so long thread-start failures do not flood logs, status text, or cluster-log messages.
- Worker claimed-job schedule diagnostic bounding is now covered so long UI scheduling failures do not flood logs or status text while release behavior is preserved.
- Worker claim-handoff diagnostic bounding is now covered so long unexpected post-claim failures do not flood logs or status text while release behavior is preserved.
- Worker claim-record diagnostic bounding is now covered so long QueueRecord build failures do not flood logs, cluster-log messages, or release reasons while release behavior is preserved.
- Worker done/release POST diagnostic bounding is now covered so long coordinator delivery failures do not flood worker logs or operator status while pending retry behavior is preserved.
- Worker poll-thread shutdown diagnostics are now covered so stuck worker poll threads do not disappear silently after a bounded shutdown join.
- Local coordinator runtime diagnostics are now covered so local claim/release registry-save failures and malformed local heartbeat progress do not break coordinator encode mode.
- Coordinator claim-rejection diagnostics are now covered so invalid `/api/claim` identity failures do not disappear behind 400 responses.
- Worker-board endpoint failure diagnostics are now covered so `/api/workers` snapshot failures produce a logged JSON error response.
- Worker-board runtime-stat sanitization is now covered so malformed active and idle worker metrics do not break the worker-board snapshot.
- Worker crash-recovery cluster-log guardrails are now covered for orphaned-job failed reports and pending done-report retry success paths.
- Worker crash-recovery safe-wrapper diagnostics are now covered for orphaned-job failed reports and pending done-report retry success paths.
- Worker crash-recovery POST diagnostic bounding is now covered so long pending done-retry and crash-failed report failures do not flood worker startup logs while retry state is preserved.
- Coordinator health probe detail normalization is now covered for unreachable coordinator and HTTP error responses.
- Worker auth probe detail normalization is now covered for 401, non-401 HTTP errors, and unreachable coordinators.
- HTTP JSON error-body preview bounding is now covered for long coordinator HTTP error responses.
- Worker poll auth-error classification is now covered so HTTP 500 bodies mentioning 401 do not emit false token-mismatch status or cluster events.
- Worker-board UI render isolation is now covered so dispatcher snapshot failures preserve existing rows and one failed row does not block later valid rows.
- Worker lifecycle controller guardrails are now covered for malformed completion events, completion-report build/submit failures, start-launch vs post-launch UI failures, and reclaimed-job abort fallback.
- Coordinator claim/done/heartbeat state-failure guardrails are now covered so registry exceptions produce logged structured HTTP failures and post-claim retry-policy failures release the claim immediately.
- Worker cluster-log control-flow isolation is now covered so cluster-log failures cannot block claim record release or remapped claim handoff.
- Coordinator cluster-log append guardrails are now covered so path resolution, line formatting, and unexpected `/api/log` append failures cannot unwind coordinator control flow.
- Worker shutdown/auth cluster-log guardrails are now covered so cluster-log failures cannot block active-job release during shutdown or kill the auth-error poll loop.
- Coordinator shutdown active-count guardrails are now covered so registry count failures cannot block shutdown teardown.
- Coordinator shutdown cluster-log guardrails are now covered so diagnostic failures cannot block HTTP server, mDNS, stale-reaper, or final registry cleanup.
- Coordinator claim-handoff cluster-log guardrails are now covered so diagnostic failures cannot strand a recorded claim before the worker receives its response.
- Coordinator reclaimed-heartbeat cluster-log guardrails are now covered so diagnostic failures cannot block the worker's `reclaimed` response.
- Coordinator terminal done cluster-log guardrails are now covered so completed/failed diagnostic failures cannot block final save, queue policy, or the worker `ok` response.
- Coordinator startup cluster-log guardrails are now covered so diagnostic failures do not abort a successfully started coordinator.
- Coordinator auth-token rotation cluster-log guardrails are now covered so diagnostic failures cannot block live token update or persistence.
- Coordinator HTTP startup cleanup is now covered so thread-start failures do not leave `_http_server` pointing at a non-serving server.
- Coordinator reaper startup cleanup is now covered so failures after HTTP startup tear down the partially-started coordinator before surfacing the startup error.
- Worker poll-thread startup guardrails are now covered so thread-start failures fail closed with URL-context diagnostics.
- mDNS startup diagnostics are now covered so missing/failed coordinator advertisement and async discovery thread-start failures leave warning-level diagnostics.
- Network tab probe thread-start diagnostics are now covered so failed UI background probes do not leave disabled buttons or stale status silently.
- Network tab clipboard diagnostics are now covered so failed Network tab copy/paste actions leave logs and visible status instead of escaping from callbacks.
- Network tab queue-refresh scheduling diagnostics are now covered so queue refresh UI recovery scheduling failures leave warnings and manual recovery guidance.
- mDNS registration failure cleanup is now covered so failed service registration clears partial Zeroconf state and leaves coordinator `_mdns` unset.
- Coordinator terminal done-report queue-removal logging is now covered for both Tk scheduling failure and successful scheduling, so the log no longer claims queue removal already happened before the UI callback runs.
- Worker heartbeat snapshot diagnostics are now covered so broken live-progress snapshots warn with job context while the heartbeat continues with bounded 0% progress.
- Worker accepted-report cleanup separation is now covered for done, clean release, and internal release paths so post-accept cleanup failures do not create duplicate pending done retries.
- Worker crash-recovery cleanup guardrails are now covered so cleanup failures after accepted crash-recovery reports do not bubble out of worker startup.
- Worker accepted-cleanup diagnostic accuracy is now covered so the accepted-report helper logs its contextual no-pending-retry warning when guarded worker-state cleanup returns failure.
- Worker crash-recovery state anomaly diagnostics are now covered so missing job ids and malformed pending done reports are visible before state cleanup or crash-failed fallback.
- Worker crash-state save diagnostics are now covered so failed worker-state writes warn locally, update operator status, and emit a best-effort cluster-log event.
- Pending done-report save diagnostics are now covered so failed retry payload writes warn locally, update operator status, and emit a best-effort cluster-log event.
- Pending retry log accuracy is now covered for completion, clean release, and internal release failure paths when retry-payload persistence fails.
- Coordinator in-flight save diagnostics are now covered for claim, worker release, and done-report save failures.
- Local coordinator in-flight save diagnostics are now covered for local claim and local release save failures.
- Missing local-completion save diagnostics are now covered for reclaimed/duplicate local completion save failures.
- Shutdown in-flight save diagnostics are now covered for final coordinator teardown save failures.
- Stale-reaper in-flight save diagnostics are now covered for periodic coordinator persistence failures.
- Stale-reclaim cluster-log guardrails are now covered so cluster-log failures do not skip stale-reaper persistence.
- Stale done/release report cluster-log guardrails are now covered so cluster-log failures do not block existing not-found or forbidden responses.
- Worker terminal-report log accuracy is now covered so done/release paths no longer claim coordinator acceptance when the report is pending retry.
- Worker internal-release log accuracy is now covered so failed local handoff release reports no longer hide whether the report was accepted or saved for retry.
- Worker cluster-log POST diagnostics are now covered so coordinator log delivery failures remain best-effort but visible in the local worker log.
- Coordinator cluster-log timestamp diagnostics are now covered so `/api/log` timestamp fallback failures do not disappear silently.
- Coordinator oversized-request response diagnostics are now covered so failed 413 send attempts do not disappear at DEBUG level.
- Coordinator malformed-length response diagnostics are now covered so failed malformed `Content-Length` 400 send attempts leave warning-level context.
- Coordinator body-read diagnostics are now covered so valid-length request body stream failures leave warning-level context before dispatch stops.
- Coordinator JSON response send diagnostics are now covered so broken client sockets during normal JSON responses leave warning-level context.
- Coordinator OPTIONS response send diagnostics are now covered so broken client sockets during preflight responses leave warning-level context.
- Worker claim-failure diagnostics are now covered so repeated poll failures leave one warning per distinct error without spamming normal logs, and long poll errors do not flood warning/debug logs or operator status.
- Worker heartbeat POST diagnostics are now covered so repeated heartbeat delivery failures leave one warning per distinct error without spamming normal logs, and long delivery errors do not flood warning/debug logs or operator status.
- Shared network diagnostic policy consolidation is now covered so worker diagnostics and Network tab operator failure paths use the same bounded preview helper.
- Network tab async UI handoff recovery is now covered so scheduling failures for coordinator/discovery/status/auth/firewall callbacks share one bounded helper and fallback callback path.
- Coordinator state-transition save-failure propagation is now covered so real in-flight registry atomic-write failures reach coordinator `inflight_save_failed` cluster diagnostics after accepted done reports.
- mDNS service-resolution diagnostics are now covered so individual advertised-service resolution failures warn while the scan continues.
- Firewall check exit-status diagnostics are now covered so a failed `netsh` check does not masquerade as a missing inbound rule.
- Firewall add-rule output diagnostics are now covered so failed add-rule attempts surface bounded `netsh` output instead of only a generic administrator hint.
- `test_network_local_ip`, `test_network_mdns`, `test_network_view_source_policy`, `test_network_coordinator_startup`, `test_network_worker_source_policy`, and `test_network_coordinator_source_policy` are green in the 243-test network discovery suite.
- Tauri close-readiness warning surfacing is now covered so the native unsafe-close confirmation includes bounded backend warning details instead of only the state/reason fields.
- Tauri route-contract startup diagnostics now include the expected `auth_required` value so auth drift is distinguishable from missing route drift.
- Tauri/WebView release-gate checks are green: `cargo check`, WebView static JavaScript syntax checks, focused Tauri/local API/API policy tests, and full desktop discovery at 984 tests.
- WebView command feedback now preserves bounded backend `warnings` and `errors` in both freshly appended command results and loaded `/api/commands` journal entries.
- Completed-row open and rename-apply success paths now pass the full backend command result into command history instead of dropping warning/error fields.
- Maintenance release/backfill dry-run detail panes now render backend warnings alongside errors.
- WebView command feedback checks are green: WebView static JavaScript syntax checks, focused local API/WebView/API policy tests, and full desktop discovery at 985 tests.
- Release/preview script gate consolidation is now covered: Tauri prereq and preview check-only paths resolve the backend Python runtime from the desktop or pipeline bundled locations, preflight the local API module with that runtime, and report the selected backend path.
- Bundled-runtime mDNS optional dependency handling is now covered so missing `zeroconf` leaves patchable module symbols and no longer fails release desktop unit tests.
- Structured encoding/audio settings reliability is now covered: the release reliability gate accepts guarded settings widget-state updates, custom raw video/audio modes remain editable only under the relevant custom choices, and backend preview/validation coverage verifies reconciliation for structured presets.
- Release tool/smoke gate readiness is now covered: bundled tool integration, temp-workspace end-to-end smoke, and the root release self-test pass without `-SkipToolIntegration` or `-SkipEndToEndSmoke`.
- Cluster-log open parity is now covered: facade diagnostics-open policy, WebView controls, command allowlist coverage, Tauri checker, and full desktop discovery remain green.
- WebView parity guidance is now covered: static WebView tests verify the queue summary panel and new inventory/report empty-state guidance hooks, and Tauri checker validates the updated JavaScript.
- WebView launch feedback coverage now verifies the inline command-result formatter, backend-data/request sections, and pending-publish drain detail panel.

The release/preview script gate chunk is substantially complete:

- Tauri prereq checking and preview check-only validation now agree on backend Python runtime discovery.
- Preview check-only validation now confirms `mediapipeline_desktop_app.local_api_main --help` before reporting success.
- Optional mDNS dependency handling now works under the bundled desktop Python runtime used by the release self-test.
- Focused Tauri shell tests, prereq script, preview check-only path, bundled/runtime mDNS tests, and full desktop discovery are green.
- The root release self-test now passes layout, parser, Python syntax, desktop unit tests, environment verifier, Tauri preview prerequisites, and reliability regression checks with tool/smoke skips after the structured settings gate fix.

The structured encoding/audio settings reliability chunk is complete:

- The stale direct-widget-call reliability assertion now recognizes the guarded `_configure_widget_state()` path used by the controller.
- Focused settings coverage verifies disabled raw controls for structured modes and enabled controls for `custom_legacy_flags` / `custom_codec_list`.
- Config preview coverage verifies custom raw values are preserved only in custom modes and structured choices still reconcile raw fields.
- Option-policy coverage verifies structured audio profiles warn when they replace a custom codec list.
- Reliability regression checks, release self-test with tool/smoke skips, and full desktop discovery are green at 989 tests.

The tool integration and end-to-end smoke release gate chunk is complete:

- Bundled FFmpeg/ffprobe/subtitle integration checks passed independently.
- Temp-workspace end-to-end smoke passed independently, including queue planning, deferred publish parking, pending publish drain, audio standardization, remux preservation, CSV rerun dry-run manifesting, and CPU fallback encode planning.
- The root release self-test passed without `-SkipToolIntegration` and without `-SkipEndToEndSmoke`.
- No processing-policy changes were needed.

The next chunk should be:

### Tauri Daily-Use Parity Gap Review And Small Fixes

Target files:

- `DesktopApp\mediapipeline_desktop_app\ui_web\static\index.html`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\*.js`
- `DesktopApp\mediapipeline_desktop_app\api\contract_read.py`
- `DesktopApp\mediapipeline_desktop_app\api\contract_command.py`
- `DesktopApp\tests\test_application_facade.py`
- `DesktopApp\tests\test_tauri_shell_scaffold.py`
- `Docs\REMEDIATION_CHANGELOG.md`

Work:

- Compare the current Tk daily-use tabs against the WebView shell and list remaining parity gaps that block realistic Tauri preview usage.
- Fix only small read-only or backend-command-backed gaps that already have local API authority.
- Avoid adding split-brain WebView controls for coordinator/worker runtime mutation until backend lifecycle ownership is explicitly designed.
- Preserve the existing API route contract and add routes only when the WebView cannot consume an existing backend-owned query/command.
- Re-run WebView static coverage, Tauri source coverage, the Tauri checker, and full desktop discovery after changes.

Expected risk:

Low to medium. Small WebView parity fixes are low risk when they reuse existing backend contracts, but adding new routes or mutation controls can create split-brain behavior if not kept behind the facade.

Why this is next:

- The release gate is now structurally green with tool integration and end-to-end smoke enabled.
- The remaining V5 transition risk is whether the Tauri/WebView shell is useful enough for daily preview testing without relying on Tk-only screens.
- This keeps the work grounded in operator-visible parity while still avoiding a full GUI rewrite or risky backend behavior changes.

The queue excluded-row contract chunk is complete:

- The PowerShell queue snapshot now persists a bounded `excluded_rows` collection for already-processed source candidates that are filtered before runnable rows.
- The queue snapshot schema and Python contract parser now accept additive excluded-row count, limit, truncation, and row-detail fields.
- `/api/queue` now exposes normalized excluded-row detail, reason counts, media-type counts, and row-level availability while preserving old snapshot compatibility.
- The WebView Queue page now renders an Excluded Source Rows panel so the operator can distinguish true empty queues from completed-history filtering without opening raw JSON.
- Queue processing, completed-history logic, dry-run launch behavior, Tk fallback, and media policy were not changed.

The queue excluded-row open and blocked-row clarity chunk is complete:

- `/api/queue/open` now accepts an additive `row_scope` of `runnable` or `excluded` while preserving `runnable` as the default.
- The WebView Queue page now supports selecting excluded source rows and opening their backend-selected source file, source folder, or source root.
- Queue preview metadata now separates visible blocked rows/reasons from pre-runnable excluded rows/reasons.
- The Local API contract view now displays allowed row scopes so route-scope restrictions are visible in the WebView.
- Queue mutation, completed reconciliation, rerun, and media policy remain backend-owned and unchanged.

The queue deterministic preflight blocked-code chunk is complete:

- The queue snapshot now mirrors cheap terminal `Process-File` preflight skip decisions for bad extensions, permanent/operator-required failure markers, unreliable TV parse, and already-processed check exceptions.
- Queue snapshot rows now carry additive `blocked_reason_code` values alongside free-form `blocked_reason` text.
- `/api/queue` now exposes aggregate `blocked_reason_code_counts`, and the WebView Queue Breakdown and row details render those codes.
- Slower runtime-only checks such as file stability and output path capability remain runtime-only to avoid blocking read-only preview or probing destination paths during WebView refresh.

The queue deferred runtime-check visibility chunk is complete:

- Queue snapshot rows now explicitly report deferred runtime checks for `source_stability` and `output_path_capability` on unblocked rows.
- `/api/queue` exposes `runtime_check_deferred_count` and `runtime_check_code_counts`.
- WebView Queue summary, readiness, breakdown, and row detail now explain that source stability and output path capability are checked only when processing starts.
- No preview path calls `Test-FileStable` or `Test-OutputPathCapability`; slow disks, half-copied files, and network shares are not probed during refresh.

The queue runtime outcome history chunk is complete:

- Existing `job_completed` and `failure_recorded` events already carry enough structured data for read-only queue correlation: source path, status, stage, route, error code, reason, publish state/mode, and output path.
- `/api/queue` now reads a bounded backend-validated event tail and correlates visible queue rows by exact normalized source path only.
- Queue preview metadata now exposes runtime outcome source, event count, exact-match count, status counts, event-type counts, error-code counts, and freshness counts.
- Queue rows now expose last runtime outcome status, event type, stage, route, error code, reason, publish state/mode, output path, and freshness labels.
- WebView Queue now has a Runtime Outcome History panel and selected-row detail fields so recent `SOURCE_STILL_WRITING`, output-path, subtitle, publish, and other runtime failures are visible without manual JSONL inspection.
- Recent failed/skipped runtime history is surfaced as `Recent runtime failure`; stale history remains visible but clearly labeled as context only.
- Queue mutation, launch, completed reconciliation, rerun, pending publish, Tk fallback, pipeline event writing, and media policy remain unchanged.

The completed runtime outcome history follow-through chunk is complete:

- `/api/completed` now reads a bounded backend-validated event tail and correlates completed manifest rows by exact source path first, then exact output path when event output data exists.
- Completed preview metadata now exposes runtime outcome source, event count, exact-match count, status counts, event-type counts, error-code counts, and freshness counts.
- Completed rows now expose last runtime outcome status, event type, stage, route, error code, reason, publish state/mode, output path, match basis, and freshness labels.
- WebView Completed now has a Runtime Outcome History panel and selected-row detail fields so recent publish, rerun, and runtime conflicts are visible without manual JSONL inspection.
- Recent failed/skipped runtime history is surfaced as `Recent runtime conflict`; stale history remains visible but clearly labeled as context only.
- Completed repair, reconcile, rerun, cleanup, pipeline event writing, Tk fallback, and media policy remain unchanged.

The runtime outcome helper consolidation chunk is complete:

- Added `application/runtime_outcomes.py` for shared runtime event normalization.
- Moved exact source identity, event data extraction, bool/int coercion, status normalization, freshness labeling, and source-path indexing out of Queue policy.
- Queue policy now keeps only queue-specific runtime outcome application and operator guidance.
- Completed policy now imports the shared helper directly instead of depending on Queue policy.
- Added fixture coverage for representative `job_completed` and `failure_recorded` event shapes, including operator-required failures and `data.source_path` fallback.
- No matching behavior was expanded beyond exact source/output identity.

The settings remaining structured builders review chunk is complete:

- Added schema labels/help for existing PowerShell config keys that were previously visible mostly as raw settings: `ValidExtensions`, `EnableIntegrityCheck`, `CreateTVSubfolder`, `RobocopyFlags`, and `LogRetentionDays`.
- Extended the WebView file-safety/publish builder with existing discovery, transfer, integrity, TV folder layout, and disk-estimate controls.
- Extended the WebView runtime builder with log-retention control.
- Added backend validation for `ValidExtensions` and `RobocopyFlags` list shape and switch/extension syntax.
- Added backend risk-preview warnings for disabled stability checks, disabled integrity checks, partial-download extensions, high robocopy thread counts, and low output-size estimate multipliers.
- Kept source deletion unexposed in the WebView builder; source mutation remains available only through explicit backend-recognized settings and is still flagged as high risk.
- No queue, process, FFmpeg, subtitle, audio, publish, Tk fallback, or media-policy behavior changed.

The next chunk should be:

### Settings / Launch Preflight Follow-Through

Target files:

- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\launchView.js`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\settingsView.js`
- `DesktopApp\mediapipeline_desktop_app\application\facade_process_*.py`
- `DesktopApp\mediapipeline_desktop_app\application\facade_settings*.py`
- `DesktopApp\tests\test_application_facade.py`
- `DesktopApp\tests\test_facade_process_*`
- `Docs\architecture\TAURI_WEBVIEW_PARITY_MATRIX.md`
- `Docs\REMEDIATION_CHANGELOG.md`

Work:

- Surface the backend risk-preview output more directly before launch starts so operators can connect settings risk to launch readiness.
- Improve WebView launch preflight guidance for disabled stability/integrity checks, deferred publish, strict/off size guard, no-audio policy, and system-tool fallback using existing settings/snapshot data.
- Do not add new launch mutation routes and do not change process launch policy.

Expected risk:

Low to medium. Launch preflight text is read-only and should reuse existing backend contracts, but it must not imply that WebView owns scheduling, queue mutation, or media policy.

The Settings / Launch Preflight follow-through chunk is complete:

- `/api/settings/workspace` now includes a backend-authored `settings_current_risk_summary.v1` payload derived from the same risk policy used for settings patch preview.
- Saved path roots are intentionally filtered out of current-risk output so normal Source/Output/Scratch locations are not treated as warnings just because they are configured.
- WebView pipeline and CSV rerun preflight summaries now echo saved-settings risk, settings validation warnings/errors, deferred publish, stability/integrity checks, size-guard mode, output container, no-audio policy, and PATH tool fallback before command submission.
- WebView refresh now rerenders Launch preflight text after settings workspace data loads, so saved-settings risk is visible without manually changing Launch fields.
- WebView Launch readiness now includes saved-settings posture, and pipeline/CSV rerun preflights now classify the saved settings posture as ready, review, or blocked with explicit start guidance.
- No launch acceptance/rejection, schedule handling, process lifecycle, queue mutation, Tk fallback, or media policy behavior changed.

The next chunk should be:

### WebView Pending Publish / Diagnostics Real-Media Validation Follow-Through

Target files:

- `DesktopApp\mediapipeline_desktop_app\application\facade_pending*.py`
- `DesktopApp\mediapipeline_desktop_app\application\facade_diagnostics*.py`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\pendingPublishView.js`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\diagnostics*.js`
- `DesktopApp\tests\test_application_facade.py`
- `DesktopApp\tests\test_tauri_shell_scaffold.py`
- `Docs\architecture\TAURI_WEBVIEW_PARITY_MATRIX.md`
- `Docs\REMEDIATION_CHANGELOG.md`

Work:

- Use existing backend-owned pending publish and diagnostics payloads to improve partial-copy, malformed-manifest, missing-sidecar, and stale-state explanations where real-media testing shows ambiguity.
- Keep pending publish mutation limited to existing backend-owned drain/start/open commands.
- Avoid adding repair/reconcile controls until command contracts and rollback semantics are explicit.

Expected risk:

Low to medium. Read-only operator guidance is safe, but pending publish is data-safety critical and must not gain frontend-owned filesystem mutation or speculative repair behavior.

The WebView Pending Publish diagnostics follow-through chunk is complete:

- `/api/pending-publish` now includes backend-authored row diagnostics: diagnostic status, severity, drain recommendation, operator guidance, available open targets, and recommended open targets.
- Aggregate diagnostic status/severity/open-target counts are included in the pending publish preview so the WebView can render risk without inventing row classification logic.
- Legacy manifest row states `unreadable` and `invalid_contract` are normalized into operator-facing `unreadable_manifest` and `invalid_manifest` diagnostics.
- WebView Pending Publish readiness, risk breakdown, filtering, row severity, and selected-row detail now consume backend-authored diagnostics.
- `/api/pending-publish` now also includes backend-authored recovery classes/actions/evidence fields plus an aggregate recovery summary so drain, rerun, and manual-review decisions are less dependent on frontend inference.
- `/api/diagnostics/state-summary` now includes recovery-stage and unsafe-if-ignored fields so malformed/stale artifacts explain their operational consequence before drain, rerun, cleanup, or shutdown decisions.
- WebView Pending Publish and Diagnostics render these recovery fields while preserving read-only frontend boundaries.
- Existing backend-owned drain/open commands remain the only pending publish mutations; no repair/reconcile controls were added.

The next chunk should be:

### WebView Diagnostics Artifact Drilldown And Pending Cross-Links

Target files:

- `DesktopApp\mediapipeline_desktop_app\application\facade_diagnostics*.py`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\diagnostics*.js`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\pendingPublishView.js`
- `DesktopApp\tests\test_application_facade.py`
- `DesktopApp\tests\test_tauri_shell_scaffold.py`
- `Docs\architecture\TAURI_WEBVIEW_PARITY_MATRIX.md`
- `Docs\REMEDIATION_CHANGELOG.md`

Work:

- Improve cross-link guidance from pending publish diagnostics to existing backend-allowlisted Diagnostics state-summary/tail/open targets.
- Keep all file reads and opens behind backend allowlists.
- Do not add arbitrary path tailing, pending repair, or manifest rewrite controls.

Expected risk:

Low. This should remain read-only and should reuse existing Diagnostics allowlists and command history.

The WebView Diagnostics artifact drilldown and Pending cross-link chunk is complete:

- Pending Publish now has a Diagnostics Cross-Links panel that maps selected-row backend diagnostics to existing backend-allowlisted Diagnostics open/tail actions.
- Missing payload, missing sidecar, row error, duplicate target, unreadable/invalid manifest, orphan payload, and ready rows get targeted guidance without adding repair or arbitrary path access.
- Diagnostics artifact drilldown now treats Pending Publish clues such as orphan payloads, missing sidecars, unreadable manifests, invalid manifests, deferred publish, and drains as Pending Publish + Last Stderr next-step hints.
- All reads/opens remain behind `/api/diagnostics/open` and `/api/diagnostics/tail`; folder targets remain open-only and file tails remain bounded.
- No pending publish drain behavior, manifest parsing, repair/reconcile workflow, Tk fallback, or media policy changed.

The next chunk should be:

### WebView Queue / Completed / Pending Cross-Page Operator Context

Target files:

- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\queueView.js`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\completedView.js`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\pendingPublishView.js`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\diagnostics*.js`
- `DesktopApp\tests\test_application_facade.py`
- `DesktopApp\tests\test_tauri_shell_scaffold.py`
- `Docs\architecture\TAURI_WEBVIEW_PARITY_MATRIX.md`
- `Docs\REMEDIATION_CHANGELOG.md`

Work:

- Add read-only cross-page context and operator guidance where Queue, Completed, Pending Publish, and Diagnostics already expose the same source/output/publish state.
- Keep all cross-page actions either read-only navigation or backend-owned open/tail commands.
- Do not add queue mutation, completed repair, pending repair, rerun/export controls, or media-policy changes.

Expected risk:

Low to medium. Cross-page context can improve operator trust, but avoid duplicating backend ownership rules or creating stale frontend-only state.

The WebView Queue / Completed / Pending cross-page operator context chunk is complete:

- Added a Home Cross-Page Context panel that summarizes already-loaded Queue, Completed, Pending Publish, Diagnostics, and runtime-history payloads.
- Added exact-match checks for queued sources already present in Completed source history, Pending destinations already present in Completed outputs, and Pending sources still visible in Queue.
- Added read-only page navigation buttons from the Home context panel to Queue, Completed, Pending Publish, and Diagnostics.
- Extracted page switching into a shared `showPage()` helper so normal nav and cross-page context nav use the same UI-only path.
- No queue mutation, completed repair, pending repair, rerun/export, drain, filesystem mutation, Tk fallback, backend route, or media-policy behavior changed.

The next chunk should be:

### WebView Rename Daily-Use Parity Polish

Target files:

- `DesktopApp\mediapipeline_desktop_app\application\facade_rename*.py`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\rename*.js`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\index.html`
- `DesktopApp\tests\test_application_facade.py`
- `DesktopApp\tests\test_rename*`
- `Docs\architecture\TAURI_WEBVIEW_PARITY_MATRIX.md`
- `Docs\REMEDIATION_CHANGELOG.md`

Work:

- Improve WebView rename bulk-edit visibility and confidence explanations for TV/movie batches using existing backend preview/apply contracts.
- Keep filesystem mutation exclusively behind `/api/rename/apply`.
- Do not add frontend-only rename rules that diverge from backend preview.

Expected risk:

Medium. Rename is operator-visible filesystem mutation, so polishing can be useful, but every mutation path must remain backend-owned and selected-source scoped.

The WebView Rename Daily-Use Parity Polish chunk is complete:

- `/api/rename/preview` now returns additive aggregate counts for confidence, preview source, and change kind.
- The WebView Rename page now includes a Review Board that summarizes preview-wide trust signals, status mix, duplicate destinations, sidecar moves, force-pipeline rows, overrides, TV range, and movie scrub guidance before apply.
- Rename row hover text now exposes status, confidence, preview source, and change kind for quick inspection.
- Rename warnings, preview/apply behavior, selected-source scoping, confirmation, apply locking, Tk fallback, and media policy remain unchanged.

The next chunk should be:

### WebView Rename Bulk Editing Tools

Target files:

- `DesktopApp\mediapipeline_desktop_app\application\facade_rename*.py`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\rename*.js`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\index.html`
- `DesktopApp\tests\test_application_facade.py`
- `DesktopApp\tests\test_facade_rename_policy.py`
- `Docs\architecture\TAURI_WEBVIEW_PARITY_MATRIX.md`
- `Docs\REMEDIATION_CHANGELOG.md`

Work:

- Add richer bulk final-name editing through explicit backend-preview-compatible override contracts only.
- Keep TV/movie scrub inference in backend-owned rename planning.
- Avoid frontend-only rename rules, arbitrary path mutation, or new apply semantics.

Expected risk:

Medium. Bulk editing directly influences filesystem mutation plans, so any UI convenience must remain transparent, reversible via existing undo manifests, and validated by backend preview before apply.

The WebView Rename Bulk Editing Tools chunk is complete:

- Added a Bulk Final-Name Overrides panel with checked-row, selected-row, and all-applicable preview scopes.
- Added scoped find/replace, prefix, suffix, Use Pipeline Names, Force Scope Through Pipeline, Clear Scope Force, and Clear Scope Overrides controls.
- Bulk final-name edits preserve filename extensions, reject generated path separators, and immediately rebuild backend preview before any apply.
- No frontend filesystem mutation, rename apply semantics, Tk fallback, queue behavior, or media policy changed.

The next chunk should be:

### WebView Rename Template Preset Review

Target files:

- `DesktopApp\mediapipeline_desktop_app\service_rename*.py`
- `DesktopApp\mediapipeline_desktop_app\application\facade_rename*.py`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\rename*.js`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\index.html`
- `DesktopApp\tests\test_application_facade.py`
- `DesktopApp\tests\test_facade_rename_policy.py`
- `Docs\architecture\TAURI_WEBVIEW_PARITY_MATRIX.md`
- `Docs\REMEDIATION_CHANGELOG.md`

Work:

- Review whether the current TV/movie naming templates need backend-owned preset names beyond the existing show/season/start/movie fields and manual override map.
- If useful, expose preset intent through backend preview rather than duplicating naming inference in the frontend.
- Keep apply unchanged and selected-source scoped.

Expected risk:

Medium. Template presets can accidentally become a second rename engine if implemented in the frontend. Prefer backend-owned preset interpretation or defer until real operator usage proves the need.

The WebView Rename Template Preset Review chunk is complete:

- Added a backend-owned rename template catalog with TV standard, TV no-episode-title, and movie standard entries.
- Added additive `template_preset`, `active_template`, and `template_catalog` fields to the rename preview/apply planning contract.
- Added backend planning behavior for TV no-episode-title so manual, auto, and pipeline TV preview names can produce `Show - SxxEyy.ext`.
- Added a WebView Template selector and Review Board/detail visibility for the active backend template.
- Default rename behavior remains unchanged when no template is selected.

The next chunk should be:

### Queue / Completed / Pending Real-Media Validation Polish

Target files:

- `DesktopApp\mediapipeline_desktop_app\application\facade_queue*.py`
- `DesktopApp\mediapipeline_desktop_app\application\facade_completed*.py`
- `DesktopApp\mediapipeline_desktop_app\application\facade_pending_publish*.py`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\queueView.js`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\completedView.js`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\pendingPublishView.js`
- `DesktopApp\tests\test_application_facade.py`
- `Docs\architecture\TAURI_WEBVIEW_PARITY_MATRIX.md`
- `Docs\REMEDIATION_CHANGELOG.md`

Work:

- Use the existing read-only queue/completed/pending contracts to improve daily-driver trust around real-media validation findings.
- Prefer clearer operator guidance, malformed-state explanations, and cross-page consistency signals over new mutation controls.
- Do not add repair, reconcile, rerun, drain, or media-policy changes unless a backend-owned command contract already exists.

Expected risk:

Low to medium. This should mostly be read-only WebView/operator-feedback polish over existing backend payloads. Avoid creating frontend-owned interpretation that conflicts with backend status fields.

The WebView Reports/Audit operator investigation chunk is complete:

- Added a read-only Reports Investigation Checklist that combines report-path availability, report-root availability, snapshot warnings, failure preview state, audit preview state, and a concrete operator investigation order.
- Added a Failure Review Board that summarizes classification, stage, error-code, media counts, prioritized rows to inspect, operator/permanent failure posture, transient retry posture, and safe next actions.
- Added an Audit Review Board that summarizes bucket, priority, issue-code, media counts, redownload/rerun/high-priority counts, duplicate groups, prioritized rows to inspect, and CSV rerun guidance.
- Kept Reports as a read-only triage surface. No rerun/export/repair/delete controls, frontend filesystem mutation, audit launch behavior, CSV rerun behavior, Tk fallback, or media policy changed.

The next chunk should be:

### WebView Schedule And Launch Timing Trust

Target files:

- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\scheduleView.js`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\launch*.js`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\index.html`
- `DesktopApp\tests\test_application_facade.py`
- `Docs\architecture\TAURI_WEBVIEW_PARITY_MATRIX.md`
- `Docs\REMEDIATION_CHANGELOG.md`

Work:

- Improve read-only schedule and launch timing trust with clearer outside-window, override, continuous-mode, and schedule-stop limitation explanations.
- Historical constraint at the time: keep schedule editing out of WebView until a backend-owned save contract exists. Superseded by the backend-owned Schedule Editor contract added later; direct frontend state writes remain prohibited.
- Do not change backend launch gating, schedule enforcement, process lifecycle, or media policy.

Expected risk:

Low. This should be read-only operator guidance over existing schedule/launch payloads.

The WebView Schedule and Launch Timing Trust chunk is complete:

- Added a Schedule Timing Trust panel that evaluates the currently selected pipeline mode and schedule override against the loaded schedule payload.
- Added a Launch Timing Trust panel that combines selected mode/override, close-readiness active-work state, saved-settings posture, and schedule timing guidance.
- Re-rendered timing guidance when Launch mode or schedule override changes so preflight text and trust text stay aligned.
- Kept backend launch gating, continuous-mode blocking, schedule enforcement, process lifecycle, Tk fallback, and media policy unchanged.

The next chunk should be:

### WebView Reports-To-Launch Action Handoff

Target files:

- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\reportsView.js`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\launchView.js`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\crossPageContextView.js`
- `DesktopApp\tests\test_application_facade.py`
- `Docs\architecture\TAURI_WEBVIEW_PARITY_MATRIX.md`
- `Docs\REMEDIATION_CHANGELOG.md`

Work:

- Add read-only navigation/context hints from audit/rerun recommendations to existing Launch CSV Rerun controls without auto-filling or submitting mutation commands.
- Keep CSV path selection and rerun start backend-owned.
- Do not add report export, CSV mutation, queue mutation, or media-policy changes.

Expected risk:

Low to medium. This should improve operator flow, but must not turn Reports into a frontend rerun engine.

The WebView Reports-to-Launch Handoff chunk is complete:

- Added a Reports Launch Handoff panel that lists candidate latest priority/audit CSV paths, selected audit-row context, rerun/redownload/failure-review posture, and safe next actions.
- Added Go To CSV Rerun, Go To Audit Launch, and Go To Diagnostics buttons.
- The Launch buttons only navigate/focus existing Launch controls. They do not fill CSV path fields, submit rerun/audit commands, copy files, export reports, repair records, or mutate media.
- Kept CSV rerun start, audit start, diagnostics open/tail, report parsing, Tk fallback, and media policy unchanged.

The next chunk should be:

### WebView Maintenance Release Confidence Polish

Target files:

- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\maintenanceView.js`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\index.html`
- `DesktopApp\tests\test_application_facade.py`
- `Docs\architecture\TAURI_WEBVIEW_PARITY_MATRIX.md`
- `Docs\REMEDIATION_CHANGELOG.md`

Work:

- Improve release/backfill dry-run confidence summaries, option review, and diagnostics handoff using existing backend dry-run results.
- Keep WebView Maintenance limited to dry-run commands.
- Do not add real release package writes, manifest rewrites, repair commands, or frontend filesystem mutation.

Expected risk:

Low. This should remain dry-run/result-presentation polish over existing backend commands.

The WebView Maintenance Release Confidence chunk is complete:

- Added a Maintenance Dry-Run Confidence panel that combines health readiness, required blockers, optional warnings, latest maintenance dry-run outcome, and current release dry-run options.
- Added warnings for disabled verify, keeping personal config, and optional tool/doc payload expansion.
- Re-rendered confidence as release dry-run options change and when maintenance command history updates.
- Kept WebView Maintenance dry-run only. No real release packaging, manifest rewrite, repair command, file mutation, Tk fallback, or media policy changed.

The next chunk should be:

### WebView Settings Remaining Raw-Key Triage

Target files:

- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\settings*.js`
- `DesktopApp\mediapipeline_desktop_app\application\settings_*`
- `DesktopApp\tests\test_application_facade.py`
- `Docs\architecture\TAURI_WEBVIEW_PARITY_MATRIX.md`
- `Docs\REMEDIATION_CHANGELOG.md`

Work:

- Identify high-impact settings still only visible in raw Config Values and either add structured display/builders or explicitly mark them as advanced/raw.
- Keep patch preview/save backend-owned.
- Do not change saved settings semantics or media routing policy.

Expected risk:

Medium. Settings affect processing behavior, so keep this to structured visibility and existing patch contracts unless a backend policy defect is proven.

The WebView Settings Remaining Raw-Key / Safety Lock chunk is complete:

- Added a read-only Settings Raw-Key Triage panel that classifies loaded config keys as structured-builder, advanced raw, known raw, or unknown raw.
- Added selectable raw-key rows and a detail pane that shows current value, backend field definition, impact note, and safe next step.
- Added a read-only Settings Safety Lock Review panel for source deletion, skipped stability checks, disabled integrity checks, no-audio output, PATH fallback, remote cleanup, one-pass reprocess, legacy video flags, and worker overrides.
- Kept high-risk settings out of one-click WebView toggles; changes still require Changes JSON plus backend Preview/Save.
- Kept PSD1 serialization, backend validation, Tk fallback, launch acceptance, and media policy unchanged.

The next chunk should be:

### WebView Queue / Completed / Pending Real-Media Review Polish

Target files:

- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\queueView.js`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\completedView.js`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\pendingPublishView.js`
- `DesktopApp\tests\test_application_facade.py`
- `Docs\architecture\TAURI_WEBVIEW_PARITY_MATRIX.md`
- `Docs\REMEDIATION_CHANGELOG.md`

Work:

- Improve dense row detail and status summaries for real-media validation, especially oversized outputs, pending-publish rows, stale manifests, and safe next actions.
- Prefer backend-authored fields where available and keep WebView logic presentation-only.
- Do not add repair, rerun, publish, delete, rewrite, or arbitrary filesystem mutation controls.

Expected risk:

Low to medium. These pages are operator trust-critical, but the next pass should stay read-only and avoid media policy changes.

The WebView Completed Size-Growth Review chunk is complete:

- Added a read-only Completed Size Growth Review board.
- The board lists rows with output growth, growth over +5%, and missing source/output size comparisons.
- Rows are sorted with highest-risk growth first and selecting one reuses the existing Completed detail, diagnostics cross-links, and backend-allowlisted open actions.
- Kept rerun, repair, delete, reconcile, publish, file mutation, size guard policy, and media routing unchanged.

The next chunk should be:

### WebView Pending Publish Drain Evidence Polish

Target files:

- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\pendingPublishView.js`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\index.html`
- `DesktopApp\tests\test_application_facade.py`
- `Docs\architecture\TAURI_WEBVIEW_PARITY_MATRIX.md`
- `Docs\REMEDIATION_CHANGELOG.md`

Work:

- Add a focused read-only evidence board for rows that should not drain, missing payloads, orphan payloads, invalid manifests, and sidecar mismatches.
- Reuse existing backend-authored pending row diagnostics and recovery-plan dry-run data.
- Do not add repair, drain bypass, delete, rewrite, publish, or arbitrary filesystem controls.

Expected risk:

Low to medium. Pending publish is data-safety critical, so the next pass should remain presentation-only over backend-owned row contracts.

The WebView Pending Publish Drain Evidence chunk is complete:

- Added a read-only Drain Evidence Board for do-not-drain, diagnostic-error, missing-payload, invalid/unreadable manifest, orphan-payload, missing-sidecar, and review rows.
- The board sorts highest-risk rows first and shows recommendation, evidence summary, row identity, and safe next action.
- Selecting a board row reuses existing Pending row details, backend diagnostics cross-links, backend-allowlisted open actions, and recovery-plan dry runs.
- Kept Publish Parked Outputs, recovery planning, open actions, validation, repair, delete, rewrite, move, publish, Tk fallback, and media policy unchanged.

The next chunk should be:

### WebView Pending Publish Recovery Plan Result Drilldown

Target files:

- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\pendingPublishView.js`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\index.html`
- `DesktopApp\tests\test_application_facade.py`
- `Docs\architecture\TAURI_WEBVIEW_PARITY_MATRIX.md`
- `Docs\REMEDIATION_CHANGELOG.md`

Work:

- Add a selected dry-run plan row/detail view for backend-authored recovery plan results.
- Keep it dry-run only, with no repair, drain bypass, delete, rewrite, move, publish, or arbitrary filesystem controls.

Expected risk:

Low. Recovery-plan result drilldown should remain presentation-only over existing backend dry-run payloads.

The WebView Pending Publish Recovery Plan Result Drilldown chunk is complete:

- Added a selectable read-only recovery-plan row table beneath the existing Recovery Dry Run controls.
- Added selected-plan-row detail showing row key, diagnostic severity, drain recommendation, trust state, recovery class, planned action, dry-run guardrails, unsafe-if-ignored text, recommended targets, affected paths, evidence fields, and proof lines.
- Kept the existing `/api/pending-publish/recovery-plan` command as the only plan source and preserved its dry-run-only/would-not-mutate contract.
- Kept Publish Parked Outputs, open actions, validation, repair, delete, rewrite, move, publish, Tk fallback, and media policy unchanged.

The next chunk should be:

### WebView Pending Publish Command Result And Drain Summary Correlation

Target files:

- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\pendingPublishView.js`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\commandHistory.js`
- `DesktopApp\tests\test_application_facade.py`
- `Docs\architecture\TAURI_WEBVIEW_PARITY_MATRIX.md`
- `Docs\REMEDIATION_CHANGELOG.md`

Work:

- Correlate the latest pending-publish drain command result, durable drain summary, and current pending rows into one read-only explanation.
- Make incomplete drains, summary read failures, and remaining manifests easier to interpret before another drain attempt.
- Do not add repair, drain bypass, delete, rewrite, move, publish, or arbitrary filesystem controls.

Expected risk:

Low to medium. The correlation should remain presentation-only, but it sits next to the destructive backend-owned Publish Parked Outputs command and must avoid implying frontend repair authority.

The WebView Pending Publish Command Result And Drain Summary Correlation chunk is complete:

- Added a read-only Drain Correlation panel that combines current parked row counts, ready/review/do-not-drain posture, latest drain command, command mode, durable drain summary counts, and recent backend drain events.
- The panel explains blocked/failed commands, unreadable summaries, stopped/error summaries, remaining parked rows after a drain, empty pending rows with successful backend evidence, and first-run/no-evidence states.
- Pending drain command history now includes backend result counts such as attempted, succeeded, already-published, errors, and remaining when present.
- Kept Publish Parked Outputs, recovery planning, open actions, validation, repair, delete, rewrite, move, publish, Tk fallback, and media policy unchanged.

The next chunk should be:

### WebView Completed-To-Pending Output Proof Cross-Check

Target files:

- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\completedView.js`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\pendingPublishView.js`
- `DesktopApp\tests\test_application_facade.py`
- `Docs\architecture\TAURI_WEBVIEW_PARITY_MATRIX.md`
- `Docs\REMEDIATION_CHANGELOG.md`

Work:

- Improve read-only operator guidance when a completed output, pending destination, or recently drained payload appears to overlap.
- Surface the safest proof order: Completed manifest, output path, pending state, drain summary, Run Logs, Last Stderr.
- Do not add repair, rerun, delete, reconcile, publish, or arbitrary filesystem mutation controls.

Expected risk:

Low. This should remain presentation-only over already-loaded Completed and Pending Publish payloads.

The WebView Completed-To-Pending Output Proof Cross-Check chunk is complete:

- Added a read-only Completed Output Proof Cross-Check panel that correlates loaded Completed rows with current Pending Publish rows and the latest durable pending drain summary.
- Exact full-path matches are surfaced as higher-confidence overlaps/proof. Same-leaf matches are explicitly labeled review-only so duplicate titles or different folders do not become false proof.
- The panel explains the safe proof order: Completed manifest, output/source path, Pending Publish state, durable drain summary, Run Logs, and Last Stderr.
- Pending Publish refresh now repaints the Completed proof panel with the latest pending payload, while Completed remains safe when pending data has not loaded yet.
- Kept repair, rerun, delete, reconcile, publish, arbitrary path opening, Tk fallback, and media policy unchanged.

The next chunk should be:

### WebView Queue/Completed/Pending Conflict Board

Target files:

- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\queueView.js`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\completedView.js`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\pendingPublishView.js`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\crossPageContextView.js`
- `DesktopApp\tests\test_application_facade.py`

Work:

- Consolidate already-loaded queue/completed/pending conflict hints into one operator-focused board.
- Keep all comparisons read-only and exact-path-first.
- Make same-leaf/title-only matches advisory, not proof.
- Do not add queue mutation, cleanup, rerun, repair, publish, or path-opening shortcuts.

Expected risk:

Low to medium. The value is high for operator trust, but the display must avoid implying that advisory duplicate-title matches are safe mutation targets.

The WebView Queue/Completed/Pending Conflict Board chunk is complete:

- Added a Home Cross-Page Conflict Board table under the existing Cross-Page Context panel.
- Correlates already-loaded Queue, Completed, and Pending Publish payloads without backend route changes.
- Exact path matches cover queued source in Completed history, queued source in Pending Publish, completed output in Pending destination, and queued runtime output in Pending destination.
- Same-leaf matches are explicitly advisory duplicate-title/path-review hints, not proof.
- Selecting a conflict row only navigates/selects an owning page row for review. It does not open paths, launch, repair, rerun, drain, reconcile, delete, or rewrite files.
- Kept Tk fallback, backend command ownership, pending publish safety, and media policy unchanged.

The next chunk should be:

### WebView Diagnostics And Conflict Handoff Polish

Target files:

- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\diagnosticsView.js`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\crossPageContextView.js`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\diagnosticsBridge.js`
- `DesktopApp\tests\test_application_facade.py`

Work:

- Make conflict-board and selected-row diagnostics handoffs easier to follow from Diagnostics.
- Keep diagnostics open/tail actions backend-allowlisted.
- Do not add arbitrary file paths, repair controls, lifecycle controls, queue mutation, rerun, drain, or media-policy changes.

Expected risk:

Low. This should be presentation-only over existing diagnostics bridge data and backend allowlisted diagnostics commands.

The WebView Diagnostics And Conflict Handoff Polish chunk is complete:

- Diagnostics Investigation Trail now includes Cross-Page Conflict Board counts and top conflict handoffs.
- Exact-path conflict rows and advisory filename-only rows are labeled differently in Diagnostics so duplicate-title hints are not treated as proof.
- Diagnostics suggested actions now include existing backend-allowlisted Last Stderr, Queue Snapshot, Completed Manifest, and Pending Publish targets when cross-page conflicts exist.
- Kept diagnostics open/tail actions backend-allowlisted and did not add arbitrary paths, repair controls, lifecycle controls, queue mutation, rerun, drain, or media-policy changes.

The next chunk should be:

### WebView Settings Structured Audio/Subtitle Cross-Check

Target files:

- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\settingsView.js`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\settingsMetadata.js`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\settingsOverview.js`
- `DesktopApp\tests\test_application_facade.py`

Work:

- Continue replacing hard-to-interpret saved setting keys with structured operator summaries for audio/subtitle routing and publish-safety posture.
- Keep settings preview/save backend-owned.
- Do not change FFmpeg/subtitle/audio policy behavior in this pass.

Expected risk:

Low to medium. This should be display/patch-builder clarity only, but settings text must not imply behavior that backend validation does not enforce.

The WebView Settings Structured Audio/Subtitle Cross-Check chunk is complete:

- Added a read-only Audio / Subtitle Policy Cross-Check panel to WebView Settings.
- Cross-checks the visible subtitle/audio builder state for preferred subtitle language routing, TX3G/BDPGS SRT generation, original subtitle preservation, ASS/SSA drop posture, subtitle timeout posture, preferred audio defaults, passthrough/transcode mode, channel caps, and no-audio safety.
- Blocks/reviews local contradictions such as drop-without-convert and no-audio output while keeping backend preview/save authoritative.
- Fixed the subtitle guidance language summary to read the actual `settings-subtitle-languages` control instead of a stale/nonexistent id.
- Kept FFmpeg, subtitle extraction/OCR, audio routing, remux/encode policy, publish behavior, settings save semantics, Tk fallback, and backend command ownership unchanged.

The next chunk should be:

### WebView Settings To Launch Risk Handoff

Target files:

- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\settingsView.js`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\launchView.js`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\launchReadinessView.js`
- `DesktopApp\tests\test_application_facade.py`

Work:

- Make saved settings risk and staged patch risk easier to connect to Launch pipeline/CSV rerun preflight.
- Keep Launch commands backend-owned and do not alter launch acceptance policy.
- Do not add process lifecycle controls, media policy changes, or settings mutation outside the existing backend preview/save routes.

Expected risk:

Low to medium. The work is still presentation and command-readiness guidance, but wording must avoid suggesting that local WebView checks replace backend launch validation.

The WebView Settings To Launch Risk Handoff chunk is complete:

- Added a read-only Launch Risk Handoff table under Launch > Saved Settings Trust.
- Translates saved settings risk into start-specific rows for backend settings risk, source/scratch/output roots, stability/integrity gates, deferred publish, remux/encode size posture, subtitle SRT routing, audio no-output safety, PATH tool fallback, and continuous-mode sensitivity.
- Pipeline and CSV rerun preflight text still includes saved settings risk, and Audit preflight now includes the compact saved-settings decision without changing audit start behavior.
- Kept Launch commands, backend launch validation, process locks, settings preview/save, FFmpeg/subtitle/audio policy, pending publish behavior, and Tk fallback unchanged.

The next chunk should be:

### WebView Pending Publish Drain Action Confidence

Target files:

- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\pendingPublishView.js`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\launchView.js`
- `DesktopApp\tests\test_application_facade.py`

Work:

- Make the existing Pending Publish drain controls and Launch publish-parked mode explain readiness using already-loaded pending row diagnostics, drain evidence, and close-readiness.
- Keep drain mutation backend-owned and do not add repair, bypass, delete, rewrite, move, or arbitrary path actions.

Expected risk:

Low to medium. The value is high for operator trust, but wording must avoid implying that frontend checks can override backend drain safety.

The WebView Pending Publish Drain Action Confidence chunk is complete:

- Added a read-only Drain Action Confidence table before the existing Publish Parked Outputs control.
- The handoff combines current parked rows, blocker evidence, validation checklist posture, recovery dry-run rows, latest drain command, durable drain summary, recent backend drain events, and selected-row evidence into explicit confidence/action rows.
- Recovery-plan and drain-command history refreshes now re-render the confidence handoff so it does not go stale after dry-run planning or command-history updates.
- Fixed Pending Publish Drain Correlation evidence filtering so backend-authored evidence classes drive do-not-drain correlation counts.
- Kept Publish Parked Outputs backend-owned and did not add repair, bypass, delete, rewrite, move, arbitrary path, or frontend drain controls.

The next chunk should be:

### WebView Pending Publish And Completed Publish-Proof Polish

Target files:

- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\pendingPublishView.js`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\completedView.js`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\crossPageContextView.js`
- `DesktopApp\tests\test_application_facade.py`

Work:

- Tighten the read-only flow from Completed output proof to Pending Publish and back, especially after a drain leaves no parked rows but completed/output proof is missing or stale.
- Keep exact-path matches as proof and same-leaf matches advisory.
- Do not add repair, rerun, reconcile, cleanup, drain bypass, deletion, publish, or arbitrary path actions.

Expected risk:

Low to medium. This is still display-only over existing payloads, but wording must not imply that WebView correlation can prove a completed output was safely published without backend manifest/output evidence.

The WebView Pending Publish And Completed Publish-Proof Polish chunk is complete:

- Completed Output Proof now flags completed rows that report a missing output and have no exact Pending Publish or durable drain-summary proof.
- The proof summary now includes `Missing completed output without pending/drain proof` so the missing-output case is visible even when Pending Publish is empty.
- Cross-page context now explicitly warns that an empty Pending Publish view is not publish proof when Completed reports missing outputs.
- Kept exact-path matches as proof, same-leaf matches as advisory, and did not add repair, rerun, reconcile, cleanup, drain bypass, deletion, publish, or arbitrary path actions.

The next chunk should be:

### WebView Diagnostics Command-Result Drilldown

Target files:

- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\commandHistory.js`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\diagnosticsView.js`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\diagnosticsBridge.js`
- `DesktopApp\tests\test_application_facade.py`

Work:

- Make command-result failures easier to drill into from Diagnostics without adding retry/mutation controls.
- Group backend-owned command results by owner page, severity, refresh target, and diagnostics target.
- Preserve command journal atomicity, duplicate-command guards, and backend allowlists.

Expected risk:

Low. This should be display-only over existing command-history and diagnostics bridge payloads.

The WebView Diagnostics Command-Result Drilldown chunk is complete:

- Added a Diagnostics Command Result Drilldown panel with owner page, command, issue level, refresh target, and safest next action.
- The drilldown prioritizes warning/error commands and shows recent successful commands only when no issues are visible.
- Selecting a command row shows backend message, owner page, refresh target, warnings/errors, specialized Pending Publish command triage, backend data, submitted request, and read/open diagnostics handoff.
- Reused existing command-history classification and diagnostics bridge allowlist actions; no new backend route or mutation path was added.
- Kept command journal behavior, duplicate-command guards, backend allowlists, Tk fallback, and media policy unchanged.

The next chunk should be:

### WebView Diagnostics Artifact And Command Correlation

Target files:

- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\commandHistory.js`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\diagnosticsView.js`
- `DesktopApp\tests\test_application_facade.py`

Work:

- Correlate selected command failures with visible diagnostics log rows and state artifact hints so operators can see whether a command warning has matching stderr/log/state evidence.
- Keep correlation exact and read-only.
- Do not add retry, lifecycle, repair, drain, save, rename, delete, publish, arbitrary path, or media-policy behavior.

Expected risk:

Low to medium. This is presentation-only, but matching text too loosely can create false confidence; prefer conservative "possible related evidence" wording.

The WebView Diagnostics Artifact And Command Correlation chunk is complete:

- Added Related Diagnostics Evidence under Diagnostics Command Result Drilldown.
- Selected commands now show possible visible diagnostics log matches plus backend-allowlisted evidence targets.
- Matching is deliberately conservative and labeled as possible related evidence, not proof.
- Diagnostics refresh re-renders selected-command evidence after structured log rows are rebuilt.
- Kept all actions backend-allowlisted and did not add retry, lifecycle, repair, drain, save, rename, delete, publish, arbitrary path, or media-policy behavior.

The next chunk should be:

### WebView Settings/Launch Final Parity Review

Target files:

- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\settingsView.js`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\launchView.js`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\commandHistory.js`
- `DesktopApp\tests\test_application_facade.py`

Work:

- Review remaining Settings and Launch parity gaps now that diagnostics/pending/completed trust panels are mature.
- Prefer small structural polish over new backend routes.
- Keep launch commands, settings preview/save, and media policy backend-owned.

Expected risk:

Low to medium. Most work should be display/readiness polish, but avoid changing launch acceptance, settings persistence, FFmpeg policy, or scheduler behavior.

The WebView Settings/Launch Final Parity Review chunk is complete:

- Added a read-only Settings Launch Impact Handoff panel under Patch Preview.
- The panel summarizes staged patch state, changed settings groups, local save readiness, last backend settings command, and launch authority guardrails.
- Added a touched-patch tracker so the default example Changes JSON is not treated as an unsaved launch concern until the operator edits, builds, previews, or saves the patch.
- Launch preflights now warn when the same WebView session has touched unsaved effective settings changes or invalid Changes JSON.
- The warning explicitly states that Launch uses saved backend settings only until backend Save Patch succeeds and settings reload/refresh completes.
- Kept settings preview/save, launch commands, schedule gates, and media policy backend-owned.

The next chunk should be:

### WebView Daily-Driver Readiness Pass

Target files:

- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\app.js`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\launchView.js`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\diagnosticsView.js`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\queueView.js`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\completedView.js`
- `DesktopApp\tauri_shell\src-tauri\src\lib.rs`
- `DesktopApp\tests\test_application_facade.py`

Work:

- Do a final operator-trust pass across Home, Launch, Queue, Completed, Pending Publish, Diagnostics, Rename, and Settings for confusing empty states, stale refresh wording, duplicated warnings, and missing next-step text.
- Prefer cleanup and consistency over new features.
- Keep all mutation routes backend-owned and do not change media policy.

Expected risk:

Low. This should be mostly presentation polish and static coverage. Stop if the pass exposes a backend contract defect that needs a separate tested fix.

The WebView Daily-Driver Readiness browser smoke pass found and fixed one real startup defect:

- The WebView refresh loop could fail with `diagnosticsBridgeActions is not defined` because the shared diagnostics bridge exported most helper functions globally but missed that one.
- `diagnosticsBridgeActions` is now exported on `window`, matching the rest of the bridge helper contract used by Launch, Queue, Diagnostics, and command-review panels.
- The sidebar product version is now initialized from the backend bootstrap on `DOMContentLoaded`, before the first snapshot refresh, so the WebView does not briefly show the static V5 shell label as the product version.
- Browser smoke verification confirmed Home refresh, Launch Backend Preflight, Queue Launch Decision Checklist, and browser console health against a live local API server.
- No route schema, command contract, settings contract, media policy, Tk fallback, or filesystem mutation behavior changed.

The next chunk should be:

### WebView Real-Media Validation And Packaging Confidence Pass

Target files:

- `DesktopApp\tests\test_application_facade.py`
- `DesktopApp\tests\test_tauri_shell_scaffold.py`
- `DesktopApp\tauri_shell\Test-TauriShell-Build.ps1`
- `Docs\architecture\TAURI_WEBVIEW_PARITY_MATRIX.md`
- `Docs\active-plans\V5_TAURI_TRANSITION_CURRENT_PLAN.md`

Work:

- Move from static/operator-trust parity polish into repeatable smoke validation for the Tauri preview launch path and local API startup path.
- Confirm the deployable package still includes the WebView static assets, split JS modules, local API server, Tauri launcher scripts, and docs needed by the preview shell.
- Add or update lightweight checks only where they catch real packaging drift; avoid broad packaging rewrites.

Expected risk:

Low to medium. This should be validation-focused, but release packaging checks can expose stale include/exclude assumptions after the WebView module split.

The WebView packaging-confidence pass is complete:

- Added a release self-test gate that parses the WebView static index, verifies the backend bootstrap placeholder, rejects unsafe `/assets/...` references, and confirms every referenced asset exists in the bundle.
- Tauri build checks still validate JavaScript syntax, while the release self-test now validates asset presence in the package layout.
- The release self-test exposed and the pass fixed pending-publish reliability drift:
  - the reliability behavior harness now extracts pending drain summary helpers before testing `Invoke-RetryPendingPushes`;
  - `Invoke-RetryPendingPushes` now passes its summary item list directly to `Complete-PendingDrainSummary` instead of wrapping the generic list in `@(...)`, which PowerShell 7 rejects during parameter binding;
  - the config-preview behavior fixture now includes current required `ValidExtensions` and `RobocopyFlags` safety keys.
- Validation passed for the Tauri scaffold tests, Tauri cargo check, WebView JavaScript syntax checks, release self-test with tool integration/end-to-end media smoke skipped, reliability regressions, and the full desktop unit suite.

The next chunk should be:

### Tauri Preview Launch Smoke Hardening

Target files:

- `DesktopApp\tauri_shell\Test-TauriShell-Launch.ps1`
- `DesktopApp\tauri_shell\Launch-MediaPipelineRemuxEncodeAIO-TauriPreview.ps1`
- `DesktopApp\tauri_shell\src-tauri\src\lib.rs`
- `DesktopApp\tests\test_tauri_shell_scaffold.py`
- `Docs\active-plans\V5_TAURI_TRANSITION_CURRENT_PLAN.md`

Work:

- Review whether the existing Tauri launch smoke checker proves enough of the real preview lifecycle: backend bootstrap, health/contract validation, WebView window creation, close-readiness prompt path, graceful backend shutdown, and orphan backend detection.
- Improve the checker only where it remains bounded and non-destructive.
- Avoid adding Network lifecycle controls, media processing starts, or filesystem mutation to the smoke path.

Expected risk:

Medium. Launch smoke checks touch process lifecycle and can be flaky if too aggressive. Keep them bounded, explicit, and optional until they are reliable on the operator workstation.

The Tauri Preview Launch Smoke Hardening chunk is complete:

- The launch smoke checker now baselines existing Tauri shell PIDs and only accepts newly created `mediapipeline-tauri-shell` processes as evidence for the current run.
- Failure paths now include bounded stdout/stderr tails for early process exit, missing window, missing backend, close-request refusal, and close timeout.
- The checker now verifies the close request is accepted, waits separately for new Tauri shell PIDs and new backend PIDs to exit, and cleans up both in `finally`.
- A live launch smoke test passed on the operator workstation with `Test-TauriShell-Launch.ps1 -TimeoutSeconds 180 -CloseTimeoutSeconds 30`; no preview shell or local API process remained afterward.
- No Rust shell behavior, backend route contract, Tk fallback, Network lifecycle, media policy, or filesystem mutation behavior changed.

The next chunk should be:

### Tauri Preview Operator Error Surface

Target files:

- `DesktopApp\tauri_shell\src-tauri\src\lib.rs`
- `DesktopApp\tests\test_tauri_shell_scaffold.py`
- `Docs\active-plans\V5_TAURI_TRANSITION_CURRENT_PLAN.md`

Work:

- Improve operator-facing startup error messages from the Rust shell without changing backend acceptance rules.
- Focus on missing bundled Python, backend bootstrap timeout, invalid health/contract response, oversized/malformed response, and local API shutdown failures.
- Keep responses bounded and avoid logging secrets such as bearer tokens.

Expected risk:

Low to medium. This is mostly diagnostics wording, but the Rust shell is process-lifecycle code; keep changes small and preserve existing validation/shutdown semantics.

The Tauri Preview Operator Error Surface chunk is complete:

- Rust shell startup errors now include bounded DesktopApp/Python candidate context for layout and runtime discovery failures.
- Backend bootstrap timeout/read/disconnect errors now include bounded stdout-before-bootstrap context, and stdout-before-bootstrap log lines are bounded before printing.
- Health and contract validation failures now identify the backend URL and include bounded reported capability or route samples when required contracts are missing.
- Bearer tokens remain excluded from operator-facing error context.
- Added Rust unit tests for diagnostic helper behavior and Python static coverage for the shell startup diagnostics contract.
- Validation passed for Rust helper tests, Tauri cargo check, Tauri build checker, Tauri launch smoke, the full desktop Python suite, and the release self-test with tool integration/end-to-end media smoke skipped.
- No backend acceptance rule, route contract, shutdown sequence, Tk fallback, Network lifecycle, media policy, or filesystem mutation behavior changed.

The next chunk should be:

### Tauri Preview Failure-Injection Coverage

Target files:

- `DesktopApp\tauri_shell\src-tauri\src\lib.rs`
- `DesktopApp\tests\test_tauri_shell_scaffold.py`
- `DesktopApp\tauri_shell\Test-TauriShell-Launch.ps1`
- `Docs\active-plans\V5_TAURI_TRANSITION_CURRENT_PLAN.md`

Work:

- Add lightweight failure-path coverage around the Rust shell bootstrap and HTTP-response helpers where it can be tested without launching media work.
- Prefer pure Rust helper tests and bounded launch-checker assertions over fragile GUI failure simulation.
- Keep preview smoke optional, non-mutating, and bounded.
- Do not add Network lifecycle controls, backend bypasses, media starts, queue mutation, publish mutation, or filesystem mutation.

Expected risk:

Low to medium. The goal is validation depth around existing process boundaries, not behavior change. Avoid broad shell rewrites or brittle environment-dependent failure simulations.

The Tauri Preview Failure-Injection Coverage chunk is complete:

- Added Rust failure-injection tests for backend JSON request success shape, non-200 bounded body previews, missing HTTP body separators, non-HTTP backend URLs, oversized responses, invalid UTF-8, missing health capabilities, and missing local API route-contract entries.
- The tests use one-shot localhost test backends and pure helper calls; they do not start media work, launch the pipeline, mutate queue/publish state, or touch operator media files.
- Added explicit assertions that bearer tokens do not leak into validation failure text.
- `Test-TauriShell-Build.ps1` now runs Rust shell unit tests after cargo check, so preview build validation catches helper drift automatically.
- Python static coverage now tracks the failure-injection tests and the Rust unit-test build gate.
- Validation passed for Rust helper tests, Tauri cargo check, the strengthened Tauri build checker, the full desktop Python suite, and the release self-test with tool integration/end-to-end media smoke skipped.
- No backend acceptance rule, route contract, shutdown sequence, Tk fallback, Network lifecycle, media policy, or filesystem mutation behavior changed.

The next chunk should be:

### Tauri Preview Packaging And Launcher Documentation Tightening

Target files:

- `DesktopApp\tauri_shell\README.md`
- `DesktopApp\tauri_shell\Launch-MediaPipelineRemuxEncodeAIO-TauriPreview.ps1`
- `DesktopApp\tauri_shell\Test-TauriShell-Prereqs.ps1`
- `DesktopApp\tests\test_tauri_shell_scaffold.py`
- `Docs\active-plans\V5_TAURI_TRANSITION_CURRENT_PLAN.md`

Work:

- Tighten operator-facing preview launcher docs and prereq messages now that launch/build checks are stronger.
- Confirm the preview remains explicitly non-default and Tk remains the supported fallback.
- Improve wording around what the Tauri preview validates, what it does not validate, and what to run before trusting it for daily use.
- Avoid changing backend launch semantics, install behavior, network lifecycle, media policy, or filesystem mutation.

Expected risk:

Low. This should be mostly documentation and static launcher/prereq message clarity. Keep code changes small and avoid adding installer behavior.

The Tauri Preview Packaging And Launcher Documentation Tightening chunk is complete:

- The Tauri preview README now describes the current validation ladder: prereq `-CheckOnly`, build gate, launch smoke, release self-test, and separate real-media/tool integration checks.
- The preview launcher now states that Tk remains the supported daily-use shell until Tauri parity and real-media validation are complete.
- Launcher output now explicitly states the WebView/backend ownership boundary and warns that `-CheckOnly` does not launch WebView2, process media, validate FFmpeg, or prove pending-publish behavior.
- The prereq checker now labels itself as non-mutating and prints the next validation steps after it passes.
- Static tests now preserve the non-default preview posture and validation wording.
- Validation passed for prereq checks, launcher `-CheckOnly`, the strengthened Tauri build checker, the full desktop Python suite, and the release self-test with tool integration/end-to-end media smoke skipped.
- No backend launch semantics, local API contracts, install behavior, Tk fallback, Network lifecycle, media policy, or filesystem mutation behavior changed.

The next chunk should be:

### WebView Real-Media Dry-Run Readiness Review

Target files:

- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\launchView.js`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\diagnosticsView.js`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\maintenanceView.js`
- `DesktopApp\tests\test_application_facade.py`
- `Docs\active-plans\V5_TAURI_TRANSITION_CURRENT_PLAN.md`

Work:

- Review whether the WebView clearly separates launch readiness, release dry runs, diagnostics evidence, and real-media validation readiness.
- Improve presentation-only guidance where the operator could confuse a preview/build/release check with proof that real media processing is safe.
- Prefer reusing existing backend state, command history, and diagnostics data.
- Do not add media starts, repair controls, queue mutation, publish mutation, Network lifecycle controls, or media-policy changes.

Expected risk:

Low to medium. This is operator-trust wording and presentation over existing backend data, but avoid implying that WebView checks replace backend launch validation or real processing proof.

The WebView real-media dry-run readiness review is complete:

- Added Launch real-media validation boundary guidance to pipeline and CSV rerun preflights, plus Audit-specific wording that audit evidence applies after files already exist.
- Added Launch saved-settings risk wording that treats preview/build/release checks as shell/package readiness only, not proof of FFmpeg routing, subtitle OCR/SRT output, audio selection, size guard behavior, sidecar correctness, or pending-publish completion.
- Added Diagnostics investigation and log guidance that clean or empty diagnostics evidence is not proof of real-media success.
- Added Maintenance readiness, dry-run confidence, release dry-run, and completed-manifest backfill dry-run wording that separates packaging/backfill posture from real-media processing proof.
- Static coverage now preserves the new Launch, Diagnostics, and Maintenance proof-boundary helper functions and wording.
- No backend route, media start, repair control, queue mutation, publish mutation, Network lifecycle control, media policy, Tk fallback, or V4 behavior changed.

The next chunk should be:

### WebView Daily-Driver Real-Media Validation Playbook

Target files:

- `Docs\architecture\TAURI_WEBVIEW_PARITY_MATRIX.md`
- `Docs\active-plans\V5_TAURI_TRANSITION_CURRENT_PLAN.md`
- `Docs\sample-validation\V5_REAL_MEDIA_VALIDATION_PLAYBOOK.md`
- Optionally, WebView Home/Launch presentation files if a non-mutating checklist belongs in-app.

Work:

- Create a concrete operator checklist for the first small known media batch: expected Queue route evidence, subtitle/audio proof, size-growth review, Completed output proof, Diagnostics log order, and Pending Publish drain proof.
- Keep the playbook read-only and observational; do not add media policy changes or WebView-owned mutation.
- Use real logs/output observations from operator testing before changing route or size policy.

Expected risk:

Low. Documentation and optional presentation-only guidance, but avoid implying that sample validation replaces backend acceptance rules or full regression testing.

The WebView daily-driver real-media validation playbook chunk is complete:

- Added `Docs\sample-validation\V5_REAL_MEDIA_VALIDATION_PLAYBOOK.md` with a concrete small-batch validation flow covering pre-run readiness, during-run process evidence, post-run output/sidecar proof, subtitle proof, audio proof, size-growth proof, Pending Publish proof, acceptance criteria, and stop conditions.
- Added a Home Daily-Driver Checklist row for real-media sample proof using already-loaded Queue, Completed, Diagnostics, and Pending Publish payloads.
- Added Home summary wording that WebView readiness is not proof by itself and daily-driver confidence still requires a known sample run whose evidence agrees.
- Added the new playbook to `DOCS_INDEX.md`, `TLDR.md`, and the bundle README.
- No backend route, process start, media policy, queue mutation, publish mutation, Network lifecycle control, Tk fallback, or V4 behavior changed.

The next chunk should be:

### WebView Real-Media Evidence Drilldown Polish

Target files:

- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\queueView.js`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\completedView.js`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\pendingPublishView.js`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\diagnosticsView.js`
- `DesktopApp\tests\test_application_facade.py`

Work:

- Improve selected-row evidence text for the real-media sample validation path so a known source can be followed from Queue route decision to Completed output proof, Pending Publish drain proof, and Diagnostics evidence.
- Keep this read-only and based on existing backend payloads.
- Do not add repair, accept, rerun, drain-bypass, delete, manifest-write, or arbitrary path actions.

Expected risk:

Low to medium. This is read-only presentation, but avoid duplicating business logic or presenting stale evidence as proof.

The WebView Real-Media Evidence Drilldown Polish chunk is complete:

- Added selected-row real-media trace sections to Queue, Completed, Pending Publish, Diagnostics ActiveJobs, and Diagnostics log rows.
- Queue detail now identifies the source/route/runtime proof that exists before launch and explicitly lists FFmpeg execution, subtitle/audio result, completed output, sidecar, size-growth, and publish proof as still unproven.
- Completed detail now identifies output, sidecar, route, size, audio, and subtitle evidence when present and separates that from final publish or Plex playback acceptance.
- Pending Publish detail now identifies parked payload, manifest, sidecar payload count, drain recommendation, and durable drain-proof boundaries before another publish decision.
- Diagnostics ActiveJobs and log details now state that process/log clues are not output, sidecar, subtitle/audio, size, or publish proof by themselves.
- Static coverage preserves the new proof-boundary helper names and wording.
- No backend route, process start, media policy, queue mutation, publish mutation, Network lifecycle control, Tk fallback, or V4 behavior changed.

The next chunk should be:

### WebView Sample Run Evidence Correlation Report

Target files:

- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\app.js`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\queueView.js`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\completedView.js`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\pendingPublishView.js`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\diagnosticsView.js`
- `DesktopApp\tests\test_application_facade.py`

Work:

- Add a read-only evidence correlation view that starts from a selected source/output path and summarizes matching Queue, Completed, Pending Publish, ActiveJobs, and Diagnostics clues already loaded in the WebView session.
- Treat filename-only matches as advisory and exact normalized path matches as stronger proof.
- Keep this as an operator investigation report only; do not add accept, repair, delete, rerun, drain, manifest-write, arbitrary path, or media-policy controls.

Expected risk:

Medium. Cross-page correlation can become misleading if it overstates filename-only evidence. Keep proof labels explicit and prefer backend-authored fields when available.

The WebView Sample Run Evidence Correlation Report chunk is complete:

- Added a Home Cross-Page Context "Sample Evidence Correlation" table.
- The report seeds from selected Queue, Completed, and Pending Publish rows first, then recent visible rows when no row is selected.
- It compares exact normalized paths and filename-only advisory matches across Queue source/runtime-output, Completed source/output, Pending source/destination/parked-payload, and Diagnostics text clues already loaded in the WebView session.
- Exact path evidence is labeled separately from filename-only evidence, and row text states when Completed output/sidecar proof is still not exact-matched.
- Selecting a correlation row jumps to the owning Queue, Completed, or Pending Publish detail through existing frontend selection helpers; it does not open files or mutate backend state.
- Static coverage preserves the new DOM ids, helper functions, and proof-boundary wording.
- No backend route, process start, media policy, queue mutation, publish mutation, settings mutation, arbitrary path action, Network lifecycle control, Tk fallback, or V4 behavior changed.

The next chunk should be:

### WebView Real-Media Validation Run Log Template

Target files:

- `Docs\sample-validation\V5_REAL_MEDIA_VALIDATION_PLAYBOOK.md`
- `Docs\architecture\TAURI_WEBVIEW_PARITY_MATRIX.md`
- `Docs\active-plans\V5_TAURI_TRANSITION_CURRENT_PLAN.md`
- optionally `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\app.js`

Work:

- Add a concise operator-facing validation log template for recording one small known media batch: source, expected route, subtitle/audio expectations, output path, sidecar path, size-growth result, pending-publish result, and final acceptance/review decision.
- Keep it observational and read-only. Do not add backend acceptance flags, manifest writes, media-policy changes, or WebView-owned mutation.
- Use actual operator sample results before turning this into a persisted backend artifact.

Expected risk:

Low. This is documentation or presentation-only guidance, but it should avoid implying that manual sample acceptance changes backend routing or publish safety rules.

The WebView Real-Media Validation Run Log Template chunk is complete:

- Added a Home Cross-Page Context "Validation Log Template" panel.
- The template uses the highest-priority selected/recent sample evidence row and prints a manual checklist for route/remux-vs-encode evidence, FFmpeg/run logs, subtitle behavior, audio behavior, Completed output, sidecar/manifest, size-growth policy, Pending Publish, Diagnostics, and operator decision.
- The template states that it is generated from loaded WebView payloads only and is not backend acceptance, manifest mutation, persisted validation state, or media policy.
- Updated the real-media playbook with the same template fields and the warning not to turn this into an acceptance button without a backend-owned persisted validation artifact.
- Static coverage preserves the new DOM ids, helper functions, and no-mutation wording.
- No backend route, process start, media policy, queue mutation, publish mutation, settings mutation, persisted validation artifact, arbitrary path action, Network lifecycle control, Tk fallback, or V4 behavior changed.

The next chunk should be:

### WebView Real-Media Evidence Export Design

Target files:

- `Docs\sample-validation\V5_REAL_MEDIA_VALIDATION_PLAYBOOK.md`
- `Docs\active-plans\V5_TAURI_TRANSITION_CURRENT_PLAN.md`
- optionally backend/API design docs if a route contract is proposed

Historical work:

- This design-only chunk was later superseded by the constrained backend-owned Sample Validation Record implementation.
- The implemented route still follows the original non-goals: evidence-only JSONL, no acceptance flag, no manifest/sidecar rewrite, no publish/drain signal, no launch unblock, no queue mutation, and no media-file mutation.

Expected risk:

Low for the original design-only chunk. The later implementation is intentionally constrained because a persisted validation artifact could be mistaken for processing success unless backend contracts make the boundary explicit.

The WebView Real-Media Evidence Export Design chunk is complete:

- Added `Docs\sample-validation\V5_SAMPLE_VALIDATION_ARTIFACT_DESIGN.md`.
- Defined the backend-owned `sample_validation_record.v1` JSONL artifact under `LocalBase\State\Validation`; this has since been implemented as evidence-only state.
- Documented non-goals so future validation records cannot mark jobs complete, suppress failures, drain publish state, rewrite sidecars/manifests, change media policy, unblock launch, or override diagnostics.
- Proposed preview/append/read/tail/open route boundaries; these have since been implemented with backend-owned write-path control.
- Listed validation warnings, reconciliation rules, UI constraints, test requirements, and rollout criteria before any implementation should begin.
- The older WebView Validation Log Template wording has since been replaced by the backend-owned Sample Validation Record panel.
- No acceptance flag, manifest mutation, media policy, queue mutation, publish mutation, settings mutation, arbitrary path action, Network lifecycle control, Tk fallback, or V4 behavior changed.

The next chunk should be:

### WebView Real-Media Validation Usability Smoke

Target files:

- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\crossPageContextView.js`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\queueView.js`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\completedView.js`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\pendingPublishView.js`
- `DesktopApp\tests\test_application_facade.py`
- optional Browser smoke notes

Work:

- Run a local API/WebView browser smoke against the Home Cross-Page Context, Queue, Completed, Pending Publish, and Diagnostics panels.
- Fix any obvious layout, scroll, empty-state, or console-error issues in the new real-media trace/correlation/template panels.
- Keep all changes presentation-only and read-only.

Expected risk:

Low to medium. Browser smoke can expose frontend-only defects. Avoid adding backend routes or mutation controls during polish.

The WebView Real-Media Validation Usability Smoke chunk is complete:

- Started a temporary token-protected local API on localhost and shut it down after the smoke.
- Opened the backend-served WebView in the browser.
- Verified Home loaded Operator Readiness, Daily-Driver Checklist, Cross-Page Context, Sample Evidence Correlation, and Validation Log Template.
- Verified Sample Evidence Correlation selected a Completed sample and navigated to the Completed detail panel.
- Verified Queue and Completed selected-row real-media trace sections rendered after selecting actual rows.
- Verified Diagnostics log selected-row real-media trace rendered.
- Verified Pending Publish empty-state behavior stayed non-mutating when no real pending rows were present.
- Browser console warning/error capture returned no warnings or errors during the smoke.
- No code, backend route, process start behavior, media policy, queue mutation, publish mutation, settings mutation, persisted validation artifact, arbitrary path action, Network lifecycle control, Tk fallback, or V4 behavior changed.

The next chunk should be:

### WebView Settings/Launch Real-Media Policy Handoff Smoke

Target files:

- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\settingsView.js`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\launchView.js`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\launchReadinessView.js`
- `DesktopApp\tests\test_application_facade.py`

Work:

- Browser-smoke Settings saved-policy visibility and Launch saved-settings/preflight handoff.
- Confirm video/remux/encode, subtitle, audio, size-guard, and pending-publish settings summaries are visible before Launch.
- Fix presentation-only issues where Launch fails to explain which saved policies will apply to a real-media run.
- Do not change media policy or add launch bypasses.

Completed:

- Added Settings Active Media Policy Handoff rows for route/size/video/subtitle/audio/pending-publish builder state.
- Expanded Launch Risk Handoff with saved H.264 copy/remux precision, size-growth, route/encoder, remux-safe codec, container, and original-subtitle preservation evidence.
- Kept Settings Preview/Save and Launch Start backend-owned; no FFmpeg, subtitle, audio, queue, publish, or path policy changed.

Expected risk:

Low to medium. The work should remain read-only unless an existing backend-owned Settings preview/save command is deliberately tested. Keep any fixes focused on visibility and handoff wording.

The WebView Backend Media Policy Readiness chunk is complete:

- Added backend-authored `settings_media_policy_readiness.v1` data to the existing Settings workspace payload.
- The readiness rows summarize saved routing/size guard, output container and subtitle preservation posture, subtitle language routing, TX3G/BDPGS/ASS behavior, audio default/passthrough/channel safety, pending publish recovery posture, and source-preservation toggles.
- Added a Settings page Backend Media Policy Readiness table that renders only saved backend data and remains read-only.
- Added the same readiness status to Saved Settings Trust, Launch Risk Handoff, and Home cross-page context so operator-facing preflight text no longer depends only on local frontend builder logic.
- Kept Settings Preview/Save, Launch, FFmpeg, subtitle, audio, queue, publish, source, scratch, output, and Network lifecycle behavior unchanged.

The WebView Settings/Launch Policy Smoke And Tauri Asset Gate chunk is complete:

- Added `Test-WebViewSettingsLaunchPolicySmoke.ps1`, a bounded root smoke that starts a temporary token-protected local API against generated temporary state and verifies Settings/Launch backend media-policy readiness handoff visibility.
- Extended the WebView generated-state smoke fixture so it exercises Settings, Saved Settings Trust, Launch Risk Handoff, and Home cross-page context readiness text from the backend-owned Settings workspace.
- Hardened the Tauri pre-window WebView asset gate so the preview shell verifies the Settings backend media-policy table, Launch risk rows, Settings overview summary, Launch readiness text, and Home cross-page media readiness handoff before opening the window.
- Added scaffold coverage that keeps the new smoke script bounded and preserves the non-mutating boundary: no media processing, no pipeline launch, no publish/drain, no rename, no settings save, no source/output/scratch mutation, and no direct FFmpeg invocation from the Tauri shell.
- Added the new root smoke script to release layout validation.

The next chunk should be:

### WebView Settings Browser Smoke With Live Config

Target files:

- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\settingsView.js`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\settingsOverview.js`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\launchView.js`
- `DesktopApp\tests\test_application_facade.py`

Completed:

- Added `Test-WebViewSettingsLaunchLiveConfigSmoke.ps1`, a bounded root smoke that reads the current saved config through the local backend path and verifies Settings/Launch media-policy handoff visibility against live config data.
- Added `mediapipeline_desktop_app.webview_settings_live_smoke`, a reusable Python smoke helper that starts a temporary local API without background telemetry or mutation commands, fetches backend-served WebView assets, and validates `/api/settings/workspace`.
- Validated the current live config: 98 saved keys; backend media-policy readiness returned `Ready` with 10 coherent rows, 0 review rows, and 0 blocked rows.
- Added deterministic temp-config unit coverage for the live smoke helper, including sensitive-token redaction behavior for populated and blank auth-token settings.
- Added the new live-config smoke to the Tauri preview validation ladder and release layout validation.
- No media policy, launch acceptance, settings persistence, FFmpeg, subtitle/audio, queue, publish, source/scratch/output, Network lifecycle, Tk fallback, or V4 behavior changed.

Expected risk:

Low. This is read-only WebView visibility over existing backend settings data.

The next chunk should be:

### WebView Settings Save/Preview Operator Feedback Parity

Target files:

- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\settingsView.js`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\commandHistoryView.js`
- `DesktopApp\tests\test_application_facade.py`

Work:

- Improve WebView feedback around Settings Preview Patch and Save Patch results: pending state, confirmation requirement, redacted diff summary, backend warnings/errors, and saved-vs-staged status after refresh.
- Keep all settings mutation backend-owned through existing `/api/settings/preview-patch` and `/api/settings/save-patch` commands.
- Do not add new editable media-policy behavior or bypass backend validation.

Completed:

- Added a selectable Settings `Backend Preview / Save Result` detail pane.
- Backend result rows now expose current/evidence patch signature match, command result status, warnings, errors, backend data, changed/removed keys, redacted diff count/content, risk summary, backup path, config path, and reload evidence.
- Backend Preview Patch and Save Patch exception paths now retain page-local evidence for the current staged JSON so failed backend calls show as failed evidence instead of missing evidence.
- Tauri pre-window WebView validation now checks the backend-result detail DOM and helper function before opening the preview shell.
- Browser Settings/Launch smoke now verifies the detail panel after Preview Patch and still asserts the smoke does not call `settings.save_patch`.
- Cancelled Save Patch attempts now set visible `Save cancelled` operator feedback, select the Save confirmation boundary detail row, repeat that no backend save command was sent, and keep Launch warnings on saved-backend-settings-only semantics.
- Browser Settings/Launch smoke now overrides confirmation to cancel Save Patch after a real backend Preview Patch, verifies the cancellation text, verifies command history length is unchanged, and still asserts no `settings.save_patch` command is emitted.
- Existing backend-owned `/api/settings/preview-patch` and `/api/settings/save-patch` command semantics stayed unchanged.

Expected risk:

Medium. This touches operator feedback around a real mutation command, so keep changes UI-only unless a backend command-contract defect is found.

### WebView Backend Publish Reconciliation Evidence

Target files:

- `DesktopApp\mediapipeline_desktop_app\application\facade_publish_reconciliation_policy.py`
- `DesktopApp\mediapipeline_desktop_app\application\facade_publish_reconciliation.py`
- `DesktopApp\mediapipeline_desktop_app\api\read_payloads_inventory.py`
- `DesktopApp\mediapipeline_desktop_app\api\routes_read.py`
- `DesktopApp\mediapipeline_desktop_app\api\contract_read.py`
- `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\completedView.js`
- `DesktopApp\tests\test_application_facade.py`
- `DesktopApp\tests\test_webview_browser_completed_pending_proof_smoke.py`

Completed:

- Added backend-owned `GET /api/publish-reconciliation` with response schema `desktop_publish_reconciliation.v1`.
- Correlates Completed Manifest rows, current Pending Publish rows, and latest durable pending-drain summary items using exact normalized output/source paths first.
- Marks same-leaf matches as duplicate-title hints only.
- Flags missing completed outputs with no exact pending/drain proof as blockers so an empty Pending Publish view is not mistaken for proof of publication.
- Added a manual WebView Completed panel for the backend reconciliation result. It is not part of the normal refresh loop and only reads when the operator presses Refresh Backend Reconciliation.
- Extended the real-browser Completed/Pending smoke to call the backend route, render the reconciliation result, select row detail, and confirm no mutation POSTs occur.
- Updated route ownership/evidence docs, parity notes, smoke catalog/runbook, TLDR, changelog, and static/contract tests.
- No queue planning, FFmpeg/media policy, completed manifest writes, pending publish drain behavior, publish mutation, settings mutation, Tk fallback, or V4 behavior changed.

Expected risk:

Low. This is a bounded read-only evidence endpoint plus manual WebView display. The only new runtime work is an operator-triggered scan of already-supported Completed/Pending/drain-summary payloads.

The next chunk should be:

### WebView Queue / Completed / Pending Daily-Use Table Polish

Tighten row density, empty states, and selected-row operator detail for the daily-use media tables. Prefer read-only presentation over existing backend state and do not add new queue, publish, rename, or filesystem mutation authority.

Completed:

- Queue, Completed, and Pending Publish table status chips now explicitly disclose the WebView 250-row render cap when more filtered rows exist than are rendered.
- Status wording now uses `250 shown / N filtered / M rows` for large result sets, while the existing filter summary still explains that filtering is display-only and does not change backend command scope.
- No queue planning, publish drain, rerun, diagnostics open, manifest, media policy, Tk fallback, or V4 behavior changed.

The next chunk should be:

### WebView Rename / Settings Cross-Check Polish

Improve read-only confidence/status wording where Rename staged names and Settings media-routing policy meet operator decisions. Keep rename filesystem mutation backend-owned and avoid changing naming/media policy unless a concrete bug is reproduced.

Completed:

- Rename now includes a read-only `Pipeline Handoff` panel that compares previewed names against saved routing profile, size guard, output container, subtitle convert/drop posture, deferred publish, source-delete posture, filename extensions, sidecar preview state, force-pipeline rows, and final-name overrides.
- The handoff explicitly states that rename changes filenames only and does not convert containers, change codecs, remux, encode, OCR subtitles, publish, or make staged Settings JSON active.
- Node and browser rename smokes now verify the handoff text alongside apply-readiness and duplicate-target no-post behavior.
- No rename planner, filesystem apply transaction, sidecar update, media routing, FFmpeg policy, Settings save, Tk fallback, or V4 behavior changed.

The next chunk should be:

### WebView Rename Large-Batch Browser Coverage

Add a bounded browser smoke or Node smoke for large rename previews that verifies render-cap disclosure, checked-row scope, and row-order guidance without calling `/api/rename/apply`.

Completed:

- Rename now discloses its 250-row WebView render cap in the status text and table legend when backend preview rows exceed the rendered table limit.
- Batch Safety, Selection Audit, and Apply Readiness now state how many backend preview rows exist, how many are rendered, and that Check Applicable Rows/Apply Selected can include checked backend rows that are not currently visible in the capped table.
- Node and browser Rename smokes now render a 260-row preview, check all applicable rows, verify `260 checked`, verify render-cap wording, and then continue to the duplicate-target blocker path without posting `/api/rename/apply`.
- No rename planner, filesystem apply transaction, sidecar update, media routing, Settings save, Tk fallback, or V4 behavior changed.

The next chunk should be:

### WebView Daily Tables Large-Payload Browser Coverage

Add bounded browser or Node smoke coverage for large Queue, Completed, and Pending Publish payloads so the existing `250 shown / N filtered / M rows` status chips, filter warnings, selected-row detail, and no-mutation boundaries are proven under realistic large table conditions.

Completed:

- Added `Test-WebViewBrowserLargeTableSmoke.ps1`.
- The smoke starts a temporary local API, opens the real backend-served WebView in Chrome/Edge headless, injects 260-row Queue, Completed, and Pending Publish payloads, and verifies each table renders only 250 rows while disclosing `250 shown / 260 filtered / 260 rows`.
- It applies local display filters that hide one high-risk row, verifies hidden blocked/warning row warnings, then selects the hidden row programmatically and verifies selected-row detail still explains that the row is hidden by the current filter.
- It records attempted POSTs and fails if any mutation route such as launch, rerun, pending recovery, rename apply, or settings save is called.
- No backend queue planning, completed history, pending publish manifests/drain behavior, media policy, settings persistence, Tk fallback, or V4 behavior changed.

The next chunk should be:

### WebView Browser Smoke Stability Sweep

Review the browser-backed smoke runner duplication and failure diagnostics. Prefer a small shared helper only if it reduces repeated CDP launch/wait/error-reporting code without making individual smoke intent harder to read. Keep all smoke boundaries read-only unless the specific smoke already tests a guarded backend-owned mutation path.

Completed:

- Centralized browser-backed smoke process execution in `run_node_browser_smoke`, including bounded timeout conversion, process-result failure text, JSON result parsing, and malformed/no-output diagnostics.
- Moved all browser-backed smoke modules to the shared runner instead of local `subprocess.run` and ad hoc last-line JSON parsing.
- Hardened the shared Node/CDP prelude so Chrome/Edge launches with stdout/stderr ignored instead of undrained pipes.
- Added `terminateBrowser` with pre-exit detection and bounded kill/wait behavior so already-exited browsers cannot hang the smoke runner.
- Added static scaffold coverage requiring all browser-backed smoke modules to use the shared runner, shared browser launch, and bounded termination helpers.
- Ran all 14 browser-backed WebView tests successfully through the updated shared runner.
- No WebView runtime behavior, backend route contract, media policy, pipeline launch, settings save, rename apply, publish/drain, Network lifecycle, Tk fallback, or V4 behavior changed.

The next chunk should be:

### WebView Schedule Watcher Lifecycle Extended Validation

Add longer fixture/API/browser validation around continuous schedule-stop watcher lifecycle transitions that are already exposed by `/api/schedule`, `/api/backend/close-readiness`, Launch preflight/start, and Diagnostics lifecycle panels. Keep this validation-only unless a concrete backend lifecycle defect is reproduced.

Completed:

- Expanded focused schedule-stop watcher lifecycle coverage for deadline parsing, missing/invalid gate data, deadline stop requests, process-completed exit, cancellation, poll exceptions, unavailable flag writers, and flag-write failures.
- Added Local API fixture coverage proving a terminal `stop_requested` watcher state is exposed through `/api/schedule` and `/api/backend/close-readiness` without incorrectly blocking safe close after the stop request has been issued.
- Extended the real-browser WebView lifecycle smoke to cover the `stop_requested` watcher state in Diagnostics/Backend Lifecycle and to prove WebView still posts only the backend-owned `/api/backend/shutdown` request after close-readiness reports safe.
- Kept the work validation-only: no process launch semantics, schedule enforcement, stop-flag path, FFmpeg/media policy, settings, queue, publish, rename, Network lifecycle, Tk fallback, or V4 behavior changed.

The next chunk should be:

### WebView Maintenance / Reports Smoke Coverage

Add bounded WebView smoke coverage for the remaining low-mutation daily-use pages: Maintenance dry-run rendering and Audit/Reports investigation rendering. Keep the smoke fixture-backed and non-mutating except for already-safe backend dry-run commands.

Completed:

- Added `Test-WebViewBrowserMaintenanceReportsSmoke.ps1`.
- Added browser-backed coverage for real backend-served Maintenance and Reports pages.
- The smoke verifies Maintenance health/readiness, release dry-run result rendering, completed-manifest backfill dry-run result rendering, maintenance dry-run history, Reports failure/audit triage, selected failure/audit row details, and read-only Reports-to-Launch/Diagnostics navigation.
- It records attempted POSTs and fails if backend mutation routes for launch, audit start, CSV rerun, maintenance dry-run execution, settings save, rename apply, or pending-publish drain are posted.
- Added the wrapper to release layout validation, Tauri scaffold coverage, smoke catalogs, runbooks, coverage matrix, Docs index, mutation-boundary matrix, status board, and Tauri README.
- No release packaging command was executed from the WebView, no completed manifest was rewritten, and no media processing, process launch, audit start, CSV rerun, publish/drain, rename, settings save, queue mutation, source/output/scratch mutation, Tk fallback, or V4 behavior changed.

The next chunk should be:

### WebView Reports / Maintenance Command-Route Decision

Completed:

- Added `Test-LocalApiMaintenanceDryRunContractSmoke.ps1`.
- Added browser-free local API coverage that executes only `/api/maintenance/release-dry-run` and `/api/maintenance/completed-backfill-dry-run` against generated temporary state.
- Verified token enforcement, command history, release dry-run `dry_run=true`/no-manifest/no-zip evidence, completed-manifest backfill `writes_manifest=false` evidence, bounded timeout coercion, and unchanged temp source/output/completed manifest bytes.
- Added the wrapper to release layout validation, Tauri scaffold checks, Tauri README, API route inventory, validation ladder, TLDR, smoke catalog, status board, coverage matrix, root script inventory, release layout audit, and remediation changelog.
- Kept the browser-backed Maintenance/Reports smoke presentation-only for Maintenance POSTs so browser UI coverage still proves no mutation posts from that scenario.
- No real release package was created, no release manifest or zip was written, no completed manifest was rewritten, no media was processed, and no launch/audit/rerun/publish/rename/settings/queue/source/output/scratch behavior changed.

The next chunk should be:

### Real-Media Validation Readiness / Evidence Tightening

Completed:

- Added current-backend-evidence reconciliation to `/api/sample-validation/preview` and `/api/sample-validation/append` using `desktop_sample_validation_current_evidence.v1`.
- Made accepted/review sample records warn before append when the current Completed/Diagnostics evidence no longer proves the recorded source/output pair.
- Exposed current-evidence status, severity, proof matches, missing-evidence lines, safe next action, artifact read problems, and the read-only guardrail in the WebView Sample Validation result panel.
- Added `Test-LocalApiSampleValidationContractSmoke.ps1` to run the preview/append/read/tail sample-validation contract without Chrome/Edge, using only temporary state.
- Added route coverage for token enforcement, strict JSON handling, current-evidence preview, temp-only validation-log writes, diagnostics tail allowlisting, command history, and stale accepted-record warning behavior.
- Added the wrapper to release layout validation, Tauri scaffold checks, Tauri README, API route inventory, validation ladder, TLDR, smoke catalog, status board, coverage matrix, root script inventory, release layout audit, and remediation changelog.
- No sample was accepted automatically, no output was marked complete, no failure was cleared, no manifest/sidecar was rewritten, no media was probed or processed, and no launch/publish/rename/settings/queue/source/output/scratch behavior changed.

The next chunk should be:

### Real-Media Sample Run Operator Pilot

Completed:

- Added `desktop_real_media_pilot_plan.v1` to `/api/sample-validation` read payloads.
- The pilot plan is backend-authored and read-only. It turns existing sample-validation readiness and reconciliation evidence into staged operator checks for sample selection, saved media policy confirmation, backend-owned Launch, Completed output/sidecar proof, Diagnostics/run-log proof, Pending Publish proof, and evidence-only validation-note recording.
- Home Sample Validation Record now renders pilot-plan status, sample-run requirement, recommended sample count, per-stage actions, stop conditions, and mutation guardrails before readiness/reconciliation/history lines.
- Added regression coverage for pilot-plan payload shape, missing-evidence pilot-needed posture, fixture-backed real-media smoke coverage, and WebView static rendering strings.
- No pilot run was launched, no source/output/scratch paths were touched, no media was probed, no route/media policy was changed, and no backend mutation authority moved into WebView.

The next chunk should be:

### Operator-Selected Real-Media Sample Execution

Completed browser-readiness step:

- Added `Test-WebViewBrowserSampleValidationSmoke.ps1`.
- Added Chrome/Edge-backed coverage for the real backend-served Home Sample Validation panel.
- The smoke verifies pilot-plan/readiness/reconciliation rendering, sets an accepted decision, executes only `/api/sample-validation/preview`, and checks the current-evidence result including the Pending Publish review warning.
- The smoke verifies no `/api/sample-validation/append`, launch, audit, CSV rerun, drain, publish, rename, settings-save, queue mutation, or media mutation route is posted, and verifies no validation JSONL is written in the temporary state.
- Added the wrapper to release layout validation, Tauri scaffold checks, Tauri README, smoke catalog, validation ladder, TLDR, coverage matrix, root script inventory, release layout audit, mutation-boundary matrix, boundary audit, status board, Docs index, and remediation changelog.
- No real media was processed, no sample was accepted, no validation record was appended, and no source/output/scratch behavior changed.

The next chunk should be:

### Operator-Selected Real-Media Sample Execution

Run a small operator-approved sample batch and compare Queue route evidence, Completed proof, size policy, subtitle/audio decisions, Pending Publish posture, Diagnostics logs, and Sample Validation recording. This should remain observational first: do not change FFmpeg policy unless the pilot exposes a concrete mismatch.

### Sample Validation Append Readiness

Completed:

- Added `desktop_sample_validation_append_readiness.v1` to sample-validation preview and append result payloads.
- Home Sample Validation preview now shows operator status, append allowed, accepted-ready posture, manual-check counts, required acceptance gaps, recommended review gaps, current backend proof cleanliness, per-check rows, and a read-only guardrail.
- Append authorization remains unchanged: valid hold/rerun/fallback evidence notes can still be appended, while accepted samples now show required acceptance gaps before the operator records them as accepted evidence.
- Extended static/unit/browser-backed coverage so append-readiness text remains visible and the browser sample-validation smoke still proves no append or mutation routes are posted during preview.
- No sample was accepted automatically, no validation record append semantics changed, no media was probed or processed, and no launch/publish/rename/settings/queue/source/output/scratch behavior changed.

The next chunk should remain:

### Operator-Selected Real-Media Sample Execution

Run a small operator-approved sample batch and compare Queue route evidence, Completed proof, size policy, subtitle/audio decisions, Pending Publish posture, Diagnostics logs, and Sample Validation recording. This should remain observational first: do not change FFmpeg policy unless the pilot exposes a concrete mismatch.

### Sample Validation Execution Checklist

Completed:

- Added `desktop_real_media_execution_checklist.v1` rows to the backend-authored `/api/sample-validation` pilot plan.
- The checklist separates before-launch sample selection, saved policy confirmation, backend-owned Launch boundary, post-run Completed proof, post-run Diagnostics proof, Pending Publish proof, and evidence-record steps.
- Home now renders an `Operator Sample Execution Checklist` table with selectable details for backend evidence, expected operator proof, safe next action, unsafe-if-ignored text, and a mutation guardrail.
- Browser-backed coverage verifies the checklist and post-run Completed-proof detail in real Chrome/Edge rendering while still permitting only the preview route and blocking append/mutation posts.
- No launch, process, publish, drain, rename, settings save, queue mutation, source/output/scratch mutation, Tk fallback, V4, or FFmpeg/media policy behavior changed.

The next chunk should remain:

### Operator-Approved Real-Media Pilot Run

Run a small operator-approved sample batch and compare Queue route evidence, Completed proof, size policy, subtitle/audio decisions, Pending Publish posture, Diagnostics logs, and Sample Validation recording. This should remain observational first: do not change FFmpeg policy unless the pilot exposes a concrete mismatch.

### Launch Sample Execution Checklist

Completed:

- Launch now mirrors Home's backend-authored `desktop_real_media_execution_checklist.v1` rows at the start-decision surface.
- The Launch panel shows before-launch sample selection, saved policy confirmation, backend-owned Launch boundary, post-run Completed proof, post-run Diagnostics proof, Pending Publish proof, and evidence-record steps.
- Selectable detail shows current backend evidence, expected backend proof, operator proof, safe next action, unsafe-if-ignored text, and a Launch boundary reminder.
- `Test-WebViewBrowserLaunchQueueReadinessSmoke.ps1` now verifies the Launch sample execution checklist in real Chrome/Edge rendering while still proving no POST routes are sent during readiness rendering.
- No launch, process, publish, drain, rename, settings save, sample-validation append, queue mutation, source/output/scratch mutation, Tk fallback, V4, or FFmpeg/media policy behavior changed.

The next chunk should remain:

### Operator-Approved Real-Media Pilot Run

Run a small operator-approved sample batch and compare Queue route evidence, Completed proof, size policy, subtitle/audio decisions, Pending Publish posture, Diagnostics logs, and Sample Validation recording. This should remain observational first: do not change FFmpeg policy unless the pilot exposes a concrete mismatch.

### Launch Real-Media Sample Proof Handoff

Completed:

- Added a read-only `Real-Media Sample Proof Handoff` panel to the WebView Launch page.
- Launch now mirrors the Home `Real-Media Validation Worksheet` evidence before start: sample identity, Queue route intent, Completed output/sidecar/size proof, Diagnostics run evidence, Pending Publish/final destination posture, Settings saved-policy posture, Home Sample Validation evidence, and Launch mutation boundary.
- Reused the existing cross-page worksheet evidence builder through a shared `crossPageContext` from `refreshAllNow`, so Launch and Home read the same evidence context instead of drifting into separate proof logic.
- Extended static and browser-backed coverage so `Test-WebViewBrowserLaunchQueueReadinessSmoke.ps1`, `test_application_facade`, and `test_webview_real_media_smoke` verify the Launch proof handoff and shared context wiring.
- No launch, process, publish, drain, rename, settings save, queue mutation, source/output/scratch mutation, Tk fallback, V4, or media policy behavior changed.

The next chunk should remain:

### Operator-Selected Real-Media Sample Execution

Run a small operator-approved sample batch and compare Queue route evidence, Completed proof, size policy, subtitle/audio decisions, Pending Publish posture, Diagnostics logs, and Sample Validation recording. This should remain observational first: do not change FFmpeg policy unless the pilot exposes a concrete mismatch.

### Sample Validation Manual Acceptance Checklist

Completed:

- Added an `Acceptance Checklist` to the WebView Home Sample Validation Record panel.
- Loaded backend evidence can pre-check route, completed-output, sidecar/manifest, size, diagnostics, and pending-publish items. Manual checklist selections can add operator-confirmed diagnostics, subtitle, audio, size, sidecar, and pending-publish checks before Preview/Append.
- The checklist is carried only in the existing backend-owned sample-validation preview/append request body and is evaluated by the append-readiness payload. It does not accept output, clear failures, launch work, publish/drain, rename, save settings, probe media, or touch source/output/scratch paths.
- Added browser-backed coverage that fills manual checklist items, verifies they are present in the preview POST body, and still proves no append or mutation routes are posted.

The next chunk should remain:

### Operator-Selected Real-Media Sample Execution

Run a small operator-approved sample batch and compare Queue route evidence, Completed proof, size policy, subtitle/audio decisions, Pending Publish posture, Diagnostics logs, and Sample Validation recording. This should remain observational first: do not change FFmpeg policy unless the pilot exposes a concrete mismatch.

### Diagnostics State Artifact Browser Coverage

Completed:

- Extended `Test-WebViewBrowserDiagnosticsHandoffSmoke.ps1` so real Chrome/Edge rendering now covers Diagnostics State Artifact Summary in addition to Queue/Completed/Pending handoffs and API Contract Safety Review.
- The smoke renders backend `/api/diagnostics/state-summary`, verifies state recovery summary, backend read-order summary, read-order detail, artifact detail, read-first/open-next wording, and read-only guardrails.
- It clicks the backend-selected `last_stderr_log` triage row, uses the allowlisted tail action, then uses the allowlisted open action and verifies `diagnostics.open` command history.
- It clicks the `queue_snapshot` artifact row and verifies operational interpretation, recovery stage, unsafe-if-ignored, action plan, and read-only guardrail text.
- No launch, process, publish, drain, rename, settings save, arbitrary filesystem read, queue mutation, source/output/scratch mutation, Tk fallback, V4, or media policy behavior changed.

The next chunk should remain:

### Operator-Selected Real-Media Sample Execution

Run a small operator-approved sample batch and compare Queue route evidence, Completed proof, size policy, subtitle/audio decisions, Pending Publish posture, Diagnostics logs, and Sample Validation recording. This should remain observational first: do not change FFmpeg policy unless the pilot exposes a concrete mismatch.

### Diagnostics API Contract Safety Review

Completed:

- Added a read-only `Contract Safety Review` panel under Diagnostics API Contract.
- The panel derives route-surface posture from `/api/contract` and classifies auth coverage, mutation boundaries, shell-open boundaries, preview/dry-run boundaries, read-only contracts, contract completeness, and frontend ownership boundaries.
- The panel does not post command routes, open files, launch work, save settings, rename, drain/publish, change media policy, move backend authority into WebView, touch Tk fallback, touch V4, or mutate source/output/scratch paths.
- Extended `Test-WebViewBrowserDiagnosticsHandoffSmoke.ps1` to verify the contract safety summary/detail in real Chrome/Edge rendering while preserving the existing Queue/Completed/Pending Publish diagnostics handoff coverage.
- Updated static WebView coverage, smoke catalogs, mutation-boundary docs, coverage matrix, TLDR, parity matrix, and remediation changelog.

The next chunk should remain:

### Operator-Selected Real-Media Sample Execution

Run a small operator-approved sample batch and compare Queue route evidence, Completed proof, size policy, subtitle/audio decisions, Pending Publish posture, Diagnostics logs, and Sample Validation recording. This should remain observational first: do not change FFmpeg policy unless the pilot exposes a concrete mismatch.

### Queue/Completed/Pending Combined Row Review Plans

Completed:

- Queue selected-row details now build a combined review plan when launch blockers, fresh runtime failures, deferred checks, low-confidence TV parsing, and review flags overlap.
- Completed selected-row details now build a combined review plan when missing outputs, sidecar mismatches, size-growth outliers, fresh runtime issues, consistency failures, and review flags overlap.
- Pending Publish selected-row details now build a combined drain review plan when do-not-drain posture, diagnostic errors, missing payloads, missing sidecars, invalid manifests, orphan payloads, and row errors overlap.
- Each plan explicitly gives read-first evidence, cross-check evidence, decision guidance, and the read-only guardrail before launch, rerun, drain, cleanup, or acceptance decisions.
- Extended `Test-WebViewRowDetailSmoke.ps1`, `Test-WebViewBrowserDiagnosticsHandoffSmoke.ps1`, and static WebView coverage so the plans are verified in mocked DOM and real Chrome/Edge rendering.
- No launch, process, publish, drain, rename, settings save, queue mutation, source/output/scratch mutation, Tk fallback, V4, or media policy behavior changed.

The next chunk should remain:

### Operator-Selected Real-Media Sample Execution

Run a small operator-approved sample batch and compare Queue route evidence, Completed proof, size policy, subtitle/audio decisions, Pending Publish posture, Diagnostics logs, and Sample Validation recording. This should remain observational first: do not change FFmpeg policy unless the pilot exposes a concrete mismatch.

### Network Runtime State-File Evidence

Completed:

- `/api/network/workers` now includes backend-authored metadata for the coordinator in-flight registry, local worker state, and cluster log: path, present/missing/unreadable status, size, modified time, age, purpose, error, and read-only marker.
- The WebView Network page now has a selectable `Network Runtime State Files` panel with summary counts, read order, detail rows, and mutation guardrails.
- Network evidence and worker summaries now include compact state-file posture so the operator can see missing/unreadable runtime artifacts without opening raw files first.
- `Test-WebViewBrowserNetworkSmoke.ps1` now verifies the state-file panel and state-file detail in real Chrome/Edge rendering while preserving the no-lifecycle-mutation boundary.
- No coordinator/worker start/stop controls, queue mutation, settings save, media processing, Tk fallback, V4, or source/output/scratch behavior changed.

The next chunk should remain:

### Operator-Selected Real-Media Sample Execution

Run a small operator-approved sample batch and compare Queue route evidence, Completed proof, size policy, subtitle/audio decisions, Pending Publish posture, Diagnostics logs, and Sample Validation recording. This should remain observational first: do not change FFmpeg policy unless the pilot exposes a concrete mismatch.

### Sample Validation Pilot Evidence Packet

Completed:

- Added `desktop_sample_validation_evidence_packet.v1` to `/api/sample-validation/preview` and `/api/sample-validation/append` result payloads.
- The packet is backend-authored from the proposed record, current Queue/Completed/Pending/Diagnostics evidence, and append-readiness result. It summarizes sample identity, Queue route proof, Completed output/sidecar proof, Diagnostics/run-log proof, Pending Publish posture, playback/subtitle/audio/size proof, evidence-record readiness, stop conditions, row counts, and safe next action.
- Home Sample Validation preview renders the packet before append-readiness so a selected sample's proof posture is visible before any evidence note is recorded.
- Browser-backed coverage verifies packet rows, stop conditions, and the read-only guardrail in real Chrome/Edge rendering while still allowing only `/api/sample-validation/preview`.
- No validation append semantics, launch, process, publish, drain, rename, settings save, queue mutation, source/output/scratch mutation, Tk fallback, V4, or FFmpeg/media policy behavior changed.

The next chunk should remain:

### Operator-Approved Real-Media Pilot Run

Run a small operator-approved sample batch and compare Queue route evidence, Completed proof, size policy, subtitle/audio decisions, Pending Publish posture, Diagnostics logs, and Sample Validation recording. This should remain observational first: do not change FFmpeg policy unless the pilot exposes a concrete mismatch.

### Real-Media Validation Worksheet Packet Capture

Completed:

- Updated `New-RealMediaValidationWorksheet.ps1` so generated worksheets can prefill per-sample categories and expected routes in addition to source paths.
- Added `-QueueSnapshotPath` support to `New-RealMediaValidationWorksheet.ps1`. When provided, the helper reads an existing queue snapshot, matches worksheet sample paths to Queue rows, prefills route/reason/blocked/excluded/source-root evidence, records snapshot age, and reports match counts in `-PlanOnly` JSON.
- Added a `WebView Pilot Evidence Packet Capture` section to `Docs\sample-validation\REAL_MEDIA_VALIDATION_EVIDENCE_TEMPLATE.md` so Home -> Sample Validation -> Preview Record packet status, proof rows, stop-condition status, and safe next action can be copied before appending an evidence note.
- Hardened the helper with `PositionalBinding = $false` so additional sample paths cannot accidentally bind to unrelated positional parameters.
- Extended worksheet tests to prove `-PlanOnly` returns sample/category/route/queue-match JSON without writing, worksheet creation fills the new packet capture and Queue Evidence rows, and the helper remains Markdown-only with no process/media/publish/settings/rename behavior.
- No WebView route, validation append semantics, launch, process, publish, drain, rename, settings save, queue mutation, source/output/scratch mutation, Tk fallback, V4, or FFmpeg/media policy behavior changed.

The next chunk should remain:

### Operator-Approved Real-Media Pilot Run

Run a small operator-approved sample batch and compare Queue route evidence, Completed proof, size policy, subtitle/audio decisions, Pending Publish posture, Diagnostics logs, Sample Validation recording, and the generated worksheet's pilot-evidence-packet capture. This should remain observational first: do not change FFmpeg policy unless the pilot exposes a concrete mismatch.

### Progress Bars Production Readiness

Completed:

- Exported the progress-bar implementation queue; after P1-P7 completion it was archived at `Docs\archive\completed-checklists\V5_PROGRESS_BARS_PLAN.md`.
- P1 snapshot progress bars are complete: `/api/snapshot` exposes backend-authored `progress_bars` for current stage, run total, publish state, and audit progress, and the WebView Run Progress panel renders them above detailed progress evidence.
- P2 publish copy progress is complete: robocopy publish/drain copies now emit backend-owned byte telemetry from the staging file without changing copy/reveal ownership; pending-publish drain exposes `CurrentQueuePhase=pending_push` with item index/total; WebView snapshots can distinguish per-file `Publish copy` from `Pending publish total`.
- P3 startup progress is complete: Local API startup emits `desktop_startup_progress.v1` checkpoint payloads, Tauri requests startup-progress emission when launching the backend, `/api/health` and bootstrap can expose the latest startup progress, and WebView backend lifecycle detail renders startup checkpoint lines.
- P4 health-check progress is complete: Maintenance health exposes `desktop_maintenance_health_progress.v1`, `/api/maintenance/progress` returns the latest backend-authored stepped progress without running probes, and the WebView Maintenance panel polls that read-only progress route while the bounded health check runs.
- P5 worker/coordinator progress is complete: `/api/network/workers` exposes `desktop_network_worker_progress.v1` and shared progress bars for network mode, persisted coordinator worker rows, local worker state, heartbeat/stale posture, and pending done-report warnings. The WebView Workers page renders these bars without adding lifecycle controls.
- P6 audit reports progress is complete: `audit_progress.json` keeps scan `percent_complete` and now records backend-owned report-generation stage fields for classify, JSON, CSV, priority CSV, and text summary work. `/api/snapshot` emits both the scan bar and stepped `Audit reports` bar, and WebView renders audit progress on Dashboard, Launch/Audit, Reports, and Diagnostics.
- P7 queue refresh/source scan progress is complete: `/api/queue` now exposes backend-authored `desktop_queue_source_scan_progress.v1` through `queue_progress` and shared `progress_bars`, and the WebView Queue page renders the indeterminate source-scan bar without adding queue mutation authority.
- P7 subtitle conversion/OCR progress is complete: `pipeline_progress.json` now records `pipeline_subtitle_progress.v1` for ASS/TX3G/BDPGS extract, convert/OCR, validate, and sidecar-write stages, and `/api/snapshot` renders it as the shared stepped `subtitle_track` progress bar.
- P7 rename apply progress is complete: backend `rename.apply` success results now include `desktop_rename_apply_progress.v1` and a shared determinate `rename_apply` bar for renamed files versus planned/selected files, and the WebView Rename outcome review renders it from backend command evidence without moving filesystem mutation into the frontend.
- P7 settings save/reload progress is complete: backend Settings preview/save/reload results now expose stepped `desktop_settings_save_reload_progress.v1` or `desktop_settings_reload_progress.v1` evidence for preview, backup write, config write, reload, and loaded-config validation, and the WebView Settings save-result surface renders the shared bar from command evidence without adding frontend config persistence.
- P7 release package dry-run progress is complete: backend release dry-run results now expose `desktop_release_package_progress.v1` for layout, copy plan, manifest, validate, and optional-smoke posture, and the WebView Maintenance Release Check renders the shared `release_package` bar while preserving the dry-run/no-artifact-write boundary.
- P7 maintenance backfill progress is complete: completed-manifest backfill dry-run results now expose `desktop_maintenance_backfill_progress.v1` with scanned, would-write, written, and skipped record counts, and the WebView Maintenance Manifest Backfill panel renders the shared `maintenance_backfill` bar without adding manifest rewrite authority.
- P7 Completed/Pending inventory refresh progress is complete: Completed preview now exposes `desktop_completed_inventory_progress.v1`, Pending Publish preview now exposes `desktop_pending_publish_inventory_progress.v1`, and the WebView Completed/Pending panels render shared inventory bars from backend row-count evidence without changing filtering, accept, publish/drain, open, or manifest mutation authority.
- Validation passed for focused backend tests, PowerShell parse checks, contract schema checks, reliability regressions, Tauri shell build checks, local API help output, browser-backed smokes, root release self-test with tool integration/end-to-end media smoke skipped, and full `DesktopApp\tests` discovery (1200 tests).
- No frontend-owned filesystem mutation, queue mutation, publish/drain authority, backend policy bypass, Tk fallback behavior, V4 behavior, or FFmpeg media policy changed.

### Progress-bar status

P7 progress-bar implementation is complete. Next production-readiness work should start from the next active plan item or a new production-readiness plan; do not add frontend-owned mutation, queue mutation, publish/drain authority, settings persistence, rename filesystem mutation, or backend policy bypasses without an explicit plan update.
