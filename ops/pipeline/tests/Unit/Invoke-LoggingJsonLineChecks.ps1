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

function Invoke-PipelineEventLogRotationCheck {
    $tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('MediaPipelineEventLogRotationTest_' + [guid]::NewGuid().ToString('N'))
    $oldLogLock = $script:logLock
    $oldEventLogFile = $script:PipelineEventLogFile
    $oldMaxBytes = $script:PipelineEventLogMaxBytes
    $oldArchiveFolderName = $script:PipelineEventArchiveFolderName
    $oldRetentionDays = $script:LogRetentionDays
    try {
        New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null
        $mutexName = 'Global\MediaPipelineEventLogRotationTest_' + [guid]::NewGuid().ToString('N')
        $script:logLock = [System.Threading.Mutex]::new($false, $mutexName)
        $script:PipelineEventLogMaxBytes = 64
        $script:PipelineEventArchiveFolderName = 'ArchivedEvents'
        $script:LogRetentionDays = 14

        $eventPath = Join-Path $tempRoot 'pipeline_events.jsonl'
        $script:PipelineEventLogFile = $eventPath
        [System.IO.File]::WriteAllText($eventPath, ('x' * 80), [System.Text.Encoding]::UTF8)

        $written = Write-PipelineEvent -EventType 'rotation_test' -Stage 'unit' -Status 'ok' -Data @{ case = 'rotation' }
        Assert-True ([bool]$written) 'Write-PipelineEvent should append after rotating an oversized event journal.'

        $archiveDir = Join-Path $tempRoot 'ArchivedEvents'
        $archives = @(Get-ChildItem -LiteralPath $archiveDir -Filter 'pipeline_events.*.archived.jsonl' -ErrorAction Stop)
        Assert-Equal $archives.Count 1 'Oversized pipeline_events.jsonl should be moved into exactly one archive file.'
        Assert-Equal ([System.IO.File]::ReadAllText($archives[0].FullName, [System.Text.Encoding]::UTF8)) ('x' * 80) 'Archived event journal should preserve previous content.'
        $lines = @(Get-Content -LiteralPath $eventPath)
        Assert-Equal $lines.Count 1 'Fresh pipeline_events.jsonl should contain exactly the newly appended event.'
        $parsed = $lines[0] | ConvertFrom-Json -ErrorAction Stop
        Assert-Equal ([string]$parsed.event_type) 'rotation_test' 'Rotated event journal should contain the submitted event.'

        $otherPath = Join-Path $tempRoot 'other.jsonl'
        [System.IO.File]::WriteAllText($otherPath, ('y' * 80), [System.Text.Encoding]::UTF8)
        $otherWritten = Write-JsonLineAppend -Path $otherPath -Payload ([ordered]@{ event_type = 'not_rotated' }) -UseLogLock -RotatePipelineEventLog
        Assert-True ([bool]$otherWritten) 'Write-JsonLineAppend should still append non-event JSONL files.'
        $archivesAfterOther = @(Get-ChildItem -LiteralPath $archiveDir -Filter 'other.*' -ErrorAction SilentlyContinue)
        Assert-Equal $archivesAfterOther.Count 0 'Rotation must be limited to pipeline_events.jsonl.'
    } finally {
        if ($script:logLock -and $script:logLock -ne $oldLogLock) {
            $script:logLock.Dispose()
        }
        $script:logLock = $oldLogLock
        $script:PipelineEventLogFile = $oldEventLogFile
        $script:PipelineEventLogMaxBytes = $oldMaxBytes
        $script:PipelineEventArchiveFolderName = $oldArchiveFolderName
        $script:LogRetentionDays = $oldRetentionDays
        Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}

function Invoke-DebugLogRotationDuringWriteCheck {
    $tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('MediaPipelineDebugLogRotationTest_' + [guid]::NewGuid().ToString('N'))
    $oldLogLock = $script:logLock
    $oldLogFile = $global:LogFile
    $oldConsoleLogLevel = $script:ConsoleLogLevel
    $oldFileLogLevel = $script:FileLogLevel
    $oldRetentionDays = $script:LogRetentionDays
    $oldMaxBytes = $script:PipelineDebugLogMaxBytes
    $oldLastRotation = $script:PipelineDebugLogLastRotationAt
    $oldLastArchive = $script:PipelineDebugLogLastArchivePath
    try {
        New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null
        $mutexName = 'Global\MediaPipelineDebugLogRotationTest_' + [guid]::NewGuid().ToString('N')
        $script:logLock = [System.Threading.Mutex]::new($false, $mutexName)
        $global:LogFile = Join-Path $tempRoot 'pipeline_debug.log'
        $script:ConsoleLogLevel = 'ERROR'
        $script:FileLogLevel = 'DEBUG'
        $script:LogRetentionDays = 14
        $script:PipelineDebugLogMaxBytes = 64
        $script:PipelineDebugLogLastRotationAt = ''
        $script:PipelineDebugLogLastArchivePath = ''
        [System.IO.File]::WriteAllText($global:LogFile, ('x' * 80), [System.Text.Encoding]::UTF8)

        Write-Log 'rotation check line' 'INFO'

        $archives = @(Get-ChildItem -LiteralPath $tempRoot -Filter 'pipeline_debug_*.log.old' -ErrorAction Stop)
        Assert-Equal $archives.Count 1 'Oversized pipeline_debug.log should rotate during Write-Log.'
        Assert-Equal ([System.IO.File]::ReadAllText($archives[0].FullName, [System.Text.Encoding]::UTF8)) ('x' * 80) 'Debug log archive should preserve previous content.'
        $newText = [System.IO.File]::ReadAllText($global:LogFile, [System.Text.Encoding]::UTF8)
        Assert-True ($newText -match 'rotation check line') 'Fresh debug log should contain the triggering log line.'
        Assert-True (-not [string]::IsNullOrWhiteSpace([string]$script:PipelineDebugLogLastRotationAt)) 'Debug log rotation should stamp last rotation time.'
        Assert-True (-not [string]::IsNullOrWhiteSpace([string]$script:PipelineDebugLogLastArchivePath)) 'Debug log rotation should stamp archive path.'
    } finally {
        if ($script:logLock -and $script:logLock -ne $oldLogLock) {
            $script:logLock.Dispose()
        }
        $script:logLock = $oldLogLock
        $global:LogFile = $oldLogFile
        $script:ConsoleLogLevel = $oldConsoleLogLevel
        $script:FileLogLevel = $oldFileLogLevel
        $script:LogRetentionDays = $oldRetentionDays
        $script:PipelineDebugLogMaxBytes = $oldMaxBytes
        $script:PipelineDebugLogLastRotationAt = $oldLastRotation
        $script:PipelineDebugLogLastArchivePath = $oldLastArchive
        Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}

function Invoke-ConcurrentCompletedManifestJsonLineAppendCheck {
    $tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('MediaPipelineCompletedJsonLineStress_' + [guid]::NewGuid().ToString('N'))
    $jobs = @()
    try {
        New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null
        $manifestPath = Join-Path $tempRoot 'completed_jobs.jsonl'
        $mutexName = 'Global\MediaPipelineCompletedJsonLineStress_' + [guid]::NewGuid().ToString('N')
        for ($slot = 0; $slot -lt 4; $slot++) {
            $jobs += Start-Job -ScriptBlock {
                param([string] $RepoRoot, [string] $ManifestPath, [string] $MutexName, [int] $Slot)
                . (Join-Path $RepoRoot 'ops\pipeline\engine\observability\logging.ps1')
                $script:logLock = [System.Threading.Mutex]::new($false, $MutexName)
                try {
                    for ($index = 0; $index -lt 50; $index++) {
                        $ok = Write-JsonLineAppend -Path $ManifestPath -Payload ([ordered]@{
                            schema_version = 'completed_job.v1'
                            slot           = $Slot
                            index          = $index
                            output_path    = "C:\Out\slot-$Slot-$index.mkv"
                        }) -Depth 10 -UseLogLock
                        if (-not [bool]$ok) { throw "append failed for slot $Slot index $index" }
                    }
                } finally {
                    if ($script:logLock) {
                        $script:logLock.Dispose()
                        $script:logLock = $null
                    }
                }
            } -ArgumentList $repoRoot, $manifestPath, $mutexName, $slot
        }

        Wait-Job -Job $jobs -Timeout 30 | Out-Null
        $notDone = @($jobs | Where-Object { $_.State -ne 'Completed' })
        if ($notDone.Count -gt 0) {
            throw "concurrent append jobs did not complete: $($notDone.State -join ', ')"
        }
        foreach ($job in $jobs) {
            Receive-Job -Job $job -ErrorAction Stop | Out-Null
        }

        $lines = @(Get-Content -LiteralPath $manifestPath)
        Assert-Equal $lines.Count 200 'Concurrent completed manifest append should preserve every JSONL row.'
        foreach ($line in $lines) {
            $parsed = $line | ConvertFrom-Json -ErrorAction Stop
            Assert-Equal ([string]$parsed.schema_version) 'completed_job.v1' 'Completed manifest JSONL row schema mismatch.'
        }
    } finally {
        foreach ($job in $jobs) {
            Remove-Job -Job $job -Force -ErrorAction SilentlyContinue
        }
        Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Invoke-JsonLineAppendFailsClosedWhenLogLockIsHeldCheck
Invoke-PipelineEventLogRotationCheck
Invoke-DebugLogRotationDuringWriteCheck
Invoke-ConcurrentCompletedManifestJsonLineAppendCheck

Write-Host 'Logging JSONL checks passed.'
