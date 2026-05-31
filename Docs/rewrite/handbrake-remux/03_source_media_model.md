# Phase 03 Source Media Model and Fixture Strategy

Date: 2026-05-30

Scope: additive Python-owned source-facts model, metadata fixtures, and unit
tests. This phase does not change routing decisions, queue behavior, settings
persistence, UI, FFmpeg/remux command generation, subtitle/audio execution,
source/scratch/output movement, publish/drain behavior, cleanup, command
journal behavior, or Tauri lifecycle behavior.

## Phase Confirmations

- Approved docs and tracker location: `Docs/rewrite/handbrake-remux/`
- Edit domain for this phase: Python contracts under `app/`, Python tests and
  fixtures under `tests/`, generated summaries/index context, and this approved
  rewrite docs/tracker subtree
- High-risk areas touched: yes, conceptually. The model records source media
  identity and source-derived facts, and it lives in the contract layer. No
  high-risk runtime implementation was changed.

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
- `C:/Users/lmmye/Downloads/handbrake_remux_rewrite_plan/13_CODEX_MASTER_PROMPT.md`
- `C:/Users/lmmye/Downloads/handbrake_remux_rewrite_plan/00_EXECUTION_ORDER.md`
- `C:/Users/lmmye/Downloads/handbrake_remux_rewrite_plan/03_SOURCE_MEDIA_MODEL_AND_FIXTURES.md`

## Current Probe Metadata Located

Current probing remains PowerShell-owned:

- `engine/probe/media_probe.ps1` owns `Get-SourceMediaRouteProfile`, which
  calls ffprobe JSON and returns `source_media_profile.v1` fields:
  `probe_ok`, `probe_error`, `video_codec`, `width`, `height`, `is_hdr`,
  `color_transfer`, `duration_seconds`, `container_bitrate_mbps`,
  `estimated_bitrate_mbps`, and `size_bytes`.
- `engine/probe/stage.ps1` owns `Invoke-ProbeStage`, which wraps that profile
  and adds stage-result fields including `container`, `bitrate_bps`, and a
  simplified `streams` list.
- `app/contracts/stages.py` already models that stage result with
  `ProbeResult` and `StreamSummary`.

Phase 03 did not edit those PowerShell files. The new Python adapter consumes
their existing shape.

## SourceMediaInfo Contract

New files:

- `app/contracts/source_media.py`
- `app/contracts/source_media_adapters.py`
- `app/contracts/source_media_values.py`
- `app/contracts/source_media_streams.py`
- `app/contracts/source_media_derived.py`

The normalized model separates source facts from future output settings and
route decisions:

- `SourceContainerInfo`: path/source id, file size, container format, duration,
  overall bitrate, title, and media type.
- `SourceVideoStream`: codec, profile, level, pixel format, storage and display
  dimensions, aspect ratio, frame rate, scan type, HDR markers, bit depth,
  bitrate, and stream index.
- `SourceAudioStream`: stream index, codec, channels, layout, language,
  bitrate, default/forced flags, title, and policy-annotation passthrough
  status.
- `SourceSubtitleStream`: stream index, codec, language, flags, text/image
  classification, and read-only candidate flags for passthrough, convert, burn,
  and drop.
- `SourceDerivedFacts`: dimension bucket, bitrate bucket, direct-play codec
  annotation, audio passthrough annotation, subtitle candidate stream indexes,
  remux-compatibility annotation, and visible unknown-metadata fields.

Adapters in `source_media_adapters.py`:

- `source_media_from_ffprobe(...)` consumes raw ffprobe-like JSON metadata.
- `source_media_from_probe_result(...)` consumes the existing `ProbeResult` /
  `StreamSummary` shape from `app/contracts/stages.py`.
- `source_media_from_mapping(...)` dispatches between those supported shapes.

Helper ownership:

- `source_media_values.py`: scalar coercion, codec/text normalization, frame
  rate/aspect parsing, and media-type normalization.
- `source_media_streams.py`: ffprobe and stream-summary builders for video,
  audio, and subtitle stream facts.
- `source_media_derived.py`: read-only policy annotations and derived buckets.

These adapters do not choose `copy`, `remux`, `encode`, `reject`, or per-stream
actions. Policy-derived booleans are annotations only and remain intentionally
separate from Phase 04 decision logic.

## Fixture Strategy

Fixture files live under `tests/fixtures/source_media/` and contain small JSON
metadata only, not media binaries:

- `tv_h264_1080p_12mbps_mkv.json`
- `tv_h264_1080p_24mbps_mkv.json`
- `movie_h264_1080p_30mbps_mkv.json`
- `movie_h264_1080p_45mbps_mkv.json`
- `movie_hevc_4k_hdr_high_bitrate_mkv.json`
- `avi_mpeg2_480p.json`
- `source_with_image_subtitles.json`
- `interlaced_source.json`
- `multi_audio_tracks.json`
- `unknown_bitrate_source.json`

These fixtures cover container facts, H.264 and HEVC, 480p/720p/1080p/4K,
HDR, high bitrate, image subtitles, interlacing, multi-audio sources, and
missing bitrate/size metadata.

## Tests Added

New test file: `tests/contract/test_source_media_contract.py`

Coverage:

- raw ffprobe fixture normalization for container, video, audio, subtitle,
  duration, dimensions, frame rate, bit depth, flags, and title;
- all ten Phase 03 fixture cases;
- image subtitle and interlaced-video visibility;
- policy annotations without route decisions;
- missing bitrate/size metadata staying visible and conservative;
- existing `ProbeResult`/`StreamSummary` adapter compatibility;
- strict model rejection of unexpected fields.

## Acceptance Notes

- Source facts can now be represented independently from output settings.
- Existing probe-stage metadata can be adapted without changing PowerShell.
- Fixtures are JSON metadata only and require no downloads or real media files.
- Existing behavior remains unchanged because no runtime caller was switched to
  the new model.

## Risks And Follow-Ups

- The new source facts model is not yet connected to routing. That is correct
  for Phase 03; Phase 04 owns the pure decision engine.
- `already_remux_compatible` is a compatibility annotation, not a route result.
  Phase 04 must still define authoritative per-stream decisions.
- Current raw probe output is less rich than the fixture model for fields such
  as codec profile, display dimensions, bit depth, and scan type. Raw ffprobe
  JSON can populate these fields, while the existing `ProbeResult` adapter only
  maps fields that the stage already exposes.
- Baseline guardrails were red before this phase because of pre-existing
  summary freshness and risky-file-registry drift. Postflight should be
  compared against that baseline.
- Adapter helper code is now split before Phase 04, so no new source-media
  file is above the god-file warning threshold.

## Next Phase Readiness

Phase 04 can consume `SourceMediaInfo` as an input type for a pure decision
engine, but it should not replace PowerShell production routing until parity
fixtures and behavior-preservation tests are in place.
