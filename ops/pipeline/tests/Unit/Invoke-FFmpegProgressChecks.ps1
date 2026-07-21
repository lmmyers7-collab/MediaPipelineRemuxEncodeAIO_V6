[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$testsRoot = Split-Path -Parent $PSCommandPath
$pipelineRoot = Split-Path -Parent (Split-Path -Parent $testsRoot)
$repoRoot = Split-Path -Parent (Split-Path -Parent $pipelineRoot)
if (-not (Test-Path -LiteralPath (Join-Path $repoRoot 'AGENTS.md') -PathType Leaf)) {
    throw "Unable to resolve repository root from $PSCommandPath."
}
if (-not (Test-Path -LiteralPath (Join-Path $repoRoot 'ops\pipeline\engine') -PathType Container)) {
    throw "Resolved repository root is missing ops\pipeline\engine: $repoRoot"
}

function Assert-True {
    param(
        [bool]$Condition,
        [string]$Message
    )
    if (-not $Condition) { throw $Message }
}

function Assert-Equal {
    param(
        $Actual,
        $Expected,
        [string]$Message
    )
    if ($Actual -ne $Expected) {
        throw "$Message Expected '$Expected' but got '$Actual'."
    }
}

function Assert-PathUnderRoot {
    param([string] $Path, [string] $Root, [string] $Message)
    $fullPath = [System.IO.Path]::GetFullPath($Path)
    $fullRoot = [System.IO.Path]::GetFullPath($Root).TrimEnd('\') + '\'
    if (-not $fullPath.StartsWith($fullRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "$Message Path '$fullPath' is outside '$fullRoot'."
    }
}

function Write-Log {
    param(
        [string]$Message,
        [string]$Level = 'INFO'
    )
    $script:CapturedLogs += ,([pscustomobject]@{ Message = $Message; Level = $Level })
}

function DebugLog {
    param([string]$Message)
}

function Set-ProgressStage {
    param(
        [string]$Stage,
        [string]$Status,
        [string]$Route,
        $Percent,
        [switch]$SaveNow
    )
    $script:CapturedProgress += ,([pscustomobject]@{
        Stage = $Stage
        Route = $Route
        Percent = $Percent
        PercentWasBound = $PSBoundParameters.ContainsKey('Percent')
        SaveNow = [bool]$SaveNow
    })
}

function New-MediaPipelineCurrentStageNativePollHandler {
    param(
        [string]$Stage,
        [string]$Status = '',
        [string]$Route = '',
        [double]$MinimumIntervalSeconds = 15,
        [switch]$RefreshActiveAudioTracks,
        [string]$EvidenceSource = ''
    )
    $setProgressCommand = Get-Command -Name Set-ProgressStage -ErrorAction Stop
    return {
        param($ElapsedSeconds, $Process)
        & $setProgressCommand -Stage $Stage -Status $Status -Route $Route -SaveNow
    }.GetNewClosure()
}

function Set-MediaPipelineCurrentRunMonitorStage {
    param(
        [string]$StageId,
        [string]$State,
        [string]$Detail = '',
        [string]$ReasonCode = '',
        [string]$EvidenceSource = '',
        $Numerator = $null,
        $Denominator = $null,
        [switch]$Indeterminate,
        [switch]$NumericOnly
    )
    $script:CapturedMonitorStages += ,([pscustomobject]@{
        StageId = $StageId; State = $State; Detail = $Detail
        ReasonCode = $ReasonCode; EvidenceSource = $EvidenceSource
    })
}

function Start-MediaPipelineRunMonitorAudioWork {
    param([string]$RunId, [string]$JobId, [string]$EvidenceSource, [string]$Detail = '')
    $script:CapturedAudioWork += ,([pscustomobject]@{
        Event = 'started'; RunId = $RunId; JobId = $JobId; EvidenceSource = $EvidenceSource; Detail = $Detail
    })
}

function Update-MediaPipelineRunMonitorActiveTrackHeartbeat {
    param(
        [string]$Kind,
        [string]$RunId,
        [string]$JobId,
        [string]$EvidenceSource,
        [string]$EvidenceProvenance,
        $Numerator = $null,
        $Denominator = $null
    )
    $script:CapturedAudioWork += ,([pscustomobject]@{
        Event = 'progress'; Kind = $Kind; RunId = $RunId; JobId = $JobId
        EvidenceSource = $EvidenceSource; EvidenceProvenance = $EvidenceProvenance
        Numerator = $Numerator; Denominator = $Denominator
    })
}

function Complete-MediaPipelineRunMonitorAudioWork {
    param([string]$RunId, [string]$JobId, [string]$EvidenceSource, [string]$Detail = '')
    $script:CapturedAudioWork += ,([pscustomobject]@{
        Event = 'completed'; RunId = $RunId; JobId = $JobId; EvidenceSource = $EvidenceSource; Detail = $Detail
    })
}

function End-MediaPipelineRunMonitorAudioWorkAttempt {
    param(
        [string]$RunId,
        [string]$JobId,
        [string]$EvidenceSource,
        [string]$ReasonCode = '',
        [string]$Detail = ''
    )
    $script:CapturedAudioWork += ,([pscustomobject]@{
        Event = 'attempt_ended'; RunId = $RunId; JobId = $JobId; EvidenceSource = $EvidenceSource
        ReasonCode = $ReasonCode; Detail = $Detail
    })
}

function ConvertTo-MediaPipelineRunMonitorStageId {
    param([string]$PipelineStage)
    switch -Regex (([string]$PipelineStage).Trim().ToLowerInvariant()) {
        '^(encode|encoding|encode_cpu|encode_video|transcode)$' { return 'transcode' }
        '^(encode_mux|remux_av|remux_mux)$' { return 'mux' }
        default { return '' }
    }
}

function Write-PipelineEvent {
    param(
        [string]$EventType,
        [string]$Stage = '',
        [string]$Route = '',
        [string]$Status = '',
        [string]$SourcePath = '',
        $Data = $null
    )
    $script:CapturedEvents += ,([pscustomobject]@{
        EventType = $EventType
        Stage = $Stage
        Route = $Route
        Status = $Status
        SourcePath = $SourcePath
        Data = $Data
    })
    return $true
}

function Format-NativeCommandLine {
    param(
        [string]$FilePath,
        [array]$ArgumentList = @()
    )
    return (@($FilePath) + @($ArgumentList | ForEach-Object { [string]$_ })) -join ' '
}

function Save-ReproCommand {
    param(
        [string]$ToolName,
        [string]$Executable,
        [array]$ArgumentList,
        [string]$Stage
    )
    $script:ReproSaves++
    return "repro-$Stage.cmd"
}

. (Join-Path $repoRoot 'ops\pipeline\engine\shared\native_process_contracts.ps1')
. (Join-Path $repoRoot 'ops\pipeline\engine\decide\size_policy.ps1')
. (Join-Path $repoRoot 'ops\pipeline\engine\process\tool_log_lifecycle.ps1')
. (Join-Path $repoRoot 'ops\pipeline\engine\process\ffmpeg_progress.ps1')

$script:CapturedLogs = @()
$script:CapturedProgress = @()
$script:CapturedEvents = @()
$script:CapturedMonitorStages = @()
$script:CapturedAudioWork = @()
$script:ReproSaves = 0
$script:FFmpegProgressWriteStepPercent = 25
$mkvmergePath = 'mkvmerge.exe'
$StopFlag = Join-Path ([System.IO.Path]::GetTempPath()) ("mediapipeline-mkvmerge-warning-{0}.stop" -f ([Guid]::NewGuid().ToString('N')))

function Invoke-NativeProcess {
    param(
        [string]$FilePath,
        [array]$ArgumentList,
        [int]$TimeoutSeconds = 0,
        [string]$StopFlagPath = '',
        [string]$Label = '',
        [int]$MaxStdoutChars = 0,
        [int]$MaxStderrChars = 0,
        [scriptblock]$StdoutLineHandler,
        [scriptblock]$PollHandler,
        [int]$PollMilliseconds = 100
    )
    if ($PollHandler) {
        & $PollHandler 1 $null | Out-Null
        & $PollHandler 16 $null | Out-Null
        & $PollHandler 31 $null | Out-Null
    }
    if ($StdoutLineHandler) {
        & $StdoutLineHandler '#GUI#progress 33%' 'stdout'
        & $StdoutLineHandler 'Progress: 100%' 'stdout'
    }
    return New-NativeCommandResult -ExitCode 1 -Stdout '#GUI#progress 33%' -Stderr 'mkvmerge warning text' -TimedOut:$false -Stopped:$false -ErrorCode 'NATIVE_EXIT_1'
}

try {
    Assert-Equal (Get-MkvmergeProgressPercentFromLine -Line '#GUI#progress 42%') 42 'GUI mkvmerge progress parsing changed.'
    Assert-Equal (Get-MkvmergeProgressPercentFromLine -Line 'Progress: 125%') 100 'mkvmerge progress clamp changed.'

    $result = Invoke-MkvmergeWithProgress `
        -ArgumentList @('--output', 'out.mkv', 'in.mkv') `
        -Label 'TEST-MKVMERGE-WARN' `
        -TimeoutSeconds 30 `
        -Stage 'remux-mkvmerge' `
        -ProgressStage 'remux_mux' `
        -ProgressRoute 'remux' `
        -SaveReproOnFailure

    Assert-Equal ([int]$result.ExitCode) 1 'mkvmerge warning exit code changed.'
    Assert-Equal ([string]$result.ToolErrorCode) 'MKVMERGE_WARNINGS' 'mkvmerge warning exit must not be classified as failure.'
    Assert-True ([string]::IsNullOrWhiteSpace([string]$result.ReproPath)) 'mkvmerge warning exit must not save a repro command.'
    Assert-Equal $script:ReproSaves 0 'mkvmerge warning exit should not invoke Save-ReproCommand.'

    $completed = @($script:CapturedEvents | Where-Object { $_.EventType -eq 'tool_completed' })[-1]
    Assert-Equal ([string]$completed.Status) 'succeeded' 'mkvmerge warning exit should emit succeeded tool status.'
    Assert-Equal ([string]$completed.Data.error_code) 'MKVMERGE_WARNINGS' 'mkvmerge warning event should carry warning classification.'

    $progressValues = @($script:CapturedProgress | Where-Object { $_.Stage -eq 'remux_mux' } | ForEach-Object { $_.Percent })
    Assert-True ($progressValues -contains 0) 'mkvmerge wrapper did not publish initial progress.'
    Assert-True ($progressValues -contains 100) 'mkvmerge warning exit should publish final 100 percent.'
    $mkvmergeHeartbeats = @($script:CapturedProgress | Where-Object { $_.Stage -eq 'remux_mux' -and -not $_.PercentWasBound })
    Assert-True ($mkvmergeHeartbeats.Count -ge 3) 'A slow mkvmerge process must refresh exact stage evidence even when no new percentage is emitted.'
    $mkvmergeTerminalStage = @($script:CapturedMonitorStages | Where-Object { $_.StageId -eq 'mux' })[-1]
    Assert-Equal ([string]$mkvmergeTerminalStage.State) 'completed' 'Exact mkvmerge success must complete the backend mux stage.'
    Assert-Equal ([string]$mkvmergeTerminalStage.EvidenceSource) 'mkvmerge_process_exit' 'Mux completion must name its process-exit authority.'

    $script:CapturedProgress = @()
    $script:CapturedEvents = @()
    $script:CapturedMonitorStages = @()
    $script:ReproSaves = 0
    function Invoke-NativeProcess {
        param(
            [string]$FilePath,
            [array]$ArgumentList,
            [int]$TimeoutSeconds = 0,
            [string]$StopFlagPath = '',
            [string]$Label = '',
            [int]$MaxStdoutChars = 0,
            [int]$MaxStderrChars = 0,
            [scriptblock]$StdoutLineHandler,
            [scriptblock]$PollHandler,
            [int]$PollMilliseconds = 100
        )
        if ($PollHandler) { & $PollHandler 16 $null | Out-Null }
        return New-NativeCommandResult -ExitCode 1 -Stdout 'Warning: Skipping track ID 2 because the codec is unsupported.' -Stderr '' -TimedOut:$false -Stopped:$false -ErrorCode 'NATIVE_EXIT_1'
    }

    $blocked = Invoke-MkvmergeWithProgress `
        -ArgumentList @('--output', 'out.mkv', 'in.mkv') `
        -Label 'TEST-MKVMERGE-BLOCKING-WARN' `
        -TimeoutSeconds 30 `
        -Stage 'remux-mkvmerge' `
        -ProgressStage 'remux_mux' `
        -ProgressRoute 'remux' `
        -SaveReproOnFailure

    Assert-Equal ([int]$blocked.ExitCode) 1 'blocking mkvmerge warning should preserve native exit code evidence.'
    Assert-Equal ([string]$blocked.ToolErrorCode) 'MKVMERGE_WARNING_STREAM_LOSS' 'risky mkvmerge warning text must block with a stream-loss code.'
    Assert-True ([bool]$blocked.MkvmergeWarningBlocking) 'risky mkvmerge warning should be marked blocking.'
    Assert-True (-not [string]::IsNullOrWhiteSpace([string]$blocked.MkvmergeWarningMatchedText)) 'blocking warning should retain matched warning text.'
    Assert-True (-not [string]::IsNullOrWhiteSpace([string]$blocked.ReproPath)) 'blocking warning should save a repro command.'
    Assert-Equal $script:ReproSaves 1 'blocking warning should invoke Save-ReproCommand.'

    $blockedCompleted = @($script:CapturedEvents | Where-Object { $_.EventType -eq 'tool_completed' })[-1]
    Assert-Equal ([string]$blockedCompleted.Status) 'failed' 'blocking mkvmerge warning should emit failed tool status.'
    Assert-Equal ([string]$blockedCompleted.Data.error_code) 'MKVMERGE_WARNING_STREAM_LOSS' 'blocking mkvmerge warning event should carry stream-loss classification.'

    $blockedProgressValues = @($script:CapturedProgress | Where-Object { $_.Stage -eq 'remux_mux' } | ForEach-Object { $_.Percent })
    Assert-True ($blockedProgressValues -contains 0) 'blocking mkvmerge warning should still publish initial progress.'
    Assert-True (-not ($blockedProgressValues -contains 100)) 'blocking mkvmerge warning must not publish final 100 percent.'
    $blockedMkvmergeStage = @($script:CapturedMonitorStages | Where-Object { $_.StageId -eq 'mux' })[-1]
    Assert-Equal ([string]$blockedMkvmergeStage.State) 'failed' 'A blocking mkvmerge exit must fail the backend mux stage.'

    $script:CapturedProgress = @()
    $script:CapturedEvents = @()
    $script:CapturedMonitorStages = @()
    $script:ReproSaves = 0
    $script:FFmpegProgressWriteStepPercent = 25
    $script:StopRequested = $false
    $script:LastFFmpegAbortCode = ''
    $script:LastFFmpegAbortReason = ''
    $script:LastEncodeWasteGuardProjection = $null
    $script:CapturedFFmpegWorkingDirectory = ''

    $ffmpegPath = 'ffmpeg.exe'
    $LocalFailed = Join-Path ([System.IO.Path]::GetTempPath()) ("mediapipeline-ffmpeg-waste-guard-{0}" -f ([Guid]::NewGuid().ToString('N')))
    New-Item -ItemType Directory -Path $LocalFailed | Out-Null
    $LocalActiveToolLogs = Join-Path $LocalFailed 'ActiveToolLogs'
    $LocalInterruptedToolLogs = Join-Path $LocalFailed 'InterruptedToolLogs'
    $LocalFailureArtifacts = Join-Path $LocalFailed 'FailureArtifacts'
    foreach ($path in @($LocalActiveToolLogs, $LocalInterruptedToolLogs, $LocalFailureArtifacts)) {
        New-Item -ItemType Directory -Path $path -Force | Out-Null
    }
    $script:PipelineRunId = 'ffmpeg-progress-check'
    $script:CurrentRunMonitorJobId = 'ffmpeg-progress-check:item:1'
    $PauseFlag = Join-Path $LocalFailed 'pause.flag'
    $StopFlag = Join-Path $LocalFailed 'stop.flag'
    $sourcePath = Join-Path $LocalFailed 'source.bin'
    $outputPath = Join-Path $LocalFailed 'encode-temp.mkv'
    [System.IO.File]::WriteAllBytes($sourcePath, (New-Object byte[] 1000))
    $script:WasteGuardOutputPath = $outputPath

    function Invoke-FFprobeCommand {
        param(
            [array]$ArgumentList,
            [int]$TimeoutSeconds = 0,
            [string]$Stage = ''
        )
        return New-NativeCommandResult -ExitCode 0 -Stdout '100' -Stderr '' -ErrorCode 'OK'
    }

    function Invoke-NativeProcess {
        param(
            [string]$FilePath,
            [array]$ArgumentList,
            [int]$TimeoutSeconds = 0,
            [string]$StopFlagPath = '',
            [string]$Label = '',
            [int]$MaxStdoutChars = 0,
            [int]$MaxStderrChars = 0,
            [scriptblock]$StderrLineHandler,
            [scriptblock]$PollHandler,
            [scriptblock]$ProcessStartedHandler,
            [string]$WorkingDirectory = ''
        )
        $script:CapturedFFmpegWorkingDirectory = $WorkingDirectory
        if ($ProcessStartedHandler) { & $ProcessStartedHandler ([System.Diagnostics.Process]::GetCurrentProcess()) }
        [System.IO.File]::WriteAllBytes($script:WasteGuardOutputPath, (New-Object byte[] 700))
        if ($StderrLineHandler) {
            & $StderrLineHandler 'out_time_us=25000000' 'stderr'
        }
        $abort = if ($PollHandler) { & $PollHandler 180 $null } else { $null }
        if ($abort -and [bool]$abort.Abort) {
            $result = New-NativeCommandResult -ExitCode -1 -Stdout '' -Stderr '[KILLED: waste guard projection]' -TimedOut:$false -Stopped:$false -ErrorCode ([string]$abort.AbortCode)
            Set-ExternalToolResultProperty -Result $result -Name 'Aborted' -Value $true
            Set-ExternalToolResultProperty -Result $result -Name 'AbortCode' -Value ([string]$abort.AbortCode)
            Set-ExternalToolResultProperty -Result $result -Name 'AbortReason' -Value ([string]$abort.AbortReason)
            Set-ExternalToolResultProperty -Result $result -Name 'DurationSeconds' -Value 180
            return $result
        }
        return New-NativeCommandResult -ExitCode 0 -Stdout '' -Stderr '' -ErrorCode 'OK'
    }

    $wasteGuardContext = [pscustomobject][ordered]@{
        Enabled = $true
        Mode = 'enforce'
        Enforce = $true
        DryRun = $false
        SourceSizeBytes = 1000L
        OutputPath = $outputPath
        LimitRatio = 1.05
        OversizeMarginPercent = 20
        MinProgressPercent = 15
        MinElapsedSeconds = 120
        ConsecutiveSamples = 1
        ConsecutiveHits = 0
        PollSeconds = 0
    }

    $script:CapturedAudioWork = @()
    $ffmpegOk = Invoke-FFmpegWithProgress `
        -FFArgs @('-i', $sourcePath, $outputPath) `
        -Label 'TEST-FFMPEG-WASTE-GUARD' `
        -InputFile $sourcePath `
        -TimeoutSeconds 30 `
        -ProgressStage 'encode' `
        -ProgressRoute 'encode' `
        -ReproStage 'encode' `
        -OutputPath $outputPath `
        -WasteGuardContext $wasteGuardContext `
        -TrackAudioWork `
        -WorkingDirectory $LocalFailed

    Assert-Equal ([bool]$ffmpegOk) $false 'FFmpeg wrapper should return false when the waste guard aborts.'
    Assert-Equal ([string]$script:LastFFmpegAbortCode) 'ENCODE_WASTE_GUARD_PROJECTED_OVERSIZE' 'FFmpeg waste guard abort code was not exposed.'
    Assert-True ($script:LastEncodeWasteGuardProjection -ne $null) 'FFmpeg waste guard abort should expose projection metadata.'
    Assert-Equal ([bool]$script:LastEncodeWasteGuardProjection.ShouldAbort) $true 'Projection metadata should record an abort decision.'
    Assert-Equal ([string]$script:CapturedFFmpegWorkingDirectory) $LocalFailed 'FFmpeg wrapper did not pass the requested working directory to the native runner.'
    $ffmpegStarted = @($script:CapturedEvents | Where-Object { $_.EventType -eq 'tool_started' -and $_.Data.tool_name -eq 'ffmpeg' })[-1]
    $ffmpegCompleted = @($script:CapturedEvents | Where-Object { $_.EventType -eq 'tool_completed' -and $_.Data.tool_name -eq 'ffmpeg' })[-1]
    Assert-Equal ([string]$ffmpegStarted.Data.working_directory) $LocalFailed 'FFmpeg started event did not retain the requested working directory.'
    Assert-Equal ([string]$ffmpegCompleted.Data.working_directory) $LocalFailed 'FFmpeg completed event did not retain the requested working directory.'
    Assert-Equal ([string]$ffmpegCompleted.Data.diagnostic_log_disposition) 'failure' 'Waste-guard abort must promote the live capture as failure evidence.'
    Assert-PathUnderRoot -Path ([string]$script:LastFFmpegErrorLog) -Root $LocalFailureArtifacts -Message 'FFmpeg failure log must be stored under failure artifacts.'
    Assert-True (@(Get-ChildItem -LiteralPath $LocalActiveToolLogs -File -ErrorAction SilentlyContinue).Count -eq 0) 'FFmpeg failure left a capture in the active directory.'
    $failedFfmpegStage = @($script:CapturedMonitorStages | Where-Object { $_.StageId -eq 'transcode' })[-1]
    Assert-Equal ([string]$failedFfmpegStage.State) 'failed' 'A failed FFmpeg process must fail its exact backend stage.'
    Assert-Equal ([string]$failedFfmpegStage.EvidenceSource) 'ffmpeg_process_exit' 'FFmpeg failure must name its process-exit authority.'
    Assert-Equal @($script:CapturedAudioWork | Where-Object Event -eq started).Count 1 'Waste-guard audio work must begin only after Process.Start proof.'
    Assert-Equal @($script:CapturedAudioWork | Where-Object Event -eq attempt_ended).Count 1 'Waste-guard abort must clear active audio work before remux fallback can wait or start.'
    Assert-Equal ([string]@($script:CapturedAudioWork | Where-Object Event -eq attempt_ended)[0].ReasonCode) 'ENCODE_WASTE_GUARD_PROJECTED_OVERSIZE' 'Waste-guard audio attempt termination must preserve the exact abort reason.'
    $ffmpegHeartbeats = @($script:CapturedProgress | Where-Object { $_.Stage -eq 'encode' -and -not $_.PercentWasBound })
    Assert-True ($ffmpegHeartbeats.Count -ge 1) 'A long-running FFmpeg poll must refresh exact stage evidence without manufacturing a percentage.'

    $script:CapturedEvents = @()
    $script:CapturedMonitorStages = @()
    $script:StopRequested = $false
    function Invoke-NativeProcess {
        param(
            [string]$FilePath,
            [array]$ArgumentList,
            [int]$TimeoutSeconds = 0,
            [string]$StopFlagPath = '',
            [string]$Label = '',
            [int]$MaxStdoutChars = 0,
            [int]$MaxStderrChars = 0,
            [scriptblock]$StderrLineHandler,
            [scriptblock]$PollHandler,
            [scriptblock]$ProcessStartedHandler,
            [int]$IdleTimeoutSeconds = 0,
            [string]$WorkingDirectory = ''
        )
        if ($ProcessStartedHandler) { & $ProcessStartedHandler ([System.Diagnostics.Process]::GetCurrentProcess()) }
        if ($StderrLineHandler) {
            & $StderrLineHandler 'out_time_us=50000000' 'stderr'
            & $StderrLineHandler 'successful diagnostic line' 'stderr'
        }
        return New-NativeCommandResult -ExitCode 0 -Stdout '' -Stderr 'successful diagnostic line' -ErrorCode 'OK'
    }
    $script:CapturedAudioWork = @()
    $successOk = Invoke-FFmpegWithProgress -FFArgs @('-i', $sourcePath, $outputPath) -Label 'TEST-FFMPEG-SUCCESS' -InputFile $sourcePath -ProgressStage 'encode' -ProgressRoute 'encode' -WorkingDirectory $LocalFailed -TrackAudioWork
    Assert-True ([bool]$successOk) 'Successful FFmpeg run did not return true.'
    $successCompleted = @($script:CapturedEvents | Where-Object { $_.EventType -eq 'tool_completed' -and $_.Data.tool_name -eq 'ffmpeg' })[-1]
    Assert-Equal ([string]$successCompleted.Status) 'succeeded' 'Successful FFmpeg event status changed.'
    Assert-Equal ([string]$successCompleted.Data.diagnostic_log_disposition) 'deleted' 'Successful FFmpeg capture must be deleted.'
    Assert-True ([string]::IsNullOrWhiteSpace([string]$successCompleted.Data.diagnostic_log_path)) 'Successful FFmpeg event must not retain a diagnostic path.'
    Assert-True (@(Get-ChildItem -LiteralPath $LocalActiveToolLogs -File -ErrorAction SilentlyContinue).Count -eq 0) 'Successful FFmpeg run left a capture in the active directory.'
    $successfulFfmpegStage = @($script:CapturedMonitorStages | Where-Object { $_.StageId -eq 'transcode' })[-1]
    Assert-Equal ([string]$successfulFfmpegStage.State) 'completed' 'Exact FFmpeg success must complete the backend transcode stage.'
    Assert-Equal ([string]$successfulFfmpegStage.EvidenceSource) 'ffmpeg_process_exit' 'Transcode completion must name its process-exit authority.'
    $audioStart = @($script:CapturedAudioWork | Where-Object Event -eq started)
    $audioProgress = @($script:CapturedAudioWork | Where-Object Event -eq progress)
    $audioComplete = @($script:CapturedAudioWork | Where-Object Event -eq completed)
    Assert-Equal $audioStart.Count 1 'A correlated FFmpeg audio boundary must publish one runtime start.'
    Assert-Equal $audioStart[0].JobId 'ffmpeg-progress-check:item:1' 'FFmpeg audio start must retain the exact backend job identity.'
    Assert-True ($audioProgress.Count -ge 1) 'Truthful FFmpeg media-time progress must update active audio tracks.'
    Assert-Equal $audioProgress[-1].Numerator 50 'Audio work must use the parsed FFmpeg media-time numerator.'
    Assert-Equal $audioProgress[-1].Denominator 100 'Audio work progress denominator changed.'
    Assert-Equal $audioComplete.Count 1 'A successful correlated FFmpeg audio boundary must publish one runtime completion.'
    Assert-Equal $audioComplete[0].EvidenceSource 'ffmpeg_process_exit' 'Audio completion must name its exact process-exit authority.'

    function Invoke-NativeProcess {
        param(
            [string]$FilePath, [array]$ArgumentList, [int]$TimeoutSeconds = 0, [string]$StopFlagPath = '',
            [string]$Label = '', [int]$MaxStdoutChars = 0, [int]$MaxStderrChars = 0,
            [scriptblock]$StderrLineHandler, [scriptblock]$PollHandler, [scriptblock]$ProcessStartedHandler,
            [int]$IdleTimeoutSeconds = 0, [string]$WorkingDirectory = ''
        )
        if ($ProcessStartedHandler) { & $ProcessStartedHandler ([System.Diagnostics.Process]::GetCurrentProcess()) }
        return New-NativeCommandResult -ExitCode 1 -Stdout '' -Stderr 'synthetic hardware encode failure' -ErrorCode 'NATIVE_EXIT_1'
    }
    $script:CapturedAudioWork = @()
    $hardwareFailureOk = Invoke-FFmpegWithProgress -FFArgs @('-i', $sourcePath, $outputPath) -Label 'TEST-FFMPEG-HARDWARE-FAILURE' -InputFile $sourcePath -ProgressStage 'encode' -ProgressRoute 'encode-hardware' -WorkingDirectory $LocalFailed -TrackAudioWork
    Assert-Equal ([bool]$hardwareFailureOk) $false 'Hardware FFmpeg failure should return false before fallback selection.'
    Assert-Equal @($script:CapturedAudioWork | Where-Object Event -eq started).Count 1 'Hardware attempt must start audio work only after Process.Start proof.'
    Assert-Equal @($script:CapturedAudioWork | Where-Object Event -eq attempt_ended).Count 1 'Hardware failure must clear audio work before CPU fallback wait.'
    Assert-Equal ([string]@($script:CapturedAudioWork | Where-Object Event -eq attempt_ended)[0].ReasonCode) 'NATIVE_EXIT_1' 'Hardware attempt cleanup must retain exact native failure evidence.'

    function Invoke-NativeProcess {
        param(
            [string]$FilePath, [array]$ArgumentList, [int]$TimeoutSeconds = 0, [string]$StopFlagPath = '',
            [string]$Label = '', [int]$MaxStdoutChars = 0, [int]$MaxStderrChars = 0,
            [scriptblock]$StderrLineHandler, [scriptblock]$PollHandler, [scriptblock]$ProcessStartedHandler,
            [int]$IdleTimeoutSeconds = 0, [string]$WorkingDirectory = ''
        )
        if ($ProcessStartedHandler) { & $ProcessStartedHandler ([System.Diagnostics.Process]::GetCurrentProcess()) }
        return New-NativeCommandResult -ExitCode -1 -Stdout '' -Stderr 'synthetic timeout' -TimedOut:$true -ErrorCode 'NATIVE_TIMEOUT'
    }
    $script:CapturedAudioWork = @()
    $timeoutOk = Invoke-FFmpegWithProgress -FFArgs @('-i', $sourcePath, $outputPath) -Label 'TEST-FFMPEG-TIMEOUT' -InputFile $sourcePath -ProgressStage 'encode' -ProgressRoute 'encode-hardware' -WorkingDirectory $LocalFailed -TrackAudioWork
    Assert-Equal ([bool]$timeoutOk) $false 'Timed-out FFmpeg run should return false.'
    Assert-Equal @($script:CapturedAudioWork | Where-Object Event -eq attempt_ended).Count 1 'Timeout must clear active audio work with the process.'
    Assert-Equal ([string]@($script:CapturedAudioWork | Where-Object Event -eq attempt_ended)[0].ReasonCode) 'NATIVE_TIMEOUT' 'Timeout audio cleanup must retain exact timeout evidence.'

    $script:CapturedEvents = @()
    $script:StopRequested = $false
    $script:LastFFmpegErrorLog = ''
    function Invoke-NativeProcess {
        param(
            [string]$FilePath,
            [array]$ArgumentList,
            [int]$TimeoutSeconds = 0,
            [string]$StopFlagPath = '',
            [string]$Label = '',
            [int]$MaxStdoutChars = 0,
            [int]$MaxStderrChars = 0,
            [scriptblock]$StderrLineHandler,
            [scriptblock]$PollHandler,
            [scriptblock]$ProcessStartedHandler,
            [int]$IdleTimeoutSeconds = 0,
            [string]$WorkingDirectory = ''
        )
        if ($ProcessStartedHandler) { & $ProcessStartedHandler ([System.Diagnostics.Process]::GetCurrentProcess()) }
        if ($StderrLineHandler) { & $StderrLineHandler 'operator stopped' 'stderr' }
        return New-NativeCommandResult -ExitCode -1 -Stdout '' -Stderr 'operator stopped' -Stopped:$true -ErrorCode 'NATIVE_STOPPED'
    }
    $script:CapturedAudioWork = @()
    $stopOk = Invoke-FFmpegWithProgress -FFArgs @('-i', $sourcePath, $outputPath) -Label 'TEST-FFMPEG-STOP' -InputFile $sourcePath -WorkingDirectory $LocalFailed -TrackAudioWork
    Assert-Equal ([bool]$stopOk) $false 'Stopped FFmpeg run should return false.'
    $stopCompleted = @($script:CapturedEvents | Where-Object { $_.EventType -eq 'tool_completed' -and $_.Data.tool_name -eq 'ffmpeg' })[-1]
    Assert-Equal ([string]$stopCompleted.Status) 'stopped' 'Operator stop must not emit a failed tool status.'
    Assert-Equal ([string]$stopCompleted.Data.diagnostic_log_disposition) 'interrupted' 'Operator stop must retain diagnostic output as interrupted.'
    Assert-PathUnderRoot -Path ([string]$stopCompleted.Data.diagnostic_log_path) -Root $LocalInterruptedToolLogs -Message 'Stopped FFmpeg diagnostic must stay outside failure artifacts.'
    Assert-True ([string]::IsNullOrWhiteSpace([string]$script:LastFFmpegErrorLog)) 'Operator stop must not create a failure-log reference.'
    Assert-Equal @($script:CapturedAudioWork | Where-Object Event -eq attempt_ended).Count 1 'Operator stop must clear active audio work immediately after the native process exits.'
    Assert-Equal ([string]@($script:CapturedAudioWork | Where-Object Event -eq attempt_ended)[0].ReasonCode) 'NATIVE_STOPPED' 'Operator-stop audio attempt evidence must preserve the stop reason.'

    $script:CapturedEvents = @()
    $script:StopRequested = $false
    $script:LastFFmpegErrorLog = ''
    function Invoke-NativeProcess {
        param(
            [string]$FilePath,
            [array]$ArgumentList,
            [int]$TimeoutSeconds = 0,
            [string]$StopFlagPath = '',
            [string]$Label = '',
            [int]$MaxStdoutChars = 0,
            [int]$MaxStderrChars = 0,
            [scriptblock]$StderrLineHandler,
            [scriptblock]$PollHandler,
            [scriptblock]$ProcessStartedHandler,
            [int]$IdleTimeoutSeconds = 0,
            [string]$WorkingDirectory = ''
        )
        throw 'synthetic runner exception'
    }
    $script:CapturedAudioWork = @()
    $exceptionOk = Invoke-FFmpegWithProgress -FFArgs @('-i', $sourcePath, $outputPath) -Label 'TEST-FFMPEG-RUNNER-EXCEPTION' -InputFile $sourcePath -WorkingDirectory $LocalFailed -TrackAudioWork
    Assert-Equal ([bool]$exceptionOk) $false 'FFmpeg runner exception should return false.'
    $exceptionCompleted = @($script:CapturedEvents | Where-Object { $_.EventType -eq 'tool_completed' -and $_.Data.tool_name -eq 'ffmpeg' })[-1]
    Assert-Equal ([string]$exceptionCompleted.Status) 'failed' 'FFmpeg runner exception must emit a failed tool status.'
    Assert-Equal ([string]$exceptionCompleted.Data.diagnostic_log_disposition) 'failure' 'FFmpeg runner exception must promote diagnostic output to failure evidence.'
    Assert-PathUnderRoot -Path ([string]$script:LastFFmpegErrorLog) -Root $LocalFailureArtifacts -Message 'FFmpeg runner exception log must be stored under failure artifacts.'
    Assert-True (@(Get-ChildItem -LiteralPath $LocalActiveToolLogs -File -ErrorAction SilentlyContinue).Count -eq 0) 'FFmpeg runner exception left a capture in the active directory.'
    Assert-Equal @($script:CapturedAudioWork | Where-Object Event -eq started).Count 0 'A runner exception before Process.Start proof must not claim active audio work.'
    Assert-Equal @($script:CapturedAudioWork | Where-Object Event -eq completed).Count 0 'A runner exception before Process.Start proof must not claim completed audio work.'
    Assert-Equal @($script:CapturedAudioWork | Where-Object Event -eq attempt_ended).Count 0 'A runner exception before Process.Start proof must not claim an ended audio attempt.'

    function Invoke-NativeProcess {
        param(
            [string]$FilePath, [array]$ArgumentList, [int]$TimeoutSeconds = 0, [string]$StopFlagPath = '',
            [string]$Label = '', [int]$MaxStdoutChars = 0, [int]$MaxStderrChars = 0,
            [scriptblock]$StderrLineHandler, [scriptblock]$PollHandler, [scriptblock]$ProcessStartedHandler,
            [int]$IdleTimeoutSeconds = 0, [string]$WorkingDirectory = ''
        )
        if ($ProcessStartedHandler) { & $ProcessStartedHandler ([System.Diagnostics.Process]::GetCurrentProcess()) }
        throw 'synthetic post-start runner exception'
    }
    $script:CapturedAudioWork = @()
    $postStartExceptionOk = Invoke-FFmpegWithProgress -FFArgs @('-i', $sourcePath, $outputPath) -Label 'TEST-FFMPEG-POST-START-EXCEPTION' -InputFile $sourcePath -WorkingDirectory $LocalFailed -TrackAudioWork
    Assert-Equal ([bool]$postStartExceptionOk) $false 'Post-start FFmpeg runner exception should return false.'
    Assert-Equal @($script:CapturedAudioWork | Where-Object Event -eq started).Count 1 'Post-start exception must retain the exact Process.Start boundary.'
    Assert-Equal @($script:CapturedAudioWork | Where-Object Event -eq attempt_ended).Count 1 'Post-start exception must clear active audio work.'
    Assert-Equal ([string]@($script:CapturedAudioWork | Where-Object Event -eq attempt_ended)[0].ReasonCode) 'FFMPEG_RUNNER_EXCEPTION' 'Post-start cleanup must retain exact runner-exception evidence.'

    Remove-Item -LiteralPath $LocalFailed -Recurse -Force -ErrorAction SilentlyContinue
} finally {
    Remove-Item -LiteralPath $StopFlag -Force -ErrorAction SilentlyContinue
}

Write-Host 'FFmpeg/mkvmerge progress checks passed.'
