---
file: ops/pipeline/engine/shared/native_process_contracts.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: contracts
token_priority: medium
owner_domain: shared
last_modified: 2026-06-30
last_reviewed: 2026-06-04
sha256: eb9ef11da727f18475977bde0e0c19bf318da7541bc4a86bb312349f66a70cd0
---
# `ops/pipeline/engine/shared/native_process_contracts.ps1`

**Purpose:** PowerShell implementation for native process contracts; exposes Get-ExternalToolFailureCode, Get-NativeToolDefaultTimeoutSeconds, New-NativeCommandResult.

**Public symbols:** `Get-ExternalToolFailureCode`, `Get-NativeToolDefaultTimeoutSeconds`, `New-NativeCommandResult`, `Set-ExternalToolResultProperty`
**Invoked tools:** `ffmpeg`, `ffprobe`, `mkvmerge`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/shared/native_process_contracts.ps1`._
