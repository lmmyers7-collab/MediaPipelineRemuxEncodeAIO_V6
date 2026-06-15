# ==============================================================================
# ops\pipeline\engine\queue\worker_claim_store.ps1
# ==============================================================================
# Extracted from ops\pipeline\engine\queue\local_worker_slots.ps1. Keep function names
# stable; local_worker_slots.ps1 dot-sources this file for compatibility.
# ==============================================================================

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

function Get-MediaPipelineProcessStartTimeUtcText {
    param([object] $ProcessId)

    try {
        $pidValue = [int]$ProcessId
        if ($pidValue -le 0) { return '' }
        $proc = Get-Process -Id $pidValue -ErrorAction SilentlyContinue
        if ($null -eq $proc -or $proc.HasExited) { return '' }
        return $proc.StartTime.ToUniversalTime().ToString('o')
    } catch {
        return ''
    }
}

function Test-MediaPipelineUtcTimestampMatch {
    param(
        [object] $Expected,
        [object] $Actual,
        [double] $ToleranceSeconds = 2
    )

    try {
        if ($null -eq $Expected -or $null -eq $Actual) { return $false }
        $expectedTime = ([datetime]$Expected).ToUniversalTime()
        $actualTime = ([datetime]$Actual).ToUniversalTime()
        return ([math]::Abs(($expectedTime - $actualTime).TotalSeconds) -le $ToleranceSeconds)
    } catch {
        return $false
    }
}

function Test-MediaPipelineLocalWorkerClaimIdentity {
    param(
        [Parameter(Mandatory)] $Claim,
        [string] $CurrentRunId = ''
    )

    $workerPid = if ($Claim.PSObject.Properties['worker_pid']) { $Claim.worker_pid } else { $null }
    if (-not (Test-MediaPipelineProcessAlive -ProcessId $workerPid)) { return $false }

    $workerStartTime = if ($Claim.PSObject.Properties['worker_start_time']) { $Claim.worker_start_time } else { $null }
    if ($null -eq $workerStartTime -or [string]::IsNullOrWhiteSpace([string]$workerStartTime)) { return $false }
    $actualStartTime = Get-MediaPipelineProcessStartTimeUtcText -ProcessId $workerPid
    if ([string]::IsNullOrWhiteSpace($actualStartTime) -or -not (Test-MediaPipelineUtcTimestampMatch -Expected $workerStartTime -Actual $actualStartTime)) { return $false }

    $metadataPath = if ($Claim.PSObject.Properties['worker_metadata_path']) { [string]$Claim.worker_metadata_path } else { '' }
    if ([string]::IsNullOrWhiteSpace($metadataPath) -or -not (Test-Path -LiteralPath $metadataPath -PathType Leaf)) { return $false }

    $metadata = $null
    try { $metadata = Read-MediaPipelineJsonFile -Path $metadataPath } catch { $metadata = $null }
    if (-not $metadata) { return $false }
    if (-not $metadata.PSObject.Properties['schema_version'] -or [string]$metadata.schema_version -ne 'local_worker_metadata.v1') { return $false }
    if (-not $metadata.PSObject.Properties['claim_id'] -or [string]$metadata.claim_id -ne [string]$Claim.claim_id) { return $false }

    $ownerRun = if ($Claim.PSObject.Properties['owner_run_id']) { [string]$Claim.owner_run_id } else { '' }
    if (-not [string]::IsNullOrWhiteSpace($CurrentRunId) -and $ownerRun -ne $CurrentRunId) { return $false }
    if (-not $metadata.PSObject.Properties['owner_run_id'] -or [string]$metadata.owner_run_id -ne $ownerRun) { return $false }

    if ($metadata.PSObject.Properties['worker_pid'] -and [string]$metadata.worker_pid -ne [string]$workerPid) { return $false }
    if ($metadata.PSObject.Properties['worker_start_time'] -and -not (Test-MediaPipelineUtcTimestampMatch -Expected $workerStartTime -Actual $metadata.worker_start_time)) { return $false }

    $resultPath = if ($Claim.PSObject.Properties['result_path']) { [string]$Claim.result_path } else { '' }
    if (-not [string]::IsNullOrWhiteSpace($resultPath) -and $metadata.PSObject.Properties['result_path'] -and [string]$metadata.result_path -ne $resultPath) {
        return $false
    }

    return $true
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
            $identityVerified = Test-MediaPipelineLocalWorkerClaimIdentity -Claim $claim -CurrentRunId $CurrentRunId
            if ($identityVerified) { continue }

            if (-not [string]::IsNullOrWhiteSpace($resultPath) -and (Test-Path -LiteralPath $resultPath -PathType Leaf)) {
                $releasedAt = Get-MediaPipelineLocalWorkerTimestamp
                $claim.status = 'released_stale_result'
                $claim | Add-Member -NotePropertyName released_at -NotePropertyValue $releasedAt -Force
                $claim | Add-Member -NotePropertyName updated_at -NotePropertyValue $releasedAt -Force
                $claim | Add-Member -NotePropertyName release_reason -NotePropertyValue 'released stale worker claim with no live worker process; prior result file remains available for diagnostics' -Force
                $claim | Add-Member -NotePropertyName recovery_note -NotePropertyValue 'released because no current controller can finalize the prior worker result; source may be claimed again' -Force
                $changed = $true
                continue
            }

            $claimedAt = $null
            try { $claimedAt = [datetime]::Parse([string]$claim.claimed_at) } catch {}
            $ageSeconds = if ($claimedAt) { ($now - $claimedAt).TotalSeconds } else { [double]::MaxValue }
            $ownerRun = if ($claim.PSObject.Properties['owner_run_id']) { [string]$claim.owner_run_id } else { '' }
            if ($ownerRun -ne $CurrentRunId -or $ageSeconds -ge $ClaimStaleSeconds -or [string]::IsNullOrWhiteSpace([string]$workerPid)) {
                $claim.status = 'released_stale'
                $releasedAt = Get-MediaPipelineLocalWorkerTimestamp
                $claim | Add-Member -NotePropertyName released_at -NotePropertyValue $releasedAt -Force
                $claim | Add-Member -NotePropertyName updated_at -NotePropertyValue $releasedAt -Force
                $claim | Add-Member -NotePropertyName recovery_note -NotePropertyValue 'released because no verified live worker process owned the claim' -Force
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
            queue_index    = Get-MediaPipelineQueueEntryRunValue -Entry $Entry -RunProperty 'RunQueueIndex' -BucketProperty 'QueueIndex'
            queue_total    = Get-MediaPipelineQueueEntryRunValue -Entry $Entry -RunProperty 'RunQueueTotal' -BucketProperty 'QueueTotal'
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
