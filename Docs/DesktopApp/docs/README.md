# MediaPipelineRemuxEncodeAIO V6 WebView Notes

This folder holds implementation documentation for the V6 Python local API, backend-served WebView assets, and Tauri/WebView2 shell integration.

The UI itself should not contain roadmap or changelog tabs. Notes belong here instead.

## Current V6 Layout

- `mediapipeline_desktop_app\local_api_main.py`
  - local API entry point
- `mediapipeline_desktop_app\api\`
  - HTTP routes, command/read contracts, token enforcement, static WebView serving
- `mediapipeline_desktop_app\application\`
  - facade and DTO boundary for backend-owned actions
- `mediapipeline_desktop_app\service_*.py`
  - testable service modules for queue, process, settings, rename, pending publish, diagnostics, maintenance, and sample validation
- `mediapipeline_desktop_app\ui_web\static\`
  - backend-served WebView HTML/CSS/JS assets
- `DesktopApp\tauri_shell\`
  - Tauri/WebView2 shell, launchers, and shell validation scripts
- `mediapipeline_desktop_app\views\rename.py`
  - standalone pre/post rename workflow with TV sequencing, movie prediction, forced-name sidecars, selectable scrub filters, and custom negative terms
- `mediapipeline_desktop_app\network\*.py`
  - standalone dispatcher groundwork and future coordinator/worker skeletons
- `mediapipeline_desktop_app\service_*.py`
  - focused service mixins for path resolution, process lifecycle, config, app state, telemetry, status/diagnostics, queue, audit/rerun, completed jobs, pending publish, release packaging, file opening, failure cleanup, folder policy, and rename logic

## Backend Integration Notes

- The backend PowerShell pipeline is split between `Pipeline\MediaPipeline_chatgpt.ps1` and `Pipeline\Modules\*.ps1`.
- Audit implementation is split into focused PowerShell modules: progress, issue policy, probe cache, report writers, and scanner orchestration. The desktop app consumes audit outputs instead of owning audit classification rules.
- Subtitle implementation is split behind the stable `Pipeline\Modules\Subtitles.ps1` facade. Keep public subtitle entrypoints stable unless every pipeline/test call site is migrated in the same change.
- Subtitle settings exposed in the app are grouped by shared policy, ASS/SSA, TX3G, and BDPGS controls. Keep those groups distinct because each subtitle class has different conversion risks and failure modes.
- Folder-level `mediapipeline.folder.json` sidecars can override audio, subtitle, and routing policy for a show/season folder. Use `Pipeline\Schemas\media_pipeline_folder_policy.example.json` as the operator template, then validate the folder from the Maintenance tab before running a batch.
- Routing policy is backend-owned. The UI should expose selected profile, size guard, encode ladder, and route reason metadata, but it should not duplicate route decision logic.
- Rename preview should use the pipeline naming planner when built-in filters are all enabled. If the operator disables a built-in scrub category, the desktop rename scrubber becomes the preview authority so the row reflects those selected filters.
- Pending publish state can include generated SRT sidecar artifacts. The app should treat parked outputs as media-plus-sidecars, not just a single media file.
- Output-destination low-space parking is expected deferred-publish behavior when artifacts are safely parked; it should not be presented as a real processing failure.
- Audio compatibility settings are passthrough controls. Named passthrough profiles should be preferred over raw codec lists; PCM audio is intentionally standardized by the backend even if a user adds a PCM-like string to the custom passthrough list.
- App/pipeline state is centered under `LocalBase\State`; direct `LocalBase` state paths are legacy compatibility fallbacks.

## Design Rules

- left sidebar navigation
- dark premium theme with green accent
- `.grid()` for main layout
- diagnostics as both a first-class workspace and a quick drawer
- live monitoring via `psutil` plus `nvidia-smi` when available
- structured settings profiles before raw flag/text escape hatches
- backend PowerShell pipeline owns media orchestration; the app remains a control and monitoring surface
- destructive or emergency controls should explain what they changed and where their manifest/log evidence was written
