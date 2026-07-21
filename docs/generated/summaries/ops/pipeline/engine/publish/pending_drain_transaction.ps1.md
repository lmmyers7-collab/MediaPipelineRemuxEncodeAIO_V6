---
file: ops/pipeline/engine/publish/pending_drain_transaction.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: publish
token_priority: high
owner_domain: publish
last_modified: 2026-07-20
last_reviewed: 2026-06-04
sha256: 46d6c8f7e847f79ac3c824d7fd162fa30e87d711ba20dcebe6976141d9fe9631
---
# `ops/pipeline/engine/publish/pending_drain_transaction.ps1`

**Purpose:** PowerShell implementation for pending drain transaction; exposes Invoke-PendingDrainTransaction, Invoke-PendingDrainTransactionCore, New-PendingDrainSidecarExtra.

**Public symbols:** `Invoke-PendingDrainTransaction`, `Invoke-PendingDrainTransactionCore`, `New-PendingDrainSidecarExtra`, `Remove-PendingDrainLocalArtifacts`
**Invoked stages:** `pending-tx3g-sidecar`, `retry_pending_push`, `sidecar`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/publish/pending_drain_transaction.ps1`._
