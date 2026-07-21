---
file: ops/pipeline/tests/Unit/Invoke-AudioPolicyChecks.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: n/a
token_priority: medium
owner_domain: tests
last_modified: 2026-07-20
last_reviewed: 2026-06-04
sha256: 165d55115706ae0e9fef53d2cc1b10ef8f953397bd013915650efbf0e82e0498
---
# `ops/pipeline/tests/Unit/Invoke-AudioPolicyChecks.ps1`

**Purpose:** PowerShell implementation for invoke audio policy checks; exposes Assert-Equal, Assert-SequenceEqual, Assert-True.

**Public symbols:** `Assert-Equal`, `Assert-SequenceEqual`, `Assert-True`, `DebugLog`, `Get-AudioTrackTitleOverride`, `Get-FileOverrideAudioSettings`, `Get-MediaAudioCodecDisplayLabel`, `Get-MediaAudioCodecFidelityRankValue`, `Get-MediaAudioCodecFlacName`, `Invoke-FFprobeCommand`, `Set-MediaPipelineRunMonitorAudioRecords`, `Set-ProgressAudioTrack`, `Test-AudioTrackKeptByOverride`, `Write-Log`
**Invoked tools:** `ffmpeg`, `ffprobe`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/tests/Unit/Invoke-AudioPolicyChecks.ps1`._
