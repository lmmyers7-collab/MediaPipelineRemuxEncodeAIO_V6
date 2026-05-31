# Phase 5 - Harden Dependency Rules

Previous: [05_phase_4_shared_blast_radius.md](05_phase_4_shared_blast_radius.md)

Next: [07_full_cleanup_review_and_done.md](07_full_cleanup_review_and_done.md)

Source plan: `Docs/rewrite/CODEX_DEPENDENCY_REFACTOR_PLAN (1).md`

## Carry-Forward Requirements

Do not start this phase until the checker exists and earlier phases have either
cleared their target violations or recorded explicit deferrals.

Before doing any work, read `AGENTS.md`, `Docs/CURRENT_PROJECT_STATE.md`,
`OPEN_WORK_CHECKLIST.md`, `Docs/generated/PROJECT_INDEX.md`,
[00_navigation_and_tracker.md](00_navigation_and_tracker.md), and prior phase
handoffs.

Rules to preserve:

- No intentional product behavior change.
- No media policy, queue, publish/drain, settings persistence, source movement,
  cleanup, or WebView/Tauri ownership changes.
- Use summaries before opening full source files.
- Use the bundled Python interpreter at
  `.\DesktopApp\Runtime\Python\python.exe`.
- Enforce rules with tooling, not with hidden lazy imports.
- Use a durable allowlist only when a violation cannot be safely fixed yet.
- Stop after this phase and produce a handoff.

## Phase Goal

Move from report-only dependency visibility to automatic enforcement.

Architecture rules should be enforced by a repeatable `scripts/dev/` command
and focused tests.

## Hard Failure Rules

Once the baseline is clean, these should fail:

```text
NO_PACKAGE_CYCLES
NO_MODULE_CYCLES
NO_CONFIG_TO_ORCHESTRATION
NO_CONFIG_TO_DECIDE
NO_API_TO_UI
NO_OBSERVABILITY_TO_STATUS
NO_TELEMETRY_TO_OBSERVABILITY
NO_DIRECT_APP_SHARED_IMPORTS
```

## Warning Rules Until Cleaned

These may remain warnings until explicitly cleaned:

```text
NO_SHARED_UTILS_IMPORTS
NO_SHARED_CONSTANTS_IMPORTS
NO_SHARED_PROTOCOLS_IMPORTS
NO_BARREL_INIT_REEXPORTS
NO_DOMAIN_IMPORTS_FROM_SHARED_CONSTANTS
```

## Tasks

1. Turn the dependency checker from report-only into fail-on-new-violation mode.
2. Use a baseline allowlist only for violations that cannot be safely fixed yet.
3. Store the allowlist in a durable architecture location, for example:

   ```text
   Docs/architecture/dependency_boundary_allowlist.txt
   ```

4. Every allowlist entry must include:

   ```text
   importing module
   imported module
   rule id
   reason
   target removal phase or owner
   ```

5. Add the checker to existing local safety nets where appropriate.
6. Update `Docs/architecture/DEPENDENCY_BOUNDARY_RULES.md` with the final
   enforcement and allowlist workflow.
7. Refresh summaries for touched source files.
8. Ensure generated dependency/index artifacts remain current.

## Acceptance Criteria

- New package cycles fail the check.
- New module cycles fail the check.
- New `app.api -> app.ui` imports fail the check.
- New `app.config -> app.orchestration` imports fail the check.
- New direct `app.shared` imports fail the check unless temporarily allowlisted.
- Documentation explains how to run and update the checker.
- `Docs/generated/PROJECT_INDEX.md` and `Docs/generated/DEPENDENCY_GRAPH.md`
  remain generated and current.
- Allowlist entries are specific, justified, and have an owner or target removal
  phase.

## Suggested Validation

```powershell
.\DesktopApp\Runtime\Python\python.exe -m pytest tests\tooling
.\DesktopApp\Runtime\Python\python.exe .\scripts\dev\check_dependency_boundaries.py
.\DesktopApp\Runtime\Python\python.exe .\scripts\dev\check_active_doc_references.py
.\DesktopApp\Runtime\Python\python.exe .\scripts\lint-naming.py
.\DesktopApp\Runtime\Python\python.exe .\scripts\dev\refresh_summaries.py --check
.\DesktopApp\Runtime\Python\python.exe .\scripts\dev\generate_project_index.py --check
```

Explain any failure and distinguish known pre-existing failures from new issues.

## Phase Activity Log

| Date | Agent | Action | Evidence | Next |
|---|---|---|---|---|
| 2026-05-31 | Codex | Split Phase 5 into its own operating file | Original plan inspected; no checker enforcement changed | Start Phase 5 after earlier cleanup or explicit deferrals |

## Completion Handoff

```text
Phase: 5 - Harden dependency rules
Status:
Files changed:
Behavior changes:
Checks run:
Dependency checker result:
Generated artifacts updated:
Summaries refreshed:
Known risks:
Explicit deferrals:
Allowlist entries:
Next phase: Final cleanup review
```
