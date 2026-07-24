---
file: ops/scripts/release/build.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: n/a
token_priority: medium
owner_domain: scripts
last_modified: 2026-07-23
last_reviewed: 2026-06-04
sha256: 17f235696bc9d1542b8236707d97d3e294362872d7f37a41c018f14c164f7879
---
# `ops/scripts/release/build.ps1`

**Purpose:** PowerShell implementation for build; exposes Assert-ReleaseDestinationPathAllowed, Assert-ReleaseDestinationReplacementAllowed, Assert-ReleaseReplacementPathHasNoReparsePoint.

**Public symbols:** `Assert-ReleaseDestinationPathAllowed`, `Assert-ReleaseDestinationReplacementAllowed`, `Assert-ReleaseReplacementPathHasNoReparsePoint`, `ConvertTo-ReleaseCanonicalPath`, `ConvertTo-ReleaseRelativeDirectory`, `Find-ReleaseContentFinding`, `Get-DeployExclusionReason`, `Get-FileVersionText`, `Get-MediaPipelineReleaseLabel`, `Get-NormalizedMediaPipelineReleaseVersion`, `Get-PythonPackageVersions`, `Get-RelativePathText`, `Get-ReleaseFileHashEntries`, `Get-ReleasePathIdentity`, `Get-ReleaseSourceFileItems`, `Get-ReleaseSourceRevision`, `Move-ReleaseDestinationToQuarantine`, `New-ReleaseDestinationIdentity`, `Resolve-ReleaseVerificationPowerShell`, `Test-ReleaseDestinationHasInProgressMarker`, `Test-ReleaseDestinationHasMarker`, `Test-ReleaseDestinationIdentity`, `Test-ReleaseDirectoryIsEmpty`, `Test-ReleasePathEqualOrChild`, `Test-ReleaseTraversalDirectoryPruned`
**State/config identifiers:** `MediaPipeline_config.psd1`, `MediaPipeline_config_chatgpt.psd1`, `MediaPipeline_config_template.psd1`, `release_manifest.json`
**Invoked tools:** `ffmpeg`, `ffprobe`, `mkvmerge`, `pgstosrt`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/scripts/release/build.ps1`._
