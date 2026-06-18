# Network Lifecycle Command Contract

Date: 2026-06-13

This is the source-of-truth contract for WebView/Tauri Network lifecycle commands. The current workspace exposes backend-owned coordinator/worker dry-run routes and confirmed start/stop routes. Confirmed routes are intentionally provider-guarded: they return a blocked command result until the real coordinator or worker lifecycle provider is available and preconditions pass.

The WebView may render Network lifecycle controls only by calling these Local API routes. It must not infer lifecycle safety, start or stop runtime loops directly, author queue state, release claims, send done reports, write Network state files, launch media work, or touch source/scratch/output/pending-publish files.

---

## Current Status

- `/api/contract` publishes `network_lifecycle_summary.status=backend_lifecycle_routes_available_provider_guarded`.
- Network lifecycle contracts have `mutation_enabled=true` and `frontend_allowed=true` because backend routes now exist.
- `GET /api/network/workers` remains read-only persisted runtime-state evidence.
- Dry-run routes have `effect=none` and must report role, lifecycle state, preconditions, active work, pending done reports, state-file posture, redacted config evidence, and `would_not_touch` evidence.
- Confirmed routes have `effect=backend-lifecycle`, require `confirm_start` or `confirm_stop`, create command-journal evidence, and fail closed when provider preconditions are blocked.
- Normal Launch is blocked whenever `NetworkRole` is `coordinator` or `worker`; Network work starts only from Network lifecycle controls.

---

## Route Flow

Operators should use routes in this order:

1. `POST /api/network/coordinator/start-dry-run`
2. `POST /api/network/coordinator/stop-dry-run`
3. `POST /api/network/worker/start-dry-run`
4. `POST /api/network/worker/stop-dry-run`
5. Confirmed `POST /api/network/{coordinator|worker}/{start|stop}` only after the relevant dry-run evidence is acceptable.

Dry-runs are no-mutation. Confirmed routes are still not allowed to substitute for the real dispatcher provider. If the provider hook is unavailable, the route must return a blocked command result instead of starting a normal local run, scanning the queue, releasing claims, or processing media.

---

## Published Contract Fields

Each `network_lifecycle_contracts[]` item in `/api/contract` must include:

| Field | Requirement |
|---|---|
| `current_status` | `backend_route_available_provider_guarded` while routes exist but the real lifecycle provider is still guarded |
| `mutation_enabled` | `true` for lifecycle start/stop route exposure |
| `frontend_allowed` | `true` only for the backend-owned routes in this contract |
| `dry_run_contract` | Defines the no-mutation result schema and required result fields |
| `rollback_contract` | Defines process cleanup, state preservation, and journal evidence required for mutation routes |
| `source_file_policy` | Keeps source media mutation/delete/rename forbidden and path authority backend-owned |
| `route_exposure_gates` | Lists the inventory/test/doc gates required for WebView exposure |
| `must_not` | Explicitly forbids unsafe behavior for the lifecycle surface |

The required dry-run result fields are:

`schema_version`, `candidate_command`, `dry_run_only`, `role`, `requested_action`, `lifecycle_state`, `precondition_results`, `would_start_processes`, `would_stop_processes`, `dry_run_writes`, `confirmed_route_would_write`, `would_not_touch`, `safe_to_apply`, and `operator_confirmation_scope`.

---

## Surface Contracts

| Surface | Routes | Current authority | Mutation class | Hard boundary |
|---|---|---|---|---|
| Coordinator start | `/api/network/coordinator/start-dry-run`, `/api/network/coordinator/start` | Network / backend dispatcher | `none`, then `backend-lifecycle` | Must not start while close-readiness or provider preconditions are unsafe; must not process local files unless the real provider supports the configured coordinator-local mode |
| Coordinator stop | `/api/network/coordinator/stop-dry-run`, `/api/network/coordinator/stop` | Network / backend dispatcher | `none`, then `backend-lifecycle` | Must preserve `coordinator_inflight.json`, `worker_state.json`, and `cluster.log`; must not silently abandon claims or mutate media/publish state |
| Worker start | `/api/network/worker/start-dry-run`, `/api/network/worker/start` | Network / backend dispatcher | `none`, then `backend-lifecycle` | Must claim only coordinator-assigned work one file at a time; must not scan local queue or use normal Launch |
| Worker stop | `/api/network/worker/stop-dry-run`, `/api/network/worker/stop` | Network / backend dispatcher | `none`, then `backend-lifecycle` | Must preserve pending done reports and worker state; abort and scratch partial cleanup remain separate explicit commands |

---

## Worker Claim Protocol

The coordinator HTTP server advertises Network protocol version `2`. The
version bump is additive: older workers may continue to consume `source_path`,
and newer workers prefer the library-relative fields when present.

`GET /api/claim` returns `ClaimResponse` with these path-authority fields:

| Field | Requirement |
|---|---|
| `source_path` | Required compatibility field containing the coordinator-visible absolute source path |
| `library_id` | Optional additive field identifying the configured library that owns the source |
| `relative_path` | Optional additive field containing the safe path under `library_id`'s source root |

Worker resolution order is:

1. If both `library_id` and a safe `relative_path` are present and the worker
   has a matching local library source root, resolve `worker.library_root(library_id) +
   relative_path`.
2. Otherwise apply the effective source path map, including coordinator-advertised
   library auto-maps and manual `WorkerSourcePathMap` overrides.
3. Otherwise use `source_path` unchanged.

The worker must reject unsafe relative claim paths, including absolute paths,
drive-qualified paths, and any `..` traversal segment. Falling back from absent
or unusable additive fields is expected for mixed-version clusters.

---

## Validation Gates

Current static/unit gates:

- `tests/python/desktop/test_api_contract_payload.py` verifies route exposure, dry-run schemas, rollback journal fields, source-file policy, and deep-copy behavior.
- `tests/python/desktop/test_api_command_contracts.py` verifies strict payload contracts for all eight Network lifecycle POST routes.
- `tests/python/desktop/test_application_facade_process_launch.py` verifies normal Launch blocks network modes and Network dry-runs are no-touch/provider-guarded.
- `tests/webview/test_webview_network_read_only_boundary.py` verifies Network controls call only documented backend lifecycle routes and keep future controls disabled.
- Route inventories and ownership maps list every Network lifecycle route.

Remaining implementation gates before real distributed processing is complete:

- Wire the real coordinator lifecycle provider and worker polling provider into the Local API facade.
- Add duplicate-start/stop tests, provider active-state tests, command-journal success/failure tests, process cleanup/orphan tests, and source/scratch/output/pending-publish hash checks.
- Add integration coverage proving coordinator-only does not process local files, worker-only claims only coordinator-assigned files, coordinator-local work starts only through Network lifecycle, and done-report/final-acceptance evidence is coordinator-owned.
