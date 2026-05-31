# Phase 02 Terminology and Rule Taxonomy Spec

Date: 2026-05-30

Scope: documentation-only terminology and rule taxonomy for the
HandBrake/remux rewrite. This phase does not rename config keys, change runtime
behavior, edit UI code, migrate schema, alter route selection, or touch
FFmpeg/audio/subtitle/publish execution.

## Phase Confirmations

- Approved docs and tracker location: `Docs/rewrite/handbrake-remux/`
- Edit domain for this phase: documentation only in the approved subtree
- High-risk areas touched: yes, conceptually. This spec classifies settings
  related to route decisions, settings schema, FFmpeg/remux/encode, subtitles,
  audio, verification, publish, source/scratch/output movement, and queue
  behavior, but it does not edit those implementations.

## Input Documents Read

- `AGENTS.md`
- `Docs/CURRENT_PROJECT_STATE.md`
- `OPEN_WORK_CHECKLIST.md`
- `Docs/generated/PROJECT_INDEX.md`
- `Docs/audits/latest.md`
- `Docs/rewrite/handbrake-remux/00_execution_tracker.md`
- `Docs/rewrite/handbrake-remux/01_repo_audit.md`
- `C:/Users/lmmye/Downloads/handbrake_remux_rewrite_plan/13_CODEX_MASTER_PROMPT.md`
- `C:/Users/lmmye/Downloads/handbrake_remux_rewrite_plan/00_EXECUTION_ORDER.md`
- `C:/Users/lmmye/Downloads/handbrake_remux_rewrite_plan/02_TERMINOLOGY_AND_RULE_TAXONOMY_SPEC.md`

Current setting names and defaults were checked against
`app/config/metadata_parts/*.py`, `app/contracts/config.py`,
`schemas/config.v1.schema.json`, `engine/config/config_schema.ps1`, and
`Pipeline/Profiles/Default.psd1`.

## Binding Decisions For Later Phases

- Existing config keys remain compatibility keys. Do not rename PSD1/JSON keys
  in Phase 02.
- Display labels may change later only through a display-label layer or UI
  metadata update that preserves the existing backend keys.
- The rewrite must distinguish source facts, user policy, preset policy,
  computed effective values, route decisions, encode command settings,
  verification guards, and publish guards.
- Route representation is per-stream. The coarse route label is derived and is
  not the source of truth.
- Python-owned future decision logic must model current remux codec fallback
  and CPU fallback explicitly. Do not leave those as silent PowerShell-only
  route changes when later phases migrate routing.

## Operator-Accepted Decisions

Accepted by operator reply on 2026-05-30:

- Use `Processing Strategy` as the future display label for `RoutingProfile`.
  `Playback Goal` may appear only as explanatory/help copy.
- Keep `EncodeThresholdGB` and `TVEncodeThresholdGB` as route source-size
  limits. Do not relabel them as target output sizes unless a later phase
  explicitly changes the behavior and adds true output-size target fields.
- Keep old JSON/PSD1 keys as compatibility keys through the rewrite. Phase 05
  may add v2 aliases for cleaner UI/API naming only if needed, but stored
  config compatibility remains required.
- Keep `hevc_nvenc` as the current default. Phase 06 may make codec choice
  preset-driven after the encoding model and tests define preset semantics.

## Rule Tags

| Tag | Meaning | Examples |
| --- | --- | --- |
| `ROUTE` | Decides copy/remux vs encode or reject | copy bitrate cap, H.264 copy eligibility |
| `COMPAT` | Plex/client compatibility policy | allowed codecs, container, dimensions, subtitle compatibility |
| `QUALITY` | Encode quality or compression intent | CQ/CRF, encoder tune profile |
| `SIZE` | Output or source-size budget/expectation | route size limit, growth tolerance |
| `BITRATE` | Bitrate ceiling or target | direct-copy cap, encode target/max |
| `OUTPUT` | Output codec/container/layout | video codec, output container, TV folder layout |
| `DIMENSIONS` | Resolution, crop, scaling, aspect rules | H.264 max height |
| `FILTER` | Image or subtitle text processing | ASS formatting strip, karaoke removal |
| `AUDIO` | Audio stream copy/transcode/default policy | passthrough profile, downmix mode |
| `SUBTITLE` | Subtitle copy/convert/burn/drop policy | TX3G/BDPGS/ASS conversion |
| `VERIFY` | Post-process validation | output probe, duration tolerance, size check |
| `PUBLISH` | Final placement and replacement behavior | deferred publish, promotion verification |
| `ADVISORY` | Warns or informs without blocking | advisory size guard |
| `PROCESS` | Execution scheduling/runtime limits | parallel encode mode, timeouts |
| `SOURCE` | Source discovery or source-readiness policy | file stability, valid extensions |

## Enforcement Types

| Enforcement | Meaning |
| --- | --- |
| `HARD_ROUTE` | Violation changes route, usually copy/remux to encode or reject. |
| `HARD_BLOCK` | Violation blocks publish, fails a job, or holds for manual review. |
| `SOFT_TARGET` | Planning/scoring target that may be exceeded. |
| `ADVISORY` | Warning/report only. |
| `DERIVED` | Computed from source/config and not directly user-set. |
| `CONDITIONAL` | Enforcement depends on another setting, route, source fact, or phase. |

## Value Sources

| Source | Meaning |
| --- | --- |
| `SOURCE_DERIVED` | Detected from ffprobe, filesystem, queue context, or source identity. |
| `USER_CONFIGURABLE` | Persisted config/profile value set by operator. |
| `PRESET_DERIVED` | Derived from a named strategy, preset, ladder, or profile. |
| `COMPUTED_EFFECTIVE` | Read-only effective value after defaults, profile, overrides, and source facts are combined. |

## Route Representation

The authoritative route must be represented as per-stream actions:

| Stream scope | Allowed actions |
| --- | --- |
| Video | `copy`, `encode`, `reject`, `unknown` |
| Each audio track | `copy`, `transcode`, `drop`, `unknown` |
| Each subtitle track | `copy`, `convert`, `burn`, `drop`, `unknown` |
| Container | `keep`, `remux`, `change`, `unknown` |

The UI/log summary label `COPY`, `REMUX`, `ENCODE`, `REJECT`, or `UNKNOWN` is
`DERIVED` from these actions. It must not be used as the only route record
because valid cases can copy video while transcoding audio or converting
subtitles.

## Canonical Vocabulary

| Legacy/current term | Phase 02 display term | Internal concept name | Notes |
| --- | --- | --- | --- |
| Routing profile | Processing Strategy | `processing_strategy` | Accepted future display label. Values stay `RoutingProfile` for compatibility. |
| Playback goal | Playback Goal | `playback_goal` | Explanatory/help-copy synonym only; do not use as the primary settings label. |
| Route threshold mode | Route Enforcement Mode | `route_enforcement_mode` | More precise than generic `Enforcement Mode` because it applies to initial copy/remux-vs-encode routing. |
| Size guard | Output Size Check | `output_size_check` | Post-encode verification/publish guard, not an initial route decision. |
| Encode tuning | Encoder Tune Profile | `encoder_tune_profile` | Avoids conflict with `VideoPreset`, which is the codec speed preset. |
| Encode ladder | Bitrate/Quality Target | `bitrate_quality_target` | Structured target used to choose bitrate/quality defaults. |
| Normal growth percent | Quality-encode size tolerance | `quality_encode_size_tolerance_percent` | Soft size rule for normal quality/bitrate-driven encodes. |
| Compatibility growth percent | Compatibility-encode size tolerance | `compatibility_encode_size_tolerance_percent` | Soft size rule for compatibility-driven encodes. |
| Movie/TV encode threshold GB | Movie/TV route size limit | `movie_route_size_limit_gb`, `tv_route_size_limit_gb` | Current behavior is a route source-size threshold. Do not label as target output size until semantics change. |
| Movie/TV copy max Mbps | Movie/TV max bitrate for direct copy | `movie_direct_copy_max_bitrate_mbps`, `tv_direct_copy_max_bitrate_mbps` | Hard route cap when bitrate enforcement is active. |
| H.264 remux shortcut | Compatible H.264 direct-copy rule | `h264_compat_direct_copy_rule` | H.264-specific compatibility shortcut, not universal remux permission. |
| Video preset | Encoder speed preset | `encoder_speed_preset` | Current `p1` to `p7` NVENC speed/compression control. |
| Video quality | Video quality target | `video_quality_target` | CQ/CRF-like value. |
| Remux-safe codecs | Direct-copy video codec allowlist | `direct_copy_video_codec_allowlist` | Used to decide whether video can stay copied/remuxed. |
| Deferred publish | Park output for later publish | `deferred_publish` | Publish/placement guard, not route or encode policy. |

## Existing Settings Map

The `Legacy key/name` column is the persisted compatibility key. The proposed
display label may be used only in a display-only layer until a later schema
migration is explicitly scoped.

### Routing And Size Policy

| Legacy key/name | Proposed display label | Internal concept | Tags | Enforcement | Affects | Source | Help copy |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `RoutingProfile` / Routing Profile | Processing Strategy | `processing_strategy` | `ROUTE`, `COMPAT`, `SIZE`, `QUALITY` | `CONDITIONAL` | route | `USER_CONFIGURABLE`, `PRESET_DERIVED` | Choose the high-level library policy. Plex-first strategies copy compatible sources and encode only when compatibility, size, bitrate, or explicit policy requires it. |
| `RouteThresholdMode` / Route Threshold Mode | Route Enforcement Mode | `route_enforcement_mode` | `ROUTE`, `SIZE`, `BITRATE`, `COMPAT` | `HARD_ROUTE` or `ADVISORY` depending on value | route | `USER_CONFIGURABLE` | Select which size and bitrate limits are hard route triggers versus advisory scoring inputs. |
| `EncodeThresholdGB` / Movie Encode Threshold (GB) | Movie route size limit (GB) | `movie_route_size_limit_gb` | `ROUTE`, `SIZE` | `CONDITIONAL` | route | `USER_CONFIGURABLE` | Movie source-size limit used by route enforcement. Rename to target output size only after later phases change the semantics. |
| `TVEncodeThresholdGB` / TV Encode Threshold (GB) | TV route size limit (GB) | `tv_route_size_limit_gb` | `ROUTE`, `SIZE` | `CONDITIONAL` | route | `USER_CONFIGURABLE` | TV source-size limit used by route enforcement. Rename to target output size only after later phases change the semantics. |
| `MovieRouteMaxVideoBitrateMbps` / Movie Copy Max Mbps | Movie max bitrate for direct copy | `movie_direct_copy_max_bitrate_mbps` | `ROUTE`, `BITRATE`, `COMPAT` | `HARD_ROUTE` when bitrate applies | route | `USER_CONFIGURABLE` | Highest estimated movie video bitrate eligible for direct copy/remux before encode is selected. |
| `TVRouteMaxVideoBitrateMbps` / TV Copy Max Mbps | TV max bitrate for direct copy | `tv_direct_copy_max_bitrate_mbps` | `ROUTE`, `BITRATE`, `COMPAT` | `HARD_ROUTE` when bitrate applies | route | `USER_CONFIGURABLE` | Highest estimated TV video bitrate eligible for direct copy/remux before encode is selected. |
| `AllowH264RemuxIfPlexCompatible` / Copy Compatible H.264 | Compatible H.264 direct-copy rule | `allow_h264_compatible_direct_copy` | `ROUTE`, `COMPAT` | `CONDITIONAL` | route | `USER_CONFIGURABLE` | Allow H.264/AVC sources to remain copied/remuxed when bitrate, dimensions, and Plex compatibility are acceptable. |
| `H264RemuxMaxBitrateMbps` / H.264 Copy Max Mbps | H.264 direct-copy max bitrate | `h264_direct_copy_max_bitrate_mbps` | `ROUTE`, `BITRATE`, `COMPAT` | `CONDITIONAL` | route | `USER_CONFIGURABLE` | Bitrate ceiling for the H.264 compatibility shortcut and scoring. This is not the universal remux safety limit. |
| `H264RemuxMaxHeight` / H.264 Copy Max Height | H.264 direct-copy max height | `h264_direct_copy_max_height` | `ROUTE`, `DIMENSIONS`, `COMPAT` | `CONDITIONAL` | route | `USER_CONFIGURABLE` | Maximum source height for the H.264 compatibility shortcut; codec-safe fallback may still remux taller sources when hard routing permits. |
| `SizeGuardMode` / Encode Size Guard | Output Size Check | `output_size_check_mode` | `VERIFY`, `SIZE`, `PUBLISH` | `ADVISORY`, `HARD_BLOCK`, or off | verification, publish | `USER_CONFIGURABLE` | Decide whether oversized encoded output warns, blocks publish for review, or skips the growth check. |
| `MaxEncodeGrowthPercent` / Normal Growth Limit % | Quality-encode size tolerance | `quality_encode_size_tolerance_percent` | `VERIFY`, `SIZE` | `SOFT_TARGET` or `HARD_BLOCK` via size check mode | verification, publish | `USER_CONFIGURABLE` | Allowed size growth for normal quality/bitrate-driven encodes before the output size check warns or blocks. |
| `CompatibilityEncodeGrowthPercent` / Compatibility Growth Limit % | Compatibility-encode size tolerance | `compatibility_encode_size_tolerance_percent` | `VERIFY`, `SIZE`, `COMPAT` | `SOFT_TARGET` or `HARD_BLOCK` via size check mode | verification, publish | `USER_CONFIGURABLE` | Allowed size growth when encoding to satisfy compatibility policy before the output size check warns or blocks. |
| `OutputSizeMultiplier` / Output Size Multiplier | Route output-size safety multiplier | `route_output_size_multiplier` | `ROUTE`, `SIZE`, `VERIFY` | `CONDITIONAL` | route, verification | `USER_CONFIGURABLE` | Advanced multiplier used by route validation and size safety calculations. |
| `ShowOverrides` / direct config only | Per-show policy overrides | `show_policy_overrides` | `ROUTE`, `COMPAT`, `QUALITY`, `AUDIO`, `SUBTITLE` | `CONDITIONAL` | route, encode command | `USER_CONFIGURABLE` | Advanced per-show overrides. Keep direct-config-only until a future structured editor is explicitly scoped. |

### Video, Encode, And Remux Policy

| Legacy key/name | Proposed display label | Internal concept | Tags | Enforcement | Affects | Source | Help copy |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `VideoCodec` / Hardware / Codec | Video encoder | `video_encoder` | `OUTPUT`, `QUALITY`, `COMPAT` | `HARD_ROUTE` when source requires encode | encode command | `USER_CONFIGURABLE` | Encoder used when the plan chooses video encode. Copy/remux plans do not imply a video re-encode. |
| `VideoPreset` / Preset | Encoder speed preset | `encoder_speed_preset` | `QUALITY`, `PROCESS` | `SOFT_TARGET` | encode command | `USER_CONFIGURABLE` | Speed/compression preset for the selected encoder. Faster is more responsive; slower usually compresses better. |
| `VideoQuality` / Quality | Video quality target | `video_quality_target` | `QUALITY`, `SIZE` | `SOFT_TARGET` | encode command, verification | `USER_CONFIGURABLE` | CQ/CRF-style quality target. Lower is cleaner and larger; higher is smaller and softer. |
| `OutputContainer` / Container | Encoded output container | `encoded_output_container` | `OUTPUT`, `COMPAT` | `CONDITIONAL` | encode command, publish | `USER_CONFIGURABLE` | Container for encoded outputs. Later planner work must clarify whether remux container changes use this or a separate remux target. |
| `EncodeTuningPreset` / Encode Tuning Preset | Encoder Tune Profile | `encoder_tune_profile` | `QUALITY`, `COMPAT`, `OUTPUT` | `SOFT_TARGET` | encode command | `USER_CONFIGURABLE`, `PRESET_DERIVED` | Named encoder flag profile. Use custom legacy flags only when intentionally preserving raw FFmpeg/NVENC arguments. |
| `EncodeLadder` / Encode Ladder | Bitrate/Quality Target | `bitrate_quality_target` | `QUALITY`, `BITRATE`, `SIZE`, `COMPAT` | `SOFT_TARGET` | encode command, verification | `USER_CONFIGURABLE`, `PRESET_DERIVED` | Structured target for bitrate and quality. Auto chooses TV or movie defaults; Plex compatibility chooses conservative targets. |
| `ExtraVideoFlags` / Legacy Extra Video Flags | Advanced encoder flags | `advanced_encoder_flags` | `OUTPUT`, `QUALITY` | `CONDITIONAL` | encode command | `USER_CONFIGURABLE` | Raw FFmpeg/NVENC flags preserved for legacy configs or custom expert use. Keep hidden behind advanced controls. |
| `RemuxSafeVideoCodecs` / Remux-Safe Video Codecs | Direct-copy video codec allowlist | `direct_copy_video_codec_allowlist` | `ROUTE`, `COMPAT`, `OUTPUT` | `HARD_ROUTE` | route | `USER_CONFIGURABLE` | Codecs eligible for direct video copy/remux. Unsafe codecs must route to encode or review. |
| `FallbackCpuQuality` / CPU Fallback Quality | CPU fallback quality target | `cpu_fallback_quality_target` | `QUALITY`, `PROCESS`, `VERIFY` | `CONDITIONAL` | encode command, verification | `USER_CONFIGURABLE`, `COMPUTED_EFFECTIVE` | Quality target used when GPU encoding falls back to CPU. It is libx265 CRF, not NVENC CQ. |
| `CpuEncodePreset` / CPU Encode Preset | CPU encoder speed preset | `cpu_encoder_speed_preset` | `QUALITY`, `PROCESS` | `SOFT_TARGET` | encode command | `USER_CONFIGURABLE` | libx265 preset for CPU primary or fallback encodes. Slower presets can run for many hours. |
| `CpuEncodeProcessPriority` / CPU Encode Process Priority | CPU encode process priority | `cpu_encode_process_priority` | `PROCESS` | `ADVISORY` operational limit | encode command | `USER_CONFIGURABLE` | Windows process priority applied to ffmpeg during CPU encode. Lower priorities keep the desktop more responsive. |
| `CpuEncodeMaxThreads` / CPU Encode Max Threads | CPU encode thread cap | `cpu_encode_max_threads` | `PROCESS`, `QUALITY` | `SOFT_TARGET` | encode command | `USER_CONFIGURABLE` | Maximum libx265 threads. 0 means autodetect; positive values cap CPU pressure. |
| `FFmpegEncodeTimeoutSeconds` / Encode Timeout (s) | GPU encode timeout | `ffmpeg_encode_timeout_seconds` | `PROCESS`, `VERIFY` | `HARD_BLOCK` | encode command, verification | `USER_CONFIGURABLE` | Wall-clock limit for standard ffmpeg encode jobs. Expiry should fail/hold rather than publish unverified output. |
| `FFmpegCpuEncodeTimeoutSeconds` / CPU Encode Timeout (seconds) | CPU encode timeout | `ffmpeg_cpu_encode_timeout_seconds` | `PROCESS`, `VERIFY` | `HARD_BLOCK` | encode command, verification | `USER_CONFIGURABLE` | Wall-clock limit for CPU encode jobs, which can run much longer than GPU encodes. |
| `FFmpegRemuxTimeoutSeconds` / Remux Timeout (s) | FFmpeg remux timeout | `ffmpeg_remux_timeout_seconds` | `PROCESS`, `VERIFY` | `HARD_BLOCK` | remux command, verification | `USER_CONFIGURABLE` | Wall-clock limit for ffmpeg remux steps. Expiry must fail/hold instead of publishing partial output. |
| `MkvmergeRemuxTimeoutSeconds` / Mkvmerge Remux Timeout (seconds) | Mkvmerge remux timeout | `mkvmerge_remux_timeout_seconds` | `PROCESS`, `VERIFY` | `HARD_BLOCK` | remux command, verification | `USER_CONFIGURABLE` | Wall-clock limit for mkvmerge remux work, especially large MKVs over slow scratch/output volumes. |
| `MaxParallelEncodes` / direct config | Local encode worker limit | `max_parallel_encodes` | `PROCESS` | `CONDITIONAL` | queue, encode command | `USER_CONFIGURABLE` | Maximum local parallel encodes. Values above 1 require an explicitly compatible parallel encode mode and hardware capacity. |
| `ParallelEncodeMode` / direct config | Parallel encode mode | `parallel_encode_mode` | `PROCESS`, `ROUTE` | `CONDITIONAL` | queue, encode command | `USER_CONFIGURABLE` | Controls whether local worker-slot scheduling is allowed. Keep disabled unless the operator has validated hardware, scratch, and share pressure. |

### Audio Policy

| Legacy key/name | Proposed display label | Internal concept | Tags | Enforcement | Affects | Source | Help copy |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `AudioPassthroughProfile` / Audio Passthrough Profile | Audio passthrough policy | `audio_passthrough_policy` | `AUDIO`, `COMPAT`, `ROUTE` | `CONDITIONAL` | per-stream audio action, encode/remux command | `USER_CONFIGURABLE`, `PRESET_DERIVED` | Choose which audio codecs can be copied. Tracks outside the policy are normalized or held according to audio rules. |
| `CompatibleAudioCodecs` / Custom Audio Passthrough Codecs | Custom audio passthrough codecs | `custom_audio_passthrough_codecs` | `AUDIO`, `COMPAT` | `CONDITIONAL` | per-stream audio action | `USER_CONFIGURABLE` | Manual codec allowlist used only by the custom passthrough profile. Structured profiles should populate it on save. |
| `PreferredDefaultAudioLanguages` / Preferred Default Audio Languages | Default audio language priority | `preferred_default_audio_languages` | `AUDIO`, `COMPAT` | `SOFT_TARGET` | per-stream audio action | `USER_CONFIGURABLE` | Ordered language preference for selecting the default audio track before falling back to highest-fidelity non-commentary audio. |
| `AudioTranscodeCodec` / Transcode Codec | Audio transcode codec | `audio_transcode_codec` | `AUDIO`, `OUTPUT`, `COMPAT` | `CONDITIONAL` | per-stream audio action, encode/remux command | `USER_CONFIGURABLE` | Codec used when an audio track must be normalized instead of copied. |
| `AudioTranscodeBitrate` / Transcode Bitrate | Audio transcode bitrate | `audio_transcode_bitrate` | `AUDIO`, `BITRATE`, `SIZE` | `SOFT_TARGET` | encode/remux command, verification | `USER_CONFIGURABLE` | Bitrate for normalized audio tracks when automatic per-channel bitrate is disabled. |
| `AudioTranscodeAutoBitrateByChannels` / Auto Bitrate by Channels | Auto audio bitrate by channels | `audio_auto_bitrate_by_channels` | `AUDIO`, `BITRATE`, `SIZE` | `SOFT_TARGET` | encode/remux command | `USER_CONFIGURABLE`, `COMPUTED_EFFECTIVE` | Choose audio bitrate from codec and channel count rather than one static bitrate. |
| `AudioDownmixMode` / Downmix Mode | Audio downmix policy | `audio_downmix_policy` | `AUDIO`, `COMPAT` | `CONDITIONAL` | per-stream audio action, encode/remux command | `USER_CONFIGURABLE` | Control whether transcoded audio caps channels, preserves channels, or forces stereo. |
| `AudioMaxChannels` / Max Channels | Audio max channels | `audio_max_channels` | `AUDIO`, `COMPAT` | `CONDITIONAL` | encode/remux command | `USER_CONFIGURABLE` | Maximum channel count when the downmix policy caps channels. |
| `AllowNoAudio` / Allow No-Audio Outputs | Allow silent outputs | `allow_no_audio_outputs` | `AUDIO`, `VERIFY`, `PUBLISH` | `HARD_BLOCK` when false | verification, publish | `USER_CONFIGURABLE` | Permit processing of silent source files. Keep disabled for normal Plex media so missing audio is held for review. |

### Subtitle Policy

| Legacy key/name | Proposed display label | Internal concept | Tags | Enforcement | Affects | Source | Help copy |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `SubKeepLanguages` / Subtitle Languages | Subtitle language keep list | `subtitle_keep_languages` | `SUBTITLE`, `COMPAT` | `CONDITIONAL` | per-stream subtitle action | `USER_CONFIGURABLE` | Languages eligible to keep, copy, or convert during subtitle processing. |
| `ConvertTx3gToSrt` / Convert TX3G to SRT | Convert TX3G to SRT | `convert_tx3g_to_srt` | `SUBTITLE`, `COMPAT`, `OUTPUT` | `CONDITIONAL` | per-stream subtitle action, command | `USER_CONFIGURABLE` | Convert MP4 Timed Text/mov_text subtitles to SRT during output muxing. |
| `DropTx3gAfterConversion` / Drop TX3G After Conversion | Drop original TX3G after conversion | `drop_tx3g_after_conversion` | `SUBTITLE`, `OUTPUT` | `CONDITIONAL` | per-stream subtitle action | `USER_CONFIGURABLE` | Drop original TX3G after SRT conversion when enabled; otherwise preserve it when the container supports it. |
| `CreateExternalTx3gSrtSidecars` / Write TX3G SRT Sidecars | Write TX3G SRT sidecars | `create_external_tx3g_srt_sidecars` | `SUBTITLE`, `PUBLISH`, `OUTPUT` | `CONDITIONAL` | command, publish | `USER_CONFIGURABLE` | Also write TX3G-derived external SRT files next to output while keeping converted tracks muxed when enabled. |
| `Tx3gExtractLanguages` / TX3G Extract Languages | TX3G extract language list | `tx3g_extract_languages` | `SUBTITLE`, `COMPAT` | `CONDITIONAL` | per-stream subtitle action | `USER_CONFIGURABLE` | Language tags eligible for TX3G-to-SRT extraction. Undefined tracks use `und`. |
| `Tx3gPreserveExistingSrt` / Preserve Existing TX3G SRTs | Preserve existing TX3G SRT sidecars | `tx3g_preserve_existing_srt` | `SUBTITLE`, `PUBLISH` | `CONDITIONAL` | command, publish | `USER_CONFIGURABLE` | Leave matching external SRT files in place unless explicit full reprocessing is active. |
| `Tx3gTreatForcedAsSeparate` / Separate Forced TX3G | Separate forced TX3G sidecars | `tx3g_treat_forced_as_separate` | `SUBTITLE`, `OUTPUT` | `CONDITIONAL` | command, publish | `USER_CONFIGURABLE` | Include forced status in TX3G SRT filenames so forced and full subtitles do not collide. |
| `ConvertBdpgsToSrt` / OCR BDPGS to SRT | OCR BDPGS to SRT | `convert_bdpgs_to_srt` | `SUBTITLE`, `COMPAT`, `OUTPUT` | `CONDITIONAL` | per-stream subtitle action, command | `USER_CONFIGURABLE` | OCR Blu-ray PGS image subtitles to SRT using the configured external tool. Failures must route to review. |
| `DropBdpgsAfterConversion` / Drop BDPGS After OCR | Drop original BDPGS after OCR | `drop_bdpgs_after_conversion` | `SUBTITLE`, `OUTPUT` | `CONDITIONAL` | per-stream subtitle action | `USER_CONFIGURABLE` | Drop original BDPGS after successful OCR when enabled; otherwise keep the image subtitle track. |
| `BdpgsExtractLanguages` / BDPGS OCR Languages | BDPGS OCR language list | `bdpgs_extract_languages` | `SUBTITLE`, `COMPAT` | `CONDITIONAL` | per-stream subtitle action, command | `USER_CONFIGURABLE` | Language tags eligible for BDPGS OCR. Undefined tracks use `und`. |
| `BdpgsOcrToolPath` / BDPGS OCR Tool | BDPGS OCR tool path | `bdpgs_ocr_tool_path` | `SUBTITLE`, `PROCESS` | `HARD_BLOCK` when OCR is required and unavailable | command | `USER_CONFIGURABLE` | Path to the OCR executable or DLL used for BDPGS conversion. Relative paths resolve from the Pipeline folder. |
| `BdpgsOcrTessdataPath` / BDPGS Tessdata | BDPGS OCR tessdata path | `bdpgs_ocr_tessdata_path` | `SUBTITLE`, `PROCESS` | `CONDITIONAL` | command | `USER_CONFIGURABLE` | Optional Tesseract tessdata folder for BDPGS OCR. |
| `BdpgsOcrTimeoutSeconds` / BDPGS OCR Timeout (s) | BDPGS OCR timeout | `bdpgs_ocr_timeout_seconds` | `SUBTITLE`, `PROCESS`, `VERIFY` | `HARD_BLOCK` | command, verification | `USER_CONFIGURABLE` | Wall-clock limit for external BDPGS OCR commands. Timeout must hold/review rather than silently publish bad subtitles. |
| `DropAssAfterConversion` / Drop ASS After Conversion | Drop original ASS after conversion | `drop_ass_after_conversion` | `SUBTITLE`, `OUTPUT` | `CONDITIONAL` | per-stream subtitle action | `USER_CONFIGURABLE` | Remove the original ASS/SSA track after successful SRT conversion when enabled. |
| `RemoveKaraoke` / Filter Karaoke Styling | Remove karaoke subtitle events | `remove_karaoke_subtitle_events` | `SUBTITLE`, `FILTER` | `CONDITIONAL` | subtitle conversion command | `USER_CONFIGURABLE` | Exclude karaoke-style events during ASS/SSA to SRT conversion. |
| `KeepSignsAndSongs` / Keep Signs & Songs | Keep supplemental subtitle tracks | `keep_supplemental_subtitle_tracks` | `SUBTITLE`, `COMPAT` | `CONDITIONAL` | per-stream subtitle action | `USER_CONFIGURABLE` | Preserve signs/songs/supplemental subtitle tracks separately instead of treating them as disposable noise. |
| `TreatAssSignsSongsAsForced` / ASS Signs/Songs Forced | Mark ASS signs/songs as forced | `treat_ass_signs_songs_as_forced` | `SUBTITLE`, `OUTPUT` | `CONDITIONAL` | per-stream subtitle action | `USER_CONFIGURABLE` | Mark kept or converted ASS/SSA supplemental tracks as forced. |
| `TreatTx3gSignsSongsAsForced` / TX3G Signs/Songs Forced | Mark TX3G signs/songs as forced | `treat_tx3g_signs_songs_as_forced` | `SUBTITLE`, `OUTPUT` | `CONDITIONAL` | per-stream subtitle action | `USER_CONFIGURABLE` | Mark converted TX3G supplemental tracks as forced. |
| `TreatBdpgsSignsSongsAsForced` / BDPGS Signs/Songs Forced | Mark BDPGS signs/songs as forced | `treat_bdpgs_signs_songs_as_forced` | `SUBTITLE`, `OUTPUT` | `CONDITIONAL` | per-stream subtitle action | `USER_CONFIGURABLE` | Mark kept or OCR-converted BDPGS supplemental tracks as forced. |
| `StripFormatting` / Strip ASS Formatting | Strip ASS formatting | `strip_ass_formatting` | `SUBTITLE`, `FILTER` | `CONDITIONAL` | subtitle conversion command | `USER_CONFIGURABLE` | Remove inline ASS formatting when converting to SRT. |
| `MergeAdjacent` / Merge Adjacent Cues | Merge adjacent subtitle cues | `merge_adjacent_subtitle_cues` | `SUBTITLE`, `FILTER` | `CONDITIONAL` | subtitle conversion command | `USER_CONFIGURABLE` | Merge nearby subtitle cues separated by very small gaps. |
| `MergeThresholdMs` / Subtitle Merge Threshold (ms) | Subtitle merge gap threshold | `subtitle_merge_threshold_ms` | `SUBTITLE`, `FILTER` | `SOFT_TARGET` | subtitle conversion command | `USER_CONFIGURABLE` | Maximum cue gap, in milliseconds, eligible for adjacent merge logic. |
| `SubSDHTitleKeywords` / SDH Title Keywords | SDH subtitle title keywords | `sdh_subtitle_title_keywords` | `SUBTITLE`, `COMPAT` | `CONDITIONAL` | per-stream subtitle action | `USER_CONFIGURABLE` | Keywords used to identify SDH/hearing-impaired subtitle tracks. |
| `SubSupplementalKeywords` / Supplemental Title Keywords | Supplemental subtitle title keywords | `supplemental_subtitle_title_keywords` | `SUBTITLE`, `COMPAT` | `CONDITIONAL` | per-stream subtitle action | `USER_CONFIGURABLE` | Keywords used to identify signs, songs, karaoke, and other supplemental subtitle tracks. |
| `ExcludeSubtitleStyles` / Excluded Subtitle Styles | Excluded ASS subtitle styles | `excluded_subtitle_styles` | `SUBTITLE`, `FILTER` | `CONDITIONAL` | subtitle conversion command | `USER_CONFIGURABLE` | ASS style names or patterns to filter out during conversion. |
| `IncludeSubtitleStyles` / Included Subtitle Styles | Included ASS subtitle styles | `included_subtitle_styles` | `SUBTITLE`, `FILTER` | `CONDITIONAL` | subtitle conversion command | `USER_CONFIGURABLE` | Optional allowlist of ASS style names or patterns to keep during conversion. |

### Verification, Publish, And File-Safety Policy

| Legacy key/name | Proposed display label | Internal concept | Tags | Enforcement | Affects | Source | Help copy |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `OutputValidationProbeTimeoutSeconds` / direct config | Output validation probe timeout | `output_validation_probe_timeout_seconds` | `VERIFY`, `PROCESS` | `HARD_BLOCK` | verification, publish | `USER_CONFIGURABLE` | Timeout for output probing during validation. Failure must hold/review instead of publishing unverified output. |
| `OutputValidationMinSizeBytes` / direct config | Minimum valid output size | `output_validation_min_size_bytes` | `VERIFY`, `SIZE` | `HARD_BLOCK` | verification, publish | `USER_CONFIGURABLE` | Minimum byte size for a valid output artifact. Smaller outputs are treated as failed or review-only. |
| `OutputValidationDurationToleranceSeconds` / direct config | Output duration tolerance | `output_validation_duration_tolerance_seconds` | `VERIFY` | `HARD_BLOCK` | verification, publish | `USER_CONFIGURABLE` | Allowed duration difference between source and output before validation fails or holds for review. |
| `EnableIntegrityCheck` / Enable Integrity Check | Source integrity preflight | `source_integrity_preflight_enabled` | `SOURCE`, `VERIFY` | `HARD_BLOCK` when enabled and failing | route, verification | `USER_CONFIGURABLE` | Probe source media before processing so corrupt or incomplete files are held back. |
| `FileStabilityWait` / direct config | Source stability wait | `source_stability_wait_seconds` | `SOURCE`, `PROCESS` | `HARD_BLOCK` when source is unstable | route | `USER_CONFIGURABLE` | Wait period for source file stability before processing begins. |
| `SkipStabilityCheck` / direct config | Skip source stability check | `skip_source_stability_check` | `SOURCE`, `PROCESS` | `CONDITIONAL` | route | `USER_CONFIGURABLE` | Developer/test escape hatch. Keep off for normal library operation. |
| `ValidExtensions` / Valid Media Extensions | Source media extensions | `source_media_extensions` | `SOURCE`, `ROUTE` | `HARD_ROUTE` discovery eligibility | route, queue | `USER_CONFIGURABLE` | File extensions considered source media candidates during discovery. |
| `MinFreeSpaceGB` / Scratch Free Space Reserve (GB) | Scratch free-space reserve | `scratch_free_space_reserve_gb` | `SOURCE`, `PROCESS`, `VERIFY` | `HARD_BLOCK` | route, command | `USER_CONFIGURABLE` | Required scratch free-space reserve before copy/remux/encode work proceeds. |
| `OutsourceMinFreeSpaceGB` / Output Free Space Reserve (GB) | Output free-space reserve | `output_free_space_reserve_gb` | `PUBLISH`, `VERIFY` | `HARD_BLOCK` or pending publish park | publish | `USER_CONFIGURABLE` | Required output destination reserve. Unsafe final output must park through pending publish rather than bypass safety. |
| `RobocopyFlags` / Robocopy Flags | Copy transfer flags | `copy_transfer_flags` | `SOURCE`, `PUBLISH`, `PROCESS` | `CONDITIONAL` | command, publish | `USER_CONFIGURABLE` | Robocopy flags for source-to-scratch and scratch-to-output transfer. Keep retries/waits/logging explicit. |
| `RobocopyTimeoutSeconds` / Copy Timeout (s) | Copy transfer timeout | `copy_transfer_timeout_seconds` | `SOURCE`, `PUBLISH`, `PROCESS` | `HARD_BLOCK` | command, publish | `USER_CONFIGURABLE` | Wall-clock limit for robocopy source, scratch, and publish transfers. |
| `TransientFailureRetryLimit` / Transient Failure Retry Limit | Transient failure retry limit | `transient_failure_retry_limit` | `VERIFY`, `PROCESS` | `HARD_BLOCK` after limit | verification, queue | `USER_CONFIGURABLE` | Number of repeated transient failures before escalation to operator-required review. |
| `DeferredPublish` / Deferred Publish | Park output for later publish | `deferred_publish` | `PUBLISH`, `VERIFY` | `HARD_BLOCK` to final publish until drained | publish | `USER_CONFIGURABLE` | Park completed outputs locally instead of publishing immediately; drain later with manifest evidence. |
| `FinalLibraryPromotionEnabled` / Enable Promotion | Enable final library promotion | `final_library_promotion_enabled` | `PUBLISH` | `CONDITIONAL` | publish | `USER_CONFIGURABLE` | Expose manual promotion from completed publish output to the final library. |
| `FinalLibraryPromotionRules` / Source to Destination Rules | Final library promotion rules | `final_library_promotion_rules` | `PUBLISH`, `OUTPUT` | `CONDITIONAL` | publish | `USER_CONFIGURABLE` | JSON rule list mapping source/output roots to final library destinations. Longest matching root wins. |
| `FinalLibraryPromotionVerificationMode` / Verification Mode | Final library promotion verification | `final_library_promotion_verification_mode` | `PUBLISH`, `VERIFY` | `HARD_BLOCK` when verification fails | publish | `USER_CONFIGURABLE` | Choose cautious hash-and-size verification or faster destination/size verification for final library promotion. |
| `FinalLibraryPromotionCleanupAfterVerified` / Cleanup After Verified | Cleanup promoted publish output | `final_library_promotion_cleanup_after_verified` | `PUBLISH`, `SOURCE` | `HARD_BLOCK` unless verified | publish | `USER_CONFIGURABLE` | After verified promotion, delete only copied publish-output files and empty folders under the publish output root. |
| `FinalLibraryPromotionOverwriteExisting` / Overwrite Existing Final Files | Overwrite existing final files | `final_library_promotion_overwrite_existing` | `PUBLISH` | `HARD_BLOCK` unless explicitly enabled | publish | `USER_CONFIGURABLE` | Destructive final-library overwrite toggle. Must remain explicit and backend-owned. |

### Library, Source Identity, And Queue Context

| Legacy key/name | Proposed display label | Internal concept | Tags | Enforcement | Affects | Source | Help copy |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `LibraryProfiles` / Library Profiles | Library policy profiles | `library_policy_profiles` | `ROUTE`, `OUTPUT`, `AUDIO`, `SUBTITLE`, `PUBLISH` | `CONDITIONAL` | route, encode command, publish | `USER_CONFIGURABLE`, `PRESET_DERIVED` | Per-library source, output, designation, promotion destination, and explicit editor/video/subtitle/audio overrides. |
| `SourceMovies` / Movies Source | Movie source root | `movie_source_root` | `SOURCE` | `HARD_ROUTE` discovery scope | route, queue | `USER_CONFIGURABLE` | Folder scanned for incoming movie files. Not an encoding policy knob. |
| `SourceTV` / TV Source | TV source root | `tv_source_root` | `SOURCE` | `HARD_ROUTE` discovery scope | route, queue | `USER_CONFIGURABLE` | Folder scanned for incoming TV files. Not an encoding policy knob. |
| `Outsource` / Final Output | Publish output root | `publish_output_root` | `OUTPUT`, `PUBLISH` | `HARD_BLOCK` when unsafe | publish | `USER_CONFIGURABLE` | Processed output destination. Unsafe final placement must use pending publish parking. |
| `LocalBase` / Scratch Disk | Scratch workspace root | `scratch_workspace_root` | `SOURCE`, `PROCESS` | `HARD_BLOCK` when unavailable/unsafe | command | `USER_CONFIGURABLE` | Local working directory for source copies, remuxes, encodes, sidecars, and runtime state. |
| `CreateTVSubfolder` / Create TV Library Folders | TV output folder layout | `create_tv_output_subfolders` | `OUTPUT`, `PUBLISH` | `CONDITIONAL` | publish | `USER_CONFIGURABLE` | Place TV outputs under Plex-style show and season folders when enabled. |
| `AggressiveEpisodeParsing` / Aggressive Episode Parsing | Expanded episode identity parsing | `aggressive_episode_identity_parsing` | `SOURCE`, `OUTPUT` | `CONDITIONAL` | route, publish | `USER_CONFIGURABLE`, `COMPUTED_EFFECTIVE` | Use folder and loose filename hints to build episode identity when strict parsing fails. |
| `ReprocessAll` / Force One Reprocess Pass | Force one reprocess pass | `force_one_reprocess_pass` | `SOURCE`, `ROUTE`, `PROCESS` | `HARD_ROUTE` queue eligibility | queue, route | `USER_CONFIGURABLE` | Reconsider previously completed outputs for one deliberate pass. Use only for planned rerun testing. |
| `CleanupRemoteStaging` / Clean Remote Staging | Clean remote staging artifacts | `cleanup_remote_staging_enabled` | `SOURCE`, `PUBLISH`, `PROCESS` | `HARD_BLOCK` unless enabled | command, publish | `USER_CONFIGURABLE` | Allow cleanup scans against remote output paths. Keep disabled for normal daily use. |
| `CleanupStaleAgeHours` / Cleanup Age (h) | Cleanup stale artifact age | `cleanup_stale_age_hours` | `SOURCE`, `PUBLISH`, `PROCESS` | `HARD_BLOCK` before age | command, publish | `USER_CONFIGURABLE` | Minimum age before partial/staging artifacts can be cleaned by startup cleanup. |

## Source-Derived And Computed Terms

These are not config keys, but later phases should expose them separately from
desired output settings.

| Term | Internal concept | Tags | Enforcement | Source | Help copy |
| --- | --- | --- | --- | --- | --- |
| Source codec | `source_video_codec`, `source_audio_codecs`, `source_subtitle_codecs` | `SOURCE`, `COMPAT`, `ROUTE` | `DERIVED` | `SOURCE_DERIVED` | Detected stream codecs from probe data. These are facts, not desired output settings. |
| Source container | `source_container` | `SOURCE`, `COMPAT`, `OUTPUT` | `DERIVED` | `SOURCE_DERIVED` | Detected input container used to decide keep/remux/change actions. |
| Source duration | `source_duration_seconds` | `SOURCE`, `VERIFY` | `DERIVED` | `SOURCE_DERIVED` | Probe-derived duration used for route evidence and output validation. |
| Source size | `source_size_bytes` | `SOURCE`, `SIZE`, `ROUTE` | `DERIVED` | `SOURCE_DERIVED` | Filesystem source size used by route size limits and evidence. |
| Estimated video bitrate | `estimated_source_video_bitrate_mbps` | `SOURCE`, `BITRATE`, `ROUTE` | `DERIVED` | `SOURCE_DERIVED`, `COMPUTED_EFFECTIVE` | Estimated source bitrate used by direct-copy caps and compatibility scoring. |
| Source dimensions | `source_width`, `source_height` | `SOURCE`, `DIMENSIONS`, `COMPAT` | `DERIVED` | `SOURCE_DERIVED` | Probe dimensions used for compatibility and H.264 shortcut decisions. |
| Media type | `media_type` | `SOURCE`, `ROUTE`, `SIZE` | `DERIVED` | `SOURCE_DERIVED`, `COMPUTED_EFFECTIVE` | Movie/TV classification used to choose the applicable route size and bitrate limits. |
| Effective policy | `effective_processing_policy` | all policy tags | `DERIVED` | `COMPUTED_EFFECTIVE` | Read-only merge of defaults, library profile, show overrides, file overrides, and user settings. |
| Processing decision | `processing_decision` | all route tags | `DERIVED` | `COMPUTED_EFFECTIVE` | Per-stream action set plus reasons produced by the future Python decision engine. |
| Route summary label | `route_summary_label` | `ROUTE` | `DERIVED` | `COMPUTED_EFFECTIVE` | Display/log label derived from per-stream actions. It is not authoritative by itself. |

## Labels That Can Change Versus Keys That Must Remain

Can change in a future display-only/UI metadata phase after human approval:

- `RoutingProfile` label to `Processing Strategy`; `Playback Goal` may be
  explanatory/help copy only.
- `RouteThresholdMode` label to `Route Enforcement Mode`.
- `SizeGuardMode` label to `Output Size Check`.
- `EncodeTuningPreset` label to `Encoder Tune Profile`.
- `EncodeLadder` label to `Bitrate/Quality Target`.
- `MaxEncodeGrowthPercent` label to `Quality-encode size tolerance`.
- `CompatibilityEncodeGrowthPercent` label to
  `Compatibility-encode size tolerance`.
- `MovieRouteMaxVideoBitrateMbps` and `TVRouteMaxVideoBitrateMbps` labels to
  max bitrate for direct copy.
- `RemuxSafeVideoCodecs` label to `Direct-copy video codec allowlist`.

Must remain compatibility keys until a later versioned migration phase:

- Every PSD1/JSON key listed in this spec.
- Existing enum slugs such as `plex_direct_stream`,
  `compatibility_advisory`, `balanced_nvenc`, `auto`, `advisory`, and
  `strict`.
- Existing legacy raw flags key `ExtraVideoFlags`.
- Existing local runtime profile keys under `Pipeline/Profiles/Default.psd1`
  and `Pipeline/MediaPipeline_config_*.psd1`.

Do not introduce v2 config keys, migration aliases, or runtime key renames in
Phase 02.

## Product Decisions

| Question | Accepted direction | Status | Blocking phase |
| --- | --- | --- | --- |
| Preferred user-facing label for `RoutingProfile` | Use `Processing Strategy` for settings. Use `Playback Goal` only as explanatory/help copy. | Accepted 2026-05-30 | Phase 08 |
| Meaning of `EncodeThresholdGB` and `TVEncodeThresholdGB` | Keep as route source-size limits. Add separate output-size target fields later only if behavior changes. | Accepted 2026-05-30 | Phase 04/06 |
| Old JSON/PSD1 key policy | Keep existing keys as compatibility keys through the rewrite. Phase 05 may add v2 aliases only if needed. | Accepted 2026-05-30 | Phase 05 |
| HEVC default | Keep `hevc_nvenc` as the current default. Phase 06 may make codec choice preset-driven after model/test coverage exists. | Accepted 2026-05-30 | Phase 06 |
| Output container semantics | Keep current encoded-output meaning until `PipelinePlan` separates container actions. | Open | Phase 07 |
| CPU fallback ownership | Model CPU fallback in Python decision/plan records, as operator decided on 2026-05-30. | Accepted 2026-05-30 | Phase 04/07 |
| Remux codec fallback ownership | Model remux codec fallback in Python decision/plan records, as operator decided on 2026-05-30. | Accepted 2026-05-30 | Phase 04/07 |
| Subtitle burn-in vocabulary | Keep `burn` in the route model vocabulary but mark as future/unknown unless implementation exists. | Open | Phase 04/08 |
| `FinalLibraryPromotion*` in rewrite UI | Keep separate from encode settings but classify under publish guards for terminology consistency. | Open | Phase 08/09 |

## Phase 02 Acceptance Notes

- Threshold terminology is resolved by separating current route size limits
  from future output-size targets.
- Advisory, soft target, hard route, and hard block enforcement are explicit.
- Route decisions, encode command settings, verification checks, and publish
  guards are separate in the map.
- Legacy config keys and enum slugs remain unchanged.
- Operator accepted the Phase 02 choices for `Processing Strategy`,
  route source-size limits, legacy key compatibility, and the current HEVC
  default on 2026-05-30.
- No display-label module was added because a docs-only phase avoids touching
  settings schema/UI surfaces before human term approval.
