[CmdletBinding()]
param()

if ($PSVersionTable.PSVersion.Major -lt 7) {
    $pwsh = (Get-Command pwsh.exe -ErrorAction SilentlyContinue).Source
    if (-not $pwsh) { $pwsh = (Get-Command pwsh -ErrorAction SilentlyContinue).Source }
    if (-not $pwsh) {
        throw "Pipeline queue engine checks require PowerShell 7. Install pwsh or use the bundled runtime."
    }
    & $pwsh -NoProfile -ExecutionPolicy Bypass -File $PSCommandPath @args
    exit $LASTEXITCODE
}

$ErrorActionPreference = 'Stop'

$testsRoot = Split-Path -Parent $PSCommandPath
$pipelineRoot = Split-Path -Parent (Split-Path -Parent $testsRoot)
$repoRoot = Split-Path -Parent (Split-Path -Parent $pipelineRoot)
if (-not (Test-Path -LiteralPath (Join-Path $repoRoot 'AGENTS.md') -PathType Leaf)) {
    throw "Unable to resolve repository root from $PSCommandPath."
}
if (-not (Test-Path -LiteralPath (Join-Path $repoRoot 'ops\pipeline\engine') -PathType Container)) {
    throw "Resolved repository root is missing ops\pipeline\engine: $repoRoot"
}

. (Join-Path $repoRoot 'ops\pipeline\engine\shared\native.ps1')
. (Join-Path $repoRoot 'ops\pipeline\engine\queue\queue_plan.ps1')
. (Join-Path $repoRoot 'ops\pipeline\engine\naming\naming.ps1')
$script:QueueEngineActualGetTVInfoFromFile = ${function:Get-TVInfoFromFile}
. (Join-Path $repoRoot 'ops\pipeline\engine\queue\pipeline_engine.ps1')

function Assert-True {
    param([bool] $Condition, [string] $Message)
    if (-not $Condition) { throw $Message }
}

function Assert-Equal {
    param($Actual, $Expected, [string] $Message)
    if ($Actual -ne $Expected) {
        throw "$Message Expected '$Expected', got '$Actual'."
    }
}

Assert-Equal (Get-QueueEpisodeNumber '[SubsPlease] Kanan-sama wa Akumade Choroi - 12v2 (1080p) [80A8418A]') 12 'Queue ordering should ignore uploader revision suffixes.'

function New-ManualOrderSortEntry {
    param(
        [string] $SourcePath,
        [bool] $IsTV = $false
    )
    return [pscustomobject]@{
        SourcePath     = $SourcePath
        File           = [pscustomobject]@{ Name = [System.IO.Path]::GetFileName($SourcePath); Length = 1 }
        IsTV           = $IsTV
        ShowSortKey    = if ($IsTV) { 'Show' } else { [System.IO.Path]::GetFileNameWithoutExtension($SourcePath) }
        RelativePathSort = [System.IO.Path]::GetFileName($SourcePath)
        LastWriteUtc   = [datetime]'2026-06-04T00:00:00Z'
    }
}

function Invoke-ManualOrderSortsHighPriorityBucketsCheck {
    $highMovieA = New-ManualOrderSortEntry 'C:\Media\HighA.mkv'
    $highMovieB = New-ManualOrderSortEntry 'C:\Media\HighB.mkv'
    $highTvA = New-ManualOrderSortEntry 'C:\Media\Show\S01E01.mkv' $true
    $highTvB = New-ManualOrderSortEntry 'C:\Media\Show\S01E02.mkv' $true
    $normalMovieA = New-ManualOrderSortEntry 'C:\Media\NormalA.mkv'
    $normalMovieB = New-ManualOrderSortEntry 'C:\Media\NormalB.mkv'
    $manifest = @{
        version = 1
        entries = @{
            'c:/media/higha.mkv' = @{ position = 2 }
            'c:/media/highb.mkv' = @{ position = 1 }
            'c:/media/show/s01e01.mkv' = @{ position = 4 }
            'c:/media/show/s01e02.mkv' = @{ position = 3 }
            'c:/media/normala.mkv' = @{ position = 6 }
            'c:/media/normalb.mkv' = @{ position = 5 }
        }
    }

    $sorted = Invoke-QueueStrategySort `
        -Strategy 'ManualOrder' `
        -HighMovies @($highMovieA, $highMovieB) `
        -HighTV @($highTvA, $highTvB) `
        -NormalMovies @($normalMovieA, $normalMovieB) `
        -NormalTV @() `
        -LowEntries @() `
        -Manifest $manifest

    Assert-Equal ((@($sorted.HighMovies) | ForEach-Object { $_.SourcePath }) -join '|') 'C:\Media\HighB.mkv|C:\Media\HighA.mkv' 'ManualOrder should sort high-priority movie bucket by manifest position.'
    Assert-Equal ((@($sorted.HighTV) | ForEach-Object { $_.SourcePath }) -join '|') 'C:\Media\Show\S01E02.mkv|C:\Media\Show\S01E01.mkv' 'ManualOrder should sort high-priority TV bucket by manifest position.'
    Assert-Equal ((@($sorted.NormalMovies) | ForEach-Object { $_.SourcePath }) -join '|') 'C:\Media\NormalB.mkv|C:\Media\NormalA.mkv' 'ManualOrder should keep sorting normal movie bucket by manifest position.'
}

function Invoke-ExplicitManifestNormalSuppressesFilesystemPriorityCheck {
    $tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('MediaPipelineQueuePriorityTest_' + [guid]::NewGuid().ToString('N'))
    $previousMarkers = $script:PriorityMarkers
    try {
        New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null
        $script:PriorityMarkers = @('!')
        $source = Join-Path $tempRoot '! Movie.mkv'
        Set-Content -LiteralPath $source -Value 'fake media' -Encoding UTF8
        $file = Get-Item -LiteralPath $source
        $key = $source.Replace('\', '/').ToLowerInvariant().TrimEnd('/')
        $manifest = @{
            version = 1
            entries = @{
                $key = @{ level = 'normal'; reason = 'operator normalized marker'; position = 1 }
            }
        }

        $entries = @(Get-QueuedEntries -Files @($file) -RootPath $tempRoot -PriorityManifest $manifest)
        Assert-Equal $entries.Count 1 'Expected one queued entry.'
        Assert-True ([bool]$entries[0].PriorityInfo.IsPriority) 'Fixture should still carry the physical filesystem priority marker.'
        Assert-True ([bool]$entries[0].ManifestPriorityExplicit) 'Exact normal manifest entry should be marked explicit.'
        Assert-Equal $entries[0].EffectivePriorityLevel 'normal' 'Explicit manifest normal should suppress filesystem priority.'

        $phasePlan = New-MediaQueuePhasePlan -MovieEntries $entries -TVEntries @()
        Assert-Equal @($phasePlan.HighPriorityMovieEntries).Count 0 'Explicit manifest normal should not enter high-priority movie phase.'
        Assert-Equal @($phasePlan.NormalMovieEntries).Count 1 'Explicit manifest normal should remain in normal movie phase.'
    } finally {
        $script:PriorityMarkers = $previousMarkers
        if (Test-Path -LiteralPath $tempRoot -PathType Container) {
            Remove-Item -LiteralPath $tempRoot -Recurse -Force
        }
    }
}

function Invoke-CorruptPriorityManifestFailsClosedCheck {
    $tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('MediaPipelineQueuePriorityCorruptTest_' + [guid]::NewGuid().ToString('N'))
    $previousLayout = $script:LocalStateLayout
    try {
        New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null
        $stateRoot = Join-Path $tempRoot 'State'
        New-Item -ItemType Directory -Path $stateRoot -Force | Out-Null
        $source = Join-Path $tempRoot 'Movie.mkv'
        Set-Content -LiteralPath $source -Value 'fake media' -Encoding UTF8
        $manifestPath = Join-Path $stateRoot 'priority_manifest.json'
        Set-Content -LiteralPath $manifestPath -Value '{not-json' -Encoding UTF8
        $script:LocalStateLayout = [pscustomobject]@{
            Paths = [pscustomobject]@{ PriorityManifest = $manifestPath }
        }

        $failedClosed = $false
        try {
            Get-QueuedEntries -Files @((Get-Item -LiteralPath $source)) -RootPath $tempRoot | Out-Null
        } catch {
            $failedClosed = ([string]$_ -match 'Priority manifest is unreadable')
        }
        Assert-True $failedClosed 'Corrupt priority manifest should fail closed before queue entries become runnable.'
    } finally {
        $script:LocalStateLayout = $previousLayout
        if (Test-Path -LiteralPath $tempRoot -PathType Container) {
            Remove-Item -LiteralPath $tempRoot -Recurse -Force
        }
    }
}

function New-TestQueuePlan {
    return [pscustomobject]@{
        HighPriorityMovieEntries = @()
        HighPriorityTVEntries    = @()
        PriorityEntries          = @()
        NormalMovieEntries       = @()
        NormalTVEntries          = @()
        LowEntries               = @()
        HoldEntries              = @()
        MixPriorityPhase         = $false
        MovieCount               = 0
        TVCount                  = 0
        MoviePriorityCount       = 0
        TVPriorityCount          = 0
        LowCount                 = 0
        HoldCount                = 0
    }
}

function Reset-TestDispatchState {
    $script:StopRequested = $false
    $script:SerialDispatchCount = 0
    $script:WorkerDispatchCount = 0
    $script:CleanupDispatchCount = 0
    $script:LastWorkerDispatch = $null
    $script:LogMessages = @()
    $script:StopAfterCurrentBoundaryRequested = $false
    $script:StopAfterCurrentBoundaryAfterDispatchCount = 0
}

function Check-ControlFlags {}
function Test-MediaPipelineStopAfterCurrentBoundary {
    return [bool](
        $script:StopAfterCurrentBoundaryRequested -and
        @($script:ProcessFileCalls).Count -ge [int]$script:StopAfterCurrentBoundaryAfterDispatchCount
    )
}
function Consume-RescanFlag { return $false }
function Invoke-RetryPendingPushes { return 0 }
function Refresh-PendingPublishIndex { return $null }
function Invalidate-ProcessedIndexCache {}
function Reset-ProgressItemContext {}
function Write-Log {
    param([string] $Message, [string] $Level = 'INFO')
    $script:LogMessages += "$Level`:$Message"
}
function Set-ProgressStage {
    param(
        [string] $Stage,
        [string] $Status,
        $Percent,
        $Route,
        $CopyState,
        $PushState,
        $SidecarState,
        [switch] $SaveNow
    )
}
function Reset-RoundTracking {}
function Get-ProcessedIndexCached {
    param([switch] $ForceRefresh)
    return @{}
}
function Get-MediaQueueDiscoveryPlan {
    param(
        [string] $MovieRoot,
        [string] $TVRoot,
        [switch] $ForceRefresh
    )
    return New-TestQueuePlan
}
function Already-Processed {
    param($File, [bool] $IsTV, $TvInfo, $ProcessedIndex)
    return ([string]$File.Name -eq 'Already.mkv')
}
function Get-TVInfoFromFile {
    param(
        $File,
        [string] $SourceRootPath = '',
        [string] $LibraryName = '',
        [string] $LibraryId = '',
        [string] $LibraryDesignation = ''
    )
    if ($script:QueueEngineUseRealTVParser) {
        $script:QueueEngineTVParseCallCount++
        return & $script:QueueEngineActualGetTVInfoFromFile `
            -file $File `
            -SourceRootPath $SourceRootPath `
            -LibraryName $LibraryName `
            -LibraryId $LibraryId `
            -LibraryDesignation $LibraryDesignation
    }
    return [pscustomobject]@{
        IsReliable = $true
        ShowName = 'Show'
        Season = 1
        Episode = 1
        EpisodeEnd = $null
        ParseMode = 'test-stub'
        ParseError = ''
    }
}
function Process-File {
    param(
        $File,
        [bool] $IsTV,
        $ProcessedIndex,
        [int] $QueueIndex = 0,
        [int] $QueueTotal = 0,
        $PriorityInfo = $null,
        [string] $LibraryProfileId = ''
    )
    $script:ProcessFileCalls += ,([pscustomobject]@{
        Name       = [string]$File.Name
        IsTV       = [bool]$IsTV
        QueueIndex = [int]$QueueIndex
        QueueTotal = [int]$QueueTotal
    })
    if ($script:ProcessFileThrowNames -and [string]$File.Name -in @($script:ProcessFileThrowNames)) {
        throw "synthetic process failure for $($File.Name)"
    }
    return [pscustomobject]@{ Status = 'processed'; Success = $true }
}

function New-QueueEngineTestEntry {
    param(
        [Parameter(Mandatory)] [string] $Root,
        [Parameter(Mandatory)] [string] $Name,
        [string] $Phase = 'movie',
        [string] $MediaKind = 'movie',
        [string] $PriorityLevel = 'normal',
        [int] $QueueIndex = 1,
        [int] $QueueTotal = 1
    )

    $path = Join-Path $Root $Name
    $parent = Split-Path -Parent $path
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
    Set-Content -LiteralPath $path -Value 'not real media' -Encoding UTF8
    $file = Get-Item -LiteralPath $path
    return [pscustomobject]@{
        File                   = $file
        SourcePath             = [string]$file.FullName
        RootPath               = [string]$Root
        QueuePhase             = $Phase
        MediaKind              = $MediaKind
        IsTV                   = ($MediaKind -eq 'tv')
        IsPriority             = ($PriorityLevel -eq 'high')
        PriorityInfo           = [pscustomobject]@{ Reasons = @(); PriorityOrderTicks = 0L }
        PriorityOrderTicks     = 0L
        EffectivePriorityLevel = $PriorityLevel
        QueueIndex             = $QueueIndex
        QueueTotal             = $QueueTotal
        SortName               = [System.IO.Path]::GetFileNameWithoutExtension($Name)
        ShowSortKey            = if ($MediaKind -eq 'tv') { 'Show' } else { [System.IO.Path]::GetFileNameWithoutExtension($Name) }
        SeasonSortOrder        = 0
        SeasonSortKey          = ''
        EpisodeSortOrder       = 0
        RelativePathSort       = $Name
        LibraryId              = ''
        LibraryName            = ''
        LibraryDesignation     = ''
        LibraryOutputRoot      = ''
        LastWriteUtc           = $file.LastWriteTimeUtc
        Metadata               = @{}
    }
}

function Invoke-PriorityOnlyQueuePlanSelectsEffectiveHighEntriesCheck {
    $tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('MediaPipelinePriorityOnlyQueuePlanTest_' + [guid]::NewGuid().ToString('N'))
    try {
        New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null
        $highMovie = New-QueueEngineTestEntry -Root $tempRoot -Name 'High Movie.mkv' -Phase 'priority_movie' -MediaKind 'movie' -PriorityLevel 'high'
        $highTV = New-QueueEngineTestEntry -Root $tempRoot -Name 'Show\High S01E01.mkv' -Phase 'priority_tv' -MediaKind 'tv' -PriorityLevel 'high'
        $normalMovie = New-QueueEngineTestEntry -Root $tempRoot -Name 'Normal Movie.mkv' -Phase 'movie' -MediaKind 'movie' -PriorityLevel 'normal'
        $normalTV = New-QueueEngineTestEntry -Root $tempRoot -Name 'Show\Normal S01E02.mkv' -Phase 'tv' -MediaKind 'tv' -PriorityLevel 'normal'
        $strategyPromotedNormalTV = New-QueueEngineTestEntry -Root $tempRoot -Name 'Show\Strategy Promoted Normal S01E05.mkv' -Phase 'priority_tv' -MediaKind 'tv' -PriorityLevel 'normal'
        $lowMovie = New-QueueEngineTestEntry -Root $tempRoot -Name 'Low Movie.mkv' -Phase 'low' -MediaKind 'movie' -PriorityLevel 'low'
        $lowTV = New-QueueEngineTestEntry -Root $tempRoot -Name 'Show\Low S01E03.mkv' -Phase 'low' -MediaKind 'tv' -PriorityLevel 'low'
        $holdMovie = New-QueueEngineTestEntry -Root $tempRoot -Name 'Hold Movie.mkv' -Phase 'hold' -MediaKind 'movie' -PriorityLevel 'hold'
        $holdTV = New-QueueEngineTestEntry -Root $tempRoot -Name 'Show\Hold S01E04.mkv' -Phase 'hold' -MediaKind 'tv' -PriorityLevel 'hold'

        $plan = New-TestQueuePlan
        $plan.HighPriorityMovieEntries = @($highMovie)
        $plan.HighPriorityTVEntries = @($highTV, $strategyPromotedNormalTV)
        $plan.PriorityEntries = @($highMovie, $highTV)
        $plan.NormalMovieEntries = @($normalMovie)
        $plan.NormalTVEntries = @($normalTV)
        $plan.LowEntries = @($lowMovie, $lowTV)
        $plan.HoldEntries = @($holdMovie, $holdTV)
        $plan.MovieCount = 4
        $plan.TVCount = 4
        $plan.MoviePriorityCount = 1
        $plan.TVPriorityCount = 1
        $plan.LowCount = 2
        $plan.HoldCount = 2

        $priorityOnlyPlan = Select-MediaPipelinePriorityOnlyQueuePlan -QueuePlan $plan

        Assert-Equal ((@($priorityOnlyPlan.HighPriorityMovieEntries) | ForEach-Object { $_.File.Name }) -join '|') 'High Movie.mkv' 'PriorityOnly should retain only effective-High movie entries.'
        Assert-Equal ((@($priorityOnlyPlan.HighPriorityTVEntries) | ForEach-Object { $_.File.Name }) -join '|') 'High S01E01.mkv' 'PriorityOnly should retain only effective-High TV entries.'
        Assert-Equal ([string]$priorityOnlyPlan.HighPriorityMovieEntries[0].QueuePhase) 'priority_movie' 'PriorityOnly should preserve the high-movie phase.'
        Assert-Equal ([string]$priorityOnlyPlan.HighPriorityTVEntries[0].QueuePhase) 'priority_tv' 'PriorityOnly should preserve the high-TV phase.'
        Assert-Equal ((@($priorityOnlyPlan.PriorityEntries) | ForEach-Object { $_.File.Name }) -join '|') 'High Movie.mkv|High S01E01.mkv' 'PriorityOnly should retain legacy combined priority evidence in movie-then-TV order.'
        Assert-Equal @($priorityOnlyPlan.NormalMovieEntries).Count 0 'PriorityOnly must exclude Normal movies.'
        Assert-Equal @($priorityOnlyPlan.NormalTVEntries).Count 0 'PriorityOnly must exclude Normal TV entries.'
        Assert-Equal @($priorityOnlyPlan.LowEntries).Count 0 'PriorityOnly must exclude Low entries.'
        Assert-Equal @($priorityOnlyPlan.HoldEntries).Count 0 'PriorityOnly must exclude Hold entries.'
        Assert-Equal ([int]$priorityOnlyPlan.MovieCount) 1 'PriorityOnly movie count should include only effective-High movies.'
        Assert-Equal ([int]$priorityOnlyPlan.TVCount) 1 'PriorityOnly TV count should include only effective-High TV entries.'
        Assert-Equal ([int]$priorityOnlyPlan.MoviePriorityCount) 1 'PriorityOnly should preserve the high-movie count.'
        Assert-Equal ([int]$priorityOnlyPlan.TVPriorityCount) 1 'PriorityOnly should preserve the high-TV count.'
        Assert-Equal ([int]$priorityOnlyPlan.LowCount) 0 'PriorityOnly low count must be zero.'
        Assert-Equal ([int]$priorityOnlyPlan.HoldCount) 0 'PriorityOnly hold count must be zero.'
    } finally {
        if (Test-Path -LiteralPath $tempRoot -PathType Container) {
            Remove-Item -LiteralPath $tempRoot -Recurse -Force
        }
    }
}

function New-QueueEngineSyntheticEntry {
    param(
        [Parameter(Mandatory)] [string] $Root,
        [Parameter(Mandatory)] [string] $Name,
        [int] $QueueIndex = 1,
        [int] $QueueTotal = 1
    )

    $path = Join-Path $Root $Name
    $file = [pscustomobject]@{
        Name             = $Name
        FullName         = $path
        Length           = 1
        Extension        = '.mkv'
        LastWriteTimeUtc = [datetime]'2026-06-04T00:00:00Z'
    }
    return [pscustomobject]@{
        File                   = $file
        SourcePath             = [string]$path
        RootPath               = [string]$Root
        QueuePhase             = 'movie'
        MediaKind              = 'movie'
        IsTV                   = $false
        IsPriority             = $false
        PriorityInfo           = [pscustomobject]@{ Reasons = @(); PriorityOrderTicks = 0L }
        PriorityOrderTicks     = 0L
        EffectivePriorityLevel = 'normal'
        QueueIndex             = $QueueIndex
        QueueTotal             = $QueueTotal
        SortName               = [System.IO.Path]::GetFileNameWithoutExtension($Name)
        ShowSortKey            = [System.IO.Path]::GetFileNameWithoutExtension($Name)
        SeasonSortOrder        = 0
        SeasonSortKey          = ''
        EpisodeSortOrder       = 0
        RelativePathSort       = $Name
        LibraryId              = ''
        LibraryName            = ''
        LibraryDesignation     = ''
        LibraryOutputRoot      = ''
        LastWriteUtc           = [datetime]'2026-06-04T00:00:00Z'
        Metadata               = @{}
    }
}

function Invoke-KananRevisionQueueSnapshotParseReuseCheck {
    $tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('MediaPipelineQueueKananRevisionTest_' + [guid]::NewGuid().ToString('N'))
    $previousAggressiveEpisodeParsing = $script:AggressiveEpisodeParsing
    $previousUseRealTVParser = $script:QueueEngineUseRealTVParser
    $previousTVParseCallCount = $script:QueueEngineTVParseCallCount
    $previousValidExtensions = $script:ValidExtensions
    $previousOutputContainer = $script:OutputContainer
    $previousSourceTV = $script:SourceTV
    $previousLocalBase = $script:LocalBase
    try {
        $tvRoot = Join-Path $tempRoot 'TV'
        $showRoot = Join-Path $tvRoot 'Kanan-sama wa Akumade Choroi'
        New-Item -ItemType Directory -Path $showRoot -Force | Out-Null
        $episodeFiles = @(
            '[SubsPlease] Kanan-sama wa Akumade Choroi - 09 (1080p) [23C50705].mkv',
            '[SubsPlease] Kanan-sama wa Akumade Choroi - 10 (1080p) [219C7DF9].mkv',
            '[SubsPlease] Kanan-sama wa Akumade Choroi - 11 (1080p) [911C7398].mkv',
            '[SubsPlease] Kanan-sama wa Akumade Choroi - 12v2 (1080p) [80A8418A].mkv',
            'Unparseable Bonus Clip.mkv'
        )
        foreach ($episodeFile in $episodeFiles) {
            [System.IO.File]::WriteAllBytes((Join-Path $showRoot $episodeFile), [System.Text.Encoding]::UTF8.GetBytes("queue-$episodeFile"))
        }

        $script:AggressiveEpisodeParsing = $true
        $script:QueueEngineUseRealTVParser = $true
        $script:QueueEngineTVParseCallCount = 0
        $script:ValidExtensions = @('.mkv')
        $script:OutputContainer = '.mkv'
        $script:SourceTV = $tvRoot
        $script:LocalBase = $tempRoot
        $libraryProfile = @{
            library_id = 'tv'
            library_name = 'TV'
            designation = 'tv'
            output_root = ''
        }
        $manifest = @{ version = 1; entries = @{} }
        $files = @(Get-ChildItem -LiteralPath $showRoot -File)
        $entries = @(Get-QueuedEntries -Files $files -RootPath $tvRoot -IsTV -LibraryProfileMetadata $libraryProfile -PriorityManifest $manifest)

        Assert-Equal (@($entries | Where-Object { $_.TVParseReliable } | ForEach-Object { [int]$_.EpisodeSortOrder }) -join '|') '9|10|11|12' 'Queue discovery should sort the revised episode after episodes 09-11 by canonical episode identity.'
        Assert-Equal (@($entries | Where-Object { -not $_.TVParseReliable }).Count) 1 'An unreliable TV row should remain visible in discovery evidence.'
        Assert-True (-not [bool]$entries[-1].TVParseReliable) 'Unreliable TV rows should sort after every reliable canonical identity.'

        $plan = New-TestQueuePlan
        $plan.NormalTVEntries = @(Set-QueueEntryRuntimeMetadata -Entries $entries -IsTV $true -PhaseOverride 'tv')
        $plan.TVCount = $plan.NormalTVEntries.Count
        $snapshot = Build-QueuePlanSnapshotRows -QueuePlan $plan -ProcessedIndex @{}
        $revisionPath = Join-Path $showRoot '[SubsPlease] Kanan-sama wa Akumade Choroi - 12v2 (1080p) [80A8418A].mkv'
        $revisionRow = @($snapshot.rows | Where-Object { [string]$_.source_path -eq $revisionPath })[0]
        $revisionAcceptedRow = @($snapshot.accepted_run_rows | Where-Object { [string]$_.source_path -eq $revisionPath })[0]
        $unreliableRow = @($snapshot.rows | Where-Object { [string]$_.source_path -eq (Join-Path $showRoot 'Unparseable Bonus Clip.mkv') })[0]

        Assert-Equal ([int]$snapshot.runnable_count) 4 'All four Kanan episodes should remain runnable in the Queue dry-run snapshot.'
        Assert-True ($null -ne $revisionRow) 'Queue dry run should emit a row for the exact real-world 12v2 fixture.'
        Assert-True ([string]$revisionRow.blocked_reason_code -ne 'tv_parse_unreliable') 'The exact real-world 12v2 fixture must not be blocked as tv_parse_unreliable.'
        Assert-True ([string]::IsNullOrWhiteSpace([string]$revisionRow.blocked_reason)) 'The exact real-world 12v2 fixture should have no snapshot preflight block.'
        Assert-Equal ([int]$revisionRow.season_number) 1 'Queue dry run should resolve the exact real-world fixture to season 1.'
        Assert-Equal ([int]$revisionRow.episode_number) 12 'Queue dry run should resolve the exact real-world fixture to episode 12.'
        Assert-Equal ([int]$revisionRow.run_queue_index) 4 'Queue dry run ordering should place episode 12v2 after episodes 09-11.'
        Assert-Equal ([string]$revisionAcceptedRow.display_name) 'Kanan-sama wa Akumade Choroi - S01E12.mkv' 'Accepted workload must expose the production TV rename state, not the raw release filename.'
        Assert-Equal ([string]$unreliableRow.blocked_reason_code) 'tv_parse_unreliable' 'An unreliable cached TV identity should remain visible but blocked in Queue dry-run.'
        Assert-Equal ([int]$script:QueueEngineTVParseCallCount) 5 'Queue discovery should parse each TV file once and the dry-run snapshot should reuse both reliable and unreliable canonical results.'
    } finally {
        $script:AggressiveEpisodeParsing = $previousAggressiveEpisodeParsing
        $script:QueueEngineUseRealTVParser = $previousUseRealTVParser
        $script:QueueEngineTVParseCallCount = $previousTVParseCallCount
        $script:ValidExtensions = $previousValidExtensions
        $script:OutputContainer = $previousOutputContainer
        $script:SourceTV = $previousSourceTV
        $script:LocalBase = $previousLocalBase
        if (Test-Path -LiteralPath $tempRoot -PathType Container) {
            Remove-Item -LiteralPath $tempRoot -Recurse -Force
        }
    }
}

function Invoke-ActiveBadRenameCorpusQueueChecks {
    $fixturePath = Join-Path $repoRoot 'tests\fixtures\rename\bad_rename_cases.jsonl'
    Assert-True (Test-Path -LiteralPath $fixturePath -PathType Leaf) 'The authoritative bad-rename JSONL fixture should exist for Queue execution coverage.'
    $cases = @(Get-Content -LiteralPath $fixturePath | ForEach-Object {
        $line = ([string]$_).Trim()
        if ($line -and -not $line.StartsWith('#')) { $line | ConvertFrom-Json }
    } | Where-Object { [string]$_.status -eq 'active' -and [string]$_.kind -eq 'tv_auto' })
    Assert-True ($cases.Count -gt 0) 'The authoritative bad-rename corpus should contain active TV cases for Queue execution coverage.'

    $tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('MediaPipelineQueueBadRenameCorpusTest_' + [guid]::NewGuid().ToString('N'))
    $previousAggressiveEpisodeParsing = $script:AggressiveEpisodeParsing
    $previousUseRealTVParser = $script:QueueEngineUseRealTVParser
    $previousTVParseCallCount = $script:QueueEngineTVParseCallCount
    $previousValidExtensions = $script:ValidExtensions
    $previousSourceTV = $script:SourceTV
    $previousLocalBase = $script:LocalBase
    $previousTVFilterOptions = $script:RenameTVFilterOptions
    $previousTVFilterTerms = $script:RenameTVFilterTerms
    $previousTVRemoveTerms = $script:RenameTVRemoveTerms
    try {
        New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null
        $script:AggressiveEpisodeParsing = $true
        $script:QueueEngineUseRealTVParser = $true
        $script:QueueEngineTVParseCallCount = 0
        $script:ValidExtensions = @('.mkv','.mp4','.avi','.mov','.m4v','.ts','.m2ts')
        $script:LocalBase = $tempRoot

        foreach ($case in $cases) {
            $caseId = [string]$case.id
            $caseRoot = Join-Path (Join-Path $tempRoot $caseId) 'TV'
            $sourceFolder = Join-Path $caseRoot ([string]$case.source_folder)
            New-Item -ItemType Directory -Path $sourceFolder -Force | Out-Null
            $sourcePath = Join-Path $sourceFolder ([string]$case.source_file)
            [System.IO.File]::WriteAllBytes($sourcePath, [System.Text.Encoding]::UTF8.GetBytes("bad-rename-queue-$caseId"))
            $script:SourceTV = $caseRoot

            if ($case.PSObject.Properties['tv_filter_options']) { $script:RenameTVFilterOptions = $case.tv_filter_options } else { Remove-Variable -Name RenameTVFilterOptions -Scope Script -ErrorAction SilentlyContinue }
            if ($case.PSObject.Properties['tv_filter_terms']) { $script:RenameTVFilterTerms = $case.tv_filter_terms } else { Remove-Variable -Name RenameTVFilterTerms -Scope Script -ErrorAction SilentlyContinue }
            if ($case.PSObject.Properties['tv_remove_terms']) {
                $script:RenameTVRemoveTerms = $case.tv_remove_terms
            } elseif ($case.PSObject.Properties['remove_terms']) {
                $script:RenameTVRemoveTerms = $case.remove_terms
            } else {
                Remove-Variable -Name RenameTVRemoveTerms -Scope Script -ErrorAction SilentlyContinue
            }

            $libraryProfile = @{
                library_id = 'tv'
                library_name = 'TV'
                designation = 'tv'
                output_root = ''
            }
            $manifest = @{ version = 1; entries = @{} }
            $entries = @(Get-QueuedEntries -Files @((Get-Item -LiteralPath $sourcePath)) -RootPath $caseRoot -IsTV -LibraryProfileMetadata $libraryProfile -PriorityManifest $manifest)
            Assert-Equal $entries.Count 1 "Bad-rename Queue case '$caseId' should produce one queue entry."
            $entry = $entries[0]
            $plan = New-TestQueuePlan
            $plan.NormalTVEntries = @(Set-QueueEntryRuntimeMetadata -Entries $entries -IsTV $true -PhaseOverride 'tv')
            $plan.TVCount = 1
            $snapshot = Build-QueuePlanSnapshotRows -QueuePlan $plan -ProcessedIndex @{}
            $row = @($snapshot.rows | Where-Object { [string]$_.source_path -eq $sourcePath })[0]
            Assert-True ($null -ne $row) "Bad-rename Queue case '$caseId' should produce a dry-run snapshot row."

            $expectedBlocked = $false
            if ($case.PSObject.Properties['expected_queue_blocked']) {
                $expectedBlocked = [bool]$case.expected_queue_blocked
            } elseif ($case.PSObject.Properties['expected_blocked']) {
                $expectedBlocked = [bool]$case.expected_blocked
            }
            $isBlocked = -not [string]::IsNullOrWhiteSpace([string]$row.blocked_reason_code)
            Assert-Equal $isBlocked $expectedBlocked "Bad-rename Queue case '$caseId' blocked state should match the fixture."
            Assert-Equal ([int]$snapshot.runnable_count) $(if ($expectedBlocked) { 0 } else { 1 }) "Bad-rename Queue case '$caseId' runnable count should match its blocked state."

            $expectedReasonCode = ''
            if ($case.PSObject.Properties['expected_queue_block_reason_code']) {
                $expectedReasonCode = [string]$case.expected_queue_block_reason_code
            } elseif ($case.PSObject.Properties['expected_block_reason_code']) {
                $expectedReasonCode = [string]$case.expected_block_reason_code
            }
            if (-not [string]::IsNullOrWhiteSpace($expectedReasonCode)) {
                Assert-Equal ([string]$row.blocked_reason_code) $expectedReasonCode "Bad-rename Queue case '$caseId' block reason code should match the fixture."
            }
            if ($case.PSObject.Properties['expected_error_contains']) {
                Assert-True ([string]$row.blocked_reason -like "*$([string]$case.expected_error_contains)*") "Bad-rename Queue case '$caseId' should expose the expected error fragment."
            }

            if ($case.PSObject.Properties['expected_parse_mode']) {
                Assert-Equal ([string]$entry.TVInfo.ParseMode) ([string]$case.expected_parse_mode) "Bad-rename Queue case '$caseId' parse mode should match the fixture."
            }
            if ($case.PSObject.Properties['expected_episode_end']) {
                Assert-Equal ([int]$entry.TVInfo.EpisodeEnd) ([int]$case.expected_episode_end) "Bad-rename Queue case '$caseId' episode range end should match the fixture."
            }

            $expectedShowSortKey = ''
            if ($case.PSObject.Properties['expected_queue_show_sort_key']) {
                $expectedShowSortKey = [string]$case.expected_queue_show_sort_key
            } elseif ($case.PSObject.Properties['expected_show']) {
                $expectedShowSortKey = [string]$case.expected_show
            } elseif ([string]$case.expected_name -match '^(?<show>.+?)\s+-\s+S\d{2}E\d{2,3}\b') {
                $expectedShowSortKey = [string]$Matches['show']
            }
            if (-not [string]::IsNullOrWhiteSpace($expectedShowSortKey)) {
                Assert-Equal ([string]$entry.ShowSortKey) $expectedShowSortKey "Bad-rename Queue case '$caseId' show sort key should match its expected identity."
            }

            $expectedSeasonSortOrder = $null
            if ($case.PSObject.Properties['expected_queue_season_sort_order']) {
                $expectedSeasonSortOrder = [int]$case.expected_queue_season_sort_order
            } elseif ($case.PSObject.Properties['expected_season']) {
                $expectedSeasonSortOrder = [int]$case.expected_season
            } elseif ([string]$case.expected_name -match '\bS(?<season>\d{2})E\d{2,3}\b') {
                $expectedSeasonSortOrder = [int]$Matches['season']
            }
            if ($null -ne $expectedSeasonSortOrder) {
                Assert-Equal ([int]$entry.SeasonSortOrder) ([int]$expectedSeasonSortOrder) "Bad-rename Queue case '$caseId' season sort order should match the fixture."
                Assert-Equal ([int]$row.season_number) ([int]$expectedSeasonSortOrder) "Bad-rename Queue case '$caseId' snapshot season should match the fixture."
            }

            $expectedEpisodeSortOrder = $null
            if ($case.PSObject.Properties['expected_queue_episode_sort_order']) {
                $expectedEpisodeSortOrder = [int]$case.expected_queue_episode_sort_order
            } elseif ($case.PSObject.Properties['expected_episode']) {
                $expectedEpisodeSortOrder = [int]$case.expected_episode
            } elseif ([string]$case.expected_name -match '\bS\d{2}E(?<episode>\d{2,3})\b') {
                $expectedEpisodeSortOrder = [int]$Matches['episode']
            }
            if ($null -ne $expectedEpisodeSortOrder) {
                Assert-Equal ([int]$entry.EpisodeSortOrder) ([int]$expectedEpisodeSortOrder) "Bad-rename Queue case '$caseId' episode sort order should match the fixture."
                Assert-Equal ([int]$row.episode_number) ([int]$expectedEpisodeSortOrder) "Bad-rename Queue case '$caseId' snapshot episode should match the fixture."
            }
        }

        Assert-Equal ([int]$script:QueueEngineTVParseCallCount) $cases.Count 'Queue snapshot coverage should reuse the one canonical parser result created for each active bad-rename TV case.'
    } finally {
        $script:AggressiveEpisodeParsing = $previousAggressiveEpisodeParsing
        $script:QueueEngineUseRealTVParser = $previousUseRealTVParser
        $script:QueueEngineTVParseCallCount = $previousTVParseCallCount
        $script:ValidExtensions = $previousValidExtensions
        $script:SourceTV = $previousSourceTV
        $script:LocalBase = $previousLocalBase
        $script:RenameTVFilterOptions = $previousTVFilterOptions
        $script:RenameTVFilterTerms = $previousTVFilterTerms
        $script:RenameTVRemoveTerms = $previousTVRemoveTerms
        if (Test-Path -LiteralPath $tempRoot -PathType Container) {
            Remove-Item -LiteralPath $tempRoot -Recurse -Force
        }
    }
}

function Invoke-GlobalRunnableQueueSnapshotMetadataCheck {
    $tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("MediaPipelineQueueRunCountTest_" + [guid]::NewGuid().ToString('N'))
    try {
        New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null
        $highOne = New-QueueEngineTestEntry -Root $tempRoot -Name 'HighOne.mkv' -Phase 'priority_movie' -MediaKind 'movie' -PriorityLevel 'high' -QueueIndex 1 -QueueTotal 2
        $highTwo = New-QueueEngineTestEntry -Root $tempRoot -Name 'HighTwo.mkv' -Phase 'priority_movie' -MediaKind 'movie' -PriorityLevel 'high' -QueueIndex 2 -QueueTotal 2
        $normal = New-QueueEngineTestEntry -Root $tempRoot -Name 'Normal.mkv' -Phase 'movie' -MediaKind 'movie' -PriorityLevel 'normal' -QueueIndex 1 -QueueTotal 2
        $already = New-QueueEngineTestEntry -Root $tempRoot -Name 'Already.mkv' -Phase 'movie' -MediaKind 'movie' -PriorityLevel 'normal' -QueueIndex 2 -QueueTotal 2
        $tv = New-QueueEngineTestEntry -Root $tempRoot -Name 'Show\S01E01.mkv' -Phase 'tv' -MediaKind 'tv' -PriorityLevel 'normal' -QueueIndex 1 -QueueTotal 1
        $low = New-QueueEngineTestEntry -Root $tempRoot -Name 'Low.mkv' -Phase 'low' -MediaKind 'movie' -PriorityLevel 'low' -QueueIndex 1 -QueueTotal 1
        $hold = New-QueueEngineTestEntry -Root $tempRoot -Name 'Hold.mkv' -Phase 'hold' -MediaKind 'movie' -PriorityLevel 'hold' -QueueIndex 0 -QueueTotal 0

        $plan = New-TestQueuePlan
        $plan.HighPriorityMovieEntries = @($highOne, $highTwo)
        $plan.NormalMovieEntries = @($normal, $already)
        $plan.NormalTVEntries = @($tv)
        $plan.LowEntries = @($low)
        $plan.HoldEntries = @($hold)
        $plan.HoldCount = 1
        $script:configPath = ''
        $script:LocalBase = $tempRoot
        $script:SourceMovies = $tempRoot
        $script:SourceTV = $tempRoot
        $script:Outsource = ''
        $script:ValidExtensions = @('.mkv')

        $snapshot = Build-QueuePlanSnapshotRows -QueuePlan $plan -ProcessedIndex @{}
        Assert-Equal $snapshot.runnable_count 5 'Snapshot runnable_count should exclude already-processed and hold rows.'
        Assert-Equal $snapshot.excluded_count 1 'Snapshot should report the already-processed row as excluded.'
        Assert-Equal ([int]$normal.RunQueueIndex) 3 'Normal movie should be third in the global runnable order.'
        Assert-Equal ([int]$normal.RunQueueTotal) 5 'Normal movie should see the full runnable queue total.'
        Assert-Equal ([int]$normal.QueueIndex) 1 'Normal movie bucket index should remain unchanged.'
        Assert-Equal ([int]$normal.QueueTotal) 2 'Normal movie bucket total should remain unchanged.'
        Assert-Equal ([int]$already.RunQueueIndex) 0 'Already-processed rows must not receive runnable queue position.'
        Assert-Equal ([int]$already.RunQueueTotal) 0 'Already-processed rows must not receive runnable queue total.'

        $normalRow = @($snapshot.rows | Where-Object { $_['source_path'] -eq [string]$normal.SourcePath })[0]
        $tvRow = @($snapshot.rows | Where-Object { $_['source_path'] -eq [string]$tv.SourcePath })[0]
        $lowRow = @($snapshot.rows | Where-Object { $_['source_path'] -eq [string]$low.SourcePath })[0]
        $holdRow = @($snapshot.rows | Where-Object { $_['source_path'] -eq [string]$hold.SourcePath })[0]
        Assert-Equal ([int]$normalRow['run_queue_index']) 3 'Snapshot row should expose global run index.'
        Assert-Equal ([int]$normalRow['run_queue_total']) 5 'Snapshot row should expose global run total.'
        Assert-Equal ([int]$normalRow['queue_index']) 1 'Snapshot row should preserve bucket index.'
        Assert-Equal ([int]$normalRow['queue_total']) 2 'Snapshot row should preserve bucket total.'
        Assert-Equal ([int]$tvRow['run_queue_index']) 4 'TV row should follow high-priority and normal movie rows.'
        Assert-Equal ([int]$lowRow['run_queue_index']) 5 'Low-priority row should be last runnable item.'
        Assert-Equal ([int]$holdRow['run_queue_index']) 0 'Hold rows should not have global runnable index.'
        Assert-Equal ([int]$holdRow['run_queue_total']) 0 'Hold rows should not have global runnable total.'
    } finally {
        if (Test-Path -LiteralPath $tempRoot -ErrorAction SilentlyContinue) {
            Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}

function Invoke-AcceptedRunUsesBackendRenameDisplayNameCheck {
    $tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("MediaPipelineQueueRenameDisplayTest_" + [guid]::NewGuid().ToString('N'))
    $previousOutputContainer = $script:OutputContainer
    $existingShowOverrideResolver = Get-Command -Name Resolve-ShowOverrides -CommandType Function -ErrorAction SilentlyContinue
    $originalShowOverrideResolver = if ($existingShowOverrideResolver) { $existingShowOverrideResolver.ScriptBlock } else { $null }
    try {
        New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null
        $entry = New-QueueEngineTestEntry `
            -Root $tempRoot `
            -Name 'Django.Unchained.2012.1080p.BluRay.x264.YIFY.mp4' `
            -Phase 'movie' `
            -MediaKind 'movie'
        $edgeEntry = New-QueueEngineTestEntry `
            -Root $tempRoot `
            -Name 'Edge.of.Tomorrow.2014.1080p.BluRay.DDP5.1.x265.10bit-GalaxyRG265.mkv' `
            -Phase 'movie' `
            -MediaKind 'movie'
        $tvEntry = New-QueueEngineTestEntry `
            -Root $tempRoot `
            -Name 'Raw.Show.S01E01.mkv' `
            -Phase 'tv' `
            -MediaKind 'tv'
        $cachedTvInfo = [pscustomobject]@{
            IsReliable = $true
            ShowName = 'Raw Show'
            Season = 1
            Episode = 1
            EpisodeEnd = $null
            OriginalName = 'Raw.Show.S01E01.mkv'
            ParseMode = 'test-stub'
            ParseError = ''
        }
        $tvEntry | Add-Member -NotePropertyName TVIdentityParsed -NotePropertyValue $true -Force
        $tvEntry | Add-Member -NotePropertyName TVInfo -NotePropertyValue $cachedTvInfo -Force
        $plan = New-TestQueuePlan
        $plan.NormalMovieEntries = @($entry, $edgeEntry)
        $plan.NormalTVEntries = @($tvEntry)
        $plan.MovieCount = 2
        $plan.TVCount = 1
        $script:configPath = ''
        $script:LocalBase = $tempRoot
        $script:SourceMovies = $tempRoot
        $script:SourceTV = $tempRoot
        $script:Outsource = ''
        $script:ValidExtensions = @('.mp4', '.mkv')
        $script:OutputContainer = '.mp4'
        Set-Item -LiteralPath Function:\Resolve-ShowOverrides -Value {
            param([string] $ShowName)
            if ([string]::Equals($ShowName, 'Raw Show', [System.StringComparison]::Ordinal)) {
                return [pscustomobject]@{ ShowName = 'Canonical Show' }
            }
            return $null
        }

        $snapshot = Build-QueuePlanSnapshotRows -QueuePlan $plan -ProcessedIndex @{}
        $accepted = @($snapshot.accepted_run_rows | Where-Object { [string]$_.source_path -eq [string]$entry.SourcePath })[0]
        $edgeAccepted = @($snapshot.accepted_run_rows | Where-Object { [string]$_.source_path -eq [string]$edgeEntry.SourcePath })[0]
        $tvAccepted = @($snapshot.accepted_run_rows | Where-Object { [string]$_.source_path -eq [string]$tvEntry.SourcePath })[0]

        Assert-Equal ([string]$accepted.display_name) 'Django Unchained (2012).mp4' 'Accepted workload must use the production planned rename filename.'
        Assert-Equal ([string]$accepted.planned_display_name) 'Django Unchained (2012).mp4' 'Accepted workload must expose the explicit production planned filename.'
        Assert-Equal ([string]$accepted.planned_display_name_source) 'plex_destination_plan.v1' 'Accepted workload must version its production naming-plan evidence.'
        Assert-Equal ([System.IO.Path]::GetFileName([string]$accepted.source_path)) 'Django.Unchained.2012.1080p.BluRay.x264.YIFY.mp4' 'Raw source identity must remain unchanged.'
        Assert-Equal ([string]$edgeAccepted.display_name) 'Edge of Tomorrow (2014).mp4' 'Accepted workload must discard the complete verified metadata tail without a filename-specific release-group rule.'
        Assert-Equal ([string]$tvAccepted.display_name) 'Canonical Show - S01E01.mp4' 'Accepted TV naming must apply the same reliable ShowName override used by execution.'
        Assert-Equal ([string]$cachedTvInfo.ShowName) 'Raw Show' 'Accepted TV naming must not mutate the cached parsed identity while planning the canonical execution name.'
        Assert-Equal ([string]$snapshot.accepted_run_rows_fingerprint_schema) 'accepted_run_rows_fingerprint.v1' 'Accepted workload must publish a versioned content fingerprint.'
        Assert-Equal ([string]$snapshot.accepted_run_rows_fingerprint) (Get-MediaPipelineAcceptedRunRowsFingerprint -Rows $snapshot.accepted_run_rows) 'Accepted workload content fingerprint must bind the clean planned names and stable identities.'

        $originalFingerprint = [string]$snapshot.queue_plan_fingerprint
        $originalAcceptedRowsFingerprint = [string]$snapshot.accepted_run_rows_fingerprint
        $overridePath = Get-RenameOverrideSidecarPath -File $entry.File
        $overridePayload = [ordered]@{
            RenameTool = [ordered]@{
                ForcePipelineName = $true
                FinalName = 'Operator Approved Django Name.mp4'
            }
        } | ConvertTo-Json -Depth 5
        Set-Content -LiteralPath $overridePath -Value $overridePayload -Encoding UTF8

        $forcedSnapshot = Build-QueuePlanSnapshotRows -QueuePlan $plan -ProcessedIndex @{}
        $forcedAccepted = @($forcedSnapshot.accepted_run_rows)[0]
        Assert-Equal ([string]$forcedAccepted.display_name) 'Operator Approved Django Name.mp4' 'Accepted workload must honor the authoritative force-rename sidecar.'
        Assert-True ([string]$forcedSnapshot.queue_plan_fingerprint -ne $originalFingerprint) 'Changing the accepted backend naming plan must change the accepted Queue fingerprint.'
        Assert-True ([string]$forcedSnapshot.accepted_run_rows_fingerprint -ne $originalAcceptedRowsFingerprint) 'Changing the accepted backend naming plan must change the accepted workload content fingerprint.'
    } finally {
        if ($originalShowOverrideResolver) {
            Set-Item -LiteralPath Function:\Resolve-ShowOverrides -Value $originalShowOverrideResolver
        } else {
            Remove-Item -LiteralPath Function:\Resolve-ShowOverrides -ErrorAction SilentlyContinue
        }
        $script:OutputContainer = $previousOutputContainer
        if (Test-Path -LiteralPath $tempRoot -PathType Container) {
            Remove-Item -LiteralPath $tempRoot -Recurse -Force
        }
    }
}

function Invoke-QueuePlanFingerprintDimensionCheck {
    $row = [pscustomobject]@{
        global_order = 1; phase = 'movie'; media_kind = 'movie'; source_path = 'C:\Media\Movie.mkv'
        display_name = 'Rendered label only'; manifest_priority_level = 'normal'; route = 'remux'
        route_reason_code = 'copy_compatible'; blocked_reason_code = ''
    }
    $accepted = [pscustomobject]@{
        run_queue_index = 1; run_queue_total = 1; source_identity = 'source-identity-a'
        source_path = 'C:\Media\Movie.mkv'; planned_display_name = 'Movie (2026).mkv'
        planned_display_name_source = 'plex_destination_plan.v1'; route = 'remux'
        route_reason_code = 'copy_compatible'; intended_final_path = 'C:\Final\Movie (2026).mkv'
    }
    $backpressure = [pscustomobject]@{
        Blocked = $false; BlockReason = ''; DeferredPublish = $false; ManifestCount = 0; RetryExhaustedCount = 0
    }
    $health = [pscustomobject]@{
        status = 'ready'; count = 0; missing_payload_count = 0; unreadable_manifest_count = 0
    }
    $baseline = Get-MediaPipelineQueuePlanFingerprint `
        -Rows @($row) -ExcludedRows @() -AcceptedRows @($accepted) `
        -InputFingerprint 'inputs-a' -OrderingStrategy 'priority_then_oldest' `
        -PendingBackpressure $backpressure -PendingHealth $health

    $renderOnlyRow = [pscustomobject]@{
        global_order = 1; phase = 'movie'; media_kind = 'movie'; source_path = 'C:\Media\Movie.mkv'
        display_name = 'Different rendered label'; manifest_priority_level = 'normal'; route = 'remux'
        route_reason_code = 'copy_compatible'; blocked_reason_code = ''
    }
    $renderOnly = Get-MediaPipelineQueuePlanFingerprint `
        -Rows @($renderOnlyRow) -ExcludedRows @() -AcceptedRows @($accepted) `
        -InputFingerprint 'inputs-a' -OrderingStrategy 'priority_then_oldest' `
        -PendingBackpressure $backpressure -PendingHealth $health
    Assert-Equal $renderOnly $baseline 'A render-only display label must not alter execution identity.'

    $sourceChangedRow = [pscustomobject]@{
        global_order = 1; phase = 'movie'; media_kind = 'movie'; source_path = 'C:\Media\Replacement.mkv'
        display_name = 'Rendered label only'; manifest_priority_level = 'normal'; route = 'remux'
        route_reason_code = 'copy_compatible'; blocked_reason_code = ''
    }
    $sourceChanged = Get-MediaPipelineQueuePlanFingerprint `
        -Rows @($sourceChangedRow) -ExcludedRows @() -AcceptedRows @($accepted) `
        -InputFingerprint 'inputs-a' -OrderingStrategy 'priority_then_oldest' `
        -PendingBackpressure $backpressure -PendingHealth $health
    Assert-True ($sourceChanged -ne $baseline) 'A source inventory membership change must alter the active Queue plan fingerprint.'

    $inputsChanged = Get-MediaPipelineQueuePlanFingerprint `
        -Rows @($row) -ExcludedRows @() -AcceptedRows @($accepted) `
        -InputFingerprint 'inputs-b' -OrderingStrategy 'priority_then_oldest' `
        -PendingBackpressure $backpressure -PendingHealth $health
    Assert-True ($inputsChanged -ne $baseline) 'Config/profile, priority/hold, strategy/manual-order, or file-override input changes must alter the Queue plan fingerprint.'

    $strategyChanged = Get-MediaPipelineQueuePlanFingerprint `
        -Rows @($row) -ExcludedRows @() -AcceptedRows @($accepted) `
        -InputFingerprint 'inputs-a' -OrderingStrategy 'manual_order' `
        -PendingBackpressure $backpressure -PendingHealth $health
    Assert-True ($strategyChanged -ne $baseline) 'An ordering strategy change must alter the Queue plan fingerprint.'

    $blockedBackpressure = [pscustomobject]@{
        Blocked = $true; BlockReason = 'deferred_threshold'; DeferredPublish = $true; ManifestCount = 3; RetryExhaustedCount = 1
    }
    $pendingChanged = Get-MediaPipelineQueuePlanFingerprint `
        -Rows @($row) -ExcludedRows @() -AcceptedRows @($accepted) `
        -InputFingerprint 'inputs-a' -OrderingStrategy 'priority_then_oldest' `
        -PendingBackpressure $blockedBackpressure -PendingHealth $health
    Assert-True ($pendingChanged -ne $baseline) 'Pending-publish backpressure changes must alter the Queue plan fingerprint.'

    $blockedHealth = [pscustomobject]@{
        status = 'blocked'; count = 1; missing_payload_count = 1; unreadable_manifest_count = 0
    }
    $healthChanged = Get-MediaPipelineQueuePlanFingerprint `
        -Rows @($row) -ExcludedRows @() -AcceptedRows @($accepted) `
        -InputFingerprint 'inputs-a' -OrderingStrategy 'priority_then_oldest' `
        -PendingBackpressure $backpressure -PendingHealth $blockedHealth
    Assert-True ($healthChanged -ne $baseline) 'Pending-publish index health changes must alter the Queue plan fingerprint.'

    $renamedAccepted = [pscustomobject]@{
        run_queue_index = 1; run_queue_total = 1; source_identity = 'source-identity-a'
        source_path = 'C:\Media\Movie.mkv'; planned_display_name = 'Operator Name (2026).mkv'
        planned_display_name_source = 'plex_destination_plan.v1'; route = 'remux'
        route_reason_code = 'copy_compatible'; intended_final_path = 'C:\Final\Operator Name (2026).mkv'
    }
    $renameChanged = Get-MediaPipelineQueuePlanFingerprint `
        -Rows @($row) -ExcludedRows @() -AcceptedRows @($renamedAccepted) `
        -InputFingerprint 'inputs-a' -OrderingStrategy 'priority_then_oldest' `
        -PendingBackpressure $backpressure -PendingHealth $health
    Assert-True ($renameChanged -ne $baseline) 'A production naming-plan change must alter execution identity.'
}

function Invoke-AcceptedRunBlocksWhenBackendNamingEvidenceFailsCheck {
    $tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("MediaPipelineQueueRenameFailureTest_" + [guid]::NewGuid().ToString('N'))
    $originalPlanner = (Get-Command -Name New-PlexDestinationPlan -ErrorAction Stop).ScriptBlock
    $existingLibraryOverrideResolver = Get-Command -Name Resolve-MediaPipelineLibraryOverridesForPath -ErrorAction SilentlyContinue
    $originalLibraryOverrideResolver = if ($existingLibraryOverrideResolver) { $existingLibraryOverrideResolver.ScriptBlock } else { $null }
    $previousOutputContainer = $script:OutputContainer
    try {
        New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null
        $successfulEntry = New-QueueEngineTestEntry -Root $tempRoot -Name 'Naming.Success.2026.mkv' -Phase 'movie' -MediaKind 'movie' -QueueIndex 1 -QueueTotal 3
        $failedEntry = New-QueueEngineTestEntry -Root $tempRoot -Name 'Naming.Failure.2026.mkv' -Phase 'movie' -MediaKind 'movie' -QueueIndex 2 -QueueTotal 3
        $overrideFailureEntry = New-QueueEngineTestEntry -Root $tempRoot -Name 'Naming.Override.Failure.2026.mkv' -Phase 'movie' -MediaKind 'movie' -QueueIndex 3 -QueueTotal 3
        $plan = New-TestQueuePlan
        $plan.NormalMovieEntries = @($successfulEntry, $failedEntry, $overrideFailureEntry)
        $plan.MovieCount = 3
        $script:configPath = ''
        $script:LocalBase = $tempRoot
        $script:SourceMovies = $tempRoot
        $script:SourceTV = $tempRoot
        $script:Outsource = ''
        $script:ValidExtensions = @('.mkv')
        $script:OutputContainer = '.mkv'

        $script:QueueEngineOriginalDestinationPlanner = $originalPlanner
        Set-Item -LiteralPath Function:\New-PlexDestinationPlan -Value {
            param(
                [string]$MediaKind,
                $File = $null,
                $TvInfo = $null,
                [string]$OriginalName = '',
                [string]$Extension = '',
                [switch]$IncludeLibraryFolder,
                [string]$LibraryFolder = ''
            )
            if ([string]$File.Name -eq 'Naming.Failure.2026.mkv') {
                throw 'synthetic naming planner failure'
            }
            & $script:QueueEngineOriginalDestinationPlanner @PSBoundParameters
        }
        Set-Item -LiteralPath Function:\Resolve-MediaPipelineLibraryOverridesForPath -Value {
            param([string]$SourcePath, [string]$LibraryProfileId = '')
            if ([System.IO.Path]::GetFileName($SourcePath) -eq 'Naming.Override.Failure.2026.mkv') {
                throw 'synthetic pre-naming override failure'
            }
            return [ordered]@{}
        }
        $snapshot = Build-QueuePlanSnapshotRows -QueuePlan $plan -ProcessedIndex @{}

        Assert-Equal ([int]$snapshot.runnable_count) 1 'Only files with backend-authored naming evidence may enter the accepted workload.'
        Assert-Equal ([int]$snapshot.accepted_run_rows.Count) 1 'Naming failure must not persist the raw source leaf as accepted planned-name evidence.'
        Assert-Equal ([string]$snapshot.accepted_run_rows[0].display_name) 'Naming Success (2026).mkv' 'The preceding successful naming plan must remain accepted.'
        Assert-Equal ([string]$snapshot.rows[1].blocked_reason_code) 'destination_naming_plan_failed' 'Queue must expose an explicit backend naming-plan blocker.'
        Assert-Equal ([string]$snapshot.rows[1].route_reason_code) 'destination_naming_plan_failed' 'A stale route from the preceding row must not overwrite the naming blocker.'
        Assert-True ([string]$snapshot.rows[1].blocked_reason -match 'synthetic naming planner failure') 'Queue naming blocker must preserve the backend planner reason.'
        Assert-Equal ([string]$snapshot.rows[2].blocked_reason_code) 'destination_naming_plan_failed' 'An exception before the naming planner must also block Queue acceptance.'
        Assert-Equal ([string]$snapshot.rows[2].route_reason_code) 'destination_naming_plan_failed' 'Pre-naming failure must not retain stale route evidence.'
        Assert-True ([string]$snapshot.rows[2].blocked_reason -match 'synthetic pre-naming override failure') 'Pre-naming blocker must preserve the backend evidence reason.'
    } finally {
        Set-Item -LiteralPath Function:\New-PlexDestinationPlan -Value $originalPlanner
        if ($originalLibraryOverrideResolver) {
            Set-Item -LiteralPath Function:\Resolve-MediaPipelineLibraryOverridesForPath -Value $originalLibraryOverrideResolver
        } else {
            Remove-Item -LiteralPath Function:\Resolve-MediaPipelineLibraryOverridesForPath -ErrorAction SilentlyContinue
        }
        Remove-Variable -Name QueueEngineOriginalDestinationPlanner -Scope Script -ErrorAction SilentlyContinue
        $script:OutputContainer = $previousOutputContainer
        if (Test-Path -LiteralPath $tempRoot -PathType Container) {
            Remove-Item -LiteralPath $tempRoot -Recurse -Force
        }
    }
}

function Invoke-QueueSnapshotRowsAreCappedButTotalsRemainAccurateCheck {
    $tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("MediaPipelineQueueRowCapTest_" + [guid]::NewGuid().ToString('N'))
    $previousRowLimit = $script:QueueSnapshotRowLimit
    $previousRunId = $script:PipelineRunId
    $previousRunMonitorContext = $script:BackendQueueRunMonitorSeedContext
    try {
        New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null
        $script:QueueSnapshotRowLimit = 5
        $script:PipelineRunId = 'uncapped-monitor-run'
        $script:BackendQueueRunMonitorSeedContext = [pscustomobject]@{
            RunId = 'uncapped-monitor-run'
            QueuePlanFingerprint = 'accepted-plan'
        }
        $entries = [System.Collections.ArrayList]::new()
        $acceptedTotal = 505
        for ($index = 1; $index -le $acceptedTotal; $index++) {
            $entries.Add((New-QueueEngineSyntheticEntry -Root $tempRoot -Name ("Movie-{0:D3}.mkv" -f $index) -QueueIndex $index -QueueTotal $acceptedTotal)) | Out-Null
        }
        $plan = New-TestQueuePlan
        $plan.NormalMovieEntries = $entries.ToArray()
        $plan.MovieCount = $acceptedTotal
        $script:configPath = ''
        $script:LocalBase = $tempRoot
        $script:SourceMovies = $tempRoot
        $script:SourceTV = $tempRoot
        $script:Outsource = ''
        $script:ValidExtensions = @('.mkv')

        $snapshot = Build-QueuePlanSnapshotRows -QueuePlan $plan -ProcessedIndex @{}

        Assert-Equal $snapshot.runnable_count $acceptedTotal 'Snapshot runnable_count must preserve the full runnable total.'
        Assert-Equal $snapshot.total_row_count $acceptedTotal 'Snapshot total_row_count must preserve the full display candidate total.'
        Assert-Equal $snapshot.shown_row_count 5 'Snapshot should cap displayed rows at the row limit.'
        Assert-Equal $snapshot.row_limit 5 'Snapshot row_limit should expose the display cap.'
        Assert-True ([bool]$snapshot.rows_truncated) 'Snapshot should mark rows_truncated when display rows are capped.'
        Assert-Equal ([int]$snapshot.rows.Count) 5 'Snapshot rows payload should be capped.'
        Assert-Equal ([int]$snapshot.rows[0]['run_queue_total']) $acceptedTotal 'Visible runnable rows must retain the full run_queue_total.'
        Assert-Equal ([int]$plan.NormalMovieEntries[$acceptedTotal - 1].RunQueueTotal) $acceptedTotal 'Non-visible entries must still receive the full RunQueueTotal for execution.'
        Assert-Equal ([int]$script:LastRunMonitorAcceptedRows.Count) $acceptedTotal 'Run monitor membership must preserve every accepted row beyond the display cap and legacy 500-row limit.'
        Assert-Equal ([int]$script:LastRunMonitorAcceptedRows[$acceptedTotal - 1].run_queue_index) $acceptedTotal 'Uncapped monitor membership must preserve the final run-wide position.'
        Assert-Equal ([int]$script:LastRunMonitorAcceptedRows[$acceptedTotal - 1].run_queue_total) $acceptedTotal 'Uncapped monitor membership must preserve the run-wide total.'
        Assert-True (-not [string]::IsNullOrWhiteSpace([string]$script:LastRunMonitorAcceptedRows[$acceptedTotal - 1].job_id)) 'Every accepted monitor row must have a stable job ID.'
        Assert-True (-not [string]::IsNullOrWhiteSpace([string]$script:LastRunMonitorAcceptedRows[$acceptedTotal - 1].source_identity)) 'Every accepted monitor row must have a path-aware source identity.'
        Assert-Equal ([int]$snapshot.accepted_run_rows.Count) $acceptedTotal 'The durable dry-run snapshot must preserve uncapped accepted membership for pre-scan seeding.'
        Assert-Equal ([int]$snapshot.accepted_run_rows[$acceptedTotal - 1].run_queue_index) $acceptedTotal 'Accepted snapshot membership must preserve the final run-wide position.'
        Assert-Equal ([int]$snapshot.accepted_run_rows[$acceptedTotal - 1].run_queue_total) $acceptedTotal 'Accepted snapshot membership must preserve the run-wide total.'
        Assert-True (-not $snapshot.accepted_run_rows[0].Contains('job_id')) 'A pre-launch accepted plan must not claim a run job ID before the backend creates the run.'

        $script:BackendQueueRunMonitorSeedContext = $null
        $standaloneEntry = New-QueueEngineSyntheticEntry -Root $tempRoot -Name 'Standalone-Once.mkv' -QueueIndex 1 -QueueTotal 1
        $standalonePlan = New-TestQueuePlan
        $standalonePlan.NormalMovieEntries = @($standaloneEntry)
        $standalonePlan.MovieCount = 1
        $standaloneSnapshot = Build-QueuePlanSnapshotRows -QueuePlan $standalonePlan -ProcessedIndex @{}

        Assert-Equal ([int]$script:LastRunMonitorAcceptedRows.Count) 0 'A queue round without an adopted Backend Queue seed must not invent active monitor membership.'
        Assert-True (-not $standaloneEntry.PSObject.Properties['RunMonitorJobId']) 'A standalone queue entry must not receive a monitor job ID merely because the process has a run ID.'
        Assert-Equal ([int]$standaloneSnapshot.accepted_run_rows.Count) 1 'Standalone planning must retain ordinary uncapped accepted-row preview evidence.'
        Assert-True (-not $standaloneSnapshot.accepted_run_rows[0].Contains('job_id')) 'Standalone accepted-row preview evidence must remain free of monitor job identity.'
    } finally {
        $script:QueueSnapshotRowLimit = $previousRowLimit
        $script:PipelineRunId = $previousRunId
        $script:BackendQueueRunMonitorSeedContext = $previousRunMonitorContext
        if (Test-Path -LiteralPath $tempRoot -ErrorAction SilentlyContinue) {
            Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}

function Invoke-AcceptedRunRowsMustMatchActiveEvidenceExactlyCheck {
    $accepted = [pscustomobject]@{
        job_id = 'run-1-item-00000001'; source_identity = 'source-1'; source_path = 'C:\Media\Movie.mkv'
        source_identity_algorithm = 'path_size_mtime_sha256.v1'; display_name = 'Movie.mkv'; display_name_source = 'plex_destination_plan.v1'; parent_context = 'C:\Media'
        run_queue_index = 1; run_queue_total = 1; route = 'remux'; route_reason = 'Compatible streams'
        route_reason_code = 'streams_compatible'; intended_final_path = 'C:\Final\Movie.mkv'
    }
    Assert-True (Assert-MediaPipelineRunMonitorActiveMembershipMatchesAcceptedSnapshot -AcceptedRows @($accepted) -ActiveRows @($accepted)) `
        'An exact active rescan should match the accepted Run Once workload.'

    foreach ($field in @('source_identity_algorithm','display_name','display_name_source','parent_context','route','route_reason','route_reason_code','intended_final_path')) {
        $active = $accepted | Select-Object *
        $active.$field = "tampered-$field"
        $rejected = $false
        try {
            Assert-MediaPipelineRunMonitorActiveMembershipMatchesAcceptedSnapshot -AcceptedRows @($accepted) -ActiveRows @($active) | Out-Null
        } catch {
            $rejected = ([string]$_ -match 'RUN_MONITOR_ACTIVE_MEMBERSHIP_MISMATCH')
        }
        Assert-True $rejected "Accepted monitor evidence must reject active parity changes to $field."
    }
}

function Invoke-AcceptedRunSeedRequiresPlannedNameEvidenceCheck {
    $tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("MediaPipelineAcceptedNameEvidenceTest_" + [guid]::NewGuid().ToString('N'))
    try {
        New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null
        $crossRuntimeVector = [ordered]@{
            run_queue_index = 1; run_queue_total = 1; source_identity = 'source-1'
            source_identity_algorithm = 'path_size_mtime_sha256.v1'; source_path = 'C:\Media\Django.mkv'
            planned_display_name = 'Django Unchained (2012).mkv'; planned_display_name_source = 'plex_destination_plan.v1'
            parent_context = 'C:\Media'; route = 'remux'; route_reason_code = 'compatible'
            route_reason = 'Compatible streams'; intended_final_path = 'C:\Final\Django Unchained (2012).mkv'
        }
        Assert-Equal `
            (Get-MediaPipelineAcceptedRunRowsFingerprint -Rows @($crossRuntimeVector)) `
            '4b5ae5cb3bb7d1ce1a1c8f93df5e71fa3bd88a725c9a38f12765f7fa073fbaee' `
            'PowerShell accepted-workload fingerprint must match the bundled Python canonical test vector.'
        $unicodeCrossRuntimeVector = [ordered]@{
            run_queue_index = 1; run_queue_total = 1; source_identity = 'source-straße-STRASSE'
            source_identity_algorithm = 'path_size_mtime_sha256.v1'; source_path = 'C:\Médien\Straße\STRASSE.mkv'
            planned_display_name = 'Straße and STRASSE (2026).mkv'; planned_display_name_source = 'plex_destination_plan.v1'
            parent_context = 'C:\Médien\Straße'; route = 'remux'; route_reason_code = 'compatible'
            route_reason = 'Preserve Straße and STRASSE distinctly'; intended_final_path = 'C:\Final\Straße and STRASSE (2026).mkv'
        }
        Assert-Equal `
            (Get-MediaPipelineAcceptedRunRowsFingerprint -Rows @($unicodeCrossRuntimeVector)) `
            'ace99b28d58a6f32177a320dbfddb64781e10cfea8d773fd7ab6ca1bbe27cd63' `
            'PowerShell accepted-workload fingerprint must match the bundled Python Unicode canonical test vector.'
        $unicodeFingerprint = Get-MediaPipelineAcceptedRunRowsFingerprint -Rows @($unicodeCrossRuntimeVector)
        $asciiCaseVariant = ([pscustomobject]$unicodeCrossRuntimeVector | Select-Object *)
        $asciiCaseVariant.source_path = 'c:\Médien\Straße\strasse.mkv'
        Assert-Equal `
            (Get-MediaPipelineAcceptedRunRowsFingerprint -Rows @($asciiCaseVariant)) `
            $unicodeFingerprint `
            'Accepted-workload path normalization must ignore ASCII-only path casing.'
        $unicodeTextChange = ([pscustomobject]$unicodeCrossRuntimeVector | Select-Object *)
        $unicodeTextChange.source_path = 'C:\Médien\STRASSE\STRASSE.mkv'
        Assert-True `
            ((Get-MediaPipelineAcceptedRunRowsFingerprint -Rows @($unicodeTextChange)) -ne $unicodeFingerprint) `
            'Accepted-workload path normalization must not collapse distinct non-ASCII path text.'
        $snapshotPath = Join-Path $tempRoot 'queue_snapshot.json'
        $acceptedRow = [ordered]@{
            source_identity = 'source-1'; source_identity_algorithm = 'path_size_mtime_sha256.v1'
            source_path = 'C:\Media\Django.Unchained.2012.1080p.BluRay.x264.YIFY.mkv'
            display_name = 'Django.Unchained.2012.1080p.BluRay.x264.YIFY.mkv'; parent_context = 'C:\Media'
            run_queue_index = 1; run_queue_total = 1; route = 'remux'; route_reason = 'Compatible streams'
            route_reason_code = 'streams_compatible'; intended_final_path = 'C:\Final\Django Unchained (2012).mkv'
        }
        $snapshot = [ordered]@{
            schema_version = 'queue_plan_snapshot.v1'; queue_snapshot_origin = 'dry_run'
            queue_plan_fingerprint_schema = 'queue_plan_fingerprint.v1'; queue_plan_fingerprint = 'accepted-plan'
            runnable_count = 1; accepted_run_rows = @($acceptedRow)
        }
        $snapshot | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $snapshotPath -Encoding UTF8

        $rejected = $false
        try {
            Get-MediaPipelineRunMonitorSeedRowsFromAcceptedSnapshot -Path $snapshotPath -ExpectedFingerprint 'accepted-plan' -RunId 'run-1' | Out-Null
        } catch {
            $rejected = ([string]$_ -match 'RUN_MONITOR_ACCEPTED_NAME_EVIDENCE_MISSING')
        }
        Assert-True $rejected 'A raw public Queue display_name must not be accepted as production rename-plan evidence.'

        $acceptedRow.planned_display_name = 'Django Unchained (2012).mkv'
        $acceptedRow.planned_display_name_source = 'plex_destination_plan.v1'
        $snapshot.accepted_run_rows_fingerprint_schema = 'accepted_run_rows_fingerprint.v1'
        $snapshot.accepted_run_rows_fingerprint = Get-MediaPipelineAcceptedRunRowsFingerprint -Rows @($acceptedRow)
        $snapshot | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $snapshotPath -Encoding UTF8
        $seedRows = @(Get-MediaPipelineRunMonitorSeedRowsFromAcceptedSnapshot -Path $snapshotPath -ExpectedFingerprint 'accepted-plan' -RunId 'run-1')
        Assert-Equal ([string]$seedRows[0].display_name) 'Django Unchained (2012).mkv' 'Run Monitor seed must map only verified planned-name evidence into display_name.'

        $acceptedRow.planned_display_name = 'Tampered Raw Release.mkv'
        $snapshot | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $snapshotPath -Encoding UTF8
        $tamperRejected = $false
        try {
            Get-MediaPipelineRunMonitorSeedRowsFromAcceptedSnapshot -Path $snapshotPath -ExpectedFingerprint 'accepted-plan' -RunId 'run-1' | Out-Null
        } catch {
            $tamperRejected = ([string]$_ -match 'RUN_MONITOR_ACCEPTED_ROWS_FINGERPRINT_MISMATCH')
        }
        Assert-True $tamperRejected 'Accepted planned-name evidence must remain bound to its content fingerprint at Run Monitor seed time.'
    } finally {
        if (Test-Path -LiteralPath $tempRoot -PathType Container) {
            Remove-Item -LiteralPath $tempRoot -Recurse -Force
        }
    }
}

function Invoke-QueueExecutionCapLimitsRunnableWindowCheck {
    $tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("MediaPipelineQueueExecutionCapTest_" + [guid]::NewGuid().ToString('N'))
    $previousLimit = $script:QueueExecutionMaxRunnablePerRound
    try {
        New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null
        $script:QueueExecutionMaxRunnablePerRound = 3
        $plan = New-TestQueuePlan
        $plan.HighPriorityMovieEntries = @(
            (New-QueueEngineTestEntry -Root $tempRoot -Name 'HighOne.mkv' -Phase 'priority_movie' -MediaKind 'movie' -PriorityLevel 'high' -QueueIndex 1 -QueueTotal 2),
            (New-QueueEngineTestEntry -Root $tempRoot -Name 'HighTwo.mkv' -Phase 'priority_movie' -MediaKind 'movie' -PriorityLevel 'high' -QueueIndex 2 -QueueTotal 2)
        )
        $plan.NormalMovieEntries = @(
            (New-QueueEngineTestEntry -Root $tempRoot -Name 'NormalOne.mkv' -Phase 'movie' -MediaKind 'movie' -PriorityLevel 'normal' -QueueIndex 1 -QueueTotal 2),
            (New-QueueEngineTestEntry -Root $tempRoot -Name 'NormalTwo.mkv' -Phase 'movie' -MediaKind 'movie' -PriorityLevel 'normal' -QueueIndex 2 -QueueTotal 2)
        )
        $plan.LowEntries = @(
            (New-QueueEngineTestEntry -Root $tempRoot -Name 'LowOne.mkv' -Phase 'low' -MediaKind 'movie' -PriorityLevel 'low' -QueueIndex 1 -QueueTotal 1)
        )

        $window = Select-MediaPipelineQueuePlanExecutionWindow -QueuePlan $plan
        $windowEntries = @(Get-MediaPipelineQueuePlanRunnableEntries -QueuePlan $window)

        Assert-True ([bool]$window.RowsTruncatedForExecution) 'Execution cap should mark the execution window as truncated.'
        Assert-Equal ([int]$window.RunnableTotalBeforeCap) 5 'Execution cap should preserve the full runnable total as evidence.'
        Assert-Equal ([int]$window.RunnableExecutionLimit) 3 'Execution cap should expose the configured execution limit.'
        Assert-Equal ([int]$windowEntries.Count) 3 'Execution cap should process only the configured number of runnable rows.'
        Assert-Equal (($windowEntries | ForEach-Object { [string]$_.File.Name }) -join '|') 'HighOne.mkv|HighTwo.mkv|NormalOne.mkv' 'Execution cap should preserve deterministic runnable ordering for the first window.'
        Assert-Equal ([int]@($window.LowEntries).Count) 0 'Execution cap should leave later low-priority rows for a later round.'
    } finally {
        $script:QueueExecutionMaxRunnablePerRound = $previousLimit
        if (Test-Path -LiteralPath $tempRoot -ErrorAction SilentlyContinue) {
            Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}

function Invoke-SerialQueueDispatchUsesGlobalRunnableMetadataCheck {
    $tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("MediaPipelineQueueDispatchRunCountTest_" + [guid]::NewGuid().ToString('N'))
    try {
        New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null
        $highOne = New-QueueEngineTestEntry -Root $tempRoot -Name 'HighOne.mkv' -Phase 'priority_movie' -MediaKind 'movie' -PriorityLevel 'high' -QueueIndex 1 -QueueTotal 2
        $highTwo = New-QueueEngineTestEntry -Root $tempRoot -Name 'HighTwo.mkv' -Phase 'priority_movie' -MediaKind 'movie' -PriorityLevel 'high' -QueueIndex 2 -QueueTotal 2
        $normal = New-QueueEngineTestEntry -Root $tempRoot -Name 'Normal.mkv' -Phase 'movie' -MediaKind 'movie' -PriorityLevel 'normal' -QueueIndex 1 -QueueTotal 1
        $tv = New-QueueEngineTestEntry -Root $tempRoot -Name 'Show\S01E01.mkv' -Phase 'tv' -MediaKind 'tv' -PriorityLevel 'normal' -QueueIndex 1 -QueueTotal 1
        $low = New-QueueEngineTestEntry -Root $tempRoot -Name 'Low.mkv' -Phase 'low' -MediaKind 'movie' -PriorityLevel 'low' -QueueIndex 1 -QueueTotal 1

        $plan = New-TestQueuePlan
        $plan.HighPriorityMovieEntries = @($highOne, $highTwo)
        $plan.NormalMovieEntries = @($normal)
        $plan.NormalTVEntries = @($tv)
        $plan.LowEntries = @($low)
        $script:configPath = ''
        $script:LocalBase = $tempRoot
        $script:SourceMovies = $tempRoot
        $script:SourceTV = $tempRoot
        $script:Outsource = ''
        $script:ValidExtensions = @('.mkv')
        $script:StopRequested = $false
        $script:ProcessFileCalls = @()

        Build-QueuePlanSnapshotRows -QueuePlan $plan -ProcessedIndex @{} | Out-Null
        Invoke-MediaQueuePhasePlan -QueuePlan $plan -ProcessedIndex @{} | Out-Null

        Assert-Equal ([int]$script:ProcessFileCalls.Count) 5 'Serial queue should dispatch all five runnable rows.'
        Assert-Equal ($script:ProcessFileCalls | ForEach-Object { "$($_.Name):$($_.QueueIndex)/$($_.QueueTotal)" } | Select-Object -Index 2) 'Normal.mkv:3/5' 'Normal movie should receive global runnable progress 3/5.'
        Assert-Equal ($script:ProcessFileCalls | ForEach-Object { "$($_.Name):$($_.QueueIndex)/$($_.QueueTotal)" } | Select-Object -Last 1) 'Low.mkv:5/5' 'Low-priority item should receive final global runnable progress.'
    } finally {
        if (Test-Path -LiteralPath $tempRoot -ErrorAction SilentlyContinue) {
            Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}

function Invoke-PendingPublishBackpressureBlocksBeforeExecutionCheck {
    $tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("MediaPipelinePendingBackpressureTest_" + [guid]::NewGuid().ToString('N'))
    $previousPendingRoot = $script:PendingPushRoot
    $previousDeferred = $script:DeferredPublish
    $previousDeferredThreshold = $script:PendingPublishDeferredBlockThreshold
    $previousNormalThreshold = $script:PendingPublishBacklogBlockThreshold
    try {
        $pendingRoot = Join-Path $tempRoot 'State\PendingServerPush'
        New-Item -ItemType Directory -Path $pendingRoot -Force | Out-Null
        foreach ($name in @('one.manifest.json', 'two.manifest.json')) {
            $manifest = @{
                schema_version = 'pending_push_manifest.v1'
                parked_at      = (Get-Date).ToUniversalTime().ToString('o')
                output_size    = 10
                retry_count    = 0
                retry_limit    = 3
            } | ConvertTo-Json -Depth 5
            Set-Content -LiteralPath (Join-Path $pendingRoot $name) -Value $manifest -Encoding UTF8
        }
        $script:PendingPushRoot = $pendingRoot
        $script:DeferredPublish = $true
        $script:PendingPublishDeferredBlockThreshold = 2
        $script:PendingPublishBacklogBlockThreshold = 100
        $script:StopRequested = $false
        $script:RetryPendingCalls = 0
        $script:RefreshPendingCalls = 0
        $script:DiscoveryCalls = 0
        $script:SerialDispatchCount = 0
        $script:BackpressureEvents = @()
        $script:BackpressureStages = @()

        function Invoke-RetryPendingPushes {
            $script:RetryPendingCalls++
            return 0
        }
        function Refresh-PendingPublishIndex {
            $script:RefreshPendingCalls++
            return $null
        }
        function Get-ProcessedIndexCached {
            return @{}
        }
        function Get-MediaQueueDiscoveryPlan {
            $script:DiscoveryCalls++
            return New-TestQueuePlan
        }
        function Invoke-MediaPipelineQueueSnapshot {
            return [pscustomobject]@{ queue_plan_fingerprint = 'backpressure-plan' }
        }
        function Invoke-MediaQueuePhasePlan {
            $script:SerialDispatchCount++
            throw 'queue execution should not run while pending backpressure blocks discovery'
        }
        function Write-PipelineEvent {
            param(
                [string] $EventType,
                [string] $Stage,
                [string] $Status,
                [hashtable] $Data
            )
            $script:BackpressureEvents += ,([pscustomobject]@{
                EventType = $EventType
                Stage     = $Stage
                Status    = $Status
                Data      = $Data
            })
        }
        function Set-ProgressStage {
            param(
                [string] $Stage,
                [string] $Status,
                $Percent,
                $Route,
                $CopyState,
                $PushState,
                $SidecarState,
                [switch] $SaveNow
            )
            $script:BackpressureStages += ,([pscustomobject]@{ Stage = $Stage; Status = $Status; PushState = $PushState })
        }

        $plan = New-MediaPipelineEnginePlan `
            -SourceMovies 'MoviesRoot' `
            -SourceTV 'TVRoot' `
            -QueueSnapshotPath 'snapshot.json' `
            -Once:$false `
            -SleepSeconds 5
        $round = Invoke-MediaPipelineRound -EnginePlan $plan

        Assert-True ([bool]$round.Completed) 'Backpressure-blocked round should complete safely without new queue work.'
        Assert-True ([bool]$round.BackpressureBlocked) 'Round should report backpressure blocked evidence.'
        Assert-Equal ([string]$round.BackpressureReason) 'deferred_backlog_threshold' 'Deferred pending backlog should block at the configured threshold.'
        Assert-Equal ([int]$script:RetryPendingCalls) 1 'Backpressure-blocked round should still run safe pending-publish retry.'
        Assert-Equal ([int]$script:RefreshPendingCalls) 1 'Backpressure-blocked round should still refresh pending publish evidence.'
        Assert-Equal ([int]$script:DiscoveryCalls) 1 'Backpressure evidence should be captured with the same discovery boundary used by the Queue dry-run.'
        Assert-Equal ([int]$script:SerialDispatchCount) 0 'Backpressure should skip queue execution.'
        Assert-Equal ([string]$script:BackpressureEvents[0].EventType) 'pending_publish_backpressure_blocked' 'Backpressure should emit structured event evidence.'
        Assert-Equal ([string]$script:BackpressureEvents[0].Data.block_reason) 'deferred_backlog_threshold' 'Backpressure event should preserve the block reason.'
        Assert-True (@($script:BackpressureStages | Where-Object { $_.Stage -eq 'pending_publish_backpressure' }).Count -eq 1) 'Backpressure should write blocked progress evidence.'
    } finally {
        $script:PendingPushRoot = $previousPendingRoot
        $script:DeferredPublish = $previousDeferred
        $script:PendingPublishDeferredBlockThreshold = $previousDeferredThreshold
        $script:PendingPublishBacklogBlockThreshold = $previousNormalThreshold
        if (Test-Path -LiteralPath $tempRoot -ErrorAction SilentlyContinue) {
            Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}

function Invoke-QueuePlanFingerprintGuardCheck {
    $script:StopRequested = $false
    $script:PipelineBlockedExitCode = 0
    $script:PipelineStopReason = ''
    $script:RetryPendingCalls = 0
    $script:RefreshPendingCalls = 0
    $script:DiscoveryCalls = 0
    $script:SerialDispatchCount = 0
    $script:CleanupDispatchCount = 0
    $script:FingerprintEvents = @()
    $script:SnapshotFingerprint = 'active-plan'
    $script:RunMonitorSeedCount = 0
    $script:SourceDiscoveryHeartbeatCount = 0
    $script:FingerprintDispatchSequence = @()
    $script:FingerprintProgressStages = @()

    function Set-ProgressStage {
        param(
            [string] $Stage,
            [string] $Status,
            $Percent,
            $Route,
            $CopyState,
            $PushState,
            $SidecarState,
            [switch] $SaveNow
        )
        $script:FingerprintProgressStages += ,([pscustomobject]@{ Stage = $Stage; Status = $Status })
    }

    function Get-MediaPipelineRunMonitorAcceptedSeedRows {
        param([string] $RunId, [string] $CommandId, [string] $ExpectedFingerprint)
        $script:RunMonitorSeedCount++
        $script:FingerprintDispatchSequence += 'seed_adopt'
        Assert-Equal ([string]$ExpectedFingerprint) ([string]$script:ExpectedSeedFingerprint) 'Run monitor adoption must use the backend-accepted dry-run fingerprint.'
        return @([ordered]@{
            job_id = "$RunId-item-00000001"; source_identity = 'source-1'; source_path = 'MoviesRoot\Movie.mkv'
        source_identity_algorithm = 'path_size_mtime_sha256.v1'; display_name = 'Movie.mkv'; display_name_source = 'plex_destination_plan.v1'; parent_context = 'MoviesRoot'
            run_queue_index = 1; run_queue_total = 1; route = 'remux'; route_reason = 'policy'; route_reason_code = 'policy'
        })
    }

    function Invoke-RetryPendingPushes {
        $script:RetryPendingCalls++
        return 0
    }
    function Refresh-PendingPublishIndex {
        $script:RefreshPendingCalls++
        return $null
    }
    function Get-ProcessedIndexCached { return @{} }
    function Get-MediaQueueDiscoveryPlan {
        $script:FingerprintDispatchSequence += 'discovery'
        $script:DiscoveryCalls++
        return New-TestQueuePlan
    }
    function Invoke-MediaPipelineQueueSnapshot {
        $script:FingerprintDispatchSequence += 'active_snapshot'
        $script:LastRunMonitorAcceptedRows = @([ordered]@{
            job_id = "$script:PipelineRunId-item-00000001"; source_identity = 'source-1'; source_path = 'MoviesRoot\Movie.mkv'
            source_identity_algorithm = 'path_size_mtime_sha256.v1'; display_name = 'Movie.mkv'; display_name_source = 'plex_destination_plan.v1'; parent_context = 'MoviesRoot'
            run_queue_index = 1; run_queue_total = 1; route = 'remux'; route_reason = 'policy'; route_reason_code = 'policy'
        })
        return [pscustomobject]@{
            queue_plan_fingerprint = [string]$script:SnapshotFingerprint
            runnable_count = 1
        }
    }
    function Set-MediaPipelineRunMonitorSourceDiscoveryState {
        param(
            [string] $RunId,
            [string] $State,
            [string] $RunState,
            [string] $ExpectedQueuePlanFingerprint,
            [string] $EvidenceSource
        )
        if (-not [string]::IsNullOrWhiteSpace($ExpectedQueuePlanFingerprint)) {
            Assert-Equal $ExpectedQueuePlanFingerprint $script:ExpectedSeedFingerprint 'Source-discovery state must remain bound to the accepted Queue fingerprint.'
        }
        $script:FingerprintDispatchSequence += "discovery_state:$State"
    }
    function New-MediaPipelineSourceDiscoveryPollHandler {
        param(
            [string] $RunId,
            [string] $AcceptedQueueFingerprint,
            [double] $MinimumIntervalSeconds
        )
        Assert-Equal $RunId ([string]$script:PipelineRunId) 'Source-discovery heartbeat must use the exact active run ID.'
        Assert-Equal $AcceptedQueueFingerprint $script:ExpectedSeedFingerprint 'Source-discovery heartbeat must use the accepted Queue fingerprint.'
        $script:SourceDiscoveryHeartbeatCount++
        return { param($ElapsedSeconds, $Process) return $null }
    }
    function Invoke-MediaQueuePhasePlan {
        $script:SerialDispatchCount++
        $script:FingerprintDispatchSequence += 'dispatch'
        return [pscustomobject]@{ Stopped = $false }
    }
    function Invoke-PeriodicLocalEncodedDirectoryCleanup {
        $script:CleanupDispatchCount++
        return $null
    }
    function Get-ProcessingStats { return 'stats ok' }
    function Write-RoundFailureSummary { return $null }
    function Get-MediaPipelinePendingPublishBackpressure {
        return [pscustomobject]@{ Blocked = $false; BlockReason = '' }
    }
    function Write-PipelineEvent {
        param([string] $EventType, [string] $Stage, [string] $Status, [hashtable] $Data)
        $script:FingerprintEvents += ,([pscustomobject]@{ EventType = $EventType; Stage = $Stage; Status = $Status; Data = $Data })
    }

    $mismatchPlan = New-MediaPipelineEnginePlan `
        -SourceMovies 'MoviesRoot' `
        -SourceTV 'TVRoot' `
        -QueueSnapshotPath 'snapshot.json' `
        -Once:$true `
        -ExpectedQueuePlanFingerprint 'accepted-plan'
    $script:ExpectedSeedFingerprint = 'accepted-plan'
    $mismatch = Invoke-MediaPipelineRound -EnginePlan $mismatchPlan

    Assert-True (-not [bool]$mismatch.Completed) 'A mismatched active Queue plan must not complete.'
    Assert-True ([bool]$mismatch.FingerprintBlocked) 'A mismatched active Queue plan should return fingerprint-blocked evidence.'
    Assert-Equal ([int]$script:RetryPendingCalls) 0 'A fingerprint-guarded Queue run must not retry or publish parked outputs before verification.'
    Assert-Equal ([int]$script:DiscoveryCalls) 1 'The guard should compare the active discovery plan exactly once.'
    Assert-Equal ([int]$script:SerialDispatchCount) 0 'A mismatched plan must not dispatch media processing.'
    Assert-Equal ([int]$script:RunMonitorSeedCount) 1 'A mismatched active rescan must retain the already accepted, pre-scan monitor membership.'
    Assert-Equal ([int]$script:SourceDiscoveryHeartbeatCount) 1 'A fingerprint-guarded rescan must create one run-scoped discovery heartbeat.'
    Assert-Equal ([string]$script:BackendQueueRunMonitorSeedContext.RunId) ([string]$script:PipelineRunId) 'A mismatched rescan must remain correlated to the accepted run.'
    Assert-Equal ([int]$script:PipelineBlockedExitCode) 76 'A mismatched plan should request the blocked exit code.'
    Assert-Equal ([string]$script:PipelineStopReason) 'queue_plan_fingerprint_mismatch' 'A mismatched plan should preserve its stop reason.'
    Assert-Equal ([string]$script:FingerprintEvents[0].Data.command_id) '' 'Fingerprint mismatch evidence should preserve an empty command ID when none was supplied.'
    Assert-Equal ([string]$script:FingerprintEvents[0].Data.error_code) 'QUEUE_PLAN_FINGERPRINT_MISMATCH' 'Fingerprint mismatch evidence must identify the exact failed dimension.'
    Assert-Equal ([string]$script:FingerprintEvents[0].Data.expected_fingerprint) 'accepted-plan' 'Fingerprint mismatch evidence must retain the backend-accepted plan.'
    Assert-Equal ([string]$script:FingerprintEvents[0].Data.actual_fingerprint) 'active-plan' 'Fingerprint mismatch evidence must retain the rebuilt active plan.'
    Assert-Equal ([string]$script:FingerprintProgressStages[-1].Stage) 'blocked' 'A plan mismatch must persist blocked progress before returning.'
    Assert-True ([string]$script:FingerprintProgressStages[-1].Status -match 'refresh Queue before launch') 'A plan mismatch must guide the operator to refresh Queue.'

    $script:StopRequested = $false
    $script:PipelineBlockedExitCode = 0
    $script:PipelineStopReason = ''
    $script:DiscoveryCalls = 0
    $script:SerialDispatchCount = 0
    $script:CleanupDispatchCount = 0
    $script:RunMonitorSeedCount = 0
    $script:SourceDiscoveryHeartbeatCount = 0
    $script:FingerprintDispatchSequence = @()
    $matchingPlan = New-MediaPipelineEnginePlan `
        -SourceMovies 'MoviesRoot' `
        -SourceTV 'TVRoot' `
        -QueueSnapshotPath 'snapshot.json' `
        -Once:$true `
        -ExpectedQueuePlanFingerprint 'active-plan'
    $script:ExpectedSeedFingerprint = 'active-plan'
    $matching = Invoke-MediaPipelineRound -EnginePlan $matchingPlan

    Assert-True ([bool]$matching.Completed) 'A matching active Queue plan should continue through execution.'
    Assert-Equal ([int]$script:RetryPendingCalls) 0 'A matching fingerprint-guarded run should still defer pending-publish retry side effects.'
    Assert-Equal ([int]$script:SerialDispatchCount) 1 'A matching plan should dispatch the active queue.'
    Assert-Equal ([int]$script:RunMonitorSeedCount) 1 'A matching plan must seed the Run Monitor exactly once.'
    Assert-Equal ([int]$script:SourceDiscoveryHeartbeatCount) 1 'A matching fingerprint-guarded rescan must create one run-scoped discovery heartbeat.'
    Assert-Equal ([string]$script:BackendQueueRunMonitorSeedContext.RunId) ([string]$script:PipelineRunId) 'Successful seed context must preserve the exact run ID.'
    Assert-Equal ([string]$script:BackendQueueRunMonitorSeedContext.QueuePlanFingerprint) 'active-plan' 'Successful seed context must preserve the exact accepted fingerprint.'
    Assert-True ([array]::IndexOf($script:FingerprintDispatchSequence, 'seed_adopt') -lt [array]::IndexOf($script:FingerprintDispatchSequence, 'discovery')) 'Run Monitor membership must be adopted before the active source rescan.'
    Assert-True ([array]::IndexOf($script:FingerprintDispatchSequence, 'discovery_state:active') -lt [array]::IndexOf($script:FingerprintDispatchSequence, 'discovery')) 'Scanning state must be durable before active discovery starts.'
    Assert-True ([array]::IndexOf($script:FingerprintDispatchSequence, 'discovery_state:completed') -lt [array]::IndexOf($script:FingerprintDispatchSequence, 'dispatch')) 'Discovery completion must be durable before media dispatch.'
    Assert-Equal ([int]$script:CleanupDispatchCount) 1 'A matching plan should complete normal round cleanup.'
}

function Invoke-RunMonitorFinalizationClassificationCheck {
    $script:RunMonitorFinalizationCalls = @()
    function Complete-MediaPipelineRunMonitor {
        param(
            [string] $RunId,
            [string] $State,
            [string] $RemainingItemState,
            [string] $Reason,
            [string] $ReasonCode,
            $Retryable,
            [string] $RecoveryOwner,
            [string] $NextAction
        )
        $script:RunMonitorFinalizationCalls += ,([pscustomobject]@{
            RunId = $RunId; State = $State; RemainingItemState = $RemainingItemState
            Reason = $Reason; ReasonCode = $ReasonCode; Retryable = $Retryable
            RecoveryOwner = $RecoveryOwner; NextAction = $NextAction
        })
        return [pscustomobject]@{ run = [pscustomobject]@{ lifecycle_state = $State } }
    }

    $plan = New-MediaPipelineEnginePlan `
        -SourceMovies 'MoviesRoot' `
        -SourceTV 'TVRoot' `
        -QueueSnapshotPath 'snapshot.json' `
        -Once:$true `
        -ExpectedQueuePlanFingerprint 'accepted-plan'
    $script:PipelineRunId = 'finalization-run'
    $script:BackendQueueRunMonitorSeedContext = [pscustomobject]@{
        RunId = 'finalization-run'
        QueuePlanFingerprint = 'accepted-plan'
    }

    Complete-MediaPipelineBackendQueueRunOnceMonitor -EnginePlan $plan -RoundResult ([pscustomobject]@{ Completed = $true }) | Out-Null
    Assert-Equal $script:RunMonitorFinalizationCalls[-1].State 'completed' 'A normally completed round must finalize the monitor as completed.'

    Complete-MediaPipelineBackendQueueRunOnceMonitor -EnginePlan $plan -RoundResult ([pscustomobject]@{ Completed = $true; BackpressureBlocked = $true; BackpressureReason = 'backlog_threshold' }) | Out-Null
    Assert-Equal $script:RunMonitorFinalizationCalls[-1].State 'blocked' 'Pending publish backpressure must finalize the run as blocked.'
    Assert-Equal $script:RunMonitorFinalizationCalls[-1].RemainingItemState 'blocked' 'Backpressure must retain unresolved accepted rows as blocked.'
    Assert-Equal $script:RunMonitorFinalizationCalls[-1].ReasonCode 'PENDING_PUBLISH_BACKPRESSURE_BLOCKED' 'Backpressure must preserve a stable reason code.'

    Complete-MediaPipelineBackendQueueRunOnceMonitor -EnginePlan $plan -RoundResult ([pscustomobject]@{ Completed = $false; StopRequested = $true; FingerprintBlocked = $true }) | Out-Null
    Assert-Equal $script:RunMonitorFinalizationCalls[-1].State 'blocked' 'An accepted run whose active rescan mismatches must finalize as blocked, not stopped.'
    Assert-Equal $script:RunMonitorFinalizationCalls[-1].RemainingItemState 'blocked' 'Fingerprint mismatch must retain every accepted row as blocked.'
    Assert-Equal $script:RunMonitorFinalizationCalls[-1].ReasonCode 'QUEUE_PLAN_FINGERPRINT_MISMATCH' 'Fingerprint mismatch must retain its stable authority code.'

    Complete-MediaPipelineBackendQueueRunOnceMonitor -EnginePlan $plan -RoundResult ([pscustomobject]@{ Completed = $false; StopRequested = $true }) | Out-Null
    Assert-Equal $script:RunMonitorFinalizationCalls[-1].State 'stopped' 'A post-seed stop must finalize the run as stopped.'
    Assert-Equal $script:RunMonitorFinalizationCalls[-1].RemainingItemState 'stopped' 'A post-seed stop must retain undispatched accepted rows as stopped.'

    Complete-MediaPipelineBackendQueueRunOnceMonitor -EnginePlan $plan -RoundResult ([pscustomobject]@{ Completed = $false; StopAfterCurrentRequested = $true }) | Out-Null
    Assert-Equal $script:RunMonitorFinalizationCalls[-1].State 'stopped' 'An acknowledged Stop After Current boundary must finalize the run as stopped.'
    Assert-Equal $script:RunMonitorFinalizationCalls[-1].ReasonCode 'RUN_STOPPED_AT_QUEUE_BOUNDARY' 'Graceful stop finalization must retain the stable queue-boundary reason.'

    $roundError = $null
    try { throw 'synthetic finalization exception' } catch { $roundError = $_ }
    Complete-MediaPipelineBackendQueueRunOnceMonitor -EnginePlan $plan -RoundError $roundError | Out-Null
    Assert-Equal $script:RunMonitorFinalizationCalls[-1].State 'failed' 'A genuine round exception must finalize the run as failed.'
    Assert-Equal $script:RunMonitorFinalizationCalls[-1].RemainingItemState 'skipped' 'Untouched accepted rows must not be mislabeled as media failures after a round exception.'
    Assert-Equal $script:RunMonitorFinalizationCalls[-1].ReasonCode 'UNEXPECTED_PIPELINE_ROUND_EXCEPTION' 'Round exception finalization must use a stable reason code.'

    $beforeMissingContext = @($script:RunMonitorFinalizationCalls).Count
    $script:BackendQueueRunMonitorSeedContext = $null
    Complete-MediaPipelineBackendQueueRunOnceMonitor -EnginePlan $plan -RoundResult ([pscustomobject]@{ Completed = $true }) | Out-Null
    Assert-Equal @($script:RunMonitorFinalizationCalls).Count $beforeMissingContext 'A run without confirmed seed context must not finalize an unrelated monitor.'
}

function Invoke-QueueSnapshotHoldRowsRunnableCountCheck {
    $tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("MediaPipelineQueueHoldTest_" + [guid]::NewGuid().ToString('N'))
    try {
        New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null
        $sourcePath = Join-Path $tempRoot 'HeldMovie.mkv'
        Set-Content -LiteralPath $sourcePath -Value 'not real media' -Encoding UTF8
        $file = Get-Item -LiteralPath $sourcePath
        $plan = New-TestQueuePlan
        $plan.MovieCount = 1
        $plan.HoldCount = 1
        $plan.HoldEntries = @([pscustomobject]@{
            File                   = $file
            SourcePath             = [string]$file.FullName
            RootPath               = [string]$tempRoot
            QueuePhase             = 'hold'
            MediaKind              = 'movie'
            IsTV                   = $false
            IsPriority             = $false
            PriorityInfo           = [pscustomobject]@{ Reasons = @(); PriorityOrderTicks = 0L }
            PriorityOrderTicks     = 0L
            EffectivePriorityLevel = 'hold'
            QueueIndex             = 0
            QueueTotal             = 0
            SortName               = 'HeldMovie'
            ShowSortKey            = 'HeldMovie'
            SeasonSortOrder        = 0
            SeasonSortKey          = ''
            EpisodeSortOrder       = 0
            RelativePathSort       = 'HeldMovie.mkv'
            LibraryId              = ''
            LibraryName            = ''
            LibraryDesignation     = ''
            LibraryOutputRoot      = ''
            LastWriteUtc           = $file.LastWriteTimeUtc
            Metadata               = @{}
        })

        $script:configPath = ''
        $script:LocalBase = $tempRoot
        $script:SourceMovies = $tempRoot
        $script:SourceTV = ''
        $script:Outsource = ''
        $snapshot = Build-QueuePlanSnapshotRows -QueuePlan $plan -ProcessedIndex @{}
        Assert-Equal $snapshot.runnable_count 0 'Hold-only snapshots must not report runnable work.'
        Assert-Equal ([int]$snapshot.rows.Count) 1 'Hold rows should remain visible for operator review.'
        Assert-Equal $snapshot.rows[0]['blocked_reason_code'] 'hold' 'Hold rows should be marked blocked by hold policy.'
    } finally {
        if (Test-Path -LiteralPath $tempRoot -ErrorAction SilentlyContinue) {
            Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}

function Invoke-PerFileUnexpectedExceptionContinuesSerialQueueCheck {
    $tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("MediaPipelineQueueUnexpectedItemTest_" + [guid]::NewGuid().ToString('N'))
    try {
        New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null
        $boom = New-QueueEngineTestEntry -Root $tempRoot -Name 'Boom.mkv' -Phase 'movie' -MediaKind 'movie' -PriorityLevel 'normal' -QueueIndex 1 -QueueTotal 2
        $after = New-QueueEngineTestEntry -Root $tempRoot -Name 'After.mkv' -Phase 'movie' -MediaKind 'movie' -PriorityLevel 'normal' -QueueIndex 2 -QueueTotal 2
        $plan = New-TestQueuePlan
        $plan.NormalMovieEntries = @($boom, $after)
        $plan.MovieCount = 2
        $script:StopRequested = $false
        $script:ProcessFileCalls = @()
        $script:ProcessFileThrowNames = @('Boom.mkv')
        $script:UnexpectedQueueEntryFailures = 0
        $script:totalFailed = 0
        $script:SourceFailures = @()
        $script:PipelineEvents = @()

        function Register-SourceFailure {
            param(
                $SourceFile,
                [string] $Classification,
                [string] $Reason,
                [string] $Stage,
                [string] $ErrorCode,
                [string] $SuggestedAction
            )
            $script:SourceFailures += ,([pscustomobject]@{
                Source = [string]$SourceFile.FullName
                Classification = $Classification
                Reason = $Reason
                Stage = $Stage
                ErrorCode = $ErrorCode
                SuggestedAction = $SuggestedAction
            })
        }
        function Write-PipelineEvent {
            param(
                [string] $EventType,
                [string] $Stage,
                [string] $Status,
                [string] $SourcePath,
                [hashtable] $Data
            )
            $script:PipelineEvents += ,([pscustomobject]@{
                EventType = $EventType
                Stage     = $Stage
                Status    = $Status
                SourcePath = $SourcePath
                Data      = $Data
            })
        }

        $result = @(Invoke-MediaQueuePhasePlan -QueuePlan $plan -ProcessedIndex @{})
        $phaseResult = $result[-1]
        Assert-Equal ([int]$script:ProcessFileCalls.Count) 2 'Unexpected per-file exception should not stop later serial queue entries in continuous mode.'
        Assert-Equal ([string]$script:ProcessFileCalls[1].Name) 'After.mkv' 'Serial queue should continue with the entry after an unexpected per-file exception.'
        Assert-Equal ([int]$script:UnexpectedQueueEntryFailures) 1 'Unexpected per-file exception should increment the unexpected item counter.'
        Assert-Equal ([int]$script:totalFailed) 1 'Unexpected per-file exception should increment the failure counter.'
        Assert-Equal ([int]$phaseResult.UnexpectedFailures) 1 'Phase result should expose unexpected item failures.'
        Assert-Equal ([string]$script:SourceFailures[0].ErrorCode) 'UNEXPECTED_PIPELINE_EXCEPTION' 'Unexpected per-file exception should record source failure evidence.'
        Assert-Equal ([string]$script:PipelineEvents[0].EventType) 'queue_item_unexpected_failure' 'Unexpected per-file exception should emit a structured event.'

        $script:ProcessFileCalls = @()
        $script:UnexpectedQueueEntryFailures = 0
        $script:totalFailed = 0
        $onceFailed = $false
        try {
            Invoke-MediaQueuePhasePlan -QueuePlan $plan -ProcessedIndex @{} -StopOnUnexpectedFailure | Out-Null
        } catch {
            $onceFailed = ([string]$_ -match 'synthetic process failure')
        }
        Assert-True $onceFailed 'StopOnUnexpectedFailure should make the serial queue terminal for once/single-pass behavior.'
        Assert-Equal ([int]$script:ProcessFileCalls.Count) 1 'Terminal per-file exception should not process later queue entries.'
    } finally {
        $script:ProcessFileThrowNames = @()
        Remove-Item Function:\Register-SourceFailure -ErrorAction SilentlyContinue
        Remove-Item Function:\Write-PipelineEvent -ErrorAction SilentlyContinue
        if (Test-Path -LiteralPath $tempRoot -ErrorAction SilentlyContinue) {
            Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}

function Invoke-StopAfterCurrentFinishesCurrentSerialItemCheck {
    $tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("MediaPipelineQueueStopAfterCurrentTest_" + [guid]::NewGuid().ToString('N'))
    try {
        New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null
        $current = New-QueueEngineTestEntry -Root $tempRoot -Name 'Current.mkv' -QueueIndex 1 -QueueTotal 2
        $next = New-QueueEngineTestEntry -Root $tempRoot -Name 'Next.mkv' -QueueIndex 2 -QueueTotal 2
        $plan = New-TestQueuePlan
        $plan.NormalMovieEntries = @($current, $next)
        $plan.MovieCount = 2
        $script:StopRequested = $false
        $script:ProcessFileCalls = @()
        $script:ProcessFileThrowNames = @()
        $script:UnexpectedQueueEntryFailures = 0
        $script:StopAfterCurrentBoundaryRequested = $true
        $script:StopAfterCurrentBoundaryAfterDispatchCount = 1

        $result = @(Invoke-MediaQueuePhasePlan -QueuePlan $plan -ProcessedIndex @{})[-1]

        Assert-Equal @($script:ProcessFileCalls).Count 1 'Stop After Current must allow the current serial item to finish and suppress the next dispatch.'
        Assert-Equal ([string]$script:ProcessFileCalls[0].Name) 'Current.mkv' 'Stop After Current must not replace the current item.'
        Assert-True ([bool]$result.StoppedAfterCurrent) 'Phase result must distinguish graceful stop from immediate interruption.'
        Assert-True (-not [bool]$result.Stopped) 'Graceful stop must not set the immediate StopRequested state.'
        Assert-True (-not [bool]$script:StopRequested) 'Graceful stop must not enter native-process interruption state.'
    } finally {
        $script:StopAfterCurrentBoundaryRequested = $false
        $script:StopAfterCurrentBoundaryAfterDispatchCount = 0
        if (Test-Path -LiteralPath $tempRoot -ErrorAction SilentlyContinue) {
            Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}

Invoke-ManualOrderSortsHighPriorityBucketsCheck
Invoke-ExplicitManifestNormalSuppressesFilesystemPriorityCheck
Invoke-CorruptPriorityManifestFailsClosedCheck
Invoke-PriorityOnlyQueuePlanSelectsEffectiveHighEntriesCheck
Invoke-KananRevisionQueueSnapshotParseReuseCheck
Invoke-ActiveBadRenameCorpusQueueChecks
Assert-Equal (Get-QueueSeasonNumber 'Example.Show.S01E12') 1 'Queue fallback season parsing should recognize a canonical SxxEyy token without requiring a trailing separator.'
Assert-Equal (Get-QueueEpisodeNumber 'Example.Show.S01E100') 100 'Queue fallback ordering should accept a valid three-digit episode number.'
Assert-Equal (Get-QueueEpisodeNumber 'Example.Show.S01E1000') 0 'Queue fallback ordering must reject E1000 rather than truncate it to a smaller episode number.'
Invoke-GlobalRunnableQueueSnapshotMetadataCheck
Invoke-AcceptedRunSeedRequiresPlannedNameEvidenceCheck
Invoke-AcceptedRunUsesBackendRenameDisplayNameCheck
Invoke-QueuePlanFingerprintDimensionCheck
Invoke-AcceptedRunBlocksWhenBackendNamingEvidenceFailsCheck
Invoke-QueueSnapshotRowsAreCappedButTotalsRemainAccurateCheck
Invoke-AcceptedRunRowsMustMatchActiveEvidenceExactlyCheck
Invoke-QueueExecutionCapLimitsRunnableWindowCheck
Invoke-SerialQueueDispatchUsesGlobalRunnableMetadataCheck
Invoke-PendingPublishBackpressureBlocksBeforeExecutionCheck
Invoke-QueuePlanFingerprintGuardCheck
Invoke-RunMonitorFinalizationClassificationCheck
Invoke-QueueSnapshotHoldRowsRunnableCountCheck
Invoke-PerFileUnexpectedExceptionContinuesSerialQueueCheck
Invoke-StopAfterCurrentFinishesCurrentSerialItemCheck

function Build-QueuePlanSnapshotRows {
    param($QueuePlan, $ProcessedIndex)
    return [pscustomobject]@{
        schema_version = 'queue_plan_snapshot.v1'
        runnable_count = 0
        rows           = @()
    }
}
function Write-QueuePlanSnapshot {
    param($Plan, [string] $Path)
}
function Get-ProcessingStats { return 'stats ok' }
function Write-RoundFailureSummary { return $null }
function Invoke-PeriodicLocalEncodedDirectoryCleanup {
    $script:CleanupDispatchCount++
    return $null
}
function Write-Log {
    param([string] $Message, [string] $Level = 'INFO')
    $script:LogMessages += "$Level`:$Message"
}
function Invoke-MediaQueuePhasePlan {
    param($QueuePlan, $ProcessedIndex)
    $script:SerialDispatchCount++
    return [pscustomobject]@{ Stopped = $false }
}
function Invoke-MediaQueuePhasePlanLocalWorkerSlots {
    param(
        [Parameter(Mandatory)] $QueuePlan,
        [Parameter(Mandatory)] $ProcessedIndex,
        [Parameter(Mandatory)] [string] $ScriptPath,
        [Parameter(Mandatory)] [string] $ConfigPath,
        [Parameter(Mandatory)] [string] $PowerShellPath,
        [Parameter(Mandatory)] [int] $MaxParallelEncodes
    )
    $script:WorkerDispatchCount++
    $script:LastWorkerDispatch = [pscustomobject]@{
        ScriptPath         = $ScriptPath
        ConfigPath         = $ConfigPath
        PowerShellPath     = $PowerShellPath
        MaxParallelEncodes = $MaxParallelEncodes
    }
    return [pscustomobject]@{ Stopped = $false }
}

Reset-TestDispatchState
$singlePlan = New-MediaPipelineEnginePlan `
    -SourceMovies 'MoviesRoot' `
    -SourceTV 'TVRoot' `
    -QueueSnapshotPath 'snapshot.json' `
    -Once:$true `
    -SleepSeconds 5
$singleRound = Invoke-MediaPipelineRound -EnginePlan $singlePlan
Assert-True ([bool]$singleRound.Completed) 'Single-mode round should complete.'
Assert-Equal $singlePlan.ParallelEncodeMode 'single' 'Default parallel mode mismatch.'
Assert-Equal $singlePlan.MaxParallelEncodes 1 'Default max parallel encodes mismatch.'
Assert-Equal $script:SerialDispatchCount 1 'Default mode should dispatch through the serial queue phase.'
Assert-Equal $script:WorkerDispatchCount 0 'Default mode should not dispatch through local worker slots.'
Assert-Equal $script:CleanupDispatchCount 1 'Completed single-mode round should invoke periodic local encoded cleanup once.'

Reset-TestDispatchState
$oneSlotPlan = New-MediaPipelineEnginePlan `
    -SourceMovies 'MoviesRoot' `
    -SourceTV 'TVRoot' `
    -QueueSnapshotPath 'snapshot.json' `
    -Once:$true `
    -SleepSeconds 5 `
    -ScriptPath 'C:\Repo\ops\pipeline\entrypoints\MediaPipeline.ps1' `
    -ConfigPath 'C:\Repo\ops\pipeline\config\MediaPipeline_config.psd1' `
    -PowerShellPath 'C:\Program Files\PowerShell\7\pwsh.exe' `
    -ParallelEncodeMode 'local_worker_slots' `
    -MaxParallelEncodes 1
$oneSlotRound = Invoke-MediaPipelineRound -EnginePlan $oneSlotPlan
Assert-True ([bool]$oneSlotRound.Completed) 'One-slot local-worker config should complete.'
Assert-Equal $script:SerialDispatchCount 1 'One-slot local-worker config should remain serial.'
Assert-Equal $script:WorkerDispatchCount 0 'One-slot local-worker config should not invoke the worker scheduler.'
Assert-Equal $script:CleanupDispatchCount 1 'Completed one-slot round should invoke periodic local encoded cleanup once.'

Reset-TestDispatchState
$workerPlan = New-MediaPipelineEnginePlan `
    -SourceMovies 'MoviesRoot' `
    -SourceTV 'TVRoot' `
    -QueueSnapshotPath 'snapshot.json' `
    -Once:$true `
    -SleepSeconds 5 `
    -ScriptPath 'C:\Repo\ops\pipeline\entrypoints\MediaPipeline.ps1' `
    -ConfigPath 'C:\Repo\ops\pipeline\config\MediaPipeline_config.psd1' `
    -PowerShellPath 'C:\Program Files\PowerShell\7\pwsh.exe' `
    -ParallelEncodeMode 'local_worker_slots' `
    -MaxParallelEncodes 2
$workerRound = Invoke-MediaPipelineRound -EnginePlan $workerPlan
Assert-True ([bool]$workerRound.Completed) 'Worker-slot round should complete.'
Assert-Equal $script:SerialDispatchCount 0 'Worker-slot mode should not dispatch through the serial queue phase.'
Assert-Equal $script:WorkerDispatchCount 1 'Worker-slot mode should dispatch through the worker-slot scheduler.'
Assert-Equal $script:LastWorkerDispatch.ScriptPath 'C:\Repo\ops\pipeline\entrypoints\MediaPipeline.ps1' 'Worker scheduler script path mismatch.'
Assert-Equal $script:LastWorkerDispatch.ConfigPath 'C:\Repo\ops\pipeline\config\MediaPipeline_config.psd1' 'Worker scheduler config path mismatch.'
Assert-Equal $script:LastWorkerDispatch.PowerShellPath 'C:\Program Files\PowerShell\7\pwsh.exe' 'Worker scheduler PowerShell path mismatch.'
Assert-Equal $script:LastWorkerDispatch.MaxParallelEncodes 2 'Worker scheduler max parallel encodes mismatch.'
Assert-Equal $script:CleanupDispatchCount 1 'Completed worker-slot round should invoke periodic local encoded cleanup once.'

Reset-TestDispatchState
$missingContextPlan = New-MediaPipelineEnginePlan `
    -SourceMovies 'MoviesRoot' `
    -SourceTV 'TVRoot' `
    -QueueSnapshotPath 'snapshot.json' `
    -Once:$true `
    -SleepSeconds 5 `
    -ParallelEncodeMode 'local_worker_slots' `
    -MaxParallelEncodes 2
$missingContextFailed = $false
try {
    Invoke-MediaPipelineRound -EnginePlan $missingContextPlan | Out-Null
} catch {
    $missingContextFailed = ([string]$_ -match 'pipeline script path')
}
Assert-True $missingContextFailed 'Worker-slot mode should fail fast when the pipeline script path is missing.'
Assert-Equal $script:SerialDispatchCount 0 'Missing worker context should not fall back to serial dispatch.'
Assert-Equal $script:WorkerDispatchCount 0 'Missing worker context should not call the worker scheduler.'
Assert-Equal $script:CleanupDispatchCount 0 'Failed worker context validation should not invoke periodic local encoded cleanup.'

function Invoke-PerRoundUnexpectedExceptionContinuousRetryCheck {
    $script:RoundCalls = 0
    $script:RoundMode = 'continuous'
    $script:StopRequested = $false
    $script:PipelineEvents = @()
    $script:BackoffSeconds = @()
    $script:LogMessages = @()
    $script:ProgressStages = @()
    $script:RoundFailuresBeforeSuccess = 1
    $script:ConsecutiveRoundFailureBlockLimit = 12
    $script:ConsecutiveRoundFailureProbeBackoffSeconds = 900
    $script:PipelineBlockedExitCode = 0
    $script:PipelineStopReason = ''

    function Invoke-MediaPipelineRound {
        param($EnginePlan)
        $script:RoundCalls++
        if ($script:RoundMode -eq 'once' -or $script:RoundCalls -le [int]$script:RoundFailuresBeforeSuccess) {
            throw 'synthetic round failure'
        }
        $script:StopRequested = $true
        return [pscustomobject]@{ Completed = $true; StopRequested = $false }
    }
    function Write-PipelineEvent {
        param(
            [string] $EventType,
            [string] $Stage,
            [string] $Status,
            [hashtable] $Data
        )
        $script:PipelineEvents += ,([pscustomobject]@{
            EventType = $EventType
            Stage     = $Stage
            Status    = $Status
            Data      = $Data
        })
    }
    function Set-ProgressStage {
        param(
            [string] $Stage,
            [string] $Status,
            $Percent,
            $Route,
            $CopyState,
            $PushState,
            $SidecarState,
            [switch] $SaveNow
        )
        $script:ProgressStages += ,([pscustomobject]@{ Stage = $Stage; Status = $Status })
    }
    function Start-StopAwareSleep {
        param([int] $Seconds)
        $script:BackoffSeconds += $Seconds
        return $true
    }

    $continuousPlan = New-MediaPipelineEnginePlan `
        -SourceMovies 'MoviesRoot' `
        -SourceTV 'TVRoot' `
        -QueueSnapshotPath 'snapshot.json' `
        -Once:$false `
        -SleepSeconds 5
    $continuousResult = Invoke-MediaPipelineRun -EnginePlan $continuousPlan

    Assert-Equal ([int]$script:RoundCalls) 2 'Continuous mode should retry the round after an unexpected round exception.'
    Assert-Equal ([int]$continuousResult.RoundsCompleted) 1 'Continuous mode should count the successful retry round.'
    Assert-Equal ([int]$continuousResult.UnexpectedRoundFailures) 1 'Continuous mode should report the unexpected round failure count.'
    Assert-Equal ([int]$script:BackoffSeconds[0]) 30 'Continuous mode should use bounded backoff after the first unexpected round exception.'
    Assert-Equal ([string]$script:PipelineEvents[0].EventType) 'pipeline_round_unexpected_failure' 'Unexpected round exception should emit structured event evidence.'
    Assert-Equal ([int]$script:PipelineEvents[0].Data.failure_count) 1 'Unexpected round event should include the failure count.'
    Assert-Equal ([string]$script:PipelineEvents[0].Status) 'failed' 'First unexpected round event should be failed, not blocked.'

    $script:RoundCalls = 0
    $script:RoundMode = 'continuous'
    $script:RoundFailuresBeforeSuccess = 2
    $script:StopRequested = $false
    $script:PipelineEvents = @()
    $script:BackoffSeconds = @()
    $script:ProgressStages = @()
    $script:ConsecutiveRoundFailureBlockLimit = 2
    $script:ConsecutiveRoundFailureProbeBackoffSeconds = 900
    $script:PipelineBlockedExitCode = 0
    $script:PipelineStopReason = ''
    $blockedPlan = New-MediaPipelineEnginePlan `
        -SourceMovies 'MoviesRoot' `
        -SourceTV 'TVRoot' `
        -QueueSnapshotPath 'snapshot.json' `
        -Once:$false `
        -SleepSeconds 5
    $blockedResult = Invoke-MediaPipelineRun -EnginePlan $blockedPlan

    Assert-Equal ([int]$script:RoundCalls) 2 'Continuous mode should stop at the block threshold instead of probing indefinitely.'
    Assert-Equal ([int]$blockedResult.RoundsCompleted) 0 'Blocked continuous mode should not count a recovery round after the terminal block.'
    Assert-Equal ([int]$blockedResult.UnexpectedRoundFailures) 2 'Blocked continuous mode should report both unexpected round failures.'
    Assert-Equal ([int]$script:BackoffSeconds[0]) 30 'First consecutive failure should use normal bounded retry backoff.'
    Assert-Equal ([int]@($script:BackoffSeconds).Count) 1 'Failure at the block threshold should not enter probe backoff.'
    Assert-Equal ([string]$script:PipelineEvents[1].Status) 'blocked' 'Failure at the block threshold should emit blocked event evidence.'
    Assert-True ([bool]$script:PipelineEvents[1].Data.blocked) 'Blocked event data should mark the threshold state.'
    Assert-Equal ([int]$script:PipelineEvents[1].Data.consecutive_failure_count) 2 'Blocked event should include the consecutive failure count.'
    Assert-Equal ([string]$script:PipelineEvents[2].EventType) 'pipeline_round_failure_blocked' 'Blocked threshold should emit a terminal blocked event.'
    Assert-Equal ([string]$script:ProgressStages[1].Stage) 'blocked' 'Failure at the block threshold should write blocked progress state.'
    Assert-Equal ([int]$script:PipelineBlockedExitCode) 76 'Blocked continuous mode should request blocked exit code 76.'
    Assert-Equal ([string]$script:PipelineStopReason) 'consecutive_round_failures_blocked' 'Blocked continuous mode should preserve stop reason.'
    Assert-Equal ([int]$script:ConsecutiveUnexpectedRoundFailures) 2 'Blocked continuous mode should preserve consecutive failure evidence.'
    Assert-True ([bool]$script:ContinuousRoundFailuresBlocked) 'Blocked continuous mode should keep blocked state until restart.'

    $script:RoundCalls = 0
    $script:RoundMode = 'once'
    $script:RoundFailuresBeforeSuccess = 999
    $script:StopRequested = $false
    $script:PipelineEvents = @()
    $script:BackoffSeconds = @()
    $oncePlan = New-MediaPipelineEnginePlan `
        -SourceMovies 'MoviesRoot' `
        -SourceTV 'TVRoot' `
        -QueueSnapshotPath 'snapshot.json' `
        -Once:$true `
        -SleepSeconds 5
    $onceFailed = $false
    try {
        Invoke-MediaPipelineRun -EnginePlan $oncePlan | Out-Null
    } catch {
        $onceFailed = ([string]$_ -match 'synthetic round failure')
    }
    Assert-True $onceFailed 'Once mode should remain terminal when a round cannot safely continue.'
    Assert-Equal ([int]$script:RoundCalls) 1 'Once mode should not retry a failed round.'
    Assert-Equal ([int]@($script:BackoffSeconds).Count) 0 'Once mode should not back off and retry after a failed round.'
    Assert-Equal ([string]$script:PipelineEvents[0].EventType) 'pipeline_round_unexpected_failure' 'Once round failure should still emit structured event evidence before terminating.'
}

Invoke-PerRoundUnexpectedExceptionContinuousRetryCheck

$mainScriptText = Get-Content -LiteralPath (Join-Path $pipelineRoot 'entrypoints\MediaPipeline.ps1') -Raw
$nativeScriptText = Get-Content -LiteralPath (Join-Path $pipelineRoot 'engine\shared\native.ps1') -Raw
$workerResultText = Get-Content -LiteralPath (Join-Path $repoRoot 'ops\pipeline\engine\process\worker_result.ps1') -Raw
Assert-True ($mainScriptText -match '\[string\]\$WorkerResultPath\s*=\s*""') 'Worker-child startup should expose WorkerResultPath.'
Assert-True ($mainScriptText -match 'function Write-MediaPipelineEarlyWorkerChildFailureResult') 'Worker-child startup should define an early result writer for config/bootstrap failures.'
Assert-True ($mainScriptText -match 'CONFIG_SCHEMA_INVALID') 'Config schema failures should write a structured worker-child result.'
Assert-True ($mainScriptText -match '(?i)worker_result\.ps1') 'Main script should load the worker-child result writer module.'
Assert-True ($mainScriptText -match 'AllowSubtitleHelperFallback') 'ASS helper self-check should be gated by AllowSubtitleHelperFallback.'
Assert-True ($mainScriptText -match 'Subtitle helper self-check failed[\s\S]+exit 76') 'ASS helper self-check failure should block startup with exit code 76 when fallback is disabled.'
Assert-True ($mainScriptText -match 'Invoke-PythonToolCommand\s+-ArgumentList @\(\$assToSrtScript\)\s+-TimeoutSeconds 15\s+-Stage ''subtitle-helper-selfcheck''\s+-SuccessExitCodes @\(0, 2\)') 'ASS helper self-check should classify the intentional no-argument exit code as successful telemetry.'
Assert-True ($nativeScriptText -match 'SuccessExitCodes' -and $nativeScriptText -match '\$isExpectedExitCode' -and $nativeScriptText -match 'Status \$\(if \(\$isExpectedExitCode\) \{ ''succeeded'' \} else \{ ''failed'' \}\)') 'Native tool events should report configured expected exit codes as succeeded.'
Assert-True ($workerResultText -match 'function Write-MediaPipelineWorkerChildResult') 'Worker result module should define the worker-child result writer.'
Assert-True ($workerResultText -match 'if \(-not \$WorkerChild -or \[string\]::IsNullOrWhiteSpace\(\$WorkerResultPath\)\)') 'Worker result writer should require WorkerResultPath before writing child results.'
Assert-True ($workerResultText -match 'SchemaVersion\s+=\s+''local_worker_result\.v1''') 'Worker-child result should have a versioned schema.'
Assert-True ($mainScriptText -match 'Write-MediaPipelineWorkerChildResult[\s\S]{0,400}-Status ''failed''') 'Missing SingleFile path should write a failed worker result.'
Assert-True ($mainScriptText -match 'Write-MediaPipelineWorkerChildResult[\s\S]{0,400}-ProcessResult \$sfResult') 'SingleFile completion should write the process result for the parent scheduler.'
Assert-True ($mainScriptText -match 'catch\s*\{[\s\S]{0,1800}WORKER_CHILD_SINGLE_FILE_EXCEPTION') 'SingleFile worker-child exceptions should be converted to structured worker results.'
Assert-True ($mainScriptText -match 'finally\s*\{[\s\S]{0,2200}WORKER_CHILD_RESULT_FALLBACK') 'SingleFile worker-child finalization should write a fallback structured result if no result exists.'
Assert-True ($mainScriptText -match 'Test-Path -LiteralPath \$WorkerResultPath') 'SingleFile fallback should check for an existing worker result before writing.'
Assert-True ($mainScriptText -match 'PriorityOnly live execution requires Once') 'PriorityOnly entrypoint should reject continuous live execution.'
Assert-True ($mainScriptText -match 'PriorityOnly live execution requires ExpectedQueuePlanFingerprint') 'PriorityOnly entrypoint should require an exported plan fingerprint for live execution.'
Assert-True ($mainScriptText -match 'PriorityOnly cannot be combined with SingleFile') 'PriorityOnly entrypoint should reject SingleFile execution.'

function Invoke-PriorityOnlyEntrypointBoundaryCheck {
    $entrypoint = Join-Path $pipelineRoot 'entrypoints\MediaPipeline.ps1'
    $hostPath = (Get-Process -Id $PID).Path
    $cases = @(
        @{ Args = @('-PriorityOnly'); Expected = 'requires Once' },
        @{ Args = @('-PriorityOnly', '-Once'); Expected = 'requires ExpectedQueuePlanFingerprint' },
        @{ Args = @('-PriorityOnly', '-Once', '-ExpectedQueuePlanFingerprint', 'test-fingerprint', '-SingleFile', 'C:\Media\One.mkv'); Expected = 'cannot be combined with SingleFile' }
    )
    foreach ($case in $cases) {
        $output = & $hostPath -NoProfile -NonInteractive -File $entrypoint @($case.Args) 2>&1
        $exitCode = $LASTEXITCODE
        $outputText = (@($output) | ForEach-Object { [string]$_ }) -join "`n"
        Assert-True ($exitCode -ne 0) "PriorityOnly invalid entrypoint combination should fail: $($case.Args -join ' ')"
        Assert-True ($outputText -match [regex]::Escape([string]$case.Expected)) "PriorityOnly failure should explain '$($case.Expected)'. Output: $outputText"
    }
}

Invoke-PriorityOnlyEntrypointBoundaryCheck

Write-Host 'Pipeline queue engine checks passed.'
