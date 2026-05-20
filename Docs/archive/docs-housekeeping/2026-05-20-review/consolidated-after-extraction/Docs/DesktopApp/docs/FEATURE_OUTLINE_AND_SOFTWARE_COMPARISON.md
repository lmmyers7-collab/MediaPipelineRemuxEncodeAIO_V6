# MediaPipelineRemuxEncodeAIO V5 Feature Outline

This document describes the current purpose, feature set, operator workflow, and practical limits of MediaPipelineRemuxEncodeAIO V5. It is project-specific documentation only. V4 remains the stable backup; V5 is the active remediation and Tauri/WebView2 transition workspace.

## Product Purpose

MediaPipelineRemuxEncodeAIO V5 is a Windows-first desktop operations console and PowerShell media pipeline for a personal Plex-style library. It is designed for one primary operator who needs controlled remuxing, encoding, subtitle conversion, audio normalization, audit/remediation, queue control, scheduling, scratch-disk processing, and deferred publishing to a slower or unreliable output destination.

The system is not a media acquisition tool, metadata scraper, poster/artwork manager, cloud service, or multi-user administration platform. Its main value is controlled file processing and operator visibility.

## Operating Model

- Runs as a portable bundle with root launchers, a Python desktop app, PowerShell pipeline scripts, and bundled tools.
- Prefers bundled PowerShell 7, Python, FFmpeg/ffprobe, MKVToolNix, and PgsToSrt before falling back to system tools.
- Uses `Pipeline\MediaPipeline_config_chatgpt.psd1` as the live machine config.
- Uses `Pipeline\MediaPipeline_config_template.psd1` for clean deployable packages.
- Keeps most runtime state under `LocalBase\State`.
- Supports nested source, scratch, output, and pending-publish paths.
- Copies media to scratch before processing; source files are not supposed to be mutated by normal pipeline operation.
- Source deletion is intended to remain an explicit safe toggle, not default behavior.

## Main Entry Points

- `Start-MediaPipelineRemuxEncodeAIO-DesktopApp.bat`: launches the desktop app.
- `Start-MediaPipelineRemuxEncodeAIO-DesktopApp.bat console`: launches with visible console output for startup diagnostics.
- `Run-MediaPipelineRemuxEncodeAIO.bat`: runs the backend pipeline directly.
- `Setup-MediaPipelineRemuxEncodeAIO.bat`: launches setup/config validation.
- `Verify-MediaPipelineRemuxEncodeAIO-Environment.bat`: verifies runtime/tool readiness.
- `Build-MediaPipelineRemuxEncodeAIO-Release.ps1`: builds clean deployable copies or zip packages.
- `Test-MediaPipelineRemuxEncodeAIO-Release.ps1`: validates release/package layout and hygiene.

## Desktop App Views

### Home

- Primary operator dashboard.
- Start continuous runs, run once, validate, publish parked outputs, refresh queue, pause, stop, and kill/quit.
- Shows queue, processed, failed, worker, pending-publish, schedule, and pipeline summary tiles.
- Shows next queue items and recovery/failure summaries.
- Provides quick navigation into Queue, Library, Schedule, and Pending Publish workflows.

### Live

- Shows current pipeline activity, run state, timing details, queue-next preview, and recent events.
- Displays CPU telemetry and NVENC/GPU telemetry when available.
- Keeps the NVENC panel visible even when utilization is 0 percent so "idle but detected" is distinguishable from "not available".
- Provides a quick path to the full Queue view.

### Queue

- Displays the pipeline-authored queue plan from `-EmitQueuePlan`.
- Shows priority, movie, and TV queue items in estimated processing order.
- Supports queue refresh, filtering, item details, opening source/output folders, copying paths, and queue CSV export.
- Supports priority marker operations for files/folders.
- Supports temporary in-app row reordering for operator planning; actual durable priority remains marker/config driven.

### Rename

- Standalone rename tool independent of normal queue processing.
- Works for pre-processing and post-processing file names.
- Supports adding individual files or loading media from a folder.
- TV mode supports selected-row season numbering using show name, season, and start episode.
- Movie mode supports title/year input, scrubbed predictions, final names, and force-pipeline-name sidecar tagging.
- Supports selectable movie scrub filter categories:
  - video/source tags
  - audio/channel tags
  - editions/cuts
  - file-size tags
  - services/containers
  - release groups
  - custom negative terms
- Can rename associated `.pipeline.json` sidecars when enabled.
- Uses preview statuses such as match, warning, blocked, and pending so already-correct names are not treated as errors.
- Applies only selected rows when rows are selected.

### Library

- Contains Audit, Failures, Completed, and Reports tabs.
- Runs or displays library audit results for movies and TV.
- Surfaces high-priority findings, subtitle issues, audio issues, TV/movie issues, and duplicate grouping.
- Shows persistent failure records and suggested remediation actions.
- Supports rerunning selected failures through the rerun workflow.
- Shows completed job details, route metadata, output info, and sidecar-derived status.

### CSV Rerun

- Runs exactly the files listed in an audit/rerun CSV.
- Uses copy-to-staging behavior by default.
- Keeps source files by default.
- Parks outputs by default through the pending-publish workflow.
- Shows policy summary, CSV preview, and process output tail.
- Intended for targeted remediation batches rather than full-library runs.

### Schedule

- Provides a weekly schedule grid using 30-minute blocks.
- Applies to app-started pipeline runs.
- Supports outside-schedule operator choices.
- Can request stop-after-current-file when a scheduled run window ends.
- Persists schedule state in the desktop app state file.

### Network

- Experimental network/coordinator/worker controls are present in the desktop app.
- Standalone/local operation remains the supported default.
- Network mode is treated as optional infrastructure, not required for normal processing.

### Maintenance

- Contains Release Package, Pending Publish, and Diagnostics tabs.
- Release Package wraps `Build-MediaPipelineRemuxEncodeAIO-Release.ps1`.
- Pending Publish inspects parked output manifests and payloads under `LocalBase\State\PendingServerPush`.
- Diagnostics exposes maintenance/recovery actions such as environment checks and progress reset.

### Diagnostics

- Shows recent errors, pipeline state, logs, and recovery shortcuts.
- Supports searching/focusing diagnostics details from the app shell.
- Reduces the need to manually locate log files for common troubleshooting.

### Settings

- Edits grouped configuration sections while preserving unknown PSD1 keys.
- Covers basic paths, video/routing, audio, subtitles, queue behavior, advanced settings, and optional network-related controls.
- Tracks unsaved changes and blocks unsafe starts when config edits have not been saved.
- Supports profile handling and validation warnings for path shape and conflicting options.

## Pipeline Flow

The normal backend workflow is:

1. Resolve config and state layout.
2. Scan source roots and build a queue plan.
3. Filter already-completed or already-parked outputs.
4. Copy the selected source file to scratch/staging.
5. Probe media with ffprobe and related helpers.
6. Decide remux vs encode using route profile, codec, audio, subtitle, size, and Plex compatibility policy.
7. Process subtitles and audio according to settings.
8. Run FFmpeg, mkvmerge, and OCR helpers through centralized wrappers.
9. Verify output duration, metadata, sidecars, and publish readiness.
10. Publish to output or park under PendingServerPush.
11. Write completion, failure, progress, event, manifest, and sidecar state.
12. Clean scratch artifacts when safe.

## Remux And Encode Routing

- Default routing profile is Plex Direct/Stream.
- Additional profiles include stricter Direct Play, archive shrink, archive quality, and manual-style policies.
- H.264 sources can be remux-safe when codec/profile/bitrate/resolution policy says they are already acceptable.
- HEVC and other codecs are evaluated by route policy, Plex compatibility score, audio/subtitle needs, and size thresholds.
- Route plans include:
  - route decision
  - reason code
  - decision trace
  - source profile
  - estimated bitrate
  - Plex compatibility score
  - component actions
  - encode fallback attempt metadata
- Size-growth policy can warn, reject, or ignore oversized encodes depending on `SizeGuardMode`.
- Output sidecars and structured events record route details so the operator can see why a file remuxed or encoded.

## Video Encoding

- Supports GPU-first encode attempts with CPU fallback.
- Supports structured encoder presets and flag profiles rather than relying only on freeform flags.
- Records selected encoder, encoder kind, and GPU selection where available.
- Uses timeout-aware FFmpeg wrappers.
- Classifies native tool failures into structured failure records when possible.
- Keeps command, duration, classification, and repro metadata for failed external tool calls.

## Subtitle Handling

Subtitle handling is one of the core policy areas of the project.

- Handles ASS/SSA, tx3g/mov_text, and BDPGS/PGS as separate subtitle families.
- Preserves original subtitle tracks by default unless configured otherwise or unless the selected output container cannot safely carry the subtitle type.
- Converts only the configured/preferred language by default, with unknown-language tracks treated according to language policy.
- ASS/SSA:
  - can convert to SRT
  - can strip formatting for SRT output
  - can filter styles and events
  - can merge adjacent cues
  - can filter karaoke/sign/song content according to config
  - can preserve original ASS tracks unless configured to drop them
- tx3g/mov_text:
  - can generate SRT-compatible subtitle outputs
  - can preserve original tx3g when the target container supports it
  - can drop tx3g when configured or when required to avoid invalid muxing
- BDPGS/PGS:
  - can run OCR through bundled PgsToSrt and tessdata
  - validates temp OCR outputs before muxing
  - marks OCR failures for manual review instead of silently treating conversion as success
  - preserves original PGS tracks by default unless configured otherwise
- Subtitle conversion failures are routed into the failure/remediation workspace.
- Pending publish carries generated subtitle sidecars with the parked media file.

## Audio Handling

- Supports preferred default audio language selection.
- Supports passthrough profiles instead of only raw codec lists.
- Supports incompatible/PCM-like audio normalization through configured transcode codec and bitrate.
- Supports output channel policy, downmix behavior, and max-channel settings.
- Preserves or assigns language/default/forced disposition according to policy.
- Can fall back to highest-fidelity non-commentary audio when preferred language is absent.
- Treats no-audio behavior as an explicit policy decision rather than an accidental success path.

## Audit And Remediation

- Audits movie and TV library roots.
- Produces CSV, JSON, and text reports.
- Writes live audit progress for the UI.
- Uses probe-cache acceleration for repeat scans.
- Detects and surfaces issues such as:
  - multiple default audio tracks
  - missing or incompatible default audio
  - missing audio title metadata
  - subtitle default problems
  - ASS-only subtitle situations
  - tx3g-only or tx3g-conversion candidates
  - BDPGS OCR candidates and failures
  - multiple video streams
  - duplicate title groups
  - TV/movie layout issues
- Supports exporting or rerunning targeted remediation sets.

## Deferred Publish And PendingServerPush

- Allows verified outputs to be parked locally when immediate server publishing is not desired or not safe.
- Stores parked media, generated subtitle sidecars, and a manifest under `LocalBase\State\PendingServerPush`.
- Tracks intended destination, route, sidecar count, source identity, and publish metadata.
- Suppresses reprocessing of already-parked sources.
- Supports manual drain/publish later from the app.
- Treats low-space output destination parking as deferred publish when the local artifact is safely parked.
- Designed for upload-constrained or unreliable network-share environments.

## File Safety And State

- Normal processing copies to scratch first.
- Source mutation should not occur during ordinary processing.
- App state, config saves, subtitle helper outputs, audit progress, reports, manifests, and sidecars use atomic or safer write paths where implemented.
- Runtime control files are stored under `LocalBase\State\Pipeline`.
- Progress, queue snapshots, events, active jobs, completed jobs, failures, and pending publish state are separated into state subfolders.
- Clear Failure Errors is constrained to the failure workspace and writes a clear manifest.
- Kill + Quit verifies process-tree termination and clears known runtime control/progress artifacts.

## Packaging And Deployment

- The desktop Maintenance view can create release packages through the same release builder used from PowerShell.
- Default release packages:
  - include root launchers, desktop app, pipeline scripts/modules, bundled required tools, schemas, release self-test, and operator docs under `Docs`
  - exclude live personal config
  - exclude run logs, state files, caches, Python bytecode, config backups, local assistant metadata, and Office temp/working documents
  - exclude optional GUI/tool bulk and bundled tool docs/examples unless requested
  - write `release_manifest.json`
- `-Verify` runs the release self-test.
- `-IncludeTests -Verify` runs reliability regression, tool integration, and end-to-end smoke checks inside the copied package.
- `-KeepPersonalConfig` is intended only for private machine-to-machine mirror packages.

## Configuration Surfaces

- Global config lives in `Pipeline\MediaPipeline_config_chatgpt.psd1`.
- Folder-level `mediapipeline.folder.json` sidecars can override routing, audio, and subtitle policy for a folder after validation.
- Settings UI groups common controls by operational area and preserves unknown PSD1 keys.
- Rename scrub filters are controlled in the standalone Rename tab.
- Subtitle, audio, routing, size guard, queue, and schedule behavior are exposed through settings and persisted state.

## Reliability Features

- Centralized wrappers for FFmpeg, ffprobe, mkvmerge, PgsToSrt, and related external tools.
- Timeout-aware subprocess execution for core native tool paths.
- Process-tree cleanup for app-owned runs.
- Background telemetry worker so UI polling does not block normal interaction.
- Incremental/tail log reading instead of repeatedly rereading full logs.
- Structured progress, event, failure, and sidecar metadata.
- Release self-test validates package hygiene and core script parsing.
- Regression checks cover critical pipeline and desktop behavior.

## Current Practical Strengths

- Plex-first media processing policy.
- Strong subtitle conversion and cleanup workflow.
- Operator-friendly queue, schedule, audit, and rerun visibility.
- Safe default stance around source files and scratch processing.
- First-class deferred publish for slow or unreliable output shares.
- Portable Windows bundle with included runtimes/tools.
- Standalone rename tool for real-world messy downloads before or after pipeline processing.

## Current Practical Limits

- Windows-first assumptions remain part of the architecture.
- Standalone/local workstation operation is the supported default.
- Network/coordinator mode exists but should be treated as optional/experimental.
- The project does not acquire media, scrape metadata, manage posters/artwork, or write NFO metadata.
- It is optimized for one primary operator rather than multi-user administration.
- It is opinionated around Plex-style playback and personal-library remediation instead of being a generic automation framework.

## Recommended Operator Mental Model

Use the app as a controlled processing workstation:

1. Clean up filenames in Rename when needed.
2. Use Queue to inspect what will run.
3. Use Settings to define routing, audio, subtitle, size, and folder policy behavior.
4. Start processing from Home.
5. Monitor current activity in Live.
6. Use Library to audit and remediate.
7. Use CSV Rerun for targeted fix batches.
8. Use Maintenance to inspect Pending Publish and build clean packages.
