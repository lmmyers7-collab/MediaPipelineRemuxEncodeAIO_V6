# Browser Smoke "Does Not Mutate" Matrix

Date: 2026-05-18

Provides explicit mutation-boundary guarantees for all WebView smoke wrappers. Each row states what the smoke exercises AND what it explicitly does not do. Use this when verifying that a smoke run is safe to execute against a live backend or when interpreting a smoke result.

---

## Smoke Wrapper Tiers

**Non-browser smokes** — use bundled Python only, no Chrome/Edge required. Suitable for all CI environments.

**Browser-backed smokes** — require Chrome or Edge. Skip cleanly (exit 0) when no browser is installed. A skip is not a failure.

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
| **Exercises** | Rename WebView assets in Node with mocked DOM state. Verifies Apply Readiness and Apply Outcome Review for a ready single-row scope, 260-row render-cap disclosure, and a blocked duplicate-target scope. |
| **Does not** | Call `rename.apply`, rename files, save settings, process media, mutate queue state, or touch source/output/scratch paths. |
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

## Browser-Backed Smokes (16 wrappers)

All browser-backed smokes: start a temporary local API, open a backend-served WebView page in installed Chrome/Edge headless, and exit 0 (skip) cleanly when no browser is installed.

As of 2026-05-20, every fixture-backed browser smoke captures a SHA-256/size snapshot of media, subtitle, pending-publish sidecar, manifest, and JSONL evidence artifacts under its temporary fixture root after setup and compares it again before fixture cleanup. This converts the "does not mutate source/output/scratch paths" claim into executable evidence for the Chrome/Edge smoke layer while still allowing command-history or app-state writes that a specific smoke intentionally exercises.

### Test-WebViewBrowserHighRiskSmoke.ps1

| | |
|---|---|
| **Exercises** | Injected + backend-produced blocked Queue rows, broken Completed rows, and do-not-drain Pending Publish row guidance. Verifies correct rendering and warning text in Chrome/Edge. |
| **Does not** | Launch, process media, publish, rename, save settings, mutate queue state, drain pending publish, or touch source/output/scratch paths. |
| **Skip** | Exits 0 (SkipTest) when Chrome/Edge not installed. |

### Test-WebViewBrowserScheduleSmoke.ps1

| | |
|---|---|
| **Exercises** | Drives real backend-served Schedule Editor preview/save controls and Launch timing trust under Chrome/Edge. Confirms schedule app-state writes stay backend-owned and limited to schedule keys. |
| **Does not** | Process media, launch pipeline commands, publish, rename files, save settings, mutate queue state, or touch source/output/scratch paths. |
| **Skip** | Exits 0 when Chrome/Edge not installed. |

### Test-WebViewBrowserLifecycleSmoke.ps1

| | |
|---|---|
| **Exercises** | Drives real backend-served Diagnostics backend lifecycle controls in blocked and safe close-readiness states. Verifies watcher-armed shutdown remains disabled/local-only and safe shutdown posts only backend-owned `/api/backend/shutdown` after confirmation. |
| **Does not** | Process media, launch pipeline commands, publish, rename files, save settings, mutate queue state, drain pending publish, close a real encode process, or touch source/output/scratch paths. |
| **Skip** | Exits 0 when Chrome/Edge not installed. |

### Test-WebViewBrowserDiagnosticsHandoffSmoke.ps1

| | |
|---|---|
| **Exercises** | Clicks actual Queue/Completed/Pending table rows; verifies selected-row investigation signals, combined row review plans, and filter visibility; verifies text/status/investigation filters warn when blocked/warning rows are hidden; verifies clear-filter buttons restore visibility; clicks diagnostics bridge, bounded tail, and allowlisted open controls; verifies Diagnostics First Response Checklist summary plus selectable row detail, ActiveJobs active/malformed rows, and stale-progress guidance; verifies Diagnostics State Artifact Summary read-order/artifact detail and allowlisted tail/open actions; verifies Diagnostics `Go To Owner Row` handoff for all three pages; renders the API Contract Safety Review from `/api/contract`. |
| **Does not** | Launch, process media, publish, rename, save settings, mutate queue state, post command routes from the contract safety panel, or touch source/output/scratch paths. `Go To Owner Row` is local UI selection only - no backend call. |
| **Skip** | Exits 0 when Chrome/Edge not installed. |

### Test-WebViewBrowserLargeTableSmoke.ps1

| | |
|---|---|
| **Exercises** | Injects 260-row Queue, Completed, and Pending Publish payloads. Verifies 250-row render cap disclosure; verifies filter warnings when blocked/warning rows are hidden; verifies Queue Launch Decision filter-scope evidence plus Queue Backend Launch Scope Preview and Pending Backend Drain Scope Preview; verifies hidden selected-row detail and Selected Row At A Glance summaries remain visible; proves no mutation routes are posted. |
| **Does not** | Launch, process media, drain pending publish, publish, rerun, rename, save settings, mutate queue state, or touch source/output/scratch paths. |
| **Skip** | Exits 0 when Chrome/Edge not installed. |

### Test-WebViewBrowserMaintenanceReportsSmoke.ps1

| | |
|---|---|
| **Exercises** | Renders Maintenance health/readiness, release dry-run result output, completed-manifest backfill dry-run result output, dry-run history, Reports failure/audit triage, failure-marker clear dry-run preview, selected failure/audit row details, and read-only Launch/Diagnostics handoff navigation. |
| **Does not** | Launch, process media, run audit, run CSV rerun, execute release packaging, rewrite completed manifests, publish, rename, save settings, mutate queue state, post non-dry-run backend mutation routes, or touch source/output/scratch paths. |
| **Skip** | Exits 0 when Chrome/Edge not installed. |

### Test-WebViewBrowserMaintenanceChangeLedgerSmoke.ps1

| | |
|---|---|
| **Exercises** | Renders the Maintenance Change Ledger summary, table, selected detail, changelog hygiene, affected Python-script detail, status/search filters, empty state, and read-only `GET /api/maintenance/change-ledger` usage. |
| **Does not** | Edit change packets, regenerate changelog docs, run health probes, launch, process media, run audit, run CSV rerun, drain pending publish, publish, rename, save settings, mutate queue state, post media/queue/settings/pending-publish/rename mutation routes, or touch source/output/scratch paths. |
| **Skip** | Exits 0 when Chrome/Edge not installed. |

### Test-WebViewBrowserSampleValidationSmoke.ps1

| | |
|---|---|
| **Exercises** | Renders Home Sample Validation pilot checkpoint/attention/readiness/reconciliation text, renders the backend-authored operator sample execution checklist and generated pilot worksheet table, verifies selected-sample worksheet matching, verifies the Real-Media Validation Worksheet repeats Sample Validation posture in Chrome/Edge, fills manual acceptance-checklist items, and executes only `/api/sample-validation/preview` to verify current-evidence, pilot evidence packet, and append-readiness/manual-check gap result rendering. |
| **Does not** | Append validation records, accept outputs, clear failures, launch, process media, run audit, run CSV rerun, drain pending publish, publish, rename, save settings, mutate queue state, or touch source/output/scratch paths. |
| **Skip** | Exits 0 when Chrome/Edge not installed. |

### Test-WebViewBrowserHomeLiveStateSmoke.ps1

| | |
|---|---|
| **Exercises** | Renders Home Daily-Driver Checklist, Operator Readiness, Active Work, Live Progress Details/Evidence, Diagnostics runtime progress, Command Results, Sample Validation posture, generated worksheet readback, and Real-Media Validation Worksheet handoff in Chrome/Edge against temporary backend state, generated active-progress state, a generated ActiveJobs record, and a generated command journal. |
| **Does not** | Send POST routes, append validation records, accept outputs, clear failures, launch, process media, run audit, run CSV rerun, drain pending publish, publish, rename, save settings, mutate queue state, or touch source/output/scratch paths. |
| **Skip** | Exits 0 when Chrome/Edge not installed. |

### Test-WebViewBrowserLaunchQueueReadinessSmoke.ps1

| | |
|---|---|
| **Exercises** | Renders Launch readiness, Launch timing trust, Launch Scope Reconciliation, Launch Start Decision Summary, Launch Real-Media Sample Proof Handoff mirrored from Home worksheet evidence, Launch generated-worksheet selected-sample match detail, Launch Sample Validation record selected-sample match/reconciliation detail, Launch Sample Execution Checklist mirrored from Home sample-validation execution guidance, backend Launch preflight from `GET /api/launch/preflight`, Queue Launch Decision checklist, Schedule guidance/timing trust, close-readiness, and launch command-review correlation in Chrome/Edge against temporary backend state, generated launch command history, and a temporary validation record. |
| **Does not** | Send POST routes, launch, process media, run audit, run CSV rerun, drain pending publish, publish, rename, save settings, mutate queue state, or touch source/output/scratch paths. |
| **Skip** | Exits 0 when Chrome/Edge not installed. |

### Test-WebViewBrowserLayoutManagerSmoke.ps1

| | |
|---|---|
| **Exercises** | Opens the WebView Layout Editor drawer in Chrome/Edge and verifies representative Queue, Completed, Settings, Diagnostics, Launch, and Reports boxes are listed and can be locally reordered, hidden/gated, previewed, and reset without exposing inactive subtabs inline. |
| **Does not** | Send POST routes, launch, process media, run audit, run CSV rerun, drain pending publish, publish, rename, save settings, mutate queue state, or touch source/output/scratch paths. |
| **Skip** | Exits 0 when Chrome/Edge not installed. |

### Test-WebViewBrowserRenameSmoke.ps1

| | |
|---|---|
| **Exercises** | Clicks the Rename Browse Files control through a stubbed backend browse response, stages selected paths without apply, clicks Rename preview rows and Check Applicable Rows, verifies Apply Readiness and Apply Outcome Review, verifies 260-row render-cap disclosure, and verifies duplicate-target apply blocking. |
| **Does not** | Call `rename.apply`, rename files, save settings, process media, launch pipeline commands, publish, mutate queue state, or touch source/output/scratch paths. |
| **Skip** | Exits 0 when Chrome/Edge not installed. |

### Test-WebViewBrowserNetworkSmoke.ps1

| | |
|---|---|
| **Exercises** | Read-only Network readiness and lifecycle handoff; renders backend-authored runtime state-file evidence and persisted worker rows; selects lifecycle, state-file, and worker detail; verifies local worker filters warn when active/problem rows are hidden. |
| **Does not** | Start or stop coordinator or workers, process media, launch pipeline commands, publish, rename, save settings, mutate queue state, or touch source/output/scratch paths. The smoke exercises read-only Network runtime/lifecycle evidence and does not click Worker Mode Settings save. |
| **Skip** | Exits 0 when Chrome/Edge not installed. |

### Test-WebViewBrowserTelemetrySmoke.ps1

| | |
|---|---|
| **Exercises** | Fixture telemetry: verifies zero-percent NVENC remains visible without duplicate idle wording; verifies GPU detail row synthesis; verifies CPU/RAM-only fallback wording. |
| **Does not** | Sample the local GPU, process media, launch pipeline commands, publish, rename, save settings, mutate queue state, or touch source/output/scratch paths. |
| **Skip** | Exits 0 when Chrome/Edge not installed. |

### Test-WebViewBrowserSettingsLaunchSmoke.ps1

| | |
|---|---|
| **Exercises** | Drives Settings and Launch controls; verifies staged settings patch handoff, Settings Effective Policy Trust, selectable Launch Risk Handoff proof-chain detail, and Settings-to-Launch intent; verifies Preview Patch is called; cancels Save Patch; confirms cancellation is visible; verifies Save Patch is not posted. |
| **Does not** | Save settings, process media, launch pipeline commands, publish, rename files, mutate queue state, or touch source/output/scratch paths. |
| **Skip** | Exits 0 when Chrome/Edge not installed. |

### Test-WebViewBrowserPendingDrainGuardSmoke.ps1

| | |
|---|---|
| **Exercises** | Injects a backend-shaped blocked recovery dry-run result; verifies Publish Button Guard refreshes immediately; clicks `Publish Parked Outputs`; proves the blocked click records local `frontend_guard` evidence without posting `/api/pipeline/start`. |
| **Does not** | Launch, process media, drain pending publish, publish, rename, save settings, mutate queue state, or touch source/output/scratch paths. |
| **Skip** | Exits 0 when Chrome/Edge not installed. |

### Test-WebViewBrowserCompletedPendingProofSmoke.ps1

| | |
|---|---|
| **Exercises** | Completed-to-Pending proof detail for exact output-to-destination overlap; Completed Real-Media Output Proof Sample Validation handoff; selected Pending row Completed Manifest correlation; missing-output-without-proof blocker detail; same-leaf proof vs. duplicate-title guidance. |
| **Does not** | Launch, process media, drain pending publish, publish, rename, save settings, mutate queue state, or touch source/output/scratch paths. |
| **Skip** | Exits 0 when Chrome/Edge not installed. |

---

## Consolidated Mutation Guarantee

Every smoke in this matrix guarantees:

| Action | All smokes |
|---|---|
| Process real media (FFmpeg encode/remux) | Never |
| Launch pipeline (`/api/pipeline/start`) | Never |
| Save live config (`/api/settings/save-patch`) | Never* |
| Rename files on disk (`/api/rename/apply`) | Never |
| Drain / publish pending outputs | Never |
| Write to source, output, or scratch paths | Never |
| Delete any file | Never |
| Post to any route not in the 53-route contract | Never |

Browser-backed fixture smokes additionally enforce that watched media/sidecar/manifest artifacts are not changed, deleted, or newly created unless the file existed as part of fixture setup before the snapshot was captured.

*Exception: `Test-WebViewSettingsPatchEvidenceSmoke.ps1` writes to a **generated temporary config**, not the live `MediaPipeline_config_chatgpt.psd1`. The live config is never touched.

---

## Skip vs. Fail

| Exit code | Meaning |
|---|---|
| `0` + "SkipTest" message | Chrome/Edge not installed — test skipped, not failed |
| `0` + no error | Test passed |
| non-`0` | Test failed — review runner output and browser-side exception detail |

A skip exit code of 0 must not be treated as a pass. The smoke did not execute and made no assertions.

---

## What Smokes Do Not Prove

- That real media is routed, encoded, or remuxed correctly
- That subtitle OCR produces correct SRT output
- That audio policy is applied correctly during an actual pipeline run
- That the Completed manifest is written correctly
- That Pending Publish drains or publishes correctly
- That rename produces correct final file names on disk
- That the backend produces the correct config after a real save

For real-media proof, see `docs/implementation/release-foundation/PHASE_6_REAL_MEDIA_PILOT.md`.

---

## See Also

- Smoke test catalog: `docs/testing/WEBVIEW_SMOKE_TEST_CATALOG.md`
- Browser prerequisites: `docs/testing/BROWSER_SMOKE_PREREQUISITES_CHECKLIST.md`
- Browser runbook: `docs/testing/BROWSER_SMOKE_TEST_RUNBOOK.md`
- Smoke result template: `docs/testing/WEBVIEW_SMOKE_RESULT_TEMPLATE.md`

---

## Freshness Review — 2026-05-15 (CLN3-013)

Recounted all `Test-WebViewBrowser*.ps1` `ops/scripts/smoke/` wrappers. Count is 15 (was "13" in original header — two wrappers added since original write: `Test-WebViewBrowserPendingDrainGuardSmoke.ps1` and `Test-WebViewBrowserCompletedPendingProofSmoke.ps1`). Header updated to 15.

Matrix now covers all 15 browser-backed wrappers including:
- `Test-WebViewBrowserLaunchQueueReadinessSmoke.ps1`: explicitly does not send POST routes during Launch readiness/worksheet/record/scope-reconciliation rendering.
- `Test-WebViewBrowserSampleValidationSmoke.ps1`: exercises only `/api/sample-validation/preview`; does not append records.
- `Test-WebViewBrowserHomeLiveStateSmoke.ps1`: sends no POST routes during Home live-state rendering.
- `Test-WebViewBrowserPendingDrainGuardSmoke.ps1`: proves `frontend_guard` evidence is recorded without posting `/api/pipeline/start`.
- `Test-WebViewBrowserCompletedPendingProofSmoke.ps1`: all Completed/Pending proof panels verified read-only.

Consolidated mutation guarantee table and "Does not prove" section remain accurate.

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


