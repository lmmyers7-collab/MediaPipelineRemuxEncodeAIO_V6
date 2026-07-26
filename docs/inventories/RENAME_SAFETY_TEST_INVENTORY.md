# Rename Safety Test Inventory

Purpose: inventory all rename-related test files, describe what each covers and does not cover, identify how fixture data is provided, and note safety-property gaps. This document is observational and does not add new tests.

Total inventoried files: 23. This count is the 20 active `test_*rename*.py` files plus three directly supporting safety suites: `test_api_path_dialogs.py`, `test_stage_contracts.py`, and `test_stage_runner.py`. Shared cross-command contract suites cited below are supporting evidence but are not included in this count.
Most fixture data is generated dynamically in temporary directories or hardcoded as Python dicts within test methods. The bad rename regression corpus lives at `tests/fixtures/rename/bad_rename_cases.jsonl`.

---

## Test File Inventory

### WebView / UI Layer

| Test file | Type | What it covers |
|---|---|---|
| `test_rename_workbench.py` | Python unittest | Rename WebView static structure, JS route literals/exports, production-plan authority wording, backend browse mode normalization, and bad-case corpus append command boundary |
| `test_application_facade_web_static_rename.py` | Python unittest | Static rename asset/DOM ownership, cleaning-filter/settings hooks, preview/apply/outcome contracts, browse selection, busy guards, and namespace wiring |
| `test_webview_rename_readiness_smoke.py` | Node VM (no browser) | Apply Readiness state transitions in mocked DOM; single-row "Ready" scope; duplicate-destination "Blocked" scope; verifies `rename.apply` is not called when blocked; verifies immediate apply progress and `rename.undo` post shape |
| `test_webview_browser_rename_smoke.py` | Chrome/Edge CDP | Same logic under real browser rendering; verifies the Settings workbench labels the production destination plan as authority and exposes reference-cleaner parity; verifies the Browse Files button posts `POST /api/rename/browse` and stages returned paths without apply; renders a TV rename preview row, selects it, validates readiness = Ready; creates duplicate-destination scenario, validates readiness = Blocked; confirms no POST to `/api/rename/apply`; verifies Undo Last Apply visibility after a backend result with undo manifest |

The two readiness smokes share the same fixture shape: a single TV episode row — `Serial Experiments Lain E01 Weird.mkv` → `Serial Experiments Lain - S02E01 - Weird.mkv` — and a duplicate-destination scenario with two rows sharing the same target path.

### Local API Dialog Host Layer

| Test file | Type | What it covers |
|---|---|---|
| `test_api_path_dialogs.py` | Python unittest | Windows PowerShell host selection for the native path picker, encoded-command invocation, selected-path JSON payload parsing, missing-host reporting, and process-failure diagnostics that identify the selected host |
| `test_application_facade_local_api_rename.py` | Python unittest | Browse, production-authoritative workbench preview with server-resolved PowerShell and matching cleaning-policy fingerprint, filter-case, apply, and undo Local API routes; strict confirmations; configured-root authority; active-work rejection without mutation; injected native path picker |

### Facade / Policy Layer

| Test file | Type | What it covers |
|---|---|---|
| `test_application_facade_rename.py` | Python unittest | Facade preview/apply confirmation, production-plan versus Python-reference parity, fail-closed production/policy evidence handling, selection, backend apply lock, active-pipeline work rejection, configured-root authority, and filesystem-mutation guard behavior |
| `test_facade_rename_policy.py` | Python unittest | Preview count aggregation (total/ready/warning/blocked); confidence/source/change_kind breakdowns; selected-source filtering with path casefolding (Windows/POSIX); missing-source warning generation |
| `test_rename_service.py` | Python unittest | High-level facade integration: movie prediction with natural file sort order; pipeline preview runner integration with mocked subprocess; force-pipeline-name per-row config |

### Service Layer — Name Parsing

| Test file | Type | What it covers |
|---|---|---|
| `test_service_rename_tv.py` | Python unittest | Episode revisions, canonical multi-episode ranges, E001-E999 bounds, ordinal seasons/cours, specials precedence, bare anime episodes, pure-numeric versus numeric-leading titles, metadata-tail scoping, and folder/file season precedence |
| `test_service_rename_movie.py` | Python unittest | Release cleaning, rightmost plausible year selection, legitimate numeric/metadata-like title preservation, verified-tail revision removal, explicit remove-term token bounds, and per-category filter options/terms |
| `test_service_rename_utils.py` | Python unittest | Shared utility functions |

### Service Layer — Planning And Policy

| Test file | Type | What it covers |
|---|---|---|
| `test_service_rename_planner.py` | Python unittest | Rename path planning, cleaning-policy propagation, exact preservation plus strict leaf/suffix validation of authoritative PowerShell movie/TV preview results, duplicate destinations, canonical multi-episode identity, semantic overlap blocking, hierarchy destinations, sidecar numbering, and path authority |
| `test_service_rename_plan_policy.py` | Python unittest | Policy decisions applied during planning (blocker assignment, status derivation) |
| `test_service_rename_discovery.py` | Python unittest | Media file discovery in folders with natural sort order (`Show.10.mkv` after `Show.2.mkv`) |

### Service Layer — Preview And Apply Execution

| Test file | Type | What it covers |
|---|---|---|
| `test_service_rename_preview.py` | Python unittest | Preview generation and pipeline naming integration |
| `test_service_rename_preview_runner.py` | Python unittest | Preview script execution/output parsing plus the active bad-case corpus through the real PowerShell production naming preview; verifies Python/PowerShell parity for numeric, ambiguous-title, and verified metadata-tail cases |
| `test_service_rename_apply_runner.py` | Python unittest | Temporary-filesystem apply and undo, real media-plus-sidecar reversal, metadata restore, multi-episode range identity preservation, and unsafe/missing manifest preflight blocking |
| `test_service_rename_apply.py` | Python unittest | Filesystem operation construction, semantic TV-overlap defense, Windows case-only handling, mutation boundaries, sidecar collisions/metadata, rollback, and undo-manifest path authority |
| `test_stage_contracts.py` | Python unittest | Rename-stage registration, strict mutation intent/confirmation DTOs, and generated stage-schema coverage |
| `test_stage_runner.py` | Python unittest | Scratch-only dispatcher rename dry-run/execute, literal confirmation, source/scratch boundary rejection, stale fingerprint rejection, required command/operation journals, duplicate-operation replay, undo evidence, and rollback after terminal-evidence failure |
| `test_service_rename_tv_folder.py` | Python unittest | TV folder structure handling |
| `test_rename_bad_case_corpus.py` | Python unittest | JSONL bad rename regression corpus schema, unique IDs, and active case output expectations, including the Edge of Tomorrow verified-tail drift case shared with the real PowerShell preview gate |

---

## Fixture Data Approach

Most rename test data is inline:

- **Inline Python dicts**: `test_service_rename_apply.py`, `test_facade_rename_policy.py` hardcode row structures like `{"source": ..., "destination": ..., "status": "ready", ...}` inside test methods.
- **Temporary directories**: `test_rename_service.py`, `test_service_rename_discovery.py`, `test_service_rename_planner.py`, `test_service_rename_apply.py`, `test_service_rename_apply_runner.py`, `test_application_facade_rename.py`, and `test_application_facade_local_api_rename.py` create isolated files and directories. Apply/undo coverage includes an on-disk media file plus pipeline sidecar.
- **Scratch-only dispatcher fixtures**: `test_stage_runner.py` creates separate temporary Source, Scratch, and Outside roots with byte fixtures; it never points the stage at operator media.
- **Preview subprocess coverage**: `test_service_rename_preview_runner.py` covers mocked process/error handling and also executes the active corpus through the installed real PowerShell production preview; `test_rename_service.py` uses a mock for service integration. `test_api_path_dialogs.py` mocks the Windows PowerShell dialog process so automated tests do not open an interactive picker.
- **Mocked DOM**: `test_webview_rename_readiness_smoke.py` constructs in-memory mock DOM elements and a minimal `apiPost` spy function.
- **Dynamic fixture state**: `test_webview_browser_rename_smoke.py` calls `_write_fixture_state()` to populate a temporary local API with queue/completed/rename fixture rows.
- **JSONL corpus**: `tests/fixtures/rename/bad_rename_cases.jsonl` stores real bad rename cases. `test_rename_bad_case_corpus.py` gates active cases; `POST /api/rename/filter-cases` and `ops/scripts/operator/Add-RenameFilterCase.ps1` append cases.

---

## Safety Properties And Where They Are Tested

| Safety property | Where tested | Coverage assessment |
|---|---|---|
| Windows file-browser selection stages paths only | `test_application_facade_local_api_rename.py`, `test_api_path_dialogs.py`, `test_webview_browser_rename_smoke` | Covered with injected picker/stubbed route plus dialog-host selection and process-failure coverage; automated smokes do not open the real native dialog |
| `rename.apply` is not called when readiness is Blocked | `test_webview_rename_readiness_smoke`, `test_webview_browser_rename_smoke` | Covered at UI layer (Node VM and real browser) |
| `rename.undo` requires backend manifest authority and strict confirmation | `test_service_rename_apply_runner`, `test_application_facade_local_api_rename.py`, `test_api_command_contracts` | Covered with temp fixtures; source/destination reversal and `confirm_undo` strict boolean rejection are verified |
| Duplicate-destination detection blocks apply | `test_service_rename_planner.py`, `test_webview_rename_readiness_smoke`, `test_webview_browser_rename_smoke` | Covered at service and UI layers; backend planner blocks every colliding row |
| Backend rebuilds plan independently before apply | Implicit in `test_rename_service` (apply path uses planner) | Service-level coverage; no explicit "backend ignores frontend plan" test |
| `confirm_apply` required as literal JSON boolean `true` in API payload | Route contract (`contract_command.py` field list), `test_application_facade_rename.py`, `test_application_facade_local_api_rename.py` | Covered at facade and Local API route layers for absent, false, and non-boolean truthy confirmation values with no rename mutation |
| Dispatcher rename requires literal `confirm_apply`, UUID operation ID, matching dry-run fingerprint, and command/operation journals | `test_stage_contracts.py`, `test_stage_runner.py` | Covered with temporary scratch fixtures; every missing/stale evidence case fails before rename |
| Dispatcher rename is confined to scratch disjoint from protected source roots | `test_stage_runner.py` | Covered for source-root overlap and targets outside scratch; fixture bytes and original names remain unchanged |
| Dispatcher duplicate operation replays its terminal result without a second rename | `test_stage_runner.py` | Covered through an atomic-operation-journal test adapter and destination-byte verification |
| Dispatcher terminal-evidence failure rolls the scratch file back | `test_stage_runner.py` | Covered by injected terminal manifest-write failure; original name and bytes are restored |
| Path casefolding for Windows case-insensitive match | `test_facade_rename_policy.py` | Covered |
| Case-only rename (Windows-safe two-step) | `test_service_rename_apply.py` | Covered |
| Sidecar metadata preserved after rename | `test_service_rename_apply.py` | Covered (error marker preservation, history cap) |
| Media and sidecar apply/undo on disk | `test_service_rename_apply_runner.py`, `test_rename_service.py` | Covered with isolated temporary files, including sidecar metadata backup/restore and multi-episode range identity |
| Rename history capped at 25 entries | `test_service_rename_apply.py` | Covered |
| Natural sort order for file discovery | `test_service_rename_discovery.py`, `test_rename_service.py` | Covered |
| TV season extraction precedence (file > folder) | `test_service_rename_tv.py` | Covered |
| Non-season embedded digits in folder names | `test_service_rename_tv.py` | Covered |
| Revisions, bare anime episodes, multi-episode ranges, ordinal seasons, and specials | `test_service_rename_tv.py`, `test_rename_bad_case_corpus.py`, `Invoke-NamingSupportChecks.ps1`, `Invoke-PipelineQueueEngineChecks.ps1` | Covered across Python prediction, PowerShell destination naming, the bad-case corpus, and Queue dry-run parsing/order |
| Multi-episode semantic overlap blocked in preview and apply | `test_service_rename_planner.py`, `test_service_rename_apply.py` | Covered at planning and defensive pre-mutation layers |
| Active pipeline work blocks rename apply | `test_application_facade_rename.py`, `test_application_facade_local_api_rename.py` | Covered before plan construction and at the Local API, with no mutation |
| Missing-source warning generation | `test_facade_rename_policy.py` | Covered |
| Settings workbench actual result uses production naming authority | `test_application_facade_rename.py`, `test_application_facade_local_api_rename.py`, `test_service_rename_preview.py`, `test_webview_browser_rename_smoke.py` | Covered with a synthetic no-media-probe PowerShell request, exact response correlation, matching requested/applied policy fingerprints, explicit Python-reference parity, and fail-closed unavailable/mismatch states |
| Queue-accepted production filename remains invariant at execution | `Invoke-RunMonitorStateChecks.ps1`, `Invoke-PipelineProcessingPreflightChecks.ps1`, `Invoke-PipelineQueueEngineChecks.ps1`, `Invoke-FailureCodeRegistryChecks.ps1` | Covered for exact accepted workload naming, verified match, missing/tampered accepted evidence, and changed execution plan before probe/scratch/media work; the verified path object is reused by encode/remux/fallback stages, while direct/manual and pre-fingerprint legacy work remain explicitly compatible |

---

## Closed Gaps

### 1. Duplicate-Destination Detection At Service Layer

Closed 2026-05-19. `test_service_rename_planner.py` now creates two source rows that resolve to the same destination and asserts every colliding row is `blocked`, has `change_kind=blocked`, and carries the duplicate-destination error before apply.

### 2. `confirm_apply` Rejection Not Integration-Tested

Closed 2026-05-19 and tightened 2026-06-02. `test_application_facade_local_api_rename.py` now posts `POST /api/rename/apply` with `confirm_apply` absent, explicitly `false`, and non-boolean `"false"`, asserts a `desktop_command_result.v1` warning result, and verifies the source file was not renamed.

### 3. Undo Manifest And On-Disk Sidecar Verification

Closed 2026-06-23 and extended 2026-07-12. `test_service_rename_apply_runner.py` reads a completed undo manifest back, reverses an on-disk media file and sidecar, restores sidecar metadata from manifest backups, blocks unsafe/missing manifest inputs before mutation, and preserves multi-episode range identity through apply and undo.

### 4. Active-Pipeline Apply Guard

Closed. `test_application_facade_rename.py` verifies the backend apply lock and active-work check run before plan construction. `test_application_facade_local_api_rename.py` verifies the Local API reports active PIDs and leaves the source and destination unchanged.

### 5. Rename Workbench / Production Planner Drift

Closed 2026-07-20. The Settings workbench no longer treats the standalone Python cleaner as the production result. It sends synthetic filename/folder context through the PowerShell destination-planning protocol, binds requested and applied cleaning-policy fingerprints, shows the production filename as actual, reports exact Python-reference parity diagnostically, and fails closed when production evidence is unavailable or disagrees. The planner no longer re-cleans authoritative PowerShell leaves in Python. Fingerprinted Backend Queue execution compares its post-override destination against the immutable accepted filename before probe or scratch work and carries that verified output-path object through encode, remux, and fallbacks, so later code/config drift cannot silently change output.

## Known Gaps

### 1. WorkerSourcePathMap Path Rewriting

In coordinator/worker mode, `WorkerSourcePathMap` rewrites source path prefixes when a worker's filesystem paths differ from the coordinator's. The rename service operates on local paths; there is no test that verifies rename planning or apply handles path-rewrite scenarios when paths use coordinator-mapped prefixes.

**Recommendation**: Document this as an open gap. Network-mode rename is considered experimental and the gap is consistent with the broader coordinator/worker testing posture.

---

## What The Rename Tests Do NOT Prove

- FFmpeg or remux behavior — rename tests never launch pipeline processes.
- Subtitle or audio track behavior — rename operates on filenames only, not container tracks.
- Pending publish interaction — rename and pending publish are separate subsystems; no test crosses the boundary.
- Network-mode coordinator path rewrites — see the known gap above.
- Native Windows dialog display in an interactive shell — automated smokes inject/stub `/api/rename/browse` and `test_api_path_dialogs.py` stubs the PowerShell process, so they do not block on a real dialog.
- Representative full-size media behavior — filesystem safety uses minimal temporary files because rename does not inspect container streams.

---

## See Also

- Rename command route: `LOCAL_API_ROUTE_OWNERSHIP_MAP.md` (`POST /api/rename/browse`, `POST /api/rename/preview`, `POST /api/rename/filter-cases`, `POST /api/rename/apply`, `POST /api/rename/undo`)
- Rename apply route contract: `src/mediapipeline/desktop/api/contract_command.py` (`LOCAL_API_RENAME_COMMAND_ROUTE_CONTRACT`)
- WebView smoke catalog: `docs/testing/WEBVIEW_SMOKE_TEST_CATALOG.md`
- Browser smoke runbook: `docs/testing/BROWSER_SMOKE_TEST_RUNBOOK.md`
