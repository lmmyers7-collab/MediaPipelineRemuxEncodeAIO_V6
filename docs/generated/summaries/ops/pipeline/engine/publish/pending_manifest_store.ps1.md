---
file: ops/pipeline/engine/publish/pending_manifest_store.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: publish
token_priority: high
owner_domain: publish
last_modified: 2026-07-20
last_reviewed: 2026-07-10
sha256: 71fe395a741430a49d118ca0a63833b4ec4c7d14368713f2c0bfbfb2fb7286c8
---
# `ops/pipeline/engine/publish/pending_manifest_store.ps1`

**Purpose:** PowerShell implementation for pending manifest store; exposes ConvertTo-PendingManifestMap, Get-PendingManifestConfiguredOutputRoot, Get-PendingManifestConfiguredSourceRoots.

**Public symbols:** `ConvertTo-PendingManifestMap`, `Get-PendingManifestConfiguredOutputRoot`, `Get-PendingManifestConfiguredSourceRoots`, `Get-PendingManifestFilePathText`, `Get-PendingManifestLocalEncodedRoot`, `Get-PendingManifestPathKey`, `Get-PendingManifestRetryCount`, `Get-PendingManifestText`, `Get-PendingObjectProperty`, `Get-PendingPublishRetryLimit`, `Get-PendingScriptVariableText`, `Get-PendingSidecarEntries`, `New-PendingManifestTrustResult`, `Read-PendingManifestFile`, `Test-PendingManifestBoolFieldValid`, `Test-PendingManifestBoolTrue`, `Test-PendingManifestCurrentContractFields`, `Test-PendingManifestDestinationTrusted`, `Test-PendingManifestPathBoundary`, `Test-PendingManifestPathOutsideForbiddenRoots`, `Test-PendingManifestPathUnderRoot`, `Test-PendingManifestRoundTripValid`, `Test-PendingManifestTrustedForDrain`, `Test-PendingManifestTrustedForRepair`, `Test-PendingObjectHasProperty`, `Test-PendingSidecarTrustedForPublish`, `Update-PendingManifestDrainAttempt`, `Update-PendingManifestReplacementEvidence`, `Update-PendingManifestRetryState`, `Update-PendingManifestReviewState`, `Update-PendingManifestTransactionPhase`, `Update-PendingManifestTx3gFailures`, `Write-PendingManifestFile`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/publish/pending_manifest_store.ps1`._
