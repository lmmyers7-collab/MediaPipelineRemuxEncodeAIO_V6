---
file: ops/pipeline/engine/process/dynamic_hdr_metadata.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: n/a
token_priority: medium
owner_domain: process
last_modified: 2026-07-11
last_reviewed: 2026-07-11
sha256: f642cacf5fe0c811ba1a4e01c070ac6fd46e4a32832ced3371696737ae688a6d
---
# `ops/pipeline/engine/process/dynamic_hdr_metadata.ps1`

**Purpose:** PowerShell implementation for dynamic hdr metadata; exposes ConvertFrom-DynamicHdrRpuSummaryFrameCount, Export-DynamicHdrMetadata, Invoke-DynamicHdrExtractionCommand.

**Public symbols:** `ConvertFrom-DynamicHdrRpuSummaryFrameCount`, `Export-DynamicHdrMetadata`, `Invoke-DynamicHdrExtractionCommand`, `New-DynamicHdrMetadataExtractionPlan`, `Test-DynamicHdrArtifactPresent`
**Invoked stages:** `dynamic-hdr-`
**Invoked tools:** `ffmpeg`, `mkvextract`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/process/dynamic_hdr_metadata.ps1`._
