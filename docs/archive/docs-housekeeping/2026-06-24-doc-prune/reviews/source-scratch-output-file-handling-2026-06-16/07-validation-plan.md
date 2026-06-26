# Validation Plan

This plan is for validating future fixes and for re-running the review gates. This review did not edit source code.

## Static Review Gates

1. Search for destructive operations:
   - `Remove-Item`
   - `Move-Item`
   - `Copy-Item`
   - `os.remove`
   - `Path.unlink`
   - `Path.rename`
   - `Path.replace`
   - `shutil.move`
   - `shutil.copy2`
2. For each operation, confirm:
   - Target is generated or user-approved.
   - Target is inside an approved boundary.
   - Root target deletion is rejected.
   - Reparse/junction targets are rejected where mutation is possible.
   - Failure cleanup cannot cross out of the intended root.

## Targeted PowerShell Tests

Run after adding remediation tests:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File ops/pipeline/tests/Unit/Invoke-PathBoundaryGuardChecks.ps1
pwsh -NoProfile -ExecutionPolicy Bypass -File ops/pipeline/tests/Unit/Invoke-PendingPublishSafetyChecks.ps1
pwsh -NoProfile -ExecutionPolicy Bypass -File ops/pipeline/tests/Legacy/Invoke-LegacyDesktopReliabilityRegressionChecks.ps1
```

Expected additions:

- Stale cleanup preserves old user-owned matching filenames under `LocalEncoded`.
- Stale cleanup preserves old user-owned matching filenames under `Outsource`.
- Stale cleanup removes only pipeline-owned stale partials/backups.
- Low-space preflight leaves no empty `.mediapipeline-staging`.
- Stop-request-before-attempt leaves no empty `.mediapipeline-staging`.

## Targeted Python Tests

Run after path/final-library/rename changes:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python -m unittest tests.python.desktop.test_service_path_layout -q
python -m unittest tests.python.desktop.test_final_library_promotion -q
python -m unittest tests.python.desktop.test_application_facade_rename -q
python -m unittest tests.python.desktop.test_service_rename_apply -q
```

Expected assertions:

- Sibling-prefix paths remain rejected.
- Root mutation remains rejected.
- Reparse/junction mutation remains rejected.
- Final-library cleanup deletes only verified publish-root outputs after copy success.
- Rename source mutation remains explicit, undo-manifested, and outside-root gated.

## Manual Reproduction Checks

F-001 check:

1. Create an old file under a local output root with a legitimate name that includes `.mp-partial`.
2. Run stale cleanup.
3. Confirm the file is preserved.
4. Create a confirmed pipeline-owned stale partial.
5. Run stale cleanup.
6. Confirm only the pipeline-owned artifact is removed.

F-002 check:

1. Force a low-space preflight failure for a destination under a trusted root.
2. Confirm copy returns `OUTPUT_DESTINATION_LOW_SPACE`.
3. Confirm no empty `.mediapipeline-staging` remains.
4. Repeat for stop-request-before-attempt.

UNC check:

1. Configure a UNC-like cleanup root in tests.
2. Confirm stale cleanup skips it when remote cleanup is disabled.
3. Enable remote cleanup in the test.
4. Confirm provenance is still required before deletion.

## Change-Control Validation

Run:

```powershell
$env:PYTHONPATH='src'
python -m mediapipeline.tools.change_control.validate_changes --require-worktree-coverage
```

Expected result in a clean branch:

- Only intended source/test/doc files and the change packet are listed.
- Every touched file is recorded in the relevant `ops/release/changes/unreleased/MP-CHANGE-*.json` packet.

In the current workspace, strict worktree coverage is expected to fail unless unrelated pre-existing dirty files are separately packeted or cleaned.
