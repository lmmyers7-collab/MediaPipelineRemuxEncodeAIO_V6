# ==============================================================================
# ops\pipeline\engine\queue\worker_progress.ps1
# ==============================================================================
# Extracted from ops\pipeline\engine\queue\local_worker_slots.ps1. Keep function names
# stable; local_worker_slots.ps1 dot-sources this file for compatibility.
# ==============================================================================

function Get-MediaPipelineQueueEntryRunValue {
    param(
        [Parameter(Mandatory)] $Entry,
        [Parameter(Mandatory)] [string] $RunProperty,
        [Parameter(Mandatory)] [string] $BucketProperty
    )

    $runValue = $null
    try {
        $runPropertyValue = $Entry.PSObject.Properties[$RunProperty]
        if ($runPropertyValue) { $runValue = [int]$runPropertyValue.Value }
    } catch {}
    if ($runValue -gt 0) { return [int]$runValue }

    try {
        $bucketPropertyValue = $Entry.PSObject.Properties[$BucketProperty]
        if ($bucketPropertyValue) { return [int]$bucketPropertyValue.Value }
    } catch {}
    return 0
}

if (-not (Get-Command -Name Get-MediaPipelineQueuePlanRunnableEntries -ErrorAction SilentlyContinue)) {
function Get-MediaPipelineQueuePlanRunnableEntries {
    param([Parameter(Mandatory)] $QueuePlan)

    $entries = [System.Collections.Generic.List[object]]::new()
    $highMovies = @($QueuePlan.HighPriorityMovieEntries | Where-Object { $null -ne $_ -and $null -ne $_.File })
    $highTV = @($QueuePlan.HighPriorityTVEntries | Where-Object { $null -ne $_ -and $null -ne $_.File })
    if ($highMovies.Count -eq 0 -and $highTV.Count -eq 0 -and $QueuePlan.PriorityEntries) {
        $legacyPriorityEntries = @($QueuePlan.PriorityEntries)
        $highMovies = @($legacyPriorityEntries | Where-Object { -not [bool]$_.IsTV })
        $highTV = @($legacyPriorityEntries | Where-Object { [bool]$_.IsTV })
    }

    $phaseSets = @()
    if ($QueuePlan.MixPriorityPhase -and ($highMovies.Count + $highTV.Count) -gt 0) {
        $phaseSets += ,@('priority', @(@($highMovies) + @($highTV)))
    } else {
        $phaseSets += ,@('priority_movie', $highMovies)
        $phaseSets += ,@('priority_tv', $highTV)
    }
    $phaseSets += ,@('movie', @($QueuePlan.NormalMovieEntries | Where-Object { $null -ne $_ -and $null -ne $_.File }))
    $phaseSets += ,@('tv', @($QueuePlan.NormalTVEntries | Where-Object { $null -ne $_ -and $null -ne $_.File }))
    $phaseSets += ,@('low', @($QueuePlan.LowEntries | Where-Object { $null -ne $_ -and $null -ne $_.File }))

    foreach ($phase in $phaseSets) {
        $phaseName = [string]$phase[0]
        foreach ($entry in @($phase[1])) {
            $entry | Add-Member -NotePropertyName LocalWorkerPhase -NotePropertyValue $phaseName -Force
            $entry | Add-Member -NotePropertyName RunQueuePhase -NotePropertyValue $phaseName -Force
            [void]$entries.Add($entry)
        }
    }
    return @($entries)
}
}

function Get-MediaPipelineWorkerProgressSnapshot {
    param([Parameter(Mandatory)] $SlotLayout)

    try {
        $payload = Read-MediaPipelineJsonFile -Path $SlotLayout.ProgressFile
        if ($payload) { return $payload }
    } catch {}
    return $null
}

function Write-MediaPipelineLocalWorkerActiveJobs {
    param(
        [Parameter(Mandatory)] [string] $ActiveJobsPath,
        [Parameter(Mandatory)] [string] $CompatibilityProgressPath,
        [Parameter(Mandatory)] [AllowEmptyCollection()] [array] $ActiveJobs,
        [switch] $WriteCompatibilityProgress
    )

    $jobs = [System.Collections.Generic.List[object]]::new()
    foreach ($job in @($ActiveJobs)) {
        $slot = $job.SlotLayout
        $claim = $job.Claim
        $progress = if ($slot) { Get-MediaPipelineWorkerProgressSnapshot -SlotLayout $slot } else { $null }
        $stage = if ($progress -and $progress.PSObject.Properties['CurrentStage']) { [string]$progress.CurrentStage } else { [string]$job.Status }
        $status = if ($progress -and $progress.PSObject.Properties['Status']) { [string]$progress.Status } else { [string]$job.Status }
        $route = if ($progress -and $progress.PSObject.Properties['CurrentRoute']) { [string]$progress.CurrentRoute } else { '' }
        $percent = if ($progress -and $progress.PSObject.Properties['CurrentStagePercent']) { $progress.CurrentStagePercent } else { $null }
        $libraryId = if ($progress -and $progress.PSObject.Properties['CurrentLibraryId']) { [string]$progress.CurrentLibraryId } else { '' }
        $libraryName = if ($progress -and $progress.PSObject.Properties['CurrentLibraryName']) { [string]$progress.CurrentLibraryName } else { '' }
        $libraryDesignation = if ($progress -and $progress.PSObject.Properties['CurrentLibraryDesignation']) { [string]$progress.CurrentLibraryDesignation } else { '' }
        $librarySourceRoot = if ($progress -and $progress.PSObject.Properties['CurrentLibrarySourceRoot']) { [string]$progress.CurrentLibrarySourceRoot } else { '' }
        $libraryOutputRoot = if ($progress -and $progress.PSObject.Properties['CurrentLibraryOutputRoot']) { [string]$progress.CurrentLibraryOutputRoot } else { '' }
        $fileName = if ($claim -and $claim.PSObject.Properties['source_name']) { [string]$claim.source_name } else { [System.IO.Path]::GetFileName([string]$claim.source_path) }
        [void]$jobs.Add([ordered]@{
            schema_version       = 'local_worker_active_job.v1'
            slot                 = [int]$slot.SlotId
            slot_number          = [int]$slot.SlotId
            claim_id             = [string]$claim.claim_id
            worker_pid           = if ($job.Process) { [int]$job.Process.Id } else { $null }
            source_path          = [string]$claim.source_path
            file_name            = $fileName
            media_kind           = [string]$claim.media_kind
            route_type           = $route
            stage                = $stage
            status               = $status
            percent              = $percent
            library_id           = $libraryId
            library_name         = $libraryName
            library_designation  = $libraryDesignation
            library_source_root  = $librarySourceRoot
            library_output_root  = $libraryOutputRoot
            eta                  = ''
            speed                = ''
            fps                  = ''
            ffmpeg_status        = $stage
            warnings             = @()
            failure_state        = if ($status -match 'fail|error') { $status } else { '' }
            queue_index          = [int]$claim.queue_index
            queue_total          = [int]$claim.queue_total
            progress_path        = [string]$slot.ProgressFile
            log_path             = [string]$slot.LogFile
            stdout_log           = [string]$slot.StdoutLog
            stderr_log           = [string]$slot.StderrLog
            updated_at           = Get-MediaPipelineLocalWorkerTimestamp
        })
    }

    $payload = [ordered]@{
        schema_version = 'local_worker_active_jobs.v1'
        updated_at     = Get-MediaPipelineLocalWorkerTimestamp
        job_count      = [int]$jobs.Count
        jobs           = @($jobs)
    }
    Write-MediaPipelineJsonAtomic -Path $ActiveJobsPath -InputObject $payload -Depth 8 | Out-Null

    if ($WriteCompatibilityProgress) {
        $first = if ($jobs.Count -gt 0) { $jobs[0] } else { $null }
        $compat = [ordered]@{
            ProgressVersion       = 2
            LastUpdate            = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
            SessionStartedAt      = if ($script:SessionStartedAt) { $script:SessionStartedAt.ToString('o') } else { Get-MediaPipelineLocalWorkerTimestamp }
            CurrentFile           = if ($first) { [string]$first.file_name } else { 'None' }
            CurrentFileDisplay    = if ($first) { "Slot $($first.slot): $($first.file_name)" } else { $null }
            CurrentFilePath       = if ($first) { [string]$first.source_path } else { $null }
            CurrentMediaType      = if ($first) { [string]$first.media_kind } else { $null }
            CurrentLibraryId      = if ($first) { [string]$first.library_id } else { $null }
            CurrentLibraryName    = if ($first) { [string]$first.library_name } else { $null }
            CurrentLibraryDesignation = if ($first) { [string]$first.library_designation } else { $null }
            CurrentLibrarySourceRoot  = if ($first) { [string]$first.library_source_root } else { $null }
            CurrentLibraryOutputRoot  = if ($first) { [string]$first.library_output_root } else { $null }
            CurrentQueuePhase     = if ($first) { 'local_worker_slots' } else { $null }
            CurrentQueueIndex     = if ($first) { [int]$first.queue_index } else { 0 }
            CurrentQueueTotal     = if ($first) { [int]$first.queue_total } else { 0 }
            CurrentRoute          = if ($first) { [string]$first.route_type } else { $null }
            CurrentStage          = if ($first) { [string]$first.stage } else { 'idle' }
            CurrentStagePercent   = if ($first) { $first.percent } else { $null }
            CurrentItemStartedAt  = $null
            CurrentStageStartedAt = $null
            CopyState             = $null
            PushState             = $null
            SidecarState          = $null
            PauseRequested        = (Test-Path -LiteralPath $PauseFlag -ErrorAction SilentlyContinue)
            StopRequested         = [bool]($script:StopRequested -or (Test-Path -LiteralPath $StopFlag -ErrorAction SilentlyContinue))
            ControlRequests       = @{}
            Status                = if ($jobs.Count -gt 0) { 'Processing local worker slots' } else { 'Idle' }
            TotalProcessed        = [int]$script:totalProcessed
            Encoded               = [int]$script:totalEncoded
            Remuxed               = [int]$script:totalRemuxed
            Failed                = [int]$script:totalFailed
            Movies                = [int]$script:totalMovies
            TVEpisodes            = [int]$script:totalTVEpisodes
            ActiveEncodeJobs      = @($jobs)
            ActiveEncodeJobCount  = [int]$jobs.Count
            ParallelEncodeMode    = 'local_worker_slots'
        }
        Write-MediaPipelineJsonAtomic -Path $CompatibilityProgressPath -InputObject $compat -Depth 8 | Out-Null
    }
    return $payload
}

function Update-MediaPipelineParentCountersFromWorkerResult {
    param($Result, [bool] $IsTV)

    if (-not $Result) { return }
    $status = if ($Result.PSObject.Properties['Status']) { [string]$Result.Status } else { '' }
    $success = if ($Result.PSObject.Properties['Success']) { [bool]$Result.Success } else { $false }
    $route = if ($Result.PSObject.Properties['Route']) { [string]$Result.Route } else { '' }
    if ($success -and $status -in @('processed','skipped')) {
        if ($status -eq 'processed') {
            $script:totalProcessed++
            if ($route -match 'encode') { $script:totalEncoded++ } else { $script:totalRemuxed++ }
            if ($IsTV) { $script:totalTVEpisodes++ } else { $script:totalMovies++ }
        }
        return
    }
    if ($status -eq 'failed') {
        $script:totalFailed++
    }
}
