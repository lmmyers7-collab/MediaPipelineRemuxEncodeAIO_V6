# Audio Routing Invariants And Boundaries

## Runtime Invariants

1. Current media mutation goes through PowerShell `Build-AudioArgs`.

   `Do-Remux` calls `Build-AudioArgs` at `ops/pipeline/entrypoints/MediaPipeline/remux.ps1:162`. `Do-Encode` calls it at `ops/pipeline/entrypoints/MediaPipeline/encode.ps1:130`. The Python planner is not the current canonical mutation engine.

2. Missing audio fails closed unless `AllowNoAudio` is explicitly effective.

   `Build-AudioArgs` performs a second audio presence probe when metadata probe returns no streams. Probe failure throws `SOURCE_MEDIA_AUDIO_PRESENCE_PROBE_FAILED` regardless of `AllowNoAudio` at `ops/pipeline/engine/audio/audio.ps1:416-429`. True no-audio throws unless `Get-EffectiveAllowNoAudio` is true, where it emits `-an` and records `omit_all` at `ops/pipeline/engine/audio/audio.ps1:430-440`.

3. Metadata probe failure fails closed.

   If ffprobe can see audio but metadata parsing fails, runtime throws `SOURCE_MEDIA_AUDIO_METADATA_PROBE_FAILED` instead of guessing `0:a:0`, at `ops/pipeline/engine/audio/audio.ps1:442-447`.

4. File overrides can intentionally drop tracks, but all-audio-dropped fails unless no-audio output is explicitly allowed.

   Track filtering records drops at `ops/pipeline/engine/audio/audio/stream_decisions.ps1:242-328`. If no tracks remain, `Build-AudioArgs` throws `SOURCE_MEDIA_AUDIO_OVERRIDE_STRIPPED` unless `AllowNoAudio` is true, at `ops/pipeline/engine/audio/audio.ps1:545-557`.

5. PCM audio is standardized and never copied as passthrough.

   Compatible-codec resolution removes PCM names at `ops/pipeline/engine/audio/audio.ps1:264-269`. Stream decisions transcode PCM with reason `PCM standardization` at `ops/pipeline/engine/audio/audio/stream_decisions.ps1:330-344`.

6. Codec passthrough is profile/config driven.

   Non-custom `AudioPassthroughProfile` replaces `CompatibleAudioCodecs` in runtime config at `ops/pipeline/engine/config/runtime_config.ps1:372-386` and in effective audio resolution at `ops/pipeline/engine/audio/audio.ps1:259-262`. `custom_codec_list` is the only profile that uses the raw codec list as owner.

7. Channel cap is applied only to transcoded output in the current PowerShell runtime.

   `Get-AudioDecisionOutputChannelCount` computes the capped transcode channel count at `ops/pipeline/engine/audio/audio/stream_decisions.ps1:9-21`. That value is used for transcode args at `ops/pipeline/engine/audio/audio.ps1:492-496`. Copy actions keep `$ch` as output channels and emit `-c:a copy` without channel layout at `ops/pipeline/engine/audio/audio/stream_decisions.ps1:345-354` and `ops/pipeline/engine/audio/audio.ps1:513-517`.

8. Default audio selection avoids commentary unless every kept track is commentary.

   `Get-AudioDecisionPreferredDefaultIndex` builds a non-commentary pool first, then ranks by preferred language, fidelity, and output ordinal at `ops/pipeline/engine/audio/audio/stream_decisions.ps1:24-57`.

9. MP4 output intentionally keeps only one audio track.

   In MP4 mode, `Build-AudioArgs` forces effective compatible codecs to EAC3 at `ops/pipeline/engine/audio/audio.ps1:381-384` and transcode codec to EAC3 at `ops/pipeline/engine/audio/audio.ps1:403-405`. `Build-AudioStreamDecisionPlan` drops all non-selected audio with reason `mp4_single_eac3_compatibility` at `ops/pipeline/engine/audio/audio/stream_decisions.ps1:289-328`.

10. Kept tracks get language metadata and, for non-MP4 output, generated titles.

    Runtime writes `language=` metadata for each kept track at `ops/pipeline/engine/audio/audio.ps1:534-537` and skips title metadata in MP4 mode at `ops/pipeline/engine/audio/audio.ps1:538-540`.

11. Completion sidecars preserve audio decision evidence.

    Runtime stores `Get-LastAudioDecisionRecords` in `audio_decisions` at `ops/pipeline/engine/publish/publish_completion.ps1:190`. Completed rows expose count/details/preview at `src/mediapipeline/core/completed/policy.py:407-409`.

12. MKV default audio flags are explicitly restamped after FFmpeg.

    Runtime records `LastAudioDefaultIndex` and `LastAudioTrackCount` at `ops/pipeline/engine/audio/audio.ps1:562-570`. Remux uses mkvmerge TIDs and emits `--default-track` flags at `ops/pipeline/entrypoints/MediaPipeline/remux.ps1:326-343`.

## Ownership Boundaries

- PowerShell runtime owns actual FFmpeg and mkvmerge audio mutation today.
- Python decision code owns read-only route previews, queue/source decision models, sample validation, and future plan generation.
- `EffectiveDecisionPolicy` is not a full execution audio policy. It omits `AudioDownmixMode`, transcode bitrate, auto bitrate, and `AllowNoAudio` at `src/mediapipeline/contracts/decision_policy.py:120-127`.
- `PresetV2` carries fuller audio policy, including downmix and allow-no-audio, at `src/mediapipeline/core/config/preset_migration.py:135-147`, but only a subset is converted into `EffectiveDecisionPolicy` at `src/mediapipeline/core/config/preset_migration.py:291-296`.
- Settings/profile ownership is split:
  - Named profiles own codecs unless `custom_codec_list` is selected.
  - Raw `CompatibleAudioCodecs` owns passthrough only for `custom_codec_list` or legacy blank-profile configs.
  - Runtime treats blank profile plus non-empty legacy codec list as `custom_codec_list` at `ops/pipeline/engine/config/choice_registry.ps1:196-205`.
- File override ownership is currently narrower in Python APIs than PowerShell runtime support. Python supports only `keepTracks`, `dropTracks`, `maxChannels`, and `preferDefaultLanguage` at `src/mediapipeline/core/queue/file_overrides.py:102-105`, while PowerShell maps additional audio fields at `ops/pipeline/engine/queue/file_overrides.ps1:291-297`.
- MP4 mode is a compatibility policy that trades track preservation for container/client compatibility. That policy must be treated as a destructive/drop policy even when the route remains `REMUX`.

## Review Boundary

Any future work that changes these invariants needs media-policy validation, not just unit tests. The repo states FFmpeg/media policy changes require high validation and real-media samples where practical at `docs/CURRENT_PROJECT_STATE.md:79-80`, and the no-touch register requires unit tests plus real-media validation with multi-audio samples at `docs/operator/NO_TOUCH_BOUNDARY_REGISTER.md:73-81`.
