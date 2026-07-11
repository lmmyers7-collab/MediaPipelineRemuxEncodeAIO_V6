---
file: ops/pipeline/engine/decide/encode_policy_probe.ps1
pipeline_stage: decide
token_priority: high
owner_domain: decide
last_modified: 2026-07-11
last_reviewed: 2026-07-11
sha256: 7aaa7a2cd6819fdc5b2395677aeebb16493e2640ff29e698c75831334d420aa8
---
# `ops/pipeline/engine/decide/encode_policy_probe.ps1`

**Purpose:** F-new-2 — Detect whether the bundled ffmpeg can actually run NVENC on

**Functions:** `Convert-DescriptorProbeToNvencProbeResult`, `Invalidate-NvencAvailableProbe`, `Resolve-NvencProbeDescriptor`, `Test-NvencAvailable`, `Test-NvencEncoderListMatch`, `Test-NvencProbeReportsAvailable`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/decide/encode_policy_probe.ps1`._
