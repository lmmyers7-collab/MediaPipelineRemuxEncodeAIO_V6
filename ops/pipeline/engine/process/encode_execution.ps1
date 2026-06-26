# Dot-sourced by ops/pipeline/entrypoints/MediaPipeline/module_loader.ps1.
# Encode FFmpeg execution wrapper for core attempts.

function Invoke-MediaPipelineEncodeAttemptExecution {
    param(
        [Parameter(Mandatory)] $Plan,
        [array] $ArgumentList = @(),
        [Parameter(Mandatory)] [string] $InputPath,
        [Parameter(Mandatory)] [string] $OutputPath,
        [Parameter(Mandatory)] [int] $TimeoutSeconds,
        $WasteGuardContext = $null,
        [switch] $CpuEncode,
        [string] $ProcessPriority = '',
        [string] $WorkingDirectory = ''
    )

    $callArgs = @{
        FFArgs            = $ArgumentList
        Label             = $Plan.Label
        InputFile         = $InputPath
        TimeoutSeconds    = $TimeoutSeconds
        ProgressStage     = $Plan.ProgressStage
        ProgressRoute     = $Plan.ProgressRoute
        ReproStage        = $Plan.ReproStage
        OutputPath        = $OutputPath
        WasteGuardContext = $WasteGuardContext
    }
    if ($CpuEncode) {
        $callArgs['CpuEncode'] = $true
        if (-not [string]::IsNullOrWhiteSpace($ProcessPriority)) {
            $callArgs['ProcessPriority'] = $ProcessPriority
        }
    }
    if (-not [string]::IsNullOrWhiteSpace($WorkingDirectory)) {
        $callArgs['WorkingDirectory'] = $WorkingDirectory
    }

    return Invoke-FFmpegWithProgress @callArgs
}
