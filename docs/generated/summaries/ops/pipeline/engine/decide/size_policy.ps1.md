---
file: ops/pipeline/engine/decide/size_policy.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: decide
token_priority: high
owner_domain: decide
last_modified: 2026-06-19
last_reviewed: 2026-06-04
sha256: cba35612a1c5456de634e33e8f8039de24a3a13088c9c92ee54a7cb646f5aea9
---
# `ops/pipeline/engine/decide/size_policy.ps1`

**Purpose:** PowerShell implementation for size policy; exposes Get-MediaEncodeCompatibilitySizeReasonCodes, Get-MediaEncodeFallbackRemuxReasonCodes, Get-MediaEncodeForcedRouteOverrideReasonCodes.

**Public symbols:** `Get-MediaEncodeCompatibilitySizeReasonCodes`, `Get-MediaEncodeFallbackRemuxReasonCodes`, `Get-MediaEncodeForcedRouteOverrideReasonCodes`, `Get-MediaRouteHeightToleranceBoundaries`, `Get-MediaRouteMaxHeightFromUpperTolerance`, `Get-MediaRouteMinHeightFromLowerTolerance`, `Measure-MediaEncodeWasteGuardProjection`, `Resolve-MediaEncodeWasteGuardModeName`, `Resolve-MediaRouteResolutionBitrateSelection`, `Resolve-MediaRouteResolutionSizeSelection`, `Test-MediaEncodeOutputSizePolicy`, `Test-MediaEncodeWasteGuardEligibility`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/decide/size_policy.ps1`._
