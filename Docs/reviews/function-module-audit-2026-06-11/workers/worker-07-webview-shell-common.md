# Worker Review: worker-07-webview-shell-common

## Scope

Review-only function/module-level audit for the shared WebView shell/common surface:

- `apps/desktop/webview/static/index.html`
- app shell partials
- shared API client
- shared DOM helpers
- layout manager
- lifecycle, refresh, topbar, readiness, and Tauri lifecycle bridge modules
- shared formatters, command history, progress, status, filtering, and table utilities
- shared WebView CSS files assigned to W07

Required first reads were completed: `AGENTS.md`, `docs/CURRENT_PROJECT_STATE.md`, `docs/OPEN_WORK_CHECKLIST.md`, `docs/generated/PROJECT_INDEX.md`, and `docs/reviews/function-module-audit-2026-06-11/ASSIGNMENTS.md`.

Generated summaries under `docs/generated/summaries/<path>.md` were checked before opening assigned source files. The assigned summaries existed but were unparsed medium-priority stubs, so source reads were needed for symbol-level evidence.

No source, runtime, media, LocalBase, aggregate review, queue, publish, rename, or launcher files were edited.

## Coverage Ledger

| File | Coverage | Notes |
| --- | --- | --- |
| `apps/desktop/webview/static/assets/apiClient.js` | Complete static | API base, auth headers, timeout wrapper, GET/POST, response parsing. Finding W07-001. |
| `apps/desktop/webview/static/assets/app.js` | Complete static for shell/common paths | Startup order, refresh orchestration, backend shutdown, shared UI preference sync, Tauri lifecycle listener, top-level bindings. Finding W07-004. |
| `apps/desktop/webview/static/assets/app/closeReadiness.js` | Complete static | Compatibility wrapper only; delegates to lifecycle module. |
| `apps/desktop/webview/static/assets/app/home.js` | Complete targeted static | Home readiness/storage/queue/recent output render helpers, DOM writes, cross-page delegates. |
| `apps/desktop/webview/static/assets/app/homeReadiness.js` | Complete static | Compatibility wrapper only; delegates to `mediaPipelineAppHome`. |
| `apps/desktop/webview/static/assets/app/layoutManager.js` | Complete static for layout shell | Drawer open/close, reset handlers, drawer tree rendering, local layout persistence, legacy class references. Finding W07-003. |
| `apps/desktop/webview/static/assets/app/lifecycle.js` | Complete static for shell/common lifecycle | Navigation, tab accessibility, theme/evidence/advanced toggles, keyboard shortcuts, Tauri lifecycle alert rendering, empty-state actions. Finding W07-005. |
| `apps/desktop/webview/static/assets/app/refresh.js` | Complete static | Refresh button state, current-output read-only refresh, queue scan busy text. |
| `apps/desktop/webview/static/assets/app/rowOpenActions.js` | Complete static | Backend-owned open action groups and renderer delegation. |
| `apps/desktop/webview/static/assets/app/tauriLifecycle.js` | Complete static | Compatibility wrapper only; delegates to lifecycle module. |
| `apps/desktop/webview/static/assets/app/topbar.js` | Complete static | Topbar label formatting and delegated renderers. |
| `apps/desktop/webview/static/assets/commandHistory.js` | Complete targeted static | Read-only command rendering, selected command state, diagnostics action delegation, DOM safety. |
| `apps/desktop/webview/static/assets/commandHistory/formatters.js` | Complete static | Command result labels, ownership, pending publish/final-placement advisory text. |
| `apps/desktop/webview/static/assets/dom/filtering.js` | Complete static | In-memory row filtering/status summaries. |
| `apps/desktop/webview/static/assets/dom/query.js` | Complete static | `byId` helper only. |
| `apps/desktop/webview/static/assets/dom/status.js` | Complete static | Status normalization, chips, table legend text. |
| `apps/desktop/webview/static/assets/dom/table.js` | Complete static | Row selection, scroll preservation, table filtering/sorting/column UI, open-target actions. Finding W07-002. |
| `apps/desktop/webview/static/assets/dom/text.js` | Complete static | Safe text rendering, diagnostic callouts, JSON detail text. |
| `apps/desktop/webview/static/assets/domHelpers.js` | Complete static | Split-module composition, exported DOM helper namespace. |
| `apps/desktop/webview/static/assets/formatters.js` | Complete static | Percent/memory/config/list/path formatting helpers. |
| `apps/desktop/webview/static/assets/progressView.js` | Complete targeted static | Progress bar/detail renderers, diagnostic progress evidence, active work renderers, DOM safety. |
| `apps/desktop/webview/static/assets/styles.components.css` | Complete static CSS scan | Focus-visible, table UI, action hint, overflow, hidden-state rules. |
| `apps/desktop/webview/static/assets/styles.controls.css` | Complete static CSS scan | Control focus states, visibility, tooltip rules. |
| `apps/desktop/webview/static/assets/styles.css` | Complete static | Imports and reduced-motion/global responsive rules. |
| `apps/desktop/webview/static/assets/styles.layout-manager.css` | Complete static CSS scan | Drawer visibility/focus behavior, mobile drawer, layout manager states. Finding W07-003. |
| `apps/desktop/webview/static/assets/styles.layout.css` | Complete static CSS scan | App shell, nav, topbar, focus, responsive layout. |
| `apps/desktop/webview/static/assets/styles.pages.css` | Complete static CSS scan | Shared page/tab/layout helper rules. |
| `apps/desktop/webview/static/assets/styles.queue.css` | Complete static CSS scan | Queue shared controls/drawers, focus and reduced-motion rules. |
| `apps/desktop/webview/static/assets/styles.theme.css` | Complete static CSS scan | Theme-specific shared states. |
| `apps/desktop/webview/static/assets/styles.tokens.css` | Complete static | Design/status/focus tokens and light-mode remapping. |
| `apps/desktop/webview/static/assets/tauriLifecycleBridge.js` | Complete static | Read-only Tauri event listener and WebView custom event bridge. Finding W07-004. |
| `apps/desktop/webview/static/index.html` | Complete static | Script order, includes, bootstrap wiring. Finding W07-004. |
| `apps/desktop/webview/static/partials/app-shell-end.html` | Complete static | Shell close tags only. |
| `apps/desktop/webview/static/partials/app-shell-start.html` | Complete static | Topbar, force stop control, layout editor drawer markup. Finding W07-003. |

## Findings Summary

| Severity | ID | Finding |
| --- | --- | --- |
| High | W07-001 | API client treats invalid JSON from successful API responses as successful data. |
| Medium | W07-002 | Keyboard row navigation can focus and select rows hidden by enhanced table filters. |
| Medium | W07-003 | Closed layout editor drawer is only translated offscreen, leaving reset controls focusable and operable under `aria-hidden`. |
| Medium | W07-004 | Tauri backend lifecycle events can be lost during startup before `app.js` registers its listener. |
| Low | W07-005 | Empty-state Customize action checks the retired `layout-customize-mode` class instead of the active drawer state. |

## Detailed Findings

### W07-001 - High - API client accepts invalid JSON as successful data

- Severity: High
- File: `apps/desktop/webview/static/assets/apiClient.js`
- Symbol/section: `parseResponse`, `apiGet`, `apiPost`
- Evidence: `parseResponse` reads response text, attempts `JSON.parse(raw)`, but on parse failure stores `{ error: raw.slice(0, 500) }` and still returns that object when `response.ok` is true (`apiClient.js:13-26`). Both `apiGet` and `apiPost` return `parseResponse(response)` (`apiClient.js:54-71`).
- Impact: Strict JSON route handling is release-critical for this project. A 2xx HTML/token/captive/static response or backend bug returning non-JSON is accepted as a successful API payload. Command callers commonly distinguish backend failures through `ok === false` or thrown errors; `{ error: "...raw..." }` has neither a failed HTTP status nor a required response shape. That can hide backend/API breakage and let shell state render as stale, empty, or apparently successful instead of failing closed.
- Fix direction: Fail closed on JSON parse errors for `/api/*` responses. Throw an explicit invalid JSON error that includes route/status context. Optionally require `Content-Type: application/json` for API responses, while preserving an explicit empty-body policy for any intended 204/empty responses.
- Validation: Add an API client unit/smoke test that mocks `fetch` with `ok: true` and invalid JSON and asserts `apiGet`/`apiPost` reject. Add a command-path test, for example backend shutdown or UI preferences, proving parse errors render as command/read failures rather than success.

### W07-002 - Medium - Filtered-out rows remain keyboard-selectable

- Severity: Medium
- File: `apps/desktop/webview/static/assets/dom/table.js`
- Symbol/section: `selectableRowsFor`, `moveSelectableRowFocus`, `applyTableFilters`
- Evidence: `selectableRowsFor(row)` returns every `tr[data-selectable-row="true"]` in the row's `tbody` without filtering hidden rows (`dom/table.js:250-253`). Arrow navigation calls `moveSelectableRowFocus`, which focuses and clicks `rows[index + delta]` (`dom/table.js:265-293`). Enhanced table filtering sets `row.hidden = !rowMatchesFilters(row, state)` (`dom/table.js:550-553`). A nearby lifecycle shortcut implementation already filters visible rows through `shortcutElementVisible` (`app/lifecycle.js:1085-1088`).
- Impact: After a user applies shared table filtering or column filters, ArrowUp/ArrowDown can focus and click rows that are hidden from the table. That can move selected-row/detail state to an invisible item. On command-heavy pages such as Queue, Completed, Pending Publish, and Command History, the operator can believe the selected row belongs to the visible filtered result while subsequent backend-owned actions or diagnostics use a hidden row.
- Fix direction: Make `selectableRowsFor` return only visible rows, at minimum excluding `row.hidden` and elements hidden by CSS or `aria-hidden`. Reuse or mirror `shortcutElementVisible` so table row navigation and global page shortcuts share visibility semantics.
- Validation: Extend `tests/webview/test_webview_dom_helpers_smoke.py` with three selectable rows, hide the middle row, press ArrowDown from the first row, and assert the third row is focused/selected. Add a browser large-table smoke that applies an enhanced table filter and verifies ArrowUp/ArrowDown never selects hidden rows.

### W07-003 - Medium - Closed layout editor drawer keeps focusable reset controls alive

- Severity: Medium
- Files: `apps/desktop/webview/static/partials/app-shell-start.html`, `apps/desktop/webview/static/assets/styles.layout-manager.css`, `apps/desktop/webview/static/assets/app/layoutManager.js`
- Symbol/section: `#layout-editor-drawer`, `enterCustomize`, `exitCustomize`, drawer reset handlers
- Evidence: The drawer starts as `<aside id="layout-editor-drawer" class="layout-editor-drawer" aria-hidden="true">` and contains focusable buttons including `layout-editor-done`, `layout-editor-reset-subtab`, `layout-editor-reset-page`, and `layout-editor-reset-all` (`app-shell-start.html:50-63`). Closed CSS keeps the drawer in the DOM with `display: grid` and `transform: translateX(100%)`; opening changes only the transform (`styles.layout-manager.css:46-63`). `enterCustomize` and `exitCustomize` toggle only `body.layout-editor-open` and `aria-hidden` (`layoutManager.js:1382-1403`). The reset-subtab/page/all button handlers are registered unconditionally and do not check that the drawer is open (`layoutManager.js:1434-1446`).
- Impact: Keyboard users can tab into an offscreen drawer that is marked `aria-hidden`, which is an accessibility regression and a confusing focus trap. More importantly, reset controls can mutate local layout preferences while the Customize drawer appears closed. This does not mutate media or backend state, but it can reset or change operator-facing panel layout unexpectedly.
- Fix direction: When closed, make the drawer non-interactive and out of the sequential focus order using `inert` plus `aria-hidden`, or `hidden` if transitions are not required. Restore interactivity on open. Add an open-state guard to destructive/local-reset handlers as a defense in depth.
- Validation: Extend `tests/webview/test_webview_browser_layout_manager_smoke.py` to assert drawer buttons are not focusable or activatable while closed, then open the drawer and assert focusability returns. Add a closed-state reset-button activation check that proves local layout state is unchanged.

### W07-004 - Medium - Tauri backend lifecycle event can be lost during startup

- Severity: Medium
- Files: `apps/desktop/webview/static/index.html`, `apps/desktop/webview/static/assets/tauriLifecycleBridge.js`, `apps/desktop/webview/static/assets/app.js`
- Symbol/section: script order, `startTauriLifecycleBridge`, `DOMContentLoaded` startup
- Evidence: `index.html` loads `tauriLifecycleBridge.js` before `app.js` (`index.html:156`, `index.html:184`). The bridge registers a Tauri listener and immediately dispatches `window.dispatchEvent(new CustomEvent("mediapipeline:backend-lifecycle", ...))` for backend lifecycle messages (`tauriLifecycleBridge.js:12-23`). `app.js` registers its `mediapipeline:backend-lifecycle` listener only near the end of an async `DOMContentLoaded` handler (`app.js:1476-1496`). Before listener registration, that handler awaits `restoreSharedUiPreferences()` (`app.js:1479`), which performs a 5 second timeout API read from `/api/ui-preferences` (`app.js:1112-1118`). The event handler is the only place that records `lastTauriBackendLifecycleEvent` and renders the alert (`app.js:335-339`).
- Impact: If Tauri emits a backend exit, health failure, or monitor error after the bridge starts listening but before `app.js` registers its WebView event listener, the event is dropped. The operator can miss the startup/crash recovery banner during the exact window where lifecycle evidence is most important before starting, draining, saving, renaming, publishing, or closing.
- Fix direction: Register `window.addEventListener("mediapipeline:backend-lifecycle", handleTauriBackendLifecycleEvent)` before the first awaited startup call in `app.js`. Alternatively, have `tauriLifecycleBridge.js` buffer the latest lifecycle event on a well-known global and let app startup replay it after initialization.
- Validation: Add a browser/Tauri lifecycle smoke that dispatches `mediapipeline:backend-lifecycle` before a mocked `/api/ui-preferences` request resolves, then asserts `.tauri-lifecycle-alert` renders after app initialization. Keep the existing read-only bridge boundary test.

### W07-005 - Low - Empty-state Customize action checks retired layout class

- Severity: Low
- File: `apps/desktop/webview/static/assets/app/lifecycle.js`
- Symbol/section: `panelVisibilityEmptyState`
- Evidence: The empty-state Customize button checks `document.body.classList.contains("layout-customize-mode")` and clicks `#customize-layout-btn` when that legacy class is absent (`app/lifecycle.js:456-463`). The active drawer implementation uses `layout-editor-open` (`layoutManager.js:1382-1403`), and the layout-manager browser smoke explicitly asserts the legacy inline customize class should not activate (`tests/webview/test_webview_browser_layout_manager_smoke.py:59-64`).
- Impact: The empty-state Customize action is not idempotent with the current drawer state. If the drawer is already open, the empty-state action can click the topbar toggle and close it instead of leaving Customize open or refreshing empty-state visibility. This is a stale state check and a minor layout workflow bug.
- Fix direction: Check `layout-editor-open` or call a layout-manager open-only API instead of toggling through the topbar button. Consider removing stale `layout-customize-mode` checks from shell code that is no longer expected to activate.
- Validation: Add a layout-manager smoke case for the no-visible-panels empty state: click Customize when closed and assert the drawer opens; click the empty-state action while open and assert the drawer remains open.

## Test Coverage Gaps

- API client tests assert `JSON.parse(raw)` exists but do not exercise invalid JSON on a 2xx response. Add fail-closed parse tests for `apiGet` and `apiPost`.
- DOM helper row-selection smoke covers ArrowDown selecting the next row, but not hidden rows after shared table filtering. Add hidden-row keyboard navigation coverage.
- Browser layout manager smoke verifies drawer opens and manages panel order, but not closed drawer focusability, inertness, or reset-button no-op behavior while closed.
- Tauri lifecycle static tests verify bridge strings and read-only posture, but not the startup race where the bridge dispatches before `app.js` registers the listener.
- Empty-state layout tests do not cover the "no boxes visible" Customize action against the current `layout-editor-open` drawer state.

## Boundary Risks

- No direct filesystem, media, shell, Tauri filesystem, source/scratch/output, pending-publish drain, rename apply, or queue mutation was found in the assigned shared shell/common files.
- Direct `fetch` use in the assigned slice is centralized in `apiClient.js`.
- Direct W07 `apiPost` routes are limited to backend-owned `/api/backend/shutdown` and `/api/ui-preferences`; page-owned mutation routes are delegated outside this slice.
- `tauriLifecycleBridge.js` is read-only event bridging; no `apiPost`, `fetch`, invoke, shell, filesystem, remove, or open-path operation was found there.
- Assigned files use `textContent`, `createElement`, `append`, and `replaceChildren` for inspected dynamic rendering. `innerHTML`/`insertAdjacentHTML` hits found during broad search were in page-owned assets outside W07 scope.
- Row open actions in this slice delegate to backend-owned page functions such as `requestCompletedOpen`, `requestPendingPublishOpen`, and `requestQueueOpen`; the owning page implementations were not audited here.

## Files Reviewed With No Findings

- `apps/desktop/webview/static/assets/app/closeReadiness.js`
- `apps/desktop/webview/static/assets/app/home.js`
- `apps/desktop/webview/static/assets/app/homeReadiness.js`
- `apps/desktop/webview/static/assets/app/refresh.js`
- `apps/desktop/webview/static/assets/app/rowOpenActions.js`
- `apps/desktop/webview/static/assets/app/tauriLifecycle.js`
- `apps/desktop/webview/static/assets/app/topbar.js`
- `apps/desktop/webview/static/assets/commandHistory.js`
- `apps/desktop/webview/static/assets/commandHistory/formatters.js`
- `apps/desktop/webview/static/assets/dom/filtering.js`
- `apps/desktop/webview/static/assets/dom/query.js`
- `apps/desktop/webview/static/assets/dom/status.js`
- `apps/desktop/webview/static/assets/dom/text.js`
- `apps/desktop/webview/static/assets/domHelpers.js`
- `apps/desktop/webview/static/assets/formatters.js`
- `apps/desktop/webview/static/assets/progressView.js`
- `apps/desktop/webview/static/assets/styles.components.css`
- `apps/desktop/webview/static/assets/styles.controls.css`
- `apps/desktop/webview/static/assets/styles.css`
- `apps/desktop/webview/static/assets/styles.layout.css`
- `apps/desktop/webview/static/assets/styles.pages.css`
- `apps/desktop/webview/static/assets/styles.queue.css`
- `apps/desktop/webview/static/assets/styles.theme.css`
- `apps/desktop/webview/static/assets/styles.tokens.css`
- `apps/desktop/webview/static/partials/app-shell-end.html`

## Files Marked Out Of Scope

- Page-owned WebView assets such as `queueView.js`, `completedView.js`, `pendingPublishView.js`, `renameView.js`, `launchView.js`, `settingsView.js`, `settingsWizard.js`, `diagnosticsView.js`, `reportsView.js`, `scheduleView.js`, and maintenance/network/sample-validation views. References to their globals were considered only for shared-shell ownership boundaries.
- Backend route implementations, contracts, and local API handlers, except where needed to classify W07 frontend route ownership.
- Existing test files were read only as coverage-gap evidence and were not part of this worker's source audit.
- Existing uppercase worker report files and aggregate audit files under `docs/reviews/function-module-audit-2026-06-11/` were not edited.

## Incomplete Coverage

None for the assigned W07 file list as a static function/module review. Browser/Tauri runtime smokes, visual rendering, contrast measurement, and assistive-technology execution were not run because this mission was review-only and prohibited code changes.

Validation status at report creation:

- Static source and test inspection only.
- No automated tests or browser smokes run.
- `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.change_control.validate_changes --require-worktree-coverage` failed because unrelated existing worktree file `docs/implementation/encoder-breadth-av1-plan.md` is not listed in any unreleased packet.
- W07 report coverage is complete: `docs/reviews/function-module-audit-2026-06-11/workers/worker-07-webview-shell-common.md` and `ops/release/changes/unreleased/MP-CHANGE-2026-0610-005.json` are listed in `MP-CHANGE-2026-0610-005`.
