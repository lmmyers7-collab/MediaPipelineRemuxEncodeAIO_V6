# Audio Routing Validation Plan

## Goal

Validate that audio routing changes do not:

- Drop audio tracks without explicit policy.
- Transcode when passthrough policy says copy.
- Copy when policy says transcode.
- Ignore saved profile/config/folder/file policy.
- Produce files likely to force unexpected Plex transcoding.
- Produce no-audio output without explicit `AllowNoAudio`.

## Static Validation

1. Search and inspect:
   - `rg -n "AudioPassthroughProfile|CompatibleAudioCodecs|AudioMaxChannels|AudioDownmixMode|AllowNoAudio" ops src tests docs`
   - `rg -n "mp4_single|MP4_COMPATIBILITY|audio_max_channels|audio_transcode_reason" ops src tests`

2. Change-control validation:
   - `.\apps\desktop\runtime\Python\python.exe .\ops\scripts\dev\run-python-tool.py mediapipeline.tools.change_control.validate_changes --require-worktree-coverage`

3. Docs-only checks:
   - Verify the nine requested review files exist under `docs/reviews/audio-routing-policy-2026-06-15/`.
   - Verify the change packet lists every new review file.

## Unit Validation

### PowerShell

Run:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File ops/pipeline/tests/Unit/Invoke-AudioPolicyChecks.ps1
pwsh -NoProfile -ExecutionPolicy Bypass -File ops/pipeline/tests/Unit/Invoke-ConfigKeyRegistryChecks.ps1
```

Add or update tests for:

- Packaged default profile profile/codec ownership.
- Compatible high-channel passthrough track under `AudioMaxChannels=6`.
- Incompatible high-channel transcode under `AudioDownmixMode=max_channels`.
- `AudioDownmixMode=preserve`, `max_channels`, and `stereo`.
- MP4 selected-track parity.
- All-dropped file override with `AllowNoAudio=false/true`.

### Python

Run:

```powershell
.\apps\desktop\runtime\Python\python.exe -m pytest tests/python/core/decide/test_processing_decision.py -q
.\apps\desktop\runtime\Python\python.exe -m pytest tests/python/integration/test_handbrake_remux_regression_matrix.py -q
.\apps\desktop\runtime\Python\python.exe -m pytest tests/python/desktop/test_service_config_preview.py tests/python/desktop/test_service_config_option_policy.py -q
.\apps\desktop\runtime\Python\python.exe -m pytest tests/python/desktop/test_facade_queue_policy.py tests/python/desktop/test_file_override_tracks.py -q
```

Add or update tests for:

- Python/PowerShell channel-cap parity.
- Python/PowerShell MP4 retained-stream parity.
- Save-flow managed key coverage for `AudioPassthroughProfile` plus `CompatibleAudioCodecs`.
- File override supported/rejected audio field ownership.

## Planner Validation

Before enabling any plan executor mutation path:

1. Add unit tests around `New-PipelinePlanExecutorAudioArgumentList`.
2. Prove `AllowNoAudio=false` blocks all-drop audio.
3. Prove `AllowNoAudio=true` is the only path to `-an`.
4. Prove transcode bitrate and output channel count match runtime `Build-AudioArgs`.
5. Prove MP4 selected stream matches runtime selection.

## Real-Media Validation Samples

### Sample A - MKV Multi-Audio Preservation

Source shape:

- Video stream compatible for remux.
- Audio 0: English AAC/AC3 commentary.
- Audio 1: Japanese PCM 2.0, forced.
- Audio 2: English TrueHD 7.1.
- Audio 3: English EAC3 5.1.

Validate:

- Non-MP4 output preserves all tracks except intentional overrides.
- PCM transcodes to configured codec.
- Commentary is preserved but not default.
- Preferred language becomes default.
- MKV has exactly one default audio track.
- Completion sidecar contains one record per source audio stream.

### Sample B - Plex-Balanced Lossless/DTS Boundary

Source shape:

- FLAC 5.1.
- DTS or DTS-HD.
- EAC3 fallback track.

Validate under:

- `AudioPassthroughProfile=plex_balanced`: FLAC/DTS should not copy unless explicit custom/override policy says so.
- `AudioPassthroughProfile=lossless_passthrough`: lossless passthrough is expected.
- `AudioPassthroughProfile=custom_codec_list`: raw codec list owns behavior.

Manual review:

- Check whether Plex/client direct-plays or transcodes audio for each profile.

### Sample C - MP4 Compatibility

Source shape:

- Multiple audio languages.
- EAC3 and non-EAC3 candidates.
- Commentary and non-commentary tracks.

Validate:

- Exactly one audio track remains.
- Selected track is expected by shared MP4 ranking.
- Selected non-EAC3 track transcodes to EAC3.
- Dropped tracks are recorded with `mp4_single_eac3_compatibility`.
- Operator evidence surfaces dropped-track count and reasons.

### Sample D - No-Audio Failure

Validate:

- No audio plus `AllowNoAudio=false` fails before output acceptance.
- No audio plus `AllowNoAudio=true` emits `-an`, records `omit_all`, and is visibly high-risk.
- Probe failure still fails when `AllowNoAudio=true`.

### Sample E - File Override Drop Safety

Validate:

- Exact stream selector mismatch fails with `FILE_OVERRIDE_EXACT_TRACK_UNAVAILABLE`.
- Broad language selector warnings appear when multiple tracks match.
- All tracks dropped with `AllowNoAudio=false` fails.
- All tracks dropped with `AllowNoAudio=true` emits `-an` and records each drop.

## Acceptance Criteria

- No new or changed audio policy ships without unit tests and real-media validation.
- PowerShell runtime and Python preview select the same retained MP4 audio stream.
- Channel-cap semantics are identical in docs, runtime, preview, and planner.
- Packaged profiles cannot silently resolve to unintended custom codec policy.
- Completion evidence shows every copied, transcoded, dropped, or omitted audio decision.
- Strict change-control validation is run or any unrelated dirty-worktree blockers are reported.
