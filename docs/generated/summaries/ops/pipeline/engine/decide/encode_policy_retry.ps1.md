---
file: ops/pipeline/engine/decide/encode_policy_retry.ps1
pipeline_stage: decide
token_priority: high
owner_domain: decide
last_modified: 2026-07-11
last_reviewed: 2026-07-11
sha256: af091f0685280e0149b57745fa87b9a6d817503df9c2d8e64f811eb12ee68506
---
# `ops/pipeline/engine/decide/encode_policy_retry.ps1`

**Purpose:** F-new-4 — Hold a machine-wide mutex while a CPU encode is running.

**Functions:** `Acquire-CpuEncodeMutex`, `Test-IsHardwareEncoderFailure`, `Test-ShouldRetryEncodeWithCpuFallback`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/decide/encode_policy_retry.ps1`._
