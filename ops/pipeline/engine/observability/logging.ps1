# ==============================================================================
# ops\pipeline\engine\observability\logging.ps1
# ==============================================================================
# Logging primitives extracted from MediaPipeline.ps1.
#
# Dot-sourced (NOT a `.psm1` module) so all of the following stay in the
# main script's scope and don't need to be re-plumbed as parameters:
#
#   $LogFile                   — absolute path to the rolling log file
#   $logLock                   — named OS mutex for cross-process log writes
#   $script:ConsoleLogLevel    — ERROR/WARN/INFO/DEBUG threshold for stdout
#   $script:FileLogLevel       — same threshold for the log file
#   $script:LogRetentionDays   — *.log.old retention window
#   $script:StartupWarnings    — list filled before logging is initialised,
#                                replayed via Write-StartupWarnings once the
#                                log file is ready.
#
# Functions in here are split into two phases:
#
#   Phase A (must run before config loading):
#     Add-StartupWarning  — appends to $script:StartupWarnings AND writes a
#                           yellow Write-Host line. Safe to call before the
#                           log file path is known.
#
#   Phase B (must run after $LogFile is defined and Invoke-LogRotation has
#   created the parent directory):
#     Invoke-LogRotation, Get-LogLevelRank, Should-WriteLog, Write-Log,
#     DebugLog, Write-StartupWarnings, Get-EffectiveConfigSummary,
#     Write-EffectiveConfigSummary, Write-StartupEnvironmentSummary
#
# The split matters because the main script calls Add-StartupWarning during
# config validation (well before the log file directory has been created),
# but the rest of the helpers can't run until LocalBase is resolved.
# ==============================================================================

# --- Phase A: startup-warning collector --------------------------------------
# This block runs at dot-source time. Initialises the list once; if the file
# is dot-sourced more than once (it shouldn't be) we keep the existing list
# rather than discard accumulated warnings.
if (-not $script:StartupWarnings) {
    $script:StartupWarnings = [System.Collections.Generic.List[string]]::new()
}

function Add-StartupWarning {
    param([string]$Message)
    if ([string]::IsNullOrWhiteSpace($Message)) { return }
    [void]$script:StartupWarnings.Add($Message)
    Write-Host "WARN: $Message" -ForegroundColor Yellow
}

# --- Phase B: log file + Write-Log -------------------------------------------

function Invoke-LogRotation {
    $acquired = $false
    try {
        if ($logLock.WaitOne(2000)) {
            $acquired = $true
            if ((Test-Path $LogFile) -and (Get-Item $LogFile).Length -gt 100MB) {
                $archive = $LogFile -replace '\.log$', "_$(Get-Date -Format 'yyyyMMdd_HHmmss').log.old"
                Move-Item $LogFile $archive -Force
            }
            $cutoff = (Get-Date).AddDays(-$script:LogRetentionDays)
            Get-ChildItem -LiteralPath (Split-Path $LogFile -Parent) -Filter "*.log.old" -ErrorAction SilentlyContinue |
                Where-Object { $_.LastWriteTime -lt $cutoff } |
                Remove-Item -Force -ErrorAction SilentlyContinue
        }
    } catch { Write-Host "Log rotation error: $_" }
    finally  { if ($acquired) { $logLock.ReleaseMutex() } }
}

function Get-LogLevelRank {
    param([string]$Level)
    switch (($Level ?? 'INFO').ToUpperInvariant()) {
        'ERROR' { return 0 }
        'WARN'  { return 1 }
        'INFO'  { return 2 }
        'DEBUG' { return 3 }
        default { return 2 }
    }
}

function Should-WriteLog {
    param(
        [string]$MessageLevel,
        [string]$TargetLevel
    )
    return (Get-LogLevelRank $MessageLevel) -le (Get-LogLevelRank $TargetLevel)
}

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    $line = "$timestamp [$Level] $Message"
    if (Should-WriteLog -MessageLevel $Level -TargetLevel $script:ConsoleLogLevel) {
        switch ($Level) {
            "ERROR" { Write-Host $line -ForegroundColor Red    }
            "WARN"  { Write-Host $line -ForegroundColor Yellow }
            "DEBUG" { Write-Host $line -ForegroundColor Gray   }
            default { Write-Host $line }
        }
    }
    $acquired = $false
    try {
        if ((Should-WriteLog -MessageLevel $Level -TargetLevel $script:FileLogLevel) -and $logLock.WaitOne(2000)) {
            $acquired = $true
            Add-Content -LiteralPath $LogFile -Value $line -ErrorAction SilentlyContinue
        }
    } catch {
        Write-Host "Log write error: $_" -ForegroundColor Yellow
    } finally { if ($acquired) { $logLock.ReleaseMutex() } }
}

function ConvertTo-PipelineEventData {
    param($Data)

    if ($null -eq $Data) { return [ordered]@{} }
    if ($Data -is [System.Collections.IDictionary]) {
        $map = [ordered]@{}
        foreach ($key in $Data.Keys) {
            if ($null -eq $key) { continue }
            $map[[string]$key] = $Data[$key]
        }
        return $map
    }

    $objectMap = [ordered]@{}
    foreach ($prop in $Data.PSObject.Properties) {
        $objectMap[$prop.Name] = $prop.Value
    }
    return $objectMap
}

function Write-JsonLineAppend {
    param(
        [Parameter(Mandatory)] [string] $Path,
        [Parameter(Mandatory)] $Payload,
        [int] $Depth = 8,
        [switch] $UseLogLock
    )

    $dir = Split-Path -Parent $Path
    if ($dir -and -not (Test-Path -LiteralPath $dir)) {
        [System.IO.Directory]::CreateDirectory($dir) | Out-Null
    }

    $line = $Payload | ConvertTo-Json -Depth $Depth -Compress
    $acquired = $false
    try {
        if ($UseLogLock -and $logLock) {
            $acquired = $logLock.WaitOne(2000)
        }
        [System.IO.File]::AppendAllText(
            $Path,
            ($line + [Environment]::NewLine),
            [System.Text.Encoding]::UTF8
        )
        return $true
    } finally {
        if ($acquired) { $logLock.ReleaseMutex() }
    }
}

function Write-PipelineEvent {
    param(
        [Parameter(Mandatory)] [string]$EventType,
        [string]$Stage = '',
        [string]$SourcePath = '',
        [string]$Route = '',
        [string]$Status = '',
        [string]$JobId = '',
        [string]$CorrelationId = '',
        $Data = $null
    )

    try {
        $eventPath = if ($script:PipelineEventLogFile) { [string]$script:PipelineEventLogFile } elseif ($PipelineEventLogFile) { [string]$PipelineEventLogFile } else { '' }
        if ([string]::IsNullOrWhiteSpace($eventPath)) { return $false }

        $eventDir = Split-Path -Parent $eventPath
        if ($eventDir -and -not (Test-Path -LiteralPath $eventDir)) {
            [System.IO.Directory]::CreateDirectory($eventDir) | Out-Null
        }

        $timestamp = (Get-Date -Format 'o')
        $resolvedJobId = if (-not [string]::IsNullOrWhiteSpace($JobId)) { $JobId } elseif ($script:CurrentJobId) { [string]$script:CurrentJobId } else { '' }
        $resolvedCorrelationId = if (-not [string]::IsNullOrWhiteSpace($CorrelationId)) { $CorrelationId } elseif ($script:PipelineRunId) { [string]$script:PipelineRunId } else { '' }

        $payload = [ordered]@{
            schema_version   = 'pipeline_event.v1'
            event_id         = [guid]::NewGuid().ToString('N')
            event_type       = $EventType
            timestamp        = $timestamp
            created_at       = $timestamp
            run_id           = $resolvedCorrelationId
            correlation_id   = $resolvedCorrelationId
            job_id           = $resolvedJobId
            product_version  = if ($script:ProductVersion) { [string]$script:ProductVersion } else { '' }
            pipeline_version = if ($script:PipelineVersion) { [string]$script:PipelineVersion } else { '' }
            stage            = $Stage
            route            = $Route
            status           = $Status
            source_path      = $SourcePath
            data             = ConvertTo-PipelineEventData $Data
        }
        return (Write-JsonLineAppend -Path $eventPath -Payload $payload -Depth 8 -UseLogLock)
    } catch {
        Write-Log "Pipeline event write failed: $_" "WARN"
        return $false
    }
}

function DebugLog {
    param([string]$msg)
    if ((Should-WriteLog -MessageLevel 'DEBUG' -TargetLevel $script:ConsoleLogLevel) -or
        (Should-WriteLog -MessageLevel 'DEBUG' -TargetLevel $script:FileLogLevel)) {
        Write-Log $msg "DEBUG"
    }
}

function Write-StartupWarnings {
    if (-not $script:StartupWarnings -or $script:StartupWarnings.Count -eq 0) { return }

    Write-Log "CONFIG ADJUSTMENTS APPLIED: $($script:StartupWarnings.Count) warning(s)" "WARN"
    foreach ($warning in $script:StartupWarnings) {
        Write-Log $warning "WARN"
    }
}

function Get-EffectiveConfigSummary {
    $showOverrideSummary = if ($script:ShowOverrides.Count -gt 0) {
        "$($script:ShowOverrides.Count) pattern(s)"
    } else {
        "(none)"
    }
    return [ordered]@{
        RunMode               = if ($ValidateOnly) { 'validate-only' } elseif ($Once) { 'single-pass' } else { 'continuous' }
        ConfigFile            = $configPath
        SourceMovies          = $SourceMovies
        SourceTV              = $SourceTV
        Outsource             = $Outsource
        LocalBase             = $LocalBase
        SleepSeconds          = $SleepSeconds
        SourceScanIntervalSeconds = $script:SourceScanIntervalSeconds
        SourceScanTimeoutSeconds  = $script:SourceScanTimeoutSeconds
        ProcessedIndexRefreshSeconds = $script:ProcessedIndexRefreshSeconds
        IndexScanTimeoutSeconds = $script:IndexScanTimeoutSeconds
        RobocopyTimeoutSeconds  = $script:RobocopyTimeoutSeconds
        CleanupRemoteStaging    = $script:CleanupRemoteStaging
        CleanupStaleAgeHours    = $script:CleanupStaleAgeHours
        AllowSystemTools        = $script:AllowSystemTools
        TransientFailureRetryLimit = $script:TransientFailureRetryLimit
        EncodeThresholdGB     = $EncodeThresholdGB
        TVEncodeThresholdGB   = $TVEncodeThresholdGB
        VideoCodec            = $VideoCodec
        VideoPreset           = $VideoPreset
        VideoQuality          = $VideoQuality
        OutputContainer       = $OutputContainer
        DropAssAfterConversion = $DropAssAfterConversion
        DropTx3gAfterConversion = $script:DropTx3gAfterConversion
        DropBdpgsAfterConversion = $script:DropBdpgsAfterConversion
        CreateExternalTx3gSrtSidecars = $script:CreateExternalTx3gSrtSidecars
        ConvertBdpgsToSrt     = $script:ConvertBdpgsToSrt
        BdpgsOcrToolPath      = $script:BdpgsOcrToolPath
        MergeAdjacent         = $script:MergeAdjacent
        MergeThresholdMs      = $script:MergeThresholdMs
        RemoveKaraoke         = $script:RemoveKaraoke
        TreatAssSignsSongsAsForced = $script:TreatAssSignsSongsAsForced
        TreatTx3gSignsSongsAsForced = $script:TreatTx3gSignsSongsAsForced
        TreatBdpgsSignsSongsAsForced = $script:TreatBdpgsSignsSongsAsForced
        ReprocessAll          = $script:ReprocessAll
        MinPipelineVersion    = $script:MinPipelineVersion
        ConsoleLogLevel       = $script:ConsoleLogLevel
        FileLogLevel          = $script:FileLogLevel
        PriorityMarkers       = if ($script:PriorityMarkers.Count -gt 0) { $script:PriorityMarkers -join ', ' } else { '(none)' }
        ShowOverrides         = $showOverrideSummary
    }
}

function Write-EffectiveConfigSummary {
    Write-Log "===== EFFECTIVE CONFIG ====="
    foreach ($entry in (Get-EffectiveConfigSummary).GetEnumerator()) {
        Write-Log ("{0,-21}: {1}" -f $entry.Key, $entry.Value)
    }
}

function Write-StartupEnvironmentSummary {
    Write-Log "Resolved tools:"
    Write-Log "  ffmpeg   : $ffmpegPath"
    Write-Log "  ffprobe  : $ffprobePath"
    Write-Log "  mkvmerge : $mkvmergePath"
    Write-Log "  python   : $pythonPath"
    Write-Log "  subtitles: $assToSrtScript"
    Write-Log "Working paths:"
    Write-Log "  log file     : $LogFile"
    Write-Log "  progress     : $ProgressFile"
    Write-Log "  events       : $PipelineEventLogFile"
    Write-Log "  pause flag   : $PauseFlag"
    Write-Log "  stop flag    : $StopFlag"
    Write-Log "  pending push : $LocalPendingPush"
    Write-Log "  failed files : $LocalFailed"
    Write-Log "  fail markers : $LocalFailureMarkers"
    Write-Log "  fail reports : $LocalFailureReports"
    Write-Log "  rescan flag  : $RescanFlag"
}
