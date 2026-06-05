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
