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
$repoRoot = Split-Path -Parent $pipelineRoot

. (Join-Path $repoRoot 'engine\queue\pipeline_engine.ps1')

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
    -ScriptPath 'C:\Repo\Pipeline\MediaPipeline.ps1' `
    -ConfigPath 'C:\Repo\Pipeline\MediaPipeline_config.psd1' `
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
    -ScriptPath 'C:\Repo\Pipeline\MediaPipeline.ps1' `
    -ConfigPath 'C:\Repo\Pipeline\MediaPipeline_config.psd1' `
    -PowerShellPath 'C:\Program Files\PowerShell\7\pwsh.exe' `
    -ParallelEncodeMode 'local_worker_slots' `
    -MaxParallelEncodes 2
$workerRound = Invoke-MediaPipelineRound -EnginePlan $workerPlan
Assert-True ([bool]$workerRound.Completed) 'Worker-slot round should complete.'
Assert-Equal $script:SerialDispatchCount 0 'Worker-slot mode should not dispatch through the serial queue phase.'
Assert-Equal $script:WorkerDispatchCount 1 'Worker-slot mode should dispatch through the worker-slot scheduler.'
Assert-Equal $script:LastWorkerDispatch.ScriptPath 'C:\Repo\Pipeline\MediaPipeline.ps1' 'Worker scheduler script path mismatch.'
Assert-Equal $script:LastWorkerDispatch.ConfigPath 'C:\Repo\Pipeline\MediaPipeline_config.psd1' 'Worker scheduler config path mismatch.'
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

$mainScriptText = Get-Content -LiteralPath (Join-Path $pipelineRoot 'MediaPipeline.ps1') -Raw
Assert-True ($mainScriptText -match 'if \(\$WorkerChild\)[\s\S]{0,1200}\$WorkerResultPath') 'Worker-child startup should require WorkerResultPath.'
Assert-True ($mainScriptText -match 'function Write-MediaPipelineWorkerChildResult') 'Main script should define the worker-child result writer.'
Assert-True ($mainScriptText -match 'SchemaVersion\s+=\s+''local_worker_result\.v1''') 'Worker-child result should have a versioned schema.'
Assert-True ($mainScriptText -match 'Write-MediaPipelineWorkerChildResult[\s\S]{0,400}-Status ''failed''') 'Missing SingleFile path should write a failed worker result.'
Assert-True ($mainScriptText -match 'Write-MediaPipelineWorkerChildResult[\s\S]{0,400}-ProcessResult \$sfResult') 'SingleFile completion should write the process result for the parent scheduler.'

Write-Host 'Pipeline queue engine checks passed.'
