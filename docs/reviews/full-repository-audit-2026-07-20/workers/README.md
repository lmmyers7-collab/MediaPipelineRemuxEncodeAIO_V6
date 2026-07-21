# Worker Ledgers

Each worker owns one non-overlapping slice from `../COVERAGE_MATRIX.jsonl`. Worker ledgers record semantic review progress and candidate findings; the coordinator alone merges terminal coverage and deduplicates findings.

Workers must not claim a file complete from its generated summary, grep results, test pass, or prior audit status. Exact current source must be reviewed. High-risk files require an independent second reviewer.

## Evidence contract

- Bind every row to the current `content_sha256`, assigned worker, category-compatible status, and all applicable `verified_obligations`.
- Use a canonical `/root/...` reviewer identity. First-pass rows keep `second_review_status: pending`; the coordinator derives completion only from a distinct current-hash attestation.
- For every achieved row, `finding_ids` must exactly equal all current finding records located on that path under the Windows case-insensitive identity model. Do not omit cross-worker or prior-audit findings, and do not attach a finding merely because it is related elsewhere.
- Record every failed command, stderr-bearing false success, missing prerequisite, truncation, skip, and expected negative-path result in the worker error fragment before correction or retry.
- Log semantic sections, dependencies, routes, commands, state/config/process boundaries, artifacts, relevant tests, prior-audit reconciliation, and meaningful evidence commands. Inventory metadata alone is never semantic proof.
- Validate worker finding and error fragments before review rows, then validate first-pass rows and independent attestations through the current audit-ledger implementation. Only the coordinator writes central coverage, finding, and error mirrors.
