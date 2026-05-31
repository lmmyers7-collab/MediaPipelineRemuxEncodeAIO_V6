# Phase 12 Developer Guide

Last updated: 2026-05-31

This guide records the developer-facing contract boundaries for the
HandBrake/remux rewrite after Phase 12. It is not a runtime cutover document.
Production execution remains on the legacy PowerShell path until a separate
operator-approved high-risk phase changes that.

## Current Architecture

The intended long-term ownership is:

```text
PowerShell probe JSON
-> Python SourceMediaInfo
-> Python EffectiveDecisionPolicy
-> Python ProcessingDecision
-> Python abstract PipelinePlan
-> PowerShell plan executor builds concrete commands from existing builders
```

Python decides what should happen. PowerShell builds and runs the concrete
FFmpeg/mkvmerge/robocopy commands. Do not port FFmpeg argument construction
into Python, and do not let PowerShell silently re-derive routing after Python
cutover without feeding the reason back into the plan record.

## Contract Map

| Area | Files | Purpose |
| --- | --- | --- |
| Source facts | `app/contracts/source_media.py`, `app/contracts/source_media_adapters.py`, `app/contracts/source_media_values.py`, `app/contracts/source_media_streams.py`, `app/contracts/source_media_derived.py` | Normalize read-only media facts from ffprobe-style JSON and existing stage results. |
| Preset policy | `app/config/preset_policy.py`, `app/config/preset_encoding_sections.py`, `app/config/preset_migration.py` | Versioned `PresetV2` view, legacy adapters, and section-labelled validation. |
| Decision engine | `app/decide/processing_decision.py`, `app/decide/routing.py`, `app/decide/routing_facts.py`, `app/decide/routing_outputs.py`, `app/decide/encoding_rules.py`, `app/decide/stream_actions.py` | Pure Python per-stream copy/remux/encode decision model. |
| Plan contract | `app/contracts/pipeline_plan.py`, `app/orchestration/planner.py` | Abstract non-executable `pipeline_plan.v1` dry-run preview. |
| Verification | `app/contracts/verification.py` | Output Size Check and verification/publish guard result model. |
| Rollout | `app/config/rollout.py` | Read-only rollout resolver and planner comparison evidence. |
| PowerShell dry-run executor | `engine/process/pipeline_plan_executor.ps1`, `engine/process/pipeline_plan_executor/validation.ps1` | Validates `pipeline_plan.v1` and builds non-executing command previews from existing builders. |
| Regression coverage | `tests/contract/`, `tests/decide/`, `tests/orchestration/`, `tests/integration/`, `Pipeline/Tests/Unit/Invoke-PipelinePlanExecutorChecks.ps1` | Metadata-only contract/decision/planner and dry-run command-shape coverage. |

## SourceMediaInfo

`SourceMediaInfo` is Python-owned and normalized from PowerShell probe JSON.
It is read-only source evidence, not desired output policy.

Important model groups:

- `SourceContainerInfo`: path identity, size, container format, duration,
  overall bitrate, title, and media type.
- `SourceVideoStream`: codec, profile, level, pixel format, dimensions,
  frame/aspect details, scan type, HDR markers, bit depth, bitrate, and stream
  index.
- `SourceAudioStream`: codec, channels, layout, language, bitrate,
  default/forced flags, title, and passthrough annotations.
- `SourceSubtitleStream`: codec, language, text/image classification, flags,
  and candidate annotations for copy/convert/burn/drop.
- `SourceDerivedFacts`: compatibility annotations, buckets, and unknown
  metadata visibility.

Adapters:

- `source_media_from_ffprobe(...)` consumes raw ffprobe-like JSON.
- `source_media_from_probe_result(...)` consumes existing `ProbeResult` /
  `StreamSummary` stage output.
- `source_media_from_mapping(...)` dispatches supported shapes.

These adapters do not choose copy/remux/encode. They expose facts and
annotations that the decision engine consumes.

## PresetV2 And Effective Policy

`PresetV2` is the versioned user-facing policy wrapper. It is not the same as
`EffectiveDecisionPolicy`.

Current flow:

```text
legacy flat config or PresetV2
-> adapter
-> EffectiveDecisionPolicy
-> ProcessingDecision
```

`PresetV2` sections:

- identity: `version`, `name`, `impactLevel`, `presetCategory`,
  `processingStrategy`, `compatibilityTarget`;
- `routing`;
- `dimensions`;
- `filters`;
- `video`;
- `audio`;
- `subtitles`;
- `container`;
- `guards.size`;
- `verification`;
- `publish`;
- `advanced`.

Legacy compatibility rules:

- `PRESET_POLICY_WRITE_FORMAT` remains `legacy`.
- Current PSD1/JSON keys remain compatibility keys.
- Unknown legacy keys are preserved under `advanced.legacyPassthrough`.
- Source facts are rejected from persisted presets.
- `preset_v2_from_legacy_config(...)` adapts current flat config into
  `PresetV2`.
- v2 and legacy shapes both project to `EffectiveDecisionPolicy`.

Enforcement expansion:

- Route enforcement controls how source-size, bitrate, codec, dimensions, and
  compatibility rules affect copy/remux versus encode decisions.
- `SizeGuardMode` maps to explicit Output Size Check actions:
  `off -> disabled`, `advisory -> warn_only`, and `strict -> fail_job`.
- v2 can model `block_publish`, but production PowerShell does not act on that
  path yet.

## Library Profiles And Settings Overrides

The richer HandBrake-inspired settings model must stay subordinate to the
existing library/profile policy model until a separate settings cutover is
approved. Backend normalization owns inheritance and compatibility; the WebView
only renders and stages backend-owned profile data.

Accepted library-profile rules:

- Built-in `movies` and `tv` profiles remain synthesized when missing and
  cannot be disabled.
- A custom library with a missing or blank `output_path` inherits `Outsource`
  by backend default. A custom library with an explicit `output_path` keeps that
  path, even if it currently equals `Outsource`.
- Custom libraries do not inherit `source_path` by default. Enabled custom
  libraries still require an explicit source root.
- Missing per-library override fields inherit global settings. Explicit
  library overrides beat globals even when the explicit value currently equals
  the global value.
- Legacy `editor_overrides` and `media_overrides` remain accepted and coerced
  into nested `overrides` until an approved cleanup phase removes that
  compatibility path.
- Unknown or unsupported library override keys must fail validation before
  runtime. Do not rely on PowerShell runtime filtering as the only guard; Python
  preview/save validation, PowerShell schema validation, and runtime allowed-key
  filtering need parity tests.

Promotion must stay profile-aligned during the transition:

- Normalize `LibraryProfiles` first.
- Generate profile-derived final-library promotion rules for enabled profiles
  with `promotion_enabled` and `promotion_destination`.
- Merge existing `FinalLibraryPromotionRules` only as fallback compatibility
  for uncovered roots.
- Do not let stale legacy rules override the current profile output root or
  promotion destination.

Runtime precedence remains:

```text
library profile < show overrides < folder policy < per-file override
```

`library_effective_settings` is library-only evidence: global defaults plus
library profile overrides. It does not include show, folder, or per-file
overrides. Do not rename this field during transition. If later work needs full
job-level effective settings, add a separate field such as
`runtime_effective_settings` and test that it reflects every precedence layer.

## ProcessingDecision

`ProcessingDecision` is the Python-owned decision contract. It records
per-stream actions first and a derived summary second.

Key fields include:

- `streamActions`;
- `routeSummary`;
- `routeReasons`;
- `sourceFactsUsed`;
- `hardRulesTriggered`;
- `softTargetsExceeded`;
- `advisoryWarnings`;
- `plannedOutputSummary`;
- `plannedEncodeOutput`;
- `verificationRequirements`;
- `verificationGuards`;
- `verificationResult`;
- `publishRequirements`;
- `effectiveSettings`;
- `legacyRoute`;
- `legacyReasonCode`.

Derived summary rules:

- `REJECT` if video is rejected.
- `UNKNOWN` if video or container action is unknown.
- `ENCODE` if video is encoded or subtitle burn-in is present.
- `REMUX` if container changes/remuxes, audio transcodes/drops, or subtitles
  convert/drop.
- `COPY` only when every stream copies and the container is kept.

Do not write UI or PowerShell code that treats `routeSummary` as the only
decision record.

## Route Reason Codes

The decision contract currently defines these route reasons:

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

Additions need tests that prove legacy behavior is preserved or that any
intentional divergence is operator-approved.

## PipelinePlan And 07B Boundary

`pipeline_plan.v1` is abstract and dry-run-only. It describes intent; it does
not contain executable FFmpeg argument lists.

Important fields:

- source identity;
- route summary and reasons;
- output proposal;
- per-stream actions;
- verification requirements and result;
- publish requirements;
- runtime fallback branches;
- command preview steps;
- effective preset and decision snapshots.

`CommandPlan` must remain non-executable from the Settings preview:

- `dryRunOnly=true`;
- `canExecute=false`;
- no native tool execution;
- no filesystem writes.

Phase 07B validates serialized plans and builds dry-run command records in
PowerShell. It reuses existing encode builders for encode previews and models
the current remux command shape for dry-run parity. It intentionally does not
switch production callers.

Current 07B limitations:

- subtitle burn-in is rejected because no approved existing builder is exposed
  in this path;
- non-MKV concrete parity remains unsupported;
- stream indexes are dry-run source indexes, not a substitute for real-media
  stream-ID validation.

## Guards And Pending Publish

`app/contracts/verification.py` separates:

- `VerificationGuard`;
- `OutputSizeCheck`;
- `VerificationResult`;
- advisory warnings;
- failures;
- publish blockers.

Output Size Check actions:

| Action | Runtime meaning today |
| --- | --- |
| `disabled` | No output-growth evaluation. |
| `warn_only` | Advisory only. |
| `block_publish` | Dry-run model for parking through pending publish; not production behavior yet. |
| `fail_job` | Current strict behavior: fail before publish. |

If `block_publish` is later promoted, it must map to the existing
pending-publish park/drain flow. Do not invent a separate publish bypass. The
pending-publish manifest and drain lifecycle remain high-risk and backend-owned.

## Runtime Fallbacks

Phase 01 found two current mid-execution route changes:

- remux codec recheck can redirect remux to encode;
- NVENC hardware encode can fall back to CPU encode.

The plan contract models these as explicit fallback branches:

- `remux-codec-recheck`;
- `nvenc-cpu-fallback`.

Future production cutover should treat them as bounded re-plan back-edges or
typed executor outcomes. Do not leave them as silent PowerShell decisions after
Python becomes the decision authority.

## UI Data Flow

Settings preview flow:

```text
operator selects source facts and stages Settings patch
-> WebView posts explicit SourceMediaInfo JSON to backend preview route
-> backend builds PresetV2/effective policy and ProcessingDecision
-> backend returns dry-run PipelinePlan
-> WebView renders plan evidence with Predicted pending cutover label
```

The WebView must not duplicate routing logic. It may render backend evidence,
labels, and local form state. It must not own media policy, queue mutation,
settings persistence, publish/drain, rename apply, or filesystem mutation.

## Test Fixture Strategy

The normal automated matrix is metadata-only:

- JSON fixtures under `tests/fixtures/source_media/`;
- contract tests for source normalization, presets, verification, and rollout;
- decision tests for copy/remux/encode outcomes;
- planner tests for `pipeline_plan.v1` shape;
- integration tests for legacy/v2 parity and route matrix cases;
- Phase 07B PowerShell dry-run command-shape checks.

Settings/library synchronization tests should also cover backend default
inheritance for custom-library `output_path`, explicit-equals-global override
preservation, legacy override coercion, profile-derived promotion rule
precedence over stale fallback rules, and the distinction between
`library_effective_settings` and any future runtime/full-job effective-settings
field.

No normal test should require large binary fixtures, external downloads, long
encodes, or real media. Real-media validation remains operator-run and is
required before high-risk production behavior changes.

## Rollout And Ownership Cutover

`resolve_planner_rollout_config(...)` defaults to:

- `stage: legacy`;
- `executionAuthority: legacy_powershell`;
- `newPlannerExecutionEnabled: false`;
- `dryRunOnly: true`;
- `presetWriteFormat: legacy`.

Recognized rollout stages include:

- `legacy`;
- `shadow`;
- `selected_jobs`;
- `ui_old_backend`;
- `new_planner_default`;
- `deprecation_cleanup`.

The resolver can report a Python planner cutover only when stage, planner
enablement, and explicit cutover approval keys are all present. No production
caller consumes that state in Phase 12.

Before ownership cutover:

- zero unexplained route divergences across the golden matrix;
- operator-approved intentional divergences;
- live old/new shadow comparison evidence;
- Phase 07B concrete command parity evidence;
- Local API/WebView operator-surface proof;
- relevant release gate checks;
- representative real-media validation for remux, encode/size, subtitle,
  audio, pending-publish/final-placement, and rollback behavior.

## Maintenance Rules

- Keep new Python code under `app/<domain>/<role>.py`.
- Keep new PowerShell code under `engine/<domain>/<role>.ps1`.
- Do not add new flat `facade_*.py`, `service_*.py`, or
  `command_payloads_*.py` files.
- Do not add new dotted-suffix PowerShell modules under `Pipeline/Modules/`.
- After source edits, refresh summaries and generated project context.
- For docs-only updates in this subtree, run active doc reference checks and
  guardrail postflight.
- Do not remove compatibility adapters or legacy labels until a separate
  cleanup phase is approved after production cutover.
