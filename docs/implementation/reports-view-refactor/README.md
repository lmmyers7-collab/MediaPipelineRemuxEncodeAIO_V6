# Reports View Refactor Planning Pack

Date: 2026-06-25
Status: planning only
Change packet: MP-CHANGE-2026-0624-046

## Purpose

This planning pack describes how to split
`apps/desktop/webview/static/assets/reportsView.js` into smaller,
troubleshooting-oriented WebView modules without changing operator behavior,
backend route ownership, or public WebView contracts first.

The current file is too broad to maintain safely:

| Current surface | Current shape |
|---|---:|
| File | `apps/desktop/webview/static/assets/reportsView.js` |
| Approximate size | about 200 KB / 4k+ lines |
| Runtime model | ordered `<script>` tags, no bundler |
| Public namespace | `window.mediaPipelineReportsView` |
| Flat exports | none |
| Main page partial | `apps/desktop/webview/static/partials/page-reports.html` |
| Page tabs | Failures, Audit, Locations |

The goal is not to create many files for its own sake. The goal is one clear
failure boundary per module so a failing Reports test tells the maintainer
whether the issue is shared report shell state, failure triage rendering,
failure preview-first commands, audit row rendering, audit process controls,
locations/open-target evidence, or cross-tab triage status.

This pack is subordinate to:

- `AGENTS.md`
- `docs/DOCS_INDEX.md`
- `docs/architecture/ARCHITECTURE.md`
- `docs/architecture/MODULE_MAP.md`
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
- No media, source, output, publish, queue, settings, or filesystem mutation
  policy changes.
- No ES modules, imports, bundler, TypeScript conversion, React migration, or
  new frontend framework.
- No removal or renaming of `window.mediaPipelineReportsView` exports until
  inventories and tests intentionally prove the export is unused.
- No generated-file hand edits under `docs/generated/`.

## Public Contracts To Preserve

The parent `reportsView.js` remains the public facade throughout the split.
All child modules must be loaded before the parent in
`apps/desktop/webview/static/index.html`.

Preserve at least these namespace functions until a later contract-change
packet deliberately updates tests and inventories:

| Function | Current public use |
|---|---|
| `renderReports` | Refresh path and browser smoke setup |
| `renderFailurePreview` | Reports failure table, grouped resolution, marker clear smokes |
| `renderAuditPreview` | Audit table/review smoke coverage |
| `renderAuditControls` | Audit controls smoke coverage |
| `initReportsViewEvents` | Browser smoke event binding and tab/key behavior |
| `renderReportTriage` / `renderReportInvestigation` | Static report-triage surface |
| `requestFailureMarkerClear` / `requestFailureEvidenceArchive` | Preview-first failure command coverage |
| `startReportAuditFromForm` / `stopReportAuditFromForm` | Backend-owned audit process control surface |

Preserve these backend route boundaries:

| Route | Reports role | Required guardrail |
|---|---|---|
| `POST /api/failures/lifecycle` | Operator resolution journal write | preview fingerprint plus `confirm_transition` for confirmed resolve/reopen/waive |
| `POST /api/failures/clear` | Failure marker move only | preview-first flow plus `confirm_clear` for confirmed marker clear |
| `POST /api/failures/archive-evidence` | Failure marker/report archive only | preview fingerprint, reason, and `confirm_archive` |
| `POST /api/audit/start` | Audit process launch | explicit operator confirmation before POST; backend owns launch locks |
| `POST /api/audit/stop` | Audit process control | `confirm_stop: true` and reason |
| `POST /api/audit/score-policy` | Audit policy state write | backend-owned score-policy write only |
| `POST /api/audit/ignore` | Audit ignore state write | audit-only ignore state; no queue/media mutation |
| `POST /api/audit/export-rerun-csv` | Backend-owned CSV artifact write | no rerun launch |

Generated WebView route ownership data may lag the source in a dirty worktree.
Before moving command code, rerun the route ownership guard tooling and make
sure the generated route list agrees with the routes above.

At minimum, compare source routes with:

```powershell
node .\ops\scripts\dev\check-webview-route-ownership.mjs
node .\ops\scripts\dev\check-webview-command-boundary.mjs
```

If those scripts report stale generated data or missing confirmation evidence,
fix that in the same phase before moving command code.

## Target Runtime Pattern

Use the existing WebView split pattern from `completed/`, `settings/`, and
`dom/` modules:

1. Child file declares a factory on a temporary stash global.
2. Parent `reportsView.js` creates the single Reports state instance.
3. Parent `reportsView.js` reads the child factory, passes dependencies, then
   deletes the stash global.
4. Child modules may mutate the injected state object, but must not create
   competing copies of selection, busy, timer, preview, or last-payload state.
5. Parent keeps the public `window.mediaPipelineReportsView` namespace and
   wrapper functions.

Example shape:

```javascript
// apps/desktop/webview/static/assets/reports/failures.model.js
(function () {
  "use strict";

  function createReportsFailuresModelModule(deps = {}) {
    const state = deps.state || {};
    return {
      failureRowKey,
      failureReviewStatus,
    };
  }

  window.__reportsViewFailuresModelModule = {
    createReportsFailuresModelModule,
  };
})();
```

The parent should consume it with dependency injection, not with ad hoc access
to unrelated globals:

```javascript
const failuresModelModule = window.__reportsViewFailuresModelModule || {};
delete window.__reportsViewFailuresModelModule;
const failuresModel = typeof failuresModelModule.createReportsFailuresModelModule === "function"
  ? failuresModelModule.createReportsFailuresModelModule({
    state: reportsState,
    byId: typeof byId === "function" ? byId : window.byId,
    setText: typeof setText === "function" ? setText : window.setText,
  })
  : {};
```

The script order in `index.html` should remain plain ordered scripts. Child
modules load immediately before the parent:

```html
<script src="/assets/reports/state.js"></script>
<script src="/assets/reports/shared.js"></script>
<script src="/assets/reports/failures.model.js"></script>
<script src="/assets/reportsView.js"></script>
```

Do not switch to `type="module"` as part of this refactor.

## Target File Shape

Use a dedicated `reports/` child directory to keep Reports-owned modules
discoverable:

```text
apps/desktop/webview/static/assets/reportsView.js
apps/desktop/webview/static/assets/reports/state.js
apps/desktop/webview/static/assets/reports/shared.js
apps/desktop/webview/static/assets/reports/locations.js
apps/desktop/webview/static/assets/reports/failures.model.js
apps/desktop/webview/static/assets/reports/failures.view.js
apps/desktop/webview/static/assets/reports/failures.commands.js
apps/desktop/webview/static/assets/reports/audit.model.js
apps/desktop/webview/static/assets/reports/audit.view.js
apps/desktop/webview/static/assets/reports/audit.commands.js
apps/desktop/webview/static/assets/reports/triage.js
```

Do not create every file mechanically. Create a child module only when the
phase has a concrete boundary, wrapper, test target, and rollback path.

| Target module | Owns | Must not own |
|---|---|---|
| `reports/state.js` | Factory for the single Reports page state container and reset helpers injected by the parent | Backend policy, DOM rendering, or independent state copies |
| `reports/shared.js` | Row limits, selection helpers, tab nav, chip state, report labels, diagnostics action rendering | Failure/audit route POSTs |
| `reports/locations.js` | Latest report paths, report roots, open history, warning rows | Diagnostics open/tail policy |
| `reports/failures.model.js` | Pure failure row/group/retry/evidence classification helpers | DOM writes or API calls |
| `reports/failures.view.js` | Failure preview, grouped issues, detail panels, rows, keyboard navigation | POST routes |
| `reports/failures.commands.js` | Lifecycle, marker clear, evidence archive request building and result rendering | Backend validation logic or marker path trust |
| `reports/audit.model.js` | Pure audit row keys, matching, owner, review status helpers | DOM writes or API calls |
| `reports/audit.view.js` | Audit preview rows, detail panel, review board, score form rendering | POST routes |
| `reports/audit.commands.js` | Audit start/stop, score-policy, ignore, export-rerun CSV command flows | Backend process policy |
| `reports/triage.js` | Cross-tab report triage and investigation summary | Owning failure/audit command decisions |

## Phase Order

Execute these in order. Do not move command code before the public contracts
and baseline behavior are locked.

| Phase | Name | Purpose | Exit criteria |
|---:|---|---|---|
| 0 | Baseline and contract map | Capture current exports, routes, DOM IDs, tests, and stale generated-data gaps. | Route list, namespace exports, direct test callers, DOM ownership, and validation commands are recorded in the change packet. |
| 1 | Parent state seam | Replace scattered top-level mutable variables with a single `reportsState` object inside `reportsView.js`; no child files yet. | Behavior unchanged; public namespace unchanged; static Reports tests pass. |
| 2 | Shared child loader pattern | Add `reports/state.js` and `reports/shared.js`; parent consumes factories and keeps wrappers. | Child scripts load before parent; no new public globals remain after parent initialization except `mediaPipelineReportsView`. |
| 3 | Locations and report shell extraction | Move latest paths, report roots, warnings, open history, tab nav, and diagnostics-action rendering. | Reports Locations tab renders unchanged; diagnostics handoff still uses backend-owned diagnostics functions. |
| 4 | Failure model extraction | Move pure failure helpers: row keys, grouping, retry state, evidence lines, owners, severity, search/chip matching. | Existing failure renderers call child helpers; no DOM or API logic moves with model helpers. |
| 5 | Failure view extraction | Move failure preview rendering, grouped resolution UI, failure rows/detail, keyboard selection, and review board rendering. | `renderFailurePreview`, `renderFailureRows`, `renderFailureDetail`, and review-board exports remain wrapper-compatible. |
| 6 | Audit model and view extraction | Move audit row keys, matching, review helpers, preview rows/detail, score-policy UI, and audit review board rendering. | `renderAuditPreview`, `renderAuditRows`, `renderAuditDetail`, and `renderAuditControls` remain wrapper-compatible. |
| 7 | Failure command extraction | Move lifecycle, marker clear, row clear, and evidence archive command flows. | `confirm_transition`, `confirm_clear`, `confirm_archive`, dry-run fingerprints, busy state, and local post-clear UI updates are unchanged. |
| 8 | Audit command extraction | Move audit start/stop, score policy, ignore, export-rerun CSV, saved locations, audit progress timers, and refresh handoff. | `confirm_stop`, operator confirmation prompts, refresh scheduling, command history, and busy state are unchanged. |
| 9 | Facade cleanup and generated context | Shrink parent to dependency wiring, wrapper exports, and initialization; refresh docs/generated and inventories. | Public export inventory, DOM inventory, route ownership guard, generated summaries, and change packet coverage are current. |

Phase 0 must capture a baseline table before implementation begins:

| Baseline item | Evidence source |
|---|---|
| Namespace exports | `docs/inventories/WEBVIEW_GLOBAL_EXPORT_INVENTORY.md` plus source search |
| DOM IDs and tab panels | `docs/inventories/WEBVIEW_DOM_ID_INVENTORY.md` plus `page-reports.html` |
| Backend routes | source search for `/api/` plus `API_ROUTE_INVENTORY.md` |
| Direct test callers | source search for `window.mediaPipelineReportsView.` under `tests/` |
| Generated route guard freshness | `check-webview-route-ownership.mjs` and `check-webview-command-boundary.mjs` |
| Dirty-worktree caveat | `git status --short`, reported without absorbing unrelated files |

## Stop Conditions

Stop the phase and reassess if any of these occur:

- A public `mediaPipelineReportsView` function disappears or changes signature.
- A child script must load after `reportsView.js` to work.
- A command route is moved without a test proving its request payload, busy
  state, confirmation field, and error handling.
- Generated route ownership data disagrees with source and the phase is about
  to move command code.
- Any extraction duplicates state instead of sharing a single parent-owned
  state object.
- Failure marker paths, audit row keys, dry-run fingerprints, or hidden selected
  row behavior are recomputed differently.
- A phase would require backend route or schema changes.
- A browser smoke reveals layout overlap, missing controls, or broken tab
  visibility.

## Validation Ladder

Use the smallest safe rung for each phase, but do not skip the command-route
checks for phases 7 and 8.

| Phase | Minimum validation |
|---:|---|
| 0 | No source edits; record baseline commands and current dirty-worktree caveats. |
| 1-3 | `python -m unittest tests.python.desktop.test_reports_view_static -q`; WebView public contract/static route ownership checks if script order or exports change. |
| 4-6 | Static Reports tests plus targeted browser maintenance/reports smoke when renderers or selection behavior move. |
| 7 | Static Reports tests, command contract tests covering failure lifecycle/clear/archive, and browser maintenance/reports smoke. |
| 8 | Static Reports tests, audit command route tests, process launch/control route tests, and browser maintenance/reports smoke. |
| 9 | Generated context refresh, WebView route ownership guard, public export/DOM inventories, and change-packet validation. |

Preferred commands use the bundled Python runtime:

```powershell
.\apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_reports_view_static -q
.\apps\desktop\runtime\Python\python.exe -m unittest tests.webview.test_webview_browser_maintenance_reports_smoke -q
.\apps\desktop\runtime\Python\python.exe -m unittest tests.webview.test_webview_frontend_mutation_boundary -q
node .\ops\scripts\dev\check-webview-route-ownership.mjs
node .\ops\scripts\dev\check-webview-command-boundary.mjs
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.dev.refresh_summaries --changed
.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.change_control.validate_changes --require-worktree-coverage
```

If browser-backed smoke prerequisites are unavailable, record the skip reason
and run the strongest static WebView contract checks available in the current
environment.

## Rollback Strategy

Every phase should be reversible by restoring the moved functions to
`reportsView.js`, removing the child script tag(s), and deleting the temporary
stash global consumption from the parent. Do not combine unrelated cleanup with
an extraction phase. Do not delete old parent wrappers until the final cleanup
phase proves the wrappers are no longer needed.

## Required Phase Report

Every implementation phase should finish with:

- change packet ID
- files touched
- functions moved
- public exports preserved or intentionally changed
- backend routes touched
- validation commands and outcomes
- generated summary/inventory refresh status
- strict change-packet coverage status
- unrelated dirty files not absorbed into the packet
- rollback plan

## Adversarial Review Gate

Before declaring any phase complete, review it as if it was poorly made:

- Does it split by line count instead of by failure boundary?
- Did it hide behavior changes inside "cleanup"?
- Did it assume generated route ownership data is current without rerunning it?
- Did it create a child module that silently depends on parent closure state?
- Did it add a new public global that inventories do not track?
- Did it leave a temporary stash global visible after parent initialization?
- Did it let more than one module own Reports selection, timer, busy, or
  preview-fingerprint state?
- Did it remove a wrapper only because local source search missed a browser
  smoke or external operator path?
- Did it weaken strict confirmation fields or preview-fingerprint matching?
- Did it leave generated summaries stale?
- Did it skip the browser smoke even though tab/render/command behavior moved?
- Did it absorb unrelated dirty worktree files into the phase packet?

If any answer is yes, fix the phase before moving on.
