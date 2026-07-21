---
file: ops/pipeline/engine/process/encode_size_guard.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: n/a
token_priority: medium
owner_domain: process
last_modified: 2026-07-17
last_reviewed: 2026-06-24
sha256: 5ad028ca0b2453488e746e2f9160112d4da11ff3ca0d7f21495d839c4adb261e
---
# `ops/pipeline/engine/process/encode_size_guard.ps1`

**Purpose:** PowerShell implementation for encode size guard; exposes Get-EncodeWasteGuardConfigValue, Get-EncodeWasteGuardLimitPolicy, Get-MediaPipelineEncodeSizeGuardBoundaryVersion.

**Public symbols:** `Get-EncodeWasteGuardConfigValue`, `Get-EncodeWasteGuardLimitPolicy`, `Get-MediaPipelineEncodeSizeGuardBoundaryVersion`, `Invoke-EncodeWasteGuardPreflight`, `Invoke-EncodeWasteGuardRemuxFallback`, `Invoke-MediaPipelineEncodeSizeGuard`, `New-EncodeWasteGuardContext`, `New-EncodeWasteGuardSizePolicyMetadata`
**Invoked stages:** `encode-size-policy`, `encode-waste-guard-preflight`, `encode-waste-guard-preflight-duration`, `encode_preflight`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/process/encode_size_guard.ps1`._
