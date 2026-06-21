# docs/SESSION.md — Current session scope

Created: 2026-06-02
Branch: master
Operator-approved scope (chat, 2026-06-02): execute ADR-0013 Wave 1 step 1,
Wave 2 (steps 2-3), Wave 3 (steps 4-5), Wave 4 (step 6), then Wave 5
(steps 7-8) on follow-up approval ("just continue").

## Encoder runtime matrix HDR coverage 2026-06-21

Scope: continue the encoder breadth/AV1 remediation stream by extending the
descriptor-owned runtime matrix test with synthetic HDR10 coverage for
HDR-capable descriptors. Packet
`ops/release/changes/unreleased/MP-CHANGE-2026-0621-013.json`.

In scope:
- Add HDR10 synthetic matrix rows for HEVC CPU, HEVC/NVENC, and AV1/NVENC
  descriptor topology.
- Build descriptor flags before hardware runtime skips so dormant hardware rows
  still prove HDR flag shape without requiring host hardware.
- Execute only runtime-available rows; hardware execution remains gated by
  `MEDIAPIPELINE_ENCODER_RUNTIME_HARDWARE=1`.
- Assert executed HDR rows produce 10-bit BT.2020 non-constant-color-space output.

Out of scope: enabling dormant hardware descriptors, changing `Do-Encode`,
changing FFmpeg production argument generation, changing quality offsets,
running real-media validation, or certifying HDR side-data preservation for real
operator media.

## Encoder capability Launch preflight evidence 2026-06-21

Scope: continue the encoder breadth/AV1 remediation stream by threading the
existing backend-authored descriptor capability report into pipeline Launch
preflight as non-blocking read-only evidence. Packet
`ops/release/changes/unreleased/MP-CHANGE-2026-0621-012.json`.

In scope:
- Reuse the bounded settings capability report reader for Launch preflight.
- Add a backend-authored `encoder_capability_report` preflight row for pipeline
  starts.
- Treat missing or warning evidence as review-only; start blocking remains owned
  by existing launch guards.
- Update route/artifact/test/status docs and targeted Python tests.

Out of scope: generating the capability diagnostic, running FFmpeg from
preflight, changing saved settings, filtering choices, enabling dormant hardware
descriptors, changing encoder selection/fallback behavior, queue/network
behavior, source/scratch/output movement, pending publish, and real-media
validation.

## Encoder capability Settings WebView annotations 2026-06-21

Scope: continue the encoder breadth/AV1 remediation stream by rendering the
backend-authored `encoder_capability_report` from `/api/settings/workspace` in
the Settings Media Output tab as read-only encoder/backend availability
annotations. Packet `ops/release/changes/unreleased/MP-CHANGE-2026-0621-011.json`.

In scope:
- Add a read-only Settings Media Output evidence panel for existing descriptor
  capability report rows.
- Annotate video-builder guidance with the saved capability report status.
- Keep all `VideoCodec` and `EncoderBackend` choices visible; unavailable
  capability rows are advisory evidence only.
- Update WebView static tests, DOM inventory, generated summaries, and active
  Phase 6 docs.

Out of scope: generating the capability diagnostic, running FFmpeg from WebView,
filtering or removing dropdown choices, enabling dormant hardware descriptors,
changing encoder selection/fallback behavior, launch preflight, queue/network
behavior, source/scratch/output movement, pending publish, and real-media
validation.

## Encoder breadth settings workspace capability evidence 2026-06-21

Scope: continue the encoder breadth/AV1 remediation stream by threading existing
descriptor capability diagnostic evidence into the read-only Settings workspace.
Packet `ops/release/changes/unreleased/MP-CHANGE-2026-0621-010.json`.

In scope:
- Read `State\Progress\encoder_capabilities.json` when the backend-owned
  diagnostic artifact already exists.
- Expose a bounded, summarized, read-only `encoder_capability_report` object from
  `/api/settings/workspace`.
- Treat missing or malformed reports as non-blocking Settings workspace evidence.
- Update route/artifact/test/status docs and targeted Python tests.

Out of scope: running FFmpeg from the settings route, generating the diagnostic
artifact, changing encoder selection, activating hardware descriptors, filtering
WebView choices, launch/preflight behavior, queue/network behavior, source/scratch
output movement, pending publish, and real-media validation.

## Encoder breadth Phase 6 settings exposure 2026-06-21

Scope: continue the encoder breadth/AV1 remediation stream by exposing the
dormant global `EncoderBackend` key in the WebView video detail settings
builder, without activating new hardware encoder families or changing
`Do-Encode` selection behavior. Packet
`ops/release/changes/unreleased/MP-CHANGE-2026-0621-009.json`.

In scope:
- Add the `EncoderBackend` select to the WebView video detail builder.
- Ensure the builder syncs/saves the key through existing backend-owned settings
  save validation.
- Update WebView static tests and active docs/inventories to show the key is
  directly surfaced but still dormant for runtime selection.

Out of scope: FFmpeg command generation, descriptor activation, capability-based
choice filtering, queue/network behavior, source/scratch/output movement,
pending-publish drain behavior, and real-media validation.

## Network worker hardening A1 2026-06-14 (operator requested "execute this MD")

Scope: execute the first work item only from
`docs/architecture/NETWORK_WORKER_HARDENING_PLAN.md`, per the plan's
one-item-per-session rule. A1 surfaces when a running worker dispatcher is
using coordinator URL, auth-token fingerprint, or source-path-map settings that
no longer match saved config. Packet
`ops/release/changes/unreleased/MP-CHANGE-2026-0614-005.json`.

In scope:
- Added token-safe running dispatcher evidence via
  `WorkerDispatcher.runtime_descriptor()`.
- Added backend `running_vs_saved` network worker evidence with status,
  drift fields, summary lines, warnings, and `Running with drift` runtime
  severity when applicable.
- Added WebView Network and Home read-only drift visibility; token values
  remain hidden and only fingerprints are compared.
- Added focused Python tests for match/drift behavior and a WebView static
  guard assertion for the new drift UI contract.

Out of scope: lifecycle route mutation behavior, queue claim behavior,
media/FFmpeg/subtitle/audio policy, source/scratch/output movement, and
pending-publish drain behavior.

Validation performed (agent-side):
- `node --check apps\desktop\webview\static\assets\networkView.js` passed.
- `node --check apps\desktop\webview\static\assets\app\home.js` passed.
- `PYTHONPATH=src apps\desktop\runtime\Python\python.exe -m unittest -q tests.python.desktop.test_network_drift_descriptor tests.python.desktop.test_application_facade_network tests.python.desktop.test_network_worker_runtime tests.webview.test_webview_network_read_only_boundary` -> 57 tests OK.
- `PYTHONPATH=src apps\desktop\runtime\Python\python.exe -m unittest discover -s tests/python/desktop -p "test_network*.py" -q` -> 276 tests OK.
- `pwsh -NoProfile -File ops\scripts\smoke\Test-WebViewBrowserNetworkSmoke.ps1` -> 1 test OK.

## Network worker hardening A2 2026-06-14 (operator requested "execute the next part")

Scope: execute the next single work item from
`docs/architecture/NETWORK_WORKER_HARDENING_PLAN.md`, per the plan's
one-item-per-session rule. A2 adds a read-only worker test-connection preflight
that separates coordinator TCP reachability, signed coordinator auth, and worker
library/source-output path accessibility. Packet
`ops/release/changes/unreleased/MP-CHANGE-2026-0614-006.json`.

In scope:
- Added auth-required coordinator `GET /api/ping`, returning a bounded no-op
  ping response with server time.
- Added worker local API `POST /api/network/worker/test-connection`, owned by
  the backend command route contract, with `effect=none`, `journaled=false`, and
  `suppress_command_journal=true` in the command result data.
- Added L1 TCP, L2 signed ping, and L3 read-only path accessibility reporting;
  the command does not write, claim, start, stop, save settings, touch media, or
  drain/publish.
- Added WebView Network-page button/result rendering, Tauri required-route
  coverage, command ownership matrix updates, and focused Python/WebView tests.

Out of scope: claim contract changes, worker lifecycle mutation behavior, queue
dispatch behavior, media/FFmpeg/subtitle/audio policy, source/scratch/output
movement, pending-publish drain behavior, and live cluster UI-button execution.

Validation performed (agent-side):
- `PYTHONPATH=src apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_network_test_connection` -> 5 tests OK.
- `PYTHONPATH=src apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_network_test_connection tests.python.desktop.test_network_coordinator_helpers tests.python.desktop.test_network_coordinator_http tests.python.desktop.test_api_contract_payload tests.python.desktop.test_api_command_contracts tests.python.desktop.test_application_facade_local_api tests.webview.test_webview_network_read_only_boundary tests.webview.test_webview_frontend_mutation_boundary` -> 159 tests OK.
- `node --check apps\desktop\webview\static\assets\networkView.js` passed.
- `PYTHONPATH=src apps\desktop\runtime\Python\python.exe -m unittest tests.python.desktop.test_tauri_shell_scaffold tests.webview.test_webview_browser_network_smoke` -> 90 tests OK.
- `pwsh -NoProfile -File ops\scripts\smoke\Test-WebViewBrowserNetworkSmoke.ps1` -> 1 test OK.
- `PYTHONPATH=src apps\desktop\runtime\Python\python.exe -m unittest discover -s tests\python\desktop -p "test_network*.py"` -> 282 tests OK.
- `ops\scripts\dev\start-tauri-preview.bat -CheckOnly` passed; this verifies prerequisites and does not launch WebView2/process media/validate FFmpeg/pending publish.
- `powershell -ExecutionPolicy Bypass -File apps\desktop\tauri\Test-TauriShell-Build.ps1` passed: JS syntax check, cargo check, and 38 Rust tests OK.
- `PYTHONPATH=src apps\desktop\runtime\Python\python.exe ops\scripts\dev\run-python-tool.py mediapipeline.tools.change_control.validate_changes` passed: 281 packets valid.
- Strict change coverage `validate_changes --require-worktree-coverage` exits 1 only because four unrelated dependency-atlas assets are dirty and uncovered:
  `docs/generated/dependency-atlas/assets/dependency_detail_core_library.{png,svg}` and
  `docs/generated/dependency-atlas/assets/dependency_detail_desktop_watch.{png,svg}`.

## Handoff 2026-06-12 -- release Verify unblock (operator-approved in chat: "Fix both root causes"; separate from all other scopes)

Operator reported the deployment package "keeps failing". Root cause: the build copies files and
writes the manifest fine; the failure is the optional in-package self-test (ops/scripts/release/test.ps1,
run when "Verify package" is enabled). Two `-Required` gates failed. Packet
`ops/release/changes/unreleased/MP-CHANGE-2026-0612-007.json`.

Fixes applied (no runtime behavior changed):
- `docs/architecture/dependency_boundary_allowlist.txt` -- added a dated block of 9 entries (7
  NO_CORE_TO_DESKTOP for diagnostics.tdarr_matrix_audit, library.facade, metrics.facade x2 targets,
  metrics.policy, metrics.sources, subtitles.facade; 2 NO_PACKAGE_CYCLES for completed<->subtitles).
  These modules gained desktop coupling after the 2026-06-05 allowlist snapshot and were the only
  unallowlisted hard findings. check_dependency_boundaries now exits 0 (0 unallowlisted/unused/errors).
- `src/mediapipeline/tools/dev/check_legacy_removal_readiness.py` -- `_git_ls_files` now falls back to a
  filesystem walk (new `_filesystem_ls_files`) when REPO_ROOT is not a git work tree (git exit 128) or git
  is missing, instead of crashing (exit 2) inside a git-less release package. Git-work-tree behavior
  unchanged. Added 3 fallback unit tests in `tests/python/desktop/test_legacy_removal_readiness.py`.
- Refreshed the 2 summaries for the edited files.

Validation (agent-side): check_dependency_boundaries --max-internal-imports 1 -> exit 0;
check_legacy_removal_readiness (source) -> exit 0; test_legacy_removal_readiness -> 10/10 OK; full package
rebuild with -Verify confirmed both gates now pass in package mode.

Update (operator then chose "fully green the Verify self-test"): added a third, durable structural fix.
NEW `src/mediapipeline/tools/dev/release_package_scope.py` reads `release_manifest.json`; when
`tests_included=false`, `refresh_summaries`, `generate_project_index`, and `generate_feature_file_map`
`--check` ignore paths under `tests/` and `ops/pipeline/tests/`. Proven in the real package:
feature-map REFERENCED_PATH_MISSING 17->0 (exit 0), summary-freshness orphans 329->0, project-index
test-orphan findings ->0. Source/CI behavior unchanged (no manifest at source root). New unit test
`tests/python/tooling/test_release_package_scope.py` (6 cases). Also regenerated the source summaries +
project index/dependency graph.

STILL NOT green (environmental, NOT a code defect): the residual in-package Verify failures are stale
non-test summaries/project-index and two DOC005 active-doc lints
(docs/implementation/objective-quality-verification-plan.md:618 and
docs/reviews/function-module-audit-2026-06-11/workers/W10-ops-powershell-scripts.md:45). These are driven
by other concurrent sessions editing the working tree LIVE -- empirically confirmed: files this work never
touched (tdarr_matrix_console.py, contract_command.py, app.js, page-home.html, plus new tdarr_proof_pack.py
/ tdarr_matrix_proof.py) went stale within minutes of a full `refresh_summaries --all`. A stable green UI
Verify additionally requires the tree to be quiesced/committed at build time, OR making those source/CI
freshness+active-doc gates advisory in package mode (a small test.ps1 change). Immediate working package:
build with "Verify package" off -- contents are identical (Verify is a post-copy self-test).

## Telemetry GPU spawn-cadence 2026-06-12 (operator-approved in chat: "go")

Scope: reduce the periodic system stutter that appears when the desktop app and
an external coding agent (Codex) run at once. Investigation found the telemetry
sampler spawned `nvidia-smi.exe` every 2s (TELEMETRY_INTERVAL_SECONDS), an
unconditional background process-spawn cadence that contends with the agent's
reindex disk-scan/process storm. Not an AGENTS.md section 7 area (telemetry is
not listed); agent-side validation permitted.

In scope (changed):
- `src/mediapipeline/core/telemetry/service.py` — added
  `GPU_TELEMETRY_INTERVAL_SECONDS = 12.0`; split GPU probing into
  `_apply_gpu_telemetry`, which now spawns `nvidia-smi` at most every 12s and
  reuses the last parsed rows on intermediate cycles. CPU/mem keep the 2s
  cadence. `sample_system_telemetry` gained an optional `now` arg for
  deterministic testing. Fixed the stale comment that referenced a 4s UI refresh
  (actual cadence is 15s, app.js AUTOMATIC_REFRESH_INTERVAL_MS).
- `tests/python/desktop/test_telemetry_service.py` — added
  `test_gpu_probe_respects_sub_cadence_and_reuses_cached_rows`.

Effect: nvidia-smi spawns drop ~6x (every 2s -> every 12s). GPU dashboard values
become at most ~12s stale; CPU/mem/headline cadence unchanged; `/api/telemetry`
payload shape unchanged.

Out of scope (not touched): watch-folder scanner ignore-list (investigation
suspect #2), webview `refreshAll` fan-out/visibility gating (suspect #3),
`system_metrics.py`, `nvidia.py`, any media/FFmpeg/queue/publish path.

Validation (agent-side, AGENTS.md section 5 diagnostics rung):
- `PYTHONPATH=src apps\desktop\runtime\Python\python.exe tests\python\desktop\test_telemetry_service.py -v`
  -> 25 tests OK (bundled Python lacks pytest; ran the unittest file directly with
  PYTHONPATH=src because the module's `sys.path` insert follows its first import).

## Encoder breadth + AV1 Phase 0 2026-06-11 (operator requested "Execute this")

Scope: execute Phase 0 only from
`docs/implementation/encoder-breadth-av1-plan.md`. The plan explicitly requires
one phase per session and operator sign-off before later phases. This phase is
test-only characterization for FFmpeg encode argument generation.

In scope:
- NEW `ops/pipeline/tests/Unit/Invoke-EncodeFlagPolicyChecks.ps1` with current
  `New-EncodeAttemptPlan(...).ArgumentList` snapshots and retry truth-table
  assertions.
- `docs/generated/summaries/` mirror for the new test after validation.
- Change packet `ops/release/changes/unreleased/MP-CHANGE-2026-0611-300.json`.

Out of scope:
- Production code edits, encoder descriptors, config keys, capability probing,
  AV1/QSV/AMF behavior, `Do-Encode`, audio/subtitle/publish/queue/source/scratch
  movement, and real-media validation. Those are later plan phases.

Validation rung: AGENTS.md section 5 media row is acknowledged because this area
pins FFmpeg command generation. Phase 0 itself changes no production behavior, so
agent-side validation is the plan's three-command unit/smoke set plus summary and
change-control validation. No operator media gate is required for Phase 0.

Status 2026-06-11: Phase 0 implemented. Added 22 current-behavior argument-list
snapshots covering primary, safe hardware retry, CPU fallback, SDR/HDR, MKV/MP4,
ladder selection, CPU thread emission, and complex segment ordering. Added retry
truth-table assertions for success, stop, ForceCpu, NVENC, AMF, QSV, and generic
stderr cases. No production files changed.

Validation performed (agent-side):
- `pwsh -NoProfile -File ops\pipeline\tests\Unit\Invoke-EncodeFlagPolicyChecks.ps1`
  passed twice; snapshot count 22.
- `pwsh -NoProfile -File ops\pipeline\tests\Unit\Invoke-MediaRouteSelectionChecks.ps1`
  passed.
- `pwsh -NoProfile -File ops\pipeline\tests\Invoke-EndToEndSmokeChecks.ps1`
  passed.
- Targeted `refresh_summaries --paths` wrote the new test and packet summaries.

Strict change-control result: after fixing this packet's type to `test`, rerun
`validate_changes --require-worktree-coverage`. Any remaining failures are
unrelated to this Phase 0 scope and must be reported in the final response.

## Objective quality verification (VMAF/SSIM/PSNR) 2026-06-11 (operator-approved; plan: docs/implementation/objective-quality-verification-plan.md)

AGENTS.md section 7 applies: encode acceptance gating, settings schema, FFmpeg invocation adjacency,
and publish gating. NOT self-certified; operator real-media validation rung is required before final
sign-off (see plan section 12).

In-scope files:
- NEW `ops/pipeline/engine/verify/quality.ps1`; `ops/pipeline/entrypoints/MediaPipeline/module_loader.ps1`
- `ops/pipeline/engine/config/{config_keys,config_schema,default_values,choice_registry,runtime_config}.ps1`
- `ops/pipeline/config/schemas/media_pipeline_config.schema.json`; `ops/pipeline/config/MediaPipeline_config_template.psd1`; `ops/pipeline/config/profiles/Default.psd1`
- `ops/pipeline/engine/shared/failure_codes.ps1`; `ops/pipeline/engine/failures/failure_state.ps1`
- `ops/pipeline/entrypoints/MediaPipeline/encode.ps1`; `ops/pipeline/engine/process/pipeline_processing.ps1`
- `ops/pipeline/engine/publish/publish_completion.ps1`; `ops/pipeline/engine/paths/output_evidence.ps1`
- `src/mediapipeline/core/kernel/{config_key_order,config_key_groups}.py`; `src/mediapipeline/contracts/config.py`
- `src/mediapipeline/core/config/metadata_parts/<chosen part>.py`; `src/mediapipeline/desktop/application/settings_risk_policy_rules.py`
- `src/mediapipeline/core/completed/{policy,trust_fields,validation_state}.py`
- NEW `apps/desktop/webview/static/assets/settingsView.builders.quality.js`; `apps/desktop/webview/static/assets/settingsView.js`; `apps/desktop/webview/static/assets/settingsMetadata.js`
- `apps/desktop/webview/static/index.html`; `apps/desktop/webview/static/partials/page-settings.html`
- NEW `ops/pipeline/tests/Unit/Invoke-QualityVerificationChecks.ps1`; targeted Python/WebView test updates
- `docs/inventories/{WEBVIEW_DOM_ID_INVENTORY,SETTINGS_BUILDER_COVERAGE_MATRIX,SETTINGS_KEY_OWNERSHIP_MAP}.md`
- `docs/architecture/CONFIG_KEY_GLOSSARY.md`; `CHANGELOG.md`; generated summaries for changed source files; change packet `MP-CHANGE-2026-0611-202`

Out of scope:
- Remux behavior, routing/decide, audio/subtitle policy, scratch copy, cleanup, queue, drain, rename.
- Pending publish parking/drain changes for quality-failed outputs.
- Library-profile or worker-override exposure of the quality keys.
- New progress stage strings, VMAF model files, ffmpeg bundle changes, top-level Markdown files, archive/vendor/local-runtime edits.

## Handoff 2026-06-11 -- objective quality verification: implementation review + fixes (packet MP-CHANGE-2026-0611-202)

Status: implementation reviewed against docs/implementation/objective-quality-verification-plan.md and found
faithful; review findings fixed this session (operator-approved in chat: "please fix those issues"). Agent-side
validation green. AGENTS.md section 7 NOT self-certified; operator real-media rung still required (below).
Ollama: not used.

Review verification performed (agent-side, 2026-06-11):
- Invoke-ConfigKeyRegistryChecks (156 keys), Invoke-FailureCodeRegistryChecks, Invoke-ContractSchemaChecks,
  Invoke-QualityVerificationChecks (includes live synthetic ffmpeg ordering case), end-to-end smoke: all exit 0.
- -ValidateOnly exit 0 (loader contract incl. QualityVerify.ps1); -DumpEffectiveConfigPath shows all 9 quality
  keys with planned defaults.
- Bundled Python unittest: test_config_keys, test_metadata_contract, all test_*completed* (56),
  test_service_completed_validation_state (incl. T6 passthrough pin), test_settings_risk_policy_rules,
  test_facade_completed_policy (3 quality cases): all OK. node --check clean on both touched JS files.
- Plan trap index audited T1-T10; all honored. Log-path escaping form (C\\:) proven against the bundled
  ffmpeg 8.1 (libvmaf JSON log written and parsed).

Fixes applied this session:
- docs/inventories/WEBVIEW_GLOBAL_EXPORT_INVENTORY.md -- synced to live assets: tauriLifecycleBridge.js now
  exports the mediaPipelineTauriLifecycleBridge namespace (uncommitted change from another session), so the
  summary counts (34 namespace / 38 no-namespace), module table row, and generated manifest section were
  updated. test_webview_inventory_docs now 4/4 OK (was 2 failures).
- ops/release/changes/unreleased/MP-CHANGE-2026-0611-160.json (NEW) -- coverage-only docs packet for the
  orphaned worker-08-webview-pages.md audit report (every other worker report already had a packet).
- ops/pipeline/entrypoints/MediaPipeline/encode.ps1 -- quality hook now sets the encode_verify progress Status
  to "Verifying encode quality (<metric>)" so long VMAF runs do not look stalled (status text only; stage
  label unchanged).
- This handoff block (the scope block above predates it).

Known unabsorbed coverage gap (NOT mine): validate_changes --require-worktree-coverage exits 1 only on
apps/desktop/tauri/src-tauri/src/backend_contract/routes.rs, a live in-flight edit by a concurrent session
(modified 2026-06-11 17:50 during this review); its owning session should cover it. All quality-feature files
are covered by MP-CHANGE-2026-0611-202.

Operator validation REQUIRED before section-7 sign-off (plan section 12): real encode with verification on
(score on Completed page, overhead recorded); deliberately bad encode with QualityFailAction=block_review
confirming ENCODE_QUALITY_BELOW_FLOOR and no publish; one remux-route file (no quality stage); one 4K/10-bit
encode (sane score); ai_guardrail preflight/postflight; WebView settings smokes.

## Dynamic HDR preservation Phase 1 2026-06-11 (operator-approved in chat)

Operator request: execute `docs/implementation/dynamic-hdr-preservation/PLAN.md`.
Per the plan, only Phase 1 is in scope for this session; Phases 2-4 require
separate operator approval and validation.

In-scope files:
- `ops/pipeline/engine/probe/media_probe.ps1` -- additive Dolby Vision and
  HDR10+ detection helpers plus a pure dynamic-HDR evidence builder.
- `ops/pipeline/entrypoints/MediaPipeline/encode.ps1` -- probe HDR sources after
  HDR10 static metadata probing, warn and emit a pipeline event when encode will
  drop dynamic metadata, and reset per-file evidence state.
- `ops/pipeline/entrypoints/MediaPipeline/remux.ps1` -- probe HDR remux sources
  after the remux route is committed and record expected-pass-through evidence.
- `ops/pipeline/engine/publish/publish_completion.ps1` -- add dynamic-HDR
  evidence to immediate-publish sidecars/completed manifest entries.
- `ops/pipeline/tests/Unit/Invoke-DynamicHdrDetectionChecks.ps1` -- stubbed
  ffprobe coverage for DoVi/HDR10+ detection and evidence outcomes.
- `CHANGELOG.md`, `docs/generated/summaries/`, and change packet
  `ops/release/changes/unreleased/MP-CHANGE-2026-0611-201.json`.

Out of scope:
- No config keys, new tools, module-count changes, route forcing, command
  generation, x265 parameter changes, preservation extraction, or verification
  gate.
- Parked-then-drained outputs may lack `dynamic_hdr` evidence until Phase 4
  carries evidence through the pending-publish manifest.
- WebView badges/chips for dynamic HDR evidence are a separate UI follow-up.

Validation rung (AGENTS.md section 5 and No-Touch register): agent-side
PowerShell parse checks, new unit check, end-to-end smoke, and sidecar schema
check if a sidecar schema changes. Operator-side real-media validation remains
required for section-7 sign-off: one DoVi source, one HDR10+ source, and one
plain HDR10 source through `-Once`, confirming the warning/event/sidecar evidence.

Operator confirmation 2026-06-11: Phase 1 real-media validation passed for
DoVi, HDR10+, and plain HDR10 samples. This unblocked Phase 2.

## Dynamic HDR preservation Phase 2 2026-06-11 (operator-approved in chat)

Scope: execute Phase 2 from
`docs/implementation/dynamic-hdr-preservation/PLAN.md` after the operator
confirmed Phase 1 validation passed. Approved tool versions:
`dovi_tool` 2.3.2 and `hdr10plus_tool` 1.7.2.

Implemented:
- Added ignored operator drop-zone notes and MIT license files under
  `ops/pipeline/tools/dovi_tool/` and
  `ops/pipeline/tools/hdr10plus_tool/`. Executables remain operator-placed;
  SHA-256 fields are pending until binaries exist.
- Added `ops/pipeline/engine/process/dynamic_hdr.ps1` with dynamic-HDR policy
  helpers, config/bundled/PATH tool resolution, version parsing, tool
  availability reporting, and cached x265 dynamic-HDR capability answer.
- Registered the process module in `MediaPipeline/module_loader.ps1` and wired
  nonfatal startup resolution in `MediaPipeline.ps1`.
- Added config keys `DynamicHdrPolicy`, `DoviToolPath`, and
  `Hdr10PlusToolPath` across PowerShell config registry/default/template,
  Python config contract/key order/metadata, and generated schemas. These keys
  are global-only in Phase 2 because no per-library preservation behavior exists
  yet.
- Added `ops/pipeline/tests/Unit/Invoke-DynamicHdrToolingChecks.ps1`.

Out of scope / still pending:
- No executable binaries were downloaded or bundled by the agent.
- No SHA-256 values were recorded because the executables are absent.
- No FFmpeg/x265 command generation or preservation behavior changed.
- Phase 2 real remux-verdict evidence remains pending until operator-placed
  binaries and representative media fixtures are available.

Change packet: `ops/release/changes/unreleased/MP-CHANGE-2026-0611-304.json`.

## Watch-folder auto-start 2026-06-11 (operator-approved in chat; plan: docs/implementation/watch-folder-autostart/PLAN.md)

Implements watch-folder detection + optional gated auto-launch per the plan. AGENTS.md §7
contact: settings schema (5 new keys) and schedule-start adjacency -- NOT self-certified;
operator validation list in plan §12 required.

In-scope files:
- NEW src/mediapipeline/desktop/watch/{__init__,scanner,manager}.py
- EDIT src/mediapipeline/desktop/application/facade.py (manager init + start/stop/state hooks)
- EDIT src/mediapipeline/desktop/api/server.py (stop hook)
- EDIT src/mediapipeline/desktop/local_api_main.py (startup step + manager start)
- EDIT src/mediapipeline/desktop/api/{routes_read,read_payloads_status,contract_read}.py (status route)
- Config-key registration set from plan §5 (contracts/config.py + generated config.v1.schema.json,
  core/kernel/config_key_{s,_order,_groups}.py, core/config/metadata_parts/watch_fields.py + aggregator,
  ops/pipeline/engine/config/{config_keys,default_values,schema_keys}.ps1,
  ops/pipeline/config/schemas/media_pipeline_config.schema.json,
  ops/pipeline/config/MediaPipeline_config_template.psd1, ops/pipeline/config/profiles/Default.psd1,
  apps/desktop/webview/static/assets/settingsMetadata.js + settings builder,
  docs/architecture/CONFIG_KEY_GLOSSARY.md, docs/inventories/SETTINGS_* and API route inventories)
- EDIT apps/desktop/webview/static/assets/scheduleView.js (+ apiClient wiring, DOM/export inventories)
- NEW tests/python/desktop/test_watch_folder_{scanner,manager,routes}.py
- docs/generated/summaries/ mirrors; CHANGELOG.md; change packet
  `ops/release/changes/unreleased/MP-CHANGE-2026-0611-203.json`.

Out of scope: everything in plan §9; all other AGENTS.md §7 areas; engine behavior.
Validation rung: plan §11. Exit criteria: plan phases 0-6 green + handoff written.

Status 2026-06-11: implemented through focused unit/static validation. The feature
is disabled by default. `enqueue_only` records pending work; `enqueue_and_launch`
requests backend Run Once through existing launch gates, with worker disabled and
coordinator forced to enqueue-only.

Validation performed (agent-side):
- `py_compile` passed for changed watch/API/facade Python files and new tests.
- `node --check` passed for changed WebView JS files.
- `python -m unittest tests.python.desktop.test_watch_folder_scanner tests.python.desktop.test_watch_folder_manager tests.python.desktop.test_watch_folder_routes` passed (18 tests).
- `python -m unittest tests.webview.test_webview_schedule_smoke tests.webview.test_webview_inventory_docs.WebViewInventoryDocsTests.test_dom_inventory_manifest_matches_index_html` passed.
- `python -m unittest tests.python.desktop.test_local_api_lifecycle_contract_smoke tests.python.desktop.test_application_facade_schedule tests.python.desktop.test_schedule_stop_watcher` passed.
- `pwsh -File ops\pipeline\tests\Unit\Invoke-ConfigKeyRegistryChecks.ps1` passed.
- `pwsh -File ops\pipeline\tests\Unit\Invoke-ContractSchemaChecks.ps1` passed.
- Live local API/browser smoke: started `http://127.0.0.1:8765` with an explicit
  token, `/api/health` reached `startup_progress.status=complete` with
  `watch_folders` detail `disabled`, Browser DOM check found
  `schedule-watch-folder-status`, `schedule-watch-folder-summary`, and
  `schedule-watch-folder-recent`, then PID 60484 was stopped and port 8765 was
  no longer listening.

Known unrelated validation drift in the current dirty worktree:
- `tests.python.core.contract.test_config_contract.ConfigContractTests.test_generated_schema_matches_config_contract`
  still fails because generated config schema contains pre-existing `Quality*` fields that are not in the live config-contract baseline.
- `tests.python.desktop.test_api_route_inventory` still fails on pre-existing Tdarr Matrix route inventory drift.
- WebView global export inventory checks still fail on pre-existing dirty WebView/global-export drift.

## TDARR Matrix audit gap remediation 2026-06-07 (operator-approved in chat; separate from kernel/entrypoint work)

Operator approved (chat, 2026-06-07: "begin working through the MD") implementing the
remediation items in `docs/dev/tdarr-matrix-audit-gaps.md`. Diagnostics/tooling domain;
NOT the kernel migration, entrypoint-slice, or telemetry work. Non-§7 (diagnostics audit
tool only; does not touch FFmpeg/subtitle/audio/publish/queue/settings behaviour).

In-scope files:
- `src/mediapipeline/core/diagnostics/tdarr_matrix_audit.py` (G1 derived runner timeout;
  G2 bucket-count constant).
- `src/mediapipeline/tools/dev/tdarr_matrix_audit.py`,
  `src/mediapipeline/tools/dev/materialize_tdarr_test_library.py` (later items: G6 etc.).
- `tests/python/desktop/test_service_tdarr_matrix_audit.py`,
  `tests/python/tooling/test_tdarr_matrix_audit.py` (G2 sync + G11 unit tests).
- `docs/dev/tdarr-matrix-audit-gaps.md` (status updates).
- `docs/generated/summaries/` mirrors for edited sources; change packet under
  `ops/release/changes/unreleased/`.

Validation rung (AGENTS.md §5): agent-side Python unit tests via
`apps\desktop\runtime\Python\python.exe`. G9 (strict-gate media-policy severity) is the only
§7-adjacent item and is deferred / not self-certified.

Status 2026-06-07: G1, G2, G4, G5, G6, G7, G8, G10, G11 implemented; G3 found already
mitigated (facade `_diagnostics_command_lock`) and given regression tests. 28/28 TDARR
unittests pass via bundled Python; summaries refreshed; change packet
`ops/release/changes/unreleased/MP-CHANGE-2026-0607-020.json` created/updated and valid. Full
per-gap log in `docs/dev/tdarr-matrix-audit-gaps.md`. G4 retention is opt-in CLI only
(--keep-last; UI never deletes). G9 resolved by operator decision as a documented advisory
(audio-only stays a warning; strict gate documented as static, no behavior change). All gaps
G1-G11 now addressed (G3 was a non-gap); no remaining work in this docs/SESSION.md scope.

## Config hardening #1 2026-06-02 (AGENTS.md §7; operator-approved this turn)

Task: startup self-heal for the live config so it cannot silently go missing.
Spans app/ + DesktopApp/ (operator approved "create the plan then perform it").

In-scope:
- NEW `app/config/recovery.py` -- `ensure_canonical_config(app_root,
  workspace_root)`: present / migrated (legacy _chatgpt -> canonical copy) /
  backup_available (names newest ConfigBackups entry) / absent. Filesystem
  only (no PowerShell), unit-testable.
- EDIT `src/mediapipeline/desktop/local_api_main.py` build_backend:
  call recovery before default_config_path(); add startup steps for the
  recovery outcome and a verify_config_loaded signal from resolved.config_data.
- NEW `tests/python/desktop/test_config_recovery.py`.

NOT self-certified (§7): operator restart + pending-publish smokes required.
No parsing/saving/publish behaviour changed; only config presence + startup
reporting.

Status 2026-06-02: implemented. Changed files:
- `app/config/recovery.py` (new) -- ensure_canonical_config + ConfigRecoveryResult.
- `src/mediapipeline/desktop/local_api_main.py` -- import; build_backend
  now runs recovery before default_config_path() (only when no explicit
  --config-path) and adds `recover_config` + `verify_config_loaded` startup steps.
- `tests/python/desktop/test_config_recovery.py` (new) -- 5 unit tests.

Validation (agent-side): compileall clean; recovery unit tests 5/5;
startup/facade tests 66 passed; full suite 1641 passed, 1 skipped, 1235
subtests, exit 0. End-to-end (runtime-sim) against the real layout:
recovery=present, startup steps recover_config=complete,
verify_config_loaded="settings loaded".

Operator validation REQUIRED before §7 sign-off:
- `.\ops\scripts\dev\start-local-api.bat` then confirm startup JSON shows
  `recover_config` and `verify_config_loaded` complete.
- `ops/scripts/smoke\Test-WebViewBrowserPendingDrainGuardSmoke.ps1` and
  `ops/scripts/smoke\Test-LocalApiLifecycleContractSmoke.ps1` (confirm no regression;
  this change does not touch publish/queue).
- `python -m mediapipeline.tools.dev.ai_guardrail`.

## Red-baseline cleanup 2026-06-03 (operator-approved; separate from kernel migration)

Wave-6 prerequisite: 8 failing tests caused by incomplete rename/settings
WebView work (live code added GET routes /api/rename/clean-filename-preview &
/api/rename/movie-cleaning-filters + new settings DOM/export functions) with
stale hand-maintained docs. NOT the kernel migration. Operator approved
fixing as a scoped doc-sync task.

In-scope (sync docs to live code only; no behaviour change):
- docs/inventories/API_ROUTE_INVENTORY.md
- docs/inventories/LOCAL_API_ROUTE_OWNERSHIP_MAP.md
- evidence-mutation matrix doc (per test_api_route_inventory)
- tauri required-routes list (apps/desktop/tauri scaffold)
- ops/scripts/smoke/Test-WebViewBrowserMaintenanceReportsSmoke.ps1 (add phrase)
- docs/inventories/WEBVIEW_DOM_ID_INVENTORY.md
- docs/inventories/WEBVIEW_GLOBAL_EXPORT_INVENTORY.md
New GET routes classified read/non-mutating; route-governance classifications
flagged for operator review.

## Config hardening #1b 2026-06-02 -- per-user config location (Tauri packaged)

Operator-approved (AskUserQuestion): packaged Tauri build can't find the
gitignored personal config because it's not bundled. Fix: resolve a per-user
location `%LOCALAPPDATA%\MediaPipelineRemuxEncodeAIO\MediaPipeline_config.psd1`
as a fallback for both dev and packaged.

In-scope:
- `app/paths/defaults.py` -- add user_config_dir()/user_config_candidates()
  (LOCALAPPDATA-based; [] if unset). Pure resolver default_config_path_for_roots
  left UNCHANGED (test stability).
- `app/paths/service.py` -- default_config_path(): local-if-exists else
  per-user-if-exists else local default.
- `app/config/recovery.py` -- per-user self-heal branch + seed_user_config().
- `tests/python/desktop/test_config_recovery.py` -- per-user tests with controlled
  LOCALAPPDATA.
- Seed: copy current ops/pipeline/config/MediaPipeline_config.psd1 -> per-user location.

NOT self-certified (§7 + Tauri lifecycle): operator must run a packaged Tauri
launch to confirm the backend now resolves the per-user psd1. No Rust/shell
change needed (backend already passes --app-root and no --config-path).

Status 2026-06-02: implemented. Design note: per-user selection lives at the
startup boundary (build_backend uses recovery.canonical_path), NOT in
service.default_config_path() -- putting it in the pervasive method caused
order-dependent failures (temp-root tests resolving the real per-user file).
service.default_config_path() and default_config_path_for_roots stay pure.

Changed files:
- `app/paths/defaults.py` -- user_config_dir()/user_config_candidates() +
  CONFIG_CANONICAL_NAME/CONFIG_LEGACY_NAME/PER_USER_APP_DIR_NAME constants.
- `app/config/recovery.py` -- imports names from defaults; per-user branch
  (user_present / user_migrated); seed_user_config().
- `src/mediapipeline/desktop/local_api_main.py` -- build_backend
  selects recovery.canonical_path when no explicit --config-path.
- `tests/python/desktop/test_config_recovery.py` -- per-user + seed tests with
  controlled LOCALAPPDATA (13 tests).
- Seeded: copied ops/pipeline/config/MediaPipeline_config.psd1 ->
  %LOCALAPPDATA%\MediaPipelineRemuxEncodeAIO\MediaPipeline_config.psd1 (19991 B).

Validation (agent-side): compile clean; recovery+path tests 15/15 then full
recovery 13/13; full suite 1648 passed, 1 skipped, 1235 subtests, exit 0.
End-to-end: DEV resolves local repo config (present); PACKAGED-sim resolves
the real per-user config (user_present).

Operator validation REQUIRED (§7/Tauri): launch the packaged Tauri build and
confirm startup shows recover_config=complete (user_present) and
verify_config_loaded="settings loaded"; pending-publish + local-API contract
smokes for regression.

## Packaged Tauri "settings not loading" 2026-06-02 -- root cause + rebuild

Symptom: packaged Tauri build showed defaults / "settings loaded=no".
Root cause (proven): the running app was a STALE package from 2026-05-29
(`%TEMP%\MediaPipelineRemuxEncodeAIO_Deployable_Codex_20260529_*`). Its
bundled Python predates the recovery/per-user fix (no recovery.py, no
user_config_dir, no recover_config step) AND it shipped with only
`MediaPipeline_config_template.psd1` (no live config). Its old resolver
pointed at a non-existent `_chatgpt` path -> config never loaded. The
per-user fix/seed cannot help that bundle because its code never checks
per-user. No package newer than 05-29 existed; "rebuilt" was not in effect.

Resolution: rebuilt from current source via `ops\scripts\release\build.ps1`
(invoked directly, NOT with -ExecutionPolicy Bypass which the harness blocks).
First build (`..._Deployable_20260602_152939`, default mode "live config
stripped") contains the fix; its backend, run as the Tauri shell would
(`-m mediapipeline.desktop.local_api_main --app-root <pkg>\DesktopApp
--shell-surface tauri --emit-startup-progress`), resolved
`%LOCALAPPDATA%\MediaPipelineRemuxEncodeAIO\MediaPipeline_config.psd1` with
recover_config=complete and verify_config_loaded=complete (settings loaded),
no errors. That default build omitted the standalone shell exe
(-IncludeTauriPreviewBinary is opt-in), so a second build was run WITH that
flag to produce a launchable package.

Operator: launch the NEWEST `..._Deployable_2026*` package; confirm in GUI
(Video tab VideoQuality=21 not 22; Libraries shows Movies/TV with
\\LAYNE-SERVER paths). The 05-29 Temp packages are stale and can be deleted.

## Operator config fix 2026-06-02 (separate from kernel migration)

Operator reported "settings lost" / pipeline blocked ("settings loaded=no").
Diagnosis: data was NOT lost. Canonical live config
`ops/pipeline/config/MediaPipeline_config.psd1` did not exist; resolver fell back to the
legacy `ops/pipeline/config/MediaPipeline_config_chatgpt.psd1` (intact, newest, loads).
The documented `_chatgpt` -> canonical rename (see `app/paths/defaults.py`
comment) was never completed.

Action (non-destructive, both files gitignored): copied the intact
`MediaPipeline_config_chatgpt.psd1` -> `MediaPipeline_config.psd1`. Verified:
byte-identical; canonical now resolves as active config and `load_config`
validates; real settings present (SourceMovies/SourceTV/Outsource
`\\LAYNE-SERVER\...`, movies+tv library profiles). `_chatgpt` left in place
as fallback. No code changed. Operator must restart local API + hard-refresh
browser to pick it up.

## Wave 5 in-scope files (added 2026-06-02) -- AGENTS.md §7 (pending_publish)

Move whole package `src/mediapipeline/desktop/contracts/`
-> `app/kernel/contracts/` (all 10 modules: __init__, base, active_job,
completed_job, control_flag, pending_publish, pipeline_events,
process_result, progress, queue_snapshot). Package is self-contained (every
module imports only `from .base ...`).

Recreate old `contracts/` as a shim package (robust re-export shims for each
module; __init__ shim preserves the aggregator `__all__`).

NOT self-certified: `pending_publish` is §7 release-critical. Agent-side
tests run, but operator high-risk rung + sign-off required before this wave
is "done" (see handoff).

## Wave 4 in-scope files (added 2026-06-02)

Create (move from DesktopApp `application/`):
- `app/kernel/dto_status.py`
- `app/kernel/dto.py`        (aggregator; imports the five moved siblings)

Replace with robust compatibility shims (full namespace + literal __all__):
- `src/mediapipeline/desktop/application/dto_status.py`
- `src/mediapipeline/desktop/application/dto.py`

## Wave 3 in-scope files (added 2026-06-02)

Create (move from DesktopApp `application/`):
- `app/kernel/dto_base.py`
- `app/kernel/dto_commands.py`
- `app/kernel/dto_inventory.py`
- `app/kernel/dto_workspaces.py`

Replace with robust compatibility shims (re-export full public namespace,
including non-`__all__` names like `JsonMap`):
- `src/mediapipeline/desktop/application/dto_base.py`
- `src/mediapipeline/desktop/application/dto_commands.py`
- `src/mediapipeline/desktop/application/dto_inventory.py`
- `src/mediapipeline/desktop/application/dto_workspaces.py`

## Wave 2 in-scope files (added 2026-06-02)

Create:
- `app/kernel/config_keys.py`              (moved from DesktopApp)
- `app/kernel/runtime/__init__.py`
- `app/kernel/runtime/subprocess_runner.py`(moved from DesktopApp)

Replace with compatibility shims:
- `src/mediapipeline/desktop/config_keys.py`
- `src/mediapipeline/desktop/subprocess_runner.py`

## Task

Shared-kernel extraction, Wave 1 step 1 (ADR-0012, ADR-0013): relocate the
`models` trio to the new `app/kernel/` package behind re-export shims. No
importer rewrites this session (deferred to ADR-0013 Wave 6).

## In-scope files

Create:
- `app/kernel/__init__.py`
- `app/kernel/models.py`            (moved from DesktopApp)
- `app/kernel/models_core.py`       (moved from DesktopApp)
- `app/kernel/models_media_paths.py`(moved from DesktopApp)

Replace with compatibility shims (old paths re-export from `app.kernel.*`):
- `src/mediapipeline/desktop/models.py`
- `src/mediapipeline/desktop/models_core.py`
- `src/mediapipeline/desktop/models_media_paths.py`

Docs already updated this session: `docs/adr/0012-*`, `docs/adr/0013-*`,
`docs/adr/README.md`.

## Out of scope

- Rewriting the 92/5/1 importers (Wave 6).
- Any other kernel member (config_keys, subprocess_runner, dto_*, contracts).
- Any behaviour change. This is a pure relocation.

## High-risk note (AGENTS.md §7)

`models.py` defines `QueueRecord` (queue types). The change is type-only
relocation, but the queue/settings validation rung applies and is for the
operator to run; this session does not self-certify §7.

## Validation rung (AGENTS.md §5)

- Agent-side: full Python unit suite via `apps\desktop\runtime\Python\python.exe`.
- Operator-side (required before declaring §7-safe): queue/settings targeted
  tests + affected smokes; representative real-media validation if any queue
  behaviour is suspected to change (it should not).

## Exit criteria

- `app.kernel.models`, `app.kernel.models_core`, `app.kernel.models_media_paths`
  import successfully.
- Old import paths still resolve via shims.
- Python unit suite green (or pre-existing failures identified as unrelated).
- Handoff recorded below.

## Handoff 2026-06-02

Status: Wave 1 step 1 complete; exit criteria met (agent-side). Operator §7
validation still required (see below).

Changed files:
- `app/kernel/__init__.py` (new) — kernel package marker/docstring.
- `app/kernel/models.py`, `app/kernel/models_core.py`,
  `app/kernel/models_media_paths.py` (new home; `git mv` from DesktopApp,
  history preserved). No content edits; `models.py` relative imports of the
  other two still resolve in-package.
- `src/mediapipeline/desktop/models.py`, `models_core.py`,
  `models_media_paths.py` (now compatibility shims: `from app.kernel.X import *`).
- `docs/adr/0012-*`, `docs/adr/0013-*`, `docs/adr/README.md` (the two ADRs +
  index; 0013 corrected to `app/kernel/` and shim-defers-rewrite).

Validation performed (agent-side):
- Import smoke: new paths + shims import; `mediapipeline.desktop.models.QueueRecord`
  is the identical object as `app.kernel.models.QueueRecord`.
- `compileall` clean on new + shim files.
- `pytest --collect-only` over `tests/python/desktop`: 1630 collected, exit 0
  (no import breakage anywhere).
- `pytest` on the 59 files importing the moved modules: 464 passed, 46
  subtests passed, exit 0 (53s).
- Command env: `PYTHONPATH=<root>;<root>/DesktopApp`, interpreter
  `apps\desktop\runtime\Python\python.exe`.

Operator validation still required (AGENTS.md §7, not self-certified):
- Queue/settings targeted smokes for `QueueRecord` relocation.
- `python -m mediapipeline.tools.dev.ai_guardrail` (godfile/drift) to confirm the change
  reduces the `models` godfile and trips no guard.
- `python -m mediapipeline.tools.dev.refresh_summaries` — summaries still sit at the old
  `docs/generated/summaries/DesktopApp/.../models*.py.md` paths; regen to mirror
  `app/kernel/`. Not run this session to avoid a broad out-of-scope diff.

Not mine / pre-existing working-tree changes (left untouched): `renameView.js`,
`settingsView.js`, `test_rename_workbench.py`,
`test_webview_settings_libraries.py`, and their summaries.

## Handoff 2026-06-02 (Wave 2)

Status: Wave 2 (steps 2-3) complete; exit criteria met (agent-side).
Operator §7 validation still required (config_keys feeds settings schema).

Changed files:
- `app/kernel/config_keys.py` (new home; `git mv`, no edits). Module-level
  `__all__` is computed from `globals()` and resolves correctly in the new
  location (134 `KEY_*` constants).
- `app/kernel/runtime/__init__.py` (new) — kernel runtime subpackage marker.
- `app/kernel/runtime/subprocess_runner.py` (new home; `git mv`, no edits).
- `src/mediapipeline/desktop/config_keys.py`,
  `subprocess_runner.py` (now compatibility shims).

Validation performed (agent-side):
- `compileall` clean on new + shim files.
- Import smoke: shim re-exports identical `KEY_*` values; `subprocess_runner`
  public API (`CapturedCommandResult`, `KillTreeCallback`, ...) intact.
- `pytest --collect-only` over `tests/python/desktop`: 1630 collected, exit 0.
- `pytest` on the 17 `.py` files importing the moved modules: 192 passed,
  140 subtests passed, exit 0.

Operator validation still required (AGENTS.md §7, not self-certified):
- Settings schema/persistence smokes (config_keys underpins settings keys).
- `python -m mediapipeline.tools.dev.ai_guardrail`; `python -m mediapipeline.tools.dev.refresh_summaries`.

## Handoff 2026-06-02 (Wave 3)

Status: Wave 3 (steps 4-5) complete; exit criteria met (agent-side),
verified against the full suite.

Changed files:
- `app/kernel/dto_base.py`, `app/kernel/dto_commands.py`,
  `app/kernel/dto_inventory.py`, `app/kernel/dto_workspaces.py` (new home;
  `git mv`, no content edits; sibling `from .dto_base import ...` resolves
  in-package).
- `src/mediapipeline/desktop/application/dto_base.py`,
  `dto_commands.py`, `dto_inventory.py`, `dto_workspaces.py` (robust shims:
  copy full public namespace via globals().update for back-compat, e.g.
  `JsonMap` which is not in `__all__`; plus a literal `__all__`).

Contract note (caught by test, then fixed):
- `tests/test_application_public_api.py` AST-parses every `application/dto*.py`
  and requires a literal-list `__all__`. Plain `import *` shims failed it;
  the robust shims now declare a literal `__all__` mirroring each moved
  module. This is why Wave 3 shims differ from the Wave 1-2 plain `import *`
  shims.

Validation performed (agent-side):
- `compileall` clean on new + shim files.
- Import smoke: `JsonMap`, `dto_mapping`, `json_safe` import via the shim;
  `dto_mapping` identity matches the kernel module; `dto.py`'s relative
  `from .dto_base import JsonMap` resolves via the shim.
- `pytest --collect-only` over `tests/python/desktop`: exit 0.
- Full suite `pytest tests/python/desktop`: 1631 passed, 1 skipped, 1235
  subtests passed, exit 0 (152s).

Operator validation still recommended: `python -m mediapipeline.tools.dev.ai_guardrail`;
`python -m mediapipeline.tools.dev.refresh_summaries` (summaries still at old paths for
all moved modules across Waves 1-3).

## Handoff 2026-06-02 (Wave 4)

Status: Wave 4 (step 6) complete; exit criteria met, verified against the
full suite. DTO family fully relocated to the kernel.

Changed files:
- `app/kernel/dto_status.py`, `app/kernel/dto.py` (new home; `git mv`, no
  content edits). `dto.py` aggregator's `from .dto_* import ...` all resolve
  in-package now that every sibling lives in `app.kernel`.
- `src/mediapipeline/desktop/application/dto_status.py`,
  `application/dto.py` (robust shims: full-namespace copy + literal `__all__`).

Validation performed (agent-side):
- `compileall` clean on new + shim files.
- Import smoke: `mediapipeline.desktop.application` still exposes
  `CommandResult` (via `__init__` -> `.dto` shim -> `app.kernel.dto`);
  aggregator object identity matches `app.kernel.dto`.
- Full suite `pytest tests/python/desktop`: 1631 passed, 1 skipped, 1235
  subtests passed, exit 0 (146s).

Operator validation still recommended: `python -m mediapipeline.tools.dev.ai_guardrail`;
`python -m mediapipeline.tools.dev.refresh_summaries` (summaries still at old paths for
all moved modules, Waves 1-4).

## Handoff 2026-06-02 (Wave 5) -- AGENTS.md §7, NOT self-certified

Status: mechanical move complete; agent-side tests green. NOT declared done
-- `pending_publish` is §7 release-critical; operator high-risk rung +
sign-off required (below).

Changed files:
- Whole package moved: `app/kernel/contracts/` now holds __init__, base,
  active_job, completed_job, control_flag, pending_publish, pipeline_events,
  process_result, progress, queue_snapshot (`git mv`, no content edits;
  package is self-contained, every module imports only `from .base ...`).
- `src/mediapipeline/desktop/contracts/` recreated as a shim
  package: 9 submodule robust shims + an `__init__` shim that preserves the
  aggregator `__all__` (16 names).

Validation performed (agent-side only):
- `compileall` clean on the new package and the shim package.
- Import smoke: `PendingPushManifest`, `ContractError`, `QueuePlanSnapshot`
  resolve via shim with identical object identity to `app.kernel.contracts.*`;
  aggregator `__all__` count = 16; base helpers (`text_field`) callable via
  shim.
- Full suite `pytest tests/python/desktop`: 1634 passed, 1 skipped, 1235
  subtests passed, exit 0 (147s).

Operator validation REQUIRED before Wave 5 is "done" (AGENTS.md §5/§7):
- `ops/scripts/smoke\Test-WebViewBrowserPendingDrainGuardSmoke.ps1`
- `ops/scripts/smoke\Test-WebViewBrowserCompletedPendingProofSmoke.ps1`
- `ops/scripts/smoke\Test-LocalApiLifecycleContractSmoke.ps1`
- `python -m mediapipeline.tools.dev.ai_guardrail` (godfile/drift; expect `models`/
  contracts godfile pressure reduced, no new guard trips)
- Representative real-media validation per
  `ops\scripts\operator\New-RealMediaValidationWorksheet.ps1` only if any
  publish/drain behaviour is suspected to change. This wave is a pure
  contract-type relocation; no behaviour change is intended.

Also recommended (all waves): `python -m mediapipeline.tools.dev.refresh_summaries`
(summaries still at old paths for every moved module, Waves 1-5).

Next step (new session): Wave 6 cleanup -- rewrite importers to the
`app.kernel.*` paths and delete all shims, then add the dependency-direction
check from ADR-0012 §Validation. Hold until ADR-0012/0013 are accepted and
the §7 validation above passes.

## Handoff 2026-06-03 -- MediaPipeline.ps1 keystone hardening (operator-approved in chat; separate from kernel migration)

Operator approved a code-review of the main pipeline file and, after a written
per-issue plan, said "I'll proceed with your suggestions" -- explicit
current-turn scope for `ops/pipeline/entrypoints/MediaPipeline.ps1` and
`ops/pipeline/entrypoints/MediaPipeline/remux.ps1`. NOT the ADR-0013 kernel work. Branch:
`fix/mediapipeline-keystone-hardening` (off `master`). Eight isolated commits,
end-to-end smoke (`ops/pipeline/tests/Invoke-EndToEndSmokeChecks.ps1`) green after
each cut.

Changed files / commits (most severe first):
- `ops/pipeline/entrypoints/MediaPipeline.ps1` -- config-loader reserved-name denylist +
  try/catch + re-assert ErrorActionPreference/ProgressPreference (config keys
  could clobber preference/automatic variables).
- `ops/pipeline/entrypoints/MediaPipeline.ps1` -- ass_to_srt.py existence check: de-dup
  candidates, null-guard before Test-Path (clean FATAL instead of binding
  exception).
- `ops/pipeline/entrypoints/MediaPipeline.ps1` -- progress reload: -LiteralPath + [int] field
  coercion (partial-file / bracketed-path safety).
- `ops/pipeline/entrypoints/MediaPipeline/remux.ps1` -- surface mkvmerge stdout (Output) tail
  on exit-code-1 warnings. Behaviour unchanged: exit 1 still publishes.
- `ops/pipeline/entrypoints/MediaPipeline.ps1` -- declare `$logLock = $null` before the
  ExitCleanup closure.
- `ops/pipeline/entrypoints/MediaPipeline.ps1` -- PS7 relaunch: default null `$LASTEXITCODE`
  to 1 so a failed relaunch is not reported as success.
- `ops/pipeline/entrypoints/MediaPipeline.ps1` -- rename resolved `$configPath` ->
  `$resolvedConfigPath` (stop reassigning the `$ConfigPath` parameter via its
  case-variant); updated 3 downstream consumers.
- `ops/pipeline/entrypoints/MediaPipeline.ps1` -- collapse 7 redundant array-coercion
  `elseif/else` branches to `if/else` (no behaviour change).

Ollama: not used this session.

Validation performed (agent-side):
- Baseline + per-cut `Invoke-EndToEndSmokeChecks.ps1`: exit 0 each time.
- `Invoke-ConfigKeyRegistryChecks.ps1`: passed (130 keys).
- Parser parse-check after every edit: clean.
- Integration: `pwsh -File MediaPipeline.ps1 -ValidateOnly` against the live
  config -> exit 0, "PIPELINE SHUTDOWN CLEANLY", "ass_to_srt import: OK", all
  config keys loaded, no reserved-key warnings.

NOT self-certified (AGENTS.md §7 -- config/settings and FFmpeg/publish paths):
operator validation still required before declaring §7-safe:
- Representative real-media remux that produces a mkvmerge exit-1 warning, to
  confirm the new warning-tail logging (remux.ps1) and that publish behaviour
  is unchanged.
- A real continuous/`-Once` run (this session only ran `-ValidateOnly`).
- `python -m mediapipeline.tools.dev.ai_guardrail` and, per AGENTS.md §5 media row,
  the release gate / real-media validation worksheet.

Not mine / left untouched: stray untracked `CON` file at repo root (pre-existing;
never staged).

## Handoff 2026-06-03 (cont.) -- config-loader extraction (oracle-first) + Cut 7 regression fix

Operator approved continuing: oracle-first, then extract. Branch unchanged
(`fix/mediapipeline-keystone-hardening`).

REGRESSION FOUND + FIXED (important): Cut 7 (`e8d03e0`, the `$ConfigPath` ->
`$resolvedConfigPath` rename) was reverted (`e96a2b0`). The reassignment was
load-bearing: dot-sourced engine functions read the resolved path from the
ambient `$configPath` global by canonical name (`Build-QueuePlanSnapshotRows`
-> queue snapshot `config_path`; `Get-EffectiveConfigSummary` -> ShowConfig).
The rename left them reading the empty `$ConfigPath` parameter whenever the
pipeline runs without explicit `-ConfigPath`. The end-to-end smoke missed it
(it always passes `-ConfigPath`). LOW-9 is withdrawn.

Changed files / commits (this continuation):
- `ops/pipeline/engine/config/runtime_config.ps1` (NEW) -- `Get-MediaPipelineResolvedConfigDump`
  (Phase 0 parity oracle, 99 fields) + `Initialize-MediaPipelineRuntimeConfig`
  (the extracted config value-resolution block, moved verbatim; dot-source
  scope keeps `$script:`/`Set-Variable -Scope Script` landing in main scope).
- `ops/pipeline/entrypoints/MediaPipeline.ps1` -- new read-only `-DumpEffectiveConfigPath`
  switch (no singleton lock); config block (~430 lines) replaced by a call to
  the initializer + main-scope preference re-assert. Main: ~1573 -> 1195 lines.
- `ops/pipeline/tests/Unit/Invoke-RuntimeConfigResolutionChecks.ps1` (NEW) --
  regression checks: reserved-key guard, cross-key defaults, partial progress.
- `docs/generated/summaries/...` for the 4 changed/added in-scope files.

Validation (agent-side):
- PARITY: `-DumpEffectiveConfigPath` byte-for-byte identical (99/99) before vs
  after the extraction -- proves behaviour-neutral.
- End-to-end smoke green after every commit; `-ValidateOnly` clean; config-key
  registry green; new resolution test green (2/2).
- Guardrail `god-file-guard`, `naming-lint`, `architecture-guardrails`,
  `marketecture-guard`: all OK.

NOT mine / pre-existing (operator follow-up; do not attribute to this branch):
- guardrail `dependency-boundaries` FAIL = 1 Python package-level cycle. This
  change set is PowerShell-only and cannot create a Python import cycle.
- guardrail `summary-freshness`/`--check` also lists `network/coordinator.py`,
  `ops/pipeline/engine/subtitles/srt.ps1`, `ops/pipeline/tests/Unit/Invoke-SrtValidationChecks.ps1`
  as stale/missing -- none touched here.
- guardrail `project-index` FAIL: the legacy `ops/scripts/dev/refresh_index.py` path does not
  exist; regenerate PROJECT_INDEX via `python -m mediapipeline.tools.dev.generate_project_index`.
- The guardrail postflight baseline is stale (indexed 1077 vs 1117); run a
  clean preflight/postflight pair for an accurate read.

Operator validation REQUIRED before §7 sign-off (config/settings + FFmpeg/publish):
- A real `-Once`/continuous run (this session ran only smoke / -ValidateOnly /
  -DumpEffectiveConfigPath).
- A real remux that emits a mkvmerge exit-1 warning (confirms remux.ps1 warning
  tail logging; publish behaviour unchanged).
- `python -m mediapipeline.tools.dev.ai_guardrail preflight` then `postflight` as a pair.

## Backend WebView load performance 2026-06-03 (operator-approved this turn; new branch)

Branch: `perf/backend-webview-load`, created off the `fix/mediapipeline-keystone-hardening`
tip (5570524). Operator approved (AskUserQuestion, 2026-06-03): "New docs/SESSION.md + new branch"
and "keep the related uncommitted diff in place". There is no `main` branch; `master` (4a29caa)
lacks `ops/pipeline/engine/config/runtime_config.ps1` (created by the keystone commits), and the pre-existing
"related" working-tree diff modifies that file, so branching off `master` would strand it.
Branching off the current tip is the only base that preserves the diff; backend-load therefore
stacks on top of keystone + the related diff.

Task: reduce first WebView refresh from ~30s toward 1.5-4s by bounding the completed-job read
path. Read-path / performance only. Source brief: `docs/implementation/backend-load-performance/`
packets 01-05. No change to media policy, FFmpeg/subtitle/audio, publish/pending-publish
park/drain, queue mutation, settings persistence, or decision routing.

In-scope files (backend targets are clean; build ON TOP of the related diff, never overwrite its
lines):
- Packet 1 (completed proof budget): `app/completed/manifest.py`, `app/completed/policy.py`,
  `app/completed/service.py`, plus `app/completed/facade.py` / `trust_fields.py` /
  `validation_state.py` as needed; completed read route in
  `DesktopApp/.../api/read_payloads*.py` / `routes_read.py`.
- Packet 2 (SQLite mirror off GET): `app/completed/service.py`, `app/storage/db.py`.
- Packet 3 (bounded global refresh): `DesktopApp/.../ui_web/static/assets/app.js` and
  `assets/app/refresh.js`; completed-view JS only if required (`completedView.js` et al. are in
  the pre-existing diff -- additive edits only).
- Packet 4 (final-library dedupe): `app/final_library/service.py`,
  `DesktopApp/.../api/read_payloads_inventory.py`; optional frontend lazy-load.
- Tests: `tests/python/desktop/` + `tests/` targeted completed / final_library / local-api-route /
  webview-static; `docs/generated/summaries/` mirrors for changed files.

Out of scope: every AGENTS.md §7 area except the read-path DTO surface. Proof-mode DTO fields are
additive metadata only (do not silently flip "verified live" -> "assumed exists"); route/contract
tests required where the DTO changes.

Validation rung (AGENTS.md §5): targeted route + completed/final-library/storage unit tests via
`apps\desktop\runtime\Python\python.exe`, then affected WebView/local-API smokes. Capture
before/after route timing for `/api/completed` and `/api/final-library-promotion/status` and the
initial refresh set. No real-media rung needed unless a change crosses into media/publish/queue
policy.

Pre-existing working-tree diff (operator: "related", keep): ~50 files (config-keys /
decision-routing / settings) across `app/config`, `app/contracts`, `app/decide`,
`app/kernel/config_keys.py`, `ops/pipeline/engine/config`, `ops/pipeline/engine/decide`, `ops/pipeline/engine/paths`,
`ops/pipeline/engine/entrypoint.ps1`, `Pipeline/` config+schema+tests, `src/mediapipeline/contracts/schemas/`, ui_web settings+completed
JS, `tests/python/desktop` + `tests/`, and their summaries. Plus untracked `CON` (reserved Windows
name; pre-existing, leave) and `docs/implementation/` (the packets). Left untouched except where a
backend-load packet must add to an already-modified completed-view JS.

## Handoff 2026-06-03 -- backend WebView load performance (packets 1-4 complete)

Branch `perf/backend-webview-load`. Read-path/performance only; no media policy, FFmpeg/
subtitle/audio, publish/pending-publish, queue, or settings behaviour changed. Ollama: not used.

Changed files (all mine; zero overlap with the pre-existing related diff):
- `app/completed/manifest.py` -- proof-mode constants (summary/bounded/live) + `normalize_proof_mode`;
  `read_completed_manifest_records(..., proof_mode, bounded_proof_limit)` annotates only in-budget
  rows (live exists()) and stamps every record `_diagnostics_output_proof` live|deferred. (Packet 1)
- `app/completed/policy.py` -- `completed_record_to_row`/`completed_row_consistency` honour the
  per-record stamp: deferred rows emit `output_exists=None`, payload-only size, `output_proof`,
  `sidecar_exists=None`, `consistency_status="Unverified"`, and do zero filesystem I/O; operator
  guidance + `missing_output_count` switched from falsy to explicit `is False`. Added
  `completed_size_reduction_text` (payload-size parity with the model property). (Packet 1)
- `app/completed/service.py` -- `load_recent_completed_jobs(..., proof_mode)`, proof mode added to
  the history cache key (so summary evidence is never served to a live caller); removed the GET-time
  per-row SQLite mirror loop (read path no longer opens app.storage.db). (Packets 1-2)
- `app/completed/facade.py` -- `get_completed_preview(..., proof_mode=live)` threaded to the loader.
- `DesktopApp/.../api/read_payloads_inventory.py` -- broad completed route defaults to
  `proof=bounded`, honours `?proof=live`. (Packet 1)
- `ui_web/static/assets/app.js` -- broad `refreshAllNow` completed request `limit=all` -> `limit=100`;
  removed the duplicate `/api/final-library-promotion/status` request and now renders the promotion
  glance from `values.completed.final_library_promotion` (same builder, already attached). (Packets 3-4)
- `ui_web/static/assets/app/refresh.js` -- explicit "Current Output Status" recheck keeps
  `limit=all` and now adds `&proof=live` so it still proves every destination. (Packet 3)
- Tests: NEW `tests/python/desktop/test_completed_proof_budget.py` (8 tests: manifest budgeting,
  deferred-DTO no-filesystem guarantee, proof-keyed cache, route default). Updated
  `test_phase4_storage_observability.py` (read no longer writes the SQLite mirror),
  `test_application_facade_local_api.py` (limit=100 / proof=live strings),
  `test_final_library_promotion.py` (renderHomePromotionEntry arg).
- `docs/generated/summaries/...` regenerated for the 11 changed source/test files.

Validation (agent-side, bundled `apps\desktop\runtime\Python\python.exe`):
- New proof-budget tests 8/8; consolidated completed/final-library/storage/route/pending-publish
  regression 81/81; py_compile clean on all changed sources.
- Behaviour smokes `test_webview_browser_home_live_state_smoke` / `_large_table_smoke`
  / `_completed_pending_proof_smoke` pass (they execute app.js, so they catch the Packet 3/4 JS edits).
- Timing (synthetic, 3ms/op simulated SMB, 500-row manifest): live 2000 fs ops / 6.40s; bounded
  400 fs ops / 1.32s; summary 0 fs ops / 0.04s. With Packet 3 the broad refresh loads+proves <=100
  rows regardless of manifest size; Packet 2 removes the ~8s GET SQLite mirror; Packet 4 removes the
  duplicate ~13s 500-row final-library load.

Pre-existing red baseline (NOT mine; fails at HEAD, caused by the operator's uncommitted
completedView.js/settings refactors vs stale static-assertion tests): the static-JS assertions
`function finalLibraryPromotionActionState` / `function getLastCompletedPayload` in
`test_final_library_promotion.py` and `test_application_facade_local_api.py`, plus the
`test_queue_file_settings_drawer_*` settings assertions in `test_application_facade_web_static.py`.
Proven absent in HEAD (0/0). My updated assertion in `test_final_library_promotion.py` line 1069
passes (it executes before the failing line).

Operator validation still recommended (AGENTS.md §5 Local API/contract rung): run the WebView/
local-API smokes against a running backend (`ops/scripts/smoke\Test-LocalApi*`, `Test-WebView*`) and
`python -m mediapipeline.tools.dev.ai_guardrail` preflight/postflight. No real-media rung required (no media/
publish/queue/FFmpeg behaviour touched).

Follow-ups intentionally out of scope: (a) an explicit "not checked" badge in the completed-view JS
for `output_proof=="deferred"` rows (the backend already emits the data; existing JS treats
`output_exists===null` safely as not-missing); (b) a "showing recent 100 of N" indicator + optional
backend total-available count; (c) optional backend cache-key alignment so an on-demand
final-library status reuses the completed cache. Packets 1-4 deliver the perceived-load win without
these.

## Copy-rate telemetry accuracy 2026-06-05 (operator-approved in chat; separate from backend-webview-load)

Operator observation: the dashboard "Push file" card shows write speed and ETA far below the real
transfer rate (e.g. write 13.5 MB/s while the Wi-Fi adapter sends ~53 MB/s). Root cause: the rate is
a lifetime average (total bytes copied / total elapsed since copy start) computed in
`src/mediapipeline/core/status/eta.py` `_copy_eta_row`, so it lags whenever the transfer ramps up or
is bursty.

Task: replace the displayed rate (and the ETA derived from it) with a trailing-window rate produced
by the copy-telemetry writer, falling back to the cumulative average until the window populates.
Read-only display/telemetry accuracy only. No change to the robocopy copy itself, stage-percent
sync, the save/atomic-replace flow, queue, publish/pending-publish, settings schema, FFmpeg/
subtitle/audio, or media policy.

Branch: `perf/backend-webview-load` (unchanged; operator has not asked to branch). These edits layer
on top of the existing uncommitted reorg/related diff. The four target files are clean in the
working tree (no pre-existing uncommitted changes).

In-scope files:
- `ops/pipeline/engine/status/progress_state.ps1` -- `Set-ProgressCopyTelemetry`: maintain a trailing
  (timestamp,bytes) sample buffer; extract a pure `Get-CopyRollingBytesPerSecond` helper
  (samples + now -> bytes/sec) for unit testing; emit a new `CopyBytesPerSecond` (int|null) field;
  reset the buffer in `Reset-ProgressCopyTelemetry` and on `CopyAttempt` change. `SyncStagePercent`,
  `Convert-CopyPercentToStagePercent`, and `Save-Progress` semantics UNCHANGED.
- `src/mediapipeline/core/status/eta.py` -- `_copy_eta_row`: prefer `CopyBytesPerSecond` when present
  and > 0 (derive `eta_seconds` from it; update `basis` text); fall back to existing
  `safe_copied/elapsed_seconds` otherwise.
- `ops/pipeline/config/schemas/media_pipeline_progress.schema.json` -- document `CopyBytesPerSecond`
  (additive; schema is already `additionalProperties: true`).
- `tests/python/desktop/test_service_status_eta.py` -- NEW test for the windowed path; existing
  cumulative test (`bytes_per_second == 8947849`) left UNCHANGED.
- `docs/generated/summaries/` mirrors for the changed `eta.py` / `progress_state.ps1`.
- `ops/release/changes/unreleased/MP-CHANGE-2026-0605-009.json` (change packet).

Out of scope: the robocopy copy path (`ops/pipeline/engine/storage/disk.ps1`) and every AGENTS.md §7
area. No new top-level files. `progressView.js` unchanged (it already renders
`row.bytes_per_second` / `row.eta_seconds`; the value just becomes accurate).

Tunables (defaults): trailing window = 15 s (~15 samples at the 1 s poll cadence); no relabeling of
the existing "write" token.

Validation rung (AGENTS.md §5 -- diagnostics/telemetry):
- Agent-side: Python eta unit tests (new + existing) via `apps\desktop\runtime\Python\python.exe`;
  PS parse-check + a focused unit test of `Get-CopyRollingBytesPerSecond`; the progress-schema
  contract check (`ops/pipeline/tests/Unit/Invoke-ContractSchemaChecks.ps1`);
  `mediapipeline.tools.change_control.validate_changes --require-worktree-coverage`.
- Operator-side: a real `-Once` copy over SMB to confirm `CopyBytesPerSecond` populates and the
  dashboard "write" figure tracks Task Manager. (Agent cannot run a real multi-GB SMB copy.)

Not §7: `eta.py` is declared read-only telemetry; the `progress_state.ps1` change is additive
telemetry only and does not alter file movement, stage percent, or save behavior.

### Approach revised + Handoff 2026-06-05

Approach changed during planning (operator-chosen): instead of a trailing-window rate, learn a
per-run WEIGHTED-AVERAGE server-push throughput from COMPLETED files and use it for the current
push's write speed + ETA. The first file of a run is the guinea pig (falls back to its own partial
measurement); each completed push refines the average. Local source->scratch copies are excluded
(they use CopyState, not PushState), so they never pollute the network average. The trailing-window
plan above is SUPERSEDED. Change packet: `MP-CHANGE-2026-0605-050` (the earlier `-009` id was taken
by a concurrent session, so a free id in the 050 gap was used).

Implemented (status complete, agent-side validated):
- `ops/pipeline/engine/status/progress_state.ps1` -- session accumulators
  (`$script:SessionPushBytesTotal`/`SecondsTotal`/`FilesCompleted`, reset naturally per process
  launch); pure helper `Get-PushAverageBytesPerSecond`; guarded `Add-PushThroughputSample`; one-shot
  sample fold on the existing PushState `copying`->`copied_pending_reveal`/`complete` transition
  inside `Set-ProgressStage`; emit `CopySessionBytesPerSecond` + `CopySessionFilesCompleted` in
  Save-Progress; push-sample state reset in `Reset-ProgressCopyTelemetry`. `publish_completion.ps1`
  and `disk.ps1` NOT edited (no §7 / movement files touched).
- `src/mediapipeline/core/status/eta.py` -- `_copy_eta_row` prefers `CopySessionBytesPerSecond` once
  `CopySessionFilesCompleted >= 1`; per-file cumulative remains the file-1 fallback.
- `ops/pipeline/config/schemas/media_pipeline_progress.schema.json` -- two additive nullable fields.
- `tests/python/desktop/test_service_status_eta.py` -- 3 new tests (session preferred; estimates
  before current file has elapsed; ignored for first file). Existing cumulative test unchanged.

Validation (agent-side):
- ETA unit tests 8/8 OK; related status/contract suite (snapshot, status_readers, status_summary,
  contracts) 42/42 OK.
- `progress_state.ps1` `[Parser]::ParseFile` PARSE_OK; dot-source functional harness: helper math
  correct, sample folds exactly once per file, no double-count on `complete`, second file increments.
- `Invoke-ContractSchemaChecks.ps1` -> "OK: contract schema checks passed."
- `validate_changes --require-worktree-coverage`: packet `MP-CHANGE-2026-0605-050` valid and all of
  this change's files covered. Exit 1 comes ONLY from concurrent/unrelated churn --
  `MP-CHANGE-2026-0605-010.json` (another session's packet) missing `date_completed`, and uncovered
  `tests/webview/test_webview_browser_large_table_smoke.py(.md)` (another session's webview work).
- `refresh_summaries --paths` for the two changed sources -> 0 written, 2 unchanged.

Operator validation REQUIRED before sign-off:
- A real `-Once`/continuous run with >= 2 server pushes: confirm `CopySessionBytesPerSecond` is null
  during file 1, populates after file 1 completes, and the file-2+ dashboard write/ETA track Task
  Manager. (Agent cannot run a real multi-GB SMB push.)

Concurrency note: `docs/SESSION.md` and `ops/release/changes/unreleased/` are being actively modified
by other sessions during this work (new 0605 packets appeared mid-task; another session appended the
entrypoint-slice block below). My edits are limited to the files listed above.


## MediaPipeline.ps1 entrypoint-slice refactor 2026-06-05 (operator-approved in chat; separate from telemetry/backend-load)

Operator approved (chat, 2026-06-05) a code-locality refactor of the keystone entrypoint
`ops/pipeline/entrypoints/MediaPipeline.ps1` after a written plan: style = hybrid
(procedural dot-sourced slices for scope-sensitive blocks; functions only where state is
purely `$script:` or returned), scope = full campaign (phases 1-6). This is NOT the kernel
migration, NOT backend-webview-load, NOT copy-rate telemetry.

Objective: reduce the 1112-line orchestrator to a ~220-line composition root that dot-sources
named single-purpose slices. Pure code-locality move; ZERO behaviour change, proven per cut by
the `-DumpEffectiveConfigPath` parity oracle (byte-identical dump) + a startup-log diff
(`-ValidateOnly`/`-ShowConfig`) + the end-to-end smoke.

In-scope files:
- EDIT `ops/pipeline/entrypoints/MediaPipeline.ps1` -- shrink to orchestrator; replace extracted
  blocks with dot-source/function calls.
- NEW slices under `ops/pipeline/entrypoints/MediaPipeline/` (allowed pattern; siblings of the
  existing tx3g/remux/encode slices): `bootstrap_pwsh7.ps1`, `module_loader.ps1`,
  `runtime_config_boot.ps1`, `runtime_paths.ps1`, `instance_lock.ps1`, `dependencies.ps1`,
  `startup_filesystem.ps1`, `modes.ps1`.
- NEW functions into existing engine domains:
  `Initialize-MediaPipelineSessionState` -> `ops/pipeline/engine/status/progress_state.ps1`;
  `Write-MediaPipelineStartupConfigLog` (+ NVENC probe) -> `ops/pipeline/engine/observability/logging.ps1`;
  `Test-MediaPipelineStartupPaths` -> `ops/pipeline/engine/paths/` (or new `engine/startup/`).
- NEW module-manifest contract test under `ops/pipeline/tests/Unit/` (every dot-sourced engine
  file exists; no duplicate keys; documented load order preserved).
- `docs/generated/summaries/` mirrors for changed/added in-scope files.
- Change packet under `ops/release/changes/unreleased/` (AGENTS.md §8).

Out of scope: behaviour of any engine module; the dirty `MediaPipeline/encode.ps1` and
`MediaPipeline/remux.ps1` (already modified in the working tree by unrelated reorg/telemetry work
-- do NOT touch their lines); every AGENTS.md §7 behaviour. The slice tx3g/remux/encode LOADER is
in scope (its loop), but the slice file contents are not.

Hard constraints (the reasons this is delicate):
1. Scope semantics: dot-sourced slices run in caller scope (plain locals + `$script:` persist).
   Function-wrap ONLY blocks that touch purely `$script:` or return a result object; never
   function-localize a plain entrypoint local that engine code reads by ambient name.
2. Ambient-variable contract: dot-sourced engine functions read entrypoint-scope names by
   canonical name (this is what broke prior "Cut 7": `$configPath` read by
   `Build-QueuePlanSnapshotRows`/`Get-EffectiveConfigSummary`). NO rename, NO rescope, NO
   function-localization of any ambient-read name. Audit recorded in handoff below.
3. Load order at MediaPipeline.ps1:389 is a documented topological order; the manifest extraction
   must preserve it exactly (locked by the new contract test).
4. `$Script:ExitCleanup` closure captures `$logLock`/`$workerSlotMutex`/`$instanceMutex` by
   reference -- keep the closure and those declarations in the same `instance_lock.ps1` slice.

Phases (one isolated edit + validation per cut; safest first):
- P0 ambient audit + golden baselines (no code moves).
- P1 historical-comment trim (lines 1-182; comments only).
- P2 `Initialize-MediaPipelineSessionState` + `Write-MediaPipelineStartupConfigLog` (`$script:`/log only).
- P3 `bootstrap_pwsh7.ps1` + `module_loader.ps1` (non-§7 bootstrap).
- P4 `runtime_paths.ps1` + `startup_filesystem.ps1` + `Test-MediaPipelineStartupPaths`.
- P5 (§7) `dependencies.ps1` + `instance_lock.ps1` + `runtime_config_boot.ps1`.
- P6 (§7) `modes.ps1` (ValidateOnly/Drain/SingleFile/EmitQueuePlan/Run dispatch).

Validation rung (AGENTS.md §5):
- Agent-side (P1-P4): PS parse-check after every edit; `-DumpEffectiveConfigPath` byte-parity
  before/after; `-ValidateOnly` startup-log diff; `ops/pipeline/tests/Invoke-EndToEndSmokeChecks.ps1`
  green after each cut; new manifest contract test.
- Operator-side, REQUIRED before §7 sign-off (P5-P6; config/settings + FFmpeg/publish + queue
  launch scope): a real `-Once`/continuous run, queue/pending-publish/local-API smokes, a real
  remux emitting a mkvmerge exit-1 warning, and `python -m mediapipeline.tools.dev.ai_guardrail`
  preflight/postflight pair. NOT self-certified.

Git handling: working tree has ~712 unrelated dirty files (operator reorg/telemetry; keep in
place) + `encode.ps1`/`remux.ps1` already modified. Per CLAUDE.md no-commit rule and to avoid
entangling that diff, this refactor stays UNCOMMITTED in the working tree; a precise file
manifest + commit recipe (intended branch `refactor/mediapipeline-entrypoint-slice` off the
current tip) is handed to the operator. No branch switch performed.

## Handoff 2026-06-05 -- MediaPipeline.ps1 slice refactor (phases 0-4 complete, agent-validated)

Change packet: `ops/release/changes/unreleased/MP-CHANGE-2026-0605-010.json` (status in_progress).
Ollama: not used. No commit/branch performed (working tree left dirty per above).

Validation harness established (reusable for the remaining phases):
- Parity oracle: `pwsh -File MediaPipeline.ps1 -ConfigPath %LOCALAPPDATA%\MediaPipelineRemuxEncodeAIO\MediaPipeline_config.psd1 -DumpEffectiveConfigPath <out>`.
  NOTE the dump is NON-deterministic (two nested hashtable fields -- RenameMovieFilterOptions /
  RenameMovieFilterTerms -- serialize in random key order), so raw sha is useless. Compare with
  the deep key-sorted canonicalizer at `%TEMP%\mp_refactor_baseline\Compare-Dump.ps1`.
  Golden baseline: `%TEMP%\mp_refactor_baseline\dump_before.json`.
- Startup-log diff: `-ValidateOnly` output, timestamps stripped (`^\d{4}-..-.. ..:..:.. `),
  Compare-Object vs `%TEMP%\mp_refactor_baseline\validateonly_before.log` (72 lines).
- Smoke: `ops/pipeline/tests/Invoke-EndToEndSmokeChecks.ps1` (~39s).
After EVERY cut so far: canonical dump IDENTICAL, log 0 diffs, smoke exit 0.

Ambient-variable contract (audited; the reason this is delicate): 116 references across 20
engine files read entrypoint-scope names by canonical name. Rule honoured: NOTHING renamed or
rescoped; blocks were either moved verbatim (procedural) or wrapped as dot-sourced functions
that only WRITE `$script:`/`$Global:` (reads resolve via the dot-source scope chain at call
time). Watch-list to never touch: `$configPath`, `$SourceMovies`, `$SourceTV`, `$Outsource`,
`$LocalBase`, `$ProgressFile`, `$LogFile`, `$ffmpegPath`, `$ffprobePath`, `$mkvmergePath`,
`$mkvextractPath`, `$pythonPath`, `$assToSrtScript`, the mutex vars, and the `$script:*` family.

Changed files (phases 1-4):
- `ops/pipeline/entrypoints/MediaPipeline.ps1` -- 1112 -> 597 lines. P1: 181-line historical
  [FIX#N] header -> concise comment-based-help block (adds .SYNOPSIS; history kept in git).
  P2: session-state block + startup-config-log block replaced by single calls. P3: module
  manifest + load loop replaced by a guarded dot-source of the loader slice. P4: derived paths +
  worker override, startup filesystem prep, and startup path validation replaced by three guarded
  dot-sources. `$pipelineRoot`/`$repoRootForModules`/`$moduleRoot` deliberately kept inline (used
  later + to locate the slices).
- `ops/pipeline/entrypoints/MediaPipeline/module_loader.ps1` (NEW, 99 lines) -- load-order doc +
  `$engineModulePaths` (46 entries) + ordered dot-source loop; reads `$repoRootForModules`/
  `$moduleRoot` ambiently; dot-sources engine modules into the entrypoint scope.
- `ops/pipeline/entrypoints/MediaPipeline/runtime_paths.ps1` (NEW, 81 lines) -- procedural slice:
  derived paths + `New-MediaPipelineStateLayout` + worker-child slot override. Sets ~18 plain
  entrypoint locals + `$script:*`; MUST stay procedural (a function would trap the plain locals).
- `ops/pipeline/entrypoints/MediaPipeline/startup_filesystem.ps1` (NEW, 21 lines) -- procedural
  slice: dir creation, `Initialize-MediaPipelineStateLayout`, log rotation, worker-claim repair,
  `Write-StartupWarnings`.
- `ops/pipeline/entrypoints/MediaPipeline/startup_path_validation.ps1` (NEW, 38 lines) --
  procedural slice: LocalBase hard-fail (exit 2) + source/outsource soft-warn reachability probes.
- `ops/pipeline/engine/status/progress_state.ps1` -- +`Initialize-MediaPipelineSessionState`
  (the $script:/$Global: session + progress-counter init + progress-file reload + baseline).
- `ops/pipeline/engine/observability/logging.ps1` -- +`Write-MediaPipelineStartupConfigLog`
  (run-mode log + full resolved-config Write-Log dump + NVENC probe + pipeline_started/
  gpu_unavailable events + Write-StartupEnvironmentSummary).

Design correction discovered this session: the PS7-relaunch block is NOT extractable -- it relies
on the entrypoint's own `$MyInvocation.MyCommand.Path`/`$PSScriptRoot`/`$PSBoundParameters` (a
dot-sourced slice would see the slice's own values and relaunch the wrong file) and only fires
under Windows PowerShell 5.x, which is unvalidatable agent-side. LEFT INLINE; `bootstrap_pwsh7.ps1`
dropped from the plan.

Remaining work:
- P4 DONE (2026-06-05): runtime_paths.ps1, startup_filesystem.ps1, startup_path_validation.ps1
  (all procedural slices; Test-MediaPipelineStartupPaths was reclassified as a procedural slice,
  not a function, per the hybrid rule -- it returns nothing and writes no $script:).
- P5-P6 (AGENTS.md section 7, NOT self-certifiable -- AND the agent harness has BLIND SPOTS here:
  the single-instance/worker mutex is skipped in -ValidateOnly/-DumpEffectiveConfigPath, and the
  Drain/SingleFile/EmitQueuePlan/continuous Run modes execute only after those modes exit, so the
  parity oracle + fixture smoke cannot prove a lock or mode-dispatch extraction neutral. Do NOT
  extract these without the operator running the real validation rung after each cut):
  `dependencies.ps1`, `instance_lock.ps1`
  (+ExitCleanup closure capture -- keep declarations in-slice), `runtime_config_boot.ps1`, and
  `modes.ps1` (ValidateOnly/Drain/SingleFile/EmitQueuePlan/Run dispatch). Operator must run a
  real -Once/continuous pass + queue/pending-publish/local-API smokes + a real mkvmerge exit-1
  remux + `python -m mediapipeline.tools.dev.ai_guardrail` preflight/postflight before section-7
  sign-off.
- Deferred: module-manifest contract test (tests/Unit path conventions are mid-reorg).

Commit recipe (operator, when ready; keeps the unrelated reorg diff out):
`git switch -c refactor/mediapipeline-entrypoint-slice` then
`git add ops/pipeline/entrypoints/MediaPipeline.ps1 ops/pipeline/entrypoints/MediaPipeline/module_loader.ps1 ops/pipeline/entrypoints/MediaPipeline/runtime_paths.ps1 ops/pipeline/entrypoints/MediaPipeline/startup_filesystem.ps1 ops/pipeline/entrypoints/MediaPipeline/startup_path_validation.ps1 ops/pipeline/engine/status/progress_state.ps1 ops/pipeline/engine/observability/logging.ps1 ops/release/changes/unreleased/MP-CHANGE-2026-0605-010.json docs/SESSION.md`
then commit. Do NOT `git add -A` (would sweep the ~712 unrelated dirty files).


## Handoff 2026-06-05 -- Home "Next 5 Videos" panel fix (operator-approved in chat; separate from entrypoint-slice refactor)

Operator request: the Home "Next 5 Videos" panel showed already-processed items and
file-name-looking strings; wanted live "next" items with normalized names
("Show - S01E01 - Title" / "Movie Title (Year)"), with proof.

Root causes (confirmed against live state E:\Videos\Scratch\State\Progress\):
- Wrong items: `homeNextQueueRows` took the first 5 runnable rows of the STATIC queue
  plan (`/api/queue`) and ignored live progress, so it always showed plan rows 1-5.
  The aligned live position is `snapshot.counts.queue_index` (== progress
  `CurrentQueueIndex`, global) vs each row's `global_order` (NOT per-phase `queue_index`).
- "File-name" look: clean `display_name` was passed through `shortenPath`, which (no path
  separators) prepended a bogus ".../" prefix. TV `display_name` is already normalized;
  movie `display_name` (SortName) still carried release tags.

Change (single file, read-only display only; no contract/queue-behaviour change):
- `apps/desktop/webview/static/assets/app/home.js`:
  - `homeNextQueueRows(queue, currentOrder)` now returns runnable rows with
    `global_order > currentOrder` (sorted), falling back to the first-5 runnable when
    nothing is upcoming or no global_order is present (keeps unit/smoke fixtures green).
  - `renderHomeNextQueue` passes `homeCurrentQueueOrder(context, queue.rows)`. The cutoff
    is the literal current position: first anchor to the file being processed
    (`progress.CurrentFilePath` -> matching row's `global_order`), else
    `max(counts.queue_index, counts.processed)`. The `max` is durable: `CurrentQueueIndex`
    resets to 0 between items while `TotalProcessed` (`counts.processed`,
    status_policy.snapshot_counts) does not, so the panel never reverts to finished items
    in the gap. This yields the literal next 5 in execution order (crosses show/season/phase
    boundaries; not "the next bucket").
  - Title renders the verbatim normalized name (CSS ellipsis clips overflow) instead of
    `shortenPath`. New `homeMovieTitleYear`/`homeNormalizeQueueTitle` collapse release-style
    movie names to "Title (Year)"; TV names pass through unchanged.
  - New helpers exported on `window.mediaPipelineAppHome`.

Validation (agent-side):
- `node --check` clean. Node VM harness (mirrors the web-static test technique) against the
  REAL live queue_snapshot.json + pipeline_progress.json (CurrentQueueIndex=27/62): OLD
  showed Snow White S01E01-05 (already done); NEW shows global_order 28-32 with clean names;
  movie normalizer correct on all 16 live movie names.
- Real unittest `test_home_next_queue_shows_first_five_runnable_rows_only`: OK.
- `test_real_browser_renders_home_live_state_without_mutation_posts` (real headless browser): OK.
- Pre-existing UNRELATED reds confirmed at HEAD without this change (route-inventory
  `/api/subtitle-qa/*`, rename/command-feedback, `report-warnings` markup) -- not caused here.

Ollama: not used. No commit/branch performed.

Follow-ups (optional, out of scope): movie normalizer does not apply the operator's custom
movie-cleaning policy (remove_terms/filters) -- for full parity, add a normalized title to
the Python queue preview via `current_work_item_label`; that touches the queue DTO/contract
and needs a separate plan. Movies without a year token in the filename fall back to the
space-normalized name.


## Handoff 2026-06-07 -- CPU telemetry: dual-metric display (Option C; operator-approved in chat; separate from entrypoint-slice refactor)

Operator reported the dashboard CPU reading was "consistently out of line" with Task Manager
(e.g. app ~89% during a GPU-bound NVENC encode while Task Manager total ~40%). Investigated the
full collect -> normalize -> snapshot -> DTO -> route -> view path (read-only) first, then the
operator chose Option C and approved implementing it.

Root cause (NOT a bug; proven by simultaneous Get-Counter + psutil sampling on this Windows
box): the collector samples `\Processor Information(_Total)\% Processor Time` -- a
frequency-INDEPENDENT busy fraction that equals the classic `\Processor(_Total)\% Processor
Time` exactly and matches `psutil.cpu_percent` within rounding. Windows Task Manager instead
displays `% Processor Utility`, which is frequency-SCALED (clamped 100). The two diverge
bidirectionally with CPU clock state: above base clock (turbo) Utility > Time and can exceed
100; downclocked (GPU-bound encode) Utility < Time. The `% Processor Time` headline was a
deliberate choice (see comment in `system_metrics.py`) to avoid Utility's >100 turbo saturation.

Resolution (Option C = show BOTH): kept `% Processor Time` as the headline `cpu_percent`; added
a secondary, clamped `% Processor Utility` ("Task Manager-equivalent") figure carried end-to-end
as a new `cpu_utility_percent` field. No change to the headline basis, polling cadence (backend
2.0s / UI 4s), caching, memory/GPU telemetry, or any AGENTS.md section-7 area. Telemetry is
read-only diagnostics; no media/queue/publish/settings behaviour touched.

Changed files (all mine; additive):
- `src/mediapipeline/core/telemetry/system_metrics.py` -- new `WINDOWS_PROCESSOR_UTILITY_COUNTER`;
  `create_cpu_utility_sampler()`; `_sample_cpu_utility()` (clamped 0-100, no psutil fallback --
  Utility has no psutil equivalent); `prime_cpu_sampler()` and `apply_system_metrics_to_snapshot()`
  gained an optional `cpu_utility_sampler` param (back-compatible; busy-time path unchanged).
- `src/mediapipeline/core/telemetry/service.py` -- creates/primes the utility sampler in its own
  PDH query and passes it through `sample_system_telemetry`.
- `src/mediapipeline/core/kernel/models_core.py`, `.../dto_status.py` -- new optional
  `cpu_utility_percent: float | None = None` on `TelemetrySnapshot` / `TelemetryDto`.
- `src/mediapipeline/core/observability/status_policy.py` -- `telemetry_fields` emits
  `cpu_utility_percent`.
- `apps/desktop/webview/static/partials/page-telemetry.html` -- `#cpu-utility-note` under the CPU
  chart.
- `apps/desktop/webview/static/assets/telemetryView.js` -- `cpuUtilityNoteText()` renders
  "Task Manager-equivalent (% Utility): N%"; wired into `renderTelemetry`, the readiness summary,
  and the public namespace export.
- `tests/python/desktop/test_telemetry_service.py` -- 3 new unit tests (utility counter path;
  clamped utility recorded separately from the % Processor Time headline; utility None when no
  sampler). Existing `test_cpu_counter_uses_processor_time_basis_not_turbo_utility` guard still
  green (headline basis unchanged).

Ollama: not used. No commit/branch performed.

Validation (agent-side; bundled `apps\desktop\runtime\Python\python.exe`, which lacks pytest
after the 2026-06-04 runtime refresh -- ran via `unittest`):
- `py_compile` (6 changed Python files) + `node --check telemetryView.js`: clean.
- `test_telemetry_service.py`: 24/24 OK (incl. the basis-guard test).
- `test_application_facade_core_contracts` 13/13, `test_application_facade_snapshot` 6/6,
  `test_facade_status_policy` 4/4: OK (telemetry DTO/`to_mapping` NaN-safe path carries the new
  field).
- Live backend probe (real PDH + psutil, 2s window): `cpu_percent=34.4`,
  `cpu_utility_percent=43.2`, both serialized through `telemetry_fields` (Utility > Time while
  boosting; inverts when downclocked).
- Live JS probe of `cpuUtilityNoteText`: 43.2 -> "43%", 137 -> clamped "100%", null/missing ->
  "unavailable".

Pre-existing red baseline (NOT mine; surfaced only when the wildcard `test_application_facade*.py`
pattern pulled in `test_application_facade_web_static.py`): the rename static-JS assertions vs the
operator's uncommitted rename/settings JS refactors, already documented in earlier handoffs.

Operator validation still REQUIRED before sign-off:
- Visual confirmation in the running app (Launch preview / Tauri) during a real encode: CPU card
  keeps the busy-time headline and the new "Task Manager-equivalent (% Utility)" line tracks Task
  Manager. (Agent cannot drive a live encode.)

Change-control follow-ups NOT done (flagged, held to avoid colliding with concurrent sessions):
- No `ops/release/changes/unreleased/MP-CHANGE-*.json` packet created (id-collision risk with
  active sessions). `validate_changes --require-worktree-coverage` will list the 8 changed files
  as uncovered until a packet is added.
- `docs/generated/summaries/` mirrors for the changed sources not regenerated
  (`refresh_summaries`).

## Handoff 2026-06-09 -- empty source video-stream detection (operator-approved this turn)

Task: TDARR matrix run-20260608-044850-full surfaced case tdarr-0698, an external tdarr sample
(`sample__2160__libx265__alac__30s__video.mkv`) whose mkv header declares a 2160p video stream with
zero decodable packets. ffprobe reported the stream, so the presence-only SOURCE_MEDIA_VIDEO_MISSING
guard passed; the file routed to encode, ffmpeg aborted ("Cannot determine format of input after
EOF"), and the failure was mis-classified transient and retried 3x. Operator chose the permanent
pipeline-side fix.

Scope note (AGENTS.md S7-adjacent; FFmpeg/probe area): change deliberately confined to the clean
`ops/pipeline/engine/probe/media_probe.ps1`. The source-probe preflight guard in
`pipeline_processing.ps1` and `failure_codes.ps1` already had uncommitted in-flight changes from other
work, so this change reuses the existing `video_stream_missing` signal + SOURCE_MEDIA_VIDEO_MISSING
code (no new failure code, no registry churn, no edits to those dirty files).

Changed:
- `ops/pipeline/engine/probe/media_probe.ps1` -- Get-SourceMediaRouteProfile now does a bounded
  first-video-packet probe (`ffprobe -select_streams v:0 -read_intervals %+#1 -count_packets`); a
  positive zero-packet result sets probe_ok=false / probe_error='video_stream_missing'. Ambiguous or
  failed probes leave the source eligible (no false rejects).
- `ops/release/changes/unreleased/MP-CHANGE-2026-0609-001.json` -- new change packet (status
  in_progress).

Validation (agent-side): media_probe.ps1 parse OK; Invoke-PipelineProcessingSourceProbeChecks.ps1 and
Invoke-FailureCodeRegistryChecks.ps1 pass; real-media harness (bundled ffprobe) -> broken asset
probe_ok=False/probe_error='video_stream_missing', healthy asset probe_ok=True/probe_error=''.

Operator validation REQUIRED before status=complete (AGENTS.md S5 media/FFmpeg rung; not
self-certified):
- Run the real broken source end-to-end through `ops/pipeline/entrypoints/MediaPipeline.ps1`; confirm
  permanent, non-retryable SOURCE_MEDIA_VIDEO_MISSING at stage source-probe, no encode, no retries.
- Confirm a healthy 2160p h265 source still routes/encodes normally (hot-path regression for the added
  bounded probe).

Follow-ups not done this turn: summary refresh for media_probe.ps1 deferred to the pre-commit hook to
avoid sweeping unrelated in-flight files. PROJECT_INDEX.md and docs/audit/latest.md were missing
(degraded mode).

### Part A 2026-06-09 -- quarantine undecodable-video tdarr fixtures (MP-CHANGE-2026-0609-002)

Operator approved doing both the pipeline fix and the fixture-side fix. A full ffprobe sweep of the
tdarr sample pool found 124 of 2316 files declare a video stream with zero decodable packets (the
tdarr-0698 libx265/alac/mkv family plus many *.mp2 and libx265-in-wmv stress combos). These download
byte-complete (size+sha256 match) but cannot be encoded.

Changed (repo, non-S7, prior TDARR-audit session scope):
- `src/mediapipeline/tools/dev/materialize_tdarr_test_library.py` -- TdarrSample gains
  `video_decodable`; load_inventory reads it; new is_quarantined_sample/partition_quarantined_samples
  skip samples marked 'false'; materialize() summary adds quarantined_samples. Absent/empty/other
  values include (backward compatible).
- `tests/python/tooling/test_materialize_tdarr_test_library.py` -- 2 new tests (predicate +
  end-to-end skip). Suite 6/6 pass via bundled Python.

Changed (gitignored E: asset tooling, not repo-tracked):
- `E:\Videos\TdarrMatrix\TestFixtures\TdarrSamples\download_tdarr_samples.py` -- ffprobe decodability
  check (find_ffprobe/probe_video_decodable/annotate_decodability), `video_decodable` inventory
  column, `--verify-only`/`--ffprobe` modes, undecodable_video_files summary. py_compile clean.
- Ran `--verify-only` to populate the existing inventory's video_decodable column (inventory.csv/json
  backed up to *.pre-decodable.bak first).

Operator validation REQUIRED: rebuild the matrix library (materialize --rebuild) and confirm
quarantined_samples matches the undecodable count and those sources are absent from source/Movies +
source/TV.

Optional remaining hardening (not done): broader malformed-source encode-classification fix at the
failure-recording site (belt-and-suspenders beyond the preflight catch).

## Handoff 2026-06-09 — Library profile config-cluster code-review fixes (operator-approved in chat; out of TDARR/kernel scope)

Operator approved (chat, 2026-06-09: "go ahead and work on all of these") implementing 7 findings from a
code review of the `src/mediapipeline/core/config/library_profile_*` cluster. Scope drift flagged: this is the
config domain, separate from the TDARR-matrix and entrypoint/kernel work scoped above. Touches AGENTS.md §7
"Settings schema/defaults/persistence" -> NOT self-certified; operator smokes still required (below).

Changed files (all under `src/mediapipeline/core/config/` unless noted):
- `library_profile_validation.py` -- NEW advisory warning when one enabled library source root is nested
  inside another's (`_nested_source_warning`); previously only exact-equal source roots errored. Warning only,
  never blocks save. Also commented the intentional broad `except` blocks.
- `library_profile_state.py` -- hoisted `default_library_settings`/`coerce_library_overrides` out of the
  per-key loop in `library_profile_state` (was O(N^2) full rebuilds; output identical) via new private
  `_setting_override_field_state`; dropped the dead `config` first param from `library_profile_path_field_state`
  (no external callers; still exported by name).
- `library_profile_normalization.py` -- `library_profiles_from_config` duplicate-id dedup is now consistently
  first-wins (movies/tv were last-wins, others first-wins). Only affects invalid configs with duplicate ids
  (validation already errors on those).
- `library_profile_promotion.py` -- removed an unreachable guard in `mirror_legacy_keys_from_library_profiles`;
  commented the broad `except` blocks.
- `library_profile_compatibility.py` (untracked file) -- `mp4_compatibility_applied` uses `.casefold()` not
  `.lower()` for cluster consistency.
- `tests/python/desktop/test_library_profiles.py` -- +3 tests: nested-source warning, sibling-source no-warn,
  duplicate-movies-id first-wins.

Validation performed (agent-side, bundled `apps\desktop\runtime\Python\python.exe`, `PYTHONPATH=src`):
- `test_library_profiles.py` 71/71 OK (incl. 3 new).
- `test_route_map.py`, `test_library_route_map_api.py`, `test_config_contract.py`, `test_config_keys.py`,
  `test_service_config_validation.py` all OK.
- `test_final_library_promotion.py`: promotion logic passes; the single failure
  (`test_webview_exposes_dashboard_and_selected_file_promotion_entry_points`) is PRE-EXISTING and unrelated --
  the dirty working tree changed the home partial label "Promote Files" -> "Open Completed Output" but that test
  still asserts the old text. Not caused by this change.

§7 not self-certified -- operator smokes still required:
- `ops\scripts\smoke\Test-WebViewSettingsLaunchLiveConfigSmoke.ps1`
- `ops\scripts\smoke\Test-WebViewSettingsPatchEvidenceSmoke.ps1`
- `ops\scripts\smoke\Test-LocalApiLifecycleContractSmoke.ps1` (operator-surface-opens check)

Follow-ups not done: `docs/generated/summaries/` mirrors for the 4 edited tracked files are now stale
(regenerate via the documented summary script if desired); no `ops/release/changes/unreleased/` change packet
created for this out-of-scope work. Ollama not used.

### Round 2 (same approval) -- deeper edge cases A-F

Operator approved (chat, 2026-06-09: "Please address all these issues") fixing 6 additional findings from a
deeper review (preview-vs-engine routing parity, robustness, contract clarity). Same out-of-scope config domain;
A/D are §7-adjacent (routing) -> NOT self-certified (smokes below). D additionally touches the §7 PS engine.

Changed files:
- `src/mediapipeline/core/config/library_profile_state.py` (A, B):
  - A: rewrote `effective_library_profile_for_source_path` so its path matching mirrors the engine
    (`Get-MediaPipelineLibraryProfileForPath`/`Test-MediaPipelinePathUnderRoot`): resolve `..`, absolutize,
    `os.path.normcase`, separator-boundary containment (replaces the prior forward-slash `casefold`/`startswith`).
    Added optional `selected_profile_id` kwarg that mirrors the engine's `CurrentLibraryProfileId` precedence
    (default None = unchanged; preview callers reflect default selection-free routing). Docstring documents the
    contract. The 4 preview callers were NOT rewired (they have no runtime selection).
  - B: guarded the `library_profiles_from_config` call in `apply_library_profile_resets` so malformed
    `LibraryProfiles` returns `(values, ["LibraryProfiles is invalid: ..."])` instead of raising (matches the
    sibling normalize/mirror swallow behavior; fixes the unguarded call at
    `settings_patch_candidate_facade.py:176`).
- `src/mediapipeline/core/config/library_profile_validation.py` (C, F):
  - C: `validate_library_profiles` now warns when a raw id/name slug collapses onto a reserved built-in id
    ("Library profile {label} maps to the reserved 'movies'/'tv' library (matched '{slug}').").
  - F: `_validate_profile_effective_settings` validates the base config alone first and subtracts that baseline,
    so only override-introduced errors/warnings are attributed to the profile (no more mis-attributing
    pre-existing base errors).
- `src/mediapipeline/core/config/library_profile_normalization.py` (E): comment documenting the
  explicit-`inherited_fields` output-path override behavior (no code change).
- `ops/pipeline/engine/paths/library_profiles.ps1` (D, §7 engine): added 'disable' to the enabled disabled-set
  and 'enable' to the promotion-enabled true-set so the PS enabled/promotion string vocabulary matches Python
  `_bool_value`. Note: moot in the normal flow (Python normalizes enabled/promotion_enabled to real booleans at
  save time); only affects hand-edited/legacy string values.
- `tests/python/desktop/test_library_profiles.py`: +6 tests (dotdot/case path resolution, selection precedence,
  malformed-config reset returns error, reserved-id collapse warning, explicit-inherited output, base-error
  non-attribution). Added `effective_library_profile_for_source_path` to imports.

Validation performed (agent-side):
- `test_library_profiles.py` 77/77 OK (incl. 6 new).
- `test_route_map.py`, `test_library_route_map_api.py`, `test_service_config_validation.py` OK.
- `test_final_library_promotion.py`: same single PRE-EXISTING webview-label failure
  (`test_webview_exposes_dashboard_and_selected_file_promotion_entry_points`); not introduced here.
- D engine change: `pwsh -File ops\pipeline\tests\Unit\Invoke-LibraryProfileRoutingChecks.ps1` -> exit 0,
  "Library profile routing checks passed."

§7 not self-certified -- operator smokes still required (same as Round 1):
- `ops\scripts\smoke\Test-WebViewSettingsLaunchLiveConfigSmoke.ps1`
- `ops\scripts\smoke\Test-WebViewSettingsPatchEvidenceSmoke.ps1`
- `ops\scripts\smoke\Test-LocalApiLifecycleContractSmoke.ps1`
Plus, because D edits the PS routing engine, an end-to-end/pipeline routing smoke if the operator runs one.

## Handoff 2026-06-10 -- launch-section code-review fixes (operator-approved in chat; branch refactor/mediapipeline-entrypoint-slice)

Operator approved (chat, 2026-06-10: "Please address these issues") fixing the 7 findings from a
launch-section code review of `ops/pipeline/entrypoints/MediaPipeline.ps1` + its startup slices.
Change packet `ops/release/changes/unreleased/MP-CHANGE-2026-0610-001.json` (in_progress); strict
worktree coverage passes (162 packets valid). Ollama: not used. No commit performed; the tree was
clean before this work, so the working-tree diff is exactly this change set.

Changed files:
- `ops/pipeline/entrypoints/MediaPipeline.ps1` -- pause/stop-flag cleanup and temp/stale-partial
  sweeps gated to controller-style runs (skip -WorkerChild and -DumpEffectiveConfigPath); dump and
  -ValidateOnly no longer write the shared progress file; explicit `& $Script:ExitCleanup` on every
  post-lock fatal exit; `Import-PowerShellDataFile -LiteralPath`; removed dead `$args` relaunch
  branch, `$requiredKeys`/`$arrayKeys`, `$moduleRoot`; added `$startupFatalExitCode` checks after
  each fatal-capable slice dot-source.
- `ops/pipeline/entrypoints/MediaPipeline/module_loader.ps1` -- ordered load list extracted to
  `$engineModuleLoadOrder` with a startup contract check (load order and manifest must describe the
  same 46-module set; FATAL on drift); removed the silent `Join-Path $moduleRoot` legacy fallback;
  fatal paths set the sentinel.
- `ops/pipeline/entrypoints/MediaPipeline/runtime_paths.ps1` -- worker-arg FATALs (exit 74) set the
  sentinel.
- `ops/pipeline/entrypoints/MediaPipeline/startup_filesystem.ps1` -- claims repair + active-jobs
  reset additionally skip -DumpEffectiveConfigPath.
- `ops/pipeline/entrypoints/MediaPipeline/startup_path_validation.ps1` -- LocalBase FATAL (exit 2)
  sets the sentinel.
- `ops/release/changes/unreleased/MP-CHANGE-2026-0605-010.json` -- added missing required
  `date_completed` field (schema compliance only; was blocking validate_changes for every session).
- `docs/generated/summaries/` mirrors regenerated for the 5 edited sources.

IMPORTANT LEARNING (proven by minimal repro under PS 7.6): `exit` inside a dot-sourced .ps1 aborts
only that file; the dot-sourcing script CONTINUES and the process exits 0. Every FATAL `exit`
inside the extracted slices (worker-arg 74, LocalBase 2, loader 1) was therefore a no-op for the
entrypoint -- a latent regression from the slice extraction that the parity oracle could not catch
(those paths never fire in healthy runs). Fixed via a `$startupFatalExitCode` sentinel contract:
the slice sets it and exits (aborting the rest of the slice); the entrypoint checks it after each
dot-source and exits for real, running ExitCleanup where the instance lock is already held. Any
FUTURE fatal path added to a dot-sourced slice must follow this pattern.

Validation (agent-side): parse OK x5; -DumpEffectiveConfigPath canonical parity vs pre-change
baseline IDENTICAL (live per-user config, key-sorted JSON compare); -ValidateOnly log diff 0 lines
(timestamps stripped); progress-file mtime unchanged across post-fix dump/validate runs; stop-flag
survival test (flag survives a dump run; was deleted at HEAD); dump-mode cleanup log markers absent
after fix; loader drift negative test trips both FATALs; real-entrypoint negative test
`-WorkerChild -WorkerSlotId 9` exits 74 (continued running before the sentinel fix);
`ops/pipeline/tests/Invoke-EndToEndSmokeChecks.ps1` exit 0 before and after.

§7 NOT self-certified (queue launch scope / worker dispatch / progress): operator must run a real
-Once/continuous pass with at least one parallel-encode worker-child dispatch, confirming pause/stop
flags set mid-run are honored and worker results are consumed normally; optionally
`python -m mediapipeline.tools.dev.ai_guardrail` preflight/postflight.

Pre-existing, not mine: `ops/pipeline/tests/Unit/Invoke-RuntimeConfigResolutionChecks.ps1`
self-skips (still points at pre-reorg `ops/pipeline/MediaPipeline.ps1` and
`ops/pipeline/PowerShell-7.6.0-win-x64`), and
`ops/pipeline/tests/Legacy/Invoke-LegacyDesktopReliabilityRegressionChecks.ps1` reads the same
nonexistent path. PROJECT_INDEX.md and docs/audit/latest.md absent (degraded mode). A TDARR-matrix
worker child (separate LocalBase) ran concurrently throughout; validation used the per-user live
config, whose LocalBase it does not share.
