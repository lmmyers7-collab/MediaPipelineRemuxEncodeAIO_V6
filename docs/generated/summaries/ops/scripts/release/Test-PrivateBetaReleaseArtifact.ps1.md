---
file: ops/scripts/release/Test-PrivateBetaReleaseArtifact.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: n/a
token_priority: medium
owner_domain: scripts
last_modified: 2026-07-23
last_reviewed: 2026-06-17
sha256: e82e87b5be91b4f4fdb60e6e8ac3e9260b2b7e3ccb0568c985e2d87db1bbf878
---
# `ops/scripts/release/Test-PrivateBetaReleaseArtifact.ps1`

**Purpose:** PowerShell implementation for test private beta release artifact; exposes Add-Check, ConvertTo-InventoryPath, Get-FirstFile.

**Public symbols:** `Add-Check`, `ConvertTo-InventoryPath`, `Get-FirstFile`, `Test-ChecksumLine`, `Test-InventorySuffix`
**State/config identifiers:** `release_manifest.json`
**Invoked tools:** `ffmpeg`, `ffprobe`, `mkvmerge`, `pgstosrt`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/scripts/release/Test-PrivateBetaReleaseArtifact.ps1`._
