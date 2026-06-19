# ==============================================================================
# ops\pipeline\engine\shared\native.ps1
# ==============================================================================
# External-process and bounded-job helpers extracted from
# MediaPipeline.ps1.
#
# Dot-sourced from the main script. These functions read several pieces of
# shared state at call time (resolved via dynamic scope), which is exactly
# what dot-sourcing preserves:
#
#   $StopFlag                   — flag-file path; presence means "abort"
#   $script:StopRequested       — in-process stop sentinel
#   $LocalFailureReports        — repro-command output directory
#   Set-ProgressStage           — defined later in the main script
#   Write-Log / DebugLog        — Logging.ps1 or engine stage fallback
#   Format-NativeCommandLine    — PathHelpers.ps1
#   Test-IsUncPath              — PathHelpers.ps1
#
# This module is intentionally NOT a `.psm1` so all of the above resolve
# inside the main script's scope without parameter plumbing.
# ==============================================================================

if (-not (Get-Command -Name New-NativeCommandResult -ErrorAction SilentlyContinue)) {
    $nativeContractsPath = Join-Path $PSScriptRoot 'native_process_contracts.ps1'
    if (Test-Path -LiteralPath $nativeContractsPath -PathType Leaf) {
        . $nativeContractsPath
    } else {
        $legacyContractsPath = Join-Path $PSScriptRoot 'NativeProcessContracts.ps1'
        if (Test-Path -LiteralPath $legacyContractsPath -PathType Leaf) {
            . $legacyContractsPath
        }
    }
}

# Aggressive process-tree teardown. .NET's Kill($true) is preferred (it walks
# child PIDs via the Win32 job-object API), but on PowerShell 7 with some
# bundled exes Kill($true) fails with "Access is denied" — in that case
# taskkill /T /F is the reliable fallback. The bare Kill() at the end is
# largely belt-and-braces; documented in the v1.0 review as a future
# simplification candidate.
function Stop-NativeProcessTree {
    param(
        [System.Diagnostics.Process]$Process,
        [string]$Label = "process"
    )
    if ($null -eq $Process) { return }
    try { if ($Process.HasExited) { return } } catch {}

    $pidText = try { [string]$Process.Id } catch { "" }
    try {
        $Process.Kill($true)
        return
    } catch {
        DebugLog "Process tree Kill(true) failed for $Label PID $pidText : $_"
    }

    if ($pidText -and (Get-Command taskkill.exe -ErrorAction SilentlyContinue)) {
        try {
            & taskkill.exe /PID $pidText /T /F 2>&1 | Out-Null
            return
        } catch {
            DebugLog "taskkill fallback failed for $Label PID $pidText : $_"
        }
    }

    try { $Process.Kill() } catch {}
}

# Drains a Task<string> with a bounded wait. Returns "" on timeout or
# exception so callers can keep going without checking for $null.
function Get-CompletedTaskText {
    param(
        [object]$Task,
        [int]$WaitMilliseconds = 1000
    )
    if ($null -eq $Task) { return "" }
    try {
        if ($Task.IsCompleted -or $Task.Wait($WaitMilliseconds)) {
            return [string]$Task.Result
        }
    } catch {}
    return ""
}

function Get-CompletedTaskTextWithBoundedDrain {
    param(
        [object]$Task,
        [int]$TotalWaitMilliseconds = 5000,
        [int]$PollMilliseconds = 100
    )
    if ($null -eq $Task) { return "" }
    $deadline = [DateTime]::UtcNow.AddMilliseconds([math]::Max(0, $TotalWaitMilliseconds))
    while ([DateTime]::UtcNow -lt $deadline) {
        try {
            if ($Task.IsCompleted -or $Task.Wait([math]::Max(1, $PollMilliseconds))) {
                return [string]$Task.Result
            }
        } catch {
            return ""
        }
    }
    return (Get-CompletedTaskText -Task $Task -WaitMilliseconds 0)
}

# Sleep that wakes early when the stop flag appears on disk. Returns $false
# if the wait was cut short by the stop flag, $true if it ran to completion.
# Polls in 1-second steps so the worst-case responsiveness is ~1 s.
function Start-StopAwareSleep {
    param([int]$Seconds)
    $remainingMs = [math]::Max(0, $Seconds * 1000)
    while ($remainingMs -gt 0) {
        if (Test-Path -LiteralPath $StopFlag -ErrorAction SilentlyContinue) {
            Write-Log "STOP flag detected during wait" "WARN"
            $script:StopRequested = $true
            Set-ProgressStage -Stage 'stopped' -Status 'Stopped' -Percent $null -SaveNow
            return $false
        }
        $step = [math]::Min(1000, $remainingMs)
        Start-Sleep -Milliseconds $step
        $remainingMs -= $step
    }
    return $true
}

# Bounded reachability probe. Returns $true / $false / $null:
#   $true  — Test-Path returned positive within the timeout
#   $false — Test-Path returned negative within the timeout
#   $null  — the probe job timed out (treat as "indeterminate")
# Uses Start-Job rather than Start-ThreadJob so the SMB stack lives in a
# child PowerShell process and a hung remote share can't take down the
# main script. Future optimisation: switch to Start-ThreadJob (PS7 native)
# for ~10× faster cold start — flagged in the v1.0 review.
function Test-PathAccessibleBounded {
    param(
        [string] $Path,
        [int] $TimeoutSeconds = 10
    )

    if ([string]::IsNullOrWhiteSpace($Path)) { return $false }

    $job = Start-Job -ScriptBlock {
        param($candidate)
        Test-Path -LiteralPath $candidate -ErrorAction SilentlyContinue
    } -ArgumentList $Path

    try {
        $completed = Wait-Job $job -Timeout ([math]::Max(1, $TimeoutSeconds))
        if (-not $completed) {
            Stop-Job $job -ErrorAction SilentlyContinue
            return $null
        }
        return [bool](Receive-Job $job -ErrorAction SilentlyContinue)
    } catch {
        return $null
    } finally {
        Remove-Job $job -Force -ErrorAction SilentlyContinue
    }
}

# Bounded recursive Get-ChildItem. Polls Wait-Job in 1-second slices so the
# stop flag can interrupt mid-scan instead of blocking until completion.
# Returns @() (not $null) on timeout, stop, or empty input — every caller
# can rely on iterating the result without a null check.
function Invoke-RecursivePathScan {
    param(
        [Parameter(Mandatory)] [string] $Path,
        [ValidateSet('File','Directory')] [string] $ItemType = 'File',
        [int] $TimeoutSeconds = 300,
        [string] $Label = 'recursive scan'
    )

    if ([string]::IsNullOrWhiteSpace($Path)) { return @() }
    if (-not (Test-IsUncPath $Path) -and -not (Test-Path -LiteralPath $Path -ErrorAction SilentlyContinue)) {
        Write-Log "$Label skipped because path is not accessible: $Path" "WARN"
        return @()
    }

    $job = Start-Job -ScriptBlock {
        param($root, $kind)
        if ($kind -eq 'Directory') {
            Get-ChildItem -LiteralPath $root -Recurse -Directory -Force -ErrorAction Stop |
                ForEach-Object { $_.FullName }
        } else {
            Get-ChildItem -LiteralPath $root -Recurse -File -Force -ErrorAction Stop |
                ForEach-Object { $_.FullName }
        }
    } -ArgumentList $Path, $ItemType

    $startedAt = Get-Date
    try {
        while ($true) {
            if ($script:StopRequested -or (Test-Path -LiteralPath $StopFlag -ErrorAction SilentlyContinue)) {
                Write-Log "$Label stopped during recursive scan: $Path" "WARN"
                $script:StopRequested = $true
                Stop-Job $job -ErrorAction SilentlyContinue
                return @()
            }

            $completed = Wait-Job $job -Timeout 1
            if ($completed) {
                return @(
                    Receive-Job $job -ErrorAction Stop |
                        Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) }
                )
            }

            if ($TimeoutSeconds -gt 0 -and ((Get-Date) - $startedAt).TotalSeconds -ge $TimeoutSeconds) {
                Stop-Job $job -ErrorAction SilentlyContinue
                Write-Log "$Label timed out after ${TimeoutSeconds}s while scanning $Path" "WARN"
                return @()
            }
        }
    } catch {
        Write-Log "$Label failed while scanning $Path : $_" "WARN"
        return @()
    } finally {
        Remove-Job $job -Force -ErrorAction SilentlyContinue
    }
}

# Deadlock-free native-process runner. Two design notes worth preserving:
#
#   1. ProcessStartInfo.ArgumentList (not Arguments) — lets .NET handle the
#      Windows command-line escaping rules per-arg. Avoids the entire class
#      of bugs around quoting paths with spaces / quotes.
#
#   2. ReadToEndAsync on both stdout and stderr — the classic deadlock is
#      a child that fills its stderr pipe while the parent is still
#      ReadToEnd-ing stdout. Reading both async resolves it. Get-CompletedTaskText
#      then drains both with a bounded wait after the process exits.
#
# The polling loop checks the stop flag every 100 ms, so an operator-issued
# stop terminates ffmpeg / mkvmerge / robocopy within ~100 ms.
function Add-NativeProcessText {
    param(
        [Parameter(Mandatory)] [System.Text.StringBuilder]$Builder,
        [AllowNull()] [string]$Text,
        [int]$MaxChars = 0
    )

    if ($null -eq $Text) { return }
    [void]$Builder.AppendLine($Text)
    if ($MaxChars -gt 0 -and $Builder.Length -gt $MaxChars) {
        $remove = $Builder.Length - $MaxChars
        try { [void]$Builder.Remove(0, $remove) } catch {}
    }
}

function Test-NativeProcessStopRequested {
    param([string]$StopFlagPath = '')

    if ([bool]$script:StopRequested) { return $true }
    if ([string]::IsNullOrWhiteSpace($StopFlagPath)) {
        try {
            $StopFlagPath = [string](Get-Variable -Name StopFlag -ValueOnly -ErrorAction SilentlyContinue)
        } catch {
            $StopFlagPath = ''
        }
    }
    if (-not [string]::IsNullOrWhiteSpace($StopFlagPath) -and (Test-Path -LiteralPath $StopFlagPath -ErrorAction SilentlyContinue)) {
        $script:StopRequested = $true
        return $true
    }
    return $false
}

function Receive-NativeProcessLine {
    param(
        [Parameter(Mandatory)] [ref]$LineTask,
        [Parameter(Mandatory)] [System.IO.StreamReader]$Reader,
        [Parameter(Mandatory)] [System.Text.StringBuilder]$Builder,
        [string]$StreamName = '',
        [scriptblock]$LineHandler,
        [int]$MaxChars = 0
    )

    if ($null -eq $LineTask.Value) { return $false }
    try {
        if (-not $LineTask.Value.IsCompleted) { return $false }
        $line = $LineTask.Value.Result
    } catch {
        $LineTask.Value = $null
        return $true
    }

    if ($null -eq $line) {
        $LineTask.Value = $null
        return $true
    }

    Add-NativeProcessText -Builder $Builder -Text $line -MaxChars $MaxChars
    if ($LineHandler) {
        try { & $LineHandler $line $StreamName } catch { DebugLog "Native process $StreamName line handler failed: $_" }
    }
    try {
        $LineTask.Value = $Reader.ReadLineAsync()
    } catch {
        $LineTask.Value = $null
    }
    return $true
}

function Invoke-NativeProcess {
    param(
        [string]$FilePath,
        [array]$ArgumentList,
        [int]$TimeoutSeconds = 0,
        [string]$StopFlagPath = '',
        [string]$Label = '',
        [int]$PollMilliseconds = 100,
        [int]$DrainMilliseconds = 5000,
        [int]$MaxStdoutChars = 0,
        [int]$MaxStderrChars = 0,
        [scriptblock]$StdoutLineHandler,
        [scriptblock]$StderrLineHandler,
        [scriptblock]$PollHandler,
        [scriptblock]$ProcessStartedHandler,
        # CPU-A2 — when non-empty / non-'inherit', set the child process
        # priority class right after Process.Start. Threads inherit the
        # priority class change automatically. Used by CPU-bound external
        # tools (BDPGS OCR, audio-transcode-active ffmpeg, etc.) to keep
        # the desktop UI responsive while heavy work runs.
        [string]$ProcessPriority = 'inherit'
    )

    if ([string]::IsNullOrWhiteSpace($Label)) { $Label = Split-Path $FilePath -Leaf }
    $psi = [System.Diagnostics.ProcessStartInfo]@{
        FileName               = $FilePath
        UseShellExecute        = $false
        RedirectStandardError  = $true
        RedirectStandardOutput = $true
        CreateNoWindow         = $true
    }
    foreach ($arg in $ArgumentList) { $psi.ArgumentList.Add([string]$arg) }

    # CPU-A2 — resolve the priority enum once before Process.Start.
    $priorityClassEnum = $null
    $priorityText = if ($ProcessPriority) { ([string]$ProcessPriority).Trim().ToLowerInvariant() } else { '' }
    if ($priorityText -and $priorityText -ne 'inherit') {
        switch ($priorityText) {
            'idle'        { $priorityClassEnum = [System.Diagnostics.ProcessPriorityClass]::Idle }
            'belownormal' { $priorityClassEnum = [System.Diagnostics.ProcessPriorityClass]::BelowNormal }
            'normal'      { $priorityClassEnum = [System.Diagnostics.ProcessPriorityClass]::Normal }
            'abovenormal' { $priorityClassEnum = [System.Diagnostics.ProcessPriorityClass]::AboveNormal }
            'high'        { $priorityClassEnum = [System.Diagnostics.ProcessPriorityClass]::High }
        }
    }

    $proc       = $null
    $stdoutTask = $null
    $stderrTask = $null
    $stdout     = [System.Text.StringBuilder]::new()
    $stderr     = [System.Text.StringBuilder]::new()
    $timedOut   = $false
    $stopped    = $false
    $aborted    = $false
    $abortCode  = ''
    $abortReason = ''
    # Suggestion #6 — record whether the requested ProcessPriority was
    # actually applied. Failures here are silent without this (the
    # WARN log line is easy to miss); surfacing it on the
    # NativeCommandResult lets Invoke-ExternalToolCommand stamp the
    # `tool_started` pipeline event so the diagnostics drawer can
    # render "priority requested but not applied" badges.
    $priorityRequested = if ($priorityClassEnum) { [string]$priorityClassEnum } else { 'inherit' }
    $priorityApplied   = ($priorityClassEnum -eq $null)  # 'inherit' is trivially "applied"
    $priorityError     = ''
    $startedAt  = Get-Date
    try {
        $proc       = [System.Diagnostics.Process]::Start($psi)
        if ($priorityClassEnum) {
            try {
                $proc.PriorityClass = $priorityClassEnum
                $priorityApplied = $true
                DebugLog "$Label : process priority class set to $priorityClassEnum"
            } catch {
                # PriorityClass set can fail with AccessDenied if user
                # lacks SeIncreaseBasePriorityPrivilege for the higher
                # tiers, or if the process exited before we could set
                # it. Log and move on — the process is still running.
                $priorityError = [string]$_.Exception.Message
                Write-Log "$Label : could not set process priority class to ${priorityClassEnum}: $priorityError" "WARN"
            }
        }
        if ($ProcessStartedHandler) {
            try { & $ProcessStartedHandler $proc } catch { DebugLog "Native process start handler failed for $Label : $_" }
        }
        $stdoutTask = $proc.StandardOutput.ReadLineAsync()
        $stderrTask = $proc.StandardError.ReadLineAsync()

        while (-not $proc.HasExited) {
            if ($TimeoutSeconds -gt 0 -and ((Get-Date) - $startedAt).TotalSeconds -ge $TimeoutSeconds) {
                $timedOut = $true
                Stop-NativeProcessTree -Process $proc -Label $Label
                break
            }
            if (Test-NativeProcessStopRequested -StopFlagPath $StopFlagPath) {
                $stopped = $true
                Stop-NativeProcessTree -Process $proc -Label $Label
                break
            }

            $didWork = $false
            $didWork = (Receive-NativeProcessLine -LineTask ([ref]$stdoutTask) -Reader $proc.StandardOutput -Builder $stdout -StreamName 'stdout' -LineHandler $StdoutLineHandler -MaxChars $MaxStdoutChars) -or $didWork
            $didWork = (Receive-NativeProcessLine -LineTask ([ref]$stderrTask) -Reader $proc.StandardError -Builder $stderr -StreamName 'stderr' -LineHandler $StderrLineHandler -MaxChars $MaxStderrChars) -or $didWork
            if ($PollHandler) {
                try {
                    $pollResult = & $PollHandler ([math]::Round(((Get-Date) - $startedAt).TotalSeconds, 3)) $proc
                    if ($null -ne $pollResult) {
                        $pollAbort = $false
                        $pollCode = ''
                        $pollReason = ''
                        if ($pollResult -is [System.Collections.IDictionary]) {
                            if ($pollResult.Contains('Abort')) { $pollAbort = [bool]$pollResult['Abort'] }
                            if ($pollResult.Contains('AbortCode')) { $pollCode = [string]$pollResult['AbortCode'] }
                            if ($pollResult.Contains('AbortReason')) { $pollReason = [string]$pollResult['AbortReason'] }
                        } else {
                            $abortProp = $pollResult.PSObject.Properties['Abort']
                            $codeProp = $pollResult.PSObject.Properties['AbortCode']
                            $reasonProp = $pollResult.PSObject.Properties['AbortReason']
                            if ($abortProp) { $pollAbort = [bool]$abortProp.Value }
                            if ($codeProp) { $pollCode = [string]$codeProp.Value }
                            if ($reasonProp) { $pollReason = [string]$reasonProp.Value }
                        }
                        if ($pollAbort) {
                            $aborted = $true
                            $abortCode = if ([string]::IsNullOrWhiteSpace($pollCode)) { 'NATIVE_ABORTED' } else { $pollCode }
                            $abortReason = if ([string]::IsNullOrWhiteSpace($pollReason)) { 'poll handler requested abort' } else { $pollReason }
                            Stop-NativeProcessTree -Process $proc -Label $Label
                            break
                        }
                    }
                } catch { DebugLog "Native process poll handler failed for $Label : $_" }
            }
            if (-not $didWork) { Start-Sleep -Milliseconds ([math]::Max(10, $PollMilliseconds)) }
        }

        if ($timedOut -or $stopped -or $aborted) {
            try { $proc.WaitForExit(5000) | Out-Null } catch {}
        } else {
            try { $proc.WaitForExit() } catch {}
        }
    } catch {
        try {
            if ($null -ne $proc -and -not $proc.HasExited) {
                Stop-NativeProcessTree -Process $proc -Label $Label
            }
        } catch {
            DebugLog "Native process cleanup failed after start/run error for $Label : $_"
        }
        $stderr = "Failed to start native command '$FilePath': $_"
        return (New-NativeCommandResult -ExitCode -2 -Stdout "" -Stderr $stderr -ErrorCode 'NATIVE_START_FAILED')
    }

    $drainMs = if ($timedOut -or $stopped) { [math]::Max(1000, $DrainMilliseconds) } else { [math]::Min([math]::Max(250, $DrainMilliseconds), 1000) }
    $drainUntil = (Get-Date).AddMilliseconds($drainMs)
    while (($stdoutTask -or $stderrTask) -and (Get-Date) -lt $drainUntil) {
        $didWork = $false
        if ($stdoutTask) {
            $didWork = (Receive-NativeProcessLine -LineTask ([ref]$stdoutTask) -Reader $proc.StandardOutput -Builder $stdout -StreamName 'stdout' -LineHandler $StdoutLineHandler -MaxChars $MaxStdoutChars) -or $didWork
        }
        if ($stderrTask) {
            $didWork = (Receive-NativeProcessLine -LineTask ([ref]$stderrTask) -Reader $proc.StandardError -Builder $stderr -StreamName 'stderr' -LineHandler $StderrLineHandler -MaxChars $MaxStderrChars) -or $didWork
        }
        if (-not $didWork) { Start-Sleep -Milliseconds 50 }
    }

    $stdoutText = $stdout.ToString()
    $stderrText = $stderr.ToString()
    if ($aborted) {
        $exitCode = -1
        $stderrText = ($stderrText + "`n[KILLED: $abortReason]").Trim()
        $errorCode = if ([string]::IsNullOrWhiteSpace($abortCode)) { 'NATIVE_ABORTED' } else { $abortCode }
    } elseif ($timedOut) {
        $exitCode = -1
        $stderrText = ($stderrText + "`n[KILLED: TIMEOUT after ${TimeoutSeconds}s]").Trim()
        $errorCode = 'NATIVE_TIMEOUT'
    } elseif ($stopped) {
        $exitCode = -1
        $stderrText = ($stderrText + "`n[KILLED: STOP requested]").Trim()
        $errorCode = 'NATIVE_STOPPED'
    } else {
        $exitCode = $proc.ExitCode
        $errorCode = if ($exitCode -eq 0) { 'OK' } else { "NATIVE_EXIT_$exitCode" }
    }
    $result = New-NativeCommandResult -ExitCode $exitCode -Stdout $stdoutText.TrimEnd() -Stderr $stderrText.TrimEnd() -TimedOut $timedOut -Stopped $stopped -ErrorCode $errorCode
    Set-ExternalToolResultProperty -Result $result -Name 'StartedAt' -Value $startedAt.ToString('o')
    Set-ExternalToolResultProperty -Result $result -Name 'CompletedAt' -Value (Get-Date).ToString('o')
    Set-ExternalToolResultProperty -Result $result -Name 'DurationSeconds' -Value ([math]::Round(((Get-Date) - $startedAt).TotalSeconds, 3))
    # Suggestion #6 — surface the priority application result so the
    # tool_completed pipeline event can show "requested vs applied" in
    # the diagnostics drawer. PriorityRequested mirrors the ProcessPriority
    # parameter (always populated); PriorityApplied is $true when the
    # child actually got the requested class (or when 'inherit' was
    # asked for, which is trivially satisfied). PriorityError carries
    # the Exception.Message from a failed PriorityClass assignment.
    Set-ExternalToolResultProperty -Result $result -Name 'PriorityRequested' -Value $priorityRequested
    Set-ExternalToolResultProperty -Result $result -Name 'PriorityApplied'   -Value $priorityApplied
    Set-ExternalToolResultProperty -Result $result -Name 'PriorityError'     -Value $priorityError
    Set-ExternalToolResultProperty -Result $result -Name 'Aborted'           -Value $aborted
    Set-ExternalToolResultProperty -Result $result -Name 'AbortCode'         -Value $abortCode
    Set-ExternalToolResultProperty -Result $result -Name 'AbortReason'       -Value $abortReason
    return $result
}

function Invoke-NativeCommand {
    param(
        [string]$FilePath,
        [array]$ArgumentList,
        [scriptblock]$ErrorHandler,
        [int]$TimeoutSeconds = 0,
        [string]$ProcessPriority = 'inherit',
        [scriptblock]$StdoutLineHandler,
        [scriptblock]$StderrLineHandler,
        [scriptblock]$PollHandler,
        [int]$PollMilliseconds = 100
    )
    $nativeArgs = @{
        FilePath          = $FilePath
        ArgumentList      = $ArgumentList
        TimeoutSeconds    = $TimeoutSeconds
        ProcessPriority   = $ProcessPriority
        PollMilliseconds  = $PollMilliseconds
    }
    if ($StdoutLineHandler) { $nativeArgs.StdoutLineHandler = $StdoutLineHandler }
    if ($StderrLineHandler) { $nativeArgs.StderrLineHandler = $StderrLineHandler }
    if ($PollHandler) { $nativeArgs.PollHandler = $PollHandler }
    $result = Invoke-NativeProcess @nativeArgs
    $exitCode = [int]$result.ExitCode
    $stderr = [string]$result.Stderr
    if ($exitCode -ne 0 -and $ErrorHandler) { & $ErrorHandler $exitCode $stderr }
    return $result
}

function Invoke-ExternalToolCommand {
    param(
        [Parameter(Mandatory)] [string]$ToolName,
        [Parameter(Mandatory)] [string]$FilePath,
        [Parameter(Mandatory)] [array]$ArgumentList,
        [string]$Stage = '',
        [int]$TimeoutSeconds = 0,
        [switch]$SaveReproOnFailure,
        [scriptblock]$ErrorHandler,
        # CPU-A2 — non-empty / non-'inherit' values lower the child's
        # ProcessPriorityClass right after launch. Used by BDPGS OCR and
        # other CPU-bound tool calls so they don't starve the desktop.
        [string]$ProcessPriority = 'inherit'
    )

    $startedAt = Get-Date
    $commandLine = if (Get-Command -Name Format-NativeCommandLine -ErrorAction SilentlyContinue) {
        Format-NativeCommandLine -FilePath $FilePath -ArgumentList $ArgumentList
    } else {
        ([string[]]@($FilePath) + @($ArgumentList | ForEach-Object { [string]$_ })) -join ' '
    }

    if (Get-Command -Name Write-PipelineEvent -ErrorAction SilentlyContinue) {
        Write-PipelineEvent -EventType 'tool_started' -Stage $Stage -Status 'started' -Data @{
            tool_name        = $ToolName
            executable       = $FilePath
            command_line     = $commandLine
            timeout_seconds  = $TimeoutSeconds
            process_priority = $ProcessPriority
        } | Out-Null
    }

    $nativeArgs = @{
        FilePath        = $FilePath
        ArgumentList    = $ArgumentList
        TimeoutSeconds  = $TimeoutSeconds
        ProcessPriority = $ProcessPriority
    }
    if ($ErrorHandler) {
        $nativeArgs.ErrorHandler = $ErrorHandler
    }

    $result = Invoke-NativeCommand @nativeArgs
    $completedAt = Get-Date
    $durationSeconds = [math]::Round(($completedAt - $startedAt).TotalSeconds, 3)
    $toolErrorCode = Get-ExternalToolFailureCode -ToolName $ToolName -Result $result
    $reproPath = $null

    if ($SaveReproOnFailure -and [int]$result.ExitCode -ne 0 -and -not [string]::IsNullOrWhiteSpace($Stage)) {
        if (Get-Command -Name Save-ReproCommand -ErrorAction SilentlyContinue) {
            $reproPath = Save-ReproCommand -ToolName $ToolName -Executable $FilePath -ArgumentList $ArgumentList -Stage $Stage
        }
    }

    foreach ($pair in @(
        @{ Name = 'ToolName';        Value = $ToolName },
        @{ Name = 'Stage';           Value = $Stage },
        @{ Name = 'CommandLine';     Value = $commandLine },
        @{ Name = 'StartedAt';       Value = $startedAt.ToString('o') },
        @{ Name = 'CompletedAt';     Value = $completedAt.ToString('o') },
        @{ Name = 'DurationSeconds'; Value = $durationSeconds },
        @{ Name = 'ToolErrorCode';   Value = $toolErrorCode },
        @{ Name = 'ReproPath';       Value = $reproPath }
    )) {
        Set-ExternalToolResultProperty -Result $result -Name $pair.Name -Value $pair.Value
    }

    if (Get-Command -Name Write-PipelineEvent -ErrorAction SilentlyContinue) {
        # Suggestion #6 — pull priority result out of the native result
        # so the diagnostics drawer can show "BelowNormal requested but
        # not applied (Access is denied)" instead of users wondering
        # why their UI still hangs during a 'high' encode.
        $priorityRequestedField = if ($result.PSObject.Properties['PriorityRequested']) { [string]$result.PriorityRequested } else { 'inherit' }
        $priorityAppliedField   = if ($result.PSObject.Properties['PriorityApplied']) { [bool]$result.PriorityApplied } else { $true }
        $priorityErrorField     = if ($result.PSObject.Properties['PriorityError']) { [string]$result.PriorityError } else { '' }
        Write-PipelineEvent -EventType 'tool_completed' -Stage $Stage -Status $(if ([int]$result.ExitCode -eq 0) { 'succeeded' } else { 'failed' }) -Data @{
            tool_name           = $ToolName
            executable          = $FilePath
            command_line        = $commandLine
            timeout_seconds     = $TimeoutSeconds
            exit_code           = [int]$result.ExitCode
            timed_out           = [bool]$result.TimedOut
            stopped             = [bool]$result.Stopped
            error_code          = $toolErrorCode
            duration_seconds    = $durationSeconds
            repro_path          = $reproPath
            priority_requested  = $priorityRequestedField
            priority_applied    = $priorityAppliedField
            priority_error      = $priorityErrorField
        } | Out-Null
    }

    return $result
}

function Invoke-FFprobeCommand {
    param(
        [Parameter(Mandatory)] [array]$ArgumentList,
        [int]$TimeoutSeconds = 30,
        [string]$Stage = 'ffprobe',
        [switch]$SaveReproOnFailure,
        [scriptblock]$ErrorHandler
    )

    return Invoke-ExternalToolCommand -ToolName 'ffprobe' -FilePath $ffprobePath -ArgumentList $ArgumentList -TimeoutSeconds $TimeoutSeconds -Stage $Stage -SaveReproOnFailure:$SaveReproOnFailure -ErrorHandler $ErrorHandler
}

function Invoke-FFmpegCommand {
    param(
        [Parameter(Mandatory)] [array]$ArgumentList,
        [int]$TimeoutSeconds = (Get-NativeToolDefaultTimeoutSeconds -ToolName 'ffmpeg'),
        [string]$Stage = 'ffmpeg',
        [switch]$SaveReproOnFailure,
        [scriptblock]$ErrorHandler,
        [string]$ProcessPriority = 'inherit'
    )

    return Invoke-ExternalToolCommand -ToolName 'ffmpeg' -FilePath $ffmpegPath -ArgumentList $ArgumentList -TimeoutSeconds $TimeoutSeconds -Stage $Stage -SaveReproOnFailure:$SaveReproOnFailure -ErrorHandler $ErrorHandler -ProcessPriority $ProcessPriority
}

function Invoke-MkvmergeCommand {
    param(
        [Parameter(Mandatory)] [array]$ArgumentList,
        [int]$TimeoutSeconds = (Get-NativeToolDefaultTimeoutSeconds -ToolName 'mkvmerge'),
        [string]$Stage = 'mkvmerge',
        [switch]$SaveReproOnFailure,
        [scriptblock]$ErrorHandler,
        [string]$ProcessPriority = 'inherit'
    )

    return Invoke-ExternalToolCommand -ToolName 'mkvmerge' -FilePath $mkvmergePath -ArgumentList $ArgumentList -TimeoutSeconds $TimeoutSeconds -Stage $Stage -SaveReproOnFailure:$SaveReproOnFailure -ErrorHandler $ErrorHandler -ProcessPriority $ProcessPriority
}

function Invoke-MkvextractCommand {
    param(
        [Parameter(Mandatory)] [string]$FilePath,
        [Parameter(Mandatory)] [array]$ArgumentList,
        [int]$TimeoutSeconds = (Get-NativeToolDefaultTimeoutSeconds -ToolName 'mkvmerge'),
        [string]$Stage = 'mkvextract',
        [switch]$SaveReproOnFailure,
        [scriptblock]$ErrorHandler,
        [string]$ProcessPriority = 'inherit'
    )

    return Invoke-ExternalToolCommand -ToolName 'mkvextract' -FilePath $FilePath -ArgumentList $ArgumentList -TimeoutSeconds $TimeoutSeconds -Stage $Stage -SaveReproOnFailure:$SaveReproOnFailure -ErrorHandler $ErrorHandler -ProcessPriority $ProcessPriority
}

function Invoke-PythonToolCommand {
    param(
        [Parameter(Mandatory)] [array]$ArgumentList,
        [int]$TimeoutSeconds = (Get-NativeToolDefaultTimeoutSeconds -ToolName 'python'),
        [string]$Stage = 'python',
        [switch]$SaveReproOnFailure,
        [scriptblock]$ErrorHandler,
        [string]$ProcessPriority = 'inherit'
    )

    return Invoke-ExternalToolCommand -ToolName 'python' -FilePath $pythonPath -ArgumentList $ArgumentList -TimeoutSeconds $TimeoutSeconds -Stage $Stage -SaveReproOnFailure:$SaveReproOnFailure -ErrorHandler $ErrorHandler -ProcessPriority $ProcessPriority
}

function Invoke-BdpgsOcrCommand {
    param(
        [Parameter(Mandatory)] [string]$FilePath,
        [Parameter(Mandatory)] [array]$ArgumentList,
        [int]$TimeoutSeconds = 1800,
        [string]$Stage = 'subtitle-bdpgs-ocr',
        [switch]$SaveReproOnFailure,
        [scriptblock]$ErrorHandler,
        [string]$ProcessPriority = 'inherit'
    )

    return Invoke-ExternalToolCommand -ToolName 'bdpgs-ocr' -FilePath $FilePath -ArgumentList $ArgumentList -TimeoutSeconds $TimeoutSeconds -Stage $Stage -SaveReproOnFailure:$SaveReproOnFailure -ErrorHandler $ErrorHandler -ProcessPriority $ProcessPriority
}

function Invoke-VobSubOcrCommand {
    param(
        [Parameter(Mandatory)] [string]$FilePath,
        [Parameter(Mandatory)] [array]$ArgumentList,
        [int]$TimeoutSeconds = 1800,
        [string]$Stage = 'subtitle-vobsub-ocr',
        [switch]$SaveReproOnFailure,
        [scriptblock]$ErrorHandler,
        [string]$ProcessPriority = 'inherit'
    )

    return Invoke-ExternalToolCommand -ToolName 'vobsub-ocr' -FilePath $FilePath -ArgumentList $ArgumentList -TimeoutSeconds $TimeoutSeconds -Stage $Stage -SaveReproOnFailure:$SaveReproOnFailure -ErrorHandler $ErrorHandler -ProcessPriority $ProcessPriority
}

# Drops a copy-pasteable command line into Failed\Reports\ next to the
# stderr log so the operator can repro a failed ffmpeg/mkvmerge invocation
# directly without re-running the whole pipeline. Best-effort: if the
# Reports directory can't be created or written, returns $null and logs a
# warning rather than aborting the failure-handling path.
function Save-ReproCommand {
    param(
        [Parameter(Mandatory)] [string] $ToolName,
        [Parameter(Mandatory)] [string] $Executable,
        [Parameter(Mandatory)] [array]  $ArgumentList,
        [Parameter(Mandatory)] [string] $Stage
    )

    try {
        if (-not (Test-Path -LiteralPath $LocalFailureReports)) {
            New-Item -ItemType Directory -Path $LocalFailureReports -Force | Out-Null
        }
        $path = Join-Path $LocalFailureReports ("{0}_{1}_{2}.cmd.txt" -f $ToolName, $Stage, (Get-Date -Format 'yyyyMMdd_HHmmss'))
        $body = @(
            '# Run from PowerShell or cmd after adjusting any temporary paths if needed.'
            (Format-NativeCommandLine -FilePath $Executable -ArgumentList $ArgumentList)
        )
        [System.IO.File]::WriteAllLines($path, $body, [System.Text.UTF8Encoding]::new($false))
        return $path
    } catch {
        Write-Log "Could not save repro command for $ToolName/$Stage : $_" "WARN"
        return $null
    }
}
