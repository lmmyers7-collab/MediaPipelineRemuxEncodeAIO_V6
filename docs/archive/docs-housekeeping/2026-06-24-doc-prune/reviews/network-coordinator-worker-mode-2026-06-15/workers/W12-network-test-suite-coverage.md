# Worker Review: W12 - Network Test Suite Coverage

## Scope

Review-only audit of the network coordinator/worker test suite and adjacent smoke wrappers assigned in the W12 prompt:

- `tests/python/desktop/test_network*.py`
- `tests/webview/test_webview_*network*.py`
- Network-related portions of `test_api_command_contracts.py`, `test_api_contract_payload.py`, `test_application_facade_network.py`, `test_local_api_lifecycle_contract_smoke.py`, and `test_tauri_shell_scaffold.py`
- `ops/scripts/smoke/Test-WebViewBrowserNetworkSmoke.ps1`
- `ops/pipeline/tests/Unit/Invoke-LocalWorker*.ps1`

No source, tests, generated summaries, runtime state, config, media, queue state, aggregate review files, or manifests were edited.

## Required Reads Completed

- `AGENTS.md`
- `docs/CURRENT_PROJECT_STATE.md`
- `docs/OPEN_WORK_CHECKLIST.md`
- `docs/generated/PROJECT_INDEX.md`
- `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`
- `docs/testing/VALIDATION_LADDER_RUNBOOK.md`
- `docs/testing/TEST_COVERAGE_MATRIX.md`
- `docs/testing/BROWSER_SMOKE_TEST_RUNBOOK.md`
- `docs/architecture/NETWORK_WORKER_HARDENING_PLAN.md`
- `docs/reviews/network-coordinator-worker-mode-2026-06-15/PROMPT_PACK.md`
- Generated summaries for all assigned tests where present.

Summary exception: `tests/python/desktop/test_network_coordinator_policy_phase_e.py` exists in the worktree but has no matching `docs/generated/summaries/tests/python/desktop/test_network_coordinator_policy_phase_e.py.md` entry and is untracked. I opened that test directly after confirming the missing summary.

## Coverage Ledger

| Risk area | Coverage status | Evidence |
|---|---|---|
| Duplicate claims | Partial | Duplicate registry rows and local worker duplicate source claims are covered; concurrent `/api/claim` race is not. See W12-001. |
| Registry save failure | Covered | `test_network_workflow.py` and `test_network_inflight_registry.py` cover claim/done/release save failure diagnostics and rollback. |
| Worker crash between completion and report | Covered | `test_network_crash_recovery.py` covers done retry, fallback failure report, malformed state, and pending done retention. |
| Pending done retry | Covered | `test_network_worker_state.py`, `test_network_crash_recovery.py`, and `test_network_done_release.py` cover pending done save/retry/clear behavior. |
| Auth/token leak | Mostly covered | HMAC, URL redaction, token fingerprints, and successful join redaction are covered; malformed join-blob leak handling is not. See W12-002. |
| Malformed JSON and non-finite values | Covered | Protocol, HTTP, worker-state, registry, and config JSON tests reject or sanitize non-finite payloads. |
| Stale heartbeat reclaim | Covered | Reaper, reclaimed heartbeat abort, save failure, and cluster-log failure paths are covered. |
| Thread startup failure | Covered | Coordinator HTTP/reaper start and worker poll/heartbeat/cluster-log thread start failures are covered. |
| Stop while active | Covered | `test_network_lifecycle_fixes.py` checks worker stop does not release a still-running claim. |
| Hot-apply drift | Covered | `test_network_drift_descriptor.py` and `test_network_lifecycle_fixes.py` cover fingerprints, drift fields, and hot-apply evidence. |
| Path-map UNC/case/relative traversal | Mostly covered | UNC normalization, case-insensitive prefix matching, prefix boundary, and library-relative parent traversal rejection are covered. |
| Inaccessible library filtering | Covered | Claim and heartbeat accessible-library tests cover dispatch filtering and evidence. |
| Failure retry quarantine | Covered | Same-source/same-worker/same-reason suppression and worker misconfigured evidence are covered. |
| Join blob secret handling | Partial | Successful secret transfer, no raw token in result, unjournaled routes, and confirmation-missing no-save are covered; malformed blob and hostile secret text are not. See W12-002 and W12-004. |
| WebView no-mutation boundaries | Mostly covered | Network browser smoke checks media no-mutation and limits posts to discovery/join controls; static boundary checks backend-owned routes. Contract docs are stale. See W12-003. |
| Broad discovery commands | Partial | `test_network*.py` discovery exists, but the documented gate omits assigned contract/WebView/Tauri/PowerShell coverage and stale lifecycle status. See W12-003. |

## Findings

| id | severity | file | line | summary |
|---|---|---|---|---|
| W12-001 | P1 | `tests/python/desktop/test_network_workflow.py` | `74` / `108` / `886` | Duplicate-claim coverage stops short of a concurrent `/api/claim` race. |
| W12-002 | P2 | `tests/python/desktop/test_network_join.py` | `81` / `120` / `203` / `220` | Join blob tests cover happy path and missing confirmation, but not malformed hostile blobs or redacted failure output. |
| W12-003 | P2 | `docs/testing/TEST_COVERAGE_MATRIX.md` | `26` / `273` / `277` | Active coverage docs still assert stale design-only/read-only network lifecycle behavior and understate current test requirements. |
| W12-004 | P3 | `tests/webview/test_webview_browser_network_smoke.py` | `683` / `696` | Browser Network smoke fixture marks join secret/config routes as not requiring confirmation, contradicting the Local API contract. |

## Detailed Findings

### W12-001

- `id`: W12-001
- `severity`: P1
- `file`: `tests/python/desktop/test_network_workflow.py`
- `line`: `74`, `108`, `886`
- `symbol`: `test_inflight_registry_load_rejects_duplicate_job_id`, `test_inflight_registry_load_rejects_duplicate_source_path`, `test_http_claim_skips_records_outside_worker_accessible_libraries`
- `problem`: The suite checks duplicate rows when loading an existing registry and checks single-threaded HTTP claim behavior, but I did not find a test that starts two simultaneous `/api/claim` calls against one runnable queue record and proves only one worker receives it.
- `impact`: Duplicate network claims are one of the highest-risk distributed-mode failures because two workers can process the same source and race output/manifest/pending-publish state. Existing tests verify the registry can reject already-corrupt state, not that the live coordinator claim path is race-safe under concurrent worker polling.
- `evidence`: `test_network_workflow.py:74` and `:108` seed duplicate JSON rows directly. `test_network_workflow.py:886` exercises one claim request with library filtering. `ops/pipeline/tests/Unit/Invoke-LocalWorkerSlotChecks.ps1:83` covers local worker duplicate source claims, but that is the PowerShell local-slot path, not coordinator HTTP concurrency.
- `suggested fix direction`: Add a coordinator test with one queue record, two worker IDs, a barrier around `_scan_for_next_record` or real threaded `_http_claim` calls, and assertions that one response is `ok`, the other is `empty`/retry, and the persisted registry has exactly one active job/source.
- `suggested validation/tests`: `apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_network_workflow -q` plus `apps\desktop\runtime\Python\python.exe -m unittest discover -s tests\python\desktop -p "test_network*.py" -q`.

### W12-002

- `id`: W12-002
- `severity`: P2
- `file`: `tests/python/desktop/test_network_join.py`
- `line`: `81`, `120`, `203`, `220`
- `symbol`: `NetworkJoinTests`
- `problem`: Join coverage verifies successful blob creation/import, raw token omission from successful results, no-save when `confirm_import` is missing, and unjournaled Local API routes. It does not exercise malformed, oversized, wrong-schema, or hostile join blobs containing token-like material.
- `impact`: Join blobs intentionally carry a worker auth token. Without adversarial failure tests, a future decode/facade error could echo the pasted blob or embedded token into command results, warnings/errors, logs, or command history, or could partially save worker settings before failing.
- `evidence`: `test_network_join.py:81` decodes a valid generated blob and checks the token is not in the success result. `test_network_join.py:120` imports a valid blob and checks saved config. `test_network_join.py:203` only covers missing confirmation. `test_network_join.py:220` checks successful Local API join routes do not journal. No test posts an invalid blob and asserts no token/blob leakage, no save, no journal entry, and bounded errors.
- `suggested fix direction`: Add facade and Local API tests for invalid base64, wrong schema, too-short token, oversized blob, and a blob/error string containing `token=secret-value`; assert `ok=false`, no config save, no command journal entry, no raw blob/token in serialized response/errors/warnings/logs.
- `suggested validation/tests`: `apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_network_join tests.python.desktop.test_api_command_contracts -q`.

### W12-003

- `id`: W12-003
- `severity`: P2
- `file`: `docs/testing/TEST_COVERAGE_MATRIX.md`
- `line`: `26`, `273`, `277`
- `symbol`: `Network coverage row`
- `problem`: The active coverage matrix still says network lifecycle is design-only/read-only, that the Network page has no lifecycle controls, and that backend dry-run/mutation controls remain unimplemented. Current tests and contracts now expose backend-owned dry-run/start/stop routes, join blob, join import, test-connection, and discovery routes.
- `impact`: Reviewers and future agents using the documented matrix can select the wrong validation rung, skip current network lifecycle route tests, and treat stale no-route assumptions as expected behavior. This is especially risky because the hardening plan repeatedly cites `test_network*.py` as the broad network suite, while W12 scope shows that meaningful coverage also lives in API contract tests, WebView network tests, Tauri scaffold checks, browser smoke wrappers, and PowerShell LocalWorker wrappers.
- `evidence`: `docs/testing/TEST_COVERAGE_MATRIX.md:26` says Network lifecycle controls remain diagnostics/design-only. `:273` says `test_application_facade_network.py` covers lifecycle-control absence and `test_webview_network_read_only_boundary.py` checks no lifecycle/mutation control attributes. `:277` says no coordinator/worker start/stop exist and backend dry-run routes remain unimplemented. Current assigned tests contradict that: `test_webview_network_read_only_boundary.py:383` expects 13 `/api/network/*` routes including confirmed start/stop, and `test_api_contract_payload.py:259` checks backend-owned lifecycle routes are available.
- `suggested fix direction`: Refresh the Network row and validation guidance to distinguish backend-owned lifecycle controls from still-disabled future worker operations, and define a network-mode gate that includes `test_network*.py`, network API contract tests, WebView network boundary/browser smoke, Tauri route semantics, and LocalWorker PowerShell wrappers.
- `suggested validation/tests`: Docs link/file check plus a non-mutating command list such as bundled Python `unittest discover -s tests\python\desktop -p "test_network*.py" -q`, targeted API/WebView/Tauri network tests, `ops\scripts\smoke\Test-WebViewBrowserNetworkSmoke.ps1`, and `ops\pipeline\tests\Unit\Invoke-LocalWorker*.ps1`.

### W12-004

- `id`: W12-004
- `severity`: P3
- `file`: `tests/webview/test_webview_browser_network_smoke.py`
- `line`: `683`, `696`
- `symbol`: `_network_payload`
- `problem`: The browser Network smoke fixture sets `requires_confirmation: False` for `/api/network/coordinator/join-blob` and `/api/network/worker/join-cluster`, even though those are `secret-transfer` and `config-write` routes whose real contract requires confirmation.
- `impact`: The real contract is covered elsewhere, but the browser smoke’s contract fixture is stale. If Network rendering regresses around confirmation metadata for join/create/import controls, this smoke may continue to pass against a misleading contract payload.
- `evidence`: `tests/webview/test_webview_browser_network_smoke.py:683` and `:696` mark both join routes as `requires_confirmation: False`. `tests/webview/test_webview_network_read_only_boundary.py:431` and `:445` assert the real Local API route contract has `requires_confirmation` true for both routes.
- `suggested fix direction`: Derive the browser smoke route list from `LOCAL_API_ROUTE_CONTRACT` or update the fixture to match the real route metadata. Add a browser assertion that join/create/import controls remain confirmation-gated in rendered copy or command payloads.
- `suggested validation/tests`: `apps\desktop\runtime\Python\python.exe -m unittest tests.webview.test_webview_browser_network_smoke tests.webview.test_webview_network_read_only_boundary -q`.

## Test Coverage Gaps

- Add a concurrent coordinator `/api/claim` race test for two workers and one source.
- Add malformed/hostile join blob tests that assert no partial save, no command history entry, bounded error text, and no raw blob/token leakage.
- Refresh the Network coverage matrix and define a single non-mutating network-mode validation bundle that includes Python network discovery, network API contract tests, WebView boundary/browser smoke, Tauri route semantics, and LocalWorker PowerShell wrappers.
- Align the browser Network smoke fixture with the real Local API contract for join routes.
- Generate a summary/project-index entry for `tests/python/desktop/test_network_coordinator_policy_phase_e.py` before treating that high-risk Phase E coverage as part of normal agent navigation.

## Boundary Risks

- The Python unit suite is broad and strong for isolated protocol, registry, worker-state, and coordinator handler behavior, but most tests use synthetic `SimpleNamespace` dispatchers rather than a live coordinator HTTP server with multiple workers. That is acceptable for narrow unit coverage, but it does not replace a race-focused concurrency test for claims.
- Browser Network smoke coverage is intentionally no-mutation and fixture-heavy. It is appropriate for WebView rendering and boundary checks, but it cannot prove lifecycle start/stop, real worker polling, real LAN discovery, real source access, or queue/state corruption safety.
- The PowerShell LocalWorker wrappers cover local slot/claim integrity with temp files, but they are not included in the documented `test_network*.py` discovery command.
- The worktree already contains unrelated dirty/untracked files, including high-risk Phase E policy work. I did not modify or revert them.

## Files With No Findings

Reviewed with no new W12-specific findings beyond the coverage gaps above:

- `tests/python/desktop/test_network_coordinator_helpers.py`
- `tests/python/desktop/test_network_coordinator_http.py`
- `tests/python/desktop/test_network_coordinator_source_policy.py`
- `tests/python/desktop/test_network_coordinator_startup.py`
- `tests/python/desktop/test_network_crash_recovery.py`
- `tests/python/desktop/test_network_done_release.py`
- `tests/python/desktop/test_network_drift_descriptor.py`
- `tests/python/desktop/test_network_firewall.py`
- `tests/python/desktop/test_network_inflight_registry.py`
- `tests/python/desktop/test_network_lifecycle_fixes.py`
- `tests/python/desktop/test_network_library_relative_claim.py`
- `tests/python/desktop/test_network_local_ip.py`
- `tests/python/desktop/test_network_mdns.py`
- `tests/python/desktop/test_network_path_auto_map.py`
- `tests/python/desktop/test_network_protocol_runtime.py`
- `tests/python/desktop/test_network_security.py`
- `tests/python/desktop/test_network_test_connection.py`
- `tests/python/desktop/test_network_worker_runtime.py`
- `tests/python/desktop/test_network_worker_source_policy.py`
- `tests/python/desktop/test_network_worker_state.py`
- `tests/python/desktop/test_api_command_contracts.py`
- `tests/python/desktop/test_api_contract_payload.py`
- `tests/python/desktop/test_application_facade_network.py`
- `tests/python/desktop/test_local_api_lifecycle_contract_smoke.py`
- `tests/python/desktop/test_tauri_shell_scaffold.py`
- `tests/webview/test_webview_network_read_only_boundary.py`
- `ops/scripts/smoke/Test-WebViewBrowserNetworkSmoke.ps1`
- `ops/pipeline/tests/Unit/Invoke-LocalWorkerSlotChecks.ps1`
- `ops/pipeline/tests/Unit/Invoke-LocalWorkerClaimLifecycleChecks.ps1`

## Incomplete Coverage

- `tests/python/desktop/test_network_coordinator_policy_phase_e.py` was reviewed directly but is untracked and lacks a generated summary. Because it is outside generated navigation, I do not treat it as fully integrated suite coverage.
- I did not run the assigned tests; this worker pass is static review only. No live coordinator, worker, browser, LAN, media, queue, publish, drain, rename, settings-save, or lifecycle command was executed.
- I did not inspect non-assigned source implementations except through assigned tests and required docs, so findings are coverage/test-suite findings, not source-code defect claims.

## Suggested Follow-Up Prompts

- Add a concurrent `/api/claim` race regression test that uses two worker IDs against one queue record and proves exactly-once claim assignment plus persisted registry integrity.
- Add malformed join blob and secret-redaction regression tests for facade and Local API paths.
- Refresh `docs/testing/TEST_COVERAGE_MATRIX.md` for current backend-owned Network lifecycle routes and define a single W12-style network validation bundle.
- Normalize `tests/webview/test_webview_browser_network_smoke.py` route fixtures against `LOCAL_API_ROUTE_CONTRACT`.
