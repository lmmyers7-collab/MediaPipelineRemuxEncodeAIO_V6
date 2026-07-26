---
file: ops/pipeline/engine/audio/audio.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: audio
token_priority: medium
owner_domain: audio
last_modified: 2026-07-16
last_reviewed: 2026-06-04
sha256: 5df631013f0d05cdee56b415e33b19bb7ef6163b49b2659b9ecb2e60b562afb7
---
# `ops/pipeline/engine/audio/audio.ps1`

**Purpose:** Suggestion #7 — pick an output bitrate appropriate for the codec / channel count combination instead of always emitting 640k.

**Public symbols:** `Build-AudioArgs`, `ConvertTo-EffectiveAudioBoolean`, `Get-AudioCodecFidelityRank`, `Get-AudioFidelityScore`, `Get-AudioTranscodeBitrateForChannels`, `Get-EffectiveAllowNoAudio`, `Get-EffectiveAudioDownmixMode`, `Get-EffectiveAudioMaxChannels`, `Get-EffectiveAudioOutputContainerName`, `Get-EffectiveAudioPassthroughProfile`, `Get-EffectiveAudioTranscodeAutoBitrateByChannels`, `Get-EffectiveAudioTranscodeBitrate`, `Get-EffectiveAudioTranscodeCodec`, `Get-EffectiveCompatibleAudioCodecs`, `Get-LastAudioDecisionRecords`, `Get-NormalizedPreferredAudioLanguages`, `Get-PreferredDefaultAudioIndex`, `Get-TranscodedAudioChannelCount`, `Normalize-AudioLanguagePreferenceValue`, `Set-LastAudioDecisionRecords`, `Test-EffectiveAudioOutputContainerIsMp4`, `Test-IsPcmAudioCodec`, `Write-AudioTrackProgress`
**Invoked stages:** `audio-presence-probe`, `audio-stream-probe`, `audio_policy`, `audio_probe`
**Invoked tools:** `ffmpeg`, `ffprobe`, `mkvmerge`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/audio/audio.ps1`._
