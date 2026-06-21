# Repair/Reconcile Mutation Contract

Date: 2026-06-20

This is the source-of-truth contract for Completed and Pending Publish repair/reconcile commands. The current workspace has backend dry-run routes plus confirmed apply routes for selected Completed/Pending repairs. Startup reconciliation remains dry-run only. The WebView now exposes selected-row Pending Publish manifest repair, Pending Publish orphan-payload reconciliation, Completed manifest reconciliation, and Completed sidecar metadata repair dry-run/apply controls with backend-owned fingerprint gating. Orphan-payload reconcile can create only the missing payload-adjacent pending manifest when backend dry-run evidence supplies a complete validated backend-derived `pending_push_manifest.v1` proposal; ordinary orphan rows remain blocked.

The WebView may display these boundaries from `/api/contract`, but it must not infer or perform repair, reconcile, manifest rewrite, payload move/delete, output acceptance, drain, publish, rerun, or source-file actions.

---

## Current Status

- `/api/contract` publishes `repair_reconcile_summary.status=backend_dry_run_and_confirmed_apply_routes_available_startup_dry_run_only`.
- Completed/Pending repair contracts have `current_status=backend_dry_run_and_confirmed_apply_routes_available`, a `dry_run_route`, an `apply_route`, `mutation_enabled=true`, and `frontend_allowed=true`.
- Startup reconciliation has `current_status=backend_dry_run_route_available`, `mutation_enabled=false`, and no apply route.
- Four token-authenticated POST dry-run routes exist with `effect=none`, `suppress_command_journal=true`, and a stable `dry_run_fingerprint`:
  - `POST /api/completed/reconcile-manifest-dry-run`
  - `POST /api/completed/repair-sidecar-metadata-dry-run`
  - `POST /api/pending-publish/repair-manifest-dry-run`
  - `POST /api/pending-publish/reconcile-orphan-payloads-dry-run`
- Four token-authenticated confirmed apply routes rerun the backend dry-run, require matching `dry_run_fingerprint` and `confirm_apply=true`, and are command-journaled:
  - `POST /api/completed/reconcile-manifest`
  - `POST /api/completed/repair-sidecar-metadata`
  - `POST /api/pending-publish/repair-manifest`
  - `POST /api/pending-publish/reconcile-orphan-payloads`
- Completed apply routes back up and atomically rewrite selected manifest/sidecar state. Pending manifest repair can back up and atomically rewrite selected backend-validated manifest-normalization candidates; orphan-payload reconcile can create the missing payload-adjacent manifest only from a complete backend-derived `pending_push_manifest.v1` proposal and otherwise blocks.
- `GET /api/publish-reconciliation` remains read-only evidence. It correlates Completed, Pending Publish, and durable drain-summary proof; it does not repair or publish.
- Pending Publish WebView selected-row manifest repair and orphan-payload reconcile controls plus Completed selected-row manifest/sidecar repair controls post only `scope`, `row_key`, `limit`, `reason`, `dry_run_fingerprint`, and `confirm_apply=true`; they do not send client paths, patches, sidecar JSON, raw manifests, drain/publish requests, move/delete requests, or source-media actions.

---

## Required Flow

Repair/reconcile capability must follow this order:

1. Backend dry-run route with `effect=none`.
2. Backend tests proving the dry-run returns `dry_run_only=true`, exact scope, precondition results, path allowlist evidence, diff summary, `dry_run_fingerprint`, `suppress_command_journal=true`, and `would_not_touch` source/payload/output evidence.
3. Backend confirmed apply route only after backup, rollback, atomic-write semantics, fingerprint matching, confirmation, and command journal evidence are tested.
4. WebView control only after route inventory, command ownership, browser/static mutation-boundary coverage, and change-control evidence exist.

The frontend must never construct filesystem paths or author media policy. All paths, row scope, safety posture, and diffs must come from backend state.

---

## Published Contract Fields

Each `repair_reconcile_contracts[]` item in `/api/contract` must include:

| Field | Requirement |
|---|---|
| `current_status` | `backend_dry_run_and_confirmed_apply_routes_available` for Completed/Pending apply surfaces; `backend_dry_run_route_available` for startup reconciliation |
| `dry_run_route` | The backend-only `effect=none` route for the candidate command |
| `apply_route` | Present only for Completed/Pending confirmed apply routes |
| `mutation_enabled` | `true` for Completed/Pending apply surfaces; `false` for startup reconciliation |
| `frontend_allowed` | `true` for backend-owned Completed/Pending apply surfaces; `false` for startup reconciliation |
| `dry_run_contract` | Defines the no-mutation result schema and required result fields |
| `apply_contract` | Defines request/result fields for fingerprint-gated confirmed apply routes |
| `rollback_contract` | Defines backup, rollback, and journal evidence expected for mutation routes |
| `source_file_policy` | Keeps source media mutation/delete/rename forbidden and path authority backend-owned |
| `route_exposure_gates` | Lists the inventory/test/doc gates required before WebView exposure |
| `must_not` | Explicitly forbids unsafe behavior for the surface |

The required dry-run result fields are:

`schema_version`, `candidate_command`, `dry_run_only`, `effect`, `scope`, `selected_row_keys`, `precondition_results`, `diff_summary`, `would_write_paths`, `would_move_paths`, `would_delete_paths`, `would_not_touch`, `safe_to_apply`, `mutation_route_available`, `apply_route_available`, `dry_run_fingerprint`, `operator_confirmation_scope`, and `suppress_command_journal`.

The required apply result fields are:

`schema_version`, `candidate_command`, `effect`, `selected_row_keys`, `applied`, `blocked`, `written_paths`, `backup_paths`, `transaction_id`, `rollback_status`, `dry_run_fingerprint`, `expected_dry_run_fingerprint`, and `source_payload_output_unchanged`.

---

## Surface Contracts

| Surface | Candidate command | Current authority | Mutation class | Hard boundary |
|---|---|---|---|---|
| Completed manifest reconciliation | `completed.reconcile_manifest` | Completed / Maintenance | Manifest write | Must not mark media complete without output/sidecar evidence or touch source/output/scratch files |
| Completed sidecar metadata repair | `completed.repair_sidecar_metadata` | Completed / Rename | Sidecar JSON write | Must not rewrite arbitrary frontend-provided JSON paths, rename media, or override route/audio/subtitle policy |
| Pending Publish manifest repair | `pending_publish.repair_manifest` | Pending Publish | Pending manifest write | Only backend-validated manifest-normalization candidates may write; must not move parked payloads, drain/publish, delete orphan payloads, or trust frontend paths |
| Orphan pending payload reconciliation | `pending_publish.reconcile_orphan_payloads` | Pending Publish | Pending orphan manifest write | Dry-run must list missing `pending_push_manifest.v1` evidence for ordinary orphan rows and may produce a candidate only from a complete backend-derived manifest proposal; apply creates only the missing payload-adjacent manifest and must not move/delete payloads, overwrite output, publish ambiguous proof, or run from WebView-only logic |

---

## Validation Gates

Current static gates:

- `tests/python/desktop/test_api_contract_payload.py` verifies the backend dry-run and confirmed apply contract payloads, route metadata, rollback journal fields, source-file policy, route exposure gates, and deep-copy behavior.
- `tests/python/desktop/test_api_command_contracts.py` verifies dry-run and confirmed apply request models accept only allowlisted fields and reject raw paths, patch bodies, sidecar JSON, and unknown fields.
- `tests/python/desktop/test_repair_reconcile_dry_run.py` verifies the four dry-run route builders return the required schema shape, block unsafe preconditions, suppress command journaling, and do not mutate fixture manifests, sidecars, payloads, outputs, or sources.
- `tests/python/desktop/test_repair_reconcile_apply.py` verifies confirmed apply fingerprint gating, backup/write behavior, strict payload validation, command journaling, and no frontend path acceptance.
- `tests/python/desktop/test_application_facade_local_api.py` verifies the live Local API contract exposes the same dry-run and confirmed apply fields.
- `ops/scripts/smoke/Test-LocalApiRepairReconcileDryRunContractSmoke.ps1` provides a browser-free smoke wrapper for the dry-run contract boundary.

The selected-row Pending Publish manifest repair and orphan-payload reconcile controls are covered by static mutation-boundary tests plus the Pending Publish browser smoke's bounded request-body assertions and no-media-mutation snapshot. Orphan-payload apply is still daily-driver unsafe until representative source/payload/output hash plus deferred publish/drain validation has been run against complete backend proposal evidence. The Completed selected-row manifest reconciliation and sidecar metadata repair controls are covered by static mutation-boundary tests plus the Completed/Pending proof browser smoke's no-media-mutation snapshot and bounded request-body assertions.
