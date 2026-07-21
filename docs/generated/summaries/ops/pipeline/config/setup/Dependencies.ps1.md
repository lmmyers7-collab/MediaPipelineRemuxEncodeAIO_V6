---
file: ops/pipeline/config/setup/Dependencies.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: setup
token_priority: medium
owner_domain: scripts
last_modified: 2026-06-13
last_reviewed: 2026-06-04
sha256: 07263a2fe0d6d89708089290a613783fd469ac9d7a14a2c0ca0dd8d60ad45037
---
# `ops/pipeline/config/setup/Dependencies.ps1`

**Purpose:** PowerShell implementation for dependencies; exposes Get-BundleSearchRoots, Get-DependencyStatus, Get-DetectedGpu.

**Public symbols:** `Get-BundleSearchRoots`, `Get-DependencyStatus`, `Get-DetectedGpu`, `Get-ExtraVideoFlagsForCodec`, `Get-SetupAllowSystemTools`, `Resolve-BundledPath`, `Resolve-CurrentPowerShellPath`, `Resolve-PwshPath`, `Resolve-PythonPath`, `Resolve-ToolPath`, `Test-IsRealPython`, `Test-Pysubs2Import`, `Test-VideoPresetCompatibility`
**Invoked tools:** `ffmpeg`, `ffprobe`, `mkvmerge`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/config/setup/Dependencies.ps1`._
