---
file: ops/pipeline/engine/queue/priority_manifest.ps1
pipeline_stage: orchestration
token_priority: medium
owner_domain: queue
last_modified: 2026-06-04
last_reviewed: 2026-06-04
sha256: 6f148c35c16de07a714913c25c732ba9c9b5347d2129ddfee540d352c1941c41
---
# `ops/pipeline/engine/queue/priority_manifest.ps1`

**Purpose:** Load priority_manifest.json from the state root.

**Functions:** `Get-ManifestEntryField`, `Get-ManifestPriorityLevel`, `Get-PriorityManifest`, `Remove-PriorityMarkersFromName`, `Test-StartsWithPriorityMarker`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/queue/priority_manifest.ps1`._
