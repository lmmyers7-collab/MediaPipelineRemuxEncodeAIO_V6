# Phase 4C - Status Read Models

Previous: [05_phase_4_shared_blast_radius.md](05_phase_4_shared_blast_radius.md)

Next: [05_phase_4_shared_blast_radius.md](05_phase_4_shared_blast_radius.md)

Created: 2026-05-31

## Scope

This Phase 4 sub-phase moves status-owned read-model helpers and protocols out
of `app.shared`.

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
| `app.shared.utils` | 27 |
| `app.shared.constants` | 35 |
| `app.shared.protocols` | 16 |

The targeted status imports were:

| Symbol or helper | Previous owner | Count | Category | Target owner |
|---|---|---:|---|---|
| `_read_json_file` in status modules | `app.shared.utils` | 3 | status read-model file helper | `app.status.file_io` |
| `_tail_text_file` in status readers | `app.shared.utils` | 1 | status log-tail helper | `app.status.file_io` |
| `_tail_jsonl_file` in status readers | `app.shared.utils` | 1 | status event-tail helper | `app.status.file_io` |
| `WarningLogger` for status readers | `app.shared.protocols` | 1 | status protocol/type | `app.status.contracts` |
| `StatusSnapshotServiceProtocol` | `app.shared.protocols` | 1 | status protocol/type | `app.status.contracts` |

## Sub-Phase Definition

```text
Sub-phase: 4C - Status read models
Symbols targeted: status JSON reads; status text tail; status JSONL event tail; status WarningLogger; StatusSnapshotServiceProtocol
Current import count: 5 app.shared.utils entries and 2 app.shared.protocols entries in status modules
Target owner: app.status.file_io and app.status.contracts
Risk category: read-only status evidence helpers and protocols; medium risk because status output is operator-facing
Files expected: app/status/file_io.py; app/status/contracts.py; app/status/readers.py; app/status/active_jobs.py; app/status/errors.py; app/status/snapshot_runner.py; app/shared/protocols.py; refreshed summaries
Validation: focused status tests, dependency checker, summary/project-index checks
Stop condition: stop after removing status read-model shared imports and recording remaining shared hotspots
```

## Handoff

```text
Sub-phase: 4C - Status read models
Status: Complete
Files changed: app/status/contracts.py; app/status/file_io.py; app/status/readers.py; app/status/active_jobs.py; app/status/errors.py; app/status/snapshot_runner.py; app/shared/protocols.py; refreshed summaries for touched source files; Docs/architecture/DEPENDENCY_BOUNDARY_RULES.md; Docs/rewrite/dependency-refactor-phases/00_navigation_and_tracker.md; Docs/rewrite/dependency-refactor-phases/05_phase_4_shared_blast_radius.md; Docs/rewrite/dependency-refactor-phases/05c_phase_4_status_read_models_subphase.md; Docs/generated/PROJECT_INDEX.md; Docs/generated/DEPENDENCY_GRAPH.md
Behavior changes: None intended. Status JSON reads, log tailing, JSONL event tailing, and status-specific protocols keep the same behavior under status-owned modules.
Checks run: .\DesktopApp\Runtime\Python\python.exe -m pytest DesktopApp\tests\test_service_status_readers.py DesktopApp\tests\test_service_status_active_jobs.py DesktopApp\tests\test_service_status_errors.py DesktopApp\tests\test_service_status_snapshot_runner.py DesktopApp\tests\test_status_service.py DesktopApp\tests\test_facade_status_policy.py (33 passed); .\DesktopApp\Runtime\Python\python.exe -m pytest tests\tooling (39 passed); .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\check_dependency_boundaries.py --max-internal-imports 1 (passed with allowlist); .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\check_active_doc_references.py (passed); .\DesktopApp\Runtime\Python\python.exe .\scripts\lint-naming.py (passed); .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\refresh_summaries.py --check (passed, 746 source files current); .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\generate_project_index.py --check (passed); git diff --check (passed; CRLF normalization warnings only).
Dependency checker result: app.shared.utils imports dropped from 27 to 22; app.shared.constants remains 35; app.shared.protocols imports dropped from 16 to 14; direct app.shared remains 0; package-level cycles remain 0; the existing app.contracts.source_media* module-level cycle remains allowlisted by Phase 5 tooling.
Known risks: Status output is operator-facing, so this was kept mechanical and covered with focused status tests. Status file IO helper behavior was copied from app.shared.utils, so later cleanup may consolidate read helpers under a neutral storage/observability owner if needed.
Remaining shared hotspots: settings save, folder policy, process lifecycle/control, publish pending reads, queue dry-run, rename apply/preview, schedule app-state, file opening helpers, media suffix constants, audio/routing constants, rename constants, process constants, storage/app-state constants, and service protocols outside status.
Next: Continue Phase 4 with another deliberately scoped sub-phase; rerun final review after Phase 4 reaches the desired cleanup threshold.
```
