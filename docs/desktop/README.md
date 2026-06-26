# MediaPipelineRemuxEncodeAIO WebView Notes

This folder holds implementation documentation for the Python local API, backend-served WebView assets, and Tauri/WebView2 shell integration.

The UI itself should not contain roadmap or changelog tabs. Notes belong here instead.

## Current Layout

- `src\mediapipeline\desktop\local_api_main.py`
  - local API entry point
- `src\mediapipeline\desktop\api\`
  - HTTP routes, command/read contracts, token enforcement, static WebView serving
- `src\mediapipeline\desktop\application\`
  - facade and DTO boundary for backend-owned actions
- `src\mediapipeline\core\<domain>\`
  - testable domain service modules for queue, process, settings, rename, pending publish, diagnostics, maintenance, and sample validation
- `apps\desktop\webview\static\`
  - backend-served WebView HTML/CSS/JS assets
- `apps\desktop\tauri\`
  - Tauri/WebView2 shell, launchers, and shell validation scripts
- `src\mediapipeline\core\rename\`
  - backend-owned rename workflow with TV sequencing, movie prediction, forced-name sidecars, selectable scrub filters, and custom negative terms
- `src\mediapipeline\desktop\network\*.py`
  - standalone dispatcher groundwork and future coordinator/worker skeletons
- `src\mediapipeline\core\paths`, `src\mediapipeline\core\processes`, `src\mediapipeline\core\config`, `src\mediapipeline\core\status`, `src\mediapipeline\core\queue`, `src\mediapipeline\core\audit`, `src\mediapipeline\core\completed`, `src\mediapipeline\core\publish`, and related core domains
  - focused domain modules for path resolution, process lifecycle, config, app state, telemetry, status/diagnostics, queue, audit/rerun, completed jobs, pending publish, release packaging, file opening, failure cleanup, folder policy, and rename logic

## Backend Integration Notes

- The backend PowerShell pipeline entry point remains `ops\pipeline\entrypoints\MediaPipeline.ps1`; reusable PowerShell implementations live under `ops\pipeline\engine\<domain>\*.ps1`. Do not add `Pipeline\Modules\*.ps1` compatibility shims.
- Audit implementation is split into focused PowerShell modules: progress, issue policy, probe cache, report writers, and scanner orchestration. The desktop app consumes audit outputs instead of owning audit classification rules.
- Subtitle implementation is under `ops\pipeline\engine\subtitles\`. Keep public subtitle entrypoints stable unless every pipeline/test call site is migrated in the same change.
- Subtitle settings exposed in the app are grouped by shared policy, ASS/SSA, TX3G, and BDPGS controls. Keep those groups distinct because each subtitle class has different conversion risks and failure modes.
- Folder-level `mediapipeline.folder.json` sidecars can override audio, subtitle, and routing policy for a show/season folder. Use `ops\pipeline\config\schemas\media_pipeline_folder_policy.example.json` as the operator template, then validate the folder with an approved backend/service workflow before running a batch.
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
