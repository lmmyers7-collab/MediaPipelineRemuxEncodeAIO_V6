---
file: ops/pipeline/tests/Unit/Invoke-EncodeCoreSplitChecks.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: n/a
token_priority: medium
owner_domain: tests
last_modified: 2026-07-15
last_reviewed: 2026-06-24
sha256: 3c856acaac8a1d5bb167ea19d644cf7b6db3b40f93a66f1dddfa9063fd7ed479
---
# `ops/pipeline/tests/Unit/Invoke-EncodeCoreSplitChecks.ps1`

**Purpose:** PowerShell implementation for invoke encode core split checks; exposes Assert-Equal, Assert-False, Assert-True.

**Public symbols:** `Assert-Equal`, `Assert-False`, `Assert-True`, `Clear-SourceFailureState`, `Ensure-ScratchCopy`, `Get-HDRState`, `Get-OutputPaths`, `Get-SafeLocalName`, `Invoke-FFmpegWithProgress`, `Invoke-MediaPipelineEncodePreflight`, `Invoke-Tx3gSidecarExportForExistingOutput`, `New-EncodeAttemptPlan`, `New-ExistingOutputPublishResult`, `Register-SourceFailure`, `Remove-EmptyScratchContainer`, `Remove-ScratchFingerprint`, `Reset-EncodeHarness`, `Set-ProgressStage`, `Test-DiskSpace`, `Test-EstimatedOutputSpace`, `Test-OutputNeedsReprocess`, `Test-SourceVideoStreamPublishPolicy`, `Write-Log`
**Invoked tools:** `ffmpeg`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/tests/Unit/Invoke-EncodeCoreSplitChecks.ps1`._
