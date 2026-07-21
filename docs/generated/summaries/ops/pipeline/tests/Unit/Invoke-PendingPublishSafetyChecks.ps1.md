---
file: ops/pipeline/tests/Unit/Invoke-PendingPublishSafetyChecks.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: publish
token_priority: high
owner_domain: tests
last_modified: 2026-07-20
last_reviewed: 2026-07-09
sha256: af6c2aa0d29c4cf2025cb5fbd3b4440aad48242f17e9ff9f40de6b314e1e5e0b
---
# `ops/pipeline/tests/Unit/Invoke-PendingPublishSafetyChecks.ps1`

**Purpose:** PowerShell implementation for invoke pending publish safety checks; exposes Assert-Equal, Assert-MatchText, Assert-True.

**Public symbols:** `Assert-Equal`, `Assert-MatchText`, `Assert-True`, `Clear-SourceFailureState`, `Compare-PipelineVersion`, `Copy-Item`, `Copy-SrtAtomic`, `Get-SidecarPath`, `Invoke-ParkPendingPushWithTx3gSidecars`, `Invoke-WithTempRoot`, `New-PendingParkArguments`, `New-PublishEvidenceContext`, `New-StandardFailureRecord`, `New-TestPendingManifest`, `Reset-ProgressItemContext`, `Set-MediaPipelineCurrentRunMonitorStage`, `Set-ProgressItemContext`, `Set-ProgressStage`, `Set-TestPipelineRoots`, `Test-SrtFileUsable`, `Write-Log`, `Write-PipelineEvent`
**State/config identifiers:** `.manifest.json`, `bad-array.manifest.json`, `cleanup-safe.manifest.json`, `confirmed-other-source.manifest.json`, `confirmed-source-outside-output-root.manifest.json`, `confirmed-source-overwrite.manifest.json`, `display-name.manifest.json`, `forged-local.manifest.json`, `forged-server.manifest.json`, `legacy.mkv.manifest.json`, `missing-payload.manifest.json`, `missing-proof.manifest.json`, `mixed-safe.manifest.json`, `parked.manifest.json`, `read-refresh-must-not-recover.manifest.json`, `retry-exhausted.manifest.json`, `sidecar-backup-retry.manifest.json`, `single-array-fields.manifest.json`, `single-bdpgs-track.manifest.json`, `string-confirm-source-overwrite.manifest.json`
**Invoked stages:** `heartbeat`, `Prefix`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/tests/Unit/Invoke-PendingPublishSafetyChecks.ps1`._
