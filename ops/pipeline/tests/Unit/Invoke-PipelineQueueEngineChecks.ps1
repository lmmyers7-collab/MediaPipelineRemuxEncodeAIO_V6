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

. (Join-Path $repoRoot 'ops\pipeline\engine\queue\queue_plan.ps1')
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
}

function Check-ControlFlags {}
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
    return [pscustomobject]@{
        IsReliable = $true
        ShowName = 'Show'
        Season = 1
        Episode = 1
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

function Invoke-QueueSnapshotRowsAreCappedButTotalsRemainAccurateCheck {
    $tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("MediaPipelineQueueRowCapTest_" + [guid]::NewGuid().ToString('N'))
    $previousRowLimit = $script:QueueSnapshotRowLimit
    try {
        New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null
        $script:QueueSnapshotRowLimit = 5
        $entries = [System.Collections.ArrayList]::new()
        for ($index = 1; $index -le 8; $index++) {
            $entries.Add((New-QueueEngineSyntheticEntry -Root $tempRoot -Name ("Movie-{0:D3}.mkv" -f $index) -QueueIndex $index -QueueTotal 8)) | Out-Null
        }
        $plan = New-TestQueuePlan
        $plan.NormalMovieEntries = $entries.ToArray()
        $plan.MovieCount = 8
        $script:configPath = ''
        $script:LocalBase = $tempRoot
        $script:SourceMovies = $tempRoot
        $script:SourceTV = $tempRoot
        $script:Outsource = ''
        $script:ValidExtensions = @('.mkv')

        $snapshot = Build-QueuePlanSnapshotRows -QueuePlan $plan -ProcessedIndex @{}

        Assert-Equal $snapshot.runnable_count 8 'Snapshot runnable_count must preserve the full runnable total.'
        Assert-Equal $snapshot.total_row_count 8 'Snapshot total_row_count must preserve the full display candidate total.'
        Assert-Equal $snapshot.shown_row_count 5 'Snapshot should cap displayed rows at the row limit.'
        Assert-Equal $snapshot.row_limit 5 'Snapshot row_limit should expose the display cap.'
        Assert-True ([bool]$snapshot.rows_truncated) 'Snapshot should mark rows_truncated when display rows are capped.'
        Assert-Equal ([int]$snapshot.rows.Count) 5 'Snapshot rows payload should be capped.'
        Assert-Equal ([int]$snapshot.rows[0]['run_queue_total']) 8 'Visible runnable rows must retain the full run_queue_total.'
        Assert-Equal ([int]$plan.NormalMovieEntries[7].RunQueueTotal) 8 'Non-visible entries must still receive the full RunQueueTotal for execution.'
    } finally {
        $script:QueueSnapshotRowLimit = $previousRowLimit
        if (Test-Path -LiteralPath $tempRoot -ErrorAction SilentlyContinue) {
            Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
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

function Invoke-PendingPublishBackpressureSkipsDiscoveryCheck {
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
            throw 'processed index should not be read while pending backpressure blocks discovery'
        }
        function Get-MediaQueueDiscoveryPlan {
            $script:DiscoveryCalls++
            throw 'source discovery should not run while pending backpressure blocks discovery'
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
        Assert-Equal ([int]$script:DiscoveryCalls) 0 'Backpressure should skip source discovery.'
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

Invoke-ManualOrderSortsHighPriorityBucketsCheck
Invoke-ExplicitManifestNormalSuppressesFilesystemPriorityCheck
Invoke-CorruptPriorityManifestFailsClosedCheck
Invoke-GlobalRunnableQueueSnapshotMetadataCheck
Invoke-QueueSnapshotRowsAreCappedButTotalsRemainAccurateCheck
Invoke-QueueExecutionCapLimitsRunnableWindowCheck
Invoke-SerialQueueDispatchUsesGlobalRunnableMetadataCheck
Invoke-PendingPublishBackpressureSkipsDiscoveryCheck
Invoke-QueueSnapshotHoldRowsRunnableCountCheck
Invoke-PerFileUnexpectedExceptionContinuesSerialQueueCheck

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

Write-Host 'Pipeline queue engine checks passed.'
