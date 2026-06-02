# Repair/Reconcile Mutation Contract

Date: 2026-05-19

This is the source-of-truth design contract for future Completed and Pending Publish repair/reconcile commands. It does not authorize implementation by itself. V6 currently has no repair/reconcile mutation routes and no WebView repair/reconcile buttons.

The WebView may display these boundaries from `/api/contract`, but it must not infer or perform repair, reconcile, manifest rewrite, payload move/delete, output acceptance, drain, publish, rerun, or source-file actions.

---

## Current Status

- `/api/contract` publishes `repair_reconcile_summary.status=design_only_no_mutation_routes`.
- Every repair/reconcile contract has `mutation_enabled=false` and `frontend_allowed=false`.
- No POST route in `LOCAL_API_ROUTE_CONTRACT` may include repair/reconcile/reconciliation semantics while this status remains design-only.
- `GET /api/publish-reconciliation` remains read-only evidence. It correlates Completed, Pending Publish, and durable drain-summary proof; it does not repair or publish.

---

## Required Future Flow

Any future repair/reconcile capability must ship in this order:

1. Backend dry-run route with `effect=none`.
2. Backend tests proving the dry-run returns `dry_run_only=true`, exact scope, precondition results, path allowlist evidence, diff summary, and `would_not_touch` source/payload/output evidence.
3. Backend mutation route only after backup, rollback, atomic-write or verified-move semantics, and command journal evidence are tested.
4. WebView control only after route inventory, command ownership, browser/static mutation-boundary coverage, and DOC_TOUCH_LOG updates exist.

The frontend must never construct filesystem paths or author media policy. All paths, row scope, safety posture, and diffs must come from backend state.

---

## Published Contract Fields

Each `repair_reconcile_contracts[]` item in `/api/contract` must include:

| Field | Requirement |
|---|---|
| `current_status` | `design_only_no_route` until a backend route exists |
| `mutation_enabled` | `false` until mutation route tests pass |
| `frontend_allowed` | `false` until a backend route, evidence panel, command history, and browser/static coverage exist |
| `dry_run_contract` | Defines a future no-mutation result schema and required result fields |
| `rollback_contract` | Defines backup, rollback, and journal evidence expected before any mutation route |
| `source_file_policy` | Keeps source media mutation/delete/rename forbidden and path authority backend-owned |
| `route_exposure_gates` | Lists the inventory/test/doc gates required before WebView exposure |
| `must_not` | Explicitly forbids unsafe behavior for the surface |

The required dry-run result fields are:

`schema_version`, `candidate_command`, `dry_run_only`, `scope`, `selected_row_keys`, `precondition_results`, `diff_summary`, `would_write_paths`, `would_move_paths`, `would_delete_paths`, `would_not_touch`, `safe_to_apply`, and `operator_confirmation_scope`.

---

## Surface Contracts

| Surface | Candidate command | Current authority | Mutation class | Hard boundary |
|---|---|---|---|---|
| Completed manifest reconciliation | `completed.reconcile_manifest` | Completed / Maintenance | Manifest write | Must not mark media complete without output/sidecar evidence or touch source/output/scratch files |
| Completed sidecar metadata repair | `completed.repair_sidecar_metadata` | Completed / Rename | Sidecar JSON write | Must not rewrite arbitrary frontend-provided JSON paths, rename media, or override route/audio/subtitle policy |
| Pending Publish manifest repair | `pending_publish.repair_manifest` | Pending Publish | Pending manifest write | Must not move parked payloads, drain/publish, delete orphan payloads, or trust frontend paths |
| Orphan pending payload reconciliation | `pending_publish.reconcile_orphan_payloads` | Pending Publish | Filesystem move/copy/delete risk | Must not delete payloads as cleanup, overwrite output, publish ambiguous proof, or run from WebView-only logic |

---

## Validation Gates

Current static gates:

- `DesktopApp/tests/test_api_contract_payload.py` verifies the design-only contract payload, dry-run schema fields, rollback journal fields, source-file policy, route exposure gates, and deep-copy behavior.
- `DesktopApp/tests/test_webview_frontend_mutation_boundary.py` rejects repair/reconcile POST route exposure, repair/reconcile `apiPost(...)` calls, and missing Contract page guardrail text.
- `DesktopApp/tests/test_application_facade_local_api.py` verifies the live Local API contract exposes the same design-only dry-run/rollback/source-policy fields.

Future implementation must add route-level negative tests, command-journal tests, rollback failure tests, browser no-mutation tests, and source/payload/output hash checks before any control is considered daily-driver safe.
