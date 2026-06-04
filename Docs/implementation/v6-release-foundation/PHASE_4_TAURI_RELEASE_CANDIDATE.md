# Phase 4 - Tauri Release Candidate

## Goal

Build one named `V6.0.0` portable release candidate with the compiled Tauri
shell included.

## Release Decisions

- Delivery: portable bundle only.
- Signing: unsigned.
- Tests/dev docs: excluded.
- Tauri source: included.
- Runtime state: externalized outside the install folder.
- Large artifacts: created outside the repository.

## Candidate Folder

Recommended root:

```text
C:\MediaPipelineReleases\V6.0.0\
```

Recommended candidate folder:

```text
C:\MediaPipelineReleases\V6.0.0\MediaPipelineRemuxEncodeAIO_V6.0.0_Portable_<YYYYMMDD_HHMMSS>\
```

## Steps

1. Confirm Phase 1 version identity is complete.
2. Confirm release artifacts will be written outside the repo.
3. Run Tauri release build from `DesktopApp/tauri_shell/`.
4. Build the deployable bundle from the repo root with
   `-IncludeTauriPreviewBinary -Verify`.
5. Confirm `release_manifest.json` records
   `tauri_preview_binary_included = true`.
6. Do not include tests/dev docs for the personal/friend portable artifact.

## Candidate Commands

```powershell
Push-Location .\DesktopApp\tauri_shell
npm run build
Pop-Location

.\scripts\release\build.ps1 `
  -DestinationRoot C:\MediaPipelineReleases\V6.0.0\MediaPipelineRemuxEncodeAIO_V6.0.0_Portable_<YYYYMMDD_HHMMSS> `
  -Zip `
  -Verify `
  -IncludeTauriPreviewBinary
```

Do not add `-IncludeTests`, `-IncludeDevDocs`, or `-KeepPersonalConfig` for the
normal portable artifact.

## Validation

Minimum:

```powershell
.\Pipeline\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\release\test.ps1 `
  -BundleRoot C:\MediaPipelineReleases\V6.0.0\MediaPipelineRemuxEncodeAIO_V6.0.0_Portable_<YYYYMMDD_HHMMSS>
```

Package/open/close validation is Phase 5.

