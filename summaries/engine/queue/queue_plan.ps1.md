---
file: engine/queue/queue_plan.ps1
pipeline_stage: orchestration
token_priority: medium
owner_domain: queue
last_modified: 2026-05-29
last_reviewed: 2026-05-29
sha256: ac155310827ce86bfc20975cdee322d1820db3b91b33d3e1c370fb6b46d58d31
---
# `engine/queue/queue_plan.ps1`

**Purpose:** Load priority_manifest.json from the state root.

**Functions:** `ConvertTo-MediaQueueItemRecord`, `Copy-QueueEntriesForLegacyPriorityPhase`, `Get-EffectiveQueueStrategy`, `Get-ManifestEntryField`, `Get-ManifestPriorityLevel`, `Get-PriorityManifest`, `Get-QueueEpisodeNumber`, `Get-QueueRelativePath`, `Get-QueueSeasonNumber`, `Get-QueuedEntries`, `Get-SourcePriorityInfo`, `Invoke-QueueStrategySort`, `New-MediaQueueItem`, `New-MediaQueuePhasePlan`, `Remove-PriorityMarkersFromName`, `Set-QueueEntryRuntimeMetadata`, `Test-StartsWithPriorityMarker`

_Edit the source, not this file. Regenerate with `python scripts/dev/refresh_summaries.py --paths engine/queue/queue_plan.ps1`._
