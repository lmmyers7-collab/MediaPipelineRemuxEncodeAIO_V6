---
file: ops/pipeline/tests/Unit/Invoke-SubtitleLongWorkHeartbeatChecks.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: n/a
token_priority: medium
owner_domain: tests
last_modified: 2026-07-16
last_reviewed: 2026-07-16
sha256: db919d501deee686fc240804e259122440e3af6c38d5dc63d10680907ee7b7f6
---
# `ops/pipeline/tests/Unit/Invoke-SubtitleLongWorkHeartbeatChecks.ps1`

**Purpose:** PowerShell implementation for invoke subtitle long work heartbeat checks; exposes Assert-Equal, Assert-True, Complete-AtomicSrtWrite.

**Public symbols:** `Assert-Equal`, `Assert-True`, `Complete-AtomicSrtWrite`, `DebugLog`, `Get-EffectiveSubtitleSwitch`, `Invoke-FFmpegCommand`, `Invoke-PythonToolCommand`, `New-SrtAtomicTempPath`, `Set-ProgressSubtitleTrack`, `Test-SrtFileUsable`, `Update-MediaPipelineRunMonitorActiveTrackHeartbeat`, `Write-Log`
**Invoked stages:** `convert`, `convert_ocr`
**Invoked tools:** `ffmpeg`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/tests/Unit/Invoke-SubtitleLongWorkHeartbeatChecks.ps1`._
