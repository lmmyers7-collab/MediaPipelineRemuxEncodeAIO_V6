# Phase 2 - Status, Observability, and Telemetry Direction

Previous: [02_phase_1_config_boundary.md](02_phase_1_config_boundary.md)

Next: [04_phase_3_api_ui_boundary.md](04_phase_3_api_ui_boundary.md)

Source plan: `Docs/rewrite/CODEX_DEPENDENCY_REFACTOR_PLAN (1).md`

## Carry-Forward Requirements

Do not start this phase until Phase 0 has produced dependency baseline evidence.
Prefer starting after Phase 1 is complete unless the user explicitly chooses a
different order.

Before doing any work, read `AGENTS.md`, `Docs/CURRENT_PROJECT_STATE.md`,
`OPEN_WORK_CHECKLIST.md`, `Docs/generated/PROJECT_INDEX.md`,
[00_navigation_and_tracker.md](00_navigation_and_tracker.md), and prior phase
handoffs.

Rules to preserve:

- No intentional product behavior change.
- No media policy, queue, publish/drain, settings persistence, source movement,
  cleanup, or WebView/Tauri ownership changes.
- This phase is Python-domain only. Do not move WebView telemetry JavaScript.
- Use summaries before opening full source files.
- Use the bundled Python interpreter at
  `.\DesktopApp\Runtime\Python\python.exe`.
- Keep raw telemetry collection, observability storage, and user-facing status
  presentation in clearly named owners.
- Stop after this phase and produce a handoff.

## Phase Goal

Adopt one documented direction unless source review proves a better one:

```text
app.status -> app.observability -> app.telemetry
```

Interpretation:

- `app.telemetry` gathers raw GPU, system, and runtime facts.
- `app.observability` reads and writes observability files, snapshots, metrics,
  and runtime evidence.
- `app.status` builds user-facing status views from observability, telemetry
  evidence, and active job state.

## Required Summary Reads

Inspect these summaries first:

```text
summaries/app/observability/status_facade.py.md
summaries/app/observability/status_policy.py.md
summaries/app/observability/status_files.py.md
summaries/app/status/service.py.md
summaries/app/telemetry/service.py.md
summaries/app/telemetry/gpu_usage.py.md
```

Open full source only when a summary is high priority or does not contain the
symbols needed for the change.

## Tasks

1. Verify the actual imports with the Phase 0 checker or atlas.
2. Move `app.observability.status_facade` into `app.status` if it constructs
   status-facing responses.
3. Update imports so `app.observability` no longer imports:

   ```text
   app.status
   app.status.active_jobs
   app.status.eta
   app.status.ffmpeg_progress
   ```

4. Keep observability storage and read/write code in `app.observability`.
5. Keep raw GPU and system collection code in `app.telemetry`.
6. Keep user-facing aggregation in `app.status`.
7. Refresh summaries for touched source files.
8. Update architecture docs or dependency allowlist entries from Phase 0.

## Acceptance Criteria

- `app.observability` does not import `app.status`.
- `app.telemetry` does not import `app.observability`.
- The package cycle among `app.observability`, `app.status`, and
  `app.telemetry` is gone.
- Status and telemetry tests pass.
- Status output remains unchanged unless tests intentionally expose a bug.
- No WebView telemetry files are moved in this phase.

## Suggested Validation

```powershell
.\DesktopApp\Runtime\Python\python.exe -m pytest DesktopApp\tests\test_status_service.py DesktopApp\tests\test_telemetry_service.py DesktopApp\tests\test_facade_status_policy.py
.\DesktopApp\Runtime\Python\python.exe .\scripts\dev\check_dependency_boundaries.py
.\DesktopApp\Runtime\Python\python.exe .\scripts\dev\refresh_summaries.py --check
```

If a listed test file does not exist in the current repo, use the closest
focused status, observability, telemetry, facade, or route tests and record the
substitution.

## Phase Activity Log

| Date | Agent | Action | Evidence | Next |
|---|---|---|---|---|
| 2026-05-31 | Codex | Split Phase 2 into its own operating file | Original plan inspected; no status or telemetry imports changed | Start Phase 2 after baseline and prior handoff |
| 2026-05-31 | Codex | Completed Phase 2 status/observability/telemetry direction cleanup | Checker reports 0 forbidden `app.observability` to `app.status`, 0 forbidden `app.telemetry` to `app.observability`, 0 forbidden `app.telemetry` to `app.status`, and 0 package-level cycles; focused status/telemetry tests passed | Start Phase 3 when requested |

## Completion Handoff

```text
Phase: 2 - Status, observability, and telemetry direction
Status: Complete
Files changed: app/observability/status_facade.py removed; app/status/facade.py; app/observability/system_metrics.py removed; app/telemetry/system_metrics.py; app/observability/__init__.py; app/telemetry/service.py; DesktopApp/mediapipeline_desktop_app/application/facade.py; DesktopApp/tests/test_telemetry_service.py; Docs/architecture/DEPENDENCY_BOUNDARY_RULES.md; Docs/generated/PROJECT_INDEX.md; Docs/generated/DEPENDENCY_GRAPH.md; refreshed summaries for touched source files; this phase file; 00_navigation_and_tracker.md.
Behavior changes: None intended. This phase moved Python ownership boundaries only: status-facing aggregation now lives in app.status, and raw CPU/memory metric sampling now lives in app.telemetry.
Checks run: .\DesktopApp\Runtime\Python\python.exe -m pytest DesktopApp\tests\test_status_service.py DesktopApp\tests\test_telemetry_service.py DesktopApp\tests\test_facade_status_policy.py DesktopApp\tests\test_service_status_active_jobs.py DesktopApp\tests\test_service_status_eta.py DesktopApp\tests\test_service_status_ffmpeg_progress.py DesktopApp\tests\test_service_status_files.py DesktopApp\tests\test_service_status_snapshot_runner.py DesktopApp\tests\test_service_status_readers.py DesktopApp\tests\test_service_status_progress.py DesktopApp\tests\test_service_status_presentation.py DesktopApp\tests\test_service_status_summary.py DesktopApp\tests\test_service_status_summary_sections.py DesktopApp\tests\test_service_status_errors.py (73 passed); .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\check_dependency_boundaries.py --max-internal-imports 1 (report-only baseline completed); .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\refresh_summaries.py --check (passed); .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\generate_project_index.py --check (passed); .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\check_active_doc_references.py (passed).
Dependency checker result: 1407 internal app import entries; 1 module-level cycle remains in app.contracts.source_media*; 0 package-level cycles; 0 direct app.shared imports; 32 direct app.shared.utils imports; 38 direct app.shared.constants imports; 19 direct app.shared.protocols imports; 0 forbidden app.config higher-level imports; 3 app.api to app.ui imports remain; 0 app.observability to app.status imports; 0 app.telemetry to app.observability imports; 0 app.telemetry to app.status imports.
Generated artifacts updated: Docs/generated/PROJECT_INDEX.md and Docs/generated/DEPENDENCY_GRAPH.md regenerated from 740 summaries.
Summaries refreshed: Full refresh wrote 5 summaries, left 735 unchanged, and pruned 2 orphan summaries. Final check reported 740 source files all current with no orphan summaries.
Known risks: The dependency checker is static AST analysis only. The remaining module-level source_media contract cycle and shared/API-UI findings are outside Phase 2. Unrelated dirty files in queue/engine/test areas remain untouched.
Explicit deferrals: Did not address app.api to app.ui imports, the source_media contract module cycle, or app.shared submodule imports. No WebView telemetry JavaScript was moved.
Next phase: 3 - API/UI boundary
```
