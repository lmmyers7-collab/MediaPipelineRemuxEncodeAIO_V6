# Worker Review: W10-ops-powershell-scripts

## Scope
- Assigned domain: ops-powershell-scripts
- Assigned files: 124 assigned files from the original worker list.
- Review mode: review-only audit. No implementation, runtime/media, config, queue, publish, rename, or launcher state changes were made.
- Edited artifact: this ledger only.

## Coverage Summary

Completed before the time box:

- Read required session guidance: `AGENTS.md`, `docs/CURRENT_PROJECT_STATE.md`, `docs/OPEN_WORK_CHECKLIST.md`, and `docs/generated/PROJECT_INDEX.md`.
- Read this worker ledger before editing.
- Read generated summaries for the primary assigned ops surfaces, including release scripts, setup/config helpers, key entrypoints, smoke wrappers, high-priority PowerShell tests, and assigned change packets.
- Ran read-only static searches across assigned ops script/config/entrypoint/test/release areas for process calls, filesystem mutation, package exclusions, root launcher drift, runtime state writes, and self-skipping validation.
- Fully inspected these source files enough to support findings and coverage notes:
  - `ops/scripts/release/build.ps1`
  - `ops/scripts/release/release_policy.ps1`
  - `ops/scripts/release/test.ps1`
  - `ops/scripts/release/Backup-PreOverhaul.ps1`
  - `ops/pipeline/entrypoints/Setup-MediaPipeline.ps1`
  - `ops/pipeline/entrypoints/Invoke-RerunCsv.ps1`
  - `ops/pipeline/entrypoints/Audit-MediaLibrary.ps1`
  - `ops/pipeline/entrypoints/MediaPipeline.ps1`
  - `ops/pipeline/config/setup/PathValidation.ps1`
  - `ops/pipeline/config/setup/Validation.ps1`
  - `ops/scripts/dev/verify-env.ps1`
  - `ops/scripts/dev/run.bat`
  - `ops/scripts/dev/setup.bat`
  - `ops/scripts/dev/start-local-api.bat`
  - `ops/scripts/dev/start-api-and-browser.bat`
  - `ops/scripts/dev/start-tauri-preview.bat`
  - `ops/scripts/dev/verify-env.bat`
  - `ops/pipeline/tests/Unit/Invoke-ReleasePackagePolicyChecks.ps1`
  - Representative smoke wrapper: `ops/scripts/smoke/Test-WebViewBrowserCompletedPendingProofSmoke.ps1`
  - Assigned release packets enough to identify leakage examples: notably `MP-CHANGE-2026-0604-043.json` and `MP-CHANGE-2026-0605-006.json`

## Findings

| ID | Severity | File | Symbol / area | Problem | Suggested validation |
|---|---|---|---|---|---|
| W10-001 | Medium | `ops/scripts/release/build.ps1`; `ops/scripts/release/Backup-PreOverhaul.ps1` | release manifests | Release/backup manifests persist absolute local machine paths. `build.ps1` writes `summary.source_root` and `summary.destination_root` into `release_manifest.json` (lines 156-158, 254-255). `Backup-PreOverhaul.ps1` writes `repo_root` into `manifest.json` (lines 194-199). These manifests are release/backup artifacts, so they can leak operator usernames, drive layout, or workstation paths when shared. | Build a package to a temp path and inspect both manifests for drive/user-root strings. Add a release-policy/unit assertion that public package manifests contain repo-relative or redacted roots only. |
| W10-002 | Medium | `ops/scripts/release/release_policy.ps1`; `ops/pipeline/tests/Unit/Invoke-ReleasePackagePolicyChecks.ps1` | release exclusions | Active review ledgers under `docs/reviews/...` are not excluded by the release policy or hygiene checks. The policy excludes archive/root-artifact/real-media evidence paths, but no `docs\reviews\*` rule appeared in `release_policy.ps1` lines 28-115 or hygiene rules lines 144-240, and the package policy unit checks do not cover it. This current audit ledger is untracked and intended review work, not operator release content. | Add a package-policy test for `docs\reviews\function-module-audit-*\workers\*.md` and verify `build.ps1 -DryRun` excludes active review/audit ledgers by default. |
| W10-003 | Low | `ops/release/changes/unreleased/MP-CHANGE-2026-0605-006.json`; `ops/release/changes/unreleased/MP-CHANGE-2026-0604-043.json` | change packet evidence text | Assigned change packets include local workstation details in release metadata. Example: one packet records a user-profile temp path, and another records local PIDs plus an operator desktop shortcut path. These are not secrets by themselves, but release metadata is meant to be portable and can disclose operator machine details. | Add a change-packet lint for absolute user-profile/temp/desktop paths and require redaction or `%LOCALAPPDATA%`/`<temp>` placeholders before release packaging. |
| W10-004 | Low | `ops/pipeline/entrypoints/Setup-MediaPipeline.ps1` | comment examples | The comment help still demonstrates `.\Setup-MediaPipeline.ps1` as if run from the script directory (lines 47-58). The canonical launcher rule says use `ops\scripts\...` paths and avoid root launcher drift. This is not an actual root shim, but it can nudge operators or future docs back toward non-canonical direct entrypoint use. | Update docs/help checks to flag direct `.\Setup-MediaPipeline.ps1` examples outside internal implementation docs, or explicitly label them as script-local examples. |
| W10-005 | Medium | `ops/pipeline/entrypoints/Invoke-RerunCsv.ps1` | `-DryRun` path | `Invoke-RerunCsv.ps1 -DryRun` still creates rerun directories and writes a manifest under configured `LocalBase`: directories at lines 722-724, manifest write at lines 743 and 751-755. It does skip staging copies and nested pipeline execution, so media is not mutated, but the option name can be mistaken for no state mutation. | Add/extend a dry-run contract test that asserts exactly which state artifacts may be written, or split into `-PlanOnly` for stdout/no-write behavior and keep `-DryRun` documented as evidence-writing. |
| W10-006 | Low | `ops/scripts/release/test.ps1`; `ops/scripts/smoke/Test-WebViewBrowser*.ps1`; `ops/pipeline/tests/Invoke-EndToEndSmokeChecks.ps1`; `ops/pipeline/tests/Invoke-ToolIntegrationChecks.ps1` | validation wrappers | Several validation gates can pass or report success while important coverage is absent by design: release manifest checks are skipped for source/dev folders (test.ps1 lines 480-483), full regression gates are warnings unless `-RequireTests` is set (lines 947-969), tool and end-to-end checks can be skipped by switches (lines 959-968), browser smokes state they skip when Chrome/Edge is missing, and tool/end-to-end scripts self-skip when bundled tools are missing. This is acceptable for dev convenience but creates false-confidence risk if final evidence only says "release self-test passed." | Require final release evidence to record `-RequireTests` and no skip switches for release candidates. Add summary output that says which gates were skipped and whether the run is source/dev-only or package-complete. |

## Boundary Risks

- Release package leakage is the main completed-audit risk: package and backup manifests can include absolute local roots, and active `docs/reviews` ledgers are not excluded.
- Runtime state mutation risk was observed in dry-run/planning surfaces, especially CSV rerun. I did not confirm whether this is intentional operator evidence behavior across all dry-run scripts.
- Validation false confidence risk is present in wrappers that intentionally degrade to warnings/skips for source/dev or missing browser/tool environments.
- Root launcher drift was limited in reviewed source to comment/help examples, not reintroduced root launcher files.

## Files With No Findings From Completed Review

- `ops/scripts/dev/run.bat`
- `ops/scripts/dev/setup.bat`
- `ops/scripts/dev/start-local-api.bat`
- `ops/scripts/dev/start-api-and-browser.bat`
- `ops/scripts/dev/start-tauri-preview.bat`
- `ops/scripts/dev/verify-env.bat`
- `ops/scripts/dev/verify-env.ps1`
- `ops/pipeline/entrypoints/Audit-MediaLibrary.ps1` for the inspected process-timeout/report-root sections
- `ops/pipeline/entrypoints/MediaPipeline.ps1` for the inspected single-instance, cleanup, validate-only, dump, drain, and queue-plan sections
- `ops/pipeline/config/setup/PathValidation.ps1`
- `ops/pipeline/config/setup/Validation.ps1`, except the noted first-run progress skeleton write is intentional setup behavior
- `ops/pipeline/tests/Unit/Invoke-ReleasePackagePolicyChecks.ps1`, except missing coverage for findings above
- `ops/scripts/smoke/Test-WebViewBrowserCompletedPendingProofSmoke.ps1`, except the broader browser-skip false-confidence risk

## Incomplete Coverage

The audit was time-boxed before full review of all 124 assigned files. Exact groups not fully reviewed:

- Config data files: `ops/pipeline/config/MediaPipeline_config_template.psd1`, `ops/pipeline/config/profiles/Default.psd1`.
- Setup helper full bodies: `ops/pipeline/config/setup/ConfigFile.ps1`, `Dependencies.ps1`, `UserInteraction.ps1`; only summaries/search hits were reviewed.
- Stage boundary entrypoint: `ops/pipeline/engine/entrypoint.ps1`; summary only.
- Audit helper slices: `ops/pipeline/entrypoints/Audit-MediaLibrary/path_utilities.ps1`, `scanner.ps1`; summary/search hits only.
- Maintenance/naming metadata entrypoints: `Backfill-CompletedManifest.ps1`, `Get-NamingPreview.ps1`, `Get-RerunSourceMetadata.ps1`; summaries/search hits only, not full source.
- Media entrypoint slices: `MediaPipeline/encode.ps1`, `MediaPipeline/remux.ps1`, `MediaPipeline/tx3g_sidecars.ps1`; summaries/search hits only. These are high-risk media behavior files and need a dedicated media-policy worker for full review.
- Most PowerShell test files under `ops/pipeline/tests` and `ops/pipeline/tests/Unit`; reviewed by summary/search only except `Invoke-ReleasePackagePolicyChecks.ps1` and broad skip/self-skip hits.
- Dev `.mjs` tooling scripts under `ops/scripts/dev`; summary/search only.
- Operator worksheet script `ops/scripts/operator/New-RealMediaValidationWorksheet.ps1`; summary/search only.
- Most smoke wrappers under `ops/scripts/smoke`; reviewed by summary/search pattern only, with one representative full wrapper read.
- Assigned change packets not named in findings were read by summaries and targeted leakage grep, not fully audited field-by-field.

Reason for incompleteness: user time-boxed the review and requested the ledger be written immediately.

## Validation Performed

- No test suites or runtime scripts were executed.
- No package build, release verification, setup, smoke, pipeline, queue, publish, rename, or media commands were run.
- Static evidence only: generated summaries, source reads, and read-only `rg`/`Get-Content` inspections.
