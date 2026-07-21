---
file: ops/pipeline/engine/decide/encode_policy_probe.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: decide
token_priority: high
owner_domain: decide
last_modified: 2026-07-11
last_reviewed: 2026-07-11
sha256: 33c3c68abe6919d41d4d4f9320ac7b32fc6124a4e1594cf990d12496d694bcee
---
# `ops/pipeline/engine/decide/encode_policy_probe.ps1`

**Purpose:** F-new-2 — Detect whether the bundled ffmpeg can actually run NVENC on this host, and cache the answer for the run.

**Public symbols:** `Convert-DescriptorProbeToNvencProbeResult`, `Invalidate-NvencAvailableProbe`, `Resolve-NvencProbeDescriptor`, `Test-NvencAvailable`, `Test-NvencEncoderListMatch`, `Test-NvencProbeReportsAvailable`
**Invoked stages:** `encode`
**Invoked tools:** `ffmpeg`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/decide/encode_policy_probe.ps1`._
