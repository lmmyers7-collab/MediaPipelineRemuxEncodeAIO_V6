---
file: ops/pipeline/engine/audio/audio.ps1
pipeline_stage: audio
token_priority: medium
owner_domain: audio
last_modified: 2026-06-04
last_reviewed: 2026-06-04
sha256: 97a2f85d315580292d98d00b0e19a8be5026832bdc982a84dddbbeb0c85acd16
---
# `ops/pipeline/engine/audio/audio.ps1`

**Purpose:** Suggestion #7 — pick an output bitrate appropriate for the codec /

**Functions:** `Build-AudioArgs`, `ConvertTo-EffectiveAudioBoolean`, `Get-AudioCodecFidelityRank`, `Get-AudioFidelityScore`, `Get-AudioTranscodeBitrateForChannels`, `Get-EffectiveAllowNoAudio`, `Get-EffectiveAudioDownmixMode`, `Get-EffectiveAudioMaxChannels`, `Get-EffectiveAudioPassthroughProfile`, `Get-EffectiveAudioTranscodeAutoBitrateByChannels`, `Get-EffectiveAudioTranscodeBitrate`, `Get-EffectiveAudioTranscodeCodec`, `Get-EffectiveCompatibleAudioCodecs`, `Get-LastAudioDecisionRecords`, `Get-NormalizedPreferredAudioLanguages`, `Get-PreferredDefaultAudioIndex`, `Get-TranscodedAudioChannelCount`, `Normalize-AudioLanguagePreferenceValue`, `Set-LastAudioDecisionRecords`, `Test-IsPcmAudioCodec`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/audio/audio.ps1`._
