---
file: ops/pipeline/engine/decide/encode_policy_retry.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: decide
token_priority: high
owner_domain: decide
last_modified: 2026-07-16
last_reviewed: 2026-07-11
sha256: bb5b13aa1c937fc2735b2491996741125dd980910b7addf5ecf031443383a625
---
# `ops/pipeline/engine/decide/encode_policy_retry.ps1`

**Purpose:** F-new-4 — Hold a machine-wide mutex while a CPU encode is running.

**Public symbols:** `Acquire-CpuEncodeMutex`, `Test-IsHardwareEncoderFailure`, `Test-ShouldRetryEncodeWithCpuFallback`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/decide/encode_policy_retry.ps1`._
