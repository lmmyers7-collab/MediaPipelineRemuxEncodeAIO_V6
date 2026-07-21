# Worker 04 Independent Review Checkpoint

Status: partial independent review in progress.

## Completed path

- `ops/pipeline/engine/publish/pending_manifest_store.ps1`
  - Exact current SHA-256: `71fe395a741430a49d118ca0a63833b4ec4c7d14368713f2c0bfbfb2fb7286c8`.
  - Generated summary read before all 924 physical source lines.
  - Every manifest accessor, trust boundary, retry/repair/drain update, round-trip validator, and atomic-write branch reviewed.
  - Exact current finding set: `AUDIT-FIND-W15-001`, `AUDIT-FIND-W15-002`, and `AUDIT-FIND-W15-005`; all independently confirmed.

## New independent result

`AUDIT-FIND-W15-005` records a maintenance-contract contradiction. The writer comment says writable legacy manifests let existing parked jobs be recovered and drained, but the current trust validator rejects missing or non-v1 schema before either operation, and the focused safety fixture explicitly requires zero drain. Runtime behavior remains fail-closed; the defect is the inaccurate compatibility claim nearest the release-critical writer.

This checkpoint is not a W04 completion claim. The remaining high-risk W04 paths still require independent attestations.

## Generated high-risk batch

- 125 generated summaries were independently re-read byte-for-byte.
- Canonical regeneration check: 125/125 current, with no orphan summaries.
- 2,489 Markdown lines and 151,271 artifact bytes reconciled to 1,606,547 current source bytes.
- Exact artifact hashes, declared source hashes, summary schema, generator fingerprints, first-pass reviewers/statuses, and empty path-local finding sets all matched.

## Additional source attestations

- Four previously achieved publish-package paths were completely re-read and attested.
- `CSW-2026-07-09-PENDING-003` remains confirmed: ordinary orphan discovery still has no production proposal producer.
- `AUDIT-FIND-W04-004` was reproduced in a disposable two-operation undo: one reversal committed, the next failed, and retry was blocked by the resulting mixed layout.
- `AUDIT-FIND-W04-005` remains `needs-runtime-proof`: two distinct current manifest locks were acquired simultaneously for a shared stated destination, but the destructive two-process drain interleaving was not executed.
- Focused validation passed: 41 pending/recovery Python tests plus 3 subtests, 23 rename tests, Pending Publish Safety, and Pending Publish Transaction Fault Injection.
