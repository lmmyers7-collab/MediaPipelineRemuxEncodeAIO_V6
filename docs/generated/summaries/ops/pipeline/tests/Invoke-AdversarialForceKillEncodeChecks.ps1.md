---
file: ops/pipeline/tests/Invoke-AdversarialForceKillEncodeChecks.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: n/a
token_priority: medium
owner_domain: tests
last_modified: 2026-07-15
last_reviewed: 2026-06-04
sha256: 9b0bc3b00b0a265bc2d0ccc27a5fbb1caccefc043159e3a27f2331f2c58b73bb
---
# `ops/pipeline/tests/Invoke-AdversarialForceKillEncodeChecks.ps1`

**Purpose:** PowerShell implementation for invoke adversarial force kill encode checks; exposes Add-ProcessTreeId, Assert-NoAcceptedOutput, Assert-True.

**Public symbols:** `Add-ProcessTreeId`, `Assert-NoAcceptedOutput`, `Assert-True`, `ConvertTo-Psd1Literal`, `Get-AdversarialDiagnostics`, `Get-ChildProcessIds`, `Get-TailText`, `Invoke-SmokeCommand`, `New-ForceKillSmokeVideo`, `Stop-ProcessTree`, `Test-FFmpegEncoderAvailable`, `Write-SmokeConfig`
**State/config identifiers:** `force_kill_config.psd1`, `queue_after.json`, `queue_before.json`
**Invoked tools:** `ffmpeg`, `ffprobe`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/tests/Invoke-AdversarialForceKillEncodeChecks.ps1`._
