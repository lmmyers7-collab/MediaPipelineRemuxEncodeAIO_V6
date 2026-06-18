# Tauri/WebView/Backend Lifecycle Authority Review Scope

Review date: 2026-06-16

Review basis: current dirty worktree for this MediaPipelineRemuxEncodeAIO workspace.

This packet is review-only. No runtime source, test source, pipeline code, configuration policy, queue behavior, publish behavior, rename behavior, settings behavior, or Tauri/WebView code was edited.

## Scope

The review covers the lifecycle and authority boundary among:

- Tauri shell ownership of backend process start, backend process shutdown, single-instance guard, startup validation, recovery warnings, close-readiness, and debug automation.
- Local API ownership of authenticated read/command routes, route contracts, command payload validation, command journaling, and backend-owned mutation.
- WebView ownership of read-only/evidence surfaces and operator intent staging.
- Network coordinator/worker lifecycle command contracts and state reporting.
- Queue, pending publish, completed/final-library promotion, rename, settings, and backend shutdown route boundaries.
- Tests and docs that claim or validate the same boundaries.

## Explicit Review Questions

- Does the WebView or shell bypass backend-owned filesystem mutation?
- Does the WebView own media policy, queue policy, publish policy, rename policy, settings policy, or process policy directly?
- Does Tauri own only shell/backend process lifecycle, or does it drift into media mutation?
- Are Local API command routes authenticated, contract-described, payload-validated, and backend-dispatched?
- Can a startup/recovery/banner state give the operator false confidence that mutation controls are safe?
- Can lifecycle evidence claim a stronger state than the backend actually achieved?
- Are direct filesystem, Tauri plugin, shell, or WebView-owned mutation paths present?

## Method

The review followed `AGENTS.md`:

- Read `AGENTS.md`, current project state, open work checklist, and generated project index first.
- Inspected generated summaries before opening full source for primary Tauri, WebView, Local API, route contract, and test files.
- Used direct source and test inspection after summary review.
- Used targeted static searches for Tauri APIs, WebView command posts, filesystem APIs, storage, and route usage.

Some queue and support command files were opened during targeted follow-up and their generated summary coverage was then checked. The findings below distinguish hard source evidence from inference.

## In Scope Files And Surfaces

- `apps/desktop/tauri/src-tauri/src/lib.rs`
- `apps/desktop/tauri/src-tauri/src/backend_process.rs`
- `apps/desktop/tauri/src-tauri/src/backend_contract.rs`
- `apps/desktop/tauri/src-tauri/src/single_instance_guard.rs`
- `apps/desktop/tauri/src-tauri/src/backend_lifecycle_monitor.rs`
- `apps/desktop/tauri/src-tauri/src/close_readiness.rs`
- `apps/desktop/tauri/src-tauri/src/dialogs.rs`
- `apps/desktop/tauri/src-tauri/src/debug_webview.rs`
- `apps/desktop/tauri/src-tauri/tauri.conf.json`
- `apps/desktop/tauri/src-tauri/capabilities/default.json`
- `apps/desktop/webview/static/index.html`
- `apps/desktop/webview/static/assets/apiClient.js`
- `apps/desktop/webview/static/assets/app.js`
- `apps/desktop/webview/static/assets/app/lifecycle.js`
- `apps/desktop/webview/static/assets/app/closeReadiness.js`
- `apps/desktop/webview/static/assets/tauriLifecycleBridge.js`
- `apps/desktop/webview/static/assets/networkView.js`
- `apps/desktop/webview/static/assets/pendingPublishView.drain.js`
- `apps/desktop/webview/static/assets/renameView.js`
- `apps/desktop/webview/static/assets/settingsView.js`
- `src/mediapipeline/desktop/api/*`
- `src/mediapipeline/core/api/*`
- `src/mediapipeline/contracts/api_commands.py`
- `src/mediapipeline/core/network/lifecycle_facade.py`
- `src/mediapipeline/desktop/application/network_lifecycle_provider.py`
- Relevant Python, WebView, and Tauri scaffold tests.

## Out Of Scope

- Source remediation.
- Full manual Tauri/WebView runtime operation against real media.
- External attacker modeling beyond local WebView/loopback/API authority boundaries.
- Non-Windows runtime behavior except where the code advertises cross-platform bundle targets.

## Artifact Index

- `00-review-scope.md`: scope, method, and boundaries reviewed.
- `01-code-map.md`: source map and ownership map.
- `02-invariants-and-boundaries.md`: required invariants and current status.
- `03-risk-review.md`: risk analysis by subsystem.
- `04-test-coverage-review.md`: existing coverage and gaps.
- `05-findings.md`: severity-ranked findings.
- `06-remediation-plan.md`: ordered remediation plan.
- `07-validation-plan.md`: validation commands and expected gates.
- `08-final-review-summary.md`: final review conclusion.
