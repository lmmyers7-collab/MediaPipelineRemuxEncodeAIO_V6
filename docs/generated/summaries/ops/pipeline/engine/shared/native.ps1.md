---
file: ops/pipeline/engine/shared/native.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: n/a
token_priority: medium
owner_domain: shared
last_modified: 2026-07-16
last_reviewed: 2026-06-04
sha256: 92fea643c5cbcae1c97d5f219cbce8a8d1cdb57c498149954ca2ad9310014c9d
---
# `ops/pipeline/engine/shared/native.ps1`

**Purpose:** Wraps a native-process poll callback with elapsed-time throttling.

**Public symbols:** `Add-NativeProcessText`, `Get-CompletedTaskText`, `Get-CompletedTaskTextWithBoundedDrain`, `Invoke-BdpgsOcrCommand`, `Invoke-ExternalToolCommand`, `Invoke-FFmpegCommand`, `Invoke-FFprobeCommand`, `Invoke-MediaPipelineElapsedPollHandler`, `Invoke-MkvextractCommand`, `Invoke-MkvmergeCommand`, `Invoke-NativeCommand`, `Invoke-NativeProcess`, `Invoke-PythonToolCommand`, `Invoke-RecursivePathScan`, `Invoke-VobSubOcrCommand`, `New-MediaPipelineNativeCommandFallbackPollHandler`, `New-ThrottledNativePollHandler`, `Receive-NativeProcessLine`, `Save-ReproCommand`, `Start-StopAwareSleep`, `Stop-NativeProcessTree`, `Test-NativeProcessStopRequested`, `Test-PathAccessibleBounded`
**Invoked stages:** `context`, `heartbeat`, `stopped`
**Invoked tools:** `ffmpeg`, `ffprobe`, `mkvextract`, `mkvmerge`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/shared/native.ps1`._
