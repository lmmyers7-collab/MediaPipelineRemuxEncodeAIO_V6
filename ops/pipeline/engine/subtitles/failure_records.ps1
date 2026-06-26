# ==============================================================================
# ops\pipeline\engine\subtitles\failure_records.ps1
# ==============================================================================
# Extracted from ops\pipeline\engine\subtitles\common.ps1. Keep function names stable;
# common.ps1 dot-sources this file as part of the subtitle policy surface.
# ==============================================================================

function Get-SubtitleFailureProperty {
    param(
        $Failure,
        [Parameter(Mandatory)] [string] $Name
    )

    if ($null -eq $Failure) { return $null }
    if ($Failure -is [System.Collections.IDictionary] -and $Failure.Contains($Name)) {
        return $Failure[$Name]
    }
    try {
        $prop = $Failure.PSObject.Properties[$Name]
        if ($prop) { return $prop.Value }
    } catch {}
    return $null
}

function Get-SubtitleFailureText {
    param(
        $Failure,
        [Parameter(Mandatory)] [string] $Name,
        [string] $Fallback = ''
    )

    $value = Get-SubtitleFailureProperty -Failure $Failure -Name $Name
    if ($null -eq $value) { return $Fallback }
    $text = [string]$value
    if ([string]::IsNullOrWhiteSpace($text)) { return $Fallback }
    return $text
}

function Get-SubtitleFailureStreamIndex {
    param($Failure)

    $value = Get-SubtitleFailureProperty -Failure $Failure -Name 'StreamIndex'
    if ($null -eq $value) { return -1 }
    try { return [int]$value } catch { return -1 }
}

function Get-SubtitleFailureStreamText {
    param(
        $Failure,
        [Parameter(Mandatory)] [string] $Fallback
    )

    $streamIndex = Get-SubtitleFailureStreamIndex -Failure $Failure
    if ($streamIndex -ge 0) { return "stream $streamIndex" }
    return $Fallback
}

function ConvertTo-SubtitleFailureEvidence {
    param(
        [array] $Failures = @(),
        [string] $Family = '',
        [int] $Limit = 12
    )

    $failureList = @($Failures | Where-Object { $null -ne $_ })
    $details = @()
    foreach ($failure in @($failureList | Select-Object -First $Limit)) {
        $details += [pscustomobject][ordered]@{
            stream_index = Get-SubtitleFailureStreamIndex -Failure $failure
            error_code   = Get-SubtitleFailureText -Failure $failure -Name 'ErrorCode' -Fallback 'SUBTITLE_UNKNOWN_FAILURE'
            reason       = Get-SubtitleFailureText -Failure $failure -Name 'Reason' -Fallback 'failure record was malformed'
            repro_path   = Get-SubtitleFailureText -Failure $failure -Name 'ReproPath' -Fallback ''
            codec        = Get-SubtitleFailureText -Failure $failure -Name 'Codec' -Fallback ''
            language     = Get-SubtitleFailureText -Failure $failure -Name 'Language' -Fallback ''
            tool         = Get-SubtitleFailureText -Failure $failure -Name 'Tool' -Fallback ''
            operation    = Get-SubtitleFailureText -Failure $failure -Name 'Operation' -Fallback ''
            category     = Get-SubtitleFailureText -Failure $failure -Name 'Category' -Fallback ''
        }
    }

    return [pscustomobject][ordered]@{
        schema_version  = 'pipeline_failure_subtitle_evidence.v1'
        family          = ([string]$Family).Trim()
        failure_count   = [int]$failureList.Count
        truncated_count = [math]::Max(0, [int]$failureList.Count - [int]$details.Count)
        failures        = @($details)
    }
}

function Register-Tx3gSubtitleFailure {
    param(
        [Parameter(Mandatory)] $SourceFile,
        [string] $ScratchPath,
        [array] $Failures = @(),
        [string] $Stage = 'subtitle-tx3g-extract'
    )

    $failureList = @($Failures | Where-Object { $null -ne $_ })
    if ($failureList.Count -eq 0) {
        $reason = 'TX3G subtitle failure reported without details'
        $null = Register-SourceFailure -SourceFile $SourceFile -ScratchPath $ScratchPath -Classification 'transient' -Reason $reason -Stage $Stage -ErrorCode 'SUBTITLE_TX3G_UNKNOWN_FAILURE' -SuggestedAction 'Review the pipeline log around the tx3g subtitle step and retry after correcting the source subtitle issue.'
        return
    }

    $first = $failureList[0]
    $streamText = Get-SubtitleFailureStreamText -Failure $first -Fallback 'a tx3g subtitle stream'
    $more = if ($failureList.Count -gt 1) { " (+$($failureList.Count - 1) more)" } else { "" }
    $firstReason = Get-SubtitleFailureText -Failure $first -Name 'Reason' -Fallback 'failure record was malformed'
    $reason = "TX3G subtitle extraction failed for ${streamText}${more}: $firstReason"
    $errorCode = Get-SubtitleFailureText -Failure $first -Name 'ErrorCode' -Fallback 'SUBTITLE_TX3G_EXTRACT_FAILED'
    $reproPath = Get-SubtitleFailureText -Failure $first -Name 'ReproPath' -Fallback ''
    $suggestedAction = 'Inspect the ffmpeg subtitle extraction repro/log, confirm the tx3g track is readable, or remove/replace the bad subtitle stream before retrying.'
    $failureProperties = [ordered]@{
        subtitle_failure_details = ConvertTo-SubtitleFailureEvidence -Failures $failureList -Family 'tx3g'
    }
    $null = Register-SourceFailure -SourceFile $SourceFile -ScratchPath $ScratchPath -Classification 'transient' -Reason $reason -Stage $Stage -ErrorCode $errorCode -ReproPath $reproPath -SuggestedAction $suggestedAction -AdditionalProperties $failureProperties
}

function Register-SubtitleExtractionFailure {
    param(
        [Parameter(Mandatory)] $SourceFile,
        [string] $ScratchPath,
        [array] $Failures = @(),
        [string] $Stage = 'subtitle-extract'
    )

    $failureList = @($Failures | Where-Object { $null -ne $_ })
    if ($failureList.Count -eq 0) {
        $null = Register-SourceFailure -SourceFile $SourceFile -ScratchPath $ScratchPath -Classification 'transient' -Reason 'Subtitle conversion failure reported without details' -Stage $Stage -ErrorCode 'SUBTITLE_UNKNOWN_FAILURE' -SuggestedAction 'Review the pipeline log around the subtitle step and retry after correcting the source subtitle issue.'
        return
    }

    $bdpgsFailures = @($failureList | Where-Object { (Get-SubtitleFailureText -Failure $_ -Name 'ErrorCode') -like 'SUBTITLE_BDPGS_*' })
    if ($bdpgsFailures.Count -gt 0) {
        $first = $bdpgsFailures[0]
        $streamText = Get-SubtitleFailureStreamText -Failure $first -Fallback 'a BDPGS subtitle stream'
        $more = if ($bdpgsFailures.Count -gt 1) { " (+$($bdpgsFailures.Count - 1) more)" } else { "" }
        $firstReason = Get-SubtitleFailureText -Failure $first -Name 'Reason' -Fallback 'failure record was malformed'
        $reason = "BDPGS subtitle OCR failed for ${streamText}${more}: $firstReason"
        $errorCode = Get-SubtitleFailureText -Failure $first -Name 'ErrorCode' -Fallback 'SUBTITLE_BDPGS_OCR_FAILED'
        $reproPath = Get-SubtitleFailureText -Failure $first -Name 'ReproPath' -Fallback ''
        $suggestedAction = 'Configure a PGS/SUP OCR tool such as PgsToSrt with Tesseract language data, inspect the repro command/log, or disable ConvertBdpgsToSrt to preserve image subtitles without OCR.'
        $failureProperties = [ordered]@{
            subtitle_failure_details = ConvertTo-SubtitleFailureEvidence -Failures $bdpgsFailures -Family 'bdpgs'
        }
        $null = Register-SourceFailure -SourceFile $SourceFile -ScratchPath $ScratchPath -Classification 'transient' -Reason $reason -Stage $Stage -ErrorCode $errorCode -ReproPath $reproPath -SuggestedAction $suggestedAction -AdditionalProperties $failureProperties
        return
    }

    $vobSubFailures = @($failureList | Where-Object { (Get-SubtitleFailureText -Failure $_ -Name 'ErrorCode') -like 'SUBTITLE_VOBSUB_*' })
    if ($vobSubFailures.Count -gt 0) {
        $first = $vobSubFailures[0]
        $streamText = Get-SubtitleFailureStreamText -Failure $first -Fallback 'a VobSub subtitle stream or sidecar'
        $more = if ($vobSubFailures.Count -gt 1) { " (+$($vobSubFailures.Count - 1) more)" } else { "" }
        $firstReason = Get-SubtitleFailureText -Failure $first -Name 'Reason' -Fallback 'failure record was malformed'
        $reason = "VobSub subtitle OCR failed for ${streamText}${more}: $firstReason"
        $errorCode = Get-SubtitleFailureText -Failure $first -Name 'ErrorCode' -Fallback 'SUBTITLE_VOBSUB_OCR_FAILED'
        $reproPath = Get-SubtitleFailureText -Failure $first -Name 'ReproPath' -Fallback ''
        $suggestedAction = 'Configure Subtitle Edit 4.x SubtitleEdit.exe and bundled Tesseract, inspect the repro command/log, or disable ConvertVobSubToSrt to preserve supported embedded VobSub tracks without OCR.'
        $failureProperties = [ordered]@{
            subtitle_failure_details = ConvertTo-SubtitleFailureEvidence -Failures $vobSubFailures -Family 'vobsub'
        }
        $null = Register-SourceFailure -SourceFile $SourceFile -ScratchPath $ScratchPath -Classification 'transient' -Reason $reason -Stage $Stage -ErrorCode $errorCode -ReproPath $reproPath -SuggestedAction $suggestedAction -AdditionalProperties $failureProperties
        return
    }

    $assFailures = @($failureList | Where-Object { (Get-SubtitleFailureText -Failure $_ -Name 'ErrorCode') -like 'SUBTITLE_ASS_*' })
    if ($assFailures.Count -gt 0) {
        $first = $assFailures[0]
        $streamText = Get-SubtitleFailureStreamText -Failure $first -Fallback 'an ASS subtitle stream'
        $more = if ($assFailures.Count -gt 1) { " (+$($assFailures.Count - 1) more)" } else { "" }
        $firstReason = Get-SubtitleFailureText -Failure $first -Name 'Reason' -Fallback 'failure record was malformed'
        $reason = "ASS subtitle conversion failed for ${streamText}${more}: $firstReason"
        $errorCode = Get-SubtitleFailureText -Failure $first -Name 'ErrorCode' -Fallback 'SUBTITLE_ASS_CONVERT_FAILED'
        $reproPath = Get-SubtitleFailureText -Failure $first -Name 'ReproPath' -Fallback ''
        $suggestedAction = 'Inspect the ass_to_srt helper repro/log, adjust ASS style filters if needed, or disable DropAssAfterConversion so the original ASS track can be retained while conversion is investigated.'
        $failureProperties = [ordered]@{
            subtitle_failure_details = ConvertTo-SubtitleFailureEvidence -Failures $assFailures -Family 'ass'
        }
        $null = Register-SourceFailure -SourceFile $SourceFile -ScratchPath $ScratchPath -Classification 'transient' -Reason $reason -Stage $Stage -ErrorCode $errorCode -ReproPath $reproPath -SuggestedAction $suggestedAction -AdditionalProperties $failureProperties
        return
    }

    $tx3gFailures = @($failureList | Where-Object { (Get-SubtitleFailureText -Failure $_ -Name 'ErrorCode') -like 'SUBTITLE_TX3G_*' })
    if ($tx3gFailures.Count -gt 0) {
        Register-Tx3gSubtitleFailure -SourceFile $SourceFile -ScratchPath $ScratchPath -Failures $tx3gFailures -Stage $Stage
        return
    }

    $firstFallback = $failureList[0]
    $fallbackDetail = Get-SubtitleFailureText -Failure $firstFallback -Name 'Reason' -Fallback 'failure record was malformed'
    $reasonFallback = "Subtitle conversion failed: $fallbackDetail"
    $errorCodeFallback = Get-SubtitleFailureText -Failure $firstFallback -Name 'ErrorCode' -Fallback 'SUBTITLE_UNKNOWN_FAILURE'
    $reproPathFallback = Get-SubtitleFailureText -Failure $firstFallback -Name 'ReproPath' -Fallback ''
    $failurePropertiesFallback = [ordered]@{
        subtitle_failure_details = ConvertTo-SubtitleFailureEvidence -Failures $failureList -Family 'unknown'
    }
    $null = Register-SourceFailure -SourceFile $SourceFile -ScratchPath $ScratchPath -Classification 'transient' -Reason $reasonFallback -Stage $Stage -ErrorCode $errorCodeFallback -ReproPath $reproPathFallback -SuggestedAction 'Review the pipeline log around the subtitle conversion step and retry after correcting the source subtitle issue.' -AdditionalProperties $failurePropertiesFallback
}
