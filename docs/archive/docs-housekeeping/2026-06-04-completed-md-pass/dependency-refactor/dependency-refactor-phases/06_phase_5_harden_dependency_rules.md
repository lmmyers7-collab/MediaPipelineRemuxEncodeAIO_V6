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
| 2026-05-31 | Codex | Completed Phase 5 dependency-rule hardening | Checker now enforces hard rules by default with a durable allowlist for the existing `app.contracts.source_media*` module cycle; tooling tests passed | Start final cleanup review when requested |

## Completion Handoff

```text
Phase: 5 - Harden dependency rules
Status: Complete
Files changed: scripts/dev/check_dependency_boundaries.py; scripts/dev/ai_guardrail.py; tests/tooling/test_dependency_boundaries.py; tests/tooling/test_ai_guardrail.py; Docs/architecture/DEPENDENCY_BOUNDARY_RULES.md; Docs/architecture/dependency_boundary_allowlist.txt; Docs/rewrite/dependency-refactor-phases/06_phase_5_harden_dependency_rules.md; Docs/rewrite/dependency-refactor-phases/00_navigation_and_tracker.md; refreshed summaries for touched source/tooling files; Docs/generated/PROJECT_INDEX.md; Docs/generated/DEPENDENCY_GRAPH.md.
Behavior changes: None intended. This phase changed developer tooling enforcement only.
Checks run: .\DesktopApp\Runtime\Python\python.exe -m pytest tests\tooling\test_dependency_boundaries.py tests\tooling\test_ai_guardrail.py (11 passed); .\DesktopApp\Runtime\Python\python.exe -m pytest tests\tooling (39 passed); .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\check_dependency_boundaries.py --max-internal-imports 1 (passed with allowlist); .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\check_active_doc_references.py (passed); .\DesktopApp\Runtime\Python\python.exe .\scripts\lint-naming.py (passed); .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\refresh_summaries.py --check (passed); .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\generate_project_index.py --check (passed); git diff --check (passed with existing CRLF normalization warnings).
Dependency checker result: 1411 internal app imports; 1 module-level cycle; 0 package-level cycles; 0 parse errors; 0 direct `app.shared` imports; 32 `app.shared.utils` imports; 36 `app.shared.constants` imports; 19 `app.shared.protocols` imports; 0 config/API/status/telemetry direction violations; 10 hard findings allowlisted; 0 unallowlisted hard findings; 338 warning findings; 0 allowlist errors; 0 unused allowlist entries.
Generated artifacts updated: Docs/generated/PROJECT_INDEX.md and Docs/generated/DEPENDENCY_GRAPH.md regenerated from 742 summaries.
Summaries refreshed: Targeted refresh wrote 4 summaries for touched source/tooling files. Final check reported 742 source files all current with no orphan summaries.
Known risks: The checker is static AST analysis. Warning rules still do not fail, and the existing source-media contract module cycle remains allowlisted. Broad shared-submodule cleanup remains deferred from Phase 4. `DesktopApp/mediapipeline_desktop_app/services.py` still imports other `app.shared.constants` and `app.shared.utils` symbols.
Explicit deferrals: Did not fix the `app.contracts.source_media*` module cycle; did not make `app.shared.utils`, `app.shared.constants`, `app.shared.protocols`, barrel `__init__` re-export, or domain shared-constants warning rules fail.
Allowlist entries: 10 `NO_MODULE_CYCLES` entries in `Docs/architecture/dependency_boundary_allowlist.txt` for the existing `app.contracts.source_media`, `app.contracts.source_media_adapters`, `app.contracts.source_media_derived`, `app.contracts.source_media_streams`, and `app.contracts.source_media_values` cycle edges. Each entry records the owner as app.contracts source_media cleanup.
Next phase: Final cleanup review
```
