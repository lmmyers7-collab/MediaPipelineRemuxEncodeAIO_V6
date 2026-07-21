---
file: ops/pipeline/engine/publish/pending_sidecar_transactions.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: publish
token_priority: high
owner_domain: publish
last_modified: 2026-07-20
last_reviewed: 2026-06-04
sha256: 3cb2584451631ab733bb98e543b071d6de50346d375b3b18a393f7b2f846c623
---
# `ops/pipeline/engine/publish/pending_sidecar_transactions.ps1`

**Purpose:** PowerShell implementation for pending sidecar transactions; exposes Complete-PendingPublishedSidecarFiles, Copy-PendingTx3gRecordWithStatus, New-PendingSidecarBackupPath.

**Public symbols:** `Complete-PendingPublishedSidecarFiles`, `Copy-PendingTx3gRecordWithStatus`, `New-PendingSidecarBackupPath`, `New-PendingTx3gPublishFailure`, `Publish-PendingSidecarFiles`, `Restore-PendingSidecarBackupIntoPlace`, `Test-PendingPublishedServerCopy`, `Undo-PendingPublishedSidecarFiles`
**Invoked stages:** `pending-tx3g-sidecar`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/publish/pending_sidecar_transactions.ps1`._
