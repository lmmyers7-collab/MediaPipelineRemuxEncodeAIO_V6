---
file: engine/audio/audio.ps1
pipeline_stage: audio
token_priority: medium
owner_domain: audio
last_modified: 2026-06-02
last_reviewed: 2026-05-29
sha256: de3eb80c45963d0cc9965be08facab196051f99ed5505ba1f68a619b837597df
---
# `engine/audio/audio.ps1`

**Purpose:** Suggestion #7 — pick an output bitrate appropriate for the codec /

**Functions:** `Build-AudioArgs`, `ConvertTo-EffectiveAudioBoolean`, `Get-AudioCodecFidelityRank`, `Get-AudioFidelityScore`, `Get-AudioTranscodeBitrateForChannels`, `Get-EffectiveAllowNoAudio`, `Get-EffectiveAudioDownmixMode`, `Get-EffectiveAudioMaxChannels`, `Get-EffectiveAudioPassthroughProfile`, `Get-EffectiveAudioTranscodeAutoBitrateByChannels`, `Get-EffectiveAudioTranscodeBitrate`, `Get-EffectiveAudioTranscodeCodec`, `Get-EffectiveCompatibleAudioCodecs`, `Get-LastAudioDecisionRecords`, `Get-NormalizedPreferredAudioLanguages`, `Get-PreferredDefaultAudioIndex`, `Get-TranscodedAudioChannelCount`, `Normalize-AudioLanguagePreferenceValue`, `Set-LastAudioDecisionRecords`, `Test-IsPcmAudioCodec`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths engine/audio/audio.ps1`._
