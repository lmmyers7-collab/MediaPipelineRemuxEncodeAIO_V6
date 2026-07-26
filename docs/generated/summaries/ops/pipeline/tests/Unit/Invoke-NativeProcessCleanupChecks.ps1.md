---
file: ops/pipeline/tests/Unit/Invoke-NativeProcessCleanupChecks.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: n/a
token_priority: medium
owner_domain: tests
last_modified: 2026-07-20
last_reviewed: 2026-06-04
sha256: a1f25c704e923a2857ffeedee943f25a086df86c012deaf01fcc709a0cf74df2
---
# `ops/pipeline/tests/Unit/Invoke-NativeProcessCleanupChecks.ps1`

**Purpose:** PowerShell implementation for invoke native process cleanup checks; exposes Assert-True, ConvertTo-MediaPipelineRunMonitorStageId, DebugLog.

**Public symbols:** `Assert-True`, `ConvertTo-MediaPipelineRunMonitorStageId`, `DebugLog`, `Format-NativeCommandLine`, `New-MediaPipelineCurrentStageNativePollHandler`, `Set-ProgressStage`, `Test-IsUncPath`, `Test-ProcessAlive`, `Wait-ProcessExitObserved`, `Write-Log`, `Write-PipelineEvent`
**Invoked stages:** `callback`, `different-internal-label`, `expected-exit-telemetry`, `fallback`, `internal-tool-label-must-not-be-authority`, `native-ocr-poll-forwarding`, `probe`, `wrapper-failure`, `wrapper-success`, `wrapper-timeout`
**Invoked tools:** `ffmpeg`, `ffprobe`, `mkvmerge`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/tests/Unit/Invoke-NativeProcessCleanupChecks.ps1`._
