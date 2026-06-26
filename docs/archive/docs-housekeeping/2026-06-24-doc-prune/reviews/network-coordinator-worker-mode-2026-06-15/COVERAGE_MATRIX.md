# Network Coordinator/Worker Mode Coverage Matrix

Date: 2026-06-15

Scope: aggregate coverage matrix for the 14 worker reports under
`docs/reviews/network-coordinator-worker-mode-2026-06-15/workers/`.

Status terms:

- `covered`: the assigned worker read the file and recorded review results.
- `targeted`: the worker read focused sections needed for a finding or supporting call path.
- `reviewed as evidence`: the worker reviewed tests/docs as evidence but did not claim implementation ownership.
- `incomplete`: the worker explicitly reported missing execution, missing generated summary, stale failing test, or no live validation.

## Worker Report Gate

| Worker | Report | Section status | Notes |
|---|---|---|---|
| W01 | `workers/W01-coordinator-lifecycle-auth-server.md` | complete | Assigned test run had one stale `test_network_workflow.py` mock failure. |
| W02 | `workers/W02-coordinator-http-handlers.md` | complete | Static/source review; no live HTTP server. |
| W03 | `workers/W03-coordinator-claim-registry-retry.md` | complete | Source/test review only; no targeted tests run. |
| W04 | `workers/W04-done-release-reaper-outcomes.md` | complete | Assigned broad pytest run had the same non-W04 stale claim-fixture failure. |
| W05 | `workers/W05-worker-runtime-loop-http-shutdown.md` | complete | Targeted assigned tests passed. |
| W06 | `workers/W06-worker-claims-state-crash-recovery.md` | complete | No full assigned suite run; one temp-only malformed-claim probe. |
| W07 | `workers/W07-protocol-json-auth-secret-safety.md` | complete | Targeted source/test review and small in-memory checks. |
| W08 | `workers/W08-local-api-lifecycle-provider-routes.md` | complete | Assigned suite failed Tauri route parity for three missing Network setup routes. |
| W09 | `workers/W09-join-discovery-test-connection-paths.md` | complete | Targeted assigned tests passed; no live LAN validation. |
| W10 | `workers/W10-webview-network-settings-boundary.md` | complete | Browser Network smoke failed on stale POST allowlist. |
| W11 | `workers/W11-network-read-dtos-diagnostics-drift.md` | complete | Source/test review plus temp-only payload probes; no browser smoke. |
| W12 | `workers/W12-network-test-suite-coverage.md` | complete | Static coverage review only; did not run assigned tests. |
| W13 | `workers/W13-powershell-local-worker-compatibility.md` | complete | Targeted PowerShell/Python tests passed; no real pipeline process. |
| W14 | `workers/W14-doc-contract-inventory-tauri-drift.md` | complete | Contract/inventory checks failed on stale Tauri route list and route inventory drift. |

## Assigned File Coverage

| File | Worker owner(s) | Coverage status | Incomplete coverage notes |
|---|---|---|---|
| `AGENTS.md` | W01-W14 | covered | Common required read. |
| `docs/CURRENT_PROJECT_STATE.md` | W01-W14 | covered | Contains stale Network lifecycle wording carried into findings. |
| `docs/OPEN_WORK_CHECKLIST.md` | W01-W14 | covered | Contains stale Network lifecycle wording carried into findings. |
| `docs/generated/PROJECT_INDEX.md` | W01-W14 | covered | Large generated index used for navigation; output may be truncated in shells. |
| `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md` | W01-W14 | covered | Common boundary reference. |
| `docs/architecture/NETWORK_LIFECYCLE_COMMAND_CONTRACT.md` | W01,W02,W03,W05,W07,W08,W10,W14 | covered | Current route authority used as expected contract; stale dry-run field name found. |
| `docs/architecture/NETWORK_WORKER_HARDENING_PLAN.md` | W01,W02,W03,W04,W05,W06,W09,W10,W11,W12,W14 | covered | Header and early landmarks stale versus later completed work. |
| `docs/architecture/FILE_LIFECYCLE_MAP.md` | W04,W06,W13 | covered | Boundary context; no direct finding. |
| `docs/architecture/CONFIG_KEY_GLOSSARY.md` | W09,W14 | covered | `WorkerConfigOverrides` wording stale. |
| `docs/architecture/NETWORK_MODE_READ_ONLY_DOCUMENTATION.md` | W14 | covered | Body aligned; historical filename not treated as a finding. |
| `docs/architecture/LOCAL_API_EVIDENCE_MUTATION_MATRIX.md` | W14 | covered | Matrix rows/totals stale for Network setup routes. |
| `docs/DOCS_INDEX.md` | W14 | covered | Stale design-only wording. |
| `docs/inventories/API_ROUTE_INVENTORY.md` | W01,W02,W09,W10,W14 | covered | Network command rows exist, but totals are stale. |
| `docs/inventories/COMMAND_OWNERSHIP_MATRIX.md` | W03,W07,W10,W14 | covered | No finding; aligned with current Network setup/lifecycle route ownership. |
| `docs/inventories/LOCAL_API_ROUTE_OWNERSHIP_MAP.md` | W08,W11,W14 | covered | Network setup rows present, but header totals stale. |
| `docs/inventories/TEST_SUITE_SUBSYSTEM_INVENTORY.md` | W13 | reviewed as evidence | No finding. |
| `docs/testing/VALIDATION_LADDER_RUNBOOK.md` | W12,W13 | reviewed as evidence | No finding. |
| `docs/testing/TEST_COVERAGE_MATRIX.md` | W12,W13 | covered | Stale Network lifecycle/test-gate wording found. |
| `docs/testing/BROWSER_SMOKE_TEST_RUNBOOK.md` | W12 | reviewed as evidence | No finding. |
| `docs/testing/WEBVIEW_SMOKE_TEST_CATALOG.md` | W13 | reviewed as evidence | No finding. |
| `docs/testing/BROWSER_SMOKE_DOES_NOT_MUTATE_MATRIX.md` | W13 | reviewed as evidence | No finding. |
| `docs/reviews/network-coordinator-worker-mode-2026-06-15/PROMPT_PACK.md` | W03,W04,W05,W07,W08,W09,W10,W11,W12,W13 | covered | Shared worker instructions. |
| `src/mediapipeline/desktop/network/coordinator.py` | W01,W03 | covered | No finding in startup/local heartbeat beyond supporting call paths. |
| `src/mediapipeline/desktop/network/coordinator_lifecycle.py` | W01,W04 | covered | Stale reaper evidence gap confirmed; startup/shutdown mechanics otherwise no finding. |
| `src/mediapipeline/desktop/network/coordinator_auth.py` | W01,W07 | covered | Weak configured token startup acceptance confirmed. |
| `src/mediapipeline/desktop/network/coordinator_policy.py` | W01 | covered | No finding. |
| `src/mediapipeline/desktop/network/coordinator_http.py` | W01,W02,W07 | covered | No finding in content-length/query helpers. |
| `src/mediapipeline/desktop/network/coordinator_http_handlers.py` | W02,W03,W04,W07,W09 | covered | P1/P2 findings for claim rollback, done ownership, log redaction, and done handling. |
| `src/mediapipeline/desktop/network/coordinator_parts/http_server.py` | W01,W02,W07 | covered | No finding in request handler thread/strict JSON response helper itself. |
| `src/mediapipeline/desktop/network/coordinator_queue.py` | W01,W03,W04,W09,W13 | covered | Source identity/raw removal and PowerShell result evidence issues support findings. |
| `src/mediapipeline/desktop/network/coordinator_state.py` | W01,W02,W03,W04 | covered | Unsupported cluster-log kwargs and best-effort log reliance support findings. |
| `src/mediapipeline/desktop/network/registry.py` | W02,W03,W04,W13 | covered | Ownership, raw source identity, duplicate job id, stale reclaim findings. |
| `src/mediapipeline/desktop/network/use_cases/done_outcome.py` | W02,W04,W13 | covered | Done durability and unsupported log kwargs confirmed. |
| `src/mediapipeline/desktop/network/auth.py` | W01,W02,W05,W07 | covered | No finding in HMAC canonicalization/nonce/skew behavior. |
| `src/mediapipeline/desktop/network/identity.py` | W01,W02,W07 | covered | No finding in control-character sanitation; field-wide redaction gap is in cluster-log usage. |
| `src/mediapipeline/desktop/network/protocol.py` | W02,W04,W07,W09,W13 | covered | Loose `ClaimResponse` coercion confirmed; `DoneRequest` strict booleans no finding. |
| `src/mediapipeline/desktop/network/json_policy.py` | W02,W07 | covered | No finding. |
| `src/mediapipeline/desktop/network/http_json.py` | W02,W05,W06,W07 | covered | No finding in capped/signed worker HTTP helpers. |
| `src/mediapipeline/desktop/network/library_roots.py` | W02,W03,W06,W09 | covered | No finding in library-relative safety path; manual path-map fallback remains a finding. |
| `src/mediapipeline/desktop/network/path_map.py` | W09 | covered | Manual mapping order/escape findings. |
| `src/mediapipeline/desktop/network/worker.py` | W01,W05,W06,W09,W11,W13 | covered | Runtime descriptor/auto-map drift evidence and startup context reviewed. |
| `src/mediapipeline/desktop/network/worker_loops.py` | W04,W05,W06,W07,W13 | covered | Pre-start release and crash-recovery polling findings. |
| `src/mediapipeline/desktop/network/worker_http.py` | W05,W07 | covered | No finding. |
| `src/mediapipeline/desktop/network/poll_policy.py` | W05 | covered | No finding. |
| `src/mediapipeline/desktop/network/threading_helpers.py` | W05 | covered | No finding in helper; caller gap remains. |
| `src/mediapipeline/desktop/network/worker_claims.py` | W04,W05,W06,W13 | covered | Release/done persistence and watcher-start release findings. |
| `src/mediapipeline/desktop/network/worker_state.py` | W04,W06,W13 | covered | Pending done 404 discard and active-only crash-state findings. |
| `src/mediapipeline/desktop/network/worker_done.py` | W04,W06,W13 | covered | No finding in request builders; downstream evidence loss remains. |
| `src/mediapipeline/desktop/network/worker_record.py` | W06,W13 | covered | Empty claim source to `Path('.')` finding. |
| `src/mediapipeline/desktop/network/worker_parts/tasks.py` | W05,W06,W07 | covered | Missing identity validation finding. |
| `src/mediapipeline/desktop/network/worker_parts/state_reports.py` | W04,W06 | covered | No finding. |
| `src/mediapipeline/desktop/network/worker_parts/results.py` | W04,W06 | covered | No finding. |
| `src/mediapipeline/desktop/network/worker_parts/reporting.py` | W05 | covered | No finding. |
| `src/mediapipeline/desktop/network/diagnostics.py` | W01,W11 | covered | No finding. |
| `src/mediapipeline/desktop/network/failure_reasons.py` | W11 | covered | No finding. |
| `src/mediapipeline/desktop/network/failure_policy.py` | W01,W03,W11 | covered | Raw source identity prior-failure issue is covered under registry/source identity. |
| `src/mediapipeline/desktop/network/encode_config_snapshot.py` | W01,W03,W14 | covered | No finding in override ignore behavior; docs drift found. |
| `src/mediapipeline/desktop/network/dispatcher.py` | W03,W13 | covered | No finding. |
| `src/mediapipeline/desktop/network/standalone.py` | W03 | covered | No finding. |
| `src/mediapipeline/desktop/network/mdns.py` | W09 | covered | No finding; no live LAN validation. |
| `src/mediapipeline/desktop/network/probe.py` | W09 | covered | No finding. |
| `src/mediapipeline/desktop/network/local_ip.py` | W09 | covered | No finding. |
| `src/mediapipeline/desktop/network/share_block.py` | W09 | covered | No finding. |
| `src/mediapipeline/desktop/network/coordinator_url.py` | W09 | covered | No finding. |
| `src/mediapipeline/core/network/url_policy.py` | W01,W07,W09 | targeted | Generated summary missing for some workers; source was line-read where needed. |
| `src/mediapipeline/core/network/join.py` | W07,W09 | covered | Join blob journal/bounds/order findings. |
| `src/mediapipeline/core/network/facade.py` | W07,W09,W11 | covered | Network DTO drift/state evidence findings. |
| `src/mediapipeline/core/network/lifecycle_facade.py` | W08 | covered | Stop dry-run active-work gap. |
| `src/mediapipeline/core/api/commands_network.py` | W07,W08,W09 | covered | No direct finding. |
| `src/mediapipeline/core/api/commands.py` | W08 | covered | No finding. |
| `src/mediapipeline/core/kernel/dto_workspaces.py` | W11 | covered | No finding. |
| `src/mediapipeline/core/processes/pipeline_policy.py` | W03 | covered | No finding in normal Launch network-role blocking. |
| `src/mediapipeline/contracts/api_commands.py` | W08,W09 | covered | No finding. |
| `src/mediapipeline/desktop/api/handler.py` | W07,W08,W09 | covered | Join validation-failure journal leak confirmed. |
| `src/mediapipeline/desktop/api/command_journal.py` | W08 | targeted | No finding. |
| `src/mediapipeline/desktop/api/command_journal_policy.py` | W07 | targeted | Missing `join_blob` sensitive key supports finding. |
| `src/mediapipeline/desktop/api/contract_command.py` | W07,W08,W09,W14 | covered | Python route metadata aligned; Tauri/docs drift found. |
| `src/mediapipeline/desktop/api/contract_payload.py` | W08,W14 | covered | Current lifecycle field source of truth. |
| `src/mediapipeline/desktop/api/contract_read.py` | W11 | covered | Stale read-only route wording noted through DTO/doc drift. |
| `src/mediapipeline/desktop/api/routes_command.py` | W08 | covered | No finding. |
| `src/mediapipeline/desktop/api/routes_read.py` | W11 | covered | No finding. |
| `src/mediapipeline/desktop/api/server.py` | W08 | targeted | No finding. |
| `src/mediapipeline/desktop/api/http_helpers.py` | W09 | targeted | Body cap supports join-bounds severity. |
| `src/mediapipeline/desktop/application/network_lifecycle_provider.py` | W03,W05,W06,W08,W13 | covered | Watcher, stop, startup-race, and result-artifact findings. |
| `src/mediapipeline/desktop/application/facade.py` | W11 | targeted | No finding. |
| `src/mediapipeline/desktop/network/processing_policy.py` | W03,W06 | incomplete | Untracked/no generated summary in worker context; only narrow context inspected. |
| `apps/desktop/tauri/src-tauri/src/backend_contract/routes.rs` | W08,W14 | covered | Missing required setup routes confirmed. |
| `apps/desktop/tauri/src-tauri/src/backend_contract/route_contract.rs` | W08,W14 | covered | No finding beyond missing setup semantic checks. |
| `apps/desktop/tauri/src-tauri/src/backend_contract/types.rs` | W08,W14 | covered | Rust metadata lacks fields needed for some future route semantics checks. |
| `apps/desktop/webview/static/assets/networkView.js` | W10,W11 | covered | No direct mutation finding; browser smoke/route wording findings. |
| `apps/desktop/webview/static/assets/settingsView.builders.network.js` | W09,W10 | covered | Path-map row Test finding. |
| `apps/desktop/webview/static/partials/page-network.html` | W10 | covered | No finding. |
| `apps/desktop/webview/static/assets/apiClient.js` | W10 | covered | No finding. |
| `apps/desktop/webview/static/assets/settingsView.js` | W10 | targeted | No finding. |
| `apps/desktop/webview/static/assets/settingsMetadata.js` | W10 | targeted | No token-rendering finding. |
| `apps/desktop/webview/static/assets/app.js` | W10 | targeted | UI preference sync explains browser smoke failure. |
| `apps/desktop/webview/static/assets/styles.pages.css` | W10 | targeted | No warning/confirmation hiding finding. |
| `apps/desktop/webview/static/assets/styles.css` | W10 | targeted | No finding. |
| `apps/desktop/webview/static/assets/styles.components.css` | W10 | targeted | No finding. |
| `apps/desktop/webview/static/assets/styles.controls.css` | W10 | targeted | No finding. |
| `apps/desktop/webview/static/assets/styles.layout.css` | W10 | targeted | No finding. |
| `ops/pipeline/engine/queue/local_worker_slots.ps1` | W13 | covered | No finding. |
| `ops/pipeline/engine/queue/worker_claim_store.ps1` | W13 | covered | Stale result diagnostics finding. |
| `ops/pipeline/engine/queue/worker_mutex.ps1` | W13 | covered | No finding. |
| `ops/pipeline/engine/queue/worker_process.ps1` | W13 | covered | Stale result deletion on slot reuse supports finding. |
| `ops/pipeline/engine/queue/worker_progress.ps1` | W13 | covered | No finding. |
| `ops/pipeline/engine/process/worker_result.ps1` | W13 | covered | Missing terminal/retry fields confirmed. |
| `ops/pipeline/entrypoints/MediaPipeline.ps1` | W13 | targeted | Worker-result write path supports W13-001. |
| `ops/pipeline/engine/process/pipeline_processing.ps1` | W13 | targeted | Process result schema supports W13-002. |
| `ops/scripts/smoke/Test-WebViewBrowserNetworkSmoke.ps1` | W10,W12 | reviewed as evidence | Wrapper failed due browser smoke allowlist. |
| `ops/pipeline/tests/Unit/Invoke-LocalWorkerSlotChecks.ps1` | W12,W13 | reviewed as evidence | Passed in W13; no finding. |
| `ops/pipeline/tests/Unit/Invoke-LocalWorkerClaimLifecycleChecks.ps1` | W12,W13 | reviewed as evidence | Passed in W13; missing stale-result durability assertion. |
| `tests/python/desktop/test_network_coordinator_startup.py` | W01,W12 | reviewed as evidence | No finding. |
| `tests/python/desktop/test_network_coordinator_helpers.py` | W01,W03,W12 | reviewed as evidence | No finding. |
| `tests/python/desktop/test_network_coordinator_http.py` | W01,W02,W04,W12 | reviewed as evidence | Missing log-field/claim rollback/done owner tests. |
| `tests/python/desktop/test_network_coordinator_source_policy.py` | W02,W04,W12 | reviewed as evidence | No finding. |
| `tests/python/desktop/test_network_crash_recovery.py` | W04,W06,W12 | reviewed as evidence | Missing full crash-recovery-post-failure polling sequence. |
| `tests/python/desktop/test_network_done_release.py` | W04,W06,W13,W12 | reviewed as evidence | Missing save-failure acceptance and PowerShell result mapping cases. |
| `tests/python/desktop/test_network_drift_descriptor.py` | W05,W09,W11,W12 | reviewed as evidence | Missing auto-map drift case. |
| `tests/python/desktop/test_network_firewall.py` | W12 | reviewed as evidence | No finding. |
| `tests/python/desktop/test_network_inflight_registry.py` | W03,W12 | reviewed as evidence | Missing live duplicate job id and normalized source identity cases. |
| `tests/python/desktop/test_network_join.py` | W09,W12 | reviewed as evidence | Missing malformed/hostile blob cases. |
| `tests/python/desktop/test_network_lifecycle_fixes.py` | W05,W08,W12 | reviewed as evidence | Stop test does not prove no kill/terminate call. |
| `tests/python/desktop/test_network_library_relative_claim.py` | W02,W03,W06,W09,W12 | reviewed as evidence | No finding in library-relative path safety. |
| `tests/python/desktop/test_network_local_ip.py` | W09,W12 | reviewed as evidence | No finding. |
| `tests/python/desktop/test_network_mdns.py` | W09,W12 | reviewed as evidence | No finding. |
| `tests/python/desktop/test_network_path_auto_map.py` | W09,W12 | reviewed as evidence | Missing unsafe manual path-map cases. |
| `tests/python/desktop/test_network_protocol_runtime.py` | W02,W07,W13,W12 | reviewed as evidence | Missing strict `ClaimResponse` boolean/int tests. |
| `tests/python/desktop/test_network_security.py` | W01,W02,W03,W05,W07,W12 | reviewed as evidence | Registry empty-worker internal affordance exists; HTTP boundary gap remains. |
| `tests/python/desktop/test_network_test_connection.py` | W09,W12 | reviewed as evidence | No finding. |
| `tests/python/desktop/test_network_worker_runtime.py` | W03,W05,W06,W13,W12 | reviewed as evidence | Missing watcher-start/process-result cases. |
| `tests/python/desktop/test_network_worker_source_policy.py` | W05,W06,W13,W12 | reviewed as evidence | No finding beyond gaps. |
| `tests/python/desktop/test_network_worker_state.py` | W04,W06,W13,W12 | reviewed as evidence | Current tests codify 404 discard/active-only claim-safe behavior. |
| `tests/python/desktop/test_network_workflow.py` | W01,W02,W03,W04,W12 | incomplete | Stale `_snapshot_encode_config` mock failure blocks assigned workflow evidence. |
| `tests/python/desktop/test_network_coordinator_policy_phase_e.py` | W12 | incomplete | Untracked in worktree and lacked generated summary in W12. |
| `tests/python/desktop/test_api_command_contracts.py` | W07,W08,W10,W12,W14 | reviewed as evidence | Current Python route metadata tests align; join failure leak still uncovered. |
| `tests/python/desktop/test_api_contract_payload.py` | W07,W08,W12,W14 | reviewed as evidence | Current lifecycle field source of truth. |
| `tests/python/desktop/test_api_route_inventory.py` | W14 | reviewed as evidence | Failing route inventory/mutation matrix drift. |
| `tests/python/desktop/test_application_facade_network.py` | W05,W10,W12 | reviewed as evidence | Missing malformed worker-state row cases. |
| `tests/python/desktop/test_application_facade_process_launch.py` | W06,W13 | reviewed as evidence | Does not cover PowerShell worker-result parsing. |
| `tests/python/desktop/test_local_api_lifecycle_contract_smoke.py` | W08,W12 | reviewed as evidence | No finding. |
| `tests/python/desktop/test_tauri_shell_scaffold.py` | W08,W12,W14 | incomplete | Assigned route parity test failing due missing Rust Network setup routes. |
| `tests/webview/test_webview_network_read_only_boundary.py` | W09,W10,W12,W14 | reviewed as evidence | Current real route metadata expects join confirmations. |
| `tests/webview/test_webview_browser_network_smoke.py` | W10,W11,W12 | incomplete | Browser smoke failing stale POST allowlist; fixture join confirmation metadata stale. |

## Cross-Coverage Notes

- All 14 worker files exist and contain the required review sections.
- No worker executed representative real-media validation, live LAN discovery, real coordinator/worker lifecycle start/stop, publish/drain, rename, or source/scratch/output mutation.
- Several workers ran targeted tests, but the combined review evidence is not green because `test_network_workflow.py`, `test_tauri_shell_scaffold.py`, `test_api_route_inventory.py`, and `test_webview_browser_network_smoke.py` had reported failures.
- Generated summaries were read before master source reopens. Known missing or incomplete summary coverage was reported for `src/mediapipeline/core/network/url_policy.py`, `src/mediapipeline/desktop/network/processing_policy.py`, and untracked `tests/python/desktop/test_network_coordinator_policy_phase_e.py`.
