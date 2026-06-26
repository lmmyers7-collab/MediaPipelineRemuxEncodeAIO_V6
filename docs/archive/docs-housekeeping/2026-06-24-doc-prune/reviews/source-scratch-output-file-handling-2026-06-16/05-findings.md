# Findings

## F-001: Stale Partial Cleanup Can Delete User-Owned Files Under Output Roots

Severity: High

Status: Open

Affected files:

- `ops/pipeline/entrypoints/MediaPipeline.ps1:481-486`
- `ops/pipeline/engine/storage/disk.ps1:672-728`
- `ops/pipeline/tests/Legacy/Invoke-LegacyDesktopReliabilityRegressionChecks.ps1:1825-1881`

### Issue

Pipeline startup invokes stale partial cleanup for `LocalEncoded` and `Outsource` roots (`ops/pipeline/entrypoints/MediaPipeline.ps1:481-486`). `Clear-StalePartialFiles` then recursively scans each root and deletes any old file whose leaf matches:

- `*.mp-partial*`
- `*.mp-publish-partial.*`
- `*.mp-publish-backup.*`

The deletion path checks that the candidate is inside the cleanup root (`ops/pipeline/engine/storage/disk.ps1:690-705`), but it does not prove that the file was created by the pipeline, is inside `.mediapipeline-staging`, is associated with a live transaction, or has a pipeline-owned marker. Because `LocalEncoded` and `Outsource` can contain user-visible output files, a legitimate old output whose name happens to match one of those patterns can be deleted.

The existing regression test validates the broad deletion behavior by creating and expecting deletion of `movie.mkv.mp-partial.old` under the root (`ops/pipeline/tests/Legacy/Invoke-LegacyDesktopReliabilityRegressionChecks.ps1:1852-1874`). It does not test provenance-aware preservation.

### Reproduction Path

1. Configure a local `LocalEncoded` or `Outsource` root.
2. Create a legitimate user-owned file under that root with a matching name, for example `Movie.mp-partial-cut.mkv` or `Movie.mkv.mp-publish-backup.notes`.
3. Set its last-write time older than `CleanupStaleAgeHours`.
4. Start the pipeline or invoke `Clear-StalePartialFiles -Roots @($Outsource)` with cleanup enabled.
5. Observe that the file is deleted even though it was not proven to be a pipeline partial or backup.

If the root is UNC, the same risk applies when `CleanupRemoteStaging` is enabled; otherwise UNC roots are skipped at `ops/pipeline/engine/storage/disk.ps1:679-681`.

### Impact

This is an output-root data-loss risk. It does not mutate original source media, but it can delete user-owned output or adjacent files in configured output roots based only on age and filename pattern.

### Missing Tests

- A stale-cleanup test proving user-owned old matching filenames under `LocalEncoded` and `Outsource` are preserved.
- A stale-cleanup test proving deletion is limited to pipeline-owned staging/transaction artifacts.
- A UNC variant proving remote roots are skipped unless explicitly enabled, and that enabling remote cleanup still requires pipeline provenance.

### Rollback Requirements

- Restore deleted files from backup, snapshot, or source-of-truth output copy.
- If cleanup ran on a remote root, inspect server-side recycle/snapshot capabilities before additional pipeline runs.
- Disable stale cleanup or remote stale cleanup until provenance-aware deletion is implemented.

### Validation Requirements

- Add tests that fail with the current broad pattern delete behavior.
- Implement provenance-aware cleanup, then rerun the stale cleanup regression suite.
- Validate that legitimate matching filenames are preserved and real pipeline partials/backups are still cleaned.

### Remediation Direction

Prefer one of these approaches:

- Restrict stale file deletion to `.mediapipeline-staging` directories and exact pipeline-generated transaction paths.
- Add transaction/provenance markers for publish partials/backups and delete only files with matching markers.
- Require generated partial filenames to include a constrained transaction identifier and validate the full shape before deletion.

Boundary checks alone are not sufficient because the root itself is intentionally broad.

## F-002: Low-Space and Pre-Attempt Stop Paths Can Leave Empty `.mediapipeline-staging` Directories

Severity: Low

Status: Open

Affected files:

- `ops/pipeline/engine/storage/disk.ps1:446-491`
- `ops/pipeline/engine/storage/disk.ps1:504-512`
- `ops/pipeline/tests/Legacy/Invoke-LegacyDesktopReliabilityRegressionChecks.ps1:1912-1956`

### Issue

`Copy-FileRobocopy` creates the destination directory and staging root before free-space preflight (`ops/pipeline/engine/storage/disk.ps1:446-448`). It defines a cleanup closure at `ops/pipeline/engine/storage/disk.ps1:448-457`.

The unknown-space branch calls the cleanup closure before returning (`ops/pipeline/engine/storage/disk.ps1:459-482`), and the existing regression test verifies that behavior (`ops/pipeline/tests/Legacy/Invoke-LegacyDesktopReliabilityRegressionChecks.ps1:1939-1950`).

The low-space branch returns without calling the cleanup closure (`ops/pipeline/engine/storage/disk.ps1:483-491`). The post-preflight stop-request branch also returns without calling it (`ops/pipeline/engine/storage/disk.ps1:504-512`). Both paths can leave an empty `.mediapipeline-staging` directory even though no copy attempt occurred.

### Reproduction Path

1. Configure a trusted local destination root.
2. Stub or arrange `Get-FreeSpaceGBAny` to return a value below the required copy threshold.
3. Invoke `Copy-FileRobocopy` for a destination under that root.
4. Observe the false result with `Reason = OUTPUT_DESTINATION_LOW_SPACE`.
5. Observe that the destination's `.mediapipeline-staging` directory can remain.

A second variant is to trigger stop requested after staging-root creation and before the first copy attempt.

### Impact

This is residue rather than data loss. It can clutter output roots, confuse diagnostics, and create extra work for later stale-cleanup passes. It is low severity because the directory is empty and bounded to the destination root.

### Missing Tests

- Low-space preflight should assert that `.mediapipeline-staging` is removed when empty.
- Stop-request-before-attempt should assert that `.mediapipeline-staging` is removed when empty.
- Existing unknown-space cleanup coverage should remain.

### Rollback Requirements

- Manually remove empty `.mediapipeline-staging` directories after confirming they contain no active transaction directories.
- Do not delete non-empty staging directories without transaction-age and activity checks.

### Validation Requirements

- Add unit/regression tests for low-space and stop-request branches.
- Verify all pre-attempt returns call a common empty-staging cleanup routine.
- Rerun copy preflight tests and a normal successful copy test to ensure staging cleanup does not race active copies.

### Remediation Direction

Call the existing cleanup closure before every pre-attempt return after staging-root creation, including the low-space branch and the stop-request branch.
