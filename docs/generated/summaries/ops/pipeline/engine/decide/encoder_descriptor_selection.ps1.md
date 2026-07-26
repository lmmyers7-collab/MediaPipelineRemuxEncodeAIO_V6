---
file: ops/pipeline/engine/decide/encoder_descriptor_selection.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: decide
token_priority: high
owner_domain: decide
last_modified: 2026-07-11
last_reviewed: 2026-07-11
sha256: 5e42b4c5d90d67615163ff5aabd10b69c863cf628f5d01c5815cd5cdf3d5a51e
---
# `ops/pipeline/engine/decide/encoder_descriptor_selection.ps1`

**Purpose:** PowerShell implementation for encoder descriptor selection; exposes Get-MediaEncoderDescriptorActivationEvidence, Get-MediaEncoderDescriptorProbeCacheKey, Invalidate-EncoderBackendProbe.

**Public symbols:** `Get-MediaEncoderDescriptorActivationEvidence`, `Get-MediaEncoderDescriptorProbeCacheKey`, `Invalidate-EncoderBackendProbe`, `New-MediaEncoderDescriptorProbeArgumentList`, `Resolve-MediaEncoderSelection`, `Test-MediaEncoderCapabilityProbeValue`, `Test-MediaEncoderDescriptorAvailable`, `Test-MediaEncoderDescriptorListMatch`
**Invoked stages:** `capability`, `cpu_fallback`, `encode`, `family`, `primary`
**Invoked tools:** `ffmpeg`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/decide/encoder_descriptor_selection.ps1`._
