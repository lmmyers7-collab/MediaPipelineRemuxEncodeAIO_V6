# Network Coordinator/Worker Mode Fix Batch Plan

Date: 2026-06-15

This plan groups confirmed findings by risk so fixes can be validated at the right rung. It is a planning artifact only; no source fixes are included in this review-only pass.

## Batch 1 - Source, Claim, And State Corruption

Target findings:

- NCW-P1-03, NCW-P1-04, NCW-P1-05, NCW-P1-06, NCW-P1-07, NCW-P1-08, NCW-P1-09, NCW-P1-10, NCW-P1-14
- NCW-P2-02, NCW-P2-03, NCW-P2-04

Fix themes:

- Require non-empty external done/release worker identity.
- Normalize coordinator source identity for claims, recent completions, failure ledger, prior failures, and queue removal.
- Make claim response delivery rollback-safe.
- Make done/release acceptance durable before workers clear pending reports or queue removal occurs.
- Preserve late terminal report and stale reclaim evidence.
- Prevent malformed claims from reaching backend launch.
- Keep workers blocked on unresolved crash state and failed pre-start release reports.
- Add concurrent claim race coverage.

Validation:

- Bundled Python network unit suites for coordinator HTTP, workflow, registry, worker state, crash recovery, done/release, and worker runtime.
- New adversarial tests for race, post-save response failure, save-failure done acceptance, malformed identity, and crash-recovery-post-failure.

## Batch 2 - Auth, Secret, And Journal Safety

Target findings:

- NCW-P1-01, NCW-P1-02, NCW-P1-11
- NCW-P2-01, NCW-P2-05, NCW-P2-17

Fix themes:

- Enforce the same coordinator-token strength rules at startup and live rotation.
- Redact every cluster-log field, not only the message.
- Do not journal validation-failure request bodies for unjournaled or secret-transfer routes.
- Add `join_blob` to sensitive journal keys.
- Tighten `ClaimResponse` booleans/integers.
- Bound join blob decoded size, library rows, and field lengths.

Validation:

- `test_network_security.py`, `test_network_protocol_runtime.py`, `test_network_coordinator_http.py`, `test_network_join.py`, and Local API command contract tests.
- New regression tests that assert no raw token/blob values in command history, route errors, logs, or cluster log lines.

## Batch 3 - Lifecycle And Provider Semantics

Target findings:

- NCW-P1-12, NCW-P1-13
- NCW-P2-06, NCW-P2-07, NCW-P2-18, NCW-P2-19

Fix themes:

- Make Network stop cooperative and keep forced abort separate.
- Report active in-memory work in dry-run preconditions.
- Make worker dispatcher startup two-phase so polling cannot start before runtime attachment.
- Bridge PowerShell `local_worker_result.v1` into Python network done reports.
- Add `QueueTerminal` and `Retryable` to worker-result schema.
- Preserve stale per-slot worker result evidence before slot reuse.

Validation:

- Network lifecycle/provider tests, Tauri route semantics where applicable, PowerShell local-worker slot/claim tests, and new PowerShell-result-to-Python-done fixture tests.
- No real-media validation is required for route semantics alone, but any change that affects actual FFmpeg command generation or worker effective config needs the high-risk media validation rung.

## Batch 4 - Path Map, Library Roots, And Read DTOs

Target findings:

- NCW-P2-09, NCW-P2-10, NCW-P2-13, NCW-P2-14, NCW-P2-15

Fix themes:

- Preserve order-sensitive manual path maps during join import.
- Reject unsafe manual path-map entries and unsafe legacy claim tails.
- Split manual, auto, and effective path-map drift evidence.
- Mark malformed worker-state rows unreadable.
- Surface stale active worker state as warning/blocked when lifecycle memory says stopped.

Validation:

- `test_network_join.py`, `test_network_path_auto_map.py`, `test_network_library_relative_claim.py`, `test_application_facade_network.py`, and new path-map traversal/DTO stale-state tests.
- Live two-machine blank-map validation remains operator-side after code fixes.

## Batch 5 - WebView, Docs, Contracts, And Test Fixtures

Target findings:

- NCW-P2-08, NCW-P2-11, NCW-P2-12, NCW-P2-16
- NCW-P3-01, NCW-P3-02

Fix themes:

- Sync Tauri required routes with Python Network setup routes.
- Correct path-map row Test wording or add a backend-owned no-mutation row validation route.
- Fix browser Network smoke `/api/ui-preferences` allowlist and join confirmation metadata.
- Refresh active docs, route totals, mutation matrix rows, lifecycle field names, `WorkerConfigOverrides` wording, and hardening-plan status.
- Fix the stale `test_network_workflow.py` `_snapshot_encode_config` mock signature.

Validation:

- `test_tauri_shell_scaffold.py`, `test_api_route_inventory.py`, `test_api_contract_payload.py`, `test_api_command_contracts.py`, `test_webview_network_read_only_boundary.py`, `test_webview_browser_network_smoke.py`, and `ops/scripts/smoke/Test-WebViewBrowserNetworkSmoke.ps1`.
- Docs link/file checks if doc links change.
