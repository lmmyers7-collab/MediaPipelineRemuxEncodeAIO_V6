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
- Workflow run verifier passed after dispatch:
  `.\ops\scripts\release\Test-PrivateBetaWorkflowRun.ps1 -Channel beta -Repository owner/repo -Version 2026.6.4+001 -ReleaseTag app-v2026.6.4+001 -RunId <github-actions-run-id>`.
- Release preflight passed before publishing:
  `.\ops\scripts\release\Test-PrivateBetaReleasePreflight.ps1 -Channel beta -Repository owner/repo -Version 2026.6.4+001 -ReleaseTag app-v2026.6.4+001`.
- GitHub Actions workflow `Private Beta Windows Installer` ran from a clean checkout on `windows-latest`.
- Protected secrets were present: `TAURI_SIGNING_PRIVATE_KEY`, `TAURI_UPDATER_PUBLIC_KEY`, `WINDOWS_CERTIFICATE_BASE64`, and `WINDOWS_CERTIFICATE_PASSWORD`.
- Tauri generated NSIS updater artifacts with `createUpdaterArtifacts=true`.
- Installer Authenticode signature verified as valid.
- `latest-beta.json` or `latest-stable.json` includes `version`, `platforms.windows-x86_64.url`, and `platforms.windows-x86_64.signature`.
- `SHA256SUMS.txt` includes the installer, updater signature, and channel JSON.
- Release artifact verifier passed:
  `.\ops\scripts\release\Test-PrivateBetaReleaseArtifact.ps1 -Channel beta -BundleRoot apps\desktop\tauri\src-tauri\target\release\bundle -Repository owner/repo -ReleaseTag app-v2026.6.4+001 -Version 2026.6.4+001`.
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
