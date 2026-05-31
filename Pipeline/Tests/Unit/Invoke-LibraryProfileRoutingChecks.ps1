param()

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
. (Join-Path $repoRoot 'engine\paths\output_path_planning.ps1')
. (Join-Path $repoRoot 'engine\shared\path_helpers.ps1')
. (Join-Path $repoRoot 'engine\queue\queue_plan.ps1')
. (Join-Path $repoRoot 'engine\library\library_index.ps1')
. (Join-Path $repoRoot 'engine\config\config_schema.ps1')

function Write-Log {
    param([string] $Message, [string] $Level = 'INFO')
}

function Invoke-RecursivePathScan {
    param([string] $Path, [string] $ItemType = 'File', [int] $TimeoutSeconds = 0, [string] $Label = '')
    return @(Get-ChildItem -LiteralPath $Path -File -Recurse | ForEach-Object { $_.FullName })
}

function Start-StopAwareSleep {
    param([int] $Seconds)
    return $true
}

function Assert-Equal {
    param(
        [Parameter(Mandatory)] $Actual,
        [Parameter(Mandatory)] $Expected,
        [Parameter(Mandatory)] [string] $Message
    )
    if ($Actual -ne $Expected) {
        throw "$Message Expected '$Expected' but got '$Actual'."
    }
}

function Assert-Contains {
    param(
        [Parameter(Mandatory)] $Items,
        [Parameter(Mandatory)] $Expected,
        [Parameter(Mandatory)] [string] $Message
    )
    if (-not (@($Items) -contains $Expected)) {
        throw "$Message Expected collection to contain '$Expected'."
    }
}

function Assert-True {
    param(
        [Parameter(Mandatory)] [bool] $Condition,
        [Parameter(Mandatory)] [string] $Message
    )
    if (-not $Condition) { throw $Message }
}

$script:SourceMovies = 'C:\Incoming\Movies'
$script:SourceTV = 'C:\Incoming\TV'
$script:Outsource = 'D:\Processed'
$script:OutputContainer = 'mkv'
$script:RoutingProfile = 'plex_direct_stream'
$script:VideoQuality = 22
$script:AudioMaxChannels = 8
$script:LibraryProfiles = @(
    [pscustomobject]@{
        id = 'movies'
        name = 'Movies'
        enabled = $true
        designation = 'movie'
        source_path = 'C:\Incoming\Movies'
        output_path = 'D:\Processed'
        promotion_enabled = $false
        promotion_destination = ''
        overrides = [pscustomobject]@{
            editor = [pscustomobject]@{ RoutingProfile = 'manual'; OutputContainer = 'mp4' }
            video = [pscustomobject]@{ VideoQuality = 19 }
            subtitles = [pscustomobject]@{ SubKeepLanguages = @('eng','und') }
            audio = [pscustomobject]@{ AudioMaxChannels = 2 }
        }
    },
    [pscustomobject]@{
        id = 'anime'
        name = 'Anime'
        enabled = $true
        designation = 'tv'
        source_path = 'E:\AnimeSource'
        output_path = 'F:\AnimeProcessed'
        promotion_enabled = $true
        promotion_destination = 'G:\FinalAnime'
        overrides = [pscustomobject]@{
            editor = [pscustomobject]@{ RoutingProfile = 'archive_quality' }
            audio = [pscustomobject]@{ AudioMaxChannels = 6 }
        }
    }
)

$movieOverrides = Resolve-MediaPipelineLibraryOverridesForPath -SourcePath 'C:\Incoming\Movies\Movie.mkv'
Assert-Equal $movieOverrides['RoutingProfile'] 'manual' 'Expected Movies library routing override.'
Assert-Equal $movieOverrides['VideoQuality'] 19 'Expected Movies video override.'
Assert-Equal $movieOverrides['AudioMaxChannels'] 2 'Expected Movies audio override.'
Assert-Contains $movieOverrides.Keys 'SubKeepLanguages' 'Expected Movies subtitle override key.'

$animeOverrides = Resolve-MediaPipelineLibraryOverridesForPath -SourcePath 'E:\AnimeSource\Show\Season 01\Show - S01E01.mkv'
Assert-Equal $animeOverrides['RoutingProfile'] 'archive_quality' 'Expected Anime library routing override.'
Assert-Equal $animeOverrides['AudioMaxChannels'] 6 'Expected Anime library audio override.'

$snapshot = Push-MediaPipelineActiveConfigOverrides -Overrides $movieOverrides
try {
    Assert-Equal $script:RoutingProfile 'manual' 'Expected active config push to override RoutingProfile.'
    Assert-Equal $script:VideoQuality 19 'Expected active config push to override VideoQuality.'
    Assert-Equal $script:AudioMaxChannels 2 'Expected active config push to override AudioMaxChannels.'
} finally {
    Pop-MediaPipelineActiveConfigOverrides -Snapshot $snapshot
}
Assert-Equal $script:RoutingProfile 'plex_direct_stream' 'Expected active config pop to restore RoutingProfile.'
Assert-Equal $script:VideoQuality 22 'Expected active config pop to restore VideoQuality.'
Assert-Equal $script:AudioMaxChannels 8 'Expected active config pop to restore AudioMaxChannels.'

$legacyProfile = [pscustomobject]@{
    editor_overrides = [pscustomobject]@{ RoutingProfile = 'manual' }
    media_overrides = [pscustomobject]@{ VideoQuality = 18; AudioMaxChannels = 4 }
}
$legacyOverrides = Get-MediaPipelineLibraryProfileOverrideMap -Profile $legacyProfile
Assert-Equal $legacyOverrides['RoutingProfile'] 'manual' 'Expected legacy editor override compatibility.'
Assert-Equal $legacyOverrides['VideoQuality'] 18 'Expected legacy media video override compatibility.'
Assert-Equal $legacyOverrides['AudioMaxChannels'] 4 'Expected legacy media audio override compatibility.'

$animeEvidence = Get-MediaPipelineLibraryProfileEvidenceForPath -SourcePath 'E:\AnimeSource\Show\Season 01\Show - S01E01.mkv'
Assert-Equal $animeEvidence['library_id'] 'anime' 'Expected longest matching library profile evidence.'
Assert-Equal $animeEvidence['designation'] 'tv' 'Expected TV designation to carry through profile evidence.'
Assert-Equal $animeEvidence['output_root'] 'F:\AnimeProcessed' 'Expected per-library output root.'
Assert-Contains $animeEvidence['settings_override_keys'] 'AudioMaxChannels' 'Expected evidence to include settings override keys.'
Assert-Equal $animeEvidence['settings_overrides']['AudioMaxChannels'] 6 'Expected evidence to include explicit settings override values.'
Assert-Equal $animeEvidence['effective_settings']['AudioMaxChannels'] 6 'Expected evidence to include resolved effective library settings.'
Assert-Equal $animeEvidence['effective_settings']['OutputContainer'] 'mkv' 'Expected missing library override fields to inherit global config in evidence.'

$movieOutput = Get-MediaPipelineLibraryOutputRootForPath -SourcePath 'C:\Incoming\Movies\Movie.mkv'
Assert-Equal $movieOutput 'D:\Processed' 'Expected default movie output root to mirror Outsource.'

$script:LibraryProfiles = @(
    [pscustomobject]@{
        id = 'alpha'
        name = 'Alpha'
        enabled = $true
        designation = 'movie'
        source_path = 'C:\SharedLibrary'
        output_path = 'D:\AlphaProcessed'
        overrides = [pscustomobject]@{ audio = [pscustomobject]@{ AudioMaxChannels = 2 } }
    },
    [pscustomobject]@{
        id = 'beta'
        name = 'Beta'
        enabled = $true
        designation = 'movie'
        source_path = 'C:\SharedLibrary'
        output_path = 'D:\BetaProcessed'
        overrides = [pscustomobject]@{ audio = [pscustomobject]@{ AudioMaxChannels = 8 } }
    },
    [pscustomobject]@{
        id = 'separate'
        name = 'Separate'
        enabled = $true
        designation = 'movie'
        source_path = 'C:\SeparateLibrary'
        output_path = 'D:\SeparateProcessed'
        overrides = [pscustomobject]@{ audio = [pscustomobject]@{ AudioMaxChannels = 4 } }
    }
)

$selectedBetaOverrides = Resolve-MediaPipelineLibraryOverridesForPath -SourcePath 'C:\SharedLibrary\Movie.mkv' -LibraryProfileId 'beta'
Assert-Equal $selectedBetaOverrides['AudioMaxChannels'] 8 'Expected selected library profile id to win when source root matches.'
$script:CurrentLibraryProfileId = 'beta'
$selectedBetaEvidence = Get-MediaPipelineLibraryProfileEvidenceForPath -SourcePath 'C:\SharedLibrary\Movie.mkv'
Assert-Equal $selectedBetaEvidence['library_id'] 'beta' 'Expected current queue-selected library id to flow into evidence.'
Assert-Equal $selectedBetaEvidence['output_root'] 'D:\BetaProcessed' 'Expected selected library output root to flow into evidence.'

$script:CurrentLibraryProfileId = 'beta'
$separateOverrides = Resolve-MediaPipelineLibraryOverridesForPath -SourcePath 'C:\SeparateLibrary\Movie.mkv'
Assert-Equal $separateOverrides['AudioMaxChannels'] 4 'Expected mismatched selected library id not to cross source-root boundaries.'
$script:CurrentLibraryProfileId = ''

$queueItem = New-MediaQueueItem `
    -SourcePath 'E:\AnimeSource\Show\Season 01\Show - S01E01.mkv' `
    -RootPath 'E:\AnimeSource' `
    -MediaKind 'tv' `
    -LibraryId 'anime' `
    -LibraryName 'Anime' `
    -LibraryDesignation 'tv' `
    -LibraryOutputRoot 'F:\AnimeProcessed'

Assert-Equal $queueItem.LibraryId 'anime' 'Expected queue item to carry library id.'
Assert-Equal $queueItem.LibraryDesignation 'tv' 'Expected queue item to carry designation.'
Assert-Equal $queueItem.LibraryOutputRoot 'F:\AnimeProcessed' 'Expected queue item to carry output root.'

$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("mediapipeline-library-profile-test-" + [guid]::NewGuid().ToString('N'))
try {
    $movieRoot = Join-Path $tempRoot 'Movies'
    $tvRoot = Join-Path $tempRoot 'TV'
    $animeRoot = Join-Path $tempRoot 'Anime'
    $autoRoot = Join-Path $tempRoot 'Auto'
    New-Item -ItemType Directory -Path $movieRoot, $tvRoot, $animeRoot, $autoRoot -Force | Out-Null
    New-Item -ItemType File -Path (Join-Path $movieRoot 'Movie.mkv') -Force | Out-Null
    $animeSeason = Join-Path $animeRoot 'Show\Season 01'
    New-Item -ItemType Directory -Path $animeSeason -Force | Out-Null
    New-Item -ItemType File -Path (Join-Path $animeSeason 'Show - S01E01.mkv') -Force | Out-Null
    New-Item -ItemType File -Path (Join-Path $autoRoot 'Auto Movie.mkv') -Force | Out-Null
    $autoSeason = Join-Path $autoRoot 'Auto Show\Season 01'
    New-Item -ItemType Directory -Path $autoSeason -Force | Out-Null
    New-Item -ItemType File -Path (Join-Path $autoSeason 'Auto Show - S01E01.mkv') -Force | Out-Null

    $script:SourceMovies = $movieRoot
    $script:SourceTV = $tvRoot
    $script:Outsource = Join-Path $tempRoot 'Processed'
    $script:SourceScanIntervalSeconds = 0
    $script:MovieScanCache = @()
    $script:TVScanCache = @()
    $script:MovieScanCacheAt = $null
    $script:TVScanCacheAt = $null
    $script:QueueOrderingStrategy = 'Standard'
    $script:MixPriorityPhase = $false
    $script:PriorityMarkers = @('!')
    $script:LibraryProfiles = @(
        [pscustomobject]@{
            id = 'movies'
            name = 'Movies'
            enabled = $true
            designation = 'movie'
            source_path = $movieRoot
            output_path = $script:Outsource
            overrides = [pscustomobject]@{
                editor = [pscustomobject]@{ RoutingProfile = 'manual' }
                video = [pscustomobject]@{}
                subtitles = [pscustomobject]@{}
                audio = [pscustomobject]@{}
            }
        },
        [pscustomobject]@{
            id = 'anime'
            name = 'Anime'
            enabled = $true
            designation = 'tv'
            source_path = $animeRoot
            output_path = (Join-Path $tempRoot 'AnimeProcessed')
            overrides = [pscustomobject]@{
                editor = [pscustomobject]@{}
                video = [pscustomobject]@{ VideoQuality = 20 }
                subtitles = [pscustomobject]@{}
                audio = [pscustomobject]@{ AudioMaxChannels = 6 }
            }
        },
        [pscustomobject]@{
            id = 'auto'
            name = 'Auto'
            enabled = $true
            designation = 'auto'
            source_path = $autoRoot
            output_path = (Join-Path $tempRoot 'AutoProcessed')
            overrides = [pscustomobject]@{
                editor = [pscustomobject]@{ RouteThresholdMode = 'bitrate' }
                video = [pscustomobject]@{}
                subtitles = [pscustomobject]@{}
                audio = [pscustomobject]@{}
            }
        }
    )

    $discovery = Get-MediaQueueDiscoveryPlan -MovieRoot $movieRoot -TVRoot $tvRoot -ForceRefresh:$true
    Assert-Equal @($discovery.MovieEntries).Count 2 'Expected movie discovery from default movie profile plus auto movie item.'
    Assert-Equal @($discovery.TVEntries).Count 2 'Expected TV discovery from extra anime profile plus auto TV item.'
    $animeEntry = @($discovery.TVEntries | Where-Object { $_.LibraryId -eq 'anime' })[0]
    $autoMovieEntry = @($discovery.MovieEntries | Where-Object { $_.LibraryId -eq 'auto' })[0]
    $autoTvEntry = @($discovery.TVEntries | Where-Object { $_.LibraryId -eq 'auto' })[0]
    Assert-Equal ([string]$animeEntry.LibraryOutputRoot) (Join-Path $tempRoot 'AnimeProcessed') 'Expected discovery entry to carry extra output root.'
    Assert-Contains $animeEntry.Metadata['settings_override_keys'] 'AudioMaxChannels' 'Expected discovery entry to snapshot custom library audio setting keys.'
    Assert-Equal $animeEntry.Metadata['settings_overrides']['AudioMaxChannels'] 6 'Expected discovery entry to snapshot custom library setting values.'
    Assert-Equal $animeEntry.Metadata['effective_settings']['VideoQuality'] 20 'Expected discovery entry to snapshot effective library setting values.'
    Assert-Equal ([string]$autoMovieEntry.LibraryDesignation) 'auto' 'Expected auto movie entry to carry auto designation.'
    Assert-Equal ([string]$autoMovieEntry.MediaKind) 'movie' 'Expected auto movie-looking file to route as movie.'
    Assert-Equal ([string]$autoMovieEntry.LibraryOutputRoot) (Join-Path $tempRoot 'AutoProcessed') 'Expected auto movie entry to carry auto output root.'
    Assert-Contains $autoMovieEntry.Metadata['settings_override_keys'] 'RouteThresholdMode' 'Expected auto movie entry to snapshot custom library setting keys.'
    Assert-Equal ([string]$autoTvEntry.LibraryDesignation) 'auto' 'Expected auto TV entry to carry auto designation.'
    Assert-Equal ([string]$autoTvEntry.MediaKind) 'tv' 'Expected auto TV-looking file to route as TV.'
    Assert-Equal ([string]$autoTvEntry.LibraryOutputRoot) (Join-Path $tempRoot 'AutoProcessed') 'Expected auto TV entry to carry auto output root.'
} finally {
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force
    }
}

$invalidOverrideConfig = Get-MediaPipelineConfigDefaultValues
$invalidOverrideConfig['LibraryProfiles'] = @(
    [ordered]@{
        id = 'movies'
        name = 'Movies'
        enabled = $true
        designation = 'movie'
        source_path = 'C:\Incoming\Movies'
        output_path = 'D:\Processed'
        overrides = [ordered]@{
            editor = [ordered]@{
                RouteThresholdMode = 'all'
                EncodeThresholdGB = -1
                MovieRouteMaxVideoBitrateMbps = 'many'
                TVRouteMaxVideoBitrateMbps = 0
            }
        }
    },
    [ordered]@{
        id = 'tv'
        name = 'TV'
        enabled = $true
        designation = 'tv'
        source_path = 'C:\Incoming\TV'
        output_path = 'D:\Processed'
        overrides = [ordered]@{}
    }
)
$invalidOverrideResult = Test-MediaPipelineConfigSchema -Config $invalidOverrideConfig
$invalidOverrideErrors = (@($invalidOverrideResult.Errors) -join "`n")
Assert-True (-not [bool]$invalidOverrideResult.Ok) 'Expected invalid library route overrides to fail config validation.'
Assert-True ($invalidOverrideErrors -match 'Library profile Movies override is invalid: RouteThresholdMode must be one of') 'Expected invalid RouteThresholdMode override error.'
Assert-True ($invalidOverrideErrors -match 'Library profile Movies override is invalid: MovieRouteMaxVideoBitrateMbps must be an integer') 'Expected malformed movie bitrate override error.'
Assert-True ($invalidOverrideErrors -match 'Library profile Movies override is invalid: TVRouteMaxVideoBitrateMbps must be between 1 and 500') 'Expected zero TV bitrate override error.'
Assert-True ($invalidOverrideErrors -match 'Library profile Movies override is invalid: EncodeThresholdGB must be at least 1') 'Expected negative size threshold override error.'

$duplicateRootConfig = Get-MediaPipelineConfigDefaultValues
$duplicateRootConfig['LibraryProfiles'] = @(
    [ordered]@{ id = 'movies'; name = 'Movies'; enabled = $true; designation = 'movie'; source_path = 'C:\Incoming\Movies'; output_path = 'D:\Processed'; overrides = [ordered]@{} },
    [ordered]@{ id = 'tv'; name = 'TV'; enabled = $true; designation = 'tv'; source_path = 'C:\Incoming\TV'; output_path = 'D:\Processed'; overrides = [ordered]@{} },
    [ordered]@{ id = 'alpha'; name = 'Alpha'; enabled = $true; designation = 'movie'; source_path = 'C:\SharedLibrary'; output_path = 'D:\AlphaProcessed'; overrides = [ordered]@{} },
    [ordered]@{ id = 'beta'; name = 'Beta'; enabled = $true; designation = 'movie'; source_path = 'C:\SharedLibrary'; output_path = 'D:\BetaProcessed'; overrides = [ordered]@{} }
)
$duplicateRootResult = Test-MediaPipelineConfigSchema -Config $duplicateRootConfig
$duplicateRootErrors = (@($duplicateRootResult.Errors) -join "`n")
Assert-True (-not [bool]$duplicateRootResult.Ok) 'Expected duplicate enabled library source roots to fail config validation.'
Assert-True ($duplicateRootErrors -match 'Beta shares an enabled source root with Alpha') 'Expected duplicate enabled source root error.'

Write-Host 'Library profile routing checks passed.'
