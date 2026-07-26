# Private Beta Release Checklist

Date: 2026-06-18

Use this checklist before publishing a private beta NSIS installer.

## CI Gates

- Local workflow dry-run passed:
  `.\ops\scripts\release\Test-PrivateBetaWorkflowDryRun.ps1 -Channel beta -Repository owner/repo -Version 2026.6.4+001 -ReleaseTag app-v2026.6.4+001`.
- Local release-readiness umbrella check passed:
  `.\ops\scripts\release\Test-PrivateBetaReleaseReadiness.ps1 -Channel beta -Repository owner/repo -Version 2026.6.4+001 -ReleaseTag app-v2026.6.4+001`.
- GitHub release environment setup dry-run passed, then `-Apply` was run after GitHub CLI authentication:
  `.\ops\scripts\release\Initialize-PrivateBetaGitHubReleaseSetup.ps1 -Repository owner/repo`.
- GitHub setup preflight passed after configuring the remote and authenticating GitHub CLI:
  `.\ops\scripts\release\Test-PrivateBetaGitHubSetup.ps1 -Repository owner/repo`.
- Private beta workflow dispatch dry-run passed:
  `.\ops\scripts\release\Invoke-PrivateBetaWorkflowDispatch.ps1 -Repository owner/repo -Channel beta -Version 2026.6.4+001 -ReleaseTag app-v2026.6.4+001 -DryRun`.
- Version and tag identity is exact: `release_tag == app-v<version>` in dispatch, workflow validation, preflight, updater metadata, and publication.
- New publication resolves or creates the tag at the workflow's full source SHA; an existing release matches that SHA, exact title, draft posture, and channel/prerelease state before upload.
- Existing versioned asset names fail closed without replacement. A same-commit rebuild was used only when both the explicit `-AllowSameCommitRebuild` dispatch input and the temporary protected environment approval were present; the protected approval was removed after the run.
- A different-SHA tag/release was rejected without create, upload, or asset replacement.
- Workflow concurrency is serialized by repository/channel with cancellation disabled; the immutable versioned release publishes before the channel pointer advances.
- Generated updater config uses `releases/download/updater-<channel>/latest-<channel>.json`, never `releases/latest`.
- The dedicated pointer release is a non-draft prerelease excluded from latest selection and contains only its channel JSON asset.
- Pointer publication rejects mismatched version/installer-release/signature metadata and fails unless the exact public updater endpoint returns the just-published bytes.
- The workflow has separate `validate-windows` and protected `sign-windows` jobs; validation has read-only contents permission, no release environment, and no `secrets.*` references.
- The sanitized validation handoff records the exact source commit and archive SHA-256; the signing job verifies both before its first secret-consuming step.
- Sentinel-secret scope tests prove updater private key/password and certificate material/password resolve only in the combined import/build/cleanup step. The updater public key resolves only in preflight and that build step.
- Certificate-store and temporary PFX cleanup occurs in `finally`, is verified, and fails the job if either credential artifact remains.
- Workflow run verifier passed after dispatch:
  `.\ops\scripts\release\Test-PrivateBetaWorkflowRun.ps1 -Channel beta -Repository owner/repo -Version 2026.6.4+001 -ReleaseTag app-v2026.6.4+001 -RunId <github-actions-run-id>`.
- Full release self-test passed from a separate external validation root with
  `.\ops\scripts\release\build.ps1 -DestinationRoot <validation-root> -Force -Verify -IncludeTests`.
- A lean sanitized installer resource tree was staged outside the repository with no personal config or mutable runtime state.
- Release preflight passed against that exact resource tree before publishing:
  `.\ops\scripts\release\Test-PrivateBetaReleasePreflight.ps1 -Channel beta -Repository owner/repo -Version 2026.6.4+001 -ReleaseTag app-v2026.6.4+001 -ResourceRoot <sanitized-resource-root>`.
- GitHub Actions workflow `Private Beta Windows Installer` ran from a clean checkout on `windows-latest`.
- Protected secrets were present: `TAURI_SIGNING_PRIVATE_KEY`, `TAURI_UPDATER_PUBLIC_KEY`, `WINDOWS_CERTIFICATE_BASE64`, and `WINDOWS_CERTIFICATE_PASSWORD`.
- Tauri generated NSIS updater artifacts with `createUpdaterArtifacts=true`.
- Installer Authenticode signature verified as valid.
- `latest-beta.json` or `latest-stable.json` includes `version`, `platforms.windows-x86_64.url`, and `platforms.windows-x86_64.signature`.
- `SHA256SUMS.txt` includes the installer, updater signature, and channel JSON.
- Release artifact verifier passed:
  `.\ops\scripts\release\Test-PrivateBetaReleaseArtifact.ps1 -Channel beta -BundleRoot apps\desktop\tauri\src-tauri\target\release\bundle -Repository owner/repo -ReleaseTag app-v2026.6.4+001 -Version 2026.6.4+001`.
- The artifact verifier's 7-Zip inventory found `release_manifest.json`, the `pyproject.toml` runtime root marker, backend WebView, bundled Python, `src\mediapipeline`, the PowerShell engine, and required media tools inside the NSIS installer; it found no `LocalBase`, `RunLogs`, personal config, or repository-development artifacts.
- Published GitHub Release verifier passed after `-PublishRelease`:
  `.\ops\scripts\release\Test-PrivateBetaPublishedRelease.ps1 -Channel beta -Repository owner/repo -ReleaseTag app-v2026.6.4+001 -Version 2026.6.4+001`.
- Downloaded Release assets verifier passed on the target validation machine before install:
  `.\ops\scripts\release\Test-PrivateBetaDownloadedAssets.ps1 -Channel beta -DownloadRoot C:\Path\To\DownloadedAssets -Repository owner/repo -ReleaseTag app-v2026.6.4+001 -Version 2026.6.4+001`.
- Installed-layout verifier passed on the target validation machine after first launch:
  `.\ops\scripts\release\Test-PrivateBetaInstalledLayout.ps1 -Channel beta -InstallRoot "$env:LOCALAPPDATA\Programs\MediaPipelineRemuxEncodeAIO" -AppDataRoot "$env:LOCALAPPDATA\MediaPipelineRemuxEncodeAIO" -ProductizationJsonPath C:\Path\To\productization.json`.
- Productization route and support-export redaction tests passed.
- Existing release dry run passed without copying personal runtime state.

## Clean-Machine Validation

- Fresh install on Windows 10 x64.
- Fresh install on Windows 11 x64.
- Installed app root contains immutable app files only, while state, logs, diagnostics exports, update state, backups, and migration evidence live under AppData.
- Upgrade from previous beta to new beta.
- Update check is blocked while backend close-readiness reports active or unsafe work.
- Update applies when close-readiness reports safe.
- Uninstall preserves AppData.
- Reinstall reuses existing AppData without reimporting unsafe media payloads.

## Media-Safety Validation

Representative real-media validation is required before first beta and after any change to FFmpeg, subtitle, audio, publish/drain, cleanup, source/scratch/output, or media-policy behavior.

Cover:

- Remux.
- Encode/size policy.
- Subtitle conversion and review routing.
- Audio routing.
- Pending publish park and drain.
- Rename-output safety.

## Support Validation

- Support export contains enough evidence for triage.
- Support export redacts bearer tokens, signing secrets, private keys, full private config, and personal paths.
- Support issue template asks for version, channel, Windows version, install/update path, close-readiness state, and redacted support export.
