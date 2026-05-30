# Publish result contract helpers.
# Dot-sourced before PublishCompletion.ps1 by MediaPipeline.ps1.

function New-PipelinePublishResult {
    param(
        [bool] $Ok,
        [bool] $DeleteLocalOutput = $false,
        [bool] $KeepScratchInput = $false,
        [string] $PublishState = '',
        [string] $PublishMode = '',
        [string] $OutputPath = '',
        [long] $OutputSizeBytes = 0,
        [string] $Reason = '',
        [bool] $ParkedForOutputSpace = $false
    )

    return [pscustomobject]@{
        Ok                   = [bool]$Ok
        DeleteLocalOutput    = [bool]$DeleteLocalOutput
        KeepScratchInput     = [bool]$KeepScratchInput
        PublishState         = [string]$PublishState
        PublishMode          = [string]$PublishMode
        OutputPath           = [string]$OutputPath
        OutputSizeBytes      = [long]$OutputSizeBytes
        Reason               = [string]$Reason
        ParkedForOutputSpace = [bool]$ParkedForOutputSpace
    }
}
