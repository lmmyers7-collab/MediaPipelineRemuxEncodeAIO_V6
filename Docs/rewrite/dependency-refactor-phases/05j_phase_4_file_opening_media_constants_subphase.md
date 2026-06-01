# Phase 4J - File Opening and Media Constants

Previous: [05i_phase_4_rename_ownership_subphase.md](05i_phase_4_rename_ownership_subphase.md)

Next: [05_phase_4_shared_blast_radius.md](05_phase_4_shared_blast_radius.md)

Created: 2026-05-31

## Scope

This Phase 4 sub-phase moves file-opening path coercion helpers, media file
suffixes, and the VLC long-path threshold out of `app.shared.*` and into the
files domain.

It does not change media suffix values, VLC long-path behavior, file opening
behavior, final-library companion sidecar behavior, folder-policy validation,
rename discovery, rename planning, rename apply behavior, source/scratch/output
movement, pending publish/drain behavior, settings persistence, cleanup,
process lifecycle behavior, FFmpeg policy, subtitle policy, audio policy, media
policy, or WebView/Tauri ownership.

Dead exports remain in `app.shared.constants` and `app.shared.utils` until the
planned final shared-shrink sub-phase.

## Inventory Baseline

Baseline command:

```powershell
.\DesktopApp\Runtime\Python\python.exe .\scripts\dev\check_dependency_boundaries.py --max-internal-imports 1
```

Checker baseline before this sub-phase:

| Import group | App import entries |
|---|---:|
| `app.shared` | 0 |
| `app.shared.utils` | 10 |
| `app.shared.constants` | 14 |
| `app.shared.protocols` | 0 |

The targeted imports were:

| Symbol or helper | Previous owner | Count | Category | Target owner |
|---|---|---:|---|---|
| `_coerce_open_path` | `app.shared.utils` | 1 | file-opening path coercion helper | `app.files.opening` |
| `_windows_native_path` | `app.shared.utils` | 1 | file-opening Windows path helper | `app.files.opening` |
| `MEDIA_FILE_SUFFIXES` | `app.shared.constants` | 6 | media/file suffix contract used by files, final library, folder policy, and rename | `app.files.constants` |
| `VLC_LONG_PATH_THRESHOLD` | `app.shared.constants` | 3 | VLC/file-opening long-path threshold | `app.files.constants` |

## Sub-Phase Definition

```text
Sub-phase: 4J - File opening and media constants
Symbols targeted: file-open path coercion helpers, MEDIA_FILE_SUFFIXES, VLC_LONG_PATH_THRESHOLD
Current import count: 10 app.shared.utils entries and 14 app.shared.constants entries before the sub-phase
Target owner: app.files.opening and app.files.constants
Risk category: medium/high boundary, mechanical helper/constant move only; media policy and file movement behavior are protected
Files expected: files constants/opening/open-plan owners; final-library, folder-policy, and rename consumers; refreshed summaries and docs
Validation: focused file-open/final-library/folder-policy/rename tests, dependency checker, tooling, summary/project-index checks
Stop condition: stop after file-opening helpers and media constants no longer import from app.shared and checker records reduced shared-utils/shared-constants counts
```

## Handoff

```text
Sub-phase: 4J - File opening and media constants
Status: Complete
Files changed: app/files/constants.py; app/files/open_plan.py; app/files/opening.py; app/final_library/promotion_parts/transfer.py; app/folder_policy/service.py; app/rename/discovery.py; app/rename/planner.py; app/rename/utils.py; refreshed summaries for touched source files; Docs/architecture/DEPENDENCY_BOUNDARY_RULES.md; Docs/rewrite/dependency-refactor-phases/00_navigation_and_tracker.md; Docs/rewrite/dependency-refactor-phases/05_phase_4_shared_blast_radius.md; Docs/rewrite/dependency-refactor-phases/05j_phase_4_file_opening_media_constants_subphase.md; Docs/generated/PROJECT_INDEX.md; Docs/generated/DEPENDENCY_GRAPH.md
Behavior changes: None intended. Media suffix values, VLC long-path threshold value, file URI/path normalization behavior, Windows native path conversion, VLC junction behavior, final-library companion sidecar matching, folder-policy media selection, rename media discovery, rename media suffix stripping, and rename long-path warning behavior were preserved.
Checks run: .\DesktopApp\Runtime\Python\python.exe -m pytest DesktopApp\tests\test_service_file_open_plan.py DesktopApp\tests\test_service_file_open.py DesktopApp\tests\test_final_library_promotion.py DesktopApp\tests\test_service_folder_policy_contracts.py DesktopApp\tests\test_service_folder_policy_io.py DesktopApp\tests\test_service_folder_policy_probe.py DesktopApp\tests\test_service_rename_discovery.py DesktopApp\tests\test_service_rename_planner.py DesktopApp\tests\test_service_rename_utils.py (51 passed); .\DesktopApp\Runtime\Python\python.exe -m pytest tests\tooling (39 passed); .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\check_dependency_boundaries.py --max-internal-imports 1 (passed with allowlist); .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\check_active_doc_references.py (passed); .\DesktopApp\Runtime\Python\python.exe .\scripts\lint-naming.py (passed); .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\refresh_summaries.py --check (passed); .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\generate_project_index.py --check (passed); git diff --check (passed with line-ending warnings only).
Dependency checker result: app.shared.utils imports dropped from 10 to 8; app.shared.constants imports dropped from 14 to 5; app.shared.protocols remains 0; direct app.shared remains 0; package-level cycles remain 0; the existing app.contracts.source_media* module-level cycle remains allowlisted by Phase 5 tooling.
Known risks: This pass deliberately moved shared ownership only. The broad media suffix set remains a cross-domain file/media contract, now owned by app.files. Dead shared exports remain in app.shared.constants and app.shared.utils until 4L. Remaining shared constants/helpers still touch folder policy, failure cleanup, storage app-state, config save, maintenance release, and schedule app-state behavior.
Remaining shared hotspots: app.shared.utils has 8 app import entries after this pass across config save, failure cleanup, folder-policy IO, maintenance release, and schedule app-state reads/writes; app.shared.constants has 5 app import entries across folder-policy schema/sidecar constants, failure manifest schema, and storage app-state name; app.shared.protocols has 0 app import entries but retains process-oriented protocol definitions until a later shrink/final cleanup pass.
Next: Continue Phase 4 with 4K folder policy, failure, storage, and app-state ownership; rerun final review after Phase 4 reaches the desired cleanup threshold.
```
