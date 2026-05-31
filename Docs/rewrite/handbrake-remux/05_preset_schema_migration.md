# Phase 05 Preset Schema Migration

Date: 2026-05-30

Scope: additive Python-owned `PresetV2` schema, legacy-to-v2 adapter, v2-to
`EffectiveDecisionPolicy` adapter, focused contract tests, and tracker update.
This phase does not rewrite the UI, save v2 config to disk, change current
legacy config persistence, replace PowerShell route execution, alter
FFmpeg/remux commands, or change default codecs/thresholds.

## Phase Confirmations

- Approved docs and tracker location: `Docs/rewrite/handbrake-remux/`
- Edit domain for this phase: Python config/schema adapter under `app/`,
  Python contract tests under `tests/`, generated summaries/index context, and
  this approved rewrite docs/tracker subtree
- High-risk areas touched: yes. Settings schema and migration mapping are
  AGENTS.md high-risk areas. The implementation is additive and read-only from
  the production runtime perspective; legacy config support and legacy write
  posture are preserved.

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
- `Docs/rewrite/handbrake-remux/04_decision_engine_contract.md`
- `C:/Users/lmmye/Downloads/handbrake_remux_rewrite_plan/13_CODEX_MASTER_PROMPT.md`
- `C:/Users/lmmye/Downloads/handbrake_remux_rewrite_plan/00_EXECUTION_ORDER.md`
- `C:/Users/lmmye/Downloads/handbrake_remux_rewrite_plan/05_PRESET_POLICY_SCHEMA_AND_MIGRATION.md`

## Implemented Schema Surface

New files:

- `app/config/preset_policy.py`: `PresetV2` and section schemas
- `app/config/preset_migration.py`: legacy and v2 adapters

The new `PresetV2` schema is a user-facing persisted-policy wrapper with
sectioned HandBrake-inspired names:

- top-level preset identity: `version`, `name`, `impactLevel`,
  `presetCategory`, `processingStrategy`, and `compatibilityTarget`
- `routing`
- `dimensions`
- `filters`
- `video`
- `audio`
- `subtitles`
- `container`
- `guards.size`
- `verification`
- `publish`
- `advanced`

`PresetV2` is intentionally separate from Phase 04
`EffectiveDecisionPolicy`. The accepted flow remains:

```text
legacy flat config or PresetV2
-> adapter
-> EffectiveDecisionPolicy
-> ProcessingDecision
```

`EffectiveDecisionPolicy` is not stored as the preset schema.

## Migration And Compatibility

The adapter `preset_v2_from_legacy_config(...)` in
`app/config/preset_migration.py` reads current flat config values using
`app.contracts.config.Config` defaults and maps them into `PresetV2`.

Key mappings:

| Legacy key | PresetV2 destination |
| --- | --- |
| `RoutingProfile` | `processingStrategy` |
| `RouteThresholdMode` | `routing.enforcementMode` |
| `MovieRouteMaxVideoBitrateMbps` | `routing.directCopyMaxBitrate.movieMbps` |
| `TVRouteMaxVideoBitrateMbps` | `routing.directCopyMaxBitrate.tvMbps` |
| `AllowH264RemuxIfPlexCompatible` | `routing.allowH264CompatibleDirectCopy` |
| `H264RemuxMaxBitrateMbps` | `routing.h264DirectCopyMaxBitrateMbps` |
| `H264RemuxMaxHeight` | `routing.h264DirectCopyMaxHeight` and `dimensions.h264DirectCopyMaxHeight` |
| `RemuxSafeVideoCodecs` | `routing.directCopyVideoCodecAllowlist` |
| `VideoCodec` | `video.codec` |
| `VideoPreset` | `video.encoderSpeedPreset` |
| `VideoQuality` | `video.qualityTarget` |
| `EncodeTuningPreset` | `video.encoderQualityPreset` |
| `EncodeLadder` | `video.targetSelection` |
| `OutputContainer` | `container.format` |
| `SizeGuardMode` | `guards.size.mode` and `guards.size.onExceeded` |
| `MaxEncodeGrowthPercent` | `guards.size.qualityEncodeGrowthTolerancePct` |
| `CompatibilityEncodeGrowthPercent` | `guards.size.compatibilityEncodeGrowthTolerancePct` |
| `EncodeThresholdGB` | `guards.size.movieRouteSizeLimitGb` |
| `TVEncodeThresholdGB` | `guards.size.tvRouteSizeLimitGb` |
| audio/subtitle/verification/publish/advanced keys | matching section fields |

The route-size fields intentionally use `movieRouteSizeLimitGb` and
`tvRouteSizeLimitGb`, not target-output-size names, because Phase 02 and the
operator accepted that these legacy fields are source route limits in current
behavior.

Until the later rollout/cutover phase, `PRESET_POLICY_WRITE_FORMAT` is
`legacy`. Phase 05 reads legacy or v2 policy and projects both into the
decision engine, but it does not save v2 config to disk.

Unknown future v2 fields are allowed and round-trip through model dumping.
Unknown legacy fields are preserved under `advanced.legacyPassthrough` in the
adapter output.

Source facts are rejected from persisted presets via explicit validation:
source metadata belongs in `SourceMediaInfo`, not editable preset policy.

## Validation Behavior

`preset_v2_validation_issues(...)` returns section-labelled validation issues
so callers can point errors at user-facing sections such as Routing, Video,
Container, Subtitles, Verification, Publish, or Advanced.

The model validates at least these Phase 05 sections:

- routing
- dimensions
- filters
- video
- audio
- subtitles
- container
- guards
- verification
- publish
- advanced

Subtitle cross-field validation preserves the current safety invariants:
dropping TX3G/BDPGS after conversion requires conversion to be enabled, and
BDPGS OCR requires a tool path.

## Tests Added

New test file: `tests/contract/test_preset_policy_contract.py`

Coverage:

- legacy flat config values migrate to `PresetV2`
- legacy migration preserves unknown legacy keys under
  `advanced.legacyPassthrough`
- migrated legacy config and direct Phase 04 legacy-key mapping produce the
  same `EffectiveDecisionPolicy`
- v2 configs validate and feed `build_processing_decision(...)`
- one adapter reads both legacy and v2 shapes
- invalid values produce user-facing section labels
- persisted presets reject source facts
- unknown future v2 fields round-trip
- write posture remains legacy until rollout

## Acceptance Notes

- Legacy configs still load through `Config` and can be adapted into v2 without
  removing or renaming legacy keys.
- `PresetV2` can feed the Phase 04 decision engine through
  `EffectiveDecisionPolicy`.
- No UI code, PowerShell execution code, FFmpeg argument builder, subtitle
  executor, audio executor, publish/drain, queue behavior, command journal, or
  settings save route was changed.
- Default codec and threshold values remain the current repo defaults.

## Risks And Follow-Ups

- `PresetV2` is not yet exposed through the Local API or WebView. Phase 08
  owns UI work.
- PowerShell profiles still use the flat legacy PSD1 shape. This is deliberate
  for rollback safety until Phase 11.
- Full cross-language config/profile parity should be revisited before any v2
  persistence or production routing cutover.
- Because this phase touches settings schema and migration mapping
  conceptually, the operator should treat completion as code/test evidence,
  not as approval to cut over saved config format.

## Next Phase Readiness

Phase 06 can build the HandBrake-like encoding model on top of `PresetV2`
without changing current runtime command generation. Phase 06 should keep codec
choice and advanced encoder semantics policy-driven and tested before any
production behavior changes.
