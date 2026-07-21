---
file: ops/pipeline/tests/Unit/Invoke-VobSubSubtitleChecks.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: n/a
token_priority: medium
owner_domain: tests
last_modified: 2026-07-16
last_reviewed: 2026-06-04
sha256: 8794b5ef14c402f706c277d7ffb827ce0bcaed2adfdcda9a71c71cacfc5898f0
---
# `ops/pipeline/tests/Unit/Invoke-VobSubSubtitleChecks.ps1`

**Purpose:** PowerShell implementation for invoke vob sub subtitle checks; exposes Acquire-CpuEncodeMutex, Assert-Equal, Assert-True.

**Public symbols:** `Acquire-CpuEncodeMutex`, `Assert-Equal`, `Assert-True`, `Complete-AtomicSrtWrite`, `Get-ErrorTextSummary`, `Get-NormalizedSubtitleLanguage`, `Get-SubtitleConfiguredPathBaseDirectories`, `Get-SubtitleOperationTimeoutSeconds`, `Invoke-FFmpegCommand`, `Invoke-MkvextractCommand`, `Invoke-MkvmergeCommand`, `Invoke-VobSubOcrCommand`, `New-SrtAtomicTempPath`, `New-StandardFailureRecord`, `New-SubtitleTrackHeartbeatHandler`, `Resolve-SubtitleConfiguredPath`, `Test-SrtFileUsable`, `Write-Log`, `Write-SubtitleTrackProgress`
**Invoked tools:** `ffmpeg`, `ffprobe`, `mkvextract`, `mkvmerge`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/tests/Unit/Invoke-VobSubSubtitleChecks.ps1`._
