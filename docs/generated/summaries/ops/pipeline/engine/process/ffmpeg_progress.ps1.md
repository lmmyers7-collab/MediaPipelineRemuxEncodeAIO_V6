---
file: ops/pipeline/engine/process/ffmpeg_progress.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: transcode
token_priority: medium
owner_domain: process
last_modified: 2026-07-16
last_reviewed: 2026-06-04
sha256: 91b058d9575f8043a570c50efc49b1e12e29a17cf2b1225a46d4a162aa9b4225
---
# `ops/pipeline/engine/process/ffmpeg_progress.ps1`

**Purpose:** PowerShell implementation for ffmpeg progress; exposes Get-FFmpegWasteGuardContextValue, Get-MkvmergeProgressPercentFromLine, Get-MkvmergeWarningClassification.

**Public symbols:** `Get-FFmpegWasteGuardContextValue`, `Get-MkvmergeProgressPercentFromLine`, `Get-MkvmergeWarningClassification`, `Invoke-FFmpegWithProgress`, `Invoke-MkvmergeWithProgress`, `Set-MediaPipelineToolRunMonitorTerminalStage`
**Invoked stages:** `ffmpeg-progress-duration-probe`, `Id`
**Invoked tools:** `ffmpeg`, `mkvmerge`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/process/ffmpeg_progress.ps1`._
