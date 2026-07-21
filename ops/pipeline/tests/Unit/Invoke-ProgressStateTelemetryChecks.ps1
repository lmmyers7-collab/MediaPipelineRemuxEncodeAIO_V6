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

$script:WorkerHeartbeatCalls = [System.Collections.Generic.List[object]]::new()
function Write-MediaPipelineWorkerChildHeartbeat {
    param([string]$Stage = '', [string]$Status = '', [switch]$Final)
    $script:WorkerHeartbeatCalls.Add([pscustomobject]@{
        Stage = $Stage
        Status = $Status
        Final = [bool]$Final
    }) | Out-Null
}

$script:RunMonitorTrackProgressCalls = [System.Collections.Generic.List[object]]::new()
$script:RunMonitorStageCalls = [System.Collections.Generic.List[object]]::new()
$script:RunMonitorRunStateCalls = [System.Collections.Generic.List[object]]::new()
$script:ActiveTrackHeartbeatCalls = [System.Collections.Generic.List[object]]::new()
$script:RunMonitorSubtitlePolicyFinal = $true
$script:RunMonitorSubtitleTrackStates = [ordered]@{
    'subtitle:sidecar:7' = 'awaiting_evidence'
    'subtitle:embedded:8' = 'awaiting_evidence'
}
function Set-MediaPipelineRunMonitorTrackProgress {
    param(
        [string]$Kind,
        [string]$RunId,
        [string]$JobId,
        [string]$TrackId = '',
        [int]$StreamIndex = -1,
        [string]$CurrentAction,
        [string]$State,
        $Numerator,
        $Denominator,
        [switch]$Indeterminate,
        [string]$Result,
        [string]$OutputCodec = '',
        [string]$OutputLocation = '',
        [string]$OutputPath = '',
        [string]$ParkedPath = '',
        [string]$IntendedFinalPath = '',
        [int]$StepIndex = 0,
        [int]$StepTotal = 0,
        [string]$StepName = '',
        [string]$ProgressUnit = '',
        $CueCount = $null,
        [switch]$NumericOnly
    )
    $script:RunMonitorTrackProgressCalls.Add([pscustomobject]@{
        Kind = $Kind
        RunId = $RunId
        JobId = $JobId
        TrackId = $TrackId
        StreamIndex = $StreamIndex
        CurrentAction = $CurrentAction
        State = $State
        OutputCodec = $OutputCodec
        OutputLocation = $OutputLocation
        OutputPath = $OutputPath
        StepIndex = $StepIndex
        StepTotal = $StepTotal
        StepName = $StepName
        ProgressUnit = $ProgressUnit
        CueCount = $CueCount
    }) | Out-Null

    if ($Kind -ne 'subtitles') { return $null }

    $matched = (-not [string]::IsNullOrWhiteSpace($TrackId) -and
        $script:RunMonitorSubtitleTrackStates.Contains($TrackId))
    if ($matched) {
        $script:RunMonitorSubtitleTrackStates[$TrackId] = $State
    }
    $states = @($script:RunMonitorSubtitleTrackStates.Values | ForEach-Object { [string]$_ })
    $collectionState = if (-not $matched) {
        'unknown'
    } elseif ('review' -in $states) {
        'review'
    } elseif ('failed' -in $states) {
        'failed'
    } elseif ('active' -in $states) {
        'active'
    } elseif ('awaiting_evidence' -in $states) {
        'awaiting_evidence'
    } else {
        'completed'
    }
    $tracks = @($script:RunMonitorSubtitleTrackStates.Keys | ForEach-Object {
        [pscustomobject]@{ track_id = [string]$_; state = [string]$script:RunMonitorSubtitleTrackStates[$_] }
    })
    return [pscustomobject]@{
        items = @([pscustomobject]@{
            job_id = $JobId
            subtitles = [pscustomobject]@{
                policy_final = [bool]$script:RunMonitorSubtitlePolicyFinal
                state = $collectionState
                tracks = $tracks
            }
        })
    }
}

function Set-MediaPipelineCurrentRunMonitorStage {
    param(
        [string]$StageId,
        [string]$State,
        [string]$Detail = '',
        [string]$ReasonCode = '',
        [string]$EvidenceSource = '',
        $Numerator = $null,
        $Denominator = $null,
        [switch]$Indeterminate,
        [switch]$NumericOnly
    )
    $script:RunMonitorStageCalls.Add([pscustomobject]@{
        StageId = $StageId
        State = $State
        Detail = $Detail
        ReasonCode = $ReasonCode
        EvidenceSource = $EvidenceSource
        Indeterminate = [bool]$Indeterminate
    }) | Out-Null
}

function ConvertTo-MediaPipelineRunMonitorStageId {
    param([string]$PipelineStage)
    if ($PipelineStage -match '^copy') { return 'copy_to_scratch' }
    if ($PipelineStage -match '^(encode_verify|remux_verify|verification)$') { return 'verification' }
    if ($PipelineStage -match '^encode') { return 'transcode' }
    return ''
}

function Set-MediaPipelineRunMonitorStage {
    param(
        [string]$RunId,
        [string]$JobId,
        [string]$StageId,
        [string]$State,
        [string]$Detail = '',
        [string]$EvidenceSource = '',
        $Numerator = $null,
        $Denominator = $null,
        [switch]$Indeterminate,
        [switch]$NumericOnly
    )
    $script:RunMonitorStageCalls.Add([pscustomobject]@{
        StageId = $StageId
        State = $State
        Detail = $Detail
        EvidenceSource = $EvidenceSource
        Indeterminate = [bool]$Indeterminate
    }) | Out-Null
}

function Set-MediaPipelineRunMonitorRunState {
    param(
        [string]$RunId,
        [string]$State,
        [string]$StopAfterCurrentState = '',
        [string]$RequestedAt = ''
    )
    $script:RunMonitorRunStateCalls.Add([pscustomobject]@{
        RunId = $RunId
        State = $State
        StopAfterCurrentState = $StopAfterCurrentState
        RequestedAt = $RequestedAt
    }) | Out-Null
}

function Update-MediaPipelineRunMonitorActiveTrackHeartbeat {
    param(
        [string]$Kind,
        [string]$RunId,
        [string]$JobId,
        [string]$EvidenceSource,
        [string]$EvidenceProvenance
    )
    $script:ActiveTrackHeartbeatCalls.Add([pscustomobject]@{
        Kind = $Kind
        RunId = $RunId
        JobId = $JobId
        EvidenceSource = $EvidenceSource
        EvidenceProvenance = $EvidenceProvenance
    }) | Out-Null
}

$script:ProgressStateEvents = @()
function Write-PipelineEvent {
    param(
        [string]$EventType,
        [string]$Stage,
        [string]$Status,
        [hashtable]$Data
    )
    $script:ProgressStateEvents += ,([pscustomobject]@{
        EventType = $EventType
        Stage = $Stage
        Status = $Status
        Data = $Data
    })
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
    $script:PipelineRunId = 'progress-track-run'
    $script:CurrentRunMonitorJobId = 'progress-track-run:item:1'
    $script:PauseFlagPollMilliseconds = 25

    Set-ProgressItemContext -DisplayName 'Movie.mkv' -FilePath 'C:\Media\Movie.mkv' -MediaType 'movie' -QueuePhase 'movie' -QueueIndex 1 -QueueTotal 2
    $script:currentStagePercent = $null
    Set-ProgressStage -Stage 'encode_verify' -Status 'Verification tool still working' -Route 'encode' -Percent $null -SaveNow
    $nativeHeartbeat = New-MediaPipelineCurrentStageNativePollHandler `
        -Stage 'encode_verify' `
        -Status 'Verification tool still working' `
        -Route 'encode' `
        -RefreshActiveAudioTracks `
        -EvidenceSource 'verification_process_heartbeat'
    & $nativeHeartbeat 0 $null | Out-Null
    $nativeHeartbeatStage = @($script:RunMonitorStageCalls | Where-Object { $_.StageId -eq 'verification' }) | Select-Object -Last 1
    Assert-True ($null -ne $nativeHeartbeatStage) 'A native heartbeat must refresh the exact current backend stage.'
    Assert-True ([bool]$nativeHeartbeatStage.Indeterminate) 'A native heartbeat without a truthful denominator must remain indeterminate.'
    Assert-Equal ([string]$script:ActiveTrackHeartbeatCalls[-1].Kind) 'audio' 'A CPU/native audio wait must refresh only the active audio collection.'
    Assert-Equal ([string]$script:ActiveTrackHeartbeatCalls[-1].RunId) 'progress-track-run' 'Native track heartbeat must retain exact run identity.'
    Assert-Equal ([string]$script:ActiveTrackHeartbeatCalls[-1].JobId) 'progress-track-run:item:1' 'Native track heartbeat must retain exact job identity.'
    Set-ProgressStage -Stage 'encode_cpu' -Status 'A later stage is now active' -Route 'encode-cpu-fallback' -Percent $null -SaveNow
    $monitorCallCountAfterStageChange = $script:RunMonitorStageCalls.Count
    $trackHeartbeatCountAfterStageChange = $script:ActiveTrackHeartbeatCalls.Count
    & $nativeHeartbeat 16 $null | Out-Null
    Assert-Equal $script:RunMonitorStageCalls.Count $monitorCallCountAfterStageChange 'A callback captured for verification must not migrate back after the file advances to encode_cpu.'
    Assert-Equal $script:ActiveTrackHeartbeatCalls.Count $trackHeartbeatCountAfterStageChange 'A stale native callback must not refresh active tracks after the captured canonical stage changes.'
    Set-ProgressStage -Stage 'encode_prepare' -Status 'Encoding Movie' -Route 'encode' -Percent 0 -SaveNow
    Set-ProgressStage -Stage 'copy_to_scratch' -Status 'Scratch copy complete' -CopyState 'complete' -SaveNow
    $terminalCopyStage = @($script:RunMonitorStageCalls | Where-Object {
        $_.StageId -eq 'copy_to_scratch' -and $_.State -eq 'completed'
    }) | Select-Object -Last 1
    Assert-True ($null -ne $terminalCopyStage) 'Copy completion must be authored as a terminal monitor stage.'
    Assert-True (-not [bool]$terminalCopyStage.Indeterminate) 'A terminal monitor stage must never retain indeterminate progress.'
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
    Set-ProgressSubtitleTrack `
        -Kind 'bdpgs' `
        -TrackId 'subtitle:sidecar:7' `
        -StreamIndex -1 `
        -Stage 'convert_ocr' `
        -Status 'OCR working' `
        -StepIndex 2 `
        -StepTotal 4 `
        -Steps @('extract', 'ocr', 'convert', 'write') `
        -SaveNow
    $heartbeatCountBeforeProgressSave = $script:WorkerHeartbeatCalls.Count
    Set-ProgressPendingDrain `
        -ManifestCount 4 `
        -AttemptedCount 2 `
        -SucceededCount 1 `
        -AlreadyPublishedCount 1 `
        -RemainingCount 2 `
        -CurrentItem 'Movie.mkv' `
        -Status 'Drain transaction succeeded' `
        -SaveNow
    Assert-True ($script:WorkerHeartbeatCalls.Count -gt $heartbeatCountBeforeProgressSave) 'A successful exact Save-Progress write must refresh the local-worker heartbeat.'

    $payload = Get-Content -LiteralPath $ProgressFile -Raw | ConvertFrom-Json -ErrorAction Stop

    Assert-Equal $payload.AudioProgress.schema_version 'pipeline_audio_progress.v1' 'Audio progress schema version mismatch.'
    Assert-Equal $payload.AudioProgress.action 'transcode' 'Audio progress action mismatch.'
    Assert-Equal ([int]$payload.AudioProgress.step_index) 2 'Audio progress step index mismatch.'
    Assert-True ($null -eq $payload.SubtitleProgress.percent) 'A fixed OCR step index must not manufacture completion percentage.'
    Assert-True ($null -eq $payload.SubtitleProgress.work_denominator) 'OCR without tool denominator must remain indeterminate.'
    Assert-Equal $script:RunMonitorTrackProgressCalls[-1].TrackId 'subtitle:sidecar:7' 'Subtitle progress must preserve the exact backend TrackId for an external sidecar.'
    Assert-Equal $script:RunMonitorTrackProgressCalls[-1].CurrentAction 'ocr_bdpgs_to_srt' 'Subtitle OCR progress must expose the truthful backend action, not only the codec kind.'
    Assert-Equal ([int]$script:RunMonitorTrackProgressCalls[-1].StepIndex) 2 'Subtitle progress must preserve the current backend step index.'
    Assert-Equal ([int]$script:RunMonitorTrackProgressCalls[-1].StepTotal) 4 'Subtitle progress must preserve the backend step total without treating it as work completion.'
    Assert-Equal ([string]$script:RunMonitorTrackProgressCalls[-1].StepName) 'ocr' 'Subtitle progress must preserve the exact backend step name.'
    $subtitleStageCalls = @($script:RunMonitorStageCalls | Where-Object { $_.StageId -eq 'subtitles' })
    Assert-Equal $subtitleStageCalls[-1].State 'active' 'Exact active subtitle-track evidence must drive the canonical subtitle stage active.'
    Assert-True $subtitleStageCalls[-1].Indeterminate 'Track work without a truthful run-wide denominator must leave the canonical subtitle stage indeterminate.'
    Assert-Equal $payload.PendingDrainProgress.schema_version 'pipeline_pending_drain_progress.v1' 'Pending drain progress schema version mismatch.'
    Assert-Equal ([int]$payload.PendingDrainProgress.attempted_count) 2 'Pending drain attempted count mismatch.'
    Assert-Equal ([int]$payload.PendingDrainProgress.remaining_count) 2 'Pending drain remaining count mismatch.'
    Assert-True ([bool]($payload.PSObject.Properties.Name -contains 'AudioProgress')) 'AudioProgress field was not serialized.'
    Assert-True ([bool]($payload.PSObject.Properties.Name -contains 'PendingDrainProgress')) 'PendingDrainProgress field was not serialized.'

    Set-ProgressAudioTrack `
        -StreamIndex 9 `
        -Stage 'audio_policy' `
        -Status 'Audio stream 9 dropped by backend policy' `
        -AudioAction 'drop' `
        -Reason 'file override' `
        -Detail 'Commentary'
    Assert-Equal $script:RunMonitorTrackProgressCalls[-1].State 'dropped' 'A definitive backend audio drop must remain a terminal dropped track, not active work.'

    Set-ProgressSubtitleTrack `
        -Kind 'bdpgs' `
        -TrackId 'subtitle:sidecar:7' `
        -StreamIndex -1 `
        -Stage 'convert_ocr' `
        -Status 'OCR working with page evidence' `
        -StepIndex 2 `
        -StepTotal 4 `
        -Steps @('extract', 'ocr', 'validate', 'sidecar_write') `
        -CueCount 17 `
        -WorkNumerator 3 `
        -WorkDenominator 10 `
        -ProgressUnit 'pages' `
        -SaveNow
    $determinatePayload = Get-Content -LiteralPath $ProgressFile -Raw | ConvertFrom-Json -ErrorAction Stop
    Assert-Equal ([double]$determinatePayload.SubtitleProgress.percent) 30.0 'Tool-provided OCR numerator and denominator should produce determinate progress.'
    Assert-Equal ([string]$determinatePayload.SubtitleProgress.progress_unit) 'pages' 'OCR progress unit must preserve backend tool evidence.'
    Assert-Equal ([int]$script:RunMonitorTrackProgressCalls[-1].StepIndex) 2 'Run Monitor OCR evidence must preserve the current step index.'
    Assert-Equal ([int]$script:RunMonitorTrackProgressCalls[-1].StepTotal) 4 'Run Monitor OCR evidence must preserve the step total as metadata only.'
    Assert-Equal ([string]$script:RunMonitorTrackProgressCalls[-1].StepName) 'ocr' 'Run Monitor OCR evidence must preserve the current step name.'
    Assert-Equal ([string]$script:RunMonitorTrackProgressCalls[-1].ProgressUnit) 'pages' 'Run Monitor OCR evidence must label the determinate numerator and denominator with their backend unit.'
    Assert-Equal ([int]$script:RunMonitorTrackProgressCalls[-1].CueCount) 17 'Run Monitor subtitle evidence must preserve a backend-confirmed cue count.'

    $terminalSubtitlePath = Join-Path $root 'Movie.eng.srt'
    Set-ProgressSubtitleTrack `
        -Kind 'bdpgs' `
        -TrackId 'subtitle:sidecar:7' `
        -StreamIndex -1 `
        -Stage 'sidecar_write' `
        -Status 'Subtitle sidecar written' `
        -OutputCodec 'subrip' `
        -OutputLocation 'external_sidecar' `
        -OutputPath $terminalSubtitlePath `
        -Completed `
        -SaveNow
    $terminalTrackCall = $script:RunMonitorTrackProgressCalls[-1]
    Assert-Equal $terminalTrackCall.CurrentAction 'write_sidecar' 'Subtitle sidecar completion must expose the exact write action.'
    Assert-Equal $terminalTrackCall.OutputCodec 'subrip' 'Subtitle sidecar completion must retain the output codec.'
    Assert-Equal $terminalTrackCall.OutputLocation 'external_sidecar' 'Subtitle sidecar completion must retain the output location.'
    Assert-Equal $terminalTrackCall.OutputPath $terminalSubtitlePath 'Subtitle sidecar completion must retain the exact output path.'
    $completedStageCallsBeforeSecondTrack = @($script:RunMonitorStageCalls | Where-Object {
        $_.StageId -eq 'subtitles' -and $_.State -eq 'completed'
    }).Count
    Assert-Equal $completedStageCallsBeforeSecondTrack 0 'One completed track must not close the subtitle stage while another final-policy track still awaits evidence.'

    Set-ProgressSubtitleTrack `
        -Kind 'ass' `
        -TrackId 'subtitle:embedded:8' `
        -StreamIndex 8 `
        -Stage 'validate' `
        -Status 'Second subtitle track complete' `
        -Completed
    $subtitleStageCalls = @($script:RunMonitorStageCalls | Where-Object { $_.StageId -eq 'subtitles' })
    Assert-Equal $subtitleStageCalls[-1].State 'completed' 'The canonical subtitle stage may complete only after the final policy is seeded and every exact track is terminal.'

    $script:RunMonitorSubtitlePolicyFinal = $false
    $script:RunMonitorSubtitleTrackStates = [ordered]@{ 'subtitle:embedded:9' = 'awaiting_evidence' }
    $completedStageCallCount = @($script:RunMonitorStageCalls | Where-Object {
        $_.StageId -eq 'subtitles' -and $_.State -eq 'completed'
    }).Count
    Set-ProgressSubtitleTrack `
        -Kind 'ass' `
        -TrackId 'subtitle:embedded:9' `
        -StreamIndex 9 `
        -Stage 'validate' `
        -Status 'Provisional subtitle track complete' `
        -Completed
    Assert-Equal (@($script:RunMonitorStageCalls | Where-Object {
        $_.StageId -eq 'subtitles' -and $_.State -eq 'completed'
    }).Count) $completedStageCallCount 'A provisional/partial subtitle policy must never produce canonical stage completion.'

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

    $script:StopRequested = $false
    $script:RunMonitorRunStateCalls.Clear()
    @{
        schema_version = 'pipeline_control_flag.v1'
        action = 'pause'
        request_id = 'pause-resume-test'
        created_at = (Get-Date).ToUniversalTime().ToString('o')
    } | ConvertTo-Json -Compress | Set-Content -LiteralPath $PauseFlag -Encoding UTF8
    $pauseRemovalJob = Start-Job -ScriptBlock {
        param($Path)
        Start-Sleep -Milliseconds 100
        Remove-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue
    } -ArgumentList $PauseFlag
    try {
        Check-ControlFlags
    } finally {
        Wait-Job $pauseRemovalJob -Timeout 5 | Out-Null
        Receive-Job $pauseRemovalJob -ErrorAction SilentlyContinue | Out-Null
        Remove-Job $pauseRemovalJob -Force -ErrorAction SilentlyContinue
    }
    Assert-Equal $script:RunMonitorRunStateCalls[0].State 'paused' 'A correlated pause marker must put the backend run monitor in Paused state.'
    Assert-Equal $script:RunMonitorRunStateCalls[-1].State 'running' 'Removing the pause marker must restore the backend run monitor to Running state.'

    $script:StopRequested = $false
    $script:PipelineBlockedExitCode = 0
    $script:PipelineStopReason = ''
    $script:ControlFlagDurableEventIds = @{}
    $script:ProgressStateEvents = @()
    $script:PauseFlagReviewSeconds = 60
    $script:PauseFlagBlockSeconds = 120
    $oldCreatedAt = (Get-Date).ToUniversalTime().AddSeconds(-180).ToString('o')
    @{
        schema_version = 'pipeline_control_flag.v1'
        action = 'pause'
        request_id = 'pause-stale-test'
        created_at = $oldCreatedAt
    } | ConvertTo-Json -Compress | Set-Content -LiteralPath $PauseFlag -Encoding UTF8

    Check-ControlFlags

    Assert-True ([bool]$script:StopRequested) 'Stale pause flag should request a terminal stop.'
    Assert-Equal ([int]$script:PipelineBlockedExitCode) 76 'Stale pause flag should request blocked exit code 76.'
    Assert-Equal ([string]$script:PipelineStopReason) 'pause_flag_stale_blocked' 'Stale pause flag should preserve blocked stop reason.'
    Assert-True (Test-Path -LiteralPath $PauseFlag -PathType Leaf) 'Stale pause flag must not be deleted when the run blocks.'
    $blockedPayload = Get-Content -LiteralPath $ProgressFile -Raw | ConvertFrom-Json -ErrorAction Stop
    Assert-Equal ([string]$blockedPayload.CurrentStage) 'blocked' 'Stale pause flag should persist blocked progress state.'
    Assert-True ([bool](@($script:ProgressStateEvents | Where-Object { $_.EventType -eq 'pause_flag_stale_review' }))) 'Stale pause flag should emit one review event.'
    Assert-True ([bool](@($script:ProgressStateEvents | Where-Object { $_.EventType -eq 'pause_flag_stale_blocked' }))) 'Stale pause flag should emit one blocked event.'
} finally {
    if (Test-Path -LiteralPath $root -ErrorAction SilentlyContinue) {
        Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Write-Host 'OK: progress state telemetry checks passed.'
