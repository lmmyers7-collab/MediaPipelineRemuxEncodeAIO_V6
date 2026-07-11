# Dot-sourced by ops/pipeline/entrypoints/MediaPipeline/module_loader.ps1.
# Remux scratch, route, fallback, and source-policy gates.

function Invoke-MediaPipelineRemuxPreflight {
    param([Parameter(Mandatory)] $Context)

    Set-ProgressStage -Stage 'copy_to_scratch' -Status $script:pipelineStatus -Route 'remux' -CopyState 'starting' -Percent $null -SaveNow
    $Context.LocalIn = Ensure-ScratchCopy $Context.File $Context.SafeName
    if (-not $Context.LocalIn) {
        return New-MediaPipelineRemuxStageResult -Ok $false -Terminal $true -Value $false -Stage 'copy_to_scratch'
    }

    $Context.Paths = Get-OutputPaths $Context.File $Context.IsTV $Context.TvInfo $Context.SafeName
    if (Test-Path -LiteralPath $Context.Paths.ServerOut) {
        if (-not (Test-OutputNeedsReprocess -OutputPath $Context.Paths.ServerOut -SourceFile $Context.File)) {
            if (-not (Invoke-Tx3gSidecarExportForExistingOutput -SourceFile $Context.File -ScratchPath $Context.LocalIn -MediaOutputPath $Context.Paths.ServerOut -Context "REMUX: ")) {
                $Context.LocalIn = $null
                return New-MediaPipelineRemuxStageResult -Ok $false -Terminal $true -Value $false -Stage 'existing-output-sidecar'
            }
            $script:LastPublishResult = New-ExistingOutputPublishResult -SourceFile $Context.File -OutputPath $Context.Paths.ServerOut
            Write-Log "SKIP REMUX (exists on server): $(Split-Path $Context.Paths.ServerOut -Leaf)"
            Clear-SourceFailureState $Context.File
            return New-MediaPipelineRemuxStageResult -Ok $true -Terminal $true -Value $true -Stage 'existing-output'
        }
        Write-Log "REMUX: reprocess mode - existing output will remain in place until the replacement is verified" "WARN"
    }
    if (-not (Test-DiskSpace $LocalBase -MinGB $MinFreeSpaceGB -Label "LOCAL")) {
        return New-MediaPipelineRemuxStageResult -Ok $false -Terminal $true -Value $false -Stage 'disk-space'
    }

    if (-not (Test-EstimatedOutputSpace -SourcePath $Context.LocalIn -Label "REMUX" -RemuxTwoStage)) {
        return New-MediaPipelineRemuxStageResult -Ok $false -Terminal $true -Value $false -Stage 'remux-space'
    }

    $srcCodec = ''
    if ($script:CurrentRoutePlan -and $script:CurrentRoutePlan.PSObject.Properties['SourceCodec']) {
        $srcCodec = [string]$script:CurrentRoutePlan.SourceCodec
    }
    if ([string]::IsNullOrWhiteSpace($srcCodec) -or $srcCodec -eq 'unknown') {
        $srcCodec = Get-SourceVideoCodec $Context.LocalIn
    }
    $Context.SourceCodec = $srcCodec
    $codecRoutePlan = Resolve-RemuxCodecRoutePlan -SourceCodec $srcCodec -RemuxSafeVideoCodecs $RemuxSafeVideoCodecs -BasePlan $script:CurrentRoutePlan
    $Context.CodecRoutePlan = $codecRoutePlan

    if ($codecRoutePlan.Route -eq 'encode') {
        if ($Context.FallbackFromDynamicHdrEncode) {
            $script:LastDynamicHdrRemuxFallbackRejection = [pscustomobject][ordered]@{
                schema_version = 'dynamic_hdr_remux_fallback_rejection.v1'
                reason_code = [string]$codecRoutePlan.ReasonCode
                reason = [string]$codecRoutePlan.Reason
                source_codec = [string]$srcCodec
                remux_safe_video_codecs = @($RemuxSafeVideoCodecs)
                original_route_reason_code = [string]$script:CurrentRouteReasonCode
                original_route_reason = [string]$script:CurrentRouteReason
            }
            Write-Log "DYNAMIC HDR REMUX FALLBACK: remux blocked by codec/policy check; encode may continue only under preserve_or_remux warning semantics: $($codecRoutePlan.Reason)" "WARN"
            $Context.LocalIn = $null
            return New-MediaPipelineRemuxStageResult -Ok $false -Terminal $true -Value $false -Stage 'dynamic-hdr-remux-fallback-rejection'
        }
        if ($Context.FallbackFromOversizedEncode) {
            $fallbackSizePolicyMessage = ''
            if ($Context.FallbackSizePolicyResult -and $Context.FallbackSizePolicyResult.PSObject.Properties['message']) {
                $fallbackSizePolicyMessage = [string]$Context.FallbackSizePolicyResult.message
            }
            $script:LastRemuxFallbackRejection = [pscustomobject][ordered]@{
                schema_version = 'remux_fallback_rejection.v1'
                reason_code = [string]$codecRoutePlan.ReasonCode
                reason = [string]$codecRoutePlan.Reason
                source_codec = [string]$srcCodec
                remux_safe_video_codecs = @($RemuxSafeVideoCodecs)
                original_route_reason_code = $Context.FallbackSourceRouteReasonCode
                original_route_reason = $Context.FallbackSourceRouteReason
                size_policy_message = $fallbackSizePolicyMessage
            }
            Write-Log "REMUX FALLBACK: remux blocked by codec/policy check; oversized encode will be rejected: $($codecRoutePlan.Reason)" "WARN"
            return New-MediaPipelineRemuxStageResult -Ok $false -Terminal $true -Value $false -Stage 'remux-fallback-rejection'
        }
        $script:CurrentRoutePlan = $codecRoutePlan
        $script:CurrentRouteReasonCode = [string]$codecRoutePlan.ReasonCode
        $script:CurrentRouteReason = [string]$codecRoutePlan.Reason
        Write-Log "REMUX: $($codecRoutePlan.Reason)"
        $Context.LocalIn = $null
        $encodeResult = Do-Encode $Context.File $Context.IsTV $Context.TvInfo
        return New-MediaPipelineRemuxStageResult -Ok ([bool]$encodeResult) -Terminal $true -Value ([bool]$encodeResult) -Stage 'remux-codec-fallback-encode'
    }

    if ($Context.FallbackFromOversizedEncode) {
        $script:LastRemuxFallbackRejection = $null
        $fallbackSizePolicyMessage = ''
        if ($Context.FallbackSizePolicyResult -and $Context.FallbackSizePolicyResult.PSObject.Properties['message']) {
            $fallbackSizePolicyMessage = [string]$Context.FallbackSizePolicyResult.message
        }
        $fallbackReason = 'Remux fallback after oversized encode'
        if (-not [string]::IsNullOrWhiteSpace($Context.FallbackSourceRouteReasonCode)) {
            $fallbackReason = "$fallbackReason; original encode reason $($Context.FallbackSourceRouteReasonCode)"
        }
        if (-not [string]::IsNullOrWhiteSpace($Context.FallbackSourceRouteReason)) {
            $fallbackReason = "$fallbackReason - $($Context.FallbackSourceRouteReason)"
        }
        if (-not [string]::IsNullOrWhiteSpace($fallbackSizePolicyMessage)) {
            $fallbackReason = "$fallbackReason; $fallbackSizePolicyMessage"
        }
        $fallbackReason = "$fallbackReason; direct-copy size/bitrate caps bypassed for this fallback"
        $fallbackTraceData = [ordered]@{
            original_route_reason_code = $Context.FallbackSourceRouteReasonCode
            original_route_reason      = $Context.FallbackSourceRouteReason
            size_policy_message        = $fallbackSizePolicyMessage
            bypassed_size_bitrate_caps = $true
        }
        $fallbackTrace = @($codecRoutePlan.DecisionTrace) + (New-MediaRouteDecisionTraceEntry -Code 'oversized_encode_remux_fallback' -Message $fallbackReason -Data $fallbackTraceData)
        $codecRoutePlan.ReasonCode = 'oversized_encode_remux_fallback'
        $codecRoutePlan.Reason = $fallbackReason
        $codecRoutePlan.DecisionTrace = @($fallbackTrace)
        Write-Log "REMUX FALLBACK: safe remux accepted after oversized encode; publishing remux with out-of-scope warning evidence" "WARN"
    }
    $script:CurrentRoutePlan = $codecRoutePlan
    $script:CurrentRouteReasonCode = [string]$codecRoutePlan.ReasonCode
    $script:CurrentRouteReason = [string]$codecRoutePlan.Reason

    $videoStreamPolicy = Test-SourceVideoStreamPublishPolicy -FilePath $Context.LocalIn -Route 'remux'
    $Context.VideoStreamPolicy = $videoStreamPolicy
    if (-not [bool]$videoStreamPolicy.Allowed) {
        $reason = [string]$videoStreamPolicy.Reason
        $errorCode = [string]$videoStreamPolicy.ErrorCode
        $failureProperties = [ordered]@{
            source_video_stream_count       = [int]$videoStreamPolicy.Inventory.RealVideoStreamCount
            attached_picture_stream_count   = [int]$videoStreamPolicy.Inventory.AttachedPicCount
            video_stream_inventory          = $videoStreamPolicy.Inventory
            video_stream_evidence           = ConvertTo-VideoStreamFailureEvidence -SourceInventory $videoStreamPolicy.Inventory -Route 'remux' -Reason $reason -ErrorCode $errorCode
        }
        $null = Register-SourceFailure -SourceFile $Context.File -ScratchPath $Context.LocalIn -Classification 'operator_required' -Reason $reason -Stage 'video-stream-policy' -ErrorCode $errorCode -SuggestedAction 'Inspect ffprobe video stream inventory and attached-picture detection; publish remains blocked until source video stream inventory is probeable.' -AdditionalProperties $failureProperties
        Write-Log "REMUX: $reason" "ERROR"
        $Context.LocalIn = $null
        return New-MediaPipelineRemuxStageResult -Ok $false -Terminal $true -Value $false -Stage 'video-stream-policy'
    }

    $remuxHdrKnown = $false
    $remuxIsHdr = $false
    $sourceProfile = $null
    if ($script:CurrentRoutePlan -and $script:CurrentRoutePlan.PSObject.Properties['SourceMediaProfile']) {
        $sourceProfile = $script:CurrentRoutePlan.SourceMediaProfile
    }
    if ($sourceProfile -is [System.Collections.IDictionary] -and $sourceProfile.Contains('is_hdr')) {
        $remuxHdrKnown = $true
        $remuxIsHdr = [bool]$sourceProfile['is_hdr']
    } elseif ($sourceProfile -and $sourceProfile.PSObject.Properties['is_hdr']) {
        $remuxHdrKnown = $true
        $remuxIsHdr = [bool]$sourceProfile.is_hdr
    }
    if (-not $remuxHdrKnown) {
        $remuxHdrState = Get-HDRState $Context.LocalIn
        if ([bool]$remuxHdrState.Known) {
            $remuxHdrKnown = $true
            $remuxIsHdr = [bool]$remuxHdrState.IsHDR
        } else {
            Write-Log "REMUX: HDR state unknown during dynamic HDR probe gate ($($remuxHdrState.Reason)); continuing without dynamic-HDR evidence" "DEBUG"
        }
    }
    if ($remuxIsHdr) {
        $doviState = Get-DolbyVisionState -FilePath $Context.LocalIn
        $hdr10PlusState = Test-Hdr10PlusPresence -FilePath $Context.LocalIn
        $script:CurrentDynamicHdrEvidence = New-DynamicHdrEvidence -Route 'remux' -DoviState $doviState -Hdr10PlusState $hdr10PlusState
        $dynamicHdrPolicy = Resolve-DynamicHdrPolicy -Policy ([string]$script:DynamicHdrPolicy)
        if ($dynamicHdrPolicy -in @('preserve_or_remux','preserve_or_review') -and -not [bool]$script:CurrentDynamicHdrEvidence.probed) {
            $reason = 'Dynamic HDR source detection was inconclusive under a preservation policy; refusing remux without proof.'
            $null = Register-SourceFailure -SourceFile $Context.File -ScratchPath $Context.LocalIn -Classification 'operator_required' -Reason $reason -Stage 'remux-dynamic-hdr-probe' -ErrorCode 'DYNAMIC_HDR_OUTPUT_VERIFY_UNKNOWN' -SuggestedAction 'Inspect source ffprobe Dolby Vision and HDR10+ probe evidence; preservation policies require conclusive source detection before remux publish.' -AdditionalProperties @{ dynamic_hdr = $script:CurrentDynamicHdrEvidence }
            $Context.LocalIn = $null
            return New-MediaPipelineRemuxStageResult -Ok $false -Terminal $true -Value $false -Stage 'remux-dynamic-hdr-probe'
        }
        if ([bool]$script:CurrentDynamicHdrEvidence.dynamic_metadata_present) {
            Write-Log ("REMUX: source carries dynamic HDR metadata ({0}); preservation policy {1}" -f $script:CurrentDynamicHdrEvidence.summary, $dynamicHdrPolicy)
        }
    }

    Set-ProgressStage -Stage 'remux_prepare' -Status $script:pipelineStatus -Route 'remux' -CopyState 'complete' -Percent 0 -SaveNow
    return New-MediaPipelineRemuxStageResult -Ok $true -Terminal $false -Stage 'remux-preflight'
}
