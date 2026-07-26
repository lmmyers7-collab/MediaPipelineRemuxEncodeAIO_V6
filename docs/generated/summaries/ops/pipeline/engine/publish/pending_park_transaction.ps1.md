---
file: ops/pipeline/engine/publish/pending_park_transaction.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: publish
token_priority: high
owner_domain: publish
last_modified: 2026-07-20
last_reviewed: 2026-06-04
sha256: 9f24303d2bff456cbf1c74d8dd70a9b8a35cf3b6b3d76cb5ce419c7b4797585f
---
# `ops/pipeline/engine/publish/pending_park_transaction.ps1`

**Purpose:** PowerShell implementation for pending park transaction; exposes Invoke-PendingParkTransaction, New-PendingParkManifest, New-PendingParkSidecarEntries.

**Public symbols:** `Invoke-PendingParkTransaction`, `New-PendingParkManifest`, `New-PendingParkSidecarEntries`
**State/config identifiers:** `parked.manifest.json`
**Invoked stages:** `push`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/publish/pending_park_transaction.ps1`._
