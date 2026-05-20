# GUI Framework Decision And Migration Plan

Date: 2026-05-07  
Project: MediaPipelineRemuxEncodeAIO V4  
Scope: desktop GUI framework direction, long-term UI architecture, backend/frontend boundary, packaging impact, and first safe migration chunk.

## Current GUI/Architecture Assessment

### Current State

The current desktop app is a Python `customtkinter` application wrapped around a PowerShell media pipeline. It is not a trivial launcher. It now owns real operational workflows:

- Pipeline start/stop/kill/validate/pending-drain controls.
- Queue refresh, priority planning, table filtering, queue previews, and worker/coordinator dispatch.
- Live status, telemetry graphs, CPU/RAM/NVENC readings, recent events, diagnostics, and log tails.
- Audit, failure, completed-output, pending-publish, CSV rerun, schedule, settings, release packaging, maintenance, and standalone rename tooling.
- Config persistence and PSD1 validation.
- ActiveJobs/control/progress/event contracts and recovery state.

Key files inspected:

| File | Current Responsibility | Architectural Signal |
|---|---|---|
| `DesktopApp\mediapipeline_desktop_app\app.py` | Main app object, Tk root lifecycle, controller passthrough facade, UI worker startup, polling, shutdown hooks. | `MediaPipelineApp` is still the ambient app-wide object. It is better than before, but it remains the primary dependency every controller/view receives. |
| `DesktopApp\mediapipeline_desktop_app\app_bootstrap.py` | Root window creation, controller construction, column constants, and a large amount of Tk variable/state initialization. | UI state, runtime state, process state, table state, widget references, and network state are still initialized together. |
| `DesktopApp\mediapipeline_desktop_app\services.py` | Aggregates many service mixins behind `DesktopAppService`. | Service split improved maintainability, but the service is still a broad facade with caches, telemetry thread ownership, launch state, queue counters, and file/path helpers. |
| `DesktopApp\mediapipeline_desktop_app\service_processes.py` | PowerShell launch, run logs, ActiveJobs records, process kill/reconciliation, stale runtime cleanup. | This is close to the correct backend boundary, but still coupled to desktop app path layout and desktop service mixin state. |
| `DesktopApp\mediapipeline_desktop_app\workers.py` | Background thread runner with Tk-thread callback delivery. | Good short-term abstraction for Tk. It is framework-specific because scheduling is provided by `root.after`. |
| `DesktopApp\mediapipeline_desktop_app\controllers\*.py` | Feature controllers. | Controllers still commonly access `app.*` state directly. This prevents clean UI replacement until state/contracts are centralized. |
| `DesktopApp\mediapipeline_desktop_app\views\*.py` | CustomTkinter view construction and widget layout. | Views are workable but tightly bound to Tk variables, `ttk.Treeview`, and direct app callbacks. |
| `DesktopApp\mediapipeline_desktop_app\views\network_tab.py` | Network role setup, coordinator/worker guide, firewall checks, API buttons, worker board polling. | At 1700+ lines, this is a strong example of UI, network orchestration, polling, copy text, firewall helpers, and status rendering living in one file. |
| `DesktopApp\mediapipeline_desktop_app\contracts\*.py` | Python contracts for ActiveJobs, control flags, progress, events, pending publish, queue snapshots, process results. | This is the strongest foundation for a future UI-neutral backend. |
| `DesktopApp\mediapipeline_desktop_app\network\*.py` | Coordinator/worker/standalone dispatch and HTTP protocols. | The project already has a partial API/service model, but it is for distributed workers, not a clean local UI API. |
| `Build-MediaPipelineRemuxEncodeAIO-Release.ps1` | Portable package copy, manifest, optional tool filtering, verification. | Any framework migration must fit this bundle model and avoid adding fragile machine-installed prerequisites. |

### What Is Working

- The current GUI is operational and has recently survived multiple targeted remediation phases.
- The move from one large `services.py` file into service mixins was the right direction.
- The new contracts under `DesktopApp\mediapipeline_desktop_app\contracts` are valuable. They can become the future API boundary.
- Process output is redirected to log files rather than GUI pipes, reducing deadlock risk.
- ActiveJobs/control/progress/event contracts now give the app a better recovery story than a typical Tk launcher.
- The app already exposes a local status server on `127.0.0.1`, proving that a local API model is technically compatible with the current architecture.

### What Is Still Fragile

- The app-wide object is still the real state container. `app_bootstrap.py` initializes many `tk.StringVar`, `tk.BooleanVar`, lists, caches, process handles, widget refs, and controller refs together.
- Controllers are thinly split but are not UI-neutral. Most take `app` and mutate/read attributes directly.
- Views bind directly to app callbacks and variables. A framework replacement cannot reuse most view/controller code without an adapter layer.
- The current table/grid model depends on `ttk.Treeview`, which is workable for moderate data but not ideal for large audit/queue/completed views, virtualization, column operations, rich cell state, or high-frequency updates.
- Telemetry and live status are polling-based. This is acceptable for CustomTkinter, but the underlying model should become event/snapshot driven before a migration.
- Network/coordinator UI code is too large and mixes UI, background threads, HTTP probing, firewall checks, and operator copy blocks.
- Packaging currently assumes a Python desktop runtime and CustomTkinter packages. A migration must avoid breaking the portable bundle.

### Architectural Verdict

Do not rewrite the GUI immediately. The backend/UI boundary is not clean enough yet. A direct rewrite would reproduce the same ambient state and process lifecycle coupling in a new framework.

The current CustomTkinter app should remain the production UI during the next stabilization period. The right next move is to extract a UI-neutral application/backend boundary that the existing Tk UI can call first. Once that boundary exists, a modern frontend can be built beside it with much less risk.

## Core Requirements For The Next UI

The UI framework must support this specific workload:

| Requirement | Why It Matters Here |
|---|---|
| Windows-first portable deployment | The project ships bundled Python, PowerShell 7, FFmpeg/ffprobe, MKVToolNix, PgsToSrt, config templates, and launchers. |
| Long-running task supervision | Pipeline, audit, rerun, pending drain, coordinator, worker, and telemetry tasks may run for hours. |
| Safe process control | Start, stop-after-current, pause, rescan, kill tree, orphan detection, and crash recovery must remain deterministic. |
| Large tables | Queue, audit, failures, completed outputs, pending publish, and rename previews need sorting, filtering, selection, details, and stable rendering. |
| Rich diagnostics | Logs, recent errors, pipeline events, active jobs, control flags, progress state, and repro metadata need first-class presentation. |
| Telemetry graphing | CPU, RAM, GPU/NVENC, encode speed, route breakdown, timing, and status transitions need clear graphs/charts. |
| File/folder operations | UNC paths, long paths, slow disks, network shares, file pickers, open folder, open VLC, explorer select. |
| Backend contract reuse | Existing PowerShell and Python contracts should be reused rather than reimplemented in a UI language. |
| Settings complexity | PSD1 config editing needs grouped controls, validation, dirty state, profile handling, unknown key preservation, and safer structured options. |
| Offline/local operation | This should work as a local workstation app, not require internet/cloud services. |
| Incremental migration | Current app must stay usable while the UI is gradually improved or replaced. |
| Testability | Backend logic must be testable without a GUI event loop; UI behavior should be testable with stable snapshots or browser automation if moved to web. |

## Framework Candidates

### Option A: Stay With Current CustomTkinter And Refactor

Best for short-term operational continuity. Lowest migration cost. Keeps the current launcher, bundled Python runtime, tests, and operator workflow.

Weaknesses:

- Tk event model and widgets are limiting for large tables, complex settings, rich diagnostics, and future visualization.
- UI test automation is more awkward than web or Qt.
- The current app is already stretching the framework with custom graphs, treeviews, background polling, drawers, and many tabs.
- CustomTkinter does not solve state ownership. Without backend extraction, the app object remains central.

Verdict: Keep temporarily. Do not treat it as the final long-term UI for a growing operations console.

### Option B: PySide6 / Qt

Best native-ish Python desktop replacement. Strong table/model support, signals/slots, background worker patterns, file dialogs, docking/layout options, and mature widgets. Python backend reuse is straightforward.

Strengths:

- Strong fit if the project should remain a single Python desktop app.
- Better model/view tables than Tk.
- Better threading/event tools than Tk.
- Good Windows file dialog and desktop integration.
- Can directly call existing Python service layer if the backend boundary is cleaned first.

Weaknesses:

- Still a desktop widget framework. Building highly dynamic diagnostics/settings UIs is possible but verbose.
- Packaging PySide6 increases bundle size and introduces Qt plugin deployment concerns.
- UI tests are possible but less convenient than browser automation.
- Migrating current CustomTkinter views to Qt is still a rewrite of every view.

Verdict: Best pure-Python desktop migration option. Strong fallback if web technologies are not desired.

### Option C: WPF / .NET

Best classic Windows desktop platform for a Windows-only app. Excellent MVVM patterns, data binding, virtualization, native controls, Windows integration, and process management.

Strengths:

- Very strong Windows desktop experience.
- Excellent table/grid and MVVM story.
- Good installer and long-term maintainability for Windows-native teams.
- Strong process and filesystem APIs.

Weaknesses:

- Requires a major C#/.NET UI rewrite.
- Existing Python service code becomes an external backend or must be ported.
- Cross-language contracts become mandatory earlier.
- AI-assisted changes may be split across PowerShell, Python, C#, and XAML.
- Less attractive if the main maintainer wants to stay Python-first.

Verdict: Technically strong but too expensive for this project's current trajectory unless the operator wants a Windows-only .NET product.

### Option D: WinUI 3

Modern Windows UI stack. Good appearance and Windows integration, but higher tooling and deployment complexity.

Strengths:

- Modern Windows look and native shell direction.
- Good for packaged Windows apps.

Weaknesses:

- High rewrite cost.
- More brittle deployment/tooling story than WPF for a portable utility bundle.
- Python backend still requires IPC/API.
- Less mature for this app's practical table/diagnostics workload than WPF or web.

Verdict: Not recommended. It adds migration risk without solving this project's core backend/state problems.

### Option E: Avalonia

Cross-platform .NET UI stack. Useful if cross-platform desktop becomes a real requirement.

Strengths:

- Good MVVM model.
- Cross-platform desktop story.
- Better modern styling flexibility than WPF.

Weaknesses:

- Still requires .NET/C# rewrite and backend IPC.
- Windows-first app does not currently need Avalonia's cross-platform value.
- Packaging remains an additional runtime/toolchain direction.

Verdict: Not a primary fit unless cross-platform desktop becomes a hard requirement.

### Option F: Electron With Local Backend

Chromium/Node shell with a local Python backend. Best UI ecosystem and easiest rich tables/charts, but very large deployment footprint.

Strengths:

- Excellent UI component ecosystem.
- Best-in-class table/chart/diagnostics UX potential.
- Browser automation testing is strong.
- Easy to build modern settings, rename, audit, and telemetry views.

Weaknesses:

- Large runtime size.
- Node/Electron packaging adds another runtime family.
- Local backend lifecycle/security must be carefully designed.
- Overkill for a one-operator workstation if Tauri/WebView2 can do the same job lighter.

Verdict: Technically viable but not the best footprint for this bundle.

### Option G: Tauri / WebView2 Shell With Local Python Backend

Modern web frontend in a lighter desktop shell, using the system WebView2 runtime on Windows or a Tauri-managed shell. Python remains backend owner.

Strengths:

- Rich UI, tables, charts, search, diagnostics, and settings are much easier than Tk.
- Browser-style UI testing becomes practical.
- Python backend and PowerShell pipeline can stay in their current languages.
- Smaller than Electron when WebView2 is already present.
- Fits a one-operator local workstation if the API is bound to localhost or named pipes.
- Allows an incremental migration: existing Tk app stays while web UI is built against the same local backend.

Weaknesses:

- Adds frontend toolchain complexity.
- Tauri adds Rust/build complexity if chosen.
- WebView2 availability and update behavior must be considered for portability.
- Backend lifecycle, auth, port selection, local-only binding, and shutdown must be designed.
- The current backend boundary is not ready yet.

Verdict: Best long-term direction if the operator is comfortable with a local web UI and the project can tolerate a staged migration.

### Option H: Browser-Based Local Web App

Same backend/frontend split as the Tauri/WebView2 option, but opened in a normal browser.

Strengths:

- Lowest shell complexity.
- Excellent development and testing ergonomics.
- Can be introduced as an optional diagnostics/preview UI first.
- No desktop shell migration required to validate the backend API.

Weaknesses:

- Feels less like a single desktop app.
- Browser selection/default browser behavior may confuse non-programmer operation.
- File picker and native notifications need browser-compatible solutions.
- Must manage local server lifecycle and local-only security.

Verdict: Best migration bridge. Build this first before committing to a shell.

### Option I: Hybrid Python Backend Plus Modern Frontend

This is the architectural pattern rather than a single framework. Python owns application/backend commands and state. A frontend, web shell, Qt UI, or current Tk UI talks to the same contract.

Strengths:

- Preserves PowerShell pipeline investment.
- Avoids rewriting backend logic into UI framework code.
- Lets the current GUI and future GUI coexist during migration.
- Creates testable command/query boundaries.
- Prevents future UI features from coupling directly to process and filesystem internals.

Weaknesses:

- Requires discipline. A partial API plus continued `app.*` mutation would just add a second coupling layer.
- Initial extraction work is not glamorous.
- Requires stable DTOs, schema validation, and event model ownership.

Verdict: This is the required foundation regardless of final UI framework.

## Deep Comparison Matrix

Scores are 1 to 5. Higher is better. Scores assume the current PowerShell pipeline remains and the UI is migrated incrementally.

| Criterion | Current CustomTkinter Refactor | PySide6 / Qt | WPF / .NET | WinUI 3 | Avalonia | Electron + Backend | Tauri/WebView2 + Backend | Browser Local Web App |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Maintainability after cleanup | 3 | 4 | 4 | 3 | 4 | 4 | 4 | 4 |
| Windows integration | 3 | 4 | 5 | 5 | 4 | 3 | 4 | 2 |
| Packaging complexity | 5 | 3 | 3 | 2 | 3 | 2 | 3 | 4 |
| UI responsiveness model | 3 | 4 | 5 | 4 | 4 | 5 | 5 | 5 |
| Long-running background task fit | 3 | 4 | 5 | 4 | 4 | 4 | 4 | 4 |
| Telemetry/graphing support | 2 | 4 | 4 | 4 | 4 | 5 | 5 | 5 |
| Table/grid quality | 2 | 4 | 5 | 4 | 4 | 5 | 5 | 5 |
| File/folder picker support | 4 | 4 | 5 | 5 | 4 | 3 | 3 | 2 |
| Process management fit | 4 | 4 | 5 | 4 | 4 | 3 | 3 | 3 |
| Async/event model | 2 | 4 | 5 | 4 | 4 | 5 | 5 | 5 |
| Learning curve from current code | 5 | 3 | 2 | 2 | 2 | 3 | 3 | 4 |
| AI code-generation friendliness | 3 | 4 | 4 | 3 | 3 | 5 | 5 | 5 |
| Deployment size | 5 | 3 | 4 | 3 | 3 | 1 | 4 | 5 |
| Portability | 4 | 4 | 2 | 1 | 4 | 4 | 4 | 5 |
| Bundled tool compatibility | 5 | 5 | 4 | 4 | 4 | 5 | 5 | 5 |
| Upgrade risk | 5 | 3 | 2 | 2 | 2 | 2 | 3 | 4 |
| Incremental migration fit | 5 | 3 | 2 | 2 | 2 | 4 | 5 | 5 |
| Testing strategy quality | 2 | 3 | 4 | 4 | 4 | 5 | 5 | 5 |

### Interpretation

- CustomTkinter wins only on near-term continuity and packaging simplicity.
- PySide6 is the best single-process Python desktop answer.
- WPF is the best Windows-native answer but the migration cost is high and it pulls the project away from Python-first development.
- WinUI 3 is not justified for this workload.
- Avalonia is only compelling if cross-platform .NET becomes important.
- Electron has the best UI ecosystem but the worst footprint.
- Tauri/WebView2 plus a Python backend is the best long-term app shape if a modern UI is desired without throwing away the backend.
- A browser-based local web app is the safest bridge because it validates the backend boundary before committing to a shell.

## Best Fit Recommendation

### Recommendation

Use a staged hybrid direction:

1. Keep the current CustomTkinter app as the production UI for now.
2. Extract a UI-neutral Python application/backend boundary behind the current app.
3. Build an optional local web UI against that backend, first as read-only diagnostics/live status, then queue/rename/settings.
4. After the web UI proves stable, package it either as:
   - a Tauri/WebView2 desktop shell, if single-window desktop feel is important; or
   - a browser-launched local web app, if simplest packaging wins.

PySide6 should remain the fallback recommendation if the operator strongly prefers a pure Python desktop widget app and does not want a web/frontend toolchain.

### Why Not Immediately Migrate To Qt?

Qt would improve widgets, tables, and threading. It would not automatically fix the actual architectural problem: the GUI and backend are still joined through a shared app object, Tk variables, direct process handles, and direct controller mutation. A Qt rewrite before backend extraction would likely recreate the same coupling in a different framework.

### Why Hybrid Web Is The Best Long-Term Fit

The product is now an operations console. It needs strong tables, live status, charts, diagnostics, filters, structured settings, and batch editing. Those are web UI strengths. The backend already has Python contracts and PowerShell orchestration. The cleanest long-term split is:

- Python backend: owns filesystem, process lifecycle, config, state contracts, FFmpeg/PowerShell launch, telemetry sampling, queue/pending/audit/rename logic.
- Frontend: owns presentation, interaction, tables, graphs, and operator workflows.

This keeps media safety and pipeline correctness in the existing tested languages while giving the UI a better platform.

## Migration Difficulty

| Path | Difficulty | Reason |
|---|---:|---|
| Stay CustomTkinter and refactor | Low-medium | No framework switch, but state extraction still required. |
| PySide6/Qt | Medium-high | Python reuse is good, but all views/controllers must be rewritten or adapted. |
| WPF/.NET | High | Requires C#/XAML UI and IPC/API boundary; excellent final state but expensive. |
| WinUI 3 | High | Rewrite plus deployment/tooling complexity. |
| Avalonia | High | Rewrite and .NET backend bridge with less Windows-native payoff than WPF. |
| Electron | High | Web UI plus Node/Electron packaging plus backend lifecycle. |
| Tauri/WebView2 | Medium-high | Web UI plus backend API plus shell lifecycle; lighter than Electron but still a new toolchain. |
| Browser local web app | Medium | Backend API and web UI required, but no desktop shell initially. |

The key point: every successful migration requires the same first step, which is a UI-neutral backend/application facade.

## Risks By Option

### Staying CustomTkinter Forever

- The UI will keep accumulating custom table/chart/layout code.
- Large tables and diagnostics views will remain harder to make excellent.
- Testing will remain more expensive and less deterministic.
- Future features will pressure `app_bootstrap.py`, `app.py`, and controller-to-app coupling again.

### Migrating To PySide6

- Qt packaging and plugin issues may create release friction.
- The migration can become a large widget rewrite without fixing service boundaries.
- UI logic may still directly call Python backend internals unless an application facade is enforced.

### Migrating To WPF / WinUI / Avalonia

- Cross-language boundary becomes mandatory.
- Developer velocity may drop if the project owner prefers Python/PowerShell.
- Debugging now spans PowerShell, Python, and .NET.
- Rewriting settings, rename, and diagnostics in XAML before backend stabilization would be high risk.

### Migrating To Electron

- Bundle size increases significantly.
- Node dependency and update surface becomes part of the product.
- Security rules for local API access must be explicit.

### Migrating To Tauri/WebView2

- Tauri introduces Rust build tooling if used.
- WebView2 availability must be verified in the release environment.
- Local backend startup/shutdown must be robust.
- File dialogs and native shell operations need explicit backend endpoints or shell bridges.

### Browser Local Web App

- It may feel less like a desktop app.
- Browser security model complicates direct filesystem operations.
- The local server must avoid exposing sensitive paths or commands beyond localhost.

## What To Keep From The Current App

- Existing PowerShell pipeline execution model.
- Scratch-first, source-safe pipeline behavior.
- PSD1 config as the live backend config format.
- `DesktopAppService` mixin decomposition as a temporary facade.
- ActiveJobs, control flag, progress, event, pending publish, and queue snapshot contracts.
- Run log strategy that redirects stdout/stderr to files.
- Current remediation tests and reliability regression checks.
- Diagnostics concepts: recent errors, log tails, pipeline events, ActiveJobs, control flags, stale progress recovery.
- Rename service logic, especially the recent TV season logic, movie scrub filters, sidecar tagging, transaction protections, and selected-row behavior.
- Release-builder hygiene and bundled runtime/tool resolution.
- Local status server concept, but not necessarily its current implementation or HTML.

## What To Replace

- Direct controller access to `app.*` as the main state API.
- `tk.StringVar` and `tk.BooleanVar` as the canonical application state.
- View code that owns background threads or network polling directly, especially in `views\network_tab.py`.
- `ttk.Treeview` as the long-term table model for queue/audit/completed/rename workflows.
- Custom graph widgets as the long-term telemetry visualization layer.
- Ad hoc command callbacks that directly mutate process handles and UI variables.
- Mixed state initialization in `app_bootstrap.py`.
- The current local status server as a one-off HTML view. Replace it with a versioned local API and optional web UI.

## Suggested Target Architecture

```text
PowerShell Pipeline
  - MediaPipeline_chatgpt.ps1
  - Modules/*.ps1
  - FFmpeg/ffprobe/MKVToolNix/PgsToSrt wrappers
  - PSD1 config and JSON state contracts

Python Backend
  - Application facade
  - Process runner and lifecycle service
  - Settings/config service
  - Queue/audit/pending/rename services
  - Telemetry sampler
  - State store and contract validators
  - Local API server

Frontend
  - Current CustomTkinter UI during transition
  - Future web UI or PySide6 UI
  - Calls backend commands/queries only
  - Renders tables, charts, diagnostics, settings, and rename workflows
```

### Target Python Packages

Suggested future package shape:

```text
DesktopApp/mediapipeline_desktop_app/
  application/
    facade.py              # UI-neutral command/query boundary
    dto.py                 # app-facing DTOs
    commands.py            # start/stop/pause/refresh/rename/apply commands
    errors.py              # user-facing error envelope
  backend/
    process_lifecycle.py   # extracted from service_processes.py
    telemetry.py           # extracted sampler with event output
    config_store.py        # PSD1 read/write/validate facade
    state_store.py         # JSON state contracts and atomic persistence
    queue_service.py
    audit_service.py
    pending_publish.py
    rename_service.py
  api/
    server.py              # localhost API lifecycle
    routes_status.py
    routes_commands.py
    routes_settings.py
    routes_rename.py
    routes_diagnostics.py
  ui_tk/
    app.py                 # current CustomTkinter adapter
    views/
    controllers/
  ui_web/
    package.json
    src/
```

This does not need to be created all at once. The first step is `application/facade.py` plus DTOs and tests.

## Backend/Frontend Boundary

The future UI should not know where `pipeline_progress.json`, ActiveJobs records, or pending publish manifests live. It should ask the backend for stable DTOs.

### Query Endpoints / Methods

| Query | Returns | Current Source |
|---|---|---|
| `get_app_snapshot()` | Current activity, pipeline state, counts, schedule state, progress, recent events, telemetry, health flags. | `service_status.py`, `app_state_controller.py`, `TelemetryController`. |
| `get_queue_view(filter, sort)` | Queue records plus counts and warnings. | `service_queue.py`, queue controllers. |
| `get_audit_view(filter, sort)` | Audit/failure/completed/report summaries. | `service_status.py`, audit/failure/completed services. |
| `get_pending_publish_view()` | Parked outputs, manifests, destinations, sidecars, state. | `service_pending_publish.py`, pending controller. |
| `get_settings_workspace()` | Config fields, values, dirty state, validation, profile info. | `service_config.py`, settings controllers. |
| `get_rename_preview(request)` | Rename rows, scrubbed names, final names, status, warnings, sidecar operations. | `service_rename.py`, rename controllers. |
| `get_diagnostics()` | ActiveJobs, control flags, stale progress notes, log tails, recent errors. | `service_status.py`, contracts, diagnostics controller. |

### Command Endpoints / Methods

| Command | Behavior |
|---|---|
| `start_pipeline(mode, options)` | Launch PowerShell pipeline through the process service; return launch result and log paths. |
| `stop_after_current()` | Write control flag and return current control state. |
| `pause_pipeline(enable)` | Create/remove pause control flag and return state. |
| `kill_active_processes()` | Kill known process trees with result messages. |
| `refresh_queue()` | Build queue preview without blocking UI thread. |
| `run_audit(options)` | Launch audit and return ActiveJobs/run-log info. |
| `run_rerun_csv(options)` | Launch rerun CSV and return ActiveJobs/run-log info. |
| `drain_pending_publish()` | Launch pending drain mode and return run info. |
| `save_settings(changes)` | Validate/persist PSD1 changes atomically. |
| `apply_rename(plan)` | Run transactional rename plan and return results. |
| `open_path(path_id)` | Backend-mediated file/folder open, with long-path handling. |

### Contract Rules

- DTOs must not expose raw Tk variables or widgets.
- Commands return structured `CommandResult` objects with `ok`, `message`, `warnings`, `errors`, `state_refresh_hint`, and related log paths.
- Long-running commands return a launch/job ID immediately, then progress is observed through snapshots/events.
- File paths returned to UI should be explicit and redacted where appropriate for remote/status views.
- Backend owns filesystem mutation. Frontend never directly renames, deletes, writes config, or spawns processes.

## Process And Telemetry Model

The process model should remain backend-owned:

- Keep `subprocess.Popen` and run logs in Python backend service code.
- Continue logging full PowerShell command lines and log paths.
- Continue redirecting stdout/stderr to files instead of GUI pipes.
- Keep ActiveJobs records as the durable process visibility layer.
- Keep `psutil` process-tree cleanup where available.
- Keep launch readiness checks but move blocking sleep out of UI-initiated call paths where possible.
- Expose process state through snapshot DTOs rather than direct `Popen` handles.

Telemetry should evolve from Tk polling into a backend sampler plus UI stream:

- Backend sampler owns `psutil` and `nvidia-smi` calls.
- Snapshot always includes `gpu_present`, `gpu_encoder_percent`, `gpu_count`, `gpu_rows`, `source`, `error`, and `sampled_at`.
- UI should show 0 percent as real data, not empty/missing.
- Web/PySide frontends should subscribe or poll snapshots; they should not call `nvidia-smi`.
- Long-term web UI can graph samples with a frontend chart library.

## Packaging/Installer Strategy

### Keep Existing Portable Bundle For Now

Current release packaging is good for this project. It:

- Copies the bundle to a deployable root.
- Excludes live config by default.
- Excludes run logs/state/runtime artifacts by default.
- Includes or excludes tests/dev docs/optional tools by switch.
- Records bundled tool versions and Python package versions in `release_manifest.json`.
- Prefers bundled PowerShell 7, Python, FFmpeg, MKVToolNix, and PgsToSrt.

### If Staying CustomTkinter

- No packaging redesign required.
- Add any new backend modules to the package as normal Python source.
- Add tests to release verification if desired.

### If Migrating To PySide6

- Bundle PySide6 and Qt plugins under the Python runtime.
- Add environment checks for Qt plugin paths.
- Update release manifest with PySide6 version.
- Expect a larger package and more verification cases.

### If Migrating To Browser Local Web App

- Add static frontend build output under `DesktopApp\web`.
- Add a Python local API/server launcher.
- Use the current launcher to start backend and open browser or embedded shell later.
- Keep all PowerShell/tool bundle logic unchanged.

### If Migrating To Tauri/WebView2

- Keep Python backend packaged exactly as today.
- Add a shell executable that starts or connects to the local backend.
- Use localhost or named-pipe style binding; default to `127.0.0.1`.
- Add a startup health endpoint and deterministic shutdown endpoint.
- Add release verification for WebView2/shell assets.

## Testing Strategy

### Tests To Keep

- Existing `DesktopApp\tests` contract/process/status/rename/controller tests.
- `Pipeline\Tests\Invoke-ReliabilityRegressionChecks.ps1`.
- Release packaging verification scripts.

### Tests To Add Before UI Migration

| Test Area | Purpose |
|---|---|
| Application facade unit tests | Ensure UI-neutral commands return stable DTOs and do not require Tk root. |
| Snapshot DTO tests | Ensure pipeline/telemetry/queue/diagnostics snapshots serialize cleanly. |
| Command-result tests | Ensure start/stop/pause/rename/settings errors are structured consistently. |
| Backend API smoke tests | Start local API on random localhost port, call health/status, then shut down. |
| Rename API tests | Ensure TV/movie preview matches current rename service behavior. |
| Settings API tests | Ensure dirty state, validation warnings, save-in-place, and unknown key preservation survive API boundary. |
| Process launch adapter tests | Ensure launch command builds ActiveJobs/run-log output without exposing `Popen` to frontend. |

### Tests After Web UI Prototype

- Browser automation for diagnostics/live status.
- Browser automation for table filtering/sorting/selection.
- Browser automation for rename preview/apply selected dry-path workflows.
- API contract snapshot fixtures for queue/audit/pending publish.
- Packaging test that verifies static frontend assets and backend server startup.

## Incremental Migration Plan

### Phase 0: Freeze Current UI As Production UI

Goal: no framework rewrite yet.

Tasks:

- Keep CustomTkinter app operational.
- Do not port views until backend facade exists.
- Keep fixing production bugs in the current app.
- Document all new UI-facing logic as backend-owned or view-owned.

Risk: low.

### Phase 1: Extract UI-Neutral Application Facade

Goal: create a backend command/query layer that current Tk can use without changing behavior.

Tasks:

- Add `application/dto.py` and `application/facade.py`.
- Start with read-only methods: `get_app_snapshot()`, `get_diagnostics()`, `get_telemetry()`.
- Add command-result envelope.
- Add tests that instantiate facade without Tk.
- Do not remove existing controllers yet.

Risk: low-medium. This is extraction, not behavior change.

### Phase 2: Move Tk Controllers Toward The Facade

Goal: reduce direct `app.service` and `app.*` dependency for selected features.

Tasks:

- Migrate diagnostics and live status first.
- Then migrate rename preview.
- Then migrate settings save/validate.
- Leave high-risk process launch commands until the command-result envelope is stable.

Risk: medium.

### Phase 3: Add Local API Server Beside Tk

Goal: expose the facade over localhost for an optional UI.

Tasks:

- Add `/api/health`, `/api/snapshot`, `/api/diagnostics`, `/api/telemetry`.
- Bind to `127.0.0.1` by default.
- Add random port support and health file/URL reporting.
- Add shutdown lifecycle.
- Reuse existing status server only as prior art, not as the final API.

Risk: medium because server lifecycle must not interfere with Tk shutdown.

### Phase 4: Prototype Web Diagnostics/Live View

Goal: validate the framework direction without touching core controls.

Tasks:

- Build read-only frontend for Live, Diagnostics, and telemetry graphs.
- No start/stop/kill commands yet.
- Verify browser automation and packaging of static assets.

Risk: low-medium.

### Phase 5: Add Queue And Rename Web Views

Goal: validate high-value table/batch-edit workflows.

Tasks:

- Queue table with filtering/sorting/details.
- Rename preview with TV/movie modes, filter toggles, selected rows, sidecar flags.
- No destructive apply until API transaction tests are mature.

Risk: medium.

### Phase 6: Add Settings And Safe Commands

Goal: make web UI operational but still reversible.

Tasks:

- Settings editor with validation and dirty state.
- Start validate-only and refresh commands.
- Then pause/stop-after-current.
- Kill commands only after explicit confirmation and tests.

Risk: medium-high.

### Phase 7: Choose Shell

Goal: decide between browser-only, Tauri/WebView2, or PySide6 fallback based on the prototype.

Decision criteria:

- Does the web UI feel better enough to justify a shell?
- Does packaging remain reliable?
- Is startup/shutdown deterministic?
- Is local-only API security acceptable?
- Are table/diagnostics workflows materially better?

Risk: medium.

### Phase 8: Retire Or Keep Tk

Goal: avoid duplicate long-term UI maintenance.

Options:

- Keep Tk as fallback maintenance mode.
- Freeze Tk and remove from default launcher.
- Fully retire Tk only after the new UI can run pipeline, audit, rerun, pending drain, rename, settings, diagnostics, release checks, and maintenance.

Risk: high if done too early.

## Questions For The Operator

These questions affect the final shell choice, not the immediate backend extraction:

1. Is a browser tab acceptable during the migration phase, or must the app always feel like one desktop window?
2. Is a larger package acceptable if the UI becomes significantly better?
3. Are Node/Rust build tools acceptable in the development workflow, or should the project stay Python/PowerShell only?
4. Should the future UI support remote viewing from another device on the LAN, or must everything remain localhost-only?
5. Should network coordinator/worker mode become a supported production feature, or remain experimental?
6. Is a pure Python desktop stack preferred even if the UI table/chart experience is less flexible than web?
7. Should the long-term app have an installer, or remain a portable folder with launchers?
8. Is keeping a fallback Tk maintenance UI valuable, or would one UI be preferred once migration is complete?

## Final Recommendation

The current GUI should remain in place for production use while the backend boundary is extracted. It is stable enough to keep, but it is not the best final framework for the product's growing complexity.

The best long-term direction is a hybrid Python backend plus modern web frontend, initially as a browser-based local web app and later packaged as a Tauri/WebView2 shell if a single-window desktop experience is desired.

PySide6/Qt is the best fallback if the operator rejects a web frontend/toolchain. WPF is strong but too large a language/platform shift. WinUI 3 and Avalonia are not the best fit for this project's current needs.

Do not migrate the UI until the application facade exists and current Tk controllers can call it. The facade is the next architectural milestone.

## First Safe Implementation Chunk

### Phase Name

Application Facade Phase 1: read-only status and diagnostics boundary.

### Target Files

- Add `DesktopApp\mediapipeline_desktop_app\application\__init__.py`
- Add `DesktopApp\mediapipeline_desktop_app\application\dto.py`
- Add `DesktopApp\mediapipeline_desktop_app\application\facade.py`
- Add or update `DesktopApp\tests\test_application_facade.py`
- Do not modify view layout.
- Do not change PowerShell pipeline behavior.

### Goal

Create a UI-neutral facade that can be instantiated without a Tk root and can return read-only status/diagnostics/telemetry DTOs from existing services.

### Minimal Strategy

1. Wrap an existing `DesktopAppService` instance.
2. Define simple serializable DTOs:
   - `CommandResult`
   - `AppSnapshotDto`
   - `TelemetryDto`
   - `DiagnosticsDto`
3. Start with read-only calls only:
   - `get_snapshot(resolved, audit_root)`
   - `get_cached_telemetry()`
   - `get_launch_log_summary()`
   - `get_diagnostics_summary(snapshot)`
4. Keep existing Tk app unchanged.
5. Add tests that prove DTOs can be created without importing CustomTkinter or creating a Tk root.

### Expected Risk

Low. This should be additive and should not change operator behavior.

### Validation Strategy

- Run new facade tests.
- Run existing `DesktopApp\tests` suite.
- Run `Pipeline\Tests\Invoke-ReliabilityRegressionChecks.ps1`.
- Launch the current app once to confirm no import/path regression.

### Why This Chunk First

Every framework option needs this boundary. It reduces migration risk without committing to Qt, web, Tauri, Electron, or .NET. It also improves maintainability even if the current CustomTkinter UI remains for a long time.

