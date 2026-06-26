# Dead Export Audit - 2026-05-19

> **Status:** High-confidence cleanup closed; remaining candidates are an opportunistic review queue, not a removal directive.
> **Scope:** WebView `window.*` flat exports and public top-level Python helpers under `DesktopApp/mediapipeline_desktop_app/application/`.
> **Companion:** `Docs/DOC_TOUCH_LOG.md` and `Docs/REMEDIATION_CHANGELOG.md` rows for the closed flat-export cleanup work.

This audit was run after the god-file splits completed. Its purpose is to identify exports that may only exist for historical test access or split-era compatibility, so future cleanup can remove flat compatibility exports deliberately and in small chunks.

No code was changed by the original audit. Follow-up cleanup chunks on 2026-05-19 removed 498 broad direct globals while preserving canonical `window.mediaPipeline*` namespace objects; current inventory reports 756 generated flat compatibility exports across 64 files. Remaining medium-confidence candidates require page-owned smoke/static evidence before removal.

---

## Method

The scan used an indexed heuristic:

1. Read all `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/*.js` files.
2. Find frontend assignments matching `window.<name> =` while excluding equality checks and the backend-injected `MEDIA_PIPELINE_BOOTSTRAP`.
3. Classify `window.__*Module` as split-child stashes, `window.mediaPipeline*` as namespace exports, and the remaining names as flat exports.
4. Search `DesktopApp/mediapipeline_desktop_app`, `DesktopApp/tests`, and `SmokeTests` for external `window.<name>` consumers.
5. Mark a flat export as a candidate when no external `window.<name>` consumer was found.
6. Parse top-level public functions in `DesktopApp/mediapipeline_desktop_app/application/**/*.py` and flag names with no external token references.

Confidence is intentionally conservative:

- **High:** no external `window.<name>` consumer and no external bare-name token reference found.
- **Medium:** no external `window.<name>` consumer, but bare-name references exist, usually from tests, docs, or sibling split modules.
- **Python medium:** no external token reference found. These often mean "public helper that is actually local to its policy file," not dead behavior.

The scan does not prove that a function implementation is dead. For JS, many candidates are still called internally or through namespace objects. The likely cleanup is often to remove only the flat `window.name = name` compatibility assignment after tests move to the namespace, not to remove the function.

---

## Summary

| Surface | Count |
|---|---:|
| JS `window.*` assignments scanned | 1284 |
| JS flat exports scanned | 1192 |
| JS flat exports with no external `window.<name>` consumer | 973 |
| JS high-confidence flat-export candidates | 154 |
| JS medium-confidence flat-export candidates | 819 |
| Python public top-level functions scanned | 431 |
| Python public helpers with no external token reference | 133 |

The high JS candidate count is expected after the split work. The frontend still exposes many helpers twice: once through `window.mediaPipelineXxxView = { ... }` and once as a direct `window.helperName = helperName` flat export. That compatibility surface is useful during transition but should not grow indefinitely.

---

## JS Candidate Hotspots

| File | Candidate flat exports | Interpretation |
|---|---:|---|
| `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/pendingPublishView.js` | 117 | Large compatibility surface after child splits; review namespace coverage before removing flat exports. |
| `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/settingsView.js` | 116 | Builder split left many parent helpers globally exposed for tests and old call sites. |
| `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/completedView.js` | 115 | Completed view has many read-only evidence helpers that are probably namespace/test-only now. |
| `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/queueView.js` | 89 | Queue parent still owns command paths, but many render helpers may not need flat globals. |
| `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/diagnosticsView.js` | 83 | Diagnostics split children consumed several helpers but flat compatibility exports remain broad. |
| `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/launchView.js` | 79 | Command flow must stay stable; only remove flat exports after browser smokes prove Launch still wires correctly. |
| `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/renameView.js` | 56 | Likely test/support exports; review after Rename smoke coverage is confirmed. |
| `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/commandHistory.js` | 53 | Good first cleanup target because the module is shared and many helpers are evidence-only. |
| `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/crossPageContextView.js` | 48 | Cross-page handoffs require caution; verify Home/Sample Validation browser smokes before removal. |
| `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/reportsView.js` | 40 | Lower-risk read-only page; good candidate after Command History. |

---

## High-Confidence JS Samples

These had no external `window.<name>` consumer and no external bare-name token reference in the scanned code/test roots.

**Resolution note, 2026-05-19:** The first cleanup chunk removed 22 high-confidence direct `window.*` compatibility assignments from `commandHistory.js` while keeping the functions in `window.mediaPipelineCommandHistory`. The second cleanup chunk removed 15 high-confidence direct globals from `contractView.js` and `reportsView.js` while keeping the functions in `window.mediaPipelineContractView` and `window.mediaPipelineReportsView`. The third cleanup chunk removed 7 high-confidence direct globals from `diagnosticsBridge.js`, `diagnosticsStateSummaryView.js`, `domHelpers.js`, and `formatters.js` while keeping those functions in their namespace objects. The fourth cleanup chunk removed 20 high-confidence direct globals from `launchHistoryView.js`, `launchReadinessView.js`, `networkView.js`, and `progressView.js` while keeping those functions in `window.mediaPipelineLaunchHistoryView`, `window.mediaPipelineLaunchReadinessView`, `window.mediaPipelineNetworkView`, and `window.mediaPipelineProgressView`. The fifth cleanup chunk removed 23 high-confidence direct globals from `maintenanceView.js`, `scheduleView.js`, and `settingsOverview.js` while keeping those functions in `window.mediaPipelineMaintenanceView`, `window.mediaPipelineScheduleView`, and `window.mediaPipelineSettingsOverview`. The sixth cleanup chunk removed 19 high-confidence direct globals from `settingsView.js` while keeping those functions in `window.mediaPipelineSettingsView`. The seventh cleanup chunk removed 48 high-confidence direct globals from `completedView.js`, `pendingPublishView.js`, `diagnosticsView.js`, `renameView.js`, and `queueView.js` while keeping those functions in their canonical namespace objects. The eighth cleanup chunk moved test-only and app-orchestrator consumers to namespace access and removed 84 more direct compatibility assignments across command history, cross-page context, launch, maintenance, network, pending publish, reports, schedule, settings, telemetry, and related parent modules. The ninth cleanup chunk removed 260 additional test-only/runtime-unreferenced direct aliases while preserving the `window.mediaPipeline*` namespace objects; the current generated flat export total is 756. The resolved rows remain below as audit history; do not treat those Command History, Contract, Reports, Diagnostics bridge/state-summary, DOM helper, formatter, Launch history/readiness, Network, Progress, Maintenance, Schedule, Settings Overview, Settings View, Completed, Pending Publish, Diagnostics, Rename, Queue, Cross-Page Context, or Telemetry rows as still-open.

| Export | File/Line | Suggested disposition |
|---|---|---|
| `renderCommandHistory` | `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/commandHistory.js:1903` | Check if namespace `mediaPipelineCommandHistory.renderCommandHistory` is sufficient; consider removing flat export only. |
| `commandHistorySignature` | `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/commandHistory.js:1907` | Internal helper candidate; keep function, remove flat export if tests do not need it. |
| `commandHistoryOwnerCounts` | `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/commandHistory.js:1922` | Same as above. |
| `commandHistoryFinalPlacementApplies` | `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/commandHistory.js:1931` | Evidence helper; verify no browser test uses direct global. |
| `commandHistoryFinalPlacementProofRows` | `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/commandHistory.js:1932` | Evidence helper; candidate for namespace-only access. |
| `commandHistoryEvidenceCandidates` | `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/commandHistory.js:1938` | Candidate for internal-only or namespace-only access. |
| `renderCommandDiagnosticsActions` | `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/commandHistory.js:1959` | Verify diagnostics and command-evidence smokes before removal. |
| `completedListText` | `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/completedView.js:1043` | Likely internal formatter; remove flat export only if namespace tests do not rely on it. |
| `completedOpenHistoryLine` | `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/completedView.js:1145` | Internal render helper candidate. |
| `contractSafetyStatus` | `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/contractView.js:500` | Contract page is read-only; good small removal candidate. |
| `contractSafetySummaryLines` | `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/contractView.js:501` | Same as above. |
| `diagnosticsBridgeActionGroupText` | `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/diagnosticsBridge.js:226` | Shared bridge helper; confirm consumers use namespace/other exported helpers. |
| `diagnosticsStateTriageStatusText` | `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/diagnosticsStateSummaryView.js:635` | Read-only status helper candidate. |
| `diagnosticsStateSummaryStatusText` | `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/diagnosticsStateSummaryView.js:638` | Read-only status helper candidate. |
| `diagnosticsActionLabel` | `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/diagnosticsView.js:1222` | Caution: Diagnostics action naming is shared by UI handoff flows. Remove only with diagnostics smoke coverage. |
| `stateFromStatusText` | `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/domHelpers.js:323` | Shared helper candidate; review tests first. |
| `scrollSelectedRowIntoView` | `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/domHelpers.js:329` | Shared helper candidate; keep behavior stable for large-table smokes. |
| `launchReadinessSettingsNeedsReview` | `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/launchReadinessView.js:230` | Read-only Launch readiness helper; safe candidate after Launch readiness smoke. |
| `maintenanceProgressStatus` | `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/maintenanceView.js:819` | Maintenance route evidence helper; avoid changing command behavior. |
| `networkOpenTargets` | `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/networkView.js:1346` | Network page remains read-only; candidate after Network browser smoke. |

---

## Python Candidate Hotspots

| File | Candidate public helpers | Interpretation |
|---|---:|---|
| `DesktopApp/mediapipeline_desktop_app/application/facade_pending_publish_policy.py` | 28 | Many functions are file-local policy helpers but lack `_` prefixes or `__all__` boundary. Do not delete before direct tests are reviewed. |
| `DesktopApp/mediapipeline_desktop_app/application/facade_queue_policy.py` | 24 | Similar to Pending Publish; public-looking helper names are likely used internally to build route payloads. |
| `DesktopApp/mediapipeline_desktop_app/application/facade_completed_policy.py` | 21 | Completed output policy helpers should be converted to explicit public/private boundary before removal decisions. |
| `DesktopApp/mediapipeline_desktop_app/application/facade_status_policy.py` | 13 | Many small extractors may be intentionally local. |
| `DesktopApp/mediapipeline_desktop_app/application/facade_maintenance_policy.py` | 11 | Maintenance/readiness helpers require route tests before cleanup. |

Representative Python candidates:

- `facade_artifact_freshness.py`: `format_age_seconds`, `iso_from_timestamp`, `parse_iso_datetime`, `age_seconds_from_datetime`
- `facade_completed_policy.py`: `completed_inventory_progress_payload`, `completed_row_available_open_targets`, `completed_row_trust_fields`, `completed_runtime_outcome_indices`
- `facade_pending_publish_policy.py`: `pending_publish_row_ready_to_drain`, `pending_publish_row_diagnostics`, `pending_publish_recovery_summary`, `pending_publish_open_result_data`
- `facade_queue_policy.py`: `queue_row_available_open_targets`, `queue_row_trust_fields`, `queue_media_type_label`, `queue_open_result_data`
- `facade_schedule_policy.py`: `parse_schedule_day_windows`, `schedule_grid_from_day_windows`, `schedule_command_severity`

These should be handled by the public/internal API boundary workstream, not by ad hoc deletion.

---

## Recommended Cleanup Order

1. **Command History flat exports:** first pass complete for 22 high-confidence direct globals; continue only if tests can move any remaining medium-confidence helpers to namespace access.
2. **Contract/Reports read-only pages:** first pass complete for 15 high-confidence direct globals; continue only if remaining medium-confidence helpers can be moved away from direct global test/call-site assumptions.
3. **Diagnostics state summary, bridge, DOM helper, and formatter helpers:** first pass complete for 7 high-confidence direct globals; continue only if remaining medium-confidence helpers can be moved away from direct global test/call-site assumptions.
4. **Launch history/readiness, Network, and Progress read-only exports:** first pass complete for 20 high-confidence direct globals; continue only if remaining medium-confidence helpers can be moved away from direct global test/call-site assumptions.
5. **Maintenance, Schedule, and Settings Overview read-only exports:** first pass complete for 23 high-confidence direct globals; continue only if remaining medium-confidence helpers can be moved away from direct global test/call-site assumptions.
6. **Settings parent exports:** first pass complete for 19 high-confidence direct globals; continue only if remaining medium-confidence helpers can be moved away from direct global test/call-site assumptions.
7. **Completed/Pending/Diagnostics/Rename/Queue parent exports:** first pass complete for 48 high-confidence direct globals; continue only if remaining medium-confidence helpers can be moved away from direct global test/call-site assumptions.
8. **Test-only namespace migration:** first pass complete for 84 direct compatibility globals; browser/VM smoke harnesses now use namespace promotion only inside test sandboxes, while production `app.js` calls namespace objects directly for removed aliases.
9. **Tests-only flat export cleanup:** first pass complete for 260 additional test-only/runtime-unreferenced direct aliases; generated global-export inventory now reports 756 flat exports.
10. **Launch parent exports:** continue only with Launch browser smoke and command-evidence tests green in the same chunk. Launch has higher operator-safety relevance.
11. **Python policy helper boundaries:** add `__all__` and underscore truly file-local helpers as explicit boundary chunks. Do not delete helpers until route payload tests prove they are unreachable.

---

## Do Not Do

- Do not mass-delete flat exports across all WebView files.
- Do not remove a function implementation just because the flat `window.*` export appears unused.
- Do not remove Queue, Launch, Pending Publish, Diagnostics, or Completed helpers without running the page-specific mutation-boundary and browser smokes.
- Do not turn this audit into a hard gate until the compatibility-export policy is agreed and documented in `WEBVIEW_GLOBAL_EXPORT_INVENTORY.md`.

---

## Suggested Validation For Any Removal Chunk

```powershell
DesktopApp\Runtime\Python\python.exe -m pytest DesktopApp\tests\test_webview_inventory_docs.py DesktopApp\tests\test_webview_navigation_static.py DesktopApp\tests\test_webview_frontend_mutation_boundary.py -q
DesktopApp\Runtime\Python\python.exe -m unittest DesktopApp.tests.test_application_facade_web_static DesktopApp.tests.test_webview_command_evidence_smoke DesktopApp.tests.test_webview_diagnostics_owner_handoff_smoke DesktopApp.tests.test_webview_row_detail_smoke -q
```

Add the relevant browser smoke for the page whose flat exports are removed.
