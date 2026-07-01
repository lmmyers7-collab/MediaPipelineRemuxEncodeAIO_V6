# ==============================================================================
# ops\pipeline\engine\status\progress_state.ps1
# ==============================================================================
# Operator control flags, progress JSON persistence, and round/session counters.
#
# Dot-sourced from MediaPipeline.ps1. Reads/writes at call time:
#   $PauseFlag, $StopFlag, $ProgressFile
#   $script:pipelineStatus and current item/stage fields
#   $script:total*, $script:Round*, $script:Session*
#
# Cross-module helpers:
#   Write-Log
# ==============================================================================
function Get-ControlFlagProperty {
    param(
        $Payload,
        [string]$Name
    )

    if ($null -eq $Payload) { return $null }
    $property = $Payload.PSObject.Properties[$Name]
    if ($property -and $null -ne $property.Value) {
        if ($property.Value -is [datetime]) {
            return ([datetime]$property.Value).ToUniversalTime().ToString('o')
        }
        if ($property.Value -is [datetimeoffset]) {
            return ([datetimeoffset]$property.Value).UtcDateTime.ToString('o')
        }
        return [string]$property.Value
    }
    return $null
}

function Get-ControlFlagInfo {
    param([string]$Path)

    $info = [ordered]@{
        Exists        = $false
        Path          = $Path
        SchemaVersion = $null
        Action        = $null
        Label         = $null
        RequestId     = $null
        CreatedAt     = $null
        RawValid      = $false
    }

    if ([string]::IsNullOrWhiteSpace($Path) -or -not (Test-Path -LiteralPath $Path -ErrorAction SilentlyContinue)) {
        return [pscustomobject]$info
    }

    $info.Exists = $true
    try {
        $raw = Get-Content -LiteralPath $Path -Raw -ErrorAction Stop
        if (-not [string]::IsNullOrWhiteSpace($raw)) {
            $payload = $raw | ConvertFrom-Json -ErrorAction Stop
            $info.SchemaVersion = Get-ControlFlagProperty -Payload $payload -Name 'schema_version'
            $info.Action = Get-ControlFlagProperty -Payload $payload -Name 'action'
            $info.Label = Get-ControlFlagProperty -Payload $payload -Name 'label'
            $info.RequestId = Get-ControlFlagProperty -Payload $payload -Name 'request_id'
            $info.CreatedAt = Get-ControlFlagProperty -Payload $payload -Name 'created_at'
            $info.RawValid = $true
        }
    } catch {}

    return [pscustomobject]$info
}

function Get-ControlFlagAgeSeconds {
    param($Info)

    if (-not $Info -or -not $Info.Exists) { return 0 }
    $nowUtc = (Get-Date).ToUniversalTime()
    $createdUtc = $null
    if (-not [string]::IsNullOrWhiteSpace([string]$Info.CreatedAt)) {
        try {
            $createdUtc = ([datetimeoffset]::Parse([string]$Info.CreatedAt)).UtcDateTime
        } catch {
            $createdUtc = $null
        }
    }
    if ($null -eq $createdUtc) {
        try {
            $item = Get-Item -LiteralPath ([string]$Info.Path) -ErrorAction Stop
            $createdUtc = $item.LastWriteTimeUtc
        } catch {
            $createdUtc = $nowUtc
        }
    }
    return [math]::Max(0, [int][math]::Floor(($nowUtc - $createdUtc).TotalSeconds))
}

function Write-ControlFlagEventOnce {
    param(
        [Parameter(Mandatory)] [string]$EventType,
        [Parameter(Mandatory)] [string]$Stage,
        [Parameter(Mandatory)] [string]$Status,
        [Parameter(Mandatory)] $Info,
        [int]$AgeSeconds,
        [int]$ReviewSeconds = 0,
        [int]$BlockSeconds = 0
    )

    if (-not $Info -or -not $Info.Exists) { return }
    if (-not $script:ControlFlagDurableEventIds) { $script:ControlFlagDurableEventIds = @{} }
    $requestId = [string]$Info.RequestId
    if ([string]::IsNullOrWhiteSpace($requestId)) {
        $requestId = "path:$([string]$Info.Path)"
    }
    $key = "$EventType|$requestId"
    if ($script:ControlFlagDurableEventIds.ContainsKey($key)) { return }
    $script:ControlFlagDurableEventIds[$key] = $true

    if (Get-Command -Name Write-PipelineEvent -ErrorAction SilentlyContinue) {
        try {
            Write-PipelineEvent -EventType $EventType -Stage $Stage -Status $Status -Data @{
                request_id     = [string]$Info.RequestId
                created_at     = [string]$Info.CreatedAt
                path           = [string]$Info.Path
                age_seconds    = [int]$AgeSeconds
                review_seconds = [int]$ReviewSeconds
                block_seconds  = [int]$BlockSeconds
            } | Out-Null
        } catch {}
    }
}

function Register-ControlFlagObservation {
    param(
        [ValidateSet('pause','stop','rescan')] [string]$Kind,
        $Info
    )

    if (-not $Info -or -not $Info.Exists) { return }
    $observedAt = Get-Date
    switch ($Kind) {
        'pause' {
            $script:LastPauseRequestId = $Info.RequestId
            $script:LastPauseRequestCreatedAt = $Info.CreatedAt
            $script:LastPauseRequestObservedAt = $observedAt
        }
        'stop' {
            $script:LastStopRequestId = $Info.RequestId
            $script:LastStopRequestCreatedAt = $Info.CreatedAt
            $script:LastStopRequestObservedAt = $observedAt
        }
        'rescan' {
            $script:LastRescanRequestId = $Info.RequestId
            $script:LastRescanRequestCreatedAt = $Info.CreatedAt
            $script:LastRescanRequestObservedAt = $observedAt
        }
    }
}

function New-ControlRequestProgressState {
    param(
        $PauseInfo,
        $StopInfo,
        $RescanInfo
    )

    [ordered]@{
        Pause  = [ordered]@{
            Requested             = [bool]$PauseInfo.Exists
            RequestId             = $PauseInfo.RequestId
            CreatedAt             = $PauseInfo.CreatedAt
            LastObservedRequestId = $script:LastPauseRequestId
            LastObservedCreatedAt = $script:LastPauseRequestCreatedAt
            LastObservedAt        = Get-ProgressIsoTimestamp $script:LastPauseRequestObservedAt
        }
        Stop   = [ordered]@{
            Requested             = [bool]($StopInfo.Exists -or $script:StopRequested)
            RequestId             = $StopInfo.RequestId
            CreatedAt             = $StopInfo.CreatedAt
            LastObservedRequestId = $script:LastStopRequestId
            LastObservedCreatedAt = $script:LastStopRequestCreatedAt
            LastObservedAt        = Get-ProgressIsoTimestamp $script:LastStopRequestObservedAt
        }
        Rescan = [ordered]@{
            Requested             = [bool]$RescanInfo.Exists
            RequestId             = $RescanInfo.RequestId
            CreatedAt             = $RescanInfo.CreatedAt
            LastObservedRequestId = $script:LastRescanRequestId
            LastObservedCreatedAt = $script:LastRescanRequestCreatedAt
            LastObservedAt        = Get-ProgressIsoTimestamp $script:LastRescanRequestObservedAt
        }
    }
}

function Check-ControlFlags {
    $stopInfo = Get-ControlFlagInfo -Path $StopFlag
    if ($stopInfo.Exists) {
        Register-ControlFlagObservation -Kind stop -Info $stopInfo
        Write-Log "STOP flag detected" "WARN"
        $script:StopRequested = $true
        Set-ProgressStage -Stage 'stopped' -Status 'Stopped' -Percent $null -SaveNow
    }
    $pauseInfo = Get-ControlFlagInfo -Path $PauseFlag
    if ($pauseInfo.Exists) {
        Register-ControlFlagObservation -Kind pause -Info $pauseInfo
        Write-Log "PAUSE flag detected — waiting..." "WARN"
        Set-ProgressStage -Stage 'paused' -Status 'Paused' -Percent $null -SaveNow
        $pauseReviewSeconds = [int]$script:PauseFlagReviewSeconds
        if ($pauseReviewSeconds -le 0) { $pauseReviewSeconds = 1800 }
        $pauseBlockSeconds = [int]$script:PauseFlagBlockSeconds
        if ($pauseBlockSeconds -le 0) { $pauseBlockSeconds = 21600 }
        while ($pauseInfo.Exists -and -not $script:StopRequested) {
            $pauseAgeSeconds = Get-ControlFlagAgeSeconds -Info $pauseInfo
            if ($pauseAgeSeconds -ge $pauseReviewSeconds) {
                Write-ControlFlagEventOnce -EventType 'pause_flag_stale_review' -Stage 'paused' -Status 'review' -Info $pauseInfo -AgeSeconds $pauseAgeSeconds -ReviewSeconds $pauseReviewSeconds -BlockSeconds $pauseBlockSeconds
            }
            if ($pauseAgeSeconds -ge $pauseBlockSeconds) {
                Write-Log "PAUSE flag has been present for $pauseAgeSeconds second(s); blocking unattended run without deleting flag." "ERROR"
                $script:StopRequested = $true
                $script:PipelineBlockedExitCode = 76
                $script:PipelineStopReason = 'pause_flag_stale_blocked'
                Write-ControlFlagEventOnce -EventType 'pause_flag_stale_blocked' -Stage 'blocked' -Status 'blocked' -Info $pauseInfo -AgeSeconds $pauseAgeSeconds -ReviewSeconds $pauseReviewSeconds -BlockSeconds $pauseBlockSeconds
                Set-ProgressStage -Stage 'blocked' -Status 'Pause flag stale blocked' -Percent $null -SaveNow
                break
            }
            Start-Sleep 5
            $stopInfo = Get-ControlFlagInfo -Path $StopFlag
            if ($stopInfo.Exists) {
                Register-ControlFlagObservation -Kind stop -Info $stopInfo
                Write-Log "STOP during pause" "WARN"
                $script:StopRequested = $true
                Set-ProgressStage -Stage 'stopped' -Status 'Stopped' -Percent $null -SaveNow
                break
            }
            $pauseInfo = Get-ControlFlagInfo -Path $PauseFlag
        }
        if (-not $script:StopRequested) {
            Write-Log "Resuming"
            Set-ProgressStage -Stage 'processing' -Status 'Resumed' -Percent $null -SaveNow
        }
    }
}

function Get-ProgressIsoTimestamp {
    param($Value)
    if ($null -eq $Value -or $Value -eq '') { return $null }
    try {
        if ($Value -is [datetime]) {
            return $Value.ToString('o')
        }
        return ([datetime]$Value).ToString('o')
    } catch {
        return [string]$Value
    }
}

function Reset-ProgressItemContext {
    $script:currentFile = "None"
    $script:currentFileDisplay = $null
    $script:currentFilePath = $null
    $script:currentMediaType = $null
    $script:currentLibraryId = $null
    $script:currentLibraryName = $null
    $script:currentLibraryDesignation = $null
    $script:currentLibrarySourceRoot = $null
    $script:currentLibraryOutputRoot = $null
    $script:currentQueuePhase = $null
    $script:currentQueueIndex = 0
    $script:currentQueueTotal = 0
    $script:currentRoute = $null
    $script:currentStagePercent = $null
    $script:currentItemStartedAt = $null
    $script:currentCopyState = $null
    $script:currentPushState = $null
    $script:currentSidecarState = $null
    $script:currentSubtitleProgress = $null
    $script:currentAudioProgress = $null
    Reset-ProgressCopyTelemetry
}

function Set-ProgressItemContext {
    param(
        [string]$DisplayName,
        [string]$FilePath,
        [string]$MediaType,
        [string]$LibraryId,
        [string]$LibraryName,
        [string]$LibraryDesignation,
        [string]$LibrarySourceRoot,
        [string]$LibraryOutputRoot,
        [string]$QueuePhase,
        [int]$QueueIndex = 0,
        [int]$QueueTotal = 0
    )

    $script:currentFile = if ([string]::IsNullOrWhiteSpace($DisplayName)) { "None" } else { $DisplayName }
    $script:currentFileDisplay = if ([string]::IsNullOrWhiteSpace($DisplayName)) { $null } else { $DisplayName }
    $script:currentFilePath = if ([string]::IsNullOrWhiteSpace($FilePath)) { $null } else { $FilePath }
    $script:currentMediaType = if ([string]::IsNullOrWhiteSpace($MediaType)) { $null } else { $MediaType }
    $script:currentLibraryId = if ([string]::IsNullOrWhiteSpace($LibraryId)) { $null } else { $LibraryId }
    $script:currentLibraryName = if ([string]::IsNullOrWhiteSpace($LibraryName)) { $null } else { $LibraryName }
    $script:currentLibraryDesignation = if ([string]::IsNullOrWhiteSpace($LibraryDesignation)) { $null } else { $LibraryDesignation }
    $script:currentLibrarySourceRoot = if ([string]::IsNullOrWhiteSpace($LibrarySourceRoot)) { $null } else { $LibrarySourceRoot }
    $script:currentLibraryOutputRoot = if ([string]::IsNullOrWhiteSpace($LibraryOutputRoot)) { $null } else { $LibraryOutputRoot }
    $script:currentQueuePhase = if ([string]::IsNullOrWhiteSpace($QueuePhase)) { $null } else { $QueuePhase }
    $script:currentQueueIndex = [int]$QueueIndex
    $script:currentQueueTotal = [int]$QueueTotal
    $script:currentItemStartedAt = Get-Date
    $script:currentStageStartedAt = Get-Date
    $script:currentStagePercent = $null
    $script:currentCopyState = $null
    $script:currentPushState = $null
    $script:currentSidecarState = $null
    $script:currentSubtitleProgress = $null
    $script:currentAudioProgress = $null
    if ($script:currentQueuePhase -ne 'pending_push') {
        $script:currentPendingDrainProgress = $null
    }
}

function Set-ProgressStage {
    param(
        [string]$Stage,
        [string]$Status,
        [object]$Percent,
        [string]$Route,
        [object]$CopyState,
        [object]$PushState,
        [object]$SidecarState,
        [switch]$SaveNow
    )

    if ($PSBoundParameters.ContainsKey('Stage')) {
        if ($Stage -ne $script:currentStage -or -not $script:currentStageStartedAt) {
            $script:currentStageStartedAt = Get-Date
        }
        $script:currentStage = if ([string]::IsNullOrWhiteSpace($Stage)) { $null } else { $Stage }
    }

    if ($PSBoundParameters.ContainsKey('Status')) {
        $script:pipelineStatus = if ([string]::IsNullOrWhiteSpace($Status)) { "Processing" } else { $Status }
    }

    if ($PSBoundParameters.ContainsKey('Percent')) {
        if ($null -eq $Percent -or "$Percent" -eq '') {
            $script:currentStagePercent = $null
        } else {
            try { $script:currentStagePercent = [double]$Percent }
            catch { $script:currentStagePercent = $null }
        }
    }

    if ($PSBoundParameters.ContainsKey('Route')) {
        $script:currentRoute = if ([string]::IsNullOrWhiteSpace($Route)) { $null } else { $Route }
    }
    if ($PSBoundParameters.ContainsKey('CopyState')) {
        $script:currentCopyState = if ($null -eq $CopyState -or [string]::IsNullOrWhiteSpace([string]$CopyState)) { $null } else { [string]$CopyState }
    }
    if ($PSBoundParameters.ContainsKey('PushState')) {
        $newPushState = if ($null -eq $PushState -or [string]::IsNullOrWhiteSpace([string]$PushState)) { $null } else { [string]$PushState }
        $script:currentPushState = $newPushState
        $pushStateKey = ([string]$newPushState).Trim().ToLowerInvariant()
        if ($pushStateKey -eq 'copying') {
            # A fresh server push (or retry) started: stamp its own start time and
            # arm the one-shot sample so the eventual success records this transfer.
            $script:currentPushStartedAt = Get-Date
            $script:currentPushSampleRecorded = $false
        } elseif ($pushStateKey -in @('copied_pending_reveal', 'complete')) {
            Add-PushThroughputSample
        }
    }
    if ($PSBoundParameters.ContainsKey('SidecarState')) {
        $script:currentSidecarState = if ($null -eq $SidecarState -or [string]::IsNullOrWhiteSpace([string]$SidecarState)) { $null } else { [string]$SidecarState }
    }

    if (Get-Command -Name Write-MediaPipelineWorkerChildHeartbeat -ErrorAction SilentlyContinue) {
        try {
            Write-MediaPipelineWorkerChildHeartbeat -Stage $script:currentStage -Status $script:pipelineStatus | Out-Null
        } catch {}
    }

    if ($SaveNow) {
        Save-Progress $script:pipelineStatus | Out-Null
    }
}

function Set-ProgressAudioTrack {
    param(
        [int]$StreamIndex = -1,
        [string]$Stage,
        [string]$Status,
        [string]$AudioAction,
        [string]$SourceCodec,
        [object]$SourceChannels = $null,
        [string]$OutputCodec,
        [object]$OutputChannels = $null,
        [string]$Language,
        [string]$Reason,
        [int]$StepIndex = 0,
        [int]$StepTotal = 0,
        [object]$Percent = $null,
        [string]$Detail = "",
        [switch]$Completed,
        [switch]$Failed,
        [switch]$SaveNow
    )

    $safeTotal = [math]::Max(0, [int]$StepTotal)
    $safeIndex = if ($safeTotal -gt 0) { [math]::Max(0, [math]::Min($safeTotal, [int]$StepIndex)) } else { 0 }
    $percentValue = $null
    if ($null -ne $Percent -and "$Percent" -ne '') {
        try { $percentValue = [math]::Max(0.0, [math]::Min(100.0, [double]$Percent)) } catch { $percentValue = $null }
    } elseif ($safeTotal -gt 0) {
        $percentValue = [math]::Round(($safeIndex / $safeTotal) * 100.0, 1)
    }

    $script:currentAudioProgress = [ordered]@{
        schema_version  = 'pipeline_audio_progress.v1'
        stream_index    = [int]$StreamIndex
        stage           = if ([string]::IsNullOrWhiteSpace($Stage)) { 'audio_policy' } else { $Stage }
        status          = if ([string]::IsNullOrWhiteSpace($Status)) { 'Evaluating audio policy' } else { $Status }
        action          = if ([string]::IsNullOrWhiteSpace($AudioAction)) { 'evaluate' } else { $AudioAction }
        source_codec    = if ([string]::IsNullOrWhiteSpace($SourceCodec)) { '' } else { $SourceCodec }
        source_channels = $SourceChannels
        output_codec    = if ([string]::IsNullOrWhiteSpace($OutputCodec)) { '' } else { $OutputCodec }
        output_channels = $OutputChannels
        language        = if ([string]::IsNullOrWhiteSpace($Language)) { '' } else { $Language }
        reason          = if ([string]::IsNullOrWhiteSpace($Reason)) { '' } else { $Reason }
        step_index      = $safeIndex
        step_total      = $safeTotal
        percent         = $percentValue
        detail          = $Detail
        updated_at      = Get-Date -Format 'o'
        completed       = [bool]$Completed
        failed          = [bool]$Failed
        source_file     = $script:currentFilePath
    }

    if ($SaveNow) {
        Save-Progress $script:pipelineStatus | Out-Null
    }
}

function Set-ProgressSubtitleTrack {
    param(
        [string]$Kind,
        [int]$StreamIndex = -1,
        [string]$Stage,
        [string]$Status,
        [int]$StepIndex = 0,
        [int]$StepTotal = 0,
        [array]$Steps = @(),
        [string]$Detail = "",
        [object]$CueCount = $null,
        [switch]$Completed,
        [switch]$Failed,
        [switch]$SaveNow
    )

    $safeTotal = [math]::Max(0, [int]$StepTotal)
    $safeIndex = if ($safeTotal -gt 0) { [math]::Max(0, [math]::Min($safeTotal, [int]$StepIndex)) } else { 0 }
    $percent = if ($safeTotal -gt 0) { [math]::Round(($safeIndex / $safeTotal) * 100.0, 1) } else { $null }
    $stepNames = @($Steps | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) } | ForEach-Object { [string]$_ })
    $completedSteps = @()
    if ($safeIndex -gt 0 -and $stepNames.Count -gt 0) {
        $completedSteps = @($stepNames | Select-Object -First $safeIndex)
    }

    $script:currentSubtitleProgress = [ordered]@{
        schema_version  = 'pipeline_subtitle_progress.v1'
        kind            = if ([string]::IsNullOrWhiteSpace($Kind)) { 'subtitle' } else { $Kind }
        stream_index    = [int]$StreamIndex
        stage           = if ([string]::IsNullOrWhiteSpace($Stage)) { 'unknown' } else { $Stage }
        status          = if ([string]::IsNullOrWhiteSpace($Status)) { 'Processing subtitles' } else { $Status }
        step_index      = $safeIndex
        step_total      = $safeTotal
        steps           = @($stepNames)
        completed_steps = @($completedSteps)
        percent         = $percent
        detail          = $Detail
        cue_count       = $CueCount
        updated_at      = Get-Date -Format 'o'
        completed       = [bool]$Completed
        failed          = [bool]$Failed
        source_file     = $script:currentFilePath
    }

    if ($SaveNow) {
        Save-Progress $script:pipelineStatus | Out-Null
    }
}

function Set-ProgressSubtitleSidecarWrite {
    param(
        [string]$Status = 'Writing subtitle sidecar evidence',
        [string]$Detail = '',
        [switch]$Completed,
        [switch]$Failed,
        [switch]$SaveNow
    )

    if (-not $script:currentSubtitleProgress) { return }
    $existing = $script:currentSubtitleProgress
    $steps = @($existing['steps'])
    $total = [int]($existing['step_total'])
    if ($total -le 0) { $total = [math]::Max(1, $steps.Count) }
    $index = if ($Failed) { [math]::Max(1, $total - 1) } else { $total }
    Set-ProgressSubtitleTrack `
        -Kind ([string]$existing['kind']) `
        -StreamIndex ([int]$existing['stream_index']) `
        -Stage 'sidecar_write' `
        -Status $Status `
        -StepIndex $index `
        -StepTotal $total `
        -Steps $steps `
        -Detail $Detail `
        -CueCount $existing['cue_count'] `
        -Completed:$Completed `
        -Failed:$Failed `
        -SaveNow:$SaveNow
}

function Set-ProgressPendingDrain {
    param(
        [int]$ManifestCount = 0,
        [int]$AttemptedCount = 0,
        [int]$SucceededCount = 0,
        [int]$AlreadyPublishedCount = 0,
        [int]$ErrorCount = 0,
        [int]$SkippedCount = 0,
        [int]$RemainingCount = 0,
        [string]$CurrentManifest = "",
        [string]$CurrentItem = "",
        [string]$Status = "Draining parked outputs",
        [switch]$Deferred,
        [switch]$SaveNow
    )

    $script:currentPendingDrainProgress = [ordered]@{
        schema_version            = 'pipeline_pending_drain_progress.v1'
        manifest_count            = [math]::Max(0, [int]$ManifestCount)
        attempted_count           = [math]::Max(0, [int]$AttemptedCount)
        succeeded_count           = [math]::Max(0, [int]$SucceededCount)
        already_published_count   = [math]::Max(0, [int]$AlreadyPublishedCount)
        error_count               = [math]::Max(0, [int]$ErrorCount)
        skipped_count             = [math]::Max(0, [int]$SkippedCount)
        remaining_count           = [math]::Max(0, [int]$RemainingCount)
        current_manifest          = if ([string]::IsNullOrWhiteSpace($CurrentManifest)) { '' } else { $CurrentManifest }
        current_item              = if ([string]::IsNullOrWhiteSpace($CurrentItem)) { '' } else { $CurrentItem }
        status                    = if ([string]::IsNullOrWhiteSpace($Status)) { 'Draining parked outputs' } else { $Status }
        deferred                  = [bool]$Deferred
        updated_at                = Get-Date -Format 'o'
    }

    if ($SaveNow) {
        Save-Progress $script:pipelineStatus | Out-Null
    }
}

function Reset-ProgressCopyTelemetry {
    $script:currentCopyBytesCopied = $null
    $script:currentCopyTotalBytes = $null
    $script:currentCopyPercent = $null
    $script:currentCopyAttempt = $null
    $script:currentCopySource = $null
    $script:currentCopyDestination = $null
    $script:currentCopyStartedAt = $null
    $script:currentCopyUpdatedAt = $null
    $script:currentPushStartedAt = $null
    $script:currentPushSampleRecorded = $false
}

# Session-level publish-push throughput accumulators. These $script: variables
# live for the life of the pipeline process, so they reset automatically on each
# pipeline launch and learn only from completed server pushes within the current
# run. They are intentionally NOT reset per item.
function Get-PushAverageBytesPerSecond {
    param(
        $TotalBytes,
        $TotalSeconds,
        $FilesCompleted
    )

    $bytes = 0.0
    $seconds = 0.0
    $files = 0
    try { if ($null -ne $TotalBytes) { $bytes = [double]$TotalBytes } } catch { $bytes = 0.0 }
    try { if ($null -ne $TotalSeconds) { $seconds = [double]$TotalSeconds } } catch { $seconds = 0.0 }
    try { if ($null -ne $FilesCompleted) { $files = [int]$FilesCompleted } } catch { $files = 0 }
    if ($files -lt 1 -or $seconds -le 0 -or $bytes -le 0) { return $null }
    return [long][math]::Round($bytes / $seconds)
}

# Fold the just-finished server push into the session throughput average. Called
# once per file when PushState transitions into a copy-success state. Weighted by
# bytes (sum bytes / sum seconds) so mixed file sizes aggregate honestly. Every
# step is guarded so a telemetry hiccup can never affect the publish flow that
# invokes it.
function Add-PushThroughputSample {
    if ($script:currentPushSampleRecorded) { return }
    if (-not $script:currentPushStartedAt) { return }

    $bytes = $null
    try {
        if ($null -ne $script:currentCopyTotalBytes -and "$script:currentCopyTotalBytes" -ne '') {
            $bytes = [long]$script:currentCopyTotalBytes
        }
    } catch { $bytes = $null }
    if ($null -eq $bytes -or $bytes -le 0) { return }

    $elapsed = ((Get-Date) - $script:currentPushStartedAt).TotalSeconds
    if ($elapsed -le 0) { return }

    if ($null -eq $script:SessionPushBytesTotal) { $script:SessionPushBytesTotal = [double]0 }
    if ($null -eq $script:SessionPushSecondsTotal) { $script:SessionPushSecondsTotal = [double]0 }
    if ($null -eq $script:SessionPushFilesCompleted) { $script:SessionPushFilesCompleted = 0 }

    $script:SessionPushBytesTotal += [double]$bytes
    $script:SessionPushSecondsTotal += [double]$elapsed
    $script:SessionPushFilesCompleted++
    $script:currentPushSampleRecorded = $true
}

function Convert-CopyPercentToStagePercent {
    param([double]$Percent)

    $stage = ([string]$script:currentStage).Trim().ToLowerInvariant()
    $pushState = ([string]$script:currentPushState).Trim().ToLowerInvariant()
    if ($stage -in @('push', 'retry_pending_push') -or $pushState -eq 'copying') {
        return [math]::Min(94.0, [math]::Round($Percent * 0.94, 1))
    }
    return [math]::Round($Percent, 1)
}

function Set-ProgressCopyTelemetry {
    param(
        [string]$Source,
        [string]$Destination,
        [object]$BytesCopied,
        [object]$TotalBytes,
        [object]$Percent,
        [int]$Attempt = 0,
        [switch]$SyncStagePercent,
        [switch]$SaveNow
    )

    $bytes = $null
    $total = $null
    $copyPercent = $null
    try {
        if ($null -ne $BytesCopied -and "$BytesCopied" -ne '') { $bytes = [long]$BytesCopied }
    } catch { $bytes = $null }
    try {
        if ($null -ne $TotalBytes -and "$TotalBytes" -ne '') { $total = [long]$TotalBytes }
    } catch { $total = $null }
    try {
        if ($null -ne $Percent -and "$Percent" -ne '') {
            $copyPercent = [math]::Max(0.0, [math]::Min(100.0, [double]$Percent))
        }
    } catch { $copyPercent = $null }

    $previousAttempt = $script:currentCopyAttempt
    if ($Attempt -gt 0 -and $null -ne $previousAttempt -and [int]$previousAttempt -ne [int]$Attempt) {
        $script:currentCopyStartedAt = $null
    }
    if (-not $script:currentCopyStartedAt) {
        $script:currentCopyStartedAt = Get-Date
    }

    $script:currentCopyBytesCopied = $bytes
    $script:currentCopyTotalBytes = $total
    $script:currentCopyPercent = if ($null -eq $copyPercent) { $null } else { [math]::Round($copyPercent, 1) }
    $script:currentCopyAttempt = if ($Attempt -gt 0) { [int]$Attempt } else { $null }
    $script:currentCopySource = if ([string]::IsNullOrWhiteSpace($Source)) { $null } else { $Source }
    $script:currentCopyDestination = if ([string]::IsNullOrWhiteSpace($Destination)) { $null } else { $Destination }
    $script:currentCopyUpdatedAt = Get-Date

    if ($SyncStagePercent -and $null -ne $copyPercent) {
        $script:currentStagePercent = Convert-CopyPercentToStagePercent -Percent $copyPercent
    }

    if ($SaveNow) {
        Save-Progress $script:pipelineStatus | Out-Null
    }
}

function New-SkipStats {
    return [ordered]@{
        AlreadyProcessed = 0
        BadExtension     = 0
        PermanentFailure = 0
        AmbiguousTV      = 0
        StillWriting     = 0
        PathUnsupported  = 0
        OperatorRequired = 0
    }
}

function Get-StatsSnapshot {
    return [ordered]@{
        TotalProcessed = $script:totalProcessed
        Encoded        = $script:totalEncoded
        Remuxed        = $script:totalRemuxed
        Failed         = $script:totalFailed
        Movies         = $script:totalMovies
        TVEpisodes     = $script:totalTVEpisodes
    }
}

function Reset-RoundTracking {
    $script:RoundBaseline      = Get-StatsSnapshot
    $script:RoundSkipStats     = New-SkipStats
    $script:RoundRetryCount    = 0
    $script:RoundMovieFilesFound = 0
    $script:RoundTVFilesFound    = 0
    $script:RoundFailureRecords  = [System.Collections.Generic.List[psobject]]::new()
}

function Add-SkipStat {
    param([string]$Reason)

    if (-not $script:RoundSkipStats)   { $script:RoundSkipStats = New-SkipStats }
    if (-not $script:SessionSkipStats) { $script:SessionSkipStats = New-SkipStats }

    if (-not $script:RoundSkipStats.Contains($Reason))   { $script:RoundSkipStats[$Reason] = 0 }
    if (-not $script:SessionSkipStats.Contains($Reason)) { $script:SessionSkipStats[$Reason] = 0 }

    $script:RoundSkipStats[$Reason]++
    $script:SessionSkipStats[$Reason]++
}

function Add-RetryNotice {
    $script:RoundRetryCount++
    $script:SessionRetryCount++
}

function Get-StatsDelta {
    param($Baseline)

    $current = Get-StatsSnapshot
    if (-not $Baseline) { return $current }

    return [ordered]@{
        TotalProcessed = $current.TotalProcessed - $Baseline.TotalProcessed
        Encoded        = $current.Encoded        - $Baseline.Encoded
        Remuxed        = $current.Remuxed        - $Baseline.Remuxed
        Failed         = $current.Failed         - $Baseline.Failed
        Movies         = $current.Movies         - $Baseline.Movies
        TVEpisodes     = $current.TVEpisodes     - $Baseline.TVEpisodes
    }
}

function Format-SkipSummary {
    param($Stats)

    if (-not $Stats) { return '(none)' }

    $parts = foreach ($key in $Stats.Keys) {
        $count = [int]$Stats[$key]
        if ($count -gt 0) { '{0}={1}' -f $key, $count }
    }

    if ($parts) { return ($parts -join ', ') }
    return '(none)'
}

function Get-ProgressSaveRetryDelaysMs {
    if ($script:ProgressSaveRetryDelaysMs -is [array] -and $script:ProgressSaveRetryDelaysMs.Count -gt 0) {
        return @($script:ProgressSaveRetryDelaysMs | ForEach-Object { [math]::Max(0, [int]$_) })
    }
    return @(25, 50, 100, 200, 400)
}

function Move-ProgressFileIntoPlace {
    param(
        [Parameter(Mandatory)] [string]$TempPath,
        [Parameter(Mandatory)] [string]$DestinationPath,
        [Parameter(Mandatory)] [string]$BackupPath
    )

    $delays = @(Get-ProgressSaveRetryDelaysMs)
    $maxAttempts = $delays.Count + 1
    for ($attempt = 0; $attempt -lt $maxAttempts; $attempt++) {
        try {
            if ([System.IO.File]::Exists($DestinationPath)) {
                [System.IO.File]::Replace($TempPath, $DestinationPath, $BackupPath, $true)
                Remove-Item -LiteralPath $BackupPath -Force -ErrorAction SilentlyContinue
            } else {
                [System.IO.File]::Move($TempPath, $DestinationPath)
            }
            return
        } catch {
            if ($attempt -ge ($maxAttempts - 1)) { throw }
            $delay = [int]$delays[$attempt]
            if ($delay -gt 0) { Start-Sleep -Milliseconds $delay }
        }
    }
}

function Save-Progress {
    param([string]$Status = $script:pipelineStatus)
    $tmp = $null
    $backup = $null
    try {
        $progressDir = Split-Path -Parent $ProgressFile
        if ([string]::IsNullOrWhiteSpace($ProgressFile) -or [string]::IsNullOrWhiteSpace($progressDir)) {
            throw "ProgressFile is not resolved: '$ProgressFile'"
        }
        if (-not (Test-Path -LiteralPath $progressDir)) {
            New-Item -ItemType Directory -Path $progressDir -Force | Out-Null
        }
        $pauseInfo = Get-ControlFlagInfo -Path $PauseFlag
        $stopInfo = Get-ControlFlagInfo -Path $StopFlag
        $rescanInfo = Get-ControlFlagInfo -Path $RescanFlag
        $tmp = Join-Path $progressDir ([System.IO.Path]::GetFileName($ProgressFile) + '.' + [System.IO.Path]::GetRandomFileName() + '.tmp')
        $backup = Join-Path $progressDir ([System.IO.Path]::GetFileName($ProgressFile) + '.' + [System.IO.Path]::GetRandomFileName() + '.bak')
        $json = [ordered]@{
            ProgressVersion       = $script:ProgressVersion
            LastUpdate            = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
            SessionStartedAt      = Get-ProgressIsoTimestamp $script:SessionStartedAt
            CurrentFile           = $script:currentFile
            CurrentFileDisplay    = $script:currentFileDisplay
            CurrentFilePath       = $script:currentFilePath
            CurrentMediaType      = $script:currentMediaType
            CurrentLibraryId      = $script:currentLibraryId
            CurrentLibraryName    = $script:currentLibraryName
            CurrentLibraryDesignation = $script:currentLibraryDesignation
            CurrentLibrarySourceRoot  = $script:currentLibrarySourceRoot
            CurrentLibraryOutputRoot  = $script:currentLibraryOutputRoot
            CurrentQueuePhase     = $script:currentQueuePhase
            CurrentQueueIndex     = $script:currentQueueIndex
            CurrentQueueTotal     = $script:currentQueueTotal
            CurrentRoute          = $script:currentRoute
            CurrentStage          = $script:currentStage
            CurrentStagePercent   = $script:currentStagePercent
            CurrentItemStartedAt  = Get-ProgressIsoTimestamp $script:currentItemStartedAt
            CurrentStageStartedAt = Get-ProgressIsoTimestamp $script:currentStageStartedAt
            CopyState             = $script:currentCopyState
            PushState             = $script:currentPushState
            SidecarState          = $script:currentSidecarState
            CopyBytesCopied       = $script:currentCopyBytesCopied
            CopyTotalBytes        = $script:currentCopyTotalBytes
            CopyPercent           = $script:currentCopyPercent
            CopyAttempt           = $script:currentCopyAttempt
            CopySource            = $script:currentCopySource
            CopyDestination       = $script:currentCopyDestination
            CopyStartedAt         = Get-ProgressIsoTimestamp $script:currentCopyStartedAt
            CopyUpdatedAt         = Get-ProgressIsoTimestamp $script:currentCopyUpdatedAt
            CopySessionBytesPerSecond = Get-PushAverageBytesPerSecond -TotalBytes $script:SessionPushBytesTotal -TotalSeconds $script:SessionPushSecondsTotal -FilesCompleted $script:SessionPushFilesCompleted
            CopySessionFilesCompleted = if ($null -eq $script:SessionPushFilesCompleted) { 0 } else { [int]$script:SessionPushFilesCompleted }
            SubtitleProgress      = $script:currentSubtitleProgress
            AudioProgress         = $script:currentAudioProgress
            PendingDrainProgress  = $script:currentPendingDrainProgress
            PauseRequested        = [bool]$pauseInfo.Exists
            StopRequested         = [bool]($script:StopRequested -or $stopInfo.Exists)
            ControlRequests       = New-ControlRequestProgressState -PauseInfo $pauseInfo -StopInfo $stopInfo -RescanInfo $rescanInfo
            Status                = $Status
            TotalProcessed        = $script:totalProcessed
            Encoded               = $script:totalEncoded
            Remuxed               = $script:totalRemuxed
            Failed                = $script:totalFailed
            Movies                = $script:totalMovies
            TVEpisodes            = $script:totalTVEpisodes
            RoundFailureCount     = if ($null -eq $script:RoundFailureRecords) { 0 } else { [int]$script:RoundFailureRecords.Count }
            UnexpectedQueueEntryFailures = [int]$script:UnexpectedQueueEntryFailures
            UnexpectedRoundFailures = [int]$script:UnexpectedRoundFailures
            ConsecutiveUnexpectedRoundFailures = [int]$script:ConsecutiveUnexpectedRoundFailures
            LastUnexpectedRoundFailureAt = $script:LastUnexpectedRoundFailureAt
            ContinuousRoundFailuresBlocked = [bool]$script:ContinuousRoundFailuresBlocked
            ConsecutiveRoundFailureBlockLimit = [int]$script:ConsecutiveRoundFailureBlockLimit
            ConsecutiveRoundFailureProbeBackoffSeconds = [int]$script:ConsecutiveRoundFailureProbeBackoffSeconds
            PauseFlagReviewSeconds = [int]$script:PauseFlagReviewSeconds
            PauseFlagBlockSeconds = [int]$script:PauseFlagBlockSeconds
            LastQueueScanDurationSeconds = $script:LastQueueScanDurationSeconds
            LastQueueCandidateCount = [int]$script:LastQueueCandidateCount
            LastQueueExecutionTruncated = [bool]$script:LastQueueExecutionTruncated
            LastQueueScanTruncated = [bool]$script:LastQueueScanTruncated
            LastQueueScanTimedOut = [bool]$script:LastQueueScanTimedOut
            NativeNoProgressAbortCount = [int]$script:NativeIdleWatchdogAbortCount
            NativeIdleWatchdogAbortCount = [int]$script:NativeIdleWatchdogAbortCount
            ProgressPersistenceHealthy = [bool]$script:ProgressPersistenceHealthy
            ProgressWriteFailures = [int]$script:ProgressWriteFailures
        } | ConvertTo-Json -Depth 4
        [System.IO.File]::WriteAllText($tmp, $json, [System.Text.UTF8Encoding]::new($false))
        # Replace() is a true atomic NTFS metadata swap (no delete+create gap).
        # Move-Item on SMB can leave a window where the file doesn't exist,
        # causing the UI poll to get FileNotFoundException or a zero-byte read.
        # ignoreMetadataErrors=$true prevents ACL/ownership issues on some shares.
        # WebView diagnostics polls can briefly hold the JSON open without
        # FILE_SHARE_DELETE, so keep the atomic swap but tolerate short locks.
        Move-ProgressFileIntoPlace -TempPath $tmp -DestinationPath $ProgressFile -BackupPath $backup
        $script:ProgressWriteFailures = 0
        $script:ProgressPersistenceHealthy = $true
        return $true
    } catch {
        $script:ProgressWriteFailures++
        $script:ProgressPersistenceHealthy = $false
        try {
            if ($tmp -and (Test-Path -LiteralPath $tmp)) {
                Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
            }
            if ($backup -and (Test-Path -LiteralPath $backup)) {
                Remove-Item -LiteralPath $backup -Force -ErrorAction SilentlyContinue
            }
        } catch {}
        Write-Log "Failed to save progress: $_" "WARN"
        if (Get-Command -Name Write-PipelineEvent -ErrorAction SilentlyContinue) {
            try {
                Write-PipelineEvent -EventType 'progress_persistence_failed' -Stage 'progress' -Status 'failed' -Data @{
                    error_code      = 'PROGRESS_PERSISTENCE_FAILED'
                    error           = [string]$_
                    progress_file   = [string]$ProgressFile
                    failure_count   = [int]$script:ProgressWriteFailures
                    fail_closed     = $true
                } | Out-Null
            } catch {}
        }
        return $false
    }
}

function Test-ProgressPersistence {
    try {
        $progressDir = Split-Path -Parent $ProgressFile
        if (-not [string]::IsNullOrWhiteSpace($progressDir) -and -not (Test-Path -LiteralPath $progressDir)) {
            New-Item -ItemType Directory -Path $progressDir -Force | Out-Null
        }
        $probe = Join-Path $progressDir ("pipeline_progress.probe." + [guid]::NewGuid().ToString("N") + ".json")
        $payload = @{ probe = $true; at = (Get-Date -Format 'o') } | ConvertTo-Json -Compress
        [System.IO.File]::WriteAllText($probe, $payload, [System.Text.UTF8Encoding]::new($false))
        $roundTrip = Get-Content -LiteralPath $probe -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
        if (-not $roundTrip.probe) { throw "progress probe round-trip failed" }
        Remove-Item -LiteralPath $probe -Force -ErrorAction SilentlyContinue
        $script:ProgressPersistenceHealthy = $true
        return $true
    } catch {
        $script:ProgressPersistenceHealthy = $false
        Write-Log "Progress persistence probe failed: $_" "ERROR"
        if (Get-Command -Name Write-PipelineEvent -ErrorAction SilentlyContinue) {
            try {
                Write-PipelineEvent -EventType 'progress_persistence_probe_failed' -Stage 'progress' -Status 'failed' -Data @{
                    error_code    = 'PROGRESS_PERSISTENCE_FAILED'
                    error         = [string]$_
                    progress_file = [string]$ProgressFile
                    fail_closed   = $true
                } | Out-Null
            } catch {}
        }
        return $false
    }
}

function Get-ProcessingStats {
    $round      = Get-StatsDelta $script:RoundBaseline
    $session    = Get-StatsDelta $script:SessionBaseline
    $cumulative = Get-StatsSnapshot
    return @"
========================================
PIPELINE STATISTICS
========================================
Round files seen : $($script:RoundMovieFilesFound + $script:RoundTVFilesFound) (movies: $($script:RoundMovieFilesFound), tv: $($script:RoundTVFilesFound))
Round outcomes   : processed=$($round.TotalProcessed), encoded=$($round.Encoded), remuxed=$($round.Remuxed), failed=$($round.Failed)
Round skips      : $(Format-SkipSummary $script:RoundSkipStats)
Round retries    : $($script:RoundRetryCount)
Round failures   : $($script:RoundFailureRecords.Count)
Session outcomes : processed=$($session.TotalProcessed), encoded=$($session.Encoded), remuxed=$($session.Remuxed), failed=$($session.Failed)
Session skips    : $(Format-SkipSummary $script:SessionSkipStats)
Session retries  : $($script:SessionRetryCount)
Cumulative       : processed=$($cumulative.TotalProcessed), movies=$($cumulative.Movies), tv=$($cumulative.TVEpisodes), encoded=$($cumulative.Encoded), remuxed=$($cumulative.Remuxed), failed=$($cumulative.Failed)
========================================
"@
}

function Initialize-MediaPipelineSessionState {
$Global:ffmpegProcess = $null
$script:FFmpegProgressWriteStepPercent = 5

$script:ProgressVersion = 2
$script:totalProcessed  = 0
$script:totalEncoded    = 0
$script:totalRemuxed    = 0
$script:totalFailed     = 0
$script:totalMovies     = 0
$script:totalTVEpisodes = 0
$script:SessionStartedAt = Get-Date
$script:currentFile     = "None"
$script:currentFileDisplay = $null
$script:currentFilePath = $null
$script:currentMediaType = $null
$script:currentQueuePhase = $null
$script:currentQueueIndex = 0
$script:currentQueueTotal = 0
$script:currentRoute = $null
$script:currentStage = 'initializing'
$script:currentStagePercent = $null
$script:currentItemStartedAt = $null
$script:currentStageStartedAt = Get-Date
$script:currentCopyState = $null
$script:currentPushState = $null
$script:currentSidecarState = $null
$script:pipelineStatus  = "Initializing"
$script:StopRequested   = $false
$script:LastPauseRequestId = $null
$script:LastPauseRequestCreatedAt = $null
$script:LastPauseRequestObservedAt = $null
$script:LastStopRequestId = $null
$script:LastStopRequestCreatedAt = $null
$script:LastStopRequestObservedAt = $null
$script:LastRescanRequestId = $null
$script:LastRescanRequestCreatedAt = $null
$script:LastRescanRequestObservedAt = $null
$script:SessionBaseline = $null
$script:RoundBaseline   = $null
$script:SessionSkipStats = @{}
$script:RoundSkipStats   = @{}
$script:SessionRetryCount = 0
$script:RoundRetryCount   = 0
$script:RoundMovieFilesFound = 0
$script:RoundTVFilesFound    = 0
$script:RoundFailureRecords  = [System.Collections.Generic.List[psobject]]::new()
$script:UnexpectedRoundFailures = 0
$script:ConsecutiveUnexpectedRoundFailures = 0
$script:LastUnexpectedRoundFailureAt = $null
$script:ContinuousRoundFailuresBlocked = $false
$script:LastQueueScanDurationSeconds = $null
$script:LastQueueCandidateCount = 0
$script:LastQueueExecutionTruncated = $false
$script:LastQueueScanTruncated = $false
$script:LastQueueScanTimedOut = $false
$script:ProcessedIndexCache  = $null
$script:ProcessedIndexCacheAt = $null
$script:MovieScanCache       = @()
$script:MovieScanCacheAt     = $null
$script:TVScanCache          = @()
$script:TVScanCacheAt        = $null
$script:ForceProcessedIndexRefresh = $false

$progressReadPath = if (Test-Path -LiteralPath $ProgressFile) {
    $ProgressFile
} elseif (Test-Path -LiteralPath $script:LocalStateLayout.LegacyPaths.ProgressFile) {
    $script:LocalStateLayout.LegacyPaths.ProgressFile
} else {
    $null
}
if ($progressReadPath) {
    try {
        $saved = Get-Content -LiteralPath $progressReadPath -Raw | ConvertFrom-Json
        # Coerce each counter defensively: a partially written / truncated
        # progress file can still parse yet be missing fields, which would
        # otherwise leave the counters $null and corrupt later arithmetic
        # and status text. [int]$null and a missing property both yield 0.
        $script:totalProcessed  = [int]($saved.TotalProcessed)
        $script:totalEncoded    = [int]($saved.Encoded)
        $script:totalRemuxed    = [int]($saved.Remuxed)
        $script:totalFailed     = [int]($saved.Failed)
        $script:totalMovies     = [int]($saved.Movies)
        $script:totalTVEpisodes = [int]($saved.TVEpisodes)
        Write-Log "Loaded previous progress: $($script:totalProcessed) files processed"
    } catch { Write-Log "Could not load progress file" "WARN" }
}

$script:SessionBaseline = Get-StatsSnapshot
$script:SessionSkipStats = New-SkipStats
Reset-RoundTracking
}
