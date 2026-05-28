---
file: Pipeline/Modules/Audio.Policy.ps1
pipeline_stage: audio
token_priority: medium
owner_domain: Audio
last_modified: 2026-05-25
last_reviewed: 2026-05-28
sha256: 08a324e96d2376a825c80f856e7807a131d89ad6ca0f796826973756e139a6fe
---
# `Pipeline/Modules/Audio.Policy.ps1`

**Purpose:** Suggestion #7 — pick an output bitrate appropriate for the codec /

**Functions:** `Get-AudioCodecFidelityRank`, `Get-AudioFidelityScore`, `Get-AudioTranscodeBitrateForChannels`, `Get-EffectiveAllowNoAudio`, `Get-EffectiveAudioDownmixMode`, `Get-EffectiveAudioMaxChannels`, `Get-EffectiveAudioPassthroughProfile`, `Get-EffectiveAudioTranscodeAutoBitrateByChannels`, `Get-EffectiveAudioTranscodeBitrate`, `Get-EffectiveAudioTranscodeCodec`, `Get-EffectiveCompatibleAudioCodecs`, `Get-NormalizedPreferredAudioLanguages`, `Get-TranscodedAudioChannelCount`, `Normalize-AudioLanguagePreferenceValue`, `Test-IsPcmAudioCodec`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths Pipeline/Modules/Audio.Policy.ps1`._
