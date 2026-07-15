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
