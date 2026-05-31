# Phase 04 Decision Engine Contract

Date: 2026-05-30

Scope: additive Python-owned pure decision engine, DTO contract, and metadata
fixture tests for copy/remux/encode planning. This phase does not change
production PowerShell routing, FFmpeg command generation, UI, settings
persistence, queue behavior, subtitle/audio execution, source/scratch/output
movement, publish/drain behavior, cleanup, command journal behavior, or Tauri
lifecycle behavior.

## Phase Confirmations

- Approved docs and tracker location: `Docs/rewrite/handbrake-remux/`
- Edit domain for this phase: Python decision contracts/engine under `app/`,
  Python tests under `tests/`, generated summaries/index context, and this
  approved rewrite docs/tracker subtree
- High-risk areas touched: yes. This phase models copy/remux/encode media
  policy and source-media contract concepts, but the implementation is
  additive and not wired into runtime execution.

## Input Documents Read

- `AGENTS.md`
- `Docs/CURRENT_PROJECT_STATE.md`
- `OPEN_WORK_CHECKLIST.md`
- `Docs/generated/PROJECT_INDEX.md`
- `Docs/audits/latest.md`
- `Docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`
- `Docs/rewrite/handbrake-remux/00_execution_tracker.md`
- `Docs/rewrite/handbrake-remux/01_repo_audit.md`
- `Docs/rewrite/handbrake-remux/02_taxonomy_and_terms.md`
- `Docs/rewrite/handbrake-remux/03_source_media_model.md`
- `C:/Users/lmmye/Downloads/handbrake_remux_rewrite_plan/13_CODEX_MASTER_PROMPT.md`
- `C:/Users/lmmye/Downloads/handbrake_remux_rewrite_plan/00_EXECUTION_ORDER.md`
- `C:/Users/lmmye/Downloads/handbrake_remux_rewrite_plan/04_DECISION_ENGINE_COPY_REMUX_ENCODE.md`

## New Python Decision Surface

New files:

- `app/decide/__init__.py`
- `app/decide/processing_decision.py`
- `app/decide/routing_facts.py`
- `app/decide/routing_outputs.py`
- `app/decide/routing.py`

The Phase 04 engine is pure Python and takes:

- `SourceMediaInfo` from Phase 03
- `EffectiveDecisionPolicy`, or a legacy-key mapping adapted into that policy

It returns `ProcessingDecision` with:

- `streamActions`: per-stream video/audio/subtitle/container actions
- `routeSummary`: derived display label only, never the source of truth
- `routeReasons`: machine-readable and human-readable reasons
- `sourceFactsUsed`: selected normalized facts used by the planner
- `hardRulesTriggered`, `softTargetsExceeded`, and `advisoryWarnings`
- `plannedOutputSummary`
- `verificationRequirements`
- `publishRequirements`
- `effectiveSettings`
- `legacyRoute` and `legacyReasonCode` for characterization against the
  existing PowerShell route vocabulary

The engine does not build FFmpeg arguments and does not read source files.

## Effective Policy Inputs

`EffectiveDecisionPolicy` is deliberately abstract and uses Phase 02 terms:

- `routing_profile`
- `route_threshold_mode`
- `size_guard_mode`
- movie/TV route size limits
- movie/TV direct-copy bitrate caps
- H.264 compatible direct-copy toggle, bitrate cap, and height cap
- direct-copy video codec allowlist
- output container and container remux policy
- MP4 audio/subtitle copy compatibility lists

`decision_policy_from_mapping(...)` accepts current compatibility keys such as
`RoutingProfile`, `RouteThresholdMode`, `EncodeThresholdGB`,
`TVEncodeThresholdGB`, `MovieRouteMaxVideoBitrateMbps`,
`TVRouteMaxVideoBitrateMbps`, `OutputContainer`, and `RemuxSafeVideoCodecs`.
It does not create v2 config keys or migrate stored settings.

Accepted Phase 05 direction, recorded 2026-05-30: add a versioned `PresetV2`
wrapper for persisted/user-facing policy, but keep `EffectiveDecisionPolicy`
as the computed adapter target consumed by this engine. The intended flow is:

```text
legacy config / PresetV2
-> migration or adapter
-> EffectiveDecisionPolicy
-> ProcessingDecision
```

Do not store `EffectiveDecisionPolicy` as the preset schema. It is an internal
effective contract that can evolve with decision inputs while `PresetV2`
handles versioning, migration, and UI/settings semantics.

## Route Summary Derivation

The summary is derived from stream actions:

- `REJECT` if video is rejected
- `UNKNOWN` if video or container action is unknown
- `ENCODE` if video is encoded or a subtitle burn action is present
- `REMUX` if the container remuxes/changes, audio transcodes/drops, or
  subtitles convert/drop
- `COPY` only when every stream copies and the container is kept

Tests assert per-stream actions first and use `routeSummary` as display
confirmation.

## Reason Framework

The contract defines the required Phase 04 reason framework:

- `SOURCE_CODEC_COMPATIBLE`
- `SOURCE_CODEC_INCOMPATIBLE`
- `VIDEO_BITRATE_UNDER_DIRECT_COPY_CAP`
- `VIDEO_BITRATE_EXCEEDS_DIRECT_COPY_CAP`
- `RESOLUTION_UNDER_LIMIT`
- `RESOLUTION_EXCEEDS_LIMIT`
- `FILTERS_DISABLED_COPY_ALLOWED`
- `FILTERS_ENABLED_ENCODE_REQUIRED`
- `CONTAINER_REMUX_ONLY`
- `AUDIO_PASSTHROUGH_ALLOWED`
- `AUDIO_TRANSCODE_REQUIRED`
- `SUBTITLE_BURN_IN_REQUIRES_ENCODE`
- `SUBTITLE_FORMAT_INCOMPATIBLE_WITH_CONTAINER`
- `AUDIO_CODEC_INCOMPATIBLE_WITH_CONTAINER`
- `MISSING_BITRATE_METADATA`
- `MEDIA_TYPE_UNKNOWN_CONSERVATIVE_CAP`
- `SOURCE_UNPROBEABLE_REJECT`

Phase 04 emits only reasons it can decide from the Phase 03 source facts and
effective policy. Filter-driven encode reasons are defined for the contract
but remain unreached until the encoding model phase adds those inputs.

## Preserved Current Behavior Captured

The new tests characterize current route behavior from Phase 01 and the
PowerShell route-selection unit coverage:

- compatible H.264 under bitrate and height caps copies video and remuxes the
  current output container path
- TV/movie H.264 over the applicable direct-copy bitrate cap routes to encode
- HEVC over the direct-copy bitrate cap routes to encode
- low-bitrate MPEG2 remains an encode case because the codec is not direct-copy
  safe
- size-over-threshold but Plex-compatible HEVC remains a soft/advisory remux
  case under the current `plex_direct_stream` and `compatibility_advisory`
  defaults
- unknown media type applies the most conservative movie/TV caps and emits
  `MEDIA_TYPE_UNKNOWN_CONSERVATIVE_CAP`
- missing bitrate metadata emits `MISSING_BITRATE_METADATA` instead of
  crashing or silently inventing a bitrate

## Cross-Constraint Modeling

Phase 04 includes per-stream container compatibility modeling only where the
source facts already expose enough information:

- MP4-incompatible audio streams become `transcode` stream actions and emit
  `AUDIO_CODEC_INCOMPATIBLE_WITH_CONTAINER` plus
  `AUDIO_TRANSCODE_REQUIRED`
- MP4-incompatible image subtitles become `burn` stream actions and emit
  `SUBTITLE_FORMAT_INCOMPATIBLE_WITH_CONTAINER` plus
  `SUBTITLE_BURN_IN_REQUIRES_ENCODE`
- MP4-incompatible text subtitles become `convert` stream actions

This is still a planning contract. The actual subtitle/audio command behavior
remains PowerShell-owned until later scoped phases.

## Production Boundary

Existing production routing still lives in PowerShell:

- `engine/decide/routing.ps1`
- `engine/process/pipeline_processing.ps1`
- `Pipeline/MediaPipeline/remux.ps1`
- `Pipeline/MediaPipeline/encode.ps1`

Phase 04 does not replace `Resolve-InitialMediaRoutePlan`,
`Resolve-MediaRouteBySize`, `Resolve-RemuxCodecRoutePlan`, `Do-Remux`, or
`Do-Encode`. Later migration needs parity tests and operator review before any
runtime route path changes.

## Accepted Production Replacement Gate

Before Python decisions can replace `Resolve-InitialMediaRoutePlan` in
production:

- Build a golden parity harness that feeds the same source facts, route
  settings, and policy hints into current PowerShell routing and the Python
  decision engine.
- Compare normalized route output, video action, legacy reason code, estimated
  bitrate, route size threshold, direct-copy bitrate cap, size-over and
  bitrate-over flags, remux-safe fallback result, and hard/soft/advisory
  classification.
- Cover movie, TV, and unknown media type; every `RouteThresholdMode`; the main
  `RoutingProfile` values; H.264 under cap, over cap, and over height; HEVC
  remux-safe and over cap; incompatible codecs; missing duration/bitrate;
  forced/preferred remux/encode; allowed-codec policy; max-resolution policy;
  remux codec fallback; GPU safe retry; and CPU fallback.
- Run a shadow mode before cutover where Python decisions are computed beside
  PowerShell decisions but not acted on, with divergences logged as structured
  evidence.
- Require zero unexplained divergences across the golden matrix. Any intended
  divergence must be documented and operator-approved.
- Rerun representative real-media validation for the touched media-policy
  surface before promoting the production route switch.

## Tests Added

New test file:

- `tests/decide/test_processing_decision.py`

Coverage:

- required reason framework availability
- legacy current-key mapping into abstract effective policy
- Phase 03 fixture decisions for core copy/remux/encode outcomes
- advisory size-over-threshold behavior
- unknown media type conservative caps
- rejected/unprobeable source behavior
- MP4 audio/subtitle container cross-constraints

## Validation Notes

Passed:

- `DesktopApp/Runtime/Python/python.exe -m unittest tests.decide.test_processing_decision`
- `DesktopApp/Runtime/Python/python.exe -m unittest tests.contract.test_source_media_contract`
- `DesktopApp/Runtime/Python/python.exe -m unittest discover -s tests\contract -p "test_*.py"`
- `DesktopApp/Runtime/Python/python.exe -m unittest discover -s tests -p "test_*.py"`
- `Pipeline/PowerShell-7.6.0-win-x64/pwsh.exe -NoProfile -ExecutionPolicy Bypass -File Pipeline/Tests/Unit/Invoke-MediaRouteSelectionChecks.ps1`

Postflight guardrail:

- `DesktopApp/Runtime/Python/python.exe scripts/dev/ai_guardrail.py postflight --json`
  remained red in the same required categories as preflight:
  `summary-freshness` and `risky-file-registry`.
- Project index, pipeline map, lifecycle map, config schema, stage schema,
  active doc references, architecture guardrails, naming lint, god-file guard,
  and marketecture guard passed inside postflight.

## Risks And Follow-Ups

- This is a new pure decision surface, not the production route engine yet.
  PowerShell still owns execution and may still change route evidence during
  remux codec fallback or CPU fallback.
- Real runtime migration needs the accepted parity gate above before
  PowerShell becomes a faithful executor of Python decisions.
- The MP4 audio/subtitle actions are planning signals only. They must not be
  treated as evidence that runtime command generation has changed.
- The pre-existing guardrail baseline remained red before this phase because
  of summary freshness and risky-file-registry drift.

## Next Phase Readiness

Phase 05 should add a versioned `PresetV2` wrapper for persisted/user-facing
policy and adapter tests proving legacy config or `PresetV2` produce the same
`EffectiveDecisionPolicy` values consumed by Phase 04. Production routing
should not be switched until the accepted parity gate and later
planner/executor phases are complete.
