# ==============================================================================
# engine\subtitles\common.ps1
# ==============================================================================
# Common subtitle policy, metadata normalization, config switches, and filter routing.
# Dot-sourced by engine\subtitles\subtitles.ps1; preserves script-scope configuration.
# ==============================================================================

function Get-SubtitleOperationTimeoutSeconds {
    param(
        [Parameter(Mandatory)] [string]$ScriptVariableName,
        [Parameter(Mandatory)] [int]$DefaultSeconds
    )

    $configured = Get-Variable -Name $ScriptVariableName -Scope Script -ErrorAction SilentlyContinue
    if ($configured -and $null -ne $configured.Value) {
        try {
            $seconds = [int]$configured.Value
            if ($seconds -gt 0) { return $seconds }
        } catch {}
    }
    return $DefaultSeconds
}

function ConvertTo-SubtitleBool {
    param(
        $Value,
        [bool]$Default = $false
    )

    if ($null -eq $Value) { return $Default }
    if ($Value -is [bool]) { return [bool]$Value }

    $text = ([string]$Value).Trim()
    if ($text -match '^(?i:true|1|yes|y)$') { return $true }
    if ($text -match '^(?i:false|0|no|n)$') { return $false }
    return $Default
}

function Get-EffectiveSubtitleSwitch {
    param(
        [Parameter(Mandatory)] [string]$Name,
        [bool]$Default = $false
    )

    if ($script:ActiveOverrides -and $script:ActiveOverrides.ContainsKey($Name)) {
        return (ConvertTo-SubtitleBool -Value $script:ActiveOverrides[$Name] -Default $Default)
    }

    $configured = Get-Variable -Name $Name -Scope Script -ErrorAction SilentlyContinue
    if ($configured) {
        return (ConvertTo-SubtitleBool -Value $configured.Value -Default $Default)
    }

    return $Default
}

function Get-ConfiguredOutputContainerName {
    if ($script:ActiveOverrides -and $script:ActiveOverrides.ContainsKey('OutputContainer')) {
        $activeContainer = ([string]$script:ActiveOverrides['OutputContainer']).Trim().TrimStart('.').ToLowerInvariant()
        if (-not [string]::IsNullOrWhiteSpace($activeContainer)) { return $activeContainer }
    }
    $configured = Get-Variable -Name 'OutputContainer' -Scope Script -ErrorAction SilentlyContinue
    if ($configured -and $configured.Value) {
        return ([string]$configured.Value).Trim().TrimStart('.').ToLowerInvariant()
    }
    return Get-MediaContainerMkvExtensionName
}

function Get-ConvertedSrtCodecForFfmpegOutput {
    $container = Get-ConfiguredOutputContainerName
    if ($container -in (Get-MediaContainerMp4FamilyNames)) { return Get-MediaSubtitleCodecMovTextName }
    return 'copy'
}

function Resolve-SubtitleConfiguredPath {
    param(
        [string]$PathValue,
        [switch]$AllowCommandLookup
    )

    $raw = if ($PathValue) { ([string]$PathValue).Trim() } else { '' }
    if ([string]::IsNullOrWhiteSpace($raw)) { return '' }

    if ([System.IO.Path]::IsPathRooted($raw)) {
        try { return [System.IO.Path]::GetFullPath($raw) } catch { return $raw }
    }

    $baseDir = if ($scriptDir) { $scriptDir } elseif ($PSScriptRoot) { Split-Path -Parent $PSScriptRoot } else { (Get-Location).Path }
    $candidate = Join-Path $baseDir $raw
    if (Test-Path -LiteralPath $candidate -ErrorAction SilentlyContinue) {
        return (Resolve-Path -LiteralPath $candidate).Path
    }

    if ($AllowCommandLookup -and $script:AllowSystemTools) {
        $cmd = Get-Command $raw -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($cmd -and $cmd.Source) { return $cmd.Source }
    }

    try { return [System.IO.Path]::GetFullPath($candidate) } catch { return $candidate }
}

function Get-NormalizedSubtitleLanguage {
    param([string]$Language)
    if ([string]::IsNullOrWhiteSpace($Language)) { return 'und' }
    return $Language.Trim().ToLowerInvariant()
}

function Get-SubtitleEntryPropertyValue {
    param(
        $Entry,
        [Parameter(Mandatory)] [string]$Name,
        $Default = $null
    )

    if ($null -eq $Entry) { return $Default }
    if ($Entry -is [System.Collections.IDictionary] -and $Entry.Contains($Name)) {
        return $Entry[$Name]
    }
    try {
        $prop = $Entry.PSObject.Properties[$Name]
        if ($prop) { return $prop.Value }
    } catch {}
    return $Default
}

function Get-SubtitlePreferredDefaultLanguages {
    param(
        [bool]$IsTx3g = $false,
        [bool]$IsBdpgs = $false,
        [bool]$IsAss = $false
    )

    $preferred = [System.Collections.Generic.List[string]]::new()
    foreach ($language in @(Get-SubtitleLanguagePolicy -IsTx3g:$IsTx3g -IsBdpgs:$IsBdpgs -IsAss:$IsAss)) {
        $normalized = Get-NormalizedSubtitleLanguage ([string]$language)
        if ($normalized -eq 'und') { continue }
        if (-not $preferred.Contains($normalized)) {
            $preferred.Add($normalized)
        }
    }
    return @($preferred)
}

function Test-SubtitleLanguageIsPreferredDefault {
    param(
        [string]$Language,
        [bool]$IsTx3g = $false,
        [bool]$IsBdpgs = $false,
        [bool]$IsAss = $false
    )

    $normalized = Get-NormalizedSubtitleLanguage $Language
    return (@(Get-SubtitlePreferredDefaultLanguages -IsTx3g:$IsTx3g -IsBdpgs:$IsBdpgs -IsAss:$IsAss) -contains $normalized)
}

function Test-SubtitleLanguageIsFallbackDefault {
    param([string]$Language)

    if ([string]::IsNullOrWhiteSpace($Language)) { return $true }
    return ((Get-NormalizedSubtitleLanguage $Language) -eq 'und')
}

function Test-SubtitleEntryLanguageIsPreferredDefault {
    param($Entry)

    $codec = [string](Get-SubtitleEntryPropertyValue -Entry $Entry -Name 'Codec' -Default '')
    return (Test-SubtitleLanguageIsPreferredDefault `
        -Language ([string](Get-SubtitleEntryPropertyValue -Entry $Entry -Name 'Lang' -Default '')) `
        -IsTx3g:([bool](Get-SubtitleEntryPropertyValue -Entry $Entry -Name 'IsTx3g' -Default $false)) `
        -IsBdpgs:([bool](Get-SubtitleEntryPropertyValue -Entry $Entry -Name 'IsBdpgs' -Default $false)) `
        -IsAss:($codec -in (Get-MediaSubtitleCodecAssNames)))
}

function Test-SubtitleEntryLanguageIsFallbackDefault {
    param($Entry)

    return (Test-SubtitleLanguageIsFallbackDefault -Language ([string](Get-SubtitleEntryPropertyValue -Entry $Entry -Name 'Lang' -Default '')))
}

function Get-SafeSubtitleFileToken {
    param(
        [string]$Value,
        [int]$MaxLength = 40
    )

    if ([string]::IsNullOrWhiteSpace($Value)) { return "" }
    $token = $Value.ToLowerInvariant()
    $token = $token -replace '\[[^\]]+\]', ' '
    $token = $token -replace '[^a-z0-9]+', '-'
    $token = $token.Trim('-')
    if ($token.Length -gt $MaxLength) {
        $token = $token.Substring(0, $MaxLength).Trim('-')
    }
    return $token
}

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

function Write-SubtitleTrackProgress {
    param(
        [string]$Kind,
        [int]$StreamIndex = -1,
        [string]$Stage,
        [string]$Status,
        [int]$StepIndex = 0,
        [int]$StepTotal = 4,
        [array]$Steps = @('extract','convert_ocr','validate','sidecar_write'),
        [string]$Detail = "",
        [object]$CueCount = $null,
        [switch]$Completed,
        [switch]$Failed
    )

    if (Get-Command -Name Set-ProgressSubtitleTrack -ErrorAction SilentlyContinue) {
        Set-ProgressSubtitleTrack `
            -Kind $Kind `
            -StreamIndex $StreamIndex `
            -Stage $Stage `
            -Status $Status `
            -StepIndex $StepIndex `
            -StepTotal $StepTotal `
            -Steps $Steps `
            -Detail $Detail `
            -CueCount $CueCount `
            -Completed:$Completed `
            -Failed:$Failed `
            -SaveNow
    }
}

function Write-SubtitleSidecarProgress {
    param(
        [string]$Status = 'Writing subtitle sidecar evidence',
        [string]$Detail = "",
        [switch]$Completed,
        [switch]$Failed
    )

    if (Get-Command -Name Set-ProgressSubtitleSidecarWrite -ErrorAction SilentlyContinue) {
        Set-ProgressSubtitleSidecarWrite `
            -Status $Status `
            -Detail $Detail `
            -Completed:$Completed `
            -Failed:$Failed `
            -SaveNow
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
    $null = Register-SourceFailure -SourceFile $SourceFile -ScratchPath $ScratchPath -Classification 'transient' -Reason $reason -Stage $Stage -ErrorCode $errorCode -ReproPath $reproPath -SuggestedAction $suggestedAction
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
        $null = Register-SourceFailure -SourceFile $SourceFile -ScratchPath $ScratchPath -Classification 'transient' -Reason $reason -Stage $Stage -ErrorCode $errorCode -ReproPath $reproPath -SuggestedAction $suggestedAction
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
        $null = Register-SourceFailure -SourceFile $SourceFile -ScratchPath $ScratchPath -Classification 'transient' -Reason $reason -Stage $Stage -ErrorCode $errorCode -ReproPath $reproPath -SuggestedAction $suggestedAction
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
    $null = Register-SourceFailure -SourceFile $SourceFile -ScratchPath $ScratchPath -Classification 'transient' -Reason $reasonFallback -Stage $Stage -ErrorCode $errorCodeFallback -ReproPath $reproPathFallback -SuggestedAction 'Review the pipeline log around the subtitle conversion step and retry after correcting the source subtitle issue.'
}

function Get-SubtitleLanguageDisplayMap {
    # Same language map as Build-AudioArgs so subtitle titles read consistently.
    return @{
        'eng' = 'English';    'en'  = 'English'
        'jpn' = 'Japanese';   'ja'  = 'Japanese'
        'spa' = 'Spanish';    'es'  = 'Spanish'
        'fre' = 'French';     'fra' = 'French';   'fr' = 'French'
        'ger' = 'German';     'deu' = 'German';   'de' = 'German'
        'ita' = 'Italian';    'it'  = 'Italian'
        'por' = 'Portuguese'; 'pt'  = 'Portuguese'
        'rus' = 'Russian';    'ru'  = 'Russian'
        'chi' = 'Chinese';    'zho' = 'Chinese';  'zh' = 'Chinese'
        'kor' = 'Korean';     'ko'  = 'Korean'
        'hin' = 'Hindi';      'hi'  = 'Hindi'
        'ara' = 'Arabic';     'ar'  = 'Arabic'
        'und' = 'Undefined';  ''    = 'Undefined'
    }
}

function Test-SubtitleTitleMatchesAnyKeyword {
    param(
        [string]$TitleLower,
        $Keywords
    )

    if ([string]::IsNullOrWhiteSpace($TitleLower) -or -not $Keywords) { return $false }
    foreach ($kw in @($Keywords)) {
        if ([string]::IsNullOrWhiteSpace([string]$kw)) { continue }
        if ($TitleLower -like "*$kw*") { return $true }
    }
    return $false
}

function Get-SubtitleLanguagePolicy {
    param(
        [bool]$IsTx3g = $false,
        [bool]$IsBdpgs = $false,
        [bool]$IsAss = $false
    )

    if ($IsTx3g -and $script:ActiveOverrides -and $script:ActiveOverrides.ContainsKey('Tx3gExtractLanguages') -and @($script:ActiveOverrides['Tx3gExtractLanguages']).Count -gt 0) {
        return @($script:ActiveOverrides['Tx3gExtractLanguages'])
    }
    if ($IsBdpgs -and $script:ActiveOverrides -and $script:ActiveOverrides.ContainsKey('BdpgsExtractLanguages') -and @($script:ActiveOverrides['BdpgsExtractLanguages']).Count -gt 0) {
        return @($script:ActiveOverrides['BdpgsExtractLanguages'])
    }
    if ($IsAss -and $script:ActiveOverrides -and $script:ActiveOverrides.ContainsKey('AssKeepLanguages') -and @($script:ActiveOverrides['AssKeepLanguages']).Count -gt 0) {
        return @($script:ActiveOverrides['AssKeepLanguages'])
    }

    if ($IsTx3g -and $script:Tx3gExtractLanguages -and $script:Tx3gExtractLanguages.Count -gt 0) {
        return @($script:Tx3gExtractLanguages)
    }
    if ($IsBdpgs -and $script:BdpgsExtractLanguages -and $script:BdpgsExtractLanguages.Count -gt 0) {
        return @($script:BdpgsExtractLanguages)
    }
    return @($SubKeepLanguages)
}

function Get-SubtitleSupplementalForcedSwitchName {
    param(
        [string]$Codec,
        [bool]$IsTx3g,
        [bool]$IsBdpgs
    )

    if ($IsTx3g) { return 'TreatTx3gSignsSongsAsForced' }
    if ($IsBdpgs) { return 'TreatBdpgsSignsSongsAsForced' }
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

function Resolve-SubtitleStreamPolicy {
    param(
        [Parameter(Mandatory)] $Stream,
        [int]$SubtitleOrdinal
    )

    $codec       = if ($Stream.codec_name)        { ([string]$Stream.codec_name).ToLowerInvariant() } else { "unknown" }
    $codecTag    = if ($Stream.codec_tag_string)  { ([string]$Stream.codec_tag_string).ToLowerInvariant() } else { "" }
    $isTx3g      = Test-IsTx3gSubtitleStream -Stream $Stream
    $isBdpgs     = Test-IsBdpgsSubtitleStream -Stream $Stream
    $rawLang     = if ($Stream.tags.language)     { ([string]$Stream.tags.language).ToLowerInvariant() } else { "" }
    $lang        = if ($isTx3g -or $isBdpgs) { Get-NormalizedSubtitleLanguage $rawLang } else { $rawLang }
    $titleLower  = if ($Stream.tags.title)        { ([string]$Stream.tags.title).ToLowerInvariant() } else { "" }
    $rawTitle    = if ($Stream.tags.title)        { [string]$Stream.tags.title } else { "" }
    $isForced    = ($Stream.disposition.forced -eq 1)
    $isDefault   = ($Stream.disposition.default -eq 1)

    $isSdh = Test-SubtitleTitleMatchesAnyKeyword -TitleLower $titleLower -Keywords $SubSDHTitleKeywords
    $isSupplemental = Test-SubtitleTitleMatchesAnyKeyword -TitleLower $titleLower -Keywords $SubSupplementalKeywords
    $treatSupplementalAsForced = $false
    if ($isSupplemental) {
        $switchName = Get-SubtitleSupplementalForcedSwitchName -Codec $codec -IsTx3g:$isTx3g -IsBdpgs:$isBdpgs
        if ($switchName) {
            $treatSupplementalAsForced = Get-EffectiveSubtitleSwitch -Name $switchName -Default $false
            if ($treatSupplementalAsForced) { $isForced = $true }
        }
    }

    $languagePolicy = Get-SubtitleLanguagePolicy -IsTx3g:$isTx3g -IsBdpgs:$isBdpgs -IsAss:($codec -in (Get-MediaSubtitleCodecAssNames))
    $langOk = ($languagePolicy -contains $lang)
    if ($isSdh -and -not $langOk) { $langOk = $true }
    if ($isForced -and -not $langOk) { $langOk = $true }

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
        IsSdh              = $isSdh
        IsSupplemental     = $isSupplemental
        SupplementalForced = $treatSupplementalAsForced
        IsTx3g             = $isTx3g
        IsBdpgs            = $isBdpgs
    }
}

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
        IsSdh              = $Policy.IsSdh
        IsSupplemental     = $Policy.IsSupplemental
        SupplementalForced = $Policy.SupplementalForced
        IsTx3g             = $Policy.IsTx3g
        IsBdpgs            = $Policy.IsBdpgs
    }
}

function New-SubtitleRoutingDecision {
    param(
        [Parameter(Mandatory)] [ValidateSet('Keep','ConvertAss','ConvertTx3g','ConvertBdpgs','Drop')] [string] $Action,
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

function New-SubtitleDecisionRecord {
    param(
        [Parameter(Mandatory)] $Entry,
        [Parameter(Mandatory)] $Decision
    )

    $stream = $Entry.Stream
    [pscustomobject]@{
        source_stream_index = if ($stream -and $null -ne $stream.PSObject.Properties['index']) { $stream.index } else { $null }
        subtitle_ordinal    = if ($Entry.ContainsKey('SubtitleOrdinal')) { $Entry.SubtitleOrdinal } else { $null }
        action              = ([string]$Decision.Action).ToLowerInvariant()
        reason              = [string]$Decision.Message
        language            = [string]$Entry.Lang
        source_codec        = [string]$Entry.Codec
        codec_tag_string    = [string]$Entry.CodecTagString
        title               = [string]$Entry.Title
        raw_title           = [string]$Entry.RawTitle
        is_default          = [bool]$Entry.IsDefault
        source_is_default   = [bool]$Entry.SourceIsDefault
        is_forced           = [bool]$Entry.IsForced
        is_sdh              = [bool]$Entry.IsSdh
        is_supplemental     = [bool]$Entry.IsSupplemental
        is_tx3g             = [bool]$Entry.IsTx3g
        is_bdpgs            = [bool]$Entry.IsBdpgs
        is_ass              = ([string]$Entry.Codec -in (Get-MediaSubtitleCodecAssNames))
    }
}

function Get-SubtitleRoutingPolicyChain {
    return @(
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
        [Parameter(Mandatory)] $Drop,
        [string] $Context = ''
    )

    Write-Log "${Context}$($Decision.Message)" ([string]$Decision.Level)
    switch ([string]$Decision.Action) {
        'Keep'        { $Keep.Add($Entry); break }
        'ConvertAss'  { $Convert.Add($Entry); break }
        'ConvertTx3g' { $Tx3gConvert.Add($Entry); break }
        'ConvertBdpgs' { $BdpgsConvert.Add($Entry); break }
        default       { $Drop.Add($Entry); break }
    }
}

function Filter-SubtitleStreams {
    param([string]$FilePath, [string]$Context = "")
    Set-LastSubtitleDecisionRecords @()
    $keep        = [System.Collections.Generic.List[hashtable]]::new()
    $convert     = [System.Collections.Generic.List[hashtable]]::new()
    $tx3gConvert = [System.Collections.Generic.List[hashtable]]::new()
    $bdpgsConvert = [System.Collections.Generic.List[hashtable]]::new()
    $drop        = [System.Collections.Generic.List[hashtable]]::new()
    $decisions   = [System.Collections.Generic.List[object]]::new()

    $probeTimeoutSeconds = Get-SubtitleOperationTimeoutSeconds -ScriptVariableName 'SubtitleProbeTimeoutSeconds' -DefaultSeconds 30
    $r = Invoke-FFprobeCommand -ArgumentList @(
        "-v","error","-select_streams","s",
        "-show_entries","stream=index,codec_name,codec_long_name,codec_tag_string,codec_tag,disposition:stream_tags=language,title",
        "-of","json","--",$FilePath
    ) -TimeoutSeconds $probeTimeoutSeconds -Stage 'subtitle-stream-probe'
    if ($r.ExitCode -ne 0) {
        $reason = "${Context}Subtitle probe failed with exit $($r.ExitCode)"
        if ($r.Error) { $reason = "$reason`: $($r.Error)" }
        Write-Log $reason "ERROR"
        return @{ Ok=$false; ProbeFailed=$true; ErrorCode='SUBTITLE_PROBE_FAILED'; Reason=$reason; Keep=@($keep); Convert=@($convert); Tx3gConvert=@($tx3gConvert); BdpgsConvert=@($bdpgsConvert); Drop=@($drop); Decisions=@($decisions) }
    }
    try { $probe = $r.Output | ConvertFrom-Json } catch {
        $reason = "${Context}Subtitle probe returned invalid JSON: $($_.Exception.Message)"
        Write-Log $reason "ERROR"
        return @{ Ok=$false; ProbeFailed=$true; ErrorCode='SUBTITLE_PROBE_JSON_INVALID'; Reason=$reason; Keep=@($keep); Convert=@($convert); Tx3gConvert=@($tx3gConvert); BdpgsConvert=@($bdpgsConvert); Drop=@($drop); Decisions=@($decisions) }
    }
    if (-not $probe.streams -or $probe.streams.Count -eq 0) {
        Set-LastSubtitleDecisionRecords @($decisions)
        return @{ Ok=$true; ProbeFailed=$false; ErrorCode=''; Reason=''; Keep=@($keep); Convert=@($convert); Tx3gConvert=@($tx3gConvert); BdpgsConvert=@($bdpgsConvert); Drop=@($drop); Decisions=@($decisions) }
    }

    # Per-file override: resolve subtitle track filter + rename rules once before the loop.
    $subtitleOverride = Get-FileOverrideSubtitleSettings

    $subtitleOrdinal = 0
    foreach ($s in $probe.streams) {
        $policy = Resolve-SubtitleStreamPolicy -Stream $s -SubtitleOrdinal $subtitleOrdinal
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
                is_ass              = ([string]$policy.Codec -in (Get-MediaSubtitleCodecAssNames))
            }) | Out-Null
            continue
        }

        # Per-file override: subtitle track filter (runs only on tracks that passed language/title policy).
        if (-not (Test-SubtitleTrackKeptByOverride -Language $policy.Lang -IsForced:([bool]$policy.IsForced) -Title $policy.RawTitle -SubtitleOverride $subtitleOverride)) {
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
            -Drop $drop `
            -Context $Context
        $decisions.Add((New-SubtitleDecisionRecord -Entry $entry -Decision $routingDecision)) | Out-Null
    }
    Write-Log "${Context}Subtitles: $($keep.Count) keep-as-is, $($convert.Count) ASS->SRT, $($tx3gConvert.Count) TX3G->SRT, $($bdpgsConvert.Count) BDPGS->SRT, $($drop.Count) dropped"
    Set-LastSubtitleDecisionRecords @($decisions)
    return @{ Ok=$true; ProbeFailed=$false; ErrorCode=''; Reason=''; Keep=@($keep); Convert=@($convert); Tx3gConvert=@($tx3gConvert); BdpgsConvert=@($bdpgsConvert); Drop=@($drop); Decisions=@($decisions) }
}
