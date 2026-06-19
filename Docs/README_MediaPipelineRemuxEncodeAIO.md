
# MediaPipelineRemuxEncodeAIO

This folder is the active all-in-one deployment bundle.

Start here:

- `DOCS_INDEX.md` for the full documentation map.
- `CURRENT_PROJECT_STATE.md` for the current operational summary.
- `..\README.md` for the root operator entry point.
- `..\ops\scripts\dev\verify-env.bat` to check whether this folder is runnable on the current machine.

Top-level layout:

- `src\mediapipeline\`
- `apps\desktop\`
- `ops\pipeline\`
- `ops\scripts\dev\start-api-and-browser.bat`
- `ops\scripts\dev\start-local-api.bat`
- `ops\scripts\dev\start-tauri-preview.bat`
- `ops\scripts\dev\setup.bat`
- `ops\scripts\dev\run.bat`
- `ops\scripts\dev\verify-env.bat`
- `ops\scripts\release\build.ps1`

## What This Bundle Contains

- a Python local API plus WebView/Tauri surface for day-to-day control and monitoring
- the PowerShell pipeline entrypoints and engine modules
- the audit tool
- bundled runtime/tool locations for portable deployment
- a release builder that strips personal config and generated runtime clutter for new-user packages
- a WebView Maintenance surface for release packaging and PendingServerPush review
- a standalone Rename tab for TV season numbering, movie title scrubbing, per-row final names, forced pipeline-name sidecars, and selectable negative filters
- structured routing profiles, encode ladders, and size-growth policy for Plex-first remux/encode decisions
- subtitle conversion helpers for ASS/SSA, MP4 Timed Text / tx3g, and optional BDPGS OCR
- audio policy controls for passthrough profiles, transcode codec/bitrate, downmix mode, max channels, language preference, and explicit no-audio opt-in

The backend script filenames under `ops\pipeline\entrypoints\` are the stable operator-facing names. Reusable implementation belongs under `ops\pipeline\engine\<domain>\`.

## Backend Module Boundaries

The PowerShell backend keeps stable launcher/script names. Reusable implementation logic lives under `ops\pipeline\engine\<domain>\`; the legacy root module-shim layer has been removed from the active package surface:

- subtitle policy and conversion: `ops\pipeline\engine\subtitles\*.ps1`
- audit progress, probe cache, issue policy, scanning, and reports: `ops\pipeline\engine\audit\*.ps1`
- routing, encode policy, native tool execution, media probing, audio, naming, folder policies, sidecars, and pending publish: dedicated `ops\pipeline\engine\` domain files

Do not add new legacy shim files for compatibility. New PowerShell implementation belongs under `ops\pipeline\engine\<domain>\`, with `ops\pipeline\entrypoints\MediaPipeline.ps1` and its established child scripts remaining the stable backend entrypoints.

## Recommended First-Run Order

1. Run `ops\scripts\dev\verify-env.bat`
2. Fix any missing dependency/runtime issues it reports
3. Run `ops\scripts\dev\setup.bat`
4. Run `ops\scripts\dev\start-api-and-browser.bat`
5. Use the backend-served WebView for normal operation after validation gates pass

## Main Entry Points

- `ops\scripts\dev\verify-env.bat`
  - checks the release layout, required runtimes/tools, Python dependencies, and config writability
- `ops\scripts\dev\setup.bat`
  - launches the setup wizard and validates the generated config
- `ops\scripts\dev\run.bat`
  - launches the pipeline directly without the WebView shell
- `ops\scripts\dev\start-api-and-browser.bat`
  - launches the local API and opens the backend-served WebView in a browser
- `ops\scripts\dev\start-local-api.bat`
  - launches the token-protected localhost backend API for browser/Tauri work
- `ops\scripts\dev\start-tauri-preview.bat`
  - launches the Tauri/WebView2 shell; use `-CheckOnly` to verify Node/Rust/WebView2 prerequisites without opening the shell
- `ops\scripts\release\build.ps1`
  - creates a clean deployable copy or zip from the current working bundle

## WebView/Tauri Status

The current folder is WebView-first. The WebView/Tauri path starts the local Python API, opens the backend-served web UI, and deliberately leaves media processing, queue state, settings, rename actions, pending publish, release packaging, and diagnostics owned by the Python/PowerShell backend.

The external rollback workspace remains the external fallback for operator flows that have not yet been validated in this workspace. Do not reintroduce the removed legacy desktop shell or its launcher docs into this folder.

As of 2026-05-18, the source/dev bundle validation gate is green for the release self-test, bundled Python `unittest`/`pytest`, browser no-mutation smokes, and Tauri prereq/build checks. Representative real-media validation is complete by operator attestation as of 2026-05-28, and default-launcher/package-mode promotion is complete by operator confirmation on 2026-05-30.

For future real-media validation or revalidation, use `implementation/release-foundation/PHASE_6_REAL_MEDIA_PILOT.md` with `sample-validation/REAL_MEDIA_VALIDATION_EVIDENCE_TEMPLATE.md`. The Tauri/WebView2 prerequisite, build, launch-smoke, and release self-test gates do not prove FFmpeg routing, subtitle OCR/SRT output, audio selection, size policy, Completed sidecars, or pending-publish behavior on a specific file. The WebView can append backend-owned sample-validation evidence records under `State\Validation`, but those records are notes only and do not create an acceptance path. `RealMediaValidationRuns/README.md` records the current non-sensitive operator-attested status anchor.

## Local API And WebView Diagnostics

If the WebView does not open cleanly, start the backend directly and inspect the API/browser launcher output:

- `ops\scripts\dev\start-local-api.bat`
- `ops\scripts\dev\start-api-and-browser.bat`

Those launchers keep backend startup errors visible instead of hiding API import or port failures behind the shell.

## Maintenance Surface

The WebView includes a **Maintenance** view with two focused tools:

- **Release Package** wraps `ops\scripts\release\build.ps1`. Use **Plan Only** for a dry-run package plan, then **Build Package** when the destination/options look right. Defaults match the new-user release policy: live config, generated state/logs, optional tool bulk, and dev-only clutter are stripped unless explicitly included.
- **Pending Publish** reads `LocalBase\State\PendingServerPush` manifests and payloads. It shows parked output count, total size, route, publish mode, sidecar count, missing local payload references, orphan payloads, and provides buttons to open/copy the relevant paths. **Publish Parked** launches the existing pending-push drain path.

## Bundled Runtime / Tool Locations

Preferred portable locations:

- `apps\desktop\runtime\Python\pythonw.exe`
- `apps\desktop\runtime\Python\python.exe`
- `ops\pipeline\runtime\Python\python.exe`
- `ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe`
- `ops\pipeline\tools\ffmpeg\bin\ffmpeg.exe`
- `ops\pipeline\tools\ffmpeg\bin\ffprobe.exe`
- `ops\pipeline\tools\MKVToolNix\mkvmerge.exe`
- `ops\pipeline\tools\PgsToSrt\PgsToSrt.exe`
- `ops\pipeline\tools\PgsToSrt\tessdata\`

The bundle prefers those locations before system `PATH`.

## Personal Config vs New-User Release

This working folder may keep a live operator config at:

- `ops\pipeline\config\MediaPipeline_config_chatgpt.psd1`

That file can contain machine-specific source, scratch, output, and tuning values. Keep using it for your day-to-day setup.

For a new-user deployable copy, run:

```powershell
.\ops\scripts\release\build.ps1
```

The same flow is available from the WebView Maintenance surface under **Release Package**.

To verify the copied package before zipping or handoff, add `-Verify`. For the full regression/tool/smoke gate, also add `-IncludeTests`:

```powershell
.\ops\scripts\release\build.ps1 -Zip -Verify -IncludeTests
```

By default, the release builder strips the live config and generated runtime clutter, then includes:

- `ops\pipeline\config\MediaPipeline_config_template.psd1`
- canonical `ops\scripts\` setup/run/verify/desktop launchers and the release builder
- the explicit Tauri/WebView2 preview launcher
- local API source under `src\mediapipeline\desktop\`, WebView/Tauri source under `apps\desktop\`, and bundled Python runtime
- pipeline entrypoints and engine modules under `ops\pipeline\`, bundled PowerShell, runtime-required FFmpeg/MKVToolNix command tools, and PgsToSrt
- `ops\scripts\release\test.ps1`
- `release_manifest.json`

Clean releases omit optional tool bulk such as `ffplay.exe`, MKVToolNix GUI/diagnostic utilities, MKVToolNix GUI assets, tool docs, and examples. The release self-test validates `release_manifest.json` and fails default packages that accidentally include live config, run logs/state, or optional tool bulk. Use `-IncludeOptionalTools` or `-IncludeToolDocs` only when you want a fuller maintenance package. Use `-KeepPersonalConfig` only for a private backup/mirror package. Use `-IncludeTests` or `-IncludeDevDocs` only when making an engineering handoff package.

## Documentation Map

- `..\README.md`: root operator entry point
- `DOCS_INDEX.md`: all docs and what each one is for; organized by subfolder
- `CURRENT_PROJECT_STATE.md`: current operational state, launch paths, and safety assumptions
- `implementation/release-foundation/PHASE_6_REAL_MEDIA_PILOT.md`: real-media pilot checklist for validating WebView/Tauri on real media
- `sample-validation/REAL_MEDIA_VALIDATION_EVIDENCE_TEMPLATE.md`: evidence template for real-media validation runs
- `desktop\README.md`: local API/WebView/Tauri structure and backend integration notes
- `operator\POWERSHELL_HOST_EXPECTATIONS.md`: PowerShell host/runtime expectations
- `testing\VALIDATION_LADDER_RUNBOOK.md`: ordered validation gates before promotion
- `inventories/RELEASE_PACKAGE_ADMIN_INVENTORY.md`: release package inclusion/exclusion reference
- `DOCS_INDEX.md`: current archive/quarantine locations for completed or superseded docs

## Current Media Policy Highlights

- Default routing is Plex Direct/Stream. Plex Direct Play, archive shrink, archive quality, and manual profiles are available for stricter or more specialized behavior.
- H.264 sources are remux-safe by default when codec/profile/bitrate/resolution policy says they are already compatible.
- Size-growth policy can warn, reject, or ignore oversized encodes depending on `SizeGuardMode`.
- Route plans include source profile, estimated bitrate, Plex compatibility score, component actions, reason code, decision trace, and encode fallback attempt metadata.
- ASS/SSA subtitles can be converted to SRT with style filtering, karaoke filtering, adjacent cue merging, and optional formatting stripping.
- MP4 Timed Text / tx3g subtitles can be converted to muxed SRT-compatible subtitle tracks. External SRT sidecars are optional.
- Original tx3g and BDPGS tracks are preserved unless the configured drop setting says otherwise or the target container cannot carry that subtitle type.
- BDPGS OCR is available through the bundled `PgsToSrt` tool and tessdata folder. It remains a configurable OCR path because image-subtitle OCR quality depends on source and language data.
- Deferred publish and park-on-failure carry subtitle SRT sidecars through `PendingServerPush` manifests so the media file and subtitle artifacts drain together.
- Audio passthrough is profile-driven; incompatible, PCM-like, or policy-blocked audio is normalized through the configured transcode codec/bitrate/downmix path.
- Folder-level `mediapipeline.folder.json` sidecars can override routing, audio, and subtitle policy for a folder after validation.
- The standalone Rename tab has built-in movie scrub categories for video/source tags, audio/channels, editions/cuts, file sizes, services/containers, and release groups, plus custom negative terms.

## Notes

- The local API/WebView path uses the bundled Python runtime and no longer carries the removed legacy desktop shell.
- The pipeline depends on `ffmpeg`, `ffprobe`, `mkvmerge`, Python, and `pysubs2`. BDPGS OCR also needs `PgsToSrt` and matching Tesseract language data when `ConvertBdpgsToSrt` is enabled.
- `ops\scripts\dev\verify-env.ps1` reports OCR readiness and optional network dependency status separately from standalone readiness.
- The verifier intentionally ignores Windows Store Python aliases under `WindowsApps`.
- This folder is now the active working deployment bundle, not a throwaway packaged release.
