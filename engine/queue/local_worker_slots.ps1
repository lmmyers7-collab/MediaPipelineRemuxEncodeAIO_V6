# ==============================================================================
# engine\queue\local_worker_slots.ps1
# ==============================================================================
# Local two-slot encode scheduler helpers. The controller remains the only queue
# scanner; child processes are isolated per-file workers launched through the
# existing -SingleFile path.
# ==============================================================================

function Get-MediaPipelineLocalWorkerTimestamp {
    return (Get-Date).ToString('o')
}

function Get-MediaPipelineStableHash {
    param([string] $Text)

    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [System.Text.Encoding]::UTF8.GetBytes([string]$Text)
        $hash = $sha.ComputeHash($bytes)
        return ([System.BitConverter]::ToString($hash) -replace '-', '').Substring(0, 16).ToLowerInvariant()
    } finally {
        $sha.Dispose()
    }
}

function Get-MediaPipelineWorkerMutexSuffix {
    $suffix = ''
    if (-not [string]::IsNullOrWhiteSpace($env:MEDIA_PIPELINE_TEST_MUTEX_SUFFIX)) {
        $suffix = '_' + (($env:MEDIA_PIPELINE_TEST_MUTEX_SUFFIX) -replace '[^A-Za-z0-9_.-]', '_')
    }
    return $suffix
}

function Get-MediaPipelineLocalWorkerMutexName {
    param(
        [Parameter(Mandatory)] [string] $Kind,
        [string] $LocalBase = '',
        [int] $SlotId = 0
    )

    $scopeText = if ([string]::IsNullOrWhiteSpace($LocalBase)) { 'global' } else { [string]$LocalBase }
    $hash = Get-MediaPipelineStableHash -Text $scopeText
    $slotPart = if ($SlotId -gt 0) { "_slot_$SlotId" } else { '' }
    return "Global\MediaPipeline_${Kind}_v1_${hash}${slotPart}$(Get-MediaPipelineWorkerMutexSuffix)"
}

function Invoke-MediaPipelineMutexProtected {
    param(
        [Parameter(Mandatory)] [string] $MutexName,
        [Parameter(Mandatory)] [scriptblock] $ScriptBlock,
        [int] $TimeoutMs = 30000
    )

    $mutex = [System.Threading.Mutex]::new($false, $MutexName)
    $locked = $false
    try {
        try {
            $locked = $mutex.WaitOne($TimeoutMs)
        } catch [System.Threading.AbandonedMutexException] {
            $locked = $true
        }
        if (-not $locked) {
            throw "Timed out waiting for mutex $MutexName"
        }
        return (& $ScriptBlock)
    } finally {
        if ($locked) {
            try { $mutex.ReleaseMutex() } catch {}
        }
        $mutex.Dispose()
    }
}

function Invoke-MediaPipelineFinalStateWrite {
    param(
        [Parameter(Mandatory)] [scriptblock] $ScriptBlock,
        [string] $OperationName = 'final-state',
        [int] $TimeoutMs = 600000
    )

    $localBaseForLock = ''
    try { if ($LocalBase) { $localBaseForLock = [string]$LocalBase } } catch {}
    $mutexName = Get-MediaPipelineLocalWorkerMutexName -Kind 'FinalStateWriter' -LocalBase $localBaseForLock
    return Invoke-MediaPipelineMutexProtected -MutexName $mutexName -TimeoutMs $TimeoutMs -ScriptBlock {
        if (Get-Command Write-Log -ErrorAction SilentlyContinue) {
            Write-Log "Final-state writer lock acquired for $OperationName" 'DEBUG'
        }
        & $ScriptBlock
    }
}

function Write-MediaPipelineJsonAtomic {
    param(
        [Parameter(Mandatory)] [string] $Path,
        [Parameter(Mandatory)] $InputObject,
        [int] $Depth = 8
    )

    $dir = Split-Path -Parent $Path
    if (-not [string]::IsNullOrWhiteSpace($dir) -and -not (Test-Path -LiteralPath $dir)) {
        [System.IO.Directory]::CreateDirectory($dir) | Out-Null
    }
    $leaf = Split-Path -Leaf $Path
    $id = [guid]::NewGuid().ToString('N')
    $tmp = Join-Path $dir ".$leaf.$id.tmp"
    $backup = Join-Path $dir ".$leaf.$id.bak"
    try {
        $json = ConvertTo-Json -InputObject $InputObject -Depth $Depth
        [System.IO.File]::WriteAllText($tmp, $json, [System.Text.UTF8Encoding]::new($false))
        $null = Get-Content -LiteralPath $tmp -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
        if ([System.IO.File]::Exists($Path)) {
            [System.IO.File]::Replace($tmp, $Path, $backup, $true)
            Remove-Item -LiteralPath $backup -Force -ErrorAction SilentlyContinue
        } else {
            [System.IO.File]::Move($tmp, $Path)
        }
        return $true
    } catch {
        Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $backup -Force -ErrorAction SilentlyContinue
        throw
    }
}

function Read-MediaPipelineJsonFile {
    param([Parameter(Mandatory)] [string] $Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $null }
    return Get-Content -LiteralPath $Path -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
}

function ConvertTo-MediaPipelineLocalWorkerPathKey {
    param([string] $Path)

    if ([string]::IsNullOrWhiteSpace($Path)) { return '' }
    try {
        return ([System.IO.Path]::GetFullPath($Path).TrimEnd('\', '/') -replace '\\','/').ToLowerInvariant()
    } catch {
        return (($Path.TrimEnd('\', '/') -replace '\\','/').ToLowerInvariant())
    }
}

function New-MediaPipelineWorkerSlotLayout {
    param(
        [Parameter(Mandatory)] $StateLayout,
        [Parameter(Mandatory)] [int] $SlotId
    )

    $workersRoot = if ($StateLayout.PSObject.Properties['Workers']) { [string]$StateLayout.Workers } else { Join-Path $StateLayout.Root 'Workers' }
    $root = Join-Path $workersRoot "slot-$SlotId"
    $logs = Join-Path $root 'Logs'
    $progress = Join-Path $root 'Progress'
    $failures = Join-Path $root 'Failures'
    return [pscustomobject]@{
        SlotId           = [int]$SlotId
        Root             = $root
        Incoming         = Join-Path $root 'Incoming'
        Processing       = Join-Path (Join-Path $root 'Incoming') 'Processing'
        Encoded          = Join-Path $root 'Encoded'
        RemuxTemp        = Join-Path $root 'RemuxTemp'
        Logs             = $logs
        LogFile          = Join-Path $logs 'pipeline_debug.log'
        StdoutLog        = Join-Path $logs 'worker_stdout.log'
        StderrLog        = Join-Path $logs 'worker_stderr.log'
        Progress         = $progress
        ProgressFile     = Join-Path $progress 'pipeline_progress.json'
        EventLogFile     = Join-Path $progress 'pipeline_events.jsonl'
        ResultFile       = Join-Path $root 'worker_result.json'
        MetadataFile     = Join-Path $root 'worker_metadata.json'
        Failures         = $failures
        FailureArtifacts = Join-Path $failures 'Artifacts'
        FailureReports   = Join-Path $failures 'Reports'
    }
}

function Initialize-MediaPipelineWorkerSlotLayout {
    param([Parameter(Mandatory)] $SlotLayout)

    foreach ($dir in @(
        $SlotLayout.Root,
        $SlotLayout.Incoming,
        $SlotLayout.Processing,
        $SlotLayout.Encoded,
        $SlotLayout.RemuxTemp,
        $SlotLayout.Logs,
        $SlotLayout.Progress,
        $SlotLayout.Failures,
        $SlotLayout.FailureArtifacts,
        $SlotLayout.FailureReports
    )) {
        if (-not (Test-Path -LiteralPath $dir)) {
            [System.IO.Directory]::CreateDirectory([string]$dir) | Out-Null
        }
    }
    return $SlotLayout
}

function New-MediaPipelineLocalWorkerClaimStore {
    return [ordered]@{
        schema_version = 'local_worker_claims.v1'
        updated_at     = Get-MediaPipelineLocalWorkerTimestamp
        claims         = @()
    }
}

function Get-MediaPipelineLocalWorkerClaimStore {
    param([Parameter(Mandatory)] [string] $ClaimStorePath)

    $store = $null
    try { $store = Read-MediaPipelineJsonFile -Path $ClaimStorePath } catch { $store = $null }
    if (-not $store) { return New-MediaPipelineLocalWorkerClaimStore }

    $claims = @()
    if ($store.PSObject.Properties['claims'] -and $null -ne $store.claims) {
        $claims = @($store.claims)
    }
    return [ordered]@{
        schema_version = if ($store.PSObject.Properties['schema_version']) { [string]$store.schema_version } else { 'local_worker_claims.v1' }
        updated_at     = if ($store.PSObject.Properties['updated_at']) { [string]$store.updated_at } else { Get-MediaPipelineLocalWorkerTimestamp }
        claims         = @($claims)
    }
}

function Write-MediaPipelineLocalWorkerClaimStore {
    param(
        [Parameter(Mandatory)] [string] $ClaimStorePath,
        [Parameter(Mandatory)] $Store
    )

    $Store.updated_at = Get-MediaPipelineLocalWorkerTimestamp
    Write-MediaPipelineJsonAtomic -Path $ClaimStorePath -InputObject $Store -Depth 8 | Out-Null
}

function Get-MediaPipelineLocalWorkerClaimActiveStatuses {
    return @('claimed','starting','running','result_ready','finalizing')
}

function Test-MediaPipelineProcessAlive {
    param([object] $ProcessId)

    try {
        $pidValue = [int]$ProcessId
        if ($pidValue -le 0) { return $false }
        $proc = Get-Process -Id $pidValue -ErrorAction SilentlyContinue
        return ($null -ne $proc -and -not $proc.HasExited)
    } catch {
        return $false
    }
}

function Repair-MediaPipelineLocalWorkerClaims {
    param(
        [Parameter(Mandatory)] [string] $ClaimStorePath,
        [string] $CurrentRunId = '',
        [int] $ClaimStaleSeconds = 30
    )

    $localBaseForLock = ''
    try { if ($LocalBase) { $localBaseForLock = [string]$LocalBase } } catch {}
    $mutexName = Get-MediaPipelineLocalWorkerMutexName -Kind 'ClaimStore' -LocalBase $localBaseForLock
    return Invoke-MediaPipelineMutexProtected -MutexName $mutexName -ScriptBlock {
        $store = Get-MediaPipelineLocalWorkerClaimStore -ClaimStorePath $ClaimStorePath
        $activeStatuses = @(Get-MediaPipelineLocalWorkerClaimActiveStatuses)
        $now = Get-Date
        $changed = $false
        foreach ($claim in @($store.claims)) {
            $status = [string]$claim.status
            if ($status -notin $activeStatuses) { continue }

            $resultPath = if ($claim.PSObject.Properties['result_path']) { [string]$claim.result_path } else { '' }
            $workerPid = if ($claim.PSObject.Properties['worker_pid']) { $claim.worker_pid } else { $null }
            $alive = Test-MediaPipelineProcessAlive -ProcessId $workerPid
            if ($alive) { continue }

            if (-not [string]::IsNullOrWhiteSpace($resultPath) -and (Test-Path -LiteralPath $resultPath -PathType Leaf)) {
                $claim.status = 'result_ready'
                $claim.updated_at = Get-MediaPipelineLocalWorkerTimestamp
                $claim.recovery_note = 'worker result exists; controller must consume result before releasing claim'
                $changed = $true
                continue
            }

            $claimedAt = $null
            try { $claimedAt = [datetime]::Parse([string]$claim.claimed_at) } catch {}
            $ageSeconds = if ($claimedAt) { ($now - $claimedAt).TotalSeconds } else { [double]::MaxValue }
            $ownerRun = if ($claim.PSObject.Properties['owner_run_id']) { [string]$claim.owner_run_id } else { '' }
            if ($ownerRun -ne $CurrentRunId -or $ageSeconds -ge $ClaimStaleSeconds -or [string]::IsNullOrWhiteSpace([string]$workerPid)) {
                $claim.status = 'released_stale'
                $claim.released_at = Get-MediaPipelineLocalWorkerTimestamp
                $claim.updated_at = $claim.released_at
                $claim.recovery_note = 'released because no live worker process owned the claim'
                $changed = $true
            }
        }
        if ($changed) {
            Write-MediaPipelineLocalWorkerClaimStore -ClaimStorePath $ClaimStorePath -Store $store
        }
        return $store
    }
}

function Invoke-MediaPipelineLocalWorkerClaim {
    param(
        [Parameter(Mandatory)] [string] $ClaimStorePath,
        [Parameter(Mandatory)] $Entry,
        [Parameter(Mandatory)] [int] $SlotId,
        [Parameter(Mandatory)] [string] $OwnerRunId,
        [string] $ResultPath = ''
    )

    $sourcePath = if ($Entry.PSObject.Properties['SourcePath'] -and $Entry.SourcePath) { [string]$Entry.SourcePath } else { [string]$Entry.File.FullName }
    $sourceKey = ConvertTo-MediaPipelineLocalWorkerPathKey -Path $sourcePath
    $localBaseForLock = ''
    try { if ($LocalBase) { $localBaseForLock = [string]$LocalBase } } catch {}
    $mutexName = Get-MediaPipelineLocalWorkerMutexName -Kind 'ClaimStore' -LocalBase $localBaseForLock

    return Invoke-MediaPipelineMutexProtected -MutexName $mutexName -ScriptBlock {
        $store = Get-MediaPipelineLocalWorkerClaimStore -ClaimStorePath $ClaimStorePath
        $activeStatuses = @(Get-MediaPipelineLocalWorkerClaimActiveStatuses)
        foreach ($claim in @($store.claims)) {
            if ([string]$claim.source_key -eq $sourceKey -and [string]$claim.status -in $activeStatuses) {
                return $null
            }
        }

        $claimId = [guid]::NewGuid().ToString('N')
        $nowText = Get-MediaPipelineLocalWorkerTimestamp
        $record = [ordered]@{
            schema_version = 'local_worker_claim.v1'
            claim_id       = $claimId
            status         = 'claimed'
            source_path    = $sourcePath
            source_key     = $sourceKey
            source_name    = if ($Entry.File) { [string]$Entry.File.Name } else { [System.IO.Path]::GetFileName($sourcePath) }
            media_kind     = if ([bool]$Entry.IsTV) { 'tv' } else { 'movie' }
            route_type     = ''
            slot_id        = [int]$SlotId
            owner_run_id   = [string]$OwnerRunId
            owner_pid      = [int]$PID
            worker_pid     = $null
            queue_index    = [int]$Entry.QueueIndex
            queue_total    = [int]$Entry.QueueTotal
            queue_phase    = if ($Entry.PSObject.Properties['LocalWorkerPhase']) { [string]$Entry.LocalWorkerPhase } else { [string]$Entry.QueuePhase }
            priority       = [bool]$Entry.IsPriority
            result_path    = [string]$ResultPath
            claimed_at     = $nowText
            updated_at     = $nowText
        }
        $store.claims = @(@($store.claims) + @([pscustomobject]$record))
        Write-MediaPipelineLocalWorkerClaimStore -ClaimStorePath $ClaimStorePath -Store $store
        return [pscustomobject]$record
    }
}

function Update-MediaPipelineLocalWorkerClaim {
    param(
        [Parameter(Mandatory)] [string] $ClaimStorePath,
        [Parameter(Mandatory)] [string] $ClaimId,
        [Parameter(Mandatory)] [hashtable] $Updates
    )

    $localBaseForLock = ''
    try { if ($LocalBase) { $localBaseForLock = [string]$LocalBase } } catch {}
    $mutexName = Get-MediaPipelineLocalWorkerMutexName -Kind 'ClaimStore' -LocalBase $localBaseForLock
    return Invoke-MediaPipelineMutexProtected -MutexName $mutexName -ScriptBlock {
        $store = Get-MediaPipelineLocalWorkerClaimStore -ClaimStorePath $ClaimStorePath
        $updated = $false
        foreach ($claim in @($store.claims)) {
            if ([string]$claim.claim_id -ne $ClaimId) { continue }
            foreach ($key in @($Updates.Keys)) {
                $claim | Add-Member -NotePropertyName ([string]$key) -NotePropertyValue $Updates[$key] -Force
            }
            $claim.updated_at = Get-MediaPipelineLocalWorkerTimestamp
            $updated = $true
            break
        }
        if ($updated) {
            Write-MediaPipelineLocalWorkerClaimStore -ClaimStorePath $ClaimStorePath -Store $store
        }
        return $updated
    }
}

function Release-MediaPipelineLocalWorkerClaim {
    param(
        [Parameter(Mandatory)] [string] $ClaimStorePath,
        [Parameter(Mandatory)] [string] $ClaimId,
        [string] $Status = 'released',
        [string] $Reason = ''
    )

    $updates = @{
        status      = $Status
        released_at = Get-MediaPipelineLocalWorkerTimestamp
        release_reason = $Reason
    }
    return Update-MediaPipelineLocalWorkerClaim -ClaimStorePath $ClaimStorePath -ClaimId $ClaimId -Updates $updates
}

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
            [void]$entries.Add($entry)
        }
    }
    return @($entries)
}

function Join-MediaPipelineProcessArgument {
    param([string] $Value)

    if ($null -eq $Value) { return '""' }
    $text = [string]$Value
    if ($text -notmatch '[\s"]') { return $text }
    return '"' + ($text -replace '\\(?=")', '\\' -replace '"', '\"') + '"'
}

function Start-MediaPipelineLocalWorkerChild {
    param(
        [Parameter(Mandatory)] $Entry,
        [Parameter(Mandatory)] $Claim,
        [Parameter(Mandatory)] $SlotLayout,
        [Parameter(Mandatory)] [string] $ScriptPath,
        [Parameter(Mandatory)] [string] $ConfigPath,
        [Parameter(Mandatory)] [string] $PowerShellPath,
        [Parameter(Mandatory)] [string] $OwnerRunId
    )

    Initialize-MediaPipelineWorkerSlotLayout -SlotLayout $SlotLayout | Out-Null
    foreach ($path in @($SlotLayout.ResultFile, $SlotLayout.StdoutLog, $SlotLayout.StderrLog)) {
        Remove-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
    }
    $metadata = [ordered]@{
        schema_version = 'local_worker_metadata.v1'
        slot_id        = [int]$SlotLayout.SlotId
        claim_id       = [string]$Claim.claim_id
        source_path    = [string]$Claim.source_path
        owner_run_id   = [string]$OwnerRunId
        created_at     = Get-MediaPipelineLocalWorkerTimestamp
    }
    Write-MediaPipelineJsonAtomic -Path $SlotLayout.MetadataFile -InputObject $metadata -Depth 5 | Out-Null

    $arguments = @(
        '-NoLogo',
        '-NoProfile',
        '-ExecutionPolicy', 'Bypass',
        '-File', $ScriptPath,
        '-ConfigPath', $ConfigPath,
        '-SingleFile', ([string]$Claim.source_path),
        '-WorkerChild',
        '-WorkerSlotId', ([string]$SlotLayout.SlotId),
        '-WorkerRunId', $OwnerRunId,
        '-WorkerClaimId', ([string]$Claim.claim_id),
        '-WorkerResultPath', ([string]$SlotLayout.ResultFile)
    )
    $argumentLine = ($arguments | ForEach-Object { Join-MediaPipelineProcessArgument -Value ([string]$_) }) -join ' '
    $process = Start-Process -FilePath $PowerShellPath `
        -ArgumentList $argumentLine `
        -WorkingDirectory (Split-Path -Parent $ScriptPath) `
        -RedirectStandardOutput $SlotLayout.StdoutLog `
        -RedirectStandardError $SlotLayout.StderrLog `
        -WindowStyle Hidden `
        -PassThru
    return $process
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

function Stop-MediaPipelineLocalWorkerProcess {
    param(
        [Parameter(Mandatory)] $Job,
        [int] $GraceMilliseconds = 2500
    )

    try {
        if (-not $Job.Process -or $Job.Process.HasExited) { return }
        try { $Job.Process.CloseMainWindow() | Out-Null } catch {}
        $exited = $Job.Process.WaitForExit($GraceMilliseconds)
        if (-not $exited -and -not $Job.Process.HasExited) {
            $Job.Process.Kill($true)
            $Job.Process.WaitForExit(5000) | Out-Null
        }
    } catch {
        if (Get-Command Write-Log -ErrorAction SilentlyContinue) {
            Write-Log "Failed to stop local worker slot $($Job.SlotLayout.SlotId): $_" 'WARN'
        }
    }
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

function Invoke-MediaQueuePhasePlanLocalWorkerSlots {
    param(
        [Parameter(Mandatory)] $QueuePlan,
        [Parameter(Mandatory)] $ProcessedIndex,
        [Parameter(Mandatory)] [string] $ScriptPath,
        [Parameter(Mandatory)] [string] $ConfigPath,
        [Parameter(Mandatory)] [string] $PowerShellPath,
        [Parameter(Mandatory)] [int] $MaxParallelEncodes
    )

    $allEntries = @(Get-MediaPipelineQueuePlanRunnableEntries -QueuePlan $QueuePlan)
    $claimStorePath = [string]$script:LocalStateLayout.Paths.LocalWorkerClaims
    $activeJobsPath = [string]$script:LocalStateLayout.Paths.LocalWorkerActiveJobs
    Repair-MediaPipelineLocalWorkerClaims -ClaimStorePath $claimStorePath -CurrentRunId $script:PipelineRunId | Out-Null

    $queue = [System.Collections.Queue]::new()
    foreach ($entry in $allEntries) { $queue.Enqueue($entry) }
    $active = @{}
    $slotIds = @(1..$MaxParallelEncodes)

    while (($queue.Count -gt 0 -or $active.Count -gt 0) -and -not $script:StopRequested) {
        Check-ControlFlags
        if ($script:StopRequested) { break }

        foreach ($slotId in $slotIds) {
            if ($active.ContainsKey([string]$slotId)) { continue }
            if ($queue.Count -le 0) { break }
            $entry = $queue.Dequeue()
            $slotLayout = Initialize-MediaPipelineWorkerSlotLayout -SlotLayout (New-MediaPipelineWorkerSlotLayout -StateLayout $script:LocalStateLayout -SlotId $slotId)
            $claim = Invoke-MediaPipelineLocalWorkerClaim -ClaimStorePath $claimStorePath -Entry $entry -SlotId $slotId -OwnerRunId $script:PipelineRunId -ResultPath $slotLayout.ResultFile
            if (-not $claim) {
                Write-Log "Local worker slots: skipped duplicate active claim for $($entry.File.FullName)" 'WARN'
                continue
            }
            try {
                $proc = Start-MediaPipelineLocalWorkerChild -Entry $entry -Claim $claim -SlotLayout $slotLayout -ScriptPath $ScriptPath -ConfigPath $ConfigPath -PowerShellPath $PowerShellPath -OwnerRunId $script:PipelineRunId
                Update-MediaPipelineLocalWorkerClaim -ClaimStorePath $claimStorePath -ClaimId ([string]$claim.claim_id) -Updates @{ status = 'running'; worker_pid = [int]$proc.Id; started_at = Get-MediaPipelineLocalWorkerTimestamp } | Out-Null
                $claim | Add-Member -NotePropertyName worker_pid -NotePropertyValue ([int]$proc.Id) -Force
                $claim | Add-Member -NotePropertyName status -NotePropertyValue 'running' -Force
                $active[[string]$slotId] = [pscustomobject]@{
                    SlotLayout = $slotLayout
                    Claim      = $claim
                    Entry      = $entry
                    Process    = $proc
                    Status     = 'running'
                    StartedAt  = Get-Date
                }
                Write-Log "Local worker slot $slotId started PID $($proc.Id): $($entry.File.Name)"
            } catch {
                Write-Log "Local worker slot $slotId failed to start for $($entry.File.FullName): $_" 'ERROR'
                Release-MediaPipelineLocalWorkerClaim -ClaimStorePath $claimStorePath -ClaimId ([string]$claim.claim_id) -Status 'failed_start' -Reason ([string]$_) | Out-Null
            }
        }

        Write-MediaPipelineLocalWorkerActiveJobs -ActiveJobsPath $activeJobsPath -CompatibilityProgressPath $ProgressFile -ActiveJobs @($active.Values) -WriteCompatibilityProgress | Out-Null

        foreach ($slotKey in @($active.Keys)) {
            $job = $active[$slotKey]
            if (-not $job.Process.HasExited) { continue }
            $exitCode = $job.Process.ExitCode
            $result = $null
            try {
                if (Test-Path -LiteralPath $job.SlotLayout.ResultFile -PathType Leaf) {
                    $result = Read-MediaPipelineJsonFile -Path $job.SlotLayout.ResultFile
                }
            } catch {
                Write-Log "Local worker slot $($job.SlotLayout.SlotId) result read failed: $_" 'WARN'
            }
            $status = if ($exitCode -eq 0) { 'completed' } else { 'failed' }
            $reason = if ($result -and $result.PSObject.Properties['Reason']) { [string]$result.Reason } else { "worker exit code $exitCode" }
            Update-MediaPipelineParentCountersFromWorkerResult -Result $result -IsTV:([bool]$job.Entry.IsTV)
            Release-MediaPipelineLocalWorkerClaim -ClaimStorePath $claimStorePath -ClaimId ([string]$job.Claim.claim_id) -Status $status -Reason $reason | Out-Null
            Write-Log "Local worker slot $($job.SlotLayout.SlotId) finished exit=$exitCode status=$status source=$($job.Claim.source_path)"
            $active.Remove($slotKey)
            Invalidate-ProcessedIndexCache
        }

        Write-MediaPipelineLocalWorkerActiveJobs -ActiveJobsPath $activeJobsPath -CompatibilityProgressPath $ProgressFile -ActiveJobs @($active.Values) -WriteCompatibilityProgress | Out-Null
        if ($queue.Count -gt 0 -or $active.Count -gt 0) {
            Start-Sleep -Milliseconds 500
        }
    }

    if ($script:StopRequested -and $active.Count -gt 0) {
        Write-Log "Local worker slots: stop requested; stopping $($active.Count) active worker(s)" 'WARN'
        foreach ($job in @($active.Values)) {
            Stop-MediaPipelineLocalWorkerProcess -Job $job
            Release-MediaPipelineLocalWorkerClaim -ClaimStorePath $claimStorePath -ClaimId ([string]$job.Claim.claim_id) -Status 'stopped' -Reason 'operator stop requested' | Out-Null
        }
        $active.Clear()
        Write-MediaPipelineLocalWorkerActiveJobs -ActiveJobsPath $activeJobsPath -CompatibilityProgressPath $ProgressFile -ActiveJobs @() -WriteCompatibilityProgress | Out-Null
    }

    $holdCount = [int]$QueuePlan.HoldCount
    if ($holdCount -gt 0) {
        Write-Log "HOLD: $holdCount item(s) excluded from local worker slots this round (operator hold)"
    }

    return [pscustomobject]@{
        Stopped       = [bool]$script:StopRequested
        PriorityCount = [int]($QueuePlan.MoviePriorityCount + $QueuePlan.TVPriorityCount)
        MovieCount    = [int]$QueuePlan.MovieCount
        TVCount       = [int]$QueuePlan.TVCount
        LowCount      = [int]$QueuePlan.LowCount
        HoldCount     = $holdCount
    }
}
