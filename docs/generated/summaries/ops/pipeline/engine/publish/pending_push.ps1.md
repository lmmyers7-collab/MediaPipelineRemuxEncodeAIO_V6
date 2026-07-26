---
file: ops/pipeline/engine/publish/pending_push.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: publish
token_priority: high
owner_domain: publish
last_modified: 2026-07-20
last_reviewed: 2026-06-04
sha256: d35bfe45165270e42d0bd01f1a3b271c68489a23fa9d839750a872d026e37652
---
# `ops/pipeline/engine/publish/pending_push.ps1`

**Purpose:** PowerShell implementation for pending push; exposes Add-PendingDrainSummaryCount, Complete-PendingDrainSummary, Get-PendingDrainSummaryLogLine.

**Public symbols:** `Add-PendingDrainSummaryCount`, `Complete-PendingDrainSummary`, `Get-PendingDrainSummaryLogLine`, `Get-PendingDrainSummaryPath`, `Invoke-ParkPendingPush`, `Invoke-ParkPendingPushWithTx3gSidecars`, `Invoke-RetryPendingPushes`, `New-PendingDrainSummaryItem`, `Write-PendingDrainRuntimeProgress`, `Write-PendingDrainSummary`
**State/config identifiers:** `.manifest.json`, `manifest.json`, `pending_drain_summary.json`
**Invoked stages:** `pending-publish`, `pending-push-park`, `processing`, `retry_pending_push`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/publish/pending_push.ps1`._
