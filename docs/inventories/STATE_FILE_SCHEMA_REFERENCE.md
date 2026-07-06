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
| `confirm_source_overwrite` | `bool` | `False` | Explicit confirmation that pending drain may replace `source_path` when `server_out` resolves to the same path |
| `source_size` | `int` | `0` | Source file size in bytes |
| `source_mtime_utc` | `str` | `""` | Source file modified time at parking |
| `output_size` | `int` | — | Output file size in bytes (required, non-negative) |
| `publish_mode` | `str` | `""` | Publishing mode |
| `rerun_auto_destination_policy` | `str` | `""` | CSV rerun policy that parked the output, currently `auto_replace_clean_else_pending_review` when remaining issue evidence requires Pending Publish review |
| `rerun_auto_destination_decision` | `str` | `""` | Backend/PowerShell auto-return decision such as `pending_publish_review` |
| `rerun_auto_review_issues` | `list[dict]` | `[]` | Backend/PowerShell issue evidence that blocked clean replacement and routed the rerun output to Pending Publish/review |
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
- Auto-drain requires a trusted manifest file under `State\PendingServerPush`, a present `local_file` and sidecar payloads under the pending root, and a `server_out` under the configured output root, not under local state or pending roots. Source-root destinations are trusted only when `confirm_source_overwrite` is boolean `true` and `server_out` resolves to the same path as `source_path`; sidecars are limited to files beside that confirmed target.
- `do_not_drain` guidance in the Pending Publish table derives from `manifest_state` combined with backend safety analysis, not from a dedicated field.
- The drain operation (`POST /api/pipeline/start` with `mode: drain_pending_pushes`) consumes only trusted `parked`, `parked_recovered`, `missing_payload`, or retry-state manifests with a present parked payload. `pending_move` is repair-only after strict crash-recovery proof; `complete`, `published`, blank, unknown, legacy, malformed, or outside-root manifests are blocked.

---

## CsvRerunManifest

**Contract file**: helper-owned PowerShell/Python evidence; no formal generated JSON schema is currently emitted.
**Artifact**: `RerunManifests\*.json` under `LocalBase`, plus temporary batch config files beside the manifest when a non-PlanOnly rerun starts.
**Schema version**: no `schema_version` field is currently written; treat the manifest as runtime evidence, not standalone mutation authority.

### Common Fields

| Field | Type | Default | Notes |
|---|---|---|---|
| `batch_id` | `str` | — | Unique rerun batch identifier |
| `created_at` | `str` | — | ISO 8601 batch creation timestamp |
| `csv_path` | `str` | — | CSV input path used for this batch |
| `config_path` | `str` | — | Config or generated temp config path |
| `dry_run` / `plan_only` | `bool` | `False` | Rerun execution mode evidence |
| `pipeline_local_base` | `str` | — | LocalBase used for rerun state |
| `rerun_workspace_root` | `str` | — | Sibling rerun workspace root |
| `stage_root` / `park_root` / `output_root` | `str` | — | Batch-scoped staging and parked-output roots |
| `status` | `str` | `"planned"` | Batch status such as `planned`, `dry_run_complete`, or completed/failed runtime states |
| `stopped_at` | `str` | — | UTC timestamp when a cooperative stop completed after the current row/window |
| `stop_request_id` / `stop_requested_at` | `str` | — | Backend stop marker request evidence copied by the PowerShell rerun wrapper |
| `stop_request_marker_path` | `str` | — | Backend-owned marker path observed by the wrapper |
| `current_chunk` | `int` | — | Last processed chunk/window index when status was recorded |
| `remaining_pending_count` | `int` | — | Count of rows still marked `pending` when the manifest was last written |
| `safe_next_action` | `str` | — | Operator-facing continuation guidance for cooperative stops |
| `rows` | `list[dict]` | `[]` | Per-row plan/result evidence |

### Row Fields

Rows commonly include `source_path`, `media_kind`, `stage_mode`, `original_mode`, `return_mode`, `stage_path`, `planned_output_path`, `final_output_path`, `status`, `reason`, `source_size`, `source_mtime_utc`, `source_identity_v2`, `audit_issue_codes`, and a nested `queue_item` record when planning succeeded. Runtime/result rows may also include `verified_output_path`, `review_output_path`, `pending_publish_manifest_path`, `pending_publish_payload_path`, `published_path`, `replaced_final_hold_path`, and `updated_at`. Scoped CSVs written by the backend may also carry `rerun_rule_id`, `rerun_rule_label`, `rerun_rule_status`, `rerun_rule_reason`, `rerun_rule_destination_behavior`, `rerun_rule_replacement_eligible`, `rerun_rule_required_confirmations`, and `rerun_rule_runtime_options`; older CSVs/manifests without these fields are classified by the backend read model for Queue display. Auto-return rows may also include `auto_destination_policy`, `auto_destination_decision`, `auto_destination_issue_count`, and `auto_destination_issues`; these are written by `Invoke-RerunCsv.ps1` only and the WebView renders them as read-only evidence.

### Queue Read Model

`GET /api/rerun/results` projects raw CSV rerun manifests into a backend-owned Queue read model:

| Field | Type | Default | Notes |
|---|---|---|---|
| `queue_state.schema_version` | `str` | — | `desktop_rerun_queue_state.v1` |
| `queue_state.row_schema_version` | `str` | — | `desktop_rerun_queue_state_row.v1` |
| `queue_state.uses_pipeline_start` | `bool` | `False` | Explicit boundary marker: CSV rerun rows are not normal `/api/pipeline/start` rows |
| `queue_state.rows[]` | `list[dict]` | `[]` | Backend-enriched rows rendered by the Queue CSV Rerun tab |
| `rows[].queue_status` / `queue_status_label` | `str` | — | Normalized operator status, such as `pending`, `active`, `blocked`, `warning`, `failed`, `stopped`, `completed`, `awaiting_review`, `pending_publish`, `replaced_returned`, or `skipped` |
| `rows[].rule_decision` | `dict` | `{}` | Backend-owned CSV rerun rule decision with `desktop_rerun_rule_decision.v1`; includes rule id, label, status, reason, destination behavior, replacement eligibility, required confirmations, runtime options, and evidence |
| `rows[].rerun_rule_id` / `rerun_rule_label` / `rerun_rule_reason` | `str` | — | Flattened display fields for Queue; examples include `legacy_pipeline_standardize`, `subtitle_remediation`, `audio_language_remediation`, `container_codec_remediation`, `bad_download_full_rerun`, `manual_review_required`, and `blocked_missing_rule_input` |
| `rows[].destination_state` | `dict` | `{}` | Backend evidence for destination mode, collision policy, pending/published/replaced paths, and auto-return decisions |
| `rows[].attempt_evidence` | `dict` | `{}` | Manifest, batch, source identity, row index, reason, and timestamp evidence for the rerun attempt |
| `rows[].available_actions` | `list[dict]` | `[]` | Backend-declared row actions such as open artifact/folder/manifest or promote review output to Pending Publish |

### Notes

- Queue/Home use the newest active CSV rerun manifest only as read-only operator evidence when no normal queue snapshot is available and an active `rerun_csv` job is present. The Queue CSV Rerun tab also reads `GET /api/rerun/results` directly so CSV rerun rows remain visible even when normal queue rows are empty.
- Row `status` and `reason` drive operator-visible state; failed, blocked, held, completed, pending, staged, and review-workspace rows should not all render as ready. Current manifests include per-row `row_index` for the original CSV row position so continuation can exclude failed duplicate-source rows.
- Queue-facing CSV rerun row statuses and rule decisions are normalized by the backend read model. The WebView filters and renders these labels but does not infer whether an output is clean enough to replace, should be pending-publish review, can be promoted, or is eligible for replacement.
- `stopped_after_current` is a terminal clean-stop status for CSV rerun v1 continuation. `/api/rerun/continue` may materialize a new pending-only scoped CSV only from this status; failed/review/completed rows are not retried automatically.
- CSV rerun start readiness is not delegated to stale manifests. `/api/rerun/preview`, `/api/launch/preflight?target=rerun`, `/api/rerun/start`, and `Invoke-RerunCsv.ps1` validate CSV rows against absolute paths, source existence, valid media extensions, and safe lifecycle modes before execution.

---

## NetworkCsvRerunBatch

**Contract file**: backend-owned JSON evidence written by `POST /api/rerun/network/start`.
**Artifact**: `State\Rerun\Network\network-rerun-*.json` under `LocalBase`.
**Schema version**: `desktop_rerun_network_batch.v1`.

| Field | Type | Default | Notes |
|---|---|---|---|
| `schema_version` | `str` | — | `desktop_rerun_network_batch.v1` |
| `batch_id` | `str` | — | Backend-generated deterministic network CSV rerun batch id |
| `status` | `str` | `claim_disabled` | Phase 3 active state blocks close-readiness while worker row claims remain disabled |
| `phase` | `str` | — | Implementation phase evidence, currently `phase_3_batch_state_without_worker_execution` |
| `created_at_utc` / `updated_at_utc` | `str` | — | UTC state timestamps |
| `command_id` | `str` | — | Backend command id recorded with command journal evidence |
| `csv_path` | `str` | — | CSV input modeled by the matching dry-run |
| `dry_run_fingerprint` | `str` | — | Backend dry-run proof required by the confirmed start route |
| `claim_provider_enabled` | `bool` | `False` | Must remain false until Phase 4 claim provider support |
| `worker_execution_enabled` | `bool` | `False` | Confirms no worker execution is enabled by Phase 3 |
| `rows_claimable` | `bool` | `False` | Confirms rows are not-yet-claimable |
| `rows[]` | `list[dict]` | `[]` | Coordinator-owned row records derived from preview rows |
| `rows[].schema_version` | `str` | — | `desktop_rerun_network_batch_row.v1` |
| `rows[].row_key` / `row_index` | `str` / mixed | — | Stable row identity from the network preview |
| `rows[].status` | `str` | — | `pending_claim_disabled`, `blocked`, or `skipped` |
| `rows[].claimable` | `bool` | `False` | Always false in Phase 3 |
| `rows[].claim_status` | `str` | `claim_disabled_until_phase_4` | Worker claim loops must not treat these rows as available |
| `rows[].source_mapping` / `output_handoff` / `destination_policy` | `dict` | `{}` | Read-only planning evidence from preview |

Notes:

- Phase 3 writes this file and strict command journal evidence only. It does not stage sources, start workers, create claims, mutate normal queue state, mutate Pending Publish, mutate Completed manifests, publish, replace final output, or touch media files.
- Active `desktop_rerun_network_batch.v1` files with status `claim_disabled`, `active`, `running`, `stopping`, `stopped_after_current`, or `paused` make backend close-readiness unsafe until a later safe stop/drain state exists.
- Existing normal network queue claim/done/release protocol remains unchanged by this artifact until Phase 4 adds additive claim-provider support.

---

## CsvRerunStopControlMarker

**Contract file**: helper-owned JSON evidence; no formal generated JSON schema is currently emitted.
**Artifact**: `State\Rerun\Control\stop_after_current.json` under `LocalBase`.
**Schema version**: `desktop_rerun_control.v1`.

| Field | Type | Default | Notes |
|---|---|---|---|
| `schema_version` | `str` | — | `desktop_rerun_control.v1` |
| `action` | `str` | — | `stop_after_current` |
| `request_id` | `str` | — | Backend-generated request identifier |
| `created_at` | `str` | — | UTC request timestamp |
| `batch_id` | `str` | — | Active rerun batch selected by backend active-job evidence |
| `manifest_path` | `str` | — | Latest active manifest path selected by backend evidence |
| `csv_path` | `str` | — | CSV path selected by backend evidence |

### Notes

- The marker is backend-owned and not part of the rerun manifest authority. PowerShell remains the only writer of rerun manifest row/status evidence.
- `Invoke-RerunCsv.ps1` ignores stale markers from older batches, different manifest/CSV paths, or marker timestamps predating the current rerun start window.

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
| `job_kind` | `str` | `"job"` | Job type: `"job"`, `"audit"`, `"rerun"`, `"rerun_csv"`, `"drain"` |
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

## SettingsStore

**Contract file**: `src/mediapipeline/core/config/settings_store.py`
**Authority artifact**: `%LOCALAPPDATA%\MediaPipelineRemuxEncodeAIO\settings.v1.json`
**Projection artifact**: `%LOCALAPPDATA%\MediaPipelineRemuxEncodeAIO\settings_projection.v1.json`
**Diagnostic mirrors**: `LocalBase\State\Config\settings.v1.json` and `LocalBase\State\Config\settings_projection.v1.json`
**Schema versions**: `desktop_settings_store.v1`, `desktop_settings_projection.v1`

### `settings.v1.json` Fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `schema_version` | `str` | Yes | Must be `"desktop_settings_store.v1"` |
| `config_schema_version` | `int` | Yes | Active desktop config contract version |
| `settings` | `dict` | Yes | Full canonical known-key settings dictionary validated through the Python config contract |
| `legacy_extras` | `dict` | Yes | Unknown imported PSD1 keys preserved for projection/recovery only; not runtime policy authority |
| `migrations_applied` | `list[str]` | Yes | Import and alias migration journal |
| `source_psd1_path` | `str` | Yes | PSD1 path used during initial or explicit import |
| `source_psd1_sha256` | `str` | Yes | SHA-256 of the source PSD1 at import/save time |
| `updated_at_utc` | `str` | Yes | ISO 8601 UTC timestamp |

### `settings_projection.v1.json` Fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `schema_version` | `str` | Yes | Must be `"desktop_settings_projection.v1"` |
| `settings_store_path` | `str` | Yes | Authoritative JSON store path |
| `settings_store_sha256` | `str` | Yes | SHA-256 of the JSON store text |
| `psd1_path` | `str` | Yes | Generated PSD1 projection path consumed by PowerShell |
| `psd1_sha256` | `str` | Yes | SHA-256 of the generated PSD1 projection text |
| `generated_at_utc` | `str` | Yes | ISO 8601 UTC timestamp |
| `config_schema_version` | `int` | Yes | Config contract version represented by the projection |
| `known_key_count` | `int` | Yes | Count of canonical settings keys in the projection |
| `legacy_extras_count` | `int` | Yes | Count of inert legacy extras preserved in the projection |

### Notes

- After `settings.v1.json` exists, the Python backend treats it as the settings authority and regenerates/verifies the PSD1 projection instead of silently importing later manual PSD1 edits.
- If the JSON authority is invalid, the backend restores the verified last-good JSON when available; otherwise settings save and launch paths fail closed.
- PowerShell still reads the PSD1 for runtime compatibility, but `MediaPipeline.ps1` validates the projection manifest hash before importing the PSD1 when a matching manifest is present.
- LocalBase mirrors are diagnostics/recovery snapshots only. They are not authoritative and should not be edited by operators or tests as runtime policy input.

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
| `ConsecutiveUnexpectedRoundFailures` | `int` | `0` | Consecutive unexpected continuous-mode round failures since the last clean round |
| `LastUnexpectedRoundFailureAt` | `str \| None` | `None` | ISO 8601 timestamp of the most recent unexpected continuous-mode round failure |
| `ContinuousRoundFailuresBlocked` | `bool` | `False` | Whether continuous mode has entered blocked probe-backoff state |
| `ConsecutiveRoundFailureBlockLimit` | `int` | `12` | Runtime threshold used when setting blocked probe-backoff evidence |
| `ConsecutiveRoundFailureProbeBackoffSeconds` | `int` | `900` | Runtime probe-backoff cadence after the failure threshold is reached |
| `PauseFlagReviewSeconds` | `int` | `1800` | Pause flag age threshold for review evidence |
| `PauseFlagBlockSeconds` | `int` | `21600` | Pause flag age threshold for blocked health evidence |
| `LastQueueScanDurationSeconds` | `float \| None` | `None` | Most recent queue discovery/snapshot duration when available |
| `LastQueueCandidateCount` | `int` | `0` | Candidate count observed during the most recent queue planning round |
| `LastQueueExecutionTruncated` | `bool` | `False` | Whether runnable queue work was capped for the current round |
| `LastQueueScanTruncated` | `bool` | `False` | Whether source scan evidence reported truncation |
| `LastQueueScanTimedOut` | `bool` | `False` | Whether source scan evidence reported a timeout |

### Notes

- `current_stage_percent` is `None` for stages that do not report progress (e.g., container analysis).
- `pause_requested` and `stop_requested` reflect frontend-issued control flags; the pipeline reads them and may not stop immediately.
- Long-run reliability fields are read-only health evidence. They do not authorize frontend mutation, pending-publish drain, queue rewrites, or runtime flag cleanup.
- Staleness is detected by comparing `last_update` to wall clock time. The Live page surfaces a stale-progress warning if `last_update` is older than the configured threshold.

---

## LocalWorkerHeartbeat

**Contract file**: `ops/pipeline/engine/process/worker_result.ps1`
**Artifact**: `State\Workers\slot-<n>\worker_heartbeat.json`
**Schema version**: `local_worker_heartbeat.v1`
**Authority**: Worker-liveness evidence only. Worker claims and parent scheduler state remain authoritative for claim/release behavior.

### Fields

| Field | Type | Default | Notes |
|---|---|---|---|
| `schema_version` | `str` | — | `"local_worker_heartbeat.v1"` |
| `worker_slot_id` | `int` | `0` | Local worker slot id |
| `worker_run_id` | `str` | `""` | Parent pipeline run id |
| `worker_claim_id` | `str` | `""` | Claim id assigned by the parent scheduler |
| `source_path` | `str` | `""` | Claimed source path |
| `stage` | `str` | `""` | Worker child stage at heartbeat write time |
| `status` | `str` | `""` | Worker child status text |
| `current_file` | `str` | `""` | Current file display/name evidence |
| `current_file_path` | `str` | `""` | Current file path evidence |
| `current_queue_phase` | `str` | `""` | Current queue phase evidence |
| `current_stage_started_at` | `str \| None` | `None` | ISO 8601 stage-start evidence when available |
| `progress_file` | `str` | `""` | Child progress file path |
| `final` | `bool` | `False` | True for terminal heartbeat writes |
| `updated_at` | `str` | — | ISO 8601 UTC timestamp |

### Notes

- The parent scheduler may reclaim a worker slot when heartbeat evidence is missing or stale beyond the configured grace threshold.
- A stale heartbeat does not prove source mutation or publish safety. It only supports fail-safe worker-slot release and health reporting.

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

**Contract file**: `src/mediapipeline/core/storage/db.py`
**Artifact**: `State\mediapipeline_state.sqlite3`
**Schema version**: `2`
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
| `mirror_health` | Mirror write failure and maintenance evidence | `name` | Bounded key/value health rows for observability only. |

### Common Mirror Columns

| Field | Type | Notes |
|---|---|---|
| `recorded_at` | `str` | UTC ISO 8601 timestamp when the mirror write occurred |
| `payload_hash` | `str` | SHA-256 of the strict JSON payload |
| `payload_json` | `str` | Strict JSON copy of the mirrored payload |

### Notes

- `State\mediapipeline_state.sqlite3` is not a Diagnostics open target and is not used to drive WebView command history, Queue scope, Completed acceptance, Pending Publish drain, or recovery decisions.
- The mirror may be missing rows after permission errors, DB lock contention, or disabled/missing state roots. In those cases inspect the authoritative JSON/state artifact.
- Opportunistic maintenance writes `State\state_db_maintenance.json` using schema version `state_db_maintenance_marker.v1`; this marker records last maintenance status, trigger reason, DB/WAL/SHM sizes, and any best-effort error. It is health evidence only.
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
