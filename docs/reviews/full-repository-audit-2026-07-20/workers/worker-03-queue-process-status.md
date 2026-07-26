# Worker 03 — Queue, Process, Schedule, and Status

Status: **first-pass complete; independent review pending**.

## Coverage

- Assigned baseline: **317 paths** at the current coverage-matrix hashes.
- Terminal first-pass rows: **317/317**, all unique, with no missing or extra paths and no current-byte hash mismatches.
- Exact source review: **138 first-party executable files** — 120 Python and 18 PowerShell.
- Generated provenance review: **179 generated summaries**; every embedded source path existed and every embedded source SHA-256 matched current exact source bytes.
- Review outcomes: 179 `generated_verified`, 122 `line_reviewed_no_findings`, and 16 `line_reviewed_with_findings`.
- Second review: **317 pending**. No high-risk row is represented as independently attested by its first-pass reviewer.

The review mapped discovery, queue preview/plan/runtime parity, accepted-run scope, priority and claim authority, worker results, duplicate guards, durable lifecycle state, schedule persistence and stop watching, close readiness, progress/status evidence, recovery, PowerShell process boundaries, routes, commands, state/config keys, artifacts, and matching tests. Generated summaries were used only for orientation; source conclusions came from exact current bytes, complete Python AST/function catalogs, PowerShell function catalogs/parser checks, and targeted numbered reads of failure and mutation paths.

## Findings

The W03 fragment contains **15 findings**: 5 P1, 9 P2, and 1 P3. Fourteen are confirmed; W03-011 remains `needs-runtime-proof` for the priority-manifest read race.

1. `AUDIT-FIND-W03-001` (P1): same-cwd/contradictory-command PID reuse can authorize killing an unrelated process tree.
2. `AUDIT-FIND-W03-002` (P2): lifecycle leases use recyclable PID liveness without durable launch identity.
3. `AUDIT-FIND-W03-003` (P2): retained priority-marker compatibility helpers rename and retimestamp source media without a named safety policy.
4. `AUDIT-FIND-W03-004` (P2): descendant `os.walk` failures are silently skipped while source inventory reports complete.
5. `AUDIT-FIND-W03-005` (P2): stale parsed FFmpeg fields can remain presented as loaded during Idle.
6. `AUDIT-FIND-W03-006` (P2): malformed progress JSON is represented as persistence healthy and can evade autonomy blocking.
7. `AUDIT-FIND-W03-007` (P1): unreadable/corrupt worker-claim state becomes an empty store, reopening duplicate claims.
8. `AUDIT-FIND-W03-008` (P1): a route-planning exception after naming can still emit an accepted runnable row with empty route identity.
9. `AUDIT-FIND-W03-009` (P1): pending-publish enumeration failure becomes a zero, unblocked backlog.
10. `AUDIT-FIND-W03-010` (P2): production accepted rows omit `intended_final_path` even though parity fingerprints consume it.
11. `AUDIT-FIND-W03-011` (P2): phase planning re-reads priority authority without fail-closed semantics after discovery validated it.
12. `AUDIT-FIND-W03-012` (P3): a throwing Run Monitor completion hook skips restoration of script-scoped job identity.
13. `AUDIT-FIND-W03-013` (P2): wrong-schema/non-object network-rerun state is silently ignored by close readiness.
14. `AUDIT-FIND-W03-014` (P2): a confirmed schedule save over corrupt app state overwrites unrelated machine/authentication state.
15. `AUDIT-FIND-W03-015` (P1): empty pipeline progress takes precedence over a running audit snapshot, allowing `safe_to_close=True`; the existing focused test fails deterministically.

Exact SR-010 reconciliation passed: every reviewed path carries exactly the IDs of current findings located on that path, including the pre-existing `AUDIT-FIND-DEP-001` on `preflight_facade.py`.

## Project-index reconciliation

- 133 source rows matched the generated project-index hash.
- 3 stale index rows have path-local findings: `snapshot_rows.ps1`, `preflight_facade.py`, and `queue/service.py`.
- 2 stale index rows have no current path-local finding and remain `stale_unreconciled`: `processes/pipeline_facade.py` and `queue/facade.py`.
- 179 generated summaries are explicitly `not_indexed_with_rationale` rather than treated as project-index authority.

## Validation

- Exact W03 fragment validation: 317 assigned / 317 unique terminal rows; no missing paths, extras, unsupported fields, hash mismatches, invalid IDs, or path-local finding-set differences.
- Finding/error schema validation: all 15 W03 finding records and all 30 W03 error records are valid and uniquely identified; no W03 error remains coverage-blocking.
- PowerShell parser pass: all 18 assigned `.ps1` files parsed with zero parser errors.
- Focused Python rung: **110 passed, 1 failed, 26 subtests passed**. The sole failure is the deterministic close-readiness defect recorded as W03-015; an isolated rerun failed identically.
- `Invoke-LocalWorkerSlotChecks.ps1`: passed.
- `Invoke-RunMonitorStateChecks.ps1`: passed.
- `Invoke-ProgressStateTelemetryChecks.ps1`: passed.
- `Invoke-PipelineQueueEngineChecks.ps1`: passed in 180.1 seconds when rerun alone.

The error fragment records **30 events**: 17 environment/setup issues, 7 informational warnings, 4 expected negative-path results, and 2 test-failure records for the grouped and isolated reproductions of W03-015. A timed-out parallel PowerShell wrapper was identity-checked and its orphaned queue-engine test process was terminated; all four checks were then run individually.

## Remaining work and boundaries

- All 317 rows require an independent reviewer before `second_review_status` can advance from `pending`.
- W03-011 needs a deterministic concurrent manifest-change/failure fixture to convert its runtime-race analysis to confirmed or rejected.
- W03-010 affects destination-routing evidence; representative real-media validation is advisable for a future remediation, but real media was not required or mutated for this read-only audit.
- Four current untracked same-domain files were absent from the frozen assignment and were not silently added: `ops/pipeline/engine/status/run_monitor_contract.ps1`, `ops/pipeline/engine/status/run_monitor_persistence.ps1`, `src/mediapipeline/core/processes/rerun_results_network_projection.py`, and `src/mediapipeline/core/queue/priority_export.py`.
- No product source, generated map, queue/state file, or media was edited. No change packet was created because the authorized work was confined to audit fragments and the worker report.
