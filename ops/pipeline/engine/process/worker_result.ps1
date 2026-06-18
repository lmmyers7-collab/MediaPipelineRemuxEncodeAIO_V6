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

    if ($Result -and $Result.PSObject.Properties[$Name] -and $null -ne $Result.$Name) {
        return $Result.$Name
    }
    return $Default
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
    try {
        $outputSizeBytes = [long](Get-MediaPipelineWorkerResultField -Result $ProcessResult -Name 'OutputSizeBytes' -Default 0)
    } catch {
        $outputSizeBytes = 0L
    }

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
        WorkerSlotId        = [int]$WorkerSlotId
        WorkerRunId         = [string]$WorkerRunId
        WorkerClaimId       = [string]$WorkerClaimId
        CompletedAt         = (Get-Date).ToString('o')
    }

    try {
        Write-MediaPipelineJsonAtomic -Path $WorkerResultPath -InputObject $payload -Depth 10 | Out-Null
        Write-Log "WORKER CHILD: wrote result status=$statusText success=$successValue path=$WorkerResultPath" 'DEBUG'
    } catch {
        Write-Log "WORKER CHILD: failed to write result to $WorkerResultPath`: $_" 'ERROR'
    }
}

# ==============================================================================
