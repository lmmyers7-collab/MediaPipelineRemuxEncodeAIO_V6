# Worker Review: W07-webview-shell-common

## Scope
- Assigned domain: webview-shell-common
- Assigned files: 34 files listed below
- Explicit exclusions: none. Review was time-boxed by user interruption; incomplete coverage is listed below.

## Assigned File List

- `apps/desktop/webview/static/assets/apiClient.js` (webview, medium, code-symbol-review, summary=yes)
- `apps/desktop/webview/static/assets/app.js` (webview, medium, code-symbol-review, summary=yes)
- `apps/desktop/webview/static/assets/app/closeReadiness.js` (webview, medium, code-symbol-review, summary=yes)
- `apps/desktop/webview/static/assets/app/home.js` (webview, medium, code-symbol-review, summary=yes)
- `apps/desktop/webview/static/assets/app/homeReadiness.js` (webview, medium, code-symbol-review, summary=yes)
- `apps/desktop/webview/static/assets/app/layoutManager.js` (webview, medium, code-symbol-review, summary=yes)
- `apps/desktop/webview/static/assets/app/lifecycle.js` (webview, medium, code-symbol-review, summary=yes)
- `apps/desktop/webview/static/assets/app/refresh.js` (webview, medium, code-symbol-review, summary=yes)
- `apps/desktop/webview/static/assets/app/rowOpenActions.js` (webview, medium, code-symbol-review, summary=yes)
- `apps/desktop/webview/static/assets/app/tauriLifecycle.js` (webview, medium, code-symbol-review, summary=yes)
- `apps/desktop/webview/static/assets/app/topbar.js` (webview, medium, code-symbol-review, summary=yes)
- `apps/desktop/webview/static/assets/commandHistory.js` (webview, medium, code-symbol-review, summary=yes)
- `apps/desktop/webview/static/assets/commandHistory/formatters.js` (webview, medium, code-symbol-review, summary=yes)
- `apps/desktop/webview/static/assets/dom/filtering.js` (webview, medium, code-symbol-review, summary=yes)
- `apps/desktop/webview/static/assets/dom/query.js` (webview, medium, code-symbol-review, summary=yes)
- `apps/desktop/webview/static/assets/dom/status.js` (webview, medium, code-symbol-review, summary=yes)
- `apps/desktop/webview/static/assets/dom/table.js` (webview, medium, code-symbol-review, summary=yes)
- `apps/desktop/webview/static/assets/dom/text.js` (webview, medium, code-symbol-review, summary=yes)
- `apps/desktop/webview/static/assets/domHelpers.js` (webview, medium, code-symbol-review, summary=yes)
- `apps/desktop/webview/static/assets/formatters.js` (webview, medium, code-symbol-review, summary=yes)
- `apps/desktop/webview/static/assets/progressView.js` (webview, medium, code-symbol-review, summary=yes)
- `apps/desktop/webview/static/assets/styles.components.css` (webview, medium, ui/static-review, summary=yes)
- `apps/desktop/webview/static/assets/styles.controls.css` (webview, medium, ui/static-review, summary=yes)
- `apps/desktop/webview/static/assets/styles.css` (webview, medium, ui/static-review, summary=yes)
- `apps/desktop/webview/static/assets/styles.layout-manager.css` (webview, medium, ui/static-review, summary=yes)
- `apps/desktop/webview/static/assets/styles.layout.css` (webview, medium, ui/static-review, summary=yes)
- `apps/desktop/webview/static/assets/styles.pages.css` (webview, medium, ui/static-review, summary=yes)
- `apps/desktop/webview/static/assets/styles.queue.css` (webview, medium, ui/static-review, summary=yes)
- `apps/desktop/webview/static/assets/styles.theme.css` (webview, medium, ui/static-review, summary=yes)
- `apps/desktop/webview/static/assets/styles.tokens.css` (webview, medium, ui/static-review, summary=yes)
- `apps/desktop/webview/static/assets/tauriLifecycleBridge.js` (webview, medium, code-symbol-review, summary=yes)
- `apps/desktop/webview/static/index.html` (webview, medium, ui/static-review, summary=yes)
- `apps/desktop/webview/static/partials/app-shell-end.html` (webview, medium, ui/static-review, summary=yes)
- `apps/desktop/webview/static/partials/app-shell-start.html` (webview, medium, ui/static-review, summary=yes)

## Coverage Ledger

| File | Symbols reviewed | Coverage | Notes |
|---|---:|---|---|
| `apps/desktop/webview/static/assets/apiClient.js` | 5 | complete | Full source reviewed: `apiHeaders`, `parseResponse`, `fetchWithTimeout`, `apiGet`, `apiPost`, namespace/flat exports. No confirmed finding. |
| `apps/desktop/webview/static/assets/app.js` | 9 | partial | Reviewed bootstrap reads, close-readiness render/update, backend shutdown request guard, refresh request route list, shared UI preference sync/restore, beforeunload close warning, DOMContentLoaded command/event wiring. Did not review every dashboard/home/layout helper or every delegated page command. |
| `apps/desktop/webview/static/assets/app/closeReadiness.js` | 6 | partial | Grep/symbol scan only for close-readiness wrapper functions; full source not opened before time-box. |
| `apps/desktop/webview/static/assets/app/home.js` | 0 | summary-only | Summary checked; no full source review before time-box. |
| `apps/desktop/webview/static/assets/app/homeReadiness.js` | 0 | summary-only | Summary checked; no full source review before time-box. |
| `apps/desktop/webview/static/assets/app/layoutManager.js` | 0 | partial | Grep scan saw localStorage layout mutations only; full symbol review not completed. |
| `apps/desktop/webview/static/assets/app/lifecycle.js` | 0 | partial | Grep scan covered close-readiness/backend-shutdown/shortcut boundary references; full symbol review not completed. |
| `apps/desktop/webview/static/assets/app/refresh.js` | 0 | partial | Grep scan covered API route usage; full source not reviewed. |
| `apps/desktop/webview/static/assets/app/rowOpenActions.js` | 0 | summary-only | Summary checked; no full source review before time-box. |
| `apps/desktop/webview/static/assets/app/tauriLifecycle.js` | 0 | summary-only | Summary checked; no full source review before time-box. |
| `apps/desktop/webview/static/assets/app/topbar.js` | 0 | summary-only | Summary checked; no full source review before time-box. |
| `apps/desktop/webview/static/assets/commandHistory.js` | 0 | partial | Grep scan for command/mutation wording only; no full source review. |
| `apps/desktop/webview/static/assets/commandHistory/formatters.js` | 0 | partial | Grep scan for command/mutation wording only; no full source review. |
| `apps/desktop/webview/static/assets/dom/filtering.js` | 0 | summary-only | Summary checked; no full source review before time-box. |
| `apps/desktop/webview/static/assets/dom/query.js` | 0 | summary-only | Summary checked; no full source review before time-box. |
| `apps/desktop/webview/static/assets/dom/status.js` | 0 | summary-only | Summary checked; no full source review before time-box. |
| `apps/desktop/webview/static/assets/dom/table.js` | 0 | summary-only | Summary checked; no full source review before time-box. |
| `apps/desktop/webview/static/assets/dom/text.js` | 0 | summary-only | Summary checked; no full source review before time-box. |
| `apps/desktop/webview/static/assets/domHelpers.js` | 0 | partial | Grep scan saw transitional module cleanup/flat exports; full source not reviewed. |
| `apps/desktop/webview/static/assets/formatters.js` | 0 | summary-only | Summary checked; no full source review before time-box. |
| `apps/desktop/webview/static/assets/progressView.js` | 0 | partial | Grep scan covered publish/drain/close-readiness text and read-only boundary language; full source not reviewed. |
| `apps/desktop/webview/static/assets/styles.components.css` | 0 | summary-only | Summary checked; no CSS review before time-box. |
| `apps/desktop/webview/static/assets/styles.controls.css` | 0 | summary-only | Summary checked; no CSS review before time-box. |
| `apps/desktop/webview/static/assets/styles.css` | 0 | summary-only | Summary checked; no CSS review before time-box. |
| `apps/desktop/webview/static/assets/styles.layout-manager.css` | 0 | summary-only | Summary checked; no CSS review before time-box. |
| `apps/desktop/webview/static/assets/styles.layout.css` | 0 | summary-only | Summary checked; no CSS review before time-box. |
| `apps/desktop/webview/static/assets/styles.pages.css` | 0 | summary-only | Summary checked; no CSS review before time-box. |
| `apps/desktop/webview/static/assets/styles.queue.css` | 0 | summary-only | Summary checked; no CSS review before time-box. |
| `apps/desktop/webview/static/assets/styles.theme.css` | 0 | summary-only | Summary checked; no CSS review before time-box. |
| `apps/desktop/webview/static/assets/styles.tokens.css` | 0 | summary-only | Summary checked; no CSS review before time-box. |
| `apps/desktop/webview/static/assets/tauriLifecycleBridge.js` | 2 | complete | Full source reviewed: Tauri event API detection and backend lifecycle event bridge. No confirmed finding. |
| `apps/desktop/webview/static/index.html` | 2 | complete | Full source reviewed for bootstrap placeholder/Object.assign and script order. Placeholder replacement/Tauri bootstrap checked by existing references; no confirmed finding. |
| `apps/desktop/webview/static/partials/app-shell-end.html` | 1 | complete | Full source reviewed; shell closing tags only. No finding. |
| `apps/desktop/webview/static/partials/app-shell-start.html` | 3 | complete | Full source reviewed: nav shell, topbar actions, layout editor shell, emergency force-stop button markup. No confirmed finding. |

## Findings

| ID | Severity | File | Symbol | Problem | Suggested validation |
|---|---|---|---|---|---|
| None confirmed in completed coverage. | n/a | n/a | n/a | Time-boxed review found no evidence-backed defect in the fully reviewed files/regions. | Continue the remaining source review before treating W07 as clean. |

## Detailed Findings

No confirmed findings from the completed coverage.

Reviewed evidence:
- `apiClient.js:1-86` centralizes `fetch`, attaches the bearer token only from `window.MEDIA_PIPELINE_BOOTSTRAP`, uses `cache: "no-store"`, parses JSON/error payloads, and exposes `apiGet`/`apiPost`.
- `app.js:397-435` checks loaded close-readiness via `backendLifecycleState(lastCloseReadiness)` before posting `/api/backend/shutdown`, asks for user confirmation, and delegates actual lifecycle mutation to the backend.
- `app.js:701-733` refreshes backend-owned read routes and does not POST during normal refresh.
- `app.js:1055-1079` posts only shared UI preferences to `/api/ui-preferences`; inspected keys are constrained by `UI_PREFERENCE_KEY_RE` and current collection is local UI storage only.
- `app.js:1476-1690` wires command buttons but most mutation implementations are delegated to page-specific modules outside this worker scope.
- `tauriLifecycleBridge.js:1-37` listens to Tauri backend lifecycle events and redispatches a WebView event; no direct process, filesystem, publish, queue, settings, or rename mutation found.
- `index.html:11-16` uses the backend/Tauri bootstrap path. Repository references show the placeholder is intentionally rendered by Local API/Tauri checks, so the raw placeholder was not treated as a defect.
- `partials/app-shell-start.html:36-46` exposes topbar refresh/close-readiness and a hidden emergency Force Stop button; actual command behavior is delegated outside the partial.

## Test Coverage Gaps

- Not assessed for the incomplete files. I did not finish mapping assigned symbols to `tests/webview/*` or `tests/python/desktop/*`.
- From the completed shell/API coverage, useful follow-up validation would be targeted static/browser checks that:
  - verify `apiClient.js` remains the only assigned file that calls raw `fetch`;
  - verify `app.js` cannot POST `/api/backend/shutdown` when close-readiness is missing, stale, or unsafe;
  - verify shared UI preference sync cannot include arbitrary localStorage keys outside `mediapipeline-` / `mediapipeline.` prefixes;
  - verify topbar emergency Force Stop remains hidden until backend/page state intentionally reveals it.

## Boundary Risks

- `app.js` is a central shell wiring file and attaches listeners for launch, audit, rerun, pending drain, maintenance, rename, completed promotion, pipeline control, and diagnostics open buttons. I reviewed only the wiring, not the delegated implementations in page modules. Treat command boundary conclusions as incomplete until those owner modules are reviewed by their assigned workers.
- The completed API-client review did not find token logging or token persistence in assigned files. Token exposure still depends on backend/Tauri bootstrap rendering and CSP/security-header behavior outside this worker scope.
- `layoutManager.js` and shared UI preference sync intentionally mutate browser-local state. I did not complete a full review to prove those preferences cannot accidentally hide critical safety panels or desynchronize shell state across Tauri/WebView surfaces.

## Files With No Findings

No confirmed findings in the fully reviewed portions of:
- `apps/desktop/webview/static/assets/apiClient.js`
- `apps/desktop/webview/static/assets/app.js` reviewed regions only
- `apps/desktop/webview/static/assets/tauriLifecycleBridge.js`
- `apps/desktop/webview/static/index.html`
- `apps/desktop/webview/static/partials/app-shell-end.html`
- `apps/desktop/webview/static/partials/app-shell-start.html`

## Incomplete Coverage

Review was stopped by the user time-box before full source coverage. Exact incomplete groups:

- `apps/desktop/webview/static/assets/app.js`: dashboard/home helper group, render fan-out group after refresh, complete event-binding command boundary review, keyboard shortcut wrappers, layout wrappers.
- `apps/desktop/webview/static/assets/app/closeReadiness.js`: full wrapper source not opened; only symbol/grep coverage.
- `apps/desktop/webview/static/assets/app/home.js`: not reviewed beyond summary.
- `apps/desktop/webview/static/assets/app/homeReadiness.js`: not reviewed beyond summary.
- `apps/desktop/webview/static/assets/app/layoutManager.js`: not reviewed beyond grep hits for localStorage/layout mutations.
- `apps/desktop/webview/static/assets/app/lifecycle.js`: not reviewed beyond close-readiness/backend-shutdown/shortcut grep hits.
- `apps/desktop/webview/static/assets/app/refresh.js`: not reviewed beyond API-route grep hits.
- `apps/desktop/webview/static/assets/app/rowOpenActions.js`: not reviewed beyond summary.
- `apps/desktop/webview/static/assets/app/tauriLifecycle.js`: not reviewed beyond summary.
- `apps/desktop/webview/static/assets/app/topbar.js`: not reviewed beyond summary.
- `apps/desktop/webview/static/assets/commandHistory.js`: not reviewed beyond grep hits.
- `apps/desktop/webview/static/assets/commandHistory/formatters.js`: not reviewed beyond grep hits.
- `apps/desktop/webview/static/assets/dom/filtering.js`: not reviewed beyond summary.
- `apps/desktop/webview/static/assets/dom/query.js`: not reviewed beyond summary.
- `apps/desktop/webview/static/assets/dom/status.js`: not reviewed beyond summary.
- `apps/desktop/webview/static/assets/dom/table.js`: not reviewed beyond summary.
- `apps/desktop/webview/static/assets/dom/text.js`: not reviewed beyond summary.
- `apps/desktop/webview/static/assets/domHelpers.js`: not reviewed beyond grep hits.
- `apps/desktop/webview/static/assets/formatters.js`: not reviewed beyond summary.
- `apps/desktop/webview/static/assets/progressView.js`: not reviewed beyond grep hits.
- CSS files `styles.components.css`, `styles.controls.css`, `styles.css`, `styles.layout-manager.css`, `styles.layout.css`, `styles.pages.css`, `styles.queue.css`, `styles.theme.css`, and `styles.tokens.css`: summaries checked only; no source-level CSS/layout/accessibility review completed.
