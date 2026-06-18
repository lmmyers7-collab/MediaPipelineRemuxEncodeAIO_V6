# God File Hunt / Maintainability Risk Ranking

Date: 2026-06-17

Change packet: `MP-CHANGE-2026-0617-003`

Scope: report-only audit across Python, JavaScript/WebView static assets, PowerShell, Tauri/Rust, scripts, configs, and high-value docs. No source behavior, config, generated summary, launcher, media, queue, publish, or Tauri behavior was changed.

## Executive Summary

The highest maintainability risk is concentrated in three places:

1. Large WebView panels that combine rendering, selection state, evidence summaries, route calls, and operator safety messaging. `networkView.js`, `queueView.js`, `settingsView.js`, `launchView.js`, `settingsLibraries.js`, `diagnosticsView.js`, `pendingPublishView.js`, and `renameView.js` are the largest current god-file candidates.
2. Backend/network/config policy facades that sit on safety-critical boundaries. `src/mediapipeline/core/network/facade.py`, `src/mediapipeline/core/config/settings_wizard.py`, `src/mediapipeline/core/completed/policy.py`, `src/mediapipeline/desktop/network/registry.py`, and `src/mediapipeline/contracts/config.py` combine size, broad coupling, and high operator impact.
3. PowerShell entry/engine scripts that still own media probing, pipeline entry, encode/remux routing, pending publish, subtitle building, and validation. These files have smaller module counts than the old monolith, but their blast radius remains high because they touch FFmpeg/probe policy, scratch/output movement, and publish/drain behavior.

The safest refactor path is not "split biggest first." Start with pure extraction seams that preserve backend ownership: WebView read-only render helpers, DTO formatters, CSS/HTML component grouping, and Python/PowerShell pure policy helpers. Delay any extraction that changes FFmpeg command generation, source/scratch/output movement, pending-publish drain, settings persistence, command journal semantics, or Tauri backend lifecycle until focused unit/smoke and real-media validation are in place.

## Methodology

I followed the required entry sequence:

- Read `AGENTS.md`.
- Read `docs/CURRENT_PROJECT_STATE.md`.
- Read `docs/OPEN_WORK_CHECKLIST.md`.
- Read `docs/generated/PROJECT_INDEX.md`, which existed and reported 1,580 indexed source files.
- Used generated summaries before file-level interpretation for shortlisted files. Many WebView/Tauri summaries are currently `Purpose: (unparsed)`, so their responsibility breakdown uses metric scans plus current docs and test matrices.

Searches and scans performed:

- `rg --files` inventory, excluding archived docs, generated summaries, runtime/vendor/cache directories.
- Metric scan over 1,919 relevant text files; 1,565 non-test implementation/docs/config files remained after excluding test implementation from the overall implementation ranking.
- Per-file counts: line count, function/class/symbol count, branch-marker count, import/global-reference count, route/API string count, WebView `window.` references, and fetch/POST/GET markers.
- Targeted coupling scan for shortlisted files: incoming references by file path, basename, module path, or WebView asset include; direct tests/smokes mentioning the file/module.
- Criticality search in `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`, `docs/testing/TEST_COVERAGE_MATRIX.md`, `docs/inventories/RISKY_FILE_REGISTRY.v1.json`, `docs/generated/WEBVIEW_GODFILE_SPLIT_MAP.md`, `docs/generated/WEBVIEW_SPLIT_CANDIDATES.json`, and `docs/testing/WEBVIEW_GODFILE_SPLIT_GUARDRAILS.md`.

Scoring model, relative 0-120 scale:

- Size, up to 30: line count and file length.
- Complexity, up to 25: branch markers, functions/classes, nesting/indentation signal.
- Responsibility count, up to 18: distinct domains present in one file.
- Coupling, up to 18: imports, WebView globals, route strings, incoming references, shared-state access signals.
- Churn risk, up to 10: central workflow or many tests/docs touch it.
- Blast radius, up to 14: queue/media/config/source movement/publish/rename/network/Tauri safety impact.
- Test coverage signal, negative/positive adjustment: direct tests lower uncertainty, missing or only indirect tests raise risk.
- Operator criticality, up to 14: startup, publish, settings, coordinator, worker, queue, command journal, close-readiness.

Classification:

- Confirmed: line/symbol/reference evidence plus active docs or tests identify the file as critical.
- Likely: metric evidence is strong, but responsibility/coupling is partly inferred from names, route strings, or tests.
- Needs verification: generated/config/docs artifact or summary is weak; needs maintainer confirmation before treating it as a refactor target.

## Top 25 Highest-Risk Files Overall

| Rank | File | Score | Class | Evidence Snapshot | Primary Risk |
|---:|---|---:|---|---|---|
| 1 | `apps/desktop/webview/static/assets/networkView.js` | 116 | Confirmed | 3,351 lines, 351 functions, 399 branches, 21 route strings, 14 direct test/smoke mentions | Network lifecycle UI mixes route calls, readiness evidence, worker/coordinator state, and mutation-boundary messaging. |
| 2 | `apps/desktop/webview/static/assets/queueView.js` | 114 | Confirmed | 2,437 lines, 279 functions, 280 branches, 136 `window`/global refs, 16 test/smoke mentions | Queue table, priority, launch handoff, file overrides, source-path policy display, and selection state remain tightly coupled. |
| 3 | `src/mediapipeline/core/network/facade.py` | 113 | Confirmed | 2,022 lines, 67 functions, 394 branches, 29 imports, 49 test/smoke mentions | Network facade crosses config, URL policy, worker state, registry, path map, mdns, and pipeline policy. |
| 4 | `apps/desktop/webview/static/assets/settingsView.js` | 112 | Confirmed | 1,898 lines, 296 functions, 146 branches, 156 globals, 8 route strings, 37 test mentions | Settings preview/save/browse state and high-impact policy handoffs remain in one parent. |
| 5 | `apps/desktop/webview/static/assets/launchView.js` | 111 | Confirmed | 1,692 lines, 442 functions, 117 branches, 257 globals, 9 route strings, 22 test mentions | Launch readiness, start gating, real-media proof, risk display, and route handoff are tightly coupled. |
| 6 | `apps/desktop/webview/static/assets/settingsLibraries.js` | 110 | Confirmed | 2,186 lines, 271 functions, 249 branches, 23 test mentions | Library profile inheritance/promotion UI carries settings and route-policy blast radius. |
| 7 | `apps/desktop/webview/static/assets/app.js` | 109 | Confirmed | 1,727 lines, 233 functions, 203 branches, 184 globals, 25 route strings, 46 test mentions | App shell orchestrates page refresh, route calls, global state, and lifecycle wiring. |
| 8 | `apps/desktop/webview/static/assets/diagnosticsView.js` | 108 | Confirmed | 2,076 lines, 276 functions, 165 branches, 141 globals, 6 route strings, 19 test mentions | Diagnostics combines command evidence, owner handoffs, lifecycle/status display, and operator trust paths. |
| 9 | `apps/desktop/webview/static/assets/pendingPublishView.js` | 108 | Confirmed | 1,418 lines, 438 functions, 85 branches, 196 globals, 14 test mentions | Pending publish/drain evidence is safety-critical and closely coupled to Completed/Diagnostics handoffs. |
| 10 | `apps/desktop/webview/static/assets/renameView.js` | 107 | Confirmed | 1,804 lines, 220 functions, 243 branches, 67 globals, 5 routes, 15 test mentions | Rename preview/apply readiness UI sits on a filesystem mutation boundary. |
| 11 | `apps/desktop/webview/static/assets/completedView.review.js` | 106 | Confirmed | 1,787 lines, 182 functions, 240 branches, 9 test mentions | Completed trust/review logic touches output acceptance, pending evidence, size, media, and sample-validation cues. |
| 12 | `apps/desktop/tauri/src-tauri/src/lib.rs` | 105 | Confirmed | 1,175 lines, 31 Rust functions, 18 route strings, heavy Tauri/test references | Tauri app root owns shell commands, window lifecycle, backend integration, and bridge posture. |
| 13 | `ops/pipeline/entrypoints/MediaPipeline.ps1` | 104 | Confirmed | 764 lines, 133 branches, 5 imports, 77 test/smoke mentions | Main pipeline entrypoint controls remux/encode/publish/drain paths and module loading. |
| 14 | `ops/pipeline/entrypoints/Audit-MediaLibrary.ps1` | 103 | Confirmed | 1,483 lines, 37 functions, 336 branches, 20 test/smoke mentions | Large audit entrypoint spans filesystem, media probing, route/config interpretation, and report output. |
| 15 | `ops/pipeline/engine/probe/media_probe.ps1` | 103 | Confirmed | 1,268 lines, 26 functions, 230 branches, summary lists HDR, media route, duration, integrity, video-stream functions | Probe evidence feeds media routing, verification, subtitle/audio decisions, and publish safety. |
| 16 | `src/mediapipeline/core/config/settings_wizard.py` | 102 | Confirmed | 1,101 lines, 49 functions, 218 branches, 15 imports, 2 direct tests | Settings wizard handles paths, FFmpeg tools, worker settings, payload validation, and save/preview. |
| 17 | `src/mediapipeline/core/completed/policy.py` | 101 | Confirmed | 1,283 lines, 52 functions, 322 branches, 16 imports, 71 direct/indirect test mentions | Completed output policy influences trust, acceptance, saved-policy reconciliation, and final-output evidence. |
| 18 | `apps/desktop/tauri/src-tauri/src/backend_process.rs` | 100 | Confirmed | 964 lines, 52 functions, 7 structs/enums, 72 branches | Backend process lifecycle, health/crash behavior, logging, and shutdown posture live here. |
| 19 | `src/mediapipeline/desktop/network/registry.py` | 99 | Confirmed | 1,134 lines, 35 functions, 2 classes, 223 branches, 26 direct test mentions | Network registry affects worker state, cluster claims, security, and workflow coordination. |
| 20 | `src/mediapipeline/desktop/application/network_lifecycle_provider.py` | 98 | Confirmed | 943 lines, 49 functions, 3 classes, 216 branches, 3 direct tests | Provider-guarded lifecycle commands bridge backend policy and network controls. |
| 21 | `ops/scripts/release/test.ps1` | 98 | Confirmed | 1,276 lines, 27 functions, 210 branches, 370 incoming refs | Release validation is a large orchestration script; breakage weakens release confidence. |
| 22 | `ops/pipeline/engine/subtitles/builders.ps1` | 97 | Confirmed | 964 lines, 13 functions, 172 branches, summary priority `high`, subtitle-stage owner | Subtitle builder policy is high-risk per AGENTS and no-touch register. |
| 23 | `ops/pipeline/engine/queue/file_overrides.ps1` | 96 | Confirmed | 985 lines, 22 functions, 263 branches, 2 direct PS tests | File override behavior can affect queue routing, subtitle burn decisions, and media policy. |
| 24 | `src/mediapipeline/contracts/config.py` | 95 | Confirmed | 1,194 lines, Pydantic `Config`, 17 functions, 11 imports, 10 direct tests | Canonical config contract touches schemas, defaults, validators, rename constants, and strict JSON. |
| 25 | `docs/REMEDIATION_CHANGELOG.md` | 94 | Likely | 34,798 lines, 517 route/API mentions, referenced by active checklist/current docs | Huge forensic doc is useful but too large for onboarding and future audit navigation. |

## Top 10 Highest-Risk Python Files

| Rank | File | Lines | Functions / Classes | Coupling Evidence | Classification |
|---:|---|---:|---:|---|---|
| 1 | `src/mediapipeline/core/network/facade.py` | 2,022 | 67 / 1 | 29 imports; summary imports config, DTO commands, join, URL policy, pipeline policy, desktop models, auth, roots, mdns, path map, probe, registry, worker state | Confirmed |
| 2 | `src/mediapipeline/core/config/settings_wizard.py` | 1,101 | 49 / 0 | Imports config identity/profiles/patch policy/config keys/models; settings wizard tests present | Confirmed |
| 3 | `src/mediapipeline/core/completed/policy.py` | 1,283 | 52 / 0 | 71 direct/indirect test mentions; referenced by validation ladder and test matrix | Confirmed |
| 4 | `src/mediapipeline/desktop/network/registry.py` | 1,134 | 35 / 2 | Network workflow/security/protocol/worker tests reference it | Confirmed |
| 5 | `src/mediapipeline/desktop/application/network_lifecycle_provider.py` | 943 | 49 / 3 | Referenced by process-launch, lifecycle-fix, coordinator-policy tests | Confirmed |
| 6 | `src/mediapipeline/contracts/config.py` | 1,194 | 17 / 1 | Imports config coercion/defaults/schema extras/validators/rename/strict JSON; config contract tests present | Confirmed |
| 7 | `src/mediapipeline/core/queue/file_overrides.py` | 926 | 36 / 1 | Queue file-overrides smoke, Local API, track, and queue policy tests reference it | Confirmed |
| 8 | `src/mediapipeline/desktop/network/coordinator_http_handlers.py` | 656 | 8 / 1 | 31 route strings; coordinator source-policy and HTTP tests reference it | Confirmed |
| 9 | `src/mediapipeline/core/processes/preflight_facade.py` | 625 | 18 / 1 | Launch/preflight route strings and process-launch tests make it high blast radius | Likely |
| 10 | `src/mediapipeline/pipeline/ass_to_srt_cli.py` | 818 | 14 / 4 | Subtitle conversion CLI, 21 imports, 97 branches; subtitle failures must route to review | Likely |

## Top 10 Highest-Risk PowerShell Files

| Rank | File | Lines | Functions | Branches | Coupling / Coverage Signal | Classification |
|---:|---|---:|---:|---:|---|---|
| 1 | `ops/pipeline/entrypoints/MediaPipeline.ps1` | 764 | 1 | 133 | 77 test/smoke mentions; main entrypoint for pipeline execution | Confirmed |
| 2 | `ops/pipeline/entrypoints/Audit-MediaLibrary.ps1` | 1,483 | 37 | 336 | 20 test/smoke mentions; broad media/filesystem audit scope | Confirmed |
| 3 | `ops/pipeline/engine/probe/media_probe.ps1` | 1,268 | 26 | 230 | Media verification and HDR tests reference it; summary lists route/profile/integrity/probe functions | Confirmed |
| 4 | `ops/pipeline/entrypoints/MediaPipeline/encode.ps1` | 646 | 1 | 114 | Referenced by quality/media verification/library routing/encode flag/dynamic HDR tests | Confirmed |
| 5 | `ops/pipeline/engine/queue/file_overrides.ps1` | 985 | 22 | 263 | Library routing and file override subtitle burn tests reference it | Confirmed |
| 6 | `ops/pipeline/engine/publish/pending_push.ps1` | 573 | 10 | 61 | Summary priority `high`; pending-publish safety and ownership tests reference it | Confirmed |
| 7 | `ops/pipeline/engine/subtitles/builders.ps1` | 964 | 13 | 172 | Summary priority `high`; subtitle builder and pending publish tests reference it | Confirmed |
| 8 | `ops/pipeline/engine/process/pipeline_processing.ps1` | 668 | 5 | 69 | Pipeline processing source probe and library routing tests reference it | Confirmed |
| 9 | `ops/pipeline/engine/status/progress_state.ps1` | 891 | 29 | 155 | Progress telemetry and legacy reliability tests reference it | Likely |
| 10 | `ops/scripts/release/test.ps1` | 1,276 | 27 | 210 | Release test orchestrator; referenced by AGENTS/README/build/release artifacts | Confirmed |

## Top 10 Highest-Risk UI / Static Files

| Rank | File | Lines | Functions / Selectors | Route/Global Signal | Direct Test Signal | Classification |
|---:|---|---:|---:|---|---|---|
| 1 | `apps/desktop/webview/static/assets/networkView.js` | 3,351 | 351 functions | 21 route strings, 9 globals | Network boundary, frontend mutation, command evidence, reliability smokes | Confirmed |
| 2 | `apps/desktop/webview/static/assets/queueView.js` | 2,437 | 279 functions, 1 class | 9 routes, 136 globals | Row detail, mutation boundary, dropdown, diagnostics, command evidence smokes | Confirmed |
| 3 | `apps/desktop/webview/static/assets/settingsView.js` | 1,898 | 296 functions | 8 routes, 156 globals | Settings libraries, real-media, HandBrake settings, mutation boundary tests | Confirmed |
| 4 | `apps/desktop/webview/static/assets/launchView.js` | 1,692 | 442 functions | 9 routes, 257 globals | Real-media, mutation boundary, CSS token, command evidence, reliability tests | Confirmed |
| 5 | `apps/desktop/webview/static/assets/settingsLibraries.js` | 2,186 | 271 functions | 16 globals | Settings libraries and final-library promotion tests | Confirmed |
| 6 | `apps/desktop/webview/static/assets/diagnosticsView.js` | 2,076 | 276 functions | 6 routes, 141 globals | Diagnostics owner/drilldown, command evidence, mutation boundary tests | Confirmed |
| 7 | `apps/desktop/webview/static/assets/pendingPublishView.js` | 1,418 | 438 functions | 196 globals | Pending/diagnostics/command evidence/reliability tests | Confirmed |
| 8 | `apps/desktop/webview/static/assets/renameView.js` | 1,804 | 220 functions | 5 routes, 66 globals | Rename readiness, Local API, rename workbench tests | Confirmed |
| 9 | `apps/desktop/webview/static/assets/app.js` | 1,727 | 233 functions | 25 routes, 184 globals | 46 test mentions, summary/godfile guard tests | Confirmed |
| 10 | `apps/desktop/webview/static/assets/styles.components.css` | 3,988 | 1,011 selectors | Shared component surface | CSS design token/static tests | Likely |

## Top 10 Deceptively Small But High-Blast-Radius Files

| Rank | File | Lines | Why It Is High Blast Radius | Test Signal | Classification |
|---:|---|---:|---|---|---|
| 1 | `src/mediapipeline/desktop/api/queue_source_path_policy.py` | 21 | API queue source-path policy boundary; source mutation is forbidden by default | `test_queue_source_path_policy.py` | Confirmed |
| 2 | `src/mediapipeline/core/validation/strict_json.py` | 51 | Strict JSON route parsing is release-critical per AGENTS; errors affect confirm-save/apply routes | No direct test found in targeted scan | Needs verification |
| 3 | `apps/desktop/tauri/src-tauri/src/single_instance_guard.rs` | 61 | Prevents simultaneous desktop shells and backend process races | Tauri production-surface and shell scaffold tests | Confirmed |
| 4 | `apps/desktop/tauri/src-tauri/src/backend_lifecycle_monitor.rs` | 132 | Backend health/crash lifecycle events affect operator shutdown/recovery posture | Indirect Tauri lifecycle smokes | Likely |
| 5 | `apps/desktop/tauri/src-tauri/src/close_readiness.rs` | 134 | Close-readiness false positives can kill active encode/publish work | Browser lifecycle, Tauri PG tests, close-readiness tests | Confirmed |
| 6 | `src/mediapipeline/desktop/api/command_journal_policy.py` | 152 | Command journal trust and duplicate-command guards are release-critical | Command journal policy/contracts/storage tests | Confirmed |
| 7 | `src/mediapipeline/core/processes/source_path_policy.py` | 186 | Source/scratch/output movement policy boundary | Queue source path policy test | Confirmed |
| 8 | `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md` | 222 | Canonical active high-risk boundary register; wrong guidance would misdirect future agents | Active doc reference test | Confirmed |
| 9 | `ops/pipeline/engine/config/config_keys.ps1` | 234 | Shared PowerShell config-key registry; drift can break settings/schema alignment | Config key and contract schema checks | Confirmed |
| 10 | `src/mediapipeline/desktop/api/server.py` | 235 | Local API server startup/security headers/listener behavior affects every WebView/Tauri workflow | API/static/server tests are indirect | Likely |

## File-by-File Evidence for Top Files

### 1. `apps/desktop/webview/static/assets/networkView.js`

- Responsibility breakdown: Network coordinator/worker visibility, lifecycle route calls, route metadata display, dry-run/start/stop/join setup handoffs, settings evidence, command evidence, mutation-boundary warnings.
- Coupling evidence: 21 route strings, 20 fetch/POST/GET markers, 211 incoming reference occurrences. Test examples include `test_webview_network_read_only_boundary.py`, `test_webview_frontend_mutation_boundary.py`, `test_webview_command_evidence_smoke.py`, `Invoke-WebViewReliabilityChecks.ps1`, `test_application_facade_web_static.py`, and `test_application_facade_local_api.py`.
- Risk: Network lifecycle controls have process-safety implications per the no-touch boundary register. The file is large enough that UI-only edits can accidentally change command availability or operator guidance.
- Effort / benefit: XL effort, high benefit if extracted into route-client, state-normalization, and render-only child modules.
- Before touching: `npm run webview:prework:check`, `npm run webview:check`, network read-only boundary smoke, Local API network lifecycle tests, route inventory/contract checks.

### 2. `apps/desktop/webview/static/assets/queueView.js`

- Responsibility breakdown: Queue rendering, selection/detail state, priority/strategy controls, file override drawer integration, launch handoff, source-scope warnings, diagnostics cross-links.
- Coupling evidence: 2,437 lines, 136 globals, 9 route strings, 242 incoming reference occurrences. Test examples include row-detail, mutation-boundary, dropdown remediation, diagnostics owner handoff, command evidence, and WebView reliability checks.
- Risk: Queue launch scope/rerun/schedule behavior is listed as high risk in AGENTS. Frontend must stay advisory and must not own queue mutation semantics.
- Effort / benefit: XL effort, high benefit from extracting table rendering, file override adapters, and launch handoff summaries.
- Before touching: WebView queue file-overrides smoke, queue source-path policy tests, Local API queue tests, WebView no-mutation tests, release reliability wrapper for launch/queue changes.

### 3. `src/mediapipeline/core/network/facade.py`

- Responsibility breakdown: Network runtime-state facade, coordinator/worker discovery, path-map/root handling, config/profile integration, URL policy, registry and worker-state orchestration.
- Coupling evidence: 29 imports; summary imports `library_profiles`, `config_keys`, `dto_commands`, `join`, `url_policy`, `pipeline_policy`, desktop models, network auth, roots, mdns, path map, probe, registry, and worker state. Targeted scan found 49 test/smoke mentions.
- Risk: Network mode currently has backend-owned lifecycle controls and provider gates. This facade is broad enough to become the accidental owner of several network domains.
- Effort / benefit: XL effort, high benefit from splitting read DTO assembly, provider policy, path mapping, and worker-state adapters.
- Before touching: network coordinator/worker unit suite, lifecycle route tests, `/api/contract` route inventory, command-journal checks, source-policy tests.

### 4. `apps/desktop/webview/static/assets/settingsView.js`

- Responsibility breakdown: Settings reload/validate/preview/save, browse path, builder synchronization, safety locks, raw triage, patch summaries, runtime restart messaging.
- Coupling evidence: 1,898 lines, 296 functions, 156 globals, 8 route strings, 37 test mentions. Generated split map already identifies settings child candidates and route ownership constraints.
- Risk: Settings schema/defaults/persistence are high risk. WebView must not become the source of truth for config persistence or media policy.
- Effort / benefit: L/XL effort, high benefit from extracting route-client, patch-summary renderers, safety lock renderers, and remaining builder parent-state adapters.
- Before touching: settings static/config tests, settings patch smokes, route ownership guard, config schema checks, WebView no-mutation tests.

### 5. `apps/desktop/webview/static/assets/launchView.js`

- Responsibility breakdown: Launch readiness, start request framing, command buttons, preflight, real-media proof, policy-vs-route warnings, progress/start-decision summaries.
- Coupling evidence: 1,692 lines, 442 functions, 257 globals, 9 route strings, 22 test mentions.
- Risk: Launch is the visible boundary for process start, queue scope, rerun, schedule, real-media policy, and command preconditions.
- Effort / benefit: L effort, high benefit from separating command button state, readiness DTO rendering, sample-proof rendering, and request construction.
- Before touching: launch command button smoke, launch/queue readiness browser smoke, process launch tests, Local API start/control tests, no-mutation browser smoke.

### 6. `apps/desktop/webview/static/assets/settingsLibraries.js`

- Responsibility breakdown: Library profile display, inheritance/override state, promotion rules, effective setting evidence, UI state.
- Coupling evidence: 2,186 lines, 271 functions, 249 branches, references from settings libraries tests, HandBrake settings UI tests, final-library promotion tests, and `index.html`.
- Risk: Library profile settings govern source/output/promotion semantics. Misleading UI here can cause operator mistakes even if backend remains authoritative.
- Effort / benefit: L effort, high benefit from extracting profile normalization display, promotion rule widgets, and override-state renderers.
- Before touching: final-library promotion tests, settings libraries smokes, settings config contract tests.

### 7. `apps/desktop/webview/static/assets/app.js`

- Responsibility breakdown: SPA shell, refresh orchestration, page navigation, API calls, global state, lifecycle hooks, top-level status/error flow.
- Coupling evidence: 1,727 lines, 233 functions, 184 globals, 25 route strings, 626 incoming reference occurrences, 46 direct test mentions.
- Risk: App shell drift can affect every WebView page even when a change appears local.
- Effort / benefit: XL effort, high benefit but only if done in small route/page-scope slices.
- Before touching: full `npm run webview:check`, navigation static tests, lifecycle smoke, command evidence smoke, browser no-mutation suite.

### 8. `apps/desktop/webview/static/assets/diagnosticsView.js`

- Responsibility breakdown: Diagnostics rendering, first-response rows, owner handoffs, command drilldown evidence, status/log navigation.
- Coupling evidence: 2,076 lines, 276 functions, 141 globals, 6 routes, 19 direct test mentions.
- Risk: Diagnostics is evidence/navigation only. Accidentally adding mutation authority or changing evidence semantics undermines operator trust.
- Effort / benefit: L effort, medium/high benefit from extracting owner-handoff rows, log/status adapters, and command evidence formatters.
- Before touching: diagnostics owner-handoff smoke, diagnostics drilldown static tests, command evidence smoke, Local API diagnostics tests.

### 9. `apps/desktop/webview/static/assets/pendingPublishView.js`

- Responsibility breakdown: Pending publish table, drain/recovery evidence, confidence summaries, Completed/Diagnostics cross-links, row details.
- Coupling evidence: 1,418 lines, 438 functions, 196 globals, 14 test mentions.
- Risk: Pending publish/drain is explicitly high risk because it moves parked outputs and updates manifests. UI must remain backend-owned command caller only.
- Effort / benefit: L effort, high benefit from separating table/detail/confidence/drain-adapter modules.
- Before touching: pending drain guard smoke, pending publish safety/ownership checks, Local API pending-publish tests, real-media deferred-publish validation if behavior changes.

### 10. `apps/desktop/webview/static/assets/renameView.js`

- Responsibility breakdown: Rename preview, apply readiness, result display, filter settings, row selection, undo/history handoff.
- Coupling evidence: 1,804 lines, 220 functions, 243 branches, 5 route strings, 15 test mentions.
- Risk: Rename apply is a filesystem mutation boundary requiring explicit confirmation.
- Effort / benefit: L effort, high benefit from splitting preview state, readiness rendering, result rendering, and filter controls.
- Before touching: rename readiness browser smoke, Local API rename tests, rename planner/apply tests, no-mutation static checks.

### 11. `apps/desktop/webview/static/assets/completedView.review.js`

- Responsibility breakdown: Completed output review, integrity/size routing, policy reconciliation, proof gaps, sample validation handoffs.
- Coupling evidence: 1,787 lines, 182 functions, 240 branches, 9 test mentions.
- Risk: Completed evidence guides output acceptance and rerun decisions; incorrect evidence presentation can hide pending/final-placement conflicts.
- Effort / benefit: L effort, medium/high benefit from extracting policy-reconciliation and proof-gap renderers.
- Before touching: completed/pending proof smokes, path-evidence smokes, completed policy tests.

### 12. `apps/desktop/tauri/src-tauri/src/lib.rs`

- Responsibility breakdown: Tauri shell setup, command registration, backend integration, window lifecycle, close/shutdown orchestration, bridge/event wiring.
- Coupling evidence: 1,175 lines, 31 functions, 18 route strings, 54 fetch/POST/GET-like markers, very broad test references.
- Risk: Tauri backend lifecycle ownership is high risk. UI shell changes can break startup, close readiness, crash recovery, or token/devtools posture.
- Effort / benefit: XL effort, high benefit from moving command groups and lifecycle wiring behind smaller Rust modules.
- Before touching: Tauri `-CheckOnly`, Tauri launch/close tests, production surface test, Local API bootstrap/listening smoke.

### 13. `ops/pipeline/entrypoints/MediaPipeline.ps1`

- Responsibility breakdown: Main pipeline entrypoint, argument handling, module loading, worker failure result, and dispatch into remux/encode/publish/drain paths.
- Coupling evidence: 764 lines, 133 branches, 5 imports, 413 incoming reference occurrences, 77 test/smoke mentions.
- Risk: Changes can impact every run mode. No-touch register explicitly calls out pending publish drain execution in this entrypoint.
- Effort / benefit: XL effort, high benefit only after coverage pins dispatch behavior.
- Before touching: release test wrapper, reliability regression checks, pending publish checks, route/entrypoint tests, real-media validation if media movement changes.

### 14. `ops/pipeline/entrypoints/Audit-MediaLibrary.ps1`

- Responsibility breakdown: Library audit, media probing, filesystem inventory, config/path interpretation, report generation.
- Coupling evidence: 1,483 lines, 37 functions, 336 branches, 20 test/smoke mentions.
- Risk: Broad filesystem/media audit logic is hard to change safely because it can affect operator trust and release evidence.
- Effort / benefit: L effort, medium benefit from extracting probe adapters and report writers.
- Before touching: portable path checks, audit/rerun tests, release wrapper checks.

### 15. `ops/pipeline/engine/probe/media_probe.ps1`

- Responsibility breakdown: ffprobe/media duration, video codec, HDR/Dolby Vision, route profile, stream inventory, integrity/stability checks.
- Coupling evidence: 1,268 lines, 26 functions, 230 branches; direct media verification and dynamic HDR tests reference it.
- Risk: Probe evidence feeds remux/encode/subtitle/audio decisions. Wrong evidence can publish bad outputs silently.
- Effort / benefit: XL effort, high benefit from extracting codec/HDR/duration/integrity probes independently.
- Before touching: media verification safety, dynamic HDR, quality checks, release reliability, real-media samples.

### 16. `src/mediapipeline/core/config/settings_wizard.py`

- Responsibility breakdown: Wizard defaults/status, payload validation, path/tool validation, FFmpeg hardware probing, worker settings, preview/save.
- Coupling evidence: Summary lists 13 public functions and imports config identity, library profiles, settings patch policy, config keys, and desktop models.
- Risk: This file changes initial setup, FFmpeg tool paths, worker settings, and persisted config expectations.
- Effort / benefit: L effort, medium/high benefit from extracting validators and tool probes.
- Before touching: settings wizard tests, config validation tests, tool path validation, no source/media mutation checks.

### 17. `src/mediapipeline/core/completed/policy.py`

- Responsibility breakdown: Completed output policy, acceptance/readiness evidence, saved-policy reconciliation, proof state.
- Coupling evidence: 1,283 lines, 52 functions, 322 branches, 71 direct/indirect test mentions.
- Risk: Completed trust decisions affect output acceptance and rerun choices.
- Effort / benefit: L effort, high benefit from extracting proof-state and policy-reconciliation helpers.
- Before touching: completed policy tests, completed/pending proof smokes, sample validation tests.

### 18. `apps/desktop/tauri/src-tauri/src/backend_process.rs`

- Responsibility breakdown: Backend spawn, health/crash handling, process IO/logging, stop/shutdown behavior.
- Coupling evidence: 964 lines, 52 functions, 7 Rust data types, 72 branches; referenced by `lib.rs`, reliability checks, Tauri lifecycle review docs.
- Risk: Incorrect lifecycle handling can orphan backend processes or kill active work.
- Effort / benefit: L effort, high benefit from separating spawn config, log redaction, health polling, and shutdown policy.
- Before touching: Tauri production surface, launch/close checks, close readiness tests, Local API lifecycle smoke.

### 19. `src/mediapipeline/desktop/network/registry.py`

- Responsibility breakdown: Network runtime registry, worker/claim state, workflow/security/protocol state.
- Coupling evidence: 1,134 lines, 35 functions, 223 branches; tests cover workflow, worker runtime, security, protocol, and application facade network behavior.
- Risk: Registry corruption can affect distributed worker state and done/claim/release semantics.
- Effort / benefit: L effort, high benefit from extracting storage adapters and claim lifecycle policy.
- Before touching: network workflow/security/protocol/worker-state tests.

### 20. `src/mediapipeline/desktop/application/network_lifecycle_provider.py`

- Responsibility breakdown: Network lifecycle provider, dry-run/confirmed command gating, coordinator/worker preconditions.
- Coupling evidence: 943 lines, 49 functions, 216 branches; lifecycle/provider tests and Tauri lifecycle review docs reference it.
- Risk: Provider guards are the backend authority for network lifecycle controls.
- Effort / benefit: L effort, high benefit from extracting precondition calculators and result DTO builders.
- Before touching: network lifecycle fixes, coordinator policy tests, command journal tests.

### 21. `ops/scripts/release/test.ps1`

- Responsibility breakdown: Release self-test orchestration, Python/PowerShell/WebView/Tauri checks, route/test wrappers.
- Coupling evidence: 1,276 lines, 27 functions, 210 branches, 370 incoming references from docs/build/release scripts.
- Risk: Validation drift can make unsafe changes look releasable.
- Effort / benefit: L effort, medium benefit from extracting check groups and reporting helpers.
- Before touching: run the release test script itself in check mode if available; otherwise focused wrapper tests plus change-control validation.

### 22. `ops/pipeline/engine/subtitles/builders.ps1`

- Responsibility breakdown: Subtitle builder decisions, language/policy handling, burn/add/preserve logic handoffs.
- Coupling evidence: Summary priority `high`; 964 lines, 13 functions, 172 branches; subtitle builder and pending-publish safety tests reference it.
- Risk: Subtitle handling is format-specific and silent failures are hard to detect.
- Effort / benefit: XL effort, high benefit from extracting language policy, stream matching, and command-argument builders.
- Before touching: subtitle builder decision checks, SRT validation, file override subtitle burn checks, real-media subtitle samples.

### 23. `ops/pipeline/engine/queue/file_overrides.ps1`

- Responsibility breakdown: Queue file override parsing/application, route/profile interaction, subtitle burn decisions.
- Coupling evidence: 985 lines, 22 functions, 263 branches; library routing and file-override subtitle tests reference it.
- Risk: File overrides alter per-file media policy and queue routing.
- Effort / benefit: L effort, high benefit from extracting parser/validator/effective-policy helpers.
- Before touching: file override subtitle burn checks, library profile routing, queue/file override WebView smoke.

### 24. `src/mediapipeline/contracts/config.py`

- Responsibility breakdown: Canonical config contract, defaults, coercion, schema extras, validation links, rename and strict JSON integration.
- Coupling evidence: Summary lists Pydantic `Config`, `default_config()`, and imports config/rename/strict-json modules; direct tests cover config contract and config keys.
- Risk: Schema/default drift can break both Python and PowerShell settings surfaces.
- Effort / benefit: L effort, high benefit from generated schema separation and smaller nested model groups.
- Before touching: config contract tests, generated schema checks, PowerShell config key registry checks, settings smokes.

### 25. `docs/REMEDIATION_CHANGELOG.md`

- Responsibility breakdown: Historical remediation ledger, validation references, route/API history, UI and backend status history.
- Coupling evidence: 34,798 lines; referenced by active current/checklist docs and active-doc reference tooling.
- Risk: Too large for onboarding and easy to cite stale history as current guidance.
- Effort / benefit: M effort, medium benefit from adding a current index and moving old sections only through documented archival flow.
- Before touching: active doc reference checks and docs-only link/file checks.

## Refactor Candidates by Domain

### WebView Shell and Panels

- `networkView.js`: extract route client, lifecycle precondition rows, worker table renderer, coordinator setup renderers.
- `queueView.js`: extract table/detail renderers, priority controls, file override adapter, launch handoff summary.
- `settingsView.js` and `settingsLibraries.js`: continue generated split-map work with route ownership guardrails; split patch result renderers before persistence-adjacent logic.
- `launchView.js`: split command button state, preflight DTO display, real-media proof, start-request construction.
- `pendingPublishView.js`, `completedView.review.js`, `diagnosticsView.js`: extract proof/evidence renderers that remain read-only.
- `styles.components.css`: split component families by owner page only after CSS token/static tests are pinned.

### Python Backend

- Network: split `NetworkFacadeMixin` into state DTO assembly, coordinator discovery, worker-state readers, and lifecycle policy.
- Config/settings: split `settings_wizard.py` validators from preview/save orchestration; keep backend persistence authoritative.
- Completed/output trust: separate proof reconciliation from presentation DTO building.
- Contracts: split `Config` nested model groups only with schema compatibility tests and PowerShell key alignment.
- Queue/file overrides: separate parser, validation, effective-policy calculation, and API DTO formatting.

### PowerShell Pipeline

- Probe: split `media_probe.ps1` into duration/integrity, video stream inventory, HDR/Dolby, and route profile modules.
- Pipeline entry: isolate argument/dispatch validation from mode execution in `MediaPipeline.ps1`.
- Publish: keep `pending_push.ps1` high-validation; extract pure manifest formatting only first.
- Subtitle: extract language and stream-selection helpers from `builders.ps1` before touching command generation.
- File overrides: split parse/normalize/validate/effective override logic.

### Tauri Shell

- `lib.rs`: move command registration, close-readiness bridge, and backend event wiring into smaller modules.
- `backend_process.rs`: split spawn config, environment, stdout/stderr/logging, health polling, and shutdown policy.
- Keep `single_instance_guard.rs` and `close_readiness.rs` small; add tests rather than expanding them.

### Docs and Validation

- `docs/REMEDIATION_CHANGELOG.md`: create a compact index or cross-reference page rather than moving content blindly.
- `docs/testing/TEST_COVERAGE_MATRIX.md`: keep as active test navigation but avoid embedding fresh audit histories into it.
- Generated JSON artifacts: do not hand-edit; reduce risk by making generation/check commands easy to run.

## Safe Extraction Sequence

1. Freeze behavior with characterization tests for the exact owner surface being split.
2. Extract read-only formatting/rendering helpers first. Do not move route calls, filesystem mutation, settings persistence, queue mutation, pending drain, rename apply, or media policy in the first slice.
3. Extract pure DTO normalization and status-row construction.
4. Extract route-client wrappers only after route ownership guardrails are green.
5. Extract backend pure validators/policies with unit tests before moving orchestration code.
6. For PowerShell, extract pure functions into `ops/pipeline/engine/<domain>/` and prove module loader order remains stable.
7. For Tauri, split Rust modules while preserving command signatures and event names.
8. Only after pure extractions are stable, consider moving stateful orchestration boundaries.
9. For FFmpeg/subtitle/audio/publish/source movement changes, run release gate plus representative real-media validation.
10. Refresh generated summaries and change-control packet coverage after code edits.

## Estimated Effort and Expected Benefit

| Area | Effort | Benefit | Notes |
|---|---|---|---|
| WebView render-helper extractions | M/L | High | Most benefit with low behavior risk if route ownership stays fixed. |
| WebView route/state extractions | L/XL | High | Requires browser smokes and route-ownership guardrails. |
| Python network facade split | XL | High | Broad coupling and network lifecycle blast radius. |
| Python settings wizard split | L | Medium/High | Good candidate for validator extraction. |
| Completed policy split | L | High | Improves output trust changes and test focus. |
| PowerShell probe split | XL | High | High safety value but requires real-media/probe coverage. |
| PowerShell entrypoint split | XL | High | Dispatch behavior must be characterized first. |
| Tauri backend lifecycle split | L/XL | High | Must preserve launch/close/event semantics. |
| Config contract/schema split | L/XL | High | Requires Python/PowerShell schema alignment. |
| Docs remediation changelog indexing | M | Medium | Improves onboarding without behavior risk. |

## Validation Recommendations by Risky Area

| Risky Area | Minimum Before Touching | Escalate To |
|---|---|---|
| WebView JS/HTML/CSS | Node syntax/static checks, `npm run webview:prework:check`, targeted WebView tests | Browser smoke and `ops/scripts/smoke/Test-WebView*` when visible behavior changes |
| Queue/launch scope | Queue source path tests, launch command button/readiness tests, Local API start/control tests | Release reliability and real-media pilot if queue processing behavior changes |
| Settings/config | Config contract tests, config key registry checks, settings patch/live smokes | Release gate if persisted schema/default behavior changes |
| Pending publish/drain | Pending publish safety/ownership tests, Local API pending-publish tests | Real-media deferred publish/drain validation |
| Completed/output trust | Completed policy tests, completed/pending proof smokes, sample validation tests | Real-media final-placement playback/proof validation |
| FFmpeg/probe/remux/encode | Media verification, dynamic HDR, encode flag, quality checks | Full release gate plus representative real-media samples |
| Subtitle/audio | Subtitle builder, SRT validation, file override subtitle burn, audio policy tests | Real-media subtitle/audio samples |
| Source/scratch/output movement | Path boundary, disk/robocopy, source policy tests | Adversarial kill plus real-media validation |
| Command journal/strict JSON | Command journal policy/contracts, strict JSON route tests | WebView command evidence smoke |
| Tauri lifecycle | Tauri check-only/launch/close, production surface, close-readiness tests | Package-mode open/close validation |
| Network coordinator/worker | Coordinator/worker workflow, security, lifecycle, source policy tests | Multi-node/manual network validation if behavior changes |

## Open Questions

- Should `docs/REMEDIATION_CHANGELOG.md` remain an active giant ledger, or should current docs link to a smaller generated index plus archived historical sections?
- Should the WebView split tooling expand beyond `app.js` and `settingsView.js` to rank `networkView.js`, `queueView.js`, `launchView.js`, and `pendingPublishView.js` explicitly?
- Are generated JSON artifacts such as `WEBVIEW_PUBLIC_CONTRACT_BASELINE.json` and `symbol_inventory.json` meant to be part of maintainability risk tracking, or should reports treat them as build outputs only?
- Should `src/mediapipeline/core/validation/strict_json.py` get direct tests, or is its coverage intentionally through HTTP helper and route tests?
- Which of the many current dirty/untracked files in this worktree represent accepted baseline work versus in-progress work? This affects churn-risk interpretation.

## Appendix: Reviewed Files and Search Evidence

Primary required reads:

- `AGENTS.md`
- `docs/CURRENT_PROJECT_STATE.md`
- `docs/OPEN_WORK_CHECKLIST.md`
- `docs/generated/PROJECT_INDEX.md`

Generated summaries checked for shortlisted files included:

- `docs/generated/summaries/apps/desktop/webview/static/assets/networkView.js.md`
- `docs/generated/summaries/apps/desktop/webview/static/assets/queueView.js.md`
- `docs/generated/summaries/apps/desktop/webview/static/assets/settingsView.js.md`
- `docs/generated/summaries/apps/desktop/webview/static/assets/launchView.js.md`
- `docs/generated/summaries/apps/desktop/webview/static/assets/pendingPublishView.js.md`
- `docs/generated/summaries/src/mediapipeline/core/network/facade.py.md`
- `docs/generated/summaries/src/mediapipeline/core/config/settings_wizard.py.md`
- `docs/generated/summaries/ops/pipeline/engine/probe/media_probe.ps1.md`
- `docs/generated/summaries/ops/pipeline/entrypoints/MediaPipeline.ps1.md`
- `docs/generated/summaries/apps/desktop/tauri/src-tauri/src/lib.rs.md`
- `docs/generated/summaries/apps/desktop/tauri/src-tauri/src/backend_process.rs.md`
- `docs/generated/summaries/src/mediapipeline/contracts/config.py.md`

Representative searches:

- `rg --files docs/generated/summaries`
- `rg -n "FFmpeg|subtitle|audio|source|scratch|output|Pending publish|queue|settings|Command journal|close-readiness|Tauri|Network|rename" docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`
- `rg -n "networkView|queueView|settingsView|launchView|pendingPublishView|MediaPipeline\\.ps1|media_probe|pending_push|strict_json|command_journal|source_path_policy|disk\\.ps1|config\\.py|config\\.schema" docs/inventories/RISKY_FILE_REGISTRY.v1.json docs/testing/TEST_COVERAGE_MATRIX.md docs/inventories/TEST_SUITE_SUBSYSTEM_INVENTORY.md`
- `rg -n "WebView|god-file|split|network|queue|settings|pending|publish|launch|rename" docs/generated/WEBVIEW_GODFILE_SPLIT_MAP.md docs/testing/WEBVIEW_GODFILE_SPLIT_GUARDRAILS.md docs/generated/WEBVIEW_SPLIT_CANDIDATES.json`

Metric scan limitations:

- Incoming reference counts are string-match evidence, not a full semantic call graph.
- Test signal means direct file/module/path mentions, not line or branch coverage.
- WebView and Tauri summaries are often unparsed, so their responsibility breakdown is inferred from route/global metrics, tests, generated split maps, and active docs.
- The worktree was already heavily dirty before this audit; the ranking uses current file contents and does not attempt to distinguish baseline from unrelated in-progress changes.
- No source files were refactored or behaviorally modified during this audit.
