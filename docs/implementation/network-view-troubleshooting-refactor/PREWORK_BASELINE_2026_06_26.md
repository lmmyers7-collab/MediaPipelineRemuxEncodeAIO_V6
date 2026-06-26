# Network View Prework Baseline - 2026-06-26

Change packet: MP-CHANGE-2026-0626-009

Scope: prework only. No runtime behavior, route, export, DOM, script-order, or
backend behavior changed.

## Baseline Facts

| Item | Current value |
|---|---:|
| Source file | `apps/desktop/webview/static/assets/networkView.js` |
| Current source line count | 4,087 |
| Public namespace | `window.mediaPipelineNetworkView` |
| Namespace export count from source | 92 |
| Flat exports in `WEBVIEW_GLOBAL_EXPORT_INVENTORY.md` | 0 |
| Script tag | `/assets/networkView.js` |
| Main partial | `apps/desktop/webview/static/partials/page-network.html` |
| Partial Network DOM IDs | 169 unique `network-*` / `settings-network-*` IDs |

`docs/generated/summaries/apps/desktop/webview/static/assets/networkView.js.md`
currently says `Purpose: (unparsed)`, so it is only a navigation hint for this
packet. The ledger below is built from source, inventories, and tests.

Stop-condition blocker: the existing Phase 0 baseline conflicts with current
source. `PHASE_0_BASELINE.md` says
`tests/python/desktop/application_facade_test_support.py` was migrated to read
existing Network child slots plus the parent facade, but the live file still
fetches only `/assets/networkView.js` for `network_view_js` from the served
static assets. Do not proceed to extraction until that served-static guardrail
is made parent-plus-child aware or is explicitly scoped to parent-only facade
assertions.

Other Phase 0 guardrails are already parent-plus-child aware: WebView static
tests know planned `network/*.js` child slots, and `networkView.js` is still
required to remain the public facade.

## Public Export Ledger

All 92 namespace exports must keep a parent
`window.mediaPipelineNetworkView` wrapper until a later contract-change packet
updates inventories and tests. `Source/export` is `function line / namespace
object line`.

Caller shorthand:

- `prod:app` = `app.js` direct production call.
- `prod:command-history` = `commandHistory.js` direct production call.
- `prod:settings` = `settingsView.js` or `settingsView.builders.network.js`.
- `browser` = direct browser-smoke namespace call or override.
- `static` = source/static assertion coverage only.
- `none found` = no non-test direct namespace caller found by source grep.

| Export | Source/export | Current signature | Direct callers | Proposed owner | Parent wrapper |
|---|---:|---|---|---|---|
| `networkRows` | 96 / 3994 | `function networkRows(settings)` | static | `network/config.js` | yes |
| `syncNetworkRoleDashboards` | 727 / 3995 | `function syncNetworkRoleDashboards(config)` | browser | `network/roleDashboard.js` | yes |
| `networkCoordinatorOverviewModel` | 957 / 3996 | `function networkCoordinatorOverviewModel({ queue, networkWorkers } = {})` | browser | `network/roleDashboard.js` | yes |
| `networkWorkerOverviewModel` | 1035 / 3997 | `function networkWorkerOverviewModel({ config, contract, networkWorkers, queue } = {})` | browser | `network/roleDashboard.js` | yes |
| `renderNetworkRoleDashboards` | 1226 / 3998 | `function renderNetworkRoleDashboards({ queue, networkWorkers, config, contract } = {})` | static | `network/roleDashboard.js` | yes |
| `renderCoordinatorActiveRows` | 1162 / 3999 | `function renderCoordinatorActiveRows(model)` | none found | `network/roleDashboard.js` | yes |
| `renderCoordinatorQueueRows` | 1192 / 4000 | `function renderCoordinatorQueueRows(model)` | none found | `network/roleDashboard.js` | yes |
| `renderWorkerClaimRows` | 1213 / 4001 | `function renderWorkerClaimRows(model)` | none found | `network/roleDashboard.js` | yes |
| `visibleNetworkMode` | 147 / 4002 | `function visibleNetworkMode(config)` | none found | `network/config.js` | yes |
| `visibleNetworkModeLabel` | 154 / 4003 | `function visibleNetworkModeLabel(config)` | none found | `network/config.js` | yes |
| `networkReadinessLines` | 2643 / 4004 | `function networkReadinessLines({ role, config, closeReadiness, snapshot, contract, networkWorkers })` | static | `network/readiness.js` | yes |
| `networkRuntimeStatus` | 180 / 4005 | `function networkRuntimeStatus(networkWorkers, config)` | static | `network/status.js` | yes |
| `networkStatusTone` | 238 / 4006 | `function networkStatusTone(status)` | static | `network/status.js` | yes |
| `networkDiagnosticLayerByKey` | 246 / 4007 | `function networkDiagnosticLayerByKey(networkWorkers, key)` | static | `network/status.js` | yes |
| `renderNetworkDiagnosticRail` | 275 / 4008 | `function renderNetworkDiagnosticRail(networkWorkers = {})` | browser | `network/status.js` | yes |
| `networkWorkerDriftPayload` | 484 / 4009 | `function networkWorkerDriftPayload(networkWorkers)` | static | `network/status.js` | yes |
| `networkWorkerDriftFieldText` | 489 / 4010 | `function networkWorkerDriftFieldText(drift)` | static | `network/status.js` | yes |
| `networkWorkerDriftStatusText` | 498 / 4011 | `function networkWorkerDriftStatusText(drift)` | static | `network/status.js` | yes |
| `networkWorkerDriftSummaryLines` | 507 / 4012 | `function networkWorkerDriftSummaryLines(drift)` | static | `network/status.js` | yes |
| `renderNetworkStatusBanner` | 550 / 4013 | `function renderNetworkStatusBanner(payload = {}, config = {})` | static | `network/status.js` | yes |
| `obviousWorkerCoordinatorUrlIssue` | 608 / 4014 | `function obviousWorkerCoordinatorUrlIssue(value, { required = true } = {})` | static | `network/config.js` | yes |
| `networkLifecycleMutationRouteCount` | 1309 / 4015 | `function networkLifecycleMutationRouteCount(contract)` | static | `network/contract.js` | yes |
| `networkAttentionItems` | 296 / 4016 | `function networkAttentionItems(networkWorkers = {})` | static | `network/status.js` | yes |
| `renderNetworkAttentionStack` | 369 / 4017 | `function renderNetworkAttentionStack(networkWorkers = {})` | browser | `network/status.js` | yes |
| `networkTopologyNodes` | 402 / 4018 | `function networkTopologyNodes(config = {}, networkWorkers = {})` | static | `network/status.js` | yes |
| `renderNetworkTopologyStrip` | 436 / 4019 | `function renderNetworkTopologyStrip(config = {}, networkWorkers = {})` | browser | `network/status.js` | yes |
| `renderNetworkActionReadinessGates` | 464 / 4020 | `function renderNetworkActionReadinessGates(payload = {}, config = {})` | browser | `network/status.js` | yes |
| `networkLifecycleDryRunRouteCount` | 1318 / 4021 | `function networkLifecycleDryRunRouteCount(contract)` | static | `network/contract.js` | yes |
| `networkSetupMutationRouteSummary` | 1341 / 4022 | `function networkSetupMutationRouteSummary(contract)` | static | `network/contract.js` | yes |
| `networkLifecycleRouteRow` | 1349 / 4023 | `function networkLifecycleRouteRow(contract, role, action, dryRun)` | static | `network/contract.js` | yes |
| `networkLifecycleRoutePath` | 1419 / 4024 | `function networkLifecycleRoutePath(contract, role, action, dryRun)` | static | `network/contract.js` | yes |
| `networkLifecycleRouteAvailable` | 1424 / 4025 | `function networkLifecycleRouteAvailable(contract, role, action, dryRun)` | static | `network/contract.js` | yes |
| `networkLifecycleDryRunAllowsConfirmed` | 1469 / 4026 | `function networkLifecycleDryRunAllowsConfirmed(payload = {}, config = {}, role = "", action = "")` | browser | `network/lifecycle.model.js` | yes |
| `networkWorkerTestConnectionRoute` | 1503 / 4027 | `function networkWorkerTestConnectionRoute(contract)` | browser | `network/contract.js` | yes |
| `networkWorkerDiscoverCoordinatorsRoute` | 1532 / 4028 | `function networkWorkerDiscoverCoordinatorsRoute(contract)` | browser | `network/contract.js` | yes |
| `networkCoordinatorJoinBlobRoute` | 1524 / 4029 | `function networkCoordinatorJoinBlobRoute(contract)` | browser | `network/contract.js` | yes |
| `networkWorkerJoinClusterRoute` | 1528 / 4030 | `function networkWorkerJoinClusterRoute(contract)` | browser | `network/contract.js` | yes |
| `networkLifecycleRelevantRole` | 1536 / 4031 | `function networkLifecycleRelevantRole(config)` | static | `network/lifecycle.model.js` | yes |
| `networkLifecycleRelevantRoles` | 1543 / 4032 | `function networkLifecycleRelevantRoles(config)` | browser | `network/lifecycle.model.js` | yes |
| `networkLifecycleControlLines` | 1551 / 4033 | `function networkLifecycleControlLines(payload = {}, config = {})` | static | `network/lifecycle.model.js` | yes |
| `networkLifecycleCommandResultLines` | 1736 / 4034 | `function networkLifecycleCommandResultLines(result)` | browser | `network/lifecycle.commands.js` | yes |
| `networkTestConnectionResultLines` | 1836 / 4035 | `function networkTestConnectionResultLines(result)` | static | `network/setup.commands.js` | yes |
| `networkCoordinatorDiscoveryResultLines` | 1885 / 4036 | `function networkCoordinatorDiscoveryResultLines(result)` | static | `network/setup.commands.js` | yes |
| `renderNetworkCoordinatorDiscoveryList` | 1921 / 4037 | `function renderNetworkCoordinatorDiscoveryList(result)` | static | `network/setup.commands.js` | yes |
| `discoverNetworkCoordinators` | 2179 / 4038 | `async function discoverNetworkCoordinators()` | browser | `network/setup.commands.js` | yes |
| `stageDiscoveredCoordinatorUrl` | 1954 / 4039 | `function stageDiscoveredCoordinatorUrl(url)` | static | `network/setup.commands.js` | yes |
| `networkJoinBlobResultLines` | 1986 / 4040 | `function networkJoinBlobResultLines(result)` | static | `network/setup.commands.js` | yes |
| `networkJoinImportResultLines` | 2014 / 4041 | `function networkJoinImportResultLines(result)` | static | `network/setup.commands.js` | yes |
| `networkLifecycleRows` | 2721 / 4042 | `function networkLifecycleRows({ role, config, closeReadiness, snapshot, contract, networkWorkers } = {})` | browser | `network/lifecycle.model.js` | yes |
| `networkLifecycleStatus` | 2850 / 4043 | `function networkLifecycleStatus(rows = [])` | static | `network/lifecycle.model.js` | yes |
| `networkLifecycleSummaryLines` | 2857 / 4044 | `function networkLifecycleSummaryLines(rows = [])` | static | `network/lifecycle.model.js` | yes |
| `networkLifecycleDetailLines` | 2885 / 4045 | `function networkLifecycleDetailLines(row)` | static | `network/lifecycle.model.js` | yes |
| `renderNetworkLifecycleHandoff` | 2906 / 4046 | `function renderNetworkLifecycleHandoff(payload, role, config)` | browser | `network/lifecycle.view.js` | yes |
| `networkEvidenceRows` | 2979 / 4047 | `function networkEvidenceRows({ role, config, closeReadiness, snapshot, contract, networkWorkers } = {})` | static | `network/readiness.js` | yes |
| `networkEvidenceStatus` | 2960 / 4048 | `function networkEvidenceStatus(rows = [])` | static | `network/readiness.js` | yes |
| `networkEvidenceSummaryLines` | 3136 / 4049 | `function networkEvidenceSummaryLines(rows = [])` | static | `network/readiness.js` | yes |
| `renderNetworkEvidenceChecklist` | 3179 / 4050 | `function renderNetworkEvidenceChecklist(payload, role, config)` | static | `network/readiness.js` | yes |
| `networkStateFileRows` | 3220 / 4051 | `function networkStateFileRows(networkWorkers)` | static | `network/stateFiles.js` | yes |
| `networkStateFileStatus` | 3224 / 4052 | `function networkStateFileStatus(item)` | static | `network/stateFiles.js` | yes |
| `networkStateFileSummaryLines` | 3264 / 4053 | `function networkStateFileSummaryLines(rows = [])` | static | `network/stateFiles.js` | yes |
| `networkStateFileDetailLines` | 3295 / 4054 | `function networkStateFileDetailLines(item)` | static | `network/stateFiles.js` | yes |
| `renderNetworkStateFiles` | 3327 / 4055 | `function renderNetworkStateFiles(networkWorkers)` | browser | `network/stateFiles.js` | yes |
| `networkWorkerRowKey` | 3399 / 4056 | `function networkWorkerRowKey(item)` | static | `network/workers.model.js` | yes |
| `networkWorkerStatusState` | 3417 / 4057 | `function networkWorkerStatusState(item)` | browser | `network/workers.model.js` | yes |
| `networkWorkerFilterText` | 3442 / 4058 | `function networkWorkerFilterText(item)` | static | `network/workers.model.js` | yes |
| `filteredNetworkWorkerRows` | 3475 / 4059 | `function filteredNetworkWorkerRows(rows)` | static | `network/workers.model.js` | yes |
| `networkWorkerDetailLines` | 3532 / 4060 | `function networkWorkerDetailLines(item)` | static | `network/workers.model.js` | yes |
| `workerLastResultText` | 3623 / 4061 | `function workerLastResultText(item)` | static | `network/workers.model.js` | yes |
| `workerThroughputText` | 3635 / 4062 | `function workerThroughputText(item)` | static | `network/workers.model.js` | yes |
| `renderNetworkWorkerDetail` | 3661 / 4063 | `function renderNetworkWorkerDetail(item)` | static | `network/workers.view.js` | yes |
| `renderNetworkWorkerProgress` | 3745 / 4064 | `function renderNetworkWorkerProgress(networkWorkers)` | static | `network/workers.view.js` | yes |
| `networkWorkerProgressStatus` | 3715 / 4065 | `function networkWorkerProgressStatus(progress)` | static | `network/workers.model.js` | yes |
| `networkWorkerProgressSummaryLines` | 3721 / 4066 | `function networkWorkerProgressSummaryLines(progress)` | static | `network/workers.model.js` | yes |
| `selectNetworkWorkerRow` | 3694 / 4067 | `function selectNetworkWorkerRow(item)` | none found | `network/workers.view.js` | yes |
| `initNetworkViewEvents` | 3843 / 4068 | `function initNetworkViewEvents()` | prod:app, static, browser | parent facade | yes |
| `renderNetworkWorkers` | 3904 / 4069 | `function renderNetworkWorkers(networkWorkers)` | static | `network/workers.view.js` | yes |
| `renderNetworkWorkerRows` | 3759 / 4070 | `function renderNetworkWorkerRows(networkWorkers)` | static | `network/workers.view.js` | yes |
| `networkOpenTargets` | 2502 / 4071 | `function networkOpenTargets()` | static | `network/openHistory.js` | yes |
| `isNetworkOpenCommand` | 2573 / 4072 | `function isNetworkOpenCommand(entry)` | static | `network/openHistory.js` | yes |
| `networkOpenHistoryLine` | 2578 / 4073 | `function networkOpenHistoryLine(entry)` | static | `network/openHistory.js` | yes |
| `renderNetworkOpenHistory` | 2600 / 4074 | `function renderNetworkOpenHistory(history = [])` | prod:command-history, static | `network/openHistory.js` | yes |
| `renderNetworkSettingsPatchHandoff` | 2524 / 4075 | `function renderNetworkSettingsPatchHandoff(message = "")` | prod:settings | `network/settingsHandoff.js` | yes |
| `renderNetworkLifecycleControls` | 1649 / 4076 | `function renderNetworkLifecycleControls(payload = {}, role = "standalone", config = {})` | static | `network/lifecycle.view.js` | yes |
| `runGuidedNetworkLifecycleCommand` | 2315 / 4077 | `async function runGuidedNetworkLifecycleCommand(button)` | static | `network/lifecycle.commands.js` | yes |
| `runNetworkLifecycleCommand` | 2391 / 4078 | `async function runNetworkLifecycleCommand(button)` | static | `network/lifecycle.commands.js` | yes |
| `runNetworkWorkerTestConnection` | 2457 / 4079 | `async function runNetworkWorkerTestConnection(options = {})` | prod:settings, browser | `network/setup.commands.js` | yes |
| `createNetworkJoinBlob` | 2053 / 4080 | `async function createNetworkJoinBlob()` | browser | `network/setup.commands.js` | yes |
| `copyNetworkJoinBlob` | 2109 / 4081 | `async function copyNetworkJoinBlob()` | static | `network/setup.commands.js` | yes |
| `importNetworkJoinBlob` | 2127 / 4082 | `async function importNetworkJoinBlob()` | browser | `network/setup.commands.js` | yes |
| `previewNetworkSettingsPatch` | 2547 / 4083 | `async function previewNetworkSettingsPatch()` | static | `network/settingsHandoff.js` | yes |
| `saveNetworkSettingsPatch` | 2560 / 4084 | `async function saveNetworkSettingsPatch()` | static | `network/settingsHandoff.js` | yes |
| `renderNetworkView` | 3951 / 4085 | `function renderNetworkView(payload = {})` | prod:app, browser | parent facade | yes |

## Route Ledger

Network command POSTs must remain contract-derived through
`networkLifecycleRoutePath`, `networkCommandRouteByDataSchema`, and
`postNetworkRoute(route, request)`. Do not hard-code these routes in child
command modules.

| Route | Method | Effect | Frontend caller | Confirmation fields | Backend authority note |
|---|---|---|---|---|---|
| `/api/contract` | GET | `none` | App contract payload; Network route helpers read metadata from payload | none | Local API publishes route metadata, lifecycle summary, request keys, effects, and frontend exposure. |
| `/api/network/workers` | GET | `none` | App/Network payload; Network renders persisted worker evidence and route availability text | none | Backend-authored persisted runtime evidence only. WebView must not infer lifecycle policy from rows. |
| `/api/network/coordinator/start-dry-run` | POST | `none` | `runGuidedNetworkLifecycleCommand`, `runNetworkLifecycleCommand` through contract row | none | Backend dry-run owns preconditions, active work, state-file posture, no-touch evidence, and `safe_to_apply`. |
| `/api/network/coordinator/stop-dry-run` | POST | `none` | Same lifecycle dry-run flow | none | Backend dry-run owns stop preconditions and preservation evidence. |
| `/api/network/worker/start-dry-run` | POST | `none` | Same lifecycle dry-run flow | none | Backend dry-run owns coordinator URL, path-map, pending-done, provider, and no-touch posture. |
| `/api/network/worker/stop-dry-run` | POST | `none` | Same lifecycle dry-run flow | none | Backend dry-run owns worker stop and pending-done posture. |
| `/api/network/coordinator/start` | POST | `backend-lifecycle` | `runGuidedNetworkLifecycleCommand`, `runNetworkLifecycleCommand` after current dry-run match | `confirm_start` | Backend provider starts only real coordinator lifecycle and journaled command evidence; provider unavailable fails closed. |
| `/api/network/coordinator/stop` | POST | `backend-lifecycle` | Same confirmed lifecycle flow | `confirm_stop` | Backend provider stops coordinator while preserving coordinator/worker state files and claims evidence. |
| `/api/network/worker/start` | POST | `backend-lifecycle` | Same confirmed lifecycle flow | `confirm_start` | Backend provider starts worker polling only for coordinator-assigned work, not local Launch or queue scan. |
| `/api/network/worker/stop` | POST | `backend-lifecycle` | Same confirmed lifecycle flow | `confirm_stop` | Backend provider stops worker polling while preserving pending done reports and worker state. |
| `/api/network/worker/test-connection` | POST | `none` | `runNetworkWorkerTestConnection` via `networkWorkerTestConnectionRoute` | none | Backend owns TCP/auth/path preflight; no lifecycle, queue, settings, publish, or media mutation. |
| `/api/network/worker/discover-coordinators` | POST | `none` | `discoverNetworkCoordinators` via data schema lookup | none | Backend owns mDNS discovery. Selecting a result only stages Settings intent in WebView. |
| `/api/network/coordinator/join-blob` | POST | `secret-transfer` | `createNetworkJoinBlob` via data schema lookup | `confirm_create`; `confirm_rotate` only when rotating | Backend returns unjournaled secret join blob; no lifecycle, queue, publish, drain, or media mutation. |
| `/api/network/worker/join-cluster` | POST | `config-write` | `importNetworkJoinBlob` via data schema lookup | `confirm_import` | Backend imports the secret join blob through settings save semantics, then runs read-only test-connection. Does not start polling. |
| `/api/diagnostics/open` | POST | `shell-open` | Diagnostics owns POST; Network only filters recent `diagnostics.open` history for network targets | target allowlist only | Backend resolves allowlisted diagnostics targets. Network must not open arbitrary paths. |
| `/api/settings/preview-patch` | POST | `none` | `previewNetworkSettingsPatch` delegates to `mediaPipelineSettingsView.previewSettingsPatch` | none | Settings backend validates staged config diff; Network does not persist settings directly. |
| `/api/settings/save-patch` | POST | `config-write` | `saveNetworkSettingsPatch` delegates to `mediaPipelineSettingsView.saveSettingsPatch` | Settings module must supply `confirm_save` and matching backend review confirmation | Backend owns JSON authority, PSD1 projection, backup, and reload. |
| `/api/backend/close-readiness` | GET | `none` | App payload consumed by Network readiness/lifecycle helpers | none | Backend/Tauri close-readiness remains authoritative for active-work safety. |
| `/api/snapshot` | GET | `none` | App payload consumed by Network readiness helpers | none | Backend snapshot evidence only; Network renders state, not policy. |
| `/api/commands` | GET | `none` | `commandHistory.js` passes history into `renderNetworkOpenHistory` | none | Backend command journal owns diagnostics/open and lifecycle command evidence. |

## DOM Ledger

Evidence sources: `apps/desktop/webview/static/partials/page-network.html` and
the generated ID manifest in `docs/inventories/WEBVIEW_DOM_ID_INVENTORY.md`.
The partial currently contains 169 unique `network-*` / `settings-network-*`
IDs.

| Region | Representative DOM IDs | Renderer/helper owner | Current coverage |
|---|---|---|---|
| Status command board | `network-status`, `network-health-strip`, `network-status-banner-lines`, `network-diagnostic-rail`, `network-attention-stack`, `network-topology-strip`, `network-action-readiness-gates` | `network/status.js`, `network/readiness.js` | Browser Network smoke, Web static diagnostics/reports assertions, read-only boundary test |
| Lifecycle controls/dialog | `network-lifecycle-control-buttons`, `network-lifecycle-command-result`, `network-lifecycle-confirm-dialog`, `network-lifecycle-rows`, `network-lifecycle-detail` | `network/lifecycle.model.js`, `network/lifecycle.view.js`, `network/lifecycle.commands.js` | Browser Network smoke, read-only boundary test, frontend mutation boundary, command boundary audit |
| Setup and join | `network-setup-drawer`, `network-coordinator-join-*`, `network-worker-join-*`, `network-worker-discover`, `network-worker-discovery-list` | `network/setup.commands.js` | Browser Network smoke, read-only boundary test, API command contract tests |
| Worker board | `network-worker-rows`, `network-worker-detail`, `network-worker-progress-bars`, `network-worker-status-filter`, `network-worker-filter`, `network-worker-view-presets` | `network/workers.model.js`, `network/workers.view.js` | Browser Network smoke, Web static assertions, read-only boundary |
| Role dashboards | `network-role-dashboards`, `network-coordinator-overview-*`, `network-coordinator-active-rows`, `network-coordinator-queue-rows`, `network-worker-overview-*`, `network-worker-claim-rows` | `network/roleDashboard.js` | Browser Network smoke, Web static diagnostics/reports assertions |
| Settings handoff | `settings-network-*`, `network-settings-*`, `network-role-setup-*` | `network/settingsHandoff.js`, existing `settingsView.builders.network.js`, Settings module | Browser Network smoke, settings builder/static tests, settings save/preview contract tests |
| Advanced evidence | `network-readiness-*`, `network-lifecycle-boundary-*`, `network-route-summary-*`, `network-evidence-*`, `network-state-files-*`, `network-api-*`, `network-open-history-*` | `network/readiness.js`, `network/stateFiles.js`, `network/openHistory.js`, `network/contract.js` | Browser Network smoke, Web static assertions, command evidence smoke |
| Future unavailable actions | `data-network-future-control=*`, `network-unavailable-actions-drawer` | Parent facade until backend routes exist | Read-only boundary test, command boundary local-control classification |

## Direct Caller Search Results

Search command:

```powershell
rg -n "mediaPipelineNetworkView\??\.|mediaPipelineNetworkView\." apps/desktop/webview/static/assets tests
```

Direct non-test callers:

| File | Direct use |
|---|---|
| `apps/desktop/webview/static/assets/app.js:854` | `renderNetworkView` |
| `apps/desktop/webview/static/assets/app.js:1683` | `initNetworkViewEvents` |
| `apps/desktop/webview/static/assets/commandHistory.js:1340` | `renderNetworkOpenHistory` |
| `apps/desktop/webview/static/assets/settingsView.js:584` | `runNetworkWorkerTestConnection` |
| `apps/desktop/webview/static/assets/settingsView.builders.network.js:440` | `runNetworkWorkerTestConnection` |
| `apps/desktop/webview/static/assets/settingsView.builders.network.js:582,592,662,752` | `renderNetworkSettingsPatchHandoff` |

Direct test callers:

| File | Direct use |
|---|---|
| `tests/webview/test_webview_browser_network_smoke.py` | Public function presence, direct calls to `renderNetworkView`, `renderNetworkLifecycleHandoff`, `networkLifecycleRows`, `renderNetworkStateFiles`, route helpers, setup helpers, `networkLifecycleCommandResultLines`, and worker-test override |
| `tests/webview/test_webview_command_evidence_smoke.py` | `renderNetworkOpenHistory` |
| `tests/python/desktop/test_application_facade_web_static_shell.py` | Source assertions for `renderNetworkOpenHistory` and `initNetworkViewEvents` consumers |

No other direct `mediaPipelineNetworkView.*` or
`mediaPipelineNetworkView?.*` asset/test callers were found.

## Source-Only Guardrails

These tests/scripts currently protect Network behavior through source strings
or generated command-boundary scans. They must be updated in the same phase as
any child extraction they cover.

| Guardrail | Current assumption | Extraction rule |
|---|---|---|
| `tests/webview/test_webview_network_read_only_boundary.py` | Reads planned child slots plus `networkView.js`; requires `networkView.js` to remain the public facade and checks route/confirmation strings in the combined bundle. | Keep parent facade and update child slot list before moving protected strings. |
| `tests/webview/test_webview_frontend_mutation_boundary.py` | Allows exactly one dynamic Network `apiPost(route, request)` only in parent, `network/lifecycle.commands.js`, or `network/setup.commands.js`. | Move dynamic dispatcher only with lifecycle/setup command child tests. |
| `tests/webview/test_webview_command_boundary_audit.py` | Generated dynamic post may be reported from parent or lifecycle/setup command children. | Update expected owner only when command code actually moves. |
| `ops/scripts/dev/check-webview-command-boundary.mjs` | Dynamic Network route dispatch is allowed only when lifecycle/setup confirmation markers are present in the same asset. | Keep route lookup, strict confirmations, and `apiPost(route, request)` in the same command owner. |
| `tests/python/desktop/test_application_facade_web_static.py` | Local source helper `_read_network_asset_bundle` includes planned child slots and requires `networkView.js` last with the public facade. | Keep this source helper current when child slots are added. |
| `tests/python/desktop/application_facade_test_support.py` | Served-static helper still fetches only `/assets/networkView.js` into `network_view_js`. | Migrate it to read the ordered parent-plus-child served assets, or explicitly scope its assertions to parent-only facade checks, before moving protected Network functions/text out of the parent. |
| `tests/python/desktop/test_application_facade_web_static_diagnostics_reports.py` | Asserts many Network functions/text snippets through `network_view_js`; served-static coverage is parent-only until `application_facade_test_support.py` is changed. | Migrate assertions to bundle-aware checks before moving text out of parent. |
| `tests/python/desktop/test_application_facade_web_static_shell.py` | Current script order remains `settingsView.js` -> `networkView.js` -> `diagnosticsTailView.js`; optional Network children must precede parent. | Do not add a child that loads after `networkView.js`. |
| `docs/inventories/COMMAND_OWNERSHIP_MATRIX.md` | Network command owner JS remains `networkView.js` until command code moves. | Update owner rows in the exact command extraction phase. |
| `docs/inventories/WEBVIEW_GLOBAL_EXPORT_INVENTORY.md` | `networkView.js` has namespace object and zero flat exports. | Keep `mediaPipelineNetworkView` as public facade; inventory must remain zero flat exports unless intentionally changed. |

## Troubleshooting Seams And Rollback Rules

Use these seams only when a phase has a stable contract, caller ledger, test
target, and rollback path. Do not create every file mechanically.

| Seam | Candidate owner | Valid when | Rollback rule |
|---|---|---|---|
| Contract route lookup | `assets/network/contract.js` | Functions only interpret `/api/contract` routes, `network_lifecycle_contracts`, data schemas, effects, and route availability. | Move helpers back to `networkView.js`, remove the child script, and keep wrapper exports unchanged. |
| Runtime status/readiness | `assets/network/status.js`, `assets/network/readiness.js` | Renderers explain blocked/noisy Network posture without POSTs or policy ownership. | Restore render/model helpers to parent and remove child factory consumption. |
| Lifecycle model/view | `assets/network/lifecycle.model.js`, `assets/network/lifecycle.view.js` | Helpers separate pure row/fingerprint/gate evidence from DOM rendering and do not POST. | Restore helpers and selected-row state to parent; remove child script tags. |
| Lifecycle commands | `assets/network/lifecycle.commands.js` | Dry-run and confirmed POST payload builders stay contract-derived and keep fresh-dry-run checks with `confirm_start`/`confirm_stop`. | Move command functions and dynamic `apiPost(route, request)` back to parent; restore command-boundary owner to `networkView.js`. |
| Setup commands | `assets/network/setup.commands.js` | Test-connection, discovery, join-blob, copy, and join-import keep contract-derived routes and strict setup confirmations. | Move setup functions back to parent and reset command owner rows to `networkView.js`. |
| Worker board | `assets/network/workers.model.js`, `assets/network/workers.view.js` | Worker row classification/filter/rendering remains read-only over backend-authored worker state. | Move model/view helpers back and preserve the single selected-worker/filter state. |
| State files | `assets/network/stateFiles.js` | Helpers only explain backend-authored state artifacts and safe read order. | Move helpers back; no backend or diagnostics route change required. |
| Settings handoff | `assets/network/settingsHandoff.js` | Code delegates to `mediaPipelineSettingsView` and never persists config directly. | Move handoff helpers back; Settings module remains unchanged. |
| Open history | `assets/network/openHistory.js` | Code filters recent `diagnostics.open` command history for backend-allowlisted Network targets only. | Move filtering/rendering back; Diagnostics retains POST ownership. |
| Role dashboards | `assets/network/roleDashboard.js` | Overview/claim/queue rows remain evidence-only and do not mutate queue/claim state. | Move dashboard model/render functions back and keep public wrappers. |

## Proposed First Extraction Phase

After the stop-condition blocker above is fixed, the first safe implementation
step is still a no-child parent state-container phase: put existing top-level
mutable Network state behind one injected `networkState` object inside
`networkView.js`. This reduces duplicate-state risk before any child module
exists.

The first actual child extraction should be `assets/network/contract.js`, after
the state-container phase. It is the cleanest troubleshooting seam because it
has a stable `/api/contract` input, no DOM writes, no POST execution, no
settings persistence, no worker selection/filter state, and clear tests around
route availability and command-boundary ownership.

Do not move lifecycle or setup command execution before contract lookup,
source-only guardrails, and command owner inventories are updated for the
parent-plus-child asset set.

## Validation Required Before And After First Extraction

Run these before the first extraction and again after it:

```powershell
git status --short
rg -n "mediaPipelineNetworkView|networkView.js|/api/network|confirm_start|confirm_stop|confirm_create|confirm_rotate|confirm_import" apps tests docs/inventories ops/scripts/dev
.\apps\desktop\runtime\Python\python.exe -m unittest tests.webview.test_webview_network_read_only_boundary -q
.\apps\desktop\runtime\Python\python.exe -m unittest tests.webview.test_webview_browser_network_smoke -q
npm run webview:prework:check
```

Additional guardrail commands recommended before command-seam movement:

```powershell
.\apps\desktop\runtime\Python\python.exe -m unittest tests.webview.test_webview_frontend_mutation_boundary -q
.\apps\desktop\runtime\Python\python.exe -m unittest tests.webview.test_webview_command_boundary_audit -q
node .\ops\scripts\dev\check-webview-route-ownership.mjs
node .\ops\scripts\dev\check-webview-command-boundary.mjs
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.change_control.validate_changes --require-worktree-coverage
```

## Baseline Command Results

| Command | Result |
|---|---|
| `git status --short` | Completed. Worktree was already heavily dirty; current status count is about 930 entries. This packet touched only this note and `ops/release/changes/unreleased/MP-CHANGE-2026-0626-009.json`. |
| `rg -n "mediaPipelineNetworkView|networkView.js|/api/network|confirm_start|confirm_stop|confirm_create|confirm_rotate|confirm_import" apps tests docs/inventories ops/scripts/dev` | Completed. 428 matching lines; confirmed current namespace callers, route inventories, confirmation guards, and source-only guardrails. |
| `.\apps\desktop\runtime\Python\python.exe -m unittest tests.webview.test_webview_network_read_only_boundary -q` | Passed. 14 tests in 0.080s. |
| `.\apps\desktop\runtime\Python\python.exe -m unittest tests.webview.test_webview_browser_network_smoke -q` | Passed. 1 browser-backed test in 5.992s. |
| `npm run webview:prework:check` | Failed after `webview:check` passed. Failing subcheck: `webview:lint:budget:check`; warning budgets exceed baselines: complexity 115 > 108, max-lines-per-function 46 > 37, no-extra-boolean-cast 1 > 0, no-unused-vars 192 > 143. |
| `.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.change_control.validate_changes` | Passed. 774 packets valid. |
| `.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.change_control.validate_changes --require-worktree-coverage` | Failed. 12 unrelated changed files are not listed in any unreleased change packet. |

Uncovered unrelated files reported by strict worktree coverage:

```text
docs/generated/dependency-atlas/assets/dependency_detail_core_repair_reconcile.png
docs/generated/dependency-atlas/assets/dependency_detail_core_repair_reconcile.svg
docs/generated/dependency-atlas/assets/dependency_detail_desktop_watch.png
docs/generated/dependency-atlas/assets/dependency_detail_desktop_watch.svg
docs/generated/dependency-atlas/assets/dependency_detail_tools_autonomy_growth_snapshot.png
docs/generated/dependency-atlas/assets/dependency_detail_tools_autonomy_growth_snapshot.svg
docs/generated/dependency-atlas/assets/dependency_detail_tools_autonomy_health_gate.png
docs/generated/dependency-atlas/assets/dependency_detail_tools_autonomy_health_gate.svg
docs/generated/dependency-atlas/assets/dependency_detail_tools_autonomy_soak_tick.png
docs/generated/dependency-atlas/assets/dependency_detail_tools_autonomy_soak_tick.svg
docs/generated/summaries/tests/python/desktop/test_preset_library.py.md
docs/implementation/webview-large-file-refactor-prework/renameView.phase0-baseline.md
```

## Stop Conditions For Later Phases

Stop before moving code if any of these appear:

- A child script must load after `networkView.js`.
- Any public namespace export disappears, changes signature, or loses its
  parent wrapper.
- Any route path used by command execution is hard-coded instead of derived
  from `/api/contract`.
- Lifecycle confirmed POSTs can occur without a fresh matching dry-run and the
  exact `confirm_start` or `confirm_stop` field.
- Setup POSTs can occur without `confirm_create`, optional `confirm_rotate`,
  or `confirm_import` where required.
- Any child creates duplicate selected worker, selected lifecycle row, selected
  evidence row, selected state-file row, filter state, last payload, or dry-run
  cache state.
- Any moved helper starts owning backend lifecycle policy, claim/release/done
  policy, queue mutation, settings persistence, path trust, media policy, or
  filesystem mutation.
