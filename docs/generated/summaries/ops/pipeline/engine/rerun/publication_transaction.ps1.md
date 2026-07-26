---
file: ops/pipeline/engine/rerun/publication_transaction.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: n/a
token_priority: medium
owner_domain: rerun
last_modified: 2026-07-23
last_reviewed: 2026-07-23
sha256: f8296c5ab9ef7b5b23e36a1aa4d964652c0a90ebb90b95cf2bdaa30a514f3142
---
# `ops/pipeline/engine/rerun/publication_transaction.ps1`

**Purpose:** PowerShell implementation for publication transaction; exposes Copy-RerunPublicationArtifactToStage, Get-RerunPublicationFileIdentity, Get-RerunPublicationTransactionPath.

**Public symbols:** `Copy-RerunPublicationArtifactToStage`, `Get-RerunPublicationFileIdentity`, `Get-RerunPublicationTransactionPath`, `Invoke-RerunFinalPublicationTransaction`, `Invoke-RerunPublicationCheckpoint`, `Move-RerunPublicationBackupsToHold`, `New-RerunFinalPublicationTransaction`, `New-RerunPublicationArtifact`, `New-RerunPublicationSidecarPayload`, `Repair-RerunFinalPublicationTransaction`, `Restore-RerunPublicationTransaction`, `Set-RerunPlanFromCommittedPublication`, `Set-RerunPublicationTransactionState`, `Sync-RerunPublicationPlanEvidence`, `Test-RerunCompletedPublicationEntry`, `Test-RerunPublicationDestinationsCommitted`, `Test-RerunPublicationFileIdentity`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/rerun/publication_transaction.ps1`._
