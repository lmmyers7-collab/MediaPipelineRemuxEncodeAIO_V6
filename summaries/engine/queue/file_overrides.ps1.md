---
file: engine/queue/file_overrides.ps1
pipeline_stage: orchestration
token_priority: medium
owner_domain: queue
last_modified: 2026-06-02
last_reviewed: 2026-05-29
sha256: c158aff2728718b7837e30de6870ff3b391a39cb796c84becf977c219ac721dc
---
# `engine/queue/file_overrides.ps1`

**Purpose:** Load file_overrides.json from the state root.

**Functions:** `Assert-FileOverrideExactTrackSelectorsResolvable`, `ConvertTo-MediaPipelineFileOverrideConfigMap`, `ConvertTo-MediaPipelineFileOverrideSafeScalar`, `Get-AudioTrackTitleOverride`, `Get-FileOverrideAudioSettings`, `Get-FileOverrideSubtitleSettings`, `Get-FileOverridesManifest`, `Get-MediaPipelineFileOverrideAllowedValues`, `Get-MediaPipelineFileOverrideProperty`, `Get-MediaPipelineFileOverrideRouteVideoFieldPaths`, `Get-MediaPipelineFileOverrideSelectorStreamIndex`, `Get-SubtitleTrackTitleOverride`, `Merge-FileOverrideIntoActiveOverrides`, `Normalize-MediaPipelineFileOverrideLanguage`, `Resolve-FileOverride`, `Resolve-FileOverrideMatch`, `Test-AudioTrackKeptByOverride`, `Test-MediaPipelineFileOverrideRuleMatchesTrack`, `Test-MediaPipelineFileOverrideTrackKindMatches`, `Test-SubtitleTrackKeptByOverride`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths engine/queue/file_overrides.ps1`._
