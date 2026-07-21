# State File Schema Reference

Date: 2026-07-20

Schema-level documentation for runtime state contracts in MediaPipelineRemuxEncodeAIO. Each section gives the schema version, field names with types/defaults, valid enum values, and the artifact that holds the data. Primary dataclass contracts live under `src/mediapipeline/desktop/contracts/`; focused helper contracts are called out by file.

Most contracts are Python dataclasses. All timestamps use ISO 8601 strings. Schema versions are validated at deserialization where the contract exposes a typed loader; helper-owned state files document their validation notes in their section.

---

## ScratchSourceIdentity

**Contract file**: helper-owned by `ops/pipeline/engine/storage/scratch_copy.ps1`; no generated JSON schema is emitted.
**Artifact**: `<scratch-file>.srcinfo` beside a copied scratch source.
**Schema version**: `scratch_source_identity.v2`.

| Field | Type | Required | Notes |
|---|---|---|---|
| `schema_version` | `str` | Yes | Must equal `"scratch_source_identity.v2"` |
| `hash_algorithm` | `str` | Yes | Must equal `"sha256"` (case-insensitive); no fallback algorithm is accepted |
| `source_path` | `str` | Yes | Canonical source path; Windows-equivalent case differences are accepted, while a different canonical path denies reuse |
| `source_size` | `int` | Yes | Source size observed during stable full-file hashing |
| `source_mtime_utc` | `str` | Yes | Source timestamp observed during hashing; metadata is supporting evidence and never establishes content equality |
| `source_sha256` | `str` | Yes | Exactly 64 hexadecimal characters |
| `scratch_size` | `int` | Yes | Landed scratch size observed during stable full-file hashing |
| `scratch_sha256` | `str` | Yes | Exactly 64 hexadecimal characters |
| `verified_at_utc` | `str` | Yes | UTC time when the sidecar was atomically promoted after copy verification |

### Notes

- A sidecar is evidence for scratch reuse, not mutation or processing authority. Before reuse, the pipeline re-hashes the current source, the current scratch file, and the source again. Source observations must remain stable; current source and scratch sizes and SHA-256 values must match each other and the saved evidence.
- Missing, malformed, incomplete, legacy, or unsupported evidence never authorizes reuse. A mismatch enters the guarded scratch replacement/re-copy path; if replacement or identity proof is unsafe or unavailable, the copy fails closed.
- The evidence is written atomically only after the copied scratch bytes match a stable pre/post source identity. Processing does not start when evidence cannot be written, and a restart revalidates content rather than trusting the sidecar alone.

---

## PriorityQueueExport

**Contract file**: `src/mediapipeline/core/queue/priority_export.py`.
**Artifact**: `State\QueueExports\Priority\priority-export-<timestamp>-<id>.json`; `latest.json` is an atomic copy of the latest ready export.
**Schema version**: `priority_queue_export.v1`.

| Field | Type | Required | Notes |
|---|---|---|---|
| `schema_version` | `str` | Yes | Must equal `priority_queue_export.v1` |
| `status` / `ready` | `str` / `bool` | Yes | Launch accepts only `status=ready` and `ready=true` |
| `export_id` / `created_at` | `str` | Yes | Backend-generated identifier and UTC creation time |
| `count` | `int` | Yes | Positive and exactly equal to `accepted_rows` length |
| `queue_plan_fingerprint_schema` / `queue_plan_fingerprint` | `str` | Yes | Fingerprint of the filtered PowerShell `PriorityOnly` plan; runtime must rebuild and match it before dispatch |
| `queue_input_fingerprint_schema` / `queue_input_fingerprint` | `str` | Yes | Covers config, priority manifest, queue strategy, and file overrides; any change makes the export stale |
| `accepted_run_rows_fingerprint_schema` / `accepted_run_rows_fingerprint` | `str` | Yes | Content identity for the uncapped accepted membership |
| `accepted_rows` | `list[dict]` | Yes | Backend-only Run Monitor membership; omitted from public GET/POST responses |

### Notes

- The export contains only runnable effective-High entries: explicit manifest `high` or an existing filename/folder priority marker not overridden by an explicit Normal, Low, or Hold setting.
- Export creation and launch do not clear or rewrite priority settings. Empty, missing, malformed, stale, changed, or membership-mismatched exports fail closed and never fall back to the normal backend queue.
- `queue_scope=priority_export` is valid only for Run Once without Single File. The browser submits the export ID, never row membership.

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
| `audio_decisions` | `list[dict]` | `[]` | Terminal per-source-track audio policy evidence captured at park time. Current records use stable track identity/source stream index so the Run Monitor can reconcile exact tracks without guessing; absence in an older manifest remains unknown. |
| `subtitle_decisions` | `list[dict]` | `[]` | Terminal per-source-track subtitle policy evidence captured at park time. Current records carry stable `track_id` values; older records without exact identity remain terminally unknown rather than being matched by language, filename, or ordinal similarity. |
| `subtitle_conversion_results` | `list[dict]` | `[]` | Correlated conversion/OCR outcome evidence, including output or review/failure detail when produced by the subtitle tools. |
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
- `audio_decisions`, `subtitle_decisions`, and `subtitle_conversion_results` provide track-level terminal proof for new manifests. They are additive for backward compatibility: their absence never permits the Run Monitor or WebView to infer a decision from route text, filenames, neighboring tracks, or runtime history.
- Current manifests must use `schema_version = "pending_push_manifest.v1"` and carry non-empty `pipeline_version`, `publish_transaction_id`, `manifest_state`, `local_file`, `server_out`, `route`, `source_identity_v2`, `source_identity_v2_algorithm`, and `source_path`, plus non-negative `output_size` and the required sidecar/subtitle arrays. Legacy manifests remain scan-visible for operator review but are not auto-drainable or auto-repairable.
- Auto-drain requires a trusted manifest file under `State\PendingServerPush`, a present `local_file` and sidecar payloads under the pending root, and a `server_out` under the configured output root, not under local state or pending roots. Source-root destinations are trusted only when `confirm_source_overwrite` is boolean `true` and `server_out` resolves to the same path as `source_path`; sidecars are limited to files beside that confirmed target.
- `do_not_drain` guidance in the Pending Publish table derives from `manifest_state` combined with backend safety analysis, not from a dedicated field.
- The drain operation (`POST /api/pipeline/start` with `mode: drain_pending_pushes`) consumes only trusted `parked`, `parked_recovered`, `missing_payload`, or retry-state manifests with a present parked payload. `pending_move` is repair-only after strict crash-recovery proof; `complete`, `published`, blank, unknown, legacy, malformed, or outside-root manifests are blocked.

---

## CsvRerunLocalEnrollment

**Contract file**: `src/mediapipeline/core/processes/rerun_lifecycle.py`.
**Artifact**: `State\Rerun\Local\<batch_id>.json` under `LocalBase`.
**Schema version**: `desktop_rerun_local_enrollment.v1`.

The backend writes this authority before spawning `Invoke-RerunCsv.ps1`. It
closes the acceptance-to-manifest evidence gap while the PowerShell execution
manifest is not yet available. PowerShell references this file but does not
mutate it.

| Field | Type | Default | Notes |
|---|---|---|---|
| `command_id` / `launch_id` / `batch_id` | `str` | — | Stable correlation chain shared with command journal, ActiveJobs, launch logs, and execution manifest |
| `enrollment_path` / `manifest_path` | `str` | — | Backend enrollment path and expected PowerShell execution-manifest path |
| `csv_path` / `source_csv_path` | `str` | — | Effective scoped CSV and original operator-selected CSV |
| `queue_source` | `str` | `csv_rerun` | Dedicated-rerun read-model source; the batch is not inserted into the normal queue |
| `uses_pipeline_start` / `inserted_into_normal_queue` | `bool` | `False` | Explicit ownership boundary |
| `status` / `lifecycle_state` / `current_phase` | `str` | `accepted` | Durable lifecycle state such as `accepted`, `process_spawned`, `spawn_transition_ambiguous`, or `failed_before_manifest`. `spawn_transition_ambiguous` is nonterminal and duplicate-blocking until correlated child-exit proof exists |
| `created_at` / `accepted_at` / `last_transition_at` / `completed_at` | `str` | — | UTC lifecycle timestamps when applicable |
| `pid` / `return_code` | `int` | — | Child-process evidence when available |
| `process_exit_verified` | `bool` | — | Literal `true` means correlated child exit was conclusively proved. Missing or `false` evidence never authorizes retry-generation supersession |
| `duplicate_launch_blocked` | `bool` | — | `true` keeps an enrollment nonterminal and blocks duplicate work while child/tree cleanup is unknown. Only literal `false` paired with `process_exit_verified: true` can make a terminal premanifest failure supersedable |
| `timeline[]` | `list[dict]` | `[]` | Ordered lifecycle evidence with state, timestamp, and stable reason code |
| `evidence_links` | `dict` | `{}` | ActiveJobs, stdout/stderr log, expected manifest, and command evidence links |
| `rows[]` | `list[dict]` | `[]` | Accepted CSV rows retained even if the wrapper exits before its execution manifest is complete |
| `rows[].source_content_sha256` | `str` | — | Additive full-file SHA-256 proof used for identity-safe recovery; sampled `source_identity_v2` remains separately labeled and is not treated as a full-content hash |
| `recovery_request_id` / `recovery_key` / `recovery_scope` | `str` | — | Exactly-once recovery provenance. Replaying the same request is idempotent; `recovery_key` identifies the selected generation within the logical recovery scope |
| `recovery_root_key` / `recovery_generation` | mixed | — | Stable logical recovery namespace plus positive generation number. The namespace binds the correlated source batch, recovery scope, and canonicalized row-selector set. Selector paths use Windows-equivalent case, separator, and dot-segment normalization before sorting/hashing, so ordering or equivalent spellings cannot mint duplicate work |
| `recovery_supersedes_enrollment_path` / `recovery_supersedes_recovery_key` / `recovery_supersedes_batch_id` | `str` | — | Exact prior failed-before-manifest generation superseded by this generation; empty for the first generation or when no prior generation is safely supersedable |
| `recovery_source_command_id` / `recovery_source_launch_id` / `recovery_source_batch_id` | `str` | — | Immutable logical execution identity from which recovery was authorized |
| `recovery_source_manifest_path` / `recovery_source_manifest_key` | `str` | — | Exact execution-manifest evidence path and compatibility key; neither defines the canonical logical recovery namespace |
| `recovery_row_selectors[]` | `list[dict]` | `[]` | Canonically ordered durable row selectors used in the recovery namespace and identity-safe scoped CSV |

### Notes

- The enrollment is durable acceptance/process evidence, not media-policy or
  destination authority. The PowerShell manifest owns planning, staging,
  processing, destination, and terminal row evidence.
- `GET /api/rerun/results` joins enrollment and execution evidence by
  `batch_id`, preferring the execution manifest for later-stage row state while
  retaining the shared correlation chain.
- A child exit before an execution manifest exists becomes
  `failed_before_manifest` only with conclusive exit proof. Unknown child state
  or degraded tree cleanup remains `spawn_transition_ambiguous`, retains
  duplicate blocking, and requires reconciliation.
- Backend startup and waiting-row recovery require exact command, launch,
  batch, enrollment-path, and manifest-path correlation. For v2 manifests, the
  selected file path must equal the path declared by the writer; copied or
  renamed manifests are not authoritative recovery evidence.
- A later recovery generation may supersede only a prior
  `failed_before_manifest` enrollment with literal `process_exit_verified:
  true`, literal `duplicate_launch_blocked: false`, and an expected manifest
  path proved absent. Files, directories, broken links/reparse points, and
  metadata-access failures remain fail-closed.

---

## CsvRerunManifest

**Contract file**: helper-owned PowerShell/Python evidence; no formal generated JSON schema is currently emitted.
**Artifact**: `RerunManifests\*.json` under `LocalBase`, plus temporary batch config files beside the manifest when a non-PlanOnly rerun starts.
**Schema version**: `rerun_batch_manifest.v2`; treat the manifest as runtime evidence, not standalone mutation authority.

### Common Fields

| Field | Type | Default | Notes |
|---|---|---|---|
| `batch_id` | `str` | — | Unique rerun batch identifier |
| `command_id` / `launch_id` | `str` | — | Required stable backend/ActiveJobs/log correlation identifiers; resume preserves exact values and rejects blank/mismatched replacements |
| `enrollment_path` | `str` | — | Read-only reference to the backend-owned local enrollment record |
| `created_at` | `str` | — | ISO 8601 batch creation timestamp |
| `started_at` / `last_transition_at` / `completed_at` | `str` | — | Execution lifecycle timestamps when applicable |
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
| `current_phase` / `current_row_index` | mixed | — | Current backend-authored lifecycle phase and CSV row |
| `timeline[]` | `list[dict]` | `[]` | Strictly increasing lifecycle transitions with what/why/when/next evidence |
| `rows` | `list[dict]` | `[]` | Per-row plan/result evidence |
| `write_sequence` / `transition_sequence` | `int` | `0` | Per-manifest compare-and-swap and ordered lifecycle evidence; stale, skipped/future, cross-batch, and terminal-regressing writes are rejected |

### Row Fields

Rows commonly include `source_path`, `media_kind`, `stage_mode`, `original_mode`, `return_mode`, `stage_path`, `planned_output_path`, `final_output_path`, `status`, `lifecycle_state`, `reason`, `reason_code`, `source_size`, `source_mtime_utc`, sampled `source_identity_v2`, additive `source_content_sha256` / `planned_source_content_sha256` / `staged_source_content_sha256`, `audit_issue_codes`, and a nested `queue_item` record when planning succeeded. Recoverable rows also retain `attempt_count`, `max_attempts`, `stage_attempt_id`, `stage_attempt_count`, `nested_launch_id`, `nested_launch_count`, `rerun_chunk_index`, first/last failure evidence, `next_retry_at`, operator guidance, and a per-row `timeline`. Runtime/result rows may also include `verified_output_path`, `review_output_path`, Pending Publish/final-placement evidence, and `updated_at`. Scoped CSVs written by the backend preserve the strong content hash and may also carry backend rerun-rule columns. Legacy offline rows without a persisted strong hash fail closed to review rather than establishing a new identity baseline after reconnect.

### Queue Read Model

`GET /api/rerun/results` projects raw CSV rerun manifests and Network CSV rerun batch manifests into a backend-owned Queue read model:

| Field | Type | Default | Notes |
|---|---|---|---|
| `queue_state.schema_version` | `str` | — | `desktop_rerun_queue_state.v1` |
| `queue_state.row_schema_version` | `str` | — | `desktop_rerun_queue_state_row.v1` |
| `history_window` | `dict` | `{}` | Bounded response metadata: requested limit, local/Network loaded and discovered candidate counts, truncation flags, skipped counts, and bounded per-file scan warnings. One unreadable manifest does not suppress readable history. |
| `queue_state.uses_pipeline_start` | `bool` | `False` | Explicit boundary marker: CSV rerun rows are not normal `/api/pipeline/start` rows |
| `queue_state.current_local` | `dict` | empty current summary | Backend-selected local batch for the current table. Selection order is exact identity-matched live process, newest recovery-actionable batch, newest nonterminal review batch, then none. Terminal-only history is never current. |
| `queue_state.current_network` | `dict` | empty current summary | Backend-selected Network batch. `activity_state=active` requires an exact fresh claim from persisted `coordinator_inflight.json`; an open manifest without that proof is `open_unverified`, not active. |
| `queue_state.rows[]` | `list[dict]` | `[]` | Backend-enriched rows from the bounded recent local and Network history window. The WebView current table uses only `current_local.rows` and `current_network.rows`. |
| `rows[].queue_source` / `queue_kind` | `str` | — | Distinguishes local CSV rerun rows from Network CSV rerun reducer rows; network rows use `network_csv_rerun` and `network_csv_rerun_row` |
| `rows[].queue_status` / `queue_status_label` | `str` | — | Normalized operator status, such as `pending`, `active`, `pending_reduction`, `blocked`, `warning`, `failed`, `stopped`, `completed`, `awaiting_review`, `pending_publish`, `replaced_returned`, or `skipped`; Network CSV rerun destination policy application is rendered as `active`, and destination-policy failures render as `failed` |
| `rows[].rule_decision` | `dict` | `{}` | Backend-owned CSV rerun rule decision with `desktop_rerun_rule_decision.v1`; includes rule id, label, status, reason, destination behavior, replacement eligibility, required confirmations, runtime options, and evidence |
| `rows[].rerun_rule_id` / `rerun_rule_label` / `rerun_rule_reason` | `str` | — | Flattened display fields for Queue; examples include `legacy_pipeline_standardize`, `subtitle_remediation`, `audio_language_remediation`, `container_codec_remediation`, `bad_download_full_rerun`, `manual_review_required`, and `blocked_missing_rule_input` |
| `rows[].destination_state` | `dict` | `{}` | Backend evidence for destination mode, collision policy, pending/published/replaced paths, auto-return decisions, and Network CSV rerun destination-policy result/action/status |
| `rows[].attempt_evidence` | `dict` | `{}` | Manifest, batch, source identity, row index, reason, and timestamp evidence for the rerun attempt |
| `rows[].network_reducer_result` / `network_worker_result` | `dict` | `{}` | Read-only Network CSV rerun reducer and worker evidence when projected from `NetworkCsvRerunBatch` |
| `rows[].network_destination_policy_result` | `dict` | `{}` | Read-only Network CSV rerun Phase 6 destination-policy evidence, including action, terminal status, review output, Pending Publish manifest/payload, published path, hashes, transaction data, or failure reason |
| `rows[].network_output_artifact` | `str` | `""` | Verified handoff output path for network reducer rows, when present |
| `rows[].lifecycle_state` / `reason_code` / `lifecycle_evidence` | mixed | — | Backend-authored what/why/when/next state, stable reason, attempts, error, timestamps, and evidence links; the WebView does not infer recovery safety |
| `rows[].available_actions` | `list[dict]` | `[]` | Backend-declared row actions such as open artifact/folder/manifest, promote review output, continue/retry an exact eligible scope, or request an exhausted Network-row retry |
| `counts` | `dict` | `{}` | Disjoint local and Network lifecycle totals for executable, blocked, waiting, retrying, staged, active, completed, failed, review, and pending-publish operator buckets |

### Notes

- `GET /api/queue` and the Main Queue table contain normal pipeline rows only. Dedicated local and Network CSV rerun rows, including durable waiting/retry evidence after a wrapper exit or backend restart, remain under `GET /api/rerun/results` and the Queue CSV Rerun tab.
- Network CSV rerun rows are projected from `State\Rerun\Network\*.json` as read-only Queue evidence with `network_manifest_root`, `network_manifests`, `network_row_count`, and `queue_state.contains_network_csv_rerun`. Phase 5 exposes reducer status and pending destination-policy evidence; Phase 6 may expose coordinator-applied review workspace, Pending Publish, final publish, or destination-policy failure evidence after a worker done report has been reduced.
- Row `status` and `reason` drive operator-visible state; failed, blocked, held, completed, pending, staged, and review-workspace rows should not all render as ready. Current manifests include per-row `row_index` for the original CSV row position so continuation can exclude failed duplicate-source rows.
- Queue-facing CSV rerun row statuses and rule decisions are normalized by the backend read model. The WebView filters and renders these labels but does not infer whether an output is clean enough to replace, should be pending-publish review, can be promoted, or is eligible for replacement.
- `stopped_after_current` is a terminal clean-stop status for CSV rerun continuation. `/api/rerun/continue` requires a nonblank `request_id` and strict `confirm_continue=true`; it may materialize a new pending-only or identity-preserving recovery CSV only from an exact backend-qualified scope. Request provenance makes replay idempotent and blocks a different request from duplicating the same recovery launch.
- CSV rerun start readiness is not delegated to stale manifests. `/api/rerun/preview`, `/api/launch/preflight?target=rerun`, `/api/rerun/start`, and `Invoke-RerunCsv.ps1` validate absolute paths, media extensions, source health/identity, and safe lifecycle modes. A transient configured-root/access outage is retained as waiting/retry evidence rather than misreported as an empty queue or permanently missing file.
- Scratch staging requires a proved drive/UNC-share trust root and a reparse-free
  component chain through the batch path. Missing-leaf creation is
  component-wise and re-proved; dangling reparse points, metadata uncertainty,
  identity changes, or unexpected cleanup contents fail closed as boundary or
  cleanup-ambiguity evidence. A verified full-hash scratch copy may continue
  after the source disappears, while source-mutating Robocopy modes remain
  forbidden.

---

## NetworkCsvRerunBatch

**Contract file**: backend-owned JSON evidence written by `POST /api/rerun/network/start`.
**Artifact**: `State\Rerun\Network\network-rerun-*.json` under `LocalBase`.
**Schema version**: `desktop_rerun_network_batch.v1`.

| Field | Type | Default | Notes |
|---|---|---|---|
| `schema_version` | `str` | — | `desktop_rerun_network_batch.v1` |
| `batch_id` | `str` | — | Backend-generated deterministic network CSV rerun batch id |
| `status` | `str` | `active` | Aggregate batch state such as `active`, `retry_exhausted`, `review_required`, `failed`, or `complete`; active work blocks close-readiness |
| `phase` | `str` | — | Confirmed-start phase evidence; row-level reducer evidence carries `reducer_phase=phase_5_coordinator_result_reducer`, and row-level destination evidence carries `phase=phase_6_destination_policy_integration` |
| `created_at_utc` / `updated_at_utc` | `str` | — | UTC state timestamps |
| `command_id` | `str` | — | Backend command id recorded with command journal evidence |
| `csv_path` | `str` | — | CSV input modeled by the matching dry-run |
| `dry_run_fingerprint` | `str` | — | Backend dry-run proof required by the confirmed start route |
| `claim_provider_enabled` | `bool` | `True` | Coordinator may expose claimable rows as additive `csv_rerun_row` worker claims |
| `worker_execution_enabled` | `bool` | `True` | Workers may execute one claimed source into its planned handoff folder |
| `rows_claimable` | `bool` | `True` when any row is pending claim | Confirms at least one row may be claimed by the coordinator provider |
| `output_handoff` | `dict` | `{}` | Validated `NetworkRerunHandoffRoot` evidence, including local-vs-UNC compatibility and coordinator cleanup ownership |
| `handoff_probe` | `dict` | `{}` | Confirmed-start coordinator create/write/read/list/delete probe evidence for the configured handoff root |
| `rows[]` | `list[dict]` | `[]` | Coordinator-owned row records derived from preview rows |
| `rows[].schema_version` | `str` | — | `desktop_rerun_network_batch_row.v1` |
| `rows[].row_key` / `row_index` | `str` / mixed | — | Stable row identity from the network preview |
| `rows[].status` | `str` | — | Includes `pending_claim`, `claimed`, `retry_scheduled`, `retry_exhausted`, `review_required`, worker reduction states, destination-policy states, `blocked`, or `skipped` |
| `rows[].claimable` | `bool` | `True` only for pending start-ready rows | Coordinator claim provider may hand the row to one worker when true |
| `rows[].claim_status` | `str` | `pending_claim` | Worker claim lifecycle evidence such as `pending_claim`, `claimed`, `released`, or `done_reported` |
| `rows[].planned_output_path` | `str` | `""` | Planned per-row handoff folder path under `<NetworkRerunHandoffRoot>/<batch_id>/<row_key>/` |
| `rows[].source_mapping` / `output_handoff` / `destination_policy` | `dict` | `{}` | Read-only planning evidence from preview, with actual per-row handoff paths materialized during confirmed start |
| `rows[].active_claim` | `dict` | absent | Current worker claim identity while a row is in flight |
| `rows[].worker_result` | `dict` | absent | Phase 5 worker result snapshot copied from the done request and optional worker artifact; `schema_version=desktop_rerun_network_worker_result_snapshot.v1` |
| `rows[].reducer_result` | `dict` | absent | Phase 5 coordinator result reduction; `schema_version=desktop_rerun_network_result_reduction.v1`, with classification, retryability, output evidence, identity checks, and destination-policy deferral |
| `rows[].destination_policy_result` | `dict` | absent | Phase 6 coordinator destination-policy result; `schema_version=desktop_rerun_network_destination_policy_result.v1`, with action, terminal status, source/output/final path evidence, Pending Publish manifest/payload paths, final publish transaction evidence, or failure details |
| `rows[].verified_output_path` | `str` | `""` | Handoff output accepted by the reducer as present and under the planned row handoff folder |
| `rows[].pending_publish_manifest_path` / `pending_publish_payload_path` | `str` | `""` | Manifest-backed Pending Publish evidence when coordinator policy parks a network rerun output |
| `rows[].published_path` / `server_out` / `review_output_path` | `str` | `""` | Coordinator-authored final publish, requested server output, or handoff review workspace evidence |
| `rows[].duplicate_done_count` / `late_done_count` | `int` | `0` | Idempotency counters for duplicate and late done reports |
| `rows[].reducer_events[]` / `late_worker_results[]` | `list[dict]` | `[]` | Bounded evidence history for duplicate, late, and terminal-after-release reports |
| `rows[].attempt_count` / `retry_count` / `retry_limit` | `int` | `0` | Durable bounded-attempt evidence; the retry limit reuses the coordinator retry configuration |
| `rows[].retry_after_seconds` / `next_retry_at_utc` | mixed | — | Exponential bounded backoff evidence for a retry-scheduled row |
| `rows[].first_failure` / `last_failure` / `retry_history[]` | mixed | — | First/last source or worker failure and bounded retry history with stable reason codes |
| `rows[].source_replay_evidence` | `dict` | `{}` | Fresh root/file probe, observed size/mtime/identity, mismatch list, and typed `source_location_unavailable`, `source_missing`, `source_access_failed`, or changed-identity evidence |
| `rows[].source_content_sha256` | `str` | — | Full-file SHA-256 baseline captured before claim/recovery and revalidated on reconnect; sampled identity remains separate |
| `rows[].timeline[]` | `list[dict]` | `[]` | Backend-authored what/why/when/next/operator-action lifecycle history |
| `rows[].manual_recovery_required` / `manual_recovery_available` | `bool` | `False` | Exhausted rows remain visible; only exact safe exhausted rows expose backend-owned retry action metadata |
| `rows[].manual_retry_history[]` / `manual_retry_denials[]` | `list[dict]` | `[]` | Request-id idempotency, reason, fresh source proof, and denied retry evidence |
| `row_count` / `claimable_row_count` / `active_row_count` / `terminal_row_count` | `int` | `0` | Aggregate claim/lifecycle totals recomputed under the batch-state lock |
| `retry_scheduled_row_count` / `retry_exhausted_row_count` / `review_row_count` / `failed_row_count` | `int` | `0` | Disjoint recovery and terminal operator counts |
| `batch_terminal` / `manual_recovery_row_count` | mixed | — | Whether every row is terminal and how many rows require operator recovery action |

Notes:

- Phase 4B writes this file and strict command journal evidence only after a transient coordinator handoff-root probe succeeds. Workers may claim one row at a time and write to the planned handoff folder only.
- Before every claim, the coordinator runs killable bounded root/file/identity probes. Unavailable roots and access failures schedule bounded retries; a reachable missing leaf or changed identity routes to review. Configured mapped-drive and UNC roots use the same typed contract without frontend path probing.
- Phase 5 reduces done reports by verifying batch id, row key, exact active claim/job/worker identity, source identity, worker artifact metadata, output presence, and handoff boundary. Success initially records `pending_destination_policy=true`; review, output-missing, corrupt, retryable failure, terminal failure, duplicate, and late reports are persisted as evidence without media movement. A stale done or release cannot overwrite a newer claim.
- Phase 6 applies destination policy only on the coordinator after Phase 5 acceptance. Workers still write only to row handoff folders. Coordinator policy may leave the verified output in review workspace, move it into manifest-backed Pending Publish, copy it to a non-overlapping final path, replace a final path only with confirmed replacement evidence, or fail closed with the source and handoff output preserved. Source media remains read-only.
- Active `desktop_rerun_network_batch.v1` files with status `claim_disabled`, `active`, `running`, `stopping`, `stopped_after_current`, or `paused` make backend close-readiness unsafe until a later safe stop/drain state exists.
- `POST /api/rerun/network/retry` requires exact `batch_id`, `row_key`, nonblank `request_id` and reason, plus strict `confirm_retry=true`. It revalidates the persisted source identity and reopens only one eligible `retry_exhausted` row; duplicate request IDs are idempotent and changed sources remain review-only.
- Existing normal network queue claim/done/release protocol remains compatible; `csv_rerun_row` metadata is additive and source-identity duplicate prevention still shares the normal in-flight registry.

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

**Contract file**: `src/mediapipeline/core/kernel/contracts/active_job.py`
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
| `kill_degraded` | Root termination was attempted, but descendant/process-tree exit is unproved; the record remains nonterminal and reconciliation-required |
| `orphaned` | Process record exists but no matching PID found |

### Notes

- Active job records are written and updated by the backend process service.
- `kill_degraded` is monotonic against heartbeat/stale reconciliation updates,
  keeps close-readiness blocked, and projects as an operator warning until exact
  process-tree ownership is reconciled.
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

**Contract file**: `src/mediapipeline/core/kernel/contracts/queue_snapshot.py`
**Artifact**: `State\Progress\queue_snapshot.json` — rewritten each time the queue is evaluated
**Schema version**: `queue_plan_snapshot.v1`

The snapshot contains a container record and three row lists: the uncapped accepted Run Once workload, queue display rows, and excluded rows. `runnable_count` reports only items ready to process; display rows can include blocked or held rows for operator review. Queue filters, pagination, and display caps never define launch scope.

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
| `queue_snapshot_origin` | `str` | `"unknown"` | `dry_run` for a backend Queue preview; active discovery emits `active_run` before the dry-run runner promotes a preview |
| `desktop_queue_preview_request_id` | `str` | `""` | Unique dry-run request ID; must match the completed scan status before blank Run Once |
| `queue_input_fingerprint_schema` | `str` | `""` | Queue input fingerprint schema, currently `queue_input_fingerprint.v1` |
| `queue_input_fingerprint` | `str` | `""` | Digest of config, priority, strategy, and file-override inputs used by the preview |
| `queue_input_components` | `object` | `{}` | Per-input status and SHA-256 evidence used to explain changed/unavailable preview inputs |
| `queue_plan_fingerprint_schema` | `str` | `""` | Active/dry plan fingerprint schema, currently `queue_plan_fingerprint.v1` |
| `queue_plan_fingerprint` | `str` | `""` | Digest of uncapped ordered rows, exclusions, accepted source identities and backend naming-plan filenames, input fingerprint, strategy, pending-index health, and pending-publish backpressure |
| `accepted_run_rows_fingerprint_schema` | `str` | `""` | Accepted-membership digest schema, currently `accepted_run_rows_fingerprint.v1` |
| `accepted_run_rows_fingerprint` | `str` | `""` | Digest of every uncapped accepted row's position, stable identity/path, planned filename and evidence source, planned route/reason, parent context, and intended destination; v1 makes path fields absolute, uses forward slashes, folds ASCII `A-Z` only, and preserves non-ASCII plus non-path text exactly; recomputed before launch and engine adoption |
| `pending_publish_index_health` | `object` | `{}` | Read-only pending-manifest index health used during preview and launch gating |
| `pending_publish_backpressure` | `object` | `{}` | Pending-publish count/threshold signature and launch-block decision |
| `desktop_queue_snapshot_fallback_used` | `bool` | `False` | Explicitly identifies a cached snapshot returned after a failed live dry-run; cached fallback is never launchable |
| `desktop_queue_snapshot_fallback_reason` | `str` | `""` | Failure reason when cached evidence is displayed |
| `total_row_count` | `int` | `0` | Full row count before display truncation |
| `shown_row_count` | `int` | `0` | Rows included in this snapshot payload |
| `row_limit` | `int` | `0` | Maximum displayed rows written to the snapshot |
| `rows_truncated` | `bool` | `False` | Whether display rows were capped; plan fingerprint still covers the full plan |
| `excluded_count` | `int` | `0` | Excluded items count |
| `excluded_row_limit` | `int` | `0` | Max excluded rows reported |
| `excluded_rows_truncated` | `bool` | `False` | Whether excluded list was truncated |
| `accepted_run_rows` | `list[QueueAcceptedRunRow]` | `[]` | Uncapped, ordered Backend Queue Run Once acceptance contract. It contains every accepted source exactly once, independent of `rows` display truncation. |
| `rows` | `list[QueuePlanRow]` | `[]` | Runnable/queued items |
| `excluded_rows` | `list[QueuePlanExcludedRow]` | `[]` | Excluded items |

### QueueAcceptedRunRow (Uncapped Run Once Membership)

| Field | Type | Notes |
|---|---|---|
| `source_identity` | `str` | Stable backend source identity (required and unique in the accepted workload) |
| `source_identity_algorithm` | `str` | Algorithm/version that produced `source_identity` (required) |
| `source_path` | `str` | Exact accepted source path (required and unique, case-insensitive) |
| `display_name` | `str` | Compatibility copy of `planned_display_name` for older consumers; it is not independently authoritative and the public Queue row field of the same name is only a raw display label |
| `planned_display_name` | `str` | Required nonblank filename from the backend production destination plan; remains distinct from the raw `source_path` leaf |
| `planned_display_name_source` | `str` | Required evidence version, exactly `plex_destination_plan.v1` for a newly launchable row |
| `parent_context` | `str` | Distinguishing parent/path context for identical leaf filenames |
| `run_queue_index` | `int` | One-based run-wide position; positions must be contiguous and ordered |
| `run_queue_total` | `int` | Full accepted workload total; every row must carry the same total |
| `route` | `str` | Planned route only |
| `route_reason_code` | `str` | Planned route reason code only |
| `route_reason` | `str` | Planned route reason only |
| `intended_final_path` | `str` | Planned intended final destination when backend planning can provide it |

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

- The Python dry-run runner writes a request-unique temporary snapshot, validates freshness and stable input fingerprints, atomically publishes the canonical snapshot, mirrors it to SQLite as non-authoritative evidence, and removes the temporary file on success or failure.
- Destination naming is part of acceptance evidence. If override resolution or production destination naming cannot produce a nonblank filename, that Queue row is blocked with `destination_naming_plan_failed` and cannot enter `accepted_run_rows`; neither Python nor PowerShell seed boundaries substitute the raw source leaf. The planned name and exact evidence-source token participate in both fingerprints. At execution, after the same effective override layers are active and before probe/scratch work, a fingerprinted Backend Queue job must verify its correlated `plex_destination_plan.v1` / `queue_plan` evidence and match the recomputed production filename to the immutable accepted `display_name`. The verified output-path object is carried through encode, remux, and their fallbacks rather than recomputed. Missing/tampered evidence and plan drift stop as `DESTINATION_NAMING_EVIDENCE_MISSING` or `DESTINATION_NAMING_PLAN_MISMATCH`; they never fall through to encode/remux/publish.
- Blank normal-Queue Run Once is rejected unless the canonical snapshot is a current `dry_run` with matching scan/request/scope/input evidence, a nonempty plan fingerprint, a valid accepted-membership content fingerprint, and a complete `accepted_run_rows` contract whose count matches `runnable_count`. The Python launch backend recomputes the accepted digest, retains that uncapped contract, creates the immutable `starting` Run Monitor before process spawn, and returns the same run/fingerprint identity. The active PowerShell process recomputes the digest, adopts that exact run-specific seed, and must reproduce both its Queue-plan fingerprint and accepted membership before media dispatch; it never redefines membership from a refreshed shared Queue snapshot.
- Legacy Queue snapshots without versioned planned-name evidence or the accepted-membership digest remain displayable for diagnosis but are not launchable. Refresh Queue with the current backend; do not migrate a raw label into verified evidence.
- `GET /api/queue` remains a read of the latest backend-owned snapshot. It may label cached/legacy evidence for display but does not generate or promote a Queue plan.

- The queue snapshot is rebuilt each time a dry-run or queue evaluation is performed. It is not an append-only log.
- `GET /api/queue` projects only normal queue rows and preserves compatibility metadata with `queue_sources=["normal_queue"]`, `dedicated_rerun_visible_count=0`, and an empty `rerun_correlation`; CSV rerun state is never merged into the normal queue projection.
- Blank Run Once launch preflight treats `produced_at`, file modification time, and clock skew as advisory preview-age evidence under `QueueLaunchSnapshotFreshnessSeconds` (default 60; range 15–3600). Age alone never blocks launch because the engine rebuilds the queue and requires the accepted plan fingerprint before media dispatch. Missing, mismatched, unreadable, actively scanning, wrong-origin, input-inconsistent, unversioned-name, or digest-mismatched plan evidence still blocks with an actionable Queue refresh; a validated zero-runnable plan blocks with `no_runnable_work`.
- The `blocked_reason_code` on `QueuePlanRow` drives the blocked-row warning signals in the Queue table.
- The `route` field is a prediction at queue-plan time. The final route in the completed manifest may differ if runtime conditions change.

---

## RunMonitorRecord

**Contract file**: `src/mediapipeline/contracts/run_monitor.py`
**Artifacts**: `State\RunMonitor\<run_id>.json` plus identity-only pointer `State\RunMonitor\latest.json`
**Schema versions**: durable record `pipeline_run_monitor.v1`, pointer `pipeline_run_monitor_pointer.v1`, Local API projection `desktop_run_monitor.v1`

The durable record is the backend authority for one accepted Backend Queue Run Once workload: stable run ID, accepted Queue plan fingerprint, immutable job/source membership, run-wide positions/totals, run-scoped counts, lifecycle, explicit per-file stages, per-track audio/subtitle evidence, all current workers, freshness timestamps, Stop After Current state, and correlated terminal references. The launch command returns `desktop_run_monitor_launch.v1` identity containing the same run ID and accepted Queue fingerprint so the frontend can connect the accepted launch to this record without matching filenames or Queue render order.

The Local API item projection keeps durable acceptance evidence distinct from
the operator-facing label:

| Projection field | Meaning |
|---|---|
| `accepted_display_name` | Exact label stored in the immutable per-run item. It is retained even when a newer projection label is available. |
| `display_name` | Effective operator label. It is the verified Queue-plan name for current records, an exactly proven terminal output filename for an eligible legacy terminal item, or the unchanged accepted label when neither authority exists. |
| `display_name_basis` | Explicit authority classification: `verified_queue_plan`, `terminal_output`, or `legacy_accepted`. |
| `display_name_evidence` | Source, provenance, timestamp, and freshness for the effective label. Terminal reconciliation requires exact same-run/item/job correlation and an exact Completed or Pending Publish path reference; filename similarity is never evidence. |

| Surface | Authority boundary |
|---|---|
| Queue snapshot | Planned workload and planned route/reason before launch; its accepted plan fingerprint is captured by the monitor but the current Queue display is not run membership. |
| Run monitor | Accepted membership and correlated runtime lifecycle/stage/track/worker evidence for that run. It may reference terminal proof but does not replace terminal artifacts. |
| Completed manifest/sidecar | Terminal proof for verified direct publication and final route/reason. |
| Pending Publish manifest | Terminal proof for manifest-backed parking, parked path, and intended final destination. |
| Failure/review artifact | Terminal proof for failure, block, review ownership, retryability, and recovery action. |
| Pipeline progress/events/logs | Supporting evidence only. An event, log tail, or raw progress claim cannot populate current work unless the monitor has exact run/job correlation and passes the single backend freshness decision. |
| SQLite/generated summaries | Non-authoritative mirrors/navigation evidence; never used to recover accepted membership or assert current/terminal state. |

Storage invariants:

- `<run_id>.json` is selected only by a safe exact backend identity; path fragments, reserved `latest`, and ambiguous query values are rejected.
- The Python launch backend atomically seeds the complete immutable `starting` record before spawn from validated `accepted_run_rows`. An exact retry with the same command, fingerprint, and membership may adopt that record and repair `latest.json`; any mismatch or terminal record fails closed.
- After process start, the PowerShell engine adopts the exact seed, verifies active discovery parity, and is the sole runtime evidence writer. A Queue refresh cannot add, remove, or reorder accepted items. A pre-spawn failure is terminalized by Python; a post-spawn exception is terminalized only when child cleanup is proven, otherwise the nonterminal seed remains honest pending reconciliation.
- `write_sequence` must increase. Accepted membership, source identity, and run-wide position/total are immutable after creation.
- Newly seeded items carry `display_name_evidence` with source `plex_destination_plan.v1` and provenance `queue_plan`. Older records without it are never adopted or rewritten because the accepted label participates in immutable membership/signature evidence. For a completed/published item, the read-only Local API may derive the effective filename from the terminal published path only when terminal output evidence and the exact job-correlated Completed reference prove the same path. For a parked item, it may use the intended-final filename only when terminal output evidence and an exact Pending Publish or manifest reference prove the park. The projection then reports `display_name_basis=terminal_output`, preserves the stored label in `accepted_display_name`, and exposes the terminal evidence; absent, future-dated, or contradictory proof remains `legacy_accepted`/unknown. The frontend does not clean names and the current Queue snapshot is not consulted.
- Terminal run/item states cannot regress. Active workers must correlate to an accepted job in the same run.
- A verified terminal artifact that proves failure/review before route selection closes Final route as explicit `unknown` (or `not_applicable` when the artifact proves that semantic) with the terminal artifact's reason, reason code, timestamp, and source. `awaiting_evidence` is never a terminal substitute. Terminal output-sidecar paths receive terminal provenance only when they are listed by the exact correlated Completed or Pending Publish artifact; process-result-only paths remain supporting evidence.
- Storage retains the latest ten terminal per-run records by default, never prunes nonterminal records, and preserves the latest selected record. `latest.json` is an identity-only pointer that can be repaired only from the exact persisted record.
- Missing or invalid records return an explicit unavailable projection. Stale, future-dated, backend-unavailable, or contradictory evidence suppresses active file/stage/route/worker/progress claims and may appear only as “Last known — not current.”
- Backward-compatible absent optional track/output evidence remains `unknown`/empty; it is never relabeled as pending and never reconstructed from legacy current-work payloads.

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

## Native-Tool Diagnostic Log Lifecycle

**Contract file**: `ops/pipeline/engine/process/tool_log_lifecycle.ps1`
**Artifacts**: `State\Pipeline\ToolLogs\Active\*.log`, `State\Pipeline\ToolLogs\Interrupted\*.log`, and failure-promoted logs under `State\Failures\Artifacts\`
**State layout schema**: `media_pipeline_state_layout.v1` (additive directories; no version bump)

These artifacts are plain-text diagnostic streams, not JSON contracts. Their directory and disposition carry the lifecycle contract:

| Disposition | Terminal path | Meaning |
|---|---|---|
| `active` | `Pipeline\ToolLogs\Active` | Tool work is live, or the previous process ended before it finalized the capture. Presence is not failure evidence. |
| `deleted` | None | Tool completed successfully; its temporary capture was removed. |
| `interrupted` | `Pipeline\ToolLogs\Interrupted` | Operator stop, or orphaned active capture reconciled by the next exclusive startup. |
| `failure` | `Failures\Artifacts` | Tool failure, timeout, policy abort, or runner exception promoted the capture as failure evidence. |

Worker children use equivalent slot-local paths under `State\Workers\slot-<n>`. Interrupted captures are pruned on exclusive startup using `InterruptedToolLogRetentionDays`, default 3 and bounded to 1–365. `-ValidateOnly` and lockless diagnostic dump modes do not run this maintenance.

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
- FFmpeg `tool_started` and `tool_completed` events add `diagnostic_log_path` and `diagnostic_log_disposition`; these fields describe the native-tool log lifecycle without changing `pipeline_event.v1`.
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
