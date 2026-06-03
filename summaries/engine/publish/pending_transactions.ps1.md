---
file: engine/publish/pending_transactions.ps1
pipeline_stage: publish
token_priority: high
owner_domain: publish
last_modified: 2026-06-02
last_reviewed: 2026-05-29
sha256: 1b34f1c6e75134ef5d82c3c6461cebeaca444e746e47dfbbf016bff08dc1909c
---
# `engine/publish/pending_transactions.ps1`

**Purpose:** (no .SYNOPSIS block)

**Functions:** `Complete-PendingPublishedSidecarFiles`, `Copy-PendingTx3gRecordWithStatus`, `Get-FileLengthOrNull`, `Invoke-PendingDrainTransaction`, `Invoke-PendingParkTransaction`, `New-PendingDrainSidecarExtra`, `New-PendingParkManifest`, `New-PendingParkSidecarEntries`, `New-PendingSidecarBackupPath`, `New-PendingTx3gPublishFailure`, `New-PublishTransactionId`, `Publish-PendingSidecarFiles`, `Remove-PendingDrainLocalArtifacts`, `Repair-PendingManifestState`, `Repair-PendingSidecarArtifacts`, `Restore-PendingSidecarBackupIntoPlace`, `Test-PendingPublishedServerCopy`, `Undo-PendingPublishedSidecarFiles`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths engine/publish/pending_transactions.ps1`._
