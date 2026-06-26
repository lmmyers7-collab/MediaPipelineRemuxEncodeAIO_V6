# Worker Review: W03 - Coordinator Claim Registry Retry

## Scope

Review-only audit of coordinator claim selection, in-flight registry state, retry suppression, encode config snapshotting, library accessibility filtering, and network-role launch boundaries.

Assigned source files:

- `src/mediapipeline/desktop/network/coordinator_queue.py`
- `src/mediapipeline/desktop/network/registry.py`
- `src/mediapipeline/desktop/network/failure_policy.py`
- `src/mediapipeline/desktop/network/encode_config_snapshot.py`
- `src/mediapipeline/desktop/network/library_roots.py`
- `src/mediapipeline/desktop/network/dispatcher.py`
- `src/mediapipeline/desktop/network/standalone.py`
- `src/mediapipeline/core/processes/pipeline_policy.py`

Supporting source read for claim/done request sequencing:

- `src/mediapipeline/desktop/network/coordinator_http_handlers.py`
- `src/mediapipeline/desktop/network/coordinator.py`
- `src/mediapipeline/desktop/network/coordinator_state.py`
- `src/mediapipeline/desktop/network/processing_policy.py`
- `src/mediapipeline/desktop/application/network_lifecycle_provider.py`

## Required Reads Completed

- `AGENTS.md`
- `docs/CURRENT_PROJECT_STATE.md`
- `docs/OPEN_WORK_CHECKLIST.md`
- `docs/generated/PROJECT_INDEX.md`
- `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`
- `docs/architecture/NETWORK_WORKER_HARDENING_PLAN.md`
- `docs/architecture/NETWORK_LIFECYCLE_COMMAND_CONTRACT.md`
- `docs/inventories/COMMAND_OWNERSHIP_MATRIX.md`
- `docs/reviews/network-coordinator-worker-mode-2026-06-15/PROMPT_PACK.md`
- Generated summaries for all assigned source files and assigned evidence tests.

## Coverage Ledger

| File | Coverage | Notes |
|---|---|---|
| `src/mediapipeline/desktop/network/coordinator_queue.py` | Reviewed | `claim_next`, `_scan_for_next_record`, retry suppression, local save rollback, queue removal, prior-failure wrapper, config snapshot wrapper. |
| `src/mediapipeline/desktop/network/registry.py` | Reviewed | Claim, worker-seen, heartbeat, complete, unclaim, rollback, failure ledger, stale reclaim, in-flight checks, save/load. |
| `src/mediapipeline/desktop/network/failure_policy.py` | Reviewed | Prior failure source matching. Covered by W03-002 path-identity finding. |
| `src/mediapipeline/desktop/network/encode_config_snapshot.py` | Reviewed | Snapshot keys and disabled `WorkerConfigOverrides` handling. No finding. |
| `src/mediapipeline/desktop/network/library_roots.py` | Reviewed | Library IDs, safe relative paths, worker root resolution, auto/manual map merge, accessible IDs. No finding. |
| `src/mediapipeline/desktop/network/dispatcher.py` | Reviewed | Shared `ClaimedJob` contract and dispatcher interface. No finding. |
| `src/mediapipeline/desktop/network/standalone.py` | Reviewed | Standalone dispatcher compatibility only. No network coordinator finding. |
| `src/mediapipeline/core/processes/pipeline_policy.py` | Reviewed | Network role normalization, normal Launch block, `CoordinatorAlsoEncodeLocally` strict true check. No finding. |
| `tests/python/desktop/test_network_inflight_registry.py` | Reviewed | Covers atomic save, save failure, malformed rows, retry ledger, worker override ignore. Missing W03-002/W03-003 cases. |
| `tests/python/desktop/test_network_workflow.py` | Reviewed | Covers claim save failure rollback, accessible library filtering, retry quarantine, active-count fallback. Missing normalized source identity cases. |
| `tests/python/desktop/test_network_coordinator_helpers.py` | Reviewed | Covers snapshot override ignore and prior failure casefold match. Missing slash/root-normalization case. |
| `tests/python/desktop/test_network_library_relative_claim.py` | Reviewed | Covers library-relative fields and unsafe relative rejection. No finding. |
| `tests/python/desktop/test_network_security.py` | Reviewed | Covers foreign worker rejection, but explicitly permits empty-worker completion. See W03-001. |
| `tests/python/desktop/test_network_worker_runtime.py` | Reviewed | Accessible-library claim/heartbeat reporting coverage reviewed by symbol search. No W03 source finding. |

## Findings

| id | severity | file | symbol | summary |
|---|---|---|---|---|
| W03-001 | P1 | `src/mediapipeline/desktop/network/registry.py` | `complete`, `unclaim` | Empty `worker_id` bypasses ownership checks through HTTP done/release paths. |
| W03-002 | P1 | `src/mediapipeline/desktop/network/registry.py` | `_claimed_paths`, `is_in_flight` | In-flight source identity uses raw strings, so Windows/UNC case or slash variants can be claimed as separate files. |
| W03-003 | P2 | `src/mediapipeline/desktop/network/registry.py` | `claim` | Runtime duplicate `job_id` overwrites the existing job and leaves stale claimed-path state. |

## Detailed Findings

### W03-001

- `id`: W03-001
- `severity`: P1
- `file`: `src/mediapipeline/desktop/network/registry.py`; supporting wire path in `src/mediapipeline/desktop/network/coordinator_http_handlers.py`
- `line`: `registry.py:400`, `registry.py:503`, `coordinator_http_handlers.py:270`, `coordinator_http_handlers.py:363`
- `symbol`: `InFlightRegistry.complete`, `InFlightRegistry.unclaim`, `CoordinatorHttpHandlersMixin._http_done`
- `problem`: Registry ownership checks reject mismatched non-empty `worker_id`, but explicitly allow an empty requester. The HTTP `/api/done` handler also allows empty `worker_id` and passes it directly to `complete()`/`unclaim()`. That makes the internal crash-recovery affordance reachable from the authenticated network endpoint.
- `impact`: Any authenticated worker that knows or reuses a `job_id` can submit a done or release report with no `worker_id` and close or release a job owned by another worker. A false success can remove the queue record through done outcome handling; a false release can return active work to the queue while the real worker is still encoding. This is a distributed-work correctness failure with queue corruption risk.
- `evidence`: `complete()` comments allow empty `worker_id` for compatibility and only reject when `requester` is non-empty and mismatched. `_http_done` validates malformed non-empty worker IDs but does not require one. `tests/python/desktop/test_network_security.py:288` currently asserts that empty-worker completion succeeds for internal callers, but there is no separate internal-only entry point.
- `suggested fix direction`: Require a valid non-empty `worker_id` for all HTTP done/release requests. If coordinator-internal or crash-recovery callers still need ownerless completion, move that to a separate private registry method or require an explicit internal sentinel not accepted by protocol dataclasses.
- `suggested validation/tests`: Add HTTP tests that done and release with missing/empty `worker_id` return `400` and leave the job active. Keep a separate unit test for the new internal-only path if still needed.

### W03-002

- `id`: W03-002
- `severity`: P1
- `file`: `src/mediapipeline/desktop/network/registry.py`; related exact comparisons in `src/mediapipeline/desktop/network/coordinator_queue.py` and `src/mediapipeline/desktop/network/failure_policy.py`
- `line`: `registry.py:272`, `registry.py:302`, `registry.py:637`, `coordinator_queue.py:361`, `coordinator_queue.py:438`, `failure_policy.py:11`
- `symbol`: `InFlightRegistry.claim`, `InFlightRegistry.is_in_flight`, `CoordinatorQueueMixin._scan_for_next_record`, `CoordinatorQueueMixin._remove_from_queue`, `source_has_prior_failure`
- `problem`: The in-flight registry keys `_claimed_paths` and `_recent_completions` by raw `source_path` text. Claim scan and queue removal also compare raw strings. In a Windows-first network mode, the same file can reasonably appear as `C:\Media\Movie.mkv`, `c:\media\movie.mkv`, `C:/Media/Movie.mkv`, or a UNC spelling variant.
- `impact`: If queue refresh, overlapping library profiles, or path ingestion produces two textual variants for the same source, worker A can claim one variant and worker B can claim the other because `is_in_flight()` only checks exact text. That can run two encodes for the same source and converge on the same output/publish side effects. The same raw-key issue can also miss prior-failure and same-worker retry suppression.
- `evidence`: `claim()` only checks `if source_path in self._claimed_paths`, then stores `_claimed_paths[source_path] = job_id`. `is_in_flight()` performs the same exact lookup. `_scan_for_next_record()` passes `str(getattr(r, "source_path", ""))` without normalization. `_remove_from_queue()` removes only exact string matches. Existing assigned tests cover same-text duplicate persisted rows and casefold-only prior failures, but not slash/case-equivalent active claims.
- `suggested fix direction`: Introduce one coordinator source identity normalizer for Windows paths and UNC paths, use it for claimed-path keys, recent-completion keys, failure-ledger keys, prior-failure lookup, and queue removal matching, while preserving the original path for display and worker payloads. Reject duplicate normalized source identities in both `claim()` and `load()`.
- `suggested validation/tests`: Add registry and HTTP claim tests proving `C:\Media\Movie.mkv` and `c:/media/movie.mkv` cannot both be claimed. Add load-time duplicate normalized source rejection, failure-ledger suppression across normalized variants, and queue removal across normalized variants.

### W03-003

- `id`: W03-003
- `severity`: P2
- `file`: `src/mediapipeline/desktop/network/registry.py`
- `line`: `registry.py:271`
- `symbol`: `InFlightRegistry.claim`
- `problem`: Runtime `claim()` rejects duplicate source paths but does not reject a duplicate `job_id`. A duplicate `job_id` overwrites the existing `_jobs[job_id]` entry while leaving the old source path in `_claimed_paths`.
- `impact`: A duplicate `job_id` can leave a source path permanently considered in-flight with no matching active job, causing a queue item to be skipped indefinitely and making active-count/state evidence inconsistent. Load-time recovery correctly rejects duplicate job IDs, but runtime mutation does not enforce the same invariant.
- `evidence`: `claim()` checks only `source_path in self._claimed_paths`, then assigns `self._jobs[job_id] = job` and `self._claimed_paths[source_path] = job_id`. `load()` later rejects duplicate `job_id` and duplicate `source_path`, showing the intended invariant exists for persisted state but not for live claims.
- `suggested fix direction`: In `claim()`, validate non-empty `job_id`, `worker_id`, and `source_path`, reject `job_id in self._jobs`, and keep `_jobs`/`_claimed_paths` mutation as an all-or-nothing invariant.
- `suggested validation/tests`: Add a registry unit test that a second claim with an existing `job_id` returns `False` and leaves the original source claim active without adding a stale claimed-path entry.

## Test Coverage Gaps

- Missing adversarial coverage for empty `worker_id` over HTTP done/release. Current coverage only proves foreign non-empty IDs are rejected and intentionally permits empty registry completion.
- Missing normalized source-identity tests for claim, load, recent completion grace, queue removal, prior-failure lookup, and failure-ledger retry suppression.
- Missing runtime duplicate-job-ID claim test, despite load-time duplicate-job-ID rejection tests.
- Missing explicit priority-order test in the network claim layer. The current code appears to trust upstream queue snapshot ordering; a targeted test should pin that contract or prove the coordinator reorders when needed.

## Boundary Risks

- Queue/source movement risk is concentrated in W03-001 and W03-002. Neither directly deletes source media, but both can cause incorrect queue terminal behavior or duplicate processing of the same source, which can cascade into output/publish corruption.
- `CoordinatorAlsoEncodeLocally` is guarded by a strict boolean true check in `pipeline_policy.py`, and normal Launch is blocked for all non-standalone network roles. No finding in that boundary.
- `WorkerConfigOverrides` is ignored by `snapshot_encode_config()`, and coordinator processing policy is snapshotted separately. No per-worker override mutation finding in the assigned snapshot path.
- Registry save uses temp file, flush, fsync, and `os.replace`; claim response is not sent after save failure, and local/HTTP claim rollback removes unsaved claims. No registry-save fail-open finding.

## Files With No Findings

- `src/mediapipeline/desktop/network/encode_config_snapshot.py` - reviewed; no finding.
- `src/mediapipeline/desktop/network/library_roots.py` - reviewed; no finding.
- `src/mediapipeline/desktop/network/dispatcher.py` - reviewed; no finding.
- `src/mediapipeline/desktop/network/standalone.py` - reviewed; no network coordinator finding.
- `src/mediapipeline/core/processes/pipeline_policy.py` - reviewed; no finding.
- `tests/python/desktop/test_network_library_relative_claim.py` - reviewed as evidence; no test defect beyond broader W03 gaps.
- `tests/python/desktop/test_network_worker_runtime.py` accessible-library claim/heartbeat evidence - reviewed by focused search; no W03 finding.

## Incomplete Coverage

- No targeted tests were run; this worker audit is source/test review only.
- I did not run live coordinator/worker processes, real media, publish/drain, queue scans, settings saves, or lifecycle commands.
- Done/release outcome side effects beyond the registry ownership checks overlap W04 and were only inspected enough to support W03-001.
- Full PowerShell queue-plan ordering internals were not reopened; priority ordering was assessed from Python queue preview consumption and existing tests.

## Suggested Follow-Up Prompts

- Patch W03-001: require non-empty `worker_id` for HTTP done/release and split any ownerless internal registry transition into a non-protocol helper.
- Patch W03-002: add a shared Windows/UNC source identity normalizer for registry claim keys, recent-completion keys, failure ledger keys, prior-failure checks, and queue removal.
- Patch W03-003: enforce live duplicate-job-ID rejection in `InFlightRegistry.claim`.
- Add adversarial tests for normalized duplicate source claims, load-time normalized duplicate rejection, empty-worker done/release rejection, and network priority-order preservation.
