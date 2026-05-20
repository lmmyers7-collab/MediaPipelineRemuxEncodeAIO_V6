# Sample Validation Payload Schema Reference

Date: 2026-05-15

Documents all schema version constants defined in `DesktopApp/mediapipeline_desktop_app/application/facade_sample_validation_policy.py` and the route/payload each schema serves. All payloads are backend-owned. The frontend reads or previews them only — no payload is written from frontend code.

---

## Schema Constants

| Constant | Schema string | Served by |
|---|---|---|
| `SAMPLE_VALIDATION_RECORD_SCHEMA` | `sample_validation_record.v1` | Appended to `State\Validation\sample_validation_log.jsonl` by backend |
| `SAMPLE_VALIDATION_PREVIEW_SCHEMA` | `desktop_sample_validation_preview.v1` | `GET /api/sample-validation/preview` response |
| `SAMPLE_VALIDATION_LOG_SCHEMA` | `desktop_sample_validation_log.v1` | `GET /api/sample-validation/log` (recent-records read) |
| `SAMPLE_VALIDATION_SUMMARY_SCHEMA` | `desktop_sample_validation_summary.v1` | Embedded in the health/contract response; top-level summary counts |
| `SAMPLE_VALIDATION_READINESS_SCHEMA` | `desktop_sample_validation_readiness.v1` | `GET /api/sample-validation/readiness` — backend readiness explanation |
| `SAMPLE_VALIDATION_RECONCILIATION_SCHEMA` | `desktop_sample_validation_reconciliation.v1` | `GET /api/sample-validation/reconciliation` — stale/current/review status for recent records |
| `SAMPLE_VALIDATION_CURRENT_EVIDENCE_SCHEMA` | `desktop_sample_validation_current_evidence.v1` | Embedded in the preview response; snapshot of current backend artifact state |
| `SAMPLE_VALIDATION_EVIDENCE_PACKET_SCHEMA` | `desktop_sample_validation_evidence_packet.v1` | Embedded in preview response; full evidence packet for the selected sample |
| `SAMPLE_VALIDATION_POST_RUN_CAPTURE_SCHEMA` | `desktop_sample_validation_post_run_capture.v1` | Embedded in preview/append response; copyable post-run evidence capture packet |
| `SAMPLE_VALIDATION_WORKSHEET_RUNS_SCHEMA` | `desktop_real_media_worksheet_runs.v1` | `GET /api/sample-validation/worksheet-runs` — generated worksheet run evidence |
| `SAMPLE_VALIDATION_PILOT_PLAN_SCHEMA` | `desktop_real_media_pilot_plan.v1` | `GET /api/sample-validation/pilot-plan` — real-media pilot run checkpoint plan |
| `SAMPLE_VALIDATION_EXECUTION_CHECKLIST_SCHEMA` | `desktop_real_media_execution_checklist.v1` | `GET /api/sample-validation/execution-checklist` — operator sample execution checklist |
| `SAMPLE_VALIDATION_APPEND_READINESS_SCHEMA` | `desktop_sample_validation_append_readiness.v1` | Embedded in preview response; append-level readiness flags |

---

## Per-Schema Field Summaries

### `sample_validation_record.v1`

The persisted JSONL record written to `State\Validation\sample_validation_log.jsonl` by the backend on a confirmed append.

| Field | Type | Description |
|---|---|---|
| `schema` | string | Always `"sample_validation_record.v1"` |
| `created_at` | ISO 8601 string | Timestamp of the append |
| `created_by` | string | Always `"operator"` |
| `shell` | string | Always `"webview"` |
| `app_version` | string | App version at append time |
| `source_path` | string | Source media file path |
| `output_path` | string | Completed output file path |
| `sample_label` | string | Operator-supplied label (max 600 chars) |
| `proof_strength` | enum | `exact-path` / `partial-exact` / `filename-advisory` / `none` |
| `operator_decision` | enum | `accepted` / `hold_review` / `rerun_backend` / `fallback_tk` |
| `checks` | object | 9 boolean check fields (see below) |
| `evidence` | object | Snapshots of queue / completed / pending_publish / diagnostics / commands at preview time |
| `notes` | string | Operator free-text notes (max 4000 chars) |

**Check keys**: `queue_route_checked`, `ffmpeg_log_checked`, `subtitle_checked`, `audio_checked`, `completed_output_checked`, `sidecar_manifest_checked`, `size_growth_checked`, `pending_publish_checked`, `diagnostics_checked`.

Required checks (must be true for `accepted` without warning): queue route, completed output, sidecar manifest, size growth, diagnostics.

---

### `desktop_sample_validation_preview.v1`

Returned by `GET /api/sample-validation/preview`. Read-only — never written to disk. Used by WebView Home before the operator clicks append.

| Field | Type | Description |
|---|---|---|
| `schema_version` | string | `"desktop_sample_validation_preview.v1"` |
| `ok` | bool | False if any hard errors prevent a valid append |
| `record_schema` | string | Schema of the record that would be written |
| `log_path` | string | Absolute path of the validation log (informational) |
| `record_size_bytes` | int | Projected record size |
| `request_size_bytes` | int | Incoming request size |
| `record` | object | The normalized `sample_validation_record.v1` that would be appended |
| `current_evidence` | object | `desktop_sample_validation_current_evidence.v1` snapshot |
| `append_readiness` | object | `desktop_sample_validation_append_readiness.v1` flags |
| `pilot_evidence_packet` | object | `desktop_sample_validation_evidence_packet.v1` |
| `post_run_capture` | object | `desktop_sample_validation_post_run_capture.v1` |
| `warnings` | list[string] | Non-blocking issues |
| `errors` | list[string] | Blocking validation failures |
| `guardrail` | string | Hardcoded mutation boundary statement |

---

### `desktop_sample_validation_log.v1`

Returned by `GET /api/sample-validation/log`. Contains recent records read from the JSONL file (up to `SAMPLE_VALIDATION_RECENT_LIMIT = 50` records).

| Field | Description |
|---|---|
| `schema_version` | `"desktop_sample_validation_log.v1"` |
| `records` | List of recent `sample_validation_record.v1` objects |
| `record_count` | Count of returned records |
| `log_path` | Path to the log file |

---

### `desktop_sample_validation_summary.v1`

Embedded in the health/contract backend response. Provides aggregate counts without exposing record details.

| Field | Description |
|---|---|
| `schema_version` | `"desktop_sample_validation_summary.v1"` |
| `total` | Total records in the log |
| `accepted` | Count with `operator_decision: accepted` |
| `hold_review` | Count with `operator_decision: hold_review` |
| `rerun_backend` | Count with `operator_decision: rerun_backend` |
| `fallback_tk` | Count with `operator_decision: fallback_tk` |
| `latest_decision` | `operator_decision` of the most recent record |
| `latest_proof_strength` | `proof_strength` of the most recent record |

---

### `desktop_sample_validation_readiness.v1`

Returned by `GET /api/sample-validation/readiness`. Explains whether enough backend evidence is present for a meaningful append.

| Field | Description |
|---|---|
| `schema_version` | `"desktop_sample_validation_readiness.v1"` |
| `status` | `ok` / `warn` / `block` |
| `severity` | `ok` / `warning` / `error` |
| `readiness_rows` | Per-evidence-area readiness rows with label, status, and detail |
| `required_evidence_count` | Number of required check items with backend evidence |
| `blocker_count` | Number of hard blocks preventing useful append |
| `safe_next_action` | Operator guidance: `inspect_and_append`, `inspect_before_append`, `wait_for_completion`, `review_before_append` |

---

### `desktop_sample_validation_reconciliation.v1`

Returned by `GET /api/sample-validation/reconciliation`. Compares recent records against current backend state to flag stale or mismatched records.

| Field | Description |
|---|---|
| `schema_version` | `"desktop_sample_validation_reconciliation.v1"` |
| `records` | List of reconciliation rows, one per recent record |
| `stale_count` | Number of records whose source/output no longer matches current backend artifacts |
| `current_count` | Number of records that still match |
| `review_count` | Number of records flagged for operator review |

Each reconciliation row contains: `record_id`, `status` (`current`/`stale`/`review`), `reason`, `checks_agreement` (per-check match flags).

---

### `desktop_sample_validation_current_evidence.v1`

Embedded in the preview response. Snapshot of current backend artifact state for the selected source/output at the time of the preview call.

| Field | Description |
|---|---|
| `schema_version` | `"desktop_sample_validation_current_evidence.v1"` |
| `status` | `current` / `stale` / `unknown` |
| `severity` | `ok` / `warning` / `error` |
| `artifact_errors` | List of errors reading backend artifacts |
| `queue_evidence` | Current Queue row for this source (if any) |
| `completed_evidence` | Current Completed row for this output (if any) |
| `pending_evidence` | Current Pending Publish row (if any) |
| `diagnostics_evidence` | Recent Diagnostics entries for this source/output |
| `commands_evidence` | Recent command journal entries for this source |

---

### `desktop_sample_validation_evidence_packet.v1`

Full evidence packet embedded in the preview response. Summarizes route/output/log/publish/media proof in operator-readable rows.

| Field | Description |
|---|---|
| `schema_version` | `"desktop_sample_validation_evidence_packet.v1"` |
| `sample_label` | Label from the record |
| `route_proof_rows` | Queue route decision rows |
| `output_proof_rows` | Completed output/sidecar proof rows |
| `log_proof_rows` | FFmpeg/run log evidence rows |
| `publish_proof_rows` | Pending Publish posture rows (if applicable) |
| `media_proof_rows` | Size/media type evidence rows |
| `safe_next_action` | Append readiness recommendation |
| `stop_condition` | Description of any condition that prevents a clean append |

---

### `desktop_real_media_worksheet_runs.v1`

Returned by `GET /api/sample-validation/worksheet-runs`. Summarizes evidence from generated Markdown worksheet files under `Docs\RealMediaValidationRuns`.

| Field | Description |
|---|---|
| `schema_version` | `"desktop_real_media_worksheet_runs.v1"` |
| `runs` | List of run summaries parsed from worksheets (up to `SAMPLE_VALIDATION_WORKSHEET_RUN_LIMIT = 20`) |
| `sample_count` | Total samples across all parsed worksheets (up to `SAMPLE_VALIDATION_WORKSHEET_SAMPLE_LIMIT = 12` per run) |
| `worksheet_read_bytes` | Total bytes read from worksheet files |

---

### `desktop_real_media_pilot_plan.v1`

Returned by `GET /api/sample-validation/pilot-plan`. Backend-authored checkpoint plan for a real-media pilot run.

| Field | Description |
|---|---|
| `schema_version` | `"desktop_real_media_pilot_plan.v1"` |
| `plan_rows` | Ordered list of checkpoint rows with label, status, and detail |
| `pre_run_count` | Number of pre-run checks |
| `post_run_count` | Number of post-run checks |
| `attention_count` | Number of rows flagged for attention |

---

### `desktop_real_media_execution_checklist.v1`

Returned by `GET /api/sample-validation/execution-checklist`. Operator sample execution checklist with selectable rows for pre/during/post-run evidence steps.

| Field | Description |
|---|---|
| `schema_version` | `"desktop_real_media_execution_checklist.v1"` |
| `checklist_rows` | List of checklist items with label, status, evidence hint, and selectable detail |
| `required_count` | Number of required items |
| `optional_count` | Number of optional items |

---

### `desktop_sample_validation_append_readiness.v1`

Embedded in the preview response. Fine-grained flags indicating whether each required check is satisfied.

| Field | Description |
|---|---|
| `schema_version` | `"desktop_sample_validation_append_readiness.v1"` |
| `all_required_checks_present` | True if all 5 required check fields are `true` |
| `per_check_status` | Dict of check key → `ok` / `missing` / `warning` |
| `errors` | Hard errors preventing any append |
| `warnings` | Non-blocking concerns |

---

### `desktop_sample_validation_post_run_capture.v1`

Embedded in preview and append responses. Backend-authored copyable checklist for recording post-run proof before appending an evidence note.

| Field | Description |
|---|---|
| `schema_version` | `"desktop_sample_validation_post_run_capture.v1"` |
| `operator_status` | `ready-to-record`, `review-before-append`, `blocked`, or related append-readiness status |
| `rows` | Ordered proof rows for sample identity, remux/encode decision, Completed output/sidecar, Diagnostics logs, Pending Publish/final placement, subtitles, audio, size, and append decision |
| `required_gaps` | Required capture checkpoints still missing for an accepted evidence note |
| `markdown_lines` / `markdown_text` | Copyable Markdown generated from the preview result; not written to disk by the app |
| `guardrail` | Read-only boundary; no append, launch, publish/drain, settings save, rename, manifest write, or media mutation |

---

## Mutation Boundary

All routes above are **read-only** except the append POST. The append POST is guarded by the facade's sample-validation lock and writes only to `State\Validation\sample_validation_log.jsonl`. No payload above causes any manifest mutation, media file change, queue state change, publish/drain, launch, or daily-driver approval.

The `guardrail` field in `desktop_sample_validation_preview.v1` states this boundary verbatim in every preview response.

---

## Size Limits

| Limit | Value |
|---|---|
| Maximum individual record size | 32 KB |
| Maximum request size (preview/append) | 64 KB |
| Maximum recent records read | 50 |
| Maximum validation log tail | 512 KB |
| Maximum operator notes | 4000 chars |
| Maximum text fields | 600 chars |
| Maximum evidence items per payload | 24 |
| Maximum worksheet bytes read | 128 KB |
| Maximum worksheet runs shown | 20 |
| Maximum worksheet samples per run | 12 |

---

## See Also

- Operator guide: `Docs/sample-validation/SAMPLE_VALIDATION_RECORD_OPERATOR_GUIDE.md`
- Artifact design: `Docs/sample-validation/V5_SAMPLE_VALIDATION_ARTIFACT_DESIGN.md`
- Real-media playbook: `Docs/sample-validation/V5_REAL_MEDIA_VALIDATION_PLAYBOOK.md`
- Source: `DesktopApp/mediapipeline_desktop_app/application/facade_sample_validation_policy.py`

---

## Task Output

```
Task ID: CLN3-011
Files inspected: DesktopApp\mediapipeline_desktop_app\application\facade_sample_validation_policy.py, Docs\sample-validation\V5_SAMPLE_VALIDATION_ARTIFACT_DESIGN.md
Files changed: Docs\sample-validation\SAMPLE_VALIDATION_PAYLOAD_SCHEMA_REFERENCE.md (created)
Validation: Select-String -Path Docs\sample-validation\SAMPLE_VALIDATION_PAYLOAD_SCHEMA_REFERENCE.md -Pattern "desktop_sample_validation|sample_validation_record|desktop_real_media"
Findings: 12 schema constants documented; per-field summaries provided; mutation boundary and size limits stated.
Open questions: None.
Risk: Low — documentation only.
```
