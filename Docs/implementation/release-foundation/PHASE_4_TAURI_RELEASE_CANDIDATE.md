# Phase 4 - Tauri Release Candidate

## Goal

Build one named `2026.06.04.001` portable release candidate with the compiled Tauri
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
C:\MediaPipelineReleases\2026.06.04.001\
```

Recommended candidate folder:

```text
C:\MediaPipelineReleases\2026.06.04.001\MediaPipelineRemuxEncodeAIO.0.0_Portable_<YYYYMMDD_HHMMSS>\
```

## Prerequisites

- Read the required context docs listed in `AGENTS.md`.
- Confirm Phase 1 release identity evidence exists for `2026.06.04.001`.
- Confirm the destination root is outside the repository.
- Confirm no personal live config will be included in the portable artifact.
- Stop if Tauri prerequisites, bundled runtimes, or release identity evidence
  are missing.

## Steps

1. Confirm Phase 1 version identity is complete.
2. Confirm release artifacts will be written outside the repo.
3. Run the dedicated Tauri build checker so WebView script syntax, Cargo check,
   and Rust shell tests are captured before packaging.
4. Run Tauri release build from `apps/desktop/tauri/`.
5. Build the deployable bundle from the repo root with
   `-IncludeTauriPreviewBinary -Verify`.
6. Confirm `release_manifest.json` records
   `tauri_preview_binary_included = true`.
7. Do not include tests/dev docs for the personal/friend portable artifact.

This phase produces a candidate build artifact only. It is not handoff-ready
and must not be accepted for release until Phase 5 passes package/open/close
validation for the same candidate folder.

## Candidate Commands

```powershell
.\ops\scripts\dev\start-tauri-preview.bat -CheckOnly
.\apps\desktop\tauri\Test-TauriShell-Build.ps1

Push-Location .\apps\desktop\tauri
npm run build
Pop-Location

.\ops\scripts\release\build.ps1 `
  -DestinationRoot C:\MediaPipelineReleases\2026.06.04.001\MediaPipelineRemuxEncodeAIO.0.0_Portable_<YYYYMMDD_HHMMSS> `
  -Zip `
  -Verify `
  -IncludeTauriPreviewBinary
```

Do not add `-IncludeTests`, `-IncludeDevDocs`, or `-KeepPersonalConfig` for the
normal portable artifact.

## Validation

Minimum:

```powershell
.\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\ops\scripts\release\test.ps1 `
  -BundleRoot C:\MediaPipelineReleases\2026.06.04.001\MediaPipelineRemuxEncodeAIO.0.0_Portable_<YYYYMMDD_HHMMSS>
.\apps\desktop\runtime\Python\python.exe .\src\mediapipeline\tools\change_control\validate_changes.py --require-worktree-coverage
```

Package/open/close validation is Phase 5.

## Change Ledger And Rollback

- Create or update one change packet for this phase before edits.
- Record the candidate folder, zip path, manifest path, and
  `release_manifest.json` Tauri inclusion evidence.
- Roll back by deleting only the generated candidate folder/zip and reverting
  any source metadata edits made in this phase.

## Exit Criteria

- The candidate folder and optional zip are created outside the repo.
- Tauri build-check evidence passed before the release build.
- `release_manifest.json` records `tauri_preview_binary_included = true`.
- The release self-test passes against the candidate.
- The phase report states the candidate is not accepted until Phase 5 passes
  for the same folder.


