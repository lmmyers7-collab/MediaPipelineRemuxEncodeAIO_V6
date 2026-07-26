---
file: ops/pipeline/tests/Unit/Invoke-LoggingJsonLineChecks.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: n/a
token_priority: medium
owner_domain: tests
last_modified: 2026-07-20
last_reviewed: 2026-06-12
sha256: a5399d8f608e0b550e4d7f22980f612df4572afe13cf3f9487b044a5d1997925
---
# `ops/pipeline/tests/Unit/Invoke-LoggingJsonLineChecks.ps1`

**Purpose:** PowerShell implementation for invoke logging json line checks; exposes Assert-Equal, Assert-True, Invoke-ConcurrentCompletedManifestJsonLineAppendCheck.

**Public symbols:** `Assert-Equal`, `Assert-True`, `Invoke-ConcurrentCompletedManifestJsonLineAppendCheck`, `Invoke-DebugLogRotationDuringWriteCheck`, `Invoke-JsonLineAppendFailsClosedWhenLogLockIsHeldCheck`, `Invoke-PipelineEventEnvelopeRoundTripCheck`, `Invoke-PipelineEventLogRotationCheck`
**Invoked stages:** `encode`, `processing`, `unit`
**Invoked tools:** `ffmpeg`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/tests/Unit/Invoke-LoggingJsonLineChecks.ps1`._
