# Phase 4 - Reduce app.shared Blast Radius

Previous: [04_phase_3_api_ui_boundary.md](04_phase_3_api_ui_boundary.md)

Next: [06_phase_5_harden_dependency_rules.md](06_phase_5_harden_dependency_rules.md)

Source plan: `Docs/rewrite/CODEX_DEPENDENCY_REFACTOR_PLAN (1).md`

## Carry-Forward Requirements

Do not start this phase until Phase 0 has produced dependency baseline evidence.
Prefer starting after Phases 1-3 are complete or deliberately deferred with a
written reason.

Before doing any work, read `AGENTS.md`, `Docs/CURRENT_PROJECT_STATE.md`,
`OPEN_WORK_CHECKLIST.md`, `Docs/generated/PROJECT_INDEX.md`,
[00_navigation_and_tracker.md](00_navigation_and_tracker.md), and prior phase
handoffs.

Rules to preserve:

- No intentional product behavior change.
- Treat helper moves that touch source/scratch/output movement, pending publish,
  rename apply, settings save, command journal, process lifecycle, subtitles,
  audio, or FFmpeg policy as high risk.
- Use summaries before opening full source files.
- Use the bundled Python interpreter at
  `.\DesktopApp\Runtime\Python\python.exe`.
- Do not replace `app.shared` with `app.common`, `app.helpers`, `misc`, or any
  other dumping ground.
- Prefer existing V6 domain owners.
- Split this phase into sub-phases when risk or file count grows.
- Stop after each sub-phase with a handoff and remaining hotspots.

## Phase Goal

Reduce broad shared coupling:

```text
No direct imports from app.shared.
Reduced imports from app.shared.utils/constants/protocols.
Clearer ownership of helper code.
```

## Inventory Targets

Inventory all imports from:

```text
app.shared
app.shared.utils
app.shared.constants
app.shared.protocols
```

Use the Phase 0 checker, `rg`, and atlas CSVs before opening full source.

## Symbol Categories

Categorize each imported symbol before moving it:

```text
pure generic helper
path/file helper
time/date helper
serialization helper
process/subprocess helper
domain-specific helper
constant owned by one domain
protocol/type that belongs in contracts or an owning domain
```

## Preferred Owners

Prefer existing V6 domains:

```text
app.paths
app.storage
app.processes
app.contracts
app.rename
app.publish
app.queue
app.status
app.<owning-domain>
```

Move helpers into the domain that owns the behavior when they are not truly
cross-cutting.

## Tasks

1. Inventory shared imports and record counts by module and symbol.
2. Select an initial low-risk sub-phase with obvious ownership.
3. Move only obvious low-risk items in the first pass.
4. Keep the first pass mechanical. Do not rewrite logic.
5. Avoid large rename-only sweeps unless they directly reduce coupling.
6. Refresh summaries for touched source files after each sub-phase.
7. Run the dependency checker after each sub-phase.
8. Update architecture docs or dependency allowlist entries from Phase 0.

## Sub-Phase Template

Use this template if Phase 4 needs smaller files:

```text
Sub-phase:
Symbols targeted:
Current import count:
Target owner:
Risk category:
Files expected:
Validation:
Stop condition:
```

Create sub-phase notes under `Docs/rewrite/dependency-refactor-phases/` and link
them from this file if needed.

## Acceptance Criteria

- Direct consumers of `app.shared` drop substantially, ideally to zero.
- `app/shared/__init__.py` is empty or nearly empty.
- Imports from `app.shared.utils`, `app.shared.constants`, and
  `app.shared.protocols` are reduced or classified with an owner.
- No new package cycles are introduced.
- Existing targeted tests pass.
- Dependency checker reports updated fan-in counts.
- Remaining shared hotspots are explicitly listed for a future sub-phase.

## Suggested Validation

Choose tests based on moved symbols. Minimum expected checks for each sub-phase:

```powershell
.\DesktopApp\Runtime\Python\python.exe .\scripts\dev\check_dependency_boundaries.py
.\DesktopApp\Runtime\Python\python.exe .\scripts\dev\refresh_summaries.py --check
.\DesktopApp\Runtime\Python\python.exe .\scripts\dev\generate_project_index.py --check
```

Add focused pytest targets for the domains touched by each symbol move.

## Phase Activity Log

| Date | Agent | Action | Evidence | Next |
|---|---|---|---|---|
| 2026-05-31 | Codex | Split Phase 4 into its own operating file | Original plan inspected; no shared imports changed | Start Phase 4 after earlier boundary phases or written deferral |

## Completion Handoff

```text
Phase: 4 - Reduce app.shared blast radius
Status:
Files changed:
Behavior changes:
Checks run:
Dependency checker result:
Generated artifacts updated:
Summaries refreshed:
Known risks:
Explicit deferrals:
Remaining shared hotspots:
Next phase: 5 - Harden dependency rules
```
