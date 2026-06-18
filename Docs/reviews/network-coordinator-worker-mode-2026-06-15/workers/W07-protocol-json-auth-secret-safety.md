# Worker Review: W07 - Protocol, JSON, Auth, Identity, And Secret Safety

## Scope

Review-only audit of network coordinator/worker protocol dataclasses, strict JSON handling, HMAC/bearer authentication, identity normalization, URL/join handling, Local API network command payload plumbing, and secret redaction/journal behavior.

Assigned source scope reviewed: `src/mediapipeline/desktop/network/protocol.py`, `auth.py`, `identity.py`, `json_policy.py`, `http_json.py`, `coordinator_http.py`, `src/mediapipeline/core/network/url_policy.py`, `src/mediapipeline/core/network/join.py`, and `src/mediapipeline/core/api/commands_network.py`.

Supporting source opened for secret/journal/log evidence: `src/mediapipeline/desktop/api/handler.py`, `handler_policy.py`, `command_journal_policy.py`, `contract_command.py`, `src/mediapipeline/core/network/facade.py`, `src/mediapipeline/desktop/network/coordinator_http_handlers.py`, `cluster_log.py`, `coordinator_auth.py`, `coordinator_parts/http_server.py`, `worker_http.py`, `worker_parts/tasks.py`, and targeted `worker_loops.py` lines.

## Required Reads Completed

- `AGENTS.md`
- `docs/CURRENT_PROJECT_STATE.md`
- `docs/OPEN_WORK_CHECKLIST.md`
- `docs/generated/PROJECT_INDEX.md`
- `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`
- `docs/architecture/NETWORK_LIFECYCLE_COMMAND_CONTRACT.md`
- `docs/inventories/API_ROUTE_INVENTORY.md`
- `docs/inventories/COMMAND_OWNERSHIP_MATRIX.md`
- `docs/reviews/network-coordinator-worker-mode-2026-06-15/PROMPT_PACK.md`
- Generated summaries for all assigned source/test files that exist.
- No generated summary was present for `src/mediapipeline/core/network/url_policy.py`; the file was explicitly in scope, so source was opened directly after confirming the summary was absent.

## Coverage Ledger

| File | Coverage | Notes |
|---|---|---|
| `src/mediapipeline/desktop/network/protocol.py` | Full source reviewed | Finding W07-002. |
| `src/mediapipeline/desktop/network/auth.py` | Full source reviewed | No direct finding; signed request helpers and legacy bearer fallback reviewed. |
| `src/mediapipeline/desktop/network/identity.py` | Full source reviewed | No direct finding; supports W07-003 because source path is only control-sanitized. |
| `src/mediapipeline/desktop/network/json_policy.py` | Full source reviewed | No finding. |
| `src/mediapipeline/desktop/network/http_json.py` | Full source reviewed | No finding; response cap and strict JSON reviewed. |
| `src/mediapipeline/desktop/network/coordinator_http.py` | Full source reviewed | No finding; body length cap reviewed. |
| `src/mediapipeline/core/network/url_policy.py` | Full source reviewed | No direct finding; redaction helper behavior reviewed. |
| `src/mediapipeline/core/network/join.py` | Full source reviewed | No direct finding; route-level secret handling finding is in Local API journal path, not blob encoding itself. |
| `src/mediapipeline/core/api/commands_network.py` | Full source reviewed | No direct finding; support for journal recorder behavior reviewed. |
| `tests/python/desktop/test_network_protocol_runtime.py` | Summary plus targeted assertions reviewed | Non-finite numeric and strict `DoneRequest` boolean coverage reviewed. |
| `tests/python/desktop/test_network_security.py` | Summary plus targeted assertions reviewed | HMAC, bearer fallback, redaction, content-length coverage reviewed. |
| `tests/python/desktop/test_network_coordinator_http.py` | Summary plus targeted assertions reviewed | JSON/body/log sanitization coverage reviewed. |
| `tests/python/desktop/test_network_join.py` | Summary plus targeted assertions reviewed | Successful join-route unjournaled coverage reviewed; validation-failure gap found. |
| `tests/python/desktop/test_api_command_contracts.py` | Summary plus targeted assertions reviewed | Unknown-field validation and network route payload coverage reviewed. |
| `tests/python/desktop/test_api_contract_payload.py` | Summary plus targeted assertions reviewed | Network contract/effect/journal metadata coverage reviewed. |
| `tests/python/desktop/test_application_facade_network.py` | Summary plus targeted assertions reviewed | Worker board token posture coverage reviewed. |

## Findings

| id | severity | file | line | symbol | summary |
|---|---|---|---|---|---|
| W07-001 | P1 | `src/mediapipeline/desktop/api/handler.py` | 100-109 | `_Handler.do_POST` validation-failure journal path | Secret-transfer `join_blob` can be written to command journal when payload validation fails before route suppression runs. |
| W07-002 | P2 | `src/mediapipeline/desktop/network/protocol.py` | 149-160 | `ClaimResponse.from_dict` | Type-confused claim booleans are coerced with `bool()`, so `"false"` becomes `True` before worker state is built. |
| W07-003 | P2 | `src/mediapipeline/desktop/network/cluster_log.py` | 28-30 | `format_cluster_log_line` | Worker-controlled `source_path` bypasses secret redaction when rendered into `cluster.log`. |

## Detailed Findings

### W07-001

- `id`: W07-001
- `severity`: P1
- `file`: `src/mediapipeline/desktop/api/handler.py`
- `line`: 100-109, with supporting evidence in `src/mediapipeline/desktop/api/command_journal_policy.py` lines 18-26 and 80-82.
- `symbol`: `_Handler.do_POST` validation-failure journal path
- `problem`: Local API POST validation failures are journaled with the raw request body before the route handler can return `data.suppress_command_journal`. `network/worker/join-cluster` is intentionally unjournaled because the request contains `join_blob`, but if validation fails first, `owner._record_command_journal(..., request=body)` still runs. The journal sanitizer redacts keys containing token/secret/password/auth, but `join_blob` is not in the sensitive key list, so the blob is kept as ordinary request evidence.
- `impact`: A mistyped or malicious join import request, for example a valid `join_blob` plus an unknown field, can persist the worker auth secret into the command journal, `/api/commands`, runlog-backed command history, diagnostics, and any SQLite mirror. That violates the explicit secret-transfer exclusion documented for join routes.
- `evidence`: `src/mediapipeline/desktop/api/handler.py:100-109` records validation failures with `request=body`. `src/mediapipeline/desktop/api/command_journal_policy.py:18-26` does not include `join_blob` as sensitive, and lines 80-82 only redact values when the key is sensitive. `tests/python/desktop/test_api_command_contracts.py:118-177` proves unknown-field validation rejects `/api/network/worker/join-cluster` payloads, including one with `join_blob` at line 164. `tests/python/desktop/test_network_join.py:220-296` covers successful join routes being unjournaled, but not validation failures. In-memory sanitizer check produced `{'join_blob': 'SECRET_JOIN_BLOB', ...}` in the journal request evidence.
- `suggested fix direction`: For Local API validation failures, consult route metadata and skip request journaling for routes with `journaled: false`, especially `effect: secret-transfer`; alternatively journal only route/status/error without request for those routes. Also add `join_blob` to sensitive journal keys as defense in depth.
- `suggested validation/tests`: Add a Local API test that posts a real join blob plus an unknown field to `/api/network/worker/join-cluster`, then asserts `/api/commands` does not contain the blob or decoded token. Add direct command-journal sanitizer coverage for `join_blob` request keys.

### W07-002

- `id`: W07-002
- `severity`: P2
- `file`: `src/mediapipeline/desktop/network/protocol.py`
- `line`: 149-160
- `symbol`: `ClaimResponse.from_dict`
- `problem`: `ClaimResponse.from_dict` uses `bool(...)` for `priority` and `retry_on_failure`. Python treats non-empty strings as true, so malformed wire values like `"false"` become `True` instead of being rejected. `retry_after_seconds` also goes through `int(...)`, which accepts booleans and truncates floats.
- `impact`: A malformed claim response can invert coordinator intent before the worker builds active state. `retry_on_failure="false"` becomes `True`, then `worker_parts/tasks.py:52-53` copies it into `encode_config["__retry_on_failure"]`, which later influences done reporting and retry/quarantine behavior. `priority="false"` can also mislabel the synthetic queue record and diagnostics.
- `evidence`: Direct parse check returned `{'priority': True, 'retry_on_failure': True}` for `ClaimResponse.from_dict({'priority': 'false', 'retry_on_failure': 'false'})`. `DoneRequest.from_dict` already uses strict boolean validation at `protocol.py:222-235`, and `tests/python/desktop/test_network_protocol_runtime.py:130-154` covers that strict behavior, but no equivalent claim boolean test exists.
- `suggested fix direction`: Reuse `coerce_optional_bool` for `ClaimResponse.priority` and `ClaimResponse.retry_on_failure`; add stricter integer coercion that rejects `bool` and fractional floats for protocol integer fields. Consider validating claim `status` against `ok`/`empty` and requiring `encode_config` to be a mapping.
- `suggested validation/tests`: Extend `test_network_protocol_runtime.py` with `ClaimResponse.from_dict` rejection cases for `"false"`, `"true"`, `0`, `1`, `None`, `{}`, and `[]` on claim booleans, plus integer rejection cases for booleans and fractional values.

### W07-003

- `id`: W07-003
- `severity`: P2
- `file`: `src/mediapipeline/desktop/network/cluster_log.py`
- `line`: 28-30
- `symbol`: `format_cluster_log_line`
- `problem`: `/api/log` redacts `entry.message` at `coordinator_http_handlers.py:542`, but the worker-controlled `source_path` is formatted separately. `format_cluster_log_line` sanitizes control characters and writes `Path(source_path).name` without calling `redact_network_secret_text`.
- `impact`: A worker can put token-like material in `source_path` and have it persisted in `cluster.log` even though the message field is redacted. `cluster.log` is a diagnostics artifact and can be opened or shared during support, so this is a real secret exposure path for malformed or hostile worker telemetry.
- `evidence`: In-memory check rendered `src=WorkerAuthToken=SECRET.mkv` for a `LogEntryRequest` with `source_path='C:\\Media\\WorkerAuthToken=SECRET.mkv'`. `tests/python/desktop/test_network_coordinator_http.py:502-535` verifies one-line/control-character sanitization for `source_path`, but does not assert token-like basename redaction.
- `suggested fix direction`: Apply `redact_network_secret_text` to `source_path` before extracting/rendering the basename, or redact the rendered basename before appending it to the log line. Consider the same redaction for worker-board path fields that are worker-controlled or derived from worker state.
- `suggested validation/tests`: Add cluster-log tests for `source_path` values containing `WorkerAuthToken=...`, `token=...`, URL query tokens, and userinfo URLs. Assert the log preserves a useful filename/path hint while removing the secret value.

## Test Coverage Gaps

- No test covers Local API validation-failure journaling for secret-transfer routes. Existing join-route tests cover successful unjournaled responses only.
- No test asserts `join_blob` is treated as sensitive by the command journal sanitizer.
- `ClaimResponse.from_dict` lacks strict boolean tests matching the existing `DoneRequest` boolean coverage.
- Protocol integer coercion lacks tests for booleans and fractional numbers.
- Cluster-log redaction tests cover control-character injection but not token-like values in `source_path`, `worker_name`, `event`, or other non-message fields.
- Redaction tests cover `key=value` assignments, but not common header/free-text forms such as `Authorization: Bearer ...`.

## Boundary Risks

- No source/scratch/output media mutation was observed or performed during this review.
- The strongest boundary risk is diagnostic-secret leakage: command journal entries and cluster logs are operator evidence surfaces and can flow into WebView/Diagnostics/support artifacts.
- The protocol coercion risk is bounded but real: malformed claim metadata can cross from HTTP response parsing into active worker state before later done reporting.
- Auth signing itself is consistent on the reviewed paths: worker `http_get_json` signs the path plus query, worker `http_post_json` signs the exact JSON bytes it sends, and coordinator auth validates with a nonce cache through `CoordinatorAuthMixin`.

## Files With No Findings

- `src/mediapipeline/desktop/network/auth.py`: no direct finding; HMAC signature, timestamp, nonce cache support, constant-time comparison, and legacy bearer gating were reviewed.
- `src/mediapipeline/desktop/network/json_policy.py`: no finding; strict JSON rejects non-finite constants.
- `src/mediapipeline/desktop/network/http_json.py`: no finding; response body cap and signed body construction reviewed.
- `src/mediapipeline/desktop/network/coordinator_http.py`: no finding; content-length validation reviewed.
- `src/mediapipeline/core/network/url_policy.py`: no direct finding; helper is useful but not applied to the source-path log field in W07-003.
- `src/mediapipeline/core/network/join.py`: no direct finding; blob payload necessarily contains the worker auth token, and the leak is in the Local API validation/journal path.
- `src/mediapipeline/core/api/commands_network.py`: no direct finding; lifecycle command journaling delegation reviewed.

## Incomplete Coverage

- Targeted tests were not run as full suites; evidence came from source review, test review, and small in-memory checks that did not touch runtime state.
- Assigned test files were reviewed by generated summary, `rg`, and targeted line ranges around W07 themes, not every unrelated assertion line-by-line.
- No live coordinator/worker server, real media, LAN discovery, lifecycle start/stop, settings save, queue mutation, publish, drain, or rename operation was run.
- `src/mediapipeline/core/network/url_policy.py` had no generated summary available under `docs/generated/summaries`.

## Suggested Follow-Up Prompts

- Patch W07-001 first: harden Local API validation-failure journaling for all `journaled: false` and secret-transfer routes, then add regression tests around invalid join requests.
- Patch W07-002 with strict `ClaimResponse` booleans and integer coercion, then run network protocol/runtime tests.
- Patch W07-003 by redacting all cluster-log fields, not only message text, then add adversarial log sanitization tests.
- Run a follow-up audit over all command-journal validation failure paths for other request keys that may contain credentials or operator-private artifacts.
