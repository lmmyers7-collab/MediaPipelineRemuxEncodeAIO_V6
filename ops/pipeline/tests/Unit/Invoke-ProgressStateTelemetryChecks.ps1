$ErrorActionPreference = 'Stop'

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..\..\..\..')
. (Join-Path $repoRoot 'ops\pipeline\engine\status\progress_state.ps1')

function Assert-Equal {
    param(
        [object]$Actual,
        [object]$Expected,
        [string]$Message
    )
    if ($Actual -ne $Expected) {
        throw "$Message Expected '$Expected', got '$Actual'."
    }
}

function Assert-True {
    param(
        [bool]$Condition,
        [string]$Message
    )
    if (-not $Condition) { throw $Message }
}

function Write-Log {
    param([string]$Message, [string]$Level = 'INFO')
}

$root = Join-Path ([System.IO.Path]::GetTempPath()) ('mediapipeline-progress-telemetry-' + [guid]::NewGuid().ToString('N'))
try {
    New-Item -ItemType Directory -Path $root -Force | Out-Null
    $script:ProgressVersion = 2
    $script:pipelineStatus = 'Processing'
    $script:totalProcessed = 0
    $script:totalEncoded = 0
    $script:totalRemuxed = 0
    $script:totalFailed = 0
    $script:totalMovies = 0
    $script:totalTVEpisodes = 0
    $script:SessionStartedAt = Get-Date
    $script:StopRequested = $false
    $script:SessionPushBytesTotal = 0
    $script:SessionPushSecondsTotal = 0
    $script:SessionPushFilesCompleted = 0
    $script:ProgressWriteFailures = 0
    $script:ProgressPersistenceHealthy = $true
    $global:ProgressFile = Join-Path $root 'pipeline_progress.json'
    $global:PauseFlag = Join-Path $root 'pause.flag'
    $global:StopFlag = Join-Path $root 'stop.flag'
    $global:RescanFlag = Join-Path $root 'rescan.flag'

    Set-ProgressItemContext -DisplayName 'Movie.mkv' -FilePath 'C:\Media\Movie.mkv' -MediaType 'movie' -QueuePhase 'movie' -QueueIndex 1 -QueueTotal 2
    Set-ProgressStage -Stage 'encode_prepare' -Status 'Encoding Movie' -Route 'encode' -Percent 0 -SaveNow
    Set-ProgressAudioTrack `
        -StreamIndex 1 `
        -Stage 'audio_policy' `
        -Status 'Audio stream 1 will be transcoded' `
        -AudioAction 'transcode' `
        -SourceCodec 'dts' `
        -SourceChannels 8 `
        -OutputCodec 'EAC3' `
        -OutputChannels 6 `
        -Language 'eng' `
        -Reason 'channel cap policy' `
        -StepIndex 2 `
        -StepTotal 3 `
        -SaveNow
    Set-ProgressPendingDrain `
        -ManifestCount 4 `
        -AttemptedCount 2 `
        -SucceededCount 1 `
        -AlreadyPublishedCount 1 `
        -RemainingCount 2 `
        -CurrentItem 'Movie.mkv' `
        -Status 'Drain transaction succeeded' `
        -SaveNow

    $payload = Get-Content -LiteralPath $ProgressFile -Raw | ConvertFrom-Json -ErrorAction Stop

    Assert-Equal $payload.AudioProgress.schema_version 'pipeline_audio_progress.v1' 'Audio progress schema version mismatch.'
    Assert-Equal $payload.AudioProgress.action 'transcode' 'Audio progress action mismatch.'
    Assert-Equal ([int]$payload.AudioProgress.step_index) 2 'Audio progress step index mismatch.'
    Assert-Equal $payload.PendingDrainProgress.schema_version 'pipeline_pending_drain_progress.v1' 'Pending drain progress schema version mismatch.'
    Assert-Equal ([int]$payload.PendingDrainProgress.attempted_count) 2 'Pending drain attempted count mismatch.'
    Assert-Equal ([int]$payload.PendingDrainProgress.remaining_count) 2 'Pending drain remaining count mismatch.'
    Assert-True ([bool]($payload.PSObject.Properties.Name -contains 'AudioProgress')) 'AudioProgress field was not serialized.'
    Assert-True ([bool]($payload.PSObject.Properties.Name -contains 'PendingDrainProgress')) 'PendingDrainProgress field was not serialized.'

    $script:ProgressSaveRetryDelaysMs = @(25, 50, 100, 200, 400)
    $lockMarker = Join-Path $root 'progress-reader-lock.ready'
    $lockJob = $null
    try {
        $lockJob = Start-Job -ScriptBlock {
            param($Path, $Marker)
            $stream = [System.IO.File]::Open(
                $Path,
                [System.IO.FileMode]::Open,
                [System.IO.FileAccess]::Read,
                [System.IO.FileShare]::Read
            )
            try {
                [System.IO.File]::WriteAllText($Marker, 'ready')
                Start-Sleep -Milliseconds 300
            } finally {
                $stream.Dispose()
            }
        } -ArgumentList $ProgressFile, $lockMarker

        $deadline = (Get-Date).AddSeconds(5)
        while (-not (Test-Path -LiteralPath $lockMarker -ErrorAction SilentlyContinue) -and (Get-Date) -lt $deadline) {
            Start-Sleep -Milliseconds 10
        }
        Assert-True (Test-Path -LiteralPath $lockMarker -ErrorAction SilentlyContinue) 'Reader-lock test did not acquire the progress file lock.'

        $savedAfterReaderLock = Save-Progress 'Processing after reader lock'
        Assert-True ([bool]$savedAfterReaderLock) 'Save-Progress should retry through a transient reader lock.'
        Assert-Equal ([int]$script:ProgressWriteFailures) 0 'Reader-lock retry should not increment progress write failures.'
        Assert-True ([bool]$script:ProgressPersistenceHealthy) 'Reader-lock retry should leave progress persistence healthy.'

        $payloadAfterReaderLock = Get-Content -LiteralPath $ProgressFile -Raw | ConvertFrom-Json -ErrorAction Stop
        Assert-Equal $payloadAfterReaderLock.Status 'Processing after reader lock' 'Save-Progress did not persist the post-lock status.'
    } finally {
        if ($lockJob) {
            Wait-Job $lockJob -Timeout 5 | Out-Null
            if ($lockJob.State -eq 'Running') {
                Stop-Job $lockJob -ErrorAction SilentlyContinue
            }
            Receive-Job $lockJob -ErrorAction SilentlyContinue | Out-Null
            Remove-Job $lockJob -Force -ErrorAction SilentlyContinue
        }
    }
} finally {
    if (Test-Path -LiteralPath $root -ErrorAction SilentlyContinue) {
        Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Write-Host 'OK: progress state telemetry checks passed.'
