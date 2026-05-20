# V5 Sample Validation Artifact Design

Purpose: define and track the safe backend-owned artifact for recording real-media WebView/Tauri validation evidence without turning operator notes into a "force success" mechanism.

Status: implemented as a constrained V5 backend-owned evidence log. The local API now supports preview, append, recent-record read routes, a backend-authored read summary with decision/proof/check/evidence counts plus latest-record posture, a read-only validation readiness payload that explains whether enough Queue, Completed, Diagnostics, Pending Publish, Settings, and validation-log evidence is present to record a useful sample note, a read-only stale-evidence reconciliation payload that compares recent records against current backend artifacts, a read-only real-media pilot plan that tells the operator what to check before and after a small sample run, a read-only generated worksheet evidence payload for Markdown files under `Docs\RealMediaValidationRuns`, a read-only `desktop_real_media_policy_alignment.v1` roll-up that maps saved Settings media-policy readiness to pilot categories, a read-only `desktop_real_media_validation_audit.v1` roll-up over readiness/reconciliation/worksheet/sample-set/policy/evidence-gap/runbook/cutover evidence, and a preview-time `desktop_sample_validation_evidence_packet.v1` packet that summarizes the selected sample's route/output/log/publish/media proof before append. WebView Home can preview/append records from the selected sample evidence, read the summary, show proposed coverage plus backend readiness/pilot/worksheet/policy/audit guidance before append, and flag historical records whose current Queue/Completed/Pending/Diagnostics proof no longer matches. Diagnostics can tail/open the allowlisted validation log. There is still no acceptance flag, manifest mutation, media policy change, publish/drain signal, launch unblock, source/output mutation, arbitrary media scan, or daily-driver approval behavior.

## Why This Exists

The WebView now has:

- selected-row real-media traces on Queue, Completed, Pending Publish, Diagnostics ActiveJobs, and Diagnostics logs
- Home Cross-Page Sample Evidence Correlation
- a manual Validation Log Template
- the observational `V5_REAL_MEDIA_VALIDATION_PLAYBOOK.md`

Those tools help the operator compare loaded backend evidence, but the resulting validation decision is still manual and ephemeral. A persisted artifact may become useful after enough real sample runs prove that the manual checklist is helpful but too easy to lose.

## Non-Goals

A sample validation artifact must not:

- mark a job complete
- suppress a failure marker
- mark pending publish drained
- rewrite Completed manifests or sidecars
- change routing, subtitle, audio, size, or publish policy
- unblock Launch, drain, rerun, cleanup, or delete actions
- override backend diagnostics
- provide arbitrary path write access from WebView
- replace the external rollback workspace

The artifact is evidence documentation only.

## Storage

Implemented location:

`LocalBase\State\Validation\sample_validation_log.jsonl`

Rationale:

- lives with runtime state, not inside source/output media folders
- can be excluded from clean release packages
- append-only JSONL keeps individual entries small and avoids rewriting a large document
- can be tailed by Diagnostics using a future backend allowlisted target

**Privacy warning**: `sample_validation_log.jsonl` records contain `source_path` and `output_path` fields — personal machine paths. Do not commit this file to a shared git repository. The release builder excludes `LocalBase\State\*` by default, but `.gitignore` has no explicit entry for this file. If this workspace is tracked in git, add `LocalBase/State/Validation/sample_validation_log.jsonl` (or `LocalBase/State/`) to `.gitignore` before committing any working tree state.

Writes are backend-owned and guarded by the application facade's sample-validation lock. Records are appended as strict JSONL with flush/fsync. The frontend never sends an output path for the log and cannot choose the write destination.

## Record Shape

Schema name:

`sample_validation_record.v1`

Required fields:

```json
{
  "schema": "sample_validation_record.v1",
  "created_at": "2026-05-13T00:00:00Z",
  "created_by": "operator",
  "shell": "webview",
  "app_version": "v5.000",
  "source_path": "",
  "output_path": "",
  "sample_label": "",
  "proof_strength": "exact-path|partial-exact|filename-advisory|none",
  "operator_decision": "accepted|hold_review|rerun_backend|fallback_tk",
  "checks": {
    "queue_route_checked": false,
    "ffmpeg_log_checked": false,
    "subtitle_checked": false,
    "audio_checked": false,
    "completed_output_checked": false,
    "sidecar_manifest_checked": false,
    "size_growth_checked": false,
    "pending_publish_checked": false,
    "diagnostics_checked": false
  },
  "evidence": {
    "queue": [],
    "completed": [],
    "pending_publish": [],
    "diagnostics": [],
    "commands": []
  },
  "operator_notes": ""
}
```

Optional fields:

- `route_reason`
- `route_action`
- `encoder`
- `subtitle_summary`
- `audio_summary`
- `source_size_bytes`
- `output_size_bytes`
- `size_growth_percent`
- `pending_manifest_path`
- `completed_manifest_row_key`
- `command_ids`
- `diagnostics_target_keys`

## API Boundary

| Route | Method | Effect | Notes |
|---|---:|---|---|
| `/api/sample-validation/preview` | `POST` | read-only | Implemented. Validates a proposed record and returns normalized fields, warnings, missing evidence, current-backend evidence, append readiness, and a read-only `desktop_sample_validation_evidence_packet.v1` pilot packet. Does not write. |
| `/api/sample-validation/append` | `POST` | validation-log-write | Implemented. Appends a record under `State\Validation` and returns the same preview/readiness/pilot-packet context for operator feedback; does not mutate media, manifests, sidecars, queue, pending publish, launch state, or failures. |
| `/api/sample-validation` | `GET` | read-only | Implemented. Returns recent validation records with a strict limit, a backend-authored `desktop_sample_validation_summary.v1` posture summary, `desktop_sample_validation_readiness.v1`, `desktop_sample_validation_reconciliation.v1`, `desktop_real_media_pilot_plan.v1`, `desktop_real_media_execution_checklist.v1` rows, `desktop_real_media_worksheet_runs.v1` generated worksheet evidence, `desktop_real_media_sample_set_guide.v1`, `desktop_real_media_evidence_gap.v1`, `desktop_real_media_pilot_runbook.v1`, `desktop_real_media_policy_alignment.v1`, and `desktop_real_media_validation_audit.v1` conservative roll-up evidence. |
| `/api/diagnostics/open` target `sample_validation_log` | `POST` | allowlisted open | Implemented through the existing diagnostics target allowlist. |
| `/api/diagnostics/tail` target `sample_validation_log` | `GET` | bounded read | Implemented through the existing diagnostics tail route. |

The WebView must not write the JSONL file directly.

## Validation Rules

Backend preview/append should reject or warn when:

- `schema` is missing or unknown
- `source_path` and `output_path` are both empty
- all evidence arrays are empty
- `operator_decision` is unknown
- a filename-only advisory proof is being recorded as accepted without explicit note
- Completed evidence is absent but decision is `accepted`
- Pending Publish has visible blockers but decision is `accepted`
- Diagnostics has fresh error/failure evidence but decision is `accepted`
- any path is outside known source/output/scratch/pending/log state roots when a path is expected to be rooted
- record size exceeds a strict cap

Warnings should not automatically block every note. The key is that the artifact remains evidence and never changes pipeline behavior.

## Reconciliation Model

Implemented read summary:

- `operator_status`: `not-started`, `empty`, `review`, `blocked`, or `evidence-present`
- decision counts for `accepted`, `hold_review`, `rerun_backend`, and `fallback_tk`
- proof-strength counts for `exact-path`, `partial-exact`, `filename-advisory`, and `none`
- per-check coverage counts for route, log, subtitle, audio, completed output, sidecar/manifest, size growth, pending publish, and diagnostics
- evidence-array totals for Queue, Completed, Pending Publish, Diagnostics, and Commands
- latest-record summary and safe next action

Implemented read-only readiness:

- `schema_version`: `desktop_sample_validation_readiness.v1`
- `operator_status`: `blocked`, `not-ready`, `review`, or `ready-to-record`
- required evidence counts and missing required evidence
- warning/blocker counts
- per-row readiness details for Queue route evidence, Completed output proof, Diagnostics run log proof, Pending Publish posture, Settings workspace posture, and validation-log availability
- summary lines and safe next action for the WebView Home panel
- guardrail text stating that readiness evidence is read-only and never accepts output or mutates media/state

Implemented read-only stale-evidence reconciliation:

- `schema_version`: `desktop_sample_validation_reconciliation.v1`
- `operator_status`: `not-started`, `current`, `review`, `stale`, `blocked`, or `unknown`
- bounded artifact counts for Queue sources, Completed sources/outputs, Pending Publish path clues, and Diagnostics log availability
- per-record `current`, `review`, `stale`, or `unknown` status for recent records
- exact current-match booleans for Queue source, Completed source, Completed output, Pending Publish source/output clues, and Diagnostics source/output clues
- missing-current-evidence notes when historical records no longer match current manifests/logs
- safe next action and guardrail text stating reconciliation is historical evidence comparison only

Future read views can compare validation records against current backend state:

- source path still appears in Queue or Completed evidence
- Completed row still points at the recorded output
- Pending Publish source/output clues do not indicate that an accepted sample is still parked
- latest Diagnostics/RunLogs still contain source/output clues for records that claimed log proof
- output size still matches recorded size within tolerance, if future sidecar/manifest comparison is added

Reconciliation mismatches should be displayed as stale validation evidence, not as processing failure by themselves.

Implemented read-only real-media pilot plan:

- `schema_version`: `desktop_real_media_pilot_plan.v1`
- `operator_status`: `blocked`, `pilot-needed`, `stale-history`, `review`, `current-evidence`, or `ready-for-pilot-record`
- per-stage operator rows for selecting a sample, confirming saved media policy, running only through backend-owned Launch, verifying Completed output/sidecar, reading Diagnostics/run logs, reviewing Pending Publish, and recording the evidence-only validation note
- backend-owned checkpoint counts: required stages, ready stages, manual stages, attention stages, blocked stages, and review stages
- `pilot_attention` and `next_required_action` fields so the UI can show the first operator task to resolve before trusting the pilot
- stop conditions for source mutation, unsafe close-readiness, missing output/sidecar proof, subtitle/audio/size policy disagreement, and Pending Publish blockers
- safe next action and guardrail text stating that the plan cannot launch work, accept outputs, repair state, publish, rename, rewrite manifests, or touch media

Implemented preview-time pilot evidence packet:

- `schema_version`: `desktop_sample_validation_evidence_packet.v1`
- derived only from the normalized proposed record, current backend evidence, and append-readiness payload
- row checks for sample identity, Queue route proof, Completed output/sidecar proof, Diagnostics/run-log proof, Pending Publish posture, playback/subtitle/audio/size proof, and evidence-record readiness
- counts for required/recommended manual checks plus ready/review/blocked packet rows
- stop conditions that tell the operator when not to trust or append an accepted sample note
- guardrail text stating that the packet cannot mark jobs complete, accept outputs, clear failures, drain Pending Publish, rewrite manifests/sidecars, launch work, save settings, rename files, or mutate source/output/scratch media

Implemented read-only generated worksheet evidence:

- `schema_version`: `desktop_real_media_worksheet_runs.v1`
- source folder: only `Docs\RealMediaValidationRuns` under the resolved workspace/app root
- bounded run list, sample rows, and WebView pilot evidence packet rows from generated Markdown worksheets
- per-run operator status, sample count, packet-row count, selected-sample match support in WebView, warnings/errors, and safe next action
- guardrail text stating that worksheet evidence is read-only Markdown context and cannot append records, accept output, clear failures, launch work, drain Pending Publish, save settings, rename files, rewrite manifests/sidecars, scan arbitrary media folders, or touch source/output/scratch media

## UI Model

Implemented safe UI:

- The existing manual Validation Log Template remains visible.
- Home now has a `Sample Validation Record` panel with decision, notes, Preview Record, Append Evidence Record, and recent-record readback.
- Home now shows proposed evidence coverage before preview/append and backend-authored history posture after reading recent records.
- Home now renders backend-authored validation readiness lines before recent-record history, including required evidence counts, missing blockers, warning/review rows, and safe next action.
- Home now renders backend-authored stale-evidence reconciliation lines before recent-record history and includes current-evidence status in selected record detail.
- Home now renders backend-authored real-media pilot plan lines so the operator sees pre-run and post-run evidence checkpoints, checkpoint counts, attention rows, and the next required action before recording a validation note.
- Home now renders backend-authored generated worksheet evidence so the operator can see whether a Markdown worksheet exists for the selected sample, how many sample/packet rows were captured, and which worksheet needs review before appending validation notes.
- Home preview now renders the backend-authored pilot evidence packet before append-readiness so a selected sample's route/output/log/publish/media proof is visible before an evidence note is written.
- The Home Real-Media Validation Worksheet now also summarizes Sample Validation readiness, reconciliation, pilot status, record count, accepted count, and sample-run requirement beside Queue, Completed, Pending Publish, Diagnostics, and Settings proof.
- Records are built from already-loaded Queue, Completed, Pending Publish, Diagnostics, and worksheet evidence.
- Append requests call the backend route only; WebView does not write JSONL directly.
- Accepted decisions require an extra confirmation and still only append evidence.
- Recent records are shown as read-only operator evidence.

Unsafe UI to avoid:

- Accept Output
- Force Success
- Mark Complete
- Clear Failure From Validation
- Drain From Validation
- Rewrite Sidecar From Validation

## Test Coverage

- Route contract exposes sample-validation routes and their effects.
- Append rejects malformed schema.
- Append rejects oversized records.
- Append writes only under `State\Validation\sample_validation_log.jsonl`.
- Read payload includes backend-authored decision/proof/check/evidence counts and latest-record posture.
- Read payload includes backend-authored `desktop_sample_validation_readiness.v1` readiness status and required-evidence guidance.
- Read payload includes backend-authored `desktop_sample_validation_reconciliation.v1` current/stale historical-evidence status.
- Read payload includes backend-authored `desktop_real_media_pilot_plan.v1` pilot status, stage rows, checkpoint counts, attention rows, next required action, stop conditions, and mutation guardrails.
- Read payload includes backend-authored `desktop_real_media_worksheet_runs.v1` generated worksheet status, bounded sample rows, bounded pilot packet rows, safe next action, and mutation guardrail.
- Preview/append payloads include backend-authored `desktop_sample_validation_evidence_packet.v1` status, proof rows, stop conditions, safe next action, and mutation guardrail.
- Append does not touch watched source, output, completed manifest, queue snapshot, or pending publish manifest files in the regression fixture.
- The validation log is exposed through diagnostics tail/state-summary as `sample_validation_log`.
- WebView append requires the backend token.
- WebView static coverage proves controls call `/api/sample-validation/preview` and `/api/sample-validation/append`.
- Browser-backed Sample Validation coverage proves generated worksheet rendering, selected-sample worksheet matching, the pilot evidence packet during preview, and that preview still does not append evidence or post mutation routes.
- Command-history static coverage proves append results are owned by `Home / Validation` and point at `sample_validation_log`.
- Tauri startup asset validation now checks the sample-validation Home panel and route fragments.
- Release self-test layout now requires the sample-validation backend modules.

## Rollout Criteria

The first implementation is intentionally narrow because the manual template and worksheet had enough structure to build a safe evidence-only record. Do not extend this into backend acceptance, auto-pass/fail, launch unblocking, repair, or publish behavior without a separate design and regression plan.

## Current Recommendation

Use this only as an operator evidence log while testing WebView/Tauri with known samples. Treat every record as stale until current Queue, Completed, Pending Publish, Diagnostics, and playback evidence still agree. The backend summary helps find the latest decision and coverage gaps, but the next safe improvement would still be read-only reconciliation that labels records stale when current backend state no longer matches recorded source/output evidence.
