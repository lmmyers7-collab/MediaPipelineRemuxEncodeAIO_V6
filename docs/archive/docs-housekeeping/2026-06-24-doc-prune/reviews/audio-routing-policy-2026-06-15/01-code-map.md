# Audio Routing Code Map

## Runtime Audio Owner

The current mutation path is PowerShell-owned.

- `ops/pipeline/engine/audio/audio.ps1`
  - Normalizes preferred audio languages at lines 20-54.
  - Resolves transcode codec/bitrate at lines 98-117.
  - Resolves downmix, channel cap, no-audio, output container, passthrough profile, and compatible codecs at lines 175-280.
  - Builds FFmpeg audio args, sidecar records, dispositions, and runtime progress at lines 373-590.
- `ops/pipeline/engine/audio/audio/stream_decisions.ps1`
  - Builds pure audio stream decisions before FFmpeg argument emission.
  - Chooses output channel count at lines 9-21.
  - Chooses default audio track at lines 24-57.
  - Chooses MP4 single-audio source at lines 80-138.
  - Applies file override drops, MP4 drops, transcode/copy, metadata, records, and default dispositions at lines 162-454.
- `ops/pipeline/entrypoints/MediaPipeline/remux.ps1`
  - Calls `Build-AudioArgs` during remux preparation at lines 160-176.
  - Uses `Get-MkvmergeAudioTids` and `--default-track` to stamp explicit audio defaults at lines 326-343.
- `ops/pipeline/entrypoints/MediaPipeline/encode.ps1`
  - Calls `Build-AudioArgs` during encode preparation at lines 128-145.
- `ops/pipeline/engine/subtitles/builders.ps1`
  - Provides `Get-MkvmergeAudioTids`, returning audio TIDs in input order and warning/falling back when mkvmerge probing fails, at lines 131-155.

## Runtime Config And Profile Ownership

- `ops/pipeline/engine/config/choice_registry.ps1`
  - Defines audio passthrough profiles: `plex_balanced`, `compatibility`, `lossless_passthrough`, `custom_codec_list` at lines 175-185.
  - Resolves blank profile plus legacy codec list to `custom_codec_list` at lines 196-205.
  - Defines profile codec sets at lines 213-229.
- `ops/pipeline/engine/config/runtime_config.ps1`
  - Resolves `AudioPassthroughProfile` and replaces `CompatibleAudioCodecs` for non-custom profiles at lines 372-386.
  - Resolves audio transcode/downmix/max/no-audio defaults at lines 389-401.
- `ops/pipeline/engine/config/default_values.ps1`
  - Sets PowerShell default audio profile and compatible codec defaults at lines 259-260.
- `ops/pipeline/config/MediaPipeline_config_template.psd1`
  - Sets `AudioPassthroughProfile = 'plex_balanced'` and the matching codec list at lines 50-52.
- `ops/pipeline/config/profiles/Default.psd1`
  - Contains a broad legacy `CompatibleAudioCodecs` list including FLAC and DTS at lines 59-70.
  - Contains preferred audio language defaults at lines 288-290.
  - Does not define `AudioPassthroughProfile` in the reviewed file.
- `docs/architecture/CONFIG_KEY_GLOSSARY.md`
  - Documents that `AudioMaxChannels` applies to transcodes and that passthrough copies are not channel-capped at line 153.

## Folder And File Overrides

- `ops/pipeline/engine/policy/folder_policy.ps1`
  - Converts folder policy audio settings into active overrides for passthrough profile, codecs, preferred languages, transcode codec/bitrate, downmix, and max channels at lines 193-218.
  - Writes audio policy override evidence into sidecar metadata at lines 531-537.
- `ops/pipeline/engine/queue/file_overrides.ps1`
  - Maps file override audio fields to global audio config keys at lines 291-297.
  - Resolves active file override audio settings at lines 419-435.
  - Fails exact track selectors that do not match detected streams at lines 575-636.
  - Applies `dropTracks` before `keepTracks`, and drops all non-matching keep rules, at lines 638-725.
- `src/mediapipeline/core/queue/file_overrides.py`
  - Top comment still describes `downmixMode`, `transcodeCodec`, and `transcodeBitrate` as audio override fields at lines 21-29.
  - Supported audio keys are actually limited to `keepTracks`, `dropTracks`, `maxChannels`, and `preferDefaultLanguage` at lines 102-105.
  - Validation rejects unsupported audio keys and validates max channels/preferred language at lines 407-415.
- `src/mediapipeline/core/api/file_overrides/selectors.py`
  - Warns when language selectors match zero or multiple tracks and when exact indexes mismatch metadata at lines 152-195.

## Python Preview And Planner Surfaces

- `src/mediapipeline/contracts/decision_policy.py`
  - Defines effective audio policy fields at lines 120-127.
  - MP4 output forces EAC3 transcode/copy policy at lines 197-209.
  - The model does not carry `AudioDownmixMode` or `AllowNoAudio`.
- `src/mediapipeline/core/decide/encoding_rules.py`
  - Treats codec outside passthrough policy or channels above `audio_max_channels` as transcode triggers at lines 34-44.
- `src/mediapipeline/core/decide/routing.py`
  - Applies MP4 single-audio policy at lines 49-51 and 100-152.
  - Selects MP4 audio by preferred language, commentary, EAC3, default flag, channels, and stream index at lines 155-175.
- `src/mediapipeline/core/decide/processing_decision.py`
  - Maps legacy audio keys into `EffectiveDecisionPolicy` at lines 188-199.
  - Does not map `AudioDownmixMode` or `AllowNoAudio`.
  - Derives `REMUX` if any audio stream action is transcode/drop at lines 230-244.
- `src/mediapipeline/core/config/preset_migration.py`
  - Preserves full audio policy in `PresetV2` at lines 135-147.
  - Converts only a subset into `EffectiveDecisionPolicy` at lines 291-296.
- `ops/pipeline/engine/process/pipeline_plan_executor.ps1`
  - Builds audio args from plan stream actions at lines 145-180.
  - Emits `-an` when every planned audio action is dropped at lines 177-179.
  - Uses plan audio args in remux/MP4/encode command builders at lines 331-368 and 435.

## Completion And Evidence

- `ops/pipeline/engine/publish/publish_completion.ps1`
  - Writes `audio_decisions` from `Get-LastAudioDecisionRecords` into completion sidecar metadata at line 190.
- `src/mediapipeline/core/kernel/models.py`
  - Exposes normalized `audio_decisions` from completed record payloads at lines 320-321.
- `src/mediapipeline/core/completed/policy.py`
  - Reads `record.audio_decisions` into Completed rows at lines 352-365.
  - Surfaces count, detail rows, and preview strings at lines 407-409.

## Test Surfaces

- `ops/pipeline/tests/Unit/Invoke-AudioPolicyChecks.ps1`
  - Covers PCM detection, no-audio parsing, FLAC override, invalid bitrate fallback, multi-audio copy/transcode/default behavior, MP4 single audio, auto bitrate, file override drops, no-audio fail/allow behavior, and probe failures at lines 194-348.
- `tests/python/core/decide/test_processing_decision.py`
  - Covers MP4 single-audio preview behavior at lines 453-469.
  - Covers audio channel cap causing transcode in Python preview at lines 508-518.
- `tests/python/integration/test_handbrake_remux_regression_matrix.py`
  - Contains a stale or conflicting MP4 audio expectation at lines 145-151.
- `ops/pipeline/tests/Invoke-EndToEndSmokeChecks.ps1`
  - Generates a PCM audio source and verifies EAC3 output at lines 153-160 and 257-260.
  - Does not exercise multi-audio preservation, MP4 single-audio dropping, default-language selection, or completed sidecar audio decision details.
- `tests/python/desktop/test_settings_risk_policy_rules.py`
  - Classifies `AllowNoAudio` and MP4 output as high-risk settings at lines 72-81 and includes risky saved policy in sample validation at lines 175-185.
