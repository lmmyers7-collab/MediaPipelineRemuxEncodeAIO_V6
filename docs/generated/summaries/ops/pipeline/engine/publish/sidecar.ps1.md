---
file: ops/pipeline/engine/publish/sidecar.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: publish
token_priority: medium
owner_domain: publish
last_modified: 2026-07-20
last_reviewed: 2026-06-04
sha256: ba66e5951931232fa73f5f64508f14e0c1510c738fd16526ea131a978e271ee2
---
# `ops/pipeline/engine/publish/sidecar.ps1`

**Purpose:** PowerShell implementation for sidecar; exposes Add-CompletedJobsManifestEntry, Add-CompletedJobsManifestEntryFromSidecar, Get-SidecarPath.

**Public symbols:** `Add-CompletedJobsManifestEntry`, `Add-CompletedJobsManifestEntryFromSidecar`, `Get-SidecarPath`, `Move-SidecarTempIntoPlace`, `Test-CompletedJobsManifestEntryExists`, `Test-OutputNeedsReprocess`, `Test-SidecarRoundTripValid`, `Write-Sidecar`
**Invoked stages:** `completed_manifest`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/publish/sidecar.ps1`._
