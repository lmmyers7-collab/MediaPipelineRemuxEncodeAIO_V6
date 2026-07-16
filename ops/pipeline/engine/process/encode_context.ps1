# Dot-sourced by ops/pipeline/entrypoints/MediaPipeline/module_loader.ps1.
# Encode context and stage result helpers.

function New-MediaPipelineEncodeStageResult {
    param(
        [bool] $Ok = $true,
        [bool] $Terminal = $false,
        $Value = $null,
        [string] $Stage = ''
    )

    return [pscustomobject][ordered]@{
        Ok       = [bool]$Ok
        Terminal = [bool]$Terminal
        Value    = $Value
        Stage    = [string]$Stage
    }
}

function Get-MediaPipelineEncodeContextRequiredProperties {
    return @(
        'File',
        'IsTV',
        'TvInfo',
        'SafeName',
        'LocalIn',
        'Paths',
        'VideoStreamPolicy',
        'IsHDR',
        'TempOut',
        'SubResult',
        'AudioArgs',
        'DefaultAudioLang',
        'VerifyRoute',
        'EncodePlan',
        'FfArgs',
        'WasteGuardContext',
        'UsingCpu',
        'UsingSafeRetry',
        'PushOk',
        'DynamicHdrPolicy',
        'DynamicHdrDecision',
        'DynamicHdrForceCpuEncode',
        'DynamicHdrWorkingDirectory',
        'DynamicHdrTempFiles',
        'DynamicHdrDolbyVisionRpuPath',
        'DynamicHdrDolbyVisionTargetProfile',
        'DynamicHdrHdr10PlusJsonPath',
        'Hdr10MasterDisplay',
        'Hdr10MaxCll',
        'NormalizedEncoderBackend',
        'ForceCpuBackendEncode',
        'SkipGpuDueToProbe',
        'CpuFallbackEncoderName',
        'GlobalTitle',
        'PublishResult',
        'SizePolicyResult',
        'MediaVerification',
        'Hdr10Verification',
        'AudioVerification',
        'SubtitleVerification',
        'MediaTrackVerificationPlan',
        'MediaTrackVerification'
    )
}

function Test-MediaPipelineEncodeContextContract {
    param([AllowNull()] $Context)

    $missing = [System.Collections.Generic.List[string]]::new()
    foreach ($propertyName in @(Get-MediaPipelineEncodeContextRequiredProperties)) {
        if ($null -eq $Context -or $null -eq $Context.PSObject.Properties[$propertyName]) {
            $missing.Add($propertyName) | Out-Null
        }
    }

    return [pscustomobject][ordered]@{
        Ok                = ($missing.Count -eq 0)
        MissingProperties = @($missing)
        ErrorCode         = if ($missing.Count -eq 0) { '' } else { 'ENCODE_CONTEXT_CONTRACT_INVALID' }
    }
}

function Test-MediaPipelineEncodeContextFactoryContract {
    $probe = [pscustomobject][ordered]@{
        Name     = 'encode-context-contract-probe.mkv'
        FullName = 'encode-context-contract-probe.mkv'
    }
    $context = New-MediaPipelineEncodeContext -File $probe -IsTV:$false -TvInfo $null
    return Test-MediaPipelineEncodeContextContract -Context $context
}

function New-MediaPipelineEncodeContext {
    param(
        [Parameter(Mandatory)] $File,
        [bool] $IsTV,
        $TvInfo
    )

    $safeName = Get-SafeLocalName $File.Name
    $script:CurrentEncodeAttempts = @()
    $script:LastPublishResult = $null
    $script:CurrentSizePolicyResult = $null
    $script:LastRemuxFallbackRejection = $null
    $script:LastQualityVerification = $null
    $script:LastMediaVerification = $null
    $script:LastAudioVerification = $null
    $script:LastSubtitleVerification = $null
    $script:LastMediaTrackVerification = $null
    $script:LastSubtitleConversionResults = @()
    $script:CurrentDynamicHdrEvidence = $null

    return [pscustomobject][ordered]@{
        File              = $File
        IsTV              = [bool]$IsTV
        TvInfo            = $TvInfo
        SafeName          = $safeName
        LocalIn           = $null
        Paths             = $null
        VideoStreamPolicy = $null
        IsHDR             = $false
        TempOut           = $null
        SubResult         = $null
        AudioArgs         = @()
        DefaultAudioLang  = ''
        VerifyRoute       = 'encode'
        EncodePlan        = $null
        FfArgs            = @()
        WasteGuardContext = $null
        UsingCpu          = $false
        UsingSafeRetry    = $false
        PushOk            = $false
        DynamicHdrPolicy  = ''
        DynamicHdrDecision = $null
        DynamicHdrForceCpuEncode = $false
        DynamicHdrWorkingDirectory = ''
        DynamicHdrTempFiles = @()
        DynamicHdrDolbyVisionRpuPath = ''
        DynamicHdrDolbyVisionTargetProfile = ''
        DynamicHdrHdr10PlusJsonPath = ''
        Hdr10MasterDisplay = ''
        Hdr10MaxCll       = ''
        NormalizedEncoderBackend = 'auto'
        ForceCpuBackendEncode = $false
        SkipGpuDueToProbe = $false
        CpuFallbackEncoderName = ''
        GlobalTitle       = ''
        PublishResult     = $null
        SizePolicyResult  = $null
        MediaVerification = $null
        Hdr10Verification = $null
        AudioVerification = $null
        SubtitleVerification = $null
        MediaTrackVerificationPlan = $null
        MediaTrackVerification = $null
    }
}
