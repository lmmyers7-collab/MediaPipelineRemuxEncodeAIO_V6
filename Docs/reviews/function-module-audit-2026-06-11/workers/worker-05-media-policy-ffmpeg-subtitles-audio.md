# Worker Review: worker-05-media-policy-ffmpeg-subtitles-audio

## Scope

Worker ID: `worker-05-media-policy-ffmpeg-subtitles-audio`

Assigned slice: media policy and engine behavior for probe/decide stages, FFmpeg/ffprobe command generation, remux versus encode routing, subtitle conversion/OCR/SRT behavior, audio passthrough/transcode/downmix behavior, and relevant `ops/pipeline/engine/` media modules.

Review mode: static, review-only audit. No code fixes, refactors, commits, runtime/media state changes, aggregate review edits, or generated-summary refreshes were performed. Summaries under `docs/generated/summaries/` were checked before opening assigned source files.

## Coverage Ledger

| File | Coverage | Result |
|---|---:|---|
| `ops/pipeline/engine/audio/audio.ps1` | Complete static source review | No finding |
| `ops/pipeline/engine/audio/audio/stream_decisions.ps1` | Complete static source review | No finding |
| `ops/pipeline/engine/decide/codec_policy.ps1` | Complete static source review | No finding |
| `ops/pipeline/engine/decide/encode_policy.ps1` | Complete static source review | W05-003 |
| `ops/pipeline/engine/decide/profile_selection.ps1` | Complete static source review | W05-001 |
| `ops/pipeline/engine/decide/route_plan.ps1` | Complete static source review | No finding |
| `ops/pipeline/engine/decide/routing.ps1` | Complete static source review | No finding |
| `ops/pipeline/engine/decide/show_overrides.ps1` | Complete static source review | No finding |
| `ops/pipeline/engine/decide/size_policy.ps1` | Complete static source review | W05-001 evidence |
| `ops/pipeline/engine/decide/stage.ps1` | Complete static source review | No finding |
| `ops/pipeline/engine/policy/folder_policy.ps1` | Complete static source review | W05-001 |
| `ops/pipeline/engine/probe/media_probe.ps1` | Complete static source review | No finding |
| `ops/pipeline/engine/probe/stage.ps1` | Complete static source review | No finding |
| `ops/pipeline/engine/subtitles/ass.ps1` | Complete static source review | No finding |
| `ops/pipeline/engine/subtitles/bdpgs.ps1` | Complete static source review | No finding |
| `ops/pipeline/engine/subtitles/builders.ps1` | Complete static source review | W05-002 |
| `ops/pipeline/engine/subtitles/builders/decisions.ps1` | Complete static source review | No finding |
| `ops/pipeline/engine/subtitles/common.ps1` | Complete static source review | No finding |
| `ops/pipeline/engine/subtitles/failure_records.ps1` | Complete static source review | No finding |
| `ops/pipeline/engine/subtitles/filtering.ps1` | Complete static source review | No finding |
| `ops/pipeline/engine/subtitles/language_policy.ps1` | Complete static source review | No finding |
| `ops/pipeline/engine/subtitles/routing_decisions.ps1` | Complete static source review | No finding |
| `ops/pipeline/engine/subtitles/srt.ps1` | Complete static source review | No finding |
| `ops/pipeline/engine/subtitles/subtitles.ps1` | Complete static source review | No finding |
| `ops/pipeline/engine/subtitles/tx3g.ps1` | Complete static source review | W05-002 evidence |
| `ops/pipeline/engine/subtitles/vobsub.ps1` | Complete static source review | No finding |
| `src/mediapipeline/core/decide/__init__.py` | Complete static source review | No finding |
| `src/mediapipeline/core/decide/encoding_rules.py` | Complete static source review | No finding |
| `src/mediapipeline/core/decide/processing_decision.py` | Complete static source review | No finding |
| `src/mediapipeline/core/decide/routing.py` | Complete static source review | W05-003 |
| `src/mediapipeline/core/decide/routing_facts.py` | Complete static source review | No finding |
| `src/mediapipeline/core/decide/routing_outputs.py` | Complete static source review | No finding |
| `src/mediapipeline/core/decide/routing_profiles.py` | Complete static source review | No finding |
| `src/mediapipeline/core/decide/routing_size_policy.py` | Complete static source review | No finding |
| `src/mediapipeline/core/decide/routing_trace.py` | Complete static source review | No finding |
| `src/mediapipeline/core/decide/stream_actions.py` | Complete static source review | No finding |
| `src/mediapipeline/pipeline/ass_to_srt/ass_events.py` | Complete static source review | No finding |
| `src/mediapipeline/pipeline/ass_to_srt/log.py` | Complete static source review | No finding |
| `src/mediapipeline/pipeline/ass_to_srt/srt.py` | Complete static source review | No finding |
| `src/mediapipeline/pipeline/ass_to_srt/styles.py` | Complete static source review | No finding |
| `src/mediapipeline/pipeline/ass_to_srt/text.py` | Complete static source review | No finding |
| `src/mediapipeline/pipeline/ass_to_srt/timing.py` | Complete static source review | No finding |
| `src/mediapipeline/pipeline/ass_to_srt_cli.py` | Complete static source review | No finding |

## Findings Summary

| ID | Severity | Area | Summary |
|---|---|---|---|
| W05-001 | Medium | Routing / size guard | Folder policy and route-hint normalization drop `fallback_remux`, disabling the configured remux fallback path for those override sources. |
| W05-002 | Medium | Subtitles / sidecars | MP4 converted-SRT sidecar candidates from ASS/BDPGS/VobSub are collapsed into the TX3G sidecar channel and only one candidate is retained, losing source-kind evidence for converted subtitle sidecars. |
| W05-003 | Low | Stream mapping / plan evidence | Decision planning models one primary video stream while command builders map all non-attached video streams; existing tests assert this command shape, but multi-video policy evidence is not explicit. |

## Detailed Findings

### W05-001 - `fallback_remux` is silently rejected in folder-policy and route-hint normalization

Severity: Medium

File: `ops/pipeline/engine/policy/folder_policy.ps1`; `ops/pipeline/engine/decide/profile_selection.ps1`; `ops/pipeline/engine/decide/size_policy.ps1`

Symbol/section: `ConvertTo-MediaPipelineFolderPolicyOverrides`; `ConvertTo-MediaRouteHintMap`; `Resolve-MediaRouteSizeGuardModeName`; `Test-MediaEncodeOutputSizePolicy`

Evidence:

- `ops/pipeline/engine/policy/folder_policy.ps1:253-255` reads `routing.size_guard_mode` but only accepts `advisory`, `strict`, and `off`, omitting `fallback_remux`.
- `ops/pipeline/engine/decide/profile_selection.ps1:55-58` repeats the same allowlist in `ConvertTo-MediaRouteHintMap`, so even route hints lose `fallback_remux`.
- `ops/pipeline/engine/decide/profile_selection.ps1:171-181` shows the canonical resolver accepts `fallback_remux`.
- `ops/pipeline/engine/decide/size_policy.ps1:297-308` only enables remux fallback when the effective mode equals `fallback_remux`.
- Existing test search found direct `-SizeGuardMode 'fallback_remux'` checks, but not a folder-policy or active-override path proving the value survives into route hints.

Impact:

Operators can configure `fallback_remux` through a folder policy or active override and see it silently collapse back to the default/advisory route. Oversized automatic size/bitrate-threshold encodes then warn or continue according to the fallback mode actually in scope instead of attempting the documented remux fallback, which is a media-policy behavior change with no explicit failure.

Fix direction:

Use the canonical size-guard mode set in both folder-policy and route-hint normalization. Prefer a shared helper or constants-backed validator so `fallback_remux` cannot diverge between UI/contracts/config and PowerShell routing. Reject unknown values with explicit metadata or warnings instead of silently dropping a configured known value.

Validation:

Add focused PowerShell unit coverage for `mediapipeline.folder.json` with `routing.size_guard_mode = fallback_remux`, `Get-ActiveMediaRouteHints`, `Resolve-MediaRouteBySize`, and `Test-MediaEncodeOutputSizePolicy` on an oversized automatic encode. Rerun the media-policy validation rung, and rerun representative real-media validation before shipping any behavior fix.

### W05-002 - MP4 converted-SRT sidecar path loses source subtitle kind and keeps only one candidate

Severity: Medium

File: `ops/pipeline/engine/subtitles/builders.ps1`; `ops/pipeline/engine/subtitles/tx3g.ps1`

Symbol/section: `Build-SubtitleArgsForFFmpeg` MP4 sidecar branch; `Resolve-Tx3gSrtDestination`; `New-Tx3gSrtSidecarPublishPlan`

Evidence:

- `ops/pipeline/engine/subtitles/builders.ps1:512-519` places ASS-derived converted SRT records into `$tx3gTracks` when the output container is MP4.
- `ops/pipeline/engine/subtitles/builders.ps1:743-753` combines `$tx3gTracks`, `$bdpgsTracks`, and `$vobSubTracks`, sorts all converted SRT candidates together, and selects only the first sidecar.
- `ops/pipeline/engine/subtitles/builders.ps1:754-769` logs candidate drops, returns only `Tx3gTracks`, clears `BdpgsTracks` and `VobSubTracks`, and reports `DroppedEmbeddedTrackCount = $allTracks.Count`.
- `ops/pipeline/engine/subtitles/tx3g.ps1:203` hardcodes the path component `tx3g`; `ops/pipeline/engine/subtitles/tx3g.ps1:357` publishes the sidecar as kind `tx3g_srt`.

Impact:

The MP4 compatibility path can turn a successful ASS, BDPGS, or VobSub conversion into a TX3G-labeled sidecar record. Pending-publish manifests, repair evidence, and operator review can misidentify the original subtitle source kind. When multiple converted candidates are available, successful candidates after the first are dropped under a generic log message rather than represented as typed policy decisions. This is especially risky because subtitle/OCR failures are intentionally review-routed, so successful conversion evidence needs to remain precise.

Fix direction:

Separate external SRT sidecar records from TX3G-specific records, or add explicit `source_codec`/`conversion_kind` metadata that survives selection, pending-publish, repair, and sidecar write paths. If MP4 must publish exactly one external SRT, record the selected candidate and dropped candidates with source-kind evidence and deterministic selection reason.

Validation:

Add subtitle builder tests for MP4 output with mixed ASS, TX3G, BDPGS, and VobSub converted SRT candidates. Assert selected sidecar provenance, dropped-candidate evidence, sidecar kind/path, pending-publish manifest shape, and failure behavior. Rerun real-media validation with at least one ASS sample and one bitmap subtitle OCR/conversion sample before shipping behavior changes.

### W05-003 - Video decision evidence is primary-stream only while FFmpeg maps all real video streams

Severity: Low

File: `src/mediapipeline/core/decide/routing.py`; `ops/pipeline/engine/decide/encode_policy.ps1`; cross-scope evidence in `ops/pipeline/engine/process/pipeline_plan_executor.ps1` and `ops/pipeline/engine/process/pipeline_plan_executor/validation.ps1`

Symbol/section: `build_processing_decision`; `New-EncodeFfmpegArgumentList`; pipeline-plan executor video map handling

Evidence:

- `src/mediapipeline/core/decide/routing.py:34-60` selects `source.video_streams[0]` and emits a single video stream action for that stream.
- `src/mediapipeline/contracts/source_media_models.py:145` allows a list of video streams; no single-video source invariant was found in the assigned decision files.
- `ops/pipeline/engine/decide/encode_policy.ps1:276-282` maps `-map 0:V` when no subtitle-burn filter is present, which maps all non-attached-picture video streams.
- Cross-scope command call sites in `ops/pipeline/engine/process/pipeline_plan_executor.ps1:331-337`, `355-361`, and `418-428` use one planned video action while remux/encode command shapes map all non-attached video streams.
- Cross-scope validation in `ops/pipeline/engine/process/pipeline_plan_executor/validation.ps1:97-108` enforces exactly one video stream action, not one source video stream.
- Existing tests assert `-map 0:V`, so the current command shape appears intentional, but the policy and verification evidence for multi-video sources is not explicit.

Impact:

Multi-video sources can carry extra angle/commentary/sign-language/video streams through remux or encode commands without per-stream decision evidence. If preserving all non-attached video streams is intended, the plan does not record that intent per stream. If only the primary video is intended, the command shape is too broad. Either case can make output stream topology, size, and verification evidence diverge from the policy decision the backend exposes.

Fix direction:

Make the policy explicit: either emit stream actions for every non-attached source video stream and verify them, or change command builders to map only the planned primary stream. If all-video preservation is the desired behavior, document it in route/plan metadata and add command/output verification that covers multi-video samples.

Validation:

Add a multi-video fixture or synthetic plan test that proves the intended remux and encode stream topology. Include verification expectations for output video stream count, codec/action per stream, and side effects on size/route evidence. Any real command-shape change requires representative real-media validation.

## Test Coverage Gaps

- No focused folder-policy or active-override test was found proving `size_guard_mode = fallback_remux` survives into `Get-ActiveMediaRouteHints` and the post-encode size policy path.
- No focused MP4 subtitle builder test was found for mixed ASS/TX3G/BDPGS/VobSub converted SRT candidates that asserts selected sidecar provenance and dropped-candidate evidence.
- Existing command-shape tests assert `-map 0:V`, but no multi-video fixture was found that checks whether all-video mapping is the intended policy and whether output verification records every video stream.
- Real-media validation was not run in this review-only pass. Any fix to FFmpeg/subtitle/audio/routing behavior must rerun the high-validation ladder and representative media samples.

## Boundary Risks

- Findings touch high-risk media-policy areas from `AGENTS.md`: FFmpeg mapping, subtitle sidecar/pending-publish evidence, and size-guard routing. No source behavior was changed in this worker pass.
- Source mutation, scratch/output cleanup, pending-publish drain, queue mutation, and settings persistence were not exercised or changed.
- Subtitle/OCR helper failure paths reviewed in this slice are generally fail-closed: missing tools, invalid SRT output, extraction failure, and conversion failure route to failure records instead of silent publish.
- Audio decision review found explicit no-audio failure handling, override-drop guardrails, MP4 single-audio selection, transcode metadata, and default disposition handling; no audio-loss finding was identified in the assigned files.

## Files Reviewed With No Findings

No findings were recorded for these assigned files:

`ops/pipeline/engine/audio/audio.ps1`, `ops/pipeline/engine/audio/audio/stream_decisions.ps1`, `ops/pipeline/engine/decide/codec_policy.ps1`, `ops/pipeline/engine/decide/route_plan.ps1`, `ops/pipeline/engine/decide/routing.ps1`, `ops/pipeline/engine/decide/show_overrides.ps1`, `ops/pipeline/engine/decide/stage.ps1`, `ops/pipeline/engine/probe/media_probe.ps1`, `ops/pipeline/engine/probe/stage.ps1`, `ops/pipeline/engine/subtitles/ass.ps1`, `ops/pipeline/engine/subtitles/bdpgs.ps1`, `ops/pipeline/engine/subtitles/builders/decisions.ps1`, `ops/pipeline/engine/subtitles/common.ps1`, `ops/pipeline/engine/subtitles/failure_records.ps1`, `ops/pipeline/engine/subtitles/filtering.ps1`, `ops/pipeline/engine/subtitles/language_policy.ps1`, `ops/pipeline/engine/subtitles/routing_decisions.ps1`, `ops/pipeline/engine/subtitles/srt.ps1`, `ops/pipeline/engine/subtitles/subtitles.ps1`, `ops/pipeline/engine/subtitles/vobsub.ps1`, `src/mediapipeline/core/decide/__init__.py`, `src/mediapipeline/core/decide/encoding_rules.py`, `src/mediapipeline/core/decide/processing_decision.py`, `src/mediapipeline/core/decide/routing_facts.py`, `src/mediapipeline/core/decide/routing_outputs.py`, `src/mediapipeline/core/decide/routing_profiles.py`, `src/mediapipeline/core/decide/routing_size_policy.py`, `src/mediapipeline/core/decide/routing_trace.py`, `src/mediapipeline/core/decide/stream_actions.py`, `src/mediapipeline/pipeline/ass_to_srt/ass_events.py`, `src/mediapipeline/pipeline/ass_to_srt/log.py`, `src/mediapipeline/pipeline/ass_to_srt/srt.py`, `src/mediapipeline/pipeline/ass_to_srt/styles.py`, `src/mediapipeline/pipeline/ass_to_srt/text.py`, `src/mediapipeline/pipeline/ass_to_srt/timing.py`, and `src/mediapipeline/pipeline/ass_to_srt_cli.py`.

## Files Marked Out Of Scope

- `ops/pipeline/engine/process/pipeline_plan_executor.ps1` and `ops/pipeline/engine/process/pipeline_plan_executor/validation.ps1` were used only as cross-scope call-site evidence for W05-003, not exhaustively reviewed.
- Existing aggregate review files and other worker reports under `docs/reviews/function-module-audit-2026-06-11/` were not edited.
- Runtime state, media samples, `LocalBase/`, queue state, scratch/output roots, and source media files were not opened or mutated.

## Incomplete Coverage

Assigned-file static source coverage is complete for the 43 W05 files listed in `ASSIGNMENTS.md`.

Incomplete items by design for this review-only worker pass:

- No PowerShell or Python test suite was executed.
- No FFmpeg/ffprobe command was executed against media.
- No WebView/Tauri smoke was run.
- No real-media validation was run.
- CodeRabbit CLI review was not run because the available skill targets diff review, while this assignment required an isolated static source-slice audit with a strict write boundary.
