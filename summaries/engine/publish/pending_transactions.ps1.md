---
file: engine/publish/pending_transactions.ps1
pipeline_stage: publish
token_priority: high
owner_domain: publish
last_modified: 2026-05-28
last_reviewed: 2026-05-29
sha256: 0a6187e44c9f8cdfdf995bf6636df3e699074ca27579559cce31762358a1e9e4
---
# `engine/publish/pending_transactions.ps1`

**Purpose:** (no .SYNOPSIS block)

**Functions:** `Complete-PendingPublishedSidecarFiles`, `Copy-PendingTx3gRecordWithStatus`, `Get-FileLengthOrNull`, `Invoke-PendingDrainTransaction`, `Invoke-PendingParkTransaction`, `New-PendingDrainSidecarExtra`, `New-PendingParkManifest`, `New-PendingParkSidecarEntries`, `New-PendingSidecarBackupPath`, `New-PendingTx3gPublishFailure`, `New-PublishTransactionId`, `Publish-PendingSidecarFiles`, `Remove-PendingDrainLocalArtifacts`, `Repair-PendingManifestState`, `Repair-PendingSidecarArtifacts`, `Test-PendingPublishedServerCopy`, `Undo-PendingPublishedSidecarFiles`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths engine/publish/pending_transactions.ps1`._
