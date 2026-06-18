# Network Coordinator Worker Mode Review Prompt Pack - 2026-06-15

Use this pack to run a review-only multi-worker audit of the network coordinator/worker mode. Each worker prompt below is intended to stand alone: copy one complete prompt into a fresh worker session. Workers write only their assigned Markdown file under `docs/reviews/network-coordinator-worker-mode-2026-06-15/workers/`. The master coordinator prompt runs after all worker files are present.

Important current-state note: some older active docs may still describe network lifecycle controls as absent or design-only, while newer inventories and the hardening plan describe backend-owned start/stop, setup, discovery, join, and test-connection routes. Every worker must verify current behavior from code, contracts, tests, and dated docs instead of assuming either description is authoritative.

## Shared Review Output Contract

Each worker Markdown file must contain these sections:

- `# Worker Review: Wxx - <scope>`
- `## Scope`
- `## Required Reads Completed`
- `## Coverage Ledger`
- `## Findings`
- `## Detailed Findings`
- `## Test Coverage Gaps`
- `## Boundary Risks`
- `## Files With No Findings`
- `## Incomplete Coverage`
- `## Suggested Follow-Up Prompts`

Finding fields:

- `id`: `Wxx-001`, `Wxx-002`, etc.
- `severity`: `P0`, `P1`, `P2`, or `P3`
- `file`
- `line` or narrow symbol reference
- `symbol`
- `problem`
- `impact`
- `evidence`
- `suggested fix direction`
- `suggested validation/tests`

Severity guide:

- `P0`: likely source mutation, data loss, unsafe publish/drain, cross-worker claim corruption, or lifecycle behavior that can corrupt active work.
- `P1`: high-risk boundary violation, auth/secret exposure, unsafe start/stop/claim/done handling, or realistic distributed-work correctness failure.
- `P2`: bounded correctness, stale-contract, Windows/UNC path, error-handling, diagnostics, or misleading-test issue.
- `P3`: maintainability or coverage issue that creates real future risk.

## W01 Prompt - Coordinator Lifecycle, Auth, And HTTP Server

You are W01 in a review-only audit of MediaPipelineRemuxEncodeAIO network coordinator/worker mode. Your output file is `docs/reviews/network-coordinator-worker-mode-2026-06-15/workers/W01-coordinator-lifecycle-auth-server.md`.

Read first, in order: `AGENTS.md`, `docs/CURRENT_PROJECT_STATE.md`, `docs/OPEN_WORK_CHECKLIST.md`, `docs/generated/PROJECT_INDEX.md`, `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`, `docs/architecture/NETWORK_LIFECYCLE_COMMAND_CONTRACT.md`, `docs/architecture/NETWORK_WORKER_HARDENING_PLAN.md`, `docs/inventories/API_ROUTE_INVENTORY.md`, and the generated summaries for every assigned source/test file before opening full source.

Rules: review only. Do not edit source, generated summaries, runtime state, LocalBase, media files, queue state, settings, manifests, or aggregate review files. If you write your worker MD, use the change packet provided by the coordinator; if none is provided, create a unique docs-only packet before writing and record your touched worker MD. Do not run real media, launch normal processing, publish, drain, rename, or save settings. Targeted unit/static tests are allowed only as evidence.

Assigned source scope: `src/mediapipeline/desktop/network/coordinator.py`, `coordinator_lifecycle.py`, `coordinator_auth.py`, `coordinator_policy.py`, `coordinator_http.py`, `coordinator_parts/http_server.py`, `auth.py`, `identity.py`, and `cluster_log.py`. Review these functions/classes especially: `CoordinatorDispatcher.__init__`, `_start_http_server`, `_start_reaper`, `_start_mdns`, `_reaper_loop`, `shutdown`, `workers_snapshot`, `idle_workers_snapshot`, `coordinator_stats`, `_load_or_generate_token`, `_validate_request_auth`, `_request_auth_result`, `get_auth_token`, `update_auth_token`, `parse_query_params`, `validate_content_length`, `coordinator_port`, `coordinator_bind_address`, `heartbeat_timeout_mins`, `compute_retry_after_seconds`, and `format_cluster_log_line`.

Assigned tests/evidence: `tests/python/desktop/test_network_coordinator_startup.py`, `test_network_coordinator_helpers.py`, `test_network_coordinator_http.py`, `test_network_security.py`, `test_network_workflow.py`, and any focused summaries those tests reference.

Review questions: Can coordinator construction fail closed on HTTP bind/thread/reaper restore errors? Are request-handler threads intentionally non-daemon where required? Does shutdown preserve `coordinator_inflight.json`, worker state, and cluster logs without silently releasing claims? Are auth tokens generated, stored, rotated, and compared without leaking secrets? Are bind address, port, heartbeat timeout, retry hints, and mDNS fallback validated defensively? Are cluster-log paths, rotation, control characters, URL/token redaction, timestamp skew, and write failures safe and operator-visible? Are all startup and teardown exceptions either fail-closed or logged without pretending the coordinator is healthy?

Write the required sections from the shared output contract. Include `Reviewed: no findings` rows for files or symbols with no issue. If coverage is partial, list exact files and symbols not reviewed.

## W02 Prompt - Coordinator HTTP Endpoint Handlers

You are W02 in a review-only audit of MediaPipelineRemuxEncodeAIO network coordinator/worker mode. Your output file is `docs/reviews/network-coordinator-worker-mode-2026-06-15/workers/W02-coordinator-http-handlers.md`.

Read first, in order: `AGENTS.md`, `docs/CURRENT_PROJECT_STATE.md`, `docs/OPEN_WORK_CHECKLIST.md`, `docs/generated/PROJECT_INDEX.md`, `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`, `docs/architecture/NETWORK_LIFECYCLE_COMMAND_CONTRACT.md`, `docs/architecture/NETWORK_WORKER_HARDENING_PLAN.md`, `docs/inventories/API_ROUTE_INVENTORY.md`, and generated summaries for all assigned files before opening source.

Rules: review only. Do not edit source, generated summaries, runtime state, LocalBase, media files, queue state, settings, manifests, or aggregate review files. If writing your worker MD, use or create a docs-only change packet and record the touched worker file. Do not run real media or any route that claims work against a live operator queue.

Assigned source scope: `src/mediapipeline/desktop/network/coordinator_http_handlers.py`, `coordinator_http.py`, `protocol.py`, `json_policy.py`, `http_json.py`, `library_roots.py`, `auth.py`, and `identity.py`. Review endpoint handlers for `/api/ping`, `/api/libraries`, `/api/claim`, `/api/done`, `/api/heartbeat`, `/api/workers`, and `/api/log`.

Assigned tests/evidence: `tests/python/desktop/test_network_coordinator_http.py`, `test_network_workflow.py`, `test_network_security.py`, `test_network_library_relative_claim.py`, `test_network_protocol_runtime.py`, and `test_network_coordinator_source_policy.py`.

Review questions: Are all endpoints auth-gated as intended, including read endpoints that reveal coordinator state? Are query params, JSON bodies, content length, non-finite numbers, missing identifiers, malformed claim/done/heartbeat/log payloads, and oversized responses handled without corrupting state? Does `/api/claim` release or roll back any partially claimed job if response construction, registry save, retry policy, or logging fails? Does `/api/done` distinguish success, failure, release, unknown job, and reclaimed job without removing the wrong queue row? Does `/api/heartbeat` update progress safely and return reclaim signals correctly? Does `/api/log` sanitize all worker-controlled strings into one physical log entry and avoid secret leakage?

Write the required sections from the shared output contract. Include path:line evidence for every finding.

## W03 Prompt - Coordinator Claim Selection, Registry, And Retry Policy

You are W03 in a review-only audit of MediaPipelineRemuxEncodeAIO network coordinator/worker mode. Your output file is `docs/reviews/network-coordinator-worker-mode-2026-06-15/workers/W03-coordinator-claim-registry-retry.md`.

Read first: `AGENTS.md`, `docs/CURRENT_PROJECT_STATE.md`, `docs/OPEN_WORK_CHECKLIST.md`, `docs/generated/PROJECT_INDEX.md`, `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`, `docs/architecture/NETWORK_WORKER_HARDENING_PLAN.md`, `docs/architecture/NETWORK_LIFECYCLE_COMMAND_CONTRACT.md`, `docs/inventories/COMMAND_OWNERSHIP_MATRIX.md`, and generated summaries for all assigned files.

Rules: review only. Do not alter source, queue files, state files, settings, media, generated summaries, or aggregate review files. If writing your worker MD, use or create a docs-only change packet and record it.

Assigned source scope: `src/mediapipeline/desktop/network/coordinator_queue.py`, `registry.py`, `failure_policy.py`, `encode_config_snapshot.py`, `library_roots.py`, `dispatcher.py`, `standalone.py`, and `src/mediapipeline/core/processes/pipeline_policy.py` network-role helpers. Focus on `CoordinatorQueueMixin.claim_next`, `_scan_for_next_record`, `_scan_for_next_record_for_claim`, `_source_has_prior_failure`, `_snapshot_encode_config`, `_remove_from_queue`, `_coordinator_max_job_retries`, `InFlightRegistry.claim`, `note_worker_seen`, `heartbeat`, `complete`, `unclaim`, `rollback_claim`, `claim_blocked_by_failure`, `mark_failure_quarantine_alerted`, `reclaim_stale`, `is_active`, `is_in_flight`, `save`, and `load`.

Assigned tests/evidence: `tests/python/desktop/test_network_inflight_registry.py`, `test_network_workflow.py`, `test_network_coordinator_helpers.py`, `test_network_library_relative_claim.py`, `test_network_security.py`, and `test_network_worker_runtime.py` accessible-library tests.

Review questions: Can two workers claim the same source under concurrent request paths or registry save failure? Are duplicate job IDs, duplicate source paths, malformed persisted rows, stale completion grace, and active-count failures handled safely? Does claim selection respect priority, library accessibility, current in-flight state, prior failures, same-worker retry suppression, and `CoordinatorAlsoEncodeLocally` boundaries? Does registry save/load use atomic writes and fail closed when persistence fails? Are failure-ledger entries keyed and reset correctly? Does encode config snapshot avoid allowing per-worker overrides to mutate backend media policy unexpectedly?

Write the required sections from the shared output contract. Treat queue/source movement risks as P0/P1 when realistic.

## W04 Prompt - Done, Release, Reaper, And Outcome Handling

You are W04 in a review-only audit of MediaPipelineRemuxEncodeAIO network coordinator/worker mode. Your output file is `docs/reviews/network-coordinator-worker-mode-2026-06-15/workers/W04-done-release-reaper-outcomes.md`.

Read first: `AGENTS.md`, `docs/CURRENT_PROJECT_STATE.md`, `docs/OPEN_WORK_CHECKLIST.md`, `docs/generated/PROJECT_INDEX.md`, `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`, `docs/architecture/FILE_LIFECYCLE_MAP.md`, `docs/architecture/NETWORK_WORKER_HARDENING_PLAN.md`, and generated summaries for all assigned files.

Rules: review only. Do not change source, queue, manifests, pending publish, completed output, runtime state, generated summaries, or aggregate review files. If writing your worker MD, use or create a docs-only change packet and record it.

Assigned source scope: `src/mediapipeline/desktop/network/use_cases/done_outcome.py`, `coordinator_queue.py` done/release helpers, `coordinator_lifecycle.py` reaper helpers, `coordinator_state.py`, `registry.py` completion/reclaim/unclaim paths, `worker_done.py`, `worker_parts/results.py`, and `cluster_log.py`.

Assigned tests/evidence: `tests/python/desktop/test_network_done_release.py`, `test_network_crash_recovery.py`, `test_network_workflow.py`, `test_network_coordinator_http.py`, `test_network_coordinator_source_policy.py`, and `test_network_worker_state.py`.

Review questions: Does a terminal success remove exactly the intended queue item and only after registry/state transitions are safe? Do failures preserve source safety and enough evidence for rerun/review? Are unknown-job done/release reports logged but prevented from corrupting active work? Does reaper reclaim stale jobs without skipping saves or losing failure evidence when logging fails? Are pending done reports retained when coordinator reporting fails and cleared only after accepted reports? Do done payload fields preserve publish/queue terminal evidence without letting a worker claim final publish success that backend should own?

Write the required sections from the shared output contract. Highlight any mismatch with source mutation, pending-publish, queue, or publish/drain boundaries.

## W05 Prompt - Worker Runtime Loop, HTTP Calls, Heartbeats, And Shutdown

You are W05 in a review-only audit of MediaPipelineRemuxEncodeAIO network coordinator/worker mode. Your output file is `docs/reviews/network-coordinator-worker-mode-2026-06-15/workers/W05-worker-runtime-loop-http-shutdown.md`.

Read first: `AGENTS.md`, `docs/CURRENT_PROJECT_STATE.md`, `docs/OPEN_WORK_CHECKLIST.md`, `docs/generated/PROJECT_INDEX.md`, `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`, `docs/architecture/NETWORK_LIFECYCLE_COMMAND_CONTRACT.md`, `docs/architecture/NETWORK_WORKER_HARDENING_PLAN.md`, and generated summaries for all assigned files.

Rules: review only. Do not edit source, generated summaries, runtime state, settings, queue state, or media. If writing your worker MD, use or create a docs-only change packet and record it. Do not point worker code at a live coordinator unless explicitly instructed by the operator.

Assigned source scope: `src/mediapipeline/desktop/network/worker.py`, `worker_loops.py`, `worker_http.py`, `poll_policy.py`, `threading_helpers.py`, `worker_parts/reporting.py`, and `src/mediapipeline/desktop/application/network_lifecycle_provider.py` worker start/stop/hot-apply paths. Focus on `_poll_loop`, `_heartbeat_loop`, `_stop_heartbeat`, `shutdown`, `_resolve_wait_seconds`, `_wait_interruptible`, `_headers`, `_runtime_http_context`, `_sign_request`, `_http_get`, `_http_post`, `update_auth_token`, `update_coordinator_url`, `update_source_path_map`, `runtime_descriptor`, `_hot_apply_running_worker_settings`, `start_network_worker`, and `stop_network_worker`.

Assigned tests/evidence: `tests/python/desktop/test_network_worker_runtime.py`, `test_network_worker_source_policy.py`, `test_network_drift_descriptor.py`, `test_network_lifecycle_fixes.py`, `test_network_security.py`, and `test_application_facade_network.py`.

Review questions: Does the worker only claim coordinator-assigned single-file work and never scan the local queue as normal Launch? Are poll-loop failures, auth failures, malformed claims, path-map failures, heartbeat failures, repeated warnings, thread start failures, and shutdown joins handled without orphaning active claims? Does hot-apply of URL/token/path-map wake the poll loop and avoid token disclosure? Are heartbeats bounded, signed, token-safe, and reclaim-aware? Does shutdown preserve pending done reports unless explicitly released and accepted?

Write the required sections from the shared output contract.

## W06 Prompt - Worker Claim Handoff, State, Pending Done, And Crash Recovery

You are W06 in a review-only audit of MediaPipelineRemuxEncodeAIO network coordinator/worker mode. Your output file is `docs/reviews/network-coordinator-worker-mode-2026-06-15/workers/W06-worker-claims-state-crash-recovery.md`.

Read first: `AGENTS.md`, `docs/CURRENT_PROJECT_STATE.md`, `docs/OPEN_WORK_CHECKLIST.md`, `docs/generated/PROJECT_INDEX.md`, `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`, `docs/architecture/FILE_LIFECYCLE_MAP.md`, `docs/architecture/NETWORK_WORKER_HARDENING_PLAN.md`, and generated summaries for all assigned files.

Rules: review only. Do not edit source, state, settings, queue, media, generated summaries, or aggregate review files. If writing your worker MD, use or create a docs-only change packet and record it.

Assigned source scope: `src/mediapipeline/desktop/network/worker_claims.py`, `worker_state.py`, `worker_done.py`, `worker_record.py`, `worker_parts/tasks.py`, `worker_parts/state_reports.py`, `worker_parts/results.py`, and `_NetworkRuntimeApp` plus `_start_network_claimed_job` in `src/mediapipeline/desktop/application/network_lifecycle_provider.py`.

Assigned tests/evidence: `tests/python/desktop/test_network_worker_state.py`, `test_network_crash_recovery.py`, `test_network_done_release.py`, `test_network_worker_runtime.py`, `test_network_worker_source_policy.py`, and `test_network_library_relative_claim.py`.

Review questions: Are active worker state and pending done reports written atomically and rejected when malformed or non-finite? Does crash recovery first flush pending reports, then avoid claiming while state is corrupt or unresolved? Does the worker release unstartable or malformed claims promptly, with bounded diagnostics and no stale timeout reliance? Are active jobs cleared only after accepted report/cleanup gates? Does claim handoff to encode preserve source path safety, selected queue record identity, library-relative path resolution, and failure reporting when schedule/start fails?

Write the required sections from the shared output contract.

## W07 Prompt - Network Protocol, JSON, Auth, Identity, And Secret Safety

You are W07 in a review-only audit of MediaPipelineRemuxEncodeAIO network coordinator/worker mode. Your output file is `docs/reviews/network-coordinator-worker-mode-2026-06-15/workers/W07-protocol-json-auth-secret-safety.md`.

Read first: `AGENTS.md`, `docs/CURRENT_PROJECT_STATE.md`, `docs/OPEN_WORK_CHECKLIST.md`, `docs/generated/PROJECT_INDEX.md`, `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`, `docs/architecture/NETWORK_LIFECYCLE_COMMAND_CONTRACT.md`, `docs/inventories/API_ROUTE_INVENTORY.md`, `docs/inventories/COMMAND_OWNERSHIP_MATRIX.md`, and generated summaries for all assigned files.

Rules: review only. Do not edit source, generated summaries, runtime state, config, media, or aggregate review files. If writing your worker MD, use or create a docs-only change packet and record it.

Assigned source scope: `src/mediapipeline/desktop/network/protocol.py`, `auth.py`, `identity.py`, `json_policy.py`, `http_json.py`, `coordinator_http.py`, `src/mediapipeline/core/network/url_policy.py`, `src/mediapipeline/core/network/join.py`, and `src/mediapipeline/core/api/commands_network.py`.

Assigned tests/evidence: `tests/python/desktop/test_network_protocol_runtime.py`, `test_network_security.py`, `test_network_coordinator_http.py`, `test_network_join.py`, `test_api_command_contracts.py`, `test_api_contract_payload.py`, and `test_application_facade_network.py`.

Review questions: Do all protocol dataclasses reject malformed, non-finite, oversized, or type-confused values before state mutation? Are worker IDs, worker names, reason codes, progress percent, library IDs, paths, URLs, and timestamps normalized without losing diagnostic value? Are request signatures, auth comparisons, bearer/header handling, and JSON body signing consistent between worker and coordinator? Are secrets redacted from command payloads, route responses, logs, diagnostics, worker board rows, join results, and WebView data? Are unjournaled secret-transfer routes truly excluded from command journal capture?

Write the required sections from the shared output contract.

## W08 Prompt - Local API Lifecycle Facade, Provider, Routes, And Command Journal

You are W08 in a review-only audit of MediaPipelineRemuxEncodeAIO network coordinator/worker mode. Your output file is `docs/reviews/network-coordinator-worker-mode-2026-06-15/workers/W08-local-api-lifecycle-provider-routes.md`.

Read first: `AGENTS.md`, `docs/CURRENT_PROJECT_STATE.md`, `docs/OPEN_WORK_CHECKLIST.md`, `docs/generated/PROJECT_INDEX.md`, `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`, `docs/architecture/NETWORK_LIFECYCLE_COMMAND_CONTRACT.md`, `docs/inventories/API_ROUTE_INVENTORY.md`, `docs/inventories/COMMAND_OWNERSHIP_MATRIX.md`, `docs/inventories/LOCAL_API_ROUTE_OWNERSHIP_MAP.md`, and generated summaries for all assigned files.

Rules: review only. Do not edit source, generated summaries, state, config, media, or aggregate review files. If writing your worker MD, use or create a docs-only change packet and record it. Do not start/stop real network providers except with explicit operator approval; dry-run route tests are acceptable.

Assigned source scope: `src/mediapipeline/core/network/lifecycle_facade.py`, `src/mediapipeline/desktop/application/network_lifecycle_provider.py`, `src/mediapipeline/core/api/commands_network.py`, Local API route/contract files that register network commands, and any direct network lifecycle entries in Tauri backend contract route metadata.

Assigned tests/evidence: `tests/python/desktop/test_api_command_contracts.py`, `test_api_contract_payload.py`, `test_application_facade_network.py`, `test_application_facade_process_launch.py`, `test_network_lifecycle_fixes.py`, `test_local_api_lifecycle_contract_smoke.py`, and `test_tauri_shell_scaffold.py` route metadata coverage.

Review questions: Do dry-run routes have effect `none`, report preconditions, and avoid lifecycle/state mutation? Do confirmed start/stop routes require explicit confirmation fields, fail closed when the real provider is unavailable, and journal command results except secret-transfer exceptions? Does lifecycle state commit avoid stale running/stopping state on provider failure? Does provider startup avoid normal Launch, full queue scan, media policy changes, source/scratch/output mutation, or fake local runs? Does worker stop preserve pending done reports and avoid aborting active work unless explicitly designed? Does coordinator stop preserve inflight/worker/cluster state and reject unsafe assumptions?

Write the required sections from the shared output contract.

## W09 Prompt - Join, Discovery, Test Connection, Path Mapping, And Library Roots

You are W09 in a review-only audit of MediaPipelineRemuxEncodeAIO network coordinator/worker mode. Your output file is `docs/reviews/network-coordinator-worker-mode-2026-06-15/workers/W09-join-discovery-test-connection-paths.md`.

Read first: `AGENTS.md`, `docs/CURRENT_PROJECT_STATE.md`, `docs/OPEN_WORK_CHECKLIST.md`, `docs/generated/PROJECT_INDEX.md`, `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`, `docs/architecture/CONFIG_KEY_GLOSSARY.md`, `docs/architecture/NETWORK_WORKER_HARDENING_PLAN.md`, `docs/inventories/API_ROUTE_INVENTORY.md`, and generated summaries for all assigned files.

Rules: review only. Do not edit source, config, state, media, generated summaries, or aggregate review files. If writing your worker MD, use or create a docs-only change packet and record it. Do not probe a live LAN unless explicitly authorized; use tests/mocks as evidence.

Assigned source scope: `src/mediapipeline/core/network/join.py`, network facade methods for join blob, join cluster, test connection, and coordinator discovery in `src/mediapipeline/core/network/facade.py`, plus `src/mediapipeline/desktop/network/mdns.py`, `probe.py`, `local_ip.py`, `share_block.py`, `path_map.py`, `library_roots.py`, `coordinator_url.py`, and worker path-map/library-resolution methods in `worker.py`.

Assigned tests/evidence: `tests/python/desktop/test_network_join.py`, `test_network_mdns.py`, `test_network_test_connection.py`, `test_network_path_auto_map.py`, `test_network_library_relative_claim.py`, `test_network_local_ip.py`, `test_network_drift_descriptor.py`, and `test_webview_network_read_only_boundary.py`.

Review questions: Are join blobs versioned, bounded, base64/json safe, token-safe in logs/journals, and confirmation-gated? Does worker join import write only intended Settings keys through backend settings save and then perform read-only test connection? Does discovery normalize/dedupe coordinator URLs without trusting malformed mDNS data? Do L1 TCP, L2 auth ping, and L3 path-access probes distinguish failure layers without touching media or claiming work? Does manual `WorkerSourcePathMap` override auto maps safely, preserve order, prevent parent/absolute relative escapes, and handle UNC/Windows case behavior? Are library IDs and relative paths generated and resolved without cross-library source confusion?

Write the required sections from the shared output contract.

## W10 Prompt - WebView Network Page, Worker Settings, And UI Mutation Boundary

You are W10 in a review-only audit of MediaPipelineRemuxEncodeAIO network coordinator/worker mode. Your output file is `docs/reviews/network-coordinator-worker-mode-2026-06-15/workers/W10-webview-network-settings-boundary.md`.

Read first: `AGENTS.md`, `docs/CURRENT_PROJECT_STATE.md`, `docs/OPEN_WORK_CHECKLIST.md`, `docs/generated/PROJECT_INDEX.md`, `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`, `docs/architecture/NETWORK_LIFECYCLE_COMMAND_CONTRACT.md`, `docs/architecture/NETWORK_WORKER_HARDENING_PLAN.md`, `docs/inventories/API_ROUTE_INVENTORY.md`, `docs/inventories/COMMAND_OWNERSHIP_MATRIX.md`, and generated summaries for all assigned files.

Rules: review only. Do not edit source, generated summaries, state, config, media, or aggregate review files. If writing your worker MD, use or create a docs-only change packet and record it. Do not click controls against a live operator backend unless explicitly approved; mocked browser/static tests are acceptable.

Assigned source scope: `apps/desktop/webview/static/assets/networkView.js`, `apps/desktop/webview/static/assets/settingsView.builders.network.js`, `apps/desktop/webview/static/partials/page-network.html`, related API-client usage, and CSS only where layout can hide safety warnings or confirmation text.

Assigned tests/evidence: `tests/webview/test_webview_network_read_only_boundary.py`, `tests/webview/test_webview_browser_network_smoke.py`, `tests/python/desktop/test_application_facade_network.py`, `tests/python/desktop/test_api_command_contracts.py`, and `ops/scripts/smoke/Test-WebViewBrowserNetworkSmoke.ps1`.

Review questions: Does WebView delegate settings preview/save to backend Settings routes without direct config persistence? Are auth-token fields hidden and never rendered in clear text? Do lifecycle buttons call only backend-owned dry-run/confirmed routes with required confirmations and never synthesize queue/media policy locally? Are future retry/reclaim/release/abort/quarantine controls disabled unless backend routes exist? Do join/discovery/test-connection dialogs avoid logging/copying secrets except in the intended join-blob flow? Are filter warnings, worker board rows, drift banners, accessible-library evidence, and path-map editors clear enough that operators do not mistake local UI filters for backend processing scope?

Write the required sections from the shared output contract.

## W11 Prompt - Read DTOs, Worker Board, Diagnostics, Drift, And Operator Evidence

You are W11 in a review-only audit of MediaPipelineRemuxEncodeAIO network coordinator/worker mode. Your output file is `docs/reviews/network-coordinator-worker-mode-2026-06-15/workers/W11-network-read-dtos-diagnostics-drift.md`.

Read first: `AGENTS.md`, `docs/CURRENT_PROJECT_STATE.md`, `docs/OPEN_WORK_CHECKLIST.md`, `docs/generated/PROJECT_INDEX.md`, `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`, `docs/architecture/NETWORK_WORKER_HARDENING_PLAN.md`, `docs/inventories/LOCAL_API_ROUTE_OWNERSHIP_MAP.md`, and generated summaries for all assigned files.

Rules: review only. Do not edit source, generated summaries, state, config, media, or aggregate review files. If writing your worker MD, use or create a docs-only change packet and record it.

Assigned source scope: `src/mediapipeline/core/network/facade.py`, `src/mediapipeline/desktop/network/diagnostics.py`, `src/mediapipeline/desktop/network/failure_reasons.py`, `src/mediapipeline/desktop/network/failure_policy.py`, `src/mediapipeline/desktop/network/worker.py` runtime descriptor methods, and any DTO/read payload code that exposes `/api/network/workers`.

Assigned tests/evidence: `tests/python/desktop/test_application_facade_network.py`, `test_network_drift_descriptor.py`, `test_network_test_connection.py`, `test_network_worker_runtime.py`, `test_network_workflow.py`, `tests/webview/test_webview_browser_network_smoke.py`, and `tests/webview/test_webview_network_read_only_boundary.py`.

Review questions: Does `GET /api/network/workers` expose enough evidence without pretending to control lifecycle directly? Are progress bars, worker rows, state file rows, lifecycle state, token posture, path-map fingerprints, running-vs-saved drift, diagnostic layers, last claim result, accessible libraries, and operator summary lines accurate and redacted? Are warnings bounded and actionable when state files are missing, corrupt, stale, or contradictory? Are stale docs or DTO schema names misleading operators about whether network lifecycle controls are absent, design-only, dry-run-only, or implemented?

Write the required sections from the shared output contract.

## W12 Prompt - Network Test Suite And Adversarial Coverage Review

You are W12 in a review-only audit of MediaPipelineRemuxEncodeAIO network coordinator/worker mode. Your output file is `docs/reviews/network-coordinator-worker-mode-2026-06-15/workers/W12-network-test-suite-coverage.md`.

Read first: `AGENTS.md`, `docs/CURRENT_PROJECT_STATE.md`, `docs/OPEN_WORK_CHECKLIST.md`, `docs/generated/PROJECT_INDEX.md`, `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`, `docs/testing/VALIDATION_LADDER_RUNBOOK.md`, `docs/testing/TEST_COVERAGE_MATRIX.md`, `docs/testing/BROWSER_SMOKE_TEST_RUNBOOK.md`, `docs/architecture/NETWORK_WORKER_HARDENING_PLAN.md`, and generated summaries for all assigned tests before opening full test source.

Rules: review only. Do not edit tests, source, generated summaries, state, config, media, or aggregate review files. If writing your worker MD, use or create a docs-only change packet and record it. You may run targeted tests only if they do not mutate live operator state or media.

Assigned scope: every `tests/python/desktop/test_network*.py`, `tests/webview/test_webview_*network*.py`, network-related `tests/python/desktop/test_api_command_contracts.py`, `test_api_contract_payload.py`, `test_application_facade_network.py`, `test_local_api_lifecycle_contract_smoke.py`, `test_tauri_shell_scaffold.py`, `ops/scripts/smoke/Test-WebViewBrowserNetworkSmoke.ps1`, and `ops/pipeline/tests/Unit/Invoke-LocalWorker*.ps1`.

Review questions: Do tests cover the realistic unsafe cases: duplicate claims, registry save failure, worker crash between completion and report, pending done retry, auth/token leak, malformed JSON/non-finite values, stale heartbeat reclaim, thread startup failure, stop while active, hot-apply drift, path-map UNC/case/relative traversal, inaccessible library filtering, failure retry quarantine, join blob secret handling, and WebView no-mutation boundaries? Are any tests asserting stale behavior from older docs? Are fixtures too fake to catch source/queue/state corruption? Do broad discovery test commands exist and are they appropriate for this risk class?

Write the required sections from the shared output contract. Findings here should usually be coverage gaps, misleading tests, brittle tests, or missing adversarial cases, not duplicate source-code findings from other workers unless the tests actively mask the bug.

## W13 Prompt - PowerShell Local Worker And Pipeline Compatibility

You are W13 in a review-only audit of MediaPipelineRemuxEncodeAIO network coordinator/worker mode. Your output file is `docs/reviews/network-coordinator-worker-mode-2026-06-15/workers/W13-powershell-local-worker-compatibility.md`.

Read first: `AGENTS.md`, `docs/CURRENT_PROJECT_STATE.md`, `docs/OPEN_WORK_CHECKLIST.md`, `docs/generated/PROJECT_INDEX.md`, `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`, `docs/architecture/FILE_LIFECYCLE_MAP.md`, `docs/testing/VALIDATION_LADDER_RUNBOOK.md`, and generated summaries for all assigned files.

Rules: review only. Do not edit PowerShell, source, generated summaries, runtime state, config, media, queue, or aggregate review files. If writing your worker MD, use or create a docs-only change packet and record it. Do not run a real pipeline process or media encode.

Assigned source scope: `ops/pipeline/engine/queue/local_worker_slots.ps1`, `worker_claim_store.ps1`, `worker_mutex.ps1`, `worker_process.ps1`, `worker_progress.ps1`, `ops/pipeline/engine/process/worker_result.ps1`, and any Python network code that claims compatibility with these local-worker artifacts.

Assigned tests/evidence: `ops/pipeline/tests/Unit/Invoke-LocalWorkerSlotChecks.ps1`, `Invoke-LocalWorkerClaimLifecycleChecks.ps1`, Python network tests that reference local worker semantics, and release/test inventory docs that describe worker behavior.

Review questions: Do PowerShell local-worker claim/store/mutex/progress/result semantics line up with Python network worker state and operator evidence? Are there stale assumptions from removed `Pipeline/Modules` or root launchers? Do local worker slots avoid source mutation and preserve retry/failure evidence? Are worker-result fields sufficient for network done reports and diagnostics without letting a worker bypass backend publish/drain policy? Are Windows path, locking, cleanup, and orphan handling realistic?

Write the required sections from the shared output contract.

## W14 Prompt - Documentation, Contract, Inventory, And Tauri Route Drift

You are W14 in a review-only audit of MediaPipelineRemuxEncodeAIO network coordinator/worker mode. Your output file is `docs/reviews/network-coordinator-worker-mode-2026-06-15/workers/W14-doc-contract-inventory-tauri-drift.md`.

Read first: `AGENTS.md`, `docs/CURRENT_PROJECT_STATE.md`, `docs/OPEN_WORK_CHECKLIST.md`, `docs/generated/PROJECT_INDEX.md`, `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`, `docs/DOCS_INDEX.md`, and generated summaries for assigned docs/source files.

Rules: review only. Do not edit docs, code, generated summaries, runtime state, config, media, or aggregate review files. If writing your worker MD, use or create a docs-only change packet and record it.

Assigned scope: `docs/architecture/NETWORK_LIFECYCLE_COMMAND_CONTRACT.md`, `docs/architecture/NETWORK_MODE_READ_ONLY_DOCUMENTATION.md`, `docs/architecture/NETWORK_WORKER_HARDENING_PLAN.md`, `docs/architecture/CONFIG_KEY_GLOSSARY.md`, `docs/inventories/API_ROUTE_INVENTORY.md`, `docs/inventories/COMMAND_OWNERSHIP_MATRIX.md`, `docs/inventories/LOCAL_API_ROUTE_OWNERSHIP_MAP.md`, `docs/architecture/LOCAL_API_EVIDENCE_MUTATION_MATRIX.md`, current-state/checklist references to network lifecycle, generated `/api/contract` tests, and Tauri backend contract route metadata under `apps/desktop/tauri/src-tauri/src/backend_contract/`.

Assigned tests/evidence: `tests/python/desktop/test_api_command_contracts.py`, `test_api_contract_payload.py`, `test_local_api_lifecycle_contract_smoke.py`, `test_tauri_shell_scaffold.py`, `tests/webview/test_webview_network_read_only_boundary.py`, and route inventory generation checks if present.

Review questions: Are active docs internally consistent about what exists now: read-only worker board, dry-run routes, confirmed lifecycle routes, setup/join/discovery routes, and disabled future operations? Do route inventories, command ownership, Tauri required routes, WebView tests, and `/api/contract` metadata agree on effect level, journaling, confirmation, secret-transfer, and mutation boundaries? Are any active docs still giving operators or future agents stale instructions that could lead them to skip required validation or assume controls are absent? Are dates absolute and aligned with 2026-06-14/2026-06-15 network hardening changes?

Write the required sections from the shared output contract. For stale-doc findings, include exact conflicting files and the safer source of current truth.

## Master Coordinator Prompt

You are the master coordinator for the review-only audit of MediaPipelineRemuxEncodeAIO network coordinator/worker mode. Do not start until all expected worker files exist under `docs/reviews/network-coordinator-worker-mode-2026-06-15/workers/`:

- `W01-coordinator-lifecycle-auth-server.md`
- `W02-coordinator-http-handlers.md`
- `W03-coordinator-claim-registry-retry.md`
- `W04-done-release-reaper-outcomes.md`
- `W05-worker-runtime-loop-http-shutdown.md`
- `W06-worker-claims-state-crash-recovery.md`
- `W07-protocol-json-auth-secret-safety.md`
- `W08-local-api-lifecycle-provider-routes.md`
- `W09-join-discovery-test-connection-paths.md`
- `W10-webview-network-settings-boundary.md`
- `W11-network-read-dtos-diagnostics-drift.md`
- `W12-network-test-suite-coverage.md`
- `W13-powershell-local-worker-compatibility.md`
- `W14-doc-contract-inventory-tauri-drift.md`

Read first: `AGENTS.md`, `docs/CURRENT_PROJECT_STATE.md`, `docs/OPEN_WORK_CHECKLIST.md`, `docs/generated/PROJECT_INDEX.md`, `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`, `docs/architecture/NETWORK_LIFECYCLE_COMMAND_CONTRACT.md`, `docs/architecture/NETWORK_WORKER_HARDENING_PLAN.md`, every worker MD, and generated summaries for any source file you reopen.

Rules: synthesis only unless the user explicitly asks for fixes. Do not edit source, generated summaries, runtime state, config, queue, media, or worker files. Create/update aggregate files only under `docs/reviews/network-coordinator-worker-mode-2026-06-15/`: `COVERAGE_MATRIX.md`, `FINDINGS_REGISTER.md`, `FINAL_SYNTHESIS.md`, and optionally `FIX_BATCH_PLAN.md`. Use or create a docs-only change packet and record all touched aggregate files. Run `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.change_control.validate_changes --require-worktree-coverage` before final response when feasible.

Synthesis process:

1. Verify every worker file exists and contains the required sections.
2. Build `COVERAGE_MATRIX.md` with one row per assigned source/test/doc file, worker owner, coverage status, and incomplete-coverage notes.
3. Reopen source only for findings that need validation, using generated summaries first. Reject weak findings explicitly in `FINAL_SYNTHESIS.md`; do not put rejected items in `FINDINGS_REGISTER.md`.
4. Deduplicate findings across workers. Preserve the most severe justified severity and cite all worker IDs that reported it.
5. Write `FINDINGS_REGISTER.md` sorted by severity then risk area. Each finding must include file, line/symbol, impact, evidence, fix direction, and validation.
6. Write `FINAL_SYNTHESIS.md` with executive risk summary, confirmed high-risk boundaries, stale-doc/contract drift, test coverage gaps, no-finding areas, incomplete coverage, and recommended fix order.
7. If `FIX_BATCH_PLAN.md` is written, split batches by risk: source/claim/state corruption first, auth/secret second, lifecycle/provider third, path-map/library fourth, WebView/docs/tests last.

Final response to the user must report aggregate file paths, number of workers included, number of confirmed findings by severity, any incomplete worker coverage, the change packet ID, and strict change coverage result.
