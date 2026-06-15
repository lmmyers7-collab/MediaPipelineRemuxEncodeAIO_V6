---
file: ops/pipeline/engine/queue/priority_manifest.ps1
pipeline_stage: orchestration
token_priority: medium
owner_domain: queue
last_modified: 2026-06-12
last_reviewed: 2026-06-04
sha256: 471082a9dcc2dd08e76a9b0e491343324a1c5afc7ccf259d1828006660b259f2
---
# `ops/pipeline/engine/queue/priority_manifest.ps1`

**Purpose:** Load priority_manifest.json from the state root.

**Functions:** `Get-ManifestEntryField`, `Get-ManifestPriorityLevel`, `Get-PriorityManifest`, `Remove-PriorityMarkersFromName`, `Test-ManifestPriorityEntryApplies`, `Test-StartsWithPriorityMarker`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/queue/priority_manifest.ps1`._
