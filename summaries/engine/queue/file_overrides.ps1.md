---
file: engine/queue/file_overrides.ps1
pipeline_stage: orchestration
token_priority: medium
owner_domain: queue
last_modified: 2026-06-03
last_reviewed: 2026-05-29
sha256: c936a5bdba786a90948ce54fb85162985ada98444e2159e9442954ea4f06e7d3
---
# `engine/queue/file_overrides.ps1`

**Purpose:** Load file_overrides.json from the state root.

**Functions:** `Assert-FileOverrideExactTrackSelectorsResolvable`, `ConvertTo-MediaPipelineFileOverrideConfigMap`, `ConvertTo-MediaPipelineFileOverrideSafeScalar`, `Get-AudioTrackTitleOverride`, `Get-FileOverrideAudioSettings`, `Get-FileOverrideSubtitleBurnTrack`, `Get-FileOverrideSubtitleSettings`, `Get-FileOverridesManifest`, `Get-MediaPipelineFileOverrideAllowedValues`, `Get-MediaPipelineFileOverrideProperty`, `Get-MediaPipelineFileOverrideRouteVideoFieldPaths`, `Get-MediaPipelineFileOverrideSelectorStreamIndex`, `Get-SubtitleTrackTitleOverride`, `Merge-FileOverrideIntoActiveOverrides`, `Normalize-MediaPipelineFileOverrideLanguage`, `Resolve-FileOverride`, `Resolve-FileOverrideMatch`, `Test-AudioTrackKeptByOverride`, `Test-MediaPipelineFileOverrideRuleMatchesTrack`, `Test-MediaPipelineFileOverrideTrackKindMatches`, `Test-SubtitleTrackBurnedByOverride`, `Test-SubtitleTrackKeptByOverride`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths engine/queue/file_overrides.ps1`._
