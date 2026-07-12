# ==============================================================================
# ops\pipeline\engine\naming\destination_plan.ps1
# ==============================================================================
# Extracted from ops\pipeline\engine\naming\naming.ps1. Keep function names stable;
# naming.ps1 dot-sources this file as the public compatibility surface.
# ==============================================================================

function Join-PlexRelativePathParts {
    param([string[]]$Parts)

    $cleanParts = @($Parts | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    if ($cleanParts.Count -eq 0) { return "" }

    $path = [string]$cleanParts[0]
    for ($i = 1; $i -lt $cleanParts.Count; $i++) {
        $path = Join-Path $path ([string]$cleanParts[$i])
    }
    return $path
}

function New-PlexMovieDestinationPlan {
    param(
        [Parameter(Mandatory)] [string]$OriginalName,
        [string]$Extension = "",
        [switch]$IncludeLibraryFolder,
        [string]$LibraryFolder = "Movies"
    )

    $cleanBase = Get-CleanMovieName $OriginalName
    if ([string]::IsNullOrWhiteSpace($cleanBase)) {
        $cleanBase = ([System.IO.Path]::GetFileNameWithoutExtension($OriginalName) -replace '[<>:"/\\|?*]', '').Trim()
    }
    if ([string]::IsNullOrWhiteSpace($cleanBase)) { $cleanBase = 'Unknown Movie' }

    if (-not [string]::IsNullOrWhiteSpace($Extension) -and -not $Extension.StartsWith('.')) {
        $Extension = ".$Extension"
    }
    $fileName = if ($Extension) { "$cleanBase$Extension" } else { $cleanBase }
    $relativeDirectory = if ($IncludeLibraryFolder) {
        Join-PlexRelativePathParts @($LibraryFolder, $cleanBase)
    } else {
        $cleanBase
    }
    $relativePath = if ($fileName) {
        Join-PlexRelativePathParts @($relativeDirectory, $fileName)
    } else {
        $relativeDirectory
    }

    return [pscustomobject]@{
        MediaKind          = 'Movie'
        MovieTitle         = $cleanBase
        FolderName         = $cleanBase
        FileBaseName       = $cleanBase
        FileName           = $fileName
        SidecarBaseName    = $cleanBase
        LibraryFolder      = if ($IncludeLibraryFolder) { $LibraryFolder } else { '' }
        RelativeDirectory  = $relativeDirectory
        RelativePath       = $relativePath
        IdentityKey        = $cleanBase
        SourceOriginalName = $OriginalName
    }
}

function New-PlexTVDestinationPlan {
    param(
        [Parameter(Mandatory)] $TvInfo,
        [string]$OriginalName = "",
        [string]$Extension = "",
        [switch]$IncludeLibraryFolder,
        [string]$LibraryFolder = "TV"
    )

    $rawShow = [string](Get-TVInfoField -TvInfo $TvInfo -Name 'ShowName' -Default '')
    $show = Get-CleanTVOutputNamePart $rawShow
    if ([string]::IsNullOrWhiteSpace($show)) {
        $show = ($rawShow -replace '[<>:"/\\|?*]', '').Trim()
    }
    if ([string]::IsNullOrWhiteSpace($show)) { $show = 'Unknown Show' }

    $season = [int](Get-TVInfoField -TvInfo $TvInfo -Name 'Season' -Default 0)
    $episode = [int](Get-TVInfoField -TvInfo $TvInfo -Name 'Episode' -Default 0)
    $episodeEndValue = Get-TVInfoField -TvInfo $TvInfo -Name 'EpisodeEnd' -Default $null
    $episodeEnd = $null
    if ($null -ne $episodeEndValue -and "$episodeEndValue" -match '^\d+$') {
        $episodeEnd = [int]$episodeEndValue
    }

    $episodeCode = "S$($season.ToString('00'))E$($episode.ToString('00'))"
    if ($episodeEnd -and $episodeEnd -gt $episode) {
        $episodeCode += "-E$($episodeEnd.ToString('00'))"
    }

    $sourceName = if ($OriginalName) {
        $OriginalName
    } else {
        [string](Get-TVInfoField -TvInfo $TvInfo -Name 'OriginalName' -Default '')
    }
    $episodeTitle = Get-CleanTVEpisodeTitle (Get-EpisodeTitle $sourceName)

    $fileBaseName = "$show - $episodeCode"
    if ($episodeTitle) { $fileBaseName += " - $episodeTitle" }
    $fileBaseName = ($fileBaseName -replace '[<>:"/\\|?*]', '' -replace '\s+', ' ').Trim()

    if (-not [string]::IsNullOrWhiteSpace($Extension) -and -not $Extension.StartsWith('.')) {
        $Extension = ".$Extension"
    }
    $fileName = if ($Extension) { "$fileBaseName$Extension" } else { $fileBaseName }
    $seasonFolder = "Season $($season.ToString('00'))"
    $relativeDirectory = if ($IncludeLibraryFolder) {
        Join-PlexRelativePathParts @($LibraryFolder, $show, $seasonFolder)
    } else {
        Join-PlexRelativePathParts @($show, $seasonFolder)
    }
    $relativePath = if ($fileName) {
        Join-PlexRelativePathParts @($relativeDirectory, $fileName)
    } else {
        $relativeDirectory
    }

    return [pscustomobject]@{
        MediaKind         = 'TV'
        ShowTitle         = $show
        SeasonNumber      = $season
        EpisodeNumber     = $episode
        EpisodeEnd        = $episodeEnd
        EpisodeCode       = $episodeCode
        SeasonFolder      = $seasonFolder
        EpisodeTitle      = $episodeTitle
        HasEpisodeTitle   = -not [string]::IsNullOrWhiteSpace($episodeTitle)
        FileBaseName      = $fileBaseName
        FileName          = $fileName
        SidecarBaseName   = $fileBaseName
        LibraryFolder     = if ($IncludeLibraryFolder) { $LibraryFolder } else { '' }
        RelativeDirectory = $relativeDirectory
        RelativePath      = $relativePath
        IdentityKey       = ("{0}_S{1}E{2}" -f $show, $season.ToString('00'), $episode.ToString('00'))
        ParseMode         = [string](Get-TVInfoField -TvInfo $TvInfo -Name 'ParseMode' -Default '')
        SourceOriginalName = $sourceName
    }
}

function New-PlexDestinationPlan {
    param(
        [Parameter(Mandatory)] [ValidateSet('Movie','TV')] [string]$MediaKind,
        $File = $null,
        $TvInfo = $null,
        [string]$OriginalName = "",
        [string]$Extension = "",
        [switch]$IncludeLibraryFolder,
        [string]$LibraryFolder = ""
    )

    if ([string]::IsNullOrWhiteSpace($OriginalName) -and $File -and $File.PSObject.Properties['Name']) {
        $OriginalName = [string]$File.Name
    }

    if ($MediaKind -eq 'TV') {
        if ($null -eq $TvInfo) { throw 'TvInfo is required for TV destination planning.' }
        if ([string]::IsNullOrWhiteSpace($OriginalName)) {
            $OriginalName = [string](Get-TVInfoField -TvInfo $TvInfo -Name 'OriginalName' -Default '')
        }
        $tvLibraryFolder = if ([string]::IsNullOrWhiteSpace($LibraryFolder)) { 'TV' } else { $LibraryFolder }
        $plan = New-PlexTVDestinationPlan `
            -TvInfo $TvInfo `
            -OriginalName $OriginalName `
            -Extension $Extension `
            -IncludeLibraryFolder:$IncludeLibraryFolder `
            -LibraryFolder $tvLibraryFolder
        return (Apply-RenameOverrideToDestinationPlan -Plan $plan -File $File -Extension $Extension)
    }

    $movieLibraryFolder = if ([string]::IsNullOrWhiteSpace($LibraryFolder)) { 'Movies' } else { $LibraryFolder }
    $plan = New-PlexMovieDestinationPlan `
        -OriginalName $OriginalName `
        -Extension $Extension `
        -IncludeLibraryFolder:$IncludeLibraryFolder `
        -LibraryFolder $movieLibraryFolder
    return (Apply-RenameOverrideToDestinationPlan -Plan $plan -File $File -Extension $Extension)
}
