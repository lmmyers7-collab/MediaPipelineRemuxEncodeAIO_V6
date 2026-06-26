# Smoke Test Inventory

Last updated: 2026-06-18

All project smoke wrappers live under `ops/scripts/smoke/`. Run them from the repository root with `.\ops/scripts/smoke\<script>.ps1`, or run them by absolute path. Each wrapper resolves the project root as the parent of `ops/scripts/smoke/`.

The wrappers are intentionally thin. They print boundary text, resolve a Python runtime, set `PYTHONDONTWRITEBYTECODE=1`, and call the matching Python unittest/module. They must not contain media policy, filesystem mutation logic, or WebView business rules.

Machine-readable wrapper ownership lives in `docs/generated/SMOKE_WRAPPER_MAP.json`. Regenerate it with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.generate_smoke_wrapper_map`; release/tooling checks use `--check` to catch drift between this inventory, the WebView smoke catalog, wrapper files, and `ops/scripts/release/test.ps1`.

## Quick Commands

```powershell
.\ops/scripts/smoke\Test-WebViewRowDetailSmoke.ps1
.\ops/scripts/smoke\Test-WebViewRenameReadinessSmoke.ps1
.\ops/scripts/smoke\Test-WebViewSettingsLaunchPolicySmoke.ps1
.\ops/scripts/smoke\Test-LocalApiLifecycleContractSmoke.ps1
.\ops/scripts/smoke\Test-WebViewBrowserHighRiskSmoke.ps1
```

Browser-backed smokes require Chrome or Edge plus Node/browser runner prerequisites. Browser-free smokes require Python and, for JS/DOM checks, Node.

## Inventory

| Wrapper | Type | Underlying test/module | Main coverage | Mutation boundary |
| --- | --- | --- | --- | --- |
| `ops/scripts/smoke/Test-LocalApiLifecycleContractSmoke.ps1` | Local API contract | `tests.python.desktop.test_local_api_lifecycle_contract_smoke` | Close-readiness and backend shutdown route contracts against temporary test backends | Backend lifecycle POSTs only against temporary test backend |
| `ops/scripts/smoke/Test-LocalApiMaintenanceDryRunContractSmoke.ps1` | Local API contract | `tests.python.desktop.test_local_api_maintenance_dry_run_contract_smoke` | Maintenance ops/release/metadata/backfill dry-run contracts, token enforcement, command history | Dry-run only; temp state only |
| `ops/scripts/smoke/Test-LocalApiRepairReconcileDryRunContractSmoke.ps1` | Local API contract | `pytest` selectors in `tests/python/desktop/test_repair_reconcile_dry_run.py`, `tests/python/desktop/test_api_command_contracts.py`, `tests/python/desktop/test_api_contract_payload.py`, and `tests/webview/test_webview_frontend_mutation_boundary.py` | Completed and pending-publish repair/reconcile dry-run route contracts, strict request fields, required dry-run schema fields, command-journal suppression, and frontend mutation-boundary guards | Dry-run/effect-none fixtures only; no manifests, sidecars, parked payloads, outputs, sources, or WebView controls are mutated |
| `ops/scripts/smoke/Test-LocalApiSampleValidationContractSmoke.ps1` | Local API contract | `tests.python.desktop.test_sample_validation_api` | Sample-validation preview/append/read/tail contracts and diagnostics tail allowlist | Writes validation log only inside temp state |
| `ops/scripts/smoke/Test-WebViewCommandEvidenceSmoke.ps1` | WebView non-browser | `tests.webview.test_webview_command_evidence_smoke` | Shared owner/issue command-history rendering | No mutation routes |
| `ops/scripts/smoke/Test-WebViewRealMediaEvidenceSmoke.ps1` | WebView non-browser | `tests.webview.test_webview_real_media_smoke` | Backend-served Queue/Completed/Pending/Diagnostics/Settings evidence from generated sample state | No real media processing |
| `ops/scripts/smoke/Test-WebViewRenameReadinessSmoke.ps1` | WebView non-browser | `tests.webview.test_webview_rename_readiness_smoke` | Rename Apply Readiness ready and duplicate-target scopes | Does not call `rename.apply` |
| `ops/scripts/smoke/Test-WebViewRowDetailSmoke.ps1` | WebView non-browser | `tests.webview.test_webview_row_detail_smoke` | Queue, Completed, Pending row details and diagnostics handoff | No launch, publish, rename, or settings save |
| `ops/scripts/smoke/Test-WebViewScheduleSmoke.ps1` | WebView non-browser | `tests.webview.test_webview_schedule_smoke` | Schedule coverage review, selected day detail, editor preview/save routing | Mocked/generated state only |
| `ops/scripts/smoke/Test-WebViewSettingsLaunchLiveConfigSmoke.ps1` | WebView non-browser | `mediapipeline.desktop.webview_settings_live_smoke` | Read-only Settings/Launch policy handoff against current saved config | Reads live config; does not save |
| `ops/scripts/smoke/Test-WebViewSettingsLaunchPolicySmoke.ps1` | WebView non-browser | `tests.webview.test_webview_settings_launch_policy_smoke` | Settings/Launch media-policy handoff from generated temporary state | No media processing or config writes |
| `ops/scripts/smoke/Test-WebViewSettingsPatchEvidenceSmoke.ps1` | WebView non-browser | `mediapipeline.desktop.webview_settings_patch_smoke` | Preview/Save Patch evidence against generated temporary config | Writes temp config only |
| `ops/scripts/smoke/Test-WebViewBrowserCompletedPendingProofSmoke.ps1` | WebView browser-backed | `tests.webview.test_webview_browser_completed_pending_proof_smoke` | Completed/Pending proof correlation, missing-output blockers, duplicate-title wording | Read-only rendering; no publish |
| `ops/scripts/smoke/Test-WebViewBrowserDiagnosticsHandoffSmoke.ps1` | WebView browser-backed | `tests.webview.test_webview_browser_diagnostics_handoff_smoke` | Row click to diagnostics bridge, tail/open handoff, state artifact summary, API contract view | Allowlisted read/open only |
| `ops/scripts/smoke/Test-WebViewBrowserHighRiskSmoke.ps1` | WebView browser-backed | `tests.webview.test_webview_browser_high_risk_smoke` | Blocked Queue, broken Completed, do-not-drain Pending guidance in real browser | No mutation posts |
| `ops/scripts/smoke/Test-WebViewBrowserHomeLiveStateSmoke.ps1` | WebView browser-backed | `tests.webview.test_webview_browser_home_live_state_smoke` | Home daily-driver checklist, operator readiness, active work, command results, sample validation posture | No POST routes |
| `ops/scripts/smoke/Test-WebViewBrowserLargeTableSmoke.ps1` | WebView browser-backed | `tests.webview.test_webview_browser_large_table_smoke` | 260-row render caps, filter warnings, hidden selected-row detail | No mutation posts |
| `ops/scripts/smoke/Test-WebViewBrowserLaunchQueueReadinessSmoke.ps1` | WebView browser-backed | `tests.webview.test_webview_browser_launch_queue_readiness_smoke` | Launch preflight, Queue decision, schedule guidance, close-readiness, sample evidence | Does not submit `pipeline.start` |
| `ops/scripts/smoke/Test-WebViewBrowserLayoutManagerSmoke.ps1` | WebView browser-backed | `tests.webview.test_webview_browser_layout_manager_smoke` | Layout Editor drawer across page tabs, subtabs, and generated subsections | No mutation posts; media/sidecar/manifest fixture hash guard |
| `ops/scripts/smoke/Test-WebViewBrowserLifecycleSmoke.ps1` | WebView browser-backed | `tests.webview.test_webview_browser_lifecycle_smoke` | Backend lifecycle controls, close-readiness, safe shutdown request confirmation | Shutdown only against temp backend |
| `ops/scripts/smoke/Test-WebViewBrowserMaintenanceChangeLedgerSmoke.ps1` | WebView browser-backed | `tests.webview.test_webview_browser_maintenance_change_ledger_smoke` | Maintenance Change Ledger summary/table/detail/hygiene and filters | Read-only GET route only; no mutation posts |
| `ops/scripts/smoke/Test-WebViewBrowserMaintenanceReportsSmoke.ps1` | WebView browser-backed | `tests.webview.test_webview_browser_maintenance_reports_smoke` | Maintenance health/dry-run result rendering, Reports triage, grouped failure resolution, guided marker clear, and evidence archive | Allowlisted `/api/failures/clear` and `/api/failures/archive-evidence` only; no media/process/queue/settings/publish mutation |
| `ops/scripts/smoke/Test-WebViewBrowserNetworkSmoke.ps1` | WebView browser-backed | `tests.webview.test_webview_browser_network_smoke` | Read-only Network readiness, lifecycle handoff, worker detail, worker-filter guardrails | No coordinator/worker lifecycle mutation |
| `ops/scripts/smoke/Test-WebViewBrowserPendingDrainGuardSmoke.ps1` | WebView browser-backed | `tests.webview.test_webview_browser_pending_drain_guard_smoke` | Pending Publish drain guard and blocked frontend evidence | Does not post `/api/pipeline/start` |
| `ops/scripts/smoke/Test-WebViewBrowserProseBoxAudit.ps1` | WebView browser-backed | `tests.webview.test_webview_browser_prose_box_audit` | Primary page/subtab screenshot manifest and visible prose/status/diagnostic box audit | Screenshot evidence only; no mutation posts; media/sidecar/manifest fixture hash guard |
| `ops/scripts/smoke/Test-WebViewBrowserQueueFileOverridesSmoke.ps1` | WebView browser-backed | `tests.webview.test_webview_browser_queue_file_overrides_smoke` | Queue File Settings drawer action/status feedback, dirty-state discard guard, clear-fields save payload, full-clear confirmation, series apply/clear preview modals, and failed-save alert tone | Intercepts file-overrides POST routes in the browser harness; does not persist queue/file override mutations |
| `ops/scripts/smoke/Test-WebViewBrowserRenameSmoke.ps1` | WebView browser-backed | `tests.webview.test_webview_browser_rename_smoke` | Rename row selection, Apply Readiness, duplicate-target apply blocking | Does not call `rename.apply` |
| `ops/scripts/smoke/Test-WebViewBrowserSampleValidationSmoke.ps1` | WebView browser-backed | `tests.webview.test_webview_browser_sample_validation_smoke` | Home sample-validation pilot/readiness/reconciliation and worksheet detail | Preview only; no append |
| `ops/scripts/smoke/Test-WebViewBrowserScheduleSmoke.ps1` | WebView browser-backed | `tests.webview.test_webview_browser_schedule_smoke` | Schedule editor preview/save routing and Launch timing trust | App-state write only in generated temp backend |
| `ops/scripts/smoke/Test-WebViewBrowserLibraryProfilesSaveSmoke.ps1` | WebView browser-backed | `tests.webview.test_webview_browser_library_profiles_save_smoke` | LibraryProfiles save/reload flow, read-only profile identity display, backend review confirmation, reload verification | Config write only against generated temp backend; media/sidecar/manifest fixture hash guard |
| `ops/scripts/smoke/Test-WebViewBrowserSettingsLaunchSmoke.ps1` | WebView browser-backed | `tests.webview.test_webview_browser_settings_launch_smoke` | Settings staged patch handoff, Preview/Save result visibility, Launch policy boundary | Does not save settings |
| `ops/scripts/smoke/Test-WebViewBrowserTelemetrySmoke.ps1` | WebView browser-backed | `tests.webview.test_webview_browser_telemetry_smoke` | Idle NVENC `0%`, GPU detail rows, CPU/RAM-only fallback wording | Read-only telemetry rendering |
| `ops/scripts/smoke/Test-WebViewBrowserVisualClutterScreenshots.ps1` | WebView browser-backed | `tests.webview.test_webview_browser_visual_clutter_screenshots` | Desktop/mobile screenshot manifest and visible evidence-prose clutter/overflow audit | Screenshot evidence only; no mutation posts; media/sidecar/manifest fixture hash guard |

## Safety Rules

- Add new smoke wrappers under `ops/scripts/smoke/`, not the repository root.
- Keep wrappers thin; put behavior in Python tests or backend/frontend code.
- Always print boundary text that states what the smoke does not prove.
- Browser-backed smokes must skip cleanly when Chrome/Edge is unavailable.
- Do not add source/output/scratch mutation to smoke wrappers.
- Update `ops\scripts\release\test.ps1`, `docs/testing/WEBVIEW_SMOKE_TEST_CATALOG.md`, `docs/testing/TEST_COVERAGE_MATRIX.md`, and this inventory when adding or removing smoke wrappers.
