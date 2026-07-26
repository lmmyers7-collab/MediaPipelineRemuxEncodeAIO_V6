---
file: ops/pipeline/engine/failures/failure_state.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: n/a
token_priority: medium
owner_domain: failures
last_modified: 2026-07-16
last_reviewed: 2026-06-04
sha256: 707c2a4dd60a6e888b77bdde7e814503e029bbcf558ddd5c12f5ffd1196f32fc
---
# `ops/pipeline/engine/failures/failure_state.ps1`

**Purpose:** PowerShell implementation for failure state; exposes Add-RoundFailureRecord, Clear-SourceFailureState, Get-FailureCategory.

**Public symbols:** `Add-RoundFailureRecord`, `Clear-SourceFailureState`, `Get-FailureCategory`, `Get-FailureMarkerIndex`, `Get-FailureSuggestedAction`, `Get-MediaFailureCode`, `Get-SourceFailureArtifactPath`, `Get-SourceFailureMarkerPath`, `Get-SourceFailureMarkerPathV2`, `Get-SourceFailureState`, `Get-SourceIntegrityFailureCode`, `Invalidate-FailureMarkerIndex`, `New-StandardFailureRecord`, `Normalize-FailureCode`, `Register-SourceFailure`, `Test-FailureMarkerMatchesCurrentSource`, `Test-LegacyFailureMarkerMatchesCurrentSource`, `Write-FailureJsonAtomic`, `Write-RoundFailureSummary`, `Write-SourceFailureState`
**Invoked stages:** `verify`
**Invoked tools:** `ffmpeg`, `ffprobe`, `mkvextract`, `mkvmerge`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/failures/failure_state.ps1`._
