---
file: ops/pipeline/engine/shared/failure_codes.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: n/a
token_priority: medium
owner_domain: shared
last_modified: 2026-07-23
last_reviewed: 2026-06-04
sha256: 2aa6c610c3e4e5eaddb0a8a2d62abac574500299b7b68c63a314cb1af53d2067
---
# `ops/pipeline/engine/shared/failure_codes.ps1`

**Purpose:** PowerShell implementation for failure codes; exposes Get-EncodeAttachmentMuxFailureCode, Get-EncodeMkvmergeFailureCode, Get-ErrorTextSummary.

**Public symbols:** `Get-EncodeAttachmentMuxFailureCode`, `Get-EncodeMkvmergeFailureCode`, `Get-ErrorTextSummary`, `Get-FFmpegFailureCode`, `Get-FFprobeFailureCode`, `Get-MediaPipelineCodeFamily`, `Get-MediaPipelineCodeHandledBy`, `Get-MediaPipelineCodeOperatorAction`, `Get-MediaPipelineCodeOperatorSeverity`, `Get-MediaPipelineCodeRetryable`, `Get-MediaPipelineCodeStage`, `Get-MediaPipelineCodeWhenFires`, `Get-MediaPipelineFailureCodeFamily`, `Get-MediaPipelineFailureCodeMetadata`, `Get-MediaPipelineFailureCodeRegistry`, `Get-MediaPipelineKnownFailureCodes`, `Get-MediaPipelineKnownOutcomeCodes`, `Get-MediaPipelineOutcomeCodeFamily`, `Get-MediaPipelineOutcomeCodeMetadata`, `Get-MediaPipelineOutcomeCodeRegistry`, `Get-MkvmergeFailureCode`, `New-MediaPipelineCodeMetadata`, `Test-IsNvencError`, `Test-MediaPipelineKnownFailureCode`, `Test-MediaPipelineKnownOutcomeCode`
**Invoked tools:** `ffmpeg`, `ffprobe`, `mkvmerge`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/shared/failure_codes.ps1`._
