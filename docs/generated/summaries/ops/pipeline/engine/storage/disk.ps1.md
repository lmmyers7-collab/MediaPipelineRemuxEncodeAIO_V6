---
file: ops/pipeline/engine/storage/disk.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: n/a
token_priority: medium
owner_domain: storage
last_modified: 2026-06-30
last_reviewed: 2026-06-04
sha256: f6de409561ac29a435717ea811cfffb7fdada6491635fa4812d33609ee76423e
---
# `ops/pipeline/engine/storage/disk.ps1`

**Purpose:** PowerShell implementation for disk; exposes Clear-EmptyLocalEncodedDirectories, Clear-StalePartialFiles, Copy-FileRobocopy.

**Public symbols:** `Clear-EmptyLocalEncodedDirectories`, `Clear-StalePartialFiles`, `Copy-FileRobocopy`, `Get-FreeSpaceGB`, `Get-FreeSpaceGBAny`, `Get-MediaPipelineCopyDestinationRootCandidates`, `Get-MediaPipelineCopyScriptVariableText`, `Get-RobocopyProcessWriteByteCount`, `Get-UncFreeSpaceGBBounded`, `Invoke-PeriodicLocalEncodedDirectoryCleanup`, `Resolve-MediaPipelineCopyDestinationRoot`, `Resolve-RobocopyActiveCopyProgressBytes`, `Resolve-RobocopyPath`, `Test-DiskSpace`, `Test-EstimatedOutputSpace`, `Test-MediaPipelineLocalEncodedCleanupRoot`, `Test-MediaPipelineStalePartialArtifactName`
**Invoked stages:** `check`, `pipeline`
**Invoked tools:** `ffmpeg`, `mkvmerge`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/storage/disk.ps1`._
