# Phase 4K - Folder Policy, Failure, Storage, and App State

Previous: [05j_phase_4_file_opening_media_constants_subphase.md](05j_phase_4_file_opening_media_constants_subphase.md)

Next: [05_phase_4_shared_blast_radius.md](05_phase_4_shared_blast_radius.md)

Created: 2026-05-31

## Scope

This Phase 4 sub-phase moves folder-policy schema/sidecar constants, failure
clear-manifest schema ownership, storage app-state name ownership, and
schedule/folder-policy/failure file IO helpers out of `app.shared.*` and into
their owning domains.

It does not change folder-policy sidecar shape, folder-policy read/write
behavior, failure marker clearing, failure workspace clearing, failure
manifest shape, failure cleanup path boundaries, app-state path migration,
schedule app-state load-merge behavior, settings persistence, source/scratch
or output movement, pending publish/drain behavior, queue behavior, rename
apply behavior, cleanup policy, process lifecycle behavior, FFmpeg policy,
subtitle policy, audio policy, media policy, or WebView/Tauri ownership.

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
| `app.shared.utils` | 8 |
| `app.shared.constants` | 5 |
| `app.shared.protocols` | 0 |

The targeted imports were:

| Symbol or helper | Previous owner | Count | Category | Target owner |
|---|---|---:|---|---|
| `FOLDER_POLICY_SCHEMA_VERSION` | `app.shared.constants` | 2 | folder-policy sidecar schema constant | `app.folder_policy.constants` |
| `FOLDER_POLICY_SIDECAR_NAME` | `app.shared.constants` | 1 | folder-policy sidecar filename constant | `app.folder_policy.constants` |
| `FAILURE_CLEAR_MANIFEST_SCHEMA_VERSION` | `app.shared.constants` | 1 | failure cleanup manifest schema constant | `app.failures.constants` |
| `APP_STATE_NAME` | `app.shared.constants` | 1 | storage/app-state filename constant | `app.storage.constants` |
| `_atomic_write_text` | `app.shared.utils` | 3 | folder-policy, failure, and schedule atomic write helper | owning domain file IO modules |
| `_read_json_file` | `app.shared.utils` | 3 | folder-policy and schedule JSON read helper | owning domain file IO modules |

## Sub-Phase Definition

```text
Sub-phase: 4K - Folder policy, failure, storage, and app state
Symbols targeted: folder-policy schema/sidecar constants, failure clear manifest schema, app-state filename, folder-policy/failure/schedule file IO helpers
Current import count: 8 app.shared.utils entries and 5 app.shared.constants entries before the sub-phase
Target owner: app.folder_policy, app.failures, app.storage, and app.schedule
Risk category: high boundary, mechanical helper/constant move only; cleanup and app-state write behavior are protected
Files expected: domain constants/file_io owners; folder-policy, failure cleanup, storage migration, and schedule app-state consumers; focused tests; refreshed summaries and docs
Validation: focused folder-policy/failure/storage/schedule/rename tests, dependency checker, tooling, summary/project-index checks
Stop condition: stop after targeted constants and helpers no longer import from app.shared and checker records updated shared-utils/shared-constants counts
```

## Handoff

```text
Sub-phase: 4K - Folder policy, failure, storage, and app state
Status: Complete
Files changed: app/folder_policy/constants.py; app/folder_policy/file_io.py; app/folder_policy/contracts.py; app/folder_policy/io.py; app/failures/constants.py; app/failures/file_io.py; app/failures/cleanup_service.py; app/storage/constants.py; app/storage/state_migration.py; app/schedule/file_io.py; app/schedule/app_state.py; DesktopApp/tests/test_service_folder_policy_contracts.py; DesktopApp/tests/test_service_folder_policy_io.py; DesktopApp/tests/test_service_path_state_migration.py; DesktopApp/tests/test_service_path_resolution_runner.py; DesktopApp/tests/test_rename_service.py; refreshed summaries for touched source files; Docs/architecture/DEPENDENCY_BOUNDARY_RULES.md; Docs/rewrite/dependency-refactor-phases/00_navigation_and_tracker.md; Docs/rewrite/dependency-refactor-phases/05_phase_4_shared_blast_radius.md; Docs/rewrite/dependency-refactor-phases/05k_phase_4_folder_failure_storage_app_state_subphase.md; Docs/generated/PROJECT_INDEX.md; Docs/generated/DEPENDENCY_GRAPH.md
Behavior changes: None intended. Folder-policy schema and sidecar values, JSON read behavior, atomic write retry/replace behavior, failure cleanup manifest schema values, failure marker/workspace clear manifests, app-state filename, app-state migration copy/fallback behavior, and schedule app-state load-merge/write behavior were preserved.
Checks run: .\DesktopApp\Runtime\Python\python.exe -m pytest DesktopApp\tests\test_service_folder_policy_contracts.py DesktopApp\tests\test_service_folder_policy_io.py DesktopApp\tests\test_service_folder_policy_probe.py DesktopApp\tests\test_service_failure_markers.py DesktopApp\tests\test_facade_failures_policy.py DesktopApp\tests\test_service_path_state_migration.py DesktopApp\tests\test_service_path_resolution_runner.py DesktopApp\tests\test_service_app_schedule.py DesktopApp\tests\test_application_facade_schedule.py DesktopApp\tests\test_rename_service.py (61 passed); .\DesktopApp\Runtime\Python\python.exe -m pytest tests\tooling (39 passed); .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\check_dependency_boundaries.py --max-internal-imports 1 (passed with allowlist); .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\check_active_doc_references.py (passed); .\DesktopApp\Runtime\Python\python.exe .\scripts\lint-naming.py (passed); .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\refresh_summaries.py --check (passed); .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\generate_project_index.py --check (passed); git diff --check (passed with line-ending warnings only).
Dependency checker result: app.shared.constants imports dropped from 5 to 0; app.shared.utils imports dropped from 8 to 3; app.shared.protocols remains 0; direct app.shared remains 0; package-level cycles remain 0; the existing app.contracts.source_media* module-level cycle remains allowlisted by Phase 5 tooling.
Known risks: Cleanup and app-state behavior are protected areas, so this pass only changed import ownership and mechanically copied helpers. app.config.save_runner still imports settings-save/open-path helpers from app.shared.utils, and app.maintenance.release still imports a release-manifest JSON read helper from app.shared.utils. Dead shared constants and helpers remain until 4L.
Remaining shared hotspots: app.shared.utils has 3 app import entries after this pass across config save and maintenance release; app.shared.constants has 0 app import entries; app.shared.protocols has 0 app import entries but retains process-oriented protocol definitions until a later shrink/final cleanup pass.
Next: Continue Phase 4 with 4L final shared shrink; rerun final review after Phase 4 reaches the desired cleanup threshold.
```
