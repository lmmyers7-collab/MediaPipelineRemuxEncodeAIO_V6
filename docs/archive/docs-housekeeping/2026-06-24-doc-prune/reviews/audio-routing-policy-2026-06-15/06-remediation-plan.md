# Audio Routing Remediation Plan

This plan is ordered by risk and blast radius. It is intentionally implementation-facing, but no code was edited as part of this review.

## Phase 1 - Pin Profile Ownership

1. Fix `ops/pipeline/config/profiles/Default.psd1`.
   - Add explicit `AudioPassthroughProfile = 'plex_balanced'`, or intentionally rename/document it as a custom/lossless profile.
   - Align `CompatibleAudioCodecs` with the named profile unless `custom_codec_list` is intentional.

2. Add config registry tests.
   - Assert every packaged profile has explicit `AudioPassthroughProfile`.
   - Assert non-custom profile codec lists match `Get-MediaPipelineAudioPassthroughProfileCodecs`.
   - Assert no packaged default profile silently resolves to `custom_codec_list` unless its name/description says so.

3. Add a release-note/operator note.
   - Explain that `plex_balanced` does not include FLAC/DTS.
   - Explain that `lossless_passthrough` or `custom_codec_list` may force Plex audio transcode on unsupported clients.

## Phase 2 - Align Channel Cap Semantics

1. Decide canonical semantics.
   - Current docs and PowerShell say `AudioMaxChannels` caps transcodes only.
   - Python preview currently treats it as a transcode trigger.

2. If PowerShell remains canonical:
   - Remove channel cap as a standalone transcode reason in `src/mediapipeline/core/decide/encoding_rules.py`.
   - Add `AudioDownmixMode` to preview if preview needs to compute transcode output channel count.
   - Keep copy-compatible high-channel tracks as copy in Python decisions.

3. If global channel cap becomes policy:
   - Change PowerShell runtime to transcode compatible tracks above cap.
   - Update `docs/architecture/CONFIG_KEY_GLOSSARY.md`.
   - Treat this as a media-policy behavior change requiring real-media validation.

Recommended direction: keep PowerShell semantics and align Python, because the repo already documents passthrough copies as not channel-capped.

## Phase 3 - Make Plan Execution Fail Closed

1. Carry allow-no-audio policy into plans.
   - Add `allow_no_audio` to the plan execution policy snapshot or consume it from `PresetV2.audio.allowNoAudio`.

2. Update `New-PipelinePlanExecutorAudioArgumentList`.
   - If actions exist and all are `drop`, throw unless allow-no-audio is true.
   - Preserve the current `-an` behavior only for explicit allow-no-audio.

3. Add tests.
   - All dropped with allow false -> throws.
   - All dropped with allow true -> `-an`.
   - Missing/no detected audio remains distinct from all audio intentionally dropped.

## Phase 4 - Unify MP4 Audio Selection

1. Define the MP4 selected-track contract in one place:
   - Preferred language.
   - Non-commentary/accessibility preference.
   - EAC3 preference.
   - Fidelity/channel preference.
   - Source default flag, if intentionally used.
   - Stable ordinal tie-break.

2. Make PowerShell and Python match that contract.

3. Add parity fixtures.
   - Two preferred-language EAC3 tracks where only default flag differs.
   - Preferred-language PCM vs non-preferred EAC3.
   - Commentary EAC3 vs main non-EAC3.
   - High-channel TrueHD vs EAC3 in MP4 mode.

4. Surface the selected stream and every dropped stream in queue/sample/completed review surfaces.

## Phase 5 - Clarify Per-File Audio Override Contract

1. Choose one support set.
   - Minimal current UI set: `keepTracks`, `dropTracks`, `maxChannels`, `preferDefaultLanguage`.
   - Full PowerShell set: plus `downmixMode`, `transcodeCodec`, `transcodeBitrate`.

2. If full support is desired:
   - Add Python validation for those fields.
   - Add route/track preview display.
   - Add Local API and WebView controls only if they can be represented safely.
   - Add PowerShell and Python tests.

3. If deferred:
   - Remove stale comment examples from `src/mediapipeline/core/queue/file_overrides.py`.
   - Remove or gate PowerShell mapping for unsupported fields.
   - Keep tests proving unsupported fields are rejected.

## Phase 6 - Repair Test Matrix Drift

1. Update `tests/python/integration/test_handbrake_remux_regression_matrix.py` MP4 audio expectations.
2. Add reason-code assertions for MP4 audio drops.
3. Add a named fixture comment explaining that MP4 compatibility is intentionally track-dropping.

## Phase 7 - Real-Media Validation

Run representative samples after the code fixes, not before:

- MKV multi-audio preservation with preferred/default/commentary/lossless/PCM tracks.
- MP4 single-audio compatibility with dropped-track sidecar records.
- DTS/FLAC under `plex_balanced`, `lossless_passthrough`, and `custom_codec_list`.
- No-audio source with `AllowNoAudio=false` and `AllowNoAudio=true`.
- File override all-drop with `AllowNoAudio=false` and true.

Acceptance should require ffprobe evidence, mkvmerge/default-disposition evidence, completion sidecar `audio_decisions`, and manual Plex/client playback review where practical.
