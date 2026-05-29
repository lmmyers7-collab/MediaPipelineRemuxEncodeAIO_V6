---
file: engine/queue/queue_plan.ps1
pipeline_stage: orchestration
token_priority: medium
owner_domain: queue
last_modified: 2026-05-29
last_reviewed: 2026-05-29
sha256: c09e8e65138a846a1677456fc23e4720a416f6e131167e716a390e3c552b95ca
---
# `engine/queue/queue_plan.ps1`

**Purpose:** Load priority_manifest.json from the state root.

**Functions:** `ConvertTo-MediaQueueItemRecord`, `Copy-QueueEntriesForLegacyPriorityPhase`, `Get-EffectiveQueueStrategy`, `Get-ManifestEntryField`, `Get-ManifestPriorityLevel`, `Get-PriorityManifest`, `Get-QueueEpisodeNumber`, `Get-QueueRelativePath`, `Get-QueueSeasonNumber`, `Get-QueuedEntries`, `Get-SourcePriorityInfo`, `Invoke-QueueStrategySort`, `New-MediaQueueItem`, `New-MediaQueuePhasePlan`, `Remove-PriorityMarkersFromName`, `Set-QueueEntryRuntimeMetadata`, `Test-StartsWithPriorityMarker`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths engine/queue/queue_plan.ps1`._
