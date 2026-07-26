---
file: ops/pipeline/engine/process/pipeline_processing/preflight.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: n/a
token_priority: medium
owner_domain: process
last_modified: 2026-07-19
last_reviewed: 2026-06-04
sha256: 7e98cde471d105829f4864be6f024ffc2a9142be5b05674ef1d4ac2b44a5ed36
---
# `ops/pipeline/engine/process/pipeline_processing/preflight.ps1`

**Purpose:** PowerShell implementation for preflight; exposes Add-MediaPipelinePreflightTypeName, Get-MediaPipelineFailureStatePreflight, Get-MediaPipelineTvParsePreflight.

**Public symbols:** `Add-MediaPipelinePreflightTypeName`, `Get-MediaPipelineFailureStatePreflight`, `Get-MediaPipelineTvParsePreflight`, `New-MediaPipelinePreflightCheckResult`, `New-MediaPipelinePreflightEffect`, `New-MediaPipelinePreflightFailureRegistration`, `New-MediaPipelineProcessPreflightDecision`, `Resolve-MediaPipelineTvShowNameOverridePreflight`, `Test-MediaPipelineAcceptedDestinationNamePreflight`, `Test-MediaPipelineAlreadyProcessedPreflight`, `Test-MediaPipelineExtensionPreflight`, `Test-MediaPipelineOutputPathPreflight`, `Test-MediaPipelineStabilityPreflight`
**Invoked stages:** `path-capability`, `tv-parse`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/process/pipeline_processing/preflight.ps1`._
