# Network View Troubleshooting Refactor - Phase 0 Baseline

Date: 2026-06-25
Change packet: MP-CHANGE-2026-0625-001
Phase: 0 only

## Scope

Phase 0 records the live Network WebView contract and prepares guardrails for
a future parent-plus-child asset set. No Network functions were moved, no
backend routes were changed, and
`apps/desktop/webview/static/assets/networkView.js` remains the only runtime
Network script in `index.html`.

The worktree was already broadly dirty before this packet, including generated
docs, many backend/test files, untracked change packets, and unrelated WebView
assets. Phase 0 changes must stay limited to the files recorded in
MP-CHANGE-2026-0625-001.

## Asset And Script Baseline

| Item | Baseline |
|---|---|
| Parent facade | `apps/desktop/webview/static/assets/networkView.js` |
| Current script tag | `/assets/networkView.js` after `/assets/settingsView.js` and before `/assets/diagnosticsTailView.js` |
| Planned child slots | `assets/network/*.js` as listed in `README.md` |
| Public namespace | `window.mediaPipelineNetworkView` |
| Namespace export count | 92 |
| Backend route authority | Local API contract metadata and backend handlers |
| Frontend route rule | Do not hard-code Network command routes; derive from `/api/contract` |
| Dry-run rule | WebView stale-dry-run checks are conservative UI blocks only; backend routes remain authoritative |
| Strict confirmations | Preserve `confirm_start`, `confirm_stop`, `confirm_create`, `confirm_rotate`, and `confirm_import` |

## Direct Caller Baseline

| Caller | Direct Network namespace use |
|---|---|
| `apps/desktop/webview/static/assets/app.js` | `renderNetworkView`, `initNetworkViewEvents` |
| `apps/desktop/webview/static/assets/commandHistory.js` | `renderNetworkOpenHistory` |
| `apps/desktop/webview/static/assets/settingsView.js` | `runNetworkWorkerTestConnection` |
| `apps/desktop/webview/static/assets/settingsView.builders.network.js` | `runNetworkWorkerTestConnection`, `renderNetworkSettingsPatchHandoff` |
| `tests/webview/test_webview_browser_network_smoke.py` | Browser checks for public functions, `renderNetworkView`, lifecycle helpers, setup helpers, and worker-test override |
| `tests/webview/test_webview_command_evidence_smoke.py` | `renderNetworkOpenHistory` |
| Static/source guard tests | Source assertions for `networkView.js`, `apiPost(route, request)`, dynamic command dispatch, and `network_view_js` bundle content |

## Source-Only Guardrail Baseline

Stop-condition correction, 2026-06-26:
`tests/python/desktop/application_facade_test_support.py` is not currently
parent-plus-child aware for served static Network assertions. The live helper
still fetches only `/assets/networkView.js` into `network_view_js`. Treat that
as a blocker before extracting protected Network functions or text out of the
parent unless the served-static helper is migrated to read the ordered Network
parent-plus-child asset set, or the affected served-static assertions are
explicitly narrowed to parent-only facade checks.

| Guardrail | Phase 0 handling |
|---|---|
| `tests/webview/test_webview_network_read_only_boundary.py` | Added ordered Network asset helper that reads existing child slots plus the parent facade. |
| `tests/webview/test_webview_frontend_mutation_boundary.py` | Added ordered Network asset helper and limited dynamic dispatch allowance to parent, lifecycle command child, or setup command child. |
| `tests/webview/test_webview_command_boundary_audit.py` | Allows the dynamic Network command dispatcher to be reported from the parent or planned command children. |
| `tests/python/desktop/application_facade_test_support.py` | Not migrated. Live served-static helper still fetches only `/assets/networkView.js` into `network_view_js`; migrate it or explicitly scope served-static assertions to parent-only facade checks before extraction. |
| `tests/python/desktop/test_application_facade_web_static.py` | Reads the Network asset bundle for broad source assertions. |
| `tests/python/desktop/test_application_facade_web_static_diagnostics_reports.py` | Continues using `bundle.network_view_js`; in served-static coverage that field is currently parent-only through `application_facade_test_support.py`, so assertions must be migrated or narrowed before protected text/functions move. |
| `tests/python/desktop/test_application_facade_web_static_shell.py` | Keeps parent order assertions and adds optional ordering for any future child scripts before `networkView.js`. |
| `ops/scripts/dev/check-webview-command-boundary.mjs` | Dynamic `apiPost(route, request)` remains narrow and can live only in the parent or planned Network command children. |

## Route Baseline

| Route | Effect | Phase 0 frontend rule |
|---|---|---|
| `GET /api/network/workers` | `none` | Read-only worker evidence. |
| `POST /api/network/coordinator/start-dry-run` | `none` | Contract-derived lifecycle dry-run route. |
| `POST /api/network/coordinator/stop-dry-run` | `none` | Contract-derived lifecycle dry-run route. |
| `POST /api/network/worker/start-dry-run` | `none` | Contract-derived lifecycle dry-run route. |
| `POST /api/network/worker/stop-dry-run` | `none` | Contract-derived lifecycle dry-run route. |
| `POST /api/network/worker/test-connection` | `none` | Contract-derived setup route; no lifecycle start. |
| `POST /api/network/worker/discover-coordinators` | `none` | Contract-derived setup route; stages Settings intent only. |
| `POST /api/network/coordinator/join-blob` | `secret-transfer` | Contract-derived setup route; requires `confirm_create`, and `confirm_rotate` when rotating. |
| `POST /api/network/worker/join-cluster` | `config-write` | Contract-derived setup route; requires `confirm_import`. |
| `POST /api/network/coordinator/start` | `backend-lifecycle` | Contract-derived confirmed lifecycle route; requires fresh dry-run and `confirm_start`. |
| `POST /api/network/coordinator/stop` | `backend-lifecycle` | Contract-derived confirmed lifecycle route; requires fresh dry-run and `confirm_stop`. |
| `POST /api/network/worker/start` | `backend-lifecycle` | Contract-derived confirmed lifecycle route; requires fresh dry-run and `confirm_start`. |
| `POST /api/network/worker/stop` | `backend-lifecycle` | Contract-derived confirmed lifecycle route; requires fresh dry-run and `confirm_stop`. |
| `POST /api/diagnostics/open` | `shell-open` | Diagnostics target allowlist remains backend-owned. |

## DOM Baseline

`docs/inventories/WEBVIEW_DOM_ID_INVENTORY.md` currently lists 169 Network and
Network-settings DOM IDs with the `network-` or `settings-network-` prefixes.
The active page partial is
`apps/desktop/webview/static/partials/page-network.html`.

Key troubleshooting regions:

| Region | Representative IDs |
|---|---|
| Status and diagnostics | `network-status`, `network-status-banner-lines`, `network-diagnostic-rail`, `network-attention-stack`, `network-topology-strip` |
| Lifecycle controls | `network-lifecycle-control-buttons`, `network-lifecycle-confirm-dialog`, `network-lifecycle-command-result`, `network-lifecycle-rows` |
| Setup and join | `network-coordinator-join-create`, `network-coordinator-join-output`, `network-worker-discover`, `network-worker-join-import` |
| Settings handoff | `network-settings-patch-handoff`, `network-settings-preview-button`, `network-settings-save-button`, `settings-network-role` |
| Runtime evidence | `network-evidence-rows`, `network-state-files-rows`, `network-worker-rows`, `network-worker-progress-bars` |
| Open history | `network-open-history`, `network-open-history-status` |

## Public Export Ledger

All rows keep a parent `window.mediaPipelineNetworkView` wrapper until a later
contract-change packet updates inventories and tests.

| Export | Current signature | Target owner | Known callers |
|---|---|---|---|
| `networkRows` | `function networkRows(settings)` | `network/config.js` | Static/browser tests |
| `syncNetworkRoleDashboards` | `function syncNetworkRoleDashboards(config)` | `network/roleDashboard.js` | Browser smoke |
| `networkCoordinatorOverviewModel` | `function networkCoordinatorOverviewModel({ queue, networkWorkers } = {})` | `network/roleDashboard.js` | Browser smoke |
| `networkWorkerOverviewModel` | `function networkWorkerOverviewModel({ config, contract, networkWorkers, queue } = {})` | `network/roleDashboard.js` | Browser smoke |
| `renderNetworkRoleDashboards` | `function renderNetworkRoleDashboards({ queue, networkWorkers, config, contract } = {})` | `network/roleDashboard.js` | Static/browser tests |
| `renderCoordinatorActiveRows` | `function renderCoordinatorActiveRows(model)` | `network/roleDashboard.js` | Public namespace |
| `renderCoordinatorQueueRows` | `function renderCoordinatorQueueRows(model)` | `network/roleDashboard.js` | Public namespace |
| `renderWorkerClaimRows` | `function renderWorkerClaimRows(model)` | `network/roleDashboard.js` | Public namespace |
| `visibleNetworkMode` | `function visibleNetworkMode(config)` | `network/config.js` | Public namespace |
| `visibleNetworkModeLabel` | `function visibleNetworkModeLabel(config)` | `network/config.js` | Public namespace |
| `networkReadinessLines` | `function networkReadinessLines({ role, config, closeReadiness, snapshot, contract, networkWorkers })` | `network/readiness.js` | Static tests |
| `networkRuntimeStatus` | `function networkRuntimeStatus(networkWorkers, config)` | `network/status.js` | Static/browser tests |
| `networkStatusTone` | `function networkStatusTone(status)` | `network/status.js` | Static/browser tests |
| `networkDiagnosticLayerByKey` | `function networkDiagnosticLayerByKey(networkWorkers, key)` | `network/status.js` | Static/browser tests |
| `renderNetworkDiagnosticRail` | `function renderNetworkDiagnosticRail(networkWorkers = {})` | `network/status.js` | Browser smoke |
| `networkWorkerDriftPayload` | `function networkWorkerDriftPayload(networkWorkers)` | `network/status.js` | Static tests |
| `networkWorkerDriftFieldText` | `function networkWorkerDriftFieldText(drift)` | `network/status.js` | Static tests |
| `networkWorkerDriftStatusText` | `function networkWorkerDriftStatusText(drift)` | `network/status.js` | Static tests |
| `networkWorkerDriftSummaryLines` | `function networkWorkerDriftSummaryLines(drift)` | `network/status.js` | Static tests |
| `renderNetworkStatusBanner` | `function renderNetworkStatusBanner(payload = {}, config = {})` | `network/status.js` | Static/browser tests |
| `obviousWorkerCoordinatorUrlIssue` | `function obviousWorkerCoordinatorUrlIssue(value, { required = true } = {})` | `network/config.js` | Static tests |
| `networkLifecycleMutationRouteCount` | `function networkLifecycleMutationRouteCount(contract)` | `network/contract.js` | Static tests |
| `networkAttentionItems` | `function networkAttentionItems(networkWorkers = {})` | `network/status.js` | Static tests |
| `renderNetworkAttentionStack` | `function renderNetworkAttentionStack(networkWorkers = {})` | `network/status.js` | Static tests |
| `networkTopologyNodes` | `function networkTopologyNodes(config = {}, networkWorkers = {})` | `network/status.js` | Static tests |
| `renderNetworkTopologyStrip` | `function renderNetworkTopologyStrip(config = {}, networkWorkers = {})` | `network/status.js` | Static tests |
| `renderNetworkActionReadinessGates` | `function renderNetworkActionReadinessGates(payload = {}, config = {})` | `network/status.js` | Static tests |
| `networkLifecycleDryRunRouteCount` | `function networkLifecycleDryRunRouteCount(contract)` | `network/contract.js` | Static tests |
| `networkSetupMutationRouteSummary` | `function networkSetupMutationRouteSummary(contract)` | `network/contract.js` | Static tests |
| `networkLifecycleRouteRow` | `function networkLifecycleRouteRow(contract, role, action, dryRun)` | `network/contract.js` | Static tests |
| `networkLifecycleRoutePath` | `function networkLifecycleRoutePath(contract, role, action, dryRun)` | `network/contract.js` | Static tests |
| `networkLifecycleRouteAvailable` | `function networkLifecycleRouteAvailable(contract, role, action, dryRun)` | `network/contract.js` | Static tests |
| `networkLifecycleDryRunAllowsConfirmed` | `function networkLifecycleDryRunAllowsConfirmed(payload = {}, config = {}, role = "", action = "")` | `network/lifecycle.model.js` | Browser smoke |
| `networkWorkerTestConnectionRoute` | `function networkWorkerTestConnectionRoute(contract)` | `network/contract.js` | Browser smoke |
| `networkWorkerDiscoverCoordinatorsRoute` | `function networkWorkerDiscoverCoordinatorsRoute(contract)` | `network/contract.js` | Browser smoke |
| `networkCoordinatorJoinBlobRoute` | `function networkCoordinatorJoinBlobRoute(contract)` | `network/contract.js` | Browser smoke |
| `networkWorkerJoinClusterRoute` | `function networkWorkerJoinClusterRoute(contract)` | `network/contract.js` | Browser smoke |
| `networkLifecycleRelevantRole` | `function networkLifecycleRelevantRole(config)` | `network/lifecycle.model.js` | Static tests |
| `networkLifecycleRelevantRoles` | `function networkLifecycleRelevantRoles(config)` | `network/lifecycle.model.js` | Browser smoke |
| `networkLifecycleControlLines` | `function networkLifecycleControlLines(payload = {}, config = {})` | `network/lifecycle.model.js` | Static tests |
| `networkLifecycleCommandResultLines` | `function networkLifecycleCommandResultLines(result)` | `network/lifecycle.commands.js` | Browser smoke |
| `networkTestConnectionResultLines` | `function networkTestConnectionResultLines(result)` | `network/setup.commands.js` | Static tests |
| `networkCoordinatorDiscoveryResultLines` | `function networkCoordinatorDiscoveryResultLines(result)` | `network/setup.commands.js` | Static tests |
| `renderNetworkCoordinatorDiscoveryList` | `function renderNetworkCoordinatorDiscoveryList(result)` | `network/setup.commands.js` | Static tests |
| `discoverNetworkCoordinators` | `async function discoverNetworkCoordinators()` | `network/setup.commands.js` | Browser smoke |
| `stageDiscoveredCoordinatorUrl` | `function stageDiscoveredCoordinatorUrl(url)` | `network/setup.commands.js` | Static tests |
| `networkJoinBlobResultLines` | `function networkJoinBlobResultLines(result)` | `network/setup.commands.js` | Static tests |
| `networkJoinImportResultLines` | `function networkJoinImportResultLines(result)` | `network/setup.commands.js` | Static tests |
| `networkLifecycleRows` | `function networkLifecycleRows({ role, config, closeReadiness, snapshot, contract, networkWorkers } = {})` | `network/lifecycle.model.js` | Browser smoke |
| `networkLifecycleStatus` | `function networkLifecycleStatus(rows = [])` | `network/lifecycle.model.js` | Static tests |
| `networkLifecycleSummaryLines` | `function networkLifecycleSummaryLines(rows = [])` | `network/lifecycle.model.js` | Static tests |
| `networkLifecycleDetailLines` | `function networkLifecycleDetailLines(row)` | `network/lifecycle.model.js` | Static tests |
| `renderNetworkLifecycleHandoff` | `function renderNetworkLifecycleHandoff(payload, role, config)` | `network/lifecycle.view.js` | Browser smoke |
| `networkEvidenceRows` | `function networkEvidenceRows({ role, config, closeReadiness, snapshot, contract, networkWorkers } = {})` | `network/readiness.js` | Static tests |
| `networkEvidenceStatus` | `function networkEvidenceStatus(rows = [])` | `network/readiness.js` | Static tests |
| `networkEvidenceSummaryLines` | `function networkEvidenceSummaryLines(rows = [])` | `network/readiness.js` | Static tests |
| `renderNetworkEvidenceChecklist` | `function renderNetworkEvidenceChecklist(payload, role, config)` | `network/readiness.js` | Static tests |
| `networkStateFileRows` | `function networkStateFileRows(networkWorkers)` | `network/stateFiles.js` | Static tests |
| `networkStateFileStatus` | `function networkStateFileStatus(item)` | `network/stateFiles.js` | Static tests |
| `networkStateFileSummaryLines` | `function networkStateFileSummaryLines(rows = [])` | `network/stateFiles.js` | Static tests |
| `networkStateFileDetailLines` | `function networkStateFileDetailLines(item)` | `network/stateFiles.js` | Static tests |
| `renderNetworkStateFiles` | `function renderNetworkStateFiles(networkWorkers)` | `network/stateFiles.js` | Browser smoke |
| `networkWorkerRowKey` | `function networkWorkerRowKey(item)` | `network/workers.model.js` | Static/browser tests |
| `networkWorkerStatusState` | `function networkWorkerStatusState(item)` | `network/workers.model.js` | Browser smoke |
| `networkWorkerFilterText` | `function networkWorkerFilterText(item)` | `network/workers.model.js` | Static tests |
| `filteredNetworkWorkerRows` | `function filteredNetworkWorkerRows(rows)` | `network/workers.model.js` | Static tests |
| `networkWorkerDetailLines` | `function networkWorkerDetailLines(item)` | `network/workers.model.js` | Static tests |
| `workerLastResultText` | `function workerLastResultText(item)` | `network/workers.model.js` | Static tests |
| `workerThroughputText` | `function workerThroughputText(item)` | `network/workers.model.js` | Static tests |
| `renderNetworkWorkerDetail` | `function renderNetworkWorkerDetail(item)` | `network/workers.view.js` | Static tests |
| `renderNetworkWorkerProgress` | `function renderNetworkWorkerProgress(networkWorkers)` | `network/workers.view.js` | Static tests |
| `networkWorkerProgressStatus` | `function networkWorkerProgressStatus(progress)` | `network/workers.model.js` | Static tests |
| `networkWorkerProgressSummaryLines` | `function networkWorkerProgressSummaryLines(progress)` | `network/workers.model.js` | Static tests |
| `selectNetworkWorkerRow` | `function selectNetworkWorkerRow(item)` | `network/workers.view.js` | Public namespace |
| `initNetworkViewEvents` | `function initNetworkViewEvents()` | `networkView.js` parent facade | `app.js`, static tests |
| `renderNetworkWorkers` | `function renderNetworkWorkers(networkWorkers)` | `network/workers.view.js` | Static tests |
| `renderNetworkWorkerRows` | `function renderNetworkWorkerRows(networkWorkers)` | `network/workers.view.js` | Browser/static tests |
| `networkOpenTargets` | `function networkOpenTargets()` | `network/openHistory.js` | Static tests |
| `isNetworkOpenCommand` | `function isNetworkOpenCommand(entry)` | `network/openHistory.js` | Static tests |
| `networkOpenHistoryLine` | `function networkOpenHistoryLine(entry)` | `network/openHistory.js` | Static tests |
| `renderNetworkOpenHistory` | `function renderNetworkOpenHistory(history = [])` | `network/openHistory.js` | `commandHistory.js`, command evidence smoke |
| `renderNetworkSettingsPatchHandoff` | `function renderNetworkSettingsPatchHandoff(message = "")` | `network/settingsHandoff.js` | `settingsView.builders.network.js` |
| `renderNetworkLifecycleControls` | `function renderNetworkLifecycleControls(payload = {}, role = "standalone", config = {})` | `network/lifecycle.view.js` | Static tests |
| `runGuidedNetworkLifecycleCommand` | `async function runGuidedNetworkLifecycleCommand(button)` | `network/lifecycle.commands.js` | Static/browser tests |
| `runNetworkLifecycleCommand` | `async function runNetworkLifecycleCommand(button)` | `network/lifecycle.commands.js` | Static tests |
| `runNetworkWorkerTestConnection` | `async function runNetworkWorkerTestConnection(options = {})` | `network/setup.commands.js` | `settingsView.js`, `settingsView.builders.network.js`, browser smoke |
| `createNetworkJoinBlob` | `async function createNetworkJoinBlob()` | `network/setup.commands.js` | Browser smoke |
| `copyNetworkJoinBlob` | `async function copyNetworkJoinBlob()` | `network/setup.commands.js` | Static tests |
| `importNetworkJoinBlob` | `async function importNetworkJoinBlob()` | `network/setup.commands.js` | Browser smoke |
| `previewNetworkSettingsPatch` | `async function previewNetworkSettingsPatch()` | `network/settingsHandoff.js` | Static tests |
| `saveNetworkSettingsPatch` | `async function saveNetworkSettingsPatch()` | `network/settingsHandoff.js` | Static tests |
| `renderNetworkView` | `function renderNetworkView(payload = {})` | `networkView.js` parent facade | `app.js`, browser smoke |

## Phase 0 Rollback

Revert the Phase 0 files recorded in MP-CHANGE-2026-0625-001, delete this
baseline document, and restore the command-boundary script to accepting only
`apps/desktop/webview/static/assets/networkView.js` as the dynamic Network
dispatcher. No backend rollback is required because Phase 0 does not touch
backend routes, schemas, process lifecycle, settings persistence, filesystem
mutation, or media policy.
