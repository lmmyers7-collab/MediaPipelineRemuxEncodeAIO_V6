# Worker Review: W11 - Network Read DTOs, Diagnostics, Drift, And Operator Evidence

## Scope

Reviewed the read-only evidence path for `GET /api/network/workers`: backend DTO assembly, route/contract registration, worker runtime descriptors, diagnostic-layer helpers, failure-reason helpers, worker-board state rows, drift evidence, progress evidence, lifecycle-state summaries, token posture, and targeted test evidence.

Review only. No source, generated summaries, runtime state, config, queue, media, or aggregate review files were edited.

## Required Reads Completed

- `AGENTS.md`
- `docs/CURRENT_PROJECT_STATE.md`
- `docs/OPEN_WORK_CHECKLIST.md`
- `docs/generated/PROJECT_INDEX.md`
- `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`
- `docs/architecture/NETWORK_WORKER_HARDENING_PLAN.md`
- `docs/inventories/LOCAL_API_ROUTE_OWNERSHIP_MAP.md`
- `docs/reviews/network-coordinator-worker-mode-2026-06-15/PROMPT_PACK.md`
- Generated summaries for assigned source/test files before full source reads:
  - `src/mediapipeline/core/network/facade.py`
  - `src/mediapipeline/desktop/network/diagnostics.py`
  - `src/mediapipeline/desktop/network/failure_reasons.py`
  - `src/mediapipeline/desktop/network/failure_policy.py`
  - `src/mediapipeline/desktop/network/worker.py`
  - `src/mediapipeline/core/kernel/dto_workspaces.py`
  - `src/mediapipeline/desktop/api/routes_read.py`
  - `src/mediapipeline/desktop/api/contract_read.py`
  - `src/mediapipeline/desktop/application/facade.py`
  - `apps/desktop/webview/static/assets/networkView.js`
  - assigned Python/WebView test summaries

## Coverage Ledger

| File / symbol | Coverage | Notes |
|---|---:|---|
| `src/mediapipeline/core/network/facade.py` | Full for W11 route payload | Reviewed worker rows, state files, progress, lifecycle, token posture, drift, diagnostic layers, operator summaries, and `get_network_workers`. |
| `src/mediapipeline/desktop/network/worker.py` runtime descriptor methods | Focused | Reviewed descriptor, URL/token/path-map snapshot, manual/auto map combination. |
| `src/mediapipeline/desktop/network/diagnostics.py` | Full | Bounded preview helper only; no W11 route finding. |
| `src/mediapipeline/desktop/network/failure_reasons.py` | Full | Reason-code normalization/detail bounding reviewed. |
| `src/mediapipeline/desktop/network/failure_policy.py` | Full | Prior-failure helper reviewed; no W11 DTO finding. |
| `src/mediapipeline/core/kernel/dto_workspaces.py` `NetworkWorkersDto` | Full | DTO contains expected read-only evidence fields. |
| `src/mediapipeline/desktop/api/routes_read.py` | Focused | Verified `/api/network/workers` maps to `_network_workers_payload`. |
| `src/mediapipeline/desktop/api/contract_read.py` | Focused | Verified read contract schema/effect/purpose. |
| `apps/desktop/webview/static/assets/networkView.js` | Focused | Reviewed W11-relevant worker-board/progress/lifecycle wording by search; W10 owns full UI review. |
| Assigned tests | Focused | Read targeted tests and ran two temp-only payload probes with bundled Python. Did not run full browser smoke. |

## Findings

| id | severity | file | line / symbol | summary |
|---|---|---|---|---|
| W11-001 | P2 | `src/mediapipeline/core/network/facade.py` | `_worker_running_vs_saved` | Auto-derived path maps can be reported as saved-config drift. |
| W11-002 | P2 | `src/mediapipeline/core/network/facade.py` | `_safe_worker_state` / `get_network_workers` | Malformed `worker_state.json` warns globally but still appears as a present, error-free state-file row. |
| W11-003 | P2 | `src/mediapipeline/core/network/facade.py` | `_runtime_status_from_lifecycle` / `_network_worker_progress` | A stale active `worker_state.json` can report `Runtime: Stopped (match)` while progress and claim evidence report an active local worker. |
| W11-004 | P2 | `src/mediapipeline/core/network/facade.py` | `_network_worker_progress` summary | Read/progress evidence still says WebView does not start/stop workers, conflicting with implemented backend-owned lifecycle controls. |

## Detailed Findings

### W11-001

- `id`: W11-001
- `severity`: P2
- `file`: `src/mediapipeline/core/network/facade.py`
- `line`: 656-701
- `symbol`: `_worker_running_vs_saved`
- `problem`: Drift compares the running worker's effective path map against only the saved manual `WorkerSourcePathMap`. The running descriptor uses `WorkerDispatcher.runtime_descriptor()`, which reports `_source_path_map`; that is the combined manual plus auto-derived library map from `worker.py:282-300` and `worker.py:472-480`. `test_network_path_auto_map.py:118` confirms auto-map refresh raises `runtime_descriptor()["path_map_entries"]` to 3 even when those entries are not saved in `WorkerSourcePathMap`.
- `impact`: A correctly auto-mapped worker can be shown as having saved-config drift on `source_path_map`, with the operator summary telling them to restart worker polling. That is misleading evidence during the exact multi-library path-map scenario the hardening plan prioritizes.
- `evidence`: `facade.py:658` builds `saved_map` only from `config.get("WorkerSourcePathMap")`; `facade.py:697-701` treats count/fingerprint differences as `source_path_map` drift; `worker.py:297-300` merges manual and auto maps into `_source_path_map`; `worker.py:477-480` reports the effective count/fingerprint.
- `suggested fix direction`: Split descriptor evidence into manual, auto, and effective path-map fields. Compare saved manual settings only against running manual settings, and present auto-derived map entries as separate positive runtime evidence, not saved-config drift.
- `suggested validation/tests`: Add a drift test where saved `WorkerSourcePathMap` is blank, `/api/libraries` has matched library roots, and the live descriptor has auto entries; expected status should be `match` or `auto_map_active`, not `drift`.

### W11-002

- `id`: W11-002
- `severity`: P2
- `file`: `src/mediapipeline/core/network/facade.py`
- `line`: 404-420 and 1713-1747
- `symbol`: `_safe_worker_state`, `_state_file_row`, `get_network_workers`
- `problem`: When `worker_state.json` is malformed, `_safe_worker_state()` appends a warning and returns `{}`, but the corresponding `state_files` row is created later by `_state_file_row()` from file stat only. The row remains `status: "present"` with no `error`, unlike malformed `coordinator_inflight.json`, which is copied back into the row as `unreadable`.
- `impact`: Operators can see a global warning that worker state is unreadable while the state-file table says the local worker state file is present and clean. That weakens the route's usefulness for corrupt-state triage.
- `evidence`: Temp-only bundled-Python probe with malformed `worker_state.json` returned `warnings: ["Worker state could not be read: ..."]` while `state_files["worker_state"]` was `exists: true`, `status: "present"`, `error: ""`. Existing test coverage at `test_application_facade_network.py:115-137` covers malformed coordinator state, but no equivalent worker-state row test exists.
- `suggested fix direction`: Return structured worker-state read evidence from `_safe_worker_state()` or track a `worker_state_error` beside `coordinator_state_error`, then mark the `worker_state` row `unreadable` with a bounded redacted error.
- `suggested validation/tests`: Add `test_network_workers_marks_malformed_worker_state_as_unreadable`, asserting both the warning and `state_files["worker_state"]["status"] == "unreadable"`.

### W11-003

- `id`: W11-003
- `severity`: P2
- `file`: `src/mediapipeline/core/network/facade.py`
- `line`: 513-542, 335-349, and 1025-1031
- `symbol`: `_runtime_status_from_lifecycle`, `_network_worker_progress_bars`, `_network_diagnostic_layers`
- `problem`: A `worker_state.json` with `job_id` but no `pending_done_report` is treated as an active local claim for progress and diagnostic layers, but `_runtime_status_from_lifecycle()` only blocks on `pending_done_report`. If session-memory lifecycle state is stopped, the payload can report `Runtime: Stopped (match)` with no warnings while progress shows active local worker bars and `last_claim_result` is `ready`.
- `impact`: Stale or crash-leftover worker state can look simultaneously stopped and active. That is not a lifecycle mutation by itself, but it can mislead the operator about whether to repair/clear worker state, restart worker polling, or trust the current claim evidence.
- `evidence`: Temp-only bundled-Python probe with `worker_state.json = {"job_id":"stale-job","source_path":"C:\\Media\\Movie.mkv"}` and stopped lifecycle returned `runtime_status_label: "Stopped"`, `runtime_status_severity: "match"`, no warnings, `network_local_worker` status `active`, and operator lines containing both `Runtime: Stopped (match)` and `Worker current claim: stale-job`.
- `suggested fix direction`: Treat a local worker `job_id` as active/stale claim evidence in runtime status. If lifecycle is not running, mark the runtime status `warning` or `blocked` and add an actionable warning to inspect/repair/clear `worker_state.json` or start worker crash recovery before trusting claims.
- `suggested validation/tests`: Add a test for active `worker_state.json` plus stopped lifecycle, asserting non-match runtime severity and an explicit stale/claim warning.

### W11-004

- `id`: W11-004
- `severity`: P2
- `file`: `src/mediapipeline/core/network/facade.py`
- `line`: 381-388
- `symbol`: `_network_worker_progress`
- `problem`: The progress DTO summary still says, "WebView does not start/stop workers..." even though current route ownership and WebView route contract now expose backend-owned, confirmation-gated network lifecycle start/stop controls. The read route itself is read-only, but the wording describes the whole WebView surface as lacking start/stop authority.
- `impact`: Operators and future agents can get conflicting guidance: one Network panel says backend lifecycle controls exist, while the progress/read evidence says WebView does not start/stop workers. That is exactly the absent/design-only/dry-run-only/implemented drift the prompt calls out.
- `evidence`: `facade.py:388` returns the stale line in `desktop_network_worker_progress.v1`; `contract_read.py:419` says `/api/network/workers` is for visibility "without lifecycle controls"; current `docs/inventories/LOCAL_API_ROUTE_OWNERSHIP_MAP.md:231-244` documents dry-run and confirmed coordinator/worker lifecycle routes, and `networkView.js:2002` says backend-owned lifecycle controls are available through contract routes.
- `suggested fix direction`: Reword read/progress evidence to: this read/progress panel is read-only and cannot start/stop directly; coordinator/worker start/stop lives in separate backend-owned, confirmation-gated lifecycle command routes. Avoid broad "WebView does not start/stop" wording.
- `suggested validation/tests`: Update WebView/network text assertions to require "read/progress panel is read-only" plus "lifecycle controls use separate backend routes" wording.

## Test Coverage Gaps

- No test covers running-vs-saved drift when effective path-map entries come from auto-derived library maps rather than saved `WorkerSourcePathMap`.
- No test marks malformed `worker_state.json` as an unreadable `state_files` row; current coverage only covers malformed `coordinator_inflight.json`.
- No test covers active `worker_state.json` plus stopped session lifecycle state, where runtime status and progress currently contradict each other.
- Existing text checks do not prevent stale "WebView does not start/stop workers" wording after backend-owned lifecycle controls became available.
- I did not run `tests/webview/test_webview_browser_network_smoke.py`; browser-level rendering risk remains for W10/W12/master synthesis.

## Boundary Risks

- The reviewed route stays read-only and does not directly mutate source, queue, state, config, lifecycle, publish/drain, rename, or media files.
- The main boundary risk is operator-evidence accuracy: stale or contradictory read DTOs can push the operator toward unnecessary restart/reconfiguration or make stale worker state look safe.
- Token posture and drift descriptors use fingerprints/hidden displays; I did not find clear-token exposure in the reviewed `/api/network/workers` path.
- Source paths remain visible in worker rows by design for local authenticated operator evidence; this review did not classify source-path visibility as a secret leak.

## Files With No Findings

- Reviewed: no findings - `src/mediapipeline/desktop/network/diagnostics.py` (`diagnostic_preview` is bounded; no direct W11 route issue found).
- Reviewed: no findings - `src/mediapipeline/desktop/network/failure_reasons.py` (known reason codes, single-line bounded reason detail, unknown-code rejection).
- Reviewed: no findings - `src/mediapipeline/desktop/network/failure_policy.py` (prior-failure helper only; no W11 DTO issue).
- Reviewed: no findings - `src/mediapipeline/core/kernel/dto_workspaces.py` `NetworkWorkersDto` (schema carries the expected read-only evidence fields).
- Reviewed: no findings - `src/mediapipeline/desktop/api/routes_read.py` `/api/network/workers` route registration.

## Incomplete Coverage

- Did not review the full 3,000-line `apps/desktop/webview/static/assets/networkView.js`; only W11-relevant route, worker-board, progress, diagnostic-layer, drift, and lifecycle wording was inspected.
- Did not run the full assigned test set. Evidence includes source reads, test reads, `rg` searches, and two temp-only bundled-Python payload probes.
- Did not attach to a live two-machine coordinator/worker cluster, start/stop lifecycle providers, claim work, or run real media.
- Did not edit or refresh generated summaries because the worker prompt forbids generated-summary edits.

## Suggested Follow-Up Prompts

- W11 follow-up fix prompt: Patch `/api/network/workers` drift evidence to distinguish manual, auto-derived, and effective path maps, then add the missing auto-map drift test.
- W11 follow-up fix prompt: Patch worker-state read evidence so malformed and stale active worker state produce consistent state-file rows, runtime severity, warnings, and tests.
- W14/master follow-up prompt: Reconcile active docs and read/contract wording for implemented backend-owned Network lifecycle controls versus older design-only/absent wording.
