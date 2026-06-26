# Risk Review

## Executive Risk View

The reviewed architecture largely preserves the intended authority boundary: the Local API/backend owns filesystem mutation, media policy, queue policy, pending publish, rename apply, settings persistence, final-library promotion, process launch, and backend shutdown. The WebView mostly stages intent and renders evidence. The Tauri shell mostly owns process lifecycle only.

The most important risk is not a discovered direct WebView filesystem bypass. It is a trust failure: Tauri validates safety-critical WebView fragments but opens the shell on most validation failures. That makes the recovery banner the main protection after detecting UI drift.

## Tauri Shell Lifecycle Risks

### Fail-open WebView safety validation

Risk: high.

Tauri validates many WebView guardrail fragments, but only bootstrap-security failures are fatal. Missing lifecycle, close-readiness, route-contract, pending-drain, settings, rename, or network guard fragments become startup warnings. A warning banner is useful evidence, but it does not remove stale mutation controls.

Why this matters:

- WebView guardrails are part of the authority boundary.
- A stale UI may post valid backend commands while omitting newer safety copy, disabled states, or route-contract checks.
- The operator sees an app that opened successfully after Tauri detected drift.

### Forced shutdown process termination

Risk: medium, controlled.

Forced shutdown can terminate the backend process tree after a failed/blocked safe shutdown. This is intentional process lifecycle authority, not media policy. The backend route requires forced cleanup intent before process termination. Residual risk is limited to active work interruption when the operator confirms force.

### Debug automation

Risk: low in production, medium in debug/test.

Debug-only automation can override `window.confirm` and click launch. It is env-gated and compiled as debug-only, but it is intentionally capable of bypassing operator interaction in harness scenarios.

### Single-instance guard portability

Risk: low for Windows release, medium if non-Windows bundles are shipped.

The guard is Windows-only, while the Tauri config advertises bundle targets `all`. Multiple non-Windows shells could start independent Local API backends against shared state.

## Local API Authority Risks

### Token boundary

Risk: medium.

The per-run token is generated server-side and sent only in headers by API client calls. This is good. However, in the WebView it is stored in global JavaScript bootstrap state and the API helpers are globally exposed. Any script execution inside the WebView can become fully authorized to call Local API routes.

Amplifiers:

- CSP currently permits `'unsafe-inline'` and `'unsafe-eval'`.
- The token gates all tokened routes rather than route/effect-scoped capabilities.

Mitigations already present:

- No query-string token transport.
- Host/origin checks.
- Static asset path traversal blocking.
- Command payload validation.
- Command journal redaction.

### Empty Origin acceptance

Risk: low to medium.

Empty Origin is accepted for Local API requests. This may be necessary for local desktop/webview clients and direct fetch contexts. Combined with bearer-token auth, the main boundary remains possession of the token.

## WebView Authority Risks

### Direct filesystem mutation

Risk: low.

No direct WebView filesystem mutation was found. No Tauri filesystem/shell/dialog plugin usage was found. WebView commands use tokened backend routes.

### False authority through stale UI

Risk: high, tied to Tauri validation.

The WebView code itself generally renders backend-owned authority correctly. The risk appears when Tauri knowingly opens with validation warnings for missing safety fragments.

### UI-owned policy

Risk: low to medium.

The WebView has local prechecks, preview gating, confirmation dialogs, and UI preference storage. Reviewed backend command handlers do not rely solely on UI-owned policy for authoritative mutation. Residual risk is mainly wording/trust, not mutation ownership.

## Network Lifecycle Risks

### Active stop reported as stopped

Risk: medium.

The network lifecycle provider intentionally preserves active worker/coordinator processes during stop. The facade can still report `state_after.status: stopped`, and the UI renders command-completed evidence. This can cause operator false trust: they may believe the worker/coordinator is fully stopped when a drain or active job is still preserved.

Safety note:

- This is not a source/media mutation bypass.
- Preserving active work is safer than killing active work.
- The issue is state semantics and operator evidence.

### Dry-run mutation boundary

Risk: low.

Dry-run routes are contract-described as effect-none and the backend facade returns protected path categories and `dry_run_only`. This boundary is well represented.

## Queue, Publish, Rename, Settings, And Final Library Risks

### Queue priority/strategy

Risk: low.

Queue priority and strategy writes are backend-owned. Source paths are validated under configured roots for priority mutations. The WebView does not write manifests directly.

### Pending publish drain

Risk: low.

Pending drain is routed through backend pipeline start mode. The UI presents scope/evidence; it does not publish files.

### Rename apply

Risk: low.

The WebView sends selected sources and confirmation. Backend command code strips frontend-provided policy keys and injects configured roots and rename policy.

### Settings persistence

Risk: low.

The WebView previews and confirms. Backend settings command owns validation, backup, save, and reload.

### Final-library promotion

Risk: low.

The route is contract-described as filesystem mutation and backend-owned. No WebView direct promotion/copy/delete path was found.

## Recovery Banner Risk

Risk: high as currently used.

The banner communicates that Tauri detected WebView asset drift and advises opening Diagnostics before starting, draining, saving, renaming, publishing, or closing. That is accurate text, but it is weaker than disabling or failing closed. A warning banner cannot be the only barrier after a shell has identified missing safety-critical controls.
