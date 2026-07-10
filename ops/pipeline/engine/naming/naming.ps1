# ==============================================================================
# ops\pipeline\engine\naming\naming.ps1
# ==============================================================================
# Movie name cleaning and TV episode parsing / Plex output-name helpers.
# Queue construction and priority-marker functions live in QueuePlan.ps1,
# which MUST be dot-sourced before this module (Naming.ps1 calls
# Remove-PriorityMarkersFromName defined there).
#
# Dot-sourced from MediaPipeline.ps1. Reads at call time:
#   $script:AggressiveEpisodeParsing
#   $script:ValidExtensions
#   $CreateTVSubfolder
#
# Cross-module helpers (loaded before this module):
#   Write-Log
#   Remove-PriorityMarkersFromName  (QueuePlan.ps1)
#
# Functions exported:
#   Normalize-MovieName
#   ConvertTo-MediaPipelineMovieTitleCase
#   Get-CleanMovieName
#   Normalize-TVShowFolderName
#   Get-TVEpisodeFromFilename
#   Resolve-OrdinalSeason
#   Get-TVFolderSeasonInfo
#   Test-TVSpecialSeasonFolderName
#   Get-TVEpisodeFromStrippedName
#   Get-TVLooseParseText
#   Get-TVLooseSeasonEpisodeFromName
#   Get-TVLooseBareEpisodeNumber
#   Get-TVShowNameBeforeSeasonEpisodeTokens
#   Get-TVShowNameBeforeOrdinalSeasonToken
#   Get-TVDisallowedLibraryFallbackShowNameKeys
#   Test-TVShowNameMatchesDisallowedLibraryFallback
#   Test-TVFolderEpisodeSequenceSupportsCandidate
#   Get-TVAggressiveEpisodeFromName
#   Get-TVInfoFromFile
#   Get-EpisodeTitle
#   Get-CleanTVOutputNamePart
#   Get-CleanTVEpisodeTitle
#   Get-TVInfoField
#   Join-PlexRelativePathParts
#   New-PlexMovieDestinationPlan
#   New-PlexTVDestinationPlan
#   New-PlexDestinationPlan
#   Get-CleanTVFilename
#   Get-TVParseRenameSuggestion
# ==============================================================================

. (Join-Path $PSScriptRoot 'movie_cleanup.ps1')
. (Join-Path $PSScriptRoot 'tv_parsing.ps1')
. (Join-Path $PSScriptRoot 'destination_plan.ps1')
. (Join-Path $PSScriptRoot 'rename_overrides.ps1')
