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
| 2026-05-31 | Codex | Completed Phase 1 config boundary cleanup | Checker reports 0 forbidden `app.config` higher-level imports and the `app.config`/`app.orchestration` package cycle is gone; focused tests passed | Start Phase 2 when requested |

## Completion Handoff

```text
Phase: 1 - Break app.config higher-level imports
Status: Complete
Files changed: app/contracts/decision_policy.py; app/contracts/__init__.py; app/config/preset_migration.py; app/config/settings_patch_facade.py removed; app/orchestration/settings_patch_facade.py; app/decide/processing_decision.py; DesktopApp/mediapipeline_desktop_app/application/facade.py; Docs/architecture/DEPENDENCY_BOUNDARY_RULES.md; Docs/generated/PROJECT_INDEX.md; Docs/generated/DEPENDENCY_GRAPH.md; refreshed summaries for touched source/tooling files; this phase file; 00_navigation_and_tracker.md.
Behavior changes: None intended. This phase moved ownership of the settings patch preview facade and pure decision policy contract only.
Checks run: .\DesktopApp\Runtime\Python\python.exe -m pytest tests\contract tests\orchestration tests\decide\test_processing_decision.py tests\integration\test_handbrake_remux_regression_matrix.py DesktopApp\tests\test_settings_pipeline_plan_preview.py DesktopApp\tests\test_application_facade_settings_patch.py (89 passed); .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\refresh_summaries.py --check (passed); .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\generate_project_index.py --check (passed); .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\check_dependency_boundaries.py --max-internal-imports 1 (report-only baseline completed); .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\check_active_doc_references.py (passed); git diff --check (passed with existing CRLF normalization warnings).
Dependency checker result: 1409 internal app import entries; 1 module-level cycle remains in app.contracts.source_media*; 1 package-level cycle remains in app.observability/app.status/app.telemetry; 0 direct app.shared imports; 32 direct app.shared.utils imports; 38 direct app.shared.constants imports; 19 direct app.shared.protocols imports; 0 forbidden app.config higher-level imports; 3 app.api to app.ui imports remain; 3 app.observability to app.status imports remain; 2 app.telemetry to app.observability imports remain; 0 app.telemetry to app.status imports.
Generated artifacts updated: Docs/generated/PROJECT_INDEX.md and Docs/generated/DEPENDENCY_GRAPH.md regenerated from 740 summaries.
Summaries refreshed: Full refresh wrote 6 summaries, left 734 unchanged, and pruned 1 orphan summary. Final check reported 740 source files all current with no orphan summaries.
Known risks: EffectiveDecisionPolicy remains re-exported from app.decide.processing_decision for existing callers, but the canonical low-level contract is app.contracts.decision_policy and app.config no longer imports app.decide. The checker is static AST analysis only. Unrelated dirty files in queue/engine/test areas were left untouched.
Explicit deferrals: Did not address app.api to app.ui imports, the app.observability/app.status/app.telemetry cycle, the source_media contract module cycle, or app.shared submodule imports.
Next phase: 2 - Status, observability, and telemetry direction
```
