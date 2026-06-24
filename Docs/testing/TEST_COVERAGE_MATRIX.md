# Test Coverage Matrix

Date: 2026-05-20

Maps all 13 WebView pages to their available test coverage: Python backend unit tests, non-browser WebView smokes, browser-backed WebView smokes, and identified gaps. Does not include manual test coverage (see `docs/operator/WEBVIEW_MANUAL_OPERATOR_TEST_SCRIPT.md`).

All-surface rationalization: `docs/ai-audits/2026-06-18-test-coverage-rationalization.md` records a 2026-06-18 live-worktree pass over Python tests, WebView tests, browser/non-browser smokes, PowerShell checks, smoke wrappers, and `ops/scripts/release/test.ps1`. It classifies the suite by proof tier and subsystem, flags overlap candidates, and recommends consolidation sequencing. Its default safety rule is that static/browser, Python/PowerShell, and wrapper/module pairs should not be removed merely because names overlap; they often prove different rungs.

Generated drift aids: `docs/generated/SMOKE_WRAPPER_MAP.json` is the machine-readable smoke-wrapper map checked against smoke docs and the release layout gate, while `docs/generated/DUPLICATE_TEST_NAMES.md` lists exact duplicate Python test names as consolidation review candidates only. Treat `docs/ai-audits/2026-06-17-test-coverage-gap-analysis.md` as the missing-coverage backlog and the rationalization report as the consolidation layer.

---

## Coverage Tiers

| Tier | What it verifies | What it does not verify |
|---|---|---|
| **Python unit tests** (`tests/python/desktop/test_*.py`) | Backend logic, service contracts, schema validation, route handler policies, route inventory drift checks, WebView DOM/global inventory drift checks, CSS design-token regression checks, WebView command-route ownership and frontend mutation-boundary static checks | WebView rendering, UI state, operator-facing text |
| **Non-browser smokes** (`Test-WebView*.ps1` plus browser-free `Test-LocalApi*.ps1` route smokes where noted) | Backend-served JS evaluated with mocked DOM; contract rendering, text content, route calls; selected Local API route contracts | Real browser rendering, interactive clicks, CSS layout; real media processing |
| **Browser-backed smokes** (`Test-WebViewBrowser*.ps1`, Chrome/Edge) | Real browser render, interactive clicks, filter behavior, mutation-boundary enforcement, hash-based no-mutation assertions for temporary media/sidecar/manifest fixture artifacts | Real media processing, actual pipeline launch, live state changes |
| **No coverage** | — | Gap: neither unit tests nor smokes exercise the behavior |

`test_tauri_shell_scaffold.py` includes a static reliability-wrapper gate. It verifies `ops\pipeline\tests\Invoke-ReliabilityRegressionChecks.ps1` defaults to active current WebView/backend checks while archived legacy desktop-shell checks stay under `ops\pipeline\tests\Legacy` behind `-RunLegacyDesktopChecks`. This does not open a UI window or run media processing.

`test_tauri_shell_scaffold.py` includes the Tauri/WebView2 shell static gate. It verifies the shell launches the Python Local API rather than the pipeline directly, validates health/contract/WebView assets before opening, uses backend close-readiness before shutdown, starts a bounded backend lifecycle monitor after setup, and rejects a second Tauri shell instance through a per-user Windows mutex before backend startup. The monitor and UI wiring checks cover `mediapipeline://backend-lifecycle` events, five-second health polling, two-failure thresholding, backend process-exit detection, the read-only WebView lifecycle bridge/banner, and no media-policy or frontend-owned mutation logic in the shell. `apps\desktop\tauri\Test-TauriShell-ProductionSurface.ps1` adds the focused production-surface audit for dynamic main-window creation, no static production devtools flags, no token-adjacent runtime logging, the single-instance guard, and the event-only lifecycle bridge posture.

---

## Cross-Page Command Boundary Coverage

`test_webview_frontend_mutation_boundary.py` is a static Python gate over backend-served WebView assets. It verifies every WebView `apiPost(...)` call uses a literal documented POST route, command calls stay in the expected owning JS module, shell-open routes submit backend selector keys (`row_key`/`target`) instead of raw path keys, write routes keep explicit confirmation payloads, only `apiClient.js` owns `fetch(...)`, frontend assets do not use direct filesystem/process/Tauri shell APIs, frontend media-policy risk helpers remain labelled advisory-only, and WebView repair/reconcile controls submit only bounded backend route intent for selected Pending manifest repair plus selected Completed manifest/sidecar repair. Network lifecycle/setup controls are separately pinned by `test_webview_network_read_only_boundary.py`: the Network page may call only documented backend-owned lifecycle dry-run/start/stop, worker test-connection, discovery, join-blob, and join-import routes, with no frontend-owned lifecycle, claim, done-report, queue, settings-save, publish, rename, or media mutation implementation. The only direct `window.__TAURI__` access allowed in WebView assets is `tauriLifecycleBridge.js`, and that bridge is checked as an event listener/re-dispatcher only: no `apiPost`, `fetch`, invoke, shell, process, filesystem, open, write, remove, or mutation command surface. This test does not render UI, run media, open files, or prove backend command behavior; it prevents frontend-owned mutation drift before browser or Local API smokes run.

`test_webview_command_boundary_audit.py` pins the generated `docs/generated/WEBVIEW_COMMAND_BOUNDARY_AUDIT.json` report from `ops/scripts/dev/check-webview-command-boundary.mjs`. The report classifies every action-like WebView control, verifies literal or contract-derived API dispatch, checks routes against `LOCAL_API_ROUTE_CONTRACT`, enforces owning-page/helper route effects, requires confirmation evidence for mutation routes, keeps shell-open payloads selector-key based, and preserves the single allowed dynamic dispatch path for backend-contract Network lifecycle routes. This is a static/generated guard only; backend command behavior and real browser no-mutation evidence still come from the Local API and WebView smoke tiers.

---

## Docs and Repo Hygiene Guards

| Guard | What it verifies |
|---|---|
| `ops/pipeline/tests/Unit/Invoke-ActiveDocsReferenceChecks.ps1` | Non-archive active docs do not reference the old root paths for moved source-of-truth docs such as API routes, DOM/global inventories, smoke runbooks, parity matrix, operator guides, and archived audits. It also verifies the mapped current targets exist, blocks root-level references to superseded housekeeping report names unless they point at `docs/archive/admin-audits`, prevents high-level status/checklist docs from embedding absolute local current-handoff paths, and blocks current active docs from reintroducing the removed desktop-shell framework by its old UI name. |
| `tests/tooling/*.py` | Python-side tooling guards cover active-doc reference detection, AI guardrail check-plan contents, dependency-boundary cycle/allowlist handling, god-file thresholds, lifecycle-map rendering, naming-lint creation parsing, risky-file registry validation/classification, summary/project-index orphan detection, and change-control release-manifest/version error paths. |
| `ops/pipeline/tests/Unit/Invoke-RepoHygieneChecks.ps1` | Generated root log/jsonl captures, DesktopApp root `local_api_*`/`_codex_*` validation captures, and rebuildable `.pytest_cache` are absent from source locations; required ignore entries remain present. Strict Tauri dependency/build artifact scanning is opt-in with `-IncludeBuildArtifacts` so normal Cargo/Tauri validation output does not stale-fail the default reliability gate. |
| `ops/pipeline/tests/Unit/Invoke-RuntimeStateHygieneChecks.ps1` | Completed analytics encode-speed history stays under `LocalBase\State\App`, the legacy app-root file is absent, and inventory/ignore/test coverage remain in sync. |
| `ops/pipeline/tests/Unit/Invoke-PortablePathChecks.ps1` | Active audit and legacy GUI scripts do not reintroduce local operator UNC audit defaults. |
| `tests/python/desktop/test_config_keys.py` | Python config-key constants cover the settings schema, network defaults, PowerShell ordered pipeline config keys, source-safety keys, Network runtime raw-lookup drift, settings/media-policy raw-lookup drift, and package-wide registered-key lookup drift so future typo-prone config work has a single checked registry. |
| `ops/pipeline/tests/Unit/Invoke-ConfigKeyRegistryChecks.ps1` | PowerShell config-key constants align with `ConfigSchema.ps1`, template/live PSD1 keys are known, helper lookups fail closed, and PowerShell `$config[...]` / `Get-Config*` call sites do not reference unknown config keys. |
| `ops/pipeline/tests/Unit/Invoke-ContractSchemaChecks.ps1` | Pipeline JSON schemas remain present with the expected draft/id metadata, and representative event/result/queue/pending-publish/completed-job/publish-result/folder-topology payloads round-trip without shape drift. |
| `ops/pipeline/tests/Unit/Invoke-FailureCodeRegistryChecks.ps1` | `FailureCodes.ps1` classifier return codes stay registered, broader pipeline outcome/error codes emitted by PowerShell surfaces stay known, metadata rows are unique and complete for family/stage/when-fires/retryability/operator severity/handler/operator action, representative high-risk metadata stays accurate, and lookup helpers reject unknown codes. |
| `ops/pipeline/tests/Unit/Invoke-ReleasePackagePolicyChecks.ps1` | Release package exclusion policy keeps rebuildable/vendor/runtime/local-state/personal-config paths out of default packages, release hygiene rule counts stay aligned with the policy manifest, and the pre-overhaul backup flow delegates release copy creation to the canonical builder. |
| `ops/scripts/ops/release/metadata/test.ps1` | Release self-test gates bundle layout, release-manifest hygiene, WebView include/asset references, API browser token posture, PowerShell parser checks, Python syntax, desktop unit discovery, environment verification, Tauri prereqs, and current reliability/tool/e2e regression wrappers. |

`test_webview_inventory_docs.py` guards three frontend inventories: rendered DOM IDs, generated WebView global-export manifests, and namespace object boundary comments. The namespace guard requires every future `window.mediaPipeline* = { ... }` namespace object to have adjacent `Public namespace` JSDoc that tells new code to prefer namespace access and labels flat `window.*` exports as transitional compatibility aliases when present.

`test_application_facade_local_api.py`, `test_webview_css_design_tokens.py`, and `test_webview_browser_layout_manager_smoke.py` now also guard the WebView layout-manager fixes from 2026-05-20 plus the Layout Editor drawer behavior: schema-changed stored panel order must reset to authored default order while preserving per-panel state, advanced-gated panel drag attempts must expose a transient local hint, the hint styling must remain in the split layout-manager stylesheet rather than drifting back into the parent stylesheet, and real-browser coverage must prove representative page tabs, subtabs, and generated subsections are managed from the drawer instead of exposed inline together.

`test_application_facade_web_static.py` pins the transitional `window.diagnosticsBridgeActions` compatibility alias in `diagnosticsBridge.js` and derives the currently consumed legacy diagnostics bridge helper names from the WebView assets, then verifies each one still has a matching flat export while namespace-first cleanup remains opportunistic. This prevents the live refresh regression where Reports rendering can fail with `diagnosticsBridgeActions is not defined`.

`test_application_facade_web_static.py`, `test_controllers_queue.py`, `test_controllers_completed.py`, and `test_controllers_rerun.py` now also guard the 2026-05-20 UI-improvement backlog closure. Static WebView coverage pins state-aware Launch controls, hidden-until-active emergency Force Stop posture, destructive/long-running action tooltips, telemetry render failure diagnostics, status-chip keyboard/tooltip behavior, and structured backend error routing. Service/facade coverage pins backend scan-detail progress text, Completed refresh/backfill busy-state disabling, and CSV rerun failure root-cause action history.

`test_phase4_storage_observability.py` now also guards the Phase 4 observability contract. It verifies JSON-line logging keeps the required envelope fields authoritative when structured context contains colliding keys, redacts secret-keyed context, serializes exception details, and avoids duplicate evidence lines when JSON logging is configured repeatedly for the same logger/stream.

`test_webview_css_design_tokens.py` now also guards the 2026-05-29 UX-011 design-system cleanup. It verifies the split CSS bundle keeps radius/status tokens defined before use, default danger buttons remain outlined while emergency buttons keep stronger red emphasis, status chips include a non-color shape cue, dense workflow table padding stays tokenized, Launch Audit/CSV Rerun buttons are primary actions instead of destructive-styled controls, and pipeline-control confirmation copy continues to describe source-media safety.

`test_service_status_active_jobs.py`, `test_application_facade_snapshot.py`, `test_application_facade_local_api.py`, and `test_application_facade_web_static.py` now also guard the 2026-05-29 UX-012 worker progress telemetry contract. They verify `desktop_worker_progress.v1` is built from existing ActiveJobs, `pipeline_progress.json`, and bounded log-tail evidence, remains read-only, appears in `/api/snapshot` and `/api/diagnostics`, and is consumed by Home/Diagnostics progress rendering without adding new routes, process controls, ETA, FFmpeg frame metrics, GPU/NVENC inference, retry state, or validation proof.

`test_service_status_ffmpeg_progress.py`, `test_application_facade_snapshot.py`, `test_application_facade_local_api.py`, and `test_application_facade_web_static.py` now also guard the 2026-05-29 UX-013 FFmpeg progress proof contract. They verify `desktop_ffmpeg_progress.v1` parses bounded FFmpeg console/progress-block key/value evidence without merging older block fields into newer partial blocks, remains read-only, reports an explicit parse-error row for active encode/remux evidence without parseable FFmpeg fields, appears in `/api/snapshot` and `/api/diagnostics`, and is consumed by Progress Proof/Diagnostics Runtime Progress without adding routes, controls, ETA, GPU/NVENC inference, retry state, validation proof, or output-integrity claims.

`test_telemetry_service.py`, `test_application_facade_snapshot.py`, `test_application_facade_local_api.py`, and `test_application_facade_web_static.py` now also guard the 2026-05-29 UX-014 GPU/NVENC usage telemetry contract. They verify `desktop_gpu_encoder_usage.v1` is built from the cached telemetry sample, keeps encoder sessions explicit as missing when the current sampler does not report them, remains read-only, appears in `/api/telemetry`, and is consumed by Telemetry readiness copy without adding routes, controls, ETA, retry state, validation proof, encoder-policy changes, or process-control behavior.

`test_service_status_eta.py`, `test_application_facade_snapshot.py`, `test_application_facade_local_api.py`, and `test_application_facade_web_static.py` now also guard the 2026-05-29 UX-015 ETA telemetry contract. They verify `desktop_eta.v1` estimates only from active `desktop_worker_progress.v1` percent plus elapsed-time evidence, reports explicit unavailable reasons instead of faking ETA when evidence is missing, remains read-only, appears in `/api/snapshot` and `/api/diagnostics`, and is consumed by Home Current Run, Progress Proof, and Diagnostics Runtime Progress without adding routes, controls, retry state, validation proof, output-integrity claims, or process-control behavior.

`test_service_failure_retry_state.py`, `test_facade_failures_policy.py`, `test_application_facade_reports.py`, `test_application_facade_local_api.py`, `test_application_facade_web_static.py`, and `test_webview_browser_maintenance_reports_smoke.py` now also guard the 2026-05-29 UX-016 retry state contract. They verify `desktop_retry_state.v1` is built from existing failure JSON rows and failure marker evidence, keeps transient retry as a backend next-queue-pass state, marks operator-required/permanent/exhausted rows blocked, remains read-only, appears inside `/api/failures`, and is consumed by Reports > Failures without adding routes, retry buttons, marker-clear behavior changes, process controls, validation proof, or media/source/output mutation.

`test_service_completed_validation_state.py`, `test_facade_completed_policy.py`, `test_application_facade_completed.py`, `test_application_facade_local_api.py`, `test_application_facade_web_static.py`, and `test_webview_row_detail_smoke.py` now also guard the 2026-05-29 UX-017 validation state contract. They verify `desktop_validation_state.v1` is built from existing completed-row output path/existence/health/size evidence, reports probe/hash/playback proof as unavailable until backend evidence exists, blocks missing/failed output proof, remains read-only, appears inside `/api/completed`, and is consumed by Completed checklist/detail plus the Sample Validation completed-evidence handoff without adding routes, ffprobe/hash execution, playback acceptance, repair/rerun controls, or media/source/output mutation.

The first Python service-runner Protocol cleanup is covered by the existing path/config/audit-rerun runner tests plus compile checks: `test_service_path_resolution_runner.py`, `test_service_config_document_runner.py`, `test_service_config_save_runner.py`, `test_config_keys.py`, `test_service_config_preview.py`, and `test_application_facade_settings_workspace.py`. These tests prove the typed path/config helper boundaries still load config, preserve state-root layout, validate/save configs, and assemble settings workspace evidence; they do not provide static type checking for every remaining `Any`.

The process lifecycle Protocol cleanup is covered by `test_service_process_control_runner.py`, `test_service_process_active_job_runner.py`, `test_service_process_launch_runner.py`, `test_service_process_runtime_runner.py`, `test_service_process_spawn_runner.py`, `test_application_facade_process_launch.py`, `test_application_facade_process_control.py`, and `test_application_facade_close_readiness.py`. These tests prove the typed process runner boundaries still handle control flags, ActiveJobs records, launch plans, spawn/readiness cleanup, runtime artifact cleanup, duplicate-launch rejection, command control, and close-readiness evidence. They do not launch real media processing.

The queue/rename/status Protocol cleanup is covered by `test_service_queue_preview_builder.py`, `test_service_queue_dry_run_runner.py`, `test_service_rename_preview_runner.py`, `test_service_rename_planner.py`, `test_service_rename_apply_runner.py`, `test_service_status_snapshot_runner.py`, `test_service_status_readers.py`, `test_service_status_errors.py`, `test_application_facade_queue.py`, `test_application_facade_rename.py`, and `test_application_facade_snapshot.py`. These tests prove the typed helper boundaries still build queue previews, run dry-run promotion/cached fallback, load naming previews, plan/apply rename operations, read status artifacts, build snapshots, and assemble queue/rename/snapshot facade evidence.

The low-level process logger cleanup is covered by `test_service_process_active_jobs.py`, `test_service_process_control_flags.py`, `test_service_process_kill.py`, `test_service_process_launch_cleanup.py`, `test_service_process_readiness.py`, `test_service_process_control_runner.py`, `test_service_process_active_job_runner.py`, `test_service_process_spawn_runner.py`, `test_application_facade_process_launch.py`, and `test_application_facade_close_readiness.py`. These tests prove logger contract annotation changes preserve ActiveJobs, control-flag reads, process-kill logging, stale-progress cleanup, spawn readiness, launch cleanup, and close-readiness behavior.

The Network runtime config-key migration is covered by `test_config_keys.py`, `test_network_worker_source_policy.py`, and the `test_network*.py` discovery set. The static guard blocks raw `.get("...")` lookups for high-risk Network and encode snapshot keys, while the Network tests preserve coordinator/worker policy coercion, auth, source mapping, poll interval handling, worker state, crash recovery, and read-only facade behavior.

The settings/media-policy config-key migration is covered by `test_config_keys.py`, `test*config*.py`, `test*settings*.py`, `test_sample_validation_api.py`, `test_facade_settings_policy.py`, `test_facade_process_audit_policy.py`, `test_facade_completed_policy.py`, `test_controllers_telemetry.py`, `test_controllers_home.py`, `test_service_path_layout.py`, `test_application_facade_settings_workspace.py`, `test_application_facade_local_api.py`, and `test_webview_real_media_smoke.py`. These tests prove the migrated constants preserve backend-authored settings readiness, BDPGS OCR path evidence, sample-validation policy alignment, telemetry encoder display, completed/audit outsource-root selection, valid-extension fallback, split WebView asset checks, and settings browser smoke assertions.

The final config-key sweep is covered by `test_config_keys.py`, the WebView settings live/patch smoke tests, `test_sample_validation_api.py`, `test*config*.py`, `test*settings*.py`, and the Local API/WebView real-media/inventory batch. The package-wide static guard blocks raw registered-key `.get(...)`, `values[...]`, and helper-value access across `mediapipeline.desktop`; legacy sample-validation aliases remain local compatibility constants and are not current config registry keys.

The Python application public API boundary is covered by `test_application_public_api.py`. It verifies `mediapipeline.desktop.application.__all__` remains explicit and importable, every application facade/DTO boundary module declares a literal unique `__all__`, each defined public symbol is listed, and each declared export resolves. This is a boundary guard only; it does not exercise route behavior or media processing.

---

## Freshness Review - 2026-05-20 (Layout Manager Edge Cases)

WebView layout customization coverage now includes the two deferred layout-manager edge cases that were still on the open-work checklist plus the Layout Editor drawer regression. Static Local API coverage verifies the served `app.js` keeps the stored-order schema-reset path, preserves the comment that newly added panels must appear at their authored default position, and exposes the advanced-gated drag hint text. CSS coverage verifies the hint selectors and drawer selectors remain in `styles.layout-manager.css`. Browser coverage verifies the drawer lists representative page tabs, subtabs, and generated subsections while inactive subtabs remain hidden inline.

```
Task ID: Layout manager edge cases
Files inspected: apps/desktop/webview/static/assets/app.js; apps/desktop/webview/static/assets/styles.layout-manager.css; tests/python/desktop/test_application_facade_local_api.py; tests/python/desktop/test_webview_css_design_tokens.py; tests/python/desktop/test_webview_browser_layout_manager_smoke.py; archived reconciliation evidence; docs/REMEDIATION_CHANGELOG.md
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: node --check apps/desktop/webview/static/assets/app.js; apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_application_facade_local_api.LocalApiServerTests.test_local_api_serves_read_only_web_prototype tests.webview.test_webview_css_design_tokens tests.webview.test_webview_inventory_docs tests.webview.test_webview_browser_layout_manager_smoke -q; powershell -NoProfile -ExecutionPolicy Bypass -File .\ops\pipeline\tests\Unit\Invoke-ActiveDocsReferenceChecks.ps1
Findings: Focused static coverage now pins schema-change order reset, transient advanced-gated drag guidance, split layout-manager stylesheet ownership, and inventory-doc drift checks. Browser coverage now proves representative generated tab/subtab/subsection boxes get customize bars and draggable handles. Real operator personalization persistence remains outside this rung.
Open questions: None.
Risk: Low - WebView local layout-state behavior only; no Local API route, backend command contract, media policy, source/scratch/output media handling, settings save, launch scope, publish/drain, rename, Tauri lifecycle, or removed desktop-shell fallback behavior changed.
```

## Freshness Review - 2026-05-20 (UI Improvement Backlog Closure)

The active 23-item UI-improvement checklist is now closed. Coverage focuses on operator-safety polish rather than backend behavior changes: Launch command controls are state-aware from backend snapshot/close-readiness, the emergency topbar Force Stop stays hidden until active backend work is reported, long-running/destructive controls carry explanatory tooltips, telemetry renderer failures become local command-history diagnostics, structured error reports stay routed through shared status/command-history surfaces, Queue refresh progress can display backend scan detail, Completed refresh/backfill buttons are disabled while busy, and failed CSV rerun exits record the first root-cause tail line.

```
Task ID: UI improvement backlog closure
Files inspected: apps/desktop/webview/static/assets/app.js; launchView.js; telemetryView.js; domHelpers.js; styles.layout.css; styles.controls.css; backend queue/completed/rerun/rename service and facade tests; archived reconciliation evidence; docs/REMEDIATION_CHANGELOG.md
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: node --check app.js launchView.js telemetryView.js domHelpers.js; apps\desktop\runtime\Python\python.exe -m py_compile queue_refresh_controller.py completed_controller.py completed_actions_controller.py rerun_controller.py rename_controller.py network_tab.py; apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_application_facade_web_static tests.webview.test_webview_css_design_tokens tests.python.desktop.test_controllers_queue tests.python.desktop.test_controllers_completed tests.python.desktop.test_controllers_rerun -q
Findings: Focused static/controller tests now pin state-aware command surface, tooltip/error/telemetry guards, backend scan-detail status text, Completed busy-state disabling, and CSV rerun root-cause action history. Browser click coverage for every destructive confirmation remains outside this static rung.
Open questions: None.
Risk: Low to medium - UI/control-state polish only; no Local API route, backend media policy, source/scratch/output media handling, settings save, rename apply, pending publish drain semantics, Tauri lifecycle, or external rollback behavior changed.
```

## Coverage By Page

### Home

**Module**: `crossPageContextView.js`, `crossPageContextView.conflict.js`, `crossPageContextView.sample.js`, `crossPageContextView.settings.js`, `crossPageContextView.sampleValidation.js`
**API routes**: `GET /api/snapshot`, `GET /api/telemetry`, `GET /api/sample-validation`, `GET /api/commands`

| Coverage type | Files / Wrappers |
|---|---|
| Python unit tests | `test_facade_status_policy.py`, `test_service_status_progress.py`, `test_sample_validation_api.py`, `test_service_status_events.py`, `test_service_status_summary.py`, `test_application_facade_snapshot.py` (facade snapshot assembly, progress bar shaping, active-job diagnostics rows, and zero-percent GPU telemetry presence), `test_application_facade_web_static.py` (Dashboard command-surface boundary, panel evidence read-only static checks, and canonical rendered page H1 titles) |
| Non-browser smokes | `Test-WebViewCommandEvidenceSmoke.ps1` (cross-page command history, drain guard command evidence), `Test-WebViewRealMediaEvidenceSmoke.ps1` (real-media evidence panel, settings-launch policy handoff display, sample-validation pilot-plan/checklist/worksheet payload), `Test-LocalApiSampleValidationContractSmoke.ps1` (sample-validation preview/append/read/tail contracts, current-backend-evidence preview, temp-only validation-log write) |
| Browser-backed smokes | `Test-WebViewBrowserHighRiskSmoke.ps1` (blocked/warning row guidance), `Test-WebViewBrowserDiagnosticsHandoffSmoke.ps1` (row selection and combined row review plans across tables), `Test-WebViewBrowserSampleValidationSmoke.ps1` (Home Sample Validation pilot checkpoint/attention plan, real-media validation audit roll-up, policy-alignment roll-up, Completed saved-policy reconciliation handoff, operator sample execution checklist detail, generated worksheet table and selected-sample match detail, Real-Media Validation Worksheet sample-validation posture, manual checklist preview payload, preview-only current-evidence and pilot-evidence-packet rendering, and append-readiness/manual-check gap rendering), `Test-WebViewBrowserHomeLiveStateSmoke.ps1` (Daily-Driver Checklist, Operator Readiness, Active Work, Live Progress Details/Evidence, Diagnostics runtime progress, Command Results, Sample Validation posture, generated worksheet readback, Real-Media Validation Worksheet handoff, and page-switch viewport reset), `Test-WebViewBrowserLaunchQueueReadinessSmoke.ps1` (close-readiness chip, launch command ownership evidence, Launch Start Decision Summary, Launch Real-Media Sample Proof Handoff, selected-sample worksheet and validation-record evidence, and Launch Sample Execution Checklist mirroring Home worksheet/sample-validation evidence used by launch-readiness handoff) |

**Gaps**: Home now has browser coverage for Sample Validation/pilot-plan preview, real-media validation audit roll-up, policy-alignment roll-up, operator sample execution checklist detail, generated worksheet rendering and selected-sample matching, manual checklist preview payloads, pilot-evidence-packet rendering, append-readiness/manual-check gap rendering, its Real-Media Validation Worksheet posture handoff, and live-state Daily-Driver Checklist rendering. Sample-validation preview and Home live-state coverage still do not prove real FFmpeg output quality.

---

### Live / Progress

**Module**: `progressView.js`, `telemetryView.js`
**API routes**: `GET /api/snapshot`, `GET /api/telemetry`

| Coverage type | Files / Wrappers |
|---|---|
| Python unit tests | `test_service_status_progress.py`, `test_service_status_events.py`, `test_service_process_runtime_artifacts.py`, `test_telemetry_service.py`, `test_application_facade_snapshot.py` (publish/audit/subtitle/copy progress bar presentation and zero-percent GPU mapping) |
| Non-browser smokes | None directly |
| Browser-backed smokes | `Test-WebViewBrowserTelemetrySmoke.ps1` (GPU/CPU detail rows, zero-percent NVENC display without duplicate idle wording, CPU/RAM-only fallback), `Test-WebViewBrowserHomeLiveStateSmoke.ps1` (Live Progress Details percent/current-item/route rows, Progress Evidence selected Current Item and ActiveJobs rows, Diagnostics runtime progress summary), `Test-WebViewBrowserDiagnosticsHandoffSmoke.ps1` (stale runtime-progress guidance under Diagnostics) |

**Gaps**: Stale-progress timing threshold calculation remains unit-level/service-policy coverage; browser coverage now proves the operator-facing stale-progress guidance renders from backend snapshot activity.

---

### Queue

**Module**: `queueView.js`
**API routes**: `GET /api/queue`, `GET/POST /api/queue/priority`, `GET/POST /api/queue/strategy`, `GET/POST /api/queue/file-overrides`, `POST /api/queue/file-overrides/route-preview`, `POST /api/queue/file-overrides/series-preview`, `POST /api/queue/file-overrides/series-apply`, `POST /api/queue/open`

| Coverage type | Files / Wrappers |
|---|---|
| Python unit tests | `test_facade_queue_policy.py`, `test_service_queue_snapshot.py`, `test_service_queue_preview_builder.py`, `test_service_queue_dry_run.py`, `test_service_queue_dry_run_runner.py`, `test_application_facade_queue.py` (facade queue preview snapshot-read behavior, stale evidence, blocked-vs-excluded rows, runtime outcome correlation, and row-key open allowlists), `test_application_facade_local_api.py` (queue state route contract, source-root scope, and command history), `test_api_contract_payload.py` (route effect schema, effectful POST command-result history contract, and CSV rerun copy/keep/park contract defaults) |
| Non-browser smokes | `Test-WebViewRowDetailSmoke.ps1` (Queue row detail, combined review plan, adversarial blocked rows, diagnostics handoff text), `Test-WebViewRealMediaEvidenceSmoke.ps1` (Queue evidence rows) |
| Browser-backed smokes | `Test-WebViewBrowserHighRiskSmoke.ps1` (blocked row risk signals), `Test-WebViewBrowserDiagnosticsHandoffSmoke.ps1` (row click, combined review plan, filter warnings, clear-filter buttons), `Test-WebViewBrowserLargeTableSmoke.ps1` (250/260 render cap, filter scope evidence, Launch Decision daily-use handoff/filter evidence, Backend Launch Scope Preview boundary, selected-row at-a-glance summary), `Test-WebViewBrowserLaunchQueueReadinessSmoke.ps1` (Queue Launch Decision, Queue Backend Launch Scope Preview, Launch Scope Reconciliation, Launch Start Decision Summary, Launch Real-Media Sample Proof Handoff, and Launch Sample Execution Checklist populated from backend queue state, cached backend Launch preflight, command history, schedule/close-readiness evidence, Home worksheet evidence, and Home sample-validation execution guidance) |

**Gaps**: Source-open shell operations (`POST /api/queue/open`) verified by unit tests (`test_service_file_open.py`) but not by any smoke; priority marker display remains not browser-smoke-tested. Queue priority/strategy/file-override route contracts, source-scope rejection, and command journaling are covered by Local API unit tests.

**Pipeline regression coverage**: Queue-plan legacy priority compatibility, ordered queue schema keys, and local worker-slot queue-engine dispatch/fail-closed behavior are covered by the current compatibility wrapper at `ops/pipeline/tests/Invoke-ReliabilityRegressionChecks.ps1`, `ops/pipeline/tests/Invoke-EndToEndSmokeChecks.ps1`, `ops/pipeline/tests/Unit/Invoke-ContractSchemaChecks.ps1`, and `ops/pipeline/tests/Unit/Invoke-PipelineQueueEngineChecks.ps1`.

---

### Completed

**Module**: `completedView.js`, `completedView.evidence.js`, `completedView.proof.js`, `completedView.review.js`, `completedView.diagnostics.js`
**API routes**: `GET /api/completed`, `GET /api/publish-reconciliation`, `POST /api/completed/open`

| Coverage type | Files / Wrappers |
|---|---|
| Python unit tests | `test_service_completed_validation_state.py` (read-only validation-state contract), `test_facade_completed_policy.py`, `test_service_completed_manifest.py`, `test_service_completed_backfill.py`, `test_facade_completed_open_policy.py`, `test_application_facade_completed.py` (facade completed preview evidence, validation-state payload, size/runtime/missing-output classification, completed-open row-key allowlists, and completed-manifest backfill dry-run behavior), `test_application_facade_web_static.py` (backend-served Completed asset availability/load-order, validation-state checklist/proof copy, and split evidence/proof/diagnostics compatibility hooks) |
| Non-browser smokes | `Test-WebViewRowDetailSmoke.ps1` (Completed row detail, combined review plan, broken rows, diagnostics handoff), `Test-WebViewRealMediaEvidenceSmoke.ps1` (route-reason evidence, output proof) |
| Browser-backed smokes | `Test-WebViewBrowserHighRiskSmoke.ps1` (broken row guidance), `Test-WebViewBrowserDiagnosticsHandoffSmoke.ps1` (row click, combined review plan, filter warnings), `Test-WebViewBrowserLargeTableSmoke.ps1` (250/260 cap, output acceptance daily-use handoff/filter scope, selected-row at-a-glance summary), `Test-WebViewBrowserCompletedPendingProofSmoke.ps1` (proof ladder, saved-policy reconciliation, Sample Validation handoff, overlap proof, publish reconciliation, missing-output blocker, same-leaf duplicate-title) |

**Gaps**: Size-growth outlier rendering not smoke-exercised; route-agreement check rendering has partial coverage only via `RealMediaEvidence`.

**Runtime state hygiene**: `test_controllers_completed.py` verifies encode-speed history writes and legacy migration into `LocalBase\State\App`. `ops/pipeline/tests/Unit/Invoke-RuntimeStateHygieneChecks.ps1` prevents the legacy `DesktopApp\encode_speed_history.json` app-root runtime state from returning and guards the inventory/ignore/test coverage for this state file.

---

### Pending Publish

**Module**: `pendingPublishView.js`, `pendingPublishView.recovery.js`, `pendingPublishView.diagnostics.js`, `pendingPublishView.drain.js`, `pendingPublishView.confidence.js`
**API routes**: `GET /api/pending-publish`, `POST /api/pending-publish/open`, `POST /api/pending-publish/recovery-plan`, `POST /api/pipeline/start` (`drain_pending_pushes` mode — guarded in UI/API, exercised by PowerShell end-to-end smoke)

| Coverage type | Files / Wrappers |
|---|---|
| Python unit tests | `test_facade_pending_publish_policy.py`, `test_pending_publish_service.py`, `test_service_pending_publish_manifest.py`, `test_service_pending_publish_manifest_rows.py`, `test_service_pending_publish_paths.py`, `test_application_facade_pending_publish.py`, `test_webview_row_detail_smoke.py`, `test_webview_browser_pending_drain_guard_smoke.py` (facade pending-publish preview classification, strict current-manifest proof fields, legacy/current invalid row do-not-drain readiness, durable drain summary evidence, publish reconciliation path normalization, row-key open allowlists, scan-failure surfacing, recovery dry-run planning, WebView row-detail handoff, and browser-backed drain guard coverage) |
| PowerShell focused checks | `ops/pipeline/tests/Unit/Invoke-PendingPublishSafetyChecks.ps1` (media-plus-sidecar parking, strict manifest trust gates, legacy no-drain/no-mutation, forged `local_file` / `server_out` rejection, unsafe `original_local_file` repair refusal, sidecar outside-pending rejection, mixed-slash safe path handling, local cleanup boundary refusal, missing-payload no-rewrite behavior, weak already-published proof rejection, pending sidecar rollback, and low-space deferred-publish classification); `ops/pipeline/tests/Unit/Invoke-PendingPublishOwnershipChecks.ps1` (module ownership map, parser checks, parked output as media-plus-sidecars, and frontend drain-safety boundary wording) |
| Non-browser smokes | `Test-WebViewRowDetailSmoke.ps1` (row detail, combined drain review plan, do-not-drain rows, diagnostics handoff), `Test-WebViewRealMediaEvidenceSmoke.ps1` (evidence panel), `Test-WebViewCommandEvidenceSmoke.ps1` (drain guard command evidence in command detail) |
| Browser-backed smokes | `Test-WebViewBrowserHighRiskSmoke.ps1` (do-not-drain guidance), `Test-WebViewBrowserDiagnosticsHandoffSmoke.ps1` (row click, combined drain review plan, filter warnings), `Test-WebViewBrowserLargeTableSmoke.ps1` (250/260 cap, Backend Drain Scope Preview boundary, Pending Drain Decision daily-use handoff, selected-row at-a-glance summary), `Test-WebViewBrowserPendingDrainGuardSmoke.ps1` (Backend Drain Scope Preview, Publish Button Guard, blocked click, filter-scope disclosure, frontend_guard evidence), `Test-WebViewBrowserCompletedPendingProofSmoke.ps1` (Completed-to-Pending overlap, manifest correlation) |

**Gaps**: Recovery dry-run rendering is covered only via injected payload in `PendingDrainGuard`; completed-manifest to pending-drain-summary field reconciliation is not exhaustive across all media classes.

**Pipeline regression coverage**: `test_pending_publish_service.py` covers the read-only parked media-plus-sidecar row shape before drain and legacy rows remaining scan-visible but non-drainable. `test_service_pending_publish_manifest.py`, `test_service_pending_publish_manifest_rows.py`, `test_contracts.py`, and `test_application_facade_pending_publish.py` guard strict current-manifest proof fields, invalid/legacy row readiness, schema required fields, final-placement path normalization, and same-leaf weak evidence. `test_repair_reconcile_apply.py` now includes a Local API orphan-payload repair to `MediaPipeline.ps1 -DrainPendingPushes` bridge that proves the repaired manifest is drainable, the API journal records only the repair command, the source/output/payload are unchanged before drain, the final output is published from the parked payload, the parked payload/manifest are removed, and the source remains unchanged. `ops/pipeline/tests/Unit/Invoke-PendingPublishSafetyChecks.ps1` provides focused PowerShell coverage for parking, manifest trust gates, missing-payload manifests, forged local/destination paths, unsafe crash-recovery originals, sidecar carry-forward boundaries, weak already-published proof rejection, sidecar rollback, low-space deferred-publish classification, and drain-summary helper wiring. `ops/pipeline/tests/Unit/Invoke-PendingPublishOwnershipChecks.ps1` keeps the architecture map, fixture inventory, parser checks, and frontend drain-safety wording aligned with the backend ownership boundary. `ops/pipeline/tests/Invoke-ReliabilityRegressionChecks.ps1` now runs the current WebView/backend wrapper plus focused pending-publish safety checks by default; archived legacy desktop-shell checks require `-RunLegacyDesktopChecks`. `ops/pipeline/tests/Invoke-EndToEndSmokeChecks.ps1` executes generated-media deferred publish followed by `-DrainPendingPushes`.

## Freshness Review - 2026-05-19 (Pending Publish Ownership Guard)

Pending publish ownership is now represented in both `docs/architecture/MODULE_MAP.md` and `docs/inventories/PENDING_PUBLISH_FIXTURE_INVENTORY.md`. The focused PowerShell ownership check parses the relevant publish/pending modules and fails if the module map stops stating that parked output is media plus sidecars, if WebView/Tauri drain-safety boundaries disappear, or if the parked media-plus-sidecar service scan coverage is removed.

---

### Rename

**Module**: `renameView.js`
**API routes**: `POST /api/rename/browse` (native path picker, non-mutating), `POST /api/rename/preview`, `POST /api/rename/apply` (guarded — never exercised by smokes)

| Coverage type | Files / Wrappers |
|---|---|
| Python unit tests | `test_facade_rename_policy.py`, `test_application_facade_rename.py` (facade rename preview/apply command behavior, confirmation, selected-source scope, multi-select handling, and apply-lock guard), `test_application_facade_local_api.py` (native rename browse command-result payload with injected picker, Local API absent/false `confirm_apply` rejection without rename mutation), `test_api_path_dialogs.py` (Windows PowerShell dialog host selection, encoded-command invocation, payload parsing, and host-aware failure messaging), `test_service_rename_movie.py`, `test_service_rename_tv.py`, `test_service_rename_tv_folder.py`, `test_service_rename_plan_policy.py`, `test_service_rename_planner.py` (service-layer duplicate-destination blocking for every colliding row), `test_service_rename_apply.py`, `test_service_rename_preview.py`, `test_service_rename_discovery.py`, `test_service_rename_preview_runner.py`, `test_service_rename_apply_runner.py` |
| PowerShell focused checks | `ops/pipeline/tests/Unit/Invoke-NamingSupportChecks.ps1` (shared Plex destination planning, forced rename sidecar sanitization/evidence, TV library-index identity keys, and source identity v2 path-independence/sample-byte sensitivity) |
| Non-browser smokes | `Test-WebViewRenameReadinessSmoke.ps1` (Apply Readiness, Apply Outcome Review, 260-row cap disclosure, duplicate-target blocking) |
| Browser-backed smokes | `Test-WebViewBrowserRenameSmoke.ps1` (Windows file-browser browse button stages selected paths through the backend browse route without apply, row selection, Apply Readiness, Pipeline Handoff, Apply Outcome Review, 250/260 render cap, duplicate-target blocking) |

**Gaps**: `rename.apply` is never invoked by any smoke (by design — it is a filesystem mutation); the real native Windows dialog is not opened by automated smokes because it would block headless runs; TV folder rename not exercised in smokes.

---

### Launch

**Module**: `launchView.js`, `launchView.risk.js`, `launchView.scope.js`, `launchView.realmedia.js`, `launchView.preflight.js`, `launchReadinessView.js`, `launchHistoryView.js`
**API routes**: `GET /api/launch/preflight`, `POST /api/pipeline/start`, `POST /api/pipeline/control`, `POST /api/audit/start`, `POST /api/rerun/start`

| Coverage type | Files / Wrappers |
|---|---|
| Python unit tests | `test_facade_process_pipeline_policy.py`, `test_application_facade_process_launch.py` (facade pipeline/audit/rerun launch handoff, duplicate pipeline launch rejection while a prior child process is still running, launch-lock fail-closed behavior, schedule-gated launch handling, schedule-stop watcher preservation, read-only launch preflight guard coverage, and backend-authored `desktop_launch_readiness.v1` DTO coverage), `test_application_facade_local_api.py` (Local API exposure of nested `operator_readiness`), `test_application_facade_web_static.py` (state-aware Launch command button wiring, hidden-until-active emergency topbar Force Stop, destructive/long-running action tooltips, and sanitized command-failure detail hooks), `test_facade_process_control_policy.py`, `test_application_facade_process_control.py` (facade pipeline control flag contract and backend control-lock fail-closed behavior), `test_facade_process_guard_policy.py`, `test_facade_process_rerun_policy.py`, `test_service_process_readiness.py`, `test_service_process_launch_runner.py`, `test_service_process_launch_plans.py`, `test_service_process_launch_env.py`, `test_api_contract_payload.py` (CSV rerun copy/keep/park route contract defaults) |
| Non-browser smokes | `Test-WebViewSettingsLaunchPolicySmoke.ps1` (media-policy readiness rows display), `Test-WebViewSettingsLaunchLiveConfigSmoke.ps1` (readiness against live config) |
| Browser-backed smokes | `Test-WebViewBrowserSettingsLaunchSmoke.ps1` (Settings-to-Launch intent, Settings Effective Policy Trust, selectable Launch Risk Handoff proof-chain detail, staged subtitle/audio rows, filter-scope evidence for blocked rows, Preview Patch called, Save Patch not posted), `Test-WebViewBrowserLaunchQueueReadinessSmoke.ps1` (Launch readiness prefers backend `operator_readiness` from `GET /api/launch/preflight`, Launch timing trust, Launch Scope Reconciliation, Launch Start Decision Summary, Launch Real-Media Sample Proof Handoff including generated worksheet, Sample Validation record selected-sample match evidence, saved-policy-vs-Queue-route evidence, Launch Sample Execution Checklist, Launch Pilot Run Readiness, backend preflight rendering, launch history/review correlation, and no POST routes during readiness rendering) |

**Gaps**: WebView smokes do not submit real `pipeline/start` or `pipeline/control` commands by design. PowerShell end-to-end smoke exercises `-Once` and `-DrainPendingPushes`; `validate`, `continuous`, `audit/start`, `rerun/start`, and `pipeline/control` (pause/stop/rescan) route submissions are not smoke-exercised. Launch history rendering has read-only browser coverage.

---

### Audit / Reports

**Module**: `reportsView.js`
**API routes**: `GET /api/failures`, `GET /api/audit-results`, `POST /api/audit/start` (not exercised), `POST /api/rerun/start` (not exercised)

| Coverage type | Files / Wrappers |
|---|---|
| Python unit tests | `test_facade_audit_policy.py`, `test_facade_process_audit_policy.py`, `test_facade_process_rerun_policy.py`, `test_service_audit_rerun_csv.py`, `test_service_audit_rerun_export.py`, `test_service_audit_rerun_records.py`, `test_facade_failures_policy.py`, `test_service_failure_markers.py`, `test_application_facade_reports.py` (facade read-only failure JSON/marker preview and audit CSV preview behavior) |
| PowerShell focused checks | `ops/pipeline/tests/Unit/Invoke-PortablePathChecks.ps1` (audit/legacy GUI scripts parse and do not default audit roots to local operator UNC paths); `ops/pipeline/tests/Unit/Invoke-RerunSourceIdentityChecks.ps1` (CSV rerun source identity remains deterministic and sample-hash-sensitive when `ffprobe` is unavailable) |
| Non-browser smokes | None |
| Browser-backed smokes | `Test-WebViewBrowserMaintenanceReportsSmoke.ps1` (failure/audit triage, failure-marker clear dry-run preview, selected-row details, report-to-launch handoff navigation, no non-dry-run mutation posts) |

**Gaps**: Report-open diagnostics targets are not individually exercised; `audit/start` and `rerun/start` remain intentionally unexercised by smokes because they are backend-owned process-launch mutations.

---

### Schedule

**Module**: `scheduleView.js`
**API routes**: `GET /api/schedule`, `POST /api/schedule/preview`, `POST /api/schedule/save`

| Coverage type | Files / Wrappers |
|---|---|
| Python unit tests | `test_facade_schedule_policy.py`, `test_service_app_schedule.py`, `test_facade_process_schedule_policy.py`, `test_application_facade_schedule.py` (facade Schedule workspace, watcher evidence, preview/save confirmation, app-state preservation, and invalid-time rejection) |
| Non-browser smokes | `Test-WebViewScheduleSmoke.ps1` (coverage review, day detail, schedule editor, preview/save routes, confirmation payloads, command results, app-state-write result copy) |
| Browser-backed smokes | `Test-WebViewBrowserScheduleSmoke.ps1` (real browser: schedule editor, preview/save with confirmation, app-state key preservation, Launch timing trust refresh), `Test-WebViewBrowserLaunchQueueReadinessSmoke.ps1` (Schedule guidance and timing trust consumed by Launch/Queue readiness without POST routes) |

**Gaps**: All-day window edge cases not exercised in browser smoke; multi-week schedule grid rendering not exercised.

---

### Network

**Module**: `networkView.js`
**API routes**: `GET /api/network/workers`

| Coverage type | Files / Wrappers |
|---|---|
| Python unit tests | `test_application_facade_network.py` (`/api/network/workers` state-file metadata contract, progress bars, backend-authored heartbeat age, and lifecycle/provider read evidence), `test_api_contract_payload.py` plus `test_application_facade_local_api.py` (active backend-owned Network lifecycle/setup route metadata, dry-run fields including `dry_run_writes` and `confirmed_route_would_write`, rollback journal fields, source-file policy, route exposure gates, and live Local API payload), `test_webview_network_read_only_boundary.py` (Workers page calls only documented backend lifecycle/setup routes, keeps frontend-owned mutation controls absent, verifies `/api/network/*` route effects, and pins lifecycle/setup contract display references), `test_network_security.py`, `test_network_workflow.py`, `test_network_worker_runtime.py`, `test_network_coordinator_helpers.py`, `test_network_coordinator_http.py`, `test_network_protocol_runtime.py`, `test_network_firewall.py`, `test_network_worker_state.py`, `test_network_inflight_registry.py`, `test_network_crash_recovery.py`, `test_network_done_release.py`, `test_network_coordinator_startup.py`, `test_network_coordinator_source_policy.py`, `test_network_worker_source_policy.py`, `test_network_local_ip.py`, `test_network_mdns.py` |
| Non-browser smokes | None |
| Browser-backed smokes | `Test-WebViewBrowserNetworkSmoke.ps1` (read-only posture, runtime state-file evidence, worker rows, worker detail, filter warnings when active/problem rows hidden) |

**Gaps**: coordinator live-dispatcher detail panel is still limited to fixture evidence; live LAN mDNS discovery and two-machine lifecycle execution remain operator-side validation. Backend dry-run/start/stop routes exist and are provider-guarded; the WebView must continue to use only those Local API routes.

---

### Maintenance

**Module**: `maintenanceView.js`
**API routes**: `GET /api/maintenance`, `GET /api/maintenance/change-ledger`, `POST /api/maintenance/release-dry-run`, `POST /api/maintenance/completed-backfill-dry-run`, `POST /api/maintenance/retention-dry-run`

| Coverage type | Files / Wrappers |
|---|---|
| Python unit tests | `test_facade_maintenance_policy.py`, `test_facade_maintenance_command_policy.py`, `test_application_facade_maintenance.py` (facade Maintenance workspace environment-health rows, Release Package dry-run plan/progress behavior, and maintenance command-lock fail-closed behavior); `test_maintenance_retention_dry_run.py` (retention candidate allowlist, source/output/pending-publish exclusions, no-delete/no-move evidence, authenticated unjournaled Local API route); `test_maintenance_change_ledger.py` (packet parsing, invalid JSON/missing-field hygiene, counts, Python-impact grouping, route auth/contract/read-only metadata) |
| Non-browser smokes | `Test-LocalApiMaintenanceDryRunContractSmoke.ps1` (executes backend-owned ops/release/metadata/backfill/retention dry-run POST routes against temporary state, verifies token enforcement, command history, no release manifest/zip, no completed-manifest rewrite, no retention delete/move/write plan, and unchanged temp source/output bytes) |
| Browser-backed smokes | `Test-WebViewBrowserMaintenanceReportsSmoke.ps1` (Maintenance health/readiness, release dry-run result rendering, completed-manifest backfill dry-run result rendering, dry-run history, Reports failure-marker clear dry-run preview, no non-dry-run mutation posts); `Test-WebViewBrowserMaintenanceChangeLedgerSmoke.ps1` (Change Ledger summary/table/detail/hygiene, filters, empty state, read-only `GET /api/maintenance/change-ledger`, no media/queue/settings/pending-publish/rename mutation posts) |

**Gaps**: Browser smoke remains presentation-only for Maintenance POSTs by design; the browser-free Local API smoke now executes the backend dry-run command routes. The Change Ledger browser smoke uses a representative fixture payload for UI behavior while `test_maintenance_change_ledger.py` proves the real packet reader/route contract. No smoke executes real release packaging, real completed-manifest rewrite, or retention cleanup mutation.

---

### Diagnostics

**Module**: `diagnosticsView.js`, `diagnosticsStateSummaryView.js`, `diagnosticsBridge.js`, `diagnosticsTailView.js`, `contractView.js`
**API routes**: `GET /api/diagnostics`, `GET /api/diagnostics/tail`, `GET /api/diagnostics/state-summary`, `GET /api/contract`, `POST /api/diagnostics/open`

| Coverage type | Files / Wrappers |
|---|---|
| Python unit tests | `test_facade_diagnostics_policy.py`, `test_facade_diagnostics_open_policy.py`, `test_application_facade_diagnostics.py` (diagnostics open/tail allowlists, read-only state-summary artifact evidence, and diagnostics path lookup failure logging), `test_application_facade_local_api.py` (backend diagnostics tail/state-summary route handling), `test_application_facade_web_static.py` (WebView advisory fallback static contract) |
| Non-browser smokes | `Test-WebViewCommandEvidenceSmoke.ps1` (command history rendering, owner/issue cross-page linking in Diagnostics) |
| Browser-backed smokes | `Test-WebViewBrowserDiagnosticsHandoffSmoke.ps1` (row click → investigation signals plus combined row review plans, text/status/investigation filters, clear-filter buttons, diagnostics bridge, bounded tail, allowlisted open controls, First Response Checklist status/summary rows plus selectable detail, ActiveJobs table/detail for active and malformed records, stale runtime-progress guidance, State Artifact Summary read-order/artifact detail, Go To Owner Row for all 3 tables, and API Contract Safety Review summary/detail from `/api/contract`); `Test-WebViewBrowserLifecycleSmoke.ps1` (Backend Lifecycle/Close Readiness watcher-armed shutdown blocking, terminal stop-requested watcher evidence, and safe backend-owned shutdown request) |

**Gaps**: State Artifact Summary now has browser coverage for the read-order/artifact detail path and one allowlisted tail/open action path. All 20 allowlisted open targets are not individually exercised; lifecycle browser smoke still uses fixture state. `ops/pipeline/tests/Invoke-AdversarialForceKillEncodeChecks.ps1` now force-kills a real generated-media backend encode and proves the partial is not accepted as complete, but it is not a browser/Tauri close dialog test. ActiveJobs browser coverage uses generated records, not a real orphaned FFmpeg process. Contract Safety Review is presentation-only coverage over the current route inventory; it does not prove future routes stay classified correctly without updating `/api/contract` and static tests. WebView fallback tail evidence is covered statically for advisory wording; the browser smoke exercises backend-authored tail evidence.

---

### Settings

**Module**: `settingsView.js`, `settingsView.builders.audio.js`, `settingsView.builders.video.js`, `settingsView.builders.subtitle.js`, `settingsView.builders.queue.js`, `settingsView.builders.runtime.js`, `settingsView.builders.file_safety.js`, `settingsView.builders.pending.js`, `settingsView.builders.network.js`, `settingsMetadata.js`, `settingsOverview.js`, `settingsCommandHistory.js`
**API routes**: `GET /api/settings/workspace`, `POST /api/settings/validate`, `POST /api/settings/browse-path`, `POST /api/settings/preview-patch`, `POST /api/settings/save-patch`, `POST /api/settings/import-psd1-preview`, `POST /api/settings/import-psd1`, `POST /api/settings/reload`

| Coverage type | Files / Wrappers |
|---|---|
| Python unit tests | `test_facade_settings_policy.py`, `test_facade_settings_patch_policy.py`, `test_application_facade_settings_workspace.py` (facade Settings workspace redaction, JSON-authority/projection metadata, media-policy readiness, tool-path evidence, and Validate command-result envelope), `test_settings_store.py` (JSON authority import, drift handling, last-good restore, rollback, aliases, legacy extras, and import preview), `test_application_facade_local_api.py` (Settings browse-path command route, command-result envelope, and selected-folder validation evidence), `test_webview_frontend_mutation_boundary.py` (Settings browse-path WebView caller ownership and folder-only staging payload), `test_api_path_dialogs.py` (native Windows dialog host and payload parsing), `test_application_facade_settings_patch.py` (facade Settings Preview Patch/Save Patch command behavior, JSON authority save delegation, risk summaries, redacted diff fallback, save-lock guard, backup/secret preservation, and no-op same-value handling), `test_service_config_validation.py` (cross-field config validation plus BDPGS OCR enabled-without-tool-path warning), `test_service_config_preview.py`, `test_service_config_save_runner.py`, `test_service_config_profiles.py`, `test_settings_risk_policy_rules.py` (risk rules and clean template source-safety defaults), `test_service_config_numeric_policy.py`, `test_service_config_option_policy.py`, `test_service_config_value_checks.py`, `test_application_facade_web_static.py` (backend-served Settings asset availability/load-order, split builder compatibility hooks, file-safety path Browse controls, BDPGS OCR path builder/no-frontend-owned-picker guard, and subtitle keyword list builder wiring) |
| Non-browser smokes | `Test-WebViewSettingsLaunchPolicySmoke.ps1` (handoff display), `Test-WebViewSettingsLaunchLiveConfigSmoke.ps1` (live config readiness), `Test-WebViewSettingsPatchEvidenceSmoke.ps1` (Preview Patch, denied/confirmed Save Patch, reload, command history, temp-config isolation) |
| Browser-backed smokes | `Test-WebViewBrowserSettingsLaunchSmoke.ps1` (staged settings, Settings Effective Policy Trust, Settings-to-Launch intent, Launch Risk Handoff proof-chain detail, filter-scope evidence, Preview Patch called, Save Patch not posted) |

**Gaps**: All 6 config pages (Basic / Video / Audio / Subtitles / Advanced / Network) not individually exercised; high-risk field risk overlay rendering not smoke-tested; native Settings folder Browse is route/static/live-DOM verified but not clicked in browser smoke because it opens the OS dialog.

---

## Freshness Review — 2026-05-19 (Settings Subtitle Builder Coverage)

Settings now exposes `BdpgsOcrToolPath` and `BdpgsOcrTessdataPath` as Subtitle builder text fields that stage values into the existing backend-owned Preview/Save path. `SubSDHTitleKeywords` and `SubSupplementalKeywords` are also Subtitle builder list fields; the WebView only stages list text and does not classify subtitle tracks. Static coverage pins the four DOM IDs, metadata field wiring, text/list-value collection, no-frontend-path-picker boundary, and backend-owned subtitle-classification wording. Config validation now warns when `ConvertBdpgsToSrt` is enabled with a blank OCR tool path.

Validation: Node syntax checks for `settingsMetadata.js`, `settingsView.builders.subtitle.js`, and `settingsView.rawTriage.js` passed; py_compile for changed Python/tests passed; focused Settings static/config validation tests passed.

Risk: Low to medium. This adds staged config fields for external OCR paths, but does not add a file picker, arbitrary path open/read route, path resolution in the WebView, OCR execution, media-policy ownership, or settings persistence outside the existing backend Preview/Save flow.

---

## Freshness Review - 2026-05-19 (Adversarial Force-Kill Encode Safety)

`ops/pipeline/tests/Invoke-AdversarialForceKillEncodeChecks.ps1` now covers the R-001 force-kill gap with a generated source and the real backend pipeline. It generates media under `%TEMP%`, forces backend routing into CPU fallback encode, waits for an `encode_temp_cpu_*.mkv` processing artifact, force-kills the PowerShell/FFmpeg process tree, then verifies the source hash is unchanged, no Outsource/local encoded/completed manifest/pending-publish artifact was accepted, and the same source remains present in a backend-authored queue plan.

This is runtime PowerShell coverage, not WebView/Tauri prompt coverage and not real-media output-quality proof. Keep browser lifecycle close-readiness tests and real-media validation as separate gates.

---

## Coverage Summary Table

| Page | Python unit tests | Non-browser smokes | Browser smokes | Overall |
|---|---|---|---|---|
| Home | Partial | 3 wrappers | 3 wrappers | Partial |
| Live / Progress | Good | None | 1 wrapper | Partial |
| Queue | Good | 2 wrappers | 3 wrappers | Good |
| Completed | Good | 2 wrappers | 4 wrappers | Good |
| Pending Publish | Good | 3 wrappers | 5 wrappers | Good |
| Rename | Excellent | 1 wrapper | 1 wrapper | Good; mutation smokes intentionally do not invoke apply |
| Launch | Good | 2 wrappers | 1 wrapper | Partial; duplicate launch rejection is unit-covered, route submissions remain smoke-light |
| Audit / Reports | Good | **None** | 1 wrapper | Partial |
| Schedule | Good | 1 wrapper | 1 wrapper | Good |
| Network | Good | None | 1 wrapper | Partial |
| Maintenance | Good | 1 wrapper | 1 wrapper | Good for dry-run routes; real repair deferred |
| Diagnostics | Good | 1 wrapper | 1 wrapper | Partial |
| Settings | Excellent | 3 wrappers | 1 wrapper | Good |

---

## Critical Gaps

| Gap | Risk | Mitigation |
|---|---|---|
| Pipeline launch (`once`/`continuous`/`validate`) — not smoke-exercised | Medium | Unit tests cover backend guard logic; real-media validation required for end-to-end proof |
| `rename.apply` never exercised | Low | By design — filesystem mutation; covered by `test_service_rename_apply.py` |
| Completed-manifest to pending-drain-summary reconciliation is not exhaustive | Medium | PowerShell regression and end-to-end smoke now exercise drain success/failure; add cross-field assertions before expanding drain policy |
| Real-media route/remux/encode proof | High | Requires `docs/implementation/release-foundation/PHASE_6_REAL_MEDIA_PILOT.md`; smokes use generated fixtures only |
| Stuck/orphan process recovery | High | Unit and close-readiness tests cover contracts; `Invoke-AdversarialForceKillEncodeChecks.ps1` now proves a force-killed encode partial is not accepted as complete; orphan discovery/recovery UX for real abnormal exits still needs broader runtime coverage |
| Malformed state recovery | Medium | Some diagnostics/state-summary unit tests exist; browser coverage is incomplete |
| Packaging/install confidence for Tauri/WebView2 | Medium | Release self-test and Tauri build gate pass locally; clean-machine install validation remains operator/manual |
| PG-1 live Tauri close-readiness test (window dialog) | Medium | Structural Rust patterns verified by `test_tauri_pg1_close_adversarial_scaffold.py` (25 tests); live Tauri dialog rendering requires manual or adversarial-backend Tauri run — see VALIDATION_LADDER_RUNBOOK.md Rung 5 |
| Test-suite consolidation without same-rung replacement | High | Use `docs/ai-audits/2026-06-18-test-coverage-rationalization.md` before removing overlap candidates; do not reduce source/path, media, pending-publish, command journal, strict JSON, close-readiness, network, or Tauri coverage without stronger replacement evidence |

---

## See Also

- Smoke test catalog: `docs/testing/WEBVIEW_SMOKE_TEST_CATALOG.md`
- Smoke mutation matrix: `docs/testing/BROWSER_SMOKE_DOES_NOT_MUTATE_MATRIX.md`
- Manual operator test script: `docs/operator/WEBVIEW_MANUAL_OPERATOR_TEST_SCRIPT.md`
- API route inventory: `docs/inventories/API_ROUTE_INVENTORY.md`

---

## Freshness Review — 2026-05-15 (CLN4-009)

Checked whether both scope preview panels (`Queue Backend Launch Scope Preview`, `Pending Backend Drain Scope Preview`) are represented in the matrix.

**Finding**: Matrix is already accurate. The Queue section browser-backed smoke entry includes `Test-WebViewBrowserLaunchQueueReadinessSmoke.ps1` which covers "Launch preflight...Queue Backend Launch Scope Preview panel scope boundary." The Pending Publish section browser-backed smoke entry includes `Test-WebViewBrowserPendingDrainGuardSmoke.ps1` which covers "backend-authored Pending Backend Drain Scope Preview scope boundary." Both panels are evidence-only renders with no new POST routes; the Critical Gaps table remains accurate (scope preview raises no new gap).

No changes required to matrix content.

```
Task ID: CLN4-009
Files inspected: docs\testing\TEST_COVERAGE_MATRIX.md (Queue section, Pending Publish section, Coverage Summary Table, Critical Gaps)
Files changed: docs\testing\TEST_COVERAGE_MATRIX.md (CLN4-009 freshness note added)
Validation: Select-String -Path docs\testing\TEST_COVERAGE_MATRIX.md -Pattern "Backend Launch Scope Preview|Backend Drain Scope Preview"
Findings: Both scope preview panels already named in their respective page sections. Matrix is accurate.
Open questions: None.
Risk: Low — documentation only.
```

---

## Freshness Review — 2026-05-18 (Browser Smoke No-Mutation Hash Gate)

Browser-backed smoke coverage now includes fixture-level SHA-256/size assertions for media, subtitle, pending-publish sidecar, manifest, and JSONL evidence artifacts. This strengthens the mutation-boundary tier from "no forbidden POSTs" to "no source/output/sidecar artifact bytes changed, deleted, or appeared unexpectedly" for all 16 fixture-backed browser smoke wrappers.

```
Task ID: transition checklist chunk 9
Files inspected: tests/python/desktop/test_webview_browser_*.py, tests/python/desktop/webview_browser_smoke_support.py
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest discover -s tests\python\desktop -p "test_webview_browser_*.py" -q
Findings: 20 browser smoke tests passed with hash no-mutation assertions active.
Open questions: None.
Risk: Low — tests/docs only; fixtures are temporary.
```

---

## Freshness Review — 2026-05-18 (Refactoring UI Workflow Table Scanability)

Python unit coverage now extends `test_webview_css_design_tokens.py` beyond raw-token policing to guard the first Refactoring UI scanability pass: Queue, Output, and Publish workflow tables must keep the shared `workflow-table` plus page-specific table classes, and Output/Pending owner renderers must keep using the shared status-chip helper for backend-authored health/state fields.

```
Task ID: Refactoring UI workflow table scanability pass
Files inspected: apps/desktop/webview/static/index.html; apps/desktop/webview/static/assets/styles.css; apps/desktop/webview/static/assets/domHelpers.js; apps/desktop/webview/static/assets/completedView.evidence.js; apps/desktop/webview/static/assets/completedView.js; apps/desktop/webview/static/assets/pendingPublishView.js
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest tests.webview.test_webview_css_design_tokens tests.webview.test_webview_inventory_docs tests.webview.test_webview_navigation_static tests.webview.test_webview_dom_helpers_smoke tests.webview.test_webview_row_detail_smoke tests.webview.test_webview_frontend_mutation_boundary -q
Findings: 28 targeted WebView tests cover token discipline, workflow table classes, status-chip helper wiring, inventory drift, navigation/static structure, DOM helper smoke coverage, row-detail rendering, and frontend mutation-boundary ownership.
Open questions: None.
Risk: Low — static UI wiring only; no API route or media-policy behavior changed.
```

---

## Freshness Review — 2026-05-18 (CSS Design Token Gate)

Python unit coverage now includes `test_webview_css_design_tokens.py`, which fails when any `styles*.css` file introduces raw hex/rgba/hsla colors, inline `hsl()` outside custom-property token definitions, arbitrary `font-size`, raw spacing values for margin/padding/gap, or `opacity:` de-emphasis.

```
Task ID: transition checklist chunk 10
Files inspected: apps/desktop/webview/static/assets/styles.css; apps/desktop/webview/static/assets/styles.tokens.css; apps/desktop/webview/static/assets/styles.theme.css; apps/desktop/webview/static/assets/styles.layout.css; apps/desktop/webview/static/assets/styles.components.css; apps/desktop/webview/static/assets/styles.pages.css; apps/desktop/webview/static/assets/styles.controls.css; apps/desktop/webview/static/assets/styles.layout-manager.css; apps/desktop/webview/static/assets/styles.queue.css
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest tests.webview.test_webview_css_design_tokens -q
Findings: 5 CSS design-token regression tests passed, including the `styles.css` -> `styles.tokens.css` -> `styles.theme.css` -> `styles.layout.css` -> `styles.components.css` -> `styles.pages.css` -> `styles.controls.css` -> `styles.layout-manager.css` -> `styles.queue.css` import boundary and the rule that shell layout, shared component/table, starter page, command/status-control, layout-customization, and queue feature selectors live outside the parent stylesheet.
Open questions: None.
Risk: Low — CSS/static-test only.
```

## Freshness Review — 2026-05-19 (Network Coordinator Startup Test Rename)

`test_network_coordinator_startup.py` now owns the final coordinator startup block that remained after the `test_network_persistence.py` splits. The stale persistence filename was removed so future changes land in the coordinator-startup module instead of a misleading catch-all.

```
Task ID: God-file split Wave 5: network coordinator startup test rename
Files inspected: tests/python/desktop/test_network_coordinator_startup.py; tests/python/desktop/test_network_done_release.py; tests/python/desktop/test_network*.py
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_network_coordinator_startup -q; apps\desktop\runtime\Python\python.exe -m unittest discover -s tests\python\desktop -p "test_network*.py" -q
Findings: 8 coordinator-startup tests passed under the renamed module, and 243 network-discovery tests passed.
Open questions: None.
Risk: Low — test-file rename only; no production code, WebView assets, API routes, network runtime behavior, command contracts, coordinator startup behavior, media policy, or file mutation paths changed.
```

## Freshness Review — 2026-05-19 (Controller Diagnostics Test Split)

`test_controllers_diagnostics.py` now owns the diagnostics controller test from `test_controllers.py`: log-search reset failure logging and current-match reset failure logging under the legacy test shim. `test_controllers.py` remains the broad historical controller boundary module for the other controller responsibilities.

```text
Task ID: God-file split Wave 5: controller diagnostics test extraction
Files inspected: tests/python/desktop/test_controllers.py; tests/python/desktop/test_controllers_diagnostics.py
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_controllers_diagnostics -q; apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_controllers -q; apps\desktop\runtime\Python\python.exe -m unittest discover -s tests\python\desktop -p "test_controllers*.py" -q
```

## Freshness Review — 2026-05-19 (Controller Home Test Split)

`test_controllers_home.py` now owns the Home controller tests from `test_controllers.py`: dashboard idle-state rendering, pending-publish summary/timing, pending payload stat failure logging, and live queue overview/selection. `test_controllers.py` remains the broad desktop-controller boundary module for the other controller responsibilities.

```text
Task ID: God-file split Wave 5: controller Home test extraction
Files inspected: tests/python/desktop/test_controllers.py; tests/python/desktop/test_controllers_home.py
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_controllers_home -q; apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_controllers -q; apps\desktop\runtime\Python\python.exe -m unittest discover -s tests\python\desktop -p "test_controllers*.py" -q
```

## Freshness Review — 2026-05-19 (Controller Status Presentation Test Split)

`test_controllers_status_presentation.py` now owns the status-presentation controller tests from `test_controllers.py`: topbar chip/window title/taskbar/command-bar updates, audit current-file formatting, and taskbar progress failure logging. `test_controllers.py` remains the broad desktop-controller boundary module for the other controller responsibilities.

```text
Task ID: God-file split Wave 5: controller status-presentation test extraction
Files inspected: tests/python/desktop/test_controllers.py; tests/python/desktop/test_controllers_status_presentation.py
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_controllers_status_presentation -q; apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_controllers -q; apps\desktop\runtime\Python\python.exe -m unittest discover -s tests\python\desktop -p "test_controllers*.py" -q
```

## Freshness Review — 2026-05-19 (Controller Telemetry Test Split)

`test_controllers_telemetry.py` now owns the telemetry controller test from `test_controllers.py`: non-finite CPU/GPU/RAM display sanitization and ffmpeg GPU-note rendering. `test_controllers.py` remains the broad desktop-controller boundary module for the other controller responsibilities.

```text
Task ID: God-file split Wave 5: controller telemetry test extraction
Files inspected: tests/python/desktop/test_controllers.py; tests/python/desktop/test_controllers_telemetry.py
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_controllers_telemetry -q; apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_controllers -q; apps\desktop\runtime\Python\python.exe -m unittest discover -s tests\python\desktop -p "test_controllers*.py" -q
```

## Freshness Review — 2026-05-19 (Controller Notification Test Split)

`test_controllers_notification.py` now owns the notification controller tests from `test_controllers.py`: background completion/failure notification dispatch, test toast delivery, Windows notification failure logging, and focus-check failure logging. `test_controllers.py` remains the broad desktop-controller boundary module for the other controller responsibilities.

```text
Task ID: God-file split Wave 5: controller notification test extraction
Files inspected: tests/python/desktop/test_controllers.py; tests/python/desktop/test_controllers_notification.py
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_controllers_notification -q; apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_controllers -q; apps\desktop\runtime\Python\python.exe -m unittest discover -s tests\python\desktop -p "test_controllers*.py" -q
```

## Freshness Review — 2026-05-19 (Controller Pipeline Test Split)

`test_controllers_pipeline.py` now owns the pipeline controller tests from `test_controllers.py`: pause/stop/rescan flag command-surface handling and sleep-second parsing. `test_controllers.py` remains the broad desktop-controller boundary module for the other controller responsibilities.

```text
Task ID: God-file split Wave 5: controller pipeline test extraction
Files inspected: tests/python/desktop/test_controllers.py; tests/python/desktop/test_controllers_pipeline.py
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_controllers_pipeline -q; apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_controllers -q; apps\desktop\runtime\Python\python.exe -m unittest discover -s tests\python\desktop -p "test_controllers*.py" -q
```

## Freshness Review — 2026-05-19 (Controller Process Lifecycle Test Split)

`test_controllers_process_lifecycle.py` now owns the process lifecycle controller tests from `test_controllers.py`: completed pipeline/audit handle synchronization, shutdown cleanup failure logging, pipeline/audit launch prep, schedule-window launch state, and kill-and-quit cleanup. `test_controllers.py` remains the broad desktop-controller boundary module for the other controller responsibilities.

```text
Task ID: God-file split Wave 5: controller process-lifecycle test extraction
Files inspected: tests/python/desktop/test_controllers.py; tests/python/desktop/test_controllers_process_lifecycle.py
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_controllers_process_lifecycle -q; apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_controllers -q; apps\desktop\runtime\Python\python.exe -m unittest discover -s tests\python\desktop -p "test_controllers*.py" -q
```

## Freshness Review — 2026-05-19 (Controller Worker Jobs Test Split)

`test_controllers_worker_jobs.py` now owns the worker job controller tests from `test_controllers.py`: worker completion event matching, fail-closed completion reports, malformed event skipping, dispatcher completion reporting, single-file launch failure handling, start UI failure handling, and worker abort/reclaim kill coverage. `test_controllers.py` remains the broad desktop-controller boundary module for the other controller responsibilities.

```text
Task ID: God-file split Wave 5: controller worker-jobs test extraction
Files inspected: tests/python/desktop/test_controllers.py; tests/python/desktop/test_controllers_worker_jobs.py
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_controllers_worker_jobs -q; apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_controllers -q; apps\desktop\runtime\Python\python.exe -m unittest discover -s tests\python\desktop -p "test_controllers*.py" -q
```

## Freshness Review — 2026-05-19 (Controller Network Test Split)

`test_controllers_network.py` now owns the NetworkController tests from `test_controllers.py`: coordinator status notice rendering, coordinator notice failure logging, coordinator button update failure logging, dispatcher error/shutdown failure logging, and worker status post failure logging. `test_controllers.py` remains the broad desktop-controller boundary module for the other controller responsibilities.

```text
Task ID: God-file split Wave 5: controller network test extraction
Files inspected: tests/python/desktop/test_controllers.py; tests/python/desktop/test_controllers_network.py
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_controllers_network -q; apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_controllers -q; apps\desktop\runtime\Python\python.exe -m unittest discover -s tests\python\desktop -p "test_controllers*.py" -q
```

## Freshness Review — 2026-05-19 (Controller Navigation Test Split)

`test_controllers_navigation.py` now owns the NavigationController tests from `test_controllers.py`: view routing/refresh/sidebar behavior, Network tab lifecycle failure logging, sidebar badge rendering, shortcut overlay guards, global shortcut bindings, filter trace/sort-heading/detail-copy wiring, and detail-copy failure logging. `test_controllers.py` now keeps only queue controller boundary coverage.

```text
Task ID: God-file split Wave 5: controller navigation test extraction
Files inspected: tests/python/desktop/test_controllers.py; tests/python/desktop/test_controllers_navigation.py
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_controllers_navigation -q; apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_controllers -q; apps\desktop\runtime\Python\python.exe -m unittest discover -s tests\python\desktop -p "test_controllers*.py" -q
```

## Freshness Review — 2026-05-19 (Controller Queue Test Split)

`test_controllers_queue.py` now owns the QueueController tests from `test_controllers.py`: queue filtering/quick views, selection/detail rendering, thumbnail lookup/failure handling, priority staging/menus/marker application/commit behavior, refresh progress/watchdog behavior, drag reordering, tree rendering/active-row selection, remaining-record context, ETA/preview health text, and queue file open/copy/export actions. `test_controllers.py` now only owns the controller helper import-boundary regression check.

```text
Task ID: God-file split Wave 5: controller queue test extraction
Files inspected: tests/python/desktop/test_controllers.py; tests/python/desktop/test_controllers_queue.py
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_controllers_queue -q; apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_controllers -q; apps\desktop\runtime\Python\python.exe -m unittest discover -s tests\python\desktop -p "test_controllers*.py" -q
```

## Freshness Review — 2026-05-19 (Application Facade Core Contract Test Split)

`test_application_facade_core_contracts.py` now owns the first core-contract slice from `test_application_facade.py`: command-result serialization, runtime outcome normalization/indexing, command journal bounded summaries and strict JSON failure cleanup, Local API HTTP helper auth/path/query guards, non-finite JSON body rejection, static bootstrap/asset helper behavior, and route-map coverage against `LOCAL_API_ROUTE_CONTRACT`. `test_application_facade.py` keeps the larger facade workflow, Local API server, and backend-served WebView static integration tests.

```text
Task ID: God-file split Wave 5: application facade core-contract test extraction
Files inspected: tests/python/desktop/test_application_facade.py; tests/python/desktop/test_application_facade_core_contracts.py
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_application_facade_core_contracts -q; apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_application_facade -q; apps\desktop\runtime\Python\python.exe -m unittest discover -s tests\python\desktop -p "test_application_facade*.py" -q
```

## Freshness Review — 2026-05-19 (Application Facade Close Readiness Test Split)

`test_application_facade_close_readiness.py` now owns the close-readiness slice from `test_application_facade.py`: active and unknown runtime-state blocking, fresh progress blocking, fail-closed pipeline/audit progress verification, ActiveJobs blocking and failure logging, schedule-stop watcher blocking, and related-process inspection failure handling. `test_application_facade.py` keeps diagnostics, settings, queue, pending/completed, process launch, Local API server, and backend-served WebView static integration tests.

```text
Task ID: God-file split Wave 5: application facade close-readiness test extraction
Files inspected: tests/python/desktop/test_application_facade.py; tests/python/desktop/test_application_facade_close_readiness.py
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_application_facade_close_readiness -q; apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_application_facade -q; apps\desktop\runtime\Python\python.exe -m unittest discover -s tests\python\desktop -p "test_application_facade*.py" -q
```

## Freshness Review — 2026-05-19 (Application Facade Diagnostics Test Split)

`test_application_facade_diagnostics.py` now owns the diagnostics slice from `test_application_facade.py`: diagnostics open allowlist coverage, diagnostics tail allowlist coverage, read-only diagnostics state-summary artifact coverage, blocked BDPGS OCR path surfacing, and diagnostics path lookup failure logging. `test_application_facade.py` keeps settings, queue, pending/completed, process launch, Local API server, and backend-served WebView static integration tests.

```text
Task ID: God-file split Wave 5: application facade diagnostics test extraction
Files inspected: tests/python/desktop/test_application_facade.py; tests/python/desktop/test_application_facade_diagnostics.py
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_application_facade_diagnostics -q; apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_application_facade -q; apps\desktop\runtime\Python\python.exe -m unittest discover -s tests\python\desktop -p "test_application_facade*.py" -q
```

## Freshness Review — 2026-05-19 (Application Facade Settings Patch Test Split)

`test_application_facade_settings_patch.py` now owns the Settings Preview Patch/Save Patch slice from `test_application_facade.py`: backend config redaction, PSD1 serialization fallback logging, risk summaries for high-risk, pending-publish, audio, and subtitle settings, save confirmation/backup/secret preservation, backend save-lock guarding, and no-op same-value handling. `test_application_facade.py` keeps telemetry, rename, queue, pending/completed, process launch, Local API server, and backend-served WebView static integration tests.

```text
Task ID: God-file split Wave 5: application facade settings patch test extraction
Files inspected: tests/python/desktop/test_application_facade.py; tests/python/desktop/test_application_facade_settings_patch.py
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_application_facade_settings_patch -q; apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_application_facade -q; apps\desktop\runtime\Python\python.exe -m unittest discover -s tests\python\desktop -p "test_application_facade*.py" -q
```

## Freshness Review — 2026-05-19 (Application Facade Rename Test Split)

`test_application_facade_rename.py` now owns the rename slice from `test_application_facade.py`: rename preview heuristic output, selected-only apply confirmation, multiple selected-source apply handling, temp-fixture undo-manifest cleanup, and backend apply-lock guarding. `test_application_facade.py` keeps telemetry, queue, pending/completed, process launch, Local API server, and backend-served WebView static integration tests.

```text
Task ID: God-file split Wave 5: application facade rename test extraction
Files inspected: tests/python/desktop/test_application_facade.py; tests/python/desktop/test_application_facade_rename.py
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_application_facade_rename -q; apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_application_facade -q; apps\desktop\runtime\Python\python.exe -m unittest discover -s tests\python\desktop -p "test_application_facade*.py" -q
```

## Freshness Review — 2026-05-19 (Application Facade Snapshot Test Split)

`test_application_facade_snapshot.py` now owns the snapshot/progress/telemetry slice from `test_application_facade.py`: facade snapshot assembly without native shell state, progress bar shaping for pipeline publish/audit/subtitle work, pending-publish copy byte progress, and zero-percent GPU telemetry presence. `test_application_facade.py` keeps queue, pending/completed, process launch, Local API server, and backend-served WebView static integration tests.

```text
Task ID: God-file split Wave 5: application facade snapshot test extraction
Files inspected: tests/python/desktop/test_application_facade.py; tests/python/desktop/test_application_facade_snapshot.py
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_application_facade_snapshot -q; apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_application_facade -q; apps\desktop\runtime\Python\python.exe -m unittest discover -s tests\python\desktop -p "test_application_facade*.py" -q
```

## Freshness Review — 2026-05-19 (Application Facade Queue Test Split)

`test_application_facade_queue.py` now owns the queue slice from `test_application_facade.py`: queue preview snapshot-read behavior without dry-run mutation, stale snapshot evidence, visible blocked rows versus completed exclusions, exact source-path runtime outcome correlation, and backend row-key queue open allowlists. `test_application_facade.py` keeps pending/completed, process launch, Local API server, and backend-served WebView static integration tests.

```text
Task ID: God-file split Wave 5: application facade queue test extraction
Files inspected: tests/python/desktop/test_application_facade.py; tests/python/desktop/test_application_facade_queue.py
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_application_facade_queue -q; apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_application_facade -q; apps\desktop\runtime\Python\python.exe -m unittest discover -s tests\python\desktop -p "test_application_facade*.py" -q
```

## Freshness Review — 2026-05-19 (Application Facade Pending Publish Test Split)

`test_application_facade_pending_publish.py` now owns the pending-publish slice from `test_application_facade.py`: pending-publish preview classification, unreadable manifest blocking evidence, durable drain-summary evidence, publish reconciliation correlation, read-only reconciliation endpoint behavior, backend row-key open allowlists, orphan row-key support, scan-failure surfacing, and backend-authored recovery dry-run planning. `test_application_facade.py` keeps completed, process launch, Local API server, and backend-served WebView static integration tests.

```text
Task ID: God-file split Wave 5: application facade pending publish test extraction
Files inspected: tests/python/desktop/test_application_facade.py; tests/python/desktop/test_application_facade_pending_publish.py
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_application_facade_pending_publish -q; apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_application_facade -q; apps\desktop\runtime\Python\python.exe -m unittest discover -s tests\python\desktop -p "test_application_facade*.py" -q
```

## Freshness Review — 2026-05-19 (Application Facade Completed Test Split)

`test_application_facade_completed.py` now owns the completed/output slice from `test_application_facade.py`: completed preview manifest loading, stale manifest and inventory progress evidence, size-growth and missing-output review classification, exact source-path runtime outcome correlation, backend row-key completed-open allowlists, and completed-manifest backfill dry-run behavior. `test_application_facade.py` keeps failure/audit, maintenance/release, schedule/settings workspace, network worker state, process launch, Local API server, and backend-served WebView static integration tests.

```text
Task ID: God-file split Wave 5: application facade completed test extraction
Files inspected: tests/python/desktop/test_application_facade.py; tests/python/desktop/test_application_facade_completed.py
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_application_facade_completed -q; apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_application_facade -q; apps\desktop\runtime\Python\python.exe -m unittest discover -s tests\python\desktop -p "test_application_facade*.py" -q
```

## Freshness Review — 2026-05-19 (Application Facade Reports Test Split)

`test_application_facade_reports.py` now owns the Reports slice from `test_application_facade.py`: read-only failure JSON preview, failure marker preview, and audit CSV preview behavior. `test_application_facade.py` keeps maintenance/release, schedule/settings workspace, network worker state, process launch, Local API server, and backend-served WebView static integration tests.

```text
Task ID: God-file split Wave 5: application facade reports test extraction
Files inspected: tests/python/desktop/test_application_facade.py; tests/python/desktop/test_application_facade_reports.py
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_application_facade_reports -q; apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_application_facade -q; apps\desktop\runtime\Python\python.exe -m unittest discover -s tests\python\desktop -p "test_application_facade*.py" -q
```

## Freshness Review — 2026-05-19 (Application Facade Maintenance Test Split)

`test_application_facade_maintenance.py` now owns the maintenance/release slice from `test_application_facade.py`: maintenance workspace environment-health rows, toolchain evidence/progress rows, and Release Package dry-run plan/count/progress behavior. `test_application_facade.py` keeps schedule/settings workspace, network worker state, process launch, maintenance command-lock coverage, Local API server, and backend-served WebView static integration tests.

```text
Task ID: God-file split Wave 5: application facade maintenance test extraction
Files inspected: tests/python/desktop/test_application_facade.py; tests/python/desktop/test_application_facade_maintenance.py
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_application_facade_maintenance -q; apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_application_facade -q; apps\desktop\runtime\Python\python.exe -m unittest discover -s tests\python\desktop -p "test_application_facade*.py" -q
```

## Freshness Review — 2026-05-19 (Application Facade Schedule Test Split)

`test_application_facade_schedule.py` now owns the Schedule workspace/app-state slice from `test_application_facade.py`: Schedule workspace rendering, backend schedule-stop watcher evidence, Schedule preview behavior, Schedule save confirmation, app-state preservation, and invalid-time rejection without writes. `test_application_facade.py` keeps settings workspace, network worker state, process launch, schedule-gated launch/Local API workflow coverage, maintenance command-lock coverage, Local API server, and backend-served WebView static integration tests.

```text
Task ID: God-file split Wave 5: application facade schedule test extraction
Files inspected: tests/python/desktop/test_application_facade.py; tests/python/desktop/test_application_facade_schedule.py
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_application_facade_schedule -q; apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_application_facade -q; apps\desktop\runtime\Python\python.exe -m unittest discover -s tests\python\desktop -p "test_application_facade*.py" -q
```

## Freshness Review — 2026-05-19 (Application Facade Settings Workspace Test Split)

`test_application_facade_settings_workspace.py` now owns the Settings workspace slice from `test_application_facade.py`: Settings workspace redaction, path/field metadata, validation warning surfacing, backend media-policy readiness evidence, tool-path evidence, and Settings Validate command-result envelope coverage. `test_application_facade.py` keeps network worker state, process launch, schedule-gated launch/Local API workflow coverage, maintenance command-lock coverage, Local API server, and backend-served WebView static integration tests.

```text
Task ID: God-file split Wave 5: application facade settings workspace test extraction
Files inspected: tests/python/desktop/test_application_facade.py; tests/python/desktop/test_application_facade_settings_workspace.py
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_application_facade_settings_workspace -q; apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_application_facade -q; apps\desktop\runtime\Python\python.exe -m unittest discover -s tests\python\desktop -p "test_application_facade*.py" -q
```

## Freshness Review — 2026-05-19 (Application Facade Network Test Split)

`test_application_facade_network.py` now owns the Network worker-state slice from `test_application_facade.py`: read-only `/api/network/workers` facade behavior for persisted coordinator in-flight state, worker-state metadata, progress bars, state-file evidence, and lifecycle-control absence. `test_application_facade.py` keeps process launch/control, schedule-gated launch/Local API workflow coverage, maintenance command-lock coverage, Local API server, and backend-served WebView static integration tests.

```text
Task ID: God-file split Wave 5: application facade network test extraction
Files inspected: tests/python/desktop/test_application_facade.py; tests/python/desktop/test_application_facade_network.py
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_application_facade_network -q; apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_application_facade -q; apps\desktop\runtime\Python\python.exe -m unittest discover -s tests\python\desktop -p "test_application_facade*.py" -q
```

## Freshness Review — 2026-05-19 (Application Facade Process Control Test Split)

`test_application_facade_process_control.py` now owns the process-control slice from `test_application_facade.py`: pipeline control pause/rescan flag contract coverage, invalid control-action rejection, and backend process-control lock fail-closed behavior. `test_application_facade.py` keeps process launch, schedule-gated launch/Local API workflow coverage, maintenance command-lock coverage, Local API server, and backend-served WebView static integration tests.

```text
Task ID: God-file split Wave 5: application facade process control test extraction
Files inspected: tests/python/desktop/test_application_facade.py; tests/python/desktop/test_application_facade_process_control.py
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_application_facade_process_control -q; apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_application_facade -q; apps\desktop\runtime\Python\python.exe -m unittest discover -s tests\python\desktop -p "test_application_facade*.py" -q
```

## Freshness Review — 2026-05-19 (Application Facade Process Launch Large Test Split)

`test_application_facade_process_launch.py` now owns the process-launch/preflight slice from `test_application_facade.py`: pipeline/audit/rerun launch handoff coverage, schedule-gated continuous launch behavior, backend launch-lock fail-closed behavior, schedule-stop watcher preservation when launch is blocked, and read-only launch preflight guard coverage. The remaining maintenance command-lock test moved into `test_application_facade_maintenance.py`, which now has 3 tests. `test_application_facade.py` keeps Local API server behavior and backend-served WebView static integration tests.

```text
Task ID: God-file split Wave 5: application facade process launch large extraction
Files inspected: tests/python/desktop/test_application_facade.py; tests/python/desktop/test_application_facade_process_launch.py; tests/python/desktop/test_application_facade_maintenance.py
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_application_facade_process_launch -q; apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_application_facade_maintenance -q; apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_application_facade -q; apps\desktop\runtime\Python\python.exe -m unittest discover -s tests\python\desktop -p "test_application_facade*.py" -q
```

## Freshness Review — 2026-05-19 (Backend Launch Readiness DTO)

`GET /api/launch/preflight` now returns nested `operator_readiness` with schema `desktop_launch_readiness.v1`. The backend-authored DTO summarizes target, start route, can-request-start posture, counts, non-ready checks, and final-authority text so the Launch readiness card and Start Decision Summary can display backend-authored readiness instead of deriving launch posture from DOM/cache state. `diagnosticsTailView.js` already prefers backend tail evidence (`evidence_authority=backend`) and labels older/no-evidence payload text scans as frontend advisory only.

```text
Task ID: Frontend readiness inference to backend DTOs
Files inspected: app/processes/preflight_facade.py; apps/desktop/webview/static/assets/launchReadinessView.js; apps/desktop/webview/static/assets/launchView.preflight.js; apps/desktop/webview/static/assets/launchView.scope.js; apps/desktop/webview/static/assets/diagnosticsTailView.js
Files changed: app/processes/preflight_facade.py; apps/desktop/webview/static/assets/launchReadinessView.js; apps/desktop/webview/static/assets/launchView.preflight.js; apps/desktop/webview/static/assets/launchView.scope.js; tests/python/desktop/test_application_facade_process_launch.py; tests/python/desktop/test_application_facade_local_api.py; docs/testing/TEST_COVERAGE_MATRIX.md
Validation: python -m unittest tests.python.desktop.test_application_facade_process_launch -q; python -m unittest tests.python.desktop.test_application_facade_local_api.LocalApiServerTests.test_local_api_health_is_public_and_snapshot_requires_token tests.python.desktop.test_application_facade_local_api.LocalApiServerTests.test_local_api_serves_read_only_web_prototype -q; python -m unittest tests.webview.test_webview_frontend_mutation_boundary -q; python -m unittest tests.webview.test_webview_browser_launch_queue_readiness_smoke -q
```

## Freshness Review — 2026-05-19 (Application Facade Local API and Web Static Large Test Split)

`test_application_facade_local_api.py` now owns the Local API server slice from `test_application_facade.py`: auth/public-token boundary coverage, diagnostics tail/state-summary allowlists, strict JSON response failure handling, settings reload error handling, process command auth and schedule-stop watcher behavior, backend shutdown safe/unsafe/force-cleanup/logging behavior, queue state source-scope/journaling, route workflow contracts, and backend-served Web prototype route coverage. `test_application_facade_web_static.py` now owns backend-served WebView/Tauri static integration, route-reference checks, frontend command allowlist checks, read-only/evidence panel guardrails, command feedback, shared table selection/accessibility helpers, diagnostics handoff wiring, page-scoped ID checks, and headless backend bootstrap payload coverage. `test_application_facade.py` is now a shared fixture/helper module for split application-facade tests and intentionally owns no tests.

```text
Task ID: God-file split Wave 5: application facade local API and Web static large extraction
Files inspected: tests/python/desktop/test_application_facade.py; tests/python/desktop/test_application_facade_local_api.py; tests/python/desktop/test_application_facade_web_static.py
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_application_facade_local_api -q; apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_application_facade_web_static -q; apps\desktop\runtime\Python\python.exe -m unittest discover -s tests\python\desktop -p "test_application_facade*.py" -q; apps\desktop\runtime\Python\python.exe -c "import tests.python.desktop.test_application_facade as m; print('fixture module import ok', hasattr(m, 'DummyFacadeService'), hasattr(m, '_resolved'))"
```

## Freshness Review — 2026-05-19 (WebView Design-Reference Static Guards)

`test_application_facade_web_static.py` now explicitly pins the rendered WebView design-reference boundaries that closed the stale High UI rows. Current Dashboard coverage allows the restored backend-owned Pause/Resume, Stop After Current, and Force Stop shortcuts while still blocking Dashboard-owned start, pending-drain, schedule-toggle, and raw mutation controls. Every rendered panel must declare either `data-panel-type="evidence"` or `data-panel-type="interactive"`, evidence panels must remain button-free/read-only, and all 13 rendered page H1 titles must match the canonical design-reference titles.

```text
Task ID: WebView UI command surface and page title compliance
Files inspected: apps/desktop/webview/static/partials/page-*.html; tests/python/desktop/test_application_facade_web_static.py
Files changed: apps/desktop/webview/static/partials/page-*.html; tests/python/desktop/test_application_facade_web_static.py; docs/testing/TEST_COVERAGE_MATRIX.md
Validation: python -m unittest tests.python.desktop.test_application_facade_web_static.ApplicationFacadeWebStaticTests.test_dashboard_does_not_duplicate_launch_publish_command_controls tests.python.desktop.test_application_facade_web_static.ApplicationFacadeWebStaticTests.test_webview_panel_types_and_evidence_panels_are_read_only tests.python.desktop.test_application_facade_web_static.ApplicationFacadeWebStaticTests.test_webview_page_h1_titles_match_design_reference -q; python -m unittest tests.python.desktop.test_application_facade_web_static -q
```

## Freshness Review — 2026-05-19 (Controller Feedback Test Split)

`test_controllers_feedback.py` now owns the feedback controller test from `test_controllers.py`: action-status toast display, previous-toast cancellation, auto-dismiss scheduling, toast dismissal, recent-action recording, and recent-action text propagation. `test_controllers.py` remains the broad desktop-controller boundary module for the other controller responsibilities.

```text
Task ID: God-file split Wave 5: controller feedback test extraction
Files inspected: tests/python/desktop/test_controllers.py; tests/python/desktop/test_controllers_feedback.py
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_controllers_feedback -q; apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_controllers -q; apps\desktop\runtime\Python\python.exe -m unittest discover -s tests\python\desktop -p "test_controllers*.py" -q
```

## Freshness Review — 2026-05-19 (Controller Worker Board Test Split)

`test_controllers_worker_board.py` now owns the live worker-board controller tests from `test_controllers.py`: snapshot row rendering, stale-row cleanup logging, snapshot failure fail-closed behavior, missing-worker-id logging, and per-row render failure isolation. `test_controllers.py` retains the broader WorkerController completion/report/abort coverage for a later split.

```text
Task ID: God-file split Wave 5: controller worker-board test extraction
Files inspected: tests/python/desktop/test_controllers.py; tests/python/desktop/test_controllers_worker_board.py
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_controllers_worker_board -q; apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_controllers -q; apps\desktop\runtime\Python\python.exe -m unittest discover -s tests\python\desktop -p "test_controllers*.py" -q
```

## Freshness Review — 2026-05-19 (Controller Audit Test Split)

`test_controllers_audit.py` now owns the audit controller tests from `test_controllers.py`: audit filtering/detail rendering, duplicate index behavior, multi-selection summaries, quick-view filters, context menu behavior, CSV apply/report metadata handling, creation-time failure logging, selected-row copy/open/priority actions, and selected/filtered CSV export. `test_controllers.py` remains the broad desktop-controller boundary module for the other controller responsibilities.

```text
Task ID: God-file split Wave 5: controller audit test extraction
Files inspected: tests/python/desktop/test_controllers.py; tests/python/desktop/test_controllers_audit.py
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_controllers_audit -q; apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_controllers -q; apps\desktop\runtime\Python\python.exe -m unittest discover -s tests\python\desktop -p "test_controllers*.py" -q
```

## Freshness Review — 2026-05-19 (Controller Failure Test Split)

`test_controllers_failure.py` now owns the failure controller tests from `test_controllers.py`: failure filtering/detail/trend rendering, filter reset, JSON/marker/clear-result application, selected-source open/copy/priority/audit-match actions, context menu behavior, and selected-failure re-run prioritization. `test_controllers.py` remains the broad desktop-controller boundary module for the other controller responsibilities.

```text
Task ID: God-file split Wave 5: controller failure test extraction
Files inspected: tests/python/desktop/test_controllers.py; tests/python/desktop/test_controllers_failure.py
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_controllers_failure -q; apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_controllers -q; apps\desktop\runtime\Python\python.exe -m unittest discover -s tests\python\desktop -p "test_controllers*.py" -q
```

## Freshness Review — 2026-05-19 (Controller Completed Test Split)

`test_controllers_completed.py` now owns the completed controller tests from `test_controllers.py`: completed-tree sorting/tags/detail rendering, CPU fallback encoder display, route breakdown chart updates, encode-speed history read/write/migration behavior, and backfill result handling. `test_controllers.py` remains the broad desktop-controller boundary module for the other controller responsibilities.

```
Task ID: God-file split Wave 5: controller completed test extraction
Files inspected: tests/python/desktop/test_controllers.py; tests/python/desktop/test_controllers_completed.py
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_controllers_completed -q; apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_controllers -q; apps\desktop\runtime\Python\python.exe -m unittest discover -s tests\python\desktop -p "test_controllers*.py" -q
```

## Freshness Review — 2026-05-19 (Controller Settings Test Split)

`test_controllers_settings.py` now owns the settings controller tests from `test_controllers.py`: profile save/load, list/path helper behavior, dirty-state and structured-control toggles, structured-control failure logging, unsaved-start prompt handling, config form validation/preview, missing saved-config diff logging, and save-in-place reload behavior. `test_controllers.py` remains the broad desktop-controller boundary module for the other controller responsibilities.

```
Task ID: God-file split Wave 5: controller settings test extraction
Files inspected: tests/python/desktop/test_controllers.py; tests/python/desktop/test_controllers_settings.py
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_controllers_settings -q; apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_controllers -q; apps\desktop\runtime\Python\python.exe -m unittest discover -s tests\python\desktop -p "test_controllers*.py" -q
```

## Freshness Review — 2026-05-19 (Controller File Actions Test Split)

`test_controllers_file_actions.py` now owns the file-actions controller test from `test_controllers.py`: resolved log/local-base/report/config open handoffs, latest failure/audit CSV lookups, loaded audit CSV handoff, and empty path warning behavior. `test_controllers.py` remains the broad desktop-controller boundary module for the other controller responsibilities.

```
Task ID: God-file split Wave 5: controller file-actions test extraction
Files inspected: tests/python/desktop/test_controllers.py; tests/python/desktop/test_controllers_file_actions.py
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_controllers_file_actions -q; apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_controllers -q; apps\desktop\runtime\Python\python.exe -m unittest discover -s tests\python\desktop -p "test_controllers*.py" -q
```

## Freshness Review — 2026-05-19 (Controller Maintenance Test Split)

`test_controllers_maintenance.py` now owns the maintenance controller tests from `test_controllers.py`: progress-file skeleton reset, resolved progress-path updates, reset action/status recording, confirmation dialogs, environment-health background dispatch, and environment-health result formatting. `test_controllers.py` remains the broad desktop-controller boundary module for the other controller responsibilities.

```
Task ID: God-file split Wave 5: controller maintenance test extraction
Files inspected: tests/python/desktop/test_controllers.py; tests/python/desktop/test_controllers_maintenance.py
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_controllers_maintenance -q; apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_controllers -q; apps\desktop\runtime\Python\python.exe -m unittest discover -s tests\python\desktop -p "test_controllers*.py" -q
```

## Freshness Review — 2026-05-19 (Controller Folder Policy Test Split)

`test_controllers_folder_policy.py` now owns the folder-policy controller tests from `test_controllers.py`: validation result status text, action-status text, command history action recording, success info dialog, and error/warning detail dialog formatting. `test_controllers.py` remains the broad desktop-controller boundary module for the other controller responsibilities.

```
Task ID: God-file split Wave 5: controller folder-policy test extraction
Files inspected: tests/python/desktop/test_controllers.py; tests/python/desktop/test_controllers_folder_policy.py
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_controllers_folder_policy -q; apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_controllers -q; apps\desktop\runtime\Python\python.exe -m unittest discover -s tests\python\desktop -p "test_controllers*.py" -q
```

## Freshness Review — 2026-05-19 (Controller Release Test Split)

`test_controllers_release.py` now owns the release controller tests from `test_controllers.py`: release package success status/action handling, manifest and zip path storage, manifest summary output formatting, and timeout output without success action recording. `test_controllers.py` remains the broad desktop-controller boundary module for the other controller responsibilities.

```
Task ID: God-file split Wave 5: controller release test extraction
Files inspected: tests/python/desktop/test_controllers.py; tests/python/desktop/test_controllers_release.py
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_controllers_release -q; apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_controllers -q; apps\desktop\runtime\Python\python.exe -m unittest discover -s tests\python\desktop -p "test_controllers*.py" -q
```

## Freshness Review — 2026-05-19 (Controller Pending Publish Test Split)

`test_controllers_pending_publish.py` now owns the pending-publish controller tests from `test_controllers.py`: dashboard summary application, missing parked payload detail text, tree row tags, default selection/focus/scroll behavior, and manifest/sidecar detail rendering. `test_controllers.py` remains the broad desktop-controller boundary module for the other controller responsibilities.

```
Task ID: God-file split Wave 5: controller pending-publish test extraction
Files inspected: tests/python/desktop/test_controllers.py; tests/python/desktop/test_controllers_pending_publish.py
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_controllers_pending_publish -q; apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_controllers -q; apps\desktop\runtime\Python\python.exe -m unittest discover -s tests\python\desktop -p "test_controllers*.py" -q
```

## Freshness Review — 2026-05-19 (Controller Rerun Test Split)

`test_controllers_rerun.py` now owns the rerun controller preview test from `test_controllers.py`: disabled rows, unsafe policy overrides, duplicate planned output hints, status text, and preview text rendering. `test_controllers.py` remains the broad desktop-controller boundary module for the other controller responsibilities.

```
Task ID: God-file split Wave 5: controller rerun test extraction
Files inspected: tests/python/desktop/test_controllers.py; tests/python/desktop/test_controllers_rerun.py
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_controllers_rerun -q; apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_controllers -q; apps\desktop\runtime\Python\python.exe -m unittest discover -s tests\python\desktop -p "test_controllers*.py" -q
```

## Freshness Review — 2026-05-19 (Controller Work Guard Test Split)

`test_controllers_work_guard.py` now owns the work-guard controller test from `test_controllers.py`: active external pipeline progress blocks start/close decisions, stop-requested progress no longer counts as active work, and related bundle process discovery still reports blocking PIDs. `test_controllers.py` remains the broad desktop-controller boundary module for the other controller responsibilities.

```
Task ID: God-file split Wave 5: controller work-guard test extraction
Files inspected: tests/python/desktop/test_controllers.py; tests/python/desktop/test_controllers_work_guard.py
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_controllers_work_guard -q; apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_controllers -q; apps\desktop\runtime\Python\python.exe -m unittest discover -s tests\python\desktop -p "test_controllers*.py" -q
```

## Freshness Review — 2026-05-19 (Controller App State Test Split)

`test_controllers_app_state.py` now owns the app-state controller tests from `test_controllers.py`: persisted column/view state and marker choice, persisted-state widget failure logging, refresh-state snapshot/autoload behavior, polling completed-manifest refresh behavior, and apply-snapshot-to-UI updates. `test_controllers.py` remains the broad desktop-controller boundary module for the other controller responsibilities.

```
Task ID: God-file split Wave 5: controller app-state test extraction
Files inspected: tests/python/desktop/test_controllers.py; tests/python/desktop/test_controllers_app_state.py
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_controllers_app_state -q; apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_controllers -q; apps\desktop\runtime\Python\python.exe -m unittest discover -s tests\python\desktop -p "test_controllers*.py" -q
```

## Freshness Review — 2026-05-19 (Controller Status Server Test Split)

`test_controllers_status_server.py` now owns the status-server boundary tests from `test_controllers.py`: status-server path redaction, shutdown-failure logging, pause-flag read-failure logging, and non-finite telemetry JSON safety. `test_controllers.py` remains the broad desktop-controller boundary module for the other controller responsibilities.

```
Task ID: God-file split Wave 5: controller status-server test extraction
Files inspected: tests/python/desktop/test_controllers.py; tests/python/desktop/test_controllers_status_server.py
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_controllers_status_server -q; apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_controllers -q; apps\desktop\runtime\Python\python.exe -m unittest discover -s tests\python\desktop -p "test_controllers*.py" -q
Findings: 4 moved status-server tests, 118 remaining parent controller tests, and 122 controller-discovery tests passed.
Open questions: None.
Risk: Low — test-file split only; no production code, WebView assets, API routes, controller behavior, process lifecycle behavior, media policy, or file mutation paths changed.
```

## Freshness Review — 2026-05-19 (Network Done/Release Test Split)

`test_network_done_release.py` now owns the done/release reporting block from `test_network_persistence.py`: worker done/release reporting, accepted-report cleanup behavior, pending done-report save failures, bounded done/release diagnostics, unstartable-claim release reporting, and `DoneRequest` completion/publish/queue-terminal field preservation. `test_network_persistence.py` remains the coordinator startup behavior module and now has only coordinator-startup imports.

```
Task ID: God-file split Wave 5: network done/release test extraction
Files inspected: tests/python/desktop/test_network_persistence.py; tests/python/desktop/test_network_done_release.py
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_network_done_release -q; apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_network_persistence -q; apps\desktop\runtime\Python\python.exe -m unittest discover -s tests\python\desktop -p "test_network*.py" -q
Findings: 16 moved done/release tests, 8 remaining coordinator-startup persistence tests, and 243 network-discovery tests passed.
Open questions: None.
Risk: Low — test-file split only; no production code, WebView assets, API routes, network runtime behavior, command contracts, done/release behavior, media policy, or file mutation paths changed.
```

## Freshness Review — 2026-05-19 (Network Crash Recovery Test Split)

`test_network_crash_recovery.py` now owns the crash recovery block from `test_network_persistence.py`: crash recovery done-post retry/fallback behavior, pending done-report recovery, bounded failure diagnostics, malformed/unreadable worker-state cleanup, cluster-log failure handling, and accepted-report cleanup failure handling. `test_network_persistence.py` remains the done/release reporting and coordinator startup test module.

```
Task ID: God-file split Wave 5: network crash recovery test extraction
Files inspected: tests/python/desktop/test_network_persistence.py; tests/python/desktop/test_network_crash_recovery.py
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_network_crash_recovery -q; apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_network_persistence -q; apps\desktop\runtime\Python\python.exe -m unittest discover -s tests\python\desktop -p "test_network*.py" -q
Findings: 12 moved crash-recovery tests, 24 remaining network-persistence tests, and 243 network-discovery tests passed.
Open questions: None.
Risk: Low — test-file split only; no production code, WebView assets, API routes, network runtime behavior, command contracts, crash-recovery behavior, media policy, or file mutation paths changed.
```

## Freshness Review — 2026-05-19 (Network In-Flight Registry Test Split)

`test_network_inflight_registry.py` now owns the in-flight registry persistence block from `test_network_persistence.py`: concurrent registry saves, registry temporary-file cleanup diagnostics, coordinator state-transition diagnostics on registry save failure, non-finite estimated-size sanitization, non-finite network config JSON rejection, and malformed registry-row load handling. `test_network_persistence.py` remains the crash recovery, done/release reporting, and coordinator startup test module.

```
Task ID: God-file split Wave 5: network in-flight registry test extraction
Files inspected: tests/python/desktop/test_network_persistence.py; tests/python/desktop/test_network_inflight_registry.py
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_network_inflight_registry -q; apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_network_persistence -q; apps\desktop\runtime\Python\python.exe -m unittest discover -s tests\python\desktop -p "test_network*.py" -q
Findings: 6 moved in-flight registry tests, 36 remaining network-persistence tests, and 243 network-discovery tests passed.
Open questions: None.
Risk: Low — test-file split only; no production code, WebView assets, API routes, network runtime behavior, command contracts, in-flight registry behavior, media policy, or file mutation paths changed.
```

## Freshness Review — 2026-05-19 (Network Worker-State Test Split)

`test_network_worker_state.py` now owns the worker-state persistence block from `test_network_persistence.py`: worker-state atomic write replacement, job identity and pending done-report round trips, worker-state and pending-done save-failure operator visibility, non-finite worker-state JSON rejection, temporary-file cleanup diagnostics, guarded worker-state clear failure visibility, and accepted-report cleanup context. `test_network_persistence.py` remains the in-flight registry persistence, crash recovery, done/release reporting, and coordinator startup test module.

```
Task ID: God-file split Wave 5: network worker-state test extraction
Files inspected: tests/python/desktop/test_network_persistence.py; tests/python/desktop/test_network_worker_state.py
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_network_worker_state -q; apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_network_persistence -q; apps\desktop\runtime\Python\python.exe -m unittest discover -s tests\python\desktop -p "test_network*.py" -q
Findings: 10 moved worker-state tests, 42 remaining network-persistence tests, and 243 network-discovery tests passed.
Open questions: None.
Risk: Low — test-file split only; no production code, WebView assets, API routes, network runtime behavior, command contracts, worker-state behavior, media policy, or file mutation paths changed.
```

## Freshness Review — 2026-05-19 (Network Firewall Test Split)

`test_network_firewall.py` now owns the firewall helper block from `test_network_persistence.py`: firewall rule parsing, add-rule command construction, bounded `netsh` subprocess checks, nonzero check warnings, admin-failure messaging, and `netsh` output surfacing. `test_network_persistence.py` remains the worker-state persistence, in-flight registry persistence, crash recovery, done/release reporting, and coordinator startup test module.

```
Task ID: God-file split Wave 5: network firewall test extraction
Files inspected: tests/python/desktop/test_network_persistence.py; tests/python/desktop/test_network_firewall.py
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_network_firewall -q; apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_network_persistence -q; apps\desktop\runtime\Python\python.exe -m unittest discover -s tests\python\desktop -p "test_network*.py" -q
Findings: 6 moved firewall tests, 52 remaining network-persistence tests, and 243 network-discovery tests passed.
Open questions: None.
Risk: Low — test-file split only; no production code, WebView assets, API routes, network runtime behavior, command contracts, firewall behavior, media policy, or file mutation paths changed.
```

## Freshness Review — 2026-05-19 (Network Protocol Runtime Test Split)

`test_network_protocol_runtime.py` now owns the protocol/registry runtime and worker-claim block from `test_network_persistence.py`: heartbeat and done-request non-finite validation, in-flight registry runtime snapshot sanitization, reclaimed heartbeat abort scheduling, worker claim-record construction and invalid-claim diagnostics, path remap handoff behavior, completion/ops/release/metadata/crash done-request builders, and worker poll interval/retry-hint policy. `test_network_persistence.py` remains the firewall, worker-state persistence, in-flight registry persistence, crash recovery, done/release reporting, and coordinator startup test module.

```
Task ID: God-file split Wave 5: network protocol runtime test extraction
Files inspected: tests/python/desktop/test_network_persistence.py; tests/python/desktop/test_network_protocol_runtime.py
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_network_protocol_runtime -q; apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_network_persistence tests.python.desktop.test_network_protocol_runtime tests.python.desktop.test_network_coordinator_http tests.python.desktop.test_network_coordinator_helpers tests.python.desktop.test_network_worker_runtime tests.python.desktop.test_network_workflow tests.python.desktop.test_network_security -q; apps\desktop\runtime\Python\python.exe -m unittest discover -s tests\python\desktop -p "test_network*.py" -q
Findings: 16 moved protocol/runtime tests, 58 remaining network-persistence tests, 205 split network tests, and 243 network-discovery tests passed.
Open questions: None.
Risk: Low — test-file split only; no production code, WebView assets, API routes, network runtime behavior, command contracts, media policy, or file mutation paths changed.
```

## Freshness Review — 2026-05-19 (Network Coordinator HTTP Test Split)

`test_network_coordinator_http.py` now owns the coordinator HTTP and bounded HTTP JSON block from `test_network_persistence.py`: authenticated HTTP JSON GET/POST helpers, non-finite payload rejection, invalid/non-strict JSON response handling, coordinator `_send_json` and OPTIONS failure handling, invalid request-body and identifier rejection, heartbeat/done registry failure responses, reclaimed heartbeat cluster-log failure handling, `/api/log` missing/sanitized field behavior, worker timestamp preservation warnings, cluster-log append failures, and bounded HTTP error previews. `test_network_persistence.py` remains the protocol/registry, worker-state persistence, crash recovery, done/release reporting, firewall, and coordinator startup test module.

```
Task ID: God-file split Wave 5: network coordinator HTTP test extraction
Files inspected: tests/python/desktop/test_network_persistence.py; tests/python/desktop/test_network_coordinator_http.py
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_network_coordinator_http -q; apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_network_persistence tests.python.desktop.test_network_coordinator_http tests.python.desktop.test_network_coordinator_helpers tests.python.desktop.test_network_worker_runtime tests.python.desktop.test_network_workflow tests.python.desktop.test_network_security -q; apps\desktop\runtime\Python\python.exe -m unittest discover -s tests\python\desktop -p "test_network*.py" -q
Findings: 20 moved network coordinator-HTTP tests, 74 remaining network-persistence tests, 205 split network tests, and 243 network-discovery tests passed.
Open questions: None.
Risk: Low — test-file split only; no production code, WebView assets, API routes, network runtime behavior, command contracts, media policy, or file mutation paths changed.
```

## Freshness Review — 2026-05-19 (Network Coordinator Helper Test Split)

`test_network_coordinator_helpers.py` now owns the coordinator helper/policy block from `test_network_persistence.py`: coordinator URL compatibility, share-block formatting, coordinator and worker auth probes, coordinator HTTP query/body helper validation, coordinator policy coercion and retry hints, heartbeat/reaper fallback logging, encode-config snapshot overrides, coordinator encode-config snapshot delegation, and prior-failure policy handling. `test_network_persistence.py` remains the protocol/registry, HTTP JSON/coordinator handler, worker-state persistence, crash recovery, done/release reporting, firewall, and coordinator startup test module.

```
Task ID: God-file split Wave 5: network coordinator helper test extraction
Files inspected: tests/python/desktop/test_network_persistence.py; tests/python/desktop/test_network_coordinator_helpers.py
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_network_coordinator_helpers -q; apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_network_persistence tests.python.desktop.test_network_worker_runtime tests.python.desktop.test_network_workflow tests.python.desktop.test_network_security -q; apps\desktop\runtime\Python\python.exe -m unittest discover -s tests\python\desktop -p "test_network*.py" -q
Findings: 14 moved network coordinator-helper tests, 94 remaining network-persistence tests, 191 persistence/worker-runtime/workflow/security tests, and 243 network-discovery tests passed.
Open questions: None.
Risk: Low — test-file split only; no production code, WebView assets, API routes, network runtime behavior, command contracts, media policy, or file mutation paths changed.
```

## Freshness Review — 2026-05-19 (Network Worker Runtime Test Split)

`test_network_worker_runtime.py` now owns the first worker runtime/resilience block from `test_network_persistence.py`: diagnostic preview bounds, daemon-thread start failure handling, worker source-path mapping, worker status callback failures, cluster-log post failures, poll-loop claim/release behavior, heartbeat start/post/snapshot failures, malformed claim responses, reclaimed heartbeat aborts, and worker claim handoff diagnostics. `test_network_persistence.py` remains the protocol/registry, coordinator helper, worker-state persistence, crash recovery, done/release reporting, and coordinator startup test module.

```
Task ID: God-file split Wave 5: network worker runtime test extraction
Files inspected: tests/python/desktop/test_network_persistence.py; tests/python/desktop/test_network_worker_runtime.py
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_network_worker_runtime -q; apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_network_persistence tests.python.desktop.test_network_workflow tests.python.desktop.test_network_security -q; apps\desktop\runtime\Python\python.exe -m unittest discover -s tests\python\desktop -p "test_network*.py" -q
Findings: 32 moved network worker-runtime tests, 108 remaining network-persistence tests, 173 persistence/workflow/security tests, and 243 network-discovery tests passed.
Open questions: None.
Risk: Low — test-file split only; no production code, WebView assets, API routes, network runtime behavior, command contracts, media policy, or file mutation paths changed.
```

## Freshness Review — 2026-05-19 (Network Workflow Test Split)

`test_network_workflow.py` now owns the former `WorkflowEnhancementTests` coverage from `test_network_persistence.py`: local claim/release save-failure resilience, heartbeat and done/release HTTP outcomes, queue-removal scheduling, coordinator reaper/shutdown/startup hardening, claim/done/release edge cases, cluster-log formatting, retry-hint calculation, and worker wait policy. `test_network_persistence.py` remains the broader worker/coordinator lifecycle and persistence test module.

```
Task ID: God-file split Wave 5: network workflow test extraction
Files inspected: tests/python/desktop/test_network_persistence.py; tests/python/desktop/test_network_workflow.py
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_network_workflow -q; apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_network_security tests.python.desktop.test_network_persistence -q; apps\desktop\runtime\Python\python.exe -m unittest discover -s tests\python\desktop -p "test_network*.py" -q
Findings: 40 moved network-workflow tests, 140 remaining network-persistence tests, 25 network-security tests, and 243 network-discovery tests passed.
Open questions: None.
Risk: Low — test-file split only; no production code, WebView assets, API routes, network runtime behavior, command contracts, media policy, or file mutation paths changed.
```

## Freshness Review — 2026-05-19 (Network Security Test Split)

`test_network_security.py` now owns the former `NetworkSecurityTests` coverage from `test_network_persistence.py`: auth-token rejection, token rotation persistence failures, registry foreign-worker rejection, recent-completion grace, capped worker HTTP reads, coordinator URL validation, coordinator request body caps/read failures, worker identity/name validation, hostname fallback, and log-entry sanitization. `test_network_persistence.py` remains the worker/coordinator lifecycle, persistence, and workflow test module.

```
Task ID: God-file split Wave 5: network security test extraction
Files inspected: tests/python/desktop/test_network_persistence.py; tests/python/desktop/test_network_security.py
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_network_security -q; apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_network_persistence -q; apps\desktop\runtime\Python\python.exe -m unittest discover -s tests\python\desktop -p "test_network*.py" -q
Findings: 25 moved network-security tests, 180 remaining network-persistence tests, and 243 network-discovery tests passed.
Open questions: None.
Risk: Low — test-file split only; no production code, WebView assets, API routes, network runtime behavior, command contracts, media policy, or file mutation paths changed.
```

## Freshness Review — 2026-05-19 (WebView Static Include Layer)

The Local API render path now expands allowlisted `<!-- mp-include: partials/*.html -->` markers before replacing the backend bootstrap placeholder. Coverage verifies include expansion, unsafe include rejection, rendered DOM/nav inventory parsing, release-package include reference checks, and the served WebView prototype.

```
Task ID: God-file split Wave 4: index Home partial extraction
Files inspected: src/mediapipeline/desktop/api/static_files.py; src/mediapipeline/desktop/api/static_files_policy.py; apps/desktop/webview/static/index.html; apps/desktop/webview/static/partials/page-home.html; tests/python/desktop/test_api_static_files_policy.py; tests/python/desktop/test_webview_browser_home_live_state_smoke.py; tests/python/desktop/test_webview_browser_sample_validation_smoke.py; tests/python/desktop/test_webview_command_evidence_smoke.py; tests/python/desktop/test_webview_real_media_smoke.py
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_api_static_files_policy tests.webview.test_webview_css_design_tokens tests.webview.test_webview_navigation_static tests.webview.test_webview_inventory_docs tests.webview.test_webview_frontend_mutation_boundary tests.webview.test_webview_network_read_only_boundary -q
Findings: 37 focused rendered WebView/static tests passed. Rendered index proof returned HTTP-render-equivalent HTML with Home `data-page-panel="home"`, `daily-driver-status`, `daily-driver-rows`, `home-active-work-status`, `sample-validation-status`, `sample-validation-worksheet-rows`, `sample-validation-preview-button`, `sample-validation-append-button`, `sample-validation-records`, Home-before-Telemetry ordering, `window.MEDIA_PIPELINE_BOOTSTRAP` token payload, and no remaining `mp-include` markers. Broader validation passed: 111 application-facade tests, 107 focused WebView/static/Tauri tests, browser Home live-state smoke, browser sample-validation smoke, command-evidence smoke, 2 real-media WebView smoke tests, repo hygiene, release verifier parser check, BOM check for `index.html` and `partials/page-home.html`, project-owned sentinel search, and Local API close/reopen proof at `http://127.0.0.1:16215` with health ok, startup log server-listening step 14/14, close-readiness safe/no active work, 50 contract routes, Home HTML markers, token bootstrap payload, no `mp-include`, and selected assets HTTP 200.
Open questions: None.
Risk: Low — WebView markup include/static-test only; `crossPageContextView*.js`, sample-validation routes, command-history reads, preview/append command ownership, script order, and media mutation boundaries are unchanged.
```

```
Task ID: God-file split Wave 4: index Settings partial extraction
Files inspected: src/mediapipeline/desktop/api/static_files.py; src/mediapipeline/desktop/api/static_files_policy.py; apps/desktop/webview/static/index.html; apps/desktop/webview/static/partials/page-settings.html; tests/python/desktop/test_api_static_files_policy.py; tests/python/desktop/test_webview_browser_settings_launch_smoke.py; tests/python/desktop/test_webview_browser_launch_queue_readiness_smoke.py; tests/python/desktop/test_webview_browser_sample_validation_smoke.py
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_api_static_files_policy tests.webview.test_webview_css_design_tokens tests.webview.test_webview_navigation_static tests.webview.test_webview_inventory_docs tests.webview.test_webview_frontend_mutation_boundary tests.webview.test_webview_network_read_only_boundary -q
Findings: 37 focused rendered WebView/static tests passed. Rendered index proof returned HTTP-render-equivalent HTML with Settings `data-page-panel="settings"`, `settings-validate-button`, `settings-patch-json`, `settings-save-patch-button`, `settings-audio-builder-status`, `settings-network-builder-status`, `settings-raw-triage-rows`, Diagnostics-before-Settings ordering, `window.MEDIA_PIPELINE_BOOTSTRAP` token payload, and no remaining `mp-include` markers. Broader validation passed: 111 application-facade tests, 107 focused WebView/static/Tauri tests, Settings/Launch handoff browser smoke, Launch/Queue readiness browser smoke, sample-validation browser smoke, 2 real-media WebView smoke tests, browser Home live-state smoke, repo hygiene, release verifier parser check, BOM check for `index.html` and `partials/page-settings.html`, project-owned sentinel search, and Local API close/reopen proof at `http://127.0.0.1:24415` with health ok, startup log server-listening step 14/14, close-readiness safe/no active work, 50 contract routes, Settings HTML markers, token bootstrap payload, no `mp-include`, and selected assets HTTP 200.
Open questions: None.
Risk: Low — WebView markup include/static-test only; `settingsView*.js`, Settings builder child load order, settings preview/save routes, backend validation, command history, script order, and media mutation boundaries are unchanged.
```

```
Task ID: God-file split Wave 4: index Diagnostics partial extraction
Files inspected: src/mediapipeline/desktop/api/static_files.py; src/mediapipeline/desktop/api/static_files_policy.py; apps/desktop/webview/static/index.html; apps/desktop/webview/static/partials/page-diagnostics.html; tests/python/desktop/test_api_static_files_policy.py; tests/python/desktop/test_webview_browser_diagnostics_handoff_smoke.py; tests/python/desktop/test_webview_browser_lifecycle_smoke.py; tests/python/desktop/test_webview_command_evidence_smoke.py
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_api_static_files_policy tests.webview.test_webview_css_design_tokens tests.webview.test_webview_navigation_static tests.webview.test_webview_inventory_docs tests.webview.test_webview_frontend_mutation_boundary tests.webview.test_webview_network_read_only_boundary -q
Findings: 37 focused rendered WebView/static tests passed. Rendered index proof returned HTTP-render-equivalent HTML with Diagnostics `data-page-panel="diagnostics"`, `diagnostics-triage-status`, `diagnostics-log-rows`, `diagnostics-command-drilldown-rows`, `backend-shutdown-button`, `api-contract-rows`, Diagnostics-before-Settings ordering, `window.MEDIA_PIPELINE_BOOTSTRAP` token payload, and no remaining `mp-include` markers. Broader validation passed: 111 application-facade tests, 107 focused WebView/static/Tauri tests, Diagnostics handoff browser smoke, lifecycle browser smoke, command-evidence smoke, 2 real-media WebView smoke tests, browser Home live-state smoke, repo hygiene, release verifier parser check, project-owned sentinel search, and Local API close/reopen proof at `http://127.0.0.1:23964` with health ok, startup log server-listening step 14/14, close-readiness safe/no active work, 50 contract routes, Diagnostics HTML markers, token bootstrap payload, no `mp-include`, and selected assets HTTP 200.
Open questions: None.
Risk: Low — WebView markup include/static-test only; `diagnosticsView*.js`, `diagnosticsBridge.js`, backend lifecycle/shutdown routes, diagnostics open/tail target-key allowlists, and API contract reads are unchanged.
```

```
Task ID: God-file split Wave 4: index Pending Publish partial extraction
Files inspected: src/mediapipeline/desktop/api/static_files.py; src/mediapipeline/desktop/api/static_files_policy.py; apps/desktop/webview/static/index.html; apps/desktop/webview/static/partials/page-pending.html; tests/python/desktop/test_api_static_files_policy.py; tests/python/desktop/test_webview_browser_pending_drain_guard_smoke.py; tests/python/desktop/test_webview_browser_completed_pending_proof_smoke.py; tests/python/desktop/test_webview_browser_diagnostics_handoff_smoke.py; tests/python/desktop/test_webview_row_detail_smoke.py
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_api_static_files_policy tests.webview.test_webview_css_design_tokens tests.webview.test_webview_navigation_static tests.webview.test_webview_inventory_docs tests.webview.test_webview_frontend_mutation_boundary tests.webview.test_webview_network_read_only_boundary -q
Findings: 37 focused rendered WebView/static tests passed. Rendered index proof returned HTTP-render-equivalent HTML with Pending `data-page-panel="pending"`, `class="workflow-table pending-table"`, `pending-rows`, `pending-drain-button`, `pending-drain-decision-rows`, `pending-post-drain-trust-rows`, Pending-before-Rename ordering, `window.MEDIA_PIPELINE_BOOTSTRAP` token payload, and no remaining `mp-include` markers. Broader validation passed: 111 application-facade tests, 107 focused WebView/static/Tauri tests, repo hygiene, browser Home live-state smoke, browser large-table smoke, Pending drain guard smoke, Completed/Pending proof browser smoke, row-detail smoke, Diagnostics handoff browser smoke, 2 real-media WebView smoke tests, release verifier parser check, project-owned sentinel search, and Local API close/reopen proof at `http://127.0.0.1:37382` with health ok, startup log server-listening step 14/14, close-readiness safe/no active work, 50 contract routes, Pending HTML markers, token bootstrap payload, no `mp-include`, and selected assets HTTP 200.
Open questions: None.
Risk: Low — WebView markup include/static-test only; `pendingPublishView*.js`, pending publish/open/recovery routes, guarded drain launch behavior, backend-authored drain safety, and source/open allowlists are unchanged.
```

```
Task ID: God-file split Wave 4: index Queue partial extraction
Files inspected: src/mediapipeline/desktop/api/static_files.py; src/mediapipeline/desktop/api/static_files_policy.py; apps/desktop/webview/static/index.html; apps/desktop/webview/static/partials/page-queue.html; tests/python/desktop/test_api_static_files_policy.py; tests/python/desktop/test_webview_browser_large_table_smoke.py; tests/python/desktop/test_webview_browser_launch_queue_readiness_smoke.py; tests/python/desktop/test_webview_browser_diagnostics_handoff_smoke.py; tests/python/desktop/test_webview_row_detail_smoke.py
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_api_static_files_policy tests.webview.test_webview_css_design_tokens tests.webview.test_webview_navigation_static tests.webview.test_webview_inventory_docs tests.webview.test_webview_frontend_mutation_boundary tests.webview.test_webview_network_read_only_boundary -q
Findings: 37 focused rendered WebView/static tests passed. Rendered index proof returned HTTP-render-equivalent HTML with Queue `data-page-panel="queue"`, `class="workflow-table queue-table"`, `queue-rows`, `queue-backend-scope-rows`, `queue-launch-decision-rows`, `fo-drawer`, Queue-before-Completed ordering, `window.MEDIA_PIPELINE_BOOTSTRAP` token payload, and no remaining `mp-include` markers. Broader validation passed: 111 application-facade tests, 107 focused WebView/static/Tauri tests, repo hygiene, browser Home live-state smoke, browser large-table smoke, Launch/Queue readiness browser smoke, row-detail smoke, Diagnostics handoff browser smoke, 2 real-media WebView smoke tests, release verifier parser check, project-owned sentinel search, and Local API close/reopen proof at `http://127.0.0.1:22568` with health ok, startup log server-listening step 14/14, close-readiness safe/no active work, 50 contract routes, Queue HTML markers, token bootstrap payload, no `mp-include`, and selected assets HTTP 200.
Open questions: None.
Risk: Low — WebView markup include/static-test only; `queueView.js`, queue priority/strategy/file override/open routes, backend-authored queue/launch scope decisions, and source-open allowlists are unchanged.
```

```
Task ID: God-file split Wave 4: index Completed partial extraction
Files inspected: src/mediapipeline/desktop/api/static_files.py; src/mediapipeline/desktop/api/static_files_policy.py; apps/desktop/webview/static/index.html; apps/desktop/webview/static/partials/page-completed.html; tests/python/desktop/test_api_static_files_policy.py; tests/python/desktop/test_webview_css_design_tokens.py; tests/python/desktop/test_webview_browser_completed_pending_proof_smoke.py; tests/python/desktop/test_webview_row_detail_smoke.py
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_api_static_files_policy tests.webview.test_webview_css_design_tokens tests.webview.test_webview_navigation_static tests.webview.test_webview_inventory_docs tests.webview.test_webview_frontend_mutation_boundary tests.webview.test_webview_network_read_only_boundary -q
Findings: 37 focused rendered WebView/static tests passed. Rendered index proof returned HTTP-render-equivalent HTML with Completed `data-page-panel="completed"`, `class="workflow-table completed-table"`, `completed-rows`, `completed-real-media-proof-rows`, `completed-output-acceptance-rows`, `window.MEDIA_PIPELINE_BOOTSTRAP` token payload, and no remaining `mp-include` markers. Broader validation passed: 111 application-facade tests, 107 focused WebView/static/Tauri tests, repo hygiene, browser Home live-state smoke, browser large-table smoke, 2 real-media WebView smoke tests, Completed/Pending proof browser smoke, row-detail smoke, release verifier parser check, project-owned sentinel search, and Local API close/reopen proof at `http://127.0.0.1:25942` with health ok, startup log server-listening step 14/14, close-readiness safe/no active work, 50 contract routes, Completed HTML markers, token bootstrap payload, no `mp-include`, and selected assets HTTP 200.
Open questions: None.
Risk: Low — WebView markup include/static-test only; `completedView*.js`, `/api/completed`, `/api/publish-reconciliation`, `/api/completed/open`, backend-selected open targets, and output proof policy are unchanged.
```

```
Task ID: God-file split Wave 4: index Launch partial extraction
Files inspected: src/mediapipeline/desktop/api/static_files.py; src/mediapipeline/desktop/api/static_files_policy.py; apps/desktop/webview/static/index.html; apps/desktop/webview/static/partials/page-launch.html; tests/python/desktop/test_api_static_files_policy.py; tests/python/desktop/test_application_facade.py; tests/python/desktop/test_webview_real_media_smoke.py
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_api_static_files_policy tests.python.desktop.test_application_facade.ApplicationFacadeTests.test_local_api_static_file_helpers_render_bootstrap_and_assets tests.python.desktop.test_application_facade.LocalApiServerTests.test_local_api_serves_read_only_web_prototype tests.webview.test_webview_navigation_static tests.webview.test_webview_inventory_docs tests.webview.test_webview_frontend_mutation_boundary tests.webview.test_webview_network_read_only_boundary -q
Findings: 34 focused tests passed. Rendered index proof returned HTTP-render-equivalent HTML with Launch `data-page-panel="launch"`, `launch-backend-preflight-rows`, `launch-start-decision-rows`, `launch-command-review-rows`, `pipeline-start-button`, following Reports page, `window.MEDIA_PIPELINE_BOOTSTRAP` token payload, 1,026 DOM IDs, and no remaining `mp-include` markers. UTF-8 byte check confirmed `index.html` and `partials/page-launch.html` do not begin with a BOM. Broader validation passed: 111 application-facade tests, 107 focused WebView/static/Tauri tests, 2 real-media WebView smoke tests, repo hygiene, browser Home live-state smoke, release verifier parser check, project-owned sentinel search, and Local API close/reopen proof at `http://127.0.0.1:15099` with health ok, startup progress 14/14 complete, close-readiness idle/safe, 50 contract routes, Launch HTML markers, token bootstrap payload, no `mp-include`, and selected assets HTTP 200.
Open questions: None.
Risk: Low — WebView markup include/static-test only; `launchView*.js`, `/api/launch/preflight`, `/api/pipeline/start`, `/api/pipeline/control`, `/api/audit/start`, `/api/rerun/start`, backend launch policy, command preconditions, and process semantics are unchanged.
```

```
Task ID: God-file split Wave 4: index Rename partial extraction
Files inspected: src/mediapipeline/desktop/api/static_files.py; src/mediapipeline/desktop/api/static_files_policy.py; apps/desktop/webview/static/index.html; apps/desktop/webview/static/partials/page-rename.html; tests/python/desktop/test_api_static_files_policy.py; tests/python/desktop/test_application_facade.py
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_api_static_files_policy tests.python.desktop.test_application_facade.ApplicationFacadeTests.test_local_api_static_file_helpers_render_bootstrap_and_assets tests.python.desktop.test_application_facade.LocalApiServerTests.test_local_api_serves_read_only_web_prototype tests.webview.test_webview_navigation_static tests.webview.test_webview_inventory_docs tests.webview.test_webview_frontend_mutation_boundary tests.webview.test_webview_network_read_only_boundary -q
Findings: 34 focused tests passed. Rendered index proof returned HTTP-render-equivalent HTML with Rename `data-page-panel="rename"`, `rename-rows`, `rename-apply-readiness-rows`, `rename-apply-outcome-rows`, `rename-apply-selected-button`, following Launch page, `window.MEDIA_PIPELINE_BOOTSTRAP` token payload, 1,026 DOM IDs, and no remaining `mp-include` markers. UTF-8 byte check confirmed `index.html` and `partials/page-rename.html` do not begin with a BOM. Broader validation passed: 111 application-facade tests, 107 focused WebView/static/Tauri tests, repo hygiene, browser Home live-state smoke, release verifier parser check, project-owned sentinel search, and Local API close/reopen proof at `http://127.0.0.1:59783` with health ok, startup progress 14/14 complete, close-readiness idle/safe, 50 contract routes, Rename HTML markers, token bootstrap payload, no `mp-include`, and selected assets HTTP 200.
Open questions: None.
Risk: Low — WebView markup include/static-test only; `renameView.js`, `/api/rename/preview`, `/api/rename/apply`, backend transactional rename ownership, and apply-readiness boundaries are unchanged.
```

```
Task ID: God-file split Wave 4: index Reports partial extraction
Files inspected: src/mediapipeline/desktop/api/static_files.py; src/mediapipeline/desktop/api/static_files_policy.py; apps/desktop/webview/static/index.html; apps/desktop/webview/static/partials/page-reports.html; apps/desktop/webview/static/partials/page-schedule.html; tests/python/desktop/test_api_static_files_policy.py
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_api_static_files_policy tests.python.desktop.test_application_facade.ApplicationFacadeTests.test_local_api_static_file_helpers_render_bootstrap_and_assets tests.python.desktop.test_application_facade.LocalApiServerTests.test_local_api_serves_read_only_web_prototype tests.webview.test_webview_navigation_static tests.webview.test_webview_inventory_docs tests.webview.test_webview_frontend_mutation_boundary tests.webview.test_webview_network_read_only_boundary -q
Findings: 34 focused tests passed. Rendered index proof returned HTTP-render-equivalent HTML with Reports `data-page-panel="reports"`, `failure-rows`, `audit-preview-rows`, `report-open-history`, following Schedule page, `window.MEDIA_PIPELINE_BOOTSTRAP` token payload, 1,026 DOM IDs, and no remaining `mp-include` markers. UTF-8 byte check confirmed `index.html` and `partials/page-reports.html` do not begin with a BOM. Broader validation passed: 111 application-facade tests, 107 focused WebView/static/Tauri tests, repo hygiene, browser Home live-state smoke, release verifier parser check, project-owned sentinel search, and Local API close/reopen proof at `http://127.0.0.1:45898` with health ok, startup progress 14/14 complete, close-readiness idle/safe, 50 contract routes, Reports HTML markers, token bootstrap payload, no `mp-include`, and selected assets HTTP 200.
Open questions: None.
Risk: Low — WebView markup include/static-test only; `reportsView.js`, diagnostics-open ownership, report navigation handoff, route contracts, and report read-only boundaries are unchanged.
```

```
Task ID: God-file split Wave 4: index Workers partial extraction
Files inspected: src/mediapipeline/desktop/api/static_files.py; src/mediapipeline/desktop/api/static_files_policy.py; apps/desktop/webview/static/index.html; apps/desktop/webview/static/partials/page-network.html; apps/desktop/webview/static/partials/page-maintenance.html; tests/python/desktop/test_webview_network_read_only_boundary.py
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_api_static_files_policy tests.python.desktop.test_application_facade.ApplicationFacadeTests.test_local_api_static_file_helpers_render_bootstrap_and_assets tests.python.desktop.test_application_facade.LocalApiServerTests.test_local_api_serves_read_only_web_prototype tests.webview.test_webview_navigation_static tests.webview.test_webview_inventory_docs tests.webview.test_webview_frontend_mutation_boundary tests.webview.test_webview_network_read_only_boundary -q
Findings: 34 focused tests passed. Rendered index proof returned HTTP-render-equivalent HTML with app shell, Workers `data-page-panel="network"`, `network-worker-status-filter`, `network-worker-rows`, `network-lifecycle-rows`, following Maintenance page, `window.MEDIA_PIPELINE_BOOTSTRAP` token payload, 1,026 DOM IDs, and no remaining `mp-include` markers. Workers read-only boundary coverage continues to parse rendered HTML and assert diagnostics-open-only buttons plus no lifecycle/mutation controls. Broader validation passed: 111 application-facade tests, 107 focused WebView/static/Tauri tests, repo hygiene, browser Home live-state smoke, release verifier parser check, and Local API close/reopen proof at `http://127.0.0.1:18763` with health ok, startup progress 14/14 complete, close-readiness idle/safe, 50 contract routes, Workers HTML markers, token bootstrap payload, no `mp-include`, and selected assets HTTP 200.
Open questions: None.
Risk: Low — WebView markup include/static-test only; `/api/network/workers`, Network JS, diagnostics-open ownership, and lifecycle mutation boundaries are unchanged.
```

```
Task ID: God-file split Wave 4: index Maintenance partial extraction
Files inspected: src/mediapipeline/desktop/api/static_files.py; src/mediapipeline/desktop/api/static_files_policy.py; apps/desktop/webview/static/index.html; apps/desktop/webview/static/partials/page-maintenance.html; apps/desktop/webview/static/partials/page-schedule.html; apps/desktop/webview/static/partials/page-telemetry.html; tests/python/desktop/test_webview_network_read_only_boundary.py
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_api_static_files_policy tests.python.desktop.test_application_facade.ApplicationFacadeTests.test_local_api_static_file_helpers_render_bootstrap_and_assets tests.python.desktop.test_application_facade.LocalApiServerTests.test_local_api_serves_read_only_web_prototype tests.webview.test_webview_navigation_static tests.webview.test_webview_inventory_docs tests.webview.test_webview_frontend_mutation_boundary tests.webview.test_webview_network_read_only_boundary -q; apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_application_facade -q
Findings: 34 focused tests passed, 111 application-facade tests passed, repo hygiene passed, browser Home live-state smoke passed, release verifier parser check passed, and Local API close/reopen proof passed. Rendered index proof returned HTTP-render-equivalent HTML with app shell, Maintenance `data-page-panel="maintenance"`, `maintenance-refresh-button`, `release-dry-run-button`, `backfill-dry-run-button`, following Diagnostics page, bootstrap JSON, 1,026 DOM IDs, and no remaining `mp-include` markers. Workers read-only boundary coverage now parses rendered HTML rather than the raw include template.
Open questions: None.
Risk: Low — WebView markup include/static-test only; Maintenance command routes, ops/release/metadata/backfill dry-run semantics, and backend mutation boundaries are unchanged.
```

```
Task ID: God-file split Wave 4: index Schedule partial extraction
Files inspected: src/mediapipeline/desktop/api/static_files.py; src/mediapipeline/desktop/api/static_files_policy.py; apps/desktop/webview/static/index.html; apps/desktop/webview/static/partials/page-schedule.html; apps/desktop/webview/static/partials/page-telemetry.html; apps/desktop/webview/static/partials/app-shell-start.html; apps/desktop/webview/static/partials/app-shell-end.html
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_api_static_files_policy tests.python.desktop.test_application_facade.ApplicationFacadeTests.test_local_api_static_file_helpers_render_bootstrap_and_assets tests.python.desktop.test_application_facade.LocalApiServerTests.test_local_api_serves_read_only_web_prototype tests.webview.test_webview_navigation_static tests.webview.test_webview_inventory_docs tests.webview.test_webview_frontend_mutation_boundary -q; apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_application_facade -q
Findings: 30 focused tests passed, 111 application-facade tests passed, repo hygiene passed, browser Home live-state smoke passed, release verifier parser check passed, and Local API close/reopen proof passed. Rendered index proof returned HTTP-render-equivalent HTML with app shell, Telemetry, Schedule `data-page-panel="schedule"`, `schedule-editor-preview-button`, `schedule-editor-save-button`, `schedule-day-rows`, bootstrap JSON, 1,026 DOM IDs, and no remaining `mp-include` markers.
Open questions: None.
Risk: Low — WebView markup include/static-test only; Schedule command routes and app-state write semantics are unchanged.
```

```
Task ID: God-file split Wave 4: index Telemetry partial extraction
Files inspected: src/mediapipeline/desktop/api/static_files.py; src/mediapipeline/desktop/api/static_files_policy.py; apps/desktop/webview/static/index.html; apps/desktop/webview/static/partials/app-shell-start.html; apps/desktop/webview/static/partials/app-shell-end.html; apps/desktop/webview/static/partials/page-telemetry.html
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_api_static_files_policy tests.python.desktop.test_application_facade.ApplicationFacadeTests.test_local_api_static_file_helpers_render_bootstrap_and_assets tests.python.desktop.test_application_facade.LocalApiServerTests.test_local_api_serves_read_only_web_prototype tests.webview.test_webview_navigation_static tests.webview.test_webview_inventory_docs tests.webview.test_webview_frontend_mutation_boundary -q; apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_application_facade -q
Findings: 30 focused tests passed and the full `test_application_facade.py` file passed 111 tests after stale raw-index/static-CSS assertions were moved to rendered `index.html` and the imported stylesheet bundle. Rendered index proof returned HTTP-render-equivalent HTML with app shell, Telemetry `data-page-panel="live"`, `telemetry-readiness-status`, `cpu-chart`, `gpu-rows`, bootstrap JSON, 1,026 DOM IDs, and no remaining `mp-include` markers.
Open questions: None.
Risk: Low — read-only WebView markup include/static-test only.
```

```
Task ID: God-file split Wave 4: index shell partial extraction
Files inspected: src/mediapipeline/desktop/api/static_files.py; src/mediapipeline/desktop/api/static_files_policy.py; apps/desktop/webview/static/index.html; apps/desktop/webview/static/partials/app-shell-start.html; apps/desktop/webview/static/partials/app-shell-end.html; Test-MediaPipelineRemuxEncodeAIO-Release.ps1
Files changed: docs/testing/TEST_COVERAGE_MATRIX.md
Validation: apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_api_static_files_policy tests.python.desktop.test_application_facade.ApplicationFacadeTests.test_local_api_static_file_helpers_render_bootstrap_and_assets tests.python.desktop.test_application_facade.LocalApiServerTests.test_local_api_serves_read_only_web_prototype tests.webview.test_webview_navigation_static tests.webview.test_webview_inventory_docs tests.webview.test_webview_frontend_mutation_boundary -q
Findings: 29 tests passed. Rendered index proof returned HTTP-render-equivalent HTML with app shell, nav, bootstrap JSON, 1,026 DOM IDs, and no remaining `mp-include` markers.
Open questions: None.
Risk: Low — backend template include/static-test only.
```
