# Worker Review: W14 - Documentation, Contract, Inventory, And Tauri Route Drift

## Scope

Review-only audit of active documentation, route inventories, command ownership, generated `/api/contract` tests, WebView route assertions, and Tauri backend contract metadata for MediaPipelineRemuxEncodeAIO network coordinator/worker mode.

Assigned focus:

- Active network lifecycle and read-only documentation:
  - `docs/architecture/NETWORK_LIFECYCLE_COMMAND_CONTRACT.md`
  - `docs/architecture/NETWORK_MODE_READ_ONLY_DOCUMENTATION.md`
  - `docs/architecture/NETWORK_WORKER_HARDENING_PLAN.md`
  - `docs/architecture/CONFIG_KEY_GLOSSARY.md`
- Active inventories and ownership/mutation maps:
  - `docs/inventories/API_ROUTE_INVENTORY.md`
  - `docs/inventories/COMMAND_OWNERSHIP_MATRIX.md`
  - `docs/inventories/LOCAL_API_ROUTE_OWNERSHIP_MAP.md`
  - `docs/architecture/LOCAL_API_EVIDENCE_MUTATION_MATRIX.md`
- Current state/checklist references to Network lifecycle controls.
- Generated `/api/contract` route metadata tests.
- Tauri backend contract route metadata under `apps/desktop/tauri/src-tauri/src/backend_contract/`.

This worker made no code, docs, generated-summary, runtime, config, media, or aggregate review edits. The only intended review artifact edit is this file, recorded under docs-only change packet `MP-CHANGE-2026-0615-008`.

## Required Reads Completed

| Required read | Status | Notes |
| --- | --- | --- |
| `AGENTS.md` | Completed | Used as repository operating rules and no-touch/change-packet guidance. |
| `docs/CURRENT_PROJECT_STATE.md` | Completed | Contains stale Network lifecycle statements called out below. |
| `docs/OPEN_WORK_CHECKLIST.md` | Completed | Contains stale Network lifecycle checklist text called out below. |
| `docs/generated/PROJECT_INDEX.md` | Completed | Used for navigation. |
| `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md` | Completed | Used for mutation, media-policy, command-journal, and WebView/Tauri ownership boundaries. |
| `docs/DOCS_INDEX.md` | Completed | Contains stale design-only/read-only labels called out below. |
| Generated summaries for assigned docs/source/tests | Completed where present | Most summaries were metadata-only. No generated summary was found for `docs/architecture/NETWORK_WORKER_HARDENING_PLAN.md`, so the full file was read directly. |

## Coverage Ledger

| Area | Coverage | Evidence |
| --- | --- | --- |
| Network lifecycle docs | Reviewed assigned lifecycle/read-only/hardening docs and current-state/checklist/docs-index references. | Compared docs to `src/mediapipeline/desktop/api/contract_command.py`, `src/mediapipeline/desktop/api/contract_payload.py`, route inventories, and tests. |
| Route inventories | Reviewed API route inventory, command ownership matrix, local ownership map, and evidence mutation matrix. | Ran route inventory generation checks via `tests.python.desktop.test_api_route_inventory`; failures are reported below. |
| Generated `/api/contract` metadata tests | Reviewed assigned Python contract tests. | `test_api_command_contracts.py` and `test_api_contract_payload.py` align with current route/effect metadata and expose stale docs. |
| Tauri backend route contract | Reviewed `routes.rs`, `route_contract.rs`, and `types.rs`. | Ran the Tauri required-route parity test; it currently fails because Rust required routes omit Network setup routes. |
| WebView Network route boundary | Reviewed `tests/webview/test_webview_network_read_only_boundary.py`. | Test expectations include current worker board, lifecycle dry-runs, setup/join/discovery routes, and confirmed lifecycle routes. |

## Findings

| ID | Severity | File / line | Problem |
| --- | --- | --- | --- |
| W14-001 | P2 | `docs/architecture/NETWORK_LIFECYCLE_COMMAND_CONTRACT.md:53` | Dry-run required-result fields still name removed `would_write_state` instead of current `dry_run_writes` and `confirmed_route_would_write`. |
| W14-002 | P2 | `docs/CURRENT_PROJECT_STATE.md:24`, `docs/CURRENT_PROJECT_STATE.md:114`, `docs/CURRENT_PROJECT_STATE.md:192`, `docs/OPEN_WORK_CHECKLIST.md:73`, `docs/DOCS_INDEX.md:72` | Active state/index docs still describe Network lifecycle controls as absent, future-only, or design-only even though backend-owned lifecycle and setup routes now exist. |
| W14-003 | P2 | `apps/desktop/tauri/src-tauri/src/backend_contract/routes.rs:110` | Tauri required backend routes omit active Network setup/discovery routes required by the Python local API contract. |
| W14-004 | P2 | `docs/architecture/LOCAL_API_EVIDENCE_MUTATION_MATRIX.md:5`, `docs/architecture/LOCAL_API_EVIDENCE_MUTATION_MATRIX.md:160`, `docs/architecture/LOCAL_API_EVIDENCE_MUTATION_MATRIX.md:221`, `docs/inventories/API_ROUTE_INVENTORY.md:7`, `docs/inventories/LOCAL_API_ROUTE_OWNERSHIP_MAP.md:5` | Route inventory totals and mutation matrix are stale; the matrix omits Network setup routes and their effect boundaries. |
| W14-005 | P2 | `docs/architecture/CONFIG_KEY_GLOSSARY.md:214` | `WorkerConfigOverrides` is documented as applied at job-claim time, but current backend policy ignores it. |
| W14-006 | P2 | `docs/architecture/NETWORK_WORKER_HARDENING_PLAN.md:3`, `docs/architecture/NETWORK_WORKER_HARDENING_PLAN.md:40`, `docs/architecture/NETWORK_WORKER_HARDENING_PLAN.md:55` | The hardening plan header and early landmarks still say not-started / old protocol / old endpoint set while later sections and code show 2026-06-14 implementation progress. |

## Detailed Findings

### W14-001 - Lifecycle dry-run doc names stale result fields

- Severity: P2
- File/line/symbol: `docs/architecture/NETWORK_LIFECYCLE_COMMAND_CONTRACT.md:53`, lifecycle dry-run required result fields.
- Problem: The contract doc says dry-run result fields include `would_write_state`.
- Impact: Future agents or operators could write clients/tests against a removed field and miss the newer distinction between dry-run diagnostics and confirmed-route writes.
- Evidence:
  - The doc lists `would_write_state` in the required dry-run fields.
  - Current source of truth in `src/mediapipeline/desktop/api/contract_payload.py:19` uses `dry_run_writes` and `confirmed_route_would_write`.
  - `tests/python/desktop/test_api_contract_payload.py:345` asserts `dry_run_writes` and `confirmed_route_would_write` are present and `would_write_state` is absent.
- Safer current truth: `src/mediapipeline/desktop/api/contract_payload.py` plus `tests/python/desktop/test_api_contract_payload.py`.
- Suggested fix direction: Replace `would_write_state` with `dry_run_writes` and `confirmed_route_would_write` in the lifecycle contract doc, preserving the explicit `effect: none` dry-run boundary.
- Suggested validation: Run `PYTHONPATH=src .\apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_api_contract_payload`.

### W14-002 - Active current-state/checklist/index docs still say Network lifecycle controls are absent or design-only

- Severity: P2
- Files/lines/symbols:
  - `docs/CURRENT_PROJECT_STATE.md:24`
  - `docs/CURRENT_PROJECT_STATE.md:114`
  - `docs/CURRENT_PROJECT_STATE.md:192`
  - `docs/OPEN_WORK_CHECKLIST.md:73`
  - `docs/DOCS_INDEX.md:72`
- Problem: These active docs still describe Network lifecycle controls as read-only-only, absent, future-only, or design-only.
- Impact: Operators and future agents could skip required validation or assume controls/routes are absent, despite current backend-owned lifecycle and setup/join/discovery routes being present and tested.
- Evidence:
  - `docs/architecture/NETWORK_LIFECYCLE_COMMAND_CONTRACT.md:5` describes current dry-run and confirmed start/stop routes.
  - `docs/architecture/NETWORK_MODE_READ_ONLY_DOCUMENTATION.md:5` explicitly says the historical filename is retained but the page is no longer read-only-only.
  - `src/mediapipeline/desktop/api/contract_command.py:651` through `:823` defines worker board/status, lifecycle dry-run routes, setup/discovery/join routes, and confirmed lifecycle routes.
  - `docs/inventories/COMMAND_OWNERSHIP_MATRIX.md:186` through `:205` lists backend ownership/effects for active Network commands.
  - `tests/webview/test_webview_network_read_only_boundary.py:383` through `:467` asserts WebView-visible Network routes include worker board, dry-runs, setup/discovery/join, and confirmed lifecycle routes.
- Safer current truth: `NETWORK_LIFECYCLE_COMMAND_CONTRACT.md`, `NETWORK_MODE_READ_ONLY_DOCUMENTATION.md`, `src/mediapipeline/desktop/api/contract_command.py`, `COMMAND_OWNERSHIP_MATRIX.md`, and the WebView Network boundary test.
- Suggested fix direction: Refresh current-state/checklist/index wording to say current Network mode has a backend-owned read-only worker board plus dry-run lifecycle routes, confirmed lifecycle routes, and setup/discovery/join routes; keep future reclaim/release/abort/quarantine operations disabled.
- Suggested validation: Run the assigned contract/WebView route tests and grep active docs for stale phrases such as "no Network lifecycle POST route", "design-only", "controls intentionally absent", and "future lifecycle controls".

### W14-003 - Tauri required-route metadata omits Network setup/discovery routes

- Severity: P2
- File/line/symbol: `apps/desktop/tauri/src-tauri/src/backend_contract/routes.rs:110`, `REQUIRED_ROUTES`.
- Problem: Tauri required backend routes include lifecycle dry-runs, worker test-connection, and confirmed start/stop routes, but omit:
  - `POST /api/network/coordinator/join-blob`
  - `POST /api/network/worker/discover-coordinators`
  - `POST /api/network/worker/join-cluster`
- Impact: Tauri startup contract checks can pass without requiring active Network setup routes, creating drift between Rust route metadata and the Python local API contract. This weakens setup/join/discovery route availability guarantees in desktop shell packaging.
- Evidence:
  - `src/mediapipeline/desktop/api/contract_command.py:723` defines worker discovery as `effect: none`, no confirmation, not journaled.
  - `src/mediapipeline/desktop/api/contract_command.py:744` defines coordinator join blob as `effect: secret-transfer`, confirmation required, not journaled.
  - `src/mediapipeline/desktop/api/contract_command.py:754` defines worker join cluster as `effect: config-write`, confirmation required, not journaled.
  - Running `PYTHONPATH=src .\apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_tauri_shell_scaffold.TauriShellScaffoldTests.test_tauri_shell_required_routes_match_python_local_api_contract` failed with those three route tuples missing from Tauri.
- Safer current truth: `src/mediapipeline/desktop/api/contract_command.py`, `tests/python/desktop/test_tauri_shell_scaffold.py`, and `docs/inventories/COMMAND_OWNERSHIP_MATRIX.md`.
- Suggested fix direction: Add the three setup/discovery routes to `REQUIRED_ROUTES` with auth required, then extend Tauri route semantic validation for setup route effect/confirmation/frontend exposure.
- Suggested validation: Rerun `tests.python.desktop.test_tauri_shell_scaffold`, especially `test_tauri_shell_required_routes_match_python_local_api_contract`.

### W14-004 - Route inventory totals and mutation matrix lag the current local API contract

- Severity: P2
- Files/lines/symbols:
  - `docs/architecture/LOCAL_API_EVIDENCE_MUTATION_MATRIX.md:5`
  - `docs/architecture/LOCAL_API_EVIDENCE_MUTATION_MATRIX.md:160`
  - `docs/architecture/LOCAL_API_EVIDENCE_MUTATION_MATRIX.md:221`
  - `docs/inventories/API_ROUTE_INVENTORY.md:7`
  - `docs/inventories/LOCAL_API_ROUTE_OWNERSHIP_MAP.md:5`
- Problem: Header totals still say `112` routes / `66` POST routes, while the live contract has `116` routes / `70` POST routes. The evidence mutation matrix also omits Network setup routes:
  - `POST /api/network/worker/test-connection`
  - `POST /api/network/worker/discover-coordinators`
  - `POST /api/network/coordinator/join-blob`
  - `POST /api/network/worker/join-cluster`
- Impact: The mutation/evidence matrix no longer gives a complete boundary view for Network setup. In particular, `secret-transfer` and `config-write` setup operations can be missed during audit or validation planning.
- Evidence:
  - Live `LOCAL_API_ROUTE_CONTRACT` count is `116 {'GET': 46, 'POST': 70}`.
  - `PYTHONPATH=src .\apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_api_route_inventory -q` failed three route inventory tests.
  - The matrix-specific failure reported the four omitted Network setup/test routes above.
  - `docs/inventories/API_ROUTE_INVENTORY.md:252` and `docs/inventories/LOCAL_API_ROUTE_OWNERSHIP_MAP.md:231` do list the Network command rows, so the main remaining inventory issue there is stale totals.
- Safer current truth: `src/mediapipeline/desktop/api/contract_command.py`, `docs/inventories/COMMAND_OWNERSHIP_MATRIX.md`, and `tests/python/desktop/test_api_route_inventory.py`.
- Suggested fix direction: Regenerate or manually refresh the inventory totals and mutation matrix rows. Place test-connection/discovery under no-mutation/effect-none, join-blob under secret-transfer, and join-cluster under config-write.
- Suggested validation: Rerun `PYTHONPATH=src .\apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_api_route_inventory -q`.

### W14-005 - Config glossary says `WorkerConfigOverrides` is applied, but backend policy ignores it

- Severity: P2
- File/line/symbol: `docs/architecture/CONFIG_KEY_GLOSSARY.md:214`, `WorkerConfigOverrides`.
- Problem: The glossary says `WorkerConfigOverrides` is "JSON per-worker config overrides applied at job-claim time."
- Impact: Operators or future agents could believe worker-specific encode/media policy overrides are active and skip required policy validation, when the backend currently ignores the setting.
- Evidence:
  - `docs/architecture/NETWORK_MODE_READ_ONLY_DOCUMENTATION.md:85` says `WorkerConfigOverrides` is deprecated/hidden for quality policy and must not override quality-affecting policy.
  - `src/mediapipeline/desktop/network/encode_config_snapshot.py:64` through `:71` logs that `WorkerConfigOverrides` is disabled by backend policy and returns the coordinator snapshot unchanged.
  - `src/mediapipeline/desktop/network/coordinator_queue.py:414` through `:419` says overrides remain loadable for compatibility but are ignored.
  - `apps/desktop/webview/static/assets/settingsMetadata.js:486` describes the field as compatibility-only and currently ignored by backend policy.
- Safer current truth: `NETWORK_MODE_READ_ONLY_DOCUMENTATION.md`, `encode_config_snapshot.py`, `coordinator_queue.py`, and WebView settings metadata.
- Suggested fix direction: Update the glossary to call the setting compatibility-only/backend-disabled unless a future provider rollout explicitly honors it with media-policy validation.
- Suggested validation: Grep active docs/source metadata for `WorkerConfigOverrides` and align help text with backend-disabled behavior. If source metadata text changes too, run the relevant settings metadata tests.

### W14-006 - Network worker hardening plan mixes not-started baseline text with completed 2026-06-14 work

- Severity: P2
- Files/lines/symbols:
  - `docs/architecture/NETWORK_WORKER_HARDENING_PLAN.md:3`
  - `docs/architecture/NETWORK_WORKER_HARDENING_PLAN.md:40`
  - `docs/architecture/NETWORK_WORKER_HARDENING_PLAN.md:55`
- Problem: The plan header still says `Status: DRAFT (not started)`, while later sections mark many A/B/C/D items complete on 2026-06-14. Early landmarks also still describe older protocol and endpoint assumptions.
- Impact: A future agent could treat completed hardening changes as not started, reimplement stale protocol assumptions, or omit now-active setup/discovery/join routes from follow-up validation.
- Evidence:
  - The early claim response landmark says there is no `library_id` / `relative_path` "today", while `docs/architecture/NETWORK_LIFECYCLE_COMMAND_CONTRACT.md:70` through `:80` documents protocol version 2 with those optional fields and the hardening plan later marks that work complete.
  - The early endpoint landmark lists only older coordinator/worker endpoints, while later plan sections mark join-blob/join-cluster and discover-coordinators complete.
  - Source route metadata in `src/mediapipeline/desktop/api/contract_command.py:711` through `:763` includes test-connection, discovery, join blob, and join cluster routes.
- Safer current truth: Later dated sections in the same hardening plan, `NETWORK_LIFECYCLE_COMMAND_CONTRACT.md`, and `src/mediapipeline/desktop/api/contract_command.py`.
- Suggested fix direction: Refresh the plan header/status and either convert early landmarks to dated historical baseline text or update them to the current protocol/endpoint set.
- Suggested validation: Grep the plan for "not started", "NO library_id", "today", and stale endpoint lists after the doc refresh.

## Test Coverage Gaps

- Tauri route semantic checks only validate lifecycle route metadata today. `apps/desktop/tauri/src-tauri/src/backend_contract/route_contract.rs:30` through `:62` does not validate setup/discovery/join route effects, confirmation requirements, or frontend exposure.
- Tauri route metadata types in `apps/desktop/tauri/src-tauri/src/backend_contract/types.rs:17` through `:30` do not carry `journaled` or result/data schema fields, so Rust-side checks cannot currently assert the unjournaled `secret-transfer` setup boundary or data schema names.
- Active docs stale-wording checks appear absent. The existing tests catch route contract and inventory drift, but they do not catch `CURRENT_PROJECT_STATE.md`, `OPEN_WORK_CHECKLIST.md`, or `DOCS_INDEX.md` continuing to call active routes absent/design-only.
- `test_api_route_inventory` catches the stale inventory/matrix state and is currently failing. Treat it as part of the Network hardening gate after the inventory refresh.
- This audit did not execute real lifecycle start/stop providers, Tauri preview, Browser/WebView smoke, or live local API startup; those are outside this review-only scope.

## Boundary Risks

- Stale active docs that say controls are absent can cause future agents to skip lifecycle route validation or fail to preserve the confirmation/dry-run split.
- The mutation matrix omission hides Network setup routes from the audit view, including `secret-transfer` for join blob and `config-write` for join cluster.
- The Tauri required-route gap can let the desktop shell route contract drift from Python local API metadata.
- The `WorkerConfigOverrides` glossary drift risks media-policy misunderstanding because a documented "applied" override is actually ignored by backend policy.

## Files With No Findings

- `docs/architecture/NETWORK_MODE_READ_ONLY_DOCUMENTATION.md` - Despite the historical filename, the body accurately states the Network page is no longer read-only-only and documents backend-owned lifecycle/setup boundaries.
- `docs/inventories/COMMAND_OWNERSHIP_MATRIX.md` - Network command ownership, effects, confirmation gates, unjournaled setup routes, and disabled future operations are aligned with the current contract.
- `tests/python/desktop/test_api_command_contracts.py` - Current expectations align with 70 POST routes, strict lifecycle confirmation, and Network setup payloads.
- `tests/python/desktop/test_api_contract_payload.py` - Current expectations align with lifecycle summary/status/effects, dry-run field names, test-connection, and discovery metadata.
- `tests/webview/test_webview_network_read_only_boundary.py` - Current expectations align with the active worker board, dry-run routes, setup/discovery/join routes, and confirmed lifecycle routes.

## Incomplete Coverage

- Did not run the full Python test suite.
- Did not start the local API or capture a live `/api/contract` response.
- Did not run Tauri preview/check-only or WebView browser smoke.
- Did not audit archived docs or intentionally obsolete AI handoff material.
- Did not inspect every source line in unrelated Tauri modules; Tauri review was limited to backend contract route metadata and assigned scaffold tests.

## Suggested Follow-Up Prompts

1. Refresh stale active docs and inventories for the 2026-06-14/2026-06-15 Network hardening state, including lifecycle dry-run fields, current-state/checklist wording, API totals, mutation matrix setup rows, `WorkerConfigOverrides`, and the hardening plan status.
2. Update Tauri backend contract route metadata to include Network setup/discovery/join routes and add semantic checks for effect, confirmation, frontend exposure, journaling, and schemas where Rust metadata supports them.
3. Add or extend stale-doc guard tests that fail when active current-state/checklist/index docs still say active Network lifecycle routes are absent, read-only-only, or design-only.
