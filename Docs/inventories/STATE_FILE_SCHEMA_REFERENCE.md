# State File Schema Reference

Date: 2026-06-02

Schema-level documentation for runtime state contracts in MediaPipelineRemuxEncodeAIO. Each section gives the schema version, field names with types/defaults, valid enum values, and the artifact that holds the data. Primary dataclass contracts live under `src/mediapipeline/desktop/contracts/`; focused helper contracts are called out by file.

Most contracts are Python dataclasses. All timestamps use ISO 8601 strings. Schema versions are validated at deserialization where the contract exposes a typed loader; helper-owned state files document their validation notes in their section.

---

## CompletedJob

**Contract file**: `src/mediapipeline/desktop/contracts/completed_job.py`
**Artifact**: `State\Completed\completed_jobs.jsonl` — one JSON object per line, appended per completed job
**Supported schema versions**: `completed_job.v1`, `pipeline_sidecar.v1`
**Also written to**: `.pipeline.json` sidecar (same schema, `pipeline_sidecar.v1`)

### Fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `schema_version` | `str` | Yes | `"completed_job.v1"` or `"pipeline_sidecar.v1"` |
| `product_version` | `str` | Yes | Product version at completion time |
| `pipeline_version` | `str` | Yes | Pipeline version identifier |
| `created_at` | `str` | Yes | ISO 8601 — when the job record was first created |
| `encoded_at` | `str` | Yes | ISO 8601 — when encoding/remux completed |
| `logged_at` | `str` | Yes | ISO 8601 — when the record was written to the manifest |
| `job_id` | `str` | Yes | Unique job identifier (UUID or equivalent) |
| `correlation_id` | `str` | Yes | Correlation ID for tracing across log artifacts |
| `route` | `str` | Yes | Route decision: `"remux"` or `"encode"` |
| `output_file` | `str` | Yes | Final output filename (basename only) |
| `output_path` | `str` | Yes | Final output directory path |
| `source_path` | `str` | Yes | Original source file path |
| `source_identity_v2` | `str` | Yes | Content hash of source file |

### Notes

- `route` determines whether FFmpeg performed a container copy (remux) or a full transcode (encode). This field drives route-agreement checks in the Completed table.
- `source_identity_v2` is used for deduplication and for cross-referencing between Completed and Pending Publish manifests.
- The Completed Jobs Manifest is append-only. Individual records are never updated in-place.

---

## PendingPushManifest

**Contract file**: `src/mediapipeline/desktop/contracts/pending_publish.py`
**Artifact**: `State\PendingServerPush\*.manifest.json` — one JSON object per parked output
**Schema version**: `pending_push_manifest.v1`

### Fields

| Field | Type | Default | Notes |
|---|---|---|---|
| `schema_version` | `str` | — | `"pending_push_manifest.v1"` (required) |
| `parked_at` | `str` | `""` | ISO 8601 — when the output was parked |
| `product_version` | `str` | `""` | Product version when available |
| `pipeline_version` | `str` | — | Pipeline version (required) |
| `publish_transaction_id` | `str` | — | Unique transaction ID per parked output (required) |
| `manifest_state` | `str` | — | Current state (required; see valid states below) |
| `local_file` | `str` | — | Local staging file path (required) |
| `original_local_file` | `str` | — | Original local file path before parking |
| `parked_file` | `str` | — | Parked/temporary file path in `State/PendingServerPush` |
| `server_out` | `str` | — | Destination server output path (required, non-empty) |
| `route` | `str` | — | Processing route (`"remux"` or `"encode"`) (required, non-empty) |
| `route_reason_code` | `str` | `""` | Route determination code |
| `route_reason` | `str` | `""` | Route determination reason text |
| `media_type` | `str` | `""` | Destination media kind (`"movie"` or `"tv"` when known) |
| `source_identity` | `str` | `""` | Legacy source identity (v1 compat) |
| `source_identity_v2` | `str` | — | Content hash of source file (required, non-empty) |
| `source_identity_v2_algorithm` | `str` | — | Hash algorithm name (required, non-empty) |
| `source_path` | `str` | — | Original source file path (required, non-empty) |
| `source_size` | `int` | `0` | Source file size in bytes |
| `source_mtime_utc` | `str` | `""` | Source file modified time at parking |
| `output_size` | `int` | — | Output file size in bytes (required, non-negative) |
| `publish_mode` | `str` | `""` | Publishing mode |
| `sidecar_files` | `list` | — | Associated sidecar file list (required; empty list allowed) |
| `tx3g_srt_tracks` | `list` | — | TX3G SRT sidecar evidence carried into drain (required; empty list allowed) |
| `tx3g_srt_failures` | `list` | — | TX3G SRT publish/conversion failures (required; empty list allowed) |
| `bdpgs_srt_failures` | `list` | — | BDPGS SRT conversion/OCR failures (required; empty list allowed) |
| `vobsub_srt_failures` | `list` | — | VobSub SRT conversion/OCR failures (required; empty list allowed) |
| `tx3g_embedded_srt_tracks` | `list` | — | Embedded TX3G track records for completed sidecar evidence (required; empty list allowed) |
| `bdpgs_embedded_srt_tracks` | `list` | — | Embedded BDPGS track records for completed sidecar evidence (required; empty list allowed) |
| `vobsub_embedded_srt_tracks` | `list` | — | Embedded VobSub track records for completed sidecar evidence (required; empty list allowed) |
| `tx3g_srt_conversion_enabled` | `bool` | `False` | TX3G subtitle conversion flag |
| `tx3g_external_srt_sidecars_enabled` | `bool` | `False` | External SRT sidecar support flag |
| `drop_tx3g_after_conversion` | `bool` | `False` | Drop original TX3G after conversion |
| `bdpgs_srt_conversion_enabled` | `bool` | `False` | BDPGS subtitle conversion flag |
| `drop_bdpgs_after_conversion` | `bool` | `False` | Drop original BDPGS after conversion |
| `vobsub_srt_conversion_enabled` | `bool` | `False` | VobSub subtitle conversion flag |
| `drop_vobsub_after_conversion` | `bool` | `False` | Drop original VobSub after conversion |

### Valid `manifest_state` Values

| State | Meaning |
|---|---|
| `pending_move` | Queued for move to destination; not yet attempted |
| `parked` | Parked due to destination unavailability or operator deferral |
| `parked_recovered` | Previously failed; re-parked after recovery |
| `missing_payload` | Manifest exists but local/parked file is absent |
| `retry_copy_failed` | Retry copy attempt failed |
| `retry_reveal_failed` | Retry reveal/rename step failed |
| `retry_sidecar_file_failed` | Retry sidecar file write failed |
| `retry_sidecar_failed` | Retry sidecar step failed |
| `complete` | Successfully moved to destination |
| `published` | Confirmed delivered to server destination |

### Notes

- The Pending Publish Manifest is evidence for parked outputs, not standalone mutation authority. The WebView Pending Publish page reads this via `GET /api/pending-publish`.
- Current manifests must use `schema_version = "pending_push_manifest.v1"` and carry non-empty `pipeline_version`, `publish_transaction_id`, `manifest_state`, `local_file`, `server_out`, `route`, `source_identity_v2`, `source_identity_v2_algorithm`, and `source_path`, plus non-negative `output_size` and the required sidecar/subtitle arrays. Legacy manifests remain scan-visible for operator review but are not auto-drainable or auto-repairable.
- Auto-drain requires a trusted manifest file under `State\PendingServerPush`, a present `local_file` and sidecar payloads under the pending root, and a `server_out` under the configured output root, not under source, local state, or pending roots.
- `do_not_drain` guidance in the Pending Publish table derives from `manifest_state` combined with backend safety analysis, not from a dedicated field.
- The drain operation (`POST /api/pipeline/start` with `mode: drain_pending_pushes`) consumes only trusted `parked`, `parked_recovered`, `missing_payload`, or retry-state manifests with a present parked payload. `pending_move` is repair-only after strict crash-recovery proof; `complete`, `published`, blank, unknown, legacy, malformed, or outside-root manifests are blocked.

---

## ActiveJobRecord

**Contract file**: `src/mediapipeline/desktop/contracts/active_job.py`
**Artifact**: Active jobs state folder — one JSON file per in-progress job
**Schema version**: `desktop_active_job.v1`

### Fields

| Field | Type | Default | Notes |
|---|---|---|---|
| `schema_version` | `str` | — | `"desktop_active_job.v1"` (required) |
| `launch_id` | `str` | — | Unique launch identifier (required) |
| `job_kind` | `str` | `"job"` | Job type: `"job"`, `"audit"`, `"rerun"`, `"drain"` |
| `status` | `str` | — | Current status (required; see valid statuses below) |
| `mode` | `str` | `""` | Execution mode (e.g., `"once"`, `"continuous"`) |
| `pid` | `int \| None` | `None` | OS process ID; `None` if not yet launched |
| `app_pid` | `int \| None` | `None` | Application-level process ID |
| `command_line` | `str` | `""` | Full command line string |
| `args` | `list[str]` | `[]` | Command arguments |
| `cwd` | `str` | `""` | Working directory at launch |
| `stdout_log` | `str` | `""` | Path to stdout log file |
| `stderr_log` | `str` | `""` | Path to stderr log file |
| `show_console` | `bool` | `False` | Whether a console window was shown |
| `metadata` | `dict` | `{}` | Arbitrary per-job metadata |
| `launched_at` | `str` | `""` | ISO 8601 — launch timestamp |
| `last_update` | `str` | `""` | ISO 8601 — last record update |
| `completed_at` | `str` | `""` | ISO 8601 — completion timestamp |
| `return_code` | `int \| None` | `None` | Process exit code; `None` if still running |

### Valid `status` Values

| Status | Meaning |
|---|---|
| `launching` | Process is being prepared; not yet started |
| `active` | Process is running |
| `completed` | Process exited with return code 0 |
| `failed` | Process exited with non-zero return code |
| `completed_immediate` | Completed before active-job file was polled |
| `failed_immediate` | Failed before active-job file was polled |
| `killed` | Process was terminated by a stop/kill signal |
| `orphaned` | Process record exists but no matching PID found |

### Notes

- Active job records are written and updated by the backend process service.
- The `GET /api/diagnostics/tail` and `POST /api/diagnostics/open` routes expose the active jobs folder (`active_jobs` target) read-only.
- `stdout_log` and `stderr_log` paths correspond to `last_stdout_log` and `last_stderr_log` diagnostics targets.

---

## UiPreferences

**Contract file**: `app/ui_preferences.py`
**Artifact**: `State\ui_preferences.json` — shared browser/WebView/Tauri UI customization state
**Schema version**: `desktop_ui_preferences.v1`

### Fields

| Field | Type | Default | Notes |
|---|---|---|---|
| `schema_version` | `str` | `"desktop_ui_preferences.v1"` | Identifies the UI preference payload |
| `version` | `int` | `1` | File format version |
| `updated_at` | `str` | `""` | ISO 8601 — when preferences were last written |
| `source_surface` | `str` | `""` | Short source label such as browser or Tauri |
| `source` | `str` | `"state_file"` | `state_file` for persisted data; `default` when read fallback is used |
| `storage` | `dict[str, str]` | `{}` | Allowlisted preference keys and string values |
| `warnings` | `list[str]` | `[]` | Optional validation warnings for ignored keys or values |

### Notes

- Preference keys must match `mediapipeline-*` or `mediapipeline.*` style allowlisted names enforced by `app/ui_preferences.py`.
- Corrupt, unreadable, or non-object JSON is treated as default empty UI preferences. It does not mutate settings, queue state, media policy, pending publish state, rename state, or media files.
- Writes use a temporary file, fsync, and atomic replace with bounded retries for transient Windows `PermissionError` replace failures.

---

## QueuePlanSnapshot

**Contract file**: `src/mediapipeline/desktop/contracts/queue_snapshot.py`
**Artifact**: `State\Progress\queue_snapshot.json` — rewritten each time the queue is evaluated
**Schema version**: `queue_plan_snapshot.v1`

The snapshot contains a container record and two row lists: queue display rows and excluded rows. `runnable_count` reports only items ready to process; display rows can include blocked or held rows for operator review.

### QueuePlanSnapshot (Container)

| Field | Type | Default | Notes |
|---|---|---|---|
| `schema_version` | `str` | — | `"queue_plan_snapshot.v1"` (required) |
| `produced_at` | `str` | — | ISO 8601 — when snapshot was generated (required) |
| `config_path` | `str` | `""` | Path to config file |
| `local_base` | `str` | `""` | Base local directory |
| `source_movies` | `str` | `""` | Movies source directory |
| `source_tv` | `str` | `""` | TV source directory |
| `outsource` | `str` | `""` | Scratch (Outsource) directory |
| `movie_count_total` | `int` | `0` | Total movie file count |
| `tv_count_total` | `int` | `0` | Total TV episode count |
| `priority_count` | `int` | `0` | Priority items count |
| `runnable_count` | `int` | `0` | Items ready to process |
| `excluded_count` | `int` | `0` | Excluded items count |
| `excluded_row_limit` | `int` | `0` | Max excluded rows reported |
| `excluded_rows_truncated` | `bool` | `False` | Whether excluded list was truncated |
| `rows` | `list[QueuePlanRow]` | `[]` | Runnable/queued items |
| `excluded_rows` | `list[QueuePlanExcludedRow]` | `[]` | Excluded items |

### QueuePlanRow (Individual Queued Item)

| Field | Type | Notes |
|---|---|---|
| `global_order` | `int` | Global processing order across all phases |
| `phase` | `str` | `"movie"` or `"tv"` |
| `media_kind` | `str` | Media classification code |
| `queue_index` | `int` | Position within phase queue |
| `queue_total` | `int` | Total items in phase queue |
| `is_priority` | `bool` | Priority flag |
| `source_path` | `str` | Full source path (required) |
| `root_path` | `str` | Root directory (movies or TV root) |
| `relative_path` | `str` | Path relative to root |
| `display_name` | `str` | Human-readable display name |
| `size_gb` | `float` | File size in GB |
| `route` | `str` | Route decision: `"remux"` or `"encode"` |
| `route_reason_code` | `str` | Code explaining route decision |
| `route_reason` | `str` | Human-readable route reason |
| `route_decision_trace` | `list` | Ordered route-decision evidence |
| `estimated_bitrate_mbps` | `float` | Estimated bitrate used by route policy |
| `route_size_threshold_gb` | `float` | Size threshold used by route policy |
| `route_bitrate_threshold_mbps` | `float` | Bitrate threshold used by route policy |
| `route_threshold_mode` | `str` | Threshold mode used by route policy |
| `size_over_threshold` | `bool` | Whether size crossed the configured threshold |
| `bitrate_over_threshold` | `bool` | Whether bitrate crossed the configured threshold |
| `blocked_reason_code` | `str` | Block status code (`""` if not blocked) |
| `blocked_reason` | `str` | Block reason text |
| `runtime_checks_deferred` | `bool` | Whether runtime checks were deferred |
| `runtime_check_codes` | `list` | Check result codes |
| `runtime_check_notes` | `list` | Check notes and messages |

### QueuePlanExcludedRow (Excluded Item)

| Field | Type | Notes |
|---|---|---|
| `source_order` | `int` | Original discovery order |
| `reason_code` | `str` | Exclusion code (required) |
| `reason` | `str` | Exclusion reason text |
| `phase` | `str` | Phase it would have been (`"movie"` or `"tv"`) |
| `media_kind` | `str` | Media type |
| `source_path` | `str` | Full source path (required) |
| `root_path` | `str` | Root directory |
| `relative_path` | `str` | Relative path |
| `display_name` | `str` | Display name |
| `size_gb` | `float` | File size in GB |

### Notes

- The queue snapshot is rebuilt each time a dry-run or queue evaluation is performed. It is not an append-only log.
- The `blocked_reason_code` on `QueuePlanRow` drives the blocked-row warning signals in the Queue table.
- The `route` field is a prediction at queue-plan time. The final route in the completed manifest may differ if runtime conditions change.

---

## ProgressState

**Contract file**: `src/mediapipeline/desktop/contracts/progress.py`
**Artifact**: `State\Progress\pipeline_progress.json`, polled via `GET /api/snapshot` and surfaced in the Live/Progress page
**Schema**: Not versioned as a standalone file; embedded in snapshot payload

### Fields

| Field | Type | Default | Notes |
|---|---|---|---|
| `progress_version` | `int` | — | Must be >= 1 (required) |
| `last_update` | `str` | — | ISO 8601 — most recent update (required) |
| `status` | `str` | — | Pipeline status string (required) |
| `session_started_at` | `str \| None` | `None` | ISO 8601 — session start |
| `current_file` | `str \| None` | `None` | Currently processing filename |
| `current_file_display` | `str \| None` | `None` | Display name for current file |
| `current_file_path` | `str \| None` | `None` | Full path to current file |
| `current_media_type` | `str \| None` | `None` | `"movie"` or `"tv"` |
| `current_queue_phase` | `str \| None` | `None` | Current phase |
| `current_queue_index` | `int` | `0` | Index in queue |
| `current_queue_total` | `int` | `0` | Total queue size |
| `current_route` | `str \| None` | `None` | `"remux"` or `"encode"` |
| `current_stage` | `str \| None` | `None` | Stage name (e.g., `"encode"`, `"copy"`, `"sidecar"`) |
| `current_stage_percent` | `float \| None` | `None` | Stage progress 0.0–100.0 |
| `current_item_started_at` | `str \| None` | `None` | ISO 8601 — current item start |
| `current_stage_started_at` | `str \| None` | `None` | ISO 8601 — current stage start |
| `copy_state` | `str \| None` | `None` | Copy operation state |
| `push_state` | `str \| None` | `None` | Push/publish state |
| `sidecar_state` | `str \| None` | `None` | Sidecar processing state |
| `pause_requested` | `bool` | `False` | Pause request flag |
| `stop_requested` | `bool` | `False` | Stop request flag |
| `control_requests` | `dict` | `{}` | Control request detail |
| `total_processed` | `int` | `0` | Total items processed this session |
| `encoded` | `int` | `0` | Items encoded |
| `remuxed` | `int` | `0` | Items remuxed |
| `failed` | `int` | `0` | Items failed |
| `movies` | `int` | `0` | Total movies processed |
| `tv_episodes` | `int` | `0` | Total TV episodes processed |

### Notes

- `current_stage_percent` is `None` for stages that do not report progress (e.g., container analysis).
- `pause_requested` and `stop_requested` reflect frontend-issued control flags; the pipeline reads them and may not stop immediately.
- Staleness is detected by comparing `last_update` to wall clock time. The Live page surfaces a stale-progress warning if `last_update` is older than the configured threshold.

---

## PipelineEvent

**Contract file**: `src/mediapipeline/desktop/contracts/pipeline_events.py`
**Artifact**: `State\Progress\pipeline_events.jsonl` — events written by pipeline services, surfaced via `GET /api/diagnostics` recent-events endpoint
**Schema version**: `pipeline_event.v1`

### Fields

| Field | Type | Notes |
|---|---|---|
| `schema_version` | `str` | `"pipeline_event.v1"` (required) |
| `event_id` | `str` | Unique event identifier (required) |
| `event_type` | `str` | Event type name (required) |
| `timestamp` | `str` | ISO 8601 — event time (required; `created_at` used as fallback) |
| `created_at` | `str` | ISO 8601 — creation time (fallback for timestamp) |
| `run_id` | `str` | Run/session identifier |
| `correlation_id` | `str` | Correlation ID for cross-artifact tracing |
| `job_id` | `str` | Associated job identifier |
| `product_version` | `str` | Product version |
| `pipeline_version` | `str` | Pipeline version |
| `stage` | `str` | Processing stage |
| `route` | `str` | Processing route (`"remux"` or `"encode"`) |
| `status` | `str` | Event status |
| `source_path` | `str` | Source file path |
| `data` | `dict` | Event-specific data payload |

### Notes

- `correlation_id` links events to their corresponding `CompletedJob` and `ActiveJobRecord` via the same field.
- `data` is event-type specific and not schema-validated beyond being a dict.
- Pipeline events are read-only from the WebView perspective. They are not editable or deletable through any API route.

---

## SQLiteStateMirror

**Contract file**: `app/storage/db.py`
**Artifact**: `State\mediapipeline_state.sqlite3`
**Schema version**: `1`
**Authority**: Shadow mirror only. The JSON/state artifacts above remain authoritative.

The SQLite mirror is populated opportunistically when a state root is available.
Mirror write failures are logged or swallowed by the caller so they do not change
command, stage, queue, completed-manifest, or media behavior.

### Tables

| Table | Rows mirrored | Identity / dedupe rule | Notes |
|---|---|---|---|
| `commands` | Local API command journal summaries | Append-only SQLite row id | Stores bounded, redacted command-result summaries. |
| `events` | Python stage runner events | Append-only SQLite row id | Stores request/result payload evidence for Python-owned stage boundaries. |
| `queue_snapshots` | Queue dry-run snapshot payloads | Append-only SQLite row id | Stores each promoted dry-run snapshot payload plus request id and snapshot path. |
| `completed_jobs` | Completed manifest rows read by the Completed service | `job_id` when present, otherwise payload hash | Re-reading the same manifest row is idempotent, but distinct append-only rows for the same output path are preserved. |

### Common Mirror Columns

| Field | Type | Notes |
|---|---|---|
| `recorded_at` | `str` | UTC ISO 8601 timestamp when the mirror write occurred |
| `payload_hash` | `str` | SHA-256 of the strict JSON payload |
| `payload_json` | `str` | Strict JSON copy of the mirrored payload |

### Notes

- `State\mediapipeline_state.sqlite3` is not a Diagnostics open target and is not used to drive WebView command history, Queue scope, Completed acceptance, Pending Publish drain, or recovery decisions.
- The mirror may be missing rows after permission errors, DB lock contention, or disabled/missing state roots. In those cases inspect the authoritative JSON/state artifact.
- Deleting the mirror while the backend is running is unsafe. With the backend stopped, deletion only removes diagnostic mirror history; future activity can recreate the DB.

---

## Contract Validation

All contracts are validated at read time by `test_contracts.py`. Schema version mismatches cause contract rejection, not silent coercion. Operators should not hand-edit state files outside of the documented mutation routes.

---

## See Also

- Completed/Pending failure playbook: `docs/operator/COMPLETED_PENDING_FAILURE_PLAYBOOK.md`
- Diagnostics targets (for file access): `docs/archive/completed-audits/DIAGNOSTICS_TARGET_ALLOWLIST_AUDIT.md`
- API route inventory: `docs/inventories/API_ROUTE_INVENTORY.md`
- Log artifact catalog: `docs/inventories/LOG_ARTIFACT_CATALOG.md`

