---
file: ops/pipeline/config/setup/Validation.ps1
pipeline_stage: setup
token_priority: medium
owner_domain: scripts
last_modified: 2026-06-04
last_reviewed: 2026-06-04
sha256: b953f14d9708b63ff068dc9e8b3e3157bf4c90b75becad14d4df2444ac35ed74
---
# `ops/pipeline/config/setup/Validation.ps1`

**Purpose:** Seeds pipeline_progress.json with a zeroed-out Idle skeleton if the file

**Functions:** `Initialize-ProgressSkeleton`, `Invoke-SetupValidationProbe`, `Invoke-Validation`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/config/setup/Validation.ps1`._
