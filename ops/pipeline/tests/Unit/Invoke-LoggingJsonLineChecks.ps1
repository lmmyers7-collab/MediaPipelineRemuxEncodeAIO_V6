[CmdletBinding()]
param()

if ($PSVersionTable.PSVersion.Major -lt 7) {
    $pwsh = (Get-Command pwsh.exe -ErrorAction SilentlyContinue).Source
    if (-not $pwsh) { $pwsh = (Get-Command pwsh -ErrorAction SilentlyContinue).Source }
    if (-not $pwsh) {
        throw "Logging JSONL checks require PowerShell 7. Install pwsh or use the bundled runtime."
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

. (Join-Path $repoRoot 'ops\pipeline\engine\observability\logging.ps1')

function Assert-True {
    param([bool] $Condition, [string] $Message)
    if (-not $Condition) { throw $Message }
}

function Assert-Equal {
    param($Actual, $Expected, [string] $Message)
    if ($Actual -ne $Expected) {
        throw "$Message Expected '$Expected', got '$Actual'."
    }
}

function Invoke-JsonLineAppendFailsClosedWhenLogLockIsHeldCheck {
    $tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('MediaPipelineLoggingJsonLineTest_' + [guid]::NewGuid().ToString('N'))
    $holder = $null
    $releasePath = $null
    try {
        New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null
        $eventPath = Join-Path $tempRoot 'pipeline_events.jsonl'
        $readyPath = Join-Path $tempRoot 'holder.ready'
        $releasePath = Join-Path $tempRoot 'holder.release'
        $mutexName = 'Global\MediaPipelineJsonLineAppendTest_' + [guid]::NewGuid().ToString('N')

        $holder = Start-Job -ScriptBlock {
            param([string] $Name, [string] $ReadyPath, [string] $ReleasePath)
            $mutex = [System.Threading.Mutex]::new($false, $Name)
            $acquired = $false
            try {
                $acquired = $mutex.WaitOne(0)
                if (-not $acquired) { throw "holder could not acquire $Name" }
                Set-Content -LiteralPath $ReadyPath -Value 'ready' -Encoding UTF8
                $deadline = (Get-Date).AddSeconds(10)
                while (-not (Test-Path -LiteralPath $ReleasePath -PathType Leaf)) {
                    if ((Get-Date) -gt $deadline) { throw 'timed out waiting for release marker' }
                    Start-Sleep -Milliseconds 50
                }
            } finally {
                if ($acquired) { $mutex.ReleaseMutex() }
                $mutex.Dispose()
            }
        } -ArgumentList $mutexName, $readyPath, $releasePath

        $deadline = (Get-Date).AddSeconds(5)
        while (-not (Test-Path -LiteralPath $readyPath -PathType Leaf)) {
            if ((Get-Date) -gt $deadline) { throw 'log mutex holder did not become ready' }
            Start-Sleep -Milliseconds 50
        }

        $script:logLock = [System.Threading.Mutex]::new($false, $mutexName)
        $blocked = Write-JsonLineAppend -Path $eventPath -Payload ([ordered]@{ event_type = 'blocked' }) -UseLogLock
        Assert-True (-not [bool]$blocked) 'Write-JsonLineAppend should return false when the requested log lock is unavailable.'
        Assert-True (-not (Test-Path -LiteralPath $eventPath -PathType Leaf)) 'Write-JsonLineAppend must not append without the requested lock.'

        Set-Content -LiteralPath $releasePath -Value 'release' -Encoding UTF8
        Wait-Job -Job $holder -Timeout 5 | Out-Null
        if ($holder.State -ne 'Completed') {
            throw "log mutex holder did not complete cleanly: $($holder.State)"
        }

        $written = Write-JsonLineAppend -Path $eventPath -Payload ([ordered]@{ event_type = 'written'; nested = @{ ok = $true } }) -UseLogLock
        Assert-True ([bool]$written) 'Write-JsonLineAppend should append after the lock is available.'
        $lines = @(Get-Content -LiteralPath $eventPath)
        Assert-Equal $lines.Count 1 'JSONL file should contain exactly one appended event.'
        $parsed = $lines[0] | ConvertFrom-Json -ErrorAction Stop
        Assert-Equal ([string]$parsed.event_type) 'written' 'JSONL event should remain parseable after locked append.'
        Assert-True ([bool]$parsed.nested.ok) 'Nested JSONL payload should round-trip.'
    } finally {
        if ($null -ne $releasePath -and -not (Test-Path -LiteralPath $releasePath -PathType Leaf)) {
            Set-Content -LiteralPath $releasePath -Value 'release' -Encoding UTF8 -ErrorAction SilentlyContinue
        }
        if ($null -ne $holder) {
            Wait-Job -Job $holder -Timeout 2 | Out-Null
            Receive-Job -Job $holder -ErrorAction SilentlyContinue | Out-Null
            Remove-Job -Job $holder -Force -ErrorAction SilentlyContinue
        }
        if ($script:logLock) {
            $script:logLock.Dispose()
            $script:logLock = $null
        }
        Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Invoke-JsonLineAppendFailsClosedWhenLogLockIsHeldCheck

Write-Host 'Logging JSONL checks passed.'
