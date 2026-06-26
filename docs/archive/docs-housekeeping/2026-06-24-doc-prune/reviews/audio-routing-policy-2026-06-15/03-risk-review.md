# Audio Routing Risk Review

## High-Level Risk Posture

The live PowerShell runtime is conservative in the places most likely to silently damage output: missing audio, failed probe, all tracks dropped by override, and default-track disposition. The main risk is drift across policy owners:

- Packaged/default profile files can change the effective passthrough policy before runtime.
- Python preview/planner can disagree with the PowerShell runtime.
- Future plan execution can bypass fail-closed guards present in `Build-AudioArgs`.
- MP4 compatibility intentionally drops tracks and must always be surfaced as destructive audio policy.

## Passthrough And Transcode

Runtime passthrough is profile-driven. `choice_registry.ps1` defines `plex_balanced` as AAC/AC3/EAC3/MP3/Opus/Vorbis/TrueHD/MLP, not FLAC/DTS, at `ops/pipeline/engine/config/choice_registry.ps1:213-229`. `MediaPipeline_config_template.psd1` matches that profile at `ops/pipeline/config/MediaPipeline_config_template.psd1:50-52`.

Risk: `ops/pipeline/config/profiles/Default.psd1` carries a legacy broad codec list including FLAC and DTS at lines 59-70 but does not define `AudioPassthroughProfile`. Runtime resolves blank profile plus legacy codecs to `custom_codec_list` at `ops/pipeline/engine/config/choice_registry.ps1:196-205`. That can make a packaged default profile behave like custom lossless passthrough rather than `plex_balanced`.

Plex implication: preserving FLAC/DTS can be valid for some clients but is more likely to force Plex audio transcode than EAC3/AC3/AAC. If the operator expects `plex_balanced`, the default profile can silently choose a different direct-play posture.

## Downmix And Channel Caps

Runtime channel cap applies only to transcoded audio. The architecture glossary explicitly says passthrough copies are not channel-capped at `docs/architecture/CONFIG_KEY_GLOSSARY.md:153`. PowerShell implements that: transcode uses `OutputChannels`, copy uses source channels and `-c:a copy`.

Risk: Python decision logic treats `stream.channels > audio_max_channels` as a transcode reason at `src/mediapipeline/core/decide/encoding_rules.py:40-43`, and `EffectiveDecisionPolicy` does not carry `AudioDownmixMode` at `src/mediapipeline/contracts/decision_policy.py:120-127`. This makes preview/planner stricter than runtime for copy-compatible high-channel audio.

Plex implication: a `plex_balanced` TrueHD 7.1 track with `AudioMaxChannels = 6` is copied by current runtime but preview/planner may label it for transcode. If the planner path is later promoted, it can force an unexpected EAC3 transcode.

## MP4 Compatibility And Track Drops

MP4 compatibility mode is intentionally destructive for audio track preservation. PowerShell forces EAC3-only effective compatibility at `ops/pipeline/engine/audio/audio.ps1:381-384`, chooses one audio source, and drops non-selected audio with reason `mp4_single_eac3_compatibility` at `ops/pipeline/engine/audio/audio/stream_decisions.ps1:289-328`.

Risk: This behavior is correct only if the operator chose MP4 compatibility knowingly. It can silently remove alternate languages, commentary, accessibility audio, or lossless tracks unless the dropped decisions are surfaced and reviewed.

Positive evidence: runtime records the dropped decisions into completion sidecars and the unit test asserts explicit drop reasons at `ops/pipeline/tests/Unit/Invoke-AudioPolicyChecks.ps1:256-274`.

## Default Language Selection

PowerShell normalizes common language aliases at `ops/pipeline/engine/audio/audio.ps1:20-54`, applies active overrides before global defaults at `ops/pipeline/engine/audio/audio.ps1:40-45`, and defaults to English when empty at line 52. Default track selection avoids commentary unless all kept tracks are commentary and then ranks preferred language, fidelity, and ordinal at `ops/pipeline/engine/audio/audio/stream_decisions.ps1:24-57`.

Risk: MP4 selection scoring differs between PowerShell and Python. PowerShell ranks preferred language, commentary, EAC3, fidelity, and ordinal at `ops/pipeline/engine/audio/audio/stream_decisions.ps1:130-136`. Python ranks preferred language, commentary, EAC3, source default flag, channels, and stream index at `src/mediapipeline/core/decide/routing.py:162-175`. A preview can identify a different retained MP4 track than runtime.

## Track Preservation

Non-MP4 runtime preserves all audio tracks except those dropped by file override. It preserves commentary but avoids making it default. It records output ordinals and decisions for each input stream.

Risk: file override `keepTracks` is naturally destructive: if present, every non-matching track is dropped at `ops/pipeline/engine/queue/file_overrides.ps1:708-721`. Exact `streamIndex` mismatches fail, but broad language selectors that match multiple tracks can still drop all other languages. The Python selector preview warns about ambiguous language selectors at `src/mediapipeline/core/api/file_overrides/selectors.py:167-181`.

Positive evidence: if all audio is dropped by file override, PowerShell throws unless `AllowNoAudio` is true at `ops/pipeline/engine/audio/audio.ps1:545-557`.

## Profile And Config Ownership

Named profiles should own codec lists unless `custom_codec_list` is selected. Python config preview expands profile codec lists only when `CompatibleAudioCodecs` is included in managed keys at `src/mediapipeline/core/config/preview.py:41-43`. Option validation warns when a named profile conflicts with raw codecs at `src/mediapipeline/core/config/option_policy.py:123-135`.

Risk: save paths that stage only `AudioPassthroughProfile` can leave stale raw codec lists in the config text or review surface, even though runtime will ignore them for non-custom profiles. That is not currently a runtime transcode bug, but it can confuse saved-policy review and make operators think a raw list is active when profile ownership has overridden it.

## Failure And Review Behavior

Runtime `Build-AudioArgs` fails closed for:

- Audio presence probe failure.
- Audio metadata probe failure.
- Missing audio when `AllowNoAudio` is false.
- All tracks dropped by override when `AllowNoAudio` is false.
- Invalid codec or channel metadata.

Risk: `pipeline_plan_executor.ps1` does not carry the same no-audio guard. It emits `-an` when every planned audio action is `drop` and there was at least one audio action, at `ops/pipeline/engine/process/pipeline_plan_executor.ps1:177-179`. This is currently a latent risk because the live mutation path is still `Build-AudioArgs`, but it is a high-risk promotion blocker.

## Risk Matrix

| Risk | Severity | Current Runtime? | Silent Drop? | Plex Transcode? | Config Ignored? |
|---|---:|---|---|---|---|
| `Default.psd1` legacy broad codec list resolves to custom passthrough | High | Yes, when that profile/config is loaded | No | Likely for FLAC/DTS clients | Yes, if operator expects `plex_balanced` |
| Python channel cap transcodes high-channel passthrough | High | Preview/planner only today | No | Yes, if planner promoted | Partially, ignores downmix semantics |
| Plan executor all-drop emits `-an` without `AllowNoAudio` | High | Future/latent path | Yes | N/A | Yes, omits no-audio policy |
| MP4 PowerShell/Python selected-track drift | Medium | Preview vs runtime | Yes, MP4 drops non-selected tracks | Maybe | No |
| Python file-override docs/runtime/API key drift | Medium | API/review boundary | Potentially | Maybe | Yes, for deferred override fields |
| Stale integration MP4 expectations | Medium | Test suite | N/A | N/A | N/A |
