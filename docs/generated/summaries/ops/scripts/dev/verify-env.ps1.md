---
file: ops/scripts/dev/verify-env.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: n/a
token_priority: medium
owner_domain: scripts
last_modified: 2026-07-10
last_reviewed: 2026-06-04
sha256: 61c6337dc2596ef262969240f1d69e1ee0074f8f4f383d4b9bf505645483d46a
---
# `ops/scripts/dev/verify-env.ps1`

**Purpose:** PowerShell implementation for verify env; exposes ConvertTo-EnvironmentProcessArgument, Get-ConfigBoolValue, Get-ConfigValue.

**Public symbols:** `ConvertTo-EnvironmentProcessArgument`, `Get-ConfigBoolValue`, `Get-ConfigValue`, `Invoke-EnvironmentProcess`, `Resolve-CommandPath`, `Resolve-PipelineRelativePath`, `Test-DirectoryWritable`, `Test-IsBundledPythonPath`, `Write-Fail`, `Write-Ok`, `Write-Section`, `Write-Warn`
**State/config identifiers:** `MediaPipeline_config.psd1`, `MediaPipeline_config_chatgpt.psd1`
**Invoked tools:** `ffmpeg`, `ffprobe`, `mkvmerge`, `pgstosrt`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/scripts/dev/verify-env.ps1`._
