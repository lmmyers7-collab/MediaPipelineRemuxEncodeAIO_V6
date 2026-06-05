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
        [AllowNull()] [string]$ProgressStage,
        [AllowNull()] [string]$ProgressRoute,
        [AllowNull()] [string]$InputFile,
        [AllowNull()] [object]$Result,
        [Parameter(Mandatory)] [datetime]$StartedAt,
        [Parameter(Mandatory)] [int]$ExitCode,
        [bool]$TimedOut,
        [bool]$Stopped,
        [AllowNull()] [string]$Stderr,
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

    $eventData = @{
        tool_name           = 'ffmpeg'
        label               = $Label
        executable          = $Executable
        command_line        = $CommandLine
        timeout_seconds     = $TimeoutSeconds
        exit_code           = $ExitCode
        timed_out           = $TimedOut
        stopped             = $Stopped
        error_code          = $script:LastFFmpegToolErrorCode
        duration_seconds    = $script:LastFFmpegDurationSeconds
        priority_requested  = [string]$script:LastFFmpegPriorityRequested
        priority_applied    = [bool]$script:LastFFmpegPriorityApplied
        priority_error      = [string]$script:LastFFmpegPriorityError
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
