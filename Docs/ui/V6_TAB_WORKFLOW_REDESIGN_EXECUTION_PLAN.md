# V6 Tab Workflow Redesign Execution Plan

Last updated: 2026-05-20

Purpose: track the operator-requested 13-tab WebView workflow redesign from planning through implementation. This plan is active guidance for UI work only. It does not approve moving filesystem, launch, publish, rename, settings-save, failure-clear, or worker lifecycle authority into the frontend.

## Authority Boundary

- Frontend JavaScript may render, stage UI state, and call documented backend routes through `apiClient.js`.
- Backend remains the owner for pipeline control, queue priority/exclusion writes, output open targets, pending publish drain, rename preview/apply, failure clear, schedule save, worker lifecycle, settings preview/save, diagnostics open/tail, and shutdown.
- New mutation routes require schema, inventory, tests, confirmation/selector payloads, and explicit operator approval for semantics.
- Work must follow `AGENTS.md`: one parent view per code chunk, no namespace export removals, no module-scope state moves, update inventories when DOM IDs/routes/exports/tests change, and run gates before marking a chunk done.

## Execution Order

The first pass prioritizes layout clarity and controls that can reuse existing backend routes. Deeper workflow redesigns follow after the current panels are mapped and their route coverage is confirmed.

1. Low-risk visual simplification: Dashboard, Telemetry, Diagnostics tab order, Launch tab order.
2. Workflow reboxing: Launch controls, Publish top action, Output selected-file summary/open action.
3. Reports actionability: multi-select, clearer failure columns, clear selected/all commands if backend support exists.
4. Queue redesign: simplified queue-first layout, refresh-first workflow, priority/exclusion controls.
5. Rename redesign: unified browse, staged-file list, pipeline name-cleaning preview, bulk settings.
6. Settings redesign: structured selectors, profiles, subtitles subtab, codec/flag/default controls, worker controls removed from Settings.
7. Schedule copy-day utility and Workers setup wizard after related route/settings surfaces are confirmed.

## Tab Plan

| # | Main tab | Operator request | Implementation approach | Backend authority needed | Status |
|---:|---|---|---|---|---|
| 1 | Dashboard | Make `At a glance`, `Recently completed`, and `Run progress` normal panels; add Pause/Stop/Kill quick controls. | Restyle those panels away from evidence treatment. Add quick controls that call existing pipeline-control route with confirmation for dangerous actions. | Existing `/api/pipeline/control` route. | Completed 2026-05-20 |
| 2 | Telemetry | Make telemetry normal, remove duplicated NVENC `0%`, remove idle wording. | Restyle telemetry panels as normal. Keep the numeric top-right metric and remove redundant left-side/idle copy. | None unless telemetry payload changes are later needed. | Completed 2026-05-20 |
| 3 | Queue | Simplify Queue; refresh first; show rows clearly; set priority and exclusions; make Queue central; propose 10 improvements. | Redesign layout around refresh, queue table, selected row action strip, priority/exclusion controls, and collapsed advanced evidence. | Existing queue read, priority, strategy, file override routes; confirm exclusion/unblock semantics before adding controls. | In progress - table-first pass completed 2026-05-20 |
| 4 | Output | Keep size check; select output and open/play in default player; narrower selected review with important changes. | Rebox selected output summary and route/sidecar/size proof. Add open/play action using backend selected-row open target. | Existing completed open route if it supports file open; otherwise backend route extension needed. | Planned |
| 5 | Publish | Put `Publish Parked Outputs` first; better results display similar to Output. | Move drain/publish action to top primary surface and render parked results with selected-row detail. | Existing pending publish drain route and recovery/read routes. | Completed 2026-05-20 |
| 6 | Rename | Unified browse for file/folder; show staged file list; show cleaned-name preview; bulk edit settings; use V4 as reference. | Use one browse surface with selection mode choice, staged files table, preview result table, and bulk settings next to preview. | Existing browse/preview/apply routes; apply remains guarded. | Planned |
| 7 | Launch | Subtab order: Pipeline, Audit, CSV Rerun, History, Readiness. Put buttons with their settings. | Reorder subtabs and move command buttons into their controlling option panels. | Existing launch/audit/rerun/control routes. | Completed 2026-05-20 |
| 8 | Reports | Multi-select failures; clear all button; add recommended action; fix blank reason/stage/class; shorten recorded. | Improve failure table columns, selection model, and clear selected/all actions only through backend command route. | Existing `/api/failures/clear` route; marker-only clearing remains guarded. | Completed 2026-05-20 |
| 9 | Schedule | Fine overall; add copy day/apply to days. | Add copy-day UI and apply target-day controls near schedule editor. | Existing schedule save/preview route after staging copied day. | Completed 2026-05-20 |
| 10 | Workers | Add setup/help wizard. | Add guided setup panel explaining standalone/coordinator/worker paths and required settings. Keep lifecycle controls absent unless backend dry-run routes exist. | Current Network lifecycle contracts are design-only; no mutation controls yet. | Planned |
| 11 | Maintenance | Fine. | Leave unchanged except incidental layout-manager compatibility if affected. | None. | No change planned |
| 12 | Diagnostics | Logs first; `Triage` unclear; Current Progress not useful here. | Reorder diagnostics subtabs to Logs first, rename/de-emphasize Triage, move or demote Current Progress. | Existing diagnostics read/tail/open routes. | Completed 2026-05-20 |
| 13 | Settings | Profiles editable; manual routing unlock clarity; `CPU Max Threads 0` as Unlimited; selectors with descriptions/defaults for flags/codecs/subtitles; subtitle subtab; aggressive parsing controls; remove Open Workers. | Split into structured controls by setting family. Convert raw lists into selectable checkboxes plus add-custom value. Keep Preview/Save Patch backend-owned. | Existing settings workspace/preview/save routes; new config-key controls may require inventory updates. | Planned |

## Queue Improvement Suggestions

1. Make `Refresh Queue` the first primary action.
2. Show the main queue table immediately under the primary controls.
3. Put counts in compact normal status cards: loaded, runnable, blocked, excluded, priority.
4. Move filter controls into a compact toolbar above the table.
5. Add a selected-row action strip for priority, exclusion, open source, diagnostics, and launch handoff.
6. Make blocked/excluded reasons visible in the table without requiring deep evidence panels.
7. Add a `What runs next` normal summary that reflects backend ordering.
8. Collapse advanced launch-scope/evidence panels by default.
9. Use shorter column names and keep paths secondary/expandable.
10. Keep queue mutation controls backend-owned and show command result feedback inline.

Implementation note: `queueView.js` is at 1,450 lines after the table-first pass. Deeper Queue behavior changes should split this parent before adding substantial new logic, per `AGENTS.md`.

## Chunk Checklist

For each code chunk:

1. Confirm target file line counts before editing.
2. Touch one parent view and its directly related child/partial files only.
3. Avoid adding DOM IDs when class/data selectors are enough; if adding IDs, update `WEBVIEW_DOM_ID_INVENTORY.md`.
4. Avoid new `window.*` exports; if unavoidable, update `WEBVIEW_GLOBAL_EXPORT_INVENTORY.md`.
5. Avoid new routes unless backend authority is required and tests/inventories are updated.
6. Run `node --check` for touched JS.
7. Run core WebView static gates from `AGENTS.md`.
8. Run affected browser smoke when a page has one.
9. Update `DOC_TOUCH_LOG.md` only after validation passes.

## Execution Log

| Date | Chunk | Files | Validation | Result |
|---|---|---|---|---|
| 2026-05-20 | Planning document created | `Docs/ui/V6_TAB_WORKFLOW_REDESIGN_EXECUTION_PLAN.md`, `Docs/DOCS_INDEX.md`, `Docs/DOC_TOUCH_LOG.md` | Active docs reference check, WebView inventory docs smoke | In progress |
| 2026-05-20 | Dashboard quick controls and normal summary panels | `DesktopApp/mediapipeline_desktop_app/ui_web/static/partials/page-home.html`, `DesktopApp/tests/test_application_facade_web_static.py`, `Docs/ui/V6_TAB_WORKFLOW_REDESIGN_EXECUTION_PLAN.md`, `Docs/DOC_TOUCH_LOG.md` | `python -m unittest DesktopApp.tests.test_application_facade_web_static -q`; `python -m pytest DesktopApp/tests/test_webview_inventory_docs.py DesktopApp/tests/test_webview_navigation_static.py DesktopApp/tests/test_webview_frontend_mutation_boundary.py -q` | Passed; no DOM IDs, JS globals, routes, command ownership, mutation policy, or backend behavior changed. |
| 2026-05-20 | Telemetry normal panels and zero-percent NVENC simplification | `DesktopApp/mediapipeline_desktop_app/ui_web/static/partials/page-telemetry.html`, `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/telemetryView.js`, `DesktopApp/tests/test_webview_browser_telemetry_smoke.py`, `SmokeTests/Test-WebViewBrowserTelemetrySmoke.ps1`, testing docs | `node --check telemetryView.js`; focused Local API/WebView static/Tauri scaffold tests; browser-backed telemetry smoke; WebView inventory/navigation/mutation-boundary gates | Passed; zero-percent NVENC stays visible while duplicate idle copy is removed. No backend payload, route, mutation policy, media handling, or telemetry sampling behavior changed. |
| 2026-05-20 | Diagnostics logs-first tab order | `DesktopApp/mediapipeline_desktop_app/ui_web/static/partials/page-diagnostics.html`, `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/app.js`, `Docs/ui/V6_TAB_WORKFLOW_REDESIGN_EXECUTION_PLAN.md`, `Docs/DOC_TOUCH_LOG.md` | `node --check app.js`; WebView static/API static/local API static tests; browser-backed diagnostics handoff smoke; WebView inventory/navigation/mutation-boundary gates | Passed; Logs is now first/default, Triage is labeled Overview, Progress is labeled State, and Current Progress is de-emphasized as Runtime Progress Snapshot. No diagnostics routes, open targets, mutation policy, or backend behavior changed. |
| 2026-05-20 | Launch tab order and start-control grouping | `DesktopApp/mediapipeline_desktop_app/ui_web/static/partials/page-launch.html`, `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/launchView.js`, `DesktopApp/tests/test_application_facade_local_api.py`, `DesktopApp/tests/test_webview_browser_launch_queue_readiness_smoke.py`, `Docs/ui/V6_TAB_WORKFLOW_REDESIGN_EXECUTION_PLAN.md`, `Docs/DOC_TOUCH_LOG.md` | `node --check launchView.js`; focused Local API/WebView static tests; browser-backed Launch/Queue readiness smoke; WebView inventory/navigation/mutation-boundary gates | Passed; Launch defaults to Pipeline, tab order is Pipeline/Audit/CSV Rerun/History/Readiness, and Start Pipeline now sits directly below the launch settings before the start-decision evidence. No launch route, payload, backend validation, queue scope, or mutation policy changed. |
| 2026-05-20 | Publish top primary action | `DesktopApp/mediapipeline_desktop_app/ui_web/static/partials/page-pending.html`, `DesktopApp/tests/test_application_facade_local_api.py`, `DesktopApp/tests/test_webview_navigation_static.py`, `Docs/ui/V6_TAB_WORKFLOW_REDESIGN_EXECUTION_PLAN.md`, `Docs/DOC_TOUCH_LOG.md` | focused Local API/WebView static tests; WebView inventory/navigation/mutation-boundary gates; browser-backed pending drain guard and completed/pending proof smokes | Passed; `Publish Parked Outputs` is now the first direct movable panel and the drain button appears before pending status/rows. No pending-publish route, drain guard, backend validation, filesystem mutation policy, or payload behavior changed. |
| 2026-05-20 | Reports failure table usability | `DesktopApp/mediapipeline_desktop_app/ui_web/static/partials/page-reports.html`, `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/reportsView.js`, `DesktopApp/tests/test_application_facade_local_api.py`, `DesktopApp/tests/test_webview_browser_maintenance_reports_smoke.py`, `Docs/inventories/WEBVIEW_DOM_ID_INVENTORY.md`, `Docs/ui/V6_TAB_WORKFLOW_REDESIGN_EXECUTION_PLAN.md`, `Docs/DOC_TOUCH_LOG.md` | `node --check reportsView.js`; focused Local API/WebView static tests; browser-backed Maintenance/Reports smoke; WebView inventory/navigation/mutation-boundary gates | Passed; Failures now has checkbox multi-select, Preview/Clear All marker controls, fallback display text for blank class/stage/reason/action, a Recommended Action column, and shorter recorded timestamps. Failure clearing remains marker-mode-only through `/api/failures/clear`. |
| 2026-05-20 | Schedule copy-day editor staging | `DesktopApp/mediapipeline_desktop_app/ui_web/static/partials/page-schedule.html`, `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/scheduleView.js`, `DesktopApp/tests/test_application_facade_local_api.py`, `DesktopApp/tests/test_webview_schedule_smoke.py`, `Docs/ui/V6_TAB_WORKFLOW_REDESIGN_EXECUTION_PLAN.md`, `Docs/DOC_TOUCH_LOG.md` | `node --check scheduleView.js`; focused schedule smoke and Local API/WebView static tests; WebView inventory/navigation/mutation-boundary gates | Passed; Edit Schedule can copy one staged day to selected target days using data-attribute controls. The copy action only stages editor values; preview/save remain backend-owned through existing schedule routes. No DOM IDs, route, command ownership, app-state write semantics, media policy, queue, publish, rename, settings, or lifecycle behavior changed. |
| 2026-05-20 | Queue table-first layout pass | `DesktopApp/mediapipeline_desktop_app/ui_web/static/partials/page-queue.html`, `DesktopApp/mediapipeline_desktop_app/ui_web/static/assets/queueView.js`, `DesktopApp/tests/test_application_facade_local_api.py`, `Docs/ui/V6_TAB_WORKFLOW_REDESIGN_EXECUTION_PLAN.md`, `Docs/DOC_TOUCH_LOG.md` | `node --check queueView.js`; focused Local API/WebView static tests; row-detail smoke; browser-backed Launch/Queue readiness and layout-manager smokes; WebView inventory/navigation/mutation-boundary gates | Passed; Queue controls now expose Refresh Queue first, Queue Rows moved directly below controls, and priority/hold/strategy controls sit above the table. The refresh button calls the existing backend snapshot refresh flow. No DOM IDs, routes, command ownership, backend launch scope, media policy, settings, publish, rename, or lifecycle behavior changed. |
