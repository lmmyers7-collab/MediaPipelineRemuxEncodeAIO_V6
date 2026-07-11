---
file: ops/pipeline/engine/rerun/publish.ps1
pipeline_stage: publish
token_priority: medium
owner_domain: rerun
last_modified: 2026-07-11
last_reviewed: 2026-07-11
sha256: 92f698b35893716f324ad9b7f95c87b0982b004f3bc9c8a465ca413888930cbe
---
# `ops/pipeline/engine/rerun/publish.ps1`

**Purpose:** (no .SYNOPSIS block)

**Functions:** `Backup-RerunFinalCompanionPath`, `Copy-RerunFinalSrtSidecars`, `Get-RerunFinalCompanionPath`, `Get-RerunNonOverlapPath`, `Invoke-RerunDestinationPolicy`, `Invoke-RerunOriginalPolicy`, `Move-RerunVerifiedOutput`, `New-RerunPendingPublishManifest`, `Publish-RerunPipelineSidecarToFinal`, `Publish-RerunReplaceFinal`, `Remove-RerunStagedInputs`, `Reset-RerunStageRoot`, `Resolve-RerunPendingPublishServerOut`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/rerun/publish.ps1`._
