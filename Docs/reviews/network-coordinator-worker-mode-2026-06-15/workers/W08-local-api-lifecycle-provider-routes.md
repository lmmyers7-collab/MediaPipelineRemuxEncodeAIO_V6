# Worker Review: W08 - Local API Lifecycle Provider Routes

## Scope

Reviewed the Local API network lifecycle facade, desktop lifecycle provider, route/payload contracts, command-journal path, and Tauri backend-contract route metadata for coordinator/worker lifecycle behavior. The review was static plus assigned unit/static evidence only. I did not start or stop real network providers.

## Required Reads Completed

- `AGENTS.md`
- `docs/CURRENT_PROJECT_STATE.md`
- `docs/OPEN_WORK_CHECKLIST.md`
- `docs/generated/PROJECT_INDEX.md`
- `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`
- `docs/architecture/NETWORK_LIFECYCLE_COMMAND_CONTRACT.md`
- `docs/inventories/API_ROUTE_INVENTORY.md`
- `docs/inventories/COMMAND_OWNERSHIP_MATRIX.md`
- `docs/inventories/LOCAL_API_ROUTE_OWNERSHIP_MAP.md`
- `docs/reviews/network-coordinator-worker-mode-2026-06-15/PROMPT_PACK.md`
- Generated summaries for assigned source, route metadata, and assigned evidence tests.

## Coverage Ledger

| File | Status | Notes |
|---|---|---|
| `src/mediapipeline/core/network/lifecycle_facade.py` | reviewed | Lifecycle preconditions, dry-run payloads, confirmation gate, provider/journal sequencing. Finding W08-002. |
| `src/mediapipeline/desktop/application/network_lifecycle_provider.py` | reviewed | Provider start/stop, runtime registry, active claimed-job handling. Findings W08-001 and W08-004. |
| `src/mediapipeline/core/api/commands_network.py` | reviewed | Route payload methods and strict journal handoff for confirmed lifecycle routes. No finding. |
| `src/mediapipeline/core/api/commands.py` | reviewed | Command route registry for all Network command routes. No finding. |
| `src/mediapipeline/contracts/api_commands.py` | reviewed | Strict Pydantic command payload models. No finding. |
| `src/mediapipeline/desktop/api/contract_command.py` | reviewed | Network command route metadata. No finding in Python contract; used as expected-contract evidence. |
| `src/mediapipeline/desktop/api/contract_payload.py` | reviewed | Published lifecycle contract, source-file policy, rollback/journal fields. No finding in contract; used as expected-contract evidence. |
| `src/mediapipeline/desktop/api/routes_command.py` | reviewed | POST route handler map generation. No finding. |
| `src/mediapipeline/desktop/api/handler.py`, `server.py`, `command_journal.py` | narrow review | Command-result journaling and strict lifecycle journal behavior. No finding. |
| `apps/desktop/tauri/src-tauri/src/backend_contract/routes.rs` | reviewed | Required route list and lifecycle route metadata. Finding W08-003. |
| `apps/desktop/tauri/src-tauri/src/backend_contract/route_contract.rs`, `types.rs` | reviewed | Tauri contract semantic validation for lifecycle metadata. No finding. |
| `src/mediapipeline/desktop/network/worker.py`, `worker_loops.py`, `worker_claims.py` | supporting review | Worker poll startup and claim handoff path for provider-start race. Finding W08-004. |
| Assigned tests | reviewed/run | `unittest` run covered seven assigned test modules; one existing route-drift failure found. |

## Findings

| id | severity | file | line / symbol | problem |
|---|---|---|---|---|
| W08-001 | P1 | `src/mediapipeline/desktop/application/network_lifecycle_provider.py` | `stop_network_worker`, `stop_network_coordinator` | Normal lifecycle stop aborts active worker/coordinator-local pipeline work even though the contract says abort is separate. |
| W08-002 | P2 | `src/mediapipeline/core/network/lifecycle_facade.py` | `_network_lifecycle_dry_run_data` | Stop dry-runs do not report in-memory active worker/local-worker jobs and hard-code active worker count to zero. |
| W08-003 | P2 | `apps/desktop/tauri/src-tauri/src/backend_contract/routes.rs` | `REQUIRED_ROUTES` | Tauri required-route metadata omits three Python Local API Network command routes; assigned test suite fails. |
| W08-004 | P2 | `src/mediapipeline/desktop/application/network_lifecycle_provider.py` | `start_network_worker` | Worker polling can start before `app.dispatcher` and runtime state are attached, creating a claim-release startup race. |

## Detailed Findings

### W08-001 - Normal worker/coordinator stop aborts active local work

- `severity`: P1
- `file`: `src/mediapipeline/desktop/application/network_lifecycle_provider.py`
- `line`: `stop_network_worker` at lines 426-456; `stop_network_coordinator` at lines 370-405
- `symbol`: `NetworkLifecycleProviderMixin.stop_network_worker`, `NetworkLifecycleProviderMixin.stop_network_coordinator`
- `problem`: The confirmed worker stop path calls `app.abort_current_worker_job("network worker stop")` before dispatcher shutdown. The confirmed coordinator stop path does the same for coordinator-local work with `app.abort_current_worker_job("network coordinator stop")`. `abort_current_worker_job()` delegates to `kill_process_tree()` or `terminate()`, so the ordinary confirmed stop route can kill an active single-file pipeline process.
- `impact`: This violates the published worker-stop contract that says pending done reports and `worker_state.json` are preserved and "Abort/partial scratch cleanup remains a separate explicit command" (`contract_command.py` lines 810-823). It also conflicts with coordinator-stop contract text that active local encode work must not be silently abandoned (`contract_payload.py` lines 184-188). A normal stop can turn active work into failed/partial scratch or output state and may create or lose done/report evidence depending on timing.
- `evidence`: `network_lifecycle_provider.py` lines 439-452 abort the active worker job, then calls dispatcher shutdown. Lines 388-391 abort coordinator-local worker work during coordinator stop. The regression test at `tests/python/desktop/test_network_lifecycle_fixes.py` lines 350-375 stubs `kill_process_tree` and asserts only that the coordinator claim is not released when the process is still running; it does not assert that stop avoids attempting the kill.
- `suggested fix direction`: Make lifecycle stop cooperative by stopping polling/new claims and waiting or reporting `active_work_still_running` without killing the active pipeline process. Keep claim preservation. Move forced abort into a separate explicit command/confirmation path if still needed.
- `suggested validation/tests`: Add tests where active worker and coordinator-local jobs are running and confirmed stop does not call `kill_process_tree()` or `terminate()`, does not release an active claim unless the process has actually exited, and preserves pending done reports.

### W08-002 - Lifecycle dry-runs hide active in-memory work

- `severity`: P2
- `file`: `src/mediapipeline/core/network/lifecycle_facade.py`
- `line`: lines 420-430
- `symbol`: `NetworkLifecycleFacadeMixin._network_lifecycle_dry_run_data`
- `problem`: The dry-run payload always returns `active_work.reported_worker_count: 0` and only derives `pending_done_reports` from the pending-done precondition. Stop preconditions are idempotent and pass regardless of current lifecycle status. The dry-run never inspects `_network_dispatcher_runtime`, `_NetworkRuntimeApp.has_active_worker_job()`, or `WorkerDispatcher.get_active_job()`.
- `impact`: Operator dry-runs can report `safe_to_apply=true` while a worker or coordinator-local job is actively processing. Combined with W08-001, the dry-run can present an ordinary stop as safe even though the confirmed route will attempt to abort the running process.
- `evidence`: `lifecycle_facade.py` lines 420-430 hard-code active-work evidence, and lines 255-263 make duplicate stop always pass. Runtime entries exist in `network_lifecycle_provider.py` lines 218-223, and `_NetworkRuntimeApp.has_active_worker_job()` exists at lines 208-210, but the facade dry-run does not use them.
- `suggested fix direction`: Have dry-run preconditions inspect the in-memory runtime registry for coordinator and worker entries. Report active job count, role, claim/job id prefix, process-running posture, and pending done state. Treat confirmed stop as blocked or at least review when active work is present unless an explicit active-work stop policy is added.
- `suggested validation/tests`: Add dry-run tests with active worker and coordinator-local jobs and assert `active_work.reported_worker_count > 0`, `safe_to_apply` is not clean pass, and `would_not_touch` remains present.

### W08-003 - Tauri required routes omit current Network setup commands

- `severity`: P2
- `file`: `apps/desktop/tauri/src-tauri/src/backend_contract/routes.rs`
- `line`: lines 110-118
- `symbol`: `REQUIRED_ROUTES`
- `problem`: Tauri's startup contract route list includes lifecycle dry-runs, worker test-connection, and lifecycle start/stop, but omits three current Python Local API Network command routes: `POST /api/network/coordinator/join-blob`, `POST /api/network/worker/discover-coordinators`, and `POST /api/network/worker/join-cluster`.
- `impact`: The Tauri shell can stop checking that the backend exposes route metadata for setup/join/discovery commands even though the Python route contract publishes them. The assigned route parity test currently fails, so this is an active metadata drift rather than only a missing future guard.
- `evidence`: `routes.rs` lines 110-118 omit the three routes. Python registers them in `src/mediapipeline/core/api/commands.py` lines 61, 67, and 68, and publishes their command contract metadata in `contract_command.py` lines 738-764. Running the assigned test command failed `test_tauri_shell_required_routes_match_python_local_api_contract` with exactly those three routes missing from Rust; the assertion is at `tests/python/desktop/test_tauri_shell_scaffold.py` lines 433-456.
- `suggested fix direction`: Add the three missing Network command routes to Tauri `REQUIRED_ROUTES`. If setup commands need semantic metadata beyond generic route presence, add explicit required metadata tests for `effect`, `journaled`, and `requires_confirmation`.
- `suggested validation/tests`: Re-run `python -m unittest tests.python.desktop.test_tauri_shell_scaffold` and the full W08 assigned suite.

### W08-004 - Worker polling starts before dispatcher is attached to the runtime app

- `severity`: P2
- `file`: `src/mediapipeline/desktop/application/network_lifecycle_provider.py`
- `line`: lines 418-424
- `symbol`: `NetworkLifecycleProviderMixin.start_network_worker`
- `problem`: `start_network_worker()` constructs `WorkerDispatcher(app)` before assigning `app.dispatcher = dispatcher` and before registering `runtime["worker"]`. `WorkerDispatcher.__init__()` starts the polling thread immediately (`worker.py` lines 171-172). A fast coordinator claim can therefore reach `_NetworkRuntimeApp._worker_start_single_file()` while `app.dispatcher` is still `None`.
- `impact`: A valid claim can be saved, heartbeated, then released as "encode start failed" during worker startup even though the worker would have been valid milliseconds later. This causes false failures/churn and can create pending release evidence before lifecycle start is fully journaled and committed.
- `evidence`: `network_lifecycle_provider.py` lines 418-424 attach the dispatcher after construction. `worker.py` lines 171-172 starts the poll thread in the constructor. `_NetworkRuntimeApp._worker_start_single_file()` raises when `self.dispatcher is None` at `network_lifecycle_provider.py` lines 110-113. `worker_claims.py` lines 142-156 catches that exception and releases the claim.
- `suggested fix direction`: Decouple worker dispatcher construction from polling start, or pass/attach the dispatcher before the poll thread can claim. A safe shape is `dispatcher = WorkerDispatcher(app, autostart=False)`, attach `app.dispatcher` and runtime entry, then call `dispatcher.start_polling()` after lifecycle state/journal setup reaches the intended point.
- `suggested validation/tests`: Add a fake dispatcher/poll-loop test that claims immediately during startup and proves `_worker_start_single_file()` sees an attached dispatcher and does not release a valid claim due to startup ordering.

## Test Coverage Gaps

- No test asserts that confirmed worker/coordinator stop avoids `kill_process_tree()` or `terminate()` for active jobs. The current regression test stubs the kill call and checks only release behavior.
- No dry-run test constructs an active `_network_dispatcher_runtime` job and verifies active-work reporting.
- No worker startup test forces an immediate claim during `WorkerDispatcher.__init__()` before `app.dispatcher` is assigned.
- The assigned Tauri route parity test already catches W08-003 and is currently failing.

## Boundary Risks

- Source media mutation: no direct source delete/rename/write path found in W08 lifecycle routes.
- Scratch/output risk: W08-001 can abort an active pipeline process through normal lifecycle stop, which can leave partial scratch/output state even if source media remains protected.
- Pending publish and queue mutation: lifecycle dry-runs and start/stop routes do not directly drain, publish, or rewrite queue manifests. Active-job abort/release behavior can still affect coordinator claim/done state.
- Command journal: confirmed lifecycle success uses strict journal recording before state commit, and API handler fallback journals validation/precondition failures unless strict lifecycle recording already succeeded. No W08 finding for command journal routing.
- Tauri route metadata: lifecycle semantics are checked, but three current Network setup routes are missing from the required route list.

## Files With No Findings

- Reviewed: no findings - `src/mediapipeline/core/api/commands_network.py`
- Reviewed: no findings - `src/mediapipeline/core/api/commands.py`
- Reviewed: no findings - `src/mediapipeline/contracts/api_commands.py`
- Reviewed: no findings - `src/mediapipeline/desktop/api/contract_command.py` for Python Network lifecycle metadata
- Reviewed: no findings - `src/mediapipeline/desktop/api/contract_payload.py`
- Reviewed: no findings - `src/mediapipeline/desktop/api/routes_command.py`
- Reviewed: no findings - `src/mediapipeline/desktop/api/handler.py` narrow command-journal path
- Reviewed: no findings - `src/mediapipeline/desktop/api/server.py` narrow command-journal path
- Reviewed: no findings - `src/mediapipeline/desktop/api/command_journal.py` narrow strict-write behavior
- Reviewed: no findings - `apps/desktop/tauri/src-tauri/src/backend_contract/route_contract.rs`
- Reviewed: no findings - `apps/desktop/tauri/src-tauri/src/backend_contract/types.rs`

## Incomplete Coverage

- Did not run real coordinator or worker providers, bind ports, poll a real coordinator, or process media.
- Did not review WebView Network UI behavior except as route metadata evidence through assigned tests.
- Did not line-review all non-lifecycle Network setup implementation (`join`, mDNS discovery, test-connection); only route registration and Tauri parity were reviewed where they intersected W08.
- Did not review PowerShell worker compatibility.

## Suggested Follow-Up Prompts

- "Fix W08-001 and W08-002 by making Network lifecycle stop cooperative and adding active-work dry-run reporting/tests."
- "Fix W08-003 by syncing Tauri required routes with the Python Local API contract and rerunning the Tauri scaffold suite."
- "Fix W08-004 by making WorkerDispatcher startup two-phase so polling cannot claim before the runtime app is fully attached."

## Validation Evidence

- `PYTHONPATH=src apps/desktop/runtime/Python/python.exe -m unittest tests.python.desktop.test_api_command_contracts tests.python.desktop.test_api_contract_payload tests.python.desktop.test_application_facade_network tests.python.desktop.test_application_facade_process_launch tests.python.desktop.test_network_lifecycle_fixes tests.python.desktop.test_local_api_lifecycle_contract_smoke tests.python.desktop.test_tauri_shell_scaffold` - failed 1 of 172 tests. Failure: `test_tauri_shell_required_routes_match_python_local_api_contract`, missing Rust required routes for `POST /api/network/coordinator/join-blob`, `POST /api/network/worker/discover-coordinators`, and `POST /api/network/worker/join-cluster`.
