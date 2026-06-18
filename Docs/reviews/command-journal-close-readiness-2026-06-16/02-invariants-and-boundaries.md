# Invariants And Boundaries

This document records the safety properties the current implementation appears to rely on. These invariants are the baseline used for the findings and remediation plan.

## Command Journal Invariants

1. Only `desktop_command_result.v1` payloads are eligible for backend command journal recording.

   Evidence: `command_journal_policy.py` lines 31-32 and `command_journal.py` lines 52-53.

2. Command journal entries are summaries, not full request or response bodies.

   Evidence: `command_journal.py` lines 23-28 and `command_journal_policy.py` lines 90-111.

3. The backend command journal is bounded.

   Evidence: `command_journal.py` lines 30-43 force a positive capacity; lines 45-64 trim entries; `command_journal_policy.py` lines 118-125 enforce output limits.

4. Loaded journal entries are sanitized and invalid entries are discarded.

   Evidence: `command_journal.py` lines 70-79 and `command_journal_policy.py` lines 128-152.

5. Sensitive evidence terms are redacted recursively within the bounded evidence shape.

   Evidence: `command_journal_policy.py` lines 18-28 and 61-84.

6. Backend command journal JSON persistence is best-effort by default.

   Evidence: `command_journal.py` lines 81-124 only raise save errors in strict mode; normal command recording passes `strict=False` unless the caller overrides.

7. SQLite mirroring is best-effort by design.

   Evidence: `command_journal.py` lines 126-134 swallow mirror exceptions after logging a warning.

## Strict JSON And Mutation Guard Invariants

1. Route-level payload validation occurs before mutation handlers run.

   Evidence: `handler.py` lines 98-113 and `api_commands.py` lines 414-499.

2. Mutation routes with safety-sensitive booleans use strict Pydantic payload models with `extra="forbid"`.

   Evidence: `api_commands.py` lines 17-25 and strict route mappings at lines 414-485.

3. Confirmation values must be real booleans, not truthy strings.

   Evidence: strict boolean fields in `api_commands.py` and tests in `test_api_command_contracts.py` lines 448-510.

4. Backend facades repeat the confirmation check before mutation.

   Evidence: rename, settings, schedule, file override, and network lifecycle facade checks listed in `01-code-map.md`.

5. Secret-transfer and explicitly unjournaled route validation failures must not be recorded with request bodies.

   Evidence: `handler_policy.py` lines 80-88 and tests in `test_api_command_contracts.py` lines 425-447.

## Duplicate-Command Invariants

1. Process launch commands share a non-blocking launch lock.

   Evidence: `guard_facade.py` lines 29-40 and `pipeline_facade.py` lines 99-105.

2. Active work is checked after the launch lock is acquired and before a new process starts.

   Evidence: `pipeline_facade.py` lines 99-105 and `audit_facade.py` lines 31-62.

3. Active work blockers include multiple independent sources, not just one process-state field.

   Evidence: `guard_facade.py` lines 62-103.

4. Duplicate command protection for launch-like commands should fail closed rather than queue a second launch silently.

   Evidence: tests in `test_application_facade_process_launch.py` lines 995-1035.

## Close-Readiness Invariants

1. Close-readiness is safe only when no active-work blocker is present and the computed state is non-blocking.

   Evidence: `guard_policy.py` lines 17-43.

2. Snapshot-unavailable state is unsafe.

   Evidence: `guard_policy.py` lines 17-43 and `test_facade_process_guard_policy.py` lines 43-59.

3. Unknown state with a snapshot and no blockers is treated as safe, but with an "unknown" reason.

   Evidence: `test_facade_process_guard_policy.py` lines 43-60. This is an intentional policy boundary, not a confirmed defect.

4. Fresh pipeline progress, fresh audit progress, ActiveJobs records, related processes, final-library promotion, queue source scan, and schedule-stop watcher state can all block close.

   Evidence: `guard_facade.py` lines 62-103 and supporting helper ranges in `01-code-map.md`.

5. Inspection failure for active-work sources should fail closed.

   Evidence: `guard_facade.py` lines 130-199 and `active_jobs.py` lines 272-324.

## Backend Shutdown Invariants

1. A safe backend shutdown request must refuse to shut down when close-readiness is unsafe.

   Evidence: `commands_process.py` lines 186-224 and `command_results.py` lines 217-257.

2. Confirmed force shutdown is explicit and encoded as `force_active_work_shutdown: true`.

   Evidence: `api_commands.py` line 480, `backend_process.rs` lines 475-480, and `commands_process.py` lines 186-224.

3. Confirmed force shutdown attempts backend cleanup before the process-tree termination fallback.

   Evidence: `commands_process.py` lines 165-184 and `backend_process.rs` lines 111-148.

4. WebView safe shutdown does not send the force flag.

   Evidence: `app.js` lines 399-422.

## Tauri Close Invariants

1. Tauri close must consult backend close-readiness before allowing normal close.

   Evidence: `backend_process.rs` lines 168-190.

2. If close-readiness is unsafe or unreadable, Tauri must ask for confirmation before force closing.

   Evidence: `backend_process.rs` lines 168-190.

3. Safe close is only allowed after safe backend shutdown is requested.

   Evidence: `lib.rs` lines 105-129 and `backend_process.rs` lines 111-148.

4. Destroyed and app exit events use safe-only backend shutdown.

   Evidence: `lib.rs` lines 130-142.

## Diagnostics And Command History Trust Invariants

1. UI command history distinguishes local pending/fetch-failure rows from backend journal rows.

   Evidence: `commandHistory.js` lines 530-567 and 874-887; `formatters.js` lines 55-72.

2. Command History should not present command-stream visibility as proof of success.

   Evidence: `commandHistory.js` lines 238-334.

3. Diagnostics opens are allowlisted and read-oriented.

   Evidence: `diagnostics.js` lines 179-201 and `diagnosticsView.js` lines 1848-1880.

4. Diagnostics and handoff text should direct users to live close-readiness state before exiting during active work.

   Evidence: `app/lifecycle.js` lines 909-934 and `diagnosticsView.js` lines 1090-1093.
