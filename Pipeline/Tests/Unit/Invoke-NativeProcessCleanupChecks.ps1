[CmdletBinding()]
param()

if ($PSVersionTable.PSVersion.Major -lt 7) {
    $pwsh = (Get-Command pwsh.exe -ErrorAction SilentlyContinue).Source
    if (-not $pwsh) { $pwsh = (Get-Command pwsh -ErrorAction SilentlyContinue).Source }
    if (-not $pwsh) {
        throw "Native process cleanup checks require PowerShell 7. Install pwsh or use the bundled runtime."
    }
    & $pwsh -NoProfile -ExecutionPolicy Bypass -File $PSCommandPath @args
    exit $LASTEXITCODE
}

$ErrorActionPreference = 'Stop'

$testsRoot = Split-Path -Parent $PSCommandPath
$pipelineRoot = Split-Path -Parent (Split-Path -Parent $testsRoot)
$repoRoot = Split-Path -Parent $pipelineRoot
$nativeModule = Join-Path $repoRoot 'engine\shared\native.ps1'
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
$childExe = Join-Path $pipelineRoot 'PowerShell-7.6.0-win-x64\pwsh.exe'
if (-not (Test-Path -LiteralPath $childExe -PathType Leaf)) {
    $childExe = (Get-Command pwsh.exe -ErrorAction SilentlyContinue).Source
}
if (-not $childExe) {
    $childExe = (Get-Command pwsh -ErrorAction SilentlyContinue).Source
}
Assert-True (-not [string]::IsNullOrWhiteSpace($childExe)) 'PowerShell child runtime was not found.'

try {
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
} finally {
    if ($childPid -gt 0 -and (Test-ProcessAlive -ProcessId $childPid)) {
        Stop-Process -Id $childPid -Force -ErrorAction SilentlyContinue
    }
    Remove-Item -LiteralPath $stopFlag -Force -ErrorAction SilentlyContinue
}

Write-Host 'Native process cleanup checks passed.'
