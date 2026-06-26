# Findings

## CJ-001 - High - Backend command route exceptions are absent from the persisted command journal

Status: confirmed  
Area: command recording, failure evidence, Diagnostics/Command History trust

### Evidence

- `handler.py` lines 114-117 convert unexpected route exceptions into sanitized 500 route exception responses.
- `handler_policy.py` lines 55-57 build route-exception payloads that are not `desktop_command_result.v1`.
- `handler.py` lines 152-153 record command journal entries only when `should_record_command_payload(status)` is true.
- `handler_policy.py` lines 91-92 return true only for statuses below 400.
- `command_journal.py` lines 52-53 ignore non-command-result payloads.

### Impact

A journaled command route can fail inside the backend and return a sanitized 500 to the caller, but the backend command journal will not persist a failed command row. If the frontend catches the failure, the UI may append a local row, but that row is not durable and disappears on refresh/restart. If the caller is not the WebView, `/api/commands` may show no command failure at all.

That creates misleading command evidence: Diagnostics and Command History can under-report backend command failures while server logs contain the only durable evidence.

### Why Severity Is High

The user explicitly classified misleading command evidence as high severity. This finding can cause operators to trust an incomplete backend command history after a real command failure.

### Recommended Fix

For journaled command routes, convert route exceptions into a sanitized command-result journal entry before sending the 500 response. The journal entry should:

- use schema `desktop_command_result.v1`
- use a command such as `local_api.route_exception` or the route-specific command where safely known
- set `ok: false`
- set `severity: error`
- include bounded `path`, `error_id`, and redacted request evidence
- preserve suppression for `journaled: false` and `effect: secret-transfer`
- avoid writing full exception text or secret-bearing request bodies

Add a regression test that triggers a route exception and verifies `/api/commands` contains the failed evidence row.

## CJ-002 - Medium - Command journal persistence failures are invisible to Command History users

Status: confirmed  
Area: command recording, bounded history, durability evidence

### Evidence

- `command_journal.py` lines 45-64 insert the new entry into memory before saving and only roll back if an exception escapes.
- `command_journal.py` lines 116-124 log save failures but only raise when `strict=True`.
- Normal command recording from `handler.py` lines 147-153 does not pass strict mode.
- `command_journal.py` lines 126-134 log and swallow SQLite mirror failures.
- `/api/commands` returns the in-memory command history mapping at `read_payloads_status.py` lines 128-129 without persistence status metadata.

### Impact

If the JSON journal save fails in non-strict mode, the current process can still show the row as a backend journal entry, but that row may be lost on restart. Operators have no visible indication that command evidence is degraded or memory-only.

### Why Severity Is Medium

The journal is bounded recent evidence rather than a complete audit log, and command execution itself is not caused by this issue. The trust risk is real but narrower than CJ-001 because the command row exists until process restart.

### Recommended Fix

Surface journal durability state. Acceptable approaches:

- return `journal_persistence` metadata from `/api/commands`
- attach a warning to command results when journal save/mirror fails
- make selected high-risk mutation command journal writes strict and fail the command if the evidence cannot be persisted before mutation is acknowledged

Add tests for JSON save failure and SQLite mirror failure behavior.

## CH-001 - Medium - Command History dedupe can collapse repeated identical local failures

Status: confirmed  
Area: Command History trust

### Evidence

- `commandHistory.js` lines 507-528 append local command rows with timestamps and cap history.
- `commandHistory.js` lines 530-545 convert backend journal entries into non-local rows.
- `commandHistory.js` lines 549-567 merge rows using `command|result|message` as the dedupe signature.

### Impact

Repeated identical local failures, such as two failed clicks or two identical fetch failures before backend evidence arrives, can collapse into one displayed row. That can understate repeated failed attempts.

### Why Severity Is Medium

The UI does label local vs journal rows, and this does not mutate backend state. However, the reviewed area is command evidence trust, and repeated failure counts can matter during incident review.

### Recommended Fix

Strengthen merge identity:

- include a request id, command id, or normalized submitted request hash when available
- include timestamp buckets only when replacing a local row with a confirmed backend journal row
- avoid deduping two local-only failures solely by command/result/message

Add a WebView unit or smoke test for repeated identical local failures.

## VAL-001 - Medium - Live Tauri active-work close behavior is not fully validated by automated tests

Status: confirmed coverage gap  
Area: shutdown safety, active encode/process detection, Tauri close behavior

### Evidence

- `test_tauri_pg1_close_adversarial_scaffold.py` lines 1-24 states that the test is a static scaffold and does not launch live Tauri or real media.
- The existing coverage matrix describes process lifecycle tests as using simulated process records rather than launching real media.
- Tauri close code is guarded in `backend_process.rs` and `lib.rs`, but current automated coverage does not exercise the full GUI close path with an active encode subprocess.

### Impact

The code is designed to prevent silent unsafe close, but a regression in live Tauri event handling, process-tree cleanup, or host process inspection could escape unit/static coverage.

### Why Severity Is Medium

No unsafe close bug was confirmed in source. The gap matters because unsafe close during active work would be high severity if present.

### Recommended Fix

Add an automated or release-gated live close test:

- launch Tauri with a temp backend
- start a long-running controlled process/encode fixture
- attempt close and assert safe close is denied or confirmation is required
- cancel and assert the process remains alive
- confirm force and assert `force_active_work_shutdown: true` is sent and cleanup occurs

## Non-Findings

No confirmed unguarded `confirm_apply` or `confirm_save` mutation path was found in the reviewed surfaces.

No confirmed silent unsafe Tauri close path was found. The normal close path checks close-readiness, blocks safe shutdown on unsafe readiness, and requires confirmation for force close.

No confirmed secret-transfer validation journal leak was found. The current code suppresses validation-failure journaling for secret-transfer routes and redacts `join_blob` evidence.
