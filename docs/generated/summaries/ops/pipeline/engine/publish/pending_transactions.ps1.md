---
file: ops/pipeline/engine/publish/pending_transactions.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: publish
token_priority: high
owner_domain: publish
last_modified: 2026-07-23
last_reviewed: 2026-06-04
sha256: 9cf51434d5ad9ac8e7db2ed1a6508fa41d858afd958c87af83cb52b15145fdb3
---
# `ops/pipeline/engine/publish/pending_transactions.ps1`

**Purpose:** PowerShell implementation for pending transactions; exposes Enter-PendingPublishDestinationLock, Enter-PendingPublishTransactionLock, Exit-PendingPublishDestinationLock.

**Public symbols:** `Enter-PendingPublishDestinationLock`, `Enter-PendingPublishTransactionLock`, `Exit-PendingPublishDestinationLock`, `Exit-PendingPublishTransactionLock`, `Get-FileLengthOrNull`, `Get-PendingFileSha256OrNull`, `Get-PendingPublishDestinationIdentity`, `Get-PendingPublishDestinationLockPath`, `Get-PendingPublishDuplicateDestinationManifestPaths`, `Invoke-PendingPublishFaultPoint`, `New-PublishTransactionId`, `Test-PendingPublishFaultBoundary`, `Test-PendingPublishInjectedTermination`
**State/config identifiers:** `.manifest.json`
**Invoked stages:** `callback`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/publish/pending_transactions.ps1`._
