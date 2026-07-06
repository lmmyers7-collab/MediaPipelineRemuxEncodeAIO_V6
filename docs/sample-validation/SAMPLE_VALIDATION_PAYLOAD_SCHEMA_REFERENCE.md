# Sample Validation Payload Schema Reference

Date: 2026-06-02

This reference tracks the backend-owned Sample Validation payloads served by the active Local API. The WebView may render these payloads and may submit the allowlisted preview/append commands, but it must not accept outputs, launch work, save settings, publish/drain, repair state, rewrite manifests/sidecars, rename files, or touch source/output/scratch media.

---

## Route Surface

| Route | Method | Effect | Payloads |
|---|---|---|---|
| `/api/sample-validation` | `GET` | `none` | Recent records plus summary, readiness, reconciliation, worksheet runs, pilot plan/execution checklist, sample-set guide, evidence-gap summary, pilot runbook, policy alignment, and validation audit |
| `/api/sample-validation/preview` | `POST` | `none` | Normalized record preview, current backend evidence, append readiness, pilot evidence packet, and post-run capture packet |
| `/api/sample-validation/append` | `POST` | `validation-log-write` | Appends one evidence-only JSONL record and returns the same preview evidence in the command result data |

There are no separate `/log`, `/readiness`, `/reconciliation`, `/worksheet-runs`, `/pilot-plan`, or `/execution-checklist` routes. Those payloads are embedded in `GET /api/sample-validation`.

---

## Schema Constants

| Constant | Schema string | Served by |
|---|---|---|
| `SAMPLE_VALIDATION_RECORD_SCHEMA` | `sample_validation_record.v1` | Appended under `State\Validation\sample_validation_log.jsonl` by backend append |
| `SAMPLE_VALIDATION_PREVIEW_SCHEMA` | `desktop_sample_validation_preview.v1` | `POST /api/sample-validation/preview` response and append result `data` |
| `SAMPLE_VALIDATION_LOG_SCHEMA` | `desktop_sample_validation_log.v1` | Top-level `GET /api/sample-validation` response |
| `SAMPLE_VALIDATION_SUMMARY_SCHEMA` | `desktop_sample_validation_summary.v1` | `summary` inside the log payload |
| `SAMPLE_VALIDATION_READINESS_SCHEMA` | `desktop_sample_validation_readiness.v1` | `readiness` inside the log payload |
| `SAMPLE_VALIDATION_RECONCILIATION_SCHEMA` | `desktop_sample_validation_reconciliation.v1` | `reconciliation` inside the log payload |
| `SAMPLE_VALIDATION_CURRENT_EVIDENCE_SCHEMA` | `desktop_sample_validation_current_evidence.v1` | `current_evidence` inside preview/append evidence |
| `SAMPLE_VALIDATION_APPEND_READINESS_SCHEMA` | `desktop_sample_validation_append_readiness.v1` | `append_readiness` inside preview/append evidence |
| `SAMPLE_VALIDATION_EVIDENCE_PACKET_SCHEMA` | `desktop_sample_validation_evidence_packet.v1` | `pilot_evidence_packet` inside preview/append evidence |
| `SAMPLE_VALIDATION_POST_RUN_CAPTURE_SCHEMA` | `desktop_sample_validation_post_run_capture.v1` | `post_run_capture` inside preview/append evidence |
| `SAMPLE_VALIDATION_WORKSHEET_RUNS_SCHEMA` | `desktop_real_media_worksheet_runs.v1` | `worksheet_runs` inside the log payload |
| `SAMPLE_VALIDATION_PILOT_PLAN_SCHEMA` | `desktop_real_media_pilot_plan.v1` | `pilot_plan` inside the log payload |
| `SAMPLE_VALIDATION_EXECUTION_CHECKLIST_SCHEMA` | `desktop_real_media_execution_checklist.v1` | `execution_checklist_schema` and `execution_checklist` inside `pilot_plan` |
| `SAMPLE_VALIDATION_CUTOVER_GATE_SCHEMA` | `desktop_webview_cutover_gate.v1` | `cutover_gate` inside the log payload |
| `SAMPLE_VALIDATION_SAMPLE_SET_GUIDE_SCHEMA` | `desktop_real_media_sample_set_guide.v1` | `sample_set_guide` inside the log payload |
| `SAMPLE_VALIDATION_EVIDENCE_GAP_SCHEMA` | `desktop_real_media_evidence_gap.v1` | `evidence_gap_summary` inside the log payload |
| `SAMPLE_VALIDATION_PILOT_RUNBOOK_SCHEMA` | `desktop_real_media_pilot_runbook.v1` | `pilot_runbook` inside the log payload |
| `SAMPLE_VALIDATION_POLICY_ALIGNMENT_SCHEMA` | `desktop_real_media_policy_alignment.v1` | `policy_alignment` inside the log payload |
| `SAMPLE_VALIDATION_AUDIT_SCHEMA` | `desktop_real_media_validation_audit.v1` | `validation_audit` inside the log payload |

---

## Persisted Record

`sample_validation_record.v1` is the only persisted Sample Validation payload. It is written only by `POST /api/sample-validation/append`.

| Field | Description |
|---|---|
| `schema` | Always `sample_validation_record.v1` |
| `record_id` | Caller-provided ID or backend-generated `sample-...` ID |
| `created_at` | Caller-provided timestamp or backend UTC timestamp |
| `created_by` | Caller-provided value or `operator` |
| `shell` | `webview`, `tauri`, or normalized caller value |
| `app_version` | Caller-provided version or current app version |
| `source_path` / `output_path` | Recorded sample source/output evidence paths; at least one is required |
| `sample_label` | Operator-facing sample label |
| `sample_category` | Optional controlled pilot category key: `h264-remux-safe`, `subtitle-srt-generation`, `audio-routing`, `encode-size-policy`, or `deferred-publish` |
| `proof_strength` | `exact-path`, `partial-exact`, `filename-advisory`, or `none` |
| `operator_decision` | `accepted`, `hold_review`, `manual_review`, or `rerun_backend` |
| `checks` | Boolean evidence checks for route, logs, subtitles, audio, completed output, sidecar/manifest, size growth, pending publish, and diagnostics |
| `evidence` | Bounded evidence arrays for `queue`, `completed`, `pending_publish`, `diagnostics`, and `commands` |
| `operator_notes` | Operator free-text notes, capped at 4000 characters |

Optional route/media context fields may also be present: `route_reason`, `route_action`, `encoder`, `subtitle_summary`, `audio_summary`, `pending_manifest_path`, `completed_manifest_row_key`, `source_size_bytes`, `output_size_bytes`, and `size_growth_percent`.

---

## Preview And Append

`desktop_sample_validation_preview.v1` contains the normalized record plus read-only proof packets:

| Field | Description |
|---|---|
| `ok` | False when hard validation errors prevent append |
| `record` | Normalized `sample_validation_record.v1` |
| `current_evidence` | `desktop_sample_validation_current_evidence.v1`; bounded comparison against current Queue, Completed, Pending Publish, and Diagnostics artifacts |
| `append_readiness` | `desktop_sample_validation_append_readiness.v1`; advisory append/accepted-readiness rows and gaps |
| `pilot_evidence_packet` | `desktop_sample_validation_evidence_packet.v1`; operator proof ladder for the proposed sample |
| `post_run_capture` | `desktop_sample_validation_post_run_capture.v1`; copyable Markdown/checklist for post-run proof capture |
| `warnings` / `errors` | Non-blocking and blocking validation messages |
| `guardrail` | Evidence-only mutation boundary text |

Append writes the normalized record only when preview is `ok`. Its command result data includes `current_evidence`, `append_readiness`, `pilot_evidence_packet`, `post_run_capture`, `written`, and the same guardrail.

---

## Read Payload

`desktop_sample_validation_log.v1` reads the validation JSONL tail and combines it with current backend evidence:

| Field | Description |
|---|---|
| `records` / `record_count` | Recent parsed validation records |
| `summary` | Decision/proof/category/check/evidence counts and latest-record summary |
| `readiness` | Required evidence availability across Queue, Completed, Diagnostics, Pending Publish, Settings, and validation history |
| `reconciliation` | Recent records compared against current backend artifacts, with current/review/stale status |
| `worksheet_runs` | Bounded generated Markdown worksheet evidence under `docs\RealMediaValidationRuns` |
| `pilot_plan` | Read-only real-media pilot checkpoints plus `execution_checklist` rows |
| `cutover_gate` | Conservative WebView trial evidence posture, not a production cutover switch |
| `sample_set_guide` | Representative category coverage; current accepted records are required for ready category proof |
| `evidence_gap_summary` | Required and optional proof gaps across loaded validation evidence |
| `pilot_runbook` | Copyable, backend-authored runbook for one supervised real-media pilot |
| `policy_alignment` | Saved Settings policy posture mapped to pilot categories |
| `validation_audit` | Conservative roll-up over readiness, reconciliation, worksheets, sample set, policy, evidence gaps, runbook, and cutover posture |

All read payloads are advisory evidence. Historical accepted records and generated worksheets never become durable acceptance proof unless they still reconcile to current backend artifacts and operator manual checks.

---

## Size Limits

| Limit | Value |
|---|---|
| Maximum individual record size | 32 KB |
| Maximum request size for preview/append | 64 KB |
| Maximum recent records returned | 50 |
| Maximum validation log tail read | 512 KB |
| Maximum operator notes | 4000 characters |
| Maximum text field length | 600 characters |
| Maximum evidence items per evidence list | 24 |
| Maximum worksheet bytes read per file | 128 KB |
| Maximum worksheet runs shown | 20 |
| Maximum worksheet samples per run | 12 |

---

## Mutation Boundary

All Sample Validation routes are read-only except `POST /api/sample-validation/append`, whose only write is appending a JSONL evidence record under `State\Validation`. It does not mark jobs complete, clear failures, drain pending publish, publish outputs, rewrite manifests/sidecars, launch work, save settings, rename files, scan arbitrary media folders, delete files, or mutate source/output/scratch media.

---

## See Also

- Operator guide: `docs/sample-validation/SAMPLE_VALIDATION_RECORD_OPERATOR_GUIDE.md`
- Operator guide: `docs/sample-validation/SAMPLE_VALIDATION_RECORD_OPERATOR_GUIDE.md`
- Real-media pilot: `docs/sample-validation/REAL_MEDIA_PILOT_CHECKLIST.md`
- Evidence anchor: `docs/RealMediaValidationRuns/README.md`
- Source: `app/sample_validation/policy.py`
