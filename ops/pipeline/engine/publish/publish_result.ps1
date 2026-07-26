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
        [string] $SourcePath = '',
        [long] $SourceSizeBytes = 0,
        [string] $Reason = '',
        [bool] $ParkedForOutputSpace = $false,
        [string] $PublishedPath = '',
        [string] $ParkedPath = '',
        [string] $IntendedFinalPath = '',
        [string] $ManifestPath = '',
        [array] $SidecarPaths = @(),
        [string] $PublishTransactionId = ''
    )

    return [pscustomobject]@{
        Ok                   = [bool]$Ok
        DeleteLocalOutput    = [bool]$DeleteLocalOutput
        KeepScratchInput     = [bool]$KeepScratchInput
        PublishState         = [string]$PublishState
        PublishMode          = [string]$PublishMode
        OutputPath           = [string]$OutputPath
        OutputSizeBytes      = [long]$OutputSizeBytes
        SourcePath           = [string]$SourcePath
        SourceSizeBytes      = [long]$SourceSizeBytes
        Reason               = [string]$Reason
        ParkedForOutputSpace = [bool]$ParkedForOutputSpace
        PublishedPath        = [string]$PublishedPath
        ParkedPath           = [string]$ParkedPath
        IntendedFinalPath    = [string]$IntendedFinalPath
        ManifestPath         = [string]$ManifestPath
        SidecarPaths         = @($SidecarPaths | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) } | ForEach-Object { [string]$_ })
        PublishTransactionId = [string]$PublishTransactionId
    }
}

function New-ExistingOutputPublishResult {
    param(
        [Parameter(Mandatory)] $SourceFile,
        [Parameter(Mandatory)] [string] $OutputPath
    )

    $outputSize = 0L
    if (Test-Path -LiteralPath $OutputPath -ErrorAction SilentlyContinue) {
        $outputSize = [long](Get-Item -LiteralPath $OutputPath).Length
    }

    $sourcePath = if ($SourceFile -and $SourceFile.PSObject.Properties['FullName']) { [string]$SourceFile.FullName } else { '' }
    $sourceSize = if ($SourceFile -and $SourceFile.PSObject.Properties['Length']) { [long]$SourceFile.Length } else { 0L }

    return New-PipelinePublishResult `
        -Ok:$true `
        -DeleteLocalOutput:$false `
        -KeepScratchInput:$false `
        -PublishState 'published' `
        -PublishMode 'existing-output' `
        -OutputPath $OutputPath `
        -PublishedPath $OutputPath `
        -IntendedFinalPath $OutputPath `
        -OutputSizeBytes $outputSize `
        -SourcePath $sourcePath `
        -SourceSizeBytes $sourceSize `
        -Reason 'Existing output accepted by reprocess policy'
}
