---
file: ops/pipeline/engine/audio/audio.ps1
pipeline_stage: audio
token_priority: medium
owner_domain: audio
last_modified: 2026-07-10
last_reviewed: 2026-06-04
sha256: 12c625b3827a07e91df159fcf2e0fdb618c18dcfa864b7b4b9cfa16ff67efa69
---
# `ops/pipeline/engine/audio/audio.ps1`

**Purpose:** Suggestion #7 — pick an output bitrate appropriate for the codec /

**Functions:** `Build-AudioArgs`, `ConvertTo-EffectiveAudioBoolean`, `Get-AudioCodecFidelityRank`, `Get-AudioFidelityScore`, `Get-AudioTranscodeBitrateForChannels`, `Get-EffectiveAllowNoAudio`, `Get-EffectiveAudioDownmixMode`, `Get-EffectiveAudioMaxChannels`, `Get-EffectiveAudioOutputContainerName`, `Get-EffectiveAudioPassthroughProfile`, `Get-EffectiveAudioTranscodeAutoBitrateByChannels`, `Get-EffectiveAudioTranscodeBitrate`, `Get-EffectiveAudioTranscodeCodec`, `Get-EffectiveCompatibleAudioCodecs`, `Get-LastAudioDecisionRecords`, `Get-NormalizedPreferredAudioLanguages`, `Get-PreferredDefaultAudioIndex`, `Get-TranscodedAudioChannelCount`, `Normalize-AudioLanguagePreferenceValue`, `Set-LastAudioDecisionRecords`, `Test-EffectiveAudioOutputContainerIsMp4`, `Test-IsPcmAudioCodec`, `Write-AudioTrackProgress`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/audio/audio.ps1`._
