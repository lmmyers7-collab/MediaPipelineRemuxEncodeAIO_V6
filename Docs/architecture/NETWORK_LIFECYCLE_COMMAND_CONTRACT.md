# Network Lifecycle Command Contract

Date: 2026-05-20

This is the source-of-truth design contract for future WebView/Tauri Network lifecycle commands. It does not authorize implementation by itself. The current workspace has no Network start, stop, retry, reclaim, release, abort, or worker-polling POST routes and no WebView lifecycle buttons.

The WebView may display these boundaries from `/api/contract`, but it must not infer lifecycle safety, start or stop coordinator/worker runtime, author queue state, release claims, send done reports, write Network state files, launch media work, or touch source/scratch/output/pending-publish files.

---

## Current Status

- `/api/contract` publishes `network_lifecycle_summary.status=design_only_no_lifecycle_routes`.
- Every network lifecycle contract has `mutation_enabled=false` and `frontend_allowed=false`.
- `GET /api/network/workers` remains read-only persisted runtime-state evidence.
- No Network lifecycle POST route exists on the Network page. Non-lifecycle Network-page actions are limited to backend-owned Diagnostics opens (`POST /api/diagnostics/open`) and the Worker Mode Settings panel, which delegates preview/save to the existing Settings routes (`POST /api/settings/preview-patch`, `POST /api/settings/save-patch`) instead of creating Network lifecycle routes.
- No POST route in `LOCAL_API_ROUTE_CONTRACT` may include Network lifecycle semantics while this status remains design-only.

---

## Required Future Flow

Any future Network lifecycle capability must ship in this order:

1. Backend dry-run route with `effect=none`.
2. Backend tests proving the dry-run returns `dry_run_only=true`, role/config/token/path-map precondition results, active-work evidence, duplicate-command guards, and `would_not_touch` source/scratch/output/queue/pending-publish evidence.
3. Backend mutation route only after process cleanup, dispatcher rollback, state preservation, command journaling, close-readiness integration, and timeout handling are tested.
4. WebView control only after route inventory, command ownership, browser no-mutation/static coverage, operator-visible command-result evidence, and change-control evidence exist.

The frontend must never construct filesystem paths, synthesize worker state, expose tokens, or author coordinator/worker safety decisions. All role, readiness, state-file, claim, active-work, and cleanup posture must come from backend state.

---

## Published Contract Fields

Each `network_lifecycle_contracts[]` item in `/api/contract` must include:

| Field | Requirement |
|---|---|
| `current_status` | `design_only_no_route` until a backend route exists |
| `mutation_enabled` | `false` until lifecycle mutation route tests pass |
| `frontend_allowed` | `false` until a backend route, result evidence, command history, and browser/static coverage exist |
| `dry_run_contract` | Defines a future no-mutation result schema and required result fields |
| `rollback_contract` | Defines process cleanup, state preservation, and journal evidence expected before any mutation route |
| `source_file_policy` | Keeps source media mutation/delete/rename forbidden and path authority backend-owned |
| `route_exposure_gates` | Lists the inventory/test/doc gates required before WebView exposure |
| `must_not` | Explicitly forbids unsafe behavior for the lifecycle surface |

The required dry-run result fields are:

`schema_version`, `candidate_command`, `dry_run_only`, `role`, `requested_action`, `lifecycle_state`, `precondition_results`, `would_start_processes`, `would_stop_processes`, `would_write_state`, `would_not_touch`, `safe_to_apply`, and `operator_confirmation_scope`.

---

## Surface Contracts

| Surface | Candidate command | Current authority | Mutation class | Hard boundary |
|---|---|---|---|---|
| Coordinator API start | `network.coordinator.start` | Network / backend dispatcher | Network lifecycle start | Must not start while close-readiness is unsafe, expose tokens, mutate queue/media state, or reuse removed desktop-shell dialog flow in Local API |
| Coordinator API stop | `network.coordinator.stop` | Network / backend dispatcher | Network lifecycle stop | Must not silently abandon active local encode work, delete state files, force-release claims, or mutate media/publish state |
| Worker polling start/stop | `network.worker.polling_lifecycle` | Network / backend dispatcher | Worker process lifecycle | Must not start duplicate polling loops, discard pending done reports, trust frontend paths, or launch media work from WebView-only logic |

---

## Validation Gates

Current static gates:

- `tests/python/desktop/test_api_contract_payload.py` verifies the design-only contract payload, dry-run schema fields, rollback journal fields, source-file policy, route exposure gates, and deep-copy behavior.
- `tests/python/desktop/test_application_facade_local_api.py` verifies the live Local API contract exposes the same design-only lifecycle fields.
- `tests/python/desktop/test_webview_network_read_only_boundary.py` keeps the Network page diagnostics-open-only and verifies no Network lifecycle/mutation route is callable from WebView assets.
- `tests/python/desktop/test_application_facade_network.py` verifies `GET /api/network/workers` remains read-only persisted evidence and now proves heartbeat age is backend-authored from persisted worker timestamps.

Future implementation must add route-level negative tests, duplicate-start/stop tests, active-work rejection tests, command-journal tests, process cleanup/orphan tests, browser no-mutation tests, and source/scratch/output/pending-publish hash checks before any control is considered daily-driver safe.

