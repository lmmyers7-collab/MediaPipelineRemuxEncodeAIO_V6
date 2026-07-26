---
file: ops/pipeline/engine/config/schema_validation.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: config
token_priority: medium
owner_domain: config
last_modified: 2026-07-16
last_reviewed: 2026-06-04
sha256: 83b44b2ba87bcd1499cae21e6b7326be8e1bb146f362c6b09970c0b0d6f290e8
---
# `ops/pipeline/engine/config/schema_validation.ps1`

**Purpose:** PowerShell implementation for schema validation; exposes ConvertTo-MediaPipelineConfigBool, ConvertTo-MediaPipelineConfigMap, Resolve-MediaPipelineConfigSchemaVersion.

**Public symbols:** `ConvertTo-MediaPipelineConfigBool`, `ConvertTo-MediaPipelineConfigMap`, `Resolve-MediaPipelineConfigSchemaVersion`, `Test-MediaPipelineConfigChoiceValue`, `Test-MediaPipelineConfigEncodeAudioPolicy`, `Test-MediaPipelineConfigHasKey`, `Test-MediaPipelineConfigIntegerRange`, `Test-MediaPipelineConfigNumberRange`, `Test-MediaPipelineConfigPathIsFullyQualified`, `Test-MediaPipelineConfigPathShape`, `Test-MediaPipelineConfigSubtitleToggles`, `Test-MediaPipelineSettingsProjectionManifest`
**State/config identifiers:** `manifest.psd1`, `settings_projection.v1.json`
**Invoked tools:** `ffmpeg`, `pgstosrt`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/config/schema_validation.ps1`._
