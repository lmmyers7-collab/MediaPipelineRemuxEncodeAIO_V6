# Phase 4I - Rename Ownership

Previous: [05h_phase_4_publish_pending_reads_subphase.md](05h_phase_4_publish_pending_reads_subphase.md)

Next: [05_phase_4_shared_blast_radius.md](05_phase_4_shared_blast_radius.md)

Created: 2026-05-31

## Scope

This Phase 4 sub-phase moves rename-owned sidecar schema constants, movie
filter option keys, and atomic text writes out of `app.shared.*` and into the
rename domain.

It does not change rename apply behavior, rename confirmation handling, rename
planning, rename preview logic, source/scratch/output movement, pending
publish/drain behavior, settings persistence, cleanup, process lifecycle
behavior, FFmpeg policy, subtitle policy, audio policy, media policy, or
WebView/Tauri ownership.

Media suffix and VLC long-path threshold constants remain deferred for the
later file-opening/media constants sub-phase.

## Inventory Baseline

Baseline command:

```powershell
.\DesktopApp\Runtime\Python\python.exe .\scripts\dev\check_dependency_boundaries.py --max-internal-imports 1
```

Checker baseline before this sub-phase:

| Import group | App import entries |
|---|---:|
| `app.shared` | 0 |
| `app.shared.utils` | 13 |
| `app.shared.constants` | 17 |
| `app.shared.protocols` | 0 |

The targeted rename imports were:

| Symbol or helper | Previous owner | Count | Category | Target owner |
|---|---|---:|---|---|
| `_atomic_write_text` | `app.shared.utils` | 3 | rename metadata, undo-manifest, restore, and preview input write helper | `app.rename.file_io` |
| `RENAME_TOOL_SIDECAR_SCHEMA_VERSION` | `app.shared.constants` | 2 | rename sidecar schema constant | `app.rename.constants` |
| `RENAME_MOVIE_FILTER_OPTION_KEYS` | `app.shared.constants` | 1 | rename movie filter option keys | `app.rename.constants` |

## Sub-Phase Definition

```text
Sub-phase: 4I - Rename ownership
Symbols targeted: rename atomic write helper, rename sidecar schema constant, rename movie filter option keys
Current import count: 13 app.shared.utils entries and 17 app.shared.constants entries before the sub-phase
Target owner: app.rename.file_io and app.rename.constants
Risk category: high boundary, mechanical helper/constant move only; rename apply mutation behavior is protected
Files expected: rename constants and file IO owners; rename apply, apply-runner, preview, movie, and service consumers; refreshed summaries and docs
Validation: focused rename apply/preview/planner/service/policy tests, dependency checker, tooling, summary/project-index checks
Stop condition: stop after rename-owned helper/constants no longer import from app.shared and checker records reduced shared-utils/shared-constants counts
```

## Handoff

```text
Sub-phase: 4I - Rename ownership
Status: Complete
Files changed: app/rename/constants.py; app/rename/file_io.py; app/rename/apply.py; app/rename/apply_runner.py; app/rename/movie.py; app/rename/preview.py; app/rename/service.py; refreshed summaries for touched source files; Docs/architecture/DEPENDENCY_BOUNDARY_RULES.md; Docs/rewrite/dependency-refactor-phases/00_navigation_and_tracker.md; Docs/rewrite/dependency-refactor-phases/05_phase_4_shared_blast_radius.md; Docs/rewrite/dependency-refactor-phases/05i_phase_4_rename_ownership_subphase.md; Docs/generated/PROJECT_INDEX.md; Docs/generated/DEPENDENCY_GRAPH.md
Behavior changes: None intended. Rename sidecar schema values, movie filter option keys, atomic write retry/replace behavior, undo-manifest writes, metadata restore writes, and preview input writes were preserved. Rename apply confirmation, operation ordering, rollback behavior, sidecar movement, planning, preview parsing, media suffix filtering, and VLC long-path handling were intentionally untouched.
Checks run: .\DesktopApp\Runtime\Python\python.exe -m pytest DesktopApp\tests\test_service_rename_apply.py DesktopApp\tests\test_service_rename_apply_runner.py DesktopApp\tests\test_service_rename_movie.py DesktopApp\tests\test_service_rename_preview.py DesktopApp\tests\test_service_rename_preview_runner.py DesktopApp\tests\test_service_rename_planner.py DesktopApp\tests\test_service_rename_plan_policy.py DesktopApp\tests\test_service_rename_utils.py DesktopApp\tests\test_service_rename_discovery.py DesktopApp\tests\test_service_rename_tv.py DesktopApp\tests\test_service_rename_tv_folder.py DesktopApp\tests\test_rename_service.py DesktopApp\tests\test_application_facade_rename.py DesktopApp\tests\test_facade_rename_policy.py (86 passed); .\DesktopApp\Runtime\Python\python.exe -m pytest tests\tooling (39 passed); .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\check_dependency_boundaries.py --max-internal-imports 1 (passed with allowlist); .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\check_active_doc_references.py (passed); .\DesktopApp\Runtime\Python\python.exe .\scripts\lint-naming.py (passed); .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\refresh_summaries.py --check (passed); .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\generate_project_index.py --check (passed); git diff --check (passed with line-ending warnings only).
Dependency checker result: app.shared.utils imports dropped from 13 to 10; app.shared.constants imports dropped from 17 to 14; app.shared.protocols remains 0; direct app.shared remains 0; package-level cycles remain 0; the existing app.contracts.source_media* module-level cycle remains allowlisted by Phase 5 tooling.
Known risks: Rename mutation behavior is high-risk, so this pass only changed import ownership and mechanically copied the write helper. app.rename still imports MEDIA_FILE_SUFFIXES and VLC_LONG_PATH_THRESHOLD from app.shared.constants until the planned file-opening/media constants sub-phase.
Remaining shared hotspots: app.shared.utils has 10 app import entries after this pass across config save, failure cleanup, file opening, folder-policy IO, maintenance release, and schedule app-state reads/writes; app.shared.constants has 14 app import entries across media/file suffix, folder-policy, failure, storage, and deferred rename media/VLC constants; app.shared.protocols has 0 app import entries but retains process-oriented protocol definitions until a later shrink/final cleanup pass.
Next: Continue Phase 4 with 4J file opening and media constants; rerun final review after Phase 4 reaches the desired cleanup threshold.
```
