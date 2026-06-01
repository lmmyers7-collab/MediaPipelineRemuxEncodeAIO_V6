# Phase 4A - Schedule Constants

Previous: [05_phase_4_shared_blast_radius.md](05_phase_4_shared_blast_radius.md)

Next: [05_phase_4_shared_blast_radius.md](05_phase_4_shared_blast_radius.md)

Created: 2026-05-31

## Scope

This is the first low-risk Phase 4 sub-phase. It only moves schedule day-name
ownership out of `app.shared.constants` and into `app.schedule`.

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
| `app.shared.constants` | 38 |
| `app.shared.protocols` | 19 |

Atlas category CSV baseline showed `app/shared` with 62 incoming domain edges.
Whole-source `rg` also found `DesktopApp/mediapipeline_desktop_app/services.py`
importing from `app.shared.constants` and `app.shared.utils`; the Phase 0
checker only scans `app/`.

### `app.shared.utils`

| Symbol | Count | Category | Likely owner/risk |
|---|---:|---|---|
| `_atomic_write_text` | 14 | path/file helper | Split by owning domain or storage; high risk where settings, queue, rename, process, failure cleanup, or schedule app state writes are involved. |
| `_read_json_file` | 12 | serialization/file helper | Split by owning domain or storage; high risk where publish, process, schedule app state, or status evidence behavior is involved. |
| `_tail_text_file` | 2 | log helper | `app.processes` or `app.status`; medium risk because process/status log evidence is operator-facing. |
| `_normalize_open_path_text` | 1 | path helper | `app.files` or config save boundary; medium risk because settings save/open-path normalization is sensitive. |
| `_coerce_open_path` | 1 | path helper | `app.files`; low-to-medium risk. |
| `_windows_native_path` | 1 | path helper | `app.files`; low-to-medium risk. |
| `_tail_jsonl_file` | 1 | serialization/log helper | `app.status`; medium risk because status evidence display is operator-facing. |

### `app.shared.constants`

| Symbol | Count | Category | Likely owner/risk |
|---|---:|---|---|
| `MEDIA_FILE_SUFFIXES` | 6 | domain-specific media/path constant | `app.files`, `app.rename`, or media contract; high risk because file discovery and final-library behavior are involved. |
| `VLC_LONG_PATH_THRESHOLD` | 3 | path/file constant | `app.files` with rename consumer review; medium risk. |
| `AUDIO_PASSTHROUGH_PROFILE_CODECS` | 2 | audio/config policy constant | `app.config` or audio policy contract; high risk. |
| `AUDIO_PASSTHROUGH_PROFILE_DEFAULT` | 2 | audio/config policy constant | `app.config` or audio policy contract; high risk. |
| `FOLDER_POLICY_SCHEMA_VERSION` | 2 | folder policy contract constant | `app.folder_policy`; medium risk. |
| `RENAME_TOOL_SIDECAR_SCHEMA_VERSION` | 2 | rename contract constant | `app.rename`; high risk because rename apply/service evidence is involved. |
| `SCHEDULE_DAY_NAMES` | 2 | schedule domain constant | `app.schedule`; low risk and targeted by this sub-phase. |
| `RERUN_CSV_COLUMNS` | 1 | audit export constant | `app.audit`; low-to-medium risk. |
| `AUDIO_PASSTHROUGH_PROFILE_NAMES` | 1 | audio/config policy constant | `app.config` or audio policy contract; high risk. |
| `LOG_LEVEL_VALUES` | 1 | config metadata constant | `app.config`; low-to-medium risk. |
| `ROUTE_THRESHOLD_MODE_NAMES` | 1 | routing/config policy constant | `app.config` or routing contract; high risk. |
| `ROUTING_PROFILE_NAMES` | 1 | routing/config policy constant | `app.config` or routing contract; high risk. |
| `SIZE_GUARD_MODE_NAMES` | 1 | size guard/config policy constant | `app.config` or routing contract; high risk. |
| `CONFIG_SCHEMA_VERSION` | 1 | config contract constant | Already owned by `app.contracts.config`; medium risk because config schema is exposed. |
| `PROFILE_NAME_PATTERN` | 1 | config profile helper constant | `app.config`; low risk. |
| `FAILURE_CLEAR_MANIFEST_SCHEMA_VERSION` | 1 | failure cleanup contract constant | `app.failures`; medium risk. |
| `FOLDER_POLICY_SIDECAR_NAME` | 1 | folder policy file constant | `app.folder_policy`; medium risk. |
| `ACTIVE_JOB_SCHEMA_VERSION` | 1 | process/active-job contract constant | Desktop/app process contract; high risk. |
| `CONTROL_FLAG_SCHEMA_VERSION` | 1 | process control contract constant | Desktop/app process contract; high risk. |
| `AUDIT_PROGRESS_LAUNCH_CLEANUP_STALE_SECONDS` | 1 | process lifecycle constant | `app.processes`; high risk. |
| `CONTROL_FLAG_STALE_AFTER_SECONDS` | 1 | process lifecycle constant | `app.processes`; high risk. |
| `PIPELINE_PROGRESS_LAUNCH_CLEANUP_STALE_SECONDS` | 1 | process lifecycle constant | `app.processes`; high risk. |
| `PROCESS_LAUNCH_READY_CHECK_SECONDS` | 1 | process lifecycle constant | `app.processes`; high risk. |
| `PROCESS_LAUNCH_ERROR_TAIL_LINES` | 1 | process log constant | `app.processes`; medium risk. |
| `RENAME_MOVIE_FILTER_OPTION_KEYS` | 1 | rename policy constant | `app.rename`; high risk. |
| `APP_STATE_NAME` | 1 | storage/app-state constant | `app.storage` or app-state contract; high risk because settings/schedule app-state paths are involved. |

### `app.shared.protocols`

| Symbol | Count | Category | Likely owner/risk |
|---|---:|---|---|
| `RunCaptureFunc` | 3 | protocol/type | Runner/process contract; medium risk. |
| `WarningLogger` | 2 | protocol/type | `app.contracts` or owning status/storage modules; low-to-medium risk. |
| `RerunCsvExportServiceProtocol` | 1 | audit protocol | `app.audit`; low-to-medium risk. |
| `RerunMetadataServiceProtocol` | 1 | audit protocol | `app.audit`; low-to-medium risk. |
| `ConfigDocumentServiceProtocol` | 1 | config protocol | `app.config`; low-to-medium risk. |
| `ConfigSaveServiceProtocol` | 1 | config protocol | `app.config`; high risk because settings save is involved. |
| `PowerShellHostServiceProtocol` | 1 | paths/process protocol | `app.paths` or `app.processes`; medium risk. |
| `PathResolutionServiceProtocol` | 1 | paths protocol | `app.paths`; low-to-medium risk. |
| `QueueDryRunServiceProtocol` | 1 | queue protocol | `app.queue`; high risk. |
| `QueuePreviewServiceProtocol` | 1 | queue protocol | `app.queue`; medium risk. |
| `RenameApplyServiceProtocol` | 1 | rename protocol | `app.rename`; high risk. |
| `RenamePlannerServiceProtocol` | 1 | rename protocol | `app.rename`; high risk. |
| `RenamePreviewLoadServiceProtocol` | 1 | rename protocol | `app.rename`; medium risk. |
| `RenamePreviewScriptServiceProtocol` | 1 | rename protocol | `app.rename`; medium risk. |
| `StatusSnapshotServiceProtocol` | 1 | status protocol | `app.status`; low-to-medium risk. |
| `AppStateMigrationServiceProtocol` | 1 | storage protocol | `app.storage`; high risk because app-state migration is involved. |

## Sub-Phase Definition

```text
Sub-phase: 4A - Schedule constants
Symbols targeted: SCHEDULE_DAY_NAMES
Current import count: 2 app checker entries, plus one stale DesktopApp services import found by rg
Target owner: app.schedule.constants
Risk category: constant owned by one domain; low risk
Files expected: app/schedule/constants.py; app/schedule/grid.py; app/schedule/policy.py; app/shared/constants.py; DesktopApp/mediapipeline_desktop_app/services.py; refreshed summaries
Validation: focused schedule tests, tooling tests, dependency checker, summary/project-index checks
Stop condition: stop after moving SCHEDULE_DAY_NAMES and recording remaining shared hotspots
```

## Handoff

```text
Sub-phase: 4A - Schedule constants
Status: Complete
Files changed: app/schedule/constants.py; app/schedule/grid.py; app/schedule/policy.py; app/shared/constants.py; DesktopApp/mediapipeline_desktop_app/services.py; refreshed summaries for touched source files; Docs/architecture/DEPENDENCY_BOUNDARY_RULES.md; Docs/rewrite/dependency-refactor-phases/00_navigation_and_tracker.md; Docs/rewrite/dependency-refactor-phases/05_phase_4_shared_blast_radius.md; Docs/rewrite/dependency-refactor-phases/05a_phase_4_schedule_constants_subphase.md; Docs/generated/PROJECT_INDEX.md; Docs/generated/DEPENDENCY_GRAPH.md
Behavior changes: None intended. Schedule day-name data is identical and now owned by app.schedule.constants.
Checks run: .\DesktopApp\Runtime\Python\python.exe -m pytest DesktopApp\tests\test_service_app_schedule.py DesktopApp\tests\test_facade_schedule_policy.py; .\DesktopApp\Runtime\Python\python.exe -m pytest tests\tooling; .\DesktopApp\Runtime\Python\python.exe .\scripts\dev\check_dependency_boundaries.py --max-internal-imports 1; final summary and project-index checks listed in the owning Phase 4 handoff.
Dependency checker result: app.shared.constants imports dropped from 38 to 36; app.shared.utils remains 32; app.shared.protocols remains 19; direct app.shared remains 0; package-level cycles remain 0; the existing app.contracts.source_media* module-level cycle remains.
Known risks: DesktopApp/mediapipeline_desktop_app/services.py still imports other app.shared constants and utils for legacy compatibility surface. Higher-risk shared helpers/constants were only inventoried, not moved.
Remaining shared hotspots: app.shared.utils file helpers across write/read paths; media, audio, route, rename, process, publish, queue, and app-state constants; service protocols that should move to owning domains or app.contracts in later sub-phases.
Next: Continue Phase 4 with another deliberately scoped sub-phase; do not start Phase 5 yet.
```
