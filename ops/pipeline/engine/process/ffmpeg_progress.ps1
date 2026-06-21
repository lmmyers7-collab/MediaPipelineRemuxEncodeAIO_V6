# ==============================================================================
# ops\pipeline\engine\process\ffmpeg_progress.ps1
# ==============================================================================
# FFmpeg progress parsing and progress-aware FFmpeg execution.
#
# Dot-sourced from MediaPipeline.ps1. Reads these at call time:
#
#   $ffmpegPath, $StopFlag, $PauseFlag, $LocalFailed
#   $script:FFmpegProgressWriteStepPercent
#   $script:pipelineStatus, $script:StopRequested
#   Format-NativeCommandLine, Get-CompletedTaskText, Stop-NativeProcessTree
#   Invoke-FFprobeCommand, Save-ReproCommand
#   Get-ExternalToolFailureCode
#   Set-ProgressStage, Save-Progress
#   Write-Log, Write-PipelineEvent
# ==============================================================================

$ffmpegProgressHelperRoot = Join-Path $PSScriptRoot 'ffmpeg_progress'
. (Join-Path $ffmpegProgressHelperRoot 'parsing.ps1')
. (Join-Path $ffmpegProgressHelperRoot 'tool_context.ps1')
. (Join-Path $ffmpegProgressHelperRoot 'events.ps1')

function Get-MkvmergeWarningClassification {
    param([string]$Text)

    $warningText = [string]$Text
    if ([string]::IsNullOrWhiteSpace($warningText)) {
        return [pscustomobject][ordered]@{
            Blocking    = $false
            Code        = 'MKVMERGE_WARNINGS'
            Reason      = ''
            MatchedText = ''
        }
    }

    $riskyPatterns = @(
        '(?i)\bskipp(?:ed|ing)\b.*\b(track|packet|element|attachment|subtitle|audio|video)\b',
        '(?i)\b(track|packet|element|attachment|subtitle|audio|video)\b.*\bskipp(?:ed|ing)\b',
        '(?i)\bunsupported\b.*\b(track|codec|subtitle|attachment|element|stream)\b',
        '(?i)\b(track|codec|subtitle|attachment|element|stream)\b.*\bunsupported\b',
        '(?i)\bun(?:recognized|recognised|readable)\b.*\b(track|codec|subtitle|attachment|element|stream|file)\b',
        '(?i)\b(track|codec|subtitle|attachment|element|stream|file)\b.*\bun(?:recognized|recognised|readable)\b',
        '(?i)\bdropp(?:ed|ing)\b.*\b(track|packet|element|attachment|subtitle|audio|video|stream)\b',
        '(?i)\b(track|packet|element|attachment|subtitle|audio|video|stream)\b.*\bdropp(?:ed|ing)\b',
        '(?i)\binvalid\b.*\b(track|packet|element|attachment|subtitle|audio|video|stream)\b'
    )

    foreach ($line in ($warningText -split '\r?\n')) {
        $trimmed = ([string]$line).Trim()
        if ([string]::IsNullOrWhiteSpace($trimmed)) { continue }
        foreach ($pattern in $riskyPatterns) {
            if ($trimmed -match $pattern) {
                return [pscustomobject][ordered]@{
                    Blocking    = $true
                    Code        = 'MKVMERGE_WARNING_STREAM_LOSS'
                    Reason      = 'mkvmerge warning text indicates skipped, unsupported, unreadable, dropped, or invalid stream content'
                    MatchedText = $trimmed
                }
            }
        }
    }

    return [pscustomobject][ordered]@{
        Blocking    = $false
        Code        = 'MKVMERGE_WARNINGS'
        Reason      = ''
        MatchedText = ''
    }
}

function Get-FFmpegWasteGuardContextValue {
    param(
        [AllowNull()] $Context,
        [Parameter(Mandatory)] [string] $Name,
        $DefaultValue = $null
    )

    if ($null -eq $Context) { return $DefaultValue }
    if ($Context -is [System.Collections.IDictionary]) {
        if ($Context.Contains($Name)) { return $Context[$Name] }
        return $DefaultValue
    }
    $prop = $Context.PSObject.Properties[$Name]
    if ($prop) { return $prop.Value }
    return $DefaultValue
}

function Invoke-FFmpegWithProgress {
    param(
        [array]$FFArgs,
        [string]$Label,
        [string]$InputFile,
        [int]$TimeoutSeconds = (Get-NativeToolDefaultTimeoutSeconds -ToolName 'ffmpeg'),
        [string]$ProgressStage = $null,
        [string]$ProgressRoute = $null,
        [string]$ReproStage = $null,
        # F11: Allow callers (the CPU branch in Do-Encode) to lower the
        # ffmpeg priority class so a libx265 saturating every core does not
        # starve the desktop UI's main loop. 'inherit' is a no-op for
        # backwards compat; any unrecognized value falls back to inherit.
        [switch]$CpuEncode,
        [string]$ProcessPriority = 'inherit',
        [string]$OutputPath = '',
        [AllowNull()] $WasteGuardContext = $null,
        [string]$WorkingDirectory = ''
    )

    $duration = 0
    $dr = Invoke-FFprobeCommand -ArgumentList @(
        "-v","error","-show_entries","format=duration",
        "-of","default=noprint_wrappers=1:nokey=1","--",$InputFile
    ) -TimeoutSeconds 30 -Stage 'ffmpeg-progress-duration-probe'
    if ($dr.ExitCode -eq 0) { [double]::TryParse($dr.Output.Trim(), [ref]$duration) | Out-Null }
    Write-Log "$Label : starting (duration $([math]::Round($duration/60,1)) min)"
    if ($ProgressStage) {
        Set-ProgressStage -Stage $ProgressStage -Percent 0 -Route $ProgressRoute -SaveNow
    }

    # Map the user-facing priority string before emitting tool_started so
    # diagnostics record the effective requested priority, not just the raw
    # config text.
    $ffmpegContext = New-FFmpegToolContext -FFArgs $FFArgs -Executable $ffmpegPath -CpuEncode:$CpuEncode -ProcessPriority $ProcessPriority
    $ffmpegArgs = $ffmpegContext.Arguments
    $priorityClassEnum = $ffmpegContext.PriorityClass

    Write-PipelineEvent -EventType 'tool_started' -Stage $ProgressStage -Route $ProgressRoute -Status 'started' -SourcePath $InputFile -Data @{
        tool_name        = 'ffmpeg'
        label            = $Label
        executable       = $ffmpegPath
        command_line     = $ffmpegContext.CommandLine
        timeout_seconds  = $TimeoutSeconds
        cpu_encode       = [bool]$CpuEncode
        process_priority = if ($priorityClassEnum) { [string]$priorityClassEnum } else { 'inherit' }
        working_directory = $WorkingDirectory
    } | Out-Null

    $proc       = $null
    $errorLines = [System.Text.StringBuilder]::new()
    $stderrLogPath = $null
    $startedAt  = Get-Date
    $timedOut   = $false
    $stopped    = $false
    $script:LastFFmpegAbortCode = ''
    $script:LastFFmpegAbortReason = ''
    $script:LastEncodeWasteGuardProjection = $null
    try {
    $lastPct     = -1
    $lastObservedProgressPercent = 0.0
    $progressStep = [math]::Max(1, [int]$script:FFmpegProgressWriteStepPercent)
    $lastBeat    = Get-Date
    $lastFlagChk = Get-Date
    $lastWasteGuardPollElapsed = -999999.0
    $wasteGuardConsecutiveHits = 0
    try {
        if (-not [string]::IsNullOrWhiteSpace($LocalFailed)) {
            if (-not (Test-Path -LiteralPath $LocalFailed)) {
                New-Item -ItemType Directory -Path $LocalFailed -Force | Out-Null
            }
            $stderrLogPath = Join-Path $LocalFailed ("ffmpeg_stderr_{0}_{1}.log" -f (Get-Date -Format 'yyyyMMdd_HHmmss'), ([guid]::NewGuid().ToString('N')))
        }
    } catch {
        $stderrLogPath = $null
    }

    $processStartedHandler = {
        param([System.Diagnostics.Process]$StartedProcess)
        # E6 fix — assigning `$proc = $StartedProcess` inside this
        # scriptblock used to create a *local* $proc that vanished as
        # soon as the handler returned, leaving the outer $proc null and
        # disabling the catch-block tree-kill path. Use Set-Variable
        # -Scope 1 to write into the calling Invoke-FFmpegWithProgress
        # frame so the catch can see the live process handle.
        Set-Variable -Name proc -Value $StartedProcess -Scope 1
        $Global:ffmpegProcess = $StartedProcess
        if ($priorityClassEnum) {
            try {
                $StartedProcess.PriorityClass = $priorityClassEnum
                $script:LastFFmpegPriorityApplied = $true
                Write-Log "$Label : ffmpeg priority class set to $priorityClassEnum" "DEBUG"
            } catch {
                # PriorityClass can fail with AccessDenied if the user
                # lacks SeIncreaseBasePriorityPrivilege for higher tiers,
                # or if the process exited before we could set it. Log
                # and move on; the encode itself is still running.
                $script:LastFFmpegPriorityError = [string]$_.Exception.Message
                Write-Log "$Label : could not set ffmpeg priority class to ${priorityClassEnum}: $($script:LastFFmpegPriorityError)" "WARN"
            }
        }
    }

    $stderrLineHandler = {
        param([string]$ln)
        Add-FFmpegErrorTail -Builder $errorLines -Text $ln
        if ($stderrLogPath) {
            try { [System.IO.File]::AppendAllText($stderrLogPath, $ln + [Environment]::NewLine) } catch {}
        }
        $pct = Get-FFmpegProgressPercentFromLine -Line $ln -DurationSeconds $duration
        if ($null -ne $pct) {
            Set-Variable -Name lastObservedProgressPercent -Value ([double]$pct) -Scope 1
            if ($pct -ge ($lastPct + $progressStep)) {
                $step = $pct - ($pct % $progressStep)
                Write-Log "$Label : $step%"
                Set-Variable -Name lastPct -Value $step -Scope 1
                Set-Variable -Name lastBeat -Value (Get-Date) -Scope 1
                if ($ProgressStage) {
                    Set-ProgressStage -Stage $ProgressStage -Percent $step -Route $ProgressRoute -SaveNow
                } else {
                    Save-Progress $script:pipelineStatus | Out-Null
                }
            }
        }
    }

    $pollHandler = {
        param($ElapsedSeconds, $RunningProcess)

        if (((Get-Date) - $lastFlagChk).TotalSeconds -ge 5) {
            if (Test-Path -LiteralPath $PauseFlag -ErrorAction SilentlyContinue) {
                # Cannot pause ffmpeg mid-encode; pause takes effect after current file
                Write-Log "$Label : PAUSE flag detected — will pause after current file completes" "WARN"
            }
            Set-Variable -Name lastFlagChk -Value (Get-Date) -Scope 1
        }

        if (((Get-Date) - $lastBeat).TotalSeconds -gt 60) {
            Write-Log "$Label : still running..." "DEBUG"; Set-Variable -Name lastBeat -Value (Get-Date) -Scope 1
        }

        if ($null -ne $WasteGuardContext -and [bool](Get-FFmpegWasteGuardContextValue -Context $WasteGuardContext -Name 'Enabled' -DefaultValue $false)) {
            $mode = ([string](Get-FFmpegWasteGuardContextValue -Context $WasteGuardContext -Name 'Mode' -DefaultValue 'off')).Trim().ToLowerInvariant()
            if ($mode -ne 'off') {
                $pollSeconds = [double](Get-FFmpegWasteGuardContextValue -Context $WasteGuardContext -Name 'PollSeconds' -DefaultValue 10)
                if ($pollSeconds -lt 0) { $pollSeconds = 0 }
                if (([double]$ElapsedSeconds - $lastWasteGuardPollElapsed) -ge $pollSeconds) {
                    Set-Variable -Name lastWasteGuardPollElapsed -Value ([double]$ElapsedSeconds) -Scope 1
                    $guardOutputPath = [string](Get-FFmpegWasteGuardContextValue -Context $WasteGuardContext -Name 'OutputPath' -DefaultValue $OutputPath)
                    if (-not [string]::IsNullOrWhiteSpace($guardOutputPath) -and (Test-Path -LiteralPath $guardOutputPath -ErrorAction SilentlyContinue)) {
                        $sourceSize = [long](Get-FFmpegWasteGuardContextValue -Context $WasteGuardContext -Name 'SourceSizeBytes' -DefaultValue 0)
                        if ($sourceSize -le 0 -and -not [string]::IsNullOrWhiteSpace($InputFile) -and (Test-Path -LiteralPath $InputFile -ErrorAction SilentlyContinue)) {
                            $sourceSize = [long](Get-Item -LiteralPath $InputFile).Length
                        }
                        $outputSize = [long](Get-Item -LiteralPath $guardOutputPath).Length
                        $projection = Measure-MediaEncodeWasteGuardProjection `
                            -SourceSizeBytes $sourceSize `
                            -OutputSizeBytes $outputSize `
                            -ProgressPercent $lastObservedProgressPercent `
                            -LimitRatio ([double](Get-FFmpegWasteGuardContextValue -Context $WasteGuardContext -Name 'LimitRatio' -DefaultValue 1.05)) `
                            -OversizeMarginPercent ([double](Get-FFmpegWasteGuardContextValue -Context $WasteGuardContext -Name 'OversizeMarginPercent' -DefaultValue 20)) `
                            -MinProgressPercent ([double](Get-FFmpegWasteGuardContextValue -Context $WasteGuardContext -Name 'MinProgressPercent' -DefaultValue 15)) `
                            -ElapsedSeconds ([double]$ElapsedSeconds) `
                            -MinElapsedSeconds ([double](Get-FFmpegWasteGuardContextValue -Context $WasteGuardContext -Name 'MinElapsedSeconds' -DefaultValue 120)) `
                            -PreviousConsecutiveHits $wasteGuardConsecutiveHits `
                            -ConsecutiveSamples ([int](Get-FFmpegWasteGuardContextValue -Context $WasteGuardContext -Name 'ConsecutiveSamples' -DefaultValue 2))
                        Set-Variable -Name wasteGuardConsecutiveHits -Value ([int]$projection.ConsecutiveHits) -Scope 1
                        $script:LastEncodeWasteGuardProjection = $projection
                        if ([bool]$projection.ShouldAbort) {
                            $abortReason = ("projected encode output {0:N0} bytes exceeds waste guard threshold {1:N0} bytes at {2:N1}% progress" -f [double]$projection.ProjectedOutputBytes, [double]$projection.AbortThresholdBytes, [double]$projection.ProgressPercent)
                            $eventData = @{
                                mode                   = $mode
                                projected_output_bytes = [double]$projection.ProjectedOutputBytes
                                abort_threshold_bytes  = [double]$projection.AbortThresholdBytes
                                allowed_output_bytes   = [double]$projection.AllowedOutputBytes
                                source_size_bytes      = [long]$projection.SourceSizeBytes
                                output_size_bytes      = [long]$projection.OutputSizeBytes
                                progress_percent       = [double]$projection.ProgressPercent
                                projected_ratio        = [double]$projection.ProjectedRatio
                                consecutive_hits       = [int]$projection.ConsecutiveHits
                            }
                            if ($mode -eq 'dry_run' -or [bool](Get-FFmpegWasteGuardContextValue -Context $WasteGuardContext -Name 'DryRun' -DefaultValue $false)) {
                                Write-Log "$Label : waste guard dry-run would abort: $abortReason" "WARN"
                                Write-PipelineEvent -EventType 'encode_waste_guard_projection' -Stage $ProgressStage -Route $ProgressRoute -Status 'dry_run' -SourcePath $InputFile -Data $eventData | Out-Null
                                return $null
                            }
                            Write-Log "$Label : waste guard aborting encode: $abortReason" "WARN"
                            Write-PipelineEvent -EventType 'encode_waste_guard_projection' -Stage $ProgressStage -Route $ProgressRoute -Status 'aborting' -SourcePath $InputFile -Data $eventData | Out-Null
                            return @{
                                Abort = $true
                                AbortCode = 'ENCODE_WASTE_GUARD_PROJECTED_OVERSIZE'
                                AbortReason = $abortReason
                            }
                        }
                    }
                }
            }
        }
    }

    $result = Invoke-NativeProcess `
        -FilePath $ffmpegPath `
        -ArgumentList $ffmpegArgs `
        -TimeoutSeconds $TimeoutSeconds `
        -StopFlagPath $StopFlag `
        -Label $Label `
        -MaxStderrChars 262144 `
        -StderrLineHandler $stderrLineHandler `
        -PollHandler $pollHandler `
        -ProcessStartedHandler $processStartedHandler `
        -WorkingDirectory $WorkingDirectory

    if ([int]$result.ExitCode -eq -2) {
        throw ([string]$result.Stderr)
    }

    $timedOut = [bool]$result.TimedOut
    $stopped  = [bool]$result.Stopped
    $aborted  = [bool](Get-FFmpegWasteGuardContextValue -Context $result -Name 'Aborted' -DefaultValue $false)
    if ($timedOut) {
        Write-Log "$Label : timeout after ${TimeoutSeconds}s — killing ffmpeg" "ERROR"
        if ($stderrLogPath) { try { [System.IO.File]::AppendAllText($stderrLogPath, "[KILLED: TIMEOUT after ${TimeoutSeconds}s]" + [Environment]::NewLine) } catch {} }
    } elseif ($stopped) {
        Write-Log "$Label : STOP requested — killing ffmpeg" "WARN"
        if ($stderrLogPath) { try { [System.IO.File]::AppendAllText($stderrLogPath, "[KILLED: STOP requested]" + [Environment]::NewLine) } catch {} }
    } elseif ($aborted) {
        $script:LastFFmpegAbortCode = [string](Get-FFmpegWasteGuardContextValue -Context $result -Name 'AbortCode' -DefaultValue ([string]$result.ErrorCode))
        $script:LastFFmpegAbortReason = [string](Get-FFmpegWasteGuardContextValue -Context $result -Name 'AbortReason' -DefaultValue 'ffmpeg aborted by poll handler')
        Write-Log "$Label : aborted by runner policy ($($script:LastFFmpegAbortCode))" "WARN"
        if ($stderrLogPath) { try { [System.IO.File]::AppendAllText($stderrLogPath, "[KILLED: $($script:LastFFmpegAbortReason)]" + [Environment]::NewLine) } catch {} }
    }
    $exitCode = [int]$result.ExitCode
    $Global:ffmpegProcess = $null
    $completedWorkingDirectory = $WorkingDirectory
    if ($result -is [System.Collections.IDictionary] -and $result.Contains('WorkingDirectory')) {
        $completedWorkingDirectory = [string]$result['WorkingDirectory']
    } elseif ($result.PSObject.Properties['WorkingDirectory']) {
        $completedWorkingDirectory = [string]$result.WorkingDirectory
    }

    # Expose full stderr text for caller inspection (e.g. NVENC fallback logic).
    # Kept at script scope so callers don't need to change signature.
    Complete-FFmpegToolEvent `
        -Label $Label `
        -Executable $ffmpegPath `
        -CommandLine $ffmpegContext.CommandLine `
        -TimeoutSeconds $TimeoutSeconds `
        -ProgressStage $ProgressStage `
        -ProgressRoute $ProgressRoute `
        -InputFile $InputFile `
        -Result $result `
        -StartedAt $startedAt `
        -ExitCode $exitCode `
        -TimedOut $timedOut `
        -Stopped $stopped `
        -Stderr ([string]$result.Stderr) `
        -WorkingDirectory $completedWorkingDirectory | Out-Null

    if ($script:StopRequested) { Write-Log "$Label : stopped by user request"; return $false }

    if ($exitCode -ne 0) {
        if (-not [string]::IsNullOrWhiteSpace($ReproStage)) {
            $script:LastFFmpegReproPath = Save-ReproCommand -ToolName 'ffmpeg' -Executable $ffmpegPath -ArgumentList $FFArgs -Stage $ReproStage
        }
        if ($ProgressStage) {
            Set-ProgressStage -Stage $ProgressStage -Percent $null -Route $ProgressRoute -SaveNow
        }
        Write-Log "$Label : FAILED (exit $exitCode)" "ERROR"
        $errText = $script:LastFFmpegStderr
        $errLog = $stderrLogPath
        if ([string]::IsNullOrWhiteSpace($errLog)) {
            $errLog  = Join-Path $LocalFailed "ffmpeg_error_$(Get-Date -Format 'yyyyMMdd_HHmmss').log"
            try { $errText | Out-File -LiteralPath $errLog -Force } catch {}
        }
        $script:LastFFmpegErrorLog = $errLog
        Write-Log "FFmpeg error log: $errLog" "ERROR"
        $errText -split '\r?\n' | Where-Object { $_ -match '\S' } |
            Select-Object -Last 5 | ForEach-Object { Write-Log "  ffmpeg: $_" "ERROR" }
        return $false
    }
    if ($ProgressStage) {
        Set-ProgressStage -Stage $ProgressStage -Percent 100 -Route $ProgressRoute -SaveNow
    }
    if ($stderrLogPath -and (Test-Path -LiteralPath $stderrLogPath -ErrorAction SilentlyContinue)) {
        Remove-Item -LiteralPath $stderrLogPath -Force -ErrorAction SilentlyContinue
    }
    Write-Log "$Label : 100% complete"
    return $true
    } catch {
        $message = [string]$_.Exception.Message
        Write-Log "$Label : ffmpeg runner exception: $message" "ERROR"
        try {
            if ($proc -and -not $proc.HasExited) {
                Stop-NativeProcessTree -Process $proc -Label $Label
            }
        } catch {}
        Add-FFmpegErrorTail -Builder $errorLines -Text "[RUNNER EXCEPTION: $message]"
        if ($stderrLogPath) { try { [System.IO.File]::AppendAllText($stderrLogPath, "[RUNNER EXCEPTION: $message]" + [Environment]::NewLine) } catch {} }
        try {
            Complete-FFmpegToolEvent `
                -Label $Label `
                -Executable $ffmpegPath `
                -CommandLine $script:LastFFmpegCommandLine `
                -TimeoutSeconds $TimeoutSeconds `
                -ProgressStage $ProgressStage `
                -ProgressRoute $ProgressRoute `
                -InputFile $InputFile `
                -Result $null `
                -StartedAt $startedAt `
                -ExitCode -1 `
                -TimedOut $timedOut `
                -Stopped $stopped `
                -Stderr ($errorLines.ToString()) `
                -WorkingDirectory $WorkingDirectory `
                -RunnerException $message | Out-Null
        } catch {}
        try {
            if (-not [string]::IsNullOrWhiteSpace($ReproStage)) {
                $script:LastFFmpegReproPath = Save-ReproCommand -ToolName 'ffmpeg' -Executable $ffmpegPath -ArgumentList $FFArgs -Stage $ReproStage
            }
        } catch {}
        return $false
    } finally {
        $Global:ffmpegProcess = $null
    }
}

# Parses mkvmerge progress lines. mkvmerge prints either
#   "Progress: NN%"
# in default mode or
#   "#GUI#progress NN%"
# in --gui-mode. Both forms are accepted so the wrapper works regardless
# of which stdout dialect the invoking call requested.
function Get-MkvmergeProgressPercentFromLine {
    param([string]$Line)
    if ([string]::IsNullOrWhiteSpace($Line)) { return $null }
    if ($Line -match '^\s*#GUI#progress\s+(\d{1,3})%') {
        return [int][math]::Min(100, [math]::Max(0, [int]$Matches[1]))
    }
    if ($Line -match '^\s*Progress:\s+(\d{1,3})%') {
        return [int][math]::Min(100, [math]::Max(0, [int]$Matches[1]))
    }
    return $null
}

# Run mkvmerge with --gui-mode and parse its progress lines so the GUI
# can show a per-percent counter during the multi-minute mkvmerge step
# of a remux. Returns a result object compatible with what
# Invoke-MkvmergeCommand returns (ExitCode/Output/Error/TimedOut/Stopped),
# plus the standard Stage/CommandLine/StartedAt/CompletedAt/ToolErrorCode/
# ReproPath properties added by Invoke-ExternalToolCommand so the existing
# call sites in Do-Remux do not need to change.
function Invoke-MkvmergeWithProgress {
    param(
        [Parameter(Mandatory)] [array]$ArgumentList,
        [string]$Label = 'MKVMERGE',
        [int]$TimeoutSeconds = (Get-NativeToolDefaultTimeoutSeconds -ToolName 'mkvmerge'),
        [string]$Stage = 'remux-mkvmerge',
        [string]$ProgressStage = $null,
        [string]$ProgressRoute = $null,
        [switch]$SaveReproOnFailure
    )

    if ($ProgressStage) {
        Set-ProgressStage -Stage $ProgressStage -Percent 0 -Route $ProgressRoute -SaveNow
    }

    # Prepend --gui-mode so we always get the parseable #GUI#progress
    # form even on mkvtoolnix builds where the default Progress: format
    # has changed.
    $effectiveArgs = @('--gui-mode') + @($ArgumentList)

    $startedAt = Get-Date
    $commandLine = if (Get-Command -Name Format-NativeCommandLine -ErrorAction SilentlyContinue) {
        Format-NativeCommandLine -FilePath $mkvmergePath -ArgumentList $effectiveArgs
    } else {
        ([string[]]@($mkvmergePath) + @($effectiveArgs | ForEach-Object { [string]$_ })) -join ' '
    }

    Write-Log "$Label : starting (timeout ${TimeoutSeconds}s)"
    if (Get-Command -Name Write-PipelineEvent -ErrorAction SilentlyContinue) {
        Write-PipelineEvent -EventType 'tool_started' -Stage $ProgressStage -Route $ProgressRoute -Status 'started' -Data @{
            tool_name       = 'mkvmerge'
            label           = $Label
            executable      = $mkvmergePath
            command_line    = $commandLine
            timeout_seconds = $TimeoutSeconds
        } | Out-Null
    }

    $lastPct = -1
    $progressStep = [math]::Max(1, [int]$script:FFmpegProgressWriteStepPercent)

    $stdoutLineHandler = {
        param([string]$ln)
        $pct = Get-MkvmergeProgressPercentFromLine -Line $ln
        if ($null -ne $pct -and $pct -ge ($lastPct + $progressStep)) {
            $step = $pct - ($pct % $progressStep)
            Write-Log "$Label : $step%"
            $lastPct = $step
            if ($ProgressStage) {
                Set-ProgressStage -Stage $ProgressStage -Percent $step -Route $ProgressRoute -SaveNow
            }
        }
    }

    $result = Invoke-NativeProcess `
        -FilePath $mkvmergePath `
        -ArgumentList $effectiveArgs `
        -TimeoutSeconds $TimeoutSeconds `
        -StopFlagPath $StopFlag `
        -Label $Label `
        -MaxStdoutChars 65536 `
        -MaxStderrChars 65536 `
        -StdoutLineHandler $stdoutLineHandler

    $completedAt = Get-Date
    $durationSeconds = [math]::Round(($completedAt - $startedAt).TotalSeconds, 3)
    $exitCode = [int]$result.ExitCode

    $reproPath = $null
    $baseMkvmergeFailed = ([bool]$result.TimedOut -or [bool]$result.Stopped -or $exitCode -lt 0 -or $exitCode -ge 2)
    $mkvmergeWarning = (-not $baseMkvmergeFailed -and $exitCode -eq 1)
    $warningText = if (-not [string]::IsNullOrWhiteSpace([string]$result.Output)) { [string]$result.Output } else { [string]$result.Error }
    $warningClassification = if ($mkvmergeWarning) { Get-MkvmergeWarningClassification -Text $warningText } else { $null }
    $mkvmergeBlockingWarning = ($warningClassification -and [bool]$warningClassification.Blocking)
    $mkvmergeFailed = ($baseMkvmergeFailed -or $mkvmergeBlockingWarning)
    if ($SaveReproOnFailure -and $mkvmergeFailed) {
        if (Get-Command -Name Save-ReproCommand -ErrorAction SilentlyContinue) {
            $reproPath = Save-ReproCommand -ToolName 'mkvmerge' -Executable $mkvmergePath -ArgumentList $ArgumentList -Stage $Stage
        }
    }

    $toolErrorCode = if ($mkvmergeBlockingWarning) {
        [string]$warningClassification.Code
    } elseif ($mkvmergeWarning) {
        'MKVMERGE_WARNINGS'
    } elseif (Get-Command -Name Get-ExternalToolFailureCode -ErrorAction SilentlyContinue) {
        Get-ExternalToolFailureCode -ToolName 'mkvmerge' -Result $result
    } else {
        if ($exitCode -eq 0) { 'OK' } else { "MKVMERGE_EXIT_$exitCode" }
    }

    foreach ($pair in @(
        @{ Name = 'ToolName';        Value = 'mkvmerge' },
        @{ Name = 'Stage';           Value = $Stage },
        @{ Name = 'CommandLine';     Value = $commandLine },
        @{ Name = 'StartedAt';       Value = $startedAt.ToString('o') },
        @{ Name = 'CompletedAt';     Value = $completedAt.ToString('o') },
        @{ Name = 'DurationSeconds'; Value = $durationSeconds },
        @{ Name = 'ToolErrorCode';   Value = $toolErrorCode },
        @{ Name = 'ReproPath';       Value = $reproPath },
        @{ Name = 'MkvmergeWarningBlocking'; Value = [bool]$mkvmergeBlockingWarning },
        @{ Name = 'MkvmergeWarningReason';   Value = if ($warningClassification) { [string]$warningClassification.Reason } else { '' } },
        @{ Name = 'MkvmergeWarningMatchedText'; Value = if ($warningClassification) { [string]$warningClassification.MatchedText } else { '' } }
    )) {
        if (Get-Command -Name Set-ExternalToolResultProperty -ErrorAction SilentlyContinue) {
            Set-ExternalToolResultProperty -Result $result -Name $pair.Name -Value $pair.Value
        } else {
            try { $result[$pair.Name] = $pair.Value } catch {}
        }
    }

    if (Get-Command -Name Write-PipelineEvent -ErrorAction SilentlyContinue) {
        Write-PipelineEvent -EventType 'tool_completed' -Stage $ProgressStage -Route $ProgressRoute -Status $(if (-not $mkvmergeFailed) { 'succeeded' } else { 'failed' }) -Data @{
            tool_name        = 'mkvmerge'
            label            = $Label
            executable       = $mkvmergePath
            command_line     = $commandLine
            timeout_seconds  = $TimeoutSeconds
            exit_code        = $exitCode
            timed_out        = [bool]$result.TimedOut
            stopped          = [bool]$result.Stopped
            error_code       = $toolErrorCode
            duration_seconds = $durationSeconds
            repro_path       = $reproPath
            warning_blocking = [bool]$mkvmergeBlockingWarning
            warning_reason   = if ($warningClassification) { [string]$warningClassification.Reason } else { '' }
            warning_match    = if ($warningClassification) { [string]$warningClassification.MatchedText } else { '' }
        } | Out-Null
    }

    if ($ProgressStage -and -not $mkvmergeFailed) {
        Set-ProgressStage -Stage $ProgressStage -Percent 100 -Route $ProgressRoute -SaveNow
    } elseif ($ProgressStage) {
        Set-ProgressStage -Stage $ProgressStage -Percent $null -Route $ProgressRoute -SaveNow
    }

    if (-not $mkvmergeFailed) { Write-Log "$Label : 100% complete" }

    return $result
}
