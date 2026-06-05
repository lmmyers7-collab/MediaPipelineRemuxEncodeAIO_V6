# ==============================================================================
# ops\pipeline\engine\queue\queue_plan.ps1
# ==============================================================================
# Priority-marker detection, queue entry construction, and queue sort-key
# helpers.  Split from Naming.ps1; must be dot-sourced BEFORE Naming.ps1
# because Naming.ps1 functions call Remove-PriorityMarkersFromName.
#
# Dot-sourced from MediaPipeline.ps1. Reads at call time:
#   $script:PriorityMarkers
#   $script:AggressiveEpisodeParsing
#   $script:ValidExtensions
#   $script:LocalStateLayout     (optional — used for priority manifest + strategy paths)
#   $script:MixPriorityPhase     (optional bool — merge priority movies+TV into one phase)
#   $script:QueueOrderingStrategy (optional string — config-file default strategy)
#
# Cross-module helpers (loaded before this module):
#   Write-Log
#
# Functions exported:
#   Test-StartsWithPriorityMarker
#   Remove-PriorityMarkersFromName
#   Get-SourcePriorityInfo
#   Get-PriorityManifest
#   Get-ManifestPriorityLevel
#   Get-ManifestEntryField
#   Get-QueueRelativePath
#   Get-QueueSeasonNumber
#   Get-QueueEpisodeNumber
#   New-MediaQueueItem
#   ConvertTo-MediaQueueItemRecord
#   Get-QueuedEntries
#   Set-QueueEntryRuntimeMetadata
#   Get-MediaPipelineQueuePlanRunnableEntries
#   Get-EffectiveQueueStrategy
#   Invoke-QueueStrategySort
#   New-MediaQueuePhasePlan
# ==============================================================================

. (Join-Path $PSScriptRoot 'priority_manifest.ps1')
. (Join-Path $PSScriptRoot 'queue_entries.ps1')
. (Join-Path $PSScriptRoot 'strategy_sorting.ps1')
. (Join-Path $PSScriptRoot 'phase_plan.ps1')
