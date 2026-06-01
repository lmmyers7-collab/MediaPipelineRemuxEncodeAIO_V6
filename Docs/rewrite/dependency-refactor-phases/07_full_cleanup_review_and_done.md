# Full Cleanup Review and Definition of Done

Previous: [06_phase_5_harden_dependency_rules.md](06_phase_5_harden_dependency_rules.md)

Next: none

Source plan: `Docs/rewrite/CODEX_DEPENDENCY_REFACTOR_PLAN (1).md`

## Carry-Forward Requirements

Use this file only after Phases 0-5 have been completed or explicitly deferred
with documented reasons.

Before final review, read `AGENTS.md`, `Docs/CURRENT_PROJECT_STATE.md`,
`OPEN_WORK_CHECKLIST.md`, `Docs/generated/PROJECT_INDEX.md`,
[00_navigation_and_tracker.md](00_navigation_and_tracker.md), and every phase
handoff.

Rules to preserve:

- No intentional product behavior change from dependency cleanup.
- No unvalidated media policy, queue, publish/drain, settings persistence,
  source movement, cleanup, or WebView/Tauri ownership changes.
- Use the bundled Python interpreter at
  `.\DesktopApp\Runtime\Python\python.exe`.
- Do not treat this split-plan folder as canonical project state.
- Do not create root report, fixes, or checklist files.
- Keep the traceable history in the phase activity logs and central tracker.

## Review Checklist For Each Phase

Before accepting a patch, verify:

```text
[ ] The patch addresses only the requested phase.
[ ] Public behavior is unchanged.
[ ] No broad formatting-only churn was introduced.
[ ] Existing tests pass or failures are explained.
[ ] Dependency checker output improved.
[ ] No new package-level cycles were introduced.
[ ] No new app.shared imports were introduced.
[ ] No import was merely hidden inside a function to silence the graph.
[ ] Moved modules have clear ownership and names.
[ ] New Python domain code lives under app/<domain>/ unless there is a clear host-specific reason.
[ ] New tooling lives under scripts/dev/.
[ ] New docs live under Docs/architecture/ or another existing topic folder, not the repo root.
[ ] Generated docs are regenerated or checked when touched inputs changed.
[ ] Summaries are refreshed for touched source files.
```

## Things Not To Do

Do not solve dependency cleanup by doing any of these:

```text
Moving everything into app.shared
Creating app.common as a new dumping ground
Adding function-local imports just to hide cycles
Leaving compatibility shims that preserve forbidden package cycles
Renaming many modules without reducing coupling
Changing APIs and architecture in the same patch
Making the dependency checker depend on network access
Ignoring package-level cycles because module-level cycles are clean
Creating new flat facade_*.py or service_*.py files
Creating new dotted Pipeline/Modules/*.ps1 files
Reintroducing removed root launcher paths
Hand-editing Docs/generated/PROJECT_INDEX.md or Docs/generated/DEPENDENCY_GRAPH.md
```

## Full Definition Of Done

The cleanup is complete when:

```text
[ ] module-level cycles are still zero
[ ] package-level cycles are zero
[ ] app.config does not import app.orchestration or app.decide
[ ] app.api does not import app.ui
[ ] app.observability/status/telemetry follow one documented direction
[ ] direct app.shared imports are zero or explicitly justified
[ ] app.shared.utils/constants/protocols have been split or reduced to small, defensible surfaces
[ ] package __init__.py files do not hide major dependencies
[ ] dependency rules are documented under Docs/architecture/
[ ] dependency rules are enforced by a repeatable scripts/dev command
[ ] generated dependency/index artifacts remain current
[ ] summaries are current
[ ] tests pass
```

## Final Review Procedure

1. Read the central activity log in
   [00_navigation_and_tracker.md](00_navigation_and_tracker.md).
2. Read each phase activity log and completion handoff.
3. Confirm each phase file points to the next file and that no implementation
   history was stranded in a separate unlinked note.
4. Run the dependency checker and targeted test/tooling checks expected by
   Phase 5.
5. Confirm generated docs are current or document exact stale artifacts.
6. Confirm summary refresh status for touched source files.
7. Update this file's activity log with the final closeout summary.

## Final Activity Log

| Date | Agent | Action | Evidence | Next |
|---|---|---|---|---|
| 2026-05-31 | Codex | Split final review and definition of done into its own file | Original plan inspected; no cleanup implementation run | Use after Phases 0-5 |
| 2026-05-31 | Codex | Completed final review audit; full definition of done remains open | Phase handoffs read, phase links checked, Phase 5 validation commands pass, and dependency checker reports 0 package cycles plus 0 unallowlisted hard findings; full DoD remains open because the `source_media` module cycle is allowlisted and Phase 4 shared warning surfaces remain | Resume Phase 4 shared cleanup, remove the source-media allowlist, then rerun final review |
| 2026-05-31 | Codex | Reran final review after Phase 4 completion; full definition of done remains open | Phase handoffs read, phase/sub-phase links checked, Phase 5 validation commands pass, and dependency checker reports 0 direct `app.shared*` imports, 0 package cycles, and 0 unallowlisted hard findings; full DoD remains open because the `source_media` module cycle is still allowlisted and barrel re-export warnings remain | Refactor the `source_media` module cycle, resolve or explicitly accept barrel re-export warnings, then rerun final review |
| 2026-05-31 | Codex | Closed dependency-checker blockers from the final review | Source-media model definitions moved to `app.contracts.source_media_models`, package barrel re-exports retired, allowlist emptied, and checker reports 0 module cycles, 0 package cycles, 0 direct `app.shared*` imports, 0 allowlisted hard findings, 0 unallowlisted hard findings, and 0 warning findings | Resolve the unrelated Web static smoke assertion before claiming every validation target green |

## Final Handoff

```text
Cleanup status: Remaining dependency-checker blockers are closed; dependency enforcement is clean. Full validation still has one unrelated Web static smoke assertion to resolve before claiming every requested test target is green.
Completed phases: Phase 0, Phase 1, Phase 2, Phase 3, Phase 4 sub-phases 4A-4L, and Phase 5.
Deferred phases: None for dependency-checker cleanup. Validation caveat: `DesktopApp/tests/test_application_facade_local_api.py::LocalApiServerTests::test_local_api_serves_read_only_web_prototype` fails because the currently dirty Web static rename page no longer contains the literal text `Rename Workbench`; this file/static UI surface was dirty before this final dependency-blocker pass and was not changed here.
Dependency checker command: .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\check_dependency_boundaries.py --max-internal-imports 1
Dependency checker result: Passes current enforcement with 1233 internal app imports, 0 module-level cycles, 0 package-level cycles, 0 parse errors, 0 direct app.shared imports, 0 app.shared.utils imports, 0 app.shared.constants imports, 0 app.shared.protocols imports, 0 forbidden config/API/status/telemetry direction violations, 0 allowlisted hard findings, 0 unallowlisted hard findings, 0 warning findings, 0 allowlist errors, and 0 unused allowlist entries.
Tests run: .\DesktopApp\Runtime\Python\python.exe -m pytest tests\contract\test_source_media_contract.py tests\decide tests\orchestration\test_pipeline_planner.py tests\integration\test_handbrake_remux_regression_matrix.py (31 passed); .\DesktopApp\Runtime\Python\python.exe -m pytest DesktopApp\tests\test_api_command_contracts.py DesktopApp\tests\test_settings_pipeline_plan_preview.py DesktopApp\tests\test_phase4_storage_observability.py DesktopApp\tests\test_application_facade_local_api.py (49 passed, 1 failed in unrelated Web static smoke assertion described above); .\DesktopApp\Runtime\Python\python.exe -m pytest tests\tooling (39 passed); .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\check_dependency_boundaries.py --max-internal-imports 1 (passed clean); .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\check_active_doc_references.py (passed); .\DesktopApp\Runtime\Python\python.exe .\scripts\lint-naming.py (passed).
Generated artifacts: Docs/generated/PROJECT_INDEX.md and Docs/generated/DEPENDENCY_GRAPH.md regenerated from 779 summaries after the source-media model split, barrel cleanup, and final review summary refresh; no generated files were hand-edited.
Summaries: Refreshed for touched source and doc files after this dependency-blocker pass; refresh_summaries.py --check passed after the final handoff edit.
Remaining allowlist entries: None.
Residual risks: The checker is static AST-based, and the workspace contains unrelated pre-existing dirty files outside this final dependency-blocker pass.
Recommended next owner/action: Resolve the unrelated Web static smoke assertion or align the test with the current rename page wording, then rerun the remaining validation commands.
```
