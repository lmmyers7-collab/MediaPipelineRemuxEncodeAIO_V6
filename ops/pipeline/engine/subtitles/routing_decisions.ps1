# ==============================================================================
# ops\pipeline\engine\subtitles\routing_decisions.ps1
# ==============================================================================
# Extracted from ops\pipeline\engine\subtitles\common.ps1. Keep function names stable;
# common.ps1 dot-sources this file as part of the subtitle policy surface.
# ==============================================================================

function Get-SubtitleSupplementalForcedSwitchName {
    param(
        [string]$Codec,
        [bool]$IsTx3g = $false,
        [bool]$IsBdpgs = $false,
        [bool]$IsVobSub = $false
    )

    if ($IsTx3g) { return 'TreatTx3gSignsSongsAsForced' }
    if ($IsBdpgs) { return 'TreatBdpgsSignsSongsAsForced' }
    if ($IsVobSub) { return 'TreatVobSubSignsSongsAsForced' }
    if ($Codec -in (Get-MediaSubtitleCodecAssNames)) { return 'TreatAssSignsSongsAsForced' }
    return ''
}

function New-SubtitleEnrichedTitle {
    param(
        [string]$Language,
        [string]$RawTitle,
        [string]$TitleLower,
        [bool]$IsSdh,
        [bool]$IsForced,
        [bool]$IsSupplemental
    )

    $displayMap = Get-SubtitleLanguageDisplayMap
    $langDisp = if ($displayMap.ContainsKey($Language)) { $displayMap[$Language] } else {
        if ($Language) { $Language.ToUpperInvariant() } else { 'Undefined' }
    }

    $title = if ([string]::IsNullOrWhiteSpace($RawTitle)) { $langDisp } else { $RawTitle }
    if ($IsSdh -and $TitleLower -notmatch '(?i)sdh|hearing') { $title += " [SDH]" }
    if ($IsForced -and $TitleLower -notmatch '(?i)forced') { $title += " [Forced]" }
    if ($IsSupplemental -and $TitleLower -notmatch '(?i)sign|song|karaoke') {
        $title += " [Signs & Songs]"
    }
    return $title
}

function Get-SubtitleRoutingEntryValue {
    param(
        [Parameter(Mandatory)] $Entry,
        [Parameter(Mandatory)] [string] $Name,
        $Default = $null
    )

    if ($null -eq $Entry) { return $Default }
    if ($Entry -is [System.Collections.IDictionary] -and $Entry.Contains($Name)) {
        return $Entry[$Name]
    }
    $prop = $Entry.PSObject.Properties[$Name]
    if ($null -ne $prop) { return $prop.Value }
    return $Default
}

function ConvertTo-SubtitleRoutingBool {
    param(
        $Value,
        [bool] $Default = $false
    )

    if ($null -eq $Value) { return $Default }
    if ($Value -is [bool]) { return [bool]$Value }
    $text = ([string]$Value).Trim()
    if ([string]::IsNullOrWhiteSpace($text)) { return $Default }
    return ($text -match '^(true|1|yes|y)$')
}

function Resolve-SubtitleStreamPolicy {
    param(
        [Parameter(Mandatory)] $Stream,
        [int]$SubtitleOrdinal
    )

    $codec       = if ($Stream.codec_name)        { ([string]$Stream.codec_name).ToLowerInvariant() } else { "unknown" }
    $codecTag    = if ($Stream.codec_tag_string)  { ([string]$Stream.codec_tag_string).ToLowerInvariant() } else { "" }
    $isTx3g      = Test-IsTx3gSubtitleStream -Stream $Stream
    $isBdpgs     = Test-IsBdpgsSubtitleStream -Stream $Stream
    $isVobSub    = Test-IsVobSubSubtitleStream -Stream $Stream
    $isAss       = ($codec -in (Get-MediaSubtitleCodecAssNames))
    $rawLang     = if ($Stream.tags.language)     { ([string]$Stream.tags.language).ToLowerInvariant() } else { "" }
    $lang        = Get-NormalizedSubtitleLanguage $rawLang
    $titleLower  = if ($Stream.tags.title)        { ([string]$Stream.tags.title).ToLowerInvariant() } else { "" }
    $rawTitle    = if ($Stream.tags.title)        { [string]$Stream.tags.title } else { "" }
    $isForced    = ($Stream.disposition.forced -eq 1)
    $isDefault   = ($Stream.disposition.default -eq 1)

    $isSdh = Test-SubtitleTitleMatchesAnyKeyword -TitleLower $titleLower -Keywords $SubSDHTitleKeywords
    $isSupplemental = Test-SubtitleTitleMatchesAnyKeyword -TitleLower $titleLower -Keywords $SubSupplementalKeywords
    $treatSupplementalAsForced = $false
    if ($isSupplemental) {
        $switchName = Get-SubtitleSupplementalForcedSwitchName -Codec $codec -IsTx3g:$isTx3g -IsBdpgs:$isBdpgs -IsVobSub:$isVobSub
        if ($switchName) {
            $treatSupplementalAsForced = Get-EffectiveSubtitleSwitch -Name $switchName -Default $false
            if ($treatSupplementalAsForced) { $isForced = $true }
        }
    }

    $languagePolicy = Get-SubtitleLanguagePolicy -IsTx3g:$isTx3g -IsBdpgs:$isBdpgs -IsVobSub:$isVobSub -IsAss:$isAss
    $languagePolicyMatched = ($languagePolicy -contains $lang)
    $langOk = $languagePolicyMatched
    $retainReason = if ($languagePolicyMatched) { 'language_policy' } else { 'language_or_title_policy' }

    $enrichedTitle = New-SubtitleEnrichedTitle -Language $lang -RawTitle $rawTitle -TitleLower $titleLower -IsSdh:$isSdh -IsForced:$isForced -IsSupplemental:$isSupplemental
    return [pscustomobject]@{
        Retain             = [bool]$langOk
        Stream             = $Stream
        Lang               = $lang
        Title              = $enrichedTitle
        RawTitle           = $rawTitle
        Codec              = $codec
        CodecTagString     = $codecTag
        SubtitleOrdinal    = $SubtitleOrdinal
        IsDefault          = $isDefault
        SourceIsDefault    = $isDefault
        IsForced           = $isForced
        LanguagePolicyMatched = [bool]$languagePolicyMatched
        RetainReason       = $retainReason
        IsSdh              = $isSdh
        IsSupplemental     = $isSupplemental
        SupplementalForced = $treatSupplementalAsForced
        IsTx3g             = $isTx3g
        IsBdpgs            = $isBdpgs
        IsVobSub           = $isVobSub
    }
}

function New-SubtitleRoutingDecision {
    param(
        [Parameter(Mandatory)] [ValidateSet('Keep','ConvertAss','ConvertTx3g','ConvertBdpgs','ConvertVobSub','Drop')] [string] $Action,
        [Parameter(Mandatory)] [string] $Message,
        [ValidateSet('DEBUG','WARN')] [string] $Level = 'DEBUG'
    )

    [pscustomobject]@{
        Action  = $Action
        Message = $Message
        Level   = $Level
    }
}

function Set-LastSubtitleDecisionRecords {
    param([array] $Records = @())
    $script:LastSubtitleDecisionRecords = @($Records | Where-Object { $null -ne $_ })
}

function Get-LastSubtitleDecisionRecords {
    return @($script:LastSubtitleDecisionRecords)
}

function Get-SubtitleRoutingTrackId {
    param(
        $Entry = $null,
        [string] $SourceKind = '',
        $SubtitleOrdinal = $null,
        $SourceStreamIndex = $null
    )

    if ($Entry) {
        $existingTrackId = [string](Get-SubtitleRoutingEntryValue -Entry $Entry -Name 'TrackId' -Default '')
        if (-not [string]::IsNullOrWhiteSpace($existingTrackId)) { return $existingTrackId }
        if ([string]::IsNullOrWhiteSpace($SourceKind)) {
            $SourceKind = [string](Get-SubtitleRoutingEntryValue -Entry $Entry -Name 'SourceKind' -Default 'embedded')
        }
        if ($null -eq $SubtitleOrdinal) {
            $SubtitleOrdinal = Get-SubtitleRoutingEntryValue -Entry $Entry -Name 'SubtitleOrdinal' -Default $null
        }
        if ($null -eq $SourceStreamIndex) {
            $stream = Get-SubtitleRoutingEntryValue -Entry $Entry -Name 'Stream' -Default $null
            if ($stream -and $stream.PSObject.Properties['index']) { $SourceStreamIndex = $stream.index }
        }
    }
    if ([string]::IsNullOrWhiteSpace($SourceKind)) { $SourceKind = 'embedded' }
    $SourceKind = $SourceKind.Trim().ToLowerInvariant()
    if ($null -ne $SubtitleOrdinal -and "${SubtitleOrdinal}" -ne '' -and [int]$SubtitleOrdinal -ge 0) {
        return "subtitle:$SourceKind`:$([int]$SubtitleOrdinal)"
    }
    if ($SourceKind -eq 'embedded' -and $null -ne $SourceStreamIndex -and
        "${SourceStreamIndex}" -ne '' -and [int]$SourceStreamIndex -ge 0) {
        return "subtitle:embedded:stream-$([int]$SourceStreamIndex)"
    }
    return ''
}

function New-SubtitleDecisionRecord {
    param(
        [Parameter(Mandatory)] $Entry,
        [Parameter(Mandatory)] $Decision
    )

    $stream = $Entry.Stream
    $sourceKind = if ($Entry.ContainsKey('SourceKind')) { [string]$Entry.SourceKind } else { 'embedded' }
    $subtitleOrdinal = if ($Entry.ContainsKey('SubtitleOrdinal')) { $Entry.SubtitleOrdinal } else { $null }
    $sourceStreamIndex = if ($stream -and $null -ne $stream.PSObject.Properties['index']) { $stream.index } else { $null }
    $trackId = Get-SubtitleRoutingTrackId -Entry $Entry -SourceKind $sourceKind -SubtitleOrdinal $subtitleOrdinal -SourceStreamIndex $sourceStreamIndex
    if (-not [string]::IsNullOrWhiteSpace($trackId)) { $Entry['TrackId'] = $trackId }
    $plannedAction = switch ([string]$Decision.Action) {
        'Keep' { 'preserve_original' }
        'ConvertAss' { 'convert_ass_to_srt' }
        'ConvertTx3g' { 'convert_tx3g_to_srt' }
        'ConvertBdpgs' { 'ocr_bdpgs_to_srt' }
        'ConvertVobSub' { 'ocr_vobsub_to_srt' }
        'Drop' { 'drop' }
        default { ([string]$Decision.Action).Trim().ToLowerInvariant() }
    }
    [pscustomobject]@{
        track_id            = $trackId
        source_stream_index = $sourceStreamIndex
        source_kind         = $sourceKind
        subtitle_ordinal    = $subtitleOrdinal
        action              = ([string]$Decision.Action).ToLowerInvariant()
        planned_action      = $plannedAction
        reason              = [string]$Decision.Message
        language            = [string]$Entry.Lang
        source_codec        = [string]$Entry.Codec
        codec_tag_string    = [string]$Entry.CodecTagString
        title               = [string]$Entry.Title
        raw_title           = [string]$Entry.RawTitle
        is_default          = [bool]$Entry.IsDefault
        source_is_default   = [bool]$Entry.SourceIsDefault
        is_forced           = [bool]$Entry.IsForced
        language_policy_matched = ConvertTo-SubtitleRoutingBool -Value (Get-SubtitleRoutingEntryValue -Entry $Entry -Name 'LanguagePolicyMatched' -Default $true) -Default $true
        retain_reason       = [string](Get-SubtitleRoutingEntryValue -Entry $Entry -Name 'RetainReason' -Default '')
        is_sdh              = [bool]$Entry.IsSdh
        is_supplemental     = [bool]$Entry.IsSupplemental
        is_tx3g             = [bool]$Entry.IsTx3g
        is_bdpgs            = [bool]$Entry.IsBdpgs
        is_vobsub           = [bool]$Entry.IsVobSub
        is_ass              = ([string]$Entry.Codec -in (Get-MediaSubtitleCodecAssNames))
    }
}

function Get-SubtitleRoutingPolicyChain {
    return @(
        {
            param($Entry)
            $languagePolicyMatched = ConvertTo-SubtitleRoutingBool -Value (Get-SubtitleRoutingEntryValue -Entry $Entry -Name 'LanguagePolicyMatched' -Default $true) -Default $true
            if ($languagePolicyMatched) { return $null }

            $stream = Get-SubtitleRoutingEntryValue -Entry $Entry -Name 'Stream' -Default $null
            $streamText = if ($stream -and $null -ne $stream.PSObject.Properties['index']) {
                "stream $($stream.index)"
            } else {
                $sourceKind = [string](Get-SubtitleRoutingEntryValue -Entry $Entry -Name 'SourceKind' -Default 'embedded')
                $idxPath = [string](Get-SubtitleRoutingEntryValue -Entry $Entry -Name 'IdxPath' -Default '')
                if ($sourceKind -eq 'sidecar' -and -not [string]::IsNullOrWhiteSpace($idxPath)) {
                    "sidecar $([System.IO.Path]::GetFileName($idxPath))"
                } else {
                    'subtitle'
                }
            }
            $retainReason = [string](Get-SubtitleRoutingEntryValue -Entry $Entry -Name 'RetainReason' -Default 'language_or_title_policy')
            $language = [string](Get-SubtitleRoutingEntryValue -Entry $Entry -Name 'Lang' -Default '')
            $title = [string](Get-SubtitleRoutingEntryValue -Entry $Entry -Name 'Title' -Default '')
            return New-SubtitleRoutingDecision -Action 'Drop' -Message "DROP subtitle $streamText ($language) '$title': $retainReason outside configured subtitle language policy" -Level 'WARN'
        },
        {
            param($Entry)
            if ($Entry.Codec -in (Get-MediaSubtitleCodecSrtNames)) {
                return New-SubtitleRoutingDecision -Action 'Keep' -Message "KEEP SRT stream $($Entry.Stream.index) ($($Entry.Lang)) '$($Entry.Title)'"
            }
            return $null
        },
        {
            param($Entry)
            if ($Entry.Codec -notin (Get-MediaSubtitleCodecAssNames)) { return $null }
            $effectiveKeepSaS = Get-EffectiveSubtitleSwitch -Name 'KeepSignsAndSongs' -Default $true
            if ([bool]$Entry.IsSupplemental -and $effectiveKeepSaS) {
                return New-SubtitleRoutingDecision -Action 'Keep' -Message "KEEP ASS (supplemental) stream $($Entry.Stream.index) ($($Entry.Lang)) '$($Entry.Title)'"
            }
            if (-not (Get-EffectiveSubtitleSwitch -Name 'ConvertAssToSrt' -Default $true)) {
                return New-SubtitleRoutingDecision -Action 'Keep' -Message "KEEP ASS stream $($Entry.Stream.index) ($($Entry.Lang)) '$($Entry.Title)': ConvertAssToSrt disabled"
            }
            return New-SubtitleRoutingDecision -Action 'ConvertAss' -Message "CONVERT ASS stream $($Entry.Stream.index) ($($Entry.Lang)) '$($Entry.Title)'"
        },
        {
            param($Entry)
            if (-not [bool]$Entry.IsTx3g) { return $null }
            if (Get-EffectiveSubtitleSwitch -Name 'ConvertTx3gToSrt' -Default ([bool]$script:ConvertTx3gToSrt)) {
                return New-SubtitleRoutingDecision -Action 'ConvertTx3g' -Message "CONVERT TX3G stream $($Entry.Stream.index) ($($Entry.Lang)) '$($Entry.Title)'"
            }
            if (Get-EffectiveSubtitleSwitch -Name 'DropTx3gAfterConversion' -Default $false) {
                return New-SubtitleRoutingDecision -Action 'Drop' -Message "DROP TX3G stream $($Entry.Stream.index): ConvertTx3gToSrt disabled and DropTx3gAfterConversion enabled" -Level 'WARN'
            }
            return New-SubtitleRoutingDecision -Action 'Keep' -Message "KEEP TX3G stream $($Entry.Stream.index) ($($Entry.Lang)) '$($Entry.Title)': ConvertTx3gToSrt disabled"
        },
        {
            param($Entry)
            if (-not [bool]$Entry.IsBdpgs) { return $null }
            if (Get-EffectiveSubtitleSwitch -Name 'ConvertBdpgsToSrt' -Default ([bool]$script:ConvertBdpgsToSrt)) {
                return New-SubtitleRoutingDecision -Action 'ConvertBdpgs' -Message "CONVERT BDPGS stream $($Entry.Stream.index) ($($Entry.Lang)) '$($Entry.Title)' via OCR"
            }
            return New-SubtitleRoutingDecision -Action 'Keep' -Message "KEEP BDPGS stream $($Entry.Stream.index) ($($Entry.Lang)) '$($Entry.Title)'"
        },
        {
            param($Entry)
            if (-not [bool]$Entry.IsVobSub) { return $null }
            $sourceText = if ($Entry.ContainsKey('SourceKind') -and [string]$Entry.SourceKind -eq 'sidecar') { "sidecar $([System.IO.Path]::GetFileName([string]$Entry.IdxPath))" } else { "stream $($Entry.Stream.index)" }
            if (Get-EffectiveSubtitleSwitch -Name 'ConvertVobSubToSrt' -Default ([bool]$script:ConvertVobSubToSrt)) {
                return New-SubtitleRoutingDecision -Action 'ConvertVobSub' -Message "CONVERT VobSub $sourceText ($($Entry.Lang)) '$($Entry.Title)' via OCR"
            }
            if ($Entry.ContainsKey('SourceKind') -and [string]$Entry.SourceKind -eq 'sidecar') {
                return New-SubtitleRoutingDecision -Action 'Keep' -Message "REVIEW VobSub $sourceText ($($Entry.Lang)) '$($Entry.Title)': ConvertVobSubToSrt disabled and external IDX/SUB sidecars are not copied into output" -Level 'WARN'
            }
            return New-SubtitleRoutingDecision -Action 'Keep' -Message "KEEP VobSub $sourceText ($($Entry.Lang)) '$($Entry.Title)'"
        },
        {
            param($Entry)
            return New-SubtitleRoutingDecision -Action 'Drop' -Message "DROP stream $($Entry.Stream.index): unsupported codec '$($Entry.Codec)'" -Level 'WARN'
        }
    )
}

function Resolve-SubtitleRoutingDecision {
    param([Parameter(Mandatory)] $Entry)

    foreach ($rule in @(Get-SubtitleRoutingPolicyChain)) {
        $decision = & $rule $Entry
        if ($decision) { return $decision }
    }

    return New-SubtitleRoutingDecision -Action 'Drop' -Message "DROP stream $($Entry.Stream.index): unsupported codec '$($Entry.Codec)'" -Level 'WARN'
}

function Add-SubtitleRoutingDecision {
    param(
        [Parameter(Mandatory)] $Entry,
        [Parameter(Mandatory)] $Decision,
        [Parameter(Mandatory)] $Keep,
        [Parameter(Mandatory)] $Convert,
        [Parameter(Mandatory)] $Tx3gConvert,
        [Parameter(Mandatory)] $BdpgsConvert,
        [Parameter(Mandatory)] $VobSubConvert,
        [Parameter(Mandatory)] $Drop,
        [string] $Context = ''
    )

    Write-Log "${Context}$($Decision.Message)" ([string]$Decision.Level)
    switch ([string]$Decision.Action) {
        'Keep'        { $Keep.Add($Entry); break }
        'ConvertAss'  { $Convert.Add($Entry); break }
        'ConvertTx3g' { $Tx3gConvert.Add($Entry); break }
        'ConvertBdpgs' { $BdpgsConvert.Add($Entry); break }
        'ConvertVobSub' { $VobSubConvert.Add($Entry); break }
        default       { $Drop.Add($Entry); break }
    }
}
