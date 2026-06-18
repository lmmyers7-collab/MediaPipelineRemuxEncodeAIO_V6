# Test Coverage Review

## Existing Coverage

PowerShell path and copy boundaries:

- `ops/pipeline/tests/Unit/Invoke-PathBoundaryGuardChecks.ps1:217-238` verifies `Copy-FileRobocopy` rejects a destination outside configured roots and does not create the destination parent.
- `ops/pipeline/tests/Legacy/Invoke-LegacyDesktopReliabilityRegressionChecks.ps1:1912-1956` verifies unknown-space preflight fails closed and leaves no `.mediapipeline-staging` directory.

Stale cleanup:

- `ops/pipeline/tests/Legacy/Invoke-LegacyDesktopReliabilityRegressionChecks.ps1:1825-1881` verifies `Clear-StalePartialFiles` deletes an old matching `*.mp-partial*` file, keeps fresh matching files, keeps unrelated old temp names, and removes old `.mediapipeline-staging` directories.

Pending publish and sidecars:

- `ops/pipeline/tests/Legacy/Invoke-LegacyDesktopReliabilityRegressionChecks.ps1:4904-5014` covers pending park success and sidecar failure cleanup.
- `ops/pipeline/tests/Unit/Invoke-PendingPublishSafetyChecks.ps1:285-328` covers pending park transaction success.
- `ops/pipeline/tests/Unit/Invoke-PendingPublishSafetyChecks.ps1:637-679` covers fail-closed behavior when final sidecar backup fails.
- `ops/pipeline/tests/Unit/Invoke-PendingPublishSafetyChecks.ps1:681-720` covers pending sidecar copy failure restoring the existing sidecar and removing backup residue.
- `ops/pipeline/tests/Unit/Invoke-PendingPublishSafetyChecks.ps1:729-741` provides static safety assertions for publish completion and pending drain paths.

Python final-library promotion:

- `tests/python/desktop/test_final_library_promotion.py:426-542` covers outside-outsource and missing-destination blocking.
- `tests/python/desktop/test_final_library_promotion.py:685-833` covers sidecar conflict and verification rollback.
- `tests/python/desktop/test_final_library_promotion.py:858-992` covers transfer temp cleanup and overwrite cases.
- `tests/python/desktop/test_final_library_promotion.py:1013-1085` covers cleanup boundaries, root preservation, sibling-prefix rejection, empty parent cleanup, and outside-publish-root planning rejection.

Python path layout:

- `tests/python/desktop/test_service_path_layout.py:48-55` verifies sibling-prefix rejection.
- `tests/python/desktop/test_service_path_layout.py:71-83` covers outside-root, root-target, and missing-leaf cases.
- `tests/python/desktop/test_service_path_layout.py:97-121` covers symlink/junction reparse rejection.

Rename source mutation:

- `tests/python/desktop/test_application_facade_rename.py` covers outside configured-root preview/apply requiring explicit confirmation.
- `tests/python/desktop/test_service_rename_apply.py` covers undo manifest root rejection and rollback ordering.

## Coverage Gaps

G-001: No test proves stale partial cleanup preserves user-owned files whose names match the cleanup patterns.

- Existing coverage asserts the broad deletion behavior works.
- Missing: a fixture under `LocalEncoded` or `Outsource` with an old legitimate filename containing `.mp-partial`, `.mp-publish-partial.`, or `.mp-publish-backup.` that must be preserved unless accompanied by pipeline provenance.
- Related finding: F-001.

G-002: No low-space staging cleanup test exists for `Copy-FileRobocopy`.

- Existing coverage tests unknown free-space cleanup.
- Missing: low-space free-space result should also remove the empty staging root created before the preflight return.
- Related finding: F-002.

G-003: No stop-request-after-staging test exists for `Copy-FileRobocopy`.

- The stop-request branch after preflight returns before any attempt and does not call staging-root cleanup.
- Missing: a test that simulates stop requested after staging root creation and asserts no empty staging root remains.
- Related finding: F-002.

G-004: Publish helper-level boundaries are mostly covered through call-path behavior, not direct helper misuse tests.

- Missing: direct tests for partial/sidecar helper calls with malformed or outside-root paths, or explicit helper-local assertions where feasible.
- This is a hardening gap rather than an active bug in reviewed call paths.

G-005: Failure artifact capture lacks a targeted boundary test at the move/delete point.

- Existing state layout makes artifact paths generated and local to `LocalBase`.
- Missing: direct test proving failure artifact replacement cannot delete outside state failure artifacts if state input is malformed.
