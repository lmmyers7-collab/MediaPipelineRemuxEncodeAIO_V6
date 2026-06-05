# ==============================================================================
# ops\pipeline\engine\subtitles\language_policy.ps1
# ==============================================================================
# Extracted from ops\pipeline\engine\subtitles\common.ps1. Keep function names stable;
# common.ps1 dot-sources this file as part of the subtitle policy surface.
# ==============================================================================

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
        [bool]$IsVobSub = $false,
        [bool]$IsAss = $false
    )

    $preferred = [System.Collections.Generic.List[string]]::new()
    foreach ($language in @(Get-SubtitleLanguagePolicy -IsTx3g:$IsTx3g -IsBdpgs:$IsBdpgs -IsVobSub:$IsVobSub -IsAss:$IsAss)) {
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
        [bool]$IsVobSub = $false,
        [bool]$IsAss = $false
    )

    $normalized = Get-NormalizedSubtitleLanguage $Language
    return (@(Get-SubtitlePreferredDefaultLanguages -IsTx3g:$IsTx3g -IsBdpgs:$IsBdpgs -IsVobSub:$IsVobSub -IsAss:$IsAss) -contains $normalized)
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
        -IsVobSub:([bool](Get-SubtitleEntryPropertyValue -Entry $Entry -Name 'IsVobSub' -Default $false)) `
        -IsAss:($codec -in (Get-MediaSubtitleCodecAssNames)))
}

function Test-SubtitleEntryLanguageIsFallbackDefault {
    param($Entry)

    return (Test-SubtitleLanguageIsFallbackDefault -Language ([string](Get-SubtitleEntryPropertyValue -Entry $Entry -Name 'Lang' -Default '')))
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
        [bool]$IsVobSub = $false,
        [bool]$IsAss = $false
    )

    if ($IsTx3g -and $script:ActiveOverrides -and $script:ActiveOverrides.ContainsKey('Tx3gExtractLanguages') -and @($script:ActiveOverrides['Tx3gExtractLanguages']).Count -gt 0) {
        return @($script:ActiveOverrides['Tx3gExtractLanguages'])
    }
    if ($IsBdpgs -and $script:ActiveOverrides -and $script:ActiveOverrides.ContainsKey('BdpgsExtractLanguages') -and @($script:ActiveOverrides['BdpgsExtractLanguages']).Count -gt 0) {
        return @($script:ActiveOverrides['BdpgsExtractLanguages'])
    }
    if ($IsVobSub -and $script:ActiveOverrides -and $script:ActiveOverrides.ContainsKey('VobSubExtractLanguages') -and @($script:ActiveOverrides['VobSubExtractLanguages']).Count -gt 0) {
        return @($script:ActiveOverrides['VobSubExtractLanguages'])
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
    if ($IsVobSub -and $script:VobSubExtractLanguages -and $script:VobSubExtractLanguages.Count -gt 0) {
        return @($script:VobSubExtractLanguages)
    }
    return @($SubKeepLanguages)
}

