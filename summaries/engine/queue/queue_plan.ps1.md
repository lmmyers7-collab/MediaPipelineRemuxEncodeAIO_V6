---
file: engine/queue/queue_plan.ps1
pipeline_stage: orchestration
token_priority: medium
owner_domain: queue
last_modified: 2026-06-03
last_reviewed: 2026-05-29
sha256: 71501978c2d2c95c62aa134133cff38f2fe014fd00b711912c3aedca51b8959b
---
# `engine/queue/queue_plan.ps1`

**Purpose:** Load priority_manifest.json from the state root.

**Functions:** `ConvertTo-MediaQueueItemRecord`, `Copy-QueueEntriesForLegacyPriorityPhase`, `Get-EffectiveQueueStrategy`, `Get-ManifestEntryField`, `Get-ManifestPriorityLevel`, `Get-PriorityManifest`, `Get-QueueEpisodeNumber`, `Get-QueueRelativePath`, `Get-QueueSeasonNumber`, `Get-QueuedEntries`, `Get-SourcePriorityInfo`, `Invoke-QueueStrategySort`, `New-MediaQueueItem`, `New-MediaQueuePhasePlan`, `Remove-PriorityMarkersFromName`, `Set-QueueEntryRuntimeMetadata`, `Test-StartsWithPriorityMarker`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths engine/queue/queue_plan.ps1`._
