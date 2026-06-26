# Private Beta Install And Update Runbook

Date: 2026-06-18

This runbook covers the first productized Windows private beta lane.

## Release Shape

- Audience: private beta operators.
- OS: Windows 10/11 x64.
- Installer: signed NSIS `.exe`, current-user install mode.
- Updates: prompted beta/stable full-bundle updates through public GitHub Release assets.
- Runtime state: per-user AppData roots for desktop logs, command journal, update state, migration evidence, and diagnostics exports.
- Media policy: unchanged. Source mutation remains forbidden by default and backend-owned pipeline policy still controls source/scratch/output/pending-publish behavior.

## Release Preflight

Before dispatching the GitHub Actions release workflow, run the local workflow dry-run:

```powershell
.\ops\scripts\release\Test-PrivateBetaWorkflowDryRun.ps1 -Channel beta -Repository owner/repo -Version 2026.6.4+001 -ReleaseTag app-v2026.6.4+001
```

The dry-run uses placeholder signing/updater values only inside the local process so it can validate checked-in workflow wiring, updater config generation, scoped productization tests, and the Tauri scaffold without publishing artifacts. It does not prove protected GitHub secrets exist.

For the standard local release-readiness pass, run the umbrella checker:

```powershell
.\ops\scripts\release\Test-PrivateBetaReleaseReadiness.ps1 -Channel beta -Repository owner/repo -Version 2026.6.4+001 -ReleaseTag app-v2026.6.4+001
```

The readiness checker runs the workflow dry-run, static GitHub setup preflight, and workflow dispatch dry-run. It does not dispatch workflows, publish releases, upload assets, download installers, mutate GitHub state, or prove protected GitHub secrets exist.

After the repo is connected to GitHub and GitHub CLI is authenticated, run:

```powershell
.\ops\scripts\release\Initialize-PrivateBetaGitHubReleaseSetup.ps1 -Repository owner/repo
```

Review the planned environment and secret-name commands. Then create/check the GitHub environments:

```powershell
.\ops\scripts\release\Initialize-PrivateBetaGitHubReleaseSetup.ps1 -Repository owner/repo -Apply
```

The initializer creates/checks `beta-release` and `stable-release` environments and reports whether required environment secret names exist. It never prints or writes secret values; use the printed `gh secret set ... --env ...` hints to enter values through GitHub CLI or the GitHub web UI.

```powershell
.\ops\scripts\release\Test-PrivateBetaGitHubSetup.ps1 -Repository owner/repo
```

The setup preflight checks the configured GitHub remote, `gh auth status`, checked-in workflow wiring, and the `beta-release` plus `stable-release` GitHub environments. Use `-StaticOnly` only for offline/static validation; it does not prove the remote, GitHub CLI auth, or environments exist.

Dry-run the exact workflow dispatch command:

```powershell
.\ops\scripts\release\Invoke-PrivateBetaWorkflowDispatch.ps1 -Repository owner/repo -Channel beta -Version 2026.6.4+001 -ReleaseTag app-v2026.6.4+001 -DryRun
```

When the dry-run is correct and setup preflight passes, dispatch the first CI artifact build without publishing release assets:

```powershell
.\ops\scripts\release\Invoke-PrivateBetaWorkflowDispatch.ps1 -Repository owner/repo -Channel beta -Version 2026.6.4+001 -ReleaseTag app-v2026.6.4+001
```

The helper defaults `publish_release=false`. Use `-PublishRelease` only after artifact verification and approval.

After dispatch, verify the completed workflow run and uploaded CI artifact before using or publishing the bundle:

```powershell
.\ops\scripts\release\Test-PrivateBetaWorkflowRun.ps1 -Channel beta -Repository owner/repo -Version 2026.6.4+001 -ReleaseTag app-v2026.6.4+001 -RunId <github-actions-run-id>
```

If `-RunId` is omitted, the verifier reads the latest `workflow_dispatch` run for `private-beta-windows.yml`. It checks completed/success status, workflow identity, and the expected `mediapipeline-beta-windows-x64` artifact without downloading artifacts, rerunning jobs, approving deployments, or mutating GitHub state. For offline evidence review, save the workflow run JSON and artifacts JSON from GitHub and pass `-RunJsonPath` plus `-ArtifactsJsonPath`.

Before dispatching the GitHub Actions release workflow, run:

```powershell
.\ops\scripts\release\Test-PrivateBetaReleasePreflight.ps1 -Channel beta -Repository owner/repo -Version 2026.6.4+001 -ReleaseTag app-v2026.6.4+001
```

The preflight validates required signing/updater secret presence, workflow wiring, NSIS-only updater config generation, channel endpoint shape, signing digest, and timestamp configuration without printing secret values.

After CI builds the bundle, run the artifact verifier before publishing or handing out the installer:

```powershell
.\ops\scripts\release\Test-PrivateBetaReleaseArtifact.ps1 -Channel beta -BundleRoot apps\desktop\tauri\src-tauri\target\release\bundle -Repository owner/repo -ReleaseTag app-v2026.6.4+001 -Version 2026.6.4+001
```

The verifier checks the NSIS installer, updater `.sig`, `latest-beta.json` or `latest-stable.json`, `SHA256SUMS.txt`, absence of MSI artifacts, and valid Authenticode signature.

After dispatching with `-PublishRelease`, verify the published GitHub Release metadata before sharing installer links:

```powershell
.\ops\scripts\release\Test-PrivateBetaPublishedRelease.ps1 -Channel beta -Repository owner/repo -Version 2026.6.4+001 -ReleaseTag app-v2026.6.4+001
```

The verifier reads GitHub Release metadata through `gh api` and checks the release tag, draft/prerelease posture, NSIS installer asset, updater `.sig`, channel JSON, checksums, release notes, and absence of MSI assets. For support investigations, save the GitHub Release JSON and pass `-ReleaseJsonPath` to rerun the same metadata checks offline without GitHub access.

After downloading the Release assets to the target validation machine, verify the actual downloaded folder before running the installer:

```powershell
.\ops\scripts\release\Test-PrivateBetaDownloadedAssets.ps1 -Channel beta -DownloadRoot C:\Path\To\DownloadedAssets -Repository owner/repo -Version 2026.6.4+001 -ReleaseTag app-v2026.6.4+001
```

The downloaded-asset verifier is read-only. It checks the local NSIS `.exe`, matching `.exe.sig`, `latest-beta.json` or `latest-stable.json`, `SHA256SUMS.txt`, Authenticode signature, channel JSON URL/signature, checksum matches, and MSI exclusion. It does not download assets, run installers, dispatch workflows, mutate GitHub state, modify AppData, or touch media paths.

## Install

1. Run the published-release verifier against the private beta GitHub Release.
2. Download the signed NSIS installer from the verified GitHub Release.
3. Run the downloaded-asset verifier against the local download folder.
4. Run the installer as the target Windows user.
5. Open the app from the Start menu folder `MediaPipeline`.
6. Save the Maintenance productization response as local evidence, then run the installed-layout verifier:

```powershell
.\ops\scripts\release\Test-PrivateBetaInstalledLayout.ps1 -Channel beta -InstallRoot "$env:LOCALAPPDATA\Programs\MediaPipelineRemuxEncodeAIO" -AppDataRoot "$env:LOCALAPPDATA\MediaPipelineRemuxEncodeAIO" -ProductizationJsonPath C:\Path\To\productization.json
```

The installed-layout verifier is read-only. It checks that mutable runtime folders are absent from the installed app root, AppData runtime roots and migration evidence exist, guarded migration evidence did not write or delete media payloads, and the productization status reports NSIS, prompted updates, close-readiness gating, and the expected beta/stable channel.
7. Open Maintenance and confirm productization status reports the expected release channel and safe close-readiness posture before starting work.

## First Run And Migration

The installed app treats the install directory as immutable. On productized Tauri launches, the backend prepares `%LOCALAPPDATA%\MediaPipelineRemuxEncodeAIO` and records one-time guarded import evidence.

The guarded import may back up desktop-local artifacts such as:

- Legacy desktop app state.
- Legacy local API command journal.

The guarded import must not move, delete, or copy source media, scratch payloads, output payloads, pending-publish payloads, or completed media.

## Updates

- `beta` uses `latest-beta.json`.
- `stable` uses `latest-stable.json`.
- Updater artifacts are signed by the Tauri updater private key in CI.
- The app must check backend close-readiness before applying an update. Active pipeline, audit, queue scan, final-library promotion, or unsafe state blocks update application.

## Rollback

1. Uninstall the current app from Windows Apps.
2. Install the previous signed NSIS beta.
3. Leave `%LOCALAPPDATA%\MediaPipelineRemuxEncodeAIO` in place unless support explicitly asks for a clean-state reproduction.
4. Attach a redacted support export to the issue if rollback was caused by startup, migration, update, or close-readiness behavior.

## Backup And Restore

Back up `%LOCALAPPDATA%\MediaPipelineRemuxEncodeAIO` before major beta upgrades when investigating state-sensitive defects.

Do not back up or restore source media, scratch, output, or pending-publish payloads through this app-state process. Those remain governed by backend config and operator storage policy.

## Diagnostics Export

Use `POST /api/maintenance/support-export` or the Maintenance UI once wired. The export is written under AppData `DiagnosticsExports` and includes:

- App version and release channel.
- Runtime root posture.
- Migration evidence.
- Close-readiness payload.
- Release manifest summary.
- Bundled tool path/existence evidence.
- Bounded redacted desktop and pipeline log tails.

The export must not include bearer tokens, signing secrets, private keys, full private config, or unredacted personal paths.

## Uninstall

Uninstall removes app files. AppData is preserved by default so reinstall can reuse operator state safely. Remove AppData only for an explicit clean-state reset after backing up any evidence needed for support.
