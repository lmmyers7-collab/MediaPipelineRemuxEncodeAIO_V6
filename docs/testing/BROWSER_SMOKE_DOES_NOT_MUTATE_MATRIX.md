# Browser Smoke "Does Not Mutate" Matrix

Date: 2026-05-18

Provides explicit mutation-boundary guarantees for all WebView smoke wrappers. Each row states what the smoke exercises and what it explicitly does not do. Browser smokes are authorized only against their generated disposable roots and temporary local API instances; this matrix is not permission to point them at a live/operator backend.

---

## Smoke Wrapper Tiers

**Non-browser smokes** — use bundled Python only, no Chrome/Edge required. Suitable for all CI environments.

**Browser-backed smokes** — require Chrome or Edge. A direct Python module may report `SkipTest` when a prerequisite is absent. Canonical PowerShell wrappers fail that prerequisite skip by default; `-AllowSkippedTests` is an explicit non-gating exception.

---

## Non-Browser Smokes (8 wrappers)

### Test-WebViewCommandEvidenceSmoke.ps1

| | |
|---|---|
| **Exercises** | Backend-served WebView JavaScript evaluated via Node with mocked DOM state. Verifies shared command owner/issue command history rendering across daily-use panels. |
| **Does not** | Launch pipeline, process media, publish, rename files, save settings, mutate queue state, drain pending publish, touch source/output/scratch paths, or make any filesystem change. |
| **Requires** | Bundled Python, Node.js. |
| **Skip behavior** | N/A — no browser required. |

### Test-WebViewRowDetailSmoke.ps1

| | |
|---|---|
| **Exercises** | Backend-served WebView JavaScript with mocked DOM selected-row state. Verifies Queue, Completed, and Pending Publish row detail plus Selected Row At A Glance summaries and diagnostics handoff text, including adversarial blocked/missing/do-not-drain rows and combined read-first/cross-check/decision plans for overlapping review signals. |
| **Does not** | Launch, process media, publish, rename, save settings, mutate queue state, or touch source/output/scratch paths. |
| **Requires** | Bundled Python, Node.js. |

### Test-WebViewRenameReadinessSmoke.ps1

| | |
|---|---|
| **Exercises** | Rename WebView assets in Node with mocked DOM state. Verifies Apply Readiness, immediate mocked apply progress, Apply Outcome Review, Undo Last Apply post shape, 260-row render-cap disclosure, and a blocked duplicate-target scope. |
| **Does not** | Call backend `rename.apply`/`rename.undo` against real files, rename files, save settings, process media, mutate queue state, or touch source/output/scratch paths. |
| **Requires** | Bundled Python, Node.js. |

### Test-WebViewSettingsLaunchPolicySmoke.ps1

| | |
|---|---|
| **Exercises** | Read-only WebView Settings and Launch policy handoff visibility using generated temporary state. Verifies media-policy readiness rows are displayed correctly. |
| **Does not** | Launch pipeline work, process media, publish, rename, save settings, or mutate source/output/scratch paths. |
| **Requires** | Bundled Python. |

### Test-WebViewSettingsLaunchLiveConfigSmoke.ps1

| | |
|---|---|
| **Exercises** | Reads current saved config and reports backend media-policy readiness via a temporary local API. |
| **Does not** | Launch work, save settings, publish, rename, or process media. Read-only against the current config. |
| **Requires** | Bundled Python. |

### Test-WebViewSettingsPatchEvidenceSmoke.ps1

| | |
|---|---|
| **Exercises** | Backend Preview Patch, denied Save Patch, confirmed Save Patch, reload evidence, and command history against a **generated temporary config** (not the live config). |
| **Does not** | Touch the current saved config or media. All writes target a temp config that is discarded after the test. |
| **Requires** | Bundled Python. |

### Test-WebViewScheduleSmoke.ps1

| | |
|---|---|
| **Exercises** | Schedule WebView assets. Verifies coverage review, selected-day detail rendering, and read-only schedule mutation boundaries. |
| **Does not** | Save the schedule, launch pipeline work, process media, publish, rename, or touch source/output/scratch paths. |
| **Requires** | Bundled Python, Node.js. |

### Test-WebViewRealMediaEvidenceSmoke.ps1

| | |
|---|---|
| **Exercises** | Real-media evidence panel visibility. Starts a temporary local API against generated temporary state. Verifies settings-launch policy handoff display. |
| **Does not** | Process media, launch pipeline commands, publish, rename, save settings, or modify source/output/scratch media. |
| **Requires** | Bundled Python. |

---

## Browser-Backed Smokes (25 canonical browser wrappers / 34 browser Python modules)

All browser-backed smokes start a temporary local API and open the backend-served WebView in installed Chrome/Edge headless. The 25 canonical browser wrappers cover 25 wrapper-backed browser Python modules; the generated smoke-wrapper map also identifies 9 direct-only browser Python modules, for 34 browser Python modules total. Direct modules may skip when a prerequisite is absent, while canonical wrappers fail prerequisite skips unless explicitly invoked with `-AllowSkippedTests`.

As of 2026-05-20, every fixture-backed browser smoke captures a SHA-256/size snapshot of media, subtitle, pending-publish sidecar, manifest, and JSONL evidence artifacts under its temporary fixture root after setup and compares it again before fixture cleanup. This converts the "does not mutate source/output/scratch paths" claim into executable evidence for the Chrome/Edge smoke layer while still allowing command-history or app-state writes that a specific smoke intentionally exercises.

### Test-WebViewBrowserHighRiskSmoke.ps1

| | |
|---|---|
| **Exercises** | Injected + backend-produced blocked Queue rows, broken Completed rows, and do-not-drain Pending Publish row guidance. Verifies correct rendering and warning text in Chrome/Edge. |
| **Does not** | Launch, process media, publish, rename, save settings, mutate queue state, drain pending publish, or touch source/output/scratch paths. |
| **Skip** | Direct module may report `SkipTest`; canonical wrapper fails the prerequisite skip unless `-AllowSkippedTests` was explicit. |

### Test-WebViewBrowserScheduleSmoke.ps1

| | |
|---|---|
| **Exercises** | Drives real backend-served Schedule Editor preview/save controls and Launch timing trust under Chrome/Edge. Confirms schedule app-state writes stay backend-owned and limited to schedule keys. |
| **Does not** | Process media, launch pipeline commands, publish, rename files, save settings, mutate queue state, or touch source/output/scratch paths. |
| **Skip** | Direct module may report `SkipTest`; canonical wrapper fails the prerequisite skip unless `-AllowSkippedTests` was explicit. |

### Test-WebViewBrowserLifecycleSmoke.ps1

| | |
|---|---|
| **Exercises** | Drives real backend-served Diagnostics backend lifecycle controls in blocked and safe close-readiness states. Verifies watcher-armed shutdown remains disabled/local-only and safe shutdown posts only backend-owned `/api/backend/shutdown` after confirmation. |
| **Does not** | Process media, launch pipeline commands, publish, rename files, save settings, mutate queue state, drain pending publish, close a real encode process, or touch source/output/scratch paths. |
| **Skip** | Direct module may report `SkipTest`; canonical wrapper fails the prerequisite skip unless `-AllowSkippedTests` was explicit. |

### Test-WebViewBrowserDiagnosticsHandoffSmoke.ps1

| | |
|---|---|
| **Exercises** | Clicks actual Queue/Completed/Pending table rows; verifies selected-row investigation signals, combined row review plans, and filter visibility; verifies text/status/investigation filters warn when blocked/warning rows are hidden; verifies clear-filter buttons restore visibility; clicks diagnostics bridge, bounded tail, and allowlisted open controls; verifies Diagnostics First Response Checklist summary plus selectable row detail, ActiveJobs active/malformed rows, and stale-progress guidance; verifies Diagnostics State Artifact Summary read-order/artifact detail and allowlisted tail/open actions; verifies Diagnostics `Go To Owner Row` handoff for all three pages; renders the API Contract Safety Review from `/api/contract`. |
| **Does not** | Launch, process media, publish, rename, save settings, mutate queue state, post command routes from the contract safety panel, or touch source/output/scratch paths. `Go To Owner Row` is local UI selection only - no backend call. |
| **Skip** | Direct module may report `SkipTest`; canonical wrapper fails the prerequisite skip unless `-AllowSkippedTests` was explicit. |

### Test-WebViewBrowserLargeTableSmoke.ps1

| | |
|---|---|
| **Exercises** | Injects 260-row Queue, Completed, and Pending Publish payloads. Verifies 250-row render cap disclosure; verifies filter warnings when blocked/warning rows are hidden; verifies Queue Launch Decision filter-scope evidence plus Queue Backend Launch Scope Preview and Pending Backend Drain Scope Preview; verifies hidden selected-row detail and Selected Row At A Glance summaries remain visible; proves no mutation routes are posted. |
| **Does not** | Launch, process media, drain pending publish, publish, rerun, rename, save settings, mutate queue state, or touch source/output/scratch paths. |
| **Skip** | Direct module may report `SkipTest`; canonical wrapper fails the prerequisite skip unless `-AllowSkippedTests` was explicit. |

### Test-WebViewBrowserMaintenanceReportsSmoke.ps1

| | |
|---|---|
| **Exercises** | Renders Maintenance health/readiness, release dry-run result output, completed-manifest backfill dry-run result output, dry-run history, Reports failure/audit triage, grouped failure resolution, More actions, marker clear preview/confirm, evidence archive preview/confirm, selected failure/audit row evidence, and Diagnostics handoff navigation. |
| **Does not** | Launch, process media, run audit, run CSV rerun, execute release packaging, rewrite completed manifests, publish, rename, save settings, mutate queue state outside allowlisted Reports cleanup routes, or touch source/output/scratch paths. |
| **Skip** | Direct module may report `SkipTest`; canonical wrapper fails the prerequisite skip unless `-AllowSkippedTests` was explicit. |

### Test-WebViewBrowserMaintenanceChangeLedgerSmoke.ps1

| | |
|---|---|
| **Exercises** | Renders the Maintenance Change Ledger summary, table, selected detail, changelog hygiene, affected Python-script detail, status/search filters, empty state, and read-only `GET /api/maintenance/change-ledger` usage. |
| **Does not** | Edit change packets, regenerate changelog docs, run health probes, launch, process media, run audit, run CSV rerun, drain pending publish, publish, rename, save settings, mutate queue state, post media/queue/settings/pending-publish/rename mutation routes, or touch source/output/scratch paths. |
| **Skip** | Direct module may report `SkipTest`; canonical wrapper fails the prerequisite skip unless `-AllowSkippedTests` was explicit. |

### Test-WebViewBrowserSampleValidationSmoke.ps1

| | |
|---|---|
| **Exercises** | Renders Home Sample Validation pilot checkpoint/attention/readiness/reconciliation text, renders the backend-authored operator sample execution checklist and generated pilot worksheet table, verifies selected-sample worksheet matching, verifies the Real-Media Validation Worksheet repeats Sample Validation posture in Chrome/Edge, fills manual acceptance-checklist items, and executes only `/api/sample-validation/preview` to verify current-evidence, pilot evidence packet, and append-readiness/manual-check gap result rendering. |
| **Does not** | Append validation records, accept outputs, clear failures, launch, process media, run audit, run CSV rerun, drain pending publish, publish, rename, save settings, mutate queue state, or touch source/output/scratch paths. |
| **Skip** | Direct module may report `SkipTest`; canonical wrapper fails the prerequisite skip unless `-AllowSkippedTests` was explicit. |

### Test-WebViewBrowserHomeLiveStateSmoke.ps1

| | |
|---|---|
| **Exercises** | Renders Home Daily-Driver Checklist, Operator Readiness, Active Work, Live Progress Details/Evidence, Diagnostics runtime progress, Command Results, Sample Validation posture, generated worksheet readback, and Real-Media Validation Worksheet handoff in Chrome/Edge against temporary backend state, generated active-progress state, a generated ActiveJobs record, and a generated command journal. |
| **Does not** | Send POST routes, append validation records, accept outputs, clear failures, launch, process media, run audit, run CSV rerun, drain pending publish, publish, rename, save settings, mutate queue state, or touch source/output/scratch paths. |
| **Skip** | Direct module may report `SkipTest`; canonical wrapper fails the prerequisite skip unless `-AllowSkippedTests` was explicit. |

### Test-WebViewBrowserSafeOperatorCommandsSmoke.ps1

| | |
|---|---|
| **Exercises** | Physically activates the Home sample-validation preview/append controls, Metrics registry/cache controls, and Maintenance support/release/backfill/dependency-atlas controls against backend-authored fixtures. All permitted evidence, cache, export, and release-fixture writes are confined to a newly generated temporary LocalBase/state/config root and their exact route results are asserted. |
| **Does not** | Use personal configuration or operator roots; mutate source/output/scratch/pending-publish/final-library media; start pipeline, audit, rerun, publish, rename, repair, or network lifecycle work; or treat fake picker/shell routing as proof of a genuine Windows dialog/external application outcome. Media/sidecar hashes and forbidden-route observations remain unchanged. |
| **Skip** | Direct module may report `SkipTest`; canonical wrapper fails the prerequisite skip unless `-AllowSkippedTests` was explicit and emits a machine-readable prerequisite result. |

### Test-WebViewBrowserLaunchQueueReadinessSmoke.ps1

| | |
|---|---|
| **Exercises** | Renders Launch readiness, Launch timing trust, Launch Scope Reconciliation, Launch Start Decision Summary, Launch Real-Media Sample Proof Handoff mirrored from Home worksheet evidence, Launch generated-worksheet selected-sample match detail, Launch Sample Validation record selected-sample match/reconciliation detail, Launch Sample Execution Checklist mirrored from Home sample-validation execution guidance, backend Launch preflight from `GET /api/launch/preflight`, Queue Launch Decision checklist, Schedule guidance/timing trust, close-readiness, and launch command-review correlation in Chrome/Edge against temporary backend state, generated launch command history, and a temporary validation record. |
| **Does not** | Send POST routes, launch, process media, run audit, run CSV rerun, drain pending publish, publish, rename, save settings, mutate queue state, or touch source/output/scratch paths. |
| **Skip** | Direct module may report `SkipTest`; canonical wrapper fails the prerequisite skip unless `-AllowSkippedTests` was explicit. |

### Test-WebViewBrowserLayoutManagerSmoke.ps1

| | |
|---|---|
| **Exercises** | Opens the WebView Layout Editor drawer in Chrome/Edge and verifies representative Queue, Completed, Settings, Diagnostics, Launch, and Reports boxes are listed and can be locally reordered, hidden/gated, previewed, and reset without exposing inactive subtabs inline. |
| **Does not** | Send POST routes, launch, process media, run audit, run CSV rerun, drain pending publish, publish, rename, save settings, mutate queue state, or touch source/output/scratch paths. |
| **Skip** | Direct module may report `SkipTest`; canonical wrapper fails the prerequisite skip unless `-AllowSkippedTests` was explicit. |

### Test-WebViewBrowserRenameSmoke.ps1

| | |
|---|---|
| **Exercises** | Clicks the Rename Browse Files control through a stubbed backend browse response, stages selected paths without apply, clicks Rename preview rows and Check Applicable Rows, verifies Apply Readiness, Apply Outcome Review, Undo Last Apply visibility, 260-row render-cap disclosure, and duplicate-target apply blocking. |
| **Does not** | Call backend `rename.apply`/`rename.undo` against real files, rename files, save settings, process media, launch pipeline commands, publish, mutate queue state, or touch source/output/scratch paths. |
| **Skip** | Direct module may report `SkipTest`; canonical wrapper fails the prerequisite skip unless `-AllowSkippedTests` was explicit. |

### Test-WebViewBrowserNetworkSmoke.ps1

| | |
|---|---|
| **Exercises** | Read-only Network readiness and lifecycle handoff; renders backend-authored runtime state-file evidence and persisted worker rows; selects lifecycle, state-file, and worker detail; verifies local worker filters warn when active/problem rows are hidden. |
| **Does not** | Start or stop coordinator or workers, process media, launch pipeline commands, publish, rename, save settings, mutate queue state, or touch source/output/scratch paths. The smoke exercises read-only Network runtime/lifecycle evidence and does not click Worker Mode Settings save. |
| **Skip** | Direct module may report `SkipTest`; canonical wrapper fails the prerequisite skip unless `-AllowSkippedTests` was explicit. |

### Test-WebViewBrowserTelemetrySmoke.ps1

| | |
|---|---|
| **Exercises** | Fixture telemetry: verifies zero-percent NVENC remains visible without duplicate idle wording; verifies GPU detail row synthesis; verifies CPU/RAM-only fallback wording. |
| **Does not** | Sample the local GPU, process media, launch pipeline commands, publish, rename, save settings, mutate queue state, or touch source/output/scratch paths. |
| **Skip** | Direct module may report `SkipTest`; canonical wrapper fails the prerequisite skip unless `-AllowSkippedTests` was explicit. |

### Test-WebViewBrowserSettingsLaunchSmoke.ps1

| | |
|---|---|
| **Exercises** | Drives Settings and Launch controls; verifies staged settings patch handoff, Settings Effective Policy Trust, selectable Launch Risk Handoff proof-chain detail, and Settings-to-Launch intent; verifies Preview Patch is called; cancels Save Patch; confirms cancellation is visible; verifies Save Patch is not posted. |
| **Does not** | Save settings, process media, launch pipeline commands, publish, rename files, mutate queue state, or touch source/output/scratch paths. |
| **Skip** | Direct module may report `SkipTest`; canonical wrapper fails the prerequisite skip unless `-AllowSkippedTests` was explicit. |

### Test-WebViewBrowserLibraryProfilesSaveSmoke.ps1

| | |
|---|---|
| **Exercises** | Drives the Libraries page add/save flow in a real browser; verifies read-only LibraryProfile identity, backend preview before confirmation, save-patch `review_confirmation`, reload digest verification, and reloaded temp config state. |
| **Does not** | Process media, launch pipeline commands, publish, rename files, mutate queue state, drain pending publish, or touch source/output/scratch paths. Config writes are limited to the generated temp backend and media fixture hashes are checked. |
| **Skip** | Direct module may report `SkipTest`; canonical wrapper fails the prerequisite skip unless `-AllowSkippedTests` was explicit. |

### Test-WebViewBrowserPendingDrainGuardSmoke.ps1

| | |
|---|---|
| **Exercises** | Injects a backend-shaped blocked recovery dry-run result; verifies Publish Button Guard refreshes immediately; clicks `Publish Parked Outputs`; proves the blocked click records local `frontend_guard` evidence without posting `/api/pipeline/start`. |
| **Does not** | Launch, process media, drain pending publish, publish, rename, save settings, mutate queue state, or touch source/output/scratch paths. |
| **Skip** | Direct module may report `SkipTest`; canonical wrapper fails the prerequisite skip unless `-AllowSkippedTests` was explicit. |

### Test-WebViewBrowserCompletedPendingProofSmoke.ps1

| | |
|---|---|
| **Exercises** | Completed-to-Pending proof detail for exact output-to-destination overlap; Completed Real-Media Output Proof Sample Validation handoff; selected Pending row Completed Manifest correlation; missing-output-without-proof blocker detail; same-leaf proof vs. duplicate-title guidance. |
| **Does not** | Launch, process media, drain pending publish, publish, rename, save settings, mutate queue state, or touch source/output/scratch paths. |
| **Skip** | Direct module may report `SkipTest`; canonical wrapper fails the prerequisite skip unless `-AllowSkippedTests` was explicit. |

### Test-WebViewBrowserLifecycleReconciliationSmoke.ps1

| Boundary | Guarantee |
|---|---|
| **Exercises** | Lifecycle reconciliation preview/apply confirmation, archive evidence, and recovery rendering against generated stale ActiveJobs/process fixtures. |
| **Does not** | Inspect, stop, archive, or reconcile operator/live processes or runtime state; process media; launch pipeline work; publish; rename; save live config; or touch source/output/scratch paths. Reconciliation and archive writes are confined to the disposable fixture root. |
| **Skip** | Direct module may report `SkipTest`; canonical wrapper fails the prerequisite skip unless `-AllowSkippedTests` was explicit. |

### Test-WebViewBrowserQueueFileOverridesSmoke.ps1

| Boundary | Guarantee |
|---|---|
| **Exercises** | Queue File Settings drawer feedback, dirty-state discard, clear-fields payload, full-clear confirmation, series preview, and failed-save alert tone. |
| **Does not** | Persist queue or file overrides. Mutation POSTs are intercepted inside the browser harness; no source, output, scratch, media, manifest, sidecar, or live state is changed. |
| **Skip** | Direct module may report `SkipTest`; canonical wrapper fails the prerequisite skip unless `-AllowSkippedTests` was explicit. |

### Test-WebViewBrowserQueueLaunchCompletedSmoke.ps1

| Boundary | Guarantee |
|---|---|
| **Exercises** | Queue-loaded backend-confirmed idle state with no active monitor claims; authoritative Backend Queue Run Once launch with two uncapped accepted rows, accepted fingerprint/run identity, production duplicate/lifecycle rejection, real `/api/run-monitor` transitions from starting through terminal review/completion, all-worker display, route-authority labels, focus/keyboard/live-announcement behavior, exact Completed artifact-row focus, fresh idle, and terminal reload persistence. |
| **Does not** | Read or mutate operator/live roots. All Queue, command-journal, Run Monitor, progress, failure, Completed-manifest, fake-output, and sidecar writes are limited to a generated disposable root; fixture hashes prove source-like inputs remain unchanged, and no FFmpeg/remux/encode processing runs. |
| **Skip** | Direct module may report `SkipTest`; canonical wrapper fails the prerequisite skip unless `-AllowSkippedTests` was explicit. |

### Test-WebViewBrowserSettingsFieldMatrixSmoke.ps1

| Boundary | Guarantee |
|---|---|
| **Exercises** | Every structured Settings field by control type, inherited Library Profile reset behavior, strict save confirmation, reload persistence, and command-journal evidence. |
| **Does not** | Read or save live config; process media; mutate queue/publish/rename state; or touch source/output/scratch paths. Confirmed config writes are confined to generated temporary config/state. |
| **Skip** | Direct module may report `SkipTest`; canonical wrapper fails the prerequisite skip unless `-AllowSkippedTests` was explicit. |

### Test-WebViewBrowserProseBoxAudit.ps1

| Boundary | Guarantee |
|---|---|
| **Exercises** | Primary page/subtab screenshot manifest and visible prose/status/diagnostic box audit. |
| **Does not** | Submit mutation routes or change media, sidecars, manifests, queue, config, publish, rename, or operator state. Screenshots and manifests are written only under the disposable evidence directory. |
| **Skip** | Direct module may report `SkipTest`; canonical wrapper fails the prerequisite skip unless `-AllowSkippedTests` was explicit. |

### Test-WebViewBrowserVisualClutterScreenshots.ps1

| Boundary | Guarantee |
|---|---|
| **Exercises** | Desktop/mobile screenshot manifest and visible evidence-prose clutter/overflow audit. |
| **Does not** | Submit mutation routes or change media, sidecars, manifests, queue, config, publish, rename, or operator state. Screenshots and manifests are written only under the disposable evidence directory. |
| **Skip** | Direct module may report `SkipTest`; canonical wrapper fails the prerequisite skip unless `-AllowSkippedTests` was explicit. |

---

## Consolidated Mutation Guarantee

Every smoke in this matrix guarantees:

| Action | Production/operator boundary | Permitted disposable-fixture behavior |
|---|---|---|
| Process real media (FFmpeg encode/remux) | Never | Never |
| Launch pipeline (`/api/pipeline/start`) | Never | Queue→Launch→Completed smoke may exercise a synthetic backend start wholly inside its disposable root |
| Save config (`/api/settings/save-patch`) | Never against live config | Settings patch, Library Profiles save, and Settings field-matrix smokes may write generated temporary config |
| Rename files (`/api/rename/apply`, `/api/rename/undo`) | Never | Current browser smokes do not apply/undo rename |
| Drain / publish pending outputs | Never | Current browser smokes do not drain/publish |
| Write source, output, or scratch paths | Never | Fixture source-like artifacts are hash-guarded and remain unchanged |
| Runtime/evidence state writes | Never against operator state | Declared temporary writes include schedule app state, failure marker/evidence archive, lifecycle reconciliation archive, queue state, command journal, completed manifest, and output sidecar |
| Screenshots / audit manifests | Never in operator roots | Prose/visual audits write only to their disposable evidence directory |
| Undeclared route or filesystem mutation | Never | Never |

Fixture-backed browser smokes capture SHA-256/size snapshots of watched media, subtitle, pending-publish sidecar, manifest, and JSONL evidence artifacts after setup and compare them before cleanup. A smoke's row above must name every allowed temporary mutation; absence from the allowlist is a failure.

---

## Skip vs. Fail

| Invocation | Result | Gating meaning |
|---|---|---|
| Direct Python module reports `SkipTest` | Module may exit without assertions | Not a pass; prerequisite missing |
| Canonical wrapper, default | Converts prerequisite skip to non-zero failure | Gating failure |
| Canonical wrapper with explicit `-AllowSkippedTests` | Preserves non-gating skip | Environmental evidence only; not a pass |
| Canonical wrapper completes assertions with exit `0` | Test passed | Positive browser evidence |
| Any non-`0` assertion/runtime error | Test failed | Review runner and browser exception detail |

---

## What Smokes Do Not Prove

- That real media is routed, encoded, or remuxed correctly
- That subtitle OCR produces correct SRT output
- That audio policy is applied correctly during an actual pipeline run
- That the Completed manifest is written correctly
- That Pending Publish drains or publishes correctly
- That rename produces correct final file names on disk
- That the backend produces the correct config after a real save

For real-media proof, see `docs/sample-validation/REAL_MEDIA_PILOT_CHECKLIST.md`.

---

## See Also

- Smoke test catalog: `docs/testing/WEBVIEW_SMOKE_TEST_CATALOG.md`
- Browser prerequisites: `docs/testing/BROWSER_SMOKE_PREREQUISITES_CHECKLIST.md`
- Browser runbook: `docs/testing/BROWSER_SMOKE_TEST_RUNBOOK.md`
- Smoke result template: `docs/testing/WEBVIEW_SMOKE_RESULT_TEMPLATE.md`

---

## Freshness Review — 2026-05-15 (CLN3-013)

Historical note: this 2026-05-15 review counted 15 wrappers (up from 13 at that time). The authoritative current count is the 25 canonical browser wrappers / 34 browser Python modules inventory at the top of this document.

At that review point, the matrix covered these then-current additions:
- `Test-WebViewBrowserLaunchQueueReadinessSmoke.ps1`: explicitly does not send POST routes during Launch readiness/worksheet/record/scope-reconciliation rendering.
- `Test-WebViewBrowserSampleValidationSmoke.ps1`: exercises only `/api/sample-validation/preview`; does not append records.
- `Test-WebViewBrowserHomeLiveStateSmoke.ps1`: sends no POST routes during Home live-state rendering.
- `Test-WebViewBrowserPendingDrainGuardSmoke.ps1`: proves `frontend_guard` evidence is recorded without posting `/api/pipeline/start`.
- `Test-WebViewBrowserCompletedPendingProofSmoke.ps1`: all Completed/Pending proof panels verified read-only.

The consolidated mutation table has since been replaced by the current per-scenario disposable-write allowlist above.

```
Task ID: CLN3-013
Files inspected: docs\testing\BROWSER_SMOKE_DOES_NOT_MUTATE_MATRIX.md, ops/scripts/smoke/Test-WebViewBrowser*.ps1 (count check)
Files changed: docs\testing\BROWSER_SMOKE_DOES_NOT_MUTATE_MATRIX.md (header corrected: 13→15; freshness note added)
Validation: Get-ChildItem -File -Filter "Test-WebViewBrowser*.ps1" | Select-Object Name; Select-String -Path docs\testing\BROWSER_SMOKE_DOES_NOT_MUTATE_MATRIX.md -Pattern "Does not|POST|mutation"
Findings: Header was stale (13); corrected to 15. All 15 browser smoke entries present and accurate.
Open questions: None.
Risk: Low — documentation only.
```

---

## Freshness Review — 2026-05-15 (CLN4-008)

Checked whether the Consolidated Mutation Guarantee table and per-smoke entries accurately reflect the two new scope preview panels (`Queue Backend Launch Scope Preview`, `Pending Backend Drain Scope Preview`).

**Finding**: Matrix is already accurate. The `Test-WebViewBrowserLargeTableSmoke.ps1` entry explicitly names both panels in its **Exercises** row: "verifies Queue Launch Decision filter-scope evidence plus Queue Backend Launch Scope Preview and Pending Backend Drain Scope Preview." Both panels are read-only evidence renders — they issue no POST routes. The Consolidated Mutation Guarantee table remains fully accurate for both panels (no new routes added).

No changes required to matrix content.

```
Task ID: CLN4-008
Files inspected: docs\testing\BROWSER_SMOKE_DOES_NOT_MUTATE_MATRIX.md (LargeTable entry, Consolidated Mutation Guarantee table)
Files changed: docs\testing\BROWSER_SMOKE_DOES_NOT_MUTATE_MATRIX.md (CLN4-008 freshness note added)
Validation: Select-String -Path docs\testing\BROWSER_SMOKE_DOES_NOT_MUTATE_MATRIX.md -Pattern "Backend Launch Scope Preview|Backend Drain Scope Preview"
Findings: Both scope preview panels already named in LargeTable smoke entry. Matrix is accurate and complete.
Open questions: None.
Risk: Low — documentation only.
```

---

## Freshness Review — 2026-05-18 (Browser Smoke Media Hash Assertions)

All 16 fixture-backed browser smoke Python implementations now call `capture_media_no_mutation_snapshot(root)` after temporary fixture setup and `assert_media_no_mutation(self, media_snapshot)` before the temp root is removed. The shared helper watches media extensions, subtitle sidecars, `.pipeline.json`, `.manifest.json`, and `.jsonl` evidence/manifest files by size and SHA-256.

```
Task ID: transition checklist chunk 9
Files inspected: tests/python/desktop/test_webview_browser_*.py, tests/python/desktop/webview_browser_smoke_support.py
Files changed: docs/testing/BROWSER_SMOKE_DOES_NOT_MUTATE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest discover -s tests\python\desktop -p "test_webview_browser_*.py" -q
Findings: 20 browser smoke tests passed with media/sidecar/manifest hash no-mutation assertions active.
Open questions: None.
Risk: Low — tests/docs only; fixture roots are temporary.
```

---

## Freshness Review - 2026-05-20 (Layout Manager Browser Smoke)

Added `Test-WebViewBrowserLayoutManagerSmoke.ps1` and `test_webview_browser_layout_manager_smoke.py` to verify customize-mode move handles across page tabs, subtabs, and generated subsections without backend mutation. Browser-backed wrapper count is now 16.

```
Task ID: Layout manager movable tab/subtab boxes
Files inspected: tests/python/desktop/test_webview_browser_layout_manager_smoke.py, ops/scripts/smoke/Test-WebViewBrowserLayoutManagerSmoke.ps1, apps/desktop/webview/static/assets/app.js
Files changed: docs/testing/BROWSER_SMOKE_DOES_NOT_MUTATE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest tests.webview.test_webview_browser_layout_manager_smoke -q
Findings: Layout-manager smoke uses the shared Chrome/Edge CDP runner and media/sidecar/manifest hash guard; no POST routes or source/output/scratch mutations are expected.
Open questions: None.
Risk: Low - WebView layout personalization only.
```


---

## Current Inventory Review — 2026-07-13

- Confirmed 25 canonical browser wrappers and 34 browser Python modules (25 wrapper-backed and 9 direct-only); `docs/generated/SMOKE_WRAPPER_MAP.json` is the disk-derived inventory.
- Added lifecycle reconciliation, Queue file overrides, Queue→Launch→Completed, Settings field matrix, Prose Box, and Visual Clutter boundaries.
- Replaced blanket “does not mutate” language with exact disposable-root allowlists.
- Canonical wrappers fail prerequisite skips by default; `-AllowSkippedTests` is an explicit non-gating exception.
