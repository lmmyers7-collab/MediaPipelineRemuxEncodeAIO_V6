---
file: ops/pipeline/tests/Unit/Invoke-AudioPolicyChecks.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: n/a
token_priority: medium
owner_domain: tests
last_modified: 2026-07-16
last_reviewed: 2026-06-04
sha256: 5061e4a2226a9089e5a05609c5e0d2fbd0a54b56ef4a1744e344c6e51be88552
---
# `ops/pipeline/tests/Unit/Invoke-AudioPolicyChecks.ps1`

**Purpose:** PowerShell implementation for invoke audio policy checks; exposes Assert-Equal, Assert-SequenceEqual, Assert-True.

**Public symbols:** `Assert-Equal`, `Assert-SequenceEqual`, `Assert-True`, `DebugLog`, `Get-AudioTrackTitleOverride`, `Get-FileOverrideAudioSettings`, `Get-MediaAudioCodecDisplayLabel`, `Get-MediaAudioCodecFidelityRankValue`, `Get-MediaAudioCodecFlacName`, `Get-MediaPipelineAudioPassthroughProfileCodecs`, `Invoke-FFprobeCommand`, `Resolve-MediaPipelineAudioPassthroughProfile`, `Set-MediaPipelineRunMonitorAudioRecords`, `Set-ProgressAudioTrack`, `Test-AudioTrackKeptByOverride`, `Write-Log`
**Invoked tools:** `ffmpeg`, `ffprobe`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/tests/Unit/Invoke-AudioPolicyChecks.ps1`._
