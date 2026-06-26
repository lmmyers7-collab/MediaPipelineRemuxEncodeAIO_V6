---
file: ops/pipeline/engine/queue/file_overrides.ps1
pipeline_stage: orchestration
token_priority: medium
owner_domain: queue
last_modified: 2026-06-04
last_reviewed: 2026-06-04
sha256: 598b9ff252ae8e92225b92577904164ff592e63a5691d9e93ae14a7771b83f57
---
# `ops/pipeline/engine/queue/file_overrides.ps1`

**Purpose:** Load file_overrides.json from the state root.

**Functions:** `Assert-FileOverrideExactTrackSelectorsResolvable`, `ConvertTo-MediaPipelineFileOverrideConfigMap`, `ConvertTo-MediaPipelineFileOverrideSafeScalar`, `Get-AudioTrackTitleOverride`, `Get-FileOverrideAudioSettings`, `Get-FileOverrideSubtitleBurnTrack`, `Get-FileOverrideSubtitleSettings`, `Get-FileOverridesManifest`, `Get-MediaPipelineFileOverrideAllowedValues`, `Get-MediaPipelineFileOverrideProperty`, `Get-MediaPipelineFileOverrideRouteVideoFieldPaths`, `Get-MediaPipelineFileOverrideSelectorStreamIndex`, `Get-SubtitleTrackTitleOverride`, `Merge-FileOverrideIntoActiveOverrides`, `Normalize-MediaPipelineFileOverrideLanguage`, `Resolve-FileOverride`, `Resolve-FileOverrideMatch`, `Test-AudioTrackKeptByOverride`, `Test-MediaPipelineFileOverrideRuleMatchesTrack`, `Test-MediaPipelineFileOverrideTrackKindMatches`, `Test-SubtitleTrackBurnedByOverride`, `Test-SubtitleTrackKeptByOverride`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/queue/file_overrides.ps1`._
