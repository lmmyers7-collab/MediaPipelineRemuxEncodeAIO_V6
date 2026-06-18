# Audio Routing Test Coverage Review

## Existing Coverage That Helps

### PowerShell Audio Policy Unit Coverage

`ops/pipeline/tests/Unit/Invoke-AudioPolicyChecks.ps1` is the strongest current test surface.

Covered:

- PCM detection at lines 194-196.
- `AllowNoAudio` string coercion and override behavior at lines 198-203.
- `FlacAsCompatible` string false/true behavior at lines 204-208.
- Invalid transcode bitrate fallback at lines 213-216.
- Multi-audio copy/transcode/default/disposition behavior at lines 235-254.
- MP4 single-audio policy with explicit drop reasons at lines 256-274.
- Auto bitrate by channels at lines 277-283.
- File override keep/drop/title override behavior at lines 286-306.
- Missing audio fail vs `AllowNoAudio` emit `-an` at lines 309-324.
- Presence probe failure remains failure even with `AllowNoAudio` at lines 326-339.
- Metadata probe failure fails closed at lines 341-348.

### Python Decision Coverage

`tests/python/core/decide/test_processing_decision.py` covers:

- MP4 single-audio preview behavior and dropped audio count at lines 453-469.
- Channel cap causing audio transcode in Python preview at lines 508-518.

This coverage is useful, but it also locks in behavior that currently diverges from the PowerShell runtime for channel caps.

### Settings And Config Coverage

- `tests/python/desktop/test_service_config_preview.py` covers managed profile codec expansion and custom codec preservation at lines 47-68.
- `tests/python/desktop/test_service_config_option_policy.py` covers profile/raw-codec warnings at lines 179-193.
- `tests/python/desktop/test_settings_risk_policy_rules.py` classifies `AllowNoAudio` and MP4 output as high risk at lines 72-81 and includes risky saved policy at lines 175-185.

### File Override Coverage

The Python file-override tests heavily cover supported fields, path safety, selector validation, exact stream index handling, and unsupported field rejection. Relevant examples:

- Unsupported `downmixMode` and `transcodeBitrate` are expected to be rejected in `tests/python/desktop/test_application_facade_local_api.py:1806-1807`.
- Queue policy tests also expect those fields to be unsupported at `tests/python/desktop/test_facade_queue_policy.py:399-400`.

### End-To-End Smoke Coverage

`ops/pipeline/tests/Invoke-EndToEndSmokeChecks.ps1` generates a PCM audio source at lines 153-160 and verifies EAC3 output at lines 257-260.

This is valuable for toolchain and command execution coverage, but it is not enough for multi-audio policy safety.

## Coverage Gaps

### 1. Packaged Default Profile Audio Policy Is Not Pinned

`ops/pipeline/tests/Unit/Invoke-ConfigKeyRegistryChecks.ps1` imports `Default.psd1` at line 290 and validates root defaults at lines 291-313, but does not assert:

- `AudioPassthroughProfile` exists in `Default.psd1`.
- `CompatibleAudioCodecs` matches the selected named profile.
- `Default.psd1` does not drift into legacy `custom_codec_list` behavior.

Impact: the current `Default.psd1` broad codec list can bypass `plex_balanced` without a focused test failure.

### 2. No Runtime/Preview Parity Test For Channel Caps

PowerShell runtime copies compatible high-channel audio without channel cap. Python preview marks high-channel audio above cap for transcode. Existing tests assert both sides independently, but no test compares them.

Needed:

- A fixture with copy-compatible 7.1 or 8-channel audio under `plex_balanced`.
- A parity assertion that PowerShell and Python agree, or an explicit documented exception if preview is intentionally stricter.

### 3. No Runtime/Preview Parity Test For MP4 Track Selection

PowerShell and Python MP4 selection scoring differ. Existing tests use their own fixture expectations, but there is no cross-engine comparison that the same stream is retained.

Needed fixture dimensions:

- Multiple preferred-language tracks.
- EAC3 and non-EAC3 variants.
- Different channel counts.
- One source-default flag.
- Commentary/accessibility titles.

### 4. Plan Executor Lacks No-Audio Policy Tests

`New-PipelinePlanExecutorAudioArgumentList` emits `-an` for all-drop audio plans at `ops/pipeline/engine/process/pipeline_plan_executor.ps1:177-179`. There is no test proving it refuses all-drop audio unless `AllowNoAudio` is carried and true.

Needed:

- All audio actions dropped plus `AllowNoAudio=false` should throw.
- All audio actions dropped plus `AllowNoAudio=true` should emit `-an`.
- No audio source tracks and explicit allow behavior should be distinct from all tracks dropped.

### 5. Real-Media Smoke Does Not Cover Track Preservation

The current smoke covers a single PCM audio standardization path only. It does not verify:

- Multiple audio tracks are preserved in MKV.
- Commentary is preserved but not default.
- Preferred language becomes default.
- Default flags survive mkvmerge.
- Completion sidecar contains all audio decisions.
- MP4 mode drops non-selected tracks and records those drops.

### 6. Integration Matrix Contains A Conflicting MP4 Expectation

`tests/python/integration/test_handbrake_remux_regression_matrix.py` expects MP4 audio actions `["transcode", "copy", "copy"]` at lines 145-151. Current focused Python and PowerShell tests expect MP4 single-audio drop/copy/drop behavior at `tests/python/core/decide/test_processing_decision.py:453-469` and `ops/pipeline/tests/Unit/Invoke-AudioPolicyChecks.ps1:256-274`.

Impact: this integration matrix is either stale or exercising a different intended layer without saying so. It should not remain ambiguous in a high-risk media-policy area.

### 7. Config Preview Managed-Key Boundary Is Narrow

`build_config_preview` expands profile codecs only when `CompatibleAudioCodecs` is in `managed_keys` at `src/mediapipeline/core/config/preview.py:41-43`. The existing test covers that managed case. There is no test proving actual save flows always include both `AudioPassthroughProfile` and `CompatibleAudioCodecs` when profile ownership changes.

## Recommended New Tests

1. `Invoke-ConfigKeyRegistryChecks.ps1`
   - Assert `Default.psd1` contains `AudioPassthroughProfile`.
   - Assert its codec list equals `Get-MediaPipelineAudioPassthroughProfileCodecs -Profile $defaultProfileConfig.AudioPassthroughProfile`.

2. `Invoke-AudioPolicyChecks.ps1`
   - Add compatible 8-channel TrueHD under `AudioMaxChannels=6`; assert runtime copies it, records output channels as source channels, and does not emit `-ac` for that stream.
   - Add a parallel case with incompatible DTS under `plex_balanced`; assert transcode to configured codec and cap/downmix behavior.
   - Add MP4 selection fixture where Python and PowerShell currently diverge; decide and pin expected shared behavior.

3. `tests/python/core/decide/test_processing_decision.py`
   - Update channel-cap semantics to match runtime, or explicitly encode the intentional preview-only difference with a risk note.
   - Add `AudioDownmixMode` semantics if Python is meant to model execution.

4. Plan executor unit tests
   - Assert all-drop audio plans fail without explicit allow-no-audio.
   - Assert allow-no-audio is carried through `PresetV2` to plan execution if supported.

5. Real-media validation
   - Add a multi-audio fixture with AAC/AC3/EAC3/TrueHD/PCM plus commentary and language tags.
   - Add an MP4 compatibility fixture and inspect final audio stream count, codec, language, default disposition, and completion sidecar drop records.
