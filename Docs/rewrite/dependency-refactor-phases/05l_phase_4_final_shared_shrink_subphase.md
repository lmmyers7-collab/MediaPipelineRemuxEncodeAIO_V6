# Phase 4L - Final Shared Shrink

Previous: [05k_phase_4_folder_failure_storage_app_state_subphase.md](05k_phase_4_folder_failure_storage_app_state_subphase.md)

Next: [05_phase_4_shared_blast_radius.md](05_phase_4_shared_blast_radius.md)

Created: 2026-05-31

## Scope

This Phase 4 sub-phase moves the final settings-save and maintenance-release
helpers out of `app.shared.utils`, redirects the desktop compatibility service
module globals to their domain owners, moves the last rename-owned default
constant into `app.rename.constants`, and shrinks `app.shared.utils`,
`app.shared.constants`, and `app.shared.protocols` to retired empty namespaces.

It does not change settings save behavior, profile save/load behavior, config
path normalization behavior, release manifest read behavior, file opening, media
policy, queue behavior, pending publish/drain behavior, source/scratch/output
movement, cleanup policy, rename apply behavior, process lifecycle behavior,
FFmpeg policy, subtitle policy, audio policy, or WebView/Tauri ownership.

## Inventory Baseline

Baseline command:

```powershell
.\DesktopApp\Runtime\Python\python.exe .\scripts\dev\check_dependency_boundaries.py --max-internal-imports 1
```

Checker baseline before this sub-phase:

| Import group | App import entries |
|---|---:|
| `app.shared` | 0 |
| `app.shared.utils` | 3 |
| `app.shared.constants` | 0 |
| `app.shared.protocols` | 0 |

The targeted imports were:

| Symbol or helper | Previous owner | Count | Category | Target owner |
|---|---|---:|---|---|
| `_atomic_write_text` | `app.shared.utils` | 2 | settings/profile atomic write helper | `app.config.file_io` |
| `_normalize_open_path_text` | `app.shared.utils` | 1 | config path normalization helper | `app.config.file_io` |
| `_read_json_file` | `app.shared.utils` | 1 | release manifest JSON read helper | `app.maintenance.file_io` |
| `PLEX_RENAME_DEFAULT_REMOVE_TERMS` | `app.shared.constants` | Desktop compatibility import only | rename-owned default terms | `app.rename.constants` |

`DesktopApp/mediapipeline_desktop_app/services.py` also still imported
`app.shared.constants` and `app.shared.utils` for compatibility module globals.
Those imports were redirected to existing domain owners before the shared
modules were shrunk.

## Sub-Phase Definition

```text
Sub-phase: 4L - Final shared shrink
Symbols targeted: remaining settings-save/open-path helpers, release manifest JSON read helper, stale desktop compatibility imports, dead shared constants/helpers/protocols
Current import count: 3 app.shared.utils entries before the sub-phase; app.shared.constants and app.shared.protocols already at 0 app import entries
Target owner: app.config, app.maintenance, app.rename, app.files, app.failures, app.storage, and existing domain owners used by DesktopApp services
Risk category: high boundary, mechanical helper/constant move only; settings save and release manifest read behavior are protected
Files expected: config and maintenance file_io owners, config save and release consumers, desktop service compatibility imports, shared modules, refreshed summaries and docs
Validation: focused config/maintenance/desktop-service tests, dependency checker, tooling, summary/project-index checks
Stop condition: stop after app.shared.utils/constants/protocols direct import counts are zero and shared modules contain no active exports
```

## Handoff

```text
Sub-phase: 4L - Final shared shrink
Status: Complete
Files changed: app/config/file_io.py; app/config/save_runner.py; app/maintenance/file_io.py; app/maintenance/release.py; app/rename/constants.py; app/shared/constants.py; app/shared/protocols.py; app/shared/utils.py; DesktopApp/mediapipeline_desktop_app/services.py; refreshed summaries for touched source files; Docs/architecture/DEPENDENCY_BOUNDARY_RULES.md; Docs/rewrite/dependency-refactor-phases/00_navigation_and_tracker.md; Docs/rewrite/dependency-refactor-phases/05_phase_4_shared_blast_radius.md; Docs/rewrite/dependency-refactor-phases/05l_phase_4_final_shared_shrink_subphase.md; Docs/generated/PROJECT_INDEX.md; Docs/generated/DEPENDENCY_GRAPH.md
Behavior changes: None intended. Config atomic write retry/replace behavior, config path normalization, release manifest JSON read/retry behavior, desktop service module globals, rename default remove-term values, and empty importability of app.shared submodules were preserved where applicable.
Checks run: Initial focused pytest command without PYTHONPATH failed during collection with ModuleNotFoundError for mediapipeline_desktop_app; reran the same targets with PYTHONPATH set to repo and DesktopApp paths and 46 tests passed. Final validation: .\DesktopApp\Runtime\Python\python.exe -m pytest DesktopApp\tests\test_service_config_save_runner.py DesktopApp\tests\test_app_config_contract.py DesktopApp\tests\test_service_release.py DesktopApp\tests\test_service_release_plan.py DesktopApp\tests\test_service_release_result.py DesktopApp\tests\test_application_facade_maintenance.py DesktopApp\tests\test_facade_maintenance_policy.py DesktopApp\tests\test_facade_maintenance_command_policy.py DesktopApp\tests\test_telemetry_service.py (46 passed with PYTHONPATH set); .\DesktopApp\Runtime\Python\python.exe -m pytest tests\tooling (39 passed); .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\check_dependency_boundaries.py --max-internal-imports 1 (passed with allowlist); .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\check_active_doc_references.py (passed); .\DesktopApp\Runtime\Python\python.exe .\scripts\lint-naming.py (passed); .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\refresh_summaries.py --check (passed after refreshing unrelated stale summaries); .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\generate_project_index.py --check (passed); git diff --check (passed with line-ending warnings only).
Dependency checker result: 1430 internal app imports; 1 allowlisted module-level cycle in app.contracts.source_media*; 0 package-level cycles; 0 parse errors; direct app.shared imports remain 0; app.shared.utils imports dropped from 3 to 0; app.shared.constants remains 0; app.shared.protocols remains 0; 0 forbidden config/API/status/telemetry direction violations; 10 allowlisted hard findings; 0 unallowlisted hard findings; 217 warning findings; 0 allowlist errors; 0 unused allowlist entries.
Known risks: Settings save and release manifest reads are protected behavior, so this pass copied helper behavior mechanically and did not consolidate helpers across domains. The shared modules remain importable as empty retired namespaces to avoid breaking plain module imports such as import app.shared.constants, but they no longer export active helpers/constants/protocols.
Remaining shared hotspots: No app-domain or DesktopApp-domain imports from app.shared, app.shared.utils, app.shared.constants, or app.shared.protocols remain. Historical docs and dependency-checker test fixtures still mention app.shared intentionally.
Next: Rerun final cleanup review after Phase 4 completion.
```
