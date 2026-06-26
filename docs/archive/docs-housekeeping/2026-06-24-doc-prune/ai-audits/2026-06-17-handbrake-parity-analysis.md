# HandBrake Parity Analysis - 2026-06-17

Change packet: `MP-CHANGE-2026-0617-010`

Scope: report-only static audit. No source, config, preset, queue, UI, media-policy, FFmpeg, subtitle, audio, publish, worker, schema, test, script, or generated-contract behavior was changed.

## 1. Executive Summary

This project is not a HandBrake clone. It is closer to an operator-safe library pipeline with HandBrake-like encoding controls under a stronger backend-owned policy model. It already covers the important production needs HandBrake users usually expect from a queue-driven transcoder: source probing, queueing, profiles/presets, codec and container choices, remux-versus-encode decisions, audio and subtitle policy, progress/log evidence, retry/failure handling, output naming, and batch processing. It also goes well beyond HandBrake in library safety, pending-publish parking, command journaling, WebView/Tauri controls, final-library promotion, and coordinator/worker operation.

The largest parity gaps are not core encoding capability. They are operator inspection features: HandBrake-style preview encodes, clearer per-file planned-versus-actual stream outcomes, profile comparison/export ergonomics, and a more explicit launch-scope simulator. These improvements should be approached as read-only or evidence-first surfaces where possible. Any implementation that changes FFmpeg command generation, subtitle conversion, audio selection/transcoding, remux/encode route decisions, source movement, cleanup, publish/drain behavior, or preset defaults is high validation and requires representative real-media validation.

External HandBrake baseline used for this report:

- HandBrake queue docs describe a source/title/preset/add-to-queue model, plus batch adding multiple titles or folders: <https://handbrake.fr/docs/en/1.3.0/advanced/queue.html>
- HandBrake official presets target device, web, and general-use compatibility; preset selection can enforce resolution, frame rate, audio, and other settings: <https://handbrake.fr/docs/en/latest/technical/official-presets.html>
- HandBrake custom presets can be imported/exported, while audio/subtitle selections are stored as behavior rules rather than fixed source tracks: <https://handbrake.fr/docs/en/latest/advanced/custom-presets.html>
- HandBrake audio/subtitle defaults are behavior rules applied when scanning a source or selecting a title: <https://handbrake.fr/docs/en/latest/advanced/audio-subtitle-defaults.html>
- HandBrake preview encodes a short portion of a source to inspect settings before committing to the full encode: <https://handbrake.fr/docs/en/1.3.0/workflow/preview-settings.html>

Primary result:

| Area | Parity status | Operator significance |
| --- | --- | --- |
| Queue model | Supported, intentionally different | Stronger for unattended library work than HandBrake's manual job queue. |
| Preset/profile model | Partial | Strong backend schema and Library Profiles exist, but no full HandBrake-style preset manager/import-export workflow. |
| Source analysis | Supported for file libraries; intentionally different from disc/title workflows | File and ffprobe-centric source analysis fits the Plex-style pipeline. Disc title scanning is not a core goal. |
| Title selection | Missing or not applicable for DVD/Blu-ray titles; partial for per-file stream selection | Important only if operators expect disc ripping/title picking. |
| Track selection | Partial | Backend supports language/codec/index selectors and preview evidence; UI parity is not as interactive as HandBrake. |
| Remux vs encode decisions | Supported | Strong parity and stronger policy evidence than typical GUI-only flows. |
| Quality controls | Partial | CQ/CRF/preset/size guard controls exist; not a full HandBrake video-tuning workbench. |
| Codec/container choices | Supported, with policy constraints | Backend-owned choices are explicit and safer than arbitrary per-job freeform edits. |
| Audio passthrough/downmix/transcode | Supported, high-risk area | Good policy coverage; all behavior changes require real-media validation. |
| Subtitle preservation/conversion/burn-in equivalents | Partial to supported, high-risk area | Stronger than HandBrake for OCR/review routing in some paths; burn-in and preview ergonomics are less GUI-rich. |
| Preview/inspection | Partial | Evidence/log inspection exists; HandBrake-style video preview/sample encode is missing. |
| Batch behavior | Supported, intentionally different | Better for operator library batches; less like manual per-job edit queue. |
| Failure/retry behavior | Supported | Stronger than HandBrake for pipeline recovery, retry classification, pending publish, and rerun safety. |
| Progress reporting | Supported | FFmpeg/mkvmerge progress and status APIs exist. |
| Logs | Supported | Strong command and run-log evidence model. |
| Output naming | Supported, intentionally different | Library-oriented naming, promotion, and safety checks go beyond HandBrake. |
| Library workflows | Supported beyond HandBrake | A core project strength. |
| Safety around originals | Supported beyond HandBrake | Source mutation is forbidden by default; scratch copy and pending publish protect originals and final roots. |
| Distributed/worker behavior | Supported beyond HandBrake | Coordinator/worker and local worker-slot behavior exceed HandBrake-like expectations. |

## 2. Methodology

Required startup reads were completed:

- `AGENTS.md`
- `docs/CURRENT_PROJECT_STATE.md`
- `docs/OPEN_WORK_CHECKLIST.md`
- `docs/generated/PROJECT_INDEX.md`

Because this report touches high-risk media domains, `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md` was also read before drawing conclusions. Generated summaries under `docs/generated/summaries/` were used before opening source files. Full source was opened only where the summary marked the file high priority or where a specific function required source-level verification.

Evidence types used:

| Evidence type | Examples |
| --- | --- |
| Current project state | `docs/CURRENT_PROJECT_STATE.md`, `docs/OPEN_WORK_CHECKLIST.md` |
| Safety boundaries | `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md`, `docs/architecture/FILE_LIFECYCLE_MAP.md` |
| API and command ownership | `docs/inventories/API_ROUTE_INVENTORY.md`, `docs/inventories/COMMAND_OWNERSHIP_MATRIX.md` |
| Settings and profile ownership | `docs/inventories/SETTINGS_KEY_OWNERSHIP_MAP.md`, `docs/inventories/SETTINGS_BUILDER_COVERAGE_MATRIX.md` |
| Decision engine | `src/mediapipeline/core/decide/*.py`, `ops/pipeline/engine/decide/*.ps1` |
| Queue and overrides | `src/mediapipeline/core/queue/*.py`, `ops/pipeline/engine/queue/*.ps1` |
| Audio/subtitle/publish/process | `ops/pipeline/engine/audio/*.ps1`, `ops/pipeline/engine/subtitles/*.ps1`, `ops/pipeline/engine/publish/*.ps1`, `ops/pipeline/engine/process/*.ps1` |
| Network/worker | `docs/architecture/NETWORK_LIFECYCLE_COMMAND_CONTRACT.md`, `src/mediapipeline/desktop/network/*.py` |
| Test and validation posture | `docs/testing/VALIDATION_LADDER_RUNBOOK.md`, `docs/testing/RealMediaValidationRuns/README.md` |

Limitations:

- No Local API, Tauri shell, browser smoke, FFmpeg run, HandBrake install, or real-media sample was executed for this report.
- This is a source-backed static audit, not a runtime certification.
- The worktree was already heavily dirty before this report. Conclusions are based on the active files and generated summaries read during this audit, not on a clean release tag.
- HandBrake parity is evaluated as "HandBrake-like expectations", not exact compatibility with any one HandBrake release or preset file format.

## 3. Parity Matrix

Status meanings:

| Status | Meaning |
| --- | --- |
| Supported | The project has a comparable capability in active code/docs. |
| Partial | The project has meaningful coverage but lacks some HandBrake-like workflow, UI, or behavior. |
| Missing | No comparable active capability was found. |
| Intentionally different | The project solves the operator need through a different model by design. |
| Not applicable | The HandBrake expectation does not fit this pipeline's stated goals. |

| Feature area | HandBrake-like expectation | Project evidence | Status | Notes |
| --- | --- | --- | --- | --- |
| Queue model | Add scanned source/title jobs to a queue, edit/remove jobs, start queue. | Queue snapshot/source inventory/dry-run services, priority/hold/manual strategy, launch preflight/start routes, local worker slots, network worker claims. | Supported, intentionally different | Strong batch/library queue, but not a manual HandBrake job-list clone. |
| Preset/profile model | Built-in and custom presets, import/export, default preset, behavior rules for audio/subtitles. | `PresetV2`, `PresetPolicyModel`, Library Profiles, settings metadata, HandBrake-style display sections, schema-backed config. | Partial | Policy model is strong; preset import/export and friendly profile diffing are weaker. |
| Source analysis | Scan source, identify titles, durations, chapters, tracks, codec details. | ffprobe adapters, source media contracts, route map, queue source inventory, track metadata, media probe helpers. | Supported for file sources; partial for title/chapter workflows | File-library probing is strong; optical-disc title selection is absent or not applicable. |
| Title selection | Choose a DVD/Blu-ray title or multiple titles. | Source roots and file candidates; no active disc title picker found. | Missing or not applicable | This is a Plex-style file pipeline, not a disc-ripping UI. |
| Track selection | Select audio/subtitle tracks and behavior rules. | File override exact track selectors, language/codec/channel/forced/title metadata, audio/subtitle policies, preview warnings. | Partial | Backend selectors are strong; operator ergonomics are less like HandBrake's track tables. |
| Remux vs encode decisions | Decide whether to encode, pass through, or change container. | `build_processing_decision`, stream actions, routing profiles, PowerShell routing/codec policy. | Supported | One of the strongest parity areas. |
| Quality controls | Constant quality, average bitrate, presets/tunes, dimensions/filters. | `VideoQuality`, `VideoPreset`, `EncodeTuningPreset`, route target sizes/bitrates, size guards, CPU fallback CRF, NVENC CQ. | Partial | Strong practical controls, but not a full HandBrake-style filter/tune/chapter workbench. |
| Codec/container choices | Choose video codec, audio codec behavior, MKV/MP4 container. | Config schema supports video codecs, `OutputContainer`, remux-safe codec lists, MP4 compatibility shaping. | Supported | Choices are policy-constrained for library safety. |
| Audio passthrough | Keep compatible audio when allowed. | `AudioPassthroughProfile`, `CompatibleAudioCodecs`, `Build-AudioArgs`, stream decision plan. | Supported | High-risk behavior. Any change needs high validation. |
| Audio downmix/transcode | Transcode or downmix by profile/channel limits. | `AudioTranscodeCodec`, `AudioTranscodeBitrate`, auto bitrate by channel, `AudioDownmixMode`, `AudioMaxChannels`. | Supported | Good parity with stronger config governance. |
| Subtitle preservation | Preserve subtitle streams by default where safe. | `SubKeepLanguages`, subtitle routing actions, sidecar/carry-forward evidence. | Supported with constraints | Image subtitle and OCR paths route to review/failure rather than silent bad output. |
| Subtitle conversion | Convert TX3G/BDPGS/VobSub/ASS-related cases where configured. | Subtitle settings, OCR tool paths, conversion toggles, forced/signs/songs classification. | Partial to supported | Broader than simple GUI defaults, but behavior is high-risk and validation-heavy. |
| Subtitle burn-in | Burn forced or selected subtitles when configured. | `SubtitleMode`, file override burn-track support, route video-processing flag. | Partial | Capability exists, but no HandBrake-like live preview. |
| Chapters/metadata | Preserve/add chapter markers and metadata choices. | MP4 compatibility planned output strips chapters/fonts/attachments/metadata; source title tag probe exists. | Partial or intentionally different | Library compatibility and safe output shape appear to override HandBrake-style chapter tooling. |
| Preview encode | Encode a short source portion to inspect output. | No active HandBrake-style preview encode UI found. Diagnostics/open/evidence exist. | Missing | Highest visible parity gap for manual quality tuning. |
| Inspection before run | Show what selected settings will do. | Settings pipeline-plan-preview, library route map, queue track-selection preview, launch preflight. | Partial | Strong policy evidence, but not consolidated into a HandBrake-like per-source summary. |
| Batch add | Add many titles/files and process queue. | Source scan, queue inventory, queue strategy/priority/hold, pipeline start modes, rerun CSV, schedule. | Supported, intentionally different | Better for library batches than one-off title queues. |
| Failure/retry | Recover failed jobs, inspect logs, retry. | Failure code registry, retry state, rerun start, pending publish recovery, diagnostics. | Supported | Stronger than HandBrake's typical activity-log/manual retry model. |
| Progress reporting | Show live encode progress. | FFmpeg progress payloads, mkvmerge progress parsing, status ETA/progress APIs. | Supported | Backend evidence oriented. |
| Logs | Activity/run logs for support and diagnosis. | Command journal, launch logs, diagnostics tails, completed evidence, run logs. | Supported | Stronger command ownership and auditability. |
| Output naming | Automatic output naming and collision prevention. | Rename preview/apply, final library promotion, TV subfolder, duplicate destination guards. | Supported, intentionally different | More library-aware than HandBrake's output filename template model. |
| Library workflows | Manage source/output libraries. | Library Profiles, route maps, final-library promotion, pending publish, reconciliation. | Supported beyond HandBrake | Core project differentiator. |
| Safety around originals | Avoid destructive original mutation. | Source immutable by default, scratch copy invariants, no safe-delete unless explicit. | Supported beyond HandBrake | Stronger than typical desktop transcoder expectations. |
| Distributed workers | Multiple workers/coordinator. | Network lifecycle, worker claims, local worker slots, done reports. | Supported beyond HandBrake | HandBrake is not primarily a distributed library pipeline. |

## 4. Feature-by-Feature Evidence

### Queue Model

The project has a queue model, but it is not centered on manually adding one scanned title at a time. Evidence points to a backend-owned source scan and queue snapshot pipeline:

| Evidence | Finding |
| --- | --- |
| `src/mediapipeline/core/queue/service.py` summary | Queue service composes dry-run, preview, priority, snapshot, and source inventory helpers. |
| `src/mediapipeline/core/queue/source_inventory.py` summary | Builds and persists queue source inventory, queue roots, status, path, and payload artifacts. |
| `src/mediapipeline/core/queue/dry_run.py` summary | Builds queue dry-run command and source-status plan evidence. |
| `src/mediapipeline/core/queue/priority_manifest.py` summary | Supports priority levels including high and hold. |
| `src/mediapipeline/core/queue/strategy.py` summary | Supports queue strategy state. |
| `docs/inventories/API_ROUTE_INVENTORY.md` | Distinguishes read-only queue routes from backend-owned queue scan and state-write routes. |
| `ops/pipeline/engine/queue/pipeline_engine.ps1` summary | Emits queue plan/round/run behavior. |
| `ops/pipeline/engine/queue/local_worker_slots.ps1` evidence | Local slot scheduling supports more than a single foreground encode when configured. |

Parity result: supported, intentionally different. This project is stronger for a standing library queue, priority/hold workflows, schedule/rerun/pending-publish recovery, and unattended operation. It is weaker if an operator expects a HandBrake queue window where each job is edited by reopening the scanned source/title.

### Preset and Profile Model

HandBrake's preset model combines built-in presets, custom presets, import/export, default preset choice, and source-specific audio/subtitle selection behavior. This project has schema-backed settings, profiles, Library Profiles, and display sections that intentionally resemble HandBrake settings categories, but the operator workflow is different.

| Evidence | Finding |
| --- | --- |
| `src/mediapipeline/core/config/preset_policy.py` summary | Defines `PresetV2`, routing, publish, verification, guard, advanced, size, and direct-copy policies. |
| `src/mediapipeline/core/config/preset_migration.py` summary | Provides stable config and preset display adapters plus legacy conversion. |
| `src/mediapipeline/core/config/preset_encoding_sections.py` summary | Defines HandBrake-style preset sections: audio, container, dimensions, filters, subtitle, and video. |
| `src/mediapipeline/core/config/library_profiles.py` summary | Supports Library Profiles for library-specific behavior. |
| `docs/inventories/SETTINGS_KEY_OWNERSHIP_MAP.md` | Backend metadata owns 156 settings keys; high-risk keys are explicitly identified. |
| `docs/inventories/SETTINGS_BUILDER_COVERAGE_MATRIX.md` | WebView builders cover routing/size, video detail, audio, subtitle, file safety/publish, pending publish, and Library Profiles. |
| `tests/webview/test_webview_handbrake_settings_ui.py` search evidence | UI has HandBrake-style tabs and asserts backend ownership of routing, codec, container, and encoder policy. |

Parity result: partial. The policy foundation is stronger than a casual desktop preset, but the project lacks a polished HandBrake-like preset manager with import/export, profile comparison, and safe default-preset selection UX. This is a good candidate for read-only and config-preview improvements, not for casual policy changes.

### Source Analysis

The project analyzes files with ffprobe and normalizes them into source media contracts. It is designed around source roots and file candidates rather than optical-disc title scanning.

| Evidence | Finding |
| --- | --- |
| `src/mediapipeline/contracts/source_media_adapters.py` summary | Normalizes ffprobe/probe metadata into `SourceMediaInfo`. |
| `src/mediapipeline/contracts/source_media_streams.py` summary | Builds video, audio, and subtitle streams from ffprobe or stream summaries. |
| `ops/pipeline/engine/probe/media_probe.ps1` summary | Probes duration, HDR/Dolby Vision, source title tag, source video codec/inventory, file integrity, and duration match. |
| `docs/architecture/FILE_LIFECYCLE_MAP.md` | `incoming_candidate` is not implemented; source library and scratch-copy states are active. |
| `docs/inventories/API_ROUTE_INVENTORY.md` | Queue scan and route-map APIs expose source analysis/read-only evidence. |

Parity result: supported for file-library sources; partial or not applicable for DVD/Blu-ray title/chapter intake.

### Title and Track Selection

Disc-style title selection was not found as an active capability. Per-file audio/subtitle track selection has meaningful support through file overrides and source stream metadata.

| Evidence | Finding |
| --- | --- |
| `src/mediapipeline/core/queue/file_overrides.py` summary and targeted searches | Supports file override entries, validation, exact track selectors, effective matches, and warnings. |
| `tests/python/desktop/test_file_override_tracks.py` search evidence | Tests cover audio keep/drop, subtitle keep/drop, burn track, stream-index selectors, language/codec/channels/forced/title matching, unsupported raw ffmpeg map rejection, and metadata-unavailable warnings. |
| WebView file override drawer search evidence | UI exposes track metadata and track-selection preview, not raw FFmpeg map editing. |
| `src/mediapipeline/core/decide/stream_actions.py` | Applies container, audio, and subtitle actions from policy and stream properties. |

Parity result: partial. The backend supports robust, safe selectors. The missing part is a HandBrake-like title/track table workflow where an operator scans one source, manually selects tracks, previews, and adds the exact job to a queue. The project intentionally avoids raw stream maps and keeps backend policy in control.

### Remux Versus Encode Decisions

This is a strong parity area. The Python decision engine and PowerShell execution policy both encode the route reasons, stream actions, size/bitrate thresholds, codec compatibility, and output shaping.

| Evidence | Finding |
| --- | --- |
| `src/mediapipeline/core/decide/routing.py` | `build_processing_decision()` returns structured copy/remux/encode/reject decisions without running encoders. |
| `src/mediapipeline/core/decide/processing_decision.py` | Defines route summaries `COPY`, `REMUX`, `ENCODE`, `REJECT`, action DTOs, route threshold modes, size guard modes, video target modes, subtitle modes, and planned output models. |
| `src/mediapipeline/core/decide/encoding_rules.py` | Filters, crop, resolution limits, and audio transcode reasons trigger encode/transcode. |
| `src/mediapipeline/core/decide/routing_profiles.py` | Defines Plex direct-copy profile predicates and H.264 copy shortcuts. |
| `src/mediapipeline/core/decide/routing_size_policy.py` | Applies resolution-aware size and bitrate policy. |
| `ops/pipeline/engine/decide/routing.ps1` summary | Resolves initial route and size-based route plans. |
| `ops/pipeline/engine/decide/codec_policy.ps1` summary | Encodes Plex copy/remux-safe codec decisions. |

Parity result: supported. The project is arguably more explicit than HandBrake in distinguishing direct copy, remux, encode, reject, advisory, verification, and publish requirements.

### Quality Controls

The project exposes practical quality controls, but it is not trying to reproduce every HandBrake video-tuning knob.

| Evidence | Finding |
| --- | --- |
| `src/mediapipeline/contracts/config.py` search evidence | Includes `VideoCodec`, `VideoPreset`, `VideoQuality`, `OutputContainer`, route target sizes, route bitrate caps, and size guard controls. |
| `src/mediapipeline/core/config/metadata_parts/video_fields.py` | Documents hardware/codec, preset, quality, output container, remux-safe codecs, CPU fallback quality/preset, and extra video flags. |
| `src/mediapipeline/core/config/metadata_parts/basic_processing.py` search evidence | Documents route threshold modes, H.264 copy shortcut, size/bitrate caps, and output size check behavior. |
| `ops/pipeline/engine/decide/encode_policy.ps1` search evidence | Builds NVENC/QSV/CPU encode flags; uses NVENC CQ for GPU and libx265 CRF for CPU fallback, with separate semantics. |
| `ops/pipeline/config/schemas/media_pipeline_config.schema.json` search evidence | Constrains encoder, container, tuning preset, and parallel encode settings. |

Parity result: partial. The operator can influence quality, size, codec, preset, and fallback behavior. Missing or intentionally limited areas include full HandBrake filter workbench, chapter tooling, arbitrary tune/profile/level UI, and visual preview for quality tuning. Any changes to the FFmpeg flag builder or quality policy are high validation.

### Codec and Container Choices

The project has clear codec/container controls and policy constraints.

| Evidence | Finding |
| --- | --- |
| `ops/pipeline/config/schemas/media_pipeline_config.schema.json` search evidence | Video codec enum includes hardware and CPU HEVC/H.264/AV1 options; `OutputContainer` is constrained to `mkv` or `mp4`. |
| `src/mediapipeline/core/decide/stream_actions.py` | Container action remuxes when source container differs from target or remux is forced. |
| `src/mediapipeline/core/decide/routing_outputs.py` | MP4 compatibility planned output defines allowed video families, selected audio streams, EAC3 audio output, dropped audio count, external SRT sidecar requirements, and stripped attachments/metadata/chapters. |
| `ops/pipeline/engine/decide/codec_policy.ps1` summary | Defines remux-safe and Plex copy candidate codec behavior. |

Parity result: supported with intentional policy constraints. The project prioritizes library compatibility and backend proof over arbitrary per-job freeform choices.

### Audio Passthrough, Downmix, and Transcode

Audio support is strong and high risk. The project supports passthrough, transcode codec/bitrate, channel-aware auto bitrate, downmix mode, max channel controls, preferred default languages, and MP4 compatibility shaping.

| Evidence | Finding |
| --- | --- |
| `src/mediapipeline/contracts/config.py` search evidence | Defines `AudioPassthroughProfile`, `CompatibleAudioCodecs`, `PreferredDefaultAudioLanguages`, `AudioTranscodeCodec`, `AudioTranscodeBitrate`, `AudioTranscodeAutoBitrateByChannels`, `AudioDownmixMode`, `AudioMaxChannels`, and `AllowNoAudio`. |
| `src/mediapipeline/core/config/metadata_parts/audio_fields.py` via settings matrix evidence | Audio builder covers passthrough/transcode/channel/language controls. |
| `ops/pipeline/engine/audio/audio.ps1` summary | Builds audio args, preferred default audio, downmix, auto bitrate, and transcode decisions. |
| `ops/pipeline/engine/audio/stream_decisions.ps1` summary | Builds audio stream decision plan and selects MP4-compatible audio source. |
| `src/mediapipeline/core/decide/routing.py` source read | MP4 policy selects one preferred-language audio stream, transcodes to EAC3 when needed, and drops other audio streams for MP4 compatibility. |
| `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md` | Audio routing is explicitly high risk and requires unit plus real-media multi-audio validation for behavior changes. |

Parity result: supported. Compared with HandBrake, the project has less manual per-job GUI editing but stronger library policy and safety evidence. All audio policy or FFmpeg audio argument changes require high validation and representative real-media validation.

### Subtitle Preservation, Conversion, and Burn-In

Subtitle support is robust but intentionally safety-biased. Text subtitle handling, TX3G conversion, BDPGS/VobSub OCR paths, signs/songs/forced classification, SDH/supplemental keywords, and review routing are present. Image subtitle and OCR failure paths are treated conservatively.

| Evidence | Finding |
| --- | --- |
| `src/mediapipeline/contracts/config.py` search evidence | Defines subtitle language keeps, TX3G conversion, BDPGS OCR, VobSub OCR, SDH/supplemental keywords, signs/songs forced classification, style include/exclude, and timeouts. |
| `src/mediapipeline/core/config/metadata_parts/subtitle_fields.py` search evidence | Documents SRT sidecars, TX3G-to-SRT, BDPGS OCR with PgsToSrt, VobSub OCR with Subtitle Edit/Tesseract, and language selection. |
| `src/mediapipeline/core/decide/stream_actions.py` | Defines subtitle copy, convert, burn, drop, review-block, MP4 external SRT-only, and unsupported-image-subtitle behavior. |
| `src/mediapipeline/core/decide/routing.py` source read | Image subtitle review can reject a route; subtitle burn-in forces encode. |
| `ops/pipeline/engine/subtitles/subtitles.ps1` summary | Subtitle implementation is high-priority/high-risk. |
| `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md` | Subtitle conversion is high risk and requires TX3G, BDPGS, ASS, OCR, and real-media validation for behavior changes. |

Parity result: partial to supported. The project meets many HandBrake-like subtitle needs and adds review safety. It lacks HandBrake-like preview/interactive ergonomics for burn-in and subtitle visual inspection.

### Preview and Inspection Features

This is the most visible HandBrake parity gap. The project has strong evidence inspection but no obvious short preview encode workflow.

| Evidence | Finding |
| --- | --- |
| `docs/inventories/API_ROUTE_INVENTORY.md` | Exposes diagnostics, logs, settings preview, pipeline-plan preview, queue previews, route map, completed evidence, sample validation, and open actions. |
| `docs/inventories/COMMAND_OWNERSHIP_MATRIX.md` | Confirms command ownership, read-only previews, high-impact command gates, and command journaling. |
| `src/mediapipeline/core/orchestration/planner.py` summary | Builds dry-run pipeline plans from presets. |
| `src/mediapipeline/contracts/pipeline_plan.py` summary | Defines serializable abstract pipeline plans for dry-run previews. |
| Targeted preview search | No active HandBrake-style video preview/sample clip encode UI was found. |

Parity result: partial. The project can explain what it plans to do, but it does not let an operator encode a short clip and visually compare quality, subtitles, crops, or burn-in before full processing. Adding that would touch FFmpeg execution and temp artifact handling, so it is high validation unless implemented strictly as an isolated, no-publish, no-policy preview path.

### Batch Behavior

The project exceeds HandBrake-like batch processing in library-oriented workflows.

| Evidence | Finding |
| --- | --- |
| `docs/inventories/API_ROUTE_INVENTORY.md` | Queue scan writes authoritative queue snapshot; launch/rerun/audit/pending-publish routes are separated and command-journaled. |
| `docs/architecture/WEBVIEW_SCOPE_PREVIEW_OPERATOR_GUIDE.md` search evidence | UI filters do not alter backend launch/drain scope. |
| `ops/pipeline/engine/queue/engine_plan.ps1` search evidence | `ParallelEncodeMode` and `MaxParallelEncodes` are explicit. |
| `ops/pipeline/engine/queue/local_worker_slots.ps1` search evidence | Local worker-slot scheduling exists. |
| `docs/architecture/NETWORK_LIFECYCLE_COMMAND_CONTRACT.md` | Network workers claim coordinator-assigned work and do not scan local queue or use normal Launch. |

Parity result: supported and intentionally different. The main operator gap is not capability, but clarity: the UI should keep making backend launch scope explicit so operators do not confuse visible filters with action scope.

### Failure, Retry, and Recovery

The project is stronger than HandBrake-like baseline expectations here.

| Evidence | Finding |
| --- | --- |
| `src/mediapipeline/core/failures/retry_state.py` summary | Defines read-only retry-state contract for failure rows, including classification and retryability. |
| `ops/pipeline/engine/shared/failure_codes.ps1` search evidence | Failure code registry records retryability and operator actions; NVENC failures can trigger CPU fallback. |
| `docs/inventories/API_ROUTE_INVENTORY.md` | Exposes failure routes, failure clear, rerun start, pending publish recovery plans, diagnostics, and audit/rerun CSV. |
| `ops/pipeline/engine/queue/pipeline_engine.ps1` search evidence | Retry parked outputs before source discovery. |
| `docs/testing/VALIDATION_LADDER_RUNBOOK.md` | Includes force-kill encode smoke to prove partial output is not accepted. |

Parity result: supported. The project has pipeline-grade failure classes, rerun safety, pending-publish repair, and audit evidence. Operator documentation should continue making the retry path explicit.

### Progress Reporting and Logs

Progress and logs are active, backend-owned capabilities.

| Evidence | Finding |
| --- | --- |
| `ops/pipeline/engine/process/ffmpeg_progress.ps1` summary | `Invoke-FFmpegWithProgress` and `Invoke-MkvmergeWithProgress` parse progress and warnings. |
| `src/mediapipeline/core/status/ffmpeg_progress.py` summary | Provides FFmpeg progress payloads. |
| `src/mediapipeline/core/status/progress.py` and `eta.py` summaries | Format stale/progress and ETA payloads. |
| `src/mediapipeline/core/processes/logs.py` summary | Provides launch log summary and stdout/stderr tails. |
| `src/mediapipeline/desktop/api/command_journal.py` summary | Command journal persists command evidence. |
| `docs/inventories/API_ROUTE_INVENTORY.md` | Diagnostics/tail/open routes expose logs and allowlisted evidence targets. |

Parity result: supported. The gap is presentation polish, not backend evidence.

### Output Naming and Library Workflows

The project is library-first. This is a major intentional difference from HandBrake's default "choose output file" workflow.

| Evidence | Finding |
| --- | --- |
| `src/mediapipeline/core/rename/*.py` summaries and rename tests | Rename preview/apply, duplicate destination guards, case-only handling, sidecar preservation, undo/history behavior. |
| `docs/architecture/FILE_LIFECYCLE_MAP.md` | Defines source, scratch, processing, local output, pending publish, final output, and failure review states. |
| `src/mediapipeline/core/final_library/promotion.py` summary | Final library promotion classes and evidence/manifests. |
| `src/mediapipeline/core/publish/pending_service.py` summary | Pending publish inventory, duplicate marking, and drain summary. |
| `docs/inventories/SETTINGS_BUILDER_COVERAGE_MATRIX.md` | File Safety/Publish and Pending Publish/Recovery settings surfaces exist. |

Parity result: supported beyond HandBrake. The output model is safer and more automated, but less like a one-off desktop transcode dialog.

### Safety Around Originals

This is one of the project's strongest intentional differences.

| Evidence | Finding |
| --- | --- |
| `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md` | Source mutation is forbidden by default; source delete/overwrite requires intentionally enabled safe-delete behavior. |
| `docs/architecture/FILE_LIFECYCLE_MAP.md` | Source roots allow read/probe/copy only; scratch copy, processing, local output, pending publish, final output transitions are defined. |
| `docs/inventories/API_ROUTE_INVENTORY.md` | High-impact commands are backend-owned and confirmation-gated. |
| `docs/inventories/COMMAND_OWNERSHIP_MATRIX.md` | Strict confirmation, launch locks, diagnostics allowlist, and close-readiness are command safety mechanisms. |

Parity result: supported beyond HandBrake. Do not weaken this to chase desktop transcoder convenience.

### Distributed and Worker Behavior

This project goes beyond HandBrake-like expectations.

| Evidence | Finding |
| --- | --- |
| `docs/architecture/NETWORK_LIFECYCLE_COMMAND_CONTRACT.md` | WebView may render controls only through backend routes; worker claims only coordinator-assigned work; normal Launch is blocked in network roles. |
| `src/mediapipeline/desktop/network/worker.py` and `coordinator.py` summaries | Worker and coordinator runtime classes exist. |
| `src/mediapipeline/desktop/network/worker_claims.py`, `worker_done.py`, `worker_state.py` summaries | Claim, done-report, and state behavior exist. |
| `docs/inventories/API_ROUTE_INVENTORY.md` | Network lifecycle, join, discovery, test, and worker routes are command-owned and guarded. |

Parity result: supported beyond HandBrake. This is not HandBrake parity; it is pipeline orchestration.

## 5. Gaps That Matter to Operators

### Gap 1 - No HandBrake-Style Preview Encode

HandBrake users expect a short preview encode before committing to a long run. This project has dry-run plans, logs, probes, and evidence, but no active visual/sample preview encode surface was found.

Why it matters:

- It makes quality tuning harder when adjusting CQ/CRF, presets, codec, or size guards.
- It makes subtitle burn-in, OCR output, forced subtitle behavior, and crop/filter effects harder to validate visually.
- It increases reliance on full-run representative validation for changes that a preview might catch earlier.

Risk note: implementing preview encode touches FFmpeg command construction, temp outputs, cleanup, possibly subtitle/audio mapping, and UI state. Treat as high validation unless it is a strictly isolated no-publish/no-source-mutation preview path.

### Gap 2 - Planned Versus Actual Stream Outcomes Are Spread Across Evidence

The backend has rich route decisions, planned output DTOs, probe evidence, logs, and completed manifests. The operator-facing experience could still be better if one view answered: "What did the pipeline plan to do to video/audio/subtitles, and what did the output actually contain?"

Why it matters:

- It reduces operator anxiety around audio drops, subtitle sidecars, MP4 compatibility stripping, OCR results, and size growth.
- It helps distinguish expected policy behavior from a failure.
- It is safer than exposing raw FFmpeg map controls.

### Gap 3 - Preset/Profile Ergonomics Lag Behind the Policy Model

The project has strong backend profile/preset/schema machinery, but not a HandBrake-style preset manager workflow with import/export, default selection, safe comparison, and "what changes if I choose this profile?" clarity.

Why it matters:

- Operators may not see the impact of profile changes before a queue run.
- High-risk settings are numerous and need safer comparison.
- Library Profiles make this more important, because different libraries can behave differently.

### Gap 4 - Track Selection Is Safe but Less Interactive

Exact selectors and previews exist, but the workflow is not as immediately visual as HandBrake's audio/subtitle tab model.

Why it matters:

- Operators handling multi-audio or subtitle-heavy sources need confidence that default language, commentary/descriptive tracks, forced tracks, SDH, signs/songs, and OCR outcomes are correct.
- MP4 compatibility drops or sidecars can surprise operators if not presented clearly.

Risk note: behavior changes to audio/subtitle selection are high validation. UI-only or read-only explanation surfaces are lower risk.

### Gap 5 - Launch Scope Clarity Should Stay Explicit

The project intentionally separates visible filters from backend action scope. That is safer than HandBrake's visible queue list assumption, but it requires clear operator feedback.

Why it matters:

- In a large library queue, operators need to know exactly what the next Launch, rerun, audit, or pending-publish drain will act on.
- Confusing UI scope can lead to operator distrust even when the backend is safe.

### Gap 6 - Disc Title and Chapter Workflows Are Missing

If an operator expects HandBrake's DVD/Blu-ray title picker or chapter/range tooling, this project does not appear to provide that workflow.

Why it matters:

- It matters for disc-ripping or multi-title source workflows.
- It is less important for the current Plex-style file-library scope.

## 6. Gaps Not Worth Chasing

These gaps are real relative to HandBrake, but they are poor fits for this project unless the product goal changes.

| Gap | Why not chase it now |
| --- | --- |
| Full DVD/Blu-ray title picker | The active pipeline is source-root/file/ffprobe driven. Disc intake would expand scope, validation, and operator complexity. |
| Exact HandBrake preset file compatibility | The project has a safer backend-owned config/profile model. Importing arbitrary HandBrake presets could bypass policy expectations. |
| Arbitrary raw FFmpeg map editor | The current selector model rejects raw maps and keeps policy safe. Raw mapping would raise audio/subtitle failure risk. |
| Frontend-owned encoder or queue policy | AGENTS and architecture docs are clear that backend owns media policy, queue mutation, settings persistence, pending publish, and filesystem mutation. |
| Full HandBrake filter laboratory | Filters/crop are high-risk encode triggers. Unless operators need them, this would add testing cost without improving the library pipeline. |
| Manual one-off output-file chooser as the primary workflow | The project is a library publisher with promotion and pending-publish safety, not a single-output-file desktop transcoder. |
| Burn-in by default to mimic simple playback compatibility | Current subtitle preservation/review behavior is safer. Burn-in changes require representative subtitle real-media validation. |

## 7. Intentional Differences From HandBrake

| Difference | Evidence | Why it matters |
| --- | --- | --- |
| Backend owns policy | AGENTS hard rules, API route inventory, command ownership matrix | Prevents UI drift from media policy and filesystem safety. |
| Source originals are immutable by default | No-touch register, file lifecycle map | Protects the Plex-style source library. |
| Scratch copy before processing | File lifecycle map | Makes retries and failure recovery safer. |
| Pending publish parks unsafe final output | Pending publish service and file lifecycle map | Avoids unsafe final-root writes and preserves drain evidence. |
| Remux is first-class | Routing engine, codec policy, stream actions | Avoids unnecessary encoding when copy/remux is safe. |
| Library Profiles drive behavior | Library profile docs/settings | Different libraries can have different policy and publish destinations. |
| Route decisions are inspectable DTOs | `processing_decision.py`, `pipeline_plan.py`, route map docs | Makes policy auditable before execution. |
| High-impact commands are journaled and confirmation-gated | Command journal and command ownership matrix | Improves release safety and operator traceability. |
| Network coordinator/worker mode exists | Network lifecycle contract and desktop network modules | Enables distributed work beyond HandBrake's normal local app model. |
| Real-media validation is required for media behavior changes | Validation ladder and real-media validation docs | Acknowledges automated tests cannot prove FFmpeg/subtitle/audio correctness alone. |

## 8. Highest-Value Future Parity Improvements

The improvements below are ranked by value and safety. The safest improvements are read-only or evidence-only. Any item that alters FFmpeg, subtitle, audio, route, publish, source movement, cleanup, or preset default behavior is high validation.

### Improvement 1 - Consolidated Per-File Decision Review

Expected user benefit:

- Gives operators a HandBrake-like "summary" before launch: source facts, selected profile, route result, planned output, video/audio/subtitle actions, size/bitrate guard posture, publish target, and warnings.
- Reduces surprises without changing runtime policy.

Affected systems:

- Local API read-only preview routes.
- Queue source inventory.
- Pipeline-plan preview.
- Library route map.
- File override track preview.
- WebView presentation.

Media-policy risk:

- Low if it only reads and renders existing decision/planner/evidence DTOs.
- High if it changes route decision, stream selection, FFmpeg args, subtitle conversion, or audio behavior.

Likely implementation complexity:

- Medium. The data exists, but it is spread across route map, queue preview, settings preview, and file override preview.

Validation needed:

- API contract/unit tests for read-only payload shape.
- WebView smoke for rendering route, stream actions, warnings, and empty/error states.
- Docs-only/link checks if documentation changes.
- Representative real-media validation only if the implementation changes decision logic or media behavior.

### Improvement 2 - Planned Versus Actual Output Inspection Packet

Expected user benefit:

- Gives a completed-job view that compares planned output to probed output: container, video codec/resolution, audio streams kept/transcoded/dropped, subtitles copied/converted/sidecar/burned/dropped, output size, duration match, verification guards, and log links.
- Makes MP4 compatibility behavior and subtitle/audio outcomes easier to trust.

Affected systems:

- Completed evidence.
- Status/progress/readers.
- Diagnostics/log tail.
- Final-library promotion/pending-publish evidence.
- WebView Completed and Diagnostics views.

Media-policy risk:

- Low if it only aggregates existing manifests, probes, and logs.
- Medium if it adds new probe timing or manifest fields.
- High if it changes verification gates, publish eligibility, subtitle/audio outcomes, or FFmpeg execution.

Likely implementation complexity:

- Medium. Data is available but needs a stable, operator-friendly aggregation contract.

Validation needed:

- Unit tests for aggregator behavior with fixture completed manifests.
- Local API route tests for read-only evidence payloads.
- WebView smoke for completed rows with missing, partial, pending, and failed evidence.
- Representative real-media validation if any verifier, publish gate, or output stream policy changes.

### Improvement 3 - Profile Compare, Export, and Safe Default Review

Expected user benefit:

- Lets operators compare Library Profiles and preset/policy changes before saving.
- Supports backup/sharing of known-good profiles without relying on raw PSD1 edits.
- Makes high-risk setting changes more understandable.

Affected systems:

- Config metadata.
- Preset/policy migration.
- Library Profiles.
- Settings preview/save patch.
- Change-control docs for operator profile changes.

Media-policy risk:

- Low for read-only compare/export.
- Medium for import/staged profile creation.
- High if import changes defaults, route policy, audio/subtitle behavior, FFmpeg flags, or publish behavior without explicit preview and validation.

Likely implementation complexity:

- Medium. Existing metadata and patch-preview paths can be reused, but import/export needs strict schema and high-risk-key reporting.

Validation needed:

- Config schema tests.
- Settings patch preview/save tests.
- Library profile tests.
- WebView smoke for compare/export/import preview.
- Representative real-media validation if imported profiles alter media behavior and are promoted as defaults.

### Improvement 4 - Safer Track Selection Review and Templates

Expected user benefit:

- Makes audio/subtitle-heavy sources easier to operate by showing track selector confidence, exact matched streams, planned actions, and warnings.
- Helps operators reuse safe language/commentary/descriptive/forced-subtitle rules without raw FFmpeg maps.

Affected systems:

- Queue file overrides.
- Source stream metadata.
- Track selection preview.
- Audio/subtitle decision policy.
- WebView file override drawer.

Media-policy risk:

- Low for read-only selector confidence and template preview.
- Medium for saved selector templates that only generate existing override fields.
- High for any change to audio or subtitle selection behavior, burn-in, conversion, OCR, sidecar, or stream mapping.

Likely implementation complexity:

- Medium. Exact selector tests already exist, but template UX and confidence reporting need careful edge-case handling.

Validation needed:

- Unit tests for duplicate languages, missing metadata, commentary/descriptive tracks, forced subtitles, SDH/supplemental names, and unsupported image subtitles.
- WebView smoke for selector preview and save/clear behavior.
- Representative real-media validation for any behavior change to audio/subtitle selection or conversion.

### Improvement 5 - Queue Launch Scope Simulator

Expected user benefit:

- Shows exactly what the backend would act on for the next launch/rerun/audit/drain under current queue state, strategy, priority, hold, schedule, source roots, and network role.
- Reduces confusion where visible table filters are not action scope.

Affected systems:

- Launch preflight.
- Queue snapshot.
- Queue source inventory.
- Queue strategy/priority.
- Process launch policy.
- WebView Launch and Queue views.

Media-policy risk:

- Low if strictly read-only and uses existing backend preflight/planner logic.
- Medium if it introduces new selection filters.
- High if it changes actual launch scope, queue mutation, source discovery, pending drain, or worker claim behavior.

Likely implementation complexity:

- Low to medium if it builds on existing preflight and queue plan evidence.

Validation needed:

- Queue and process-launch policy tests.
- API route tests proving simulator is read-only.
- WebView smoke for stale queue, held files, priority files, empty queue, network role, and pending drain cases.
- Representative real-media validation only if actual launch scope or media behavior changes.

### Improvement 6 - Isolated Preview Encode for Visual QC

Expected user benefit:

- Closest direct HandBrake parity improvement.
- Lets operators inspect short clips for quality, subtitle burn-in, OCR output, crop/filter effects, audio sync, and compatibility before a full encode.

Affected systems:

- FFmpeg command generation.
- Temp/scratch preview outputs.
- Subtitle/audio mapping.
- Progress/status.
- Cleanup.
- WebView preview controls.
- Diagnostics/log evidence.

Media-policy risk:

- High. Even if no final publish occurs, this touches FFmpeg, subtitle, audio, source read, scratch/temp output, cleanup, and UI command lifecycle.

Likely implementation complexity:

- High. It needs a no-publish, no-source-mutation, isolated command path with strict temp output boundaries and cleanup evidence.

Validation needed:

- Unit tests for preview command construction and path boundaries.
- Local API command tests with confirmation/journal/duplicate-command behavior.
- WebView smoke for start/cancel/progress/open/cleanup states.
- FFmpeg sample validation for H.264/H.265, MP4/MKV, multi-audio, text subtitles, image subtitles, forced subtitle burn-in, OCR-enabled samples, HDR/Dolby Vision if supported, and failure cleanup.
- Representative real-media validation is required before release because this touches FFmpeg/subtitle/audio behavior.

### Improvement 7 - Profile-Aware Operator Runbook Links

Expected user benefit:

- Connects high-risk settings, Library Profiles, queue decisions, and validation requirements directly from the UI/report docs to the right runbook.
- Helps operators understand when a change needs real-media validation.

Affected systems:

- Docs.
- Settings metadata help text.
- WebView settings/read-only help surfaces.

Media-policy risk:

- Low if documentation/help-only.
- High only if it changes defaults or policy behavior.

Likely implementation complexity:

- Low.

Validation needed:

- Link/file-existence checks.
- Settings metadata snapshot tests if help text is generated into contracts.
- No real-media validation unless behavior changes.

## 9. Validation Requirements by Improvement

| Improvement | Minimum validation if read-only | Additional validation if behavior changes |
| --- | --- | --- |
| Consolidated per-file decision review | API route tests, fixture DTO tests, WebView smoke, link/file checks | Representative real-media validation if decision logic, stream selection, or planner behavior changes. |
| Planned versus actual output inspection packet | Fixture completed-manifest tests, Local API tests, WebView Completed/Diagnostics smoke | Real-media validation if verifier, output stream policy, publish gate, or sidecar handling changes. |
| Profile compare/export/default review | Config schema tests, settings preview/save tests, Library Profile tests, WebView smoke | Real-media validation before promoting media-policy-affecting profile changes. |
| Track selection review/templates | File override selector tests, WebView drawer smoke | Real-media multi-audio and subtitle validation for any audio/subtitle behavior change. |
| Queue launch scope simulator | Queue/preflight tests, read-only route assertion, WebView Launch/Queue smoke | Real-media validation if launch scope, route, source discovery, pending drain, or worker claim behavior changes. |
| Isolated preview encode | Command/path boundary tests, API command tests, WebView progress/cancel/open smoke | Full high-validation rung with representative real-media samples because FFmpeg/subtitle/audio/temp-output behavior is touched. |
| Runbook/help links | Link/file-existence checks and metadata snapshot tests | Behavior-change validation only if help work changes settings defaults or generated contracts. |

High-validation reminder:

- FFmpeg command generation changes require PowerShell unit validation, tool integration, and representative encode/remux samples.
- Subtitle behavior changes require text, TX3G, BDPGS, ASS/SSA, OCR, sidecar, forced/signs/songs, and failure-review samples where applicable.
- Audio behavior changes require multi-audio, passthrough, transcode, downmix, preferred-language, commentary/descriptive, and no-audio edge cases.
- Publish, pending-publish, source/scratch/output, cleanup, and drain changes require manifest evidence plus representative final/pending publish validation.
- Automated unit tests alone do not prove media behavior. The validation ladder says representative real-media validation is the release gate for these areas.

## 10. Bottom Line

The project already meets or exceeds most HandBrake-like expectations that matter for a Plex-style library pipeline. Its strengths are backend-owned policy, remux/encode routing, source safety, queue/batch operation, failure recovery, logs, final-library workflows, pending-publish safety, and distributed workers.

The best parity work is not to make this behave more like a desktop one-off transcoder. The best work is to make existing policy more inspectable:

1. A consolidated per-file decision review.
2. A planned-versus-actual completed-output inspection packet.
3. Safer profile compare/export/default review.
4. Better track selection review without raw FFmpeg maps.
5. A clear queue launch-scope simulator.

The only direct HandBrake feature gap that is both obvious and expensive is preview encode. It has real operator value, but it crosses the same high-risk boundaries as production FFmpeg/subtitle/audio behavior. It should be treated as a separate, validation-heavy feature, not a casual UI enhancement.
