---
file: ops/pipeline/engine/queue/file_overrides.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: orchestration
token_priority: medium
owner_domain: queue
last_modified: 2026-07-09
last_reviewed: 2026-06-04
sha256: 1f8f161b15d76c12386fddf0fc0598a4de13fe5c5c9e3ece2b3d89de066f637a
---
# `ops/pipeline/engine/queue/file_overrides.ps1`

**Purpose:** Load file_overrides.json from the state root. Returns an empty manifest only when no persisted manifest exists. Existing malformed state fails closed.

**Public symbols:** `Assert-FileOverrideExactTrackSelectorsResolvable`, `ConvertTo-MediaPipelineFileOverrideConfigMap`, `ConvertTo-MediaPipelineFileOverrideSafeScalar`, `Get-AudioTrackTitleOverride`, `Get-FileOverrideAudioSettings`, `Get-FileOverridesManifest`, `Get-FileOverrideSubtitleBurnTrack`, `Get-FileOverrideSubtitleSettings`, `Get-MediaPipelineFileOverrideAllowedValues`, `Get-MediaPipelineFileOverrideProperty`, `Get-MediaPipelineFileOverrideRouteVideoFieldPaths`, `Get-MediaPipelineFileOverrideSelectorStreamIndex`, `Get-SubtitleTrackTitleOverride`, `Merge-FileOverrideIntoActiveOverrides`, `Normalize-MediaPipelineFileOverrideLanguage`, `Resolve-FileOverride`, `Resolve-FileOverrideMatch`, `Test-AudioTrackKeptByOverride`, `Test-MediaPipelineFileOverrideRuleMatchesTrack`, `Test-MediaPipelineFileOverrideTrackKindMatches`, `Test-SubtitleTrackBurnedByOverride`, `Test-SubtitleTrackKeptByOverride`
**Invoked tools:** `ffprobe`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/queue/file_overrides.ps1`._
