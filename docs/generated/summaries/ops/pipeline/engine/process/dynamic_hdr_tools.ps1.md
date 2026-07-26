---
file: ops/pipeline/engine/process/dynamic_hdr_tools.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: n/a
token_priority: medium
owner_domain: process
last_modified: 2026-07-11
last_reviewed: 2026-07-11
sha256: 28eca271883a6bc307bb2293eb12377f120f40e5a00dd0fea5ef6da690c08630
---
# `ops/pipeline/engine/process/dynamic_hdr_tools.ps1`

**Purpose:** PowerShell implementation for dynamic hdr tools; exposes ConvertFrom-DynamicHdrToolVersionText, ConvertTo-DynamicHdrInt, Get-DynamicHdrPolicyDefault.

**Public symbols:** `ConvertFrom-DynamicHdrToolVersionText`, `ConvertTo-DynamicHdrInt`, `Get-DynamicHdrPolicyDefault`, `Get-DynamicHdrPolicyNames`, `Get-DynamicHdrResultValue`, `Get-DynamicHdrToolVersion`, `New-DynamicHdrCommandSpec`, `Resolve-DynamicHdrConfiguredPath`, `Resolve-DynamicHdrMkvVideoTrackId`, `Resolve-DynamicHdrPolicy`, `Resolve-DynamicHdrToolPath`, `Test-DynamicHdrToolsAvailable`
**Invoked stages:** `dynamic-hdr-mkv-video-identify`
**Invoked tools:** `ffprobe`, `mkvmerge`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/process/dynamic_hdr_tools.ps1`._
