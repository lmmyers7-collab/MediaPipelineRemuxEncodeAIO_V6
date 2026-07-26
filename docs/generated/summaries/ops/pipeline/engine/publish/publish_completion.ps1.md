---
file: ops/pipeline/engine/publish/publish_completion.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: publish
token_priority: medium
owner_domain: publish
last_modified: 2026-07-16
last_reviewed: 2026-06-04
sha256: b1e3ed2ef59fddfc56daa8fc60c3b1b20cefb280a87ee1c3761ce9fa00539e2a
---
# `ops/pipeline/engine/publish/publish_completion.ps1`

**Purpose:** PowerShell implementation for publish completion; exposes Complete-PipelineOutputPublish, Get-PendingParkResultOutputSize, Get-SubtitleConversionEvidenceValue.

**Public symbols:** `Complete-PipelineOutputPublish`, `Get-PendingParkResultOutputSize`, `Get-SubtitleConversionEvidenceValue`, `New-NormalizedSubtitleConversionResults`, `Set-MediaPipelinePendingParkMonitorStages`, `Set-MediaPipelinePublishMonitorStageOutcome`
**Invoked stages:** `Id`, `Prefix`, `push`, `sidecar`, `subtitle-tx3g-publish`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/publish/publish_completion.ps1`._
