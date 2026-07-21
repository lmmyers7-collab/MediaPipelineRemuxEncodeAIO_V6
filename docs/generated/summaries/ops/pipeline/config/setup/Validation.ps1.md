---
file: ops/pipeline/config/setup/Validation.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: setup
token_priority: medium
owner_domain: scripts
last_modified: 2026-07-15
last_reviewed: 2026-06-04
sha256: 0b013bb1c150f77243ba2816a59c83b1ef678ad286e12044800259347793df1a
---
# `ops/pipeline/config/setup/Validation.ps1`

**Purpose:** Seeds pipeline_progress.json with a zeroed-out Idle skeleton if the file does not already exist. Called automatically after a successful config write so that the desktop app can display an Idle state immediately on first launch.

**Public symbols:** `Initialize-ProgressSkeleton`, `Invoke-SetupValidationProbe`, `Invoke-Validation`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/config/setup/Validation.ps1`._
