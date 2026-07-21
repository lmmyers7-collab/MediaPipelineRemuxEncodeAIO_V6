# ==============================================================================
# ops\pipeline\engine\process\worker_result.ps1
# ==============================================================================
# Extracted from ops\pipeline\entrypoints\MediaPipeline.ps1. The root entry script dot-sources
# this file to preserve the historical command and function surface.
# ==============================================================================

function Get-MediaPipelineWorkerResultField {
    param(
        $Result,
        [Parameter(Mandatory)] [string] $Name,
        $Default = $null
    )

    if ($Result -is [System.Collections.IDictionary] -and $Result.Contains($Name) -and $null -ne $Result[$Name]) {
        return $Result[$Name]
    }
    if ($Result -and $Result.PSObject.Properties[$Name] -and $null -ne $Result.$Name) {
        return $Result.$Name
    }
    return $Default
}

function Write-MediaPipelineWorkerChildHeartbeat {
    param(
        [string] $Stage = '',
        [string] $Status = '',
        [switch] $Final
    )

    if (-not $WorkerChild -or [string]::IsNullOrWhiteSpace($WorkerHeartbeatPath)) {
        return
    }

    $stageText = if ([string]::IsNullOrWhiteSpace($Stage)) { [string]$script:currentStage } else { [string]$Stage }
    $statusText = if ([string]::IsNullOrWhiteSpace($Status)) { [string]$script:pipelineStatus } else { [string]$Status }
    $workerJobIdText = ''
    try { $workerJobIdText = [string]$WorkerJobId } catch {
        try { $workerJobIdText = [string]$script:CurrentRunMonitorJobId } catch {}
    }
    $payload = [ordered]@{
        schema_version           = 'local_worker_heartbeat.v1'
        worker_slot_id           = [int]$WorkerSlotId
        worker_run_id            = [string]$WorkerRunId
        worker_claim_id          = [string]$WorkerClaimId
        run_monitor_job_id       = $workerJobIdText
        source_path              = [string]$SingleFile
        stage                    = $stageText
        status                   = $statusText
        current_file             = [string]$script:currentFile
        current_file_path        = [string]$script:currentFilePath
        current_queue_phase      = [string]$script:currentQueuePhase
        current_stage_started_at = Get-ProgressIsoTimestamp $script:currentStageStartedAt
        current_stage_percent    = $script:currentStagePercent
        progress_file            = [string]$ProgressFile
        final                    = [bool]$Final
        updated_at               = (Get-Date).ToUniversalTime().ToString('o')
    }

    try {
        Write-MediaPipelineJsonAtomic -Path $WorkerHeartbeatPath -InputObject $payload -Depth 10 | Out-Null
    } catch {
        try {
            $heartbeatParent = Split-Path -Parent $WorkerHeartbeatPath
            if (-not [string]::IsNullOrWhiteSpace($heartbeatParent)) {
                New-Item -ItemType Directory -Path $heartbeatParent -Force | Out-Null
            }
            ($payload | ConvertTo-Json -Depth 10) | Set-Content -LiteralPath $WorkerHeartbeatPath -Encoding UTF8 -Force
        } catch {
            Write-Log "WORKER CHILD: failed to write heartbeat to $WorkerHeartbeatPath`: $_" 'WARN'
        }
    }
}

function Write-MediaPipelineWorkerChildResult {
    param(
        [string] $SourcePath = '',
        $ProcessResult = $null,
        [bool] $IsTV = $false,
        [string] $MediaKind = '',
        [string] $MediaKindReason = '',
        [string] $Status = '',
        [bool] $Success = $false,
        [string] $Reason = '',
        [string] $ErrorCode = '',
        [string] $Route = '',
        [string] $PublishState = ''
    )

    if (-not $WorkerChild -or [string]::IsNullOrWhiteSpace($WorkerResultPath)) {
        return
    }

    $statusText = [string](Get-MediaPipelineWorkerResultField -Result $ProcessResult -Name 'Status' -Default $Status)
    if ([string]::IsNullOrWhiteSpace($statusText)) { $statusText = 'unknown' }
    $successValue = [bool](Get-MediaPipelineWorkerResultField -Result $ProcessResult -Name 'Success' -Default $Success)
    $reasonText = [string](Get-MediaPipelineWorkerResultField -Result $ProcessResult -Name 'Reason' -Default $Reason)
    $errorCodeText = [string](Get-MediaPipelineWorkerResultField -Result $ProcessResult -Name 'ErrorCode' -Default $ErrorCode)
    $sourcePathText = [string](Get-MediaPipelineWorkerResultField -Result $ProcessResult -Name 'SourcePath' -Default $SourcePath)
    $sourceNameText = [string](Get-MediaPipelineWorkerResultField -Result $ProcessResult -Name 'SourceName' -Default ([System.IO.Path]::GetFileName($sourcePathText)))
    $routeText = [string](Get-MediaPipelineWorkerResultField -Result $ProcessResult -Name 'Route' -Default $Route)
    $routeReasonCodeText = [string](Get-MediaPipelineWorkerResultField -Result $ProcessResult -Name 'RouteReasonCode' -Default '')
    $routeReasonText = [string](Get-MediaPipelineWorkerResultField -Result $ProcessResult -Name 'RouteReason' -Default '')
    $publishStateText = [string](Get-MediaPipelineWorkerResultField -Result $ProcessResult -Name 'PublishState' -Default $PublishState)
    $publishModeText = [string](Get-MediaPipelineWorkerResultField -Result $ProcessResult -Name 'PublishMode' -Default '')
    $queueTerminalValue = [bool](Get-MediaPipelineWorkerResultField -Result $ProcessResult -Name 'QueueTerminal' -Default $false)
    $retryableValue = [bool](Get-MediaPipelineWorkerResultField -Result $ProcessResult -Name 'Retryable' -Default $true)
    $outputPathText = [string](Get-MediaPipelineWorkerResultField -Result $ProcessResult -Name 'OutputPath' -Default '')
    $outputSizeBytes = 0L
    $workerJobIdText = ''
    try { $workerJobIdText = [string]$WorkerJobId } catch {
        try { $workerJobIdText = [string]$script:CurrentRunMonitorJobId } catch {}
    }
    try {
        $outputSizeBytes = [long](Get-MediaPipelineWorkerResultField -Result $ProcessResult -Name 'OutputSizeBytes' -Default 0)
    } catch {
        $outputSizeBytes = 0L
    }
    $publishEvidence = Get-MediaPipelineWorkerResultField -Result $ProcessResult -Name 'PublishEvidence' -Default $null
    $publishedPathText = [string](Get-MediaPipelineWorkerResultField -Result $ProcessResult -Name 'PublishedPath' -Default (Get-MediaPipelineWorkerResultField -Result $publishEvidence -Name 'published_path' -Default ''))
    $parkedPathText = [string](Get-MediaPipelineWorkerResultField -Result $ProcessResult -Name 'ParkedPath' -Default (Get-MediaPipelineWorkerResultField -Result $publishEvidence -Name 'parked_path' -Default ''))
    $intendedFinalPathText = [string](Get-MediaPipelineWorkerResultField -Result $ProcessResult -Name 'IntendedFinalPath' -Default (Get-MediaPipelineWorkerResultField -Result $publishEvidence -Name 'intended_final_path' -Default ''))
    $manifestPathText = [string](Get-MediaPipelineWorkerResultField -Result $ProcessResult -Name 'ManifestPath' -Default (Get-MediaPipelineWorkerResultField -Result $publishEvidence -Name 'manifest_path' -Default ''))
    $pipelineSidecarPathText = [string](Get-MediaPipelineWorkerResultField -Result $ProcessResult -Name 'PipelineSidecarPath' -Default (Get-MediaPipelineWorkerResultField -Result $publishEvidence -Name 'pipeline_sidecar_path' -Default ''))
    $sidecarPathsValue = @(Get-MediaPipelineWorkerResultField -Result $ProcessResult -Name 'SidecarPaths' -Default (Get-MediaPipelineWorkerResultField -Result $publishEvidence -Name 'sidecar_paths' -Default @()))
    $publishTransactionIdText = [string](Get-MediaPipelineWorkerResultField -Result $ProcessResult -Name 'PublishTransactionId' -Default (Get-MediaPipelineWorkerResultField -Result $publishEvidence -Name 'publish_transaction_id' -Default ''))

    $payload = [ordered]@{
        SchemaVersion       = 'local_worker_result.v1'
        Success             = $successValue
        Status              = $statusText
        Reason              = $reasonText
        ErrorCode           = $errorCodeText
        SourcePath          = $sourcePathText
        SourceName          = $sourceNameText
        IsTV                = [bool]$IsTV
        MediaKind           = [string]$MediaKind
        MediaKindReason     = [string]$MediaKindReason
        Route               = $routeText
        RouteReasonCode     = $routeReasonCodeText
        RouteReason         = $routeReasonText
        PublishState        = $publishStateText
        PublishMode         = $publishModeText
        QueueTerminal       = $queueTerminalValue
        Retryable           = $retryableValue
        OutputPath          = $outputPathText
        OutputSizeBytes     = $outputSizeBytes
        PublishedPath       = $publishedPathText
        ParkedPath          = $parkedPathText
        IntendedFinalPath   = $intendedFinalPathText
        ManifestPath        = $manifestPathText
        PipelineSidecarPath = $pipelineSidecarPathText
        SidecarPaths        = @($sidecarPathsValue)
        PublishTransactionId = $publishTransactionIdText
        WorkerSlotId        = [int]$WorkerSlotId
        WorkerRunId         = [string]$WorkerRunId
        WorkerClaimId       = [string]$WorkerClaimId
        WorkerJobId         = $workerJobIdText
        CompletedAt         = (Get-Date).ToString('o')
    }

    try {
        Write-MediaPipelineJsonAtomic -Path $WorkerResultPath -InputObject $payload -Depth 10 | Out-Null
        Write-MediaPipelineWorkerChildHeartbeat -Stage 'final_result' -Status $statusText -Final | Out-Null
        Write-Log "WORKER CHILD: wrote result status=$statusText success=$successValue path=$WorkerResultPath" 'DEBUG'
    } catch {
        Write-Log "WORKER CHILD: failed to write result to $WorkerResultPath`: $_" 'ERROR'
        Write-MediaPipelineWorkerChildHeartbeat -Stage 'final_result_write_failed' -Status 'Failed to write worker result' -Final | Out-Null
    }
}

# ==============================================================================
