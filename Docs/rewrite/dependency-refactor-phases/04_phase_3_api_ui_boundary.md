# Phase 3 - API/UI Boundary

Previous: [03_phase_2_status_observability_telemetry.md](03_phase_2_status_observability_telemetry.md)

Next: [05_phase_4_shared_blast_radius.md](05_phase_4_shared_blast_radius.md)

Source plan: `Docs/rewrite/CODEX_DEPENDENCY_REFACTOR_PLAN (1).md`

## Carry-Forward Requirements

Do not start this phase until Phase 0 has produced dependency baseline evidence.
Prefer starting after Phases 1 and 2 are complete unless the user explicitly
chooses a different order.

Before doing any work, read `AGENTS.md`, `Docs/CURRENT_PROJECT_STATE.md`,
`OPEN_WORK_CHECKLIST.md`, `Docs/generated/PROJECT_INDEX.md`,
[00_navigation_and_tracker.md](00_navigation_and_tracker.md), and prior phase
handoffs.

Rules to preserve:

- No intentional product behavior change.
- Backend owns media policy, filesystem mutation, settings persistence, queue
  mutation, pending-publish drain, rename apply, and process lifecycle choices.
- WebView/Tauri must not gain backend-owned behavior during this phase.
- Use summaries before opening full source files.
- Use the bundled Python interpreter at
  `.\DesktopApp\Runtime\Python\python.exe`.
- Move neutral preference contracts or IO into a neutral owner; keep actual UI
  rendering behavior in UI-owned modules.
- Stop after this phase and produce a handoff.

## Phase Goal

Remove the forbidden API-to-UI import direction:

```text
app.api must not import app.ui
```

## Required Summary Reads

Inspect these summaries first:

```text
summaries/app/api/commands_ui_preferences.py.md
summaries/app/ui/preferences.py.md
```

Open full source only when a summary is high priority or does not contain the
symbols needed for the change.

## Tasks

1. Verify the actual imports with the Phase 0 checker or atlas.
2. Separate neutral preference model, schema, path, read, or write logic from
   UI-specific behavior.
3. Move neutral logic to one of these owners:

   ```text
   app/contracts/preferences.py
   app/ui_preferences.py
   app/user_preferences.py
   ```

4. Choose `app/contracts/preferences.py` if the moved code is mostly stable
   DTO/schema.
5. Choose a small domain module if the moved code owns file IO or persistence.
6. Update `app.api.commands_ui_preferences` to import the neutral module.
7. Keep actual UI-specific behavior in `app.ui.preferences`.
8. Refresh summaries for touched source files.
9. Update architecture docs or dependency allowlist entries from Phase 0.

## Acceptance Criteria

- `app.api.commands_ui_preferences` no longer imports `app.ui` or
  `app.ui.preferences`.
- API tests pass.
- UI preference behavior is unchanged.
- Dependency checker reports no API-to-UI imports.
- No WebView route, settings save, or UI mutation authority is added.

## Suggested Validation

```powershell
.\DesktopApp\Runtime\Python\python.exe -m pytest DesktopApp\tests\test_application_facade_local_api.py DesktopApp\tests\test_application_facade_web_static.py
.\DesktopApp\Runtime\Python\python.exe .\scripts\dev\check_dependency_boundaries.py
.\DesktopApp\Runtime\Python\python.exe .\scripts\dev\refresh_summaries.py --check
```

Adjust the pytest targets if source inspection shows a more focused preference
test surface, and record any substitutions.

## Phase Activity Log

| Date | Agent | Action | Evidence | Next |
|---|---|---|---|---|
| 2026-05-31 | Codex | Split Phase 3 into its own operating file | Original plan inspected; no API/UI imports changed | Start Phase 3 after baseline and prior handoff |
| 2026-05-31 | Codex | Completed Phase 3 API/UI boundary cleanup | Checker reports 0 forbidden `app.api` to `app.ui` imports; focused UI preference route and mutation-boundary tests passed; unrelated WebView static failures recorded | Start Phase 4 when requested |

## Completion Handoff

```text
Phase: 3 - API/UI boundary
Status: Complete
Files changed: app/ui_preferences.py; app/ui/preferences.py; app/api/commands_ui_preferences.py; Docs/architecture/DEPENDENCY_BOUNDARY_RULES.md; Docs/generated/PROJECT_INDEX.md; Docs/generated/DEPENDENCY_GRAPH.md; refreshed summaries for touched source files; this phase file; 00_navigation_and_tracker.md.
Behavior changes: None intended. The same UI preference schema, path, filtering, read, and write behavior now lives in neutral app.ui_preferences while app.ui.preferences remains a UI package import surface.
Checks run: .\DesktopApp\Runtime\Python\python.exe -m pytest DesktopApp\tests\test_application_facade_core_contracts.py -k ui_preferences (1 passed); .\DesktopApp\Runtime\Python\python.exe -m pytest DesktopApp\tests\test_application_facade_local_api.py DesktopApp\tests\test_application_facade_core_contracts.py -k "ui_preferences or ui-preferences or route" (3 passed); .\DesktopApp\Runtime\Python\python.exe -m pytest DesktopApp\tests\test_webview_frontend_mutation_boundary.py DesktopApp\tests\test_api_contract_payload.py (22 passed); .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\check_dependency_boundaries.py --max-internal-imports 1 (report-only baseline completed); .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\refresh_summaries.py --check (passed); .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\generate_project_index.py --check (passed); .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\check_active_doc_references.py (passed); git diff --check (passed with existing CRLF normalization warnings). Attempted suggested WebView/Local API static targets also exposed unrelated frontend static failures: DesktopApp\tests\test_application_facade_web_static.py failed 2 assertions for launch/diagnostics WebView markup, and full DesktopApp\tests\test_application_facade_local_api.py failed 1 read-only web prototype assertion in the same static WebView surface.
Dependency checker result: 1411 internal app import entries; 1 module-level cycle remains in app.contracts.source_media*; 0 package-level cycles; 0 direct app.shared imports; 32 direct app.shared.utils imports; 38 direct app.shared.constants imports; 19 direct app.shared.protocols imports; 0 forbidden app.config higher-level imports; 0 forbidden app.api to app.ui imports; 0 app.observability to app.status imports; 0 app.telemetry to app.observability imports; 0 app.telemetry to app.status imports.
Generated artifacts updated: Docs/generated/PROJECT_INDEX.md and Docs/generated/DEPENDENCY_GRAPH.md regenerated from 741 summaries.
Summaries refreshed: Full refresh wrote 3 summaries, left 738 unchanged, and pruned 0 orphan summaries. Final check reported 741 source files all current with no orphan summaries.
Known risks: The dependency checker is static AST analysis only. Suggested broad WebView static tests have unrelated pre-existing failures outside this Python API/UI dependency change. Unrelated dirty files in queue/engine/test areas remain untouched.
Explicit deferrals: Did not address the app.contracts.source_media* module cycle or app.shared submodule imports. Did not change WebView routes, settings save behavior, UI mutation authority, media policy, queue, publish/drain, rename apply, process lifecycle, or WebView/Tauri ownership.
Next phase: 4 - Reduce app.shared blast radius
```
