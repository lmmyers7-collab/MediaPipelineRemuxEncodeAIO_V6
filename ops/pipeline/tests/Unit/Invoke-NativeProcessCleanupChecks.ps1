[CmdletBinding()]
param()

if ($PSVersionTable.PSVersion.Major -lt 7) {
    $bootstrapTestsRoot = Split-Path -Parent $PSCommandPath
    $bootstrapPipelineRoot = Split-Path -Parent (Split-Path -Parent $bootstrapTestsRoot)
    $pwsh = Join-Path $bootstrapPipelineRoot 'runtime\PowerShell-7.6.0-win-x64\pwsh.exe'
    if (-not (Test-Path -LiteralPath $pwsh -PathType Leaf)) {
        throw "Native process cleanup checks require the promoted bundled PowerShell runtime: $pwsh"
    }
    & $pwsh -NoProfile -ExecutionPolicy Bypass -File $PSCommandPath @args
    exit $LASTEXITCODE
}

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
$nativeModule = Join-Path $repoRoot 'ops\pipeline\engine\shared\native.ps1'
$stopFlag = Join-Path ([System.IO.Path]::GetTempPath()) ("mediapipeline-native-cleanup-{0}.stop" -f ([Guid]::NewGuid().ToString('N')))

function Assert-True {
    param(
        [bool]$Condition,
        [string]$Message
    )
    if (-not $Condition) { throw $Message }
}

function DebugLog {
    param([string]$Message)
}

function Write-Log {
    param(
        [string]$Message,
        [string]$Level = 'INFO'
    )
}

function Set-ProgressStage {
    param(
        [string]$Stage,
        [string]$Status,
        $Percent,
        [switch]$SaveNow
    )
}

function Test-IsUncPath {
    param([string] $Path)
    return $false
}

$script:CapturedPipelineEvents = @()
function Write-PipelineEvent {
    param(
        [string]$EventType,
        [string]$Stage,
        [string]$Status,
        [hashtable]$Data
    )
    $script:CapturedPipelineEvents += [pscustomobject]@{
        EventType = $EventType
        Stage = $Stage
        Status = $Status
        Data = $Data
    }
    return $true
}

function Test-ProcessAlive {
    param([int]$ProcessId)
    try {
        $candidate = Get-Process -Id $ProcessId -ErrorAction Stop
        return (-not $candidate.HasExited)
    } catch {
        return $false
    }
}

function Wait-ProcessExitObserved {
    param(
        [int]$ProcessId,
        [int]$TimeoutMilliseconds = 5000
    )
    $deadline = [DateTime]::UtcNow.AddMilliseconds($TimeoutMilliseconds)
    while ([DateTime]::UtcNow -lt $deadline) {
        if (-not (Test-ProcessAlive -ProcessId $ProcessId)) {
            return $true
        }
        Start-Sleep -Milliseconds 100
    }
    return (-not (Test-ProcessAlive -ProcessId $ProcessId))
}

. $nativeModule

$script:FallbackFactoryCalls = [System.Collections.Generic.List[object]]::new()
$script:FallbackPollState = [pscustomobject]@{
    Elapsed = [System.Collections.Generic.List[double]]::new()
}
$script:LastFallbackPollHandler = $null
function ConvertTo-MediaPipelineRunMonitorStageId {
    param([string] $PipelineStage)
    switch (([string]$PipelineStage).Trim().ToLowerInvariant()) {
        'probe' { return 'probe' }
        'encode_verify' { return 'verification' }
        default { return '' }
    }
}

function New-MediaPipelineCurrentStageNativePollHandler {
    param(
        [string] $Stage,
        [string] $Status = '',
        [string] $Route = '',
        [double] $MinimumIntervalSeconds = 15,
        [string] $EvidenceSource = ''
    )
    $script:FallbackFactoryCalls.Add([pscustomobject]@{
        RunId = [string]$script:PipelineRunId
        JobId = [string]$script:CurrentRunMonitorJobId
        Stage = $Stage
        Status = $Status
        Route = $Route
        MinimumIntervalSeconds = $MinimumIntervalSeconds
        EvidenceSource = $EvidenceSource
    }) | Out-Null
    $pollState = $script:FallbackPollState
    $writer = {
        param($ElapsedSeconds, $Process)
        $pollState.Elapsed.Add([double]$ElapsedSeconds) | Out-Null
        return $null
    }.GetNewClosure()
    $handler = New-ThrottledNativePollHandler -Handler $writer -MinimumIntervalSeconds $MinimumIntervalSeconds
    $script:LastFallbackPollHandler = $handler
    return $handler
}

$script:StopRequested = $false
$script:StopFlag = $stopFlag
$childPid = 0
$childExe = Join-Path $pipelineRoot 'runtime\PowerShell-7.6.0-win-x64\pwsh.exe'
Assert-True (Test-Path -LiteralPath $childExe -PathType Leaf) "Promoted bundled PowerShell child runtime was not found: $childExe"
$workingDirectoryRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("mediapipeline-native-working-directory-{0}" -f ([Guid]::NewGuid().ToString('N')))
New-Item -ItemType Directory -Path $workingDirectoryRoot | Out-Null
$resolvedWorkingDirectoryRoot = (Resolve-Path -LiteralPath $workingDirectoryRoot).ProviderPath

try {
    $script:ThrottledPollCount = 0
    $throttledHandler = New-ThrottledNativePollHandler -MinimumIntervalSeconds 5 -Handler {
        param($ElapsedSeconds, $Process)
        $script:ThrottledPollCount++
        return $null
    }
    & $throttledHandler 0 $null
    & $throttledHandler 1 $null
    & $throttledHandler 5 $null
    Assert-True ($script:ThrottledPollCount -eq 2) 'Generic native poll handler must invoke immediately and then only at the configured interval.'

    $scanRoot = Join-Path $workingDirectoryRoot 'scan-fixture'
    New-Item -ItemType Directory -Path $scanRoot -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $scanRoot 'a.mkv') -Value 'a' -Encoding ASCII
    Set-Content -LiteralPath (Join-Path $scanRoot 'b.mkv') -Value 'b' -Encoding ASCII
    $script:ScanPollElapsed = [System.Collections.Generic.List[double]]::new()
    $scanPollHandler = New-ThrottledNativePollHandler -MinimumIntervalSeconds 15 -Handler {
        param($ElapsedSeconds, $Process)
        $script:ScanPollElapsed.Add([double]$ElapsedSeconds) | Out-Null
        return $null
    }
    $scanResults = @(Invoke-RecursivePathScan -Path $scanRoot -ItemType File -TimeoutSeconds 10 -Label 'heartbeat scan fixture' -PollHandler $scanPollHandler)
    Assert-True ($scanResults.Count -eq 2) 'Heartbeat-enabled recursive scan must preserve the exact file result set.'
    Assert-True ($script:ScanPollElapsed.Count -gt 0) 'Recursive scan must invoke its explicit current-stage callback while the Wait-Job loop is active.'
    Assert-True ([double]$script:ScanPollElapsed[0] -lt 30.0) 'Recursive scan callback must receive elapsed seconds, not item counts or another manufactured progress value.'
    & $scanPollHandler 46 $null | Out-Null
    Assert-True (@($script:ScanPollElapsed | Where-Object { $_ -ge 45 }).Count -eq 1) 'A simulated greater-than-45-second scan must produce a fresh indeterminate heartbeat.'

    $script:SleepPollElapsed = [System.Collections.Generic.List[double]]::new()
    $sleepPollHandler = New-ThrottledNativePollHandler -MinimumIntervalSeconds 15 -Handler {
        param($ElapsedSeconds, $Process)
        $script:SleepPollElapsed.Add([double]$ElapsedSeconds) | Out-Null
        return $null
    }
    Assert-True (Start-StopAwareSleep -Seconds 1 -PollHandler $sleepPollHandler) 'Stop-aware heartbeat sleep fixture should complete normally.'
    Assert-True ($script:SleepPollElapsed.Count -gt 0) 'Stop-aware waits must invoke their exact current-stage callback.'
    & $sleepPollHandler 46 $null | Out-Null
    Assert-True (@($script:SleepPollElapsed | Where-Object { $_ -ge 45 }).Count -eq 1) 'A simulated greater-than-45-second stop-aware wait must produce a fresh indeterminate heartbeat.'

    $script:ForwardedOcrPollCount = 0
    $forwardedOcrPollResult = Invoke-BdpgsOcrCommand `
        -FilePath $childExe `
        -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', 'Start-Sleep -Milliseconds 350') `
        -TimeoutSeconds 10 `
        -Stage 'native-ocr-poll-forwarding' `
        -PollMilliseconds 20 `
        -PollHandler {
            param($ElapsedSeconds, $Process)
            $script:ForwardedOcrPollCount++
            return $null
        }
    Assert-True ([int]$forwardedOcrPollResult.ExitCode -eq 0) 'Fake long-running OCR child should exit cleanly.'
    Assert-True ($script:ForwardedOcrPollCount -gt 0) 'OCR wrapper must forward PollHandler through Invoke-ExternalToolCommand to Invoke-NativeProcess.'

    $script:PipelineRunId = 'native-fallback-run'
    $script:CurrentRunMonitorJobId = 'native-fallback-run-item-00000001'
    $script:currentStage = 'probe'
    $script:pipelineStatus = 'Backend source probe is active'
    $script:currentRoute = 'remux'
    $script:FallbackFactoryCalls.Clear()
    $script:FallbackPollState.Elapsed.Clear()
    $fallbackResult = Invoke-ExternalToolCommand `
        -ToolName 'fallback-probe-test' `
        -FilePath $childExe `
        -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', 'Start-Sleep -Milliseconds 350') `
        -TimeoutSeconds 10 `
        -Stage 'internal-tool-label-must-not-be-authority' `
        -PollMilliseconds 20
    Assert-True ([int]$fallbackResult.ExitCode -eq 0) 'Exact-context fallback child should exit cleanly.'
    Assert-True ($script:FallbackFactoryCalls.Count -eq 1) 'Missing explicit PollHandler must request one exact current-stage fallback.'
    Assert-True ($script:FallbackFactoryCalls[0].RunId -eq 'native-fallback-run' -and $script:FallbackFactoryCalls[0].JobId -eq 'native-fallback-run-item-00000001') 'Fallback factory must capture exact run/job identity.'
    Assert-True ($script:FallbackFactoryCalls[0].Stage -eq 'probe') 'Fallback factory must use backend current stage, never the internal tool Stage label.'
    Assert-True ($script:FallbackFactoryCalls[0].Status -eq 'Backend source probe is active') 'Fallback factory must preserve backend current status.'
    Assert-True ([string]::IsNullOrWhiteSpace([string]$script:FallbackFactoryCalls[0].Route)) 'Fallback liveness must not refresh a raw compatibility route; explicit call sites own backend-known route evidence.'
    Assert-True ($script:FallbackFactoryCalls[0].MinimumIntervalSeconds -eq 15) 'Fallback native heartbeat must be throttled at the shared bounded interval.'
    Assert-True ($script:FallbackFactoryCalls[0].EvidenceSource -eq 'native_process_fallback_heartbeat') 'Fallback native heartbeat must disclose its supporting evidence source.'
    Assert-True ($script:FallbackPollState.Elapsed.Count -gt 0) 'Fallback handler must reach the native process poll loop.'
    & $script:LastFallbackPollHandler 46 $null | Out-Null
    Assert-True (@($script:FallbackPollState.Elapsed | Where-Object { $_ -ge 45 }).Count -eq 1) 'Fake long-running fallback must refresh after a greater-than-45-second elapsed poll without fabricating progress.'

    $fallbackFactoryCountBeforeMissingContext = $script:FallbackFactoryCalls.Count
    $fallbackPollCountBeforeMissingContext = $script:FallbackPollState.Elapsed.Count
    $script:PipelineRunId = ''
    $missingContextResult = Invoke-ExternalToolCommand `
        -ToolName 'fallback-missing-context-test' `
        -FilePath $childExe `
        -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', 'Start-Sleep -Milliseconds 100') `
        -TimeoutSeconds 10 `
        -Stage 'probe' `
        -PollMilliseconds 20
    Assert-True ([int]$missingContextResult.ExitCode -eq 0) 'Missing-context child should exit cleanly.'
    Assert-True ($script:FallbackFactoryCalls.Count -eq $fallbackFactoryCountBeforeMissingContext) 'Missing exact run context must not create a fallback handler.'
    Assert-True ($script:FallbackPollState.Elapsed.Count -eq $fallbackPollCountBeforeMissingContext) 'Missing exact context must not mutate heartbeat evidence.'

    $script:PipelineRunId = 'native-fallback-run'
    $script:ExplicitPollCount = 0
    $fallbackFactoryCountBeforeExplicit = $script:FallbackFactoryCalls.Count
    $explicitResult = Invoke-ExternalToolCommand `
        -ToolName 'explicit-poll-precedence-test' `
        -FilePath $childExe `
        -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', 'Start-Sleep -Milliseconds 200') `
        -TimeoutSeconds 10 `
        -Stage 'different-internal-label' `
        -PollMilliseconds 20 `
        -PollHandler {
            param($ElapsedSeconds, $Process)
            $script:ExplicitPollCount++
            return $null
        }
    Assert-True ([int]$explicitResult.ExitCode -eq 0) 'Explicit-poll child should exit cleanly.'
    Assert-True ($script:ExplicitPollCount -gt 0) 'Explicit PollHandler must reach the native process poll loop.'
    Assert-True ($script:FallbackFactoryCalls.Count -eq $fallbackFactoryCountBeforeExplicit) 'Explicit PollHandler must suppress fallback creation.'

    $script:PipelineRunId = ''
    $script:CurrentRunMonitorJobId = ''
    $script:currentStage = ''
    $script:pipelineStatus = ''
    $script:currentRoute = ''

    $expectedExitResult = Invoke-ExternalToolCommand `
        -ToolName 'expected-exit-test' `
        -FilePath $childExe `
        -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', 'exit 2') `
        -TimeoutSeconds 10 `
        -Stage 'expected-exit-telemetry' `
        -SuccessExitCodes @(0, 2)
    $expectedExitEvent = @($script:CapturedPipelineEvents | Where-Object {
        $_.EventType -eq 'tool_completed' -and $_.Stage -eq 'expected-exit-telemetry'
    })[-1]
    Assert-True ([int]$expectedExitResult.ExitCode -eq 2) "Expected exit-code test child to return 2; got $($expectedExitResult.ExitCode)."
    Assert-True ([string]$expectedExitEvent.Status -eq 'succeeded') 'Configured expected exit code should emit successful tool telemetry.'
    Assert-True ([string]$expectedExitEvent.Data.error_code -eq 'OK') 'Configured expected exit code should retain the OK telemetry error code.'

    $workingDirectoryResult = Invoke-NativeProcess `
        -FilePath $childExe `
        -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', '[Console]::Out.Write((Get-Location).ProviderPath)') `
        -TimeoutSeconds 10 `
        -StopFlagPath $stopFlag `
        -Label 'native-working-directory-regression-child' `
        -WorkingDirectory $workingDirectoryRoot

    Assert-True ([int]$workingDirectoryResult.ExitCode -eq 0) "Expected working-directory child to exit cleanly; got $($workingDirectoryResult.ExitCode)."
    Assert-True (([string]$workingDirectoryResult.Stdout).Trim() -eq $resolvedWorkingDirectoryRoot) "Native process did not start in the requested working directory."
    Assert-True ([string]$workingDirectoryResult.WorkingDirectory -eq $resolvedWorkingDirectoryRoot) "Native result did not retain the resolved working directory."

    $result = Invoke-NativeProcess `
        -FilePath $childExe `
        -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', 'Start-Sleep -Seconds 60') `
        -TimeoutSeconds 0 `
        -StopFlagPath $stopFlag `
        -Label 'native-cleanup-regression-child' `
        -ProcessStartedHandler {
            param($Process)
            $script:childPid = [int]$Process.Id
            $Process.StandardOutput.Close()
        }

    Assert-True ($childPid -gt 0) 'Native cleanup test did not capture the child PID.'
    Assert-True ([int]$result.ExitCode -eq -2) "Expected start/run failure exit code -2 after forced reader fault; got $($result.ExitCode)."
    Assert-True ([string]$result.ErrorCode -eq 'NATIVE_START_FAILED') "Expected NATIVE_START_FAILED after forced reader fault; got $($result.ErrorCode)."
    Assert-True (Wait-ProcessExitObserved -ProcessId $childPid -TimeoutMilliseconds 5000) "Child process $childPid remained alive after Invoke-NativeProcess handled a post-start fault."

    $abortChildPid = 0
    $abortResult = Invoke-NativeProcess `
        -FilePath $childExe `
        -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', 'Start-Sleep -Seconds 60') `
        -TimeoutSeconds 0 `
        -StopFlagPath $stopFlag `
        -Label 'native-poll-abort-regression-child' `
        -PollMilliseconds 20 `
        -ProcessStartedHandler {
            param($Process)
            $script:abortChildPid = [int]$Process.Id
        } `
        -PollHandler {
            param($ElapsedSeconds, $Process)
            if ($ElapsedSeconds -ge 0.05) {
                return @{
                    Abort = $true
                    AbortCode = 'TEST_NATIVE_POLL_ABORT'
                    AbortReason = 'unit test requested poll abort'
                }
            }
            return $null
        }

    Assert-True ($abortChildPid -gt 0) 'Native poll-abort test did not capture the child PID.'
    Assert-True ([int]$abortResult.ExitCode -eq -1) "Expected poll abort exit code -1; got $($abortResult.ExitCode)."
    Assert-True ([bool]$abortResult.Aborted) 'Poll abort result should expose Aborted=true.'
    Assert-True ([string]$abortResult.ErrorCode -eq 'TEST_NATIVE_POLL_ABORT') "Poll abort should preserve the requested error code; got $($abortResult.ErrorCode)."
    Assert-True ([string]$abortResult.AbortReason -eq 'unit test requested poll abort') "Poll abort should preserve the requested reason; got $($abortResult.AbortReason)."
    Assert-True (Wait-ProcessExitObserved -ProcessId $abortChildPid -TimeoutMilliseconds 5000) "Child process $abortChildPid remained alive after poll abort."

    $idleChildPid = 0
    $previousIdleAbortCount = [int]$script:NativeIdleWatchdogAbortCount
    $idleResult = Invoke-NativeProcess `
        -FilePath $childExe `
        -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', 'Start-Sleep -Seconds 60') `
        -TimeoutSeconds 0 `
        -IdleTimeoutSeconds 1 `
        -IdleTimeoutErrorCode 'TEST_NATIVE_IDLE_TIMEOUT' `
        -StopFlagPath $stopFlag `
        -Label 'native-idle-watchdog-regression-child' `
        -PollMilliseconds 20 `
        -ProcessStartedHandler {
            param($Process)
            $script:idleChildPid = [int]$Process.Id
        }

    Assert-True ($idleChildPid -gt 0) 'Native idle-watchdog test did not capture the child PID.'
    Assert-True ([int]$idleResult.ExitCode -eq -1) "Expected idle watchdog abort exit code -1; got $($idleResult.ExitCode)."
    Assert-True ([bool]$idleResult.Aborted) 'Idle watchdog result should expose Aborted=true.'
    Assert-True ([bool]$idleResult.IdleTimedOut) 'Idle watchdog result should expose IdleTimedOut=true.'
    Assert-True ([string]$idleResult.ErrorCode -eq 'TEST_NATIVE_IDLE_TIMEOUT') "Idle watchdog should preserve the requested error code; got $($idleResult.ErrorCode)."
    Assert-True ([string]$idleResult.AbortReason -like '*produced no output for 1s*') "Idle watchdog should preserve a no-progress abort reason; got $($idleResult.AbortReason)."
    Assert-True ([int]$script:NativeIdleWatchdogAbortCount -eq ($previousIdleAbortCount + 1)) 'Idle watchdog should increment the native idle abort counter.'
    Assert-True (Wait-ProcessExitObserved -ProcessId $idleChildPid -TimeoutMilliseconds 5000) "Child process $idleChildPid remained alive after idle watchdog abort."
} finally {
    if ($childPid -gt 0 -and (Test-ProcessAlive -ProcessId $childPid)) {
        Stop-Process -Id $childPid -Force -ErrorAction SilentlyContinue
    }
    if ($abortChildPid -gt 0 -and (Test-ProcessAlive -ProcessId $abortChildPid)) {
        Stop-Process -Id $abortChildPid -Force -ErrorAction SilentlyContinue
    }
    if ($idleChildPid -gt 0 -and (Test-ProcessAlive -ProcessId $idleChildPid)) {
        Stop-Process -Id $idleChildPid -Force -ErrorAction SilentlyContinue
    }
    Remove-Item -LiteralPath $stopFlag -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $workingDirectoryRoot -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host 'Native process cleanup checks passed.'
