# Invariants And Boundaries

This review treats the backend as the only authority for media mutation and lifecycle policy. The WebView may stage operator intent and display evidence, but it must not own mutation policy.

## Required Invariants

### I-01 Backend Owns Media Mutation

No WebView or Tauri shell code may directly mutate source media, scratch media, output media, queue state, pending publish state, completed-library state, rename results, or settings files.

Current status: mostly satisfied.

Evidence:

- Tauri capabilities grant only `core:default`, with no WebView filesystem or shell plugin permissions.
- Static WebView searches found no Tauri `invoke`, filesystem, shell, or dialog mutation APIs.
- Queue, rename, settings, publish, final-library, process launch, and backend shutdown operations are backend POST routes.
- Backend command handlers validate payloads and apply backend policy before mutation.

### I-02 WebView Stages Intent And Displays Evidence

The WebView may collect operator intent, request previews/dry-runs, and post confirmed commands. It must not make final policy decisions that the backend trusts without verification.

Current status: mostly satisfied.

Evidence:

- Network lifecycle commands use routes from `/api/contract`, send strict confirmation intent, and rely on backend preconditions.
- Rename apply requires a fresh preview in the WebView, but backend command code strips policy fields and rebuilds authority from backend state.
- Settings save requires preview/confirmation in the WebView, but backend save/reload owns persistence.
- Pending publish drain uses `/api/pipeline/start` with drain mode; WebView filters and selections do not publish files directly.

Residual risk:

- If a stale or drifted WebView asset is allowed to open, the UI may lack the guardrails that make intent staging trustworthy.

### I-03 Local API Owns Route And Payload Authority

All non-public read and command routes must require Local API token authentication, route lookup, strict JSON object parsing, payload validation, and backend dispatch.

Current status: satisfied for reviewed command surfaces.

Evidence:

- GET routes require auth except static index/assets and health.
- POST routes require host/origin/auth checks, route lookup, strict JSON object body, payload validation, and command dispatch.
- Auth uses headers only, not query-string tokens.
- Sensitive command-journal fields are redacted.

Residual risk:

- The token is readable from global JavaScript state in the WebView. If a local script injection or compromised static asset executes, it can call tokened routes.

### I-04 Route Contracts Must Match Runtime Effects

The `/api/contract` payload must be the public authority map for route effects, confirmation requirements, journaling expectations, and frontend exposure.

Current status: mostly satisfied.

Evidence:

- Contract metadata classifies settings save as `config-write`, rename apply and final-library promotion as filesystem mutation, and network lifecycle start/stop as backend lifecycle.
- Repair/reconcile are explicitly design-only with no mutation routes.
- Tests assert route effects and ownership metadata.

Residual risk:

- Network lifecycle confirmed stop can report a generic stopped state while active work is still intentionally preserved in provider runtime state.

### I-05 Tauri Owns Shell And Backend Process Lifecycle Only

Tauri should start the Local API, validate the backend and UI contract, inject the per-run token, display lifecycle status, and broker close/shutdown. It should not mutate media or own media policy.

Current status: satisfied for direct mutation, but not fully fail-closed for UI safety validation.

Evidence:

- Tauri starts bundled Python Local API, not media pipeline operations directly.
- Close requests call backend close-readiness and backend shutdown routes.
- Forced shutdown is process-tree termination after backend shutdown failure/timeout, not media mutation.

Boundary concern:

- Tauri treats most WebView safety validation failures as warnings and opens the shell.

### I-06 Startup Validation Must Fail Closed For Safety-Critical UI Drift

If WebView assets are missing close-readiness, shutdown, route-contract, pending-drain, settings, rename, or network lifecycle guardrails, the shell must not present mutation or lifecycle controls as usable.

Current status: violated.

Evidence:

- `backend_contract.rs` validates many safety-critical fragments.
- `backend_process.rs` only treats token leak, raw bootstrap placeholder, and missing bootstrap assignment as fatal.
- `lib.rs` renders a warning banner while still opening the WebView.

Impact:

- The operator can see a running shell after Tauri detects UI drift. The banner warns them, but the UI may still contain stale or incomplete controls.

### I-07 Close-Readiness Is The Authority For Safe Shutdown

The shell and WebView must use backend close-readiness to decide safe shutdown. Only explicit forced shutdown may terminate active work.

Current status: mostly satisfied.

Evidence:

- Tauri close requests call `/api/backend/close-readiness`.
- WebView backend shutdown button is disabled unless close-readiness is loaded and safe.
- Backend shutdown route blocks unsafe shutdown unless strict `force_active_work_shutdown` is true.

Residual risk:

- Fail-open WebView asset validation can allow a stale WebView to lack the current shutdown guard.

### I-08 Network Lifecycle Dry-Run Has No Mutation Effect

Network dry-run routes must remain read-only and must report protected path categories.

Current status: satisfied.

Evidence:

- Contract and facade mark dry-runs as `effect: none`, `dry_run_only`, and `mutation_enabled:false`.
- WebView treats dry-runs as evidence previews and does not confirm mutation.

### I-09 Network Lifecycle Confirmed Stop Must Not Mislead Operators

If stop preserves active coordinator/worker work, UI and API evidence must not imply that the network lifecycle is fully stopped.

Current status: partially violated.

Evidence:

- Provider stop preserves active runtime entries and active jobs.
- Facade result can still commit/report `state_after.status: stopped`.
- WebView prints command completion and state JSON without a stronger "stop pending active work" headline.

### I-10 Single Instance Must Protect Shared Local State

Only one shell should own a backend against shared local state at a time.

Current status: satisfied on Windows, not implemented on non-Windows.

Evidence:

- Windows mutex guard is acquired before backend start.
- Non-Windows implementation returns success without locking.
- Bundle target is configured as `all`.
