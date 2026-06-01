# Phase 4F - Process Runtime State

Previous: [05e_phase_4_config_constants_subphase.md](05e_phase_4_config_constants_subphase.md)

Next: [05_phase_4_shared_blast_radius.md](05_phase_4_shared_blast_radius.md)

Created: 2026-05-31

## Scope

This Phase 4 sub-phase moves process-owned runtime constants and process JSON
or log file helpers out of direct `app.shared.constants` and `app.shared.utils`
consumers.

It does not change process lifecycle choices, launch scope, command journal
semantics, queue behavior, media policy, publish/drain behavior, settings
persistence, source movement, cleanup, rename behavior, FFmpeg policy, subtitle
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
| `app.shared.utils` | 22 |
| `app.shared.constants` | 24 |
| `app.shared.protocols` | 0 |

The targeted process imports were:

| Symbol or helper | Previous owner | Count | Category | Target owner |
|---|---|---:|---|---|
| `ACTIVE_JOB_SCHEMA_VERSION` | `app.shared.constants` | 1 | process active-job schema constant | `app.processes.constants` |
| `CONTROL_FLAG_SCHEMA_VERSION` | `app.shared.constants` | 1 | process control-flag schema constant | `app.processes.constants` |
| `AUDIT_PROGRESS_LAUNCH_CLEANUP_STALE_SECONDS` | `app.shared.constants` | 1 | process lifecycle timing constant | `app.processes.constants` |
| `CONTROL_FLAG_STALE_AFTER_SECONDS` | `app.shared.constants` | 1 | process lifecycle timing constant | `app.processes.constants` |
| `PIPELINE_PROGRESS_LAUNCH_CLEANUP_STALE_SECONDS` | `app.shared.constants` | 1 | process lifecycle timing constant | `app.processes.constants` |
| `PROCESS_LAUNCH_READY_CHECK_SECONDS` | `app.shared.constants` | 1 | process launch readiness timing constant | `app.processes.constants` |
| `PROCESS_LAUNCH_ERROR_TAIL_LINES` | `app.shared.constants` | 1 | process log-tail constant | `app.processes.constants` |
| `_atomic_write_text` | `app.shared.utils` | 3 | process runtime JSON/text write helper | `app.processes.file_io` |
| `_read_json_file` | `app.shared.utils` | 2 | process runtime JSON read helper | `app.processes.file_io` |
| `_tail_text_file` | `app.shared.utils` | 1 | process log tail helper | `app.processes.file_io` |

The compatibility service module also imported process constants from
`app.shared.constants`; those imports were repointed to `app.processes.constants`
while leaving the service module globals available.

## Sub-Phase Definition

```text
Sub-phase: 4F - Process runtime state
Symbols targeted: active-job/control-flag schema constants, lifecycle timing constants, process log tail settings, and process JSON/text helpers
Current import count: 22 app.shared.utils entries and 24 app.shared.constants entries before the sub-phase
Target owner: app.processes.constants and app.processes.file_io
Risk category: medium/high; mechanical move only, but process lifecycle, close-readiness, and control flags are release-critical
Files expected: process constants owner; process file IO owner; active jobs, control flags, control facade, logs, lifecycle consumers; service compatibility import; focused process tests; summaries and docs
Validation: focused process lifecycle/control/readiness tests, dependency checker, tooling, summary/project-index checks
Stop condition: stop after process modules no longer import app.shared.constants/utils and the checker records reduced shared counts
```

## Handoff

```text
Sub-phase: 4F - Process runtime state
Status: Complete
Files changed: app/processes/constants.py; app/processes/file_io.py; app/processes/active_jobs.py; app/processes/control_flags.py; app/processes/control_facade.py; app/processes/logs.py; app/processes/lifecycle.py; DesktopApp/mediapipeline_desktop_app/services.py; DesktopApp/tests/test_service_process_active_jobs.py; refreshed summaries for touched source files; Docs/architecture/DEPENDENCY_BOUNDARY_RULES.md; Docs/rewrite/dependency-refactor-phases/00_navigation_and_tracker.md; Docs/rewrite/dependency-refactor-phases/05_phase_4_shared_blast_radius.md; Docs/rewrite/dependency-refactor-phases/05f_phase_4_process_runtime_state_subphase.md; Docs/generated/PROJECT_INDEX.md; Docs/generated/DEPENDENCY_GRAPH.md
Behavior changes: None intended. Process constants and file helpers were copied or repointed mechanically with values and retry/tail semantics preserved. Process lifecycle choices, command/control behavior, close-readiness behavior, and launch scope were not changed.
Checks run: .\DesktopApp\Runtime\Python\python.exe -m pytest DesktopApp\tests\test_service_process_active_jobs.py DesktopApp\tests\test_service_process_control_flags.py DesktopApp\tests\test_service_process_control_runner.py DesktopApp\tests\test_service_process_logs.py DesktopApp\tests\test_service_process_readiness.py DesktopApp\tests\test_process_service.py DesktopApp\tests\test_application_facade_process_control.py DesktopApp\tests\test_application_facade_close_readiness.py (49 passed); .\DesktopApp\Runtime\Python\python.exe -m pytest tests\tooling (39 passed); .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\check_dependency_boundaries.py --max-internal-imports 1 (passed with allowlist); .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\check_active_doc_references.py (passed); .\DesktopApp\Runtime\Python\python.exe .\scripts\lint-naming.py (passed); .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\refresh_summaries.py --check (passed, 754 source files current); .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\generate_project_index.py --check (passed); git diff --check (passed; CRLF normalization warnings only).
Dependency checker result: app.shared.utils imports dropped from 22 to 16; app.shared.constants imports dropped from 24 to 17; app.shared.protocols remains 0; direct app.shared remains 0; package-level cycles remain 0; the existing app.contracts.source_media* module-level cycle remains allowlisted by Phase 5 tooling.
Generated artifacts updated: Docs/generated/PROJECT_INDEX.md and Docs/generated/DEPENDENCY_GRAPH.md regenerated from 754 summaries.
Summaries refreshed: Targeted refresh wrote 9 summaries for the Phase 4F touched source and test files. Final .\scripts\dev\refresh_summaries.py --check reported 754 source files current with no orphan summaries.
Known risks: This sub-phase touched release-critical process surfaces only through mechanical import and helper-owner moves. app.shared.constants still contains dead process constant exports and app.shared.utils still contains the original generic helper definitions until the planned 4L final shared-shrink pass. The compatibility service still imports other non-process app.shared.constants and app.shared.utils symbols for later sub-phases.
Remaining shared hotspots: app.shared.utils has 16 app import entries after this pass across config save, failure cleanup, file opening, folder-policy IO, maintenance release, publish pending reads, queue dry-run writes, rename writes, and schedule app-state reads/writes; app.shared.constants has 17 app import entries after this pass across file/media, rename, folder-policy, failure, and storage constants; app.shared.protocols has 0 app import entries but retains process-oriented protocol definitions until a later shrink/final cleanup pass.
Next: Continue Phase 4 with 4G queue ownership; rerun final review after Phase 4 reaches the desired cleanup threshold.
```
