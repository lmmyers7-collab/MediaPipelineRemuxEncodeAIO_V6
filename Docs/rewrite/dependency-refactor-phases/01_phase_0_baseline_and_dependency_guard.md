# Phase 0 - Baseline and Dependency Guard

Previous: [00_navigation_and_tracker.md](00_navigation_and_tracker.md)

Next: [02_phase_1_config_boundary.md](02_phase_1_config_boundary.md)

Source plan: `Docs/rewrite/CODEX_DEPENDENCY_REFACTOR_PLAN (1).md`

## Carry-Forward Requirements

This phase is baseline and tooling only. Do not fix architecture yet.

Before doing any work, read `AGENTS.md`, `Docs/CURRENT_PROJECT_STATE.md`,
`OPEN_WORK_CHECKLIST.md`, `Docs/generated/PROJECT_INDEX.md`, and
[00_navigation_and_tracker.md](00_navigation_and_tracker.md).

Rules to preserve:

- No intentional product behavior change.
- No media policy, queue, publish/drain, settings persistence, source movement,
  cleanup, or WebView/Tauri ownership changes.
- Use summaries before opening full source files.
- Use the bundled Python interpreter at
  `.\DesktopApp\Runtime\Python\python.exe`.
- Add tooling under `scripts/dev/` and tests under `tests/tooling/`.
- Add durable architecture docs under `Docs/architecture/`.
- Do not hand-edit `Docs/generated/PROJECT_INDEX.md` or
  `Docs/generated/DEPENDENCY_GRAPH.md`.
- Do not create root report, fixes, or checklist files.
- Stop after this phase and produce a handoff.

## Phase Goal

Create a reproducible baseline for dependency cleanup. The result should report
actual module imports, package cycles, direct `app.shared` imports, and the
known forbidden boundary imports without changing application behavior.

## Inputs To Reuse

Existing commands from the source plan:

```powershell
.\DesktopApp\Runtime\Python\python.exe .\scripts\dev\refresh_summaries.py --check
.\DesktopApp\Runtime\Python\python.exe .\scripts\dev\generate_project_index.py --check
.\DesktopApp\Runtime\Python\python.exe .\scripts\dev\generate_dependency_atlas.py
```

Existing outputs to inspect:

```text
Docs/generated/PROJECT_INDEX.md
Docs/generated/DEPENDENCY_GRAPH.md
V6_dependency_atlas.html
V6_dependency_atlas.png
V6_dependency_atlas.svg
V6_dependency_atlas_assets/dependency_summary.csv
V6_dependency_atlas_assets/dependency_edges.csv
V6_dependency_atlas_assets/dependency_module_edges.csv
```

## Tasks

1. Confirm generated summaries and project index are fresh, or record the exact
   reason they are not fresh.
2. Regenerate or inspect the dependency atlas.
3. Verify the edge convention before acting on graph data. In the source plan,
   `config --> api` means API code imports config code.
4. Decide whether to extend `scripts/dev/generate_dependency_atlas.py` or add a
   separate `scripts/dev/check_dependency_boundaries.py`.
5. Prefer a separate checker if failing rules and report generation would make
   the atlas generator too complicated.
6. If adding a checker, keep it stdlib-only and suitable for offline local use.
7. The checker should report:
   - internal imports among `app.*` modules;
   - module-level cycles;
   - package-level cycles;
   - direct imports from `app.shared`;
   - direct imports from `app.shared.utils`;
   - direct imports from `app.shared.constants`;
   - direct imports from `app.shared.protocols`;
   - forbidden imports from `app.config` to higher-level packages;
   - forbidden imports from `app.api` to `app.ui`;
   - forbidden imports that violate the chosen
     status/observability/telemetry direction.
8. Add focused tests under `tests/tooling/`, such as
   `tests/tooling/test_dependency_boundaries.py`.
9. Start in report-only or baseline-allowlist mode if current code violates the
   rules.
10. Document the command and rules under
    `Docs/architecture/DEPENDENCY_BOUNDARY_RULES.md`.

## Acceptance Criteria

- Existing targeted tests still pass or failures are explained.
- The checker reproduces package cycles or explains why actual code differs
  from the supplied graph.
- The checker can run locally without network access and without new packages.
- Generated docs are current or explicitly reported as stale.
- New docs do not point to retired root launchers or active `Pipeline/Modules`
  implementation paths.
- No architecture fixes are included in this phase.

## Suggested Validation

```powershell
.\DesktopApp\Runtime\Python\python.exe -m pytest tests\tooling
.\DesktopApp\Runtime\Python\python.exe .\scripts\dev\refresh_summaries.py --check
.\DesktopApp\Runtime\Python\python.exe .\scripts\dev\generate_project_index.py --check
.\DesktopApp\Runtime\Python\python.exe .\scripts\dev\check_dependency_boundaries.py
```

Run only commands that match the final Phase 0 implementation. If
`check_dependency_boundaries.py` does not exist yet, create it before using the
last command.

## Phase Activity Log

| Date | Agent | Action | Evidence | Next |
|---|---|---|---|---|
| 2026-05-31 | Codex | Split Phase 0 into its own operating file | Original plan inspected; no checker or source implementation run | Start Phase 0 only when requested |
| 2026-05-31 | Codex | Completed Phase 0 report-only dependency baseline | `check_dependency_boundaries.py` reports 1407 internal app import entries, 1 module cycle, 2 package cycles, 0 direct `app.shared` imports, 32 `app.shared.utils`, 38 `app.shared.constants`, 19 `app.shared.protocols`, 2 config higher-level, 3 API-to-UI, 3 observability-to-status, and 2 telemetry-to-observability findings; `pytest tests\tooling` passed | Start Phase 1 only when requested |

## Completion Handoff

```text
Phase: 0 - Baseline and dependency guard
Status: Complete
Files changed: Docs/architecture/DEPENDENCY_BOUNDARY_RULES.md; Docs/generated/PROJECT_INDEX.md; Docs/rewrite/dependency-refactor-phases/00_navigation_and_tracker.md; Docs/rewrite/dependency-refactor-phases/01_phase_0_baseline_and_dependency_guard.md; scripts/dev/check_dependency_boundaries.py; tests/tooling/test_dependency_boundaries.py; summaries/scripts/dev/check_dependency_boundaries.py.md; summaries/tests/tooling/test_dependency_boundaries.py.md
Behavior changes: None. Phase 0 added report-only tooling, tests, docs, and generated navigation updates only.
Checks run: .\DesktopApp\Runtime\Python\python.exe -m pytest tests\tooling (34 passed); .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\refresh_summaries.py --check (passed); .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\generate_project_index.py --check (passed); .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\check_dependency_boundaries.py --max-internal-imports 20 (passed in report-only mode); .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\check_dependency_boundaries.py --max-internal-imports 0 (passed in report-only mode with full import listing); .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\check_active_doc_references.py (passed); git diff --check (exit 0, line-ending warnings only)
Dependency checker result: 1407 internal app import entries; 1 module-level cycle in app.contracts.source_media* helpers; 2 package-level cycles (app.config/app.orchestration and app.observability/app.status/app.telemetry); 0 direct app.shared imports; 32 direct app.shared.utils imports; 38 direct app.shared.constants imports; 19 direct app.shared.protocols imports; 2 forbidden app.config higher-level imports; 3 forbidden app.api to app.ui imports; 3 forbidden app.observability to app.status imports; 2 forbidden app.telemetry to app.observability imports; 0 forbidden app.telemetry to app.status imports; 0 parse errors.
Generated artifacts updated: Docs/generated/PROJECT_INDEX.md regenerated from 739 summaries. Docs/generated/DEPENDENCY_GRAPH.md was regenerated by the same command but content did not change. Existing dependency atlas CSVs were inspected to confirm importer-to-imported CSV convention; atlas image/html artifacts were not regenerated.
Summaries refreshed: New summaries were generated for scripts/dev/check_dependency_boundaries.py and tests/tooling/test_dependency_boundaries.py; full summary freshness check passed.
Known risks: Checker is static AST analysis and records import entries, not runtime import side effects. Default mode is intentionally report-only, so it does not prevent new violations yet. Existing unrelated dirty PowerShell/source-summary files remain in the worktree and were not modified for Phase 0.
Explicit deferrals: No architecture imports were fixed; no allowlist or fail-on-new enforcement file was added; dependency atlas rendering was not regenerated because Phase 0 only needed convention inspection and a separate checker baseline.
Next phase: 1 - Break app.config higher-level imports
```
