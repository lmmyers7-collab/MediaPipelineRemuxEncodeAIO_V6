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

## Completion Handoff

```text
Phase: 3 - API/UI boundary
Status:
Files changed:
Behavior changes:
Checks run:
Dependency checker result:
Generated artifacts updated:
Summaries refreshed:
Known risks:
Explicit deferrals:
Next phase: 4 - Reduce app.shared blast radius
```
