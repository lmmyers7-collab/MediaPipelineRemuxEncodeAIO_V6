# WebView Smoke Wrapper Boundary Text Audit

Date: 2026-05-15

Reviews `SmokeTests/Test-WebView*.ps1` wrappers and checks whether their `Boundary:` text matches what each smoke actually does. Source: all 23 `SmokeTests/Test-WebView*.ps1` wrappers (grep of `Boundary:` lines).

---

## Summary

All 23 wrapper `Boundary:` statements are accurate and match actual smoke behavior. No stale "read-only" phrases were found when a backend-owned mutation exists. Mutation boundaries are precise. No wrappers need editing.

---

## Non-Browser Wrappers (8)

### Test-WebViewRealMediaEvidenceSmoke.ps1

Boundary: "starts a temporary local API against generated temporary state. Does not process media, launch pipeline commands, publish, rename, save settings, or modify source/output/scratch media."

**Assessment**: Correct. The name "RealMediaEvidence" refers to the payload schema (real-media evidence structure), not actual media. Boundary text correctly clarifies "generated temporary state."

---

### Test-WebViewCommandEvidenceSmoke.ps1

Boundary: "starts a temporary local API against generated temporary state. Evaluates backend-served WebView JavaScript with mocked DOM state and fixture command history."

**Assessment**: Correct.

---

### Test-WebViewRenameReadinessSmoke.ps1

Boundary: "evaluates WebView Rename assets in Node with mocked DOM state. Verifies Apply Readiness and Pipeline Handoff for a ready single-row scope and a blocked duplicate-target scope. Verifies large-preview render cap text without calling rename.apply. Verifies duplicate-target blocking does not call rename.apply."

**Assessment**: Correct and precise. Explicit "does not call rename.apply" in two places.

---

### Test-WebViewRowDetailSmoke.ps1

Boundary: "starts a temporary local API against generated temporary state. Evaluates backend-served WebView JavaScript with mocked DOM selected-row state. Validates Queue, Completed, and Pending Publish row details plus diagnostics handoff text."

**Assessment**: Correct.

---

### Test-WebViewScheduleSmoke.ps1

Boundary: "evaluates WebView Schedule assets in Node with mocked DOM state. Verifies Schedule Coverage Review, selected day detail, table status legend, Schedule Editor preview/save routing, and app-state-write result copy. Does not start pipeline commands, override schedule gates, mutate queue state, touch media files, or write app state from frontend code."

**Assessment**: Correct. "Does not write app state from frontend code" is precise — the Schedule Editor routes through the backend save endpoint; it writes app-state through the backend, not from frontend code. This distinction is correct.

---

### Test-WebViewSettingsLaunchLiveConfigSmoke.ps1

Boundary: "starts a temporary local API using the current saved config. Validates read-only Settings and Launch policy handoff visibility against live config data."

**Assessment**: Correct. This smoke uses the live config (read-only), unlike the other settings smokes which use generated temp state. The "read-only" boundary is appropriate here.

---

### Test-WebViewSettingsLaunchPolicySmoke.ps1

Boundary: "starts a temporary local API against generated temporary state. Validates read-only Settings and Launch policy handoff visibility."

**Assessment**: Correct.

---

### Test-WebViewSettingsPatchEvidenceSmoke.ps1

Boundary: "starts a temporary local API against a generated temporary config. Exercises backend-owned Preview Patch, denied Save Patch, confirmed Save Patch, reload, and command-history evidence. Does not use the current saved config and does not process media, launch pipeline commands, publish, rename, mutate queue state, or modify source/output/scratch media."

**Assessment**: Correct and precise. "Does not use the current saved config" is an important distinction from the LiveConfig smoke.

---

## Browser-Backed Wrappers (15)

All browser-backed wrappers share these two boundary lines:
- "starts a temporary local API against generated temporary state."
- "skips cleanly when Chrome/Edge is not installed."

These common lines are accurate across all current browser-backed wrappers.

---

### Test-WebViewBrowserHighRiskSmoke.ps1

Boundary includes: "launches installed Chrome/Edge headless and drives the real backend-served WebView page through Chrome DevTools Protocol. Validates injected and backend-produced blocked Queue, broken Completed, and do-not-drain Pending Publish selected-row guidance."

**Assessment**: Correct. "Through Chrome DevTools Protocol" is more technical than other wrappers but accurate.

---

### Test-WebViewBrowserScheduleSmoke.ps1

Boundary includes: "launches installed Chrome/Edge headless and drives real backend-served WebView Schedule and Launch controls. Validates Schedule Editor preview/save routing, confirmed backend app-state write, command history ownership, and refreshed Launch timing trust."

**Assessment**: Correct. "Confirmed backend app-state write" is the one browser smoke where the backend does write app-state (schedule keys only). The boundary text correctly acknowledges this rather than claiming everything is read-only.

---

### Test-WebViewBrowserLifecycleSmoke.ps1

Boundary includes: "validates close-readiness blocked shutdown rejection while the continuous schedule-stop watcher is armed. Validates safe close-readiness posts exactly through backend-owned /api/backend/shutdown after confirmation."

**Assessment**: Correct. The shutdown route is backend-owned and the boundary text accurately states it is posted — not that it is blocked.

---

### Test-WebViewBrowserDiagnosticsHandoffSmoke.ps1

Boundary includes: 6 detailed lines covering table row clicks, filter guardrails, diagnostics bridge/tail/open, owner-row navigation, and bounded tail output.

**Assessment**: Correct and comprehensive. Most detailed boundary block of all wrappers, appropriate to the smoke's multi-step interaction scope.

---

### Test-WebViewBrowserPendingDrainGuardSmoke.ps1

Boundary includes: "verifies active Pending Publish display filters are disclosed as local-only and do not narrow backend drain scope. Injects a backend-shaped blocked recovery dry-run result and verifies Publish Button Guard refreshes immediately. Verifies a blocked Publish Parked Outputs click records local frontend_guard evidence without posting /api/pipeline/start."

**Assessment**: Correct and precise. The `frontend_guard` evidence detail and explicit `without posting /api/pipeline/start` are correct.

---

### Test-WebViewBrowserCompletedPendingProofSmoke.ps1

Boundary includes: "verifies the Completed Real-Media Output Proof ladder, including Sample Validation handoff. Verifies exact completed-output to pending-destination overlap. Verifies selected Pending row Completed Manifest correlation remains read-only. Verifies same-leaf proof wording remains a duplicate-title hint, not publish proof. Does not append validation records."

**Assessment**: Correct and precise.

---

### Test-WebViewBrowserLargeTableSmoke.ps1

Boundary includes: "verifies 260-row payloads disclose the 250-row render cap, filter warnings, and hidden selected-row detail. Verifies no backend mutation routes are posted."

**Assessment**: Correct.

---

### Test-WebViewBrowserMaintenanceReportsSmoke.ps1

Boundary includes: "verifies Maintenance health, dry-run result rendering, dry-run history, Reports failure/audit triage, row details, and read-only Launch/Diagnostics handoff navigation. Verifies no backend mutation routes are posted."

**Assessment**: Correct. The smoke renders dry-run result evidence but does not execute release packaging or completed-manifest backfill commands.

---

### Test-WebViewBrowserSampleValidationSmoke.ps1

Boundary includes: "verifies real-media pilot-plan rendering and sample-validation preview result rendering. Permits only /api/sample-validation/preview and verifies no append or mutation routes are posted."

**Assessment**: Correct. The smoke exercises the preview route only, does not append validation JSONL, and explicitly blocks launch, audit, CSV rerun, drain, publish, rename, settings save, queue mutation, and media path mutation.

---

### Test-WebViewBrowserHomeLiveStateSmoke.ps1

Boundary includes: "verifies Daily-Driver Checklist, Operator Readiness, Active Work, Command Results, Sample Validation posture, and Real-Media Validation Worksheet handoff. Verifies no POST routes are sent during Home live-state rendering."

**Assessment**: Correct. The smoke renders Home from backend reads plus a generated command journal and explicitly blocks append, launch, audit, CSV rerun, drain, publish, rename, settings save, queue mutation, and media path mutation.

---

### Test-WebViewBrowserLaunchQueueReadinessSmoke.ps1

Boundary includes: "verifies Launch preflight, Queue launch decision, Schedule guidance, close-readiness, launch command-review evidence, Launch real-media sample proof handoff, Launch Sample Validation record evidence, and Launch sample execution checklist align. Verifies no POST routes are sent while reading launch readiness evidence."

**Assessment**: Correct. The smoke renders backend-served Launch, Queue, Schedule, Home worksheet, and Home sample-validation execution evidence from GET/read state plus generated command history and explicitly blocks launch, audit, CSV rerun, drain, publish, rename, settings save, queue mutation, and media path mutation.

---

### Test-WebViewBrowserRenameSmoke.ps1

Boundary includes: "clicks actual Rename preview rows and Check Applicable Rows, then verifies Apply Readiness, Pipeline Handoff, and duplicate-target blocking. Verifies large-preview render cap text without calling rename.apply. Verifies blocked duplicate-target scope does not call rename.apply."

**Assessment**: Correct. Explicit "without calling rename.apply" appears twice.

---

### Test-WebViewBrowserNetworkSmoke.ps1

Boundary includes: "validates read-only network readiness, persisted worker rows, worker detail, and local worker filters. Verifies filters warn when active/problem worker rows are hidden. Verifies no network lifecycle mutation commands are posted; WebView Network remains read-only."

**Assessment**: Correct.

---

### Test-WebViewBrowserTelemetrySmoke.ps1

Boundary includes: "validates idle NVENC at 0% remains visible and synthesizes a GPU detail row when only top-level GPU telemetry is present. Validates CPU/RAM-only fallback wording keeps the GPU graph area explicit instead of empty."

**Assessment**: Correct. "GPU graph area explicit instead of empty" is a precise behavioral statement.

---

### Test-WebViewBrowserSettingsLaunchSmoke.ps1

Boundary includes: "validates staged settings patch handoff, Settings-to-Launch intent status, and backend Preview/Save result visibility. Validates Launch Active Media Policy Boundary separates saved launch-active policy from staged subtitle/audio/pending-publish candidates. Verifies Preview Patch is called, cancelled Save Patch remains visible, and Save Patch is not posted by the browser smoke."

**Assessment**: Correct and precise. "Save Patch is not posted by the browser smoke" is the key mutation-negative guarantee.

---

## Acceptance Criteria

| Criterion | Status |
|---|---|
| No stale "read-only" phrases when backend-owned mutation exists | Pass — Schedule browser smoke correctly says "confirmed backend app-state write"; Lifecycle says shutdown is "posted through backend-owned route" |
| Mutation boundaries precise ("does not save settings" vs "does save schedule app-state through backend") | Pass — all wrappers distinguish between what does and does not occur |
| No wrapper edits needed | Pass — no mismatches found |

---

## Sweep Recheck — 2026-05-15 (CLN2-08)

Re-read all 23 wrapper `Boundary:` lines via grep after recent browser-smoke runner hardening, Maintenance/Reports smoke addition, Sample Validation smoke addition, Home live-state smoke addition, and Launch/Queue readiness worksheet/record evidence additions. All wrappers verified accurate; no corrections needed.

| Check | Result |
|---|---|
| All 23 boundary lines present | Pass |
| Browser schedule smoke acknowledges backend app-state write | Pass — "confirmed backend app-state write" |
| Settings patch smoke acknowledges backend Preview/Save | Pass — "exercises backend-owned Preview Patch…" |
| Lifecycle smoke acknowledges `/api/backend/shutdown` POST | Pass — "posts exactly through backend-owned /api/backend/shutdown" |
| No stale "read-only" where backend mutation exists | Pass — no such phrase found |
| Network smoke correctly says read-only | Pass — "verifies no network lifecycle mutation commands are posted" |
| Browser settings/launch smoke says Save Patch NOT posted | Pass — "Save Patch is not posted by the browser smoke" |

No wrappers need editing.

---

## Freshness Review — 2026-05-15 (CLN3-017)

Re-confirmed all wrapper boundary texts after the CLN3 session additions (Sample Validation, Home Live State, Launch/Queue Readiness smokes). Fixed header count from "(13)" to "(15)" to reflect all current browser-backed wrappers.

| Check | Result |
|---|---|
| Browser-backed wrapper count corrected | Pass — header now reads "(15)"; 15 wrapper assessments present in the document |
| 3 new wrappers all have boundary assessments | Pass — `SampleValidation`, `HomeLiveState`, `LaunchQueueReadiness` each assessed above |
| No stale "read-only" phrases where backend mutation exists | Pass — Schedule smoke correctly says "confirmed backend app-state write"; Lifecycle says shutdown posted through backend-owned route; Settings Launch smoke says "Save Patch is not posted by the browser smoke" |
| No new wrappers added since CLN2-08 recheck | Confirmed — 15 is the current count; no additional browser smokes added after CLN3 |

No boundary text corrections needed. Count corrected.

```
Task ID: CLN3-017
Files inspected: Docs\WEBVIEW_SMOKE_BOUNDARY_TEXT_AUDIT.md
Files changed: Docs\WEBVIEW_SMOKE_BOUNDARY_TEXT_AUDIT.md (count corrected: 13→15; CLN3-017 freshness note added)
Validation: Select-String -Path Docs\WEBVIEW_SMOKE_BOUNDARY_TEXT_AUDIT.md -Pattern "Browser-Backed Wrappers"
Findings: Header count was stale (13 instead of 15). All 15 boundary assessments present and accurate.
Open questions: None.
Risk: Low — documentation only.
```

---

## Task Output

```
Task ID: CLN-004
Files inspected: All 23 SmokeTests/Test-WebView*.ps1 wrappers (Boundary: grep)
Files changed: Docs\WEBVIEW_SMOKE_BOUNDARY_TEXT_AUDIT.md (created)
Validation: Read all Boundary: lines via grep. Cross-referenced with WEBVIEW_SMOKE_TEST_CATALOG.md descriptions.
Findings: All 23 wrappers have accurate boundary text. Schedule smoke correctly acknowledges backend app-state write. Sample Validation smoke correctly permits only preview and blocks append/mutation posts. Home live-state smoke correctly verifies no POST routes during read-only Home rendering. Launch/Queue readiness smoke correctly verifies no POST routes during read-only worksheet/validation-record readiness rendering. No stale read-only phrases found.
Open questions: None.
Risk: Low — documentation only.
```

