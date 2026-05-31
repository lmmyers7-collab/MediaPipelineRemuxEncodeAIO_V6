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

## Final Handoff

```text
Cleanup status:
Completed phases:
Deferred phases:
Dependency checker command:
Dependency checker result:
Tests run:
Generated artifacts:
Summaries:
Remaining allowlist entries:
Residual risks:
Recommended next owner/action:
```
