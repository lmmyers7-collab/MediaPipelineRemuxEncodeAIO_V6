# ==============================================================================
# ops\pipeline\engine\queue\worker_process.ps1
# ==============================================================================
# Extracted from ops\pipeline\engine\queue\local_worker_slots.ps1. Keep function names
# stable; local_worker_slots.ps1 dot-sources this file for compatibility.
# ==============================================================================

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

function Join-MediaPipelineProcessArgument {
    param([string] $Value)

    if ($null -eq $Value) { return '""' }
    $text = [string]$Value
    if ($text -notmatch '[\s"]') { return $text }
    return '"' + ($text -replace '\\(?=")', '\\' -replace '"', '\"') + '"'
}

function Save-MediaPipelineLocalWorkerResultDiagnostic {
    param(
        [string] $ResultPath = '',
        [string] $ClaimId = '',
        [string] $Reason = ''
    )

    if ([string]::IsNullOrWhiteSpace($ResultPath) -or -not (Test-Path -LiteralPath $ResultPath -PathType Leaf)) {
        return [pscustomobject]@{ Archived = $false; Path = ''; Error = ''; Reason = [string]$Reason }
    }

    try {
        $resultDir = Split-Path -Parent $ResultPath
        if ([string]::IsNullOrWhiteSpace($resultDir)) {
            return [pscustomobject]@{ Archived = $false; Path = ''; Error = 'result path has no parent directory'; Reason = [string]$Reason }
        }
        $archiveDir = Join-Path $resultDir 'ResultArchive'
        New-Item -ItemType Directory -Path $archiveDir -Force | Out-Null
        $safeClaim = ([string]$ClaimId -replace '[^A-Za-z0-9._-]+', '-').Trim('.-_')
        if ([string]::IsNullOrWhiteSpace($safeClaim)) { $safeClaim = 'unclaimed' }
        $stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssfffffffZ')
        $archivePath = Join-Path $archiveDir "$stamp-$safeClaim-worker_result.json"
        Copy-Item -LiteralPath $ResultPath -Destination $archivePath -Force
        return [pscustomobject]@{ Archived = $true; Path = $archivePath; Error = ''; Reason = [string]$Reason }
    } catch {
        return [pscustomobject]@{ Archived = $false; Path = ''; Error = [string]$_; Reason = [string]$Reason }
    }
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

    $spawnRequestedAt = (Get-Date).ToUniversalTime()
    $spawnStopwatch = [System.Diagnostics.Stopwatch]::StartNew()
    Initialize-MediaPipelineWorkerSlotLayout -SlotLayout $SlotLayout | Out-Null
    Save-MediaPipelineLocalWorkerResultDiagnostic `
        -ResultPath ([string]$SlotLayout.ResultFile) `
        -ClaimId ([string]$Claim.claim_id) `
        -Reason 'slot reuse before worker child start' | Out-Null
    foreach ($path in @($SlotLayout.ResultFile, $SlotLayout.HeartbeatFile, $SlotLayout.ProgressFile, $SlotLayout.StdoutLog, $SlotLayout.StderrLog)) {
        Remove-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
    }
    $runMonitorJobId = if ($Claim.PSObject.Properties['run_monitor_job_id']) { [string]$Claim.run_monitor_job_id } else { '' }
    $metadata = [ordered]@{
        schema_version = 'local_worker_metadata.v1'
        slot_id        = [int]$SlotLayout.SlotId
        claim_id       = [string]$Claim.claim_id
        source_path    = [string]$Claim.source_path
        owner_run_id   = [string]$OwnerRunId
        run_monitor_job_id = $runMonitorJobId
        result_path    = [string]$SlotLayout.ResultFile
        heartbeat_path = [string]$SlotLayout.HeartbeatFile
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
        '-WorkerJobId', $runMonitorJobId,
        '-WorkerResultPath', ([string]$SlotLayout.ResultFile),
        '-WorkerHeartbeatPath', ([string]$SlotLayout.HeartbeatFile)
    )
    $argumentLine = ($arguments | ForEach-Object { Join-MediaPipelineProcessArgument -Value ([string]$_) }) -join ' '
    try {
        $process = Start-Process -FilePath $PowerShellPath `
            -ArgumentList $argumentLine `
            -WorkingDirectory (Split-Path -Parent $ScriptPath) `
            -RedirectStandardOutput $SlotLayout.StdoutLog `
            -RedirectStandardError $SlotLayout.StderrLog `
            -WindowStyle Hidden `
            -PassThru
    } finally {
        $spawnStopwatch.Stop()
    }
    $process | Add-Member -NotePropertyName MediaPipelineSpawnRequestedAt -NotePropertyValue $spawnRequestedAt.ToString('o') -Force
    $process | Add-Member -NotePropertyName MediaPipelineSpawnDurationMs -NotePropertyValue ([math]::Round($spawnStopwatch.Elapsed.TotalMilliseconds, 3)) -Force
    return $process
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
