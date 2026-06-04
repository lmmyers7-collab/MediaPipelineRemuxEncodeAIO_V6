# Phase 1 - Release Identity

## Goal

Align all human-facing and machine-readable release identity for `V6.0.0`.

## Current Decision

- Use `V6.0.0` in change-control folders and release manifests.
- Keep Tauri package metadata semver-compatible as `6.0.0`.
- Align backend version surfaces that currently report `v6.000` to the
  operator-facing `V6.0.0` release identity.

## Candidate Surfaces

- `DesktopApp/tauri_shell/package.json`
- `DesktopApp/tauri_shell/src-tauri/tauri.conf.json`
- `engine/shared/versioning.ps1`
- Local API health/version payloads
- generated or packaged release manifests
- `Docs/change_control/CURRENT_VERSION.md`
- `release/VERSION`
- change packets under `changes/unreleased/`

## Rules

- Tauri internals may keep semver `6.0.0` where Tauri requires semver.
- User-facing docs, release folders, change-control release folders, and
  manifests should use `V6.0.0`.
- Do not change media behavior while aligning version strings.

## Steps

1. Inventory all active version strings with `rg`.
2. Classify each string as Tauri-semver, backend identity, docs, manifest, or
   historical/archive.
3. Update only active, release-relevant surfaces.
4. Regenerate any affected generated docs/manifests through existing scripts.
5. Verify Local API health and release metadata agree on the intended identity.

## Validation

Minimum:

```powershell
.\DesktopApp\Runtime\Python\python.exe .\scripts\change_control\validate_changes.py
.\DesktopApp\Runtime\Python\python.exe .\scripts\change_control\prepare_release.py --version V6.0.0 --channel local --dry-run
.\Pipeline\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\release\test.ps1 `
  -SkipToolIntegration -SkipEndToEndSmoke
```

Add Tauri/package open-close validation if this phase touches Tauri files or
Local API startup/version code.

## Exit Criteria

- Active release docs and manifests name `V6.0.0`.
- Tauri-required semver remains valid.
- Backend health/version surfaces no longer present `v6.000` as the current
  release identity unless explicitly documented as a compatibility alias.

