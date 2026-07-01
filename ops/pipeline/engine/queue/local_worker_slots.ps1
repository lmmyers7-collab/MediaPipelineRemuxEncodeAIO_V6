# ==============================================================================
# ops\pipeline\engine\queue\local_worker_slots.ps1
# ==============================================================================
# Local two-slot encode scheduler helpers. The controller remains the only queue
# scanner; child processes are isolated per-file workers launched through the
# existing -SingleFile path.
# ==============================================================================


. (Join-Path $PSScriptRoot 'worker_mutex.ps1')
. (Join-Path $PSScriptRoot 'worker_process.ps1')
. (Join-Path $PSScriptRoot 'worker_progress.ps1')
. (Join-Path $PSScriptRoot 'worker_claim_store.ps1')

function Resolve-MediaPipelineLocalWorkerSlotCompletion {
    param(
        [int] $ExitCode,
        $Result = $null,
        [bool] $ResultFileExists = $false,
        [string] $ResultReadError = '',
        [Parameter(Mandatory)] $Claim,
        [Parameter(Mandatory)] [string] $OwnerRunId
    )

    $resultReason = ''
    if ($Result -and $Result.PSObject.Properties['Reason']) {
        $resultReason = [string]$Result.Reason
    }
    $resultStatus = ''
    if ($Result -and $Result.PSObject.Properties['Status']) {
        $resultStatus = [string]$Result.Status
    }

    if ($ExitCode -ne 0) {
        return [pscustomobject]@{
            Status                = 'failed'
            Reason                = if (-not [string]::IsNullOrWhiteSpace($resultReason)) { $resultReason } else { "worker exit code $ExitCode" }
            ApplyCounters         = ($null -ne $Result)
            CountSyntheticFailure = $false
        }
    }

    if (-not $ResultFileExists) {
        return [pscustomobject]@{
            Status                = 'failed_result_missing'
            Reason                = 'worker exited 0 but worker_result.json is missing'
            ApplyCounters         = $false
            CountSyntheticFailure = $true
        }
    }

    if (-not $Result) {
        $reason = if ([string]::IsNullOrWhiteSpace($ResultReadError)) {
            'worker exited 0 but worker_result.json was empty or unreadable'
        } else {
            "worker exited 0 but worker_result.json could not be read: $ResultReadError"
        }
        return [pscustomobject]@{
            Status                = 'failed_result_invalid'
            Reason                = $reason
            ApplyCounters         = $false
            CountSyntheticFailure = $true
        }
    }

    if (-not $Result.PSObject.Properties['SchemaVersion'] -or [string]$Result.SchemaVersion -ne 'local_worker_result.v1') {
        return [pscustomobject]@{
            Status                = 'failed_result_invalid'
            Reason                = 'worker exited 0 but worker_result.json schema is not local_worker_result.v1'
            ApplyCounters         = $false
            CountSyntheticFailure = $true
        }
    }

    if (-not $Result.PSObject.Properties['WorkerClaimId'] -or [string]$Result.WorkerClaimId -ne [string]$Claim.claim_id) {
        return [pscustomobject]@{
            Status                = 'failed_result_invalid'
            Reason                = 'worker exited 0 but worker_result.json claim id does not match the active claim'
            ApplyCounters         = $false
            CountSyntheticFailure = $true
        }
    }

    if (-not $Result.PSObject.Properties['WorkerRunId'] -or [string]$Result.WorkerRunId -ne [string]$OwnerRunId) {
        return [pscustomobject]@{
            Status                = 'failed_result_invalid'
            Reason                = 'worker exited 0 but worker_result.json run id does not match the controller run'
            ApplyCounters         = $false
            CountSyntheticFailure = $true
        }
    }

    if (-not $Result.PSObject.Properties['Success'] -or $Result.Success -isnot [bool]) {
        return [pscustomobject]@{
            Status                = 'failed_result_invalid'
            Reason                = 'worker exited 0 but worker_result.json does not contain a boolean Success field'
            ApplyCounters         = $false
            CountSyntheticFailure = $true
        }
    }

    if (-not [bool]$Result.Success) {
        return [pscustomobject]@{
            Status                = 'failed'
            Reason                = if (-not [string]::IsNullOrWhiteSpace($resultReason)) { $resultReason } else { 'worker result reported Success=false after exit 0' }
            ApplyCounters         = $true
            CountSyntheticFailure = ($resultStatus -ne 'failed')
        }
    }

    return [pscustomobject]@{
        Status                = 'completed'
        Reason                = if (-not [string]::IsNullOrWhiteSpace($resultReason)) { $resultReason } else { 'worker result confirmed success' }
        ApplyCounters         = $true
        CountSyntheticFailure = $false
    }
}

function Get-MediaPipelineLocalWorkerHardTimeoutSeconds {
    $override = [int]$script:LocalWorkerChildHardTimeoutSeconds
    if ($override -gt 0) { return $override }
    $configuredTimeouts = @(
        [int]$script:FFmpegEncodeTimeoutSeconds,
        [int]$script:FFmpegCpuEncodeTimeoutSeconds,
        [int]$script:FFmpegRemuxTimeoutSeconds,
        [int]$script:MkvmergeRemuxTimeoutSeconds,
        [int]$script:SubtitleExtractTimeoutSeconds,
        [int]$script:BdpgsOcrTimeoutSeconds,
        [int]$script:VobSubOcrTimeoutSeconds,
        [int]$script:QualityVerifyTimeoutSeconds,
        [int]$script:OutputValidationProbeTimeoutSeconds,
        [int]$script:RobocopyTimeoutSeconds
    ) | Where-Object { $_ -gt 0 }
    $largest = if (@($configuredTimeouts).Count -gt 0) { [int](@($configuredTimeouts) | Measure-Object -Maximum).Maximum } else { 43200 }
    return [int]($largest + 1800)
}

function Get-MediaPipelineLocalWorkerHeartbeatAgeSeconds {
    param([string] $HeartbeatPath = '')

    if ([string]::IsNullOrWhiteSpace($HeartbeatPath) -or -not (Test-Path -LiteralPath $HeartbeatPath -PathType Leaf)) {
        return $null
    }
    try {
        $item = Get-Item -LiteralPath $HeartbeatPath -ErrorAction Stop
        return [math]::Max(0, [int]((Get-Date) - $item.LastWriteTime).TotalSeconds)
    } catch {
        return $null
    }
}

function Get-MediaPipelineLocalWorkerHeartbeatGraceSeconds {
    $configured = [int]$script:LocalWorkerHeartbeatGraceSeconds
    if ($configured -gt 0) { return $configured }
    return 900
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
    $childHardTimeoutSeconds = Get-MediaPipelineLocalWorkerHardTimeoutSeconds
    $heartbeatGraceSeconds = Get-MediaPipelineLocalWorkerHeartbeatGraceSeconds

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
            $proc = $null
            try {
                $proc = Start-MediaPipelineLocalWorkerChild -Entry $entry -Claim $claim -SlotLayout $slotLayout -ScriptPath $ScriptPath -ConfigPath $ConfigPath -PowerShellPath $PowerShellPath -OwnerRunId $script:PipelineRunId
                $workerStartTime = Get-MediaPipelineProcessStartTimeUtcText -ProcessId $proc.Id
                if (Test-Path -LiteralPath $slotLayout.MetadataFile -PathType Leaf) {
                    try {
                        $metadata = Read-MediaPipelineJsonFile -Path $slotLayout.MetadataFile
                        if ($metadata) {
                            $metadata | Add-Member -NotePropertyName worker_pid -NotePropertyValue ([int]$proc.Id) -Force
                            $metadata | Add-Member -NotePropertyName worker_start_time -NotePropertyValue $workerStartTime -Force
                            $metadata | Add-Member -NotePropertyName started_at -NotePropertyValue (Get-MediaPipelineLocalWorkerTimestamp) -Force
                            $metadata | Add-Member -NotePropertyName heartbeat_path -NotePropertyValue ([string]$slotLayout.HeartbeatFile) -Force
                            Write-MediaPipelineJsonAtomic -Path $slotLayout.MetadataFile -InputObject $metadata -Depth 5 | Out-Null
                        }
                    } catch {
                        Write-Log "Local worker slot $slotId metadata update failed after launch: $_" 'WARN'
                    }
                }
                Update-MediaPipelineLocalWorkerClaim -ClaimStorePath $claimStorePath -ClaimId ([string]$claim.claim_id) -Updates @{ status = 'running'; worker_pid = [int]$proc.Id; worker_start_time = $workerStartTime; worker_metadata_path = [string]$slotLayout.MetadataFile; worker_heartbeat_path = [string]$slotLayout.HeartbeatFile; started_at = Get-MediaPipelineLocalWorkerTimestamp } | Out-Null
                $claim | Add-Member -NotePropertyName worker_pid -NotePropertyValue ([int]$proc.Id) -Force
                $claim | Add-Member -NotePropertyName worker_start_time -NotePropertyValue $workerStartTime -Force
                $claim | Add-Member -NotePropertyName worker_metadata_path -NotePropertyValue ([string]$slotLayout.MetadataFile) -Force
                $claim | Add-Member -NotePropertyName worker_heartbeat_path -NotePropertyValue ([string]$slotLayout.HeartbeatFile) -Force
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
                $releaseStatus = 'failed_start'
                $releaseReason = [string]$_
                if ($null -ne $proc -and -not $proc.HasExited) {
                    Stop-MediaPipelineLocalWorkerProcess -Job ([pscustomobject]@{
                        SlotLayout = $slotLayout
                        Claim      = $claim
                        Entry      = $entry
                        Process    = $proc
                    })
                    $releaseStatus = 'failed_start_child_stopped'
                    $releaseReason = "spawned child stopped after claim update failure: $_"
                }
                Release-MediaPipelineLocalWorkerClaim -ClaimStorePath $claimStorePath -ClaimId ([string]$claim.claim_id) -Status $releaseStatus -Reason $releaseReason | Out-Null
            }
        }

        Write-MediaPipelineLocalWorkerActiveJobs -ActiveJobsPath $activeJobsPath -CompatibilityProgressPath $ProgressFile -ActiveJobs @($active.Values) -WriteCompatibilityProgress | Out-Null

        foreach ($slotKey in @($active.Keys)) {
            $job = $active[$slotKey]
            if (-not $job.Process.HasExited) {
                $elapsedSeconds = ((Get-Date) - ([datetime]$job.StartedAt)).TotalSeconds
                $heartbeatAgeSeconds = Get-MediaPipelineLocalWorkerHeartbeatAgeSeconds -HeartbeatPath ([string]$job.SlotLayout.HeartbeatFile)
                if ($childHardTimeoutSeconds -gt 0 -and $elapsedSeconds -ge $childHardTimeoutSeconds) {
                    $reason = "local worker child exceeded hard timeout of ${childHardTimeoutSeconds}s"
                    Write-Log "Local worker slot $($job.SlotLayout.SlotId) PID $($job.Process.Id) $reason; stopping child and releasing claim" 'ERROR'
                    if (Get-Command -Name Write-PipelineEvent -ErrorAction SilentlyContinue) {
                        try {
                            Write-PipelineEvent -EventType 'local_worker_child_hard_timeout' -Stage 'local_worker_slots' -Status 'failed' -SourcePath ([string]$job.Claim.source_path) -Data @{
                                claim_id              = [string]$job.Claim.claim_id
                                slot_id               = [int]$job.SlotLayout.SlotId
                                worker_pid            = [int]$job.Process.Id
                                timeout_seconds       = [int]$childHardTimeoutSeconds
                                elapsed_seconds       = [math]::Round($elapsedSeconds, 3)
                                error_code            = 'LOCAL_WORKER_CHILD_TIMEOUT'
                            } | Out-Null
                        } catch {}
                    }
                    Stop-MediaPipelineLocalWorkerProcess -Job $job
                    $script:totalFailed = [int]$script:totalFailed + 1
                    Release-MediaPipelineLocalWorkerClaim -ClaimStorePath $claimStorePath -ClaimId ([string]$job.Claim.claim_id) -Status 'failed_child_timeout' -Reason $reason | Out-Null
                    $active.Remove($slotKey)
                    Invalidate-ProcessedIndexCache
                    continue
                }
                $heartbeatMissingPastGrace = ($heartbeatGraceSeconds -gt 0 -and $null -eq $heartbeatAgeSeconds -and $elapsedSeconds -ge $heartbeatGraceSeconds)
                $heartbeatStalePastGrace = ($heartbeatGraceSeconds -gt 0 -and $null -ne $heartbeatAgeSeconds -and $heartbeatAgeSeconds -ge $heartbeatGraceSeconds)
                if ($heartbeatMissingPastGrace -or $heartbeatStalePastGrace) {
                    $heartbeatAgeForEvidence = if ($null -eq $heartbeatAgeSeconds) { [int]$elapsedSeconds } else { [int]$heartbeatAgeSeconds }
                    $reason = "local worker child heartbeat stale for ${heartbeatAgeForEvidence}s (grace ${heartbeatGraceSeconds}s)"
                    Write-Log "Local worker slot $($job.SlotLayout.SlotId) PID $($job.Process.Id) $reason; stopping child and releasing claim" 'ERROR'
                    if (Get-Command -Name Write-PipelineEvent -ErrorAction SilentlyContinue) {
                        try {
                            Write-PipelineEvent -EventType 'local_worker_child_stale_heartbeat' -Stage 'local_worker_slots' -Status 'failed' -SourcePath ([string]$job.Claim.source_path) -Data @{
                                claim_id              = [string]$job.Claim.claim_id
                                slot_id               = [int]$job.SlotLayout.SlotId
                                worker_pid            = [int]$job.Process.Id
                                heartbeat_path        = [string]$job.SlotLayout.HeartbeatFile
                                heartbeat_age_seconds = [int]$heartbeatAgeForEvidence
                                heartbeat_missing     = [bool]$heartbeatMissingPastGrace
                                grace_seconds         = [int]$heartbeatGraceSeconds
                                elapsed_seconds       = [math]::Round($elapsedSeconds, 3)
                                error_code            = 'LOCAL_WORKER_CHILD_STALE_HEARTBEAT'
                            } | Out-Null
                        } catch {}
                    }
                    Stop-MediaPipelineLocalWorkerProcess -Job $job
                    $script:totalFailed = [int]$script:totalFailed + 1
                    Release-MediaPipelineLocalWorkerClaim -ClaimStorePath $claimStorePath -ClaimId ([string]$job.Claim.claim_id) -Status 'failed_child_stale_heartbeat' -Reason $reason | Out-Null
                    $active.Remove($slotKey)
                    Invalidate-ProcessedIndexCache
                }
                continue
            }
            $exitCode = $job.Process.ExitCode
            $result = $null
            $resultFileExists = Test-Path -LiteralPath $job.SlotLayout.ResultFile -PathType Leaf
            $resultReadError = ''
            try {
                if ($resultFileExists) {
                    $result = Read-MediaPipelineJsonFile -Path $job.SlotLayout.ResultFile
                }
            } catch {
                $resultReadError = [string]$_
                Write-Log "Local worker slot $($job.SlotLayout.SlotId) result read failed: $_" 'WARN'
            }
            $completion = Resolve-MediaPipelineLocalWorkerSlotCompletion `
                -ExitCode $exitCode `
                -Result $result `
                -ResultFileExists:$resultFileExists `
                -ResultReadError $resultReadError `
                -Claim $job.Claim `
                -OwnerRunId $script:PipelineRunId
            $status = [string]$completion.Status
            $reason = [string]$completion.Reason
            if ([bool]$completion.ApplyCounters) {
                Update-MediaPipelineParentCountersFromWorkerResult -Result $result -IsTV:([bool]$job.Entry.IsTV)
            }
            if ([bool]$completion.CountSyntheticFailure) {
                $script:totalFailed = [int]$script:totalFailed + 1
            }
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
