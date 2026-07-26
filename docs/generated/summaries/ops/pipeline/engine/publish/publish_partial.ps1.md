---
file: ops/pipeline/engine/publish/publish_partial.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: publish
token_priority: medium
owner_domain: publish
last_modified: 2026-07-10
last_reviewed: 2026-06-04
sha256: 20503b466ad90bbc05504760e3fa4dd80b7a3c1807e3e3cb6ad5c70b9090a4ac
---
# `ops/pipeline/engine/publish/publish_partial.ps1`

**Purpose:** PowerShell implementation for publish partial; exposes Backup-PublishSidecarForReveal, Complete-PublishMediaReveal, Get-PublishSidecarBackupPath.

**Public symbols:** `Backup-PublishSidecarForReveal`, `Complete-PublishMediaReveal`, `Get-PublishSidecarBackupPath`, `Move-PublishSidecarBackupIntoPlace`, `New-PublishPartialMediaPath`, `New-PublishSidecarBackupResult`, `Remove-PublishPartialMedia`, `Remove-PublishSidecarBackup`, `Restore-PublishMediaAfterRevealFailure`, `Restore-PublishSidecarAfterRevealFailure`, `Test-PublishSidecarBackupReadyForReveal`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/publish/publish_partial.ps1`._
