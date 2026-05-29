---
file: engine/audio/audio.ps1
pipeline_stage: audio
token_priority: medium
owner_domain: audio
last_modified: 2026-05-29
last_reviewed: 2026-05-29
sha256: b7ac7e99678db6316602f166f204f0f3e44df7b4e8d8a7f992f29499eeeb044b
---
# `engine/audio/audio.ps1`

**Purpose:** Suggestion #7 — pick an output bitrate appropriate for the codec /

**Functions:** `Build-AudioArgs`, `Get-AudioCodecFidelityRank`, `Get-AudioFidelityScore`, `Get-AudioTranscodeBitrateForChannels`, `Get-EffectiveAllowNoAudio`, `Get-EffectiveAudioDownmixMode`, `Get-EffectiveAudioMaxChannels`, `Get-EffectiveAudioPassthroughProfile`, `Get-EffectiveAudioTranscodeAutoBitrateByChannels`, `Get-EffectiveAudioTranscodeBitrate`, `Get-EffectiveAudioTranscodeCodec`, `Get-EffectiveCompatibleAudioCodecs`, `Get-LastAudioDecisionRecords`, `Get-NormalizedPreferredAudioLanguages`, `Get-PreferredDefaultAudioIndex`, `Get-TranscodedAudioChannelCount`, `Normalize-AudioLanguagePreferenceValue`, `Set-LastAudioDecisionRecords`, `Test-IsPcmAudioCodec`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths engine/audio/audio.ps1`._
