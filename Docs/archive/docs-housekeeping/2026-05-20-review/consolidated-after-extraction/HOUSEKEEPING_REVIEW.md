# HOUSEKEEPING REVIEW

Date: 2026-05-19

Scope: pre-work housekeeping review of the V5 workspace. This pass did not delete, move, or rewrite code. The only intended change is this report.

Status update 2026-05-19: the superseded root housekeeping audit and execution checklist have been archived under `Docs\archive\admin-audits`; the stale root desktop-app log capture has been archived under ignored `RunLogs`; root `HOUSEKEEPING_REVIEW.md` remains the current housekeeping entry point.

## Executive Summary

V5 is not clutter-free, but the important media safety boundaries are mostly in the right places. PowerShell still owns route decisions, scratch-copy-first processing, FFmpeg/MKVToolNix execution, source identity, subtitle/audio policy, sidecar writing, pending publish, and output verification. The WebView mostly displays backend state and posts backend commands; it does not appear to duplicate core media execution policy.

The practical cleanup work should start with recovery/state placement and publish boundaries, not with visual polish. The highest-value housekeeping item is that rename undo manifests currently default to `%TEMP%` instead of `LocalBase\State`; rename is a real file mutation path, so its recovery evidence should be durable and visible with the rest of runtime state. The next priority is to keep pending-publish sidecar behavior tightly owned and covered by focused tests before any future publish/drain changes.

The repo also has obvious non-source clutter: root/DesktopApp API logs, Tauri `node_modules` and `src-tauri\target`, `.pytest_cache`, a very large remediation changelog, large WebView/test files, and several active docs that still embed local machine paths or historical handoff package names. Those do not look like immediate media-loss bugs, but they make future Codex work riskier by increasing search noise and creating multiple "current" narratives.

## Top 10 Cleanup Priorities

| Rank | ID | Risk | Disposition | File path(s) | What found | Why it matters | Recommended cleanup action |
|---:|---|---|---|---|---|---|---|
| 1 | HK-SAFE-01 | High | Fix now | `DesktopApp\mediapipeline_desktop_app\service_rename_apply.py`, `DesktopApp\mediapipeline_desktop_app\service_rename.py`, `DesktopApp\mediapipeline_desktop_app\service_rename_apply_runner.py` | `write_rename_undo_manifest()` defaults to `%TEMP%\MediaPipelineRemuxEncodeAIO\RenameUndo`; `service_rename.py` calls it without a state-root argument. | Rename mutates media names and sidecars. If undo evidence lives in temp, restart/recovery and Diagnostics can lose the operator's recovery trail. | Move the default rename undo root under `LocalBase\State\RenameUndo` through resolved paths, keep a compatibility fallback only when state is unavailable, and test restart visibility. |
| 2 | HK-SAFE-02 | High | Fix now before publish work | `Pipeline\Modules\PendingTransactions.ps1`, `PendingPush.ps1`, `PendingManifestStore.ps1`, `PendingPublishIndex.ps1`, `PublishCompletion.ps1`, `Publish.Partial.ps1` | Pending publish media-plus-sidecar logic is split across several modules and is safety-critical. Existing tests cover many contracts, but the ownership boundary is easy to violate during edits. | A small future change in the wrong module could publish partial outputs, drop sidecars, or discard parked artifacts. | Add a short ownership note to the module map and add focused tests for sidecar rollback, parked sidecar recovery, and "no discard on weak identity" before refactoring these files. |
| 3 | HK-SAFE-03 | Medium | Fix now | `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\settingsView.js`, `launchView.risk.js`, `settingsMetadata.js`, `application\settings_risk_policy.py` | Frontend contains advisory source-mutation and media-policy risk logic for `DeleteSourceAfterProcessing`, `ReprocessAll`, subtitles, and route settings. It says backend preview/save remains authoritative, but duplicated advisory logic is broad. | Future agents may accidentally turn advisory UI checks into policy decisions or let UI readiness override backend validation. | Keep the frontend wording as advisory, add/keep tests that backend preview/save is authoritative, and avoid adding any media-policy decision to WebView files. |
| 4 | HK-SAFE-04 | Medium | Fix now before portable packaging | `Pipeline\Audit-MediaLibrary_chatgpt.ps1`, `Pipeline\MediaPipelineRemuxEncodeAIO_LegacyGUI.ps1` | Active scripts still contain hardcoded `\\LAYNE-SERVER\Video` defaults. | The V5 bundle should be portable and config-driven. Hardcoded operator paths can mislead future work or accidentally scan the wrong library. | Replace script defaults with config-derived or empty defaults, leaving examples in docs/templates only. |
| 5 | HK-SAFE-05 | Medium | Fix now | `DesktopApp\encode_speed_history.json`, `DesktopApp\mediapipeline_desktop_app\controllers\completed_analytics_controller.py` | Runtime analytics state exists in `DesktopApp\` root. Controller writes `app_state_path.parent\encode_speed_history.json`. | Runtime state should be centered under `LocalBase\State`; state in the app tree is easy to ship, archive, or edit accidentally. | Move encode speed history under `LocalBase\State\App` or the resolved app-state directory; migrate old root file once. |
| 6 | HK-MAINT-01 | Medium | Defer with guardrails | `DesktopApp\tests\test_application_facade.py`, `Pipeline\Tests\Invoke-ReliabilityRegressionChecks.ps1`, `DesktopApp\mediapipeline_desktop_app\ui_web\static\index.html`, `settingsView.js`, `queueView.js` | Several files remain very large: `test_application_facade.py` 9,183 lines, reliability regression 6,545 lines, `index.html` 4,867 lines, `settingsView.js` 3,873 lines, `queueView.js` 3,194 lines. | Oversized files increase merge risk and make future agents likely to patch the wrong responsibility. | Continue the god-file split, but only by stable ownership: route/API tests, browser smokes, settings builders, queue commands, and static HTML sections. |
| 7 | HK-DOC-01 | Medium | Completed 2026-05-20 | `Docs\CURRENT_PROJECT_STATE.md`, `OPEN_WORK_CHECKLIST.md`, `Docs\archive\historical-plans\*`, compatibility redirect stubs | Active docs now have one current-state source and one active checklist. The prior active-fix checklist, Tauri transition current plan, transition status board, and transition-review fix checklist bodies were archived under `Docs\archive\historical-plans\`; old paths now redirect. | Future agents can start from one state doc and one backlog instead of chasing stale local evidence or historical package logs. | Keep `CURRENT_PROJECT_STATE.md` and `OPEN_WORK_CHECKLIST.md` as the canonical active pair; update redirect stubs only if the canonical pair changes. |
| 8 | HK-HYGIENE-01 | Low | Mostly complete; live app log deferred | Root generated `*.log`/`*.out.log`/`*.err.log`/`*.stdout.log`/`*.stderr.log`/`*.jsonl`, `DesktopApp\local_api_*`, `DesktopApp\_codex_*`, `DesktopApp\RunLogs\*` | The stale root desktop-app log capture is archived; `.gitignore` and `Invoke-RepoHygieneChecks.ps1` now block root log/jsonl captures and DesktopApp root API validation captures. Live `DesktopApp\MediaPipelineRemuxEncodeAIO_DesktopApp.log` remains ignored and untouched while API processes may own it. | Search results become noisy, and generated evidence can be mistaken for source or documentation. | Keep proof logs under `RunLogs`; do not move active `DesktopApp\*.log` while a desktop/API process may be writing it. |
| 9 | HK-HYGIENE-02 | Low | Delete/rebuild when not actively building | `DesktopApp\tauri_shell\node_modules`, `DesktopApp\tauri_shell\src-tauri\target` | Rebuildable Tauri artifacts are present in the source tree. `.gitignore` excludes them, but they still clutter local scans and package reviews. | They inflate searches and can hide generated files in review output. | Keep only when actively building Tauri. Otherwise delete locally and rely on `npm install`/`cargo build` to restore. |
| 10 | HK-DOC-02 | Low | Partially complete / defer | `Docs\archive\admin-audits\HOUSEKEEPING_AUDIT_REPORT.md`, `Docs\archive\admin-audits\HOUSEKEEPING_EXECUTION_CHECKLIST.md`, `V5_TRANSITION_CODE_REVIEW.md`, `V5_TRANSITION_REVIEW_FIX_CHECKLIST.md`, `Docs\REMEDIATION_CHANGELOG.md` | Superseded housekeeping reports are now archived; transition reports and the 31,318-line changelog remain prominent. | Multiple old reports compete with current work and lengthen searches. | Keep archived housekeeping records out of root navigation; defer transition-report archival and changelog rollover until remaining items are marked closed, deferred, or superseded. |

## Safety Risks

| ID | Risk level | Disposition | File path(s) | What found | Why it matters | Recommended cleanup action |
|---|---|---|---|---|---|---|
| HK-SAFE-01 | High | Fix now | `DesktopApp\mediapipeline_desktop_app\service_rename_apply.py:98`, `service_rename.py:386`, `service_rename_apply_runner.py:32` | Rename undo manifest defaults to temp storage and the service wrapper does not pass a state root. | Rename is destructive-adjacent. Recovery records should survive restarts and be visible in Diagnostics/State. | Route undo manifests to `LocalBase\State\RenameUndo`, migrate existing temp manifests if present, and add tests proving the manifest path is state-rooted. |
| HK-SAFE-02 | High | Fix now before publish work | `Pipeline\Modules\PendingTransactions.ps1`, `PendingPush.ps1`, `PendingManifestStore.ps1`, `PendingPublishIndex.ps1`, `PublishCompletion.ps1` | Pending publish owns media plus sidecars through multiple modules. The split is reasonable, but the responsibility map is not obvious from filenames alone. | Deferred publish is a safety feature. Confusing ownership can produce false processing failures, dropped sidecars, or partial drain behavior. | Add an ownership header/table and focused regression tests around parked media plus sidecars, rollback, and missing manifest/orphan rows. |
| HK-SAFE-03 | Medium | Fix now | `DesktopApp\mediapipeline_desktop_app\ui_web\static\assets\settingsView.js:1502`, `settingsView.js:2054`, `launchView.risk.js:613`, `application\settings_risk_policy.py:298` | WebView advisory logic describes source deletion, subtitle drop, route, and publish risks. Backend policy exists, but the UI duplicates substantial warning logic. | WebView must display/backend-preview policy, not become policy. Duplicate advisory logic is a future drift risk. | Add comments/tests naming these helpers as advisory only. Keep backend preview/save as the only authority for accepting settings. |
| HK-SAFE-04 | Medium | Fix now before packaging | `Pipeline\Audit-MediaLibrary_chatgpt.ps1:3`, `Pipeline\MediaPipelineRemuxEncodeAIO_LegacyGUI.ps1:1167` | Audit defaults point at `\\LAYNE-SERVER\Video`. | Portable bundles should not include local operator paths in executable defaults. | Use config or blank defaults; keep local examples only in docs or sample config. |
| HK-SAFE-05 | Medium | Fix now | `DesktopApp\encode_speed_history.json`, `DesktopApp\mediapipeline_desktop_app\controllers\completed_analytics_controller.py:59` | Runtime analytics state can sit in the app source folder. | State outside `LocalBase\State` can be packaged, deleted during cleanup, or desynchronized from runtime state. | Move to resolved app state. Add migration and a unit test that no root `DesktopApp\encode_speed_history.json` is created for new state. |
| HK-SAFE-06 | Low | Keep, add focused tests when touched | `Pipeline\Modules\SourceIdentity.ps1`, `Pipeline\Tests\Invoke-ReliabilityRegressionChecks.ps1:777`, `:853`, `DesktopApp\tests\test_webview_row_detail_smoke.py` | Source identity, same-leaf duplicate hints, and completed/pending correlation are covered by broad tests. | Already-processed decisions must not rely only on extension or same leaf. This currently has guardrails, but they live mostly in large test files. | Do not change source identity or completed matching without splitting focused tests for exact identity, same-leaf advisory matches, and extension-change cases. |

## Maintainability Issues

| ID | Risk level | Disposition | File path(s) | What found | Why it matters | Recommended cleanup action |
|---|---|---|---|---|---|---|
| HK-MAINT-01 | Medium | Defer with guardrails | `DesktopApp\tests\test_application_facade.py`, `Pipeline\Tests\Invoke-ReliabilityRegressionChecks.ps1` | The two largest safety test files are 9,183 and 6,545 lines. | Large tests are hard to run selectively and encourage regex-style assertions instead of focused behavior checks. | Split by contract area: API routes, command journal, pending publish, route planning, source identity, settings, and WebView boundaries. |
| HK-MAINT-02 | Medium | Continue planned split | `DesktopApp\mediapipeline_desktop_app\ui_web\static\index.html`, `settingsView.js`, `queueView.js`, `pendingPublishView.js`, `diagnosticsView.js`, `app.js` | WebView files remain large even after recent split work. | UI edits can accidentally cross evidence/interactive boundaries or command ownership. | Continue splitting by page subsection and command/evidence ownership. Require inventory checks after each split. |
| HK-MAINT-03 | Medium | Defer | `Pipeline\MediaPipeline_chatgpt.ps1`, `Pipeline\Modules\*.ps1` | Main pipeline is now a coordinator, but `Do-Remux` and `Do-Encode` remain high-density orchestration. | Splitting these hastily could damage safety. Leaving them unowned also raises future edit risk. | Keep `Do-Remux`/`Do-Encode` intact until there is a tested extraction plan. Move only pure helpers with tests. |
| HK-MAINT-04 | Low | Keep but label clearly | `Pipeline\MediaPipelineRemuxEncodeAIO_LegacyGUI.ps1` | Legacy GUI/V4 fallback lives in the V5 pipeline folder. | It is useful as fallback but can confuse V5/Tauri ownership searches. | Add a top-level legacy/fallback note and exclude it from V5 WebView/Tauri search checklists unless explicitly reviewing fallback behavior. |
| HK-MAINT-05 | Low | Defer | `Pipeline\Tools\MKVToolNix\doc\*.html`, bundled runtimes/tools | Large bundled docs and runtimes dominate file-size scans. | They are expected for portability, but they hide app-owned large files. | Keep bundled executables. Consider excluding bundled tool docs from source scans or release packages if not needed at runtime. |

## Documentation/MD Cleanup

| ID | Risk level | Disposition | File path(s) | What found | Why it matters | Recommended cleanup action |
|---|---|---|---|---|---|---|
| HK-DOC-01 | Medium | Completed 2026-05-20 | `Docs\CURRENT_PROJECT_STATE.md`, `OPEN_WORK_CHECKLIST.md`, `Docs\archive\historical-plans\*`, redirect stubs at prior active paths | Active docs previously included competing status/checklist files and long historical evidence blocks. The long bodies are now archived; prior paths redirect to the canonical current-state doc and active checklist. | Future agents need one current target, not multiple historical anchors. | Keep active docs concise. Add new active tasks only to `OPEN_WORK_CHECKLIST.md`; preserve run-specific evidence in `Docs\RealMediaValidationRuns` or archives. |
| HK-DOC-02 | Low | Archived 2026-05-19 | `Docs\archive\admin-audits\HOUSEKEEPING_AUDIT_REPORT.md`, `Docs\archive\admin-audits\HOUSEKEEPING_EXECUTION_CHECKLIST.md` | Prior housekeeping reports are stale relative to the 2026-05-19 god-file split work and new artifacts, so they were moved out of the root. | Root stale reports competed with the new review. | Keep these as historical archive evidence; use root `HOUSEKEEPING_REVIEW.md` for active housekeeping work. |
| HK-DOC-03 | Low | Partially complete | `Docs\proposals\GOD_FILE_SPLIT_PLAN.md`, `Docs\archive\completed-checklists\GOD_FILE_SPLIT_PLAN.md`, `Docs\archive\completed-checklists\GOD_FILE_SPLIT_WAVE6_PLAN.md`, `Docs\proposals\CODE_MANAGEMENT_CLEANUP_PLAN.md` | The completed god-file split plans are archived, with a short status stub left at the old main path for AI directive compatibility. `CODE_MANAGEMENT_CLEANUP_PLAN.md` remains active for Wave B/C cleanup. | Completed chunks can look like future work if status is unclear. | Keep completed split plans archived; continue using the code-management plan for follow-on cleanup. |
| HK-DOC-04 | Low | Defer | `Docs\ui\Refactoring UI Reference Text.pdf`, `Docs\ui\V5_UI_Refactoring_Suggestions.md`, `Docs\ui\V5_UI_DESIGN_REFERENCE.md` | UI reference material is large and overlaps with active V5 design docs. | Agents may follow suggestions over the canonical design reference. | Keep `V5_UI_DESIGN_REFERENCE.md` as source of truth. Treat refactoring material as advisory and archive or externalize the large PDF after useful notes are extracted. |
| HK-DOC-05 | Low | Keep but roll over | `Docs\REMEDIATION_CHANGELOG.md` | Changelog is 31,318 lines. | It is valuable evidence, but too large for routine review. | Roll into dated archive chunks and keep a short current changelog. |

## Generated Files or Repo Hygiene Issues

| ID | Risk level | Disposition | File path(s) | What found | Why it matters | Recommended cleanup action |
|---|---|---|---|---|---|---|
| HK-HYGIENE-01 | Low | Mostly complete; live app log deferred | Root generated log/jsonl captures and DesktopApp root API validation captures | Generated local API logs can live at repo root and DesktopApp root after validation runs. The stale root desktop-app log capture was archived and the repo hygiene guard now fails on root log/jsonl captures plus DesktopApp root `local_api_*`/`_codex_*` captures. | They are not source and increase search noise. | Keep validation logs under `RunLogs`; leave live `DesktopApp\MediaPipelineRemuxEncodeAIO_DesktopApp.log` alone while API/desktop processes may be active. |
| HK-HYGIENE-02 | Low | Delete/rebuild when not actively building | `DesktopApp\tauri_shell\node_modules`, `DesktopApp\tauri_shell\src-tauri\target` | Rebuildable build artifacts are present. | They clutter scans and can accidentally enter ad hoc package copies. | Remove locally before broad scans or release packaging; rebuild as needed. `.gitignore` already excludes them. |
| HK-HYGIENE-03 | Low | Delete | `.pytest_cache` | Test cache exists in the workspace. | Cache files should not be reviewed as project source. | Delete when doing cleanup; `.gitignore` already excludes it. |
| HK-HYGIENE-04 | Low | Keep with release policy | `Pipeline\Tools\ffmpeg`, `Pipeline\Tools\MKVToolNix`, `Pipeline\PowerShell-7.6.0-win-x64`, `DesktopApp\Runtime\Python` | Bundled runtime/tools are intentionally large. | They are part of the portable operating model. | Keep them. Exclude generated caches/docs from reviews, not the tools themselves. |

## Test Coverage Gaps

| ID | Risk level | Disposition | File path(s) | What found | Why it matters | Recommended cleanup action |
|---|---|---|---|---|---|---|
| HK-TEST-01 | High | Fix now with HK-SAFE-01 | `DesktopApp\tests\test_service_rename_apply.py`, `DesktopApp\tests\test_rename_service.py` | Tests cover rename undo mechanics, but the service default still writes to temp. | The test suite should enforce the V5 state-root operating model. | Add a test that service rename apply writes undo manifests under resolved `LocalBase\State\RenameUndo`. |
| HK-TEST-02 | High | Fix before publish edits | `Pipeline\Tests\Invoke-ReliabilityRegressionChecks.ps1`, new focused pending publish tests | Pending publish has broad coverage, but much of it is inside the monolithic reliability script. | Publish/drain bugs are high impact and need fast focused checks. | Split focused tests for parked media plus sidecars, orphan manifest rows, rollback after sidecar reveal failure, weak source identity, and low-space deferred publish. |
| HK-TEST-03 | Medium | Fix now | New repo hygiene test or script | No small test/check appears to fail on root `*.out.log`/`*.err.log` artifacts or generated Tauri build folders. | Generated clutter keeps returning after local API proof runs. | Add a non-mutating hygiene check that reports root logs, `.pytest_cache`, `node_modules`, and `src-tauri\target` before release or handoff. |
| HK-TEST-04 | Medium | Partially complete | `Pipeline\Tests\Unit\Invoke-ActiveDocsReferenceChecks.ps1` | High-level status/checklist docs can drift back to absolute local current-handoff paths. | Docs can misdirect implementation even when code is correct. | The active-docs guard now blocks absolute local current-handoff paths in the high-level current-state/status/checklist docs; broader historical evidence cleanup remains deferred. |
| HK-TEST-05 | Medium | Defer | `Pipeline\Tests\Invoke-ReliabilityRegressionChecks.ps1` | Several boundary checks are regex assertions against source text. | Regex tests can pass while behavior changes, or fail during safe refactors. | Preserve regex guards but add focused behavior tests for route planning, source identity, subtitle routing, and FFmpeg wrapper contracts. |

## Suggested Archive/Delete/Keep Decisions

| Item | Decision | Reason |
|---|---|---|
| `Docs\archive\admin-audits\HOUSEKEEPING_AUDIT_REPORT.md`, `Docs\archive\admin-audits\HOUSEKEEPING_EXECUTION_CHECKLIST.md` | Keep archived | Superseded by this review, but useful historical evidence. |
| `V5_TRANSITION_CODE_REVIEW.md`, `V5_TRANSITION_REVIEW_FIX_CHECKLIST.md` | Keep for now | User explicitly deferred some items; archive only after the remaining items are marked deferred/superseded. |
| `Docs\archive\completed-checklists\GOD_FILE_SPLIT_PLAN.md`, `Docs\archive\completed-checklists\GOD_FILE_SPLIT_WAVE6_PLAN.md` | Keep archived | Completed split execution evidence; active `Docs\proposals\GOD_FILE_SPLIT_PLAN.md` is only a status stub for older references. |
| `Docs\active-plans\V5_TAURI_TRANSITION_CURRENT_PLAN.md` | Redirect stub | Long body archived at `Docs\archive\historical-plans\V5_TAURI_TRANSITION_CURRENT_PLAN_20260520_ARCHIVED.md`; current state is `Docs\CURRENT_PROJECT_STATE.md`. |
| `Docs\active-plans\V5_TRANSITION_STATUS_BOARD.md` | Redirect stub | Long body archived at `Docs\archive\historical-plans\V5_TRANSITION_STATUS_BOARD_20260520_ARCHIVED.md`; current status is `Docs\CURRENT_PROJECT_STATE.md` plus root `OPEN_WORK_CHECKLIST.md`. |
| `Docs\RealMediaValidationRuns\*.md` | Keep, excluded from shared commits by policy | These are evidence records with personal/local paths. |
| Root generated `*.log`, `*.out.log`, `*.err.log`, `*.stdout.log`, `*.stderr.log`, `*.jsonl` and DesktopApp root API validation captures | Delete or archive | Generated run evidence should live under `RunLogs` or an archive, not source roots; live `DesktopApp\MediaPipelineRemuxEncodeAIO_DesktopApp.log` is ignored and should be moved only when no process owns it. |
| `.pytest_cache` | Delete | Rebuildable cache. |
| `DesktopApp\tauri_shell\node_modules`, `DesktopApp\tauri_shell\src-tauri\target` | Delete when not actively building | Rebuildable and already ignored. |
| Bundled FFmpeg, PowerShell, Python, MKVToolNix | Keep | Required by the Windows-first portable bundle model. |
| `Docs\ui\Refactoring UI Reference Text.pdf` | Defer/externalize | Large advisory reference. Keep until useful notes are extracted, then consider external storage or archive. |

## Recommended Module Ownership Map

| Area | Owner file(s) | Boundary rule |
|---|---|---|
| Route decision and remux/encode choice | `Pipeline\Modules\Routing.ps1`, `Pipeline\Modules\PipelineProcessing.ps1`, `Pipeline\Modules\PipelineEngine.ps1` | Backend-owned. WebView may display route evidence only. |
| FFmpeg/ffprobe/MKVToolNix execution | `Pipeline\Modules\Native.ps1`, `NativeProcessContracts.ps1`, `FfmpegProgress.ps1`, `MediaProbe.ps1` | Tool wrappers execute and report; they should not own media policy. |
| Scratch copy and source protection | `Pipeline\Modules\ScratchCopy.ps1`, `Disk.ps1`, `SourceIdentity.ps1` | Source media is copied to scratch first and never mutated by default. |
| Audio/subtitle policy | `Pipeline\Modules\Audio.ps1`, `Subtitles.Common.ps1`, `Subtitles.Builders.ps1`, `Subtitles.*.ps1` | Backend policy only. UI can preview settings and display decisions. |
| Output path and sidecars | `Pipeline\Modules\OutputPathPlanning.ps1`, `Sidecar.ps1`, `PublishCompletion.ps1`, `Publish.Result.ps1`, `Publish.Sidecars.ps1` | Backend writes manifests/sidecars and final output evidence. |
| Pending/deferred publish | `PendingPush.ps1`, `PendingTransactions.ps1`, `PendingManifestStore.ps1`, `PendingPublishIndex.ps1`, `Publish.Partial.ps1` | Treat parked output as media plus sidecars. Drain scope is backend-authored. |
| Queue preview and launch | `Pipeline\Modules\QueuePlan.ps1`, `DesktopApp\mediapipeline_desktop_app\application\facade_process.py`, `api\command_payloads_process.py` | Queue/launch preflight display backend plans; `/api/pipeline/start` owns execution commands. |
| Rename | `DesktopApp\mediapipeline_desktop_app\service_rename*.py`, `application\facade_rename*.py`, `api\command_payloads_rename.py` | Mutating rename must require backend preview, confirmation, undo manifest, command result, and tests. |
| Settings/config | `Pipeline\MediaPipeline_config_chatgpt.psd1`, `MediaPipeline_config_template.psd1`, `DesktopApp\application\facade_settings_patch_policy.py`, `service_config_save_runner.py` | Backend validates/saves. WebView staging is advisory until backend preview/save. |
| Diagnostics/open/tail | `application\facade_diagnostics_policy.py`, `api\command_payloads_files.py`, Diagnostics WebView assets | Backend allowlists paths. Frontend sends target keys/row keys only. |
| WebView UI | `DesktopApp\mediapipeline_desktop_app\ui_web\static\index.html`, `assets\*.js`, `styles*.css` | Control and monitoring surface only. No backend media policy. |
| Tauri shell | `DesktopApp\tauri_shell\src-tauri`, `DesktopApp\mediapipeline_desktop_app\local_api_main.py` | Shell lifecycle and local API bridge only; no media policy. |
| Network worker mode | `DesktopApp\mediapipeline_desktop_app\network\*.py`, `views\network_tab.py`, `networkView.js` | Coordinator/worker lifecycle remains backend/Tk-owned unless new routes are designed and tested. |

## Final Implementation Checklist

1. Safety state cleanup - fix now before new features.
   - Scope: rename undo and app runtime analytics state.
   - Likely files: `service_rename.py`, `service_rename_apply.py`, `service_rename_apply_runner.py`, `completed_analytics_controller.py`, related tests.
   - Validation: `python -m unittest DesktopApp.tests.test_service_rename_apply DesktopApp.tests.test_rename_service DesktopApp.tests.test_controllers -q`.
   - Expected evidence: undo manifests and encode speed history resolve under `LocalBase\State`, old root/temp files migrate or remain read-only fallback.
   - Rollback risk: Medium because rename is mutating; keep old temp fallback during migration.
   - Promotion timing: Before daily-driver promotion.

2. Pending publish ownership guard - fix before any publish/drain edits.
   - Scope: document module ownership and add focused behavior tests.
   - Likely files: `Pipeline\Modules\Pending*.ps1`, `Publish*.ps1`, `Pipeline\Tests`.
   - Validation: `Pipeline\Tests\Invoke-ReliabilityRegressionChecks.ps1` plus new focused pending-publish tests.
   - Expected evidence: parked media plus sidecars are preserved, rollback restores sidecars, weak identity does not discard parked output.
   - Rollback risk: Low if tests/docs only.
   - Promotion timing: Before daily-driver promotion if publish/drain will be used heavily.

3. Repo artifact cleanup - fix now after approval.
   - Scope: archive/delete generated logs, `.pytest_cache`, Tauri generated build folders when not active.
   - Likely files: root logs, `DesktopApp\local_api_*.log`, `DesktopApp\RunLogs`, `.gitignore`.
   - Validation: non-mutating hygiene scan reports no root generated logs and no rebuildable Tauri artifacts unless explicitly allowed.
   - Expected evidence: searches return source/docs, not run output.
   - Rollback risk: Low if logs are archived first.
   - Promotion timing: Before packaging/handoff.

4. Active docs consolidation - completed 2026-05-20.
   - Scope: `Docs\CURRENT_PROJECT_STATE.md` is the current state doc, root `OPEN_WORK_CHECKLIST.md` is the active checklist, and historical plan/checklist bodies moved to `Docs\archive\historical-plans\`.
   - Compatibility stubs remain at `Docs\ACTIVE_FIX_CHECKLIST.md`, `Docs\active-plans\V5_TAURI_TRANSITION_CURRENT_PLAN.md`, `Docs\active-plans\V5_TRANSITION_STATUS_BOARD.md`, and `V5_TRANSITION_REVIEW_FIX_CHECKLIST.md`.
   - Validation: active-docs reference guard and targeted source-of-truth scans should pass.
   - Expected evidence: new agents see one current plan and one backlog.
   - Rollback risk: Low.
   - Promotion timing: Completed before daily-driver promotion.

5. Large-file split continuation - defer until safety cleanup is complete.
   - Scope: split large UI/test files by ownership without changing behavior.
   - Likely files: `index.html`, `settingsView.js`, `queueView.js`, `test_application_facade.py`, `Invoke-ReliabilityRegressionChecks.ps1`.
   - Validation: JS syntax, WebView mutation-boundary tests, route inventory tests, browser smokes, PowerShell parser/import checks.
   - Expected evidence: smaller files, no DOM/global/route drift except documented changes.
   - Rollback risk: Medium because broad splits can break load order.
   - Promotion timing: Some before promotion if it reduces safety risk; polish splits can wait.

6. Portable path cleanup - fix before packaged handoff.
   - Scope: remove hardcoded local defaults from active scripts and legacy GUI defaults.
   - Likely files: `Audit-MediaLibrary_chatgpt.ps1`, `MediaPipelineRemuxEncodeAIO_LegacyGUI.ps1`, docs/examples.
   - Validation: parser checks plus hardcoded-path scan excluding archived evidence and tests.
   - Expected evidence: executable defaults are config-driven or blank.
   - Rollback risk: Low to Medium; audit UX changes need a clear empty state.
   - Promotion timing: Before portable package promotion.

7. Documentation/reference slimming - defer.
   - Scope: roll over `REMEDIATION_CHANGELOG.md`, archive old reports, externalize large advisory UI references after extraction.
   - Likely files: `Docs\REMEDIATION_CHANGELOG.md`, root review reports, `Docs\ui`.
   - Validation: `DOCS_INDEX.md`, `ARCHIVED_MD_INDEX.md`, and `DOC_TOUCH_LOG.md` updated.
   - Expected evidence: active docs are shorter and unambiguous.
   - Rollback risk: Low.
   - Promotion timing: After safety and packaging cleanup.
