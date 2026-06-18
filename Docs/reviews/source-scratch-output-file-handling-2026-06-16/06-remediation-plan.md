# Remediation Plan

This is a proposed plan only. No source code was changed by this review.

## Priority 1: Make Stale Cleanup Provenance-Aware

Addresses: F-001

1. Add failing tests first:
   - Old user-owned matching filenames under `LocalEncoded` are preserved.
   - Old user-owned matching filenames under `Outsource` are preserved.
   - Old pipeline-owned partials/backups are still removed.
   - UNC roots remain skipped unless `CleanupRemoteStaging` is enabled.
2. Replace broad root-recursive pattern deletion with provenance-aware deletion:
   - Prefer deleting only under `.mediapipeline-staging`.
   - For publish partials/backups outside staging, require exact transaction-generated shape plus a matching marker or manifest.
   - Avoid deleting based only on filename pattern and age under broad output roots.
3. Keep candidate boundary checks, but treat them as necessary, not sufficient.
4. Update the existing legacy stale-cleanup test so it no longer asserts broad deletion of arbitrary matching filenames.
5. Add rollback guidance to operator docs if stale cleanup previously ran on broad roots.

Validation gate:

- Stale cleanup preserves user-owned matching filenames.
- Stale cleanup removes only confirmed pipeline-owned stale artifacts.
- No source media roots are ever passed as cleanup roots.

## Priority 2: Clean Empty Staging Roots on All Pre-Attempt Returns

Addresses: F-002

1. Add failing tests for:
   - Low-space preflight leaves no empty `.mediapipeline-staging`.
   - Stop-request-before-attempt leaves no empty `.mediapipeline-staging`.
2. Call the existing staging-root cleanup closure before those returns.
3. Keep cleanup conservative: remove only empty staging roots.
4. Rerun unknown-space preflight test to avoid regression.

Validation gate:

- Unknown-space, low-space, and pre-attempt stop all leave no empty staging root.
- Successful copy and failed copy with active staging transaction behavior is unchanged.

## Priority 3: Harden Helper-Level Boundaries

Addresses: coverage gaps G-004 and G-005

1. Add local boundary assertions to publish helper functions that currently rely on caller trust where practical.
2. Add direct tests for malformed helper inputs:
   - Publish partial path outside matched destination root.
   - Sidecar target outside destination root.
   - Pending manifest paths with sibling-prefix escapes.
3. Add an explicit artifact-root guard before failure artifact replacement/deletion.

Validation gate:

- Helper misuse fails closed.
- Existing valid publish and failure-artifact paths still pass.

## Priority 4: Preserve Rename Source-Mutation Gates

Addresses: source mutation safety

1. Keep rename apply as an explicit user-command path only.
2. Keep outside-root confirmation mandatory.
3. Keep undo manifest root validation and rollback tests.
4. Add a regression that background/process workflows cannot invoke rename apply implicitly.

Validation gate:

- No automated encode/remux/publish path can rename, move, overwrite, or delete original source files.

## Operational Rollout

1. Land tests for F-001 and F-002 before source changes.
2. Implement F-002 first because it is narrow and low risk.
3. Implement F-001 behind conservative behavior: preserve more files rather than delete uncertain candidates.
4. Run targeted PowerShell tests, Python path/final-library tests, and strict change-control validation.
5. Manually inspect any output roots used during testing before and after cleanup tests.
