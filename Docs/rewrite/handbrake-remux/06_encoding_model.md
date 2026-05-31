# Phase 06 HandBrake-Style Encoding Model

Date: 2026-05-30

Scope: additive Python-owned encoding policy model, capability validation,
decision-engine route triggers, planned encode-output DTOs, focused tests, and
tracker update. This phase does not change PowerShell FFmpeg/remux command
generation, runtime route execution, WebView UI, settings persistence, queue
behavior, subtitle/audio execution, source/scratch/output movement,
publish/drain behavior, command journal behavior, or Tauri lifecycle behavior.

## Phase Confirmations

- Approved docs and tracker location: `Docs/rewrite/handbrake-remux/`
- Edit domain for this phase: Python config/decision model under `app/`,
  Python tests under `tests/`, generated summaries/index context, and this
  approved rewrite docs/tracker subtree
- High-risk areas touched: yes. Settings schema/migration and media-policy
  decision modeling are AGENTS.md high-risk areas. The implementation is
  additive and not wired into production execution.

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
- `Docs/rewrite/handbrake-remux/05_preset_schema_migration.md`
- `C:/Users/lmmye/Downloads/handbrake_remux_rewrite_plan/13_CODEX_MASTER_PROMPT.md`
- `C:/Users/lmmye/Downloads/handbrake_remux_rewrite_plan/00_EXECUTION_ORDER.md`
- `C:/Users/lmmye/Downloads/handbrake_remux_rewrite_plan/06_HANDBRAKE_STYLE_ENCODING_MODEL.md`

## Implemented Encoding Model

`PresetV2` now represents HandBrake-style encoding sections while preserving
legacy compatibility. The section models live in
`app/config/preset_encoding_sections.py` and are re-exported through
`app/config/preset_policy.py`:

- Dimensions: resolution limit, custom max height, scaling policy, aspect
  policy, crop mode, pixel aspect mode, and existing direct-copy height caps.
- Filters: detelecine, deinterlace, denoise, sharpen, deblock, chroma smooth,
  colorspace, and existing subtitle-text cleanup settings.
- Video: codec family, encoder backend, speed preset, target mode, quality,
  target/max bitrate, framerate mode, profile, level, tune, and existing
  legacy encoder/tuning/ladder fields.
- Audio: passthrough default/profile, compatible codecs, fallback transcode
  codec/bitrate/channels, force-transcode, and MP4 copy compatibility.
- Subtitles: keep/drop/convert-preferred/burn-forced mode, preferred SRT
  generation, burn-in flag, language filter mode, and existing TX3G/BDPGS/ASS
  conversion settings.
- Container: MKV/MP4 format, force remux, remux-when-possible, and MP4 stream
  compatibility posture.

`app/config/encoding_capabilities.py` adds `EncodingCapabilityFacts` and
`validate_encoding_capabilities(...)`. Capability facts are supplied data from
the execution layer; Python does not probe FFmpeg or duplicate command support.
Unsupported requested codecs, backends, filters, audio transcode codecs,
subtitle converters, or containers return section-labelled safe errors.

## Decision Engine Changes

`EffectiveDecisionPolicy` now carries the Phase 06 encoding-model inputs used
by the pure Python decision engine:

- video filter/crop settings force `video=encode` with
  `FILTERS_ENABLED_ENCODE_REQUIRED`;
- downscale requests from `resolutionLimit` force `video=encode` with
  `RESOLUTION_EXCEEDS_LIMIT`;
- subtitle forced burn-in forces `video=encode` with
  `SUBTITLE_BURN_IN_REQUIRES_ENCODE`;
- audio passthrough/channel policy can force per-stream audio `transcode`
  without forcing video encode;
- existing incompatible codec, bitrate cap, MP4 audio/subtitle compatibility,
  and source-probe rejection behavior remains covered.

`ProcessingDecision` now includes `plannedEncodeOutput`, a structured read-only
summary of planned video encode settings, audio transcode streams, subtitle
copy/convert/burn/drop streams, and container. This is planning evidence only;
it does not build FFmpeg arguments.

## Acceptance Notes

- Existing defaults still route through legacy config or `PresetV2` into
  `EffectiveDecisionPolicy`.
- Copy/remux remains first-class; audio-only transcode and subtitle conversion
  do not imply video encode.
- Actual FFmpeg command generation and PowerShell execution remain unchanged.
- Encoder capability validation is data-driven and fails safely when supplied
  facts do not advertise a requested feature.

## Validation Notes

Passed:

- `DesktopApp/Runtime/Python/python.exe -m unittest tests.contract.test_preset_policy_contract`
- `DesktopApp/Runtime/Python/python.exe -m unittest tests.decide.test_processing_decision`
- `DesktopApp/Runtime/Python/python.exe -m unittest discover -s tests\contract -p "test_*.py"`
- `DesktopApp/Runtime/Python/python.exe -m unittest discover -s tests -p "test_*.py"`
- `DesktopApp/Runtime/Python/python.exe -m unittest DesktopApp.tests.test_app_config_contract`
- `DesktopApp/Runtime/Python/python.exe scripts/dev/generate_project_index.py --check`
- `DesktopApp/Runtime/Python/python.exe scripts/dev/check_active_doc_references.py`
- `DesktopApp/Runtime/Python/python.exe scripts/dev/check_architecture_guardrails.py`
- `DesktopApp/Runtime/Python/python.exe scripts/lint-naming.py`
- `DesktopApp/Runtime/Python/python.exe scripts/dev/check_godfiles.py`

Postflight guardrail:

- `DesktopApp/Runtime/Python/python.exe scripts/dev/ai_guardrail.py postflight --json`
  remained red in the same required categories as preflight:
  `summary-freshness` and `risky-file-registry`.
- Project index, pipeline map, lifecycle map, config schema, stage schema,
  active doc references, architecture guardrails, naming lint, god-file guard,
  and marketecture guard passed inside postflight.

## Risks And Follow-Ups

- This phase models encoding policy and decisions only. It is not production
  route replacement.
- Runtime execution still lives in PowerShell; Phase 07 and 07B must preserve
  the accepted parity gate before any production switch.
- Capability facts need a later execution-layer source before the Local API/UI
  can present live encoder support.
- Because this phase touches settings schema and media-policy modeling, the
  operator should treat completion as code/test evidence, not production
  approval for command behavior.

## Human Review Before Phase 07

- Accepted by operator on 2026-05-30: target modes are `auto`,
  `constant_quality`, `average_bitrate`, and `max_bitrate`.
- Accepted by operator on 2026-05-30: presets should control
  speed/compression effort and encoder family/backend choices, including
  NVENC `p1`-`p7` and x264 versus x265 selection. `tune` remains a separate
  content/behavior tune.
- Accepted by operator on 2026-05-30: advanced controls should stay hidden by
  default in the Phase 08 UI. This includes framerate mode, profile, level,
  tune, custom crop, pixel aspect, colorspace, raw legacy flags, CPU fallback
  settings, process priority/thread caps, muxer flags, and tool timeouts.

## Next Phase Readiness

Phase 07 can define the abstract `PipelinePlan` contract on top of
`SourceMediaInfo`, `PresetV2`, `EffectiveDecisionPolicy`, `ProcessingDecision`,
and `plannedEncodeOutput`. Phase 07 must remain a planner/dry-run contract and
must not switch production PowerShell execution without the accepted parity and
operator-review gates.
