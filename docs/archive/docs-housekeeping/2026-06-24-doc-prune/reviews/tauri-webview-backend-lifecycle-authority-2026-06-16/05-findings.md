# Findings

Findings are ordered by severity. This review did not find direct WebView or Tauri filesystem mutation bypasses. The highest risks are fail-open validation and false operator trust.

## F-01 High: Tauri Opens The Shell After Safety-Critical WebView Validation Warnings

Status: confirmed.

Affected boundary:

- Tauri backend process lifecycle.
- WebView read-only/evidence trust.
- Recovery banner and route-contract safety.

Evidence:

- `apps/desktop/tauri/src-tauri/src/backend_contract.rs:18-90` validates static index lifecycle, diagnostics, and bootstrap fragments.
- `apps/desktop/tauri/src-tauri/src/backend_contract.rs:179-222` validates backend shutdown and close-readiness JavaScript fragments.
- `apps/desktop/tauri/src-tauri/src/backend_contract.rs:1180-1263` validates pending diagnostics/drain evidence fragments.
- `apps/desktop/tauri/src-tauri/src/backend_process.rs:264-281` converts most WebView validation failures into startup warnings and continues opening the shell.
- `apps/desktop/tauri/src-tauri/src/backend_process.rs:301-306` makes only token leak, raw bootstrap placeholder, and missing bootstrap assignment fatal.
- `apps/desktop/tauri/src-tauri/src/lib.rs:147-156` injects a warning banner after Tauri detected WebView asset drift.
- `apps/desktop/tauri/src-tauri/src/lib.rs:260-310` tests codify that non-bootstrap WebView validation failures are not fatal.

Impact:

Tauri can detect that the WebView no longer contains expected safety controls, then still open a mutation-capable shell. The warning banner asks the operator to open Diagnostics before starting, draining, saving, renaming, publishing, or closing. That warning is weaker than fail-closed enforcement. A stale UI could still post valid backend commands while lacking the current close-readiness, route-contract, pending-drain, rename, settings, or network lifecycle guardrails.

This is an operator trust and authority-boundary issue. It gives the operator a running UI after the shell already knows UI evidence is not trustworthy.

Recommendation:

- Treat all safety-critical WebView validation failures as fatal before opening the normal shell.
- Alternatively, open only a quarantined diagnostics-only shell with all mutation, process, lifecycle, settings, rename, publish, and drain controls disabled.
- Add tests that remove each safety fragment and assert fail-closed behavior.

Confidence: high.

## F-02 Medium: Network Lifecycle Stop Can Report Stopped While Active Work Is Preserved

Status: confirmed.

Affected boundary:

- Network coordinator/worker lifecycle state.
- WebView evidence surfaces.
- Operator trust during stop/drain.

Evidence:

- `src/mediapipeline/desktop/application/network_lifecycle_provider.py:617-655` preserves active coordinator work by setting stop/drain state and leaving runtime entries.
- `src/mediapipeline/desktop/application/network_lifecycle_provider.py:738-767` preserves active worker jobs/processes and leaves runtime state when active.
- `src/mediapipeline/core/network/lifecycle_facade.py:754-825` builds and commits the confirmed lifecycle result after journaling.
- `apps/desktop/webview/static/assets/networkView.js:1325-1400` renders confirmed command completion plus `state_before` and `state_after` evidence.
- `tests/python/desktop/test_network_lifecycle_fixes.py:470-554` verifies worker/coordinator active work is preserved on stop.
- `tests/python/desktop/test_network_lifecycle_fixes.py:814-848` verifies confirmed coordinator stop with remote claim enters drain and leaves runtime state.

Impact:

The backend intentionally preserves active work, which is the right media-safety behavior. The risk is semantic: command evidence can still present a stopped state or a completed command headline while work is draining or preserved. That can make the operator believe no active coordinator/worker work remains.

Recommendation:

- Add a distinct lifecycle state/result for `draining`, `stop_requested`, or `active_work_preserved`.
- Do not report plain `state_after.status: stopped` while runtime entries, active jobs, active claims, or preserved processes remain.
- Update WebView copy to headline active-work-preserved stop states.
- Add backend and WebView tests for confirmed stop with active local and remote work.

Confidence: high.

## F-03 Medium: Global WebView Token And Unsafe CSP Increase Local Script Blast Radius

Status: confirmed hardening risk.

Affected boundary:

- Local API authentication authority.
- WebView command authority.
- Tauri token injection.

Evidence:

- `src/mediapipeline/desktop/api/static_files_policy.py:23-43` withholds token from static bootstrap in Tauri mode and expects initialization-script injection.
- `apps/desktop/tauri/src-tauri/src/lib.rs:147-156` injects token-bearing `window.MEDIA_PIPELINE_TAURI_BOOTSTRAP`.
- `apps/desktop/webview/static/index.html:11-16` merges the Tauri bootstrap into `window.MEDIA_PIPELINE_BOOTSTRAP`.
- `apps/desktop/webview/static/assets/apiClient.js:1-10` reads the token from global bootstrap state.
- `apps/desktop/webview/static/assets/apiClient.js:67-98` exposes tokened API helpers globally.
- `apps/desktop/tauri/src-tauri/tauri.conf.json` and `src/mediapipeline/desktop/api/http_helpers.py:30-40` allow `'unsafe-inline'` and `'unsafe-eval'`.
- `src/mediapipeline/desktop/api/handler.py:77-113` permits authenticated POST command dispatch after token/origin/payload validation.

Impact:

The current design does not expose the token in URLs and does not grant Tauri filesystem/shell permissions. That is good. The remaining hardening concern is that any script running inside the WebView can read the token and use globally exposed API helpers to call authenticated Local API routes. The unsafe CSP values increase the consequences of any local script injection or compromised static asset.

Recommendation:

- Keep the token inside an API-client closure instead of a readable global object.
- Avoid exposing broad tokened command helpers globally where practical.
- Remove `'unsafe-eval'` and reduce `'unsafe-inline'` if the Tauri/static boot path can support it.
- Consider effect-scoped or route-scoped command capabilities for high-risk routes.
- Add static/browser tests that prove the token is not globally readable.

Confidence: medium-high.

## F-04 Low: Single-Instance Guard Is Windows-Only While Bundle Targets Are All

Status: confirmed conditional risk.

Affected boundary:

- Tauri backend process lifecycle.
- Local shared state ownership.

Evidence:

- `apps/desktop/tauri/src-tauri/src/single_instance_guard.rs:18-35` implements a Windows mutex guard before backend start.
- `apps/desktop/tauri/src-tauri/src/single_instance_guard.rs:41-44` returns success on non-Windows without locking.
- `apps/desktop/tauri/src-tauri/tauri.conf.json` advertises bundle targets `all`.

Impact:

The Windows target has a guard. If non-Windows bundles are produced or tested, two shells could start two Local API backends against the same user state. That violates the intended single-owner lifecycle boundary.

Recommendation:

- If non-Windows bundles remain supported, implement a cross-platform lockfile/advisory lock under backend state or app data.
- If the product is Windows-only, restrict bundle targets and document that boundary.

Confidence: high for code state; impact depends on packaging intent.

## F-05 Low: Debug Automation Can Bypass Operator Confirmation In Debug Harnesses

Status: confirmed residual/test-only risk.

Affected boundary:

- WebView operator-intent boundary in debug builds.

Evidence:

- `apps/desktop/tauri/src-tauri/src/debug_webview.rs:79-134` enables test autolaunch through explicit environment flags.
- `apps/desktop/tauri/src-tauri/src/debug_webview.rs:220-257` can set launch fields, override `window.confirm = () => true`, and click pipeline start.
- `apps/desktop/tauri/src-tauri/src/debug_webview.rs:136-137` is no-op for release builds.
- `tests/python/desktop/test_tauri_shell_scaffold.py:2157-2218` covers debug auth capture and WebView start harness behavior.

Impact:

This is acceptable for automation if it remains debug-only and env-gated. It should not be allowed into production bundles or operator workflows because it bypasses explicit confirmation.

Recommendation:

- Keep release-build no-op coverage.
- Add release validation that debug automation env hooks cannot run in production bundles.
- Keep debug automation documented as test-only.

Confidence: high.

## Confirmed Non-Findings

### No direct WebView filesystem mutation found

Static inspection found no WebView use of Tauri filesystem APIs, shell APIs, dialog mutation APIs, direct OS filesystem calls, or Tauri `invoke` command mutation. WebView command posts go through Local API helpers.

### No Tauri media mutation path found

Tauri starts/stops/monitors the backend and handles shell close. It does not directly mutate media, queue, pending publish, rename output, or settings.

### Local API remains the mutation owner for reviewed command surfaces

Backend handlers own:

- Queue priority and strategy writes.
- Pending publish drain launch.
- Completed/final-library promotion.
- Rename preview/apply policy.
- Settings preview/save/reload.
- Pipeline launch.
- Network lifecycle start/stop/dry-run.
- Backend shutdown.

### Repair/reconcile remains design-only

The Local API contract exposes repair/reconcile as design-only with no mutation routes.
