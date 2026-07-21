---
file: ops/scripts/release/test_acceptance.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: n/a
token_priority: medium
owner_domain: scripts
last_modified: 2026-07-15
last_reviewed: 2026-07-11
sha256: e0c39220c7ff610b47ccbe942a39ac3b79151b3b8577fffbda6daa4608bdf3ee
---
# `ops/scripts/release/test_acceptance.ps1`

**Purpose:** PowerShell implementation for test acceptance; exposes Get-NewReleaseTrackedProcessIds, Invoke-DeployablePackageAcceptance, Wait-ReleaseTrackedProcessExit.

**Public symbols:** `Get-NewReleaseTrackedProcessIds`, `Invoke-DeployablePackageAcceptance`, `Wait-ReleaseTrackedProcessExit`
**State/config identifiers:** `release_manifest.json`
**Invoked tools:** `ffmpeg`, `ffprobe`, `mkvmerge`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/scripts/release/test_acceptance.ps1`._
