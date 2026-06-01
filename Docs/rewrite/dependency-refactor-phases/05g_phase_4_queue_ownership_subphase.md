# Phase 4G - Queue Ownership

Previous: [05f_phase_4_process_runtime_state_subphase.md](05f_phase_4_process_runtime_state_subphase.md)

Next: [05_phase_4_shared_blast_radius.md](05_phase_4_shared_blast_radius.md)

Created: 2026-05-31

## Scope

This Phase 4 sub-phase moves queue dry-run write helper ownership out of
`app.shared.utils` and into the queue domain.

It does not change queue mutation behavior, launch scope, dry-run command
construction, cached fallback behavior, temp snapshot cleanup, SQLite mirroring,
media policy, publish/drain behavior, settings persistence, source movement,
cleanup, process lifecycle behavior, rename behavior, FFmpeg policy, subtitle
policy, audio policy, or WebView/Tauri ownership.

## Inventory Baseline

Baseline command:

```powershell
.\DesktopApp\Runtime\Python\python.exe .\scripts\dev\check_dependency_boundaries.py --max-internal-imports 1
```

Checker baseline before this sub-phase:

| Import group | App import entries |
|---|---:|
| `app.shared` | 0 |
| `app.shared.utils` | 16 |
| `app.shared.constants` | 17 |
| `app.shared.protocols` | 0 |

The targeted queue import was:

| Symbol or helper | Previous owner | Count | Category | Target owner |
|---|---|---:|---|---|
| `_atomic_write_text` | `app.shared.utils` | 1 | queue dry-run snapshot write helper | `app.queue.file_io` |

Queue service protocols were already moved to `app.queue.contracts` during
Phase 4D, so this pass only addressed the remaining queue-owned shared helper.

## Sub-Phase Definition

```text
Sub-phase: 4G - Queue ownership
Symbols targeted: queue dry-run atomic write helper
Current import count: 16 app.shared.utils entries before the sub-phase
Target owner: app.queue.file_io
Risk category: medium; mechanical helper move only, but queue dry-run and snapshot promotion semantics are operator-facing
Files expected: queue file IO owner; queue dry-run runner consumer; refreshed summaries and docs
Validation: focused queue dry-run/preview/snapshot/storage tests, dependency checker, tooling, summary/project-index checks
Stop condition: stop after app.queue has no direct app.shared.* imports and the checker records the reduced shared-utils count
```

## Handoff

```text
Sub-phase: 4G - Queue ownership
Status: Complete
Files changed: app/queue/file_io.py; app/queue/dry_run_runner.py; refreshed summaries for touched source files; Docs/architecture/DEPENDENCY_BOUNDARY_RULES.md; Docs/rewrite/dependency-refactor-phases/00_navigation_and_tracker.md; Docs/rewrite/dependency-refactor-phases/05_phase_4_shared_blast_radius.md; Docs/rewrite/dependency-refactor-phases/05g_phase_4_queue_ownership_subphase.md; Docs/generated/PROJECT_INDEX.md; Docs/generated/DEPENDENCY_GRAPH.md
Behavior changes: None intended. Queue dry-run snapshot promotion still uses the same atomic write implementation and preserves command construction, timeout/cached fallback handling, temp snapshot cleanup, and SQLite mirroring.
Checks run: .\DesktopApp\Runtime\Python\python.exe -m pytest DesktopApp\tests\test_service_queue_dry_run.py DesktopApp\tests\test_service_queue_dry_run_runner.py DesktopApp\tests\test_service_queue_preview_builder.py DesktopApp\tests\test_service_queue_snapshot.py DesktopApp\tests\test_application_facade_queue.py DesktopApp\tests\test_phase4_storage_observability.py (29 passed); .\DesktopApp\Runtime\Python\python.exe -m pytest tests\tooling (39 passed); .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\check_dependency_boundaries.py --max-internal-imports 1 (passed with allowlist); .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\check_active_doc_references.py (passed); .\DesktopApp\Runtime\Python\python.exe .\scripts\lint-naming.py (passed); .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\refresh_summaries.py --check (passed); .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\generate_project_index.py --check (passed); git diff --check (passed with line-ending warnings only).
Dependency checker result: app.shared.utils imports dropped from 16 to 15; app.shared.constants remains 17; app.shared.protocols remains 0; direct app.shared remains 0; package-level cycles remain 0; the existing app.contracts.source_media* module-level cycle remains allowlisted by Phase 5 tooling.
Known risks: app.queue has no direct app.shared.* imports after this pass, but the copied atomic helper remains duplicated until the planned 4L final shared-shrink/consolidation review. Queue launch scope and queue mutation behavior were intentionally untouched.
Remaining shared hotspots: app.shared.utils has 15 app import entries after this pass across config save, failure cleanup, file opening, folder-policy IO, maintenance release, publish pending reads, rename writes, and schedule app-state reads/writes; app.shared.constants has 17 app import entries across file/media, rename, folder-policy, failure, and storage constants; app.shared.protocols has 0 app import entries but retains process-oriented protocol definitions until a later shrink/final cleanup pass.
Next: Continue Phase 4 with 4H publish pending reads; rerun final review after Phase 4 reaches the desired cleanup threshold.
```
