# Rename Safety Test Inventory

Purpose: inventory all rename-related test files, describe what each covers and does not cover, identify how fixture data is provided, and note safety-property gaps. This document is observational and does not add new tests.

Total rename test files: 16.
No separate fixture JSON/JSONL files exist — fixture data is generated dynamically in temporary directories or hardcoded as Python dicts within test methods.

---

## Test File Inventory

### WebView / UI Layer

| Test file | Type | What it covers |
|---|---|---|
| `test_webview_rename_readiness_smoke.py` | Node VM (no browser) | Apply Readiness state transitions in mocked DOM; single-row "Ready" scope; duplicate-destination "Blocked" scope; verifies `rename.apply` is not called when blocked |
| `test_webview_browser_rename_smoke.py` | Chrome/Edge CDP | Same logic under real browser rendering; verifies the Browse Files button posts `POST /api/rename/browse` and stages returned paths without apply; renders a TV rename preview row, selects it, validates readiness = Ready; creates duplicate-destination scenario, validates readiness = Blocked; confirms no POST to `/api/rename/apply` |

Both tests share the same fixture shape: a single TV episode row — `Serial Experiments Lain E01 Weird.mkv` → `Serial Experiments Lain - S02E01 - Weird.mkv` — and a duplicate-destination scenario with two rows sharing the same target path.

### Local API Dialog Host Layer

| Test file | Type | What it covers |
|---|---|---|
| `test_api_path_dialogs.py` | Python unittest | Windows PowerShell host selection for the native path picker, encoded-command invocation, selected-path JSON payload parsing, missing-host reporting, and process-failure diagnostics that identify the selected host |

### Facade / Policy Layer

| Test file | Type | What it covers |
|---|---|---|
| `test_facade_rename_policy.py` | Python unittest | Preview count aggregation (total/ready/warning/blocked); confidence/source/change_kind breakdowns; selected-source filtering with path casefolding (Windows/POSIX); missing-source warning generation |
| `test_rename_service.py` | Python unittest | High-level facade integration: movie prediction with natural file sort order; pipeline preview runner integration with mocked subprocess; force-pipeline-name per-row config |

### Service Layer — Name Parsing

| Test file | Type | What it covers |
|---|---|---|
| `test_service_rename_tv.py` | Python unittest | Season extraction from parent folder name; file-embedded season overrides parent folder; `OVA`/specials folder maps to S00; embedded digit sequences in folder names that are NOT season markers |
| `test_service_rename_movie.py` | Python unittest | Movie name cleaning from release filenames (strip release tags, groups, quality markers); per-category disable flags for filter options |
| `test_service_rename_utils.py` | Python unittest | Shared utility functions |

### Service Layer — Planning And Policy

| Test file | Type | What it covers |
|---|---|---|
| `test_service_rename_planner.py` | Python unittest | Rename path planning, operation building from source/destination pairs |
| `test_service_rename_plan_policy.py` | Python unittest | Policy decisions applied during planning (blocker assignment, status derivation) |
| `test_service_rename_discovery.py` | Python unittest | Media file discovery in folders with natural sort order (`Show.10.mkv` after `Show.2.mkv`) |

### Service Layer — Preview And Apply Execution

| Test file | Type | What it covers |
|---|---|---|
| `test_service_rename_preview.py` | Python unittest | Preview generation and pipeline naming integration |
| `test_service_rename_preview_runner.py` | Python unittest | Preview script execution (subprocess mock) and output parsing |
| `test_service_rename_apply_runner.py` | Python unittest | Apply operation execution |
| `test_service_rename_apply.py` | Python unittest | Filesystem apply operations; Windows case-only rename (case-safe path handling); sidecar JSON reading (marks corrupt JSON with error flag); sidecar metadata update after rename (preserves error markers, appends to rename history capped at 25 entries, updates output path fields) |
| `test_service_rename_tv_folder.py` | Python unittest | TV folder structure handling |

---

## Fixture Data Approach

No fixture JSON/JSONL files. All test data is inline:

- **Inline Python dicts**: `test_service_rename_apply.py`, `test_facade_rename_policy.py` hardcode row structures like `{"source": ..., "destination": ..., "status": "ready", ...}` inside test methods.
- **Temporary directories**: `test_rename_service.py` and `test_service_rename_discovery.py` create `tempfile.TemporaryDirectory()` instances and write minimal `.mkv`/sidecar files.
- **Mocked subprocess**: `test_service_rename_preview_runner.py` and `test_rename_service.py` mock subprocess calls for pipeline preview scripts; `test_api_path_dialogs.py` mocks the Windows PowerShell dialog process so automated tests do not open an interactive picker.
- **Mocked DOM**: `test_webview_rename_readiness_smoke.py` constructs in-memory mock DOM elements and a minimal `apiPost` spy function.
- **Dynamic fixture state**: `test_webview_browser_rename_smoke.py` calls `_write_fixture_state()` to populate a temporary local API with queue/completed/rename fixture rows.

---

## Safety Properties And Where They Are Tested

| Safety property | Where tested | Coverage assessment |
|---|---|---|
| Windows file-browser selection stages paths only | `test_application_facade_local_api`, `test_api_path_dialogs.py`, `test_webview_browser_rename_smoke` | Covered with injected picker/stubbed route plus dialog-host selection and process-failure coverage; automated smokes do not open the real native dialog |
| `rename.apply` is not called when readiness is Blocked | `test_webview_rename_readiness_smoke`, `test_webview_browser_rename_smoke` | Covered at UI layer (Node VM and real browser) |
| Duplicate-destination detection blocks apply | `test_service_rename_planner.py`, `test_webview_rename_readiness_smoke`, `test_webview_browser_rename_smoke` | Covered at service and UI layers; backend planner blocks every colliding row |
| Backend rebuilds plan independently before apply | Implicit in `test_rename_service` (apply path uses planner) | Service-level coverage; no explicit "backend ignores frontend plan" test |
| `confirm_apply` required as literal JSON boolean `true` in API payload | Route contract (`contract_command.py` field list), `test_application_facade_rename.py`, `test_application_facade_local_api.py` | Covered at facade and Local API route layers for absent, false, and non-boolean truthy confirmation values with no rename mutation |
| Path casefolding for Windows case-insensitive match | `test_facade_rename_policy.py` | Covered |
| Case-only rename (Windows-safe two-step) | `test_service_rename_apply.py` | Covered |
| Sidecar metadata preserved after rename | `test_service_rename_apply.py` | Covered (error marker preservation, history cap) |
| Rename history capped at 25 entries | `test_service_rename_apply.py` | Covered |
| Natural sort order for file discovery | `test_service_rename_discovery.py`, `test_rename_service.py` | Covered |
| TV season extraction precedence (file > folder) | `test_service_rename_tv.py` | Covered |
| Non-season embedded digits in folder names | `test_service_rename_tv.py` | Covered |
| Missing-source warning generation | `test_facade_rename_policy.py` | Covered |

---

## Closed Gaps

### 1. Duplicate-Destination Detection At Service Layer

Closed 2026-05-19. `test_service_rename_planner.py` now creates two source rows that resolve to the same destination and asserts every colliding row is `blocked`, has `change_kind=blocked`, and carries the duplicate-destination error before apply.

### 2. `confirm_apply` Rejection Not Integration-Tested

Closed 2026-05-19 and tightened 2026-06-02. `test_application_facade_local_api.py` now posts `POST /api/rename/apply` with `confirm_apply` absent, explicitly `false`, and non-boolean `"false"`, asserts a `desktop_command_result.v1` warning result, and verifies the source file was not renamed.

## Known Gaps

### 1. WorkerSourcePathMap Path Rewriting

In coordinator/worker mode, `WorkerSourcePathMap` rewrites source path prefixes when a worker's filesystem paths differ from the coordinator's. The rename service operates on local paths; there is no test that verifies rename planning or apply handles path-rewrite scenarios when paths use coordinator-mapped prefixes.

**Recommendation**: Document this as an open gap. Network-mode rename is considered experimental and the gap is consistent with the broader coordinator/worker testing posture.

### 2. Undo Manifest Verification

The apply service writes an undo manifest (RENAME_TOOL_SIDECAR_SCHEMA_VERSION) alongside renames. There is no test that reads the undo manifest back and confirms it can be used to reverse a rename batch. The existence of the manifest is implied by the sidecar metadata tests but undo-path correctness is not exercised.

### 3. No Real Filesystem Rename In CI Path

All CI-safe tests use temporary directories with minimal files. No test exercises a rename on a media file with an actual sidecar `.json` pair present on disk and verifies both the main file and the sidecar were renamed consistently. The sidecar metadata update is tested in isolation.

---

## What The Rename Tests Do NOT Prove

- FFmpeg or remux behavior — rename tests never launch pipeline processes.
- Subtitle or audio track behavior — rename operates on filenames only, not container tracks.
- Pending publish interaction — rename and pending publish are separate subsystems; no test crosses the boundary.
- Network-mode coordinator path rewrites — see gap 3 above.
- Native Windows dialog display in an interactive shell — automated smokes inject/stub `/api/rename/browse` and `test_api_path_dialogs.py` stubs the PowerShell process, so they do not block on a real dialog.
- Undo reversal correctness — see gap 4 above.
- Rename under active pipeline lock — no test verifies that rename.apply is correctly blocked or serialized when the pipeline is actively encoding the same file.

---

## See Also

- Rename command route: `LOCAL_API_ROUTE_OWNERSHIP_MAP.md` (`POST /api/rename/browse`, `POST /api/rename/preview`, `POST /api/rename/apply`)
- Rename apply route contract: `DesktopApp/mediapipeline_desktop_app/api/contract_command.py` (`LOCAL_API_RENAME_COMMAND_ROUTE_CONTRACT`)
- WebView smoke catalog: `WEBVIEW_SMOKE_TEST_CATALOG.md`
- Browser smoke runbook: `BROWSER_SMOKE_TEST_RUNBOOK.md`
