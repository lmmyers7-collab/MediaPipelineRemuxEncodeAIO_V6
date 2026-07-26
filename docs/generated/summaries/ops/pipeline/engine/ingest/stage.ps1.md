---
file: ops/pipeline/engine/ingest/stage.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: ingest
token_priority: medium
owner_domain: ingest
last_modified: 2026-07-10
last_reviewed: 2026-06-23
sha256: da99c7de871a67245ca6965ead5b09efcd51f920837e55c38787c171c2ca19a0
---
# `ops/pipeline/engine/ingest/stage.ps1`

**Purpose:** PowerShell implementation for stage; exposes ConvertTo-IngestSafeSegment, Get-IngestDryRunFingerprint, Get-IngestFullPath.

**Public symbols:** `ConvertTo-IngestSafeSegment`, `Get-IngestDryRunFingerprint`, `Get-IngestFullPath`, `Get-IngestSha256`, `Invoke-IngestStage`, `New-IngestEvidence`, `Test-IngestPathEquals`, `Test-IngestPathHasReparsePoint`, `Test-IngestPathInsideBoundary`, `Write-IngestEvidence`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/ingest/stage.ps1`._
