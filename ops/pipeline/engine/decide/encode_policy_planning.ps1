# Extracted from ops/pipeline/engine/decide/encode_policy.ps1. Responsibility: encode attempt planning

function New-EncodeAttemptPlan {
    param(
        [bool] $UseCpuFallback = $false,
        [bool] $UseSafeHardwareRetry = $false,
        [bool] $IsTV = $false,
        [bool] $IsHDR = $false,
        [Parameter(Mandatory)] [string] $InputPath,
        [array] $ExtraInputs = @(),
        [Parameter(Mandatory)] [string] $GlobalTitle,
        [array] $AudioArgs = @(),
        [array] $SubtitleMapArgs = @(),
        [array] $VideoFilterArgs = @(),
        [Parameter(Mandatory)] [string] $OutputPath,
        [Parameter(Mandatory)] [string] $VideoCodec,
        [Parameter(Mandatory)] [string] $VideoPreset,
        [Parameter(Mandatory)] [int] $VideoQuality,
        [array] $ExtraVideoFlags = @(),
        [int] $FallbackCpuQuality = 20,
        [string] $EncoderBackend = 'auto',
        [string] $EncodeLadder = 'auto',
        [string] $CpuPreset = 'medium',
        [int] $CpuMaxThreads = 0,
        # Suggestion #1 — HDR10 mastering metadata extracted from the
        # source by Get-SourceHdr10MasteringMetadata. Forwarded to
        # New-EncodeVideoFlags only when UseCpuFallback (NVENC reads
        # mastering metadata from libav side-data on its own). Empty
        # strings are no-ops.
        [string] $Hdr10MasterDisplay = '',
        [string] $Hdr10MaxCll = '',
        # Dynamic HDR preservation artifacts are supplied only after a
        # backend-owned extraction step. They are no-ops when blank and are
        # guarded by New-EncodeVideoFlags so NVENC and non-HDR paths cannot
        # accidentally receive x265-only parameters.
        [string] $DolbyVisionRpuPath = '',
        [string] $DolbyVisionTargetProfile = '',
        [string] $Hdr10PlusJsonPath = ''
    )

    $normalizedEncoderBackend = if ($EncoderBackend) { $EncoderBackend.Trim().ToLowerInvariant() } else { 'auto' }
    if ([string]::IsNullOrWhiteSpace($normalizedEncoderBackend)) { $normalizedEncoderBackend = 'auto' }
    $effectiveUseCpuFallback = [bool]$UseCpuFallback -or ($normalizedEncoderBackend -eq 'cpu')
    $ladderProfile = Get-MediaEncodeLadderProfile -Ladder $EncodeLadder -IsTV:$IsTV
    $videoFlags = New-EncodeVideoFlags `
        -IsHDR:$IsHDR `
        -IsTV:$IsTV `
        -UseCpuFallback:$effectiveUseCpuFallback `
        -UseSafeHardwareRetry:$UseSafeHardwareRetry `
        -VideoCodec $VideoCodec `
        -VideoPreset $VideoPreset `
        -VideoQuality $VideoQuality `
        -ExtraVideoFlags $ExtraVideoFlags `
        -FallbackCpuQuality $FallbackCpuQuality `
        -EncoderBackend $normalizedEncoderBackend `
        -EncodeLadder $EncodeLadder `
        -CpuPreset $CpuPreset `
        -CpuMaxThreads $CpuMaxThreads `
        -Hdr10MasterDisplay $Hdr10MasterDisplay `
        -Hdr10MaxCll $Hdr10MaxCll `
        -DolbyVisionRpuPath $DolbyVisionRpuPath `
        -DolbyVisionTargetProfile $DolbyVisionTargetProfile `
        -Hdr10PlusJsonPath $Hdr10PlusJsonPath

    $argumentList = New-EncodeFfmpegArgumentList `
        -InputPath $InputPath `
        -ExtraInputs $ExtraInputs `
        -GlobalTitle $GlobalTitle `
        -VideoFlags $videoFlags `
        -VideoFilterArgs $VideoFilterArgs `
        -AudioArgs $AudioArgs `
        -SubtitleMapArgs $SubtitleMapArgs `
        -OutputPath $OutputPath

    $selectedEncoder = Get-EncodeArgumentValue -Arguments $videoFlags -Name '-c:v'
    if ([string]::IsNullOrWhiteSpace($selectedEncoder)) {
        $selectedEncoder = if ($effectiveUseCpuFallback) { Get-MediaVideoCodecLibx265Name } else { $VideoCodec }
    }
    $encoderKind = Get-EncodeEncoderKind -Encoder $selectedEncoder -UseCpuFallback:$effectiveUseCpuFallback
    # CPU encodes never bind to a GPU device. Force-clear so sidecar telemetry
    # does not falsely attribute a CPU encode to GPU 0 when an earlier hardware
    # attempt left -gpu/-hwaccel_device tokens in argv parsers' memory.
    $selectedGpuDevice = if ($effectiveUseCpuFallback) { '' } else { Get-EncodeSelectedGpuDevice -VideoFlags $videoFlags }
    $descriptorSelection = New-EncodeAttemptDescriptorSelectionEvidence `
        -VideoCodec $VideoCodec `
        -EncoderBackend $normalizedEncoderBackend `
        -UseCpuFallback:$effectiveUseCpuFallback `
        -IsHDR:$IsHDR `
        -SelectedEncoder $selectedEncoder
    $resolvedCpuPreset = if (Get-Command -Name Resolve-MediaPipelineCpuEncodePreset -ErrorAction SilentlyContinue) {
        Resolve-MediaPipelineCpuEncodePreset -Preset $CpuPreset
    } else {
        $CpuPreset
    }

    if ($effectiveUseCpuFallback) {
        return [pscustomobject]@{
            Attempt        = 'cpu_fallback'
            UseCpuFallback = $true
            UseSafeHardwareRetry = $false
            Route          = Get-MediaRouteEncodeCpuFallbackName
            Label          = 'ENCODE-CPU'
            ProgressStage  = 'encode_cpu'
            ProgressRoute  = 'encode'
            ReproStage     = 'encode-cpu'
            EncodeLadder   = [string]$ladderProfile.name
            EncodeLadderProfile = $ladderProfile
            SelectedEncoder = $selectedEncoder
            EncoderKind     = $encoderKind
            SelectedGpuDevice = $selectedGpuDevice
            DescriptorSelection = $descriptorSelection
            VideoFlags     = @($videoFlags)
            ArgumentList   = @($argumentList)
            CpuPreset      = [string]$resolvedCpuPreset
        }
    }

    if ($UseSafeHardwareRetry) {
        return [pscustomobject]@{
            Attempt        = 'hardware_safe_retry'
            UseCpuFallback = $false
            UseSafeHardwareRetry = $true
            Route          = Get-MediaRouteEncodeName
            Label          = 'ENCODE-SAFE'
            ProgressStage  = 'encode_safe'
            ProgressRoute  = 'encode'
            ReproStage     = 'encode-safe'
            EncodeLadder   = [string]$ladderProfile.name
            EncodeLadderProfile = $ladderProfile
            SelectedEncoder = $selectedEncoder
            EncoderKind     = $encoderKind
            SelectedGpuDevice = $selectedGpuDevice
            DescriptorSelection = $descriptorSelection
            VideoFlags     = @($videoFlags)
            ArgumentList   = @($argumentList)
            # D4 fix — keep CpuPreset on every plan shape so consumers
            # iterating $plan.CpuPreset don't NRE on non-CPU rows.
            CpuPreset      = ''
        }
    }

    return [pscustomobject]@{
        Attempt        = 'primary'
        UseCpuFallback = $false
        UseSafeHardwareRetry = $false
        Route          = Get-MediaRouteEncodeName
        Label          = 'ENCODE'
        ProgressStage  = 'encode'
        ProgressRoute  = 'encode'
        ReproStage     = 'encode'
        EncodeLadder   = [string]$ladderProfile.name
        EncodeLadderProfile = $ladderProfile
        SelectedEncoder = $selectedEncoder
        EncoderKind     = $encoderKind
        SelectedGpuDevice = $selectedGpuDevice
        DescriptorSelection = $descriptorSelection
        VideoFlags     = @($videoFlags)
        ArgumentList   = @($argumentList)
        # D4 fix — keep CpuPreset on every plan shape so consumers iterating
        # $plan.CpuPreset don't NRE on non-CPU rows.
        CpuPreset      = ''
    }
}
