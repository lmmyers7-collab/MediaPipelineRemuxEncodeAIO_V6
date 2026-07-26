# ==============================================================================
# MediaPipeline derived runtime paths + state layout  (dot-sourced by MediaPipeline.ps1)
# ==============================================================================
# Procedural slice: dot-sourced at the entrypoint top level, so the plain locals
# it sets ($LocalIncoming, $LogFile, $ProgressFile, $LockFile, ...) and every
# $script:* land in the entrypoint scope exactly as if inline. Reads $LocalBase
# and the -Worker* / -SingleFile parameters from the caller. No behaviour change.
# ==============================================================================
# Derived paths
$LocalIncoming        = Join-Path $LocalBase "Incoming"
$LocalEncoded         = Join-Path $LocalBase "Encoded"
$script:LocalStateLayout = New-MediaPipelineStateLayout -LocalBase $LocalBase
$LocalState           = $script:LocalStateLayout.Root
$LocalFailed          = $script:LocalStateLayout.Failures
$LocalFailureArtifacts = $script:LocalStateLayout.FailureArtifacts
$LocalActiveToolLogs     = $script:LocalStateLayout.ActiveToolLogs
$LocalInterruptedToolLogs = $script:LocalStateLayout.InterruptedToolLogs
$LocalFailureMarkers   = $script:LocalStateLayout.FailureMarkers
$LocalFailureReports   = $script:LocalStateLayout.FailureReports
# Completed-jobs manifest: an append-only JSONL log of every successful
# publish. Written locally (NOT on the outsource share) so the desktop
# app's Completed tab can list results without walking the SMB tree —
# which proved to be unacceptably slow/unreliable in the desktop UI.
# The canonical source of truth remains the .pipeline.json sidecar next
# to the output file; this manifest is a read-optimized mirror.
$LocalCompleted        = $script:LocalStateLayout.Completed
$CompletedJobsManifest = $script:LocalStateLayout.Paths.CompletedJobsManifest
$LocalRemuxTemp       = Join-Path $LocalBase "RemuxTemp"
# FIX#10: outputs whose server push failed are parked here instead of
# being deleted. The main loop retries them at the start of every round
# until they successfully land on the outsource.
$LocalPendingPush     = $script:LocalStateLayout.PendingPush
$RescanFlag           = $script:LocalStateLayout.Paths.RescanFlag
$LogFile              = Join-Path $LocalBase "pipeline_debug.log"
$PauseFlag            = $script:LocalStateLayout.Paths.PauseFlag
$StopFlag             = $script:LocalStateLayout.Paths.StopFlag
$StopAfterCurrentFlag = $script:LocalStateLayout.Paths.StopAfterCurrentFlag
$ProgressFile         = $script:LocalStateLayout.Paths.ProgressFile
$PipelineEventLogFile = $script:LocalStateLayout.Paths.PipelineEventLogFile
$script:PipelineEventLogFile = $PipelineEventLogFile
$script:PipelineRunId = if (-not [string]::IsNullOrWhiteSpace($RunId)) {
    [string]$RunId
} else {
    [guid]::NewGuid().ToString("N")
}
if ($WorkerChild -and -not [string]::IsNullOrWhiteSpace($WorkerRunId)) {
    $script:PipelineRunId = $WorkerRunId
}
$script:RunMonitorRoot = $script:LocalStateLayout.RunMonitor
$script:CurrentRunMonitorJobId = if ($WorkerChild) { [string]$WorkerJobId } else { '' }
$script:WorkerClaimId = if ($WorkerChild) { [string]$WorkerClaimId } else { '' }
$script:ProgressWriteFailures = 0
$script:ProgressPersistenceHealthy = $true
$LockFile             = Join-Path $LocalBase "pipeline.lock"
$script:processingDir = Join-Path $LocalIncoming "Processing"
$script:PendingPublishIndex = @{
    Count                 = 0
    BySourceIdentity      = @{}
    BySourceIdentityV2    = @{}
    ByServerOut           = @{}
    HasSourceIdentityV2   = $false
}
$script:FailureMarkerIndex = $null

if ($WorkerChild) {
    # exit inside a dot-sourced slice only aborts this file, not the
    # entrypoint; the sentinel tells MediaPipeline.ps1 to exit for real.
    if ($WorkerSlotId -lt 1 -or $WorkerSlotId -gt 2) {
        Write-Host "FATAL: -WorkerChild requires -WorkerSlotId 1 or 2." -ForegroundColor Red
        $startupFatalExitCode = 74
        exit 74
    }
    if ([string]::IsNullOrWhiteSpace($SingleFile)) {
        Write-Host "FATAL: -WorkerChild requires -SingleFile." -ForegroundColor Red
        $startupFatalExitCode = 74
        exit 74
    }
    if ([string]::IsNullOrWhiteSpace($WorkerResultPath)) {
        Write-Host "FATAL: -WorkerChild requires -WorkerResultPath." -ForegroundColor Red
        $startupFatalExitCode = 74
        exit 74
    }
    $script:WorkerSlotLayout = Initialize-MediaPipelineWorkerSlotLayout -SlotLayout (New-MediaPipelineWorkerSlotLayout -StateLayout $script:LocalStateLayout -SlotId $WorkerSlotId)
    $LocalIncoming        = $script:WorkerSlotLayout.Incoming
    $LocalEncoded         = $script:WorkerSlotLayout.Encoded
    $LocalRemuxTemp       = $script:WorkerSlotLayout.RemuxTemp
    $LocalFailed          = $script:WorkerSlotLayout.Failures
    $LogFile              = $script:WorkerSlotLayout.LogFile
    $ProgressFile         = $script:WorkerSlotLayout.ProgressFile
    $PipelineEventLogFile = $script:WorkerSlotLayout.EventLogFile
    $script:PipelineEventLogFile = $PipelineEventLogFile
    $LocalFailureArtifacts = $script:WorkerSlotLayout.FailureArtifacts
    $LocalActiveToolLogs     = $script:WorkerSlotLayout.ActiveToolLogs
    $LocalInterruptedToolLogs = $script:WorkerSlotLayout.InterruptedToolLogs
    $LocalFailureReports   = $script:WorkerSlotLayout.FailureReports
    $script:processingDir  = $script:WorkerSlotLayout.Processing
}
