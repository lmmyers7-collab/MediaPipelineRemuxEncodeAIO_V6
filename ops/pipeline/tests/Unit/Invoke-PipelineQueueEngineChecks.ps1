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
    param($File)
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

Invoke-ManualOrderSortsHighPriorityBucketsCheck
Invoke-ExplicitManifestNormalSuppressesFilesystemPriorityCheck
Invoke-GlobalRunnableQueueSnapshotMetadataCheck
Invoke-SerialQueueDispatchUsesGlobalRunnableMetadataCheck
Invoke-QueueSnapshotHoldRowsRunnableCountCheck

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

$mainScriptText = Get-Content -LiteralPath (Join-Path $pipelineRoot 'entrypoints\MediaPipeline.ps1') -Raw
$workerResultText = Get-Content -LiteralPath (Join-Path $repoRoot 'ops\pipeline\engine\process\worker_result.ps1') -Raw
Assert-True ($mainScriptText -match '\[string\]\$WorkerResultPath\s*=\s*""') 'Worker-child startup should expose WorkerResultPath.'
Assert-True ($mainScriptText -match 'function Write-MediaPipelineEarlyWorkerChildFailureResult') 'Worker-child startup should define an early result writer for config/bootstrap failures.'
Assert-True ($mainScriptText -match 'CONFIG_SCHEMA_INVALID') 'Config schema failures should write a structured worker-child result.'
Assert-True ($mainScriptText -match '(?i)worker_result\.ps1') 'Main script should load the worker-child result writer module.'
Assert-True ($workerResultText -match 'function Write-MediaPipelineWorkerChildResult') 'Worker result module should define the worker-child result writer.'
Assert-True ($workerResultText -match 'if \(-not \$WorkerChild -or \[string\]::IsNullOrWhiteSpace\(\$WorkerResultPath\)\)') 'Worker result writer should require WorkerResultPath before writing child results.'
Assert-True ($workerResultText -match 'SchemaVersion\s+=\s+''local_worker_result\.v1''') 'Worker-child result should have a versioned schema.'
Assert-True ($mainScriptText -match 'Write-MediaPipelineWorkerChildResult[\s\S]{0,400}-Status ''failed''') 'Missing SingleFile path should write a failed worker result.'
Assert-True ($mainScriptText -match 'Write-MediaPipelineWorkerChildResult[\s\S]{0,400}-ProcessResult \$sfResult') 'SingleFile completion should write the process result for the parent scheduler.'
Assert-True ($mainScriptText -match 'catch\s*\{[\s\S]{0,1800}WORKER_CHILD_SINGLE_FILE_EXCEPTION') 'SingleFile worker-child exceptions should be converted to structured worker results.'
Assert-True ($mainScriptText -match 'finally\s*\{[\s\S]{0,2200}WORKER_CHILD_RESULT_FALLBACK') 'SingleFile worker-child finalization should write a fallback structured result if no result exists.'
Assert-True ($mainScriptText -match 'Test-Path -LiteralPath \$WorkerResultPath') 'SingleFile fallback should check for an existing worker result before writing.'

Write-Host 'Pipeline queue engine checks passed.'
