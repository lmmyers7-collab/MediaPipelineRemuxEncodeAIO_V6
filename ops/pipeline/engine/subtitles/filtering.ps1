# ==============================================================================
# ops\pipeline\engine\subtitles\filtering.ps1
# ==============================================================================
# Extracted from ops\pipeline\engine\subtitles\common.ps1. Keep function names stable;
# common.ps1 dot-sources this file as part of the subtitle policy surface.
# ==============================================================================

function New-SubtitleFilterEntry {
    param([Parameter(Mandatory)] $Policy)

    return @{
        Stream             = $Policy.Stream
        Lang               = $Policy.Lang
        Title              = $Policy.Title
        RawTitle           = $Policy.RawTitle
        Codec              = $Policy.Codec
        CodecTagString     = $Policy.CodecTagString
        SubtitleOrdinal    = $Policy.SubtitleOrdinal
        IsDefault          = $Policy.IsDefault
        SourceIsDefault    = $Policy.SourceIsDefault
        IsForced           = $Policy.IsForced
        LanguagePolicyMatched = $Policy.LanguagePolicyMatched
        RetainReason       = $Policy.RetainReason
        IsSdh              = $Policy.IsSdh
        IsSupplemental     = $Policy.IsSupplemental
        SupplementalForced = $Policy.SupplementalForced
        IsTx3g             = $Policy.IsTx3g
        IsBdpgs            = $Policy.IsBdpgs
        IsVobSub           = $Policy.IsVobSub
        SourceKind         = 'embedded'
    }
}

function Filter-SubtitleStreams {
    param(
        [string]$FilePath,
        [string]$Context = "",
        [string]$OriginalSourcePath = ""
    )
    Set-LastSubtitleDecisionRecords @()
    $keep        = [System.Collections.Generic.List[hashtable]]::new()
    $convert     = [System.Collections.Generic.List[hashtable]]::new()
    $tx3gConvert = [System.Collections.Generic.List[hashtable]]::new()
    $bdpgsConvert = [System.Collections.Generic.List[hashtable]]::new()
    $vobSubConvert = [System.Collections.Generic.List[hashtable]]::new()
    $burn        = [System.Collections.Generic.List[hashtable]]::new()
    $drop        = [System.Collections.Generic.List[hashtable]]::new()
    $decisions   = [System.Collections.Generic.List[object]]::new()

    $probeTimeoutSeconds = Get-SubtitleOperationTimeoutSeconds -ScriptVariableName 'SubtitleProbeTimeoutSeconds' -DefaultSeconds 30
    $r = Invoke-FFprobeCommand -ArgumentList @(
        "-v","error","-select_streams","s",
        "-show_entries","stream=index,codec_name,codec_long_name,codec_tag_string,codec_tag:stream_tags=language,title:stream_disposition=default,forced",
        "-of","json","--",$FilePath
    ) -TimeoutSeconds $probeTimeoutSeconds -Stage 'subtitle-stream-probe'
    if ($r.ExitCode -ne 0) {
        $reason = "${Context}Subtitle probe failed with exit $($r.ExitCode)"
        if ($r.Error) { $reason = "$reason`: $($r.Error)" }
        Write-Log $reason "ERROR"
        return @{ Ok=$false; ProbeFailed=$true; ErrorCode='SUBTITLE_PROBE_FAILED'; Reason=$reason; Keep=@($keep); Convert=@($convert); Tx3gConvert=@($tx3gConvert); BdpgsConvert=@($bdpgsConvert); VobSubConvert=@($vobSubConvert); Burn=@($burn); Drop=@($drop); Decisions=@($decisions) }
    }
    try { $probe = $r.Output | ConvertFrom-Json } catch {
        $reason = "${Context}Subtitle probe returned invalid JSON: $($_.Exception.Message)"
        Write-Log $reason "ERROR"
        return @{ Ok=$false; ProbeFailed=$true; ErrorCode='SUBTITLE_PROBE_JSON_INVALID'; Reason=$reason; Keep=@($keep); Convert=@($convert); Tx3gConvert=@($tx3gConvert); BdpgsConvert=@($bdpgsConvert); VobSubConvert=@($vobSubConvert); Burn=@($burn); Drop=@($drop); Decisions=@($decisions) }
    }
    if (-not $probe.streams -or $probe.streams.Count -eq 0) {
        $probe = [pscustomobject]@{ streams = @() }
    }

    # Per-file override: resolve subtitle track filter + rename rules once before the loop.
    $subtitleOverride = Get-FileOverrideSubtitleSettings
    if (Get-Command -Name Assert-FileOverrideExactTrackSelectorsResolvable -ErrorAction SilentlyContinue) {
        Assert-FileOverrideExactTrackSelectorsResolvable -TrackKind 'subtitle' -Tracks @($probe.streams) -OverrideSection $subtitleOverride
    }
    $subtitleBurnTrack = if (Get-Command -Name Get-FileOverrideSubtitleBurnTrack -ErrorAction SilentlyContinue) {
        Get-FileOverrideSubtitleBurnTrack -SubtitleOverride $subtitleOverride
    } else {
        $null
    }
    $subtitleBurnActive = ($null -ne $subtitleBurnTrack)

    $subtitleOrdinal = 0
    $inputSubtitleOrdinal = 0
    foreach ($s in $probe.streams) {
        $currentInputSubtitleOrdinal = $inputSubtitleOrdinal
        $inputSubtitleOrdinal++
        $policy = Resolve-SubtitleStreamPolicy -Stream $s -SubtitleOrdinal $subtitleOrdinal
        $sourceStreamIndex = if ($null -ne $s.PSObject.Properties['index']) { $s.index } else { $null }

        if ($subtitleBurnActive) {
            $isBurnedTrack = if (Get-Command -Name Test-SubtitleTrackBurnedByOverride -ErrorAction SilentlyContinue) {
                Test-SubtitleTrackBurnedByOverride `
                    -Language $policy.Lang `
                    -IsForced:([bool]$policy.IsForced) `
                    -Title $policy.RawTitle `
                    -Codec $policy.Codec `
                    -StreamIndex $sourceStreamIndex `
                    -SubtitleOverride $subtitleOverride
            } else {
                $false
            }
            if ($isBurnedTrack) {
                $entry = New-SubtitleFilterEntry -Policy $policy
                $entry['SubtitleInputOrdinal'] = $currentInputSubtitleOrdinal
                $entry['BurnEncodeProfile'] = 'current_encode_style'
                $burn.Add($entry)
                Write-Log "${Context}BURN subtitle stream $sourceStreamIndex ($($policy.Lang)) '$($policy.RawTitle)' into video; all selectable subtitle outputs will be dropped" "WARN"
                $decisions.Add([pscustomobject]@{
                    source_stream_index = $sourceStreamIndex
                    source_kind         = 'embedded'
                    subtitle_ordinal    = $currentInputSubtitleOrdinal
                    subtitle_input_ordinal = $currentInputSubtitleOrdinal
                    action              = 'burn'
                    reason              = 'file_override_burn_track'
                    language            = [string]$policy.Lang
                    source_codec        = [string]$policy.Codec
                    codec_tag_string    = [string]$policy.CodecTagString
                    title               = [string]$policy.RawTitle
                    raw_title           = [string]$policy.RawTitle
                    is_default          = [bool]$policy.IsDefault
                    source_is_default   = [bool]$policy.SourceIsDefault
                    is_forced           = [bool]$policy.IsForced
                    is_sdh              = [bool]$policy.IsSdh
                    is_supplemental     = [bool]$policy.IsSupplemental
                    is_tx3g             = [bool]$policy.IsTx3g
                    is_bdpgs            = [bool]$policy.IsBdpgs
                    is_vobsub           = [bool]$policy.IsVobSub
                    is_ass              = ([string]$policy.Codec -in (Get-MediaSubtitleCodecAssNames))
                    burn_encode_profile = 'current_encode_style'
                }) | Out-Null
                continue
            }
            $drop.Add(@{Stream=$s; Lang=$policy.Lang; Title=$policy.RawTitle})
            $decisions.Add([pscustomobject]@{
                source_stream_index = $sourceStreamIndex
                subtitle_ordinal    = $currentInputSubtitleOrdinal
                subtitle_input_ordinal = $currentInputSubtitleOrdinal
                action              = 'drop'
                reason              = 'file_override_burn_drops_selectable_subtitles'
                language            = [string]$policy.Lang
                source_codec        = [string]$policy.Codec
                codec_tag_string    = [string]$policy.CodecTagString
                title               = [string]$policy.RawTitle
                raw_title           = [string]$policy.RawTitle
                is_default          = [bool]$policy.IsDefault
                source_is_default   = [bool]$policy.SourceIsDefault
                is_forced           = [bool]$policy.IsForced
                is_sdh              = [bool]$policy.IsSdh
                is_supplemental     = [bool]$policy.IsSupplemental
                is_tx3g             = [bool]$policy.IsTx3g
                is_bdpgs            = [bool]$policy.IsBdpgs
                is_vobsub           = [bool]$policy.IsVobSub
                is_ass              = ([string]$policy.Codec -in (Get-MediaSubtitleCodecAssNames))
            }) | Out-Null
            continue
        }

        if (-not $policy.Retain) {
            $drop.Add(@{Stream=$s; Lang=$policy.Lang; Title=$policy.RawTitle})
            $decisions.Add([pscustomobject]@{
                source_stream_index = if ($null -ne $s.PSObject.Properties['index']) { $s.index } else { $null }
                subtitle_ordinal    = $subtitleOrdinal
                action              = 'drop'
                reason              = 'language_or_title_policy'
                language            = [string]$policy.Lang
                source_codec        = [string]$policy.Codec
                codec_tag_string    = [string]$policy.CodecTagString
                title               = [string]$policy.RawTitle
                raw_title           = [string]$policy.RawTitle
                is_default          = [bool]$policy.IsDefault
                source_is_default   = [bool]$policy.SourceIsDefault
                is_forced           = [bool]$policy.IsForced
                is_sdh              = [bool]$policy.IsSdh
                is_supplemental     = [bool]$policy.IsSupplemental
                is_tx3g             = [bool]$policy.IsTx3g
                is_bdpgs            = [bool]$policy.IsBdpgs
                is_vobsub           = [bool]$policy.IsVobSub
                is_ass              = ([string]$policy.Codec -in (Get-MediaSubtitleCodecAssNames))
            }) | Out-Null
            continue
        }

        # Per-file override: subtitle track filter (runs only on tracks that passed language/title policy).
        if (-not (Test-SubtitleTrackKeptByOverride `
                -Language $policy.Lang `
                -IsForced:([bool]$policy.IsForced) `
                -Title $policy.RawTitle `
                -Codec $policy.Codec `
                -StreamIndex $sourceStreamIndex `
                -SubtitleOverride $subtitleOverride)) {
            $drop.Add(@{Stream=$s; Lang=$policy.Lang; Title=$policy.RawTitle})
            $decisions.Add([pscustomobject]@{
                source_stream_index = if ($null -ne $s.PSObject.Properties['index']) { $s.index } else { $null }
                subtitle_ordinal    = $subtitleOrdinal
                action              = 'drop'
                reason              = 'file_override'
                language            = [string]$policy.Lang
                source_codec        = [string]$policy.Codec
                codec_tag_string    = [string]$policy.CodecTagString
                title               = [string]$policy.RawTitle
                raw_title           = [string]$policy.RawTitle
                is_default          = [bool]$policy.IsDefault
                source_is_default   = [bool]$policy.SourceIsDefault
                is_forced           = [bool]$policy.IsForced
                is_sdh              = [bool]$policy.IsSdh
                is_supplemental     = [bool]$policy.IsSupplemental
                is_tx3g             = [bool]$policy.IsTx3g
                is_bdpgs            = [bool]$policy.IsBdpgs
                is_vobsub           = [bool]$policy.IsVobSub
                is_ass              = ([string]$policy.Codec -in (Get-MediaSubtitleCodecAssNames))
            }) | Out-Null
            continue
        }

        $entry = New-SubtitleFilterEntry -Policy $policy
        # Per-file override: subtitle track title rename.
        $subTitleOverride = Get-SubtitleTrackTitleOverride -Language $policy.Lang -IsForced:([bool]$policy.IsForced) -SubtitleOverride $subtitleOverride
        if (-not [string]::IsNullOrWhiteSpace($subTitleOverride)) { $entry.Title = $subTitleOverride }
        $subtitleOrdinal++
        $routingDecision = Resolve-SubtitleRoutingDecision -Entry $entry
        Add-SubtitleRoutingDecision `
            -Entry $entry `
            -Decision $routingDecision `
            -Keep $keep `
            -Convert $convert `
            -Tx3gConvert $tx3gConvert `
            -BdpgsConvert $bdpgsConvert `
            -VobSubConvert $vobSubConvert `
            -Drop $drop `
            -Context $Context
        $decisions.Add((New-SubtitleDecisionRecord -Entry $entry -Decision $routingDecision)) | Out-Null
    }

    $sidecarSourcePath = if (-not [string]::IsNullOrWhiteSpace($OriginalSourcePath)) { $OriginalSourcePath } else { $FilePath }
    $scanVobSubSidecars = $true
    if (-not $subtitleBurnActive -and $scanVobSubSidecars -and (Get-Command -Name Find-VobSubSidecarPairs -ErrorAction SilentlyContinue) -and (Get-Command -Name New-VobSubSidecarSubtitleEntry -ErrorAction SilentlyContinue)) {
        foreach ($pair in @(Find-VobSubSidecarPairs -MediaPath $sidecarSourcePath -Context $Context)) {
            $entry = New-VobSubSidecarSubtitleEntry -Pair $pair -SubtitleOrdinal $subtitleOrdinal
            if (-not [bool]$entry.Retain) {
                $drop.Add($entry)
                $decisions.Add([pscustomobject]@{
                    source_stream_index = $null
                    source_kind         = 'sidecar'
                    subtitle_ordinal    = $subtitleOrdinal
                    action              = 'drop'
                    reason              = 'language_or_title_policy'
                    language            = [string]$entry.Lang
                    source_codec        = [string]$entry.Codec
                    codec_tag_string    = [string]$entry.CodecTagString
                    title               = [string]$entry.RawTitle
                    raw_title           = [string]$entry.RawTitle
                    is_default          = [bool]$entry.IsDefault
                    source_is_default   = [bool]$entry.SourceIsDefault
                    is_forced           = [bool]$entry.IsForced
                    is_sdh              = [bool]$entry.IsSdh
                    is_supplemental     = [bool]$entry.IsSupplemental
                    is_tx3g             = [bool]$entry.IsTx3g
                    is_bdpgs            = [bool]$entry.IsBdpgs
                    is_vobsub           = [bool]$entry.IsVobSub
                    is_ass              = $false
                }) | Out-Null
                $subtitleOrdinal++
                continue
            }

            if (-not (Test-SubtitleTrackKeptByOverride `
                    -Language $entry.Lang `
                    -IsForced:([bool]$entry.IsForced) `
                    -Title $entry.RawTitle `
                    -Codec $entry.Codec `
                    -StreamIndex $null `
                    -SubtitleOverride $subtitleOverride)) {
                $drop.Add($entry)
                $decisions.Add([pscustomobject]@{
                    source_stream_index = $null
                    source_kind         = 'sidecar'
                    subtitle_ordinal    = $subtitleOrdinal
                    action              = 'drop'
                    reason              = 'file_override'
                    language            = [string]$entry.Lang
                    source_codec        = [string]$entry.Codec
                    codec_tag_string    = [string]$entry.CodecTagString
                    title               = [string]$entry.RawTitle
                    raw_title           = [string]$entry.RawTitle
                    is_default          = [bool]$entry.IsDefault
                    source_is_default   = [bool]$entry.SourceIsDefault
                    is_forced           = [bool]$entry.IsForced
                    is_sdh              = [bool]$entry.IsSdh
                    is_supplemental     = [bool]$entry.IsSupplemental
                    is_tx3g             = [bool]$entry.IsTx3g
                    is_bdpgs            = [bool]$entry.IsBdpgs
                    is_vobsub           = [bool]$entry.IsVobSub
                    is_ass              = $false
                }) | Out-Null
                $subtitleOrdinal++
                continue
            }

            $routingDecision = Resolve-SubtitleRoutingDecision -Entry $entry
            Add-SubtitleRoutingDecision `
                -Entry $entry `
                -Decision $routingDecision `
                -Keep $keep `
                -Convert $convert `
                -Tx3gConvert $tx3gConvert `
                -BdpgsConvert $bdpgsConvert `
                -VobSubConvert $vobSubConvert `
                -Drop $drop `
                -Context $Context
            $decisions.Add((New-SubtitleDecisionRecord -Entry $entry -Decision $routingDecision)) | Out-Null
            $subtitleOrdinal++
        }
    }

    Write-Log "${Context}Subtitles: $($keep.Count) keep-as-is, $($convert.Count) ASS->SRT, $($tx3gConvert.Count) TX3G->SRT, $($bdpgsConvert.Count) BDPGS->SRT, $($vobSubConvert.Count) VobSub->SRT, $($burn.Count) burn-in, $($drop.Count) dropped"
    Set-LastSubtitleDecisionRecords @($decisions)
    return @{ Ok=$true; ProbeFailed=$false; ErrorCode=''; Reason=''; Keep=@($keep); Convert=@($convert); Tx3gConvert=@($tx3gConvert); BdpgsConvert=@($bdpgsConvert); VobSubConvert=@($vobSubConvert); Burn=@($burn); Drop=@($drop); Decisions=@($decisions) }
}
