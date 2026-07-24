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

The helper defaults `publish_release=false`. Use `-PublishRelease` only after artifact verification and approval. The release tag is an identity, not a label: it must equal `app-v<version>` exactly, and publication binds it to the workflow's full `GITHUB_SHA`, title, channel/prerelease state, and asset set.

Versioned assets are immutable by default. If a release or tag already points to a different commit, create a new version and tag; never reuse or repair the old identity in place. A same-commit rebuild is exceptional: an authorized environment administrator must temporarily set the protected `MEDIAPIPELINE_ALLOW_SAME_COMMIT_REBUILD=true` variable on the selected `beta-release` or `stable-release` environment, and the operator must dispatch with both `-PublishRelease` and `-AllowSameCommitRebuild`. Remove the protected approval immediately after that run. Without both approvals, an existing asset-name collision fails before upload.

```powershell
.\ops\scripts\release\Invoke-PrivateBetaWorkflowDispatch.ps1 -Repository owner/repo -Channel beta -Version 2026.6.4+001 -ReleaseTag app-v2026.6.4+001 -PublishRelease -AllowSameCommitRebuild
```

The workflow's publisher resolves the remote tag to a commit and checks existing release target, title, draft/prerelease state, and asset collisions before any create or upload command. `--clobber` is reachable only for the protected, explicitly requested, same-commit rebuild path.

Release workflow runs are serialized by repository and channel. A versioned release is created and uploaded first; only after that succeeds does the workflow advance the channel pointer. Queued duplicate dispatches therefore cannot race release creation or channel metadata, and an unapproved duplicate version still fails on the immutable versioned-asset policy.

The updater endpoint is channel-specific and does not use GitHub's `releases/latest` resolver. Beta clients read `https://github.com/<owner>/<repo>/releases/download/updater-beta/latest-beta.json`; stable clients use the corresponding `updater-stable` tag and `latest-stable.json`. Each dedicated pointer release is itself a prerelease and is explicitly excluded from latest-release selection. It contains only its channel JSON, while that JSON points to the signed installer on the immutable `app-v<version>` release.

After versioned release publication, `Publish-TauriUpdaterChannelPointer.ps1` validates the JSON's version, installer-release URL, and signature; validates the existing pointer release's tag, title, draft/prerelease posture, mutability, and asset scope; advances only that channel asset; then downloads the exact configured public endpoint with cache-busting and compares its SHA-256 with the just-published file. A stale, unreachable, mismatched, immutable, or contaminated pointer fails release acceptance.

The workflow separates unsigned validation from protected signing. `validate-windows` has read-only contents permission, no release environment, and no signing-secret references; it runs dependency installation, tests, the full release self-test, and sanitized resource staging. It archives only that nonsecret resource tree with a schema, source commit, and SHA-256 digest. `sign-windows` downloads the handoff with a pinned action and verifies the schema, commit, archive name, and SHA-256 before any step can receive a signing credential.

Private updater-key and Windows certificate values are scoped only to `Build signed NSIS updater bundle with step-scoped credentials`. That step imports the certificate, generates the final config, runs the signed build, and removes both the certificate-store entry and temporary certificate files in `finally`; cleanup failure fails the job. Dependency installation, preflight, artifact verification, upload, and GitHub publication do not receive those private values. The updater public key is also available to the preflight because it is public verification material, but private-secret presence is deferred to the consuming build step.

After dispatch, verify the completed workflow run and uploaded CI artifact before using or publishing the bundle:

```powershell
.\ops\scripts\release\Test-PrivateBetaWorkflowRun.ps1 -Channel beta -Repository owner/repo -Version 2026.6.4+001 -ReleaseTag app-v2026.6.4+001 -RunId <github-actions-run-id>
```

If `-RunId` is omitted, the verifier reads the latest `workflow_dispatch` run for `private-beta-windows.yml`. It checks completed/success status, workflow identity, and the expected `mediapipeline-beta-windows-x64` artifact without downloading artifacts, rerunning jobs, approving deployments, or mutating GitHub state. For offline evidence review, save the workflow run JSON and artifacts JSON from GitHub and pass `-RunJsonPath` plus `-ArtifactsJsonPath`.

Before dispatching the GitHub Actions release workflow, run:

```powershell
$validationRoot = Join-Path $env:TEMP 'mediapipeline-release-validation'
$resourceRoot = Join-Path $env:TEMP 'mediapipeline-tauri-resources'
.\ops\scripts\release\build.ps1 -DestinationRoot $validationRoot -Force -Verify -IncludeTests
.\ops\scripts\release\build.ps1 -DestinationRoot $resourceRoot -Force
.\ops\scripts\release\Test-PrivateBetaReleasePreflight.ps1 -Channel beta -Repository owner/repo -Version 2026.6.4+001 -ReleaseTag app-v2026.6.4+001 -ResourceRoot $resourceRoot
```

The first build is the release-boundary self-test. The second produces the lean, sanitized, manifest-backed tree that Tauri embeds at the installer resource root. The preflight validates required backend/runtime files, manifest coverage, exclusion of mutable and personal state, signing/updater secret presence, workflow wiring, NSIS-only updater config generation, stable channel-pointer endpoint shape, signing digest, and timestamp configuration without printing secret values.

When either destination already exists, `-Force` accepts only a partial or
completed marker bound to that exact destination, repository root, version,
and source revision. Copied, legacy, mismatched, or reparse-point paths must be
moved aside manually. A valid prior tree is moved to a sibling `.replaced.*`
quarantine; a failed rebuild restores it automatically, while a successful
rebuild leaves it for operator inspection and manual cleanup.

After CI builds the bundle, run the artifact verifier before publishing or handing out the installer:

```powershell
.\ops\scripts\release\Test-PrivateBetaReleaseArtifact.ps1 -Channel beta -BundleRoot apps\desktop\tauri\src-tauri\target\release\bundle -Repository owner/repo -ReleaseTag app-v2026.6.4+001 -Version 2026.6.4+001
```

The verifier checks the NSIS installer, updater `.sig`, `latest-beta.json` or `latest-stable.json`, `SHA256SUMS.txt`, absence of MSI artifacts, and valid Authenticode signature. It also uses 7-Zip to inventory the exact installer payload and fails unless the release manifest, `pyproject.toml` runtime root marker, backend WebView, bundled Python, Python package, PowerShell engine, and required media tools are present while mutable runtime roots, personal configuration, and repository-development artifacts are absent.

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

- `beta` uses `https://github.com/<owner>/<repo>/releases/download/updater-beta/latest-beta.json`.
- `stable` uses `https://github.com/<owner>/<repo>/releases/download/updater-stable/latest-stable.json`.
- Pointer JSON advances only after its immutable versioned release is published and the public endpoint returns the exact new bytes.
- Updater artifacts are signed by the Tauri updater private key in CI.
- A productized app checks its configured signed channel once at startup. Development shells with updater artifacts disabled do not attempt an empty-endpoint check.
- When a newer version is available, the native shell first asks whether to download it. Download and signature verification complete before a separate installation prompt; declining either prompt leaves the current app and backend running. Restart the app when ready to check again.
- After installation is confirmed, the shell obtains fresh backend close-readiness and requests only safe-only backend shutdown. Active pipeline, audit, queue scan, final-library promotion, an armed schedule-stop watcher, malformed/unreachable readiness, or failed shutdown blocks installation. The updater never offers force-close.
- After safe shutdown, the verified package is handed to the Tauri NSIS updater. If handoff returns an error, the current app records failure evidence and restarts to restore its backend. On the next launch, the shell records `install_applied` only when the running version exactly matches the requested target; an unchanged version records `install_recovery_required` and displays the manual-install/rollback recovery path.
- Native lifecycle evidence is retained under `%LOCALAPPDATA%\com.mediapipeline.remuxencodeaio\UpdateState\NativeUpdater` using `tauri_native_updater_event.v1`. Keep this directory with a support bundle when investigating channel, signature, close-readiness, shutdown, installer handoff, or restart failures. Raw remote errors and secret-bearing endpoint text are not persisted.
- Until signed updater acceptance is current for the release candidate, use the versioned GitHub Release's signed NSIS installer as the documented recovery/update fallback.

Release acceptance for this flow requires a signed local update-server fixture or
an isolated signed test release and a clean Windows account. Exercise no-update,
available-update, operator decline, network failure, corrupt signature, unsafe
and safe close-readiness, installer handoff/restart, and rollback. An acceptance
case that starts active media work additionally requires representative media
and source-hash/scratch-isolation evidence; purely idle/fixture cases do not.

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
