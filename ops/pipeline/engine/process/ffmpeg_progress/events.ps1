# ==============================================================================
# ops\pipeline\engine\process\ffmpeg_progress\events.ps1
# ==============================================================================
# FFmpeg event-finalization helper for ffmpeg_progress.ps1.
# ==============================================================================

function Complete-FFmpegToolEvent {
    param(
        [Parameter(Mandatory)] [string]$Label,
        [Parameter(Mandatory)] [string]$Executable,
        [AllowNull()] [string]$CommandLine,
        [Parameter(Mandatory)] [int]$TimeoutSeconds,
        [int]$IdleTimeoutSeconds = 0,
        [AllowNull()] [string]$ProgressStage,
        [AllowNull()] [string]$ProgressRoute,
        [AllowNull()] [string]$InputFile,
        [AllowNull()] [object]$Result,
        [Parameter(Mandatory)] [datetime]$StartedAt,
        [Parameter(Mandatory)] [int]$ExitCode,
        [bool]$TimedOut,
        [bool]$Stopped,
        [AllowNull()] [string]$Stderr,
        [AllowNull()] [string]$WorkingDirectory,
        [AllowNull()] [string]$RunnerException
    )

    $script:LastFFmpegStderr = [string]$Stderr
    $script:LastFFmpegExit   = $ExitCode

    $durationProp = $null
    if ($null -ne $Result) {
        $durationProp = $Result.PSObject.Properties['DurationSeconds']
    }
    $script:LastFFmpegDurationSeconds = if ($durationProp) {
        [double]$durationProp.Value
    } else {
        [math]::Round(((Get-Date) - $StartedAt).TotalSeconds, 3)
    }

    $classificationResult = if ($null -ne $Result) {
        $Result
    } else {
        [pscustomobject]@{
            ExitCode = $ExitCode
            TimedOut = $TimedOut
            Stopped  = $Stopped
        }
    }
    $script:LastFFmpegToolErrorCode = Get-ExternalToolFailureCode -ToolName 'ffmpeg' -Result $classificationResult
    $idleTimedOut = $false
    $abortCode = ''
    $abortReason = ''
    if ($null -ne $Result) {
        if ($Result -is [System.Collections.IDictionary]) {
            if ($Result.Contains('IdleTimedOut')) { $idleTimedOut = [bool]$Result['IdleTimedOut'] }
            if ($Result.Contains('AbortCode')) { $abortCode = [string]$Result['AbortCode'] }
            if ($Result.Contains('AbortReason')) { $abortReason = [string]$Result['AbortReason'] }
        } else {
            if ($Result.PSObject.Properties['IdleTimedOut']) { $idleTimedOut = [bool]$Result.IdleTimedOut }
            if ($Result.PSObject.Properties['AbortCode']) { $abortCode = [string]$Result.AbortCode }
            if ($Result.PSObject.Properties['AbortReason']) { $abortReason = [string]$Result.AbortReason }
        }
    }

    $eventData = @{
        tool_name           = 'ffmpeg'
        label               = $Label
        executable          = $Executable
        command_line        = $CommandLine
        timeout_seconds     = $TimeoutSeconds
        idle_timeout_seconds = $IdleTimeoutSeconds
        exit_code           = $ExitCode
        timed_out           = $TimedOut
        stopped             = $Stopped
        idle_timed_out      = $idleTimedOut
        abort_code          = $abortCode
        abort_reason        = $abortReason
        error_code          = $script:LastFFmpegToolErrorCode
        duration_seconds    = $script:LastFFmpegDurationSeconds
        priority_requested  = [string]$script:LastFFmpegPriorityRequested
        priority_applied    = [bool]$script:LastFFmpegPriorityApplied
        priority_error      = [string]$script:LastFFmpegPriorityError
        working_directory   = $WorkingDirectory
    }
    if (-not [string]::IsNullOrWhiteSpace($RunnerException)) {
        $eventData.runner_exception = $RunnerException
    }

    Write-PipelineEvent -EventType 'tool_completed' -Stage $ProgressStage -Route $ProgressRoute -Status $(if ($ExitCode -eq 0) { 'succeeded' } else { 'failed' }) -SourcePath $InputFile -Data $eventData | Out-Null

    return [pscustomobject]@{
        ExitCode        = $ExitCode
        TimedOut        = $TimedOut
        Stopped         = $Stopped
        DurationSeconds = $script:LastFFmpegDurationSeconds
        ErrorCode       = $script:LastFFmpegToolErrorCode
    }
}
