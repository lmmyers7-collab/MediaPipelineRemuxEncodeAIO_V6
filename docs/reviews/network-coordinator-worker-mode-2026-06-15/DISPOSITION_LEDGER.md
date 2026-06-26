# Network Coordinator/Worker Review Disposition Ledger

Generated: 2026-06-19.

This ledger reconciles every finding from `FINDINGS_REGISTER.md` against the
implementation batches recorded in `09-implementation-ledger.md` and the live
source/test suite. It is a disposition record, not a new source of truth for
network architecture. Active Network ownership and route boundaries remain in
`Docs/architecture/NETWORK_LIFECYCLE_COMMAND_CONTRACT.md` and `/api/contract`.

## Summary

| Disposition | Count | Evidence |
| --- | ---: | --- |
| Fixed | 35 | `MP-CHANGE-2026-0615-011`, `MP-CHANGE-2026-0615-012`, `MP-CHANGE-2026-0615-014`, `MP-CHANGE-2026-0615-015`, `MP-CHANGE-2026-0615-016`, `MP-CHANGE-2026-0615-018`, plus live focused network/WebView tests. |
| Open | 0 | No finding remains ready-to-fix after current source/test inspection. |
| Superseded | 0 | No finding was closed by product removal or scope cancellation. |
| Deferred | 0 | No network review finding is intentionally deferred. |

## Batch Mapping

| Batch | Finding IDs | Disposition evidence |
| --- | --- | --- |
| Batch 1 state safety | `NCW-P1-03`, `NCW-P1-04`, `NCW-P1-05`, `NCW-P1-06`, `NCW-P1-07`, `NCW-P1-08`, `NCW-P1-09`, `NCW-P1-10`, `NCW-P1-14`, `NCW-P2-02`, `NCW-P2-03`, `NCW-P2-04` | `MP-CHANGE-2026-0615-011`; current tests under `tests/python/desktop/test_network_done_release.py`, `test_network_workflow.py`, `test_network_inflight_registry.py`, `test_network_worker_state.py`, `test_network_worker_runtime.py`, and `test_network_crash_recovery.py`. |
| Batch 2 auth/secret/journal safety | `NCW-P1-01`, `NCW-P1-02`, `NCW-P1-11`, `NCW-P2-01`, `NCW-P2-05`, `NCW-P2-17` | `MP-CHANGE-2026-0615-012`; current tests under `test_network_security.py`, `test_network_coordinator_http.py`, `test_api_command_contracts.py`, `test_network_join.py`, and `test_network_protocol_runtime.py`. |
| Batch 3 lifecycle/provider semantics | `NCW-P1-12`, `NCW-P1-13`, `NCW-P2-06`, `NCW-P2-07`, `NCW-P2-18`, `NCW-P2-19` | `MP-CHANGE-2026-0615-014`; current tests under `test_network_lifecycle_fixes.py`, `test_network_done_release.py`, and PowerShell local-worker result checks. |
| Batch 4 path-map and read DTO safety | `NCW-P2-09`, `NCW-P2-10`, `NCW-P2-13`, `NCW-P2-14`, `NCW-P2-15` | `MP-CHANGE-2026-0615-015`; current tests under `test_network_join.py`, `test_network_worker_runtime.py`, `test_network_worker_source_policy.py`, and `test_application_facade_network.py`. |
| Batch 5 WebView/docs/contracts/fixtures | `NCW-P2-08`, `NCW-P2-11`, `NCW-P2-12`, `NCW-P2-16`, `NCW-P3-01`, `NCW-P3-02` | `MP-CHANGE-2026-0615-016`; current tests under `test_tauri_shell_scaffold.py`, `test_api_route_inventory.py`, `test_api_contract_payload.py`, `test_webview_network_read_only_boundary.py`, and `test_webview_browser_network_smoke.py`. |
| Remaining remediation | `REM-NCW-01` through `REM-NCW-09` | `MP-CHANGE-2026-0615-018`; recorded 161 focused tests, 405 broader network-adjacent tests, WebView browser Network smoke, PowerShell browser smoke, summary refresh, and strict change-control validation at implementation time. |

## Per-Finding Disposition

| Finding | Severity | Disposition | Fix packet | Current evidence |
| --- | --- | --- | --- | --- |
| `NCW-P1-01` | P1 | Fixed | `MP-CHANGE-2026-0615-012` | Configured and persisted coordinator tokens now use the same strength gate as rotation; `test_network_security.py` covers short rejection, strong acceptance, blank fallback, and no raw-token leak. |
| `NCW-P1-02` | P1 | Fixed | `MP-CHANGE-2026-0615-012` | Cluster-log field rendering redacts token-like content across every worker-supplied field; `test_network_coordinator_http.py` covers formatter and `/api/log` append paths. |
| `NCW-P1-03` | P1 | Fixed | `MP-CHANGE-2026-0615-011` | External done/release paths require valid worker ownership; `test_network_coordinator_http.py`, `test_network_done_release.py`, and registry owner tests cover missing, empty, and foreign worker IDs. |
| `NCW-P1-04` | P1 | Fixed | `MP-CHANGE-2026-0615-011` | Claim response strictness and send/save rollback are covered by coordinator HTTP/workflow tests that leave sources non-in-flight when response delivery cannot be trusted. |
| `NCW-P1-05` | P1 | Fixed | `MP-CHANGE-2026-0615-011` | In-flight registry now normalizes Windows/UNC source identity for claims, load, retry, and removal; `test_network_inflight_registry.py` covers source identity variants. |
| `NCW-P1-06` | P1 | Fixed | `MP-CHANGE-2026-0615-011` | Done/release acceptance is tied to durable registry save before queue removal; `test_network_coordinator_http.py`, `test_network_done_release.py`, and `test_network_workflow.py` cover save-failure behavior. |
| `NCW-P1-07` | P1 | Fixed | `MP-CHANGE-2026-0615-011` | Late terminal reports are durably recorded and workers clear pending reports only after accepted or `late_recorded` responses; `test_network_worker_state.py` and `test_network_inflight_registry.py` cover this path. |
| `NCW-P1-08` | P1 | Fixed | `MP-CHANGE-2026-0615-011` | Watcher startup failure after launch aborts/report-fails instead of clean-releasing active work; `test_network_lifecycle_fixes.py` covers process cleanup and failed done evidence. |
| `NCW-P1-09` | P1 | Fixed | `MP-CHANGE-2026-0615-011` | Malformed `ok` claims with missing job/source identity are rejected before backend launch; `test_network_worker_runtime.py` covers no launch and bounded release/log behavior. |
| `NCW-P1-10` | P1 | Fixed | `MP-CHANGE-2026-0615-011` | Unresolved active-only worker state blocks new claims until recovery/repair; `test_network_worker_state.py`, `test_network_worker_runtime.py`, and `test_network_crash_recovery.py` cover the hold. |
| `NCW-P1-11` | P1 | Fixed | `MP-CHANGE-2026-0615-012` | Secret-transfer validation failures skip request journaling and `join_blob` keys redact recursively; `test_api_command_contracts.py` covers both behaviors. |
| `NCW-P1-12` | P1 | Fixed | `MP-CHANGE-2026-0615-014` | Network stop is cooperative for active work and returns preserved/drain evidence instead of killing active jobs; `test_network_lifecycle_fixes.py` covers worker, coordinator-local, and remote-claim stop paths. |
| `NCW-P1-13` | P1 | Fixed | `MP-CHANGE-2026-0615-014` | Worker-result artifacts bridge route, publish, output, terminal, retry, and identity evidence into Python `DoneRequest`; `test_network_lifecycle_fixes.py` and `test_network_done_release.py` cover propagation. |
| `NCW-P1-14` | P1 | Fixed | `MP-CHANGE-2026-0615-011` | Concurrent claim race coverage exists in `test_network_workflow.py::test_http_claim_allows_only_one_concurrent_worker_for_same_source`. |
| `NCW-P2-01` | P2 | Fixed | `MP-CHANGE-2026-0615-012` | Failure/quarantine cluster events use production-compatible logging signatures; `test_network_workflow.py` covers failed/quarantined done paths. |
| `NCW-P2-02` | P2 | Fixed | `MP-CHANGE-2026-0615-011` | Live duplicate job IDs are rejected without mutating existing state; `test_network_inflight_registry.py` covers the invariant. |
| `NCW-P2-03` | P2 | Fixed | `MP-CHANGE-2026-0615-011` | Stale reclaims persist a bounded ledger independent of cluster-log success; `test_network_inflight_registry.py` and `test_network_workflow.py` cover ledger durability. |
| `NCW-P2-04` | P2 | Fixed | `MP-CHANGE-2026-0615-011` | Malformed/path-map/record-build release POST failures persist pending release reports for retry; `test_network_worker_runtime.py` and `test_network_done_release.py` cover retry preservation. |
| `NCW-P2-05` | P2 | Fixed | `MP-CHANGE-2026-0615-012` | Claim protocol booleans and integers now use strict parsing; `test_network_protocol_runtime.py` covers string/number boolean rejection and integer edge cases. |
| `NCW-P2-06` | P2 | Fixed | `MP-CHANGE-2026-0615-014` | Lifecycle dry-run reports active in-memory worker, coordinator-local, and remote-claim work; `test_network_lifecycle_fixes.py` covers review/blocked evidence. |
| `NCW-P2-07` | P2 | Fixed | `MP-CHANGE-2026-0615-014` | Worker startup is two phase: dispatcher is constructed without polling, runtime is attached, then polling starts; `test_network_lifecycle_fixes.py` covers the startup race. |
| `NCW-P2-08` | P2 | Fixed | `MP-CHANGE-2026-0615-016` | Tauri required-route metadata includes network setup/discovery/join routes; `test_tauri_shell_scaffold.py` covers route parity. |
| `NCW-P2-09` | P2 | Fixed | `MP-CHANGE-2026-0615-015` | Worker join import preserves manual path-map order while sorting derived maps safely; `test_network_join.py` covers overlapping prefixes. |
| `NCW-P2-10` | P2 | Fixed | `MP-CHANGE-2026-0615-015` | Path-map parsing rejects unsafe replacements and traversal; `test_network_worker_runtime.py`, `test_network_worker_source_policy.py`, and `test_network_join.py` cover unsafe mapped claims. |
| `NCW-P2-11` | P2 | Fixed | `MP-CHANGE-2026-0615-016` | WebView row copy distinguishes local rewrite preview from generic backend preflight; `test_webview_network_read_only_boundary.py` guards the wording. |
| `NCW-P2-12` | P2 | Fixed | `MP-CHANGE-2026-0615-016` | Browser Network smoke allows only exact UI-preference sync while preserving no-mutation checks; `test_webview_browser_network_smoke.py` covers the fixture path. |
| `NCW-P2-13` | P2 | Fixed | `MP-CHANGE-2026-0615-015` | Network read DTOs separate manual, auto, and effective path maps; `test_application_facade_network.py` covers saved-vs-runtime drift evidence. |
| `NCW-P2-14` | P2 | Fixed | `MP-CHANGE-2026-0615-015` | Malformed worker state is surfaced as an unreadable state-file row; `test_application_facade_network.py` covers warning and blocked status. |
| `NCW-P2-15` | P2 | Fixed | `MP-CHANGE-2026-0615-015` | Stale active worker state with stopped lifecycle reports warning/blocked stale-claim evidence; `test_application_facade_network.py` covers operator summary text. |
| `NCW-P2-16` | P2 | Fixed | `MP-CHANGE-2026-0615-016`; refreshed by `MP-CHANGE-2026-0619-031` | Active docs, matrices, route inventory, and `/api/contract` distinguish read panels from backend-owned lifecycle/setup commands; route inventory, contract payload, and WebView boundary tests cover drift. |
| `NCW-P2-17` | P2 | Fixed | `MP-CHANGE-2026-0615-012` | Join blobs have encoded/decoded size, row, field, schema, token, and no-partial-save guards; `test_network_join.py` and command contract tests cover hostile blobs and leak prevention. |
| `NCW-P2-18` | P2 | Fixed | `MP-CHANGE-2026-0615-014` | `QueueTerminal` and `Retryable` are backward-compatible worker-result fields mapped into `DoneRequest`; `test_network_done_release.py` covers round-trip preservation. |
| `NCW-P2-19` | P2 | Fixed | `MP-CHANGE-2026-0615-014` | Stale local-worker result evidence is preserved before slot reuse; PowerShell local-worker claim/result checks are recorded in the Batch 3 packet. |
| `NCW-P3-01` | P3 | Fixed | `MP-CHANGE-2026-0615-016` | Network workflow fixture signature was repaired and accessible-library skip assertions execute in `test_network_workflow.py`. |
| `NCW-P3-02` | P3 | Fixed | `MP-CHANGE-2026-0615-016` | Browser fixture join routes match confirmation-required contract metadata; `test_webview_browser_network_smoke.py` and `test_webview_network_read_only_boundary.py` cover confirmation cues. |

## Current Validation Targets

Use these focused checks when this disposition is touched again:

```powershell
.\apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_network_security tests.python.desktop.test_network_coordinator_http tests.python.desktop.test_network_workflow tests.python.desktop.test_network_lifecycle_fixes tests.python.desktop.test_network_protocol_runtime tests.python.desktop.test_network_join tests.python.desktop.test_network_worker_runtime tests.python.desktop.test_network_done_release tests.python.desktop.test_network_worker_state tests.python.desktop.test_network_crash_recovery tests.python.desktop.test_network_inflight_registry tests.python.desktop.test_application_facade_network tests.python.desktop.test_api_command_contracts tests.webview.test_webview_network_read_only_boundary -q
```
