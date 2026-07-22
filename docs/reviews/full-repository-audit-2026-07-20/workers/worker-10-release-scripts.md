# Worker 10 Release-Script Review

Date: 2026-07-21  
Reviewed HEAD: `2494bea1fd6280f41bec3f56e21b8bd98dd20829`  
Reviewer: `/root/w10_release_scripts`

## Scope and result

All 23 tracked files under `ops/scripts/release/` were read completely at their exact current SHA-256 identities after their generated summaries and the release no-touch boundary were read. The slice contains 5,966 physical lines.

- 23/23 files have terminal first-pass line-review rows.
- 7 files are `line_reviewed_no_findings`.
- 16 files are `line_reviewed_with_findings`.
- The review fragment validates with zero schema, hash, ownership, finding-location, or error-reference issues.
- Independent second review remains pending for release-critical paths and P1 findings.

The authoritative machine-readable rows are in `worker-10-release-scripts-review.jsonl`. Exact finding evidence remains in `worker-10-ops-workflows-findings.jsonl`; command failures remain in the worker/coordinator error fragments.

## Confirmed findings

- `AUDIT-FIND-W10-016` (P1): a schema-only marker authorizes recursive replacement of a selected release directory.
- `AUDIT-FIND-W10-017` (P2): package verification validates supplied manifest entries but not exact package-file-set equality.
- `AUDIT-FIND-W10-018` (P2): private-beta verification can approve an unrelated successful run or wrong-version installer.
- `AUDIT-FIND-W10-019` (P2): portable packages attribute live worktree bytes to HEAD without clean/dirty provenance.
- `AUDIT-FIND-W10-020` (P1): the current canonical release gate rejects the valid machine-readable test inventory's serialized Windows path fixture.

Existing cross-file findings `W10-002`, `W10-011`, `W10-012`, and `W10-013` were extended to every affected release-script location rather than duplicated.

## Validation evidence

- PowerShell AST parsing covered all 23 scripts with zero parser findings.
- Thirteen focused release/private-beta Python modules completed with 45 tests passing.
- The test-suite subsystem inventory check returned `ok=true`, 528 assertion lines, and zero findings.
- Its focused test module completed with 19 tests and five subtests passing.
- The canonical `Invoke-ReleasePackagePolicyChecks.ps1` gate exited 1 at the builder dry-run because of `AUDIT-FIND-W10-020`; this non-green result is preserved as `AUDIT-ERR-COORD-126`.
- A bounded disposable fake-repository fixture reproduced `AUDIT-FIND-W10-016`; temporary files were validated, removed, and verified absent.

No application source, release implementation, generated artifact, external service, or real media was modified.
