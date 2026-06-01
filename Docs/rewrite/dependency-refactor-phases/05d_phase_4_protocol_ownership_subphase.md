# Phase 4D - Protocol Ownership

Previous: [05_phase_4_shared_blast_radius.md](05_phase_4_shared_blast_radius.md)

Next: [05_phase_4_shared_blast_radius.md](05_phase_4_shared_blast_radius.md)

Created: 2026-05-31

## Scope

This Phase 4 sub-phase moves direct `app.shared.protocols` consumers to
domain-owned contract modules.

It does not change media policy, queue behavior, publish/drain behavior,
settings persistence, source movement, cleanup, process lifecycle behavior,
rename behavior, FFmpeg policy, subtitle policy, audio policy, or WebView/Tauri
ownership.

## Inventory Baseline

Baseline command:

```powershell
.\DesktopApp\Runtime\Python\python.exe .\scripts\dev\check_dependency_boundaries.py --max-internal-imports 1
```

Checker baseline before this sub-phase:

| Import group | App import entries |
|---|---:|
| `app.shared` | 0 |
| `app.shared.utils` | 22 |
| `app.shared.constants` | 35 |
| `app.shared.protocols` | 14 |

The targeted protocol imports were:

| Symbol or protocol | Previous owner | Count | Category | Target owner |
|---|---|---:|---|---|
| `ConfigDocumentServiceProtocol` | `app.shared.protocols` | 1 | config protocol/type | `app.config.contracts` |
| `ConfigSaveServiceProtocol` | `app.shared.protocols` | 1 | config protocol/type | `app.config.contracts` |
| `RunCaptureFunc` for config document validation | `app.shared.protocols` | 1 | config runner type | `app.config.contracts` |
| `PowerShellHostServiceProtocol` | `app.shared.protocols` | 1 | paths protocol/type | `app.paths.contracts` |
| `PathResolutionServiceProtocol` | `app.shared.protocols` | 1 | paths protocol/type | `app.paths.contracts` |
| `QueueDryRunServiceProtocol` | `app.shared.protocols` | 1 | queue protocol/type | `app.queue.contracts` |
| `QueuePreviewServiceProtocol` | `app.shared.protocols` | 1 | queue protocol/type | `app.queue.contracts` |
| `RenameApplyServiceProtocol` | `app.shared.protocols` | 1 | rename protocol/type | `app.rename.contracts` |
| `RenamePlannerServiceProtocol` | `app.shared.protocols` | 1 | rename protocol/type | `app.rename.contracts` |
| `RenamePreviewLoadServiceProtocol` | `app.shared.protocols` | 1 | rename protocol/type | `app.rename.contracts` |
| `RenamePreviewScriptServiceProtocol` | `app.shared.protocols` | 1 | rename protocol/type | `app.rename.contracts` |
| `RunCaptureFunc` for rename preview | `app.shared.protocols` | 1 | rename runner type | `app.rename.contracts` |
| `AppStateMigrationServiceProtocol` | `app.shared.protocols` | 1 | storage protocol/type | `app.storage.contracts` |
| `WarningLogger` for storage migration | `app.shared.protocols` | 1 | storage logger protocol | `app.storage.contracts` |

## Sub-Phase Definition

```text
Sub-phase: 4D - Protocol ownership
Symbols targeted: remaining direct app.shared.protocols imports in config, paths, queue, rename, and storage modules
Current import count: 14 app.shared.protocols entries
Target owner: app.config.contracts; app.paths.contracts; app.queue.contracts; app.rename.contracts; app.storage.contracts
Risk category: type/protocol relocation only; medium risk because queue, rename, settings, and app-state surfaces are sensitive even though behavior is unchanged
Files expected: five domain contracts modules; ten direct consumers; app/shared/protocols.py; refreshed summaries
Validation: focused config/path/queue/rename/storage tests, dependency checker, tooling, summary/project-index checks
Stop condition: stop after direct app.shared.protocols imports reach 0 and remaining shared hotspots are recorded
```

## Handoff

```text
Sub-phase: 4D - Protocol ownership
Status: Complete
Files changed: app/config/contracts.py; app/config/document_runner.py; app/config/save_runner.py; app/paths/contracts.py; app/paths/host.py; app/paths/resolution_runner.py; app/queue/contracts.py; app/queue/dry_run_runner.py; app/queue/preview_builder.py; app/rename/contracts.py; app/rename/apply_runner.py; app/rename/planner.py; app/rename/preview_runner.py; app/storage/contracts.py; app/storage/state_migration.py; app/shared/protocols.py; refreshed summaries for touched source files; Docs/architecture/DEPENDENCY_BOUNDARY_RULES.md; Docs/rewrite/dependency-refactor-phases/00_navigation_and_tracker.md; Docs/rewrite/dependency-refactor-phases/05_phase_4_shared_blast_radius.md; Docs/rewrite/dependency-refactor-phases/05d_phase_4_protocol_ownership_subphase.md; Docs/generated/PROJECT_INDEX.md; Docs/generated/DEPENDENCY_GRAPH.md
Behavior changes: None intended. Service protocol definitions and RunCaptureFunc types moved to domain contracts; runtime helper logic and call order are unchanged.
Checks run: .\DesktopApp\Runtime\Python\python.exe -m pytest DesktopApp\tests\test_service_config_document_runner.py DesktopApp\tests\test_service_config_save_runner.py DesktopApp\tests\test_service_path_host_runner.py DesktopApp\tests\test_service_path_resolution_runner.py DesktopApp\tests\test_service_path_state_migration.py DesktopApp\tests\test_service_queue_dry_run_runner.py DesktopApp\tests\test_service_queue_preview_builder.py DesktopApp\tests\test_service_rename_apply_runner.py DesktopApp\tests\test_service_rename_planner.py DesktopApp\tests\test_service_rename_preview_runner.py (35 passed); .\DesktopApp\Runtime\Python\python.exe -m pytest tests\tooling (39 passed); .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\check_dependency_boundaries.py --max-internal-imports 1 (passed with allowlist); .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\check_active_doc_references.py (passed); .\DesktopApp\Runtime\Python\python.exe .\scripts\lint-naming.py (passed); .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\refresh_summaries.py --check (passed, 751 source files current); .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\generate_project_index.py --check (passed); git diff --check (passed; CRLF normalization warnings only).
Dependency checker result: app.shared.protocols imports dropped from 14 to 0; app.shared.utils remains 22; app.shared.constants remains 35; direct app.shared remains 0; package-level cycles remain 0; the existing app.contracts.source_media* module-level cycle remains allowlisted by Phase 5 tooling.
Known risks: This sub-phase changes protocol ownership only. app.shared.protocols still contains process-oriented protocol definitions for later shrink/final cleanup, but no app module imports it directly after this pass. Queue, rename, config save, and app-state runtime behavior were intentionally left unchanged.
Remaining shared hotspots: app.shared.utils has 22 app import entries; app.shared.constants has 35 app import entries; app.shared.protocols has 0 app import entries but retains process-oriented protocol definitions until a later final-shrink pass.
Next: Continue Phase 4 with 4E config constants; rerun final review after Phase 4 reaches the desired cleanup threshold.
```
