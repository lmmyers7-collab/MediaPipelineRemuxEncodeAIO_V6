# Home operator workflow review

Date: 2026-07-09  
Reviewer role: Home-tab senior reviewer  
Method: read-only code and test review; no pipeline starts or mutation routes invoked.

## Executive assessment

The Home workflow has a strong intended boundary: it renders backend-owned state, navigates to owning tabs, and delegates process controls to the Launch/topbar surface. The Local API owns close-readiness, process control, command journaling, duplicate-command locking, and the actual process cleanup. The backend close-readiness implementation is appropriately fail-closed for unavailable state and related-process inspection failures.

Three findings need remediation before relying on Home as an authoritative close/stop surface. Two are P1: a failed refresh can retain and reuse a previous safe close-readiness result, and Emergency Force Stop has only a frontend confirmation even though the backend immediately executes the kill action. The P2 malformed-payload issue can independently display `"false"` as safe. No source media movement, filesystem mutation, or media-policy decision was found in Home rendering itself.

## Scope and evidence map

Reviewed required guidance: `AGENTS.md`, `docs/DOCS_INDEX.md`, `docs/CURRENT_PROJECT_STATE.md`, `docs/architecture/ARCHITECTURE.md`, `docs/architecture/MODULE_MAP.md`, `docs/inventories/API_ROUTE_INVENTORY.md`, `docs/testing/VALIDATION_LADDER_RUNBOOK.md`, and `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`. Relevant generated summaries were read before their sources; most WebView summaries are presently marked `Purpose: (unparsed)`, so source was the operative evidence.

| Area | Evidence reviewed | Result |
| --- | --- | --- |
| Home markup and state rendering | `page-home.html`; `app.js`; `app/home.js`; `app/homeReadiness.js`; `app/topbar.js`; `app/refresh.js`; `app/lifecycle.js`; `app/closeReadiness.js`; `progressView.js` | Home is primarily a read-only dashboard. Its quick controls navigate; its global chrome exposes the emergency control owned by Launch. |
| Cross-page context | Every `crossPageContextView*.js` file and load order in `index.html` | The conflict/settings/sample/worksheet/record/runbook children have no direct route calls. The sample-validation child alone posts preview/append through the shared API client. |
| Read routes polled by Home | `GET /api/health`, `/snapshot`, `/backend/close-readiness`, `/telemetry`, `/diagnostics`, diagnostics tail/state-summary, `/commands`, `/rerun/results`, `/metrics`, `/queue`, `/completed`, `/failures`, `/failures/artifacts`, audit routes, `/pending-publish`, `/schedule`, `/watch-folders/status`, `/settings/workspace`, library routes, `/network/workers`, `/sample-validation`, `/contract` | All are issued through `apiGet` during `refreshAllNow`; snapshot is the only required request. |
| Command routes reachable from Home context | `POST /api/pipeline/control` (global topbar/Launch), `/api/backend/shutdown` (Diagnostics lifecycle), `/api/diagnostics/open` (Home runtime-file links), `/api/sample-validation/preview`, `/api/sample-validation/append`, `/api/ui-preferences` | Route registry and handler dispatch preserve backend authority. Sample validation is an evidence-log workflow, not a media workflow. |
| Backend route/contract/service path | `routes_read.py`, `read_payloads_status.py`, `handler.py`, `server.py`, `commands_process.py`, `control_facade.py`, `guard_facade.py`, `status/facade.py`, `status/service.py`, `api_commands.py`, command-journal files | `GET /api/backend/close-readiness` derives policy from backend process/promotion/scan/network/progress evidence. `POST /api/pipeline/control` has a backend lock and journal path. |
| Tests | Home live-state/browser and lifecycle smokes; WebView mutation-boundary/API-client tests; application-facade close-readiness/lifecycle/process-command/static tests; command-contract tests | Good coverage of normal safe/blocked lifecycle states, but the failures below are not exercised end-to-end. |

`git status --short` was run before review. The worktree contains extensive pre-existing modifications and untracked files across source, tests, inventories, generated summaries, and release packets. None are attributed to this review.

## End-to-end workflow traces

### 1. Initial snapshot and refresh

1. `app.js:856-884` serializes refreshes; automatic refreshes do not queue behind a running refresh, while an operator refresh queues one follow-up.
2. `app.js:890-930` starts a responsive stdout-tail read and fan-outs the dashboard reads with `Promise.allSettled`; `/api/snapshot` is marked required.
3. `apiClient.js:425-438` rejects invalid JSON and non-2xx responses. `apiClient.js:506-535` applies loopback/API-path controls, no-store caching, token headers, and GET timeouts.
4. `read_payloads_status.py:23-27` obtains the snapshot; `status/facade.py:78-115` turns backend status, ActiveJobs-derived worker progress, stale evidence, events, and current-work information into the DTO.
5. `app.js:961-1185` renders successful payloads, aggregates failures, builds Home/cross-page contexts, and finishes refresh health. Finding HOME-001 covers the unsafe fallback on failed critical reads.

### 2. Active-job and process-state display

`status/service.py:63-64` reads the ActiveJobs summary for the snapshot; `status/facade.py:81-115` supplies `pipeline_state`, `worker_progress`, current work, progress bars, and warnings. `app.js:104-149` renders this state in the topbar, metrics, progress, live-run strip, events, reports, and control readiness. `app.js:791-805` feeds Home live-run renderers from the snapshot, diagnostics, close readiness, and stdout tail. Home’s Runtime Files links use backend allowlisted diagnostic targets only (`page-home.html:246-260`).

### 3. Refresh-health and close-readiness display

`app/refresh.js:150-196` disables both refresh buttons while reads are in flight and labels all-settled failures by requiredness. `read_payloads_status.py:71-75` calls `facade.get_close_readiness`; `guard_facade.py:56-107` checks related bundle processes, promotion, source scan, network rerun, schedule watcher, pipeline progress, and audit progress before producing the DTO. `app.js:350-378` renders the global close chip, and `app/home.js:73-110` renders Home readiness. The backend is fail-closed; the frontend’s refresh fallback and boolean coercion are not (HOME-001 and HOME-003).

### 4. Emergency Force Stop

Force Stop is intentionally not a Home-panel control: `page-home.html` has no `data-control-action`, asserted by `test_application_facade_web_static.py:1622-1638`. It is a global emergency topbar control (`app-shell-start.html:46`) and a Launch control (`page-launch.html:182-184`), visible only for active or backend-stuck work (`launch/commandButtons.js:149-230`).

On click, `launchView.js:904-967` presents a confirmation and posts `{ action: "kill" }` to `/api/pipeline/control`. The HTTP handler authorizes, validates, dispatches, and journals responses (`handler.py:80-163`). The backend control facade validates the action, acquires a nonblocking process-control lock, kills related pipeline/audit/CSV-rerun processes, and resets stuck progress (`control_facade.py:108-183`). Finding HOME-002 is that confirmation is not also a backend contract requirement.

### 5. Cross-page summary cards and guidance

`app.js:1133-1147` passes only already-loaded backend payloads to `renderCrossPageContext`; `crossPageContextView.js:647-670` renders read-only comparisons, conflicts, sample correlation, and handoffs. Its summary explicitly states that the panel is derived from loaded backend payloads and cannot mutate media (`crossPageContextView.js:550-582`). The sample-validation child can preview or append a validation-log record after its UI confirmation (`crossPageContextView.sampleValidation.js:630-680`); the API contract limits append to `State\\Validation` evidence and expressly excludes media/pipeline mutation (`contract_command.py:1036-1055`).

### 6. Unavailable, stale, malformed, partial, and active-work states

Invalid JSON and transport failure are surfaced by `apiClient.js:380-503`; partial route failure is collected into refresh health. Backend close-readiness blocks unknown runtime and inspection failures, verified by `test_application_facade_close_readiness.py:20-80` and `:518-578`. Active/stuck control enablement is derived in `launch/controllerState.js:8-63` and `launch/commandButtons.js:194-230`. The reviewed gaps are specifically (a) reuse of last successful state after a failed policy read and (b) lack of runtime response-shape checking for close-readiness.

## Findings

### P1 — CSW-2026-07-09-HOME-001: Failed close-readiness reads retain a previous safe verdict and enabled shutdown posture

**Evidence**

- `apps/desktop/webview/static/assets/app.js:961-976` only calls `renderCloseReadiness` when a new payload exists; a rejected read leaves `lastCloseReadiness` untouched.
- `apps/desktop/webview/static/assets/app.js:1078-1103` then passes `values["close readiness"] || lastCloseReadiness` into backend lifecycle, Home readiness, Launch readiness, and live-work rendering.
- `apps/desktop/webview/static/assets/app.js:452-490` allows a shutdown request whenever the cached lifecycle says it can shut down.
- `apps/desktop/webview/static/assets/app/home.js:73-93` reports cached truthy snapshot/close data as current `Backend snapshot: ok` and `Close readiness: safe` even while the failure list contains the required snapshot failure.

**Expected vs. actual**

Expected: once the required snapshot or close-readiness read fails, policy-driving controls must immediately become fail-closed and their displayed status must say unavailable/stale, with the last observation timestamped only as historical context.

Actual: a prior `{ safe_to_close: true }` remains the effective policy input after the route fails. The refresh-health panel records an issue, but the close chip, Home readiness, backend lifecycle panel, and shutdown button can still use the prior safe value.

**Impact**

This is a misleading unsafe-close signal. The backend re-verifies close readiness before shutdown (`commands_process.py:280-318`), so it prevents a normal shutdown from becoming an unchecked stop; however, the operator is shown a stale safe state and an enabled lifecycle affordance precisely when the current state is unknown. Cached active state can likewise keep Force Stop visible after the supporting refresh fails.

**Reproduction/reasoning**

1. Complete a refresh with `safe_to_close: true` and an idle snapshot.
2. Make the next `/api/backend/close-readiness` request reject or time out (or make the required snapshot reject).
3. `Promise.allSettled` adds a failure, but `app.js:976` does not clear the cached result; all downstream contexts use `|| lastCloseReadiness`.
4. The Home readiness text continues to derive `safe` from the old object while reporting a refresh issue.

**Smallest safe remediation**

When either policy read fails, replace the policy input for the current rendering pass with an explicit unavailable sentinel (`safe_to_close: false`, `active_work: true` or a distinct `unavailable` state, reason naming the failed route) and disable lifecycle/launch controls. Retain prior values only as visibly dated, non-authoritative evidence; do not use them for `canShutdown`, force-stop visibility, or active-work control decisions.

**Required validation**

- Browser smoke: seed a safe response, then reject `GET /api/backend/close-readiness`; assert the close chip and Home readiness say unavailable/stale, Request Backend Shutdown is disabled, and no cached-safe lifecycle text remains authoritative.
- Repeat with `GET /api/snapshot` failing after a prior safe response.
- Unit coverage for the refresh context builder: no policy control may consume `lastCloseReadiness` after a current-pass policy failure.
- Run affected WebView lifecycle/Home smokes and `test_application_facade_close_readiness.py`.

### P1 — CSW-2026-07-09-HOME-002: Emergency Force Stop confirmation is frontend-only; the backend accepts and executes `kill` without strict confirmation

**Evidence**

- `apps/desktop/webview/static/assets/launchView.js:930-947` asks `window.confirm` then posts only `{ action: normalized }`.
- `src/mediapipeline/contracts/api_commands.py:562-564` defines `PipelineControlCommandPayload` with only `action`.
- `src/mediapipeline/desktop/api/contract_command.py:1263-1269` lists only `action` as the route request key and includes `kill` among allowed actions.
- `src/mediapipeline/core/processes/control_facade.py:150-164` executes related-process termination and progress reset immediately after action validation/locking.
- `src/mediapipeline/desktop/api/handler.py:105-117` validates and dispatches the request, but no strict force-stop confirmation exists to validate.

**Expected vs. actual**

Expected: after the operator confirms an emergency stop, the request should carry a literal boolean confirmation that the backend contract rejects unless true for `action == "kill"`.

Actual: the browser dialog is the only confirmation. Any authenticated same-origin caller with access to the Local API can submit `POST /api/pipeline/control` with `{ "action": "kill" }`; the backend validates the action and performs the kill/reset.

**Impact**

The backend owns the actual lifecycle action and lock, but it does not own the confirmation boundary. This permits a UI confirmation bypass through browser tooling or another in-scope caller and conflicts with the project’s strict-confirmation pattern for high-consequence commands. The command journal provides evidence after the fact; it does not prevent the stop.

**Reproduction/reasoning**

With a valid local API token, submit only `{"action":"kill"}`. The generated payload model accepts it, the handler dispatches it, and the `kill` branch calls the service’s related-process cleanup plus `_write_idle_progress_file`.

**Smallest safe remediation**

Add `confirm_force_stop: StrictBool` to the pipeline-control contract. Require it to be literal `true` only for `kill`; have the frontend send it only after `window.confirm` succeeds. Keep pause/stop/rescan compatibility unchanged. The backend should journal validation failures and successful commands as it does now.

**Required validation**

- Contract/unit tests: reject missing, false, string, numeric, and null `confirm_force_stop` for `kill`; accept literal `true`; prove non-kill actions retain their existing contracts.
- Local API process-control test: rejected `kill` invokes neither process termination nor progress reset and records the validation failure; accepted `kill` remains lock-protected and journaled.
- Browser smoke: verify cancel emits no POST, confirm posts `confirm_force_stop: true`, and command-result evidence is rendered.

### P2 — CSW-2026-07-09-HOME-003: Valid JSON with a non-boolean `safe_to_close` can render as “safe”

**Evidence**

- `apps/desktop/webview/static/assets/apiClient.js:425-438` validates JSON syntax and HTTP status but does not validate the response shape.
- `apps/desktop/webview/static/assets/app.js:366-374` uses `Boolean(closeReadiness.safe_to_close)` to render the global close chip.
- `apps/desktop/webview/static/assets/app/home.js:77-93` uses the same coercion for Home readiness.
- `apps/desktop/webview/static/assets/app/lifecycle.js:298-328` correctly requires `closeReadiness.safe_to_close === true` before it enables backend shutdown, creating contradictory UI if the value is the string `"false"`.

**Expected vs. actual**

Expected: a missing or non-boolean close-readiness value is an unavailable/invalid payload and blocks all close-related controls and safety claims.

Actual: `{ "safe_to_close": "false" }` is valid JSON and is truthy, so Home and the topbar can display safe. The lifecycle button happens to remain blocked because that separate code uses strict equality.

**Impact**

The contradiction is operator-facing: one safety indicator says safe while the lifecycle panel blocks shutdown. It also leaves future consumers vulnerable if they copy the truthiness pattern.

**Reproduction/reasoning**

Stub `/api/backend/close-readiness` with a 200 JSON object containing `safe_to_close: "false"`. The shared API client resolves it; both render functions coerce it to `true` for display.

**Smallest safe remediation**

Normalize/validate close-readiness once at the API boundary. Require `safe_to_close` and `active_work` to be booleans and `state`/`reason` to be bounded strings; replace invalid payloads with an unavailable, fail-closed model. Use `=== true` in all remaining consumers.

**Required validation**

- API-client/Home rendering tests for string, number, null, missing, and malformed-object close-readiness fields.
- Assert every invalid variant renders `Close: unavailable` (or equivalent), blocks shutdown, and records a refresh failure.
- Re-run lifecycle browser smoke to preserve normal true/false rendering.

## Verified no-finding coverage

- Home markup does not embed start, drain, schedule, pause, stop, or force-stop controls (`test_application_facade_web_static.py:1622-1638`); its stated controls navigate or request backend-allowlisted diagnostics.
- Runtime-file actions are target-based diagnostics opens, not arbitrary path opens (`page-home.html:252-260`); the inventory’s allowlist covers the targets.
- Home refresh is read-only and does not poll `/api/maintenance`, avoiding helper-probe side effects; the browser smoke explicitly checks this (`test_webview_browser_home_live_state_smoke.py:318-341`).
- The Local API handler performs host, origin, and token checks before POST dispatch (`handler.py:80-117`) and journals command outcomes/validation/route failures (`handler.py:110-163`, `server.py:184-201`).
- Backend close readiness is policy-owned and fail-closed for unknown snapshot, fresh progress, related-process inspection failure, schedule watcher, promotion, queue scan, and network rerun (`guard_facade.py:56-107`; close-readiness tests cited above).
- Shutdown rechecks backend close readiness immediately before scheduling shutdown and rejects unsafe work unless its separate strict force path is requested (`commands_process.py:280-318`).
- Cross-page context renders derived, already-loaded evidence and does not decide media policy or mutate filesystem state (`crossPageContextView.js:550-582`).

## Test and contract assessment

The tests provide valuable backend lifecycle evidence: safe/blocked watcher behavior is covered in `test_local_api_lifecycle_contract_smoke.py:67-182`; backend close-readiness covers active, unknown, stale, malformed ActiveJobs, and inspection-failure conditions in `test_application_facade_close_readiness.py`; browser smokes cover Home refresh busy state and normal active display.

Coverage is nevertheless incomplete at the seam that matters to Home:

- No browser test transitions from a successful safe close-readiness response to a failed/timeout response and asserts cache invalidation and disabled controls.
- No test supplies structurally invalid-but-JSON close-readiness data to Home/topbar renderers.
- Current static tests confirm Force Stop is absent from Home and emergency-only in the topbar (`test_application_facade_web_static.py:1610-1681`), but do not assert a backend strict-confirmation contract for `kill`.
- API-client tests prove invalid JSON and network errors are rejected (`test_webview_api_client_smoke.py:145-219`), but not route-specific response schemas.

No tests were executed for this review: the request limited filesystem changes to this report and prohibited pipeline/mutation-route activity. The assessment is based on source and existing test evidence only.

## Cross-tab handoff for the coordinator

- **Launch/topbar owner:** address HOME-002 with a strict backend `confirm_force_stop` contract and add client payload/confirmation tests. The Home panel itself deliberately has no control buttons; the global topbar is the Home-visible control surface.
- **App refresh/lifecycle owner:** address HOME-001 and HOME-003 together with a shared fail-closed close-readiness normalization/invalidation model. Do not let stale cached state drive shutdown, launch, or emergency-control visibility.
- **Diagnostics/lifecycle owner:** preserve the existing backend recheck and command-journal behavior; it is the compensating protection that currently prevents the stale Home display from directly authorizing normal shutdown.
- **Test coordinator:** add a cross-tab browser scenario covering safe -> unavailable/timeout -> recovered for Home, topbar, Diagnostics lifecycle, and Launch controls in one refresh sequence.

## Review limits

- This is a static, read-only end-to-end trace. It did not run a browser, Local API server, PowerShell, FFmpeg, or real-media validation.
- No mutation routes were invoked and no pipeline was started, stopped, or force-stopped.
- Existing dirty/untracked worktree changes were intentionally excluded; this report does not determine whether those changes caused, fix, or mask any behavior.
- No change packet was created because the request expressly prohibited changes outside this Markdown report.
