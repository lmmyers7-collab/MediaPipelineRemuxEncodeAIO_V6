---
file: ops/pipeline/tests/Invoke-ToolIntegrationChecks.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: n/a
token_priority: medium
owner_domain: tests
last_modified: 2026-07-11
last_reviewed: 2026-06-04
sha256: da33f0ce5a994685dd19792b347e5a0ba00c86f2dbf3e1dfafb1c2edffb026ca
---
# `ops/pipeline/tests/Invoke-ToolIntegrationChecks.ps1`

**Purpose:** PowerShell implementation for invoke tool integration checks; exposes Assert-True, DebugLog, Extract-BdpgsToSup.

**Public symbols:** `Assert-True`, `DebugLog`, `Extract-BdpgsToSup`, `Save-Progress`, `Set-ProgressStage`, `Write-Log`, `Write-PipelineEvent`
**Invoked stages:** `integration-ass-convert`, `integration-ass-mux`, `integration-ass-probe`, `integration-generate`, `integration-probe-encoded`, `integration-probe-output-frames`, `integration-probe-output-json`, `integration-probe-source`, `integration-tx3g-mux`, `integration-tx3g-probe`
**Invoked tools:** `ffmpeg`, `ffprobe`, `pgstosrt`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/tests/Invoke-ToolIntegrationChecks.ps1`._
