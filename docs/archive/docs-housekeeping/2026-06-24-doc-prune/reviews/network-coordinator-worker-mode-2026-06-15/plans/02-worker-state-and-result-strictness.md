# Plan 02 - Worker State And Result Strictness

Date: 2026-06-15

## Goal

Preserve crash-recovery evidence and make worker result/protocol integer
handling strict without changing media processing policy.

## Findings Covered

- REM-NCW-05: unreadable `worker_state.json` is deleted during startup.
- REM-NCW-06: selected integer fields still coerce strings/floats or clamp
  negative values.
- REM-NCW-09: existing tests assert the unsafe unreadable-state deletion path.

## Primary Files

- `src/mediapipeline/desktop/network/worker_state.py`
- `src/mediapipeline/desktop/network/worker.py`
- `src/mediapipeline/desktop/network/protocol.py`
- `src/mediapipeline/desktop/application/network_lifecycle_provider.py`
- `tests/python/desktop/test_network_crash_recovery.py`
- `tests/python/desktop/test_network_worker_runtime.py`
- `tests/python/desktop/test_network_worker_state.py`
- `tests/python/desktop/test_network_protocol_runtime.py`

## Implementation Steps

1. Preserve unreadable worker state at startup.
   - Change `WorkerStateMixin._crash_recover()` so JSON read failure does not
     call `_clear_worker_state()`.
   - Log a bounded redacted diagnostic.
   - Leave the file in place so `_flush_pending_done_report()` blocks claims.
   - If an archive is added, keep a blocking marker or replacement state file
     so the worker cannot overwrite a single-slot pending report silently.

2. Surface startup block status.
   - Store a token-safe startup recovery warning on the dispatcher if needed,
     for example `_worker_state_startup_error`.
   - Let existing read DTOs continue to mark malformed `worker_state.json` as
     `unreadable`.
   - Avoid introducing a WebView-owned repair action.

3. Keep compatible defaults while rejecting bad present fields.
   - For local worker result artifacts, keep optional fields optional.
   - When `ElapsedSeconds` or `OutputSizeBytes` is present, require
     `type(value) is int` and `value >= 0`.
   - Do not accept bool, string, float, null, or negative values for present
     integer fields.

4. Tighten wire DTO integer parsing where untrusted input is accepted.
   - Replace broad `coerce_nonnegative_int()` use in done/heartbeat parsing
     with strict helpers.
   - Preserve backwards compatibility for missing optional fields only.
   - Confirm `ClaimResponse.from_dict()` remains strict for booleans and
     `retry_after_seconds`.

5. Update tests that preserve old behavior.
   - Replace `test_crash_recover_uses_guarded_clear_for_unreadable_state` with
     a test proving the unreadable file remains and no done/report is posted.
   - Add a poll-loop test proving the preserved unreadable state blocks claim.

## Regression Tests

Add or update:

- `test_crash_recover_preserves_unreadable_state_and_does_not_post_done`
- `test_worker_start_with_unreadable_state_blocks_claim_before_http_get`
- `test_local_worker_result_rejects_string_integer_fields`
- `test_local_worker_result_rejects_float_integer_fields`
- `test_local_worker_result_rejects_negative_integer_fields`
- `test_done_request_rejects_bool_string_float_integer_fields`
- `test_heartbeat_request_rejects_bool_string_float_integer_fields`
- `test_claim_response_strict_boolean_integer_regression`

## Validation Commands

```powershell
$env:PYTHONPATH=(Resolve-Path 'src').Path
apps/desktop/runtime/Python/python.exe -m unittest tests.python.desktop.test_network_crash_recovery tests.python.desktop.test_network_worker_runtime tests.python.desktop.test_network_worker_state tests.python.desktop.test_network_protocol_runtime
```

Run the common acceptance validation in
`plans/04-acceptance-validation-runbook.md` after all plans are complete.

## Rollback Plan

Revert worker-state, protocol, result-parser, and focused test changes. Confirm
pending done recovery and worker runtime tests return to their previous passing
state.

## Acceptance Criteria

- Unreadable worker state is never silently deleted during startup.
- A preserved unreadable state blocks new claims before any claim HTTP request.
- Present wrong-type integer fields are rejected with bounded redacted errors.
- Missing optional fields keep documented defaults.
