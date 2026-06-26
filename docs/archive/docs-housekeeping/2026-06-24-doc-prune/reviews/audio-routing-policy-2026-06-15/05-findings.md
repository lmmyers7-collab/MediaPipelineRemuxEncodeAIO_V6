# Audio Routing Findings

## Finding 1 - High - Packaged Default Profile Can Bypass `plex_balanced`

`ops/pipeline/config/profiles/Default.psd1` defines `CompatibleAudioCodecs` with `truehd`, `mlp`, `flac`, `dts`, and `dts-hd` at lines 59-70, but the file does not define `AudioPassthroughProfile`. Runtime resolves a blank profile with a non-empty legacy codec list as `custom_codec_list` at `ops/pipeline/engine/config/choice_registry.ps1:196-205`, and runtime config then uses the raw compatible-codec list for custom profiles at `ops/pipeline/engine/config/runtime_config.ps1:372-386`.

Expected default behavior elsewhere is `plex_balanced`: the template sets `AudioPassthroughProfile = 'plex_balanced'` and matching codecs at `ops/pipeline/config/MediaPipeline_config_template.psd1:50-52`, and the profile registry excludes FLAC/DTS from `plex_balanced` at `ops/pipeline/engine/config/choice_registry.ps1:213-229`.

Impact:

- A packaged/default profile can preserve FLAC/DTS audio when the operator expects `plex_balanced`.
- That can force Plex audio transcoding on clients that do not support those codecs.
- The behavior is silent except for startup warning/log evidence because the raw codec list is treated as intentional custom policy.

Recommended remediation:

- Add `AudioPassthroughProfile = 'plex_balanced'` to `Default.psd1`, or narrow `CompatibleAudioCodecs` to the `plex_balanced` codec set and make ownership explicit.
- Add a config registry test that fails if `Default.psd1` omits `AudioPassthroughProfile` or if its codec list does not match the named profile.

## Finding 2 - High - Python Preview/Planner Transcodes Above Channel Cap While Runtime Copies Compatible Tracks

The PowerShell runtime applies channel caps only to transcoded output. `Get-AudioDecisionOutputChannelCount` computes the capped output count at `ops/pipeline/engine/audio/audio/stream_decisions.ps1:9-21`; transcode actions use it at `ops/pipeline/engine/audio/audio.ps1:492-496`; copy actions keep source channels and emit `-c:a copy` at `ops/pipeline/engine/audio/audio/stream_decisions.ps1:345-354` and `ops/pipeline/engine/audio/audio.ps1:513-517`. The glossary documents the same rule: passthrough copies are not channel-capped at `docs/architecture/CONFIG_KEY_GLOSSARY.md:153`.

Python decision logic disagrees. `audio_transcode_reason` returns a transcode reason whenever `stream.channels > policy.audio_max_channels` at `src/mediapipeline/core/decide/encoding_rules.py:40-43`. `EffectiveDecisionPolicy` carries `audio_max_channels` but not `AudioDownmixMode` at `src/mediapipeline/contracts/decision_policy.py:120-127`.

Impact:

- Queue/sample preview can tell the operator a compatible high-channel track will transcode when runtime would copy it.
- If `pipeline_plan_executor.ps1` is promoted to mutation execution, it can force unnecessary EAC3/AC3/AAC transcodes based on a preview-only cap rule.
- This can degrade audio quality and alter Plex direct-play behavior against saved passthrough policy.

Recommended remediation:

- Decide whether `AudioMaxChannels` is an execution cap only for transcodes, as documented and implemented in PowerShell, or a global transcode trigger.
- If PowerShell is canonical, remove channel cap as a standalone Python transcode trigger or add `AudioDownmixMode` semantics and parity tests.
- Add a parity test with compatible 7.1/8-channel passthrough audio.

## Finding 3 - High - Plan Executor Can Emit No-Audio Output Without `AllowNoAudio`

The live PowerShell runtime refuses all-audio-dropped output unless `AllowNoAudio` is effective. `Build-AudioArgs` throws `SOURCE_MEDIA_AUDIO_OVERRIDE_STRIPPED` when no tracks remain and `AllowNoAudio` is false at `ops/pipeline/engine/audio/audio.ps1:545-557`.

The plan executor does not carry that guard. `New-PipelinePlanExecutorAudioArgumentList` skips dropped actions and emits `-an` when every planned audio action is dropped at `ops/pipeline/engine/process/pipeline_plan_executor.ps1:152-179`. `EffectiveDecisionPolicy` does not carry `AllowNoAudio` at `src/mediapipeline/contracts/decision_policy.py:120-127`.

Impact:

- If plan execution is used for mutation, a plan with all audio actions dropped can produce a silent file instead of failing/reviewing.
- This directly violates the runtime fail-closed invariant and the Settings risk policy that treats `AllowNoAudio` as high risk.

Current mitigating factor:

- The current live remux/encode path still calls `Build-AudioArgs`, not the plan executor.

Recommended remediation:

- Add `allow_no_audio` to the execution policy or plan snapshot.
- Make the plan executor throw on all-drop audio unless no-audio is explicitly allowed.
- Add plan executor tests for all-drop with allow false/true.

## Finding 4 - Medium - MP4 Single-Audio Selection Drifts Between PowerShell Runtime And Python Preview

PowerShell MP4 audio selection ranks preferred language, commentary penalty, EAC3, fidelity score, and source ordinal at `ops/pipeline/engine/audio/audio/stream_decisions.ps1:130-136`.

Python MP4 audio selection ranks preferred language, commentary penalty, EAC3, source default flag, negative channel count, and stream index at `src/mediapipeline/core/decide/routing.py:162-175`.

Impact:

- For MP4 output, one engine can preview/plan one retained stream while runtime retains a different stream.
- Because MP4 mode drops every non-selected audio track, this can silently drop the wrong language/commentary/accessibility/lossless track from the operator's perspective.

Recommended remediation:

- Move MP4 selection criteria into a shared documented contract and mirror it in both engines.
- Add parity fixtures where selected stream can change based on default flag, channel count, codec, and commentary title.

## Finding 5 - Medium - Per-File Audio Override Contract Is Split Across Python And PowerShell

PowerShell maps file override audio fields `maxChannels`, `downmixMode`, `transcodeCodec`, `transcodeBitrate`, and `preferDefaultLanguage` to active config keys at `ops/pipeline/engine/queue/file_overrides.ps1:291-297`.

Python file override persistence/validation only supports `keepTracks`, `dropTracks`, `maxChannels`, and `preferDefaultLanguage` at `src/mediapipeline/core/queue/file_overrides.py:102-105`. The same Python file's top comment still advertises `downmixMode`, `transcodeCodec`, and `transcodeBitrate` at lines 21-29, while tests intentionally reject those fields as unsupported at `tests/python/desktop/test_application_facade_local_api.py:1806-1807` and `tests/python/desktop/test_facade_queue_policy.py:399-400`.

Impact:

- Operators and future agents can read one contract and assume per-file transcode/downmix policy is supported, while API validation rejects it.
- Legacy/manual override entries with those fields may behave differently depending on whether they enter through Python validation or PowerShell runtime.
- This is a policy ownership ambiguity in a high-risk audio path.

Recommended remediation:

- Either support the additional audio fields end-to-end in Python API, preview, and tests, or remove the stale documented fields and PowerShell mapping if they are intentionally deferred.
- Add a single file-override audio contract document/test that pins supported and rejected fields.

## Finding 6 - Medium - Integration Matrix Has Stale MP4 Audio Expectations

`tests/python/integration/test_handbrake_remux_regression_matrix.py` expects MP4 audio actions `["transcode", "copy", "copy"]` for `multi_audio_tracks.json` at lines 145-151. Focused Python and PowerShell tests expect MP4 single-audio behavior with non-selected tracks dropped: `tests/python/core/decide/test_processing_decision.py:453-469` and `ops/pipeline/tests/Unit/Invoke-AudioPolicyChecks.ps1:256-274`.

Impact:

- The regression matrix does not reliably represent the current policy.
- Future test failures in this area can be misread as implementation bugs instead of stale expectations.
- A stale matrix is dangerous because MP4 policy is explicitly allowed to drop tracks.

Recommended remediation:

- Update the integration matrix to expect drop/copy/drop, or split the test into a clearly named pre-MP4-single-audio legacy case that is not part of current promotion gates.
- Add a reason-code assertion for `MP4_COMPATIBILITY_SINGLE_AUDIO_TRACK`.

## Finding 7 - Low - Config Preview Codec Reconciliation Depends On Managed Key Inclusion

`build_config_preview` expands named profile codec lists only when `CompatibleAudioCodecs` is included in `managed_keys` at `src/mediapipeline/core/config/preview.py:41-43`. The test covers the managed case at `tests/python/desktop/test_service_config_preview.py:47-68`.

Impact:

- Save/review flows that stage only `AudioPassthroughProfile` can leave stale raw `CompatibleAudioCodecs` visible in preview text even though runtime ignores them for non-custom profiles.
- This is more of an operator-evidence risk than a current runtime routing bug.

Recommended remediation:

- Ensure all settings save paths stage `CompatibleAudioCodecs` whenever `AudioPassthroughProfile` changes.
- Add a save-flow test, not just a helper test, proving persisted preview text and runtime ownership agree.
