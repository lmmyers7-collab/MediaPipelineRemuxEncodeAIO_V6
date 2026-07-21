---
file: ops/pipeline/engine/storage/scratch_copy.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: n/a
token_priority: medium
owner_domain: storage
last_modified: 2026-07-20
last_reviewed: 2026-06-04
sha256: c4c88a349168bc55650ba134e70c9c39d35c3e15acb27eff802a05ba79a2b6a3
---
# `ops/pipeline/engine/storage/scratch_copy.ps1`

**Purpose:** PowerShell implementation for scratch copy; exposes Ensure-ScratchCopy, Get-FingerprintPath, Get-ScratchCanonicalPath.

**Public symbols:** `Ensure-ScratchCopy`, `Get-FingerprintPath`, `Get-ScratchCanonicalPath`, `Get-ScratchFileContentIdentity`, `Get-ScratchFingerprintValidation`, `Get-ScratchInputPath`, `Get-SourceFingerprint`, `New-ScratchFingerprintValidationResult`, `Remove-EmptyScratchContainer`, `Remove-ScratchFingerprint`, `Set-MediaPipelineScratchCopyMonitorOutcome`, `Test-ScratchContainerCleanupBoundary`, `Test-ScratchContentIdentitySameBytes`, `Test-ScratchFingerprintMatches`, `Test-ScratchSafeLeafName`, `Test-ScratchSourceIdentityStable`, `Write-ScratchCleanupBoundaryLog`, `Write-ScratchFingerprint`
**Invoked stages:** `copy_to_scratch`, `Id`, `scratch-integrity`
**Invoked tools:** `ffprobe`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/storage/scratch_copy.ps1`._
