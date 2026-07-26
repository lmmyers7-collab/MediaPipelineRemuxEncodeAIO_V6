# Worker 04 — Publish, Completed, and Rename

Assigned rows: **212**. First-pass status: **complete (212/212)**.

## Coverage

- Preserved and provenance-checked generated summaries: **125**.
- Current first-party source files reviewed at exact matrix hashes: **87**.
- Review depth for source: complete static semantic line review of every physical line, including imports, symbols, branches, exception behavior, state/config/process boundaries, callers, relevant tests, and path-local findings.
- Reviewer: `/root/w04_static_completion`.
- Change packet: `MP-CHANGE-2026-0720-011`.

The source slice covers PowerShell pending-publish park/drain, manifest/index, partial reveal, sidecar, completion, and repair behavior; Python completed-output proof/trust/presentation; final-library promotion planning, transfer, evidence, and lifecycle; pending-publish read/recovery/reconcile policy; and rename preview, planning, apply, undo, path authority, collision, and cleaning policy.

## Current findings

1. `AUDIT-FIND-W04-001` — P2 confirmed: proof-deferred completed rows still present `Healthy`, `consistent-looking`, and aggregate `ok` signals despite the correct `unverified` state.
2. `AUDIT-FIND-W04-002` — P2 confirmed: final-library `active_run.json` is write-only/best-effort, start is not gated on durable intent, and a terminal manifest-write failure can strand activity.
3. `AUDIT-FIND-W04-003` — P2 confirmed: second-resolution final-library run IDs can collide and overwrite run/item evidence.
4. `AUDIT-FIND-W04-004` — P1 confirmed: a rename undo that fails after one or more reversals has no per-operation checkpoint or compensation and cannot pass preflight on retry.
5. `AUDIT-FIND-W04-005` — P1 needs-runtime-proof: pending drain locks per manifest rather than canonical destination, allowing different manifests targeting one final path to enter conflicting reveal/verification/rollback sequences.
6. `AUDIT-FIND-W04-006` — P3 needs-runtime-proof: completed-manifest duplicate detection occurs before the cross-process append lock, leaving a check-then-append race.

Path-local current findings owned by other audit slices were also linked exactly: `AUDIT-FIND-W15-001`, `AUDIT-FIND-W15-002`, `CSW-2026-07-09-PENDING-003`, and `AUDIT-FIND-W14-001`.

## Audit errors and limitations

- W04 recorded **30** command/tool/evidence issues (`AUDIT-ERR-W04-001` through `AUDIT-ERR-W04-030`). Every record is closed for W04 and has `coverage_blocked=false`; the W04 error-fragment validator returned zero issues.
- `AUDIT-ERR-W04-028` reports an unrelated current global blocker: W03 record `AUDIT-ERR-W03-IR-008` uses the noncanonical classification `test infrastructure timeout`. W04 did not alter another worker's fragment.
- The assigned completion was static-only. No product execution, PowerShell media-engine run, real-media processing, disposable concurrency race, external system, network share, or source/product implementation edit was performed.
- Consequently, W04-005 and W04-006 remain explicitly `needs-runtime-proof`. W04-005 requires a controlled two-process disposable fixture and representative real-media park/drain validation before a final-placement-policy fix is released. W04-006 requires a controlled identical-transaction append race; real media is not required for that proof.

## Validation evidence

- All **87/87** current source SHA-256 hashes and physical line counts exactly matched `COVERAGE_MATRIX.csv`.
- `repository_audit_ledger.prepare_finding_records`: **120** current finding records, **0** issues after W04 publication.
- `repository_audit_ledger.review_fragment_findings`: **212** W04 records, exact matrix/path/hash/error/finding-location joins, **0** issues.
- `repository_audit_ledger.error_record_findings`: **30** W04 error records, **0** issues and **0** remaining coverage blocks.
- Exact fragment census: **125** `generated_provenance_check` rows plus **87** `complete_static_semantic_line_review` rows; no duplicate or missing assigned paths.
- Non-strict change-packet validation passed all **1,114** packets. Strict worktree coverage reported **27** uncovered shared-worktree paths, including W04's three new JSONL fragments and 24 unrelated/shared audit or generated-summary files; coordinator packet reconciliation remains pending.

No product test suite was run because the task prohibited product execution and made no implementation change. Independent second review remains coordinator-owned for the two P1 findings and their affected high-risk paths.
