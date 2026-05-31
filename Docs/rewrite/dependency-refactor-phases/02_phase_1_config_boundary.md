# Phase 1 - Break app.config Higher-Level Imports

Previous: [01_phase_0_baseline_and_dependency_guard.md](01_phase_0_baseline_and_dependency_guard.md)

Next: [03_phase_2_status_observability_telemetry.md](03_phase_2_status_observability_telemetry.md)

Source plan: `Docs/rewrite/CODEX_DEPENDENCY_REFACTOR_PLAN (1).md`

## Carry-Forward Requirements

Do not start this phase until Phase 0 has produced dependency baseline evidence
or the user explicitly instructs you to proceed despite a missing baseline.

Before doing any work, read `AGENTS.md`, `Docs/CURRENT_PROJECT_STATE.md`,
`OPEN_WORK_CHECKLIST.md`, `Docs/generated/PROJECT_INDEX.md`,
[00_navigation_and_tracker.md](00_navigation_and_tracker.md), and the Phase 0
handoff.

Rules to preserve:

- No intentional product behavior change.
- No media policy, queue, publish/drain, settings persistence, source movement,
  cleanup, or WebView/Tauri ownership changes.
- Use summaries before opening full source files.
- Use the bundled Python interpreter at
  `.\DesktopApp\Runtime\Python\python.exe`.
- Do not leave compatibility shims that preserve the forbidden package cycle.
- Prefer moving pure contracts downward into `app.contracts`.
- Keep diffs narrow and avoid broad formatting churn.
- Stop after this phase and produce a handoff.

## Phase Goal

Make `app.config` low-level again:

```text
app.orchestration may import app.config
app.config must not import app.orchestration
app.config should not import app.decide
```

## Required Summary Reads

Inspect these summaries first:

```text
summaries/app/config/settings_patch_facade.py.md
summaries/app/config/preset_migration.py.md
summaries/app/orchestration/planner.py.md
summaries/app/decide/processing_decision.py.md
```

Open full source only when a summary is high priority or does not contain the
symbols needed for the change.

## Tasks

1. Verify the actual imports with the Phase 0 checker or atlas.
2. If `app.config.settings_patch_facade` calls orchestration or planning logic,
   move that facade to a higher-level owner such as:

   ```text
   app/orchestration/settings_patch_facade.py
   ```

   Use a different existing owner only if source review proves it is a better
   fit.

3. Update internal imports to the new location.
4. Do not leave `app.config` importing `app.orchestration`.
5. If `app.config.preset_migration` imports decision-only types from
   `app.decide.processing_decision`, move pure DTO/type/enum contracts into
   `app.contracts`.
6. If `preset_migration` imports real decision behavior, move that behavior out
   of config and into orchestration/planning instead.
7. Refresh summaries for touched source files.
8. Update any architecture docs or dependency allowlist created in Phase 0.

## Acceptance Criteria

- `app.config` has no imports from `app.orchestration`.
- Preferably, `app.config` has no imports from `app.decide`.
- The `app.config` / `app.orchestration` package cycle is gone.
- Relevant config and orchestration tests pass.
- Public behavior is unchanged.
- No compatibility shim keeps the cycle alive.

## Suggested Validation

```powershell
.\DesktopApp\Runtime\Python\python.exe -m pytest tests\contract tests\orchestration DesktopApp\tests\test_settings_pipeline_plan_preview.py
.\DesktopApp\Runtime\Python\python.exe .\scripts\dev\refresh_summaries.py --check
.\DesktopApp\Runtime\Python\python.exe .\scripts\dev\generate_project_index.py --check
.\DesktopApp\Runtime\Python\python.exe .\scripts\dev\check_dependency_boundaries.py
```

Adjust the pytest targets if source inspection shows a different touched test
surface, and explain any skipped or unavailable command.

## Phase Activity Log

| Date | Agent | Action | Evidence | Next |
|---|---|---|---|---|
| 2026-05-31 | Codex | Split Phase 1 into its own operating file | Original plan inspected; no config imports changed | Start Phase 1 after Phase 0 baseline |

## Completion Handoff

```text
Phase: 1 - Break app.config higher-level imports
Status:
Files changed:
Behavior changes:
Checks run:
Dependency checker result:
Generated artifacts updated:
Summaries refreshed:
Known risks:
Explicit deferrals:
Next phase: 2 - Status, observability, and telemetry direction
```
