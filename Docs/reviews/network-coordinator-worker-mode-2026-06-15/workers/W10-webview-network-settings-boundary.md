# Worker Review: W10 - WebView Network Settings Boundary

## Scope

Review-only audit of the WebView Network page, Saved Distributed Mode Settings builder, Network partial markup, related API-client usage, and CSS that could hide safety/confirmation text.

Assigned source scope covered:

- `apps/desktop/webview/static/assets/networkView.js`
- `apps/desktop/webview/static/assets/settingsView.builders.network.js`
- `apps/desktop/webview/static/partials/page-network.html`
- Related settings/API-client usage in `apiClient.js`, `settingsView.js`, `settingsMetadata.js`, and `app.js`
- Relevant Network layout CSS in `styles.pages.css`, plus targeted disabled/warning searches across layout/component/control CSS

No source, generated summaries, runtime state, config, media, queue state, manifests, or aggregate review files were edited.

## Required Reads Completed

Read required repo docs:

- `AGENTS.md`
- `docs/CURRENT_PROJECT_STATE.md`
- `docs/OPEN_WORK_CHECKLIST.md`
- `docs/generated/PROJECT_INDEX.md`
- `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`
- `docs/architecture/NETWORK_LIFECYCLE_COMMAND_CONTRACT.md`
- `docs/architecture/NETWORK_WORKER_HARDENING_PLAN.md`
- `docs/inventories/API_ROUTE_INVENTORY.md`
- `docs/inventories/COMMAND_OWNERSHIP_MATRIX.md`
- `docs/reviews/network-coordinator-worker-mode-2026-06-15/PROMPT_PACK.md`

Read generated summaries before source for every assigned source/test file, including `networkView.js`, `settingsView.builders.network.js`, `page-network.html`, `apiClient.js`, relevant CSS, assigned tests, and the smoke wrapper. Most summaries were unparsed, so full source was opened only for the assigned scope and related route/settings code needed to answer the review questions.

## Coverage Ledger

| File | Coverage | Notes |
|---|---|---|
| `apps/desktop/webview/static/assets/networkView.js` | Full targeted review | Checked route discovery, lifecycle controls, confirmation flow, join/discovery/test-connection, settings handoff, drift banners, worker filters, accessible-library display, and future-control disabling. |
| `apps/desktop/webview/static/assets/settingsView.builders.network.js` | Full targeted review | Checked field set, secret exclusion, worker URL validation, path-map editor, path-map row test, role setup dialog, and patch staging. |
| `apps/desktop/webview/static/partials/page-network.html` | Full targeted review | Checked lifecycle buttons, future disabled controls, join/import/discovery controls, confirmation dialog, settings controls, hidden path-map JSON, and boundary text. |
| `apps/desktop/webview/static/assets/apiClient.js` | Full targeted review | Checked token header usage and generic POST/GET behavior. |
| `apps/desktop/webview/static/assets/settingsView.js` | Targeted related review | Checked `previewSettingsPatch` and `saveSettingsPatch` delegate to `/api/settings/preview-patch` and `/api/settings/save-patch` with `confirm_save: true`. |
| `apps/desktop/webview/static/assets/settingsMetadata.js` | Targeted related review | Checked Network builder field list excludes `CoordinatorAuthToken` and `WorkerAuthToken`. |
| `apps/desktop/webview/static/assets/app.js` | Targeted related review | Checked shared UI preference sync after browser smoke failure. |
| `apps/desktop/webview/static/assets/styles.pages.css` | Targeted review | Checked Network banner, dialogs, future controls, path-map editor, join blob textareas, and confirmation detail overflow. |
| `styles.css`, `styles.components.css`, `styles.controls.css`, `styles.layout.css` | Targeted search | Checked disabled, `prose-block`, `visually-hidden`, textarea, dialog, and warning-related selectors. |
| `tests/webview/test_webview_network_read_only_boundary.py` | Full targeted review | Static boundary tests reviewed. |
| `tests/webview/test_webview_browser_network_smoke.py` | Full targeted review | Browser smoke reviewed and run. |
| `tests/python/desktop/test_application_facade_network.py` | Targeted review and run | DTO/read evidence coverage reviewed. |
| `tests/python/desktop/test_api_command_contracts.py` | Targeted review and run | Network payload strictness and confirmation coverage reviewed. |
| `ops/scripts/smoke/Test-WebViewBrowserNetworkSmoke.ps1` | Summary plus execution | Wrapper delegates to browser-backed smoke and failed for the same POST allowlist issue. |

Validation run:

- Passed: `.\apps\desktop\runtime\Python\python.exe -m pytest tests\webview\test_webview_network_read_only_boundary.py tests\python\desktop\test_application_facade_network.py tests\python\desktop\test_api_command_contracts.py -q`
  - Result: `35 passed, 246 subtests passed in 4.98s`
- Failed: `.\apps\desktop\runtime\Python\python.exe -m pytest tests\webview\test_webview_browser_network_smoke.py -q`
  - Result: failed because the smoke observed unexpected `POST /api/ui-preferences` with `storage.mediapipeline-network-tab`.
- Failed: `powershell -NoProfile -ExecutionPolicy Bypass -File .\ops\scripts\smoke\Test-WebViewBrowserNetworkSmoke.ps1`
  - Result: same underlying browser smoke failure.

## Findings

| id | severity | file | line | symbol | summary |
|---|---|---|---|---|---|
| W10-001 | P2 | `apps/desktop/webview/static/assets/settingsView.builders.network.js` | 418 | `testPathMapRow` | Path-map row Test displays backend accessibility evidence even though the backend route is the generic worker test-connection route and cannot validate the row's resolved sample path. |
| W10-002 | P2 | `tests/webview/test_webview_browser_network_smoke.py` | 496 | `allowedPostTargets` | Browser Network smoke rejects the expected `/api/ui-preferences` write produced by shared UI preference sync, so the assigned browser validation currently fails before completing its no-mutation checks. |

## Detailed Findings

### W10-001

- `id`: W10-001
- `severity`: P2
- `file`: `apps/desktop/webview/static/assets/settingsView.builders.network.js`; related caller in `apps/desktop/webview/static/assets/networkView.js`
- `line`: `settingsView.builders.network.js:418`; related `networkView.js:1810`
- `symbol`: `testPathMapRow`, `pathLayerStatus`, `runNetworkWorkerTestConnection`
- `problem`: The WorkerSourcePathMap row Test computes `Sample:` and `Resolved:` locally, then calls `runNetworkWorkerTestConnection({ render: false })`. That function posts `{}` to `/api/network/worker/test-connection`, whose contract accepts only `timeout_seconds` and checks configured source/output paths, not the row's resolved sample path. The UI can therefore display `Resolved: <row target>` beside `Backend path preflight: accessible yes` even when that specific row target was never backend-validated.
- `impact`: An operator can mistake the row-specific local rewrite preview for backend proof that a manual path-map entry will make claimed files readable on the worker. In the failure mode described by the hardening plan, bad path maps cause fast worker failures and coordinator redispatch loops. This does not directly mutate media, but it can mislead distributed-work setup and retry decisions.
- `evidence`: `settingsView.builders.network.js:388-407` resolves the sample locally; `settingsView.builders.network.js:430-441` appends the generic path-layer status; `networkView.js:1810-1833` posts `{}` to the discovered test-connection route; `contract_command.py:710-721` defines the route with `request_keys: ["timeout_seconds"]`; `test_api_command_contracts.py:157-162` rejects adding `path` to this route; `tests/webview/test_webview_browser_network_smoke.py:398-411` mocks the row test and asserts `accessible yes` without asserting any row/sample payload reaches the backend.
- `suggested fix direction`: Either weaken the UI text to explicitly say "local rewrite preview plus generic saved-config path preflight" or add a backend-owned no-mutation path-map preview/test route that accepts `{from_prefix, to_prefix, sample_path}` and returns row-specific parser/path-access evidence. The second option should not save settings, claim work, scan queue, launch processing, or touch media.
- `suggested validation/tests`: Add a browser/static test that fails if the row Test claims row-specific backend accessibility without a row-specific backend result. If a backend route is added, cover strict payload validation, row-specific negative cases, UNC/case handling, and no-mutation evidence.

### W10-002

- `id`: W10-002
- `severity`: P2
- `file`: `tests/webview/test_webview_browser_network_smoke.py`; related source in `apps/desktop/webview/static/assets/networkView.js` and `apps/desktop/webview/static/assets/app.js`
- `line`: `test_webview_browser_network_smoke.py:496`
- `symbol`: `allowedPostTargets`, `activateNetworkTab`, `persistSharedUiPreferencesNow`
- `problem`: The browser-backed Network smoke allows only diagnostics/network POSTs, but clicking Network tabs now writes the app-owned `mediapipeline-network-tab` key through global `/api/ui-preferences` sync. The current smoke therefore fails on a bounded UI-state write even though it is not settings persistence, lifecycle mutation, queue mutation, or media policy.
- `impact`: The assigned browser smoke and `Test-WebViewBrowserNetworkSmoke.ps1` wrapper currently fail, reducing confidence in the page-level no-mutation and copy/join/discovery validation. Future agents may skip the browser smoke or misclassify the UI preference route as a Network boundary violation.
- `evidence`: `networkView.js:424-440` persists the selected Network tab to `localStorage`; `app.js:1022-1089` mirrors app-owned `mediapipeline-*` UI keys to `/api/ui-preferences`; the failed run observed `POST /api/ui-preferences` with `storage: {"mediapipeline-network-tab":"coordinator"}`; `test_webview_browser_network_smoke.py:496-503` omits `/api/ui-preferences` from the allowlist; `test_webview_browser_network_smoke.py:1044-1050` expects exactly three Network POSTs.
- `suggested fix direction`: Update the smoke to allow exactly the known UI preference sync POST, constrained to `source_surface: "webview"` and `storage` keys limited to `mediapipeline-network-tab`, while still rejecting all other unexpected POSTs. Alternatively, explicitly disable shared UI preference sync inside the smoke runner before tab clicks.
- `suggested validation/tests`: Re-run `tests/webview/test_webview_browser_network_smoke.py -q` and `ops/scripts/smoke/Test-WebViewBrowserNetworkSmoke.ps1`. Keep assertions that confirmed lifecycle routes are not executed and that settings save is not exercised by the smoke.

## Test Coverage Gaps

- Path-map row Test coverage is too shallow. Static coverage only asserts that the source contains `await runner({ render: false })`, and browser coverage mocks `runNetworkWorkerTestConnection` without checking whether the row's `from/to/sample` data was backend-validated.
- Browser smoke POST allowlist is stale for shared UI preference sync. It should either allow the exact `/api/ui-preferences` tab-persistence payload or deliberately disable shared UI preference sync inside the runner.
- No live LAN, real coordinator, real worker, or real mDNS validation was performed in this W10 review. That is intentional per prompt restrictions.

## Boundary Risks

- Settings preview/save delegation is correct in the reviewed code: Network buttons call `window.mediaPipelineSettingsView.previewSettingsPatch` and `saveSettingsPatch`, which use `/api/settings/preview-patch` and `/api/settings/save-patch` with `confirm_save: true`.
- Auth-token settings are not part of `networkSettingsBuilderFields`, Network setting rows filter `*AuthToken*`, and rendered token posture uses hidden/fingerprint language rather than clear text.
- Lifecycle controls are discovered from `/api/contract`, use backend route metadata, and confirmed commands add `confirm_start` or `confirm_stop` only after the confirmation dialog.
- Future Drain, Disable New Work, Pause, Abort Current, Reclaim Job, and Quarantine Worker buttons are disabled in HTML and re-disabled in JS.
- Join blob creation and worker import intentionally handle a secret. The reviewed WebView renders/copies the join blob only in that intended setup flow, and result summaries show token fingerprints rather than token values.
- The highest operator-confusion risk found is W10-001: the path-map row Test blends row-specific local rewrite text with generic backend path-layer evidence.

## Files With No Findings

- `apps/desktop/webview/static/partials/page-network.html`: no direct mutation controls outside the backend-owned route surfaces were found; future controls are disabled.
- `apps/desktop/webview/static/assets/apiClient.js`: no direct config persistence or Network-specific mutation synthesis found.
- `apps/desktop/webview/static/assets/settingsView.js`: Network settings save/preview delegates through backend Settings routes and uses strict save confirmation.
- `apps/desktop/webview/static/assets/settingsMetadata.js`: Network builder fields exclude coordinator/worker auth-token keys.
- `apps/desktop/webview/static/assets/styles.pages.css`: reviewed Network banner/dialog/path-map/join/future-control CSS did not hide safety warnings or confirmation text; overflow is scrollable where content can be long.
- `tests/webview/test_webview_network_read_only_boundary.py`: no direct finding, but it does not catch W10-001.
- `tests/python/desktop/test_application_facade_network.py`: no WebView boundary finding.
- `tests/python/desktop/test_api_command_contracts.py`: no finding; its strict rejection of extra `path` fields on test-connection is part of W10-001 evidence.

## Incomplete Coverage

- Did not click controls against a live operator backend.
- Did not run live coordinator/worker lifecycle, claim, done, retry, reclaim, release, abort, quarantine, publish, drain, rename, or media processing flows.
- Did not run real LAN discovery or two-machine worker setup.
- Did not inspect every CSS rule in full; CSS review was targeted to Network warning, dialog, disabled, hidden, textarea, and overflow surfaces.
- Did not regenerate generated summaries because the prompt explicitly forbids editing generated summaries in this review-only worker task.

## Suggested Follow-Up Prompts

- "Patch the Network path-map row Test so it either clearly labels the result as local-only plus generic backend preflight, or adds a backend-owned no-mutation row-specific path-map validation route with tests."
- "Update the WebView browser Network smoke to allow only the exact `/api/ui-preferences` tab-persistence payload, then rerun the Python smoke and `Test-WebViewBrowserNetworkSmoke.ps1`."
- "Run a live two-machine worker setup validation for join blob, discovery, path-map/accessibility evidence, and drift banner behavior after W10-001 is fixed."
