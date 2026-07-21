---
file: ops/pipeline/engine/publish/publish_sidecars.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: publish
token_priority: medium
owner_domain: publish
last_modified: 2026-07-16
last_reviewed: 2026-06-04
sha256: 7d0d4a4c87e8abfaba28254095b1fcf149da4ee42f78e666cba19765d408ce32
---
# `ops/pipeline/engine/publish/publish_sidecars.ps1`

**Purpose:** PowerShell implementation for publish sidecars; exposes Complete-PublishedSidecarFiles, Get-PublishedSidecarProperty, New-PublishedSidecarBackupPath.

**Public symbols:** `Complete-PublishedSidecarFiles`, `Get-PublishedSidecarProperty`, `New-PublishedSidecarBackupPath`, `Publish-Tx3gSrtSidecarsFromPlan`, `Restore-PublishedSidecarBackupIntoPlace`, `Undo-PublishedSidecarFiles`
**Invoked stages:** `sidecar_write`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/publish/publish_sidecars.ps1`._
