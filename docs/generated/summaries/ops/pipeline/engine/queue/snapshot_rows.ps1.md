---
file: ops/pipeline/engine/queue/snapshot_rows.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: orchestration
token_priority: medium
owner_domain: queue
last_modified: 2026-07-20
last_reviewed: 2026-06-04
sha256: 7b6027fa601d7d1523465327ad0696a4b7cfe4308a57692e234d305f60d9d8d9
---
# `ops/pipeline/engine/queue/snapshot_rows.ps1`

**Purpose:** PowerShell implementation for snapshot rows; exposes Assert-MediaPipelineRunMonitorActiveMembershipMatchesAcceptedSnapshot, Build-QueuePlanSnapshotRows, ConvertTo-MediaPipelineAcceptedRunFingerprintField.

**Public symbols:** `Assert-MediaPipelineRunMonitorActiveMembershipMatchesAcceptedSnapshot`, `Build-QueuePlanSnapshotRows`, `ConvertTo-MediaPipelineAcceptedRunFingerprintField`, `ConvertTo-MediaPipelineQueueFingerprintField`, `Get-MediaPipelineAcceptedRunRowsFingerprint`, `Get-MediaPipelineQueueInputFingerprint`, `Get-MediaPipelineQueuePlanFingerprint`, `Get-MediaPipelineRunMonitorSeedRowsFromAcceptedSnapshot`, `Get-MediaPipelineSha256Text`, `Get-QueuePlanPreflightBlock`, `New-QueuePlanExcludedSnapshotRow`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/queue/snapshot_rows.ps1`._
