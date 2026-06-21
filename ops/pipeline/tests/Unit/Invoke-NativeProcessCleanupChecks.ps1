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

$script:StopRequested = $false
$script:StopFlag = $stopFlag
$childPid = 0
$childExe = Join-Path $pipelineRoot 'runtime\PowerShell-7.6.0-win-x64\pwsh.exe'
Assert-True (Test-Path -LiteralPath $childExe -PathType Leaf) "Promoted bundled PowerShell child runtime was not found: $childExe"
$workingDirectoryRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("mediapipeline-native-working-directory-{0}" -f ([Guid]::NewGuid().ToString('N')))
New-Item -ItemType Directory -Path $workingDirectoryRoot | Out-Null
$resolvedWorkingDirectoryRoot = (Resolve-Path -LiteralPath $workingDirectoryRoot).ProviderPath

try {
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
} finally {
    if ($childPid -gt 0 -and (Test-ProcessAlive -ProcessId $childPid)) {
        Stop-Process -Id $childPid -Force -ErrorAction SilentlyContinue
    }
    if ($abortChildPid -gt 0 -and (Test-ProcessAlive -ProcessId $abortChildPid)) {
        Stop-Process -Id $abortChildPid -Force -ErrorAction SilentlyContinue
    }
    Remove-Item -LiteralPath $stopFlag -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $workingDirectoryRoot -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host 'Native process cleanup checks passed.'
