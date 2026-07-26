# ==============================================================================
# ops\pipeline\engine\status\progress_state.ps1
# ==============================================================================
# Operator control flags, progress JSON persistence, and round/session counters.
#
# Dot-sourced from MediaPipeline.ps1. Reads/writes at call time:
#   $PauseFlag, $StopFlag, $StopAfterCurrentFlag, $ProgressFile
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
        RunId         = $null
        TargetPid     = $null
        TargetLaunchId = $null
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
            $info.RunId = Get-ControlFlagProperty -Payload $payload -Name 'run_id'
            $info.TargetPid = Get-ControlFlagProperty -Payload $payload -Name 'target_pid'
            $info.TargetLaunchId = Get-ControlFlagProperty -Payload $payload -Name 'target_launch_id'
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
        [ValidateSet('pause','stop','stop_after_current','rescan')] [string]$Kind,
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
        'stop_after_current' {
            $script:LastStopAfterCurrentRequestId = $Info.RequestId
            $script:LastStopAfterCurrentRequestCreatedAt = $Info.CreatedAt
            $script:LastStopAfterCurrentRequestObservedAt = $observedAt
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
        $StopAfterCurrentInfo,
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
        StopAfterCurrent = [ordered]@{
            Requested             = [bool]($StopAfterCurrentInfo.Exists -or $script:StopAfterCurrentRequested)
            Acknowledged          = [bool]$script:StopAfterCurrentAcknowledged
            RequestId             = $StopAfterCurrentInfo.RequestId
            CreatedAt             = $StopAfterCurrentInfo.CreatedAt
            RunId                 = $StopAfterCurrentInfo.RunId
            TargetPid             = $StopAfterCurrentInfo.TargetPid
            TargetLaunchId        = $StopAfterCurrentInfo.TargetLaunchId
            LastObservedRequestId = $script:LastStopAfterCurrentRequestId
            LastObservedCreatedAt = $script:LastStopAfterCurrentRequestCreatedAt
            LastObservedAt        = Get-ProgressIsoTimestamp $script:LastStopAfterCurrentRequestObservedAt
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

function Get-MediaPipelineCurrentControllerLaunchId {
    param([int] $ProcessId = $PID)

    $activeJobsRoot = ''
    try { $activeJobsRoot = [string]$script:LocalStateLayout.ActiveJobs } catch {}
    if ([string]::IsNullOrWhiteSpace($activeJobsRoot) -or -not (Test-Path -LiteralPath $activeJobsRoot -PathType Container)) {
        return ''
    }
    foreach ($recordPath in @(Get-ChildItem -LiteralPath $activeJobsRoot -Filter '*.json' -File -ErrorAction SilentlyContinue)) {
        try {
            $record = Get-Content -LiteralPath $recordPath.FullName -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
            if (
                [string]$record.schema_version -eq 'desktop_active_job.v1' -and
                [string]$record.job_kind -eq 'pipeline' -and
                [string]$record.status -in @('launching','active') -and
                [int]$record.pid -eq $ProcessId
            ) {
                return [string]$record.launch_id
            }
        } catch {}
    }
    return ''
}

function Test-MediaPipelineStopAfterCurrentCorrelation {
    param($Info)

    if (-not $Info -or -not $Info.Exists -or -not $Info.RawValid) { return $false }
    if ([string]$Info.SchemaVersion -ne 'pipeline_control_flag.v1' -or [string]$Info.Action -ne 'stop_after_current') { return $false }
    if ([string]::IsNullOrWhiteSpace([string]$Info.RequestId)) { return $false }

    $runId = [string]$Info.RunId
    $targetPid = 0
    try { $targetPid = [int]$Info.TargetPid } catch { $targetPid = 0 }
    $targetLaunchId = [string]$Info.TargetLaunchId
    $currentRunId = [string]$script:PipelineRunId
    # Every pipeline mode has a process-local PipelineRunId. Only the exact
    # Backend Queue seed-adoption context proves that this process owns a
    # durable Run Once monitor and may accept a run-correlated control flag.
    $runMonitorContext = $null
    try { $runMonitorContext = $script:BackendQueueRunMonitorSeedContext } catch {}
    $monitoredRun = $null -ne $runMonitorContext
    if ($monitoredRun) {
        $monitorRunId = ''
        $monitorFingerprint = ''
        try { $monitorRunId = [string]$runMonitorContext.RunId } catch {}
        try { $monitorFingerprint = [string]$runMonitorContext.QueuePlanFingerprint } catch {}
        if (
            [string]::IsNullOrWhiteSpace($currentRunId) -or
            [string]::IsNullOrWhiteSpace($monitorRunId) -or
            [string]::IsNullOrWhiteSpace($monitorFingerprint) -or
            $monitorRunId -ne $currentRunId -or
            [string]::IsNullOrWhiteSpace($runId) -or
            $targetPid -le 0 -or
            [string]::IsNullOrWhiteSpace($targetLaunchId)
        ) { return $false }
        if ($runId -ne $monitorRunId) { return $false }
    } else {
        if (-not [string]::IsNullOrWhiteSpace($runId)) { return $false }
        if ($targetPid -le 0 -or [string]::IsNullOrWhiteSpace($targetLaunchId)) { return $false }
    }
    if ($targetPid -ne $PID) { return $false }
    $currentLaunchId = Get-MediaPipelineCurrentControllerLaunchId -ProcessId $PID
    if ([string]::IsNullOrWhiteSpace($currentLaunchId) -or $currentLaunchId -ne $targetLaunchId) { return $false }
    return $true
}

function Set-MediaPipelineStopAfterCurrentMonitorState {
    param(
        [Parameter(Mandatory)] [string] $State,
        [Parameter(Mandatory)] [string] $StopAfterCurrentState,
        [string] $RequestedAt = ''
    )

    if ([string]::IsNullOrWhiteSpace([string]$script:PipelineRunId)) { return }
    if (-not (Get-Command -Name Set-MediaPipelineRunMonitorRunState -ErrorAction SilentlyContinue)) { return }
    try {
        Set-MediaPipelineRunMonitorRunState `
            -RunId ([string]$script:PipelineRunId) `
            -State $State `
            -StopAfterCurrentState $StopAfterCurrentState `
            -RequestedAt $RequestedAt | Out-Null
    } catch {
        Write-Log "Stop After Current monitor update was unavailable: $($_.Exception.Message)" 'DEBUG'
    }
}

function Set-MediaPipelinePauseMonitorState {
    param(
        [Parameter(Mandatory)]
        [ValidateSet('running','paused','stopping','blocked')]
        [string] $State
    )
    if ([string]::IsNullOrWhiteSpace([string]$script:PipelineRunId)) { return }
    if (-not (Get-Command -Name Set-MediaPipelineRunMonitorRunState -ErrorAction SilentlyContinue)) { return }
    try {
        Set-MediaPipelineRunMonitorRunState -RunId ([string]$script:PipelineRunId) -State $State | Out-Null
    } catch {
        Write-Log "Pause monitor update was unavailable: $($_.Exception.Message)" 'DEBUG'
    }
}

function Test-MediaPipelineStopAfterCurrentRequested {
    if ([bool]$script:StopAfterCurrentRequested) { return $true }

    $info = Get-ControlFlagInfo -Path $StopAfterCurrentFlag
    if (-not (Test-MediaPipelineStopAfterCurrentCorrelation -Info $info)) { return $false }
    Register-ControlFlagObservation -Kind stop_after_current -Info $info
    $script:StopAfterCurrentRequested = $true
    $script:StopAfterCurrentAcknowledged = $false
    $script:StopAfterCurrentRequestId = [string]$info.RequestId
    $script:StopAfterCurrentRequestedAt = [string]$info.CreatedAt
    Write-Log "STOP AFTER CURRENT request detected for this exact controller/run" 'WARN'
    Set-MediaPipelineStopAfterCurrentMonitorState -State 'stop_requested' -StopAfterCurrentState 'requested' -RequestedAt ([string]$info.CreatedAt)
    return $true
}

function Test-MediaPipelineStopAfterCurrentBoundary {
    if (-not (Test-MediaPipelineStopAfterCurrentRequested)) { return $false }
    if ([bool]$script:StopAfterCurrentAcknowledged) { return $true }

    $info = Get-ControlFlagInfo -Path $StopAfterCurrentFlag
    if (
        (Test-MediaPipelineStopAfterCurrentCorrelation -Info $info) -and
        [string]$info.RequestId -eq [string]$script:StopAfterCurrentRequestId
    ) {
        try {
            Remove-Item -LiteralPath $StopAfterCurrentFlag -Force -ErrorAction Stop
            if (Test-Path -LiteralPath $StopAfterCurrentFlag -ErrorAction SilentlyContinue) {
                throw 'the marker remained after removal'
            }
            $script:StopAfterCurrentAcknowledged = $true
            Write-Log 'STOP AFTER CURRENT acknowledged at the backend queue dispatch boundary' 'WARN'
            Set-MediaPipelineStopAfterCurrentMonitorState -State 'stopping' -StopAfterCurrentState 'acknowledged' -RequestedAt ([string]$script:StopAfterCurrentRequestedAt)
        } catch {
            Write-Log "STOP AFTER CURRENT boundary was honored, but exact marker acknowledgement failed: $($_.Exception.Message)" 'ERROR'
        }
    }
    return $true
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
        Set-MediaPipelinePauseMonitorState -State paused
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
                Set-MediaPipelinePauseMonitorState -State blocked
                break
            }
            $pausePollMilliseconds = [int]$script:PauseFlagPollMilliseconds
            if ($pausePollMilliseconds -le 0) { $pausePollMilliseconds = 5000 }
            Start-Sleep -Milliseconds $pausePollMilliseconds
            $stopInfo = Get-ControlFlagInfo -Path $StopFlag
            if ($stopInfo.Exists) {
                Register-ControlFlagObservation -Kind stop -Info $stopInfo
                Write-Log "STOP during pause" "WARN"
                $script:StopRequested = $true
                Set-ProgressStage -Stage 'stopped' -Status 'Stopped' -Percent $null -SaveNow
                Set-MediaPipelinePauseMonitorState -State stopping
                break
            }
            $pauseInfo = Get-ControlFlagInfo -Path $PauseFlag
        }
        if (-not $script:StopRequested) {
            Write-Log "Resuming"
            Set-ProgressStage -Stage 'processing' -Status 'Resumed' -Percent $null -SaveNow
            Set-MediaPipelinePauseMonitorState -State running
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
    $script:CurrentExecutedRoute = $null
    $script:CurrentExecutedRouteReasonCode = $null
    $script:CurrentExecutedRouteReason = $null
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

    if ($PSBoundParameters.ContainsKey('Stage') -and
        -not [string]::IsNullOrWhiteSpace([string]$script:PipelineRunId) -and
        -not [string]::IsNullOrWhiteSpace([string]$script:CurrentRunMonitorJobId) -and
        (Get-Command -Name ConvertTo-MediaPipelineRunMonitorStageId -ErrorAction SilentlyContinue)) {
        $canonicalStage = ConvertTo-MediaPipelineRunMonitorStageId -PipelineStage $Stage
        if (-not [string]::IsNullOrWhiteSpace($canonicalStage) -and $canonicalStage -ne 'final_evidence') {
            try {
                $monitorStageState = 'active'
                if ($canonicalStage -eq 'copy_to_scratch' -and $PSBoundParameters.ContainsKey('CopyState')) {
                    $copyEvidenceState = ([string]$CopyState).Trim().ToLowerInvariant()
                    $monitorStageState = switch ($copyEvidenceState) {
                        { $_ -in @('complete','completed') } { 'completed' }
                        { $_ -in @('reused','skipped') } { 'skipped' }
                        { $_ -in @('failed','error') } { 'failed' }
                        default { 'active' }
                    }
                } elseif ($canonicalStage -eq 'publish' -and $PSBoundParameters.ContainsKey('PushState')) {
                    $pushEvidenceState = ([string]$PushState).Trim().ToLowerInvariant()
                    $monitorStageState = switch ($pushEvidenceState) {
                        { $_ -in @('complete','published','parked') } { 'completed' }
                        { $_ -in @('failed','error') } { 'failed' }
                        default { 'active' }
                    }
                } elseif ($canonicalStage -eq 'sidecar_writing' -and $PSBoundParameters.ContainsKey('SidecarState')) {
                    $sidecarEvidenceState = ([string]$SidecarState).Trim().ToLowerInvariant()
                    $monitorStageState = switch ($sidecarEvidenceState) {
                        { $_ -in @('complete','completed','written') } { 'completed' }
                        { $_ -in @('skipped','not_applicable') } { $(if ($_ -eq 'not_applicable') { 'not_applicable' } else { 'skipped' }) }
                        { $_ -in @('failed','error','review') } { $(if ($_ -eq 'review') { 'review' } else { 'failed' }) }
                        default { 'active' }
                    }
                }
                $stageParams = @{
                    RunId = [string]$script:PipelineRunId
                    JobId = [string]$script:CurrentRunMonitorJobId
                    StageId = $canonicalStage
                    State = $monitorStageState
                    Detail = [string]$script:pipelineStatus
                    EvidenceSource = 'progress_state'
                }
                if ($null -ne $script:currentStagePercent -and "" + $script:currentStagePercent -ne '' -and
                    $monitorStageState -in @('active','completed')) {
                    $stageParams['Numerator'] = [double]$script:currentStagePercent
                    $stageParams['Denominator'] = 100.0
                    $stageParams['NumericOnly'] = -not [bool]$SaveNow
                } elseif ($monitorStageState -eq 'active') {
                    $stageParams['Indeterminate'] = $true
                }
                Set-MediaPipelineRunMonitorStage @stageParams | Out-Null
            } catch {
                $script:RunMonitorPersistenceHealthy = $false
                Write-Log "Run Monitor stage update failed for ${canonicalStage}: $($_.Exception.Message)" 'WARN'
            }
        }
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

function Test-MediaPipelineCurrentStageNativePollIdentity {
    param(
        [string] $RunId,
        [string] $JobId,
        [string] $Stage
    )

    if ([string]::IsNullOrWhiteSpace($RunId) -or
        [string]::IsNullOrWhiteSpace($JobId) -or
        [string]::IsNullOrWhiteSpace($Stage) -or
        -not (Get-Command -Name ConvertTo-MediaPipelineRunMonitorStageId -ErrorAction SilentlyContinue)) {
        return $false
    }
    $capturedCanonicalStage = ConvertTo-MediaPipelineRunMonitorStageId -PipelineStage $Stage
    $currentCanonicalStage = ConvertTo-MediaPipelineRunMonitorStageId -PipelineStage ([string]$script:currentStage)
    if ([string]::IsNullOrWhiteSpace($capturedCanonicalStage) -or
        [string]::IsNullOrWhiteSpace($currentCanonicalStage)) {
        return $false
    }

    return [bool](
        [string]::Equals([string]$script:PipelineRunId, [string]$RunId, [System.StringComparison]::Ordinal) -and
        [string]::Equals([string]$script:CurrentRunMonitorJobId, [string]$JobId, [System.StringComparison]::Ordinal) -and
        [string]::Equals([string]$currentCanonicalStage, [string]$capturedCanonicalStage, [System.StringComparison]::Ordinal)
    )
}

function New-MediaPipelineCurrentStageNativePollHandler {
    <#
    .SYNOPSIS
    Creates a throttled native-process heartbeat for one exact run/job/stage.

    .DESCRIPTION
    Native tools can remain healthy without advancing a percentage for longer
    than the Run Monitor freshness window. This callback refreshes backend
    stage/worker evidence while preserving the last truthful percentage; when
    no valid percentage exists, Set-ProgressStage keeps the stage indeterminate.
    Optional audio refresh touches only already-active exact track IDs in the
    correlated Run Monitor item.
    #>
    param(
        [Parameter(Mandatory)] [string] $Stage,
        [string] $Status = '',
        [string] $Route = '',
        [double] $MinimumIntervalSeconds = 15,
        [switch] $RefreshActiveAudioTracks,
        [string] $EvidenceSource = 'native_process_heartbeat'
    )

    $runId = [string]$script:PipelineRunId
    $jobId = [string]$script:CurrentRunMonitorJobId
    $stageText = [string]$Stage
    $statusText = [string]$Status
    $routeText = [string]$Route
    $evidenceSourceText = if ([string]::IsNullOrWhiteSpace($EvidenceSource)) { 'native_process_heartbeat' } else { [string]$EvidenceSource }
    $refreshAudio = [bool]$RefreshActiveAudioTracks
    $pipelineRunVariable = Get-Variable -Name PipelineRunId -Scope Script -ErrorAction SilentlyContinue
    $currentJobVariable = Get-Variable -Name CurrentRunMonitorJobId -Scope Script -ErrorAction SilentlyContinue
    $currentStageVariable = Get-Variable -Name currentStage -Scope Script -ErrorAction SilentlyContinue
    $convertStageCommand = Get-Command -Name ConvertTo-MediaPipelineRunMonitorStageId -ErrorAction SilentlyContinue
    $setProgressCommand = Get-Command -Name Set-ProgressStage -ErrorAction SilentlyContinue
    $updateActiveTracksCommand = if ($refreshAudio) {
        Get-Command -Name Update-MediaPipelineRunMonitorActiveTrackHeartbeat -ErrorAction SilentlyContinue
    } else { $null }
    $capturedCanonicalStage = if ($convertStageCommand) {
        [string](& $convertStageCommand -PipelineStage $stageText)
    } else { '' }

    # Fail closed unless the callback is being created for the exact active
    # run/job/canonical stage. This also makes the factory safe for the native
    # wrapper's no-handler fallback: an uncorrelated tool never gains current
    # stage authority merely because it is recent.
    if ($null -eq $pipelineRunVariable -or $null -eq $currentJobVariable -or $null -eq $currentStageVariable -or
        $null -eq $convertStageCommand -or $null -eq $setProgressCommand -or
        [string]::IsNullOrWhiteSpace($capturedCanonicalStage) -or
        -not [string]::Equals([string]$pipelineRunVariable.Value, $runId, [System.StringComparison]::Ordinal) -or
        -not [string]::Equals([string]$currentJobVariable.Value, $jobId, [System.StringComparison]::Ordinal) -or
        -not [string]::Equals(
            [string](& $convertStageCommand -PipelineStage ([string]$currentStageVariable.Value)),
            $capturedCanonicalStage,
            [System.StringComparison]::Ordinal
        )) {
        return $null
    }

    $heartbeatWriter = {
        param($ElapsedSeconds, $Process)

        # A callback created for one synchronous operation must never migrate
        # to a later file if surrounding state changes during teardown.
        $currentCanonicalStage = ''
        try {
            $currentCanonicalStage = [string](& $convertStageCommand -PipelineStage ([string]$currentStageVariable.Value))
        } catch { return $null }
        if (-not [string]::Equals([string]$pipelineRunVariable.Value, $runId, [System.StringComparison]::Ordinal) -or
            -not [string]::Equals([string]$currentJobVariable.Value, $jobId, [System.StringComparison]::Ordinal) -or
            -not [string]::Equals($currentCanonicalStage, $capturedCanonicalStage, [System.StringComparison]::Ordinal)) {
            return $null
        }

        $stageArgs = @{ Stage = $stageText; SaveNow = $true }
        if (-not [string]::IsNullOrWhiteSpace($statusText)) { $stageArgs['Status'] = $statusText }
        if (-not [string]::IsNullOrWhiteSpace($routeText)) { $stageArgs['Route'] = $routeText }
        & $setProgressCommand @stageArgs

        if ($refreshAudio -and $updateActiveTracksCommand -and
            -not [string]::IsNullOrWhiteSpace($runId) -and
            -not [string]::IsNullOrWhiteSpace($jobId)) {
            & $updateActiveTracksCommand `
                -Kind audio `
                -RunId $runId `
                -JobId $jobId `
                -EvidenceSource $evidenceSourceText `
                -EvidenceProvenance worker_heartbeat | Out-Null
        }
        return $null
    }.GetNewClosure()

    if (Get-Command -Name New-ThrottledNativePollHandler -ErrorAction SilentlyContinue) {
        return New-ThrottledNativePollHandler -Handler $heartbeatWriter -MinimumIntervalSeconds $MinimumIntervalSeconds
    }
    return $heartbeatWriter
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
    $effectiveStage = if ([string]::IsNullOrWhiteSpace($Stage)) { 'audio_policy' } else { $Stage.Trim().ToLowerInvariant() }
    $isPolicyDecision = ($effectiveStage -eq 'audio_policy' -and -not $Completed -and -not $Failed)

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

    $hasRunMonitorCorrelation = (
        -not [string]::IsNullOrWhiteSpace([string]$script:PipelineRunId) -and
        -not [string]::IsNullOrWhiteSpace([string]$script:CurrentRunMonitorJobId)
    )
    if ($StreamIndex -lt 0 -and $Completed -and $effectiveStage -eq 'audio_policy' -and
        $hasRunMonitorCorrelation -and
        (Get-Command -Name Complete-MediaPipelineRunMonitorAudioPolicy -ErrorAction SilentlyContinue)) {
        try {
            Complete-MediaPipelineRunMonitorAudioPolicy `
                -RunId ([string]$script:PipelineRunId) `
                -JobId ([string]$script:CurrentRunMonitorJobId) `
                -Detail ([string]$script:currentAudioProgress.status) | Out-Null
        } catch {
            $script:RunMonitorPersistenceHealthy = $false
            Write-Log "Run Monitor aggregate audio-policy completion failed: $($_.Exception.Message)" 'WARN'
        }
    }

    if ($StreamIndex -ge 0 -and $hasRunMonitorCorrelation -and
        (Get-Command -Name Set-MediaPipelineRunMonitorTrackProgress -ErrorAction SilentlyContinue)) {
        try {
            $trackState = $(
                if ($Failed) { 'review' }
                elseif ($AudioAction -eq 'drop') { 'dropped' }
                elseif ($Completed -and $AudioAction -in @('omit','omit_all')) { 'not_applicable' }
                elseif ($Completed) { 'completed' }
                elseif ($isPolicyDecision) { 'awaiting_evidence' }
                else { 'active' }
            )
            $trackParams = @{
                Kind = 'audio'
                RunId = [string]$script:PipelineRunId
                JobId = [string]$script:CurrentRunMonitorJobId
                StreamIndex = [int]$StreamIndex
                CurrentAction = if ($isPolicyDecision -and $AudioAction -ne 'drop') { '' } elseif ([string]::IsNullOrWhiteSpace($AudioAction)) { 'evaluate' } else { $AudioAction }
                State = $trackState
                Result = if ($AudioAction -eq 'drop') { 'dropped' } elseif ($isPolicyDecision) { '' } else { $Detail }
            }
            if ($effectiveStage -eq 'audio_policy') {
                $trackParams['EvidenceSource'] = 'audio_policy'
                $trackParams['EvidenceProvenance'] = 'backend_confirmed'
            }
            if ($trackState -eq 'active' -and $PSBoundParameters.ContainsKey('Percent') -and $null -ne $percentValue) {
                $trackParams['Numerator'] = [double]$percentValue
                $trackParams['Denominator'] = 100.0
                $trackParams['NumericOnly'] = -not [bool]$SaveNow
            } elseif ($trackState -eq 'active') {
                $trackParams['Indeterminate'] = $true
            }
            $audioMonitorPayload = Set-MediaPipelineRunMonitorTrackProgress @trackParams
            if ($audioMonitorPayload -and
                (Get-Command -Name Set-MediaPipelineCurrentRunMonitorStage -ErrorAction SilentlyContinue)) {
                $itemMatches = @($audioMonitorPayload.items | Where-Object {
                    [string]$_.job_id -eq [string]$script:CurrentRunMonitorJobId
                })
                if ($itemMatches.Count -eq 1 -and $itemMatches[0].audio) {
                    $audioCollection = $itemMatches[0].audio
                    $audioTracks = @($audioCollection.tracks | Where-Object { $null -ne $_ })
                    $exactTrackMatches = @($audioTracks | Where-Object {
                        $null -ne $_.stream_index -and [int]$_.stream_index -eq [int]$StreamIndex
                    })
                    $audioStageState = ''
                    if ($exactTrackMatches.Count -eq 1) {
                        if ([string]$audioCollection.state -eq 'review') { $audioStageState = 'review' }
                        elseif ([string]$audioCollection.state -eq 'failed') { $audioStageState = 'failed' }
                        elseif ([string]$audioCollection.state -eq 'active') { $audioStageState = 'active' }
                        elseif ([string]$audioCollection.state -eq 'not_applicable') { $audioStageState = 'not_applicable' }
                        else {
                            $terminalStates = @('not_applicable','completed','failed','review','skipped','dropped')
                            $nonTerminalTracks = @($audioTracks | Where-Object { [string]$_.state -notin $terminalStates })
                            if ([bool]$audioCollection.policy_final -and
                                $audioTracks.Count -gt 0 -and
                                $nonTerminalTracks.Count -eq 0) {
                                $audioStageState = 'completed'
                            }
                            if ([string]::IsNullOrWhiteSpace($audioStageState) -and $isPolicyDecision) {
                                $audioStageState = 'active'
                            }
                        }
                    }
                    if (-not [string]::IsNullOrWhiteSpace($audioStageState)) {
                        $audioStageParams = @{
                            StageId = 'audio'
                            State = $audioStageState
                            Detail = [string]$script:currentAudioProgress.status
                            EvidenceSource = 'audio_policy'
                        }
                        if ($audioStageState -eq 'active' -and -not $isPolicyDecision -and $null -ne $percentValue) {
                            $audioStageParams['Numerator'] = [double]$percentValue
                            $audioStageParams['Denominator'] = 100.0
                            $audioStageParams['NumericOnly'] = -not [bool]$SaveNow
                        } elseif ($audioStageState -eq 'active') {
                            $audioStageParams['Indeterminate'] = $true
                        }
                        Set-MediaPipelineCurrentRunMonitorStage @audioStageParams | Out-Null
                    }
                }
            }
        } catch {
            $script:RunMonitorPersistenceHealthy = $false
            Write-Log "Run Monitor audio-track update failed for stream ${StreamIndex}: $($_.Exception.Message)" 'WARN'
        }
    }

    if ($SaveNow) {
        Save-Progress $script:pipelineStatus | Out-Null
    }
}

function Set-ProgressSubtitleTrack {
    param(
        [string]$Kind,
        [string]$TrackId = '',
        [int]$StreamIndex = -1,
        [string]$Stage,
        [string]$Status,
        [int]$StepIndex = 0,
        [int]$StepTotal = 0,
        [array]$Steps = @(),
        [string]$Detail = "",
        [object]$CueCount = $null,
        [object]$WorkNumerator = $null,
        [object]$WorkDenominator = $null,
        [string]$ProgressUnit = '',
        [string]$OutputCodec = '',
        [string]$OutputLocation = '',
        [string]$OutputPath = '',
        [string]$ParkedPath = '',
        [string]$IntendedFinalPath = '',
        [switch]$Completed,
        [switch]$Failed,
        [switch]$SaveNow
    )

    $safeTotal = [math]::Max(0, [int]$StepTotal)
    $safeIndex = if ($safeTotal -gt 0) { [math]::Max(0, [math]::Min($safeTotal, [int]$StepIndex)) } else { 0 }
    $validWorkProgress = $false
    $workNumeratorValue = $null
    $workDenominatorValue = $null
    try {
        if ($null -ne $WorkNumerator -and $null -ne $WorkDenominator -and
            [double]$WorkDenominator -gt 0 -and [double]$WorkNumerator -ge 0 -and
            [double]$WorkNumerator -le [double]$WorkDenominator) {
            $validWorkProgress = $true
            $workNumeratorValue = [double]$WorkNumerator
            $workDenominatorValue = [double]$WorkDenominator
        }
    } catch {}
    $percent = if ($validWorkProgress) { [math]::Round(($workNumeratorValue / $workDenominatorValue) * 100.0, 1) } else { $null }
    $stepNames = @($Steps | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) } | ForEach-Object { [string]$_ })
    $stepName = if ($safeIndex -gt 0 -and $safeIndex -le $stepNames.Count) {
        [string]$stepNames[$safeIndex - 1]
    } elseif (-not [string]::IsNullOrWhiteSpace($Stage)) {
        [string]$Stage
    } else { '' }
    $normalizedProgressUnit = ([string]$ProgressUnit).Trim().ToLowerInvariant()
    if ($normalizedProgressUnit -notin @('','items','pages','cues','frames','seconds','bytes','percent','unknown')) {
        $normalizedProgressUnit = 'unknown'
    }
    $cueCountValue = $null
    if ($null -ne $CueCount -and "${CueCount}" -ne '') {
        $parsedCueCount = 0
        if ([int]::TryParse([string]$CueCount, [ref]$parsedCueCount) -and $parsedCueCount -ge 0) {
            $cueCountValue = $parsedCueCount
        }
    }
    $completedSteps = @()
    if ($safeIndex -gt 0 -and $stepNames.Count -gt 0) {
        $completedSteps = @($stepNames | Select-Object -First $safeIndex)
    }

    $script:currentSubtitleProgress = [ordered]@{
        schema_version  = 'pipeline_subtitle_progress.v1'
        track_id        = $TrackId
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
        cue_count       = $cueCountValue
        work_numerator  = $workNumeratorValue
        work_denominator = $workDenominatorValue
        progress_unit   = $normalizedProgressUnit
        output_codec    = $OutputCodec
        output_location = $OutputLocation
        output_path     = $OutputPath
        parked_path     = $ParkedPath
        intended_final_path = $IntendedFinalPath
        updated_at      = Get-Date -Format 'o'
        completed       = [bool]$Completed
        failed          = [bool]$Failed
        source_file     = $script:currentFilePath
    }

    if (-not [string]::IsNullOrWhiteSpace([string]$script:PipelineRunId) -and
        -not [string]::IsNullOrWhiteSpace([string]$script:CurrentRunMonitorJobId) -and
        (Get-Command -Name Set-MediaPipelineRunMonitorTrackProgress -ErrorAction SilentlyContinue)) {
        try {
            $normalizedKind = ([string]$Kind).Trim().ToLowerInvariant()
            $normalizedStage = ([string]$Stage).Trim().ToLowerInvariant()
            $currentAction = switch ($normalizedStage) {
                'extract' { 'extract' }
                'validate' { 'validate' }
                'sidecar_write' { 'write_sidecar' }
                { $_ -in @('convert','convert_ocr','ocr') } {
                    switch -Regex ($normalizedKind) {
                        '^ass$' { 'convert_ass_to_srt'; break }
                        '^tx3g$' { 'convert_tx3g_to_srt'; break }
                        '^bdpgs(_ocr)?$' { 'ocr_bdpgs_to_srt'; break }
                        '^vobsub(_ocr)?$' { 'ocr_vobsub_to_srt'; break }
                        default { 'convert_subtitle' }
                    }
                }
                default { if ([string]::IsNullOrWhiteSpace($normalizedKind)) { 'working' } else { $normalizedKind } }
            }
            $trackParams = @{
                Kind = 'subtitles'
                RunId = [string]$script:PipelineRunId
                JobId = [string]$script:CurrentRunMonitorJobId
                StreamIndex = [int]$StreamIndex
                CurrentAction = $currentAction
                State = $(if ($Failed) { 'failed' } elseif ($Completed) { 'completed' } else { 'active' })
                Result = $Detail
                StepIndex = $safeIndex
                StepTotal = $safeTotal
                StepName = $stepName
                ProgressUnit = $normalizedProgressUnit
                CueCount = $cueCountValue
            }
            if (-not [string]::IsNullOrWhiteSpace($TrackId)) { $trackParams['TrackId'] = $TrackId }
            if (-not [string]::IsNullOrWhiteSpace($OutputCodec)) { $trackParams['OutputCodec'] = $OutputCodec }
            if (-not [string]::IsNullOrWhiteSpace($OutputLocation)) { $trackParams['OutputLocation'] = $OutputLocation }
            if (-not [string]::IsNullOrWhiteSpace($OutputPath)) { $trackParams['OutputPath'] = $OutputPath }
            if (-not [string]::IsNullOrWhiteSpace($ParkedPath)) { $trackParams['ParkedPath'] = $ParkedPath }
            if (-not [string]::IsNullOrWhiteSpace($IntendedFinalPath)) { $trackParams['IntendedFinalPath'] = $IntendedFinalPath }
            if ($validWorkProgress) {
                $trackParams['Numerator'] = $workNumeratorValue
                $trackParams['Denominator'] = $workDenominatorValue
                $trackParams['NumericOnly'] = -not [bool]$SaveNow
            } else {
                $trackParams['Indeterminate'] = -not [bool]($Completed -or $Failed)
            }
            $monitorPayload = Set-MediaPipelineRunMonitorTrackProgress @trackParams

            # The canonical subtitle stage follows only exact, backend-owned
            # track state. The final-policy marker proves that the complete
            # track set was seeded before an all-terminal collection can close
            # the stage; route names and step numbers are never stage evidence.
            if ($monitorPayload -and
                (Get-Command -Name Set-MediaPipelineCurrentRunMonitorStage -ErrorAction SilentlyContinue)) {
                $itemMatches = @($monitorPayload.items | Where-Object {
                    [string]$_.job_id -eq [string]$script:CurrentRunMonitorJobId
                })
                if ($itemMatches.Count -eq 1 -and $itemMatches[0].subtitles) {
                    $subtitleCollection = $itemMatches[0].subtitles
                    $subtitleTracks = @($subtitleCollection.tracks | Where-Object { $null -ne $_ })
                    $stageState = ''
                    $stageReasonCode = ''
                    $stageIndeterminate = $false

                    if ([string]$subtitleCollection.state -eq 'unknown') {
                        $stageState = 'unknown'
                        $stageReasonCode = 'subtitle_track_correlation_unknown'
                    } elseif (@($subtitleTracks | Where-Object { [string]$_.state -eq 'review' }).Count -gt 0) {
                        $stageState = 'review'
                        $stageReasonCode = 'subtitle_track_review'
                    } elseif (@($subtitleTracks | Where-Object { [string]$_.state -eq 'failed' }).Count -gt 0) {
                        $stageState = 'failed'
                        $stageReasonCode = 'subtitle_track_failed'
                    } elseif (@($subtitleTracks | Where-Object { [string]$_.state -eq 'active' }).Count -gt 0) {
                        $stageState = 'active'
                        $stageIndeterminate = $true
                    } else {
                        $terminalStates = @('not_applicable','completed','failed','review','skipped','dropped')
                        $nonTerminalTracks = @($subtitleTracks | Where-Object { [string]$_.state -notin $terminalStates })
                        if ([bool]$subtitleCollection.policy_final -and
                            $subtitleTracks.Count -gt 0 -and
                            $nonTerminalTracks.Count -eq 0) {
                            $stageState = 'completed'
                        }
                    }

                    if (-not [string]::IsNullOrWhiteSpace($stageState)) {
                        Set-MediaPipelineCurrentRunMonitorStage `
                            -StageId 'subtitles' `
                            -State $stageState `
                            -Detail ([string]$script:currentSubtitleProgress.status) `
                            -ReasonCode $stageReasonCode `
                            -EvidenceSource 'subtitle_progress' `
                            -Indeterminate:$stageIndeterminate | Out-Null
                    }
                }
            }
        } catch {
            $script:RunMonitorPersistenceHealthy = $false
            Write-Log "Run Monitor subtitle-track update failed for stream ${StreamIndex}: $($_.Exception.Message)" 'WARN'
        }
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

    if (-not [string]::IsNullOrWhiteSpace([string]$script:PipelineRunId) -and
        -not [string]::IsNullOrWhiteSpace([string]$script:CurrentRunMonitorJobId) -and
        (Get-Command -Name ConvertTo-MediaPipelineRunMonitorStageId -ErrorAction SilentlyContinue)) {
        $canonicalStage = ConvertTo-MediaPipelineRunMonitorStageId -PipelineStage ([string]$script:currentStage)
        if ($canonicalStage -in @('copy_to_scratch','publish')) {
            try {
                $stageParams = @{
                    RunId = [string]$script:PipelineRunId
                    JobId = [string]$script:CurrentRunMonitorJobId
                    StageId = $canonicalStage
                    State = 'active'
                    Detail = if ($null -ne $total -and [long]$total -gt 0) { 'Copying with backend byte totals.' } else { 'Copying; backend total is unavailable.' }
                    EvidenceSource = 'copy_telemetry'
                    NumericOnly = -not [bool]$SaveNow
                }
                if ($null -ne $bytes -and $null -ne $total -and [long]$total -gt 0 -and [long]$bytes -ge 0 -and [long]$bytes -le [long]$total) {
                    $stageParams['Numerator'] = [long]$bytes
                    $stageParams['Denominator'] = [long]$total
                } else {
                    $stageParams['Indeterminate'] = $true
                }
                Set-MediaPipelineRunMonitorStage @stageParams | Out-Null
            } catch {
                $script:RunMonitorPersistenceHealthy = $false
                Write-Log "Run Monitor copy telemetry failed: $($_.Exception.Message)" 'WARN'
            }
        }
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
        $stopAfterCurrentInfo = Get-ControlFlagInfo -Path $StopAfterCurrentFlag
        $rescanInfo = Get-ControlFlagInfo -Path $RescanFlag
        $tmp = Join-Path $progressDir ([System.IO.Path]::GetFileName($ProgressFile) + '.' + [System.IO.Path]::GetRandomFileName() + '.tmp')
        $backup = Join-Path $progressDir ([System.IO.Path]::GetFileName($ProgressFile) + '.' + [System.IO.Path]::GetRandomFileName() + '.bak')
        $json = [ordered]@{
            ProgressVersion       = $script:ProgressVersion
            WorkerRunId           = if ($WorkerChild) { [string]$WorkerRunId } else { '' }
            WorkerClaimId         = if ($WorkerChild) { [string]$WorkerClaimId } else { '' }
            RunMonitorJobId       = if ($WorkerChild) { [string]$WorkerJobId } else { '' }
            EvidenceUpdatedAt     = (Get-Date).ToUniversalTime().ToString('o')
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
            StopAfterCurrentRequested = [bool]($script:StopAfterCurrentRequested -or $stopAfterCurrentInfo.Exists)
            ControlRequests       = New-ControlRequestProgressState -PauseInfo $pauseInfo -StopInfo $stopInfo -StopAfterCurrentInfo $stopAfterCurrentInfo -RescanInfo $rescanInfo
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
        # A successful exact progress write is also child liveness evidence.
        # Refresh the separately watched heartbeat after the atomic save so
        # long copy/track/native stages do not trip the worker watchdog while
        # their correlated ProgressFile continues to advance.
        if (Get-Command -Name Write-MediaPipelineWorkerChildHeartbeat -ErrorAction SilentlyContinue) {
            try {
                Write-MediaPipelineWorkerChildHeartbeat -Stage $script:currentStage -Status $script:pipelineStatus | Out-Null
            } catch {}
        }
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
$script:CurrentExecutedRoute = $null
$script:CurrentExecutedRouteReasonCode = $null
$script:CurrentExecutedRouteReason = $null
$script:currentStage = 'initializing'
$script:currentStagePercent = $null
$script:currentItemStartedAt = $null
$script:currentStageStartedAt = Get-Date
$script:currentCopyState = $null
$script:currentPushState = $null
$script:currentSidecarState = $null
$script:pipelineStatus  = "Initializing"
$script:StopRequested   = $false
$script:StopAfterCurrentRequested = $false
$script:StopAfterCurrentAcknowledged = $false
$script:StopAfterCurrentRequestId = ''
$script:StopAfterCurrentRequestedAt = ''
$script:LastPauseRequestId = $null
$script:LastPauseRequestCreatedAt = $null
$script:LastPauseRequestObservedAt = $null
$script:LastStopRequestId = $null
$script:LastStopRequestCreatedAt = $null
$script:LastStopRequestObservedAt = $null
$script:LastStopAfterCurrentRequestId = $null
$script:LastStopAfterCurrentRequestCreatedAt = $null
$script:LastStopAfterCurrentRequestObservedAt = $null
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
