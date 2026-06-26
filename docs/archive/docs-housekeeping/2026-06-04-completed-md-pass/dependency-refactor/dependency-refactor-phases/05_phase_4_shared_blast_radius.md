# Phase 4 - Reduce app.shared Blast Radius

Previous: [04_phase_3_api_ui_boundary.md](04_phase_3_api_ui_boundary.md)

Next: [06_phase_5_harden_dependency_rules.md](06_phase_5_harden_dependency_rules.md)

Source plan: `Docs/rewrite/CODEX_DEPENDENCY_REFACTOR_PLAN (1).md`

Sub-phases:

- [05a_phase_4_schedule_constants_subphase.md](05a_phase_4_schedule_constants_subphase.md)
- [05b_phase_4_audit_rerun_ownership_subphase.md](05b_phase_4_audit_rerun_ownership_subphase.md)
- [05c_phase_4_status_read_models_subphase.md](05c_phase_4_status_read_models_subphase.md)
- [05d_phase_4_protocol_ownership_subphase.md](05d_phase_4_protocol_ownership_subphase.md)
- [05e_phase_4_config_constants_subphase.md](05e_phase_4_config_constants_subphase.md)
- [05f_phase_4_process_runtime_state_subphase.md](05f_phase_4_process_runtime_state_subphase.md)
- [05g_phase_4_queue_ownership_subphase.md](05g_phase_4_queue_ownership_subphase.md)
- [05h_phase_4_publish_pending_reads_subphase.md](05h_phase_4_publish_pending_reads_subphase.md)
- [05i_phase_4_rename_ownership_subphase.md](05i_phase_4_rename_ownership_subphase.md)
- [05j_phase_4_file_opening_media_constants_subphase.md](05j_phase_4_file_opening_media_constants_subphase.md)
- [05k_phase_4_folder_failure_storage_app_state_subphase.md](05k_phase_4_folder_failure_storage_app_state_subphase.md)
- [05l_phase_4_final_shared_shrink_subphase.md](05l_phase_4_final_shared_shrink_subphase.md)

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
| 2026-05-31 | Codex | Completed Phase 4A schedule constants sub-phase | Moved `SCHEDULE_DAY_NAMES` to `app.schedule.constants`; checker reports `app.shared.constants` imports dropped from 38 to 36 with cycles unchanged; focused schedule tests passed | Continue Phase 4 with another scoped shared-reduction sub-phase |
| 2026-05-31 | Codex | Completed Phase 4B audit rerun ownership sub-phase | Moved audit rerun CSV columns, audit-specific protocols, and audit rerun file helpers to `app.audit`; checker reports `app.shared.utils` 32 -> 27, `app.shared.constants` 36 -> 35, and `app.shared.protocols` 19 -> 16 with package cycles still 0 | Continue Phase 4 with another scoped shared-reduction sub-phase |
| 2026-05-31 | Codex | Completed Phase 4C status read-model sub-phase | Moved status JSON/tail helpers and status-specific protocols to `app.status`; checker reports `app.shared.utils` 27 -> 22 and `app.shared.protocols` 16 -> 14 with package cycles still 0 | Continue Phase 4 with another scoped shared-reduction sub-phase |
| 2026-05-31 | Codex | Completed Phase 4D protocol ownership sub-phase | Moved remaining direct `app.shared.protocols` consumers to domain contract modules; checker reports `app.shared.protocols` 14 -> 0 with package cycles still 0 | Continue Phase 4 with config constants sub-phase |
| 2026-05-31 | Codex | Completed Phase 4E config constants sub-phase | Moved config option/profile constants to `app.config.constants` and schema-version imports to `app.contracts.config`; checker reports `app.shared.constants` 35 -> 24 with package cycles still 0 | Continue Phase 4 with process runtime state sub-phase |
| 2026-05-31 | Codex | Completed Phase 4F process runtime state sub-phase | Moved process constants to `app.processes.constants` and process JSON/text helpers to `app.processes.file_io`; checker reports `app.shared.utils` 22 -> 16 and `app.shared.constants` 24 -> 17 with package cycles still 0 | Continue Phase 4 with queue ownership sub-phase |
| 2026-05-31 | Codex | Completed Phase 4G queue ownership sub-phase | Moved queue dry-run atomic snapshot write helper to `app.queue.file_io`; checker reports `app.shared.utils` 16 -> 15 with package cycles still 0 | Continue Phase 4 with publish pending reads sub-phase |
| 2026-05-31 | Codex | Completed Phase 4H publish pending reads sub-phase | Moved pending-publish manifest and drain-summary JSON read helper ownership to `app.publish.file_io`; checker reports `app.shared.utils` 15 -> 13 with package cycles still 0 | Continue Phase 4 with rename ownership sub-phase |
| 2026-05-31 | Codex | Completed Phase 4I rename ownership sub-phase | Moved rename sidecar/filter constants to `app.rename.constants` and rename atomic writes to `app.rename.file_io`; checker reports `app.shared.utils` 13 -> 10 and `app.shared.constants` 17 -> 14 with package cycles still 0 | Continue Phase 4 with file opening and media constants sub-phase |
| 2026-05-31 | Codex | Completed Phase 4J file opening and media constants sub-phase | Moved file-open path helpers to `app.files.opening` and media/VLC constants to `app.files.constants`; checker reports `app.shared.utils` 10 -> 8 and `app.shared.constants` 14 -> 5 with package cycles still 0 | Continue Phase 4 with folder policy, failure, storage, and app-state sub-phase |
| 2026-05-31 | Codex | Completed Phase 4K folder policy, failure, storage, and app-state sub-phase | Moved folder-policy constants/helpers, failure manifest constants/writes, storage app-state name, and schedule app-state helpers into owning domains; checker reports `app.shared.constants` 5 -> 0 and `app.shared.utils` 8 -> 3 with package cycles still 0 | Continue Phase 4 with final shared shrink |
| 2026-05-31 | Codex | Completed Phase 4L final shared-shrink sub-phase | Moved remaining settings-save/open-path helpers and release manifest reads out of `app.shared.utils`, redirected desktop compatibility imports to domain owners, and retired shared modules; checker reports `app.shared.utils` 3 -> 0 with package cycles still 0 | Rerun final cleanup review |

## Completion Handoff

```text
Phase: 4 - Reduce app.shared blast radius
Status: Complete through sub-phase 4L.
Files changed: Through 4L, see individual 4A-4L handoff files for complete per-sub-phase file lists. Phase 4L changed app/config/file_io.py; app/config/save_runner.py; app/maintenance/file_io.py; app/maintenance/release.py; app/rename/constants.py; app/shared/constants.py; app/shared/protocols.py; app/shared/utils.py; DesktopApp/mediapipeline_desktop_app/services.py; refreshed summaries for touched source files; Docs/architecture/DEPENDENCY_BOUNDARY_RULES.md; Docs/rewrite/dependency-refactor-phases/05l_phase_4_final_shared_shrink_subphase.md; Docs/rewrite/dependency-refactor-phases/05_phase_4_shared_blast_radius.md; Docs/rewrite/dependency-refactor-phases/00_navigation_and_tracker.md; Docs/generated/PROJECT_INDEX.md; Docs/generated/DEPENDENCY_GRAPH.md.
Behavior changes: None intended. Phase 4L moved settings-save/open-path helpers and release manifest JSON reads into owning domains, redirected desktop compatibility imports to domain owners, and shrank shared modules with config write behavior, path normalization, release manifest read behavior, and compatibility module globals preserved.
Checks run: Initial focused pytest command without PYTHONPATH failed during collection with ModuleNotFoundError for mediapipeline_desktop_app; reran the same targets with PYTHONPATH set to repo and DesktopApp paths and 46 tests passed. Final validation: .\DesktopApp\Runtime\Python\python.exe -m pytest DesktopApp\tests\test_service_config_save_runner.py DesktopApp\tests\test_app_config_contract.py DesktopApp\tests\test_service_release.py DesktopApp\tests\test_service_release_plan.py DesktopApp\tests\test_service_release_result.py DesktopApp\tests\test_application_facade_maintenance.py DesktopApp\tests\test_facade_maintenance_policy.py DesktopApp\tests\test_facade_maintenance_command_policy.py DesktopApp\tests\test_telemetry_service.py (46 passed with PYTHONPATH set); .\DesktopApp\Runtime\Python\python.exe -m pytest tests\tooling (39 passed); .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\check_dependency_boundaries.py --max-internal-imports 1 (passed with allowlist); .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\check_active_doc_references.py (passed); .\DesktopApp\Runtime\Python\python.exe .\scripts\lint-naming.py (passed); .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\refresh_summaries.py --check (passed after refreshing unrelated stale summaries); .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\generate_project_index.py --check (passed); git diff --check (passed with line-ending warnings only).
Dependency checker result: 1430 internal app imports; 1 allowlisted module-level cycle in `app.contracts.source_media*`; 0 package-level cycles; 0 parse errors; direct `app.shared` imports remain 0; `app.shared.utils` imports dropped from 3 to 0; `app.shared.constants` remains 0; `app.shared.protocols` remains 0; 0 forbidden config/API/status/telemetry direction violations; 10 allowlisted hard findings; 0 unallowlisted hard findings; 217 warning findings; 0 allowlist errors; 0 unused allowlist entries.
Generated artifacts updated: Docs/generated/PROJECT_INDEX.md and Docs/generated/DEPENDENCY_GRAPH.md regenerated from 776 summaries after Phase 4L summary refresh.
Summaries refreshed: Targeted refresh wrote 9 summaries for the Phase 4L touched source files and 4 summaries for touched phase/architecture docs. To restore global freshness in the already-dirty worktree, additional stale summaries outside the 4L source edits were refreshed through targeted and full summary refresh runs. Final .\scripts\dev\refresh_summaries.py --check passed with 776 current summaries and no orphan summaries.
Known risks: Settings save and release manifest reads are protected behavior, so 4L only changed import ownership and mechanically copied helper behavior. The shared modules remain importable as empty retired namespaces to avoid breaking plain module imports, but they no longer export active helpers/constants/protocols. The existing `app.contracts.source_media*` module cycle remains allowlisted by Phase 5 tooling and is outside Phase 4 shared-coupling cleanup.
Explicit deferrals: Did not address the existing `app.contracts.source_media*` module cycle. Did not make warning-only barrel `__init__` rules hard failures.
Remaining shared hotspots: No app-domain or DesktopApp-domain imports from `app.shared`, `app.shared.utils`, `app.shared.constants`, or `app.shared.protocols` remain. Historical docs and dependency-checker test fixtures still mention `app.shared` intentionally.
Next phase: Rerun final cleanup review after Phase 4 completion.
```
