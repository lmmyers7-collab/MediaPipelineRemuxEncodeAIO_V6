# Network Worker/Coordinator Remediation Master Plan

Date: 2026-06-15

This document turns the post-hardening Network Worker/Coordinator review into
handoff-ready implementation plans. It is intentionally scoped to the remaining
issues found after the Batch 1-5 fixes and validation runs.

## Safety Position

The feature has real backend-owned lifecycle, launch-blocking, auth, redaction,
join, path-map, read DTO, Tauri metadata, and WebView contract hardening. It is
not ready for ordinary operator use until the remaining lifecycle and recovery
issues are fixed.

Do not change media policy, FFmpeg command generation, subtitle/audio policy,
publish/drain behavior, queue semantics, source/scratch/output movement, or
cleanup behavior while executing these plans unless a step explicitly requires
it and the validation rung is updated.

## Remaining Issues

| ID | Issue | Severity | Plan |
| --- | --- | --- | --- |
| REM-NCW-01 | Coordinator stop/dry-run ignores remote active claims in the in-flight registry. | P1 | `plans/01-lifecycle-drain-and-provider-cleanup.md` |
| REM-NCW-02 | Confirmed coordinator stop can shut down HTTP while remote workers still need heartbeat/done routes. | P1 | `plans/01-lifecycle-drain-and-provider-cleanup.md` |
| REM-NCW-03 | Worker provider can leave a half-attached runtime entry when `start_polling()` fails. | P1 | `plans/01-lifecycle-drain-and-provider-cleanup.md` |
| REM-NCW-04 | Coordinator provider can leave a partial dispatcher if post-construction loop startup fails. | P2 | `plans/01-lifecycle-drain-and-provider-cleanup.md` |
| REM-NCW-05 | Unreadable `worker_state.json` is deleted during startup even though poll-loop code would hold claims. | P1 | `plans/02-worker-state-and-result-strictness.md` |
| REM-NCW-06 | Local worker result and selected wire integer fields still coerce strings/floats or clamp negatives. | P2 | `plans/02-worker-state-and-result-strictness.md` |
| REM-NCW-07 | Worker local cluster-log mirror writes unredacted message text before coordinator-side redaction. | P2 | `plans/03-auth-redaction-ui-contract-cleanup.md` |
| REM-NCW-08 | WebView lifecycle stop tooltip still says stop may abort active worker work. | P3 | `plans/03-auth-redaction-ui-contract-cleanup.md` |
| REM-NCW-09 | Tests preserve some unsafe behavior and miss remote-active coordinator stop coverage. | P1 | all plans and `plans/04-acceptance-validation-runbook.md` |

## Execution Order

1. Lifecycle drain and provider cleanup.
   This is first because it protects active remote workers and prevents partial
   runtime state from blocking restart.

2. Worker-state recovery and result strictness.
   This prevents crash-recovery evidence loss and makes untrusted result fields
   deterministic.

3. Auth, redaction, and WebView contract cleanup.
   This removes the remaining evidence-copy mismatch and stale operator text.

4. Acceptance validation.
   Run the targeted test set, WebView browser smoke, PowerShell wrapper, and
   change-control validation after all fixes in the implementation batch.

## Change-Control Requirements

Each implementation pass must create or update one unreleased change packet
before edits. Record the exact source, test, doc, and generated-summary paths.
Use:

```powershell
apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.change_control.record_change_touch <CHANGE_ID> <paths...> --status in_progress
```

Before final response for any implementation batch, run:

```powershell
apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.change_control.validate_changes --require-worktree-coverage
```

## Common Non-Goals

- Do not introduce a new local launch path.
- Do not route Network lifecycle work through `/api/pipeline/start`.
- Do not let WebView or Tauri own claim, done, queue, settings persistence,
  publish/drain, or filesystem mutation policy.
- Do not weaken signed coordinator auth.
- Do not silently discard worker/coordinator state evidence.

## Overall Acceptance Criteria

- Coordinator stop dry-runs report remote active claims from the in-flight
  registry.
- Confirmed ordinary coordinator stop stops new claims but preserves heartbeat
  and done/reporting paths until active remote claims are terminal or repaired.
- Provider startup failures leave no stale runtime entries.
- Unreadable worker state is preserved or archived with bounded redacted
  diagnostics and blocks new claims until repaired.
- Present wrong-type integer fields are rejected rather than coerced.
- Worker local log mirror redacts token-like assignments and URL query/fragment
  secrets.
- WebView copy accurately describes cooperative stop behavior.
- Targeted Python, WebView, PowerShell, and change-control validation pass.
