# Code Map

This map focuses on ownership, lifecycle, and authority boundaries. Line references are from the reviewed worktree on 2026-06-16.

## Tauri Shell

`apps/desktop/tauri/src-tauri/src/lib.rs`

- `lib.rs:59-64`: setup acquires the single-instance guard before backend start.
- `lib.rs:71-82`: starts the backend, captures debug auth when enabled, injects the token initialization script, validates the loopback URL, manages backend state, and starts the lifecycle monitor.
- `lib.rs:83-88`: builds the main WebView after backend setup.
- `lib.rs:105-128`: close-request handling denies unsafe close, performs safe backend shutdown when allowed, and supports confirmed forced shutdown.
- `lib.rs:147-156`: injects `window.MEDIA_PIPELINE_TAURI_BOOTSTRAP` and renders startup warnings when WebView asset validation reports drift.
- `lib.rs:260-310`: tests codify that only bootstrap-security failures are fatal; other WebView validation failures remain startup warnings.

`apps/desktop/tauri/src-tauri/src/backend_process.rs`

- `backend_process.rs:111-148`: backend shutdown first posts `/api/backend/shutdown`; safe shutdown does not kill active work, forced shutdown eventually terminates the process tree.
- `backend_process.rs:168-190`: close-request decision is delegated to backend close-readiness.
- `backend_process.rs:196-212`: backend is launched as bundled Python with `-m mediapipeline.desktop.local_api_main`, `--app-root`, `--shell-surface tauri`, and startup progress emission.
- `backend_process.rs:240-263`: bootstrap is parsed and backend health/contract validation are fatal startup checks.
- `backend_process.rs:264-281`: WebView validation failure is fatal only if `web_ui_validation_error_is_fatal` says it is; otherwise the shell opens with a warning.
- `backend_process.rs:301-306`: fatal WebView failures are limited to token leak, raw bootstrap placeholder, and missing bootstrap assignment.
- `backend_process.rs:418-456`: forced shutdown terminates the backend process tree on Windows.
- `backend_process.rs:475-512`: safe shutdown omits `force_active_work_shutdown`; forced shutdown includes strict JSON `true`.
- `backend_process.rs:515-530`: startup output redacts token-like fields.

`apps/desktop/tauri/src-tauri/src/backend_contract.rs`

- `backend_contract.rs:18-90`: validates required static index fragments, including bootstrap and lifecycle/diagnostic surfaces.
- `backend_contract.rs:168-176`: token leak and raw placeholder detection.
- `backend_contract.rs:179-222`: validates application JavaScript fragments for backend shutdown and close-readiness guardrails.
- `backend_contract.rs:1180-1192`: validates pending diagnostics route and allowlist boundary fragments.
- `backend_contract.rs:1194-1263`: validates pending-drain confidence and evidence fragments.

`apps/desktop/tauri/src-tauri/src/single_instance_guard.rs`

- `single_instance_guard.rs:18-35`: Windows mutex guard using `Local\MediaPipelineRemuxEncodeAIO_TauriShell`.
- `single_instance_guard.rs:41-44`: non-Windows guard is currently a no-op.

`apps/desktop/tauri/src-tauri/src/backend_lifecycle_monitor.rs`

- `backend_lifecycle_monitor.rs:23-79`: background monitor emits `mediapipeline://backend-lifecycle` after backend exit or repeated health failures.

`apps/desktop/tauri/src-tauri/src/close_readiness.rs`

- `close_readiness.rs:37-56`: tokened GET to `/api/backend/close-readiness`, requiring schema `desktop_close_readiness.v1`.
- `close_readiness.rs:59-90`: warning details include close-readiness warnings and watcher lines.

`apps/desktop/tauri/src-tauri/src/dialogs.rs`

- `dialogs.rs:29-50`: Windows warning dialog uses OK/Cancel and default-cancel behavior; non-Windows logs and returns false.

`apps/desktop/tauri/src-tauri/src/debug_webview.rs`

- `debug_webview.rs:1-8`: debug-only module.
- `debug_webview.rs:8-40`: writes a debug auth capture only when `MEDIA_PIPELINE_TAURI_TEST_TOKEN_CAPTURE_FILE` is set.
- `debug_webview.rs:43-72`: restricts debug capture to system temp and `.backend_auth.json`.
- `debug_webview.rs:79-134`, `debug_webview.rs:220-257`: debug automation can fill fields, override `window.confirm`, and click launch under test environment flags.
- `debug_webview.rs:136-137`: release build is no-op.

`apps/desktop/tauri/src-tauri/capabilities/default.json`

- Permissions are limited to `core:default`; no Tauri filesystem, shell, or dialog plugin permissions are granted to WebView code.

`apps/desktop/tauri/src-tauri/tauri.conf.json`

- CSP allows `'unsafe-inline'` and `'unsafe-eval'`.
- Bundle targets are set to `all`.

## Local API

`src/mediapipeline/desktop/api/server.py`

- `server.py:28-34`: health/static are public; read and command APIs require a per-run token unless dev no-auth is enabled.
- `server.py:58-59`: token is generated with `secrets.token_urlsafe(24)`.
- `server.py:91-120`: API server lifecycle starts and stops the HTTP server, watchers, and background scheduling state.
- `server.py:151-163`: command journal refreshes state DB roots.
- `server.py:165-168`: API payload validation delegates to boundary validation.

`src/mediapipeline/desktop/api/handler.py`

- `handler.py:39-60`: GET host check; public static/health; token required for other GET routes.
- `handler.py:77-113`: POST host/origin/auth checks, route lookup, strict JSON object body, payload validation, optional command journal validation, and backend dispatch.
- `handler.py:139-154`: responses use strict JSON and journal successful commands unless suppressed.

`src/mediapipeline/desktop/api/http_helpers.py`

- `http_helpers.py:30-40`: CSP mirrors unsafe inline/eval.
- `http_helpers.py:96-111`: auth accepts token headers only, not query string.
- `http_helpers.py:171-209`: origin allowlist permits loopback same port, `tauri://localhost`, and empty Origin.
- `http_helpers.py:212-244`: JSON body must have the right content type, bounded size, and be an object.
- `http_helpers.py:322-330`: static asset path resolution blocks traversal and backslashes.

`src/mediapipeline/desktop/api/static_files_policy.py`

- `static_files_policy.py:23-43`: normal WebView bootstrap may include token; Tauri bootstrap uses initialization-script token source.

`src/mediapipeline/desktop/api/contract_payload.py`

- Defines the Local API contract payload, route exposure, network lifecycle contracts, mutation/evidence classifications, and no-route repair/reconcile policy.
- `contract_payload.py:36-41`: network lifecycle source mutation/delete/rename are forbidden; backend owns path authority.
- `contract_payload.py:51-120`: coordinator start requires backend-side preconditions and forbids frontend-only trust.
- `contract_payload.py:294-365`: repair/reconcile are design-only and have no mutation routes.
- `contract_payload.py:581-614`: payload exposes lifecycle and repair/reconcile summaries.

`src/mediapipeline/desktop/api/contract_command.py`

- Describes command route effects, confirmation requirements, journal requirements, and frontend exposure.
- `contract_command.py:120-158`: open routes accept backend row keys and allowlisted targets, not arbitrary frontend paths.
- `contract_command.py:172-180`: final-library promotion is backend filesystem mutation.
- `contract_command.py:420-459`: rename browse/apply are backend-mediated.
- `contract_command.py:473-519`: settings save is config-write with backup/atomic save/reload.
- `contract_command.py:650-708`: network dry-runs are effect-none diagnostics.
- `contract_command.py:766-819`: network start/stop are confirmed backend-lifecycle routes.
- `contract_command.py:912-918`: backend shutdown is a backend-lifecycle route.

`src/mediapipeline/contracts/api_commands.py`

- Strict Pydantic command payload models map command routes to payload schemas.
- Settings save, rename apply, network start/stop, backend shutdown, and final-library promotion require strict confirmation booleans.

## WebView

`apps/desktop/webview/static/index.html`

- `index.html:11-16`: merges backend bootstrap and Tauri initialization bootstrap into `window.MEDIA_PIPELINE_BOOTSTRAP`.

`apps/desktop/webview/static/assets/apiClient.js`

- `apiClient.js:1-10`: reads bootstrap token.
- `apiClient.js:67-84`: `apiGet` and `apiPost` send tokened fetches with JSON/no-store.
- `apiClient.js:91-98`: exposes API helpers globally.

`apps/desktop/webview/static/assets/app.js`

- `app.js:399-426`: backend shutdown button is disabled unless close-readiness is safe; confirmation posts `/api/backend/shutdown` without force.
- `app.js:1089`: UI preferences post to `/api/ui-preferences`.
- `app.js:1198-1217`: storage patching is scoped to UI preference sync.

`apps/desktop/webview/static/assets/app/lifecycle.js`

- Renders backend lifecycle status and exposes backend shutdown only when close-readiness allows it.

`apps/desktop/webview/static/assets/app/closeReadiness.js`

- `closeReadiness.js:18-30`: fallback denies shutdown until close-readiness is loaded and safe.

`apps/desktop/webview/static/assets/tauriLifecycleBridge.js`

- Listens to Tauri lifecycle events and dispatches browser events. It does not call Tauri `invoke`, filesystem, shell, or dialog APIs.

`apps/desktop/webview/static/assets/networkView.js`

- `networkView.js:1737-1762`: network lifecycle confirmation text says backend owns checks, journaling, and preconditions.
- `networkView.js:1797-1850`: lifecycle commands take routes from the contract, confirm non-dry-run operations, and post strict confirmation intent to the backend.
- `networkView.js:1325-1400`: renders lifecycle command result lines, including `state_before` and `state_after`.
- `networkView.js:1618-1699`: join-cluster flow posts join blob to backend with `confirm_import:true`; command journal is suppressed for secret transfer by contract.

`apps/desktop/webview/static/assets/pendingPublishView.drain.js`

- `pendingPublishView.drain.js:93-99`: pending-drain authority is `/api/pipeline/start` with `mode: drain_pending_pushes`; WebView selection and filters do not publish files.
- `pendingPublishView.drain.js:151-169`: backend drain scope preview and mutation guardrails are rendered as evidence.

`apps/desktop/webview/static/assets/renameView.js`

- `renameView.js:1361`: rename preview posts `/api/rename/preview`.
- `renameView.js:1640-1674`: rename apply requires a fresh preview and confirmation, then posts `/api/rename/apply` with backend-owned policy inputs omitted or overridden by backend command code.

`apps/desktop/webview/static/assets/settingsView.js`

- `settingsView.js:747`, `settingsView.js:1430`: settings preview posts backend patch preview requests.
- `settingsView.js:819`, `settingsView.js:1500-1629`: settings save posts `/api/settings/save-patch` with `confirm_save:true` after preview and confirmation.

## Network Lifecycle Backend

`src/mediapipeline/core/network/lifecycle_facade.py`

- `lifecycle_facade.py:216-356`: preconditions cover role, provider availability, duplicate start/stop, active-work guard, coordinator bind/token, worker URL/token/path mapping, and pending done handling.
- `lifecycle_facade.py:489-603`: dry-run payload declares schema, `dry_run_only`, `effect: none`, protected paths, and active-work evidence.
- `lifecycle_facade.py:652-670`: confirmed start/stop require exact confirmation booleans.
- `lifecycle_facade.py:712-729`: strict command journal failure blocks provider calls.
- `lifecycle_facade.py:754-825`: confirmed result is built and journaled; state is committed only after journaling, with special cleanup for failure paths.

`src/mediapipeline/desktop/application/network_lifecycle_provider.py`

- `network_lifecycle_provider.py:575-615`: coordinator start loads queue/failure records, starts dispatcher, refreshes queue, and may start local worker.
- `network_lifecycle_provider.py:617-655`: coordinator stop preserves active work by setting drain/stop state and leaving runtime entries when needed.
- `network_lifecycle_provider.py:701-736`: worker start attaches runtime before polling.
- `network_lifecycle_provider.py:738-767`: worker stop preserves an active job/process and leaves runtime state when active.
- `network_lifecycle_provider.py:877-940`: worker claim processing launches backend process work through application service with backend-controlled config.

## Backend-Owned Media Mutation Routes

- Queue priority and strategy writes are backend-owned in `src/mediapipeline/core/api/commands_queue_priority.py` and `commands_queue_strategy.py`.
- Queue source path validation is backend-owned in `src/mediapipeline/desktop/api/queue_source_path_policy.py`.
- Rename preview/apply strips frontend-owned policy fields and injects backend policy in `src/mediapipeline/core/api/commands_rename.py`.
- Settings preview/save and reload are backend-owned in `src/mediapipeline/core/api/commands_settings.py`.
- Pipeline launch and backend shutdown are backend-owned in `src/mediapipeline/core/api/commands_process.py`.
- Pending/completed/final-library open/promotion commands are backend-owned in `src/mediapipeline/core/api/commands_files.py` and `commands_final_library.py`.

## Tests And Validation Anchors

- `tests/python/desktop/test_tauri_shell_scaffold.py`: Tauri launch, backend validation, lifecycle, close readiness, single-instance, debug harness, and shutdown scaffolding.
- `tests/python/desktop/test_application_facade_local_api.py`: contract auth, route effect metadata, network lifecycle summary, repair/reconcile no-route policy, and UI contract text.
- `tests/python/desktop/test_api_command_contracts.py`: strict payloads and command ownership matrix.
- `tests/python/desktop/test_network_lifecycle_fixes.py`: active work preservation, dry-run evidence, journal failure state, and active coordinator/worker stop behavior.
- `tests/webview/test_webview_browser_lifecycle_smoke.py`: shutdown button gating and no media mutation on lifecycle UI flows.
- `tests/webview/test_webview_network_read_only_boundary.py`: WebView network page read-only boundary and disabled future controls.
- `tests/webview/test_webview_browser_network_smoke.py`: browser-stubbed network route and evidence smoke coverage.
