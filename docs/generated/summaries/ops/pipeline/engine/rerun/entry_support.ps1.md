---
file: ops/pipeline/engine/rerun/entry_support.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: n/a
token_priority: medium
owner_domain: rerun
last_modified: 2026-07-23
last_reviewed: 2026-07-11
sha256: 20a74bfaf5daefaf98f1753cbaa9bf460f243dd00bfa8d7023fa4513d79d370b
---
# `ops/pipeline/engine/rerun/entry_support.ps1`

**Purpose:** PowerShell implementation for entry support; exposes Add-RerunCommandTail, Add-RerunCompletedJobsManifestEntry, Assert-RerunRobocopyFlagsSafe.

**Public symbols:** `Add-RerunCommandTail`, `Add-RerunCompletedJobsManifestEntry`, `Assert-RerunRobocopyFlagsSafe`, `Assert-RerunScratchPathBoundary`, `Assert-RerunScratchTrustAnchor`, `Clear-RerunCopyAttemptArtifacts`, `ConvertTo-Psd1KeyLiteral`, `ConvertTo-Psd1Literal`, `ConvertTo-RerunBool`, `Copy-RerunConfigValue`, `Copy-RerunFileVerified`, `DebugLog`, `Get-RerunFreeSpaceGB`, `Get-RerunJsonLineMutexName`, `Get-RerunManifestMutexName`, `Get-RerunProfileField`, `Get-RerunScratchMutationItem`, `Get-RerunUncShareRoot`, `Get-RerunValidExtensionSet`, `Get-RerunValue`, `Invoke-RerunStreamingCommand`, `Move-RerunFileReplaceWithRetry`, `Move-RerunStageAttemptToDestination`, `New-RerunLibraryProfiles`, `New-RerunScratchDirectorySafe`, `Normalize-RerunChoiceValue`, `Remove-RerunScratchEmptyDirectorySafe`, `Remove-RerunScratchFileSafe`, `Resolve-RerunChoice`, `Resolve-RerunPath`, `Resolve-RerunRobocopyPath`, `Resolve-RerunSourcePath`, `Set-RerunProfileField`, `Test-RerunSourcePathFullyQualified`, `Test-RerunUncPath`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/rerun/entry_support.ps1`._
