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

function Write-MediaPipelineStartupConfigLog {
Write-Log "===== PIPELINE START $($script:ProductVersion) (pipeline $($script:PipelineVersion)) ====="
$runMode = if ($ValidateOnly) { 'validate-only' } elseif ($WorkerChild) { 'local-worker-child' } elseif ($DrainPendingPushes) { 'drain-pending-pushes' } elseif ($Once) { 'single-pass' } else { 'continuous' }
Write-PipelineEvent -EventType 'pipeline_started' -Stage 'startup' -Status 'started' -Data @{
    run_mode    = $runMode
    config_path = $configPath
    local_base  = $LocalBase
} | Out-Null
Write-Log "Run mode      : $runMode"
Write-Log "Config file   : $configPath"
Write-Log "PowerShell    : $($PSVersionTable.PSVersion)"
Write-Log "SleepSeconds  : $SleepSeconds"
$workerSlotLog = if ($WorkerChild) { " worker_slot=$WorkerSlotId" } else { "" }
Write-Log "Parallel encodes: max=$script:MaxParallelEncodes mode=$script:ParallelEncodeMode$workerSlotLog"
Write-Log "Scan refresh  : source $($script:SourceScanIntervalSeconds)s | index $($script:ProcessedIndexRefreshSeconds)s"
Write-Log "Unknown height size: movie $EncodeThresholdGB GB | TV $TVEncodeThresholdGB GB"
Write-Log "Route size targets: 1080p movie $($script:MovieRoute1080pTargetSizeGB) GB / TV $($script:TVRoute1080pTargetSizeGB) GB | 1440p movie $($script:MovieRoute1440pTargetSizeGB) GB / TV $($script:TVRoute1440pTargetSizeGB) GB | 4K movie $($script:MovieRoute4KTargetSizeGB) GB / TV $($script:TVRoute4KTargetSizeGB) GB"
Write-Log "Codec         : $VideoCodec preset $VideoPreset CQ $VideoQuality"
Write-Log "Encode tuning : $script:EncodeTuningPreset flags=$($script:ExtraVideoFlags -join ' ')"
Write-Log "Encode ladder : $script:EncodeLadder"
Write-Log "Routing profile: $script:RoutingProfile"
Write-Log "Route buckets : 1080p <=$($script:Route1080pBucketMaxHeight)p $($script:Route1080pMaxVideoBitrateMbps) Mbps | 1440p $($script:Route1080pBucketMaxHeight + 1)-$($script:Route4KBucketMinHeight - 1)p $($script:Route1440pMaxVideoBitrateMbps) Mbps | 4K >=$($script:Route4KBucketMinHeight)p $($script:Route4KMaxVideoBitrateMbps) Mbps"
Write-Log "H.264 copy    : $script:AllowH264RemuxIfPlexCompatible (<= $($script:H264RemuxMaxBitrateMbps) Mbps, <= $($script:H264RemuxMaxHeight)p)"
Write-Log "Size guard    : $script:SizeGuardMode (default +$($script:MaxEncodeGrowthPercent)%; compatibility +$($script:CompatibilityEncodeGrowthPercent)%)"
Write-Log "Remux-safe    : $($RemuxSafeVideoCodecs -join ', ')"
Write-Log "Audio profile : $script:AudioPassthroughProfile"
Write-Log "Audio compat  : $($script:CompatibleAudioCodecs -join ', ')"
Write-Log "Audio policy  : transcode=$script:AudioTranscodeCodec $script:AudioTranscodeBitrate downmix=$script:AudioDownmixMode max_ch=$script:AudioMaxChannels allow_no_audio=$script:AllowNoAudio"
Write-Log "Drop ASS      : $DropAssAfterConversion"
$tx3gLanguageText = ($script:Tx3gExtractLanguages -join ', ')
$bdpgsLanguageText = ($script:BdpgsExtractLanguages -join ', ')
$vobSubLanguageText = ($script:VobSubExtractLanguages -join ', ')
$bdpgsOcrToolText = if ($script:BdpgsOcrToolPath) { $script:BdpgsOcrToolPath } else { '(not configured)' }
$vobSubOcrToolText = if ($script:VobSubOcrToolPath) { $script:VobSubOcrToolPath } else { '(not configured)' }
Write-Log ("Convert TX3G  : {0} (languages: {1}; drop original: {2}; external sidecars: {3}; preserve existing SRT: {4})" -f $script:ConvertTx3gToSrt, $tx3gLanguageText, $script:DropTx3gAfterConversion, $script:CreateExternalTx3gSrtSidecars, $script:Tx3gPreserveExistingSrt)
Write-Log ("Convert BDPGS : {0} (languages: {1}; drop original: {2}; OCR tool: {3})" -f $script:ConvertBdpgsToSrt, $bdpgsLanguageText, $script:DropBdpgsAfterConversion, $bdpgsOcrToolText)
Write-Log ("Convert VobSub: {0} (languages: {1}; drop original: {2}; OCR tool: {3})" -f $script:ConvertVobSubToSrt, $vobSubLanguageText, $script:DropVobSubAfterConversion, $vobSubOcrToolText)
Write-Log "Signs/Songs   : keep ASS=$($script:KeepSignsAndSongs) | ASS forced=$($script:TreatAssSignsSongsAsForced) | TX3G forced=$($script:TreatTx3gSignsSongsAsForced) | BDPGS forced=$($script:TreatBdpgsSignsSongsAsForced) | VobSub forced=$($script:TreatVobSubSignsSongsAsForced)"
Write-Log "Merge adjacent: $($script:MergeAdjacent) (threshold: $($script:MergeThresholdMs)ms)"
Write-Log "Remove karaoke: $($script:RemoveKaraoke)"
if ($script:ExcludeSubtitleStyles.Count -gt 0) {
    Write-Log "Exclude styles: $($script:ExcludeSubtitleStyles -join ', ')"
} else {
    Write-Log "Exclude styles: (using Python defaults)"
}
Write-Log "Log retention : $($script:LogRetentionDays) days"
Write-Log "Log levels    : console=$($script:ConsoleLogLevel) | file=$($script:FileLogLevel)"
Write-Log "Product ver   : $($script:ProductVersion)"
Write-Log "Pipeline ver  : $($script:PipelineVersion) (min for reprocess: $($script:MinPipelineVersion))"
Write-Log "ReprocessAll  : $($script:ReprocessAll)"
Write-Log "Deferred publish : $($script:DeferredPublish)"
Write-Log "Aggressive TV parse : $($script:AggressiveEpisodeParsing)"
Write-Log ("CPU fallback  : {0} CRF {1} preset {2} threads={3} (process priority: {4})" -f (Get-MediaVideoCodecLibx265Name), $script:FallbackCpuQuality, $script:CpuEncodePreset, $(if ($script:CpuEncodeMaxThreads -gt 0) { [string]$script:CpuEncodeMaxThreads } else { 'auto' }), $script:CpuEncodeProcessPriority)
Write-Log "FFmpeg timeouts: encode $($script:FFmpegEncodeTimeoutSeconds)s | encode-cpu $($script:FFmpegCpuEncodeTimeoutSeconds)s | remux $($script:FFmpegRemuxTimeoutSeconds)s | mkvmerge $($script:MkvmergeRemuxTimeoutSeconds)s | subtitle extract $($script:SubtitleExtractTimeoutSeconds)s | subtitle probe $($script:SubtitleProbeTimeoutSeconds)s | BDPGS OCR $($script:BdpgsOcrTimeoutSeconds)s | VobSub OCR $($script:VobSubOcrTimeoutSeconds)s"

# F-new-2 — probe NVENC availability once at startup and cache. The
# probe binds to the configured VideoCodec when it's an nvenc encoder so
# we test the same codec the pipeline will try first per file.
$nvencTestEncoder = if ($VideoCodec -match 'nvenc') { $VideoCodec } else { 'hevc_nvenc' }
$nvencProbe = Test-NvencAvailable -TestEncoder $nvencTestEncoder
$script:NvencAvailableProbe = $nvencProbe
if ($nvencProbe.Available) {
    Write-Log "NVENC probe   : OK ($nvencTestEncoder usable on this host)"
} else {
    $reasonText = if ($nvencProbe.Reason) { $nvencProbe.Reason } else { 'unknown' }
    Write-Log "NVENC probe   : NOT AVAILABLE ($reasonText) — primary encode will fall back to libx265 (CPU) for every file" "WARN"
    Write-Log "                CPU encode preset=$script:CpuEncodePreset CRF=$script:FallbackCpuQuality timeout=$($script:FFmpegCpuEncodeTimeoutSeconds)s — expect multi-hour runs per file" "WARN"
    Write-PipelineEvent -EventType 'gpu_unavailable' -Stage 'startup' -Status 'warn' -Data @{
        encoder         = $nvencTestEncoder
        reason          = [string]$nvencProbe.Reason
        encoder_listed  = [bool]$nvencProbe.EncoderListMatch
        runtime_probed  = [bool]$nvencProbe.Probed
    } | Out-Null
}
Write-Log "Copy/scan timeouts: robocopy $($script:RobocopyTimeoutSeconds)s | source scan $($script:SourceScanTimeoutSeconds)s | index scan $($script:IndexScanTimeoutSeconds)s"
Write-Log "Output size mult: $($script:OutputSizeMultiplier)x (for pre-encode disk check)"
Write-Log "Priority tags : $(if ($script:PriorityMarkers.Count -gt 0) { $script:PriorityMarkers -join ', ' } else { '(none)' })"
Write-StartupEnvironmentSummary
}
