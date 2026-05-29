# ==============================================================================
# engine\storage\state_store.ps1
# ==============================================================================
# Versioned local state layout. The pipeline now keeps operational state under
# LocalBase\State while preserving compatibility with legacy files directly
# under LocalBase.
# ==============================================================================

function Write-MediaPipelineStateStoreLog {
    param(
        [Parameter(Mandatory)] [string] $Message,
        [ValidateSet('DEBUG','INFO','WARN','ERROR')] [string] $Level = 'DEBUG'
    )

    if (Get-Command Write-Log -ErrorAction SilentlyContinue) {
        Write-Log $Message $Level
    } elseif ($Level -in @('WARN','ERROR')) {
        Write-Warning $Message
    } else {
        Write-Verbose $Message
    }
}

function New-MediaPipelineStateLayout {
    param([Parameter(Mandatory)] [string] $LocalBase)

    if ([string]::IsNullOrWhiteSpace($LocalBase)) {
        throw 'LocalBase is required to build the media pipeline state layout.'
    }

    $stateRoot = Join-Path $LocalBase 'State'
    $app = Join-Path $stateRoot 'App'
    $pipeline = Join-Path $stateRoot 'Pipeline'
    $progress = Join-Path $stateRoot 'Progress'
    $activeJobs = Join-Path $stateRoot 'ActiveJobs'
    $workers = Join-Path $stateRoot 'Workers'
    $completed = Join-Path $stateRoot 'Completed'
    $failures = Join-Path $stateRoot 'Failures'
    $pendingPush = Join-Path $stateRoot 'PendingServerPush'

    [pscustomobject]@{
        SchemaVersion    = 'media_pipeline_state_layout.v1'
        Root             = $stateRoot
        App              = $app
        Pipeline         = $pipeline
        Progress         = $progress
        ActiveJobs       = $activeJobs
        Workers          = $workers
        Completed        = $completed
        Failures         = $failures
        FailureArtifacts = Join-Path $failures 'Artifacts'
        FailureMarkers   = Join-Path $failures 'Markers'
        FailureReports   = Join-Path $failures 'Reports'
        PendingPush      = $pendingPush
        Paths            = [pscustomobject]@{
            ProgressFile         = Join-Path $progress 'pipeline_progress.json'
            PipelineEventLogFile = Join-Path $progress 'pipeline_events.jsonl'
            QueueSnapshot        = Join-Path $progress 'queue_snapshot.json'
            LocalWorkerClaims     = Join-Path $pipeline 'local_worker_claims.json'
            LocalWorkerActiveJobs = Join-Path $progress 'active_jobs.json'
            PauseFlag            = Join-Path $pipeline 'pipeline_pause.flag'
            StopFlag             = Join-Path $pipeline 'pipeline_stop.flag'
            RescanFlag           = Join-Path $pipeline 'pipeline_rescan.flag'
            CompletedJobsManifest = Join-Path $completed 'completed_jobs.jsonl'
            # Non-destructive priority manifest — written by the DesktopApp API,
            # read at queue-build time each pipeline round.
            PriorityManifest     = Join-Path $stateRoot 'priority_manifest.json'
            # Queue ordering strategy override — written by the DesktopApp API,
            # read at queue-build time each pipeline round.
            QueueStrategy        = Join-Path $stateRoot 'queue_strategy.json'
            # Per-file à-la-carte processing overrides — written by the DesktopApp
            # API, read at per-file processing time each pipeline round.
            FileOverrides        = Join-Path $stateRoot 'file_overrides.json'
        }
        LegacyPaths      = [pscustomobject]@{
            ProgressDirectory    = Join-Path $LocalBase 'Progress'
            ProgressFile         = Join-Path $LocalBase 'pipeline_progress.json'
            PipelineEventLogFile = Join-Path $LocalBase 'pipeline_events.jsonl'
            QueueSnapshot        = Join-Path (Join-Path $LocalBase 'Progress') 'queue_snapshot.json'
            PauseFlag            = Join-Path $LocalBase 'pipeline_pause.flag'
            StopFlag             = Join-Path $LocalBase 'pipeline_stop.flag'
            RescanFlag           = Join-Path $LocalBase 'pipeline_rescan.flag'
            Completed            = Join-Path $LocalBase 'Completed'
            CompletedJobsManifest = Join-Path (Join-Path $LocalBase 'Completed') 'completed_jobs.jsonl'
            Failures             = Join-Path $LocalBase 'Failed'
            FailureArtifacts     = Join-Path (Join-Path $LocalBase 'Failed') 'Artifacts'
            FailureMarkers       = Join-Path (Join-Path $LocalBase 'Failed') 'Markers'
            FailureReports       = Join-Path (Join-Path $LocalBase 'Failed') 'Reports'
            PendingPush          = Join-Path $LocalBase 'PendingServerPush'
        }
    }
}

function Get-MediaPipelineStateDirectories {
    param([Parameter(Mandatory)] $Layout)

    return @(
        $Layout.Root,
        $Layout.App,
        $Layout.Pipeline,
        $Layout.Progress,
        $Layout.ActiveJobs,
        $Layout.Workers,
        $Layout.Completed,
        $Layout.Failures,
        $Layout.FailureArtifacts,
        $Layout.FailureMarkers,
        $Layout.FailureReports,
        $Layout.PendingPush
    )
}

function Move-MediaPipelineLegacyStateFile {
    param(
        [Parameter(Mandatory)] [string] $LegacyPath,
        [Parameter(Mandatory)] [string] $StatePath
    )

    if (-not (Test-Path -LiteralPath $LegacyPath -PathType Leaf)) { return }
    if (Test-Path -LiteralPath $StatePath) { return }

    try {
        $parent = Split-Path -Parent $StatePath
        if (-not (Test-Path -LiteralPath $parent)) {
            [System.IO.Directory]::CreateDirectory($parent) | Out-Null
        }
        Move-Item -LiteralPath $LegacyPath -Destination $StatePath -Force
        Write-MediaPipelineStateStoreLog "Migrated legacy state file to $StatePath"
    } catch {
        Write-MediaPipelineStateStoreLog "Failed to migrate legacy state file $LegacyPath -> $StatePath : $_" 'WARN'
    }
}

function Move-MediaPipelineLegacyStateDirectory {
    param(
        [Parameter(Mandatory)] [string] $LegacyPath,
        [Parameter(Mandatory)] [string] $StatePath
    )

    if (-not (Test-Path -LiteralPath $LegacyPath -PathType Container)) { return }

    try {
        $parent = Split-Path -Parent $StatePath
        if (-not (Test-Path -LiteralPath $parent)) {
            [System.IO.Directory]::CreateDirectory($parent) | Out-Null
        }

        if (-not (Test-Path -LiteralPath $StatePath)) {
            Move-Item -LiteralPath $LegacyPath -Destination $StatePath -Force
            Write-MediaPipelineStateStoreLog "Migrated legacy state directory to $StatePath"
            return
        }

        foreach ($item in @(Get-ChildItem -LiteralPath $LegacyPath -Force -ErrorAction SilentlyContinue)) {
            $destination = Join-Path $StatePath $item.Name
            if (Test-Path -LiteralPath $destination) {
                Write-MediaPipelineStateStoreLog "Skipped legacy state item with existing destination: $destination" 'WARN'
                continue
            }
            Move-Item -LiteralPath $item.FullName -Destination $destination -Force
        }

        $remaining = @(Get-ChildItem -LiteralPath $LegacyPath -Force -ErrorAction SilentlyContinue)
        if ($remaining.Count -eq 0) {
            Remove-Item -LiteralPath $LegacyPath -Force -ErrorAction SilentlyContinue
        }
    } catch {
        Write-MediaPipelineStateStoreLog "Failed to migrate legacy state directory $LegacyPath -> $StatePath : $_" 'WARN'
    }
}

function Initialize-MediaPipelineStateLayout {
    param(
        [Parameter(Mandatory)] $Layout,
        [switch] $MigrateLegacy
    )

    if (-not (Test-Path -LiteralPath $Layout.Root)) {
        [System.IO.Directory]::CreateDirectory([string]$Layout.Root) | Out-Null
    }

    if ($MigrateLegacy) {
        Move-MediaPipelineLegacyStateDirectory -LegacyPath $Layout.LegacyPaths.ProgressDirectory -StatePath $Layout.Progress
        Move-MediaPipelineLegacyStateDirectory -LegacyPath $Layout.LegacyPaths.Completed -StatePath $Layout.Completed
        Move-MediaPipelineLegacyStateDirectory -LegacyPath $Layout.LegacyPaths.Failures -StatePath $Layout.Failures
        Move-MediaPipelineLegacyStateDirectory -LegacyPath $Layout.LegacyPaths.PendingPush -StatePath $Layout.PendingPush
        Move-MediaPipelineLegacyStateFile -LegacyPath $Layout.LegacyPaths.ProgressFile -StatePath $Layout.Paths.ProgressFile
        Move-MediaPipelineLegacyStateFile -LegacyPath $Layout.LegacyPaths.PipelineEventLogFile -StatePath $Layout.Paths.PipelineEventLogFile
        Move-MediaPipelineLegacyStateFile -LegacyPath $Layout.LegacyPaths.PauseFlag -StatePath $Layout.Paths.PauseFlag
        Move-MediaPipelineLegacyStateFile -LegacyPath $Layout.LegacyPaths.StopFlag -StatePath $Layout.Paths.StopFlag
        Move-MediaPipelineLegacyStateFile -LegacyPath $Layout.LegacyPaths.RescanFlag -StatePath $Layout.Paths.RescanFlag
    }

    foreach ($dir in @(Get-MediaPipelineStateDirectories -Layout $Layout)) {
        if (-not (Test-Path -LiteralPath $dir)) {
            [System.IO.Directory]::CreateDirectory([string]$dir) | Out-Null
        }
    }

    return $Layout
}
