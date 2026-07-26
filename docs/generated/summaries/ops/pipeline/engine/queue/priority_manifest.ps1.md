---
file: ops/pipeline/engine/queue/priority_manifest.ps1
summary_schema: 2
generator_fingerprint: d9adcc41cc119663ac0895aef6e8bd45f9aa21e5691feb0d359c1a4224030a5d
file_type: PowerShell
pipeline_stage: orchestration
token_priority: medium
owner_domain: queue
last_modified: 2026-06-17
last_reviewed: 2026-06-04
sha256: c84feb227cb55fa7e2cc3e17527aed2e9403f8d4848c829d6740bf1bf7ebf65b
---
# `ops/pipeline/engine/queue/priority_manifest.ps1`

**Purpose:** Load priority_manifest.json from the state root. Returns an empty manifest hashtable when the manifest is absent. With -FailClosed, throws when an existing manifest is unreadable or invalid so queue planning cannot silently drop operator holds.

**Public symbols:** `Get-ManifestEntryField`, `Get-ManifestPriorityLevel`, `Get-PriorityManifest`, `Remove-PriorityMarkersFromName`, `Test-ManifestPriorityEntryApplies`, `Test-StartsWithPriorityMarker`
**State/config identifiers:** `priority_manifest.json`

_Edit the source, not this file. Regenerate with `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --paths ops/pipeline/engine/queue/priority_manifest.ps1`._
