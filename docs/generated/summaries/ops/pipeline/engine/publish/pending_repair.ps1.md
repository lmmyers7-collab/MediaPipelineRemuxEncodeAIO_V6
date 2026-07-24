---
file: ops/pipeline/engine/publish/pending_repair.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: publish
token_priority: high
owner_domain: publish
last_modified: 2026-07-23
last_reviewed: 2026-06-04
sha256: 871e2b352f9422cd3bafe75660bc37b57aa2de8b3b7eb53dc60aa44c4549d373
---
# `ops/pipeline/engine/publish/pending_repair.ps1`

**Purpose:** PowerShell implementation for pending repair; exposes Get-PendingDrainPipelineSidecarBackupPath, Invoke-PendingPublishRecovery, Repair-PendingManifestState.

**Public symbols:** `Get-PendingDrainPipelineSidecarBackupPath`, `Invoke-PendingPublishRecovery`, `Repair-PendingManifestState`, `Repair-PendingSidecarArtifacts`, `Repair-PendingStaleDrainAttempt`, `Restore-PendingStaleDrainArtifacts`, `Test-PendingDrainFinalProof`
**State/config identifiers:** `.manifest.json`
**Invoked stages:** `crash`, `pending-publish-recovery`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/publish/pending_repair.ps1`._
