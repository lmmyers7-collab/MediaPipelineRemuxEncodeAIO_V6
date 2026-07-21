---
file: ops/pipeline/engine/publish/pending_transactions.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: publish
token_priority: high
owner_domain: publish
last_modified: 2026-07-20
last_reviewed: 2026-06-04
sha256: 331ec67362def772636fa828e22abd0cd4ddce6eefc07fd33a1ab20f8497cb98
---
# `ops/pipeline/engine/publish/pending_transactions.ps1`

**Purpose:** PowerShell implementation for pending transactions; exposes Enter-PendingPublishTransactionLock, Exit-PendingPublishTransactionLock, Get-FileLengthOrNull.

**Public symbols:** `Enter-PendingPublishTransactionLock`, `Exit-PendingPublishTransactionLock`, `Get-FileLengthOrNull`, `Get-PendingFileSha256OrNull`, `Invoke-PendingPublishFaultPoint`, `New-PublishTransactionId`, `Test-PendingPublishFaultBoundary`, `Test-PendingPublishInjectedTermination`
**Invoked stages:** `callback`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/publish/pending_transactions.ps1`._
