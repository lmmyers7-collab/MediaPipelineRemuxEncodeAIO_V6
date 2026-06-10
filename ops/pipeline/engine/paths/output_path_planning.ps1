# ==============================================================================
# ops\pipeline\engine\paths\output_path_planning.ps1
# ==============================================================================
# Output destination planning and path capability checks.
#
# Dot-sourced by the engine entrypoints and legacy compatibility loaders. These
# helpers read path and naming configuration from script scope at call time.
# ==============================================================================


. (Join-Path $PSScriptRoot 'library_profiles.ps1')
. (Join-Path $PSScriptRoot 'effective_settings.ps1')
. (Join-Path $PSScriptRoot 'output_evidence.ps1')
. (Join-Path $PSScriptRoot 'path_capability.ps1')

function Test-MediaPipelineOutputRootHasLibraryFolder {
    param(
        [string] $OutputRoot,
        [string] $LibraryFolder
    )

    if ([string]::IsNullOrWhiteSpace($OutputRoot) -or [string]::IsNullOrWhiteSpace($LibraryFolder)) {
        return $false
    }

    $trimmedRoot = ([string]$OutputRoot).Trim().TrimEnd([char[]]@([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar))
    if ([string]::IsNullOrWhiteSpace($trimmedRoot)) { return $false }
    $leaf = Split-Path -Leaf $trimmedRoot
    return ([string]::Equals($leaf, $LibraryFolder, [System.StringComparison]::OrdinalIgnoreCase))
}

function Get-OutputPaths {
    param($File, [bool]$isTV, $tvInfo, [string]$SafeName)
    $libraryOverrides = Resolve-MediaPipelineLibraryOverridesForPath -SourcePath ([string]$File.FullName)
    $activeOutputContainer = Get-MediaPipelineActiveOverrideValue -Name 'OutputContainer' -Default $null
    $effectiveOutputContainer = if (-not [string]::IsNullOrWhiteSpace([string]$activeOutputContainer)) {
        [string]$activeOutputContainer
    } elseif ($libraryOverrides.Contains('OutputContainer')) {
        [string]$libraryOverrides['OutputContainer']
    } else {
        [string]$OutputContainer
    }
    $libraryEvidence = Get-MediaPipelineLibraryProfileEvidenceForPath -SourcePath ([string]$File.FullName)
    $outputRoot = [string]$libraryEvidence['output_root']
    if ([string]::IsNullOrWhiteSpace($outputRoot)) { $outputRoot = [string]$Outsource }
    if ($isTV) {
        $includeTvLibraryFolder = [bool]$CreateTVSubfolder
        if ($includeTvLibraryFolder -and (Test-MediaPipelineOutputRootHasLibraryFolder -OutputRoot $outputRoot -LibraryFolder 'TV')) {
            $includeTvLibraryFolder = $false
        }
        $plan = New-PlexDestinationPlan -MediaKind 'TV' -File $File -TvInfo $tvInfo -OriginalName $tvInfo.OriginalName -Extension $effectiveOutputContainer -IncludeLibraryFolder:$includeTvLibraryFolder
    } else {
        $plan = New-PlexDestinationPlan -MediaKind 'Movie' -File $File -OriginalName $File.Name -Extension $effectiveOutputContainer
    }

    $localDir  = Join-Path $LocalEncoded $plan.RelativeDirectory
    $serverDir = Join-Path $outputRoot $plan.RelativeDirectory
    return @{
        LocalDir=$localDir; LocalOut=Join-Path $localDir $plan.FileName
        ServerDir=$serverDir; ServerOut=Join-Path $serverDir $plan.FileName
        PlexPlan=$plan; RelativePath=$plan.RelativePath; OutputRoot=$outputRoot
        LibraryProfileId=$libraryEvidence['library_id']; LibraryName=$libraryEvidence['library_name']
        LibraryDesignation=$libraryEvidence['designation']; LibrarySourceRoot=$libraryEvidence['source_root']
        LibrarySettingsOverrideKeys=$libraryEvidence['settings_override_keys']
        LibrarySettingsOverrides=$libraryEvidence['settings_overrides']
        LibraryEffectiveSettings=$libraryEvidence['effective_settings']
    }
}
