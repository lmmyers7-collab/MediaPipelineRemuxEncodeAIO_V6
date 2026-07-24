# Sample Validation Record Evidence Operator Guide

Date: 2026-05-15

Short operator guide for Sample Validation records in the promoted current WebView/Tauri surface.

---

## Purpose

A Sample Validation record is an **operator evidence document** — it records what the operator personally verified about a specific real-media sample run. It does not mark jobs complete, suppress failures, drain pending publish, rewrite completed manifests or sidecars, change routing or audio/subtitle/size policy, or unblock Launch, drain, or rerun actions.

Think of it as a structured note: "I ran this file, I read this evidence, this is what I decided."

---

## What a Record Proves

| Field | What it represents |
|---|---|
| `proof_strength` | How strongly the completed output path matches the source/output proof captured at append time (`exact-path`, `partial-exact`, `filename-advisory`, `none`) |
| `operator_decision` | The operator's explicit conclusion at append time (`accepted`, `hold_review`, `rerun_backend`, `fallback_tk`) |
| `checks` | Which of the 9 standard checks the operator verified (queue route, FFmpeg log, subtitle, audio, completed output, sidecar manifest, size growth, pending publish, diagnostics) |
| `evidence` | Snapshots of Queue, Completed, Pending Publish, Diagnostics, and command evidence captured at preview/append time |

A record with `proof_strength: exact-path` and all required checks confirmed means the operator read and agreed with specific backend evidence at a specific point in time. It does **not** mean the backend will behave the same way on a different file or after a settings change.

---

## When to Record

Record a sample validation note after a small real-media sample run when **all** of the following are true:

1. The sample run has fully completed (a Completed row exists for the source).
2. You have read Queue route evidence, Completed output/sidecar proof, and Diagnostics/run logs for this source.
3. You have read the backend-authored Sample Validation Readiness payload on the Home page and it shows no blocking errors.
4. You have inspected the evidence packet in the Preview Patch panel (Home → Sample Validation → Preview) and it matches your inspection.

Do not record before a run completes. Do not record if the Readiness payload blocks append (it will show the blocking reason).

The former `Test-TauriShell-PG2SampleValidationAppend.ps1` automatic append flow is disabled and fails closed. It constructed exact media claims from caller-provided paths instead of backend evidence. Use `/api/sample-validation/preview` through Home → Sample Validation, inspect the named files and current Queue/Completed/Pending/Diagnostics evidence, then append only through the operator-controlled WebView flow. Automation must remain unavailable until a backend-authored, run-bound provenance projection replaces those caller assertions.

---

## What `stale`, `current`, and `review` Mean

These statuses appear on the Home page for recent historical records and indicate whether the record still matches current backend evidence.

| Status | Meaning | Safe action |
|---|---|---|
| **current** | The source/output paths in the record still match a Completed row and the current Queue/Completed/Pending/Diagnostics proof agrees with the recorded decision. | Use the record as historical evidence for this file. |
| **stale** | Backend artifacts have changed since the record was written — the file was re-queued, re-encoded, the Completed row changed, or the pending-publish posture changed. The old record describes a different backend state. | Do not treat this record as proof for the current run. Re-inspect evidence and record a new note if the new run is complete. |
| **review** | The operator chose `hold_review` at append time, or the reconciliation backend found a mismatch that requires attention. The record is not automatically disqualifying, but the operator flagged it as needing follow-up. | Read the reconciliation detail and decide whether to accept, rerun, or fall back to the external rollback workspace. |

---

## Safe Next Action

The evidence packet's `safe_next_action` field tells the operator what the backend recommends before deciding to append. Common values:

| `safe_next_action` | Meaning |
|---|---|
| `inspect_and_append` | Readiness payload is clear; all required evidence checks are visible; operator may append if satisfied. |
| `inspect_before_append` | At least one optional check is missing or one evidence item is uncertain; read the callout before appending. |
| `wait_for_completion` | The source is still in active work or has no Completed row yet. Do not append until the run is done. |
| `review_before_append` | The backend found at least one discrepancy (route mismatch, stale Completed row, pending-publish posture changed). Read the specific callout and reconcile before appending. |

The `safe_next_action` is guidance only — the backend does not block append if the operator proceeds. The operator is responsible for reading the evidence before appending.

---

## Mutation Boundary

| Action | Owner | Frontend role |
|---|---|---|
| Writing the `.jsonl` record to `State\Validation\sample_validation_log.jsonl` | **Backend** (`facade_sample_validation_policy.py`) | None — frontend cannot choose the write path or write directly |
| Preview (read-only evidence packet, `sample_validation_preview.v1`) | Backend (GET route) | WebView calls `/api/sample-validation/preview` read-only; displays result |
| Append (POST) | Backend — guarded by the facade's sample-validation lock | WebView sends operator fields; backend validates, normalizes, writes, returns command result |
| Tailing the validation log | Backend (Diagnostics allowlisted tail) | Diagnostics tail opens bounded log read via backend |

The frontend **never** receives an output path for the log, cannot choose a write destination, and cannot mutate completed manifests, sidecars, or queue state through this route.

### What records do NOT do

- Do not mark a job complete or mark a failure as cleared.
- Do not drain pending publish or approve a drain.
- Do not rewrite Completed manifests or sidecar files.
- Do not change routing, subtitle, audio, size, or publish policy.
- Do not unblock Launch, drain, rerun, cleanup, or delete actions.
- Do not override backend diagnostics or allowlist decisions.
- Do not treat sample evidence as approval to remove the external rollback workspace.

---

## Privacy Warning — Validation Log

`State\Validation\sample_validation_log.jsonl` records contain personal machine paths (`source_path`, `output_path`) and operator notes. Treat this file as operator-private:

- Do not commit it to a shared or public git repository.
- The release builder excludes the entire `LocalBase\` tree (including `LocalBase\State\*`) by default, so clean release packages will not include it.
- `.gitignore` has no explicit entry for this file. If this workspace is tracked in git, add `LocalBase/State/Validation/sample_validation_log.jsonl` (or `LocalBase/State/`) to `.gitignore` before staging any working tree state.
- If the log contains paths you do not want to share, delete it or keep it out of any commits. Records are append-only — there is no edit or delete route.

---

## Reading Records in the WebView

| Panel | Where | What it shows |
|---|---|---|
| Sample Validation Record | Home page | Recent records list, reconciliation status (current/stale/review), operator decision badges |
| Sample Validation Readiness | Home page | Backend explanation of whether enough Queue/Completed/Pending/Diagnostics/Settings evidence is present to record a useful note |
| Sample Execution Checklist | Home page + Launch page | Backend-authored checklist of evidence items to read before and after a sample run; selectable rows with detail |
| Evidence Packet preview | Home page → Preview button | Snapshot of route/output/log/publish/media proof plus append readiness before committing |

---

## See Also

- Payload schema reference: `docs/sample-validation/SAMPLE_VALIDATION_PAYLOAD_SCHEMA_REFERENCE.md`
- End-to-end real-media pilot: `docs/sample-validation/REAL_MEDIA_PILOT_CHECKLIST.md`
- Payload schema reference: `docs/sample-validation/SAMPLE_VALIDATION_PAYLOAD_SCHEMA_REFERENCE.md`

---

## Task Output

```
Task ID: CLN3-002
Files inspected: retired sample-validation design/playbook notes, src\mediapipeline\core\sample_validation\policy.py
Files changed: docs\sample-validation\SAMPLE_VALIDATION_RECORD_OPERATOR_GUIDE.md (created)
Validation: Test-Path docs\sample-validation\SAMPLE_VALIDATION_RECORD_OPERATOR_GUIDE.md; Select-String -Path docs\sample-validation\SAMPLE_VALIDATION_RECORD_OPERATOR_GUIDE.md -Pattern "does not accept|does not launch|read-only|operator evidence"
Findings: Guide created with purpose, when to record, stale/current/review meaning, safe next action, and mutation boundary sections.
Open questions: None.
Risk: Low — documentation only.
```
