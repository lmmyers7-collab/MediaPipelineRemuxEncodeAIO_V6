---
file: ops/scripts/release/release_policy.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: n/a
token_priority: medium
owner_domain: scripts
last_modified: 2026-07-20
last_reviewed: 2026-06-04
sha256: 5137250a323721feae146f1094b1618446bf670710b41e9a9567899531683de6
---
# `ops/scripts/release/release_policy.ps1`

**Purpose:** PowerShell implementation for release policy; exposes Find-MediaPipelineReleaseContentFinding, Get-MediaPipelineReleaseExclusionReason, Get-MediaPipelineReleaseHygieneRules.

**Public symbols:** `Find-MediaPipelineReleaseContentFinding`, `Get-MediaPipelineReleaseExclusionReason`, `Get-MediaPipelineReleaseHygieneRules`, `Get-MediaPipelineReleasePolicyManifest`, `New-MediaPipelineReleaseHygieneRule`, `Normalize-MediaPipelineReleaseRelativePath`, `Test-MediaPipelineReleaseContentAllowed`, `Test-MediaPipelineReleaseContentScanEligible`
**State/config identifiers:** `.state.json`, `MediaPipeline_config.psd1`, `MediaPipeline_config_chatgpt.psd1`
**Invoked tools:** `ffmpeg`, `mkvextract`, `mkvpropedit`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/scripts/release/release_policy.ps1`._
