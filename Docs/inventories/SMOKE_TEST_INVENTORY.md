# Smoke Test Inventory

Last updated: 2026-05-20

All project smoke wrappers live under `SmokeTests/`. Run them from the repository root with `.\SmokeTests\<script>.ps1`, or run them by absolute path. Each wrapper resolves the project root as the parent of `SmokeTests/`.

The wrappers are intentionally thin. They print boundary text, resolve a Python runtime, set `PYTHONDONTWRITEBYTECODE=1`, and call the matching Python unittest/module. They must not contain media policy, filesystem mutation logic, or WebView business rules.

## Quick Commands

```powershell
.\SmokeTests\Test-WebViewRowDetailSmoke.ps1
.\SmokeTests\Test-WebViewRenameReadinessSmoke.ps1
.\SmokeTests\Test-WebViewSettingsLaunchPolicySmoke.ps1
.\SmokeTests\Test-LocalApiLifecycleContractSmoke.ps1
.\SmokeTests\Test-WebViewBrowserHighRiskSmoke.ps1
```

Browser-backed smokes require Chrome or Edge plus Node/browser runner prerequisites. Browser-free smokes require Python and, for JS/DOM checks, Node.

## Inventory

| Wrapper | Type | Underlying test/module | Main coverage | Mutation boundary |
| --- | --- | --- | --- | --- |
| `SmokeTests/Test-LocalApiLifecycleContractSmoke.ps1` | Local API contract | `DesktopApp.tests.test_local_api_lifecycle_contract_smoke` | Close-readiness and backend shutdown route contracts against temporary test backends | Backend lifecycle POSTs only against temporary test backend |
| `SmokeTests/Test-LocalApiMaintenanceDryRunContractSmoke.ps1` | Local API contract | `DesktopApp.tests.test_local_api_maintenance_dry_run_contract_smoke` | Maintenance release/backfill dry-run contracts, token enforcement, command history | Dry-run only; temp state only |
| `SmokeTests/Test-LocalApiSampleValidationContractSmoke.ps1` | Local API contract | `DesktopApp.tests.test_sample_validation_api` | Sample-validation preview/append/read/tail contracts and diagnostics tail allowlist | Writes validation log only inside temp state |
| `SmokeTests/Test-WebViewCommandEvidenceSmoke.ps1` | WebView non-browser | `DesktopApp.tests.test_webview_command_evidence_smoke` | Shared owner/issue command-history rendering | No mutation routes |
| `SmokeTests/Test-WebViewRealMediaEvidenceSmoke.ps1` | WebView non-browser | `DesktopApp.tests.test_webview_real_media_smoke` | Backend-served Queue/Completed/Pending/Diagnostics/Settings evidence from generated sample state | No real media processing |
| `SmokeTests/Test-WebViewRenameReadinessSmoke.ps1` | WebView non-browser | `DesktopApp.tests.test_webview_rename_readiness_smoke` | Rename Apply Readiness ready and duplicate-target scopes | Does not call `rename.apply` |
| `SmokeTests/Test-WebViewRowDetailSmoke.ps1` | WebView non-browser | `DesktopApp.tests.test_webview_row_detail_smoke` | Queue, Completed, Pending row details and diagnostics handoff | No launch, publish, rename, or settings save |
| `SmokeTests/Test-WebViewScheduleSmoke.ps1` | WebView non-browser | `DesktopApp.tests.test_webview_schedule_smoke` | Schedule coverage review, selected day detail, editor preview/save routing | Mocked/generated state only |
| `SmokeTests/Test-WebViewSettingsLaunchLiveConfigSmoke.ps1` | WebView non-browser | `mediapipeline_desktop_app.webview_settings_live_smoke` | Read-only Settings/Launch policy handoff against current saved config | Reads live config; does not save |
| `SmokeTests/Test-WebViewSettingsLaunchPolicySmoke.ps1` | WebView non-browser | `DesktopApp.tests.test_webview_settings_launch_policy_smoke` | Settings/Launch media-policy handoff from generated temporary state | No media processing or config writes |
| `SmokeTests/Test-WebViewSettingsPatchEvidenceSmoke.ps1` | WebView non-browser | `mediapipeline_desktop_app.webview_settings_patch_smoke` | Preview/Save Patch evidence against generated temporary config | Writes temp config only |
| `SmokeTests/Test-WebViewBrowserCompletedPendingProofSmoke.ps1` | WebView browser-backed | `DesktopApp.tests.test_webview_browser_completed_pending_proof_smoke` | Completed/Pending proof correlation, missing-output blockers, duplicate-title wording | Read-only rendering; no publish |
| `SmokeTests/Test-WebViewBrowserDiagnosticsHandoffSmoke.ps1` | WebView browser-backed | `DesktopApp.tests.test_webview_browser_diagnostics_handoff_smoke` | Row click to diagnostics bridge, tail/open handoff, state artifact summary, API contract view | Allowlisted read/open only |
| `SmokeTests/Test-WebViewBrowserHighRiskSmoke.ps1` | WebView browser-backed | `DesktopApp.tests.test_webview_browser_high_risk_smoke` | Blocked Queue, broken Completed, do-not-drain Pending guidance in real browser | No mutation posts |
| `SmokeTests/Test-WebViewBrowserHomeLiveStateSmoke.ps1` | WebView browser-backed | `DesktopApp.tests.test_webview_browser_home_live_state_smoke` | Home daily-driver checklist, operator readiness, active work, command results, sample validation posture | No POST routes |
| `SmokeTests/Test-WebViewBrowserLargeTableSmoke.ps1` | WebView browser-backed | `DesktopApp.tests.test_webview_browser_large_table_smoke` | 260-row render caps, filter warnings, hidden selected-row detail | No mutation posts |
| `SmokeTests/Test-WebViewBrowserLaunchQueueReadinessSmoke.ps1` | WebView browser-backed | `DesktopApp.tests.test_webview_browser_launch_queue_readiness_smoke` | Launch preflight, Queue decision, schedule guidance, close-readiness, sample evidence | Does not submit `pipeline.start` |
| `SmokeTests/Test-WebViewBrowserLayoutManagerSmoke.ps1` | WebView browser-backed | `DesktopApp.tests.test_webview_browser_layout_manager_smoke` | Layout Editor drawer across page tabs, subtabs, and generated subsections | No mutation posts; media/sidecar/manifest fixture hash guard |
| `SmokeTests/Test-WebViewBrowserLifecycleSmoke.ps1` | WebView browser-backed | `DesktopApp.tests.test_webview_browser_lifecycle_smoke` | Backend lifecycle controls, close-readiness, safe shutdown request confirmation | Shutdown only against temp backend |
| `SmokeTests/Test-WebViewBrowserMaintenanceChangeLedgerSmoke.ps1` | WebView browser-backed | `DesktopApp.tests.test_webview_browser_maintenance_change_ledger_smoke` | Maintenance Change Ledger summary/table/detail/hygiene and filters | Read-only GET route only; no mutation posts |
| `SmokeTests/Test-WebViewBrowserMaintenanceReportsSmoke.ps1` | WebView browser-backed | `DesktopApp.tests.test_webview_browser_maintenance_reports_smoke` | Maintenance health/dry-run result rendering and Reports triage | Failure-marker clear dry-run preview only; no non-dry-run mutation posts |
| `SmokeTests/Test-WebViewBrowserNetworkSmoke.ps1` | WebView browser-backed | `DesktopApp.tests.test_webview_browser_network_smoke` | Read-only Network readiness, lifecycle handoff, worker detail, worker-filter guardrails | No coordinator/worker lifecycle mutation |
| `SmokeTests/Test-WebViewBrowserPendingDrainGuardSmoke.ps1` | WebView browser-backed | `DesktopApp.tests.test_webview_browser_pending_drain_guard_smoke` | Pending Publish drain guard and blocked frontend evidence | Does not post `/api/pipeline/start` |
| `SmokeTests/Test-WebViewBrowserRenameSmoke.ps1` | WebView browser-backed | `DesktopApp.tests.test_webview_browser_rename_smoke` | Rename row selection, Apply Readiness, duplicate-target apply blocking | Does not call `rename.apply` |
| `SmokeTests/Test-WebViewBrowserSampleValidationSmoke.ps1` | WebView browser-backed | `DesktopApp.tests.test_webview_browser_sample_validation_smoke` | Home sample-validation pilot/readiness/reconciliation and worksheet detail | Preview only; no append |
| `SmokeTests/Test-WebViewBrowserScheduleSmoke.ps1` | WebView browser-backed | `DesktopApp.tests.test_webview_browser_schedule_smoke` | Schedule editor preview/save routing and Launch timing trust | App-state write only in generated temp backend |
| `SmokeTests/Test-WebViewBrowserSettingsLaunchSmoke.ps1` | WebView browser-backed | `DesktopApp.tests.test_webview_browser_settings_launch_smoke` | Settings staged patch handoff, Preview/Save result visibility, Launch policy boundary | Does not save settings |
| `SmokeTests/Test-WebViewBrowserTelemetrySmoke.ps1` | WebView browser-backed | `DesktopApp.tests.test_webview_browser_telemetry_smoke` | Idle NVENC `0%`, GPU detail rows, CPU/RAM-only fallback wording | Read-only telemetry rendering |

## Safety Rules

- Add new smoke wrappers under `SmokeTests/`, not the repository root.
- Keep wrappers thin; put behavior in Python tests or backend/frontend code.
- Always print boundary text that states what the smoke does not prove.
- Browser-backed smokes must skip cleanly when Chrome/Edge is unavailable.
- Do not add source/output/scratch mutation to smoke wrappers.
- Update `scripts\release\test.ps1`, `Docs/testing/WEBVIEW_SMOKE_TEST_CATALOG.md`, `Docs/testing/TEST_COVERAGE_MATRIX.md`, and this inventory when adding or removing smoke wrappers.
