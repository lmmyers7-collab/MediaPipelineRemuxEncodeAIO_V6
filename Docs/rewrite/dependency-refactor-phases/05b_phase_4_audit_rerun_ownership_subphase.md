# Phase 4B - Audit Rerun Ownership

Previous: [05_phase_4_shared_blast_radius.md](05_phase_4_shared_blast_radius.md)

Next: [05_phase_4_shared_blast_radius.md](05_phase_4_shared_blast_radius.md)

Created: 2026-05-31

## Scope

This Phase 4 sub-phase moves audit rerun owned constants, protocols, and local
file IO helpers out of `app.shared`.

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
| `app.shared.utils` | 32 |
| `app.shared.constants` | 36 |
| `app.shared.protocols` | 19 |

The targeted audit rerun imports were:

| Symbol or helper | Previous owner | Count | Category | Target owner |
|---|---|---:|---|---|
| `RERUN_CSV_COLUMNS` | `app.shared.constants` | 1 | audit rerun CSV contract constant | `app.audit.rerun_csv` |
| `RerunCsvExportServiceProtocol` | `app.shared.protocols` | 1 | audit protocol/type | `app.audit.rerun_contracts` |
| `RerunMetadataServiceProtocol` | `app.shared.protocols` | 1 | audit protocol/type | `app.audit.rerun_contracts` |
| `RunCaptureFunc` for audit metadata | `app.shared.protocols` | 1 | audit runner type | `app.audit.rerun_contracts` |
| `_atomic_write_text` in audit rerun modules | `app.shared.utils` | 3 | audit rerun file helper | `app.audit.rerun_file_io` |
| `_read_json_file` in audit rerun modules | `app.shared.utils` | 2 | audit rerun file helper | `app.audit.rerun_file_io` |

## Sub-Phase Definition

```text
Sub-phase: 4B - Audit rerun ownership
Symbols targeted: RERUN_CSV_COLUMNS; RerunCsvExportServiceProtocol; RerunMetadataServiceProtocol; audit RunCaptureFunc; audit rerun atomic text writes; audit rerun JSON reads
Current import count: 5 app.shared.utils entries, 1 app.shared.constants entry, and 3 app.shared.protocols entries in audit rerun modules
Target owner: app.audit.rerun_csv, app.audit.rerun_contracts, app.audit.rerun_file_io
Risk category: audit-owned constants/types plus mechanical file-helper relocation; low-to-medium risk
Files expected: app/audit/rerun_contracts.py; app/audit/rerun_file_io.py; app/audit/rerun_csv.py; app/audit/rerun_export.py; app/audit/rerun_io.py; app/audit/rerun_metadata.py; app/shared/constants.py; app/shared/protocols.py; DesktopApp/mediapipeline_desktop_app/services.py; refreshed summaries
Validation: focused audit rerun tests, dependency checker, summary/project-index checks
Stop condition: stop after removing audit rerun shared imports and recording remaining shared hotspots
```

## Handoff

```text
Sub-phase: 4B - Audit rerun ownership
Status: Complete
Files changed: app/audit/rerun_contracts.py; app/audit/rerun_file_io.py; app/audit/rerun_csv.py; app/audit/rerun_export.py; app/audit/rerun_io.py; app/audit/rerun_metadata.py; app/shared/constants.py; app/shared/protocols.py; DesktopApp/mediapipeline_desktop_app/services.py; refreshed summaries for touched source files; Docs/architecture/DEPENDENCY_BOUNDARY_RULES.md; Docs/rewrite/dependency-refactor-phases/00_navigation_and_tracker.md; Docs/rewrite/dependency-refactor-phases/05_phase_4_shared_blast_radius.md; Docs/rewrite/dependency-refactor-phases/05b_phase_4_audit_rerun_ownership_subphase.md; Docs/generated/PROJECT_INDEX.md; Docs/generated/DEPENDENCY_GRAPH.md
Behavior changes: None intended. Audit rerun CSV columns keep the same values; audit-specific protocols and file helper behavior were moved to audit-owned modules.
Checks run: .\DesktopApp\Runtime\Python\python.exe -m pytest DesktopApp\tests\test_service_audit_rerun_csv.py DesktopApp\tests\test_service_audit_rerun_export.py DesktopApp\tests\test_service_audit_rerun_io.py DesktopApp\tests\test_service_audit_rerun_metadata.py DesktopApp\tests\test_service_audit_rerun_records.py (21 passed); .\DesktopApp\Runtime\Python\python.exe -m pytest tests\tooling (39 passed); .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\check_dependency_boundaries.py --max-internal-imports 1 (passed with allowlist); .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\check_active_doc_references.py (passed); .\DesktopApp\Runtime\Python\python.exe .\scripts\lint-naming.py (passed); .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\refresh_summaries.py --check (passed after refreshing pre-existing stale WebView settings summaries); .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\generate_project_index.py --check (passed); git diff --check (passed with existing CRLF normalization warnings).
Dependency checker result: app.shared.utils imports dropped from 32 to 27; app.shared.constants imports dropped from 36 to 35; app.shared.protocols imports dropped from 19 to 16; direct app.shared remains 0; package-level cycles remain 0; the existing app.contracts.source_media* module-level cycle remains allowlisted by Phase 5 tooling.
Known risks: Audit rerun file IO helper behavior was copied mechanically from app.shared.utils so later shared cleanup may want to consolidate common storage helpers under a neutral owner. The checker is static AST analysis only. Five pre-existing stale WebView settings summaries were refreshed to restore repository summary freshness, but their source files were not part of this sub-phase.
Remaining shared hotspots: settings save, folder policy, process lifecycle/control, publish pending reads, queue dry-run, rename apply/preview, schedule app-state, status readers, media suffix constants, audio/routing constants, rename constants, process constants, storage/app-state constants, and service protocols outside audit.
Next: Continue Phase 4 with another deliberately scoped sub-phase; rerun final review after Phase 4 reaches the desired cleanup threshold.
```
