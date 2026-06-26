# Test Coverage Review

## Coverage That Supports The Boundary

### Tauri Shell Scaffold

`tests/python/desktop/test_tauri_shell_scaffold.py`

Coverage includes:

- Tauri launches the bundled Python Local API rather than launching pipeline work directly.
- Backend bootstrap output is parsed and cleaned up on failed bootstrap.
- Backend lifecycle monitor scaffolding exists.
- Single-instance and read-only lifecycle banner checks exist.
- Backend-served WebView validation is checked before opening.
- Startup warning and fatal-policy logic are present.
- Close-readiness prompt text includes watcher and forced-shutdown warning details.
- Graceful backend shutdown occurs before forced kill.
- Debug harnesses use explicit debug auth capture.
- PG2 harness starts through WebView automation rather than directly posting backend start.

Boundary value:

- Strong scaffold coverage for shell/backend lifecycle.
- Existing tests also codify the current fail-open behavior for non-bootstrap WebView drift.

Gap:

- Tests do not require safety-critical WebView validation fragments to be fatal.

### Local API Contract And Payload Tests

`tests/python/desktop/test_application_facade_local_api.py`

Coverage includes:

- `/api/contract` auth and tokened routes.
- Network lifecycle summary and route availability.
- Repair/reconcile design-only status.
- Route effects for filesystem mutation, config-write, and backend-lifecycle routes.
- Contract UI text for mutation guardrails and frontend read-only posture.

`tests/python/desktop/test_api_command_contracts.py`

Coverage includes:

- Strict boolean payload validation for backend shutdown force cleanup.
- Command ownership matrix across POST routes.
- Route/payload contract mapping.

Boundary value:

- Strong route ownership and contract metadata coverage.

Gap:

- Token capability scope is still all-or-nothing for authenticated WebView JavaScript; tests do not enforce token hiding from global state.

### WebView Lifecycle Browser Smoke

`tests/webview/test_webview_browser_lifecycle_smoke.py`

Coverage includes:

- Blocked close-readiness disables backend shutdown.
- Safe close-readiness posts only backend shutdown after confirmation.
- Lifecycle UI flows do not mutate media directly.

Boundary value:

- Good WebView shutdown gating coverage for the current built assets.

Gap:

- Does not cover stale asset validation behavior at Tauri shell startup.

### WebView Network Boundary

`tests/webview/test_webview_network_read_only_boundary.py`

Coverage includes:

- Network page buttons are diagnostics/lifecycle/settings only.
- Future mutation buttons are disabled.
- Lifecycle buttons and settings IDs are allowlisted.

`tests/webview/test_webview_browser_network_smoke.py`

Coverage includes:

- Browser-stubbed network route and evidence behaviors.
- Read-only discovery/join surfaces.

Boundary value:

- Good page-level read-only posture coverage.

Gap:

- The WebView network smoke catalog explicitly avoids confirmed coordinator/worker start/stop. Confirmed lifecycle semantics are mainly backend-tested, not browser-rendered end-to-end.

### Network Lifecycle Backend Tests

`tests/python/desktop/test_network_lifecycle_fixes.py`

Coverage includes:

- Worker stop preserves active job/process and sets stop-request state.
- Coordinator stop preserves active local worker process and sets stop-request state.
- Dry-run reports active in-memory and remote work.
- Start dry-run blocks when preserved active work exists.
- Stop already-stopped behavior is idempotent.
- Journal failure does not leave phantom running state.
- Confirmed coordinator stop with remote claim enters drain without HTTP shutdown and leaves runtime state.

Boundary value:

- Strong evidence that active work is preserved.

Gap:

- The same tests reveal the semantics risk: confirmed stop can be represented as stopped while provider runtime still preserves active work. The tests do not enforce a distinct `draining` or `stop_requested_active_work` state.

### Command-Specific Backend Tests

Existing backend tests cover large parts of:

- Queue priority and strategy command behavior.
- Rename policy and facade behavior.
- Settings validation and save/reload flows.
- Final-library and completed policy.
- Static WebView route and contract assets.

Boundary value:

- Mutation is generally backend-tested.

Gap:

- This review did not identify one single focused test that fails if any WebView route posts direct filesystem/Tauri shell commands, beyond static source assertions and page-level smoke checks.

## Coverage Gaps To Close

### G-01 Safety-critical WebView validation must fail closed

Add tests that remove or corrupt each critical WebView fragment and assert Tauri refuses to open mutation-capable shell controls, or opens only a quarantined diagnostics-only shell.

Fragments should include:

- Close-readiness guard.
- Backend shutdown disabled-state guard.
- Route contract loading.
- Network lifecycle contract/precondition text.
- Pending drain backend authority text.
- Rename fresh-preview/confirmation guard.
- Settings preview/save confirmation guard.
- Token bootstrap safety.

### G-02 Confirmed active-stop lifecycle semantics

Add backend tests requiring a distinct result/status when stop preserves active work.

Expected evidence:

- `state_after.status` must not be plain `stopped` if active runtime entries remain.
- Result should expose `stop_requested`, `draining`, or `active_work_preserved`.
- UI rendering should headline that stop is pending active work completion.

### G-03 Browser rendering of confirmed lifecycle results

Add WebView browser smoke coverage for confirmed coordinator/worker start/stop using backend stubs that return active-work-preserved stop results.

Assertions:

- UI does not display plain success/stopped copy.
- UI displays active-work-preserved evidence.
- UI does not offer actions that imply the worker/coordinator is fully inactive.

### G-04 Token/CSP hardening tests

If token storage is hardened:

- Assert token is not exposed on a readable global bootstrap object.
- Assert API helpers do not expose broad command authority globally.
- Assert CSP no longer requires unsafe eval.
- Assert static assets still boot in Tauri and browser smoke contexts.

### G-05 Non-Windows single-instance behavior

If non-Windows packaging remains supported:

- Add a cross-platform lockfile/advisory mutex test.
- Add an integration test or simulated second-instance test.
- Otherwise test or document that Tauri package targets are Windows-only.

### G-06 Release profile debug automation guard

Add release/build validation that debug automation code and environment hooks cannot run in production bundles.

## Recommended Test Priority

1. Fail-closed WebView validation tests.
2. Confirmed active-stop state semantics tests.
3. Browser rendering tests for active-stop evidence.
4. Token/CSP hardening tests.
5. Cross-platform single-instance or Windows-only target validation.
6. Release debug-automation guard.
