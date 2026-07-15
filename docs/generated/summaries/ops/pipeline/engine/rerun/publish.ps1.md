---
file: ops/pipeline/engine/rerun/publish.ps1
pipeline_stage: publish
token_priority: medium
owner_domain: rerun
last_modified: 2026-07-14
last_reviewed: 2026-07-11
sha256: 62d6fa994c5f06f542196c4369bb7ed73e4b49d35d4d52d346bee4bb02e88fcd
---
# `ops/pipeline/engine/rerun/publish.ps1`

**Purpose:** (no .SYNOPSIS block)

**Functions:** `Backup-RerunFinalCompanionPath`, `Copy-RerunFinalSrtSidecars`, `Get-RerunFinalCompanionPath`, `Get-RerunNonOverlapPath`, `Invoke-RerunDestinationPolicy`, `Invoke-RerunOriginalPolicy`, `Move-RerunVerifiedOutput`, `New-RerunPendingPublishManifest`, `Publish-RerunPipelineSidecarToFinal`, `Publish-RerunReplaceFinal`, `Remove-RerunStagedInputs`, `Reset-RerunStageRoot`, `Resolve-RerunPendingPublishServerOut`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/rerun/publish.ps1`._
