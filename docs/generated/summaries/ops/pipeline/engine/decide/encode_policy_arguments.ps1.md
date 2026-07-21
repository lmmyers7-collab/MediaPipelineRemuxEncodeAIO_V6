---
file: ops/pipeline/engine/decide/encode_policy_arguments.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: decide
token_priority: high
owner_domain: decide
last_modified: 2026-07-11
last_reviewed: 2026-07-11
sha256: 59523d22db58649b3ea43cc4ff916ed849d31417cff3cd1b9b41ced493608a62
---
# `ops/pipeline/engine/decide/encode_policy_arguments.ps1`

**Purpose:** PowerShell implementation for encode policy arguments; exposes Get-EncodeArgumentValue, Get-EncodeEncoderKind, Get-EncodeSelectedGpuDevice.

**Public symbols:** `Get-EncodeArgumentValue`, `Get-EncodeEncoderKind`, `Get-EncodeSelectedGpuDevice`, `Get-MediaEncodeBoundedQuality`, `Get-MediaEncodeLadderNames`, `Get-MediaEncodeLadderProfile`, `Get-MediaEncodeOutputMuxerName`, `New-EncodeAttemptDescriptorSelectionEvidence`, `New-EncodeFfmpegArgumentList`, `New-EncodeVideoFlags`, `New-EncodeWasteGuardSampleArgumentList`, `Resolve-MediaEncodeLadderName`, `Resolve-MediaEncoderActivationReadiness`
**Invoked tools:** `ffprobe`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/decide/encode_policy_arguments.ps1`._
