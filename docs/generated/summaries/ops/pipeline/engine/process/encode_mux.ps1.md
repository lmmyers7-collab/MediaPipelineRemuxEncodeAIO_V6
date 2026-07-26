---
file: ops/pipeline/engine/process/encode_mux.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: n/a
token_priority: medium
owner_domain: process
last_modified: 2026-06-24
last_reviewed: 2026-06-24
sha256: bfb973bffbc945dfe8de21b212d384f5fc4beba770e9fdcd4f74f91d13a17a6a
---
# `ops/pipeline/engine/process/encode_mux.ps1`

**Purpose:** PowerShell implementation for encode mux; exposes Compare-EncodeMkvAttachmentInventory, Get-EncodeMkvAttachmentInventory, Get-EncodeMkvAttachmentInventoryKey.

**Public symbols:** `Compare-EncodeMkvAttachmentInventory`, `Get-EncodeMkvAttachmentInventory`, `Get-EncodeMkvAttachmentInventoryKey`, `Get-EncodeMuxObjectValue`, `Invoke-EncodeMkvAttachmentMuxIfNeeded`, `New-EncodeMkvAttachmentMuxArgumentList`, `Test-EncodeMkvAttachmentMuxApplies`
**Invoked stages:** `encode-attachment-identify`, `encode-mkvmerge`, `encode_mux`, `insufficient-space`, `inventory`, `verify`
**Invoked tools:** `ffmpeg`, `mkvmerge`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/process/encode_mux.ps1`._
