# Worker Review: worker-10-ops-powershell-scripts

## Scope

Worker ID: `worker-10-ops-powershell-scripts`

Assigned review area: PowerShell ops, pipeline entrypoint/config scripts, dev/release/smoke/operator wrappers, and the W10 file list from `docs/reviews/function-module-audit-2026-06-11/ASSIGNMENTS.md`.

Non-overlap rule applied: the assignment sheet says indexed files are assigned exactly once. I treated the W10 assignment table as authoritative for review ownership. Files in the broader directory prose but not in the W10 table are listed under "Files Marked Out Of Scope".

Focus areas covered:

- filesystem mutation safety
- source/scratch/output handling
- PowerShell parameter validation
- launcher and bundled-runtime drift
- release and smoke reliability
- unsafe deletes and moves
- path quoting and Windows/UNC behavior
- script test gaps

## Coverage Ledger

Required first reads completed:

- `AGENTS.md`
- `docs/CURRENT_PROJECT_STATE.md`
- `docs/OPEN_WORK_CHECKLIST.md`
- `docs/generated/PROJECT_INDEX.md`
- `docs/reviews/function-module-audit-2026-06-11/ASSIGNMENTS.md`

Additional boundary read:

- `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`

Summary-first rule:

- Checked generated summaries for all W10-assigned files before source inspection.
- All W10-assigned files had generated summaries.
- High-priority summaries reviewed before full source checks included pending-publish tests, FFmpeg progress tests, library profile routing tests, completed/pending WebView smoke wrappers, and pending-drain guard smoke wrappers.

Static and targeted source coverage:

- Ran high-risk mutation scans for `Remove-Item`, `Move-Item`, `Copy-Item`, `New-Item`, `Set-Content`, `Out-File`, `Export-Csv`, `robocopy`, `Start-Process`, `Invoke-Expression`, `cmd /c`, `xcopy`, recursive deletes, and force flags across W10-assigned PowerShell/config/dev/release/smoke/operator files.
- Ran targeted source reads around each mutation hotspot and around path/root derivation logic.
- Reviewed assigned launcher/config/test wrappers for stale paths, bundled-runtime assumptions, dry-run behavior, path quoting, and skip/failure behavior.
- Reviewed assigned `MediaPipeline.ps1`, `MediaPipeline/encode.ps1`, and `MediaPipeline/remux.ps1` mutation points for source/scratch/output separation. No direct source deletion was found in assigned files; local scratch and local output deletion is conditional and scoped to scratch/output variables.
- Reviewed assigned config setup slices for path normalization, UNC handling, disjoint source/scratch/output validation, and write probes.

Coverage status:

- Complete for the W10 assignment table at function/module review level.
- Partial only relative to the broader directory prose, because most `ops/pipeline/engine/` domain modules were assigned to other workers and intentionally left out of W10 ownership.

## Findings Summary

| ID | Severity | File | Symbol/Section |
| --- | --- | --- | --- |
| W10-HIGH-001 | High | `ops/scripts/release/build.ps1` | release destination replacement |
| W10-HIGH-002 | High | `ops/pipeline/tests/Invoke-ToolIntegrationChecks.ps1` | bundled tool path discovery |
| W10-MED-001 | Medium | `ops/pipeline/entrypoints/Invoke-RerunCsv.ps1` | `-DryRun` planning path |
| W10-MED-002 | Medium | `ops/scripts/dev/check_powershell_analysis.ps1` | default analysis target |
| W10-MED-003 | Medium | `ops/pipeline/tests/Unit/Invoke-PathBoundaryGuardChecks.ps1` | repo-root calculation and gate wiring |

Severity counts:

- High: 2
- Medium: 3
- Low: 0

## Detailed Findings

### W10-HIGH-001 - Release build `-Force` can recursively delete unsafe destination ancestors

Severity: High

File: `ops/scripts/release/build.ps1`

Symbol/section: release destination setup and replacement

Evidence:

- `ops/scripts/release/build.ps1:101-115` derives `$script:SourceRoot`, defaults `$DestinationRoot`, computes `$destinationFull`, and rejects only the source folder itself or a child of source.
- `ops/scripts/release/build.ps1:193-201` resolves an existing destination and, when `-Force` is supplied, repeats the same source-or-child guard before `Remove-Item -LiteralPath $resolvedDestination -Recurse -Force`.
- The guard does not reject drive roots, user roots, workspace roots, or ancestors/siblings of `$script:SourceRoot`.

Impact:

An operator or automation can pass a mistaken `-DestinationRoot` such as the workspace parent, repository parent, user folder, or drive root with `-Force`. The script will treat it as replaceable as long as it is not equal to the repo root and not inside the repo root, then recursively remove it. This is a high-impact filesystem safety failure in a release script.

Fix direction:

Add a release destination boundary helper before any destructive operation. It should reject filesystem roots, drive roots, home/profile roots, the source root, children of the source root, ancestors of the source root, and broad workspace parents. Prefer allowing replacement only for directories that look like prior release packages under an explicit release-output parent and/or contain a release marker generated by this build script.

Validation:

- Add unit coverage to `ops/pipeline/tests/Unit/Invoke-ReleasePackagePolicyChecks.ps1` or a dedicated release safety test for root, ancestor, source, child, sibling, and valid release package destinations.
- Verify `build.ps1 -DestinationRoot <repo-parent> -Force` fails before delete.
- Run `ops/scripts/release/test.ps1` after the guard is added.

### W10-HIGH-002 - Tool integration gate silently skips in the current promoted layout

Severity: High

File: `ops/pipeline/tests/Invoke-ToolIntegrationChecks.ps1`

Symbol/section: bundled tool path discovery

Evidence:

- `ops/pipeline/tests/Invoke-ToolIntegrationChecks.ps1:6-13` derives `$pipelineRoot` as `ops\pipeline`, `$projectRoot` as `ops`, then looks for:
  - `ops\pipeline\PowerShell-7.6.0-win-x64\pwsh.exe`
  - `ops\pipeline\Tools\ffmpeg\bin\ffmpeg.exe`
  - `ops\pipeline\Tools\ffmpeg\bin\ffprobe.exe`
  - `ops\apps\desktop\runtime\Python\python.exe`
- The current canonical layout uses the promoted bundle paths under `ops\pipeline\runtime\...`, `ops\pipeline\tools\...`, and repo-root `apps\desktop\runtime\Python\python.exe`.
- `ops/pipeline/tests/Invoke-ToolIntegrationChecks.ps1:27-30` prints `SKIP` and returns success when any tool is missing.

Impact:

The tool integration check can report a clean run while never exercising bundled PowerShell, FFmpeg, ffprobe, or Python in the current layout. That weakens the high-validation boundary for FFmpeg/subtitle/media behavior and can create false confidence in release or operator smoke results.

Fix direction:

Compute the repository root correctly from `ops\pipeline\tests`, use the current promoted paths, and fail nonzero by default when required bundled tools are absent. If a skip mode is needed for source-only environments, require an explicit `-AllowMissingTools` switch and surface that status to the caller.

Validation:

- Run `ops/pipeline/tests/Invoke-ToolIntegrationChecks.ps1` in the current workspace and assert it does not emit `SKIP` when bundled tools are present.
- Add a static path regression check for `runtime\PowerShell-7.6.0-win-x64`, `tools\ffmpeg`, and repo-root `apps\desktop\runtime\Python`.
- Run the release test wrapper after fixing the paths.

### W10-MED-001 - `Invoke-RerunCsv.ps1 -DryRun` mutates LocalBase rerun state

Severity: Medium

File: `ops/pipeline/entrypoints/Invoke-RerunCsv.ps1`

Symbol/section: dry-run planning and manifest write path

Evidence:

- `ops/pipeline/entrypoints/Invoke-RerunCsv.ps1:1-9` exposes a `-DryRun` switch.
- `ops/pipeline/entrypoints/Invoke-RerunCsv.ps1:722-724` creates stage and park directories before checking `-DryRun`.
- `ops/pipeline/entrypoints/Invoke-RerunCsv.ps1:743` writes the rerun manifest before checking `-DryRun`.
- `ops/pipeline/entrypoints/Invoke-RerunCsv.ps1:751-755` then marks the manifest `dry_run_complete`, writes it again, logs the manifest path, and exits.

Impact:

A dry run creates `RerunQueue`, `RerunParked`, and rerun manifest state under `LocalBase`. That can dirty operator/runtime state and leave synthetic manifests that look like evidence from a real rerun planning pass. The source media boundary is preserved, but the dry-run contract is weaker than operators generally expect from a planning-only command.

Fix direction:

Keep dry-run planning in memory and print or return the plan without creating runtime directories or manifests. If dry-run evidence files are required, gate them behind an explicit output parameter such as `-DryRunManifestPath` or `-WriteDryRunManifest`.

Validation:

- Add a temp-LocalBase regression test asserting `Invoke-RerunCsv.ps1 -DryRun` creates no `RerunQueue`, `RerunParked`, or `RerunManifests` directories unless an explicit dry-run output path is supplied.
- Run the rerun source identity checks and any rerun CSV smoke after the behavior is clarified.

### W10-MED-002 - PowerShell analysis wrapper defaults to a removed path and exits success

Severity: Medium

File: `ops/scripts/dev/check_powershell_analysis.ps1`

Symbol/section: default path resolution

Evidence:

- `ops/scripts/dev/check_powershell_analysis.ps1:7-10` resolves `$RepoRoot` as `Join-Path $PSScriptRoot "..\.."`, which points to `ops`, then defaults `$Path` to `ops\engine`.
- The active PowerShell implementation is under `ops\pipeline\engine`.
- `ops/scripts/dev/check_powershell_analysis.ps1:12-14` prints `PSScriptAnalyzer skipped: path not found` and exits `0`.

Impact:

Default invocation of this analyzer wrapper can pass while analyzing no active engine files. That hides syntax or analyzer errors in the promoted PowerShell layout and undermines dev/release reliability.

Fix direction:

Resolve the actual repo root from `ops\scripts\dev` and default to `ops\pipeline\engine` or require an explicit path. A missing default target should fail nonzero because it indicates launcher drift, not an optional skip.

Validation:

- Add a wrapper self-check that default resolution points at `ops\pipeline\engine`.
- Run the analyzer wrapper against the active engine path with PSScriptAnalyzer installed.
- Include the wrapper in a release or dev tooling smoke that treats missing default targets as failures.

### W10-MED-003 - Path-boundary unit test resolves the wrong repo root and is absent from the active reliability gate

Severity: Medium

File: `ops/pipeline/tests/Unit/Invoke-PathBoundaryGuardChecks.ps1`

Symbol/section: repo-root setup and reliability gate coverage

Evidence:

- `ops/pipeline/tests/Unit/Invoke-PathBoundaryGuardChecks.ps1:16-21` computes `$pipelineRoot` as `ops\pipeline` and `$repoRoot` as the parent of that path, which is `ops`. It then dot-sources `ops\pipeline\engine\...` relative to `$repoRoot`, producing `ops\ops\pipeline\engine\...`.
- `ops/pipeline/tests/Invoke-ReliabilityRegressionChecks.ps1:78-97` lists the active reliability gate scripts. `Unit\Invoke-PathBoundaryGuardChecks.ps1` is not included.

Impact:

The unit test intended to protect output path boundaries is both path-broken in the promoted layout and not invoked by the active reliability wrapper. This leaves a test gap around server output path capability and outside-root rejection.

Fix direction:

Correct `$repoRoot` to the actual repository root, dot-source using current paths, and wire the test into the active reliability regression wrapper or another release-required gate.

Validation:

- Run `ops/pipeline/tests/Unit/Invoke-PathBoundaryGuardChecks.ps1` directly and confirm it reaches `Path boundary guard checks passed`.
- Run `ops/pipeline/tests/Invoke-ReliabilityRegressionChecks.ps1` and confirm the path-boundary test is part of the active gate.

## Test Coverage Gaps

- No assigned test currently proves `ops/scripts/release/build.ps1 -Force` rejects filesystem roots, source ancestors, or broad workspace parents before `Remove-Item -Recurse -Force`.
- `Invoke-RerunCsv.ps1 -DryRun` lacks a no-runtime-state-mutation regression test.
- `Invoke-ToolIntegrationChecks.ps1` can green-skip required tools due stale paths; the release gate needs a non-skip assertion for promoted bundled paths.
- `Invoke-PathBoundaryGuardChecks.ps1` is not wired into `Invoke-ReliabilityRegressionChecks.ps1`.
- Smoke wrappers under `ops/scripts/smoke/*.ps1` fall back to `python` on `PATH` when bundled Python is absent. That may be useful for ad hoc runs, but it is weaker than the project rule that Python validation uses the bundled interpreter. Consider making system Python fallback opt-in for smoke/release validation.

## Boundary Risks

- No direct source-file deletion was found in the W10-assigned pipeline entrypoint files. The assigned encode/remux cleanup points remove temp outputs, subtitle temp files, scratch input copies, or local output only after publish-success conditions.
- `Backfill-CompletedManifest.ps1 -DryRun` does not modify the completed manifest, but it does initialize state layout and write checkpoint files under `LocalBase`. This appears intentional based on its status messages, but it should be documented as a dry-run side effect or made opt-in if dry-run commands are expected to be state-free.
- `Audit-MediaLibrary.ps1` writes report/probe-cache artifacts and scans library roots with literal-path handling. I did not find source mutation in the assigned audit files.
- Config setup writes backups, temp config files, validation probes, and setup reports. The reviewed setup slices include disjoint path checks and prompted creation paths; no source/media delete was found there.

## Files Reviewed With No Findings

Reviewed with no detailed findings:

- `ops/pipeline/config/templates/processing.profile.template.psd1`
- `ops/pipeline/config/profiles/1080p balanced.psd1`
- `ops/pipeline/config/setup/ConfigFile.ps1`
- `ops/pipeline/config/setup/Dependencies.ps1`
- `ops/pipeline/config/setup/PathValidation.ps1`
- `ops/pipeline/config/setup/UserInteraction.ps1`
- `ops/pipeline/config/setup/Validation.ps1`
- `ops/pipeline/engine/entrypoint.ps1`
- `ops/pipeline/entrypoints/Audit-MediaLibrary.ps1`
- `ops/pipeline/entrypoints/Audit-MediaLibrary/path_utilities.ps1`
- `ops/pipeline/entrypoints/Audit-MediaLibrary/scanner.ps1`
- `ops/pipeline/entrypoints/Backfill-CompletedManifest.ps1`
- `ops/pipeline/entrypoints/Get-NamingPreview.ps1`
- `ops/pipeline/entrypoints/Get-RerunSourceMetadata.ps1`
- `ops/pipeline/entrypoints/MediaPipeline.ps1`
- `ops/pipeline/entrypoints/MediaPipeline/encode.ps1`
- `ops/pipeline/entrypoints/MediaPipeline/remux.ps1`
- `ops/pipeline/entrypoints/MediaPipeline/tx3g.ps1`
- `ops/pipeline/entrypoints/Setup-MediaPipeline.ps1`
- `ops/scripts/dev/*.bat`
- `ops/scripts/dev/*.mjs`
- `ops/scripts/dev/run-python-tool.py`
- `ops/scripts/dev/start-*.bat`
- `ops/scripts/dev/verify-env.ps1`
- `ops/scripts/operator/New-RealMediaValidationWorksheet.ps1`
- `ops/scripts/release/Backup-PreOverhaul.ps1`
- `ops/scripts/release/release_policy.ps1`
- `ops/scripts/release/test.ps1`
- Assigned smoke wrappers under `ops/scripts/smoke/*.ps1`
- Assigned release/change packet JSON files under `ops/release/changes/unreleased/*.json`
- Assigned pipeline test scripts under `ops/pipeline/tests/` and `ops/pipeline/tests/Unit/` except those named in detailed findings

## Files Marked Out Of Scope

Marked out of W10 scope because the assignment sheet is non-overlapping:

- All `ops/pipeline/engine/**` files except `ops/pipeline/engine/entrypoint.ps1`
- `ops/pipeline/entrypoints/MediaPipeline/module_loader.ps1`
- `ops/pipeline/entrypoints/MediaPipeline/runtime_paths.ps1`
- `ops/pipeline/entrypoints/MediaPipeline/startup_filesystem.ps1`
- `ops/pipeline/entrypoints/MediaPipeline/startup_path_validation.ps1`
- `ops/scripts/smoke/README.md`
- Any additional files in the broad directory prose that were not present in the W10 assignment table

## Incomplete Coverage

No W10-assigned files were intentionally skipped.

Not performed:

- No code fixes, refactors, commits, or media/runtime mutation.
- No real-media validation.
- No release package build execution.
- No browser/WebView smoke execution.

Reason: this was a review-only worker task. The required output was limited to this worker report and its change packet.
