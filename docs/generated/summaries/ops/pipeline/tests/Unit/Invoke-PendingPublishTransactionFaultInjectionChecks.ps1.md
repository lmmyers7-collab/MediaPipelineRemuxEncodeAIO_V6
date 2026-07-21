---
file: ops/pipeline/tests/Unit/Invoke-PendingPublishTransactionFaultInjectionChecks.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: publish
token_priority: high
owner_domain: tests
last_modified: 2026-07-20
last_reviewed: 2026-07-20
sha256: 335f6b053ffdeaa42862d38b9223cac89d3ba8be9004d1daeb42d0b2498d9668
---
# `ops/pipeline/tests/Unit/Invoke-PendingPublishTransactionFaultInjectionChecks.ps1`

**Purpose:** PowerShell implementation for invoke pending publish transaction fault injection checks; exposes Add-CompletedJobsManifestEntryFromSidecar, Add-RoundFailureRecord, Assert-Equal.

**Public symbols:** `Add-CompletedJobsManifestEntryFromSidecar`, `Add-RoundFailureRecord`, `Assert-Equal`, `Assert-True`, `Compare-PipelineVersion`, `Copy-FileRobocopy`, `Copy-SrtAtomic`, `Get-PublishCopyFailureReason`, `Get-SidecarPath`, `Invoke-FaultCheck`, `Invoke-WithFaultRoots`, `New-StandardFailureRecord`, `Refresh-PendingPublishIndex`, `Remove-PendingDrainLocalArtifacts`, `Set-ProgressStage`, `Test-PendingManifestTrustedForDrain`, `Test-PendingPublishedServerCopy`, `Test-SrtFileUsable`, `Update-PendingManifestDrainAttempt`, `Write-JsonLineAppend`, `Write-Log`, `Write-OutputSummary`, `Write-Sidecar`
**State/config identifiers:** `.manifest.json`, `local.manifest.json`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/tests/Unit/Invoke-PendingPublishTransactionFaultInjectionChecks.ps1`._
