# MediaPipelineRemuxEncodeAIO Desktop App

This is the active desktop control app bundled with `MediaPipelineRemuxEncodeAIO`.

This V5 desktop app currently uses `customtkinter` and an operator-first layout. The Tauri/WebView2 shell is being developed alongside it as an explicit preview, not as the default operator UI.

## Purpose

The desktop app is the main operator surface for:

- starting and stopping the pipeline
- monitoring current activity and progress
- reviewing logs, failures, queue state, and audit output
- editing common config values
- managing schedule windows
- publishing parked outputs when deferred publish or park-on-failure queued local artifacts
- building clean deployable release packages from the active V5 folder
- inspecting PendingServerPush manifests, payloads, sidecars, and orphaned parked files

The backend pipeline remains in `..\Pipeline\`.

## How To Launch

From the bundle root:

- `Start-MediaPipelineRemuxEncodeAIO-DesktopApp.bat`
- `Start-MediaPipelineRemuxEncodeAIO-TauriPreview.bat` for the optional V5 Tauri/WebView2 preview shell

From this folder:

- `Launch-MediaPipelineRemuxEncodeAIO-DesktopApp.bat`

Console mode for startup diagnostics:

- `Launch-MediaPipelineRemuxEncodeAIO-DesktopApp.bat console`

Tauri preview prerequisite check from the bundle root:

- `Start-MediaPipelineRemuxEncodeAIO-TauriPreview.bat -CheckOnly`

## Current Feature Areas

- home / live status
- live monitoring
- audit workspace
- queue workspace
- config workspace
- failures workspace
- schedule workspace
- diagnostics drawer
- CSV rerun workspace
- standalone Rename workspace
- maintenance workspace
- local-only status server

The settings workspace includes structured routing, encode ladder, size guard, audio policy, and dedicated subtitle controls for ASS/SSA, tx3g, and BDPGS behavior, plus timeout settings for subtitle extraction/probing and BDPGS OCR.

The Rename workspace is separate from queue processing. It supports:

- TV season/episode renaming from selected row order.
- Movie prediction from the pipeline naming rules.
- Per-row final filename override.
- Forced pipeline-name sidecars for future pipeline runs.
- Built-in selectable movie scrub filters plus custom negative terms.
- Neutral `match` status when the current filename already equals the target.

The maintenance workspace has two tabs:

- **Release Package**: wraps the root release builder. **Plan Only** performs a dry run, **Build Package** creates the package, and the options mirror the script switches for zip, verify, tests, dev docs, optional tools, tool docs, personal config, and force-replace.
- **Pending Publish**: reads `LocalBase\State\PendingServerPush` manifests. It lists parked outputs, publish mode, route, state, size, destination/source paths, sidecar counts, missing payload references, and orphan payload files. **Publish Parked** uses the existing backend drain mode.

## Path Assumptions

The app is built to work with this bundle layout:

- `..\Pipeline\MediaPipeline_chatgpt.ps1`
- `..\Pipeline\MediaPipeline_config_chatgpt.psd1`
- `..\Pipeline\Audit-MediaLibrary_chatgpt.ps1`

If the app is moved away from this bundle layout, use the app controls to point it at the correct files.

## Local App Files

The app keeps its own local state and log files in this folder, including:

- `MediaPipelineRemuxEncodeAIO_DesktopApp.state.json`
- `MediaPipelineRemuxEncodeAIO_DesktopApp.log`

Pipeline state is read primarily from `LocalBase\State`, including progress, queue snapshots, completed jobs, failures, active jobs, and pending publish manifests.

Clean new-user release packages exclude generated desktop logs, `RunLogs`, local state, and Python bytecode caches.

## Notes

- The app requires Python plus `customtkinter` and `psutil`.
- The app is only a control surface. The actual media work is still performed by the PowerShell pipeline and helper tools in `..\Pipeline\`.
- Generated tx3g SRT sidecars, pending publish manifests, and BDPGS OCR failure metadata are handled by the backend. The desktop app surfaces the resulting config, queue, audit, and failure state.
- Remux/encode route reasons and route-plan metadata are written by the backend and should be surfaced in operator views rather than recalculated in Python.
- Folder-level `mediapipeline.folder.json` policies can be edited/validated from the desktop app and consumed by the backend for routing, audio, and subtitle decisions.
- Release packaging still runs through the root PowerShell release builder; the desktop app only provides a safer operator surface over that script.
- Kill + Quit is a hardened emergency control: it requests process-tree termination, verifies exit where possible, clears known runtime flags/progress artifacts, and then exits the desktop app.
- Clear Failure Errors is constrained to the failure workspace and writes a clear manifest before deletion.
- UI redesign notes live in `docs\`.
