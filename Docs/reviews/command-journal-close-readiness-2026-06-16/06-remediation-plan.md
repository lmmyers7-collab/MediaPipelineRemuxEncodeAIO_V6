# Remediation Plan

## Priority 1: Persist Sanitized Evidence For Backend Command Route Exceptions

Finding: CJ-001  
Risk addressed: misleading command evidence

Implementation outline:

1. Extend the local API handler exception path for command routes.
2. When a route exception occurs after route metadata is known, build a sanitized `desktop_command_result.v1` journal payload.
3. Respect route metadata:
   - do not include secret-transfer request bodies
   - do not journal routes marked `journaled: false`
4. Include bounded evidence only:
   - route path
   - error id
   - command name if safely known
   - redacted/bounded submitted request when allowed
5. Record the payload before sending the 500 response.
6. Add regression tests for:
   - journaled route exception creates failed command history
   - secret-transfer route exception does not leak request body
   - unjournaled route exception remains unjournaled
   - route exception response remains sanitized

Acceptance criteria:

- `/api/commands` shows a failed command row after a journaled command route exception.
- The row contains no raw secret material.
- Existing strict JSON behavior remains unchanged.

## Priority 2: Surface Journal Persistence Degradation

Finding: CJ-002  
Risk addressed: false confidence in durable command evidence

Implementation options:

Option A: metadata-only

- Track last JSON save status and last SQLite mirror status in `CommandJournal`.
- Include bounded metadata in `/api/commands`, such as:
  - `persistence.ok`
  - `persistence.json_last_error`
  - `persistence.sqlite_last_error`
  - `persistence.memory_only_since`

Option B: command-result warning

- When a journal save or mirror fails, add a bounded warning to the command result or command history output.

Option C: strict high-risk commands

- For selected high-risk mutation commands, require journal persistence success before reporting mutation success.
- Use carefully because command execution and evidence persistence currently have looser coupling.

Recommended approach:

- Start with Option A for visibility.
- Add Option C only for commands where the product requirement is explicit that no acknowledged mutation should occur without durable command evidence.

Acceptance criteria:

- Operators can see when backend command evidence is memory-only or mirror-degraded.
- Persistence errors do not expose paths or exception details beyond bounded diagnostics-safe text.
- Tests cover save failure, mirror failure, and recovery.

## Priority 3: Strengthen Command History Dedupe Identity

Finding: CH-001  
Risk addressed: undercounted repeated local failures

Implementation outline:

1. Add a stable request identity where commands are submitted, such as `request_id`.
2. Include that identity in local command history rows.
3. Include a corresponding identity in backend command journal summaries where safe.
4. Replace local rows with backend rows only when identity matches.
5. If no identity exists, avoid deduping two local failures only by command/result/message.

Acceptance criteria:

- Two identical local failures at different times remain visible as two attempts.
- A backend journal row can still replace its matching local pending row.
- Existing local/backend source labels remain visible.

## Priority 4: Add Live Tauri Active-Work Close Validation

Finding: VAL-001  
Risk addressed: unsafe close regression escaping static tests

Implementation outline:

1. Build a temp backend fixture that exposes close-readiness and backend shutdown endpoints.
2. Launch Tauri against that backend.
3. Start a controlled long-running child process or encode fixture.
4. Exercise close:
   - safe close while active must be denied or prompt
   - canceling confirmation must keep backend and child process alive
   - confirmed force must send `force_active_work_shutdown: true`
   - confirmed force must clean up or terminate the process tree
5. Store logs and screenshots under the existing validation artifact pattern.

Acceptance criteria:

- The test fails if unsafe close proceeds without confirmation.
- The test fails if cancellation still exits.
- The test fails if confirmed force omits the force flag.
- The test produces enough artifacts to debug failures.

## Priority 5: Keep Strict Mutation Guard Coverage Current

Finding: no current defect, preventive remediation  
Risk addressed: future accidental mutation path

Implementation outline:

1. Add a checklist item for every new mutation route:
   - strict contract model
   - `extra="forbid"`
   - strict boolean confirmation if it mutates state
   - facade-level confirmation check
   - WebView confirmation payload test
   - command journal policy decision
2. Keep `tests/python/desktop/test_api_command_contracts.py` as the central route-contract tripwire.
3. Keep WebView static mutation boundary tests as the frontend tripwire.

Acceptance criteria:

- A new mutation route without strict contract coverage fails review or test gates.
- Secret-transfer routes are explicitly marked and tested for journal suppression.
