# Network View Troubleshooting Refactor Planning Pack

Date: 2026-06-25
Status: planning only
Change packet: MP-CHANGE-2026-0624-058

## Purpose

This planning pack describes how to split
`apps/desktop/webview/static/assets/networkView.js` into smaller,
troubleshooting-oriented WebView modules without changing operator behavior,
backend route ownership, or public WebView contracts first.

The current file is broad enough that unrelated Network concerns fail through
one surface:

| Current surface | Current shape |
|---|---:|
| File | `apps/desktop/webview/static/assets/networkView.js` |
| Approximate size | about 4,100 lines |
| Runtime model | ordered `<script>` tags, no bundler |
| Public namespace | `window.mediaPipelineNetworkView` |
| Flat exports | none |
| Main page partial | `apps/desktop/webview/static/partials/page-network.html` |
| Primary tests | `tests/webview/test_webview_network_read_only_boundary.py`, `tests/webview/test_webview_browser_network_smoke.py` |

The goal is not to create files for their own sake. The goal is one clear
failure boundary per troubleshooting question so a failing Network test tells
the maintainer whether the issue is route contract discovery, lifecycle
dry-run freshness, setup/join commands, connection diagnostics, state-file
evidence, worker row triage, settings handoff, or diagnostics open history.

This pack is subordinate to:

- `AGENTS.md`
- `docs/DOCS_INDEX.md`
- `docs/architecture/ARCHITECTURE.md`
- `docs/architecture/MODULE_MAP.md`
- `docs/architecture/NETWORK_LIFECYCLE_COMMAND_CONTRACT.md`
- `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`
- `docs/inventories/API_ROUTE_INVENTORY.md`
- `docs/inventories/LOCAL_API_ROUTE_OWNERSHIP_MAP.md`
- `docs/inventories/WEBVIEW_DOM_ID_INVENTORY.md`
- `docs/inventories/WEBVIEW_GLOBAL_EXPORT_INVENTORY.md`
- `docs/testing/VALIDATION_LADDER_RUNBOOK.md`
- `docs/change_control/README.md`

If this pack conflicts with those authority docs or executable source/tests,
stop and update the stale planning text before continuing.

## Non-Goals

- No UI redesign.
- No route additions.
- No backend route behavior changes.
- No media, source, output, publish, queue, rename, claim, release, done-report,
  abort, reclaim, or filesystem mutation policy changes.
- No frontend-owned lifecycle process management.
- No frontend authority over lifecycle safety. The WebView may keep the
  existing conservative stale-dry-run UI block, but backend dry-run and
  confirmed lifecycle routes remain the authority for real safety decisions.
- No ES modules, imports, bundler, TypeScript conversion, React migration, or
  new frontend framework.
- No removal or renaming of `window.mediaPipelineNetworkView` exports until
  inventories and tests intentionally prove the export is unused.
- No generated-file hand edits under `docs/generated/`.

## Public Contracts To Preserve

The parent `networkView.js` remains the public facade throughout the split.
All child modules must be loaded before the parent in
`apps/desktop/webview/static/index.html`.

Preserve every current `window.mediaPipelineNetworkView` namespace export until
a later contract-change packet deliberately updates tests and inventories.
Before any extraction phase, create an export ledger from the live
`window.mediaPipelineNetworkView = { ... }` object. Every current export must
have:

- current signature and known callers
- target owner module
- parent wrapper or explicit reason no wrapper is needed
- validation that proves the exported function is still callable from
  `window.mediaPipelineNetworkView`

At minimum, the following exported troubleshooting functions are actively
covered by source/static/browser tests, cross-module calls, or natural smoke
anchors:

| Function | Current public use |
|---|---|
| `renderNetworkView` | Main render entrypoint |
| `initNetworkViewEvents` | Browser smoke event binding |
| `syncNetworkRoleDashboards` | Role dashboard visibility |
| `networkCoordinatorOverviewModel` / `networkWorkerOverviewModel` | Role-specific evidence model tests |
| `networkRuntimeStatus` / `renderNetworkStatusBanner` | Runtime status and drift posture |
| `networkDiagnosticLayerByKey` / `renderNetworkDiagnosticRail` | Troubleshooting layer chips |
| `networkAttentionItems` / `renderNetworkAttentionStack` | Highest-priority issue stack |
| `networkTopologyNodes` / `renderNetworkTopologyStrip` | Coordinator/worker topology evidence |
| `renderNetworkActionReadinessGates` | TCP/auth/path/state/queue/close/dry-run gates |
| `networkLifecycleRouteRow` / `networkLifecycleRoutePath` / `networkLifecycleRouteAvailable` | Contract-derived route resolution |
| `networkLifecycleDryRunAllowsConfirmed` | Dry-run freshness guard |
| `networkLifecycleRelevantRoles` / `networkLifecycleControlLines` | Lifecycle control state |
| `networkLifecycleRows` / `renderNetworkLifecycleHandoff` | Lifecycle troubleshooting handoff |
| `networkEvidenceRows` / `renderNetworkEvidenceChecklist` | Evidence checklist |
| `networkStateFileRows` / `renderNetworkStateFiles` | Runtime state file troubleshooting |
| `networkWorkerRowKey` / `networkWorkerStatusState` / `filteredNetworkWorkerRows` | Worker triage and filtering |
| `renderNetworkWorkerDetail` / `renderNetworkWorkerProgress` / `renderNetworkWorkerRows` | Worker board rendering |
| `networkWorkerTestConnectionRoute` / `runNetworkWorkerTestConnection` | Backend test-connection route and result rendering |
| `networkWorkerDiscoverCoordinatorsRoute` / `discoverNetworkCoordinators` / `stageDiscoveredCoordinatorUrl` | mDNS discovery and staged coordinator URL |
| `networkCoordinatorJoinBlobRoute` / `createNetworkJoinBlob` / `copyNetworkJoinBlob` | Coordinator join-blob setup |
| `networkWorkerJoinClusterRoute` / `importNetworkJoinBlob` | Worker join import setup |
| `runGuidedNetworkLifecycleCommand` / `runNetworkLifecycleCommand` | Dry-run-first lifecycle command flow |
| `renderNetworkSettingsPatchHandoff` / `previewNetworkSettingsPatch` / `saveNetworkSettingsPatch` | Settings handoff to existing Settings module |
| `networkOpenTargets` / `isNetworkOpenCommand` / `renderNetworkOpenHistory` | Diagnostics open-history handoff |

Preserve these backend route boundaries:

| Route | Network role | Required guardrail |
|---|---|---|
| `GET /api/network/workers` | Persisted runtime evidence | read-only, `effect=none` |
| `POST /api/network/worker/test-connection` | Worker connectivity preflight | no lifecycle state, queue, media, or settings mutation |
| `POST /api/network/worker/discover-coordinators` | mDNS discovery | no lifecycle state or settings mutation |
| `POST /api/network/coordinator/join-blob` | Secret-transfer setup | `confirm_create`, optional `confirm_rotate`; route is unjournaled because response contains a secret |
| `POST /api/network/worker/join-cluster` | Config-write setup | `confirm_import`; does not start worker polling |
| `POST /api/network/{coordinator|worker}/{start|stop}-dry-run` | Lifecycle dry-run | no mutation; must render `safe_to_apply` evidence |
| `POST /api/network/{coordinator|worker}/{start|stop}` | Backend lifecycle mutation | requires matching fresh dry-run plus `confirm_start` or `confirm_stop` |
| `POST /api/diagnostics/open` | Diagnostics handoff | backend target allowlist only |

Do not hard-code Network route paths in child command modules. Resolve the route
from `/api/contract` through the same contract metadata that the current parent
uses.

## Pre-Extraction Test And Inventory Gate

Several current guardrails intentionally inspect `networkView.js` directly.
A split will fail those tests unless the assertions are migrated before moving
the functions they protect.

Before phase 2 creates child modules, update the affected tests and inventories
so they understand the parent-plus-child Network script set:

| Current guardrail | Current assumption | Required plan update |
|---|---|---|
| `tests/webview/test_webview_network_read_only_boundary.py` | Network lifecycle/setup function declarations live in `networkView.js` | Read the full ordered Network asset set or assert parent namespace wrappers after child factories are wired. |
| `tests/webview/test_webview_frontend_mutation_boundary.py` | The one dynamic `apiPost(route, request)` exception is in `networkView.js` | Move the exception to the command child that owns `postNetworkRoute` and verify the route still resolves from `/api/contract`. |
| `tests/webview/test_webview_command_boundary_audit.py` | Dynamic Network dispatch is reported under `apps/desktop/webview/static/assets/networkView.js` | Update the expected file to `network/lifecycle.commands.js`, or explicitly allow the parent wrapper plus command child pair. |
| `tests/python/desktop/test_application_facade_web_static*.py` source assertions | Some Web static checks read `/assets/networkView.js` only | Keep parent wrappers in `networkView.js`, or change the assertion helper to inspect the parent plus Network child scripts. |
| `docs/inventories/COMMAND_OWNERSHIP_MATRIX.md` | Network command owner JS is `networkView.js` | Update owner JS to the specific child command module when command code moves. |
| `docs/inventories/WEBVIEW_GLOBAL_EXPORT_INVENTORY.md` | `networkView.js` owns the public namespace and has no child globals | Preserve `mediaPipelineNetworkView` as the only public namespace; record any child stash globals only as temporary internal loader details if inventory tooling requires it. |

This gate is complete only when static Network tests, command-boundary tests,
frontend mutation-boundary tests, and the relevant inventories pass before any
behavioral extraction begins.

## Troubleshooting Boundary Map

Use troubleshooting questions as the split boundaries:

| Operator question | Target module owner | Evidence to preserve |
|---|---|---|
| "Why is Network blocked or noisy?" | `network/status.js` | status banner, attention stack, topology strip, readiness gates |
| "Is the backend route available and allowed?" | `network/contract.js` | contract summary, route rows, lifecycle/setup route discovery |
| "Can I safely start or stop this role?" | `network/lifecycle.model.js` and `network/lifecycle.view.js` | lifecycle handoff rows, dry-run requirement lines, close-readiness and state-file gates |
| "Was the dry-run current when I confirmed?" | `network/lifecycle.commands.js` | dry-run fingerprint, stale-state invalidation, confirmation dialog payload |
| "Why can this worker not connect?" | `network/setup.commands.js` and `network/status.js` | test-connection result lines, discovery output, URL validation, auth/path diagnostics |
| "How do I join a worker to the coordinator?" | `network/setup.commands.js` | join blob, import result, secret-transfer/config-write warning text, confirm fields |
| "Which state files should I inspect?" | `network/stateFiles.js` | state-file status, age, purpose, safe read order |
| "Which worker needs attention?" | `network/workers.model.js` and `network/workers.view.js` | filters, hidden review warning, selected worker inspector, progress summary |
| "What did I recently open in Diagnostics?" | `network/openHistory.js` | diagnostics.open command history filtered to network targets |
| "Are staged settings involved?" | `network/settingsHandoff.js` | staged patch status, delegated preview/save, no direct settings write |
| "What is coordinator/worker role posture?" | `network/roleDashboard.js` | coordinator active rows, queue on deck, worker claim rows, overview tiles |

## Target Runtime Pattern

Use the existing WebView split pattern from `completed/`, `queue/`, `settings/`,
and the Reports planning pack:

1. Child file declares a factory on a temporary stash global.
2. Parent `networkView.js` creates the single Network state instance.
3. Parent reads each child factory, passes dependencies, then deletes the stash
   global.
4. Child modules may mutate the injected state object, but must not create
   competing copies of selected worker, selected lifecycle row, selected
   evidence row, selected state file, filter text, view preset, last payload, or
   dry-run cache state.
5. Parent keeps the public `window.mediaPipelineNetworkView` namespace and
   wrapper functions.

Example child shape:

```javascript
// apps/desktop/webview/static/assets/network/lifecycle.model.js
(function () {
  "use strict";

  function createNetworkLifecycleModelModule(deps = {}) {
    const state = deps.state || {};
    return {
      networkLifecycleRows,
      networkLifecycleStatus,
      networkLifecycleSummaryLines,
    };
  }

  window.__networkViewLifecycleModelModule = {
    createNetworkLifecycleModelModule,
  };
})();
```

The parent should consume it with dependency injection, not with ad hoc access
to unrelated globals:

```javascript
const lifecycleModelModule = window.__networkViewLifecycleModelModule || {};
delete window.__networkViewLifecycleModelModule;
const lifecycleModel = typeof lifecycleModelModule.createNetworkLifecycleModelModule === "function"
  ? lifecycleModelModule.createNetworkLifecycleModelModule({
    state: networkState,
    byId: typeof byId === "function" ? byId : window.byId,
    setText: typeof setText === "function" ? setText : window.setText,
  })
  : {};
```

The script order in `index.html` should remain plain ordered scripts. Child
modules load immediately before the parent:

```html
<script src="/assets/network/state.js"></script>
<script src="/assets/network/shared.js"></script>
<script src="/assets/network/contract.js"></script>
<script src="/assets/network/lifecycle.model.js"></script>
<script src="/assets/networkView.js"></script>
```

Do not switch to `type="module"` as part of this refactor.

## Target File Shape

Use a dedicated `network/` child directory to keep Network-owned modules
discoverable:

```text
apps/desktop/webview/static/assets/networkView.js
apps/desktop/webview/static/assets/network/state.js
apps/desktop/webview/static/assets/network/shared.js
apps/desktop/webview/static/assets/network/config.js
apps/desktop/webview/static/assets/network/contract.js
apps/desktop/webview/static/assets/network/status.js
apps/desktop/webview/static/assets/network/readiness.js
apps/desktop/webview/static/assets/network/lifecycle.model.js
apps/desktop/webview/static/assets/network/lifecycle.view.js
apps/desktop/webview/static/assets/network/lifecycle.commands.js
apps/desktop/webview/static/assets/network/setup.commands.js
apps/desktop/webview/static/assets/network/settingsHandoff.js
apps/desktop/webview/static/assets/network/openHistory.js
apps/desktop/webview/static/assets/network/stateFiles.js
apps/desktop/webview/static/assets/network/workers.model.js
apps/desktop/webview/static/assets/network/workers.view.js
apps/desktop/webview/static/assets/network/roleDashboard.js
```

Do not create every file mechanically. Create a child module only when the
phase has a concrete troubleshooting boundary, wrapper, test target, and
rollback path.

| Target module | Owns | Must not own |
|---|---|---|
| `network/state.js` | Factory for the single Network page state container and reset helpers injected by the parent | Backend policy, DOM rendering, or independent state copies |
| `network/shared.js` | Generic text, status, path, table, chip, and row helper functions shared inside Network | API calls or route policy |
| `network/config.js` | Network setting display helpers, redaction helpers, visible mode labels, URL sanity checks | Settings persistence or backend validation |
| `network/contract.js` | `/api/contract` route discovery, lifecycle/setup route summaries, route availability helpers | Hard-coded lifecycle route behavior |
| `network/status.js` | status banner, diagnostic rail, attention stack, topology strip, action readiness gates | Command POSTs |
| `network/readiness.js` | close-readiness, snapshot, boundary, route summary, and Network readiness text | lifecycle confirmation |
| `network/lifecycle.model.js` | lifecycle gates, dry-run fingerprints, dry-run cache state, stale evidence rules | DOM writes or API calls |
| `network/lifecycle.view.js` | lifecycle controls, lifecycle handoff table, detail panes, confirmation-dialog text | route POST request execution |
| `network/lifecycle.commands.js` | dry-run-first lifecycle command execution, confirmation field payloads, result rendering | provider policy, process management, retry/reclaim/release/abort |
| `network/setup.commands.js` | test connection, coordinator discovery, join blob, join import, copy blob, result rendering | worker polling start, queue claims, or arbitrary settings save |
| `network/settingsHandoff.js` | staged settings patch status and delegation to `mediaPipelineSettingsView` | direct config writes or PSD1 mutation |
| `network/openHistory.js` | filtered diagnostics.open history for network targets | arbitrary path open/tail logic |
| `network/stateFiles.js` | runtime state-file rows, status, age, selected detail, safe read order | opening files or rewriting state files |
| `network/workers.model.js` | worker keys, status classification, filters, hidden-review warnings, progress text | DOM writes or lifecycle decisions |
| `network/workers.view.js` | worker table, selected inspector, progress bars, filter controls | POST routes or worker state writes |
| `network/roleDashboard.js` | coordinator/worker overview tiles, active claim rows, queue-on-deck rows | queue mutation, claim ownership, or launch scope |

The parent `networkView.js` owns only dependency wiring, child factory
consumption, cleanup of temporary stash globals, event initialization
coordination, public namespace wrappers, and the main `renderNetworkView`
orchestration.

## Phase Order

Execute these in order. Do not move command code before public contracts and
baseline behavior are locked.

| Phase | Name | Context brief | Exit criteria |
|---:|---|---|---|
| 0 | Baseline, export ledger, and guardrail migration | Capture current exports, route discovery, DOM IDs, direct test callers, current dirty-worktree caveats, and Network no-touch boundaries. Migrate source-only tests/inventories that assume all protected Network functions live in `networkView.js`. | Baseline and export ledger are recorded in the change packet. Static Network, command-boundary, frontend mutation-boundary, and relevant Web static tests pass before implementation starts. |
| 1 | Parent state container | Replace top-level mutable Network state with one injected `networkState` object inside `networkView.js`; no child files yet. | Behavior unchanged; public namespace unchanged; static Network tests pass. |
| 2 | Shared/config/contract modules | Add `network/state.js`, `network/shared.js`, `network/config.js`, and `network/contract.js`; parent consumes factories and keeps wrappers. | Route resolution remains contract-derived; secret/token redaction remains unchanged; no stash globals remain after initialization. |
| 3 | Status and readiness shell | Move diagnostic rail, attention stack, topology strip, action gates, status banner, readiness, boundary, and route summary rendering. | A failure in blocked TCP/auth/path/state/queue/close evidence points to `status.js` or `readiness.js`, not command code. |
| 4 | Lifecycle evidence model and view | Move lifecycle rows, summary/detail text, dry-run requirement lines, dry-run freshness helpers, and lifecycle control rendering. | Confirmed buttons remain disabled unless a matching current dry-run is cached; lifecycle tables and details render unchanged. |
| 5 | Lifecycle command execution | Move guided/non-guided lifecycle command flows, confirmation dialog handling, POST payload construction, and command result lines. Update dynamic-dispatch tests and command inventories in the same phase. | Dry-runs remain mutation-free; confirmed calls include only `confirm_start` or `confirm_stop` after current dry-run evidence; cancellation posts nothing; command-boundary tooling identifies the new child module owner. |
| 6 | Setup and connectivity commands | Move worker test-connection, coordinator discovery, stage discovered URL, join blob, copy blob, join import, and result-line helpers. Update setup route owner inventory in the same phase. | Test-connection/discovery remain no-mutation; join blob and join cluster preserve strict confirmation fields and secret/config-write warning text; command ownership matrix points at the setup child module. |
| 7 | State-file and open-history extraction | Move state-file rows/details and diagnostics.open history filtering. | State-file panels stay read-only metadata; diagnostics opens remain backend allowlisted; open history still filters only Network targets. |
| 8 | Worker model and board extraction | Move worker status classification, filters, hidden-review warning, selected inspector, progress summary, and worker row rendering. | Filtering stays visual-only and warns when active/problem/review rows are hidden; selected worker detail remains read-only persisted state. |
| 9 | Role dashboard extraction | Move coordinator/worker overview models, coordinator active rows, coordinator queue rows, and worker claim rows. | Role dashboards remain evidence-only and do not mutate queue, claims, worker state, or launch scope. |
| 10 | Facade cleanup and generated context | Shrink parent to dependency wiring, wrapper exports, initialization, and namespace publication; refresh inventories and generated summaries. | Public export inventory, DOM inventory, route guards, generated summaries, script order, and change-packet coverage are current. |

Phase 0 must capture a baseline table before implementation begins:

| Baseline item | Evidence source |
|---|---|
| Namespace exports | `docs/inventories/WEBVIEW_GLOBAL_EXPORT_INVENTORY.md` plus source search for `window.mediaPipelineNetworkView` |
| DOM IDs and page panels | `docs/inventories/WEBVIEW_DOM_ID_INVENTORY.md` plus `apps/desktop/webview/static/partials/page-network.html` |
| Backend routes | source search for `/api/network` and `/api/diagnostics/open` plus `API_ROUTE_INVENTORY.md` |
| Direct test callers | source search for `mediaPipelineNetworkView.` under `tests/` |
| Source-only guardrail assertions | source search for `networkView.js`, `function network`, `apiPost(route, request)`, and `dynamic_api_posts` under `tests/` and `docs/inventories/` |
| Route ownership guard freshness | `node .\ops\scripts\dev\check-webview-route-ownership.mjs` and `node .\ops\scripts\dev\check-webview-command-boundary.mjs` |
| Dirty-worktree caveat | `git status --short`, reported without absorbing unrelated files |

## Stop Conditions

Stop the phase and reassess if any of these occur:

- A public `mediaPipelineNetworkView` function disappears or changes signature.
- A child script must load after `networkView.js` to work.
- Any child module creates its own selected worker, selected lifecycle row,
  selected evidence row, selected state file, filter state, last payload, or
  dry-run cache instead of using the shared parent state.
- Any lifecycle command path posts without a current dry-run cache match.
- Any documentation or code text treats the WebView dry-run fingerprint as the
  authority for lifecycle safety instead of a conservative UI-only guard before
  backend confirmation.
- A confirmed lifecycle request omits `confirm_start` or `confirm_stop`.
- A setup command request omits `confirm_create`, `confirm_rotate` when
  rotating, or `confirm_import`.
- A child command module hard-codes a Network route instead of resolving it
  from `/api/contract`.
- A command child moves `apiPost(route, request)` without updating command
  boundary tests and command ownership inventory.
- A moved troubleshooting helper starts inferring backend lifecycle safety,
  provider readiness, route allowlists, path trust, or media policy.
- A filter hides active/problem/review worker rows without the existing warning.
- A phase would require backend route or schema changes.
- A browser smoke reveals layout overlap, broken drawers/dialogs, stale button
  enablement, or missing confirmation text.

## Validation Ladder

Use the smallest safe rung for each phase, but do not skip command-route
checks for phases 5 and 6.

| Phase | Minimum validation |
|---:|---|
| 0 | No production source edits; record baseline commands, current dirty-worktree caveats, export ledger, source-only assertion migration, and inventory migration. |
| 1-3 | Static Network boundary test plus WebView route ownership and command-boundary guards. |
| 4 | Static Network test plus browser Network smoke if lifecycle tables/control enablement moved. |
| 5 | Static Network test, browser Network smoke, frontend mutation-boundary test, and API command contract tests for lifecycle confirmations. |
| 6 | Static Network test, browser Network smoke, API contract payload/command tests for test-connection/discovery/join routes. |
| 7 | Static Network test plus browser Network smoke if selection/detail/open-history behavior moved. |
| 8-9 | Static Network test plus browser Network smoke for worker filters, hidden review warning, selected inspector, progress summary, and role dashboards. |
| 10 | Generated context refresh, WebView route ownership guard, public export/DOM inventories, and change-packet validation. |

Preferred commands use the bundled Python runtime:

```powershell
.\apps\desktop\runtime\Python\python.exe -m unittest tests.webview.test_webview_network_read_only_boundary -q
.\apps\desktop\runtime\Python\python.exe -m unittest tests.webview.test_webview_browser_network_smoke -q
.\apps\desktop\runtime\Python\python.exe -m unittest tests.webview.test_webview_frontend_mutation_boundary -q
.\apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_api_command_contracts -q
.\apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_api_contract_payload -q
node .\ops\scripts\dev\check-webview-route-ownership.mjs
node .\ops\scripts\dev\check-webview-command-boundary.mjs
npm run webview:prework:check
npm run webview:check
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.dev.refresh_summaries --changed
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.change_control.validate_changes --require-worktree-coverage
```

If browser-backed smoke prerequisites are unavailable, record the skip reason
and run the strongest static WebView contract checks available in the current
environment.

## Rollback Strategy

Every phase should be reversible by restoring the moved functions to
`networkView.js`, removing the child script tag or tags, and deleting the
temporary stash-global consumption from the parent. Do not combine unrelated
cleanup with an extraction phase. Do not delete old parent wrappers until the
final cleanup phase proves the wrappers are no longer needed.

## Required Phase Report

Every implementation phase should finish with:

- change packet ID
- files touched
- functions moved
- public exports preserved or intentionally changed
- export ledger row updates for every moved wrapper
- backend routes touched
- command owner inventory updates when command code moves
- validation commands and outcomes
- generated summary/inventory refresh status
- strict change-packet coverage status
- unrelated dirty files not absorbed into the packet
- rollback plan

## Adversarial Review Gate

Before declaring any phase complete, review it as if it was poorly made:

- Did it split by line count instead of by troubleshooting boundary?
- Did it hide behavior changes inside "cleanup"?
- Did it assume generated route ownership data is current without rerunning it?
- Did it create a child module that silently depends on parent closure state?
- Did it add a new public global that inventories do not track?
- Did it leave a temporary stash global visible after parent initialization?
- Did it let more than one module own selected worker, lifecycle, evidence,
  state-file, filter, last-payload, or dry-run-cache state?
- Did it remove a wrapper only because local source search missed a browser
  smoke or external operator path?
- Did it weaken strict confirmation fields or dry-run freshness matching?
- Did it start hard-coding Network route paths instead of using `/api/contract`?
- Did it make setup commands look like lifecycle start/stop commands?
- Did it let worker filters hide active/problem rows without the existing
  warning?
- Did it leave generated summaries stale?
- Did it skip the browser smoke even though tab, drawer, dialog, command, or
  selection behavior moved?
- Did it absorb unrelated dirty worktree files into the phase packet?

If any answer is yes, fix the phase before moving on.
