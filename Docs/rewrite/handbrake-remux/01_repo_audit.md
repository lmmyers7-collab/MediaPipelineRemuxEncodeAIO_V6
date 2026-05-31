# Phase 01 Repository Discovery and Architecture Audit

Date: 2026-05-30

Scope: docs-only discovery for the HandBrake/remux rewrite plan. This phase
does not change runtime behavior, schemas, tests, launchers, queue behavior,
settings persistence, media policy, source movement, publish/drain logic, or
desktop shell lifecycle.

## Phase Confirmations

- Approved docs and tracker location: `Docs/rewrite/handbrake-remux/`
- Edit domain for this phase: documentation only in the approved subtree
- High-risk areas touched: yes, but audit-only. The audit covers settings,
  queue routing, FFmpeg/remux/encode, subtitles, audio, pending publish, source
  movement, command journal, and Tauri/backend ownership boundaries without
  editing those areas.

## Input Documents Read

- `AGENTS.md`
- `Docs/CURRENT_PROJECT_STATE.md`
- `OPEN_WORK_CHECKLIST.md`
- `Docs/generated/PROJECT_INDEX.md`
- `C:/Users/lmmye/Downloads/handbrake_remux_rewrite_plan/13_CODEX_MASTER_PROMPT.md`
- `C:/Users/lmmye/Downloads/handbrake_remux_rewrite_plan/00_EXECUTION_ORDER.md`
- `C:/Users/lmmye/Downloads/handbrake_remux_rewrite_plan/01_REPO_DISCOVERY_AND_ARCHITECTURE_AUDIT.md`

The `AGENTS.md` startup list names
`Docs/architecture/ARCHITECTURAL_OVERHAUL_PLAN.md`, but that file was not
present in this checkout. The operator clarified on 2026-05-30 that the
architecture overhaul plan has been deleted. The current architecture material
found under `Docs/architecture/` includes `ARCHITECTURE.md`,
`CONFIG_KEY_GLOSSARY.md`, and related domain maps.

## Repository Summary

This repository is the V6 Windows-first media pipeline. Runtime work is split
across:

- `app/`: Python contracts, domain services, facades, orchestration, storage,
  validation, and route command mappings.
- `DesktopApp/mediapipeline_desktop_app/`: local API host, compatibility
  package, WebView-served static app, and desktop integration.
- `engine/`: domain-organized PowerShell implementation for config, decision,
  process, probe, publish, queue, shared helpers, storage, subtitles, and
  validation.
- `Pipeline/`: root engine entry scripts, profiles, schemas, bundled tools,
  helper scripts, and PowerShell tests.
- `Docs/`, `Docs/generated/`, `Docs/inventories/`, and `summaries/`:
  operator/engineering docs, generated maps, inventories, and token summaries.
- `LocalBase/`: gitignored runtime state.

The checkout is mid-overhaul. Active guidance in `AGENTS.md` prohibits new
flat Python facade/service files, new dotted PowerShell modules under
`Pipeline/Modules/`, new top-level Markdown status files, and new single
source of truth documents.

## Frontend Map

The desktop UI is a backend-served vanilla JavaScript WebView SPA, not a
React/Vue app.

Key files:

- `DesktopApp/mediapipeline_desktop_app/ui_web/static/index.html`: loads
  page partials, shared helpers, settings builders, views, lifecycle code, and
  the app bootstrap.
- `DesktopApp/mediapipeline_desktop_app/ui_web/static/partials/page-settings.html`:
  contains the current Default Editor UI for routing and encode/remux controls.
- `DesktopApp/mediapipeline_desktop_app/ui_web/static/js/settingsMetadata.js`:
  maps config keys to UI labels, element ids, help text, groups, and
  validation metadata.
- `DesktopApp/mediapipeline_desktop_app/ui_web/static/js/settingsView.js`:
  renders settings sections and posts preview/save requests.
- `DesktopApp/mediapipeline_desktop_app/ui_web/static/js/settings/patchReview.js`,
  `settings/policyImpact.js`, and `settings/backendResult.js`: render backend
  patch evidence, risk summaries, and save/preview results.
- `DesktopApp/mediapipeline_desktop_app/ui_web/static/js/queueView.js`,
  `pendingView.js`, `completedView.js`, `launchView.js`, and
  `diagnosticsView.js`: own non-settings UI surfaces.

Important frontend endpoints used today:

- `GET /api/settings/workspace`
- `POST /api/settings/preview-patch`
- `POST /api/settings/save-patch`
- `POST /api/settings/validate`
- `POST /api/settings/reload`
- `GET /api/queue`
- `POST /api/queue/priority`
- `POST /api/queue/strategy`
- `POST /api/queue/file-overrides`
- `GET /api/completed?limit=all`
- `GET /api/pending-publish`
- `GET /api/launch/preflight`

The UI stages patch payloads and evidence, but backend services own settings
validation, persistence, queue mutation, command journaling, and media policy.

## Backend Map

The local API is a Python stdlib HTTP server:

- `DesktopApp/mediapipeline_desktop_app/api/handler.py`: builds the local API
  handler class and dispatches `do_GET` and `do_POST` through route maps.
- `DesktopApp/mediapipeline_desktop_app/api/routes_read.py`: defines read
  route handlers such as settings workspace, queue, completed, pending
  publish, launch preflight, and wizard defaults/status.
- `DesktopApp/mediapipeline_desktop_app/api/routes_command.py`: builds POST
  route handlers from command route specs.
- `app/api/commands.py`: defines `ApiCommandRouteSpec`,
  `COMMAND_ROUTE_METHODS`, and `COMMAND_ROUTE_SPECS`.
- `DesktopApp/mediapipeline_desktop_app/api/contract_command.py`: documents
  command route effects and risk metadata.
- `DesktopApp/mediapipeline_desktop_app/api/command_journal.py`: implements
  `CommandJournal`.
- `DesktopApp/mediapipeline_desktop_app/api/command_journal_policy.py`:
  defines command history/result schema versions and journal policies.

Application facade and services:

- `DesktopApp/mediapipeline_desktop_app/application/facade.py`:
  `MediaPipelineApplicationFacade`, composed from domain mixins under `app/`.
- `DesktopApp/mediapipeline_desktop_app/services.py`: `DesktopAppService`,
  wired to `app.config.service`, `app.queue.service`,
  `app.publish.pending_service`, `app.completed.service`, diagnostics, and
  launch services.
- `app/config/service.py`: `ConfigProfileServiceMixin` with
  `load_config_data`, `build_config_preview`, `validate_config_values`,
  `validate_config_document_for_save`, `save_config_document`,
  `save_config_profile`, and `load_config_profile`.
- `app/config/load.py`: PSD1 load/serialize bridge, including
  `load_config`, `config_from_mapping`, `config_to_flat_dict`,
  `config_to_psd1`, `load_psd1_mapping`, and `serialize_psd1_document`.
- `app/config/settings_facade.py`,
  `app/config/settings_patch_facade.py`,
  `app/config/settings_patch_candidate_facade.py`, and
  `app/config/settings_wizard_facade.py`: settings workspace, preview/save,
  patch candidate, and wizard facade layers.
- `app/orchestration/runner.py`: Python subprocess boundary for stage
  execution through `engine/entrypoint.ps1`.

## Current Config And Schema Map

Python config contract:

- `app/contracts/config.py`: `Config`, `CONFIG_SCHEMA_VERSION`, enums and
  validation constraints for paths, routing, video, audio, subtitles, queue,
  publish, tools, runtime, and safety settings.
- `schemas/config.v1.schema.json`: generated JSON schema for the Python
  contract.
- `app/config/metadata_parts/basic_fields.py`: Basic page metadata, including
  route threshold, routing profile, copy bitrate, growth, and deferred publish
  labels.
- `app/config/metadata_parts/video_fields.py`: Video page metadata, including
  `VideoCodec`, `VideoPreset`, `VideoQuality`, `OutputContainer`,
  `EncodeTuningPreset`, `EncodeLadder`, and `RemuxSafeVideoCodecs`.
- `app/config/library_profiles.py`: `DEFAULT_EDITOR_KEYS`,
  `default_editor_values`, `library_profiles_from_config`,
  `mirror_legacy_keys_from_library_profiles`,
  `normalize_library_profile_config_values`, and `validate_library_profiles`.

PowerShell config layer:

- `engine/config/config_schema.ps1`: config defaults, enum helpers, and
  validators, including `Get-MediaPipelineRoutingProfileNames`,
  `Get-MediaPipelineRouteThresholdModeNames`,
  `Get-MediaPipelineSizeGuardModeNames`,
  `Get-MediaPipelineEncodeTuningPresetNames`,
  `Get-MediaPipelineEncodeLadderNames`, and
  `Test-MediaPipelineConfigEncodeAudioPolicy`.
- `Pipeline/Profiles/Default.psd1`: checked-in default profile with routing,
  threshold, growth, video, subtitle, audio, publish, and runtime settings.
- `Pipeline/MediaPipeline_config_template.psd1`: template profile.
- `Pipeline/MediaPipeline_config_chatgpt.psd1`: local runtime profile with
  user-specific paths and the same current routing/settings key family.
- `Pipeline/Schemas/media_pipeline_config.schema.json`: pipeline config schema.

Required legacy/current terminology appears in both layers:

| Concept | Python/UI/settings layer | PowerShell/profile layer |
| --- | --- | --- |
| Routing profile | `RoutingProfile`, `settings-builder-routing-profile`, `DEFAULT_EDITOR_KEYS` | `RoutingProfile` in `engine/config/config_schema.ps1` and `Pipeline/Profiles/Default.psd1` |
| Route threshold mode | `RouteThresholdMode`, `settings-builder-route-threshold-mode` | `RouteThresholdMode`, `Get-MediaPipelineRouteThresholdModeNames` |
| Size guard | `SizeGuardMode`, `settings-builder-size-guard` | `SizeGuardMode`, `Get-MediaPipelineSizeGuardModeNames` |
| Encode tuning | `EncodeTuningPreset`, `settings-builder-encode-tuning` | `EncodeTuningPreset`, `Get-MediaPipelineEncodeTuningPresetNames` |
| Encode ladder | `EncodeLadder`, `settings-builder-encode-ladder` | `EncodeLadder`, `Get-MediaPipelineEncodeLadderNames` |
| Growth percent | `MaxEncodeGrowthPercent`, `CompatibilityEncodeGrowthPercent` | same PSD1 keys; consumed by size guard policy |
| Threshold GB | `EncodeThresholdGB`, `TVEncodeThresholdGB` | same PSD1 keys; consumed by route selection |
| Copy max Mbps | `MovieRouteMaxVideoBitrateMbps`, `TVRouteMaxVideoBitrateMbps` | same PSD1 keys; consumed by route selection |

## Current Decision-Flow Map

The active route decision is PowerShell-owned today.

Queue preview path:

- `engine/queue/pipeline_engine.ps1` resolves library, show, folder, and
  per-file overrides, calls `Get-ActiveMediaRouteHints`, calls
  `Get-SourceMediaRouteProfile`, then calls
  `Resolve-InitialMediaRoutePlan` to populate queue row route evidence.

Processing path:

- `engine/process/pipeline_processing.ps1` function
  `Invoke-MediaPipelineProcessFile` performs preflight checks, resolves active
  overrides, calls `Get-SourceMediaRouteProfile`, calls
  `Resolve-InitialMediaRoutePlan`, writes a `route_selected` event, stores
  `$script:CurrentRoutePlan`, then dispatches to `Do-Encode` or `Do-Remux`.
- `engine/decide/routing.ps1` function `Resolve-InitialMediaRoutePlan`
  collects thresholds, route threshold mode, routing profile, size guard,
  bitrate caps, H.264 compatibility settings, source metadata, and route
  hints, then delegates to `Resolve-MediaRouteBySize`.
- `engine/decide/routing.ps1` function `Resolve-MediaRouteBySize` creates
  the route plan, action set, reason code, decision trace, threshold evidence,
  Plex compatibility score, and probe requirements.
- `engine/decide/routing.ps1` function `Resolve-RemuxCodecRoutePlan`
  finalizes remux safety once the codec is known and can switch a remux plan
  to encode with reason codes such as `codec_not_remux_safe` or
  `forced_remux_rejected_unsafe_codec`.

Stage boundary:

- `engine/decide/stage.ps1` function `Invoke-DecideStage` returns JSON-ready
  route evidence.
- `app/contracts/stages.py` defines `DecidePayload` and `DecideResult`.
- `app/orchestration/runner.py` exposes `run_decide_stage`.

This means there is a JSON-compatible decide stage, but the actual policy and
production route execution still live in PowerShell.

## Current Encode/Remux Execution Map

Process dispatch:

- `Pipeline/MediaPipeline.ps1` `Process-File` is a compatibility wrapper
  around `Invoke-MediaPipelineProcessFile`.
- `engine/process/pipeline_processing.ps1` dispatches to `Do-Encode` or
  `Do-Remux` based on `Resolve-InitialMediaRoutePlan`.

Encode path:

- `Pipeline/MediaPipeline/encode.ps1` `Do-Encode` prepares scratch input,
  subtitle/audio arguments, HDR metadata, encode plan, FFmpeg invocation,
  fallback handling, verification, and publish.
- `engine/decide/encode_policy.ps1` owns encode command policy helpers such as
  `New-EncodeVideoFlags`, `New-EncodeFfmpegArgumentList`,
  `New-EncodeAttemptPlan`, `Get-MediaEncodeLadderProfile`,
  `Test-NvencAvailable`, `Test-IsHardwareEncoderFailure`, and
  `Test-ShouldRetryEncodeWithCpuFallback`.
- `engine/process/ffmpeg_progress.ps1` wraps FFmpeg progress execution.
- `engine/shared/native.ps1` wraps native tool calls such as FFmpeg and
  ffprobe.

Remux path:

- `Pipeline/MediaPipeline/remux.ps1` `Do-Remux` prepares scratch input,
  validates remux-safe codec policy, builds audio and subtitle handling,
  invokes copy/remux tooling, verifies output, and publishes.
- `Do-Remux` can call `Resolve-RemuxCodecRoutePlan` and redirect into
  `Do-Encode` when codec safety rejects a planned remux.

Current mid-execution route changes:

- Remux-to-encode fallback happens inside `Do-Remux` when
  `Resolve-RemuxCodecRoutePlan` returns route `encode`.
- Encode safe retry and CPU fallback happen inside `Do-Encode`; successful CPU
  fallback updates `$script:CurrentRouteReasonCode` to
  `gpu_unavailable_cpu_only` or `hardware_encoder_cpu_fallback` and mutates
  route actions from hardware encode to software encode.

These mid-execution changes are the main Option A migration risk. The operator
decided on 2026-05-30 that remux codec fallback and CPU fallback should be
modeled in Python.

## Verification/Publish Map

Publish and completion:

- `engine/publish/publish_completion.ps1`: `Complete-PipelineOutputPublish`.
- `engine/publish/publish_completion/context_builders.ps1`:
  `New-PublishEvidenceContext`, `New-PendingParkArguments`, and related
  context helpers.
- `engine/publish/sidecar.ps1`: `Write-Sidecar`,
  `Move-SidecarTempIntoPlace`, `Add-CompletedJobsManifestEntry`,
  `Test-OutputNeedsReprocess`, `Test-SidecarRoundTripValid`, and
  `Get-SidecarPath`.

Pending publish:

- `engine/publish/pending_push.ps1`: `Invoke-ParkPendingPush`,
  `Invoke-ParkPendingPushWithTx3gSidecars`, and `Invoke-RetryPendingPushes`.
- `engine/publish/pending_transactions.ps1`: `Invoke-PendingParkTransaction`,
  `Invoke-PendingDrainTransaction`, `Repair-PendingManifestState`, and
  `Repair-PendingSidecarArtifacts`.
- `engine/publish/pending_manifest_store.ps1`: pending manifest read/write
  helpers.
- `engine/publish/pending_publish_index.ps1`: pending index helpers.
- Python read/API services include `app/publish/pending_service.py`,
  `app/publish/pending_manifest.py`, and pending facade/policy modules.

Verification:

- Encode verifies duration and output size policy, including
  `Test-MediaEncodeOutputSizePolicy`.
- Remux verifies output and routes publish through the same publish completion
  layer.
- Pending publish remains a high-risk safety boundary and must not be bypassed
  by future planner/executor work.

## Current UI Components

Settings page components:

- Top-level settings partial:
  `DesktopApp/mediapipeline_desktop_app/ui_web/static/partials/page-settings.html`.
- Default Editor controls:
  `settings-builder-routing-profile`,
  `settings-builder-size-guard`,
  `settings-builder-route-threshold-mode`,
  `settings-builder-encode-tuning`,
  `settings-builder-encode-ladder`,
  `settings-builder-video-codec`,
  `settings-builder-output-container`,
  `settings-builder-max-growth`,
  `settings-builder-compat-growth`,
  `settings-builder-movie-threshold`,
  `settings-builder-tv-threshold`,
  `settings-builder-movie-route-bitrate`,
  `settings-builder-tv-route-bitrate`.
- Settings scripts:
  `settingsOverview.js`, `settingsMetadata.js`,
  `settingsView.builders.audio.js`, `settingsView.builders.video.js`,
  `settingsView.builders.subtitle.js`, `settingsView.builders.queue.js`,
  `settingsView.builders.runtime.js`,
  `settingsView.builders.file_safety.js`,
  `settingsView.builders.pending.js`,
  `settingsView.builders.network.js`, `settingsView.rawTriage.js`,
  `settingsView.safetyLocks.js`, `settingsView.js`,
  `settingsLibraries.js`, and `settingsWizard.js`.

Other loaded page partials include home, telemetry, queue, completed, pending,
rename, launch, reports, schedule, network, maintenance, diagnostics,
libraries, and settings.

## Current Tests And Test Gaps

Python and API tests:

- `tests/contract/test_config_contract.py`: `Config` defaults, generated
  schema, enum validation, and routing-related fields.
- `tests/contract/test_stage_contracts.py`: stage contract validation.
- `DesktopApp/tests/test_stage_contracts.py`,
  `test_stage_entrypoint.py`, and `test_stage_runner.py`: stage boundary and
  runner behavior.
- `DesktopApp/tests/test_service_config_validation.py`,
  `test_service_config_preview.py`, `test_service_config_psd1.py`,
  `test_service_config_save_runner.py`, `test_service_config_profiles.py`,
  `test_config_keys.py`, and `test_app_config_contract.py`: config load,
  preview, validation, save, and key alignment.
- `DesktopApp/tests/test_application_facade_settings_patch.py`,
  `test_application_facade_settings_workspace.py`,
  `test_facade_settings_policy.py`,
  `test_facade_settings_patch_policy.py`, and
  `test_settings_risk_policy_rules.py`: settings workspace and patch safety.
- `DesktopApp/tests/test_application_facade_local_api.py`: route/HTML checks,
  settings builder controls, preview/save endpoints, and command history.
- WebView settings smoke tests cover settings launch, patch evidence, and live
  config behavior.

PowerShell tests:

- `Pipeline/Tests/Invoke-ReliabilityRegressionChecks.ps1`: reliability suite
  wrapper.
- `Pipeline/Tests/Unit/Invoke-MediaRouteSelectionChecks.ps1`: route selection
  unit checks for threshold modes, size/bitrate, H.264 compatibility, codec
  fallback, and missing duration behavior. This file was untracked before
  Phase 01 edits. Verification on 2026-05-30 found that it is referenced by
  the modified reliability suite, has no prior git history at that path, and
  passes when run directly.
- `Pipeline/Tests/Unit/Invoke-LibraryProfileRoutingChecks.ps1`: library
  routing override behavior.
- `Pipeline/Tests/Unit/Invoke-ConfigKeyRegistryChecks.ps1`: config key
  registry alignment.
- `Pipeline/Tests/Unit/Invoke-AudioPolicyChecks.ps1`,
  `Invoke-SubtitleBuilderDecisionChecks.ps1`,
  `Invoke-PendingPublishSafetyChecks.ps1`,
  `Invoke-PendingPublishOwnershipChecks.ps1`,
  `Invoke-SidecarWriteSafetyChecks.ps1`, and
  `Invoke-ContractSchemaChecks.ps1`: high-risk boundary coverage.
- `Pipeline/Tests/Invoke-ToolIntegrationChecks.ps1`: bundled tool checks with
  generated media.
- `Pipeline/Tests/Invoke-EndToEndSmokeChecks.ps1`: generated-media end-to-end
  smoke coverage.
- `Pipeline/Tests/Invoke-AdversarialForceKillEncodeChecks.ps1`: source safety
  and failed encode safety checks.

Gaps for later phases:

- No Python-owned pure `SourceMediaInfo`, `ProcessingDecision`, or
  `PipelinePlan` implementation owns the production decision path yet.
- Parity tests are needed before moving route selection from PowerShell to
  Python.
- Mid-execution remux codec fallback, GPU safe retry, and CPU fallback are not
  yet represented as an explicit Python plan record. The operator decided that
  remux codec fallback and CPU fallback should be modeled in Python.
- Real-media validation remains operator-attested and must be rerun after any
  future media policy, FFmpeg, subtitle, audio, publish/drain, source movement,
  or cleanup behavior change.

## Existing Command List

Canonical launch and validation commands from the current repo:

- `./scripts/dev/start-local-api.bat`
- `./scripts/dev/start-api-and-browser.bat`
- `./scripts/dev/start-tauri-preview.bat -CheckOnly`
- `./scripts/dev/start-tauri-preview.bat`
- `./scripts/dev/run.bat`
- `./scripts/dev/setup.bat`
- `./scripts/verify-env.bat`
- `./scripts/verify-env.ps1`
- `./scripts/release/build.ps1`
- `./scripts/release/test.ps1`
- `./scripts/operator/New-RealMediaValidationWorksheet.ps1`
- `DesktopApp/Runtime/Python/python.exe scripts/dev/ai_guardrail.py preflight --json`
- `DesktopApp/Runtime/Python/python.exe scripts/dev/ai_guardrail.py postflight --json`
- `DesktopApp/Runtime/Python/python.exe -m unittest discover -s DesktopApp/tests -p "test_*.py"`
- `DesktopApp/Runtime/Python/python.exe -m unittest discover -s tests -p "test_*.py"`
- `Pipeline/PowerShell-7.6.0-win-x64/pwsh.exe -NoProfile -ExecutionPolicy Bypass -File Pipeline/Tests/Invoke-ReliabilityRegressionChecks.ps1`
- `Pipeline/PowerShell-7.6.0-win-x64/pwsh.exe -NoProfile -ExecutionPolicy Bypass -File Pipeline/Tests/Invoke-ToolIntegrationChecks.ps1`
- `Pipeline/PowerShell-7.6.0-win-x64/pwsh.exe -NoProfile -ExecutionPolicy Bypass -File Pipeline/Tests/Invoke-EndToEndSmokeChecks.ps1`
- `npm run webview:prework:check`
- `npm run webview:check`
- `npm run webview:contract:check`
- `npm run webview:routes:check`
- `npm run webview:script-order:smoke`

Existing local API command routes are declared by `app/api/commands.py` and
include queue open/priority/strategy/file-overrides, pending publish open and
recovery plan, completed open, settings validate/browse/preview/save/reload,
settings wizard routes, maintenance backfill, and final library promotion.

## Option A Feasibility Answers

Where is routing decided today?

- Production routing is decided in PowerShell. Queue preview and file
  processing both call `Get-SourceMediaRouteProfile` and
  `Resolve-InitialMediaRoutePlan`, which delegates to
  `Resolve-MediaRouteBySize` in `engine/decide/routing.ps1`.
- Python has contracts and a stage runner for decide results, but it does not
  own the production decision engine today.

Does PowerShell route mid-execution?

- Yes. `Pipeline/MediaPipeline/remux.ps1` `Do-Remux` can switch a planned
  remux to encode through `Resolve-RemuxCodecRoutePlan`.
- Yes. `Pipeline/MediaPipeline/encode.ps1` `Do-Encode` can change route
  evidence for hardware safe retry and CPU fallback, including route reason
  codes and route action metadata.

Can source metadata cross as JSON into Python?

- Yes, with work. `engine/probe/media_probe.ps1`
  `Get-SourceMediaRouteProfile` already uses ffprobe JSON and normalizes a
  source media profile. `engine/probe/stage.ps1` `Invoke-ProbeStage` returns
  JSON-ready probe evidence, and `app/contracts/stages.py` models
  `ProbeResult` and `DecideResult`.
- The missing piece is not JSON transport; it is a Python-owned pure planner
  contract and parity-tested migration of route policy away from PowerShell.

## Risk List

- Routing is still implemented in PowerShell. Moving policy to Python without
  parity tests risks route regressions.
- Mid-execution route changes are real today. Treating PowerShell as a simple
  executor too early would hide remux codec fallback, GPU retry, and CPU
  fallback decisions.
- Settings keys span Python metadata, Python contracts, PowerShell schema,
  checked-in PSD1 defaults, and local runtime PSD1 files. Renames need
  cross-layer migration.
- Pending publish, sidecar, repair, and drain flows are safety-critical and
  must remain backend-owned.
- Source/scratch/output movement and cleanup are high-risk due the no-source
  mutation boundary.
- Audio, subtitle, stream mapping, and FFmpeg command generation require high
  validation and real-media samples when behavior changes.
- The checkout has pre-existing dirty files and untracked route-selection test
  files, so future diffs must separate Phase 01 docs from unrelated work. The
  untracked route-selection test appears to be intended new work and should be
  reviewed with the related reliability suite change.
- Guardrail preflight was already red before this phase due generated-summary
  and risky-file-registry drift.

## Open Questions

- Resolved 2026-05-30: do not restore
  `Docs/architecture/ARCHITECTURAL_OVERHAUL_PLAN.md`; the architecture
  overhaul plan has been deleted.
- Resolved 2026-05-30: no active root `SESSION.md` is required; the approved
  subtree tracker is sufficient.
- Resolved 2026-05-30: `Docs/audits/latest.md` is the intended audit path;
  prompts should not use the singular `Docs/audit/latest.md` path.
- Resolved 2026-05-30: the pre-existing untracked route-selection test appears
  to be intended new work and should be reviewed with the related reliability
  suite change.
- Resolved 2026-05-30: CPU fallback and remux codec fallback should be modeled
  in Python.
- Resolved 2026-05-30: the acceptance gate for moving from JSON-compatible
  stage contracts to Python-owned production route policy is zero unexplained
  divergences across a golden parity matrix, operator-approved documented
  exceptions for intentional divergences, shadow-mode comparison with no
  unresolved divergences, and representative real-media validation rerun for
  the touched media-policy surface.

## Recommended Next Phase Adjustments

- Treat Phase 02 as a planning/spec phase unless the operator explicitly
  approves code changes.
- Add a migration design for Python-owned planner types before changing route
  behavior, including Python-modeled remux codec fallback and CPU fallback.
- Define golden parity fixtures for current PowerShell route decisions,
  including size, bitrate, routing profile, route threshold mode, size guard,
  copy max Mbps, codec safety, H.264 compatibility, forced remux, GPU fallback,
  and CPU fallback cases.
- Preserve PowerShell executor behavior until golden parity and shadow-mode
  comparison prove that Python decisions match current production behavior or
  all divergences are documented and operator-approved.
- Keep pending publish, source mutation, command journal, settings
  persistence, and Tauri lifecycle boundaries out of the rewrite unless a
  later phase explicitly scopes them.
