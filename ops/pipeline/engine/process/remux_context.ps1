# Dot-sourced by ops/pipeline/entrypoints/MediaPipeline/module_loader.ps1.
# Remux context and result helpers.

function New-MediaPipelineRemuxStageResult {
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

function New-MediaPipelineRemuxContext {
    param(
        [Parameter(Mandatory)] $File,
        [bool] $IsTV,
        $TvInfo,
        [switch] $FallbackFromOversizedEncode,
        [switch] $FallbackFromDynamicHdrEncode
    )

    $safeName = Get-SafeLocalName $File.Name
    $fallbackSizePolicyResult = if ($FallbackFromOversizedEncode) { $script:CurrentSizePolicyResult } else { $null }
    $fallbackSourceRouteReasonCode = if ($FallbackFromOversizedEncode) { [string]$script:CurrentRouteReasonCode } else { '' }
    $fallbackSourceRouteReason = if ($FallbackFromOversizedEncode) { [string]$script:CurrentRouteReason } else { '' }

    $script:LastPublishResult = $null
    $script:CurrentDynamicHdrEvidence = $null
    $script:LastMediaVerification = $null
    $script:LastAudioVerification = $null
    $script:LastSubtitleVerification = $null
    $script:LastMediaTrackVerification = $null
    $script:LastSubtitleConversionResults = @()
    if ($FallbackFromOversizedEncode) {
        $script:LastRemuxFallbackRejection = $null
    }
    if ($FallbackFromDynamicHdrEncode) {
        $script:LastDynamicHdrRemuxFallbackRejection = $null
    }
    if ($FallbackFromOversizedEncode) {
        $script:CurrentSizePolicyResult = $fallbackSizePolicyResult
    } else {
        $script:CurrentSizePolicyResult = $null
    }

    return [pscustomobject][ordered]@{
        File                              = $File
        IsTV                              = [bool]$IsTV
        TvInfo                            = $TvInfo
        FallbackFromOversizedEncode       = [bool]$FallbackFromOversizedEncode
        FallbackFromDynamicHdrEncode      = [bool]$FallbackFromDynamicHdrEncode
        SafeName                          = $safeName
        LocalIn                           = $null
        Paths                             = $null
        TempAvFile                        = $null
        SubFilter                         = $null
        SubTracks                         = $null
        PushOk                            = $false
        FallbackSizePolicyResult          = $fallbackSizePolicyResult
        FallbackSourceRouteReasonCode     = $fallbackSourceRouteReasonCode
        FallbackSourceRouteReason         = $fallbackSourceRouteReason
        SourceCodec                       = ''
        CodecRoutePlan                    = $null
        VideoStreamPolicy                 = $null
        AudioArgs                         = @()
        DefaultAudioLang                  = ''
        MkvArgs                           = @()
        MkvmergeResult                    = $null
        MediaVerification                 = $null
        AudioVerification                 = $null
        SubtitleVerification              = $null
        MediaTrackVerificationPlan        = $null
        MediaTrackVerification            = $null
    }
}
