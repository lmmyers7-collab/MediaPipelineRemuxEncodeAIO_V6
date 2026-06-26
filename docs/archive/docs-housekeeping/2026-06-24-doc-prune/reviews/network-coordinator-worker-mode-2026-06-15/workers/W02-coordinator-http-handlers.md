# Worker Review: W02 - Coordinator HTTP Endpoint Handlers

## Scope

Reviewed coordinator HTTP endpoint handling for:

- `GET /api/ping`
- `GET /api/libraries`
- `GET /api/claim`
- `POST /api/done`
- `POST /api/heartbeat`
- `GET /api/workers`
- `POST /api/log`

Primary review focus: auth gates, query/body validation, strict JSON and non-finite numbers, content-length and response bounds, missing identifiers, claim rollback, done/release/reclaimed handling, heartbeat reclaim signals, and worker-controlled cluster-log sanitization.

No live coordinator, worker, media, queue, settings, LocalBase, or runtime state routes were executed.

## Required Reads Completed

- `AGENTS.md`
- `docs/CURRENT_PROJECT_STATE.md`
- `docs/OPEN_WORK_CHECKLIST.md`
- `docs/generated/PROJECT_INDEX.md`
- `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`
- `docs/architecture/NETWORK_LIFECYCLE_COMMAND_CONTRACT.md`
- `docs/architecture/NETWORK_WORKER_HARDENING_PLAN.md`
- `docs/inventories/API_ROUTE_INVENTORY.md`
- Generated summaries for all assigned source files:
  - `docs/generated/summaries/src/mediapipeline/desktop/network/coordinator_http_handlers.py.md`
  - `docs/generated/summaries/src/mediapipeline/desktop/network/coordinator_http.py.md`
  - `docs/generated/summaries/src/mediapipeline/desktop/network/protocol.py.md`
  - `docs/generated/summaries/src/mediapipeline/desktop/network/json_policy.py.md`
  - `docs/generated/summaries/src/mediapipeline/desktop/network/http_json.py.md`
  - `docs/generated/summaries/src/mediapipeline/desktop/network/library_roots.py.md`
  - `docs/generated/summaries/src/mediapipeline/desktop/network/auth.py.md`
  - `docs/generated/summaries/src/mediapipeline/desktop/network/identity.py.md`
- Generated summaries for all assigned evidence tests:
  - `docs/generated/summaries/tests/python/desktop/test_network_coordinator_http.py.md`
  - `docs/generated/summaries/tests/python/desktop/test_network_workflow.py.md`
  - `docs/generated/summaries/tests/python/desktop/test_network_security.py.md`
  - `docs/generated/summaries/tests/python/desktop/test_network_library_relative_claim.py.md`
  - `docs/generated/summaries/tests/python/desktop/test_network_protocol_runtime.py.md`
  - `docs/generated/summaries/tests/python/desktop/test_network_coordinator_source_policy.py.md`
- Supporting summaries read before opening supporting source:
  - `docs/generated/summaries/src/mediapipeline/desktop/network/coordinator_parts/http_server.py.md`
  - `docs/generated/summaries/src/mediapipeline/desktop/network/registry.py.md`
  - `docs/generated/summaries/src/mediapipeline/desktop/network/use_cases/done_outcome.py.md`
  - `docs/generated/summaries/src/mediapipeline/desktop/network/cluster_log.py.md`
  - `docs/generated/summaries/src/mediapipeline/desktop/network/coordinator_state.py.md`

## Coverage Ledger

| File | Symbols / endpoints reviewed | Coverage |
|---|---|---|
| `src/mediapipeline/desktop/network/coordinator_http_handlers.py` | `_http_ping`, `_http_libraries`, `_http_claim`, `_http_done`, `_http_heartbeat`, `_http_workers`, `_http_log` | Reviewed |
| `src/mediapipeline/desktop/network/coordinator_http.py` | `parse_query_params`, `validate_content_length` | Reviewed |
| `src/mediapipeline/desktop/network/protocol.py` | `ClaimResponse`, `DoneRequest`, `HeartbeatRequest`, `LogEntryRequest`, `WorkersResponse`, numeric/list coercers | Reviewed |
| `src/mediapipeline/desktop/network/json_policy.py` | `loads_strict_json`, `reject_json_constant` | Reviewed |
| `src/mediapipeline/desktop/network/http_json.py` | `http_get_json`, `http_post_json`, `http_read_capped` | Reviewed |
| `src/mediapipeline/desktop/network/library_roots.py` | `libraries_response_from_config`, `claim_library_fields_for_record`, `resolve_worker_library_relative_path`, auto-map helpers | Reviewed |
| `src/mediapipeline/desktop/network/auth.py` | HMAC request auth, legacy bearer gate, nonce/cache/skew handling | Reviewed |
| `src/mediapipeline/desktop/network/identity.py` | Worker ID/name and log display sanitizers | Reviewed |
| `src/mediapipeline/desktop/network/coordinator_parts/http_server.py` | `_CoordHandler` auth, body read, GET/POST dispatch, JSON send | Supporting call-path reviewed |
| `src/mediapipeline/desktop/network/registry.py` | `claim`, `complete`, `unclaim`, `rollback_claim`, `heartbeat`, `is_in_flight`, `snapshot` | Supporting call-path reviewed |
| `src/mediapipeline/desktop/network/use_cases/done_outcome.py` | `CoordinatorDoneOutcomeService.handle`, success/failure queue removal and log side effects | Supporting call-path reviewed |
| `src/mediapipeline/desktop/network/cluster_log.py` | `format_cluster_log_line` | Supporting call-path reviewed |
| `src/mediapipeline/desktop/network/coordinator_state.py` | `log_cluster_event`, `_safe_log_cluster_event`, `_append_cluster_log` | Supporting call-path reviewed |
| Assigned tests | `test_network_coordinator_http.py`, `test_network_workflow.py`, `test_network_security.py`, `test_network_library_relative_claim.py`, `test_network_protocol_runtime.py`, `test_network_coordinator_source_policy.py` | Reviewed for coverage evidence |

## Findings

| id | severity | file | line | symbol | problem |
|---|---|---|---:|---|---|
| W02-001 | P1 | `src/mediapipeline/desktop/network/coordinator_http_handlers.py` | 270 | `_http_done` | Missing `worker_id` on `/api/done` bypasses registry ownership checks and can complete or release another worker's job if the job id is known. |
| W02-002 | P1 | `src/mediapipeline/desktop/network/coordinator_http_handlers.py` | 201 | `_http_claim` | `/api/claim` saves a claim before final response serialization/write, with no rollback if the response cannot be encoded or delivered. |
| W02-003 | P1 | `src/mediapipeline/desktop/network/coordinator_http_handlers.py` | 533 | `_http_log` | `/api/log` redacts only `message`, so worker-controlled `worker_name`, `event`, `role`, timestamp, and source basename can leak token-like secrets into `cluster.log`. |
| W02-004 | P2 | `src/mediapipeline/desktop/network/use_cases/done_outcome.py` | 152 | `_handle_failure` | Failed-job and quarantine cluster-log events pass unsupported metadata kwargs to the production logger and can be silently dropped. |

## Detailed Findings

### W02-001 - Missing worker_id on `/api/done` bypasses job ownership checks

- `id`: W02-001
- `severity`: P1
- `file`: `src/mediapipeline/desktop/network/coordinator_http_handlers.py`
- `line`: 270
- `symbol`: `_http_done`
- `problem`: The HTTP handler explicitly allows an empty `worker_id` and then passes it into `registry.unclaim()` or `registry.complete()`. The registry treats an empty requester as an internal caller, so the owner mismatch check is skipped.
- `impact`: Any authenticated coordinator client that knows a valid `job_id` can send `/api/done` with `worker_id` omitted or empty and release, fail, or complete another worker's in-flight job. A success report then runs the normal success path and schedules queue-row removal, so this can remove the wrong queue row and misattribute worker stats.
- `evidence`:
  - `src/mediapipeline/desktop/network/coordinator_http_handlers.py:270` says empty `worker_id` is allowed for `/api/done`.
  - `src/mediapipeline/desktop/network/coordinator_http_handlers.py:274` only validates `worker_id` when it is present.
  - `src/mediapipeline/desktop/network/coordinator_http_handlers.py:291` passes `req.worker_id` into `unclaim()` for release reports.
  - `src/mediapipeline/desktop/network/coordinator_http_handlers.py:363` passes `req.worker_id` into `complete()` for success/failure reports.
  - `src/mediapipeline/desktop/network/registry.py:400` documents that empty `worker_id` is allowed for internal callers.
  - `src/mediapipeline/desktop/network/registry.py:404` only rejects owner mismatch when `requester` is non-empty.
  - `src/mediapipeline/desktop/network/registry.py:412` deletes the job and clears the claimed path after that skipped check.
  - `src/mediapipeline/desktop/network/registry.py:503` applies the same non-empty-only requester check in `unclaim()`, then deletes the job at `src/mediapipeline/desktop/network/registry.py:511`.
  - `src/mediapipeline/desktop/network/use_cases/done_outcome.py:83` schedules queue removal on success.
  - `src/mediapipeline/desktop/network/use_cases/done_outcome.py:201` also removes the queue row for terminal failure or non-retry failure.
  - `tests/python/desktop/test_network_security.py:288` covers the registry's empty-worker internal affordance, but there is no corresponding HTTP handler test requiring `/api/done` to reject missing or empty `worker_id`.
- `suggested fix direction`: Require a non-empty, valid `worker_id` in `_http_done` for all external HTTP done/release reports. Keep the registry's empty-worker affordance only for internal non-HTTP call paths, or introduce an explicit internal-only method for crash recovery.
- `suggested validation/tests`: Add endpoint tests for success, failure, and `released=true` bodies with omitted and empty `worker_id`; assert a `400` response and assert `registry.complete()` / `registry.unclaim()` are not called. Keep the existing registry-level empty-worker test for internal callers.

### W02-002 - `/api/claim` does not roll back when final response serialization or write fails

- `id`: W02-002
- `severity`: P1
- `file`: `src/mediapipeline/desktop/network/coordinator_http_handlers.py`
- `line`: 201
- `symbol`: `_http_claim`
- `problem`: The handler rolls back on retry-policy failure and registry-save failure, but after the registry is durably saved it constructs and sends the `ClaimResponse` without any rollback path for serialization failure or socket write failure.
- `impact`: If `encode_config` or another response field is not strict-JSON-serializable, `_send_json()` returns a 500 body while the job remains claimed. If the socket write fails, `_send_json()` raises after the claim has been saved. In both cases, the worker may never receive a usable claim while the coordinator considers the source in-flight until stale reclaim runs.
- `evidence`:
  - `src/mediapipeline/desktop/network/coordinator_http_handlers.py:153` creates the in-memory registry claim.
  - `src/mediapipeline/desktop/network/coordinator_http_handlers.py:181` starts retry-policy evaluation; failure releases the claim at `src/mediapipeline/desktop/network/coordinator_http_handlers.py:190`.
  - `src/mediapipeline/desktop/network/coordinator_http_handlers.py:201` saves the registry; failure rolls back at `src/mediapipeline/desktop/network/coordinator_http_handlers.py:207`.
  - `src/mediapipeline/desktop/network/coordinator_http_handlers.py:248` constructs the response only after the save and cluster-log side effect.
  - `src/mediapipeline/desktop/network/coordinator_http_handlers.py:259` sends the response without a `try`/rollback branch.
  - `src/mediapipeline/desktop/network/coordinator_parts/http_server.py:72` serializes JSON with `allow_nan=False`.
  - `src/mediapipeline/desktop/network/coordinator_parts/http_server.py:75` catches serialization failure and sends a generic 500, but does not signal the caller to roll back.
  - `src/mediapipeline/desktop/network/coordinator_parts/http_server.py:86` logs socket write failure and re-raises.
  - `tests/python/desktop/test_network_coordinator_http.py:202` confirms non-strict JSON response attempts become a 500.
  - `tests/python/desktop/test_network_coordinator_http.py:232` confirms response write failure raises.
  - `tests/python/desktop/test_network_workflow.py:1026` covers registry-save rollback, and `tests/python/desktop/test_network_workflow.py:1121` covers retry-policy rollback, but neither covers post-save response failure rollback.
- `suggested fix direction`: Pre-serialize the exact claim response before durable save or make `_send_json()` return/raise a structured failure that `_http_claim` can catch. If final response delivery fails before a complete body is written, call `rollback_claim()` and persist the rollback so the source is immediately claimable again.
- `suggested validation/tests`: Add tests where claim `encode_config` contains `float("nan")` or a non-serializable value and where handler `_send_json` raises after save. Assert the registry no longer reports the source in-flight and the rollback save/event is recorded.

### W02-003 - `/api/log` does not redact secrets from all worker-controlled log fields

- `id`: W02-003
- `severity`: P1
- `file`: `src/mediapipeline/desktop/network/coordinator_http_handlers.py`
- `line`: 533
- `symbol`: `_http_log`
- `problem`: The handler sanitizes all log fields for length/control characters but applies `redact_network_secret_text()` only to `entry.message`.
- `impact`: A compromised or buggy authenticated worker can place `WorkerAuthToken=...`, a join blob URL, or another token-like secret into `worker_name`, `event`, `role`, timestamp, or the source filename and have it written to `cluster.log`. That log is later used for diagnostics/operator evidence, so leaked coordinator credentials can spread into support notes or review artifacts.
- `evidence`:
  - `src/mediapipeline/desktop/network/protocol.py:397` builds `LogEntryRequest` directly from JSON fields including timestamp, worker_name, role, level, event, message, job_id, and source_path.
  - `src/mediapipeline/desktop/network/coordinator_http_handlers.py:533` calls `sanitize_log_entry_fields(entry)`.
  - `src/mediapipeline/desktop/network/coordinator_http_handlers.py:542` redacts only `entry.message`.
  - `src/mediapipeline/desktop/network/identity.py:44` through `src/mediapipeline/desktop/network/identity.py:58` sanitize display fields for control characters and length but do not call `redact_network_secret_text()`.
  - `src/mediapipeline/desktop/network/cluster_log.py:22` writes `worker_name`, `src/mediapipeline/desktop/network/cluster_log.py:23` writes `event`, and `src/mediapipeline/desktop/network/cluster_log.py:30` writes the source basename without redaction.
  - `src/mediapipeline/desktop/network/cluster_log.py:24` redacts only `entry.message`.
  - `src/mediapipeline/core/network/url_policy.py:40` through `src/mediapipeline/core/network/url_policy.py:50` provide redaction for URL secrets and token-like assignments.
  - `tests/python/desktop/test_network_coordinator_http.py:502` covers control-character one-line formatting, but it asserts sanitized unredacted field text is preserved.
  - `tests/python/desktop/test_network_security.py:162` covers the redaction helper itself, not its application across `/api/log` fields.
- `suggested fix direction`: Apply `redact_network_secret_text()` to every worker-controlled display field before append, either inside `sanitize_log_entry_fields()` or inside `format_cluster_log_line()` for worker_name, role, level, event, message, source basename, and worker timestamp.
- `suggested validation/tests`: Add `/api/log` tests with token-like assignments and URLs in `worker_name`, `event`, `role`, `timestamp`, `source_path`, and `message`; assert the rendered line contains no raw token, query secret, userinfo, or join blob.

### W02-004 - Failed-job and quarantine cluster-log events pass unsupported kwargs

- `id`: W02-004
- `severity`: P2
- `file`: `src/mediapipeline/desktop/network/use_cases/done_outcome.py`
- `line`: 152
- `symbol`: `_handle_failure`
- `problem`: Failure and quarantine paths call `_safe_log_cluster_event()` with extra keyword arguments such as `reason_code`, `reason`, `consecutive_count`, and `max_job_retries`. The production `log_cluster_event()` signature does not accept those fields, so `_safe_log_cluster_event()` catches a `TypeError` and drops the cluster-log event.
- `impact`: `/api/done` still mutates registry state and returns success, but the operator may lose the most important audit entries: failed job outcome and worker quarantine. This weakens coordinator evidence during repeated worker failures without corrupting media state.
- `evidence`:
  - `src/mediapipeline/desktop/network/use_cases/done_outcome.py:152` emits the failed-job cluster event.
  - `src/mediapipeline/desktop/network/use_cases/done_outcome.py:165` passes unsupported `reason_code`, and `src/mediapipeline/desktop/network/use_cases/done_outcome.py:166` passes unsupported `reason`.
  - `src/mediapipeline/desktop/network/use_cases/done_outcome.py:180` emits the worker-quarantined cluster event.
  - `src/mediapipeline/desktop/network/use_cases/done_outcome.py:194` through `src/mediapipeline/desktop/network/use_cases/done_outcome.py:197` pass unsupported `reason_code`, `reason`, `consecutive_count`, and `max_job_retries`.
  - `src/mediapipeline/desktop/network/coordinator_state.py:82` through `src/mediapipeline/desktop/network/coordinator_state.py:93` define `log_cluster_event()` without those metadata fields.
  - `src/mediapipeline/desktop/network/coordinator_state.py:116` through `src/mediapipeline/desktop/network/coordinator_state.py:126` catch and warn on the failed event emission instead of appending it.
  - `tests/python/desktop/test_network_workflow.py:334` exercises failure logging, but it replaces `log_cluster_event` with a permissive lambda that accepts `**_kwargs` or intentionally raises, masking the production signature mismatch.
- `suggested fix direction`: Either remove unsupported kwargs from done-outcome cluster-log calls and fold metadata into the redacted `message`, or extend `LogEntryRequest` / `log_cluster_event()` / `format_cluster_log_line()` to accept and safely render structured metadata.
- `suggested validation/tests`: Add a production-signature test that calls `_emit_done_outcome()` for a failed and quarantined job with the real `CoordinatorStateMixin.log_cluster_event()` path wired to an in-memory append. Assert the failed/quarantine log line is appended without warning.

## Test Coverage Gaps

- Missing `/api/done` endpoint tests for omitted and empty `worker_id` across success, failure, terminal failure, and release. Current tests cover registry-level empty-worker internal behavior, but not the external HTTP boundary.
- Missing `/api/claim` tests for final response serialization failure and final socket write failure after registry save.
- Missing `/api/log` tests that place token-like secrets in every worker-controlled field, not only in `message`.
- Existing failure/quarantine done-outcome tests use permissive `log_cluster_event = lambda **kwargs`, which does not catch the production signature mismatch.
- Query parameter count/size for `accessible_library_ids` is bounded indirectly by HTTP request-line limits and per-item truncation, but there is no explicit list-count cap test.
- Server responses are strict JSON, and worker clients cap response reads, but there is no server-side oversized response guard test for `/api/workers` or `/api/libraries`.

## Boundary Risks

- W02-001 touches queue correctness and cross-worker ownership. A malformed authenticated `/api/done` can remove an in-flight job from the registry and can schedule queue-row removal under the wrong worker identity.
- W02-002 touches distributed claim correctness. A response failure after durable claim save can leave work parked as in-flight even though no worker has usable claim details.
- W02-003 is a coordinator secret exposure risk through `cluster.log`.
- W02-004 weakens operator evidence for failures/quarantine but does not directly mutate source, scratch, output, pending-publish, or media policy state.

## Files With No Findings

| File | Reviewed result |
|---|---|
| `src/mediapipeline/desktop/network/coordinator_http.py` | Reviewed: no findings. Content length rejects malformed/negative/oversized bodies with 400/413; query parsing itself is simple and side-effect free. |
| `src/mediapipeline/desktop/network/protocol.py` | Reviewed: no findings beyond W02-001's HTTP boundary issue. Numeric coercers reject non-finite values; done boolean flags require literal booleans. |
| `src/mediapipeline/desktop/network/json_policy.py` | Reviewed: no findings. `loads_strict_json()` rejects JSON `NaN` / `Infinity` constants. |
| `src/mediapipeline/desktop/network/http_json.py` | Reviewed: no findings. Worker HTTP helpers sign requests and cap response reads before JSON parsing. |
| `src/mediapipeline/desktop/network/library_roots.py` | Reviewed: no findings. Library-relative claim paths reject absolute paths, drive-qualified paths, and `..` traversal before worker resolution. |
| `src/mediapipeline/desktop/network/auth.py` | Reviewed: no findings. Assigned endpoints are protected by HMAC request auth through the dispatch layer; legacy bearer is environment-gated. |
| `src/mediapipeline/desktop/network/identity.py` | Reviewed: no findings for line-shape sanitization; secret redaction gap is reported under W02-003. |
| `tests/python/desktop/test_network_library_relative_claim.py` | Reviewed: no source finding in assigned scope. Coverage confirms additive library-relative claim fields and unsafe relative-path fallback behavior. |
| `tests/python/desktop/test_network_protocol_runtime.py` | Reviewed: no source finding in assigned scope. Coverage confirms finite numeric coercion, heartbeat clamping, and done request boolean strictness. |
| `tests/python/desktop/test_network_coordinator_source_policy.py` | Reviewed: no source finding in assigned scope. Source-policy checks are static and do not run media or queue work. |

## Incomplete Coverage

- Did not execute live HTTP requests against a running coordinator.
- Did not start a worker, claim live queue work, or run real media.
- Did not inspect or modify runtime state, LocalBase, settings, queue snapshots, manifests, source media, scratch, output, pending-publish state, or aggregate review files.
- Did not review worker runtime loop ownership except where assigned tests or HTTP helper call paths required it.
- Did not review Local API network lifecycle routes; those belong to W08.

## Suggested Follow-Up Prompts

- Fix W02-001 first: harden `/api/done` so external requests require non-empty owner identity, then add endpoint-level tests that prove wrong-owner and missing-owner reports cannot complete, release, or remove queue rows.
- Fix W02-002 with a claim response pre-serialization or rollback-safe send path and add adversarial tests for non-strict response payloads.
- Fix W02-003 by applying network secret redaction to every worker-controlled cluster-log field and add token-leak regression tests.
- Fix W02-004 together with W04 if that worker reports related done-outcome evidence gaps, because the affected code lives in the shared done-outcome service.
