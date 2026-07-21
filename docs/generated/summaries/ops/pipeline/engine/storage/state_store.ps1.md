---
file: ops/pipeline/engine/storage/state_store.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: n/a
token_priority: medium
owner_domain: storage
last_modified: 2026-07-16
last_reviewed: 2026-06-04
sha256: 69f50983228ba17da14b5fa6d8b55db5b5f11591705f1758bc23df0dcffe5861
---
# `ops/pipeline/engine/storage/state_store.ps1`

**Purpose:** PowerShell implementation for state store; exposes Get-MediaPipelineStateDirectories, Initialize-MediaPipelineStateLayout, Move-MediaPipelineLegacyStateDirectory.

**Public symbols:** `Get-MediaPipelineStateDirectories`, `Initialize-MediaPipelineStateLayout`, `Move-MediaPipelineLegacyStateDirectory`, `Move-MediaPipelineLegacyStateFile`, `New-MediaPipelineStateLayout`, `Write-MediaPipelineStateStoreLog`
**State/config identifiers:** `priority_manifest.json`, `queue_snapshot.json`, `queue_strategy.json`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/storage/state_store.ps1`._
