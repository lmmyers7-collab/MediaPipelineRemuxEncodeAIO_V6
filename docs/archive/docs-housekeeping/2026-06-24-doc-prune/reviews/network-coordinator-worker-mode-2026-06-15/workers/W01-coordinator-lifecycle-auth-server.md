# Worker Review: W01 - Coordinator Lifecycle, Auth, And HTTP Server

## Scope

Review-only audit of coordinator construction/teardown, HTTP server lifecycle, request-thread policy, coordinator auth token handling, coordinator config coercion, retry hints, and cluster-log safety for network coordinator/worker mode.

Assigned source scope reviewed:

| File | Symbols reviewed | Coverage |
|---|---|---|
| `src/mediapipeline/desktop/network/coordinator.py` | `CoordinatorDispatcher.__init__`, `_coord_port`, `_coord_bind_address`, `_heartbeat_timeout_mins`, `heartbeat` | complete |
| `src/mediapipeline/desktop/network/coordinator_lifecycle.py` | `_start_http_server`, `_start_reaper`, `_start_mdns`, `_reaper_interval_seconds`, `_reaper_loop`, `shutdown`, `workers_snapshot`, `idle_workers_snapshot`, `coordinator_stats` | complete |
| `src/mediapipeline/desktop/network/coordinator_auth.py` | `_load_or_generate_token`, `_validate_request_auth`, `_request_auth_result`, `get_auth_token`, `update_auth_token` | complete; finding W01-001 |
| `src/mediapipeline/desktop/network/coordinator_policy.py` | `coordinator_port`, `coordinator_bind_address`, `heartbeat_timeout_mins`, `compute_retry_after_seconds` | complete |
| `src/mediapipeline/desktop/network/coordinator_http.py` | `parse_query_params`, `validate_content_length`, `BodyLengthDecision` | complete |
| `src/mediapipeline/desktop/network/coordinator_parts/http_server.py` | `_CoordServer`, `_CoordHandler`, `_coordinator_health_heartbeat_timeout_mins` | complete |
| `src/mediapipeline/desktop/network/auth.py` | HMAC signing/validation, legacy bearer gate, nonce/skew handling | complete |
| `src/mediapipeline/desktop/network/identity.py` | worker ID/name validation, log field control-character sanitation | complete |
| `src/mediapipeline/desktop/network/cluster_log.py` | `format_cluster_log_line` | complete; finding W01-002 |

Additional narrow source reads for W01 questions: `coordinator_state.py` cluster-log path/append/rotation helpers, `coordinator_http_handlers.py` `/api/log` timestamp/redaction path, `protocol.py` `LogEntryRequest`, and `coordinator_queue.py` `_snapshot_encode_config` call/signature for test-failure triage.

## Required Reads Completed

Read in order: `AGENTS.md`, `docs/CURRENT_PROJECT_STATE.md`, `docs/OPEN_WORK_CHECKLIST.md`, `docs/generated/PROJECT_INDEX.md`, `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`, `docs/architecture/NETWORK_LIFECYCLE_COMMAND_CONTRACT.md`, `docs/architecture/NETWORK_WORKER_HARDENING_PLAN.md`, and `docs/inventories/API_ROUTE_INVENTORY.md`.

Generated summaries read before full source/tests for all assigned files. Focused summaries referenced by assigned tests were also read for `coordinator_url.py`, `diagnostics.py`, `encode_config_snapshot.py`, `failure_policy.py`, `firewall.py`, `http_json.py`, `path_map.py`, `poll_policy.py`, `probe.py`, `protocol.py`, `registry.py`, `worker.py`, `tools/paths.py`, plus `coordinator_state.py`, `coordinator_http_handlers.py`, and `coordinator_queue.py` where W01 questions required narrow evidence.

Summary gap: no generated summary exists for `src/mediapipeline/core/network/url_policy.py`; I did not line-read that non-assigned helper.

## Coverage Ledger

| Area | Evidence | Result |
|---|---|---|
| Coordinator startup fail-closed | `coordinator.py:119-136`, `coordinator_lifecycle.py:17-61`, `coordinator_state.py:16-29`, startup tests | Reviewed: no findings for bind/thread/reaper/restore cleanup behavior. |
| Request-handler thread policy | `coordinator_parts/http_server.py:38-47`, `test_network_coordinator_startup.py:18-21` | Reviewed: no findings; request handler threads are intentionally non-daemon and server close blocks on them. |
| Shutdown/state preservation | `coordinator_lifecycle.py:163-219`, workflow tests around shutdown/save failures | Reviewed: no findings; shutdown flips claim acceptance, stops surfaces, and preserves/saves inflight registry without releasing claims. |
| Auth token lifecycle | `coordinator_auth.py`, `auth.py`, security tests | Finding W01-001 for weak configured token acceptance at startup. |
| Config and retry defensive parsing | `coordinator_policy.py`, `coordinator_http.py`, helper/workflow tests | Reviewed: no findings. |
| Cluster-log safety | `cluster_log.py`, `identity.py`, `coordinator_state.py`, `/api/log` handler tests | Finding W01-002 for redaction limited to message field. |
| Assigned tests | Five assigned test modules read; targeted unittest run attempted | Finding W01-003 for current assigned workflow test failure. |

Validation/evidence commands:

| Command | Result |
|---|---|
| `.\apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_network_coordinator_startup tests.python.desktop.test_network_coordinator_helpers tests.python.desktop.test_network_coordinator_http tests.python.desktop.test_network_security tests.python.desktop.test_network_workflow` | Failed before collection with `ModuleNotFoundError: No module named 'mediapipeline'`; rerun with `PYTHONPATH=src`. |
| `$env:PYTHONPATH='src'; .\apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_network_coordinator_startup tests.python.desktop.test_network_coordinator_helpers tests.python.desktop.test_network_coordinator_http tests.python.desktop.test_network_security tests.python.desktop.test_network_workflow` | Ran 127 tests; failed 1 error: `test_http_claim_skips_records_outside_worker_accessible_libraries` stale mock signature. |
| In-process `format_cluster_log_line` check with token-like values in `worker_name`, `event`, `source_path`, and `message` | Confirmed message was redacted, but `worker_name`, `event`, and `source_path` still rendered token-like values. |
| In-process `_load_or_generate_token` check with `CoordinatorAuthToken='short'` | Confirmed startup loads `short`; `update_auth_token('short')` rejects the same value. |

## Findings

| id | severity | file | line / symbol | problem |
|---|---|---|---|---|
| W01-001 | P1 | `src/mediapipeline/desktop/network/coordinator_auth.py` | `_load_or_generate_token`, lines 13-17 | Startup accepts any nonblank configured coordinator auth token, including tokens that live rotation rejects as too short. |
| W01-002 | P1 | `src/mediapipeline/desktop/network/cluster_log.py` | `format_cluster_log_line`, lines 20-30 | Cluster-log redaction is applied only to `message`; token-like values in worker/name/event/source fields can be written to `cluster.log`. |
| W01-003 | P3 | `tests/python/desktop/test_network_workflow.py` | `test_http_claim_skips_records_outside_worker_accessible_libraries`, line 914 | Assigned workflow suite currently fails because the test mock has a stale `_snapshot_encode_config` signature. |

## Detailed Findings

### W01-001

- `id`: W01-001
- `severity`: P1
- `file`: `src/mediapipeline/desktop/network/coordinator_auth.py`
- `line`: `_load_or_generate_token`, lines 13-17
- `symbol`: `_load_or_generate_token`
- `problem`: Startup returns any nonblank `CoordinatorAuthToken` from config without applying the same minimum-length validation used by `update_auth_token`.
- `impact`: A weak or accidentally shortened PSD1 token can start a LAN coordinator with a guessable HMAC secret. That can let an attacker or misconfigured host with the guessed token submit signed claim/done/log requests, corrupting distributed-work state.
- `evidence`: `coordinator_auth.py:15-17` returns the stripped config token immediately. `coordinator_auth.py:97-101` rejects live rotations shorter than 16 characters. In-process check: `_load_or_generate_token` loaded `short`, while `update_auth_token('short')` raised `ValueError`.
- `suggested fix direction`: Add one shared coordinator-token validation helper and call it from both `_load_or_generate_token` and `update_auth_token`. For nonblank but invalid configured tokens, fail closed with a redacted error rather than silently generating a different token.
- `suggested validation/tests`: Add tests for short configured token rejection, strong configured token acceptance, blank config falling through to persisted/generated token, and no token value appearing in logs.

### W01-002

- `id`: W01-002
- `severity`: P1
- `file`: `src/mediapipeline/desktop/network/cluster_log.py`
- `line`: `format_cluster_log_line`, lines 20-30
- `symbol`: `format_cluster_log_line`
- `problem`: `redact_network_secret_text` is applied to `entry.message` only. Other rendered fields remain only control-character sanitized.
- `impact`: Authenticated worker-controlled log fields can leak token-like values, credential-bearing URLs, or config-secret assignments into `cluster.log`. The log is intended as operator evidence and can be copied into review/debug packets, so redaction should cover every rendered field, not just free-form message text.
- `evidence`: `cluster_log.py:20-25` renders `level`, `role`, `worker_name`, and `event` without secret redaction; `cluster_log.py:29-30` renders the source basename without secret redaction. `coordinator_http_handlers.py:542` redacts only `entry.message` before append. In-process check rendered `WorkerAuthToken=work` in the worker-name column, `token=event-secret` in the event column, and `src=Movie?token=source-secret.mkv`; only the message value was redacted.
- `suggested fix direction`: Apply `redact_network_secret_text` after control-character normalization to every field that can reach the rendered line, including worker name/id, role, level, event, job id, source basename/path, and worker timestamp. Keep the one-line invariant and current length caps.
- `suggested validation/tests`: Extend cluster-log formatter and `/api/log` tests with token-like values in `worker_name`, `event`, `source_path`, `job_id`, and `timestamp`, and assert the rendered line contains no raw token/query/userinfo/secret assignment.

### W01-003

- `id`: W01-003
- `severity`: P3
- `file`: `tests/python/desktop/test_network_workflow.py`
- `line`: line 914
- `symbol`: `test_http_claim_skips_records_outside_worker_accessible_libraries`
- `problem`: The test stubs `_snapshot_encode_config` as `lambda worker_name=""`, but production code now calls `_snapshot_encode_config(worker_name, r)`.
- `impact`: The assigned W01 unit evidence cannot pass, and the accessible-library claim-filter regression test never reaches its assertions. This masks the behavior the test is supposed to pin.
- `evidence`: Targeted unittest run with `PYTHONPATH=src` ran 127 tests and failed this case with `TypeError: ... <lambda>() takes from 0 to 1 positional arguments but 2 were given`, followed by `KeyError: 'status'`. Source evidence: `coordinator_queue.py:385` calls `self._snapshot_encode_config(worker_name, r)` and `coordinator_queue.py:414` defines `record: object | None = None`.
- `suggested fix direction`: Update the test double to accept `worker_name=""` and `record=None`, or use `*args, **kwargs` when the test does not care about encode-config details.
- `suggested validation/tests`: Rerun the five assigned W01 modules with `PYTHONPATH=src`; require the accessible-library test to assert that the TV row is skipped and the movie row is claimed.

## Test Coverage Gaps

| Gap | Risk | Suggested coverage |
|---|---|---|
| Config-loaded `CoordinatorAuthToken` strength is not tested against the rotation rules. | Weak static secrets can bypass live rotation validation. | Add `_load_or_generate_token` tests for too-short configured token, strong configured token, blank token fallback, and redacted logs. |
| Cluster-log redaction tests cover `message` but not other rendered fields. | Secrets in worker name/event/source path can leak. | Add formatter and `/api/log` tests with secret-like values in every rendered field. |
| Assigned workflow suite currently fails one stale test. | Review evidence is not green and claim-filter regression coverage is inactive. | Fix the `_snapshot_encode_config` test stub signature and rerun assigned modules. |

## Boundary Risks

- No source, runtime state, LocalBase, media, queue, settings, manifests, generated summaries, or aggregate review files were edited.
- The startup/shutdown paths reviewed preserve `coordinator_inflight.json` semantics and do not silently release active claims during shutdown.
- The auth-token finding is a network-boundary risk: if the configured token is weak, the HMAC scheme is only as strong as that operator-provided secret.
- The cluster-log finding is a diagnostics/secret-boundary risk: log lines are one-line sanitized, but not all fields are secret-redacted.
- Network lifecycle controls, source movement, publish/drain, rename, FFmpeg, subtitle, and audio policy were not exercised or changed.

## Files With No Findings

| File / symbol | Result |
|---|---|
| `src/mediapipeline/desktop/network/coordinator.py` / `CoordinatorDispatcher.__init__` | Reviewed: no findings for HTTP-first startup cleanup, post-HTTP reaper/mDNS failure cleanup, restore-before-listen ordering, and bind-all warning. |
| `src/mediapipeline/desktop/network/coordinator.py` / `heartbeat` | Reviewed: no findings for local heartbeat behavior when the registry errors but the job remains active. |
| `src/mediapipeline/desktop/network/coordinator_lifecycle.py` / `_start_http_server` | Reviewed: no findings for bind/thread-start fail-closed cleanup. |
| `src/mediapipeline/desktop/network/coordinator_lifecycle.py` / `_start_reaper` | Reviewed: no findings for thread-start failure propagation. |
| `src/mediapipeline/desktop/network/coordinator_lifecycle.py` / `_start_mdns` | Reviewed: no findings; fallback is logged and non-fatal. |
| `src/mediapipeline/desktop/network/coordinator_lifecycle.py` / `_reaper_loop` | Reviewed: no findings for stale reclaim logging and inflight save-failure diagnostics. |
| `src/mediapipeline/desktop/network/coordinator_lifecycle.py` / `shutdown` | Reviewed: no findings for claim-acceptance flip, server/mDNS/reaper teardown logging, and final inflight save attempt. |
| `src/mediapipeline/desktop/network/coordinator_lifecycle.py` / `workers_snapshot`, `idle_workers_snapshot`, `coordinator_stats` | Reviewed: no findings. |
| `src/mediapipeline/desktop/network/coordinator_auth.py` / `_request_auth_result`, `_validate_request_auth`, `get_auth_token`, `update_auth_token` | Reviewed: no findings outside W01-001; live rotation rejects blank/short tokens and logs persistence failures without the token value. |
| `src/mediapipeline/desktop/network/coordinator_policy.py` | Reviewed: no findings for port, bind address, heartbeat timeout, and retry-hint defensive coercion. |
| `src/mediapipeline/desktop/network/coordinator_http.py` | Reviewed: no findings for query parsing and content-length caps. |
| `src/mediapipeline/desktop/network/coordinator_parts/http_server.py` / `_CoordServer` | Reviewed: no findings; `daemon_threads=False` and `block_on_close` default preserve request-handler cleanup. |
| `src/mediapipeline/desktop/network/coordinator_parts/http_server.py` / `_CoordHandler` | Reviewed: no findings for strict JSON response handling, public health payload, auth-gated non-health endpoints, size caps, and logged response failures. |
| `src/mediapipeline/desktop/network/auth.py` | Reviewed: no findings for HMAC canonicalization, constant-time signature compare, nonce replay cache, clock-skew diagnosis after signature match, and legacy bearer env gate. |
| `src/mediapipeline/desktop/network/identity.py` | Reviewed: no findings for worker-id validation and one-line control-character sanitation; field-wide secret redaction gap is tracked in W01-002. |
| `tests/python/desktop/test_network_coordinator_startup.py` | Reviewed: no findings. |
| `tests/python/desktop/test_network_coordinator_helpers.py` | Reviewed: no findings. |
| `tests/python/desktop/test_network_coordinator_http.py` | Reviewed: no findings. |
| `tests/python/desktop/test_network_security.py` | Reviewed: no findings. |

## Incomplete Coverage

- Did not review full `src/mediapipeline/core/network/url_policy.py` because the generated summary was missing and it is outside W01 assigned source scope.
- Did not run real media, normal processing, publish/drain, rename, settings save, live coordinator/worker lifecycle start/stop, or browser/Tauri smokes.
- Did not review W02/W03/W04-owned endpoint, claim-selection, registry, or worker execution paths beyond narrow evidence needed for W01 findings and test triage.
- Assigned tests were not green: one W01-assigned workflow test failed as described in W01-003.

## Suggested Follow-Up Prompts

1. Fix W01-001 by centralizing coordinator token validation and applying it to config-loaded tokens, then run `test_network_security.py` plus a new `_load_or_generate_token` test.
2. Fix W01-002 by redacting all rendered cluster-log fields, then run `test_network_coordinator_helpers.py`, `test_network_coordinator_http.py`, and `test_network_workflow.py`.
3. Fix W01-003 by updating the stale `_snapshot_encode_config` test stub, then rerun all five W01-assigned test modules with `PYTHONPATH=src`.
