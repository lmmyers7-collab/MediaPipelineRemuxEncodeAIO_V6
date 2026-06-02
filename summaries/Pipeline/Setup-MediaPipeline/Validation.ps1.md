---
file: Pipeline/Setup-MediaPipeline/Validation.ps1
pipeline_stage: setup
token_priority: medium
owner_domain: scripts
last_modified: 2026-05-31
last_reviewed: 2026-05-30
sha256: d35d3b94c8022ac100d482ce676a39d5ac96ed4ffdf1bd5ad707a38d493608c4
---
# `Pipeline/Setup-MediaPipeline/Validation.ps1`

**Purpose:** Seeds pipeline_progress.json with a zeroed-out Idle skeleton if the file

**Functions:** `Initialize-ProgressSkeleton`, `Invoke-SetupValidationProbe`, `Invoke-Validation`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths Pipeline/Setup-MediaPipeline/Validation.ps1`._
