# Worker 11 Tests and Tooling Completion Review

## Result

The resumed first-pass review is complete for all 481 nonterminal frozen-baseline paths assigned to `worker-11-tests-tooling` outside `tests/webview/**`. The exact current-hash slice contains 183,969 physical lines and 165,646 source lines. All rows were read semantically in full, 441 have no path-local finding, 40 carry exact current finding IDs, and every row retains `second_review_status: pending` for independent review.

This completion publishes ten new findings: three P1, four P2, and three P3. It preserves and reconciles `AUDIT-FIND-W11-001` through `AUDIT-FIND-W11-013`, the W11 HIR/SR records, and current cross-worker findings without duplicating their root causes.

No implementation, test, generated artifact, central ledger, change packet, media, or external state was modified. Publication is limited to this report and the three dedicated `worker-11-tests-tooling-completion-resume-*` JSONL fragments.

## Scope and method

| Slice | Paths |
|---|---:|
| `ops/pipeline/tests/**` | 73 |
| `src/mediapipeline/tools/**` | 60 |
| fixtures plus package/helper files | 23 |
| `tests/python/core/**` | 20 |
| `tests/python/integration/**` | 3 |
| `tests/python/tooling/**` | 42 |
| `tests/python/desktop/**` | 260 |
| **Total** | **481** |

The 74 `tests/webview/**` assignment rows were excluded because they are owned by the separate resumed WebView handoff. Three already-terminal current-review rows were also excluded: `src/mediapipeline/tools/dev/repository_audit_ledger.py`, `tests/python/tooling/test_repository_audit_ledger.py`, and `tests/python/desktop/test_backend_instance_ownership.py`.

Generated summaries were read first where present. Exact source, fixtures, callers, consumers, tests, cleanup, concurrency, subprocess, filesystem, Git, generated-proof, and negative-path behavior were then reviewed at the hashes in the review fragment. High-risk conclusions were confirmed with bounded disposable probes. Representative real-media validation was neither required nor allowed for this review-only tooling/test slice.

## New findings

- `AUDIT-FIND-W11-014` (P3): seven assigned paths have stale `PROJECT_INDEX` source-hash joins.
- `AUDIT-FIND-W11-015` (P1): release finalization overwrites a pre-existing release-history directory, and failure rollback cannot restore it.
- `AUDIT-FIND-W11-016` (P1): risky-file `--changed` mode reports a clean result when its Git discovery command fails.
- `AUDIT-FIND-W11-017` (P2): generated-summary `--changed` mode reports zero sources when its Git discovery command fails.
- `AUDIT-FIND-W11-018` (P1): the Tdarr fixture materializer accepts the shared `TestLibraries` root and can recursively delete unrelated contents after only a sentinel check.
- `AUDIT-FIND-W11-019` (P2): malformed JSON/JSONL Tdarr evidence is silently omitted from containment auditing.
- `AUDIT-FIND-W11-020` (P3): the run-monitor invalid-progress subtest loop validates only its final payload.
- `AUDIT-FIND-W11-021` (P2): unreadable legacy-reference candidates are converted to empty content and can be declared deletion-ready under `--strict`.
- `AUDIT-FIND-W11-022` (P2): two concurrency regression tests use unbounded non-daemon thread joins and can hang on the deadlocks they are meant to detect.
- `AUDIT-FIND-W11-023` (P3): the marketecture test overwrites and unconditionally deletes a fixed shared worktree path instead of using its temporary directory.

Existing findings were extended in row-level reconciliation where applicable. In particular, browser inventory/skip failures remain owned by `AUDIT-FIND-W10-003`, the package-cycle gate failure by `AUDIT-FIND-DEP-001`, generated context drift by `AUDIT-FIND-COV-001`, and the smoke-wrapper-map anchor drift by `AUDIT-FIND-W12-001`. Concurrent W12 evidence `AUDIT-ERR-W12-009` reserves `AUDIT-FIND-W12-004` for the stale generated duplicate-test report; no duplicate W11 finding was created on the correct generator or test sources.

## Validation

| Command or check | Current outcome |
|---|---|
| Bundled `context_slice --task ... --budget 2000` fallback | Passed after the required MCP service was unavailable; the failed attempt is recorded. |
| Focused W11 unittest pack | Passed: 123 tests. |
| Full `pytest tests/python/tooling -q -p no:cacheprovider` | **Nonzero:** 6 failed, 368 passed, 2 skipped, 109 subtests passed in 28.8 seconds. The result is preserved as `AUDIT-ERR-W11-R-048`, not reported as a clean gate. |
| Read-only Python compile | Passed: 388 assigned Python sources. |
| Fixture parse | Passed: 14 JSON fixtures and the comment-bearing JSONL fixture under its exact consumer semantics. |
| PowerShell parser | Passed: 77 executable/module files; the remaining PSD1 produced exactly the intentional duplicate-`routingprofile` negative-fixture error. |
| Destructive/recovery proof probes | Confirmed W11-015, W11-018, W11-021, and W11-023 using disposable roots or mocks; no repository product state was changed. |
| Fail-open Git probes | Confirmed W11-016 and W11-017 with injected Git failures. |
| Tdarr malformed-evidence probe | Confirmed valid escaped JSON yields a containment finding while malformed replacement evidence yields none. |
| Final exact rehash | Passed: 481 rows, zero duplicate paths, zero missing files, zero SHA-256 mismatches. |
| Official ledger functions over the dedicated fragment and a freshly rebuilt in-memory current baseline | Passed: 181 findings loaded; 49 scoped errors; zero finding, error, review-fragment, coverage-row, or current-content issues. |

The six full-tooling failures are current guard evidence:

1. Browser-smoke inventory omits two required direct modules (`AUDIT-FIND-W10-003`).
2. Two workflow tests see zero dynamic inventory commands where one is required (`AUDIT-FIND-W10-003`).
3. Dependency validation finds the unallowlisted `processes -> queue` package-cycle edge (`AUDIT-FIND-DEP-001`).
4. `DUPLICATE_TEST_NAMES.md` records 3,735 definitions while the generator finds 3,806 (concurrent W12 generated-artifact finding).
5. `SMOKE_WRAPPER_MAP.json` retains line 413 where the renderer now produces 415 (`AUDIT-FIND-W12-001`).

The initial full-suite failure detail was truncated by the tool display after 3,139 tokens / 173 lines. Its exit status, aggregate counts, all six named failures, and root-cause reconciliation were still delivered and are recorded before the bounded follow-up checks.

## Baseline and generated-index reconciliation

The parent directed this handoff to publish exact current hashes so the central baseline can be rebuilt after writer freeze. Three assigned sources differ from the immutable audit baseline:

| Path | Frozen baseline SHA-256 | Reviewed current SHA-256 |
|---|---|---|
| `tests/python/desktop/test_application_facade_web_static.py` | `99d2fe4214cce044aa185555619c9f768de665aa50c7d45be4ebc32ba37df6dd` | `413d03f8b07112062ddef431f8098bf6e733755002d5b7b0283b9c8d9aa146d4` |
| `tests/python/desktop/test_application_facade_web_static_cross_page.py` | `af6bf4a9f1e8fa692e18610213d970c8980b5381320fad0b8900e46382fa8c3b` | `0af0549d27853f0faf350c2c5774bd5aeddd01c7ff8ebb6b191cb3cba53fccfc` |
| `tests/python/desktop/test_metrics_feature.py` | `39c8a2b427cc126a3e6c95940ad4fe16f1a735beb08726e06749e45fed9e4623` | `a896f66bbd42c0213d9a673add9e8648f95531ae2939290c08d2cf1fc7568ab8` |

The current `PROJECT_INDEX` joins are 459 hash-matched, seven stale-with-finding, and 15 intentionally unindexed fixture rows. `AUDIT-FIND-W11-014` owns these stale assigned paths:

- `ops/pipeline/tests/Unit/Invoke-PipelineQueueEngineChecks.ps1`
- `tests/python/desktop/test_application_facade_local_api_http.py`
- `tests/python/desktop/test_application_facade_process_launch.py`
- `tests/python/desktop/test_application_facade_web_static.py`
- `tests/python/desktop/test_application_facade_web_static_cross_page.py`
- `tests/python/desktop/test_metrics_feature.py`
- `tests/python/desktop/test_service_run_monitor.py`

The 15 unindexed rows are input fixtures under `tests/fixtures/**`; each review row records `not_indexed_with_rationale` rather than treating absence from generated source navigation as a clean source-hash match.

## Publication boundary and preserved state

The dedicated artifacts are:

- `worker-11-tests-tooling-completion-resume-review.jsonl`: 481 exact current-hash first-pass rows.
- `worker-11-tests-tooling-completion-resume-findings.jsonl`: ten new path-local findings.
- `worker-11-tests-tooling-completion-resume-errors.jsonl`: 49 failed, truncated, negative-path, or recovery command records.
- `worker-11-tests-tooling-completion-resume.md`: this report.

No central merge was run because this handoff explicitly prohibits central-ledger writes. No change packet was created because the authorized scope is the existing audit's worker evidence only. Aggregate error preparation remains externally blocked by noncanonical `source_classification` values in concurrent W12 error records; the dedicated W11 error fragment itself validates cleanly.

Six current desktop test paths were outside the frozen W11 baseline and were not claimed as reviewed rows: `tests/python/desktop/application_facade_network_test_support.py`, `tests/python/desktop/test_application_facade_launch_preflight.py`, `tests/python/desktop/test_application_facade_network_lifecycle.py`, `tests/python/desktop/test_application_facade_network_rerun_launch.py`, `tests/python/desktop/test_priority_queue_export.py`, and `tests/python/desktop/test_rerun_results_network_projection.py`.

Unrelated coordinator, W10, W11 WebView, and W12 audit artifacts in the shared worktree were preserved. The exact review fragment is the authoritative per-path list; no omitted or out-of-baseline path is implied to have first-pass coverage.
