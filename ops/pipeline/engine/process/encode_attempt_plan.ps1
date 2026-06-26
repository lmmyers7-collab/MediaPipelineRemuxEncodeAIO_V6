# Dot-sourced by ops/pipeline/entrypoints/MediaPipeline/module_loader.ps1.
# Encode core attempt planning.

function New-MediaPipelineEncodeCoreAttemptPlan {
    param(
        [bool] $UseSafeHardwareRetry = $false,
        [bool] $UseCpuFallback = $false,
        [bool] $IsTV,
        [bool] $IsHDR,
        [Parameter(Mandatory)] [string] $InputPath,
        [array] $ExtraInputs = @(),
        [string] $GlobalTitle = '',
        [array] $AudioArgs = @(),
        [array] $SubtitleMapArgs = @(),
        [array] $VideoFilterArgs = @(),
        [Parameter(Mandatory)] [string] $OutputContainer,
        [Parameter(Mandatory)] [string] $VideoCodec,
        [string] $VideoPreset = '',
        [int] $VideoQuality = 0,
        [array] $ExtraVideoFlags = @(),
        [int] $FallbackCpuQuality = 0,
        [string] $EncoderBackend = 'auto',
        [string] $EncodeLadder = '',
        [string] $CpuPreset = '',
        [int] $CpuMaxThreads = 0,
        [string] $Hdr10MasterDisplay = '',
        [string] $Hdr10MaxCll = '',
        [string] $TempPrefix = 'encode_temp',
        [string] $OutputPath = ''
    )

    $outputPath = if (-not [string]::IsNullOrWhiteSpace($OutputPath)) {
        $OutputPath
    } else {
        Join-Path $script:processingDir "$TempPrefix`_$([guid]::NewGuid().ToString('N')).$OutputContainer"
    }
    $plan = New-EncodeAttemptPlan `
        -UseCpuFallback:$UseCpuFallback `
        -UseSafeHardwareRetry:$UseSafeHardwareRetry `
        -IsTV:$IsTV `
        -IsHDR:$IsHDR `
        -InputPath $InputPath `
        -ExtraInputs $ExtraInputs `
        -GlobalTitle $GlobalTitle `
        -AudioArgs $AudioArgs `
        -SubtitleMapArgs $SubtitleMapArgs `
        -VideoFilterArgs $VideoFilterArgs `
        -OutputPath $outputPath `
        -VideoCodec $VideoCodec `
        -VideoPreset $VideoPreset `
        -VideoQuality $VideoQuality `
        -ExtraVideoFlags $ExtraVideoFlags `
        -FallbackCpuQuality $FallbackCpuQuality `
        -EncoderBackend $EncoderBackend `
        -EncodeLadder $EncodeLadder `
        -CpuPreset $CpuPreset `
        -CpuMaxThreads $CpuMaxThreads `
        -Hdr10MasterDisplay $Hdr10MasterDisplay `
        -Hdr10MaxCll $Hdr10MaxCll

    return [pscustomobject][ordered]@{
        OutputPath = $outputPath
        Plan       = $plan
    }
}
