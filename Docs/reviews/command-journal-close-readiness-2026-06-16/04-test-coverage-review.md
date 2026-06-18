# Test Coverage Review

## Existing Coverage That Directly Supports This Review

Command contracts and journal safety:

- `tests/python/desktop/test_api_command_contracts.py` covers strict booleans for backend shutdown force, rename/final-library actions, settings, schedule, maintenance, and network lifecycle commands.
- The same test file verifies that secret-transfer validation failures are not journaled and that `join_blob` evidence is redacted.
- `tests/python/desktop/test_api_command_journal_policy.py` covers journal policy behavior.
- `tests/python/desktop/test_api_command_results_policy.py` covers command result shapes.
- `tests/python/desktop/test_api_read_payloads_policy.py` covers read payload status surfaces.

Mutation confirmation guards:

- `tests/python/desktop/test_application_facade_rename.py` rejects absent/string `confirm_apply` and applies only with real `True`.
- `tests/python/desktop/test_application_facade_settings_patch.py` requires confirmation, writes backups, and preserves secrets.
- WebView mutation boundary tests assert frontend assets send expected confirmation payloads.
- Browser smoke tests cover rename apply, queue file override series apply, and schedule save confirmation payloads.

Duplicate command protection:

- `tests/python/desktop/test_application_facade_process_launch.py` covers shared process launch lock rejection for pipeline, audit, and rerun commands.
- The same file covers duplicate pipeline launch rejection while the first process is still considered running.
- Network lifecycle duplicate-start behavior is covered where it overlaps launch/command evidence.

Close-readiness and backend shutdown:

- `tests/python/desktop/test_facade_process_guard_policy.py` covers close-readiness policy including active, unknown, unexpected, and progress states.
- `tests/python/desktop/test_application_facade_close_readiness.py` covers ActiveJobs, pipeline progress, audit progress, related process checks, final-library promotion, queue source scan, and watcher blockers.
- `tests/python/desktop/test_local_api_lifecycle_contract_smoke.py` covers safe close-readiness/shutdown behavior, token enforcement, and blocked shutdown when schedule-stop watcher is armed.

Tauri behavior:

- `tests/python/desktop/test_tauri_shell_scaffold.py` statically verifies Tauri shell/backend wiring.
- `tests/python/desktop/test_tauri_pg1_close_adversarial_scaffold.py` statically verifies the PG-1 close adversarial scaffold.

Diagnostics and Command History:

- `tests/webview/test_webview_frontend_mutation_boundary.py` verifies diagnostics ownership boundaries and mutation guardrail text.
- WebView smoke tests exercise command result append behavior for selected mutation workflows.

## Coverage Strengths

- Strict JSON and confirmation requirements have strong unit and static frontend coverage.
- Close-readiness policy is covered at the facade and policy level.
- Duplicate launch protection is covered at the lock and active-process simulation level.
- Secret material redaction and journal suppression for secret-transfer validation failures are explicitly covered.
- Tauri close behavior has static checks that guard the intended wiring.

## Coverage Gaps

### Gap 1: Route Exception Journal Evidence

No test currently appears to assert that an unexpected exception inside a command route is persisted as a failed command evidence row. The implementation currently does not do that, so a regression test should be added with the fix.

Recommended test:

- Trigger a journaled command route handler exception after validation.
- Assert the HTTP response is sanitized.
- Assert `/api/commands` includes a bounded failed command-result entry with the route path and error id.
- Assert secret-transfer and explicitly unjournaled route exceptions are still not recorded with request bodies.

### Gap 2: Journal Persistence Degradation

The journal save path has retry and strict-mode behavior, but normal command recording does not surface save failure to callers or `/api/commands`.

Recommended test:

- Inject a command journal path that fails atomic save.
- Verify the command result or `/api/commands` reports degraded persistence if that remediation is implemented.
- Verify no unbounded request data is exposed in the degradation metadata.

### Gap 3: Live Tauri Close During Active Encode

`test_tauri_pg1_close_adversarial_scaffold.py` states that it does not launch live Tauri or real media and that full PG-1 validation requires a live Tauri temp adversarial backend. The coverage matrix also describes process lifecycle coverage as simulated rather than real-media lifecycle.

Recommended test:

- Launch the Tauri shell against a temp backend.
- Start a controlled long-running encode/process fixture.
- Attempt close.
- Assert Tauri denies safe close or prompts for confirmation.
- Cancel and verify the backend process remains alive.
- Confirm force and verify the force path sends `force_active_work_shutdown: true` and performs cleanup.

### Gap 4: Repeated Identical Local Command Failures

The UI dedupe path merges rows using `command|result|message`, so repeated identical failures can collapse into one row. Existing smoke tests do not appear to verify repeated identical failure preservation.

Recommended test:

- Append two identical local failure rows for the same command at different times.
- Refresh backend command history with no matching journal row.
- Assert the UI preserves enough evidence to show repeated attempts, or assert the replacement is based on a stronger request identity after remediation.

## Release Gate Recommendation

Before release, the minimum focused validation set should include:

- strict command contract tests
- command journal policy tests
- close-readiness policy and facade tests
- local API lifecycle smoke
- process launch duplicate tests
- WebView mutation boundary tests
- Tauri static close scaffold tests

Before declaring close-readiness production ready, keep the live Tauri active-work close test as a PG-1/manual or automated release gate.
