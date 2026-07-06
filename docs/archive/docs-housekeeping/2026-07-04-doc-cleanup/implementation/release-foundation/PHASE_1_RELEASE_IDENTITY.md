# Phase 1 - Release Identity

## Goal

Align release-label surfaces for `2026.06.04.001` without breaking existing backend
product-version contracts.

## Current Decision

- Use `2026.06.04.001` in change-control folders and release manifests.
- Keep Tauri package metadata semver-compatible as `6.0.0`.
- Preserve backend product-version surfaces that intentionally report `2026.06.04.001`
  where schema, sidecar, health, or contract consumers expect the product
  version format.
- If a UI needs to show the portable release label, add or use a separate
  release-label field/alias instead of changing `product_version` semantics.

## Candidate Surfaces

- `apps/desktop/tauri/package.json`
- `apps/desktop/tauri/src-tauri/tauri.conf.json`
- `ops/pipeline/engine/shared/versioning.ps1` as a verification surface; do not change
  `2026.06.04.001` semantics without a separate compatibility migration.
- Local API health/version payloads as verification surfaces for product-version
  compatibility and optional release-label display.
- generated or packaged release manifests
- `docs/change_control/CURRENT_VERSION.md`
- `ops/release/metadata/VERSION`
- change packets under `ops/ops/release/metadata/changes/unreleased/`

## Prerequisites

- Read the required context docs listed in `AGENTS.md`.
- Confirm the intended release label is still `2026.06.04.001`.
- Inventory existing version strings before editing.
- Stop if version identity work would also require media-policy, package
  layout, launcher, or runtime behavior changes.

## Rules

- Tauri internals may keep semver `6.0.0` where Tauri requires semver.
- User-facing docs, release folders, change-control release folders, and
  manifests should use `2026.06.04.001`.
- Backend product-version fields may remain `2026.06.04.001` when they are contract,
  sidecar, schema, or health/report compatibility fields.
- Do not make existing `product_version` or `app_version` consumers parse
  `2026.06.04.001` unless the phase is explicitly widened to a compatibility migration
  with targeted tests.
- Do not change media behavior while aligning version strings.

## Steps

1. Inventory all active version strings with `rg`.
2. Classify each string as release label, Tauri semver, backend product-version
   contract, docs, manifest, or historical/archive.
3. Update only active, release-label surfaces. Leave backend `2026.06.04.001`
   product-version contracts unchanged unless a separate approved migration is
   in scope.
4. Regenerate any affected generated docs/manifests through existing scripts.
5. Verify release metadata reports `2026.06.04.001` and Local API/backend product
   version compatibility is either unchanged or explicitly documented as a
   compatibility alias.

## Change Ledger And Rollback

- Create or update one change packet for the phase before editing.
- Record every touched identity surface and generated artifact in the packet.
- Roll back by restoring only the version-string and generated-artifact changes
  made in this phase.

## Validation

Minimum:

```powershell
.\apps\desktop\runtime\Python\python.exe .\src\mediapipeline\tools\change_control\validate_changes.py
.\apps\desktop\runtime\Python\python.exe .\src\mediapipeline\tools\change_control\validate_changes.py --require-worktree-coverage
.\apps\desktop\runtime\Python\python.exe .\src\mediapipeline\tools\change_control\prepare_release.py --version 2026.06.04.001 --channel local --dry-run
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\scripts\release\test.ps1 `
  -SkipToolIntegration -SkipEndToEndSmoke
```

Add Tauri/package open-close validation if this phase touches Tauri files or
Local API startup/version code.

If backend product-version code or Local API version payloads are touched, also
run targeted version-contract tests such as:

```powershell
.\apps\desktop\runtime\Python\python.exe -m pytest .\tests\python\desktop\test_versioning.py .\tests\python\desktop\test_contracts.py
```

## Exit Criteria

- Active release docs and manifests name `2026.06.04.001`.
- Tauri-required semver remains valid.
- Backend `2026.06.04.001` product-version surfaces remain compatible, or any deliberate
  release-label alias is documented without replacing the existing product
  contract.
