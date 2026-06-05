# ==============================================================================
# ops\pipeline\engine\queue\file_overrides.ps1
# ==============================================================================
# Per-file (and per-folder) à-la-carte processing overrides.
#
# Reads file_overrides.json from the pipeline state root and resolves the
# effective override object for any source path at processing time.
#
# Dot-sourced from MediaPipeline.ps1. Reads at call time:
#   $script:LocalStateLayout  (used for file_overrides.json path)
#
# Cross-module helpers (loaded before this module):
#   Write-Log
#
# Functions exported:
#   Get-FileOverridesManifest
#   Resolve-FileOverride
#   ConvertTo-MediaPipelineFileOverrideConfigMap
#   Get-FileOverrideAudioSettings
#   Get-FileOverrideSubtitleSettings
#   Test-AudioTrackKeptByOverride
#   Test-SubtitleTrackKeptByOverride
#   Get-AudioTrackTitleOverride
#   Get-SubtitleTrackTitleOverride
#   Merge-FileOverrideIntoActiveOverrides
# ==============================================================================

# Cached manifest — re-loaded per pipeline round; reset to $null at start of round.
$script:CachedFileOverridesManifest = $null

function Normalize-MediaPipelineFileOverrideLanguage {
    param([string] $Value)

    $normalized = if ($Value) { $Value.Trim().ToLowerInvariant() } else { '' }
    switch -Regex ($normalized) {
        '^(|und|unknown|undefined)$' { return 'und' }
        '^(eng|en|english)$'         { return 'eng' }
        '^(jpn|ja|japanese)$'        { return 'jpn' }
        '^(spa|es|spanish)$'         { return 'spa' }
        '^(fre|fra|fr|french)$'      { return 'fra' }
        '^(ger|deu|de|german)$'      { return 'deu' }
        '^(ita|it|italian)$'         { return 'ita' }
        '^(por|pt|portuguese)$'      { return 'por' }
        '^(rus|ru|russian)$'         { return 'rus' }
        '^(kor|ko|korean)$'          { return 'kor' }
        '^(chi|zho|zh|chinese)$'     { return 'zho' }
        default                      { return $normalized }
    }
}

function ConvertTo-MediaPipelineFileOverrideSafeScalar {
    param(
        [Parameter(Mandatory)] [string] $FieldPath,
        $Value,
        [Parameter(Mandatory)] [string[]] $AllowedValues
    )

    if ($null -eq $Value) { return $null }
    $text = ([string]$Value).Trim()
    if ([string]::IsNullOrWhiteSpace($text)) { return $null }
    if ($text -notmatch '^[A-Za-z0-9_.-]+$') {
        throw "Invalid file override value for '$FieldPath': unsupported characters."
    }

    $normalized = $text.ToLowerInvariant()
    $allowed = @($AllowedValues | ForEach-Object { ([string]$_).Trim().ToLowerInvariant() } | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    if ($allowed -notcontains $normalized) {
        throw "Invalid file override value for '$FieldPath': '$text'. Allowed values: $($allowed -join ', ')."
    }
    return $normalized
}

function Get-MediaPipelineFileOverrideAllowedValues {
    param([Parameter(Mandatory)] [string] $FieldPath)

    switch ($FieldPath) {
        'routing.profile' {
            $profiles = if (Get-Command -Name Get-MediaPipelineRoutingProfileNames -ErrorAction SilentlyContinue) {
                @(Get-MediaPipelineRoutingProfileNames)
            } else {
                @('plex_direct_stream','plex_direct_play','archive_shrink','archive_quality','manual')
            }
            return @('auto','encode','transcode','remux') + @($profiles)
        }
        'routing.routeThresholdMode' {
            if (Get-Command -Name Get-MediaPipelineRouteThresholdModeNames -ErrorAction SilentlyContinue) {
                return @(Get-MediaPipelineRouteThresholdModeNames)
            }
            return @('compatibility_advisory','size','bitrate','size_or_bitrate')
        }
        'video.codec' {
            if (Get-Command -Name Get-MediaPipelineVideoCodecNames -ErrorAction SilentlyContinue) {
                return @(Get-MediaPipelineVideoCodecNames)
            }
            return @('hevc_nvenc','libx265','h264_nvenc','libx264','av1_nvenc')
        }
        'video.container' {
            if (Get-Command -Name Get-MediaPipelineOutputContainerNames -ErrorAction SilentlyContinue) {
                return @(Get-MediaPipelineOutputContainerNames)
            }
            return @('mkv','mp4')
        }
        'video.encodePreset' {
            if (Get-Command -Name Get-MediaPipelineEncodeTuningPresetNames -ErrorAction SilentlyContinue) {
                return @(Get-MediaPipelineEncodeTuningPresetNames)
            }
            return @('balanced_nvenc','quality_nvenc','fast_nvenc','compatibility','custom_legacy_flags')
        }
        'video.encodeLadder' {
            if (Get-Command -Name Get-MediaPipelineEncodeLadderNames -ErrorAction SilentlyContinue) {
                return @(Get-MediaPipelineEncodeLadderNames)
            }
            return @('auto','tv_balanced','tv_space_saver','movie_balanced','movie_archive','plex_compat')
        }
    }
    return @()
}

function Get-MediaPipelineFileOverrideProperty {
    param(
        $Object,
        [Parameter(Mandatory)] [string] $Name
    )

    if ($null -eq $Object) { return $null }
    if ($Object -is [System.Collections.IDictionary] -and $Object.Contains($Name)) {
        return $Object[$Name]
    }
    try {
        $prop = $Object.PSObject.Properties[$Name]
        if ($prop) { return $prop.Value }
    } catch {}
    return $null
}

function Get-MediaPipelineFileOverrideRouteVideoFieldPaths {
    param($Override)

    $paths = [System.Collections.Generic.List[string]]::new()
    $routing = Get-MediaPipelineFileOverrideProperty -Object $Override -Name 'routing'
    if ($routing) {
        foreach ($key in @('profile','routeThresholdMode')) {
            if ($null -ne (Get-MediaPipelineFileOverrideProperty -Object $routing -Name $key)) {
                $paths.Add("routing.$key")
            }
        }
    }
    $video = Get-MediaPipelineFileOverrideProperty -Object $Override -Name 'video'
    if ($video) {
        foreach ($key in @('codec','container','encodePreset','encodeLadder')) {
            if ($null -ne (Get-MediaPipelineFileOverrideProperty -Object $video -Name $key)) {
                $paths.Add("video.$key")
            }
        }
    }
    $subtitles = Get-MediaPipelineFileOverrideProperty -Object $Override -Name 'subtitles'
    if ($subtitles) {
        if ($null -ne (Get-MediaPipelineFileOverrideProperty -Object $subtitles -Name 'burnTrack')) {
            $paths.Add('subtitles.burnTrack')
        }
    }
    return @($paths.ToArray())
}

function Get-FileOverrideSubtitleBurnTrack {
    param($SubtitleOverride)

    if ($null -eq $SubtitleOverride) { return $null }
    $burnTrack = Get-MediaPipelineFileOverrideProperty -Object $SubtitleOverride -Name 'burnTrack'
    if ($null -eq $burnTrack) { return $null }
    return $burnTrack
}

function Get-FileOverridesManifest {
    <#
    .SYNOPSIS
        Load file_overrides.json from the state root.
        Returns an empty manifest hashtable on any error.
    .DESCRIPTION
        The manifest is loaded once per use; the caller is responsible for
        clearing $script:CachedFileOverridesManifest between pipeline rounds
        if the file may have been updated.
    #>
    if ($null -ne $script:CachedFileOverridesManifest) {
        return $script:CachedFileOverridesManifest
    }

    $manifestPath = $null
    try {
        if ($script:LocalStateLayout -and $script:LocalStateLayout.Paths) {
            $p = $script:LocalStateLayout.Paths
            if ($p.PSObject.Properties['FileOverrides']) {
                $manifestPath = [string]$p.FileOverrides
            }
        }
    } catch {}

    $empty = @{ version = 1; entries = @{} }

    if ([string]::IsNullOrWhiteSpace($manifestPath) -or -not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
        $script:CachedFileOverridesManifest = $empty
        return $empty
    }

    try {
        $text = [System.IO.File]::ReadAllText($manifestPath, [System.Text.Encoding]::UTF8)
        $obj  = $text | ConvertFrom-Json
        if (-not $obj -or $obj.version -ne 1 -or -not $obj.entries) {
            $script:CachedFileOverridesManifest = $empty
            return $empty
        }
        # Convert PSObject entries to a plain hashtable for fast lookup
        $ht = @{}
        foreach ($prop in $obj.entries.PSObject.Properties) {
            $ht[$prop.Name] = $prop.Value
        }
        $result = @{ version = 1; entries = $ht }
        $script:CachedFileOverridesManifest = $result
        return $result
    } catch {
        Write-Log "Get-FileOverridesManifest: failed to read manifest: $_" "WARN"
        $script:CachedFileOverridesManifest = $empty
        return $empty
    }
}

function Resolve-FileOverride {
    <#
    .SYNOPSIS
        Return the effective override object for a source path.
    .DESCRIPTION
        Resolution order (first match wins):
          1. Exact file-level entry
          2. Deepest ancestor folder entry
          3. $null — no override
    .PARAMETER SourcePath
        The full source file path (string).
    .OUTPUTS
        PSObject | $null
    #>
    param([string]$SourcePath)

    $match = Resolve-FileOverrideMatch -SourcePath $SourcePath
    if ($match) { return $match.Entry }
    return $null
}

function Resolve-FileOverrideMatch {
    param([string]$SourcePath)

    $manifest = Get-FileOverridesManifest
    if ($null -eq $manifest -or $manifest.entries.Count -eq 0) { return $null }

    $norm    = $SourcePath.Replace('\', '/').ToLowerInvariant().TrimEnd('/')
    $entries = $manifest.entries

    if ($entries.ContainsKey($norm)) {
        return [pscustomobject]@{
            Entry       = $entries[$norm]
            MatchedPath = $norm
            Scope       = 'file'
            IsExact     = $true
        }
    }

    $bestLen   = -1
    $bestKey   = ''
    $bestEntry = $null
    foreach ($key in $entries.Keys) {
        if ($norm.StartsWith($key + '/', [System.StringComparison]::OrdinalIgnoreCase) -and $key.Length -gt $bestLen) {
            $bestLen   = $key.Length
            $bestKey   = [string]$key
            $bestEntry = $entries[$key]
        }
    }
    if ($null -eq $bestEntry) { return $null }
    return [pscustomobject]@{
        Entry       = $bestEntry
        MatchedPath = $bestKey
        Scope       = 'folder'
        IsExact     = $false
    }
}

function ConvertTo-MediaPipelineFileOverrideConfigMap {
    param($Override)

    $configMap = [ordered]@{}
    if ($null -eq $Override) { return $configMap }

    $audioFieldMap = [ordered]@{
        maxChannels           = 'AudioMaxChannels'
        downmixMode           = 'AudioDownmixMode'
        transcodeCodec        = 'AudioTranscodeCodec'
        transcodeBitrate      = 'AudioTranscodeBitrate'
        preferDefaultLanguage = 'PreferredDefaultAudioLanguages'
    }
    try {
        $audioProp = $Override.PSObject.Properties['audio']
        if ($audioProp -and $audioProp.Value) {
            $audio = $audioProp.Value
            foreach ($srcKey in $audioFieldMap.Keys) {
                $destKey = $audioFieldMap[$srcKey]
                $vProp = $audio.PSObject.Properties[$srcKey]
                if ($vProp -and $null -ne $vProp.Value) {
                    if ($srcKey -eq 'preferDefaultLanguage') {
                        $configMap[$destKey] = @([string]$vProp.Value)
                    } else {
                        $configMap[$destKey] = $vProp.Value
                    }
                }
            }
        }
    } catch {}

    $routing = Get-MediaPipelineFileOverrideProperty -Object $Override -Name 'routing'
    if ($routing) {
        $profileRaw = Get-MediaPipelineFileOverrideProperty -Object $routing -Name 'profile'
        $profile = if ($null -ne $profileRaw) {
            ConvertTo-MediaPipelineFileOverrideSafeScalar `
                -FieldPath 'routing.profile' `
                -Value $profileRaw `
                -AllowedValues (Get-MediaPipelineFileOverrideAllowedValues -FieldPath 'routing.profile')
        } else {
            $null
        }
        if (-not [string]::IsNullOrWhiteSpace($profile)) {
            switch ($profile) {
                'encode' {
                    $configMap['RouteForce'] = 'encode'
                    $configMap['RoutePolicyReason'] = 'file override routing.profile=encode'
                }
                'transcode' {
                    $configMap['RouteForce'] = 'encode'
                    $configMap['RoutePolicyReason'] = 'file override routing.profile=transcode'
                }
                'remux' {
                    $configMap['RouteForce'] = 'remux'
                    $configMap['RoutePolicyReason'] = 'file override routing.profile=remux'
                }
                'auto' {
                    $configMap['RouteForce'] = 'auto'
                    $configMap['RoutePolicyReason'] = 'file override routing.profile=auto'
                }
                default {
                    $configMap['RoutingProfile'] = $profile
                }
            }
        }

        $thresholdRaw = Get-MediaPipelineFileOverrideProperty -Object $routing -Name 'routeThresholdMode'
        if ($null -ne $thresholdRaw) {
            $configMap['RouteThresholdMode'] = ConvertTo-MediaPipelineFileOverrideSafeScalar `
                -FieldPath 'routing.routeThresholdMode' `
                -Value $thresholdRaw `
                -AllowedValues (Get-MediaPipelineFileOverrideAllowedValues -FieldPath 'routing.routeThresholdMode')
        }
    }

    $videoRequiresEncode = $false
    $video = Get-MediaPipelineFileOverrideProperty -Object $Override -Name 'video'
    if ($video) {
        $videoFieldMap = [ordered]@{
            codec        = @{ FieldPath = 'video.codec'; DestKey = 'VideoCodec' }
            container    = @{ FieldPath = 'video.container'; DestKey = 'OutputContainer' }
            encodePreset = @{ FieldPath = 'video.encodePreset'; DestKey = 'EncodeTuningPreset' }
            encodeLadder = @{ FieldPath = 'video.encodeLadder'; DestKey = 'EncodeLadder' }
        }
        foreach ($srcKey in $videoFieldMap.Keys) {
            $rawValue = Get-MediaPipelineFileOverrideProperty -Object $video -Name $srcKey
            if ($null -eq $rawValue) { continue }
            $spec = $videoFieldMap[$srcKey]
            $configMap[[string]$spec.DestKey] = ConvertTo-MediaPipelineFileOverrideSafeScalar `
                -FieldPath ([string]$spec.FieldPath) `
                -Value $rawValue `
                -AllowedValues (Get-MediaPipelineFileOverrideAllowedValues -FieldPath ([string]$spec.FieldPath))
            if ($srcKey -in @('codec','encodePreset','encodeLadder')) {
                $videoRequiresEncode = $true
            }
        }
        if ($configMap.Contains('OutputContainer')) {
            $mp4Family = if (Get-Command -Name Get-MediaContainerMp4FamilyNames -ErrorAction SilentlyContinue) {
                @(Get-MediaContainerMp4FamilyNames)
            } else {
                @('mp4','m4v','mov')
            }
            if (@($mp4Family | ForEach-Object { ([string]$_).ToLowerInvariant() }) -contains ([string]$configMap['OutputContainer'])) {
                $videoRequiresEncode = $true
            }
        }
    }
    if ($videoRequiresEncode) {
        if ($configMap.Contains('RouteForce') -and [string]$configMap['RouteForce'] -eq 'remux') {
            throw "Invalid file override combination: routing.profile=remux cannot be combined with video encode/container override fields."
        }
        if (-not $configMap.Contains('RouteForce') -or [string]$configMap['RouteForce'] -eq 'auto') {
            $configMap['RouteForce'] = 'encode'
            $configMap['RoutePolicyReason'] = 'file override video settings require transcode'
        }
    }

    $subtitleOverride = Get-MediaPipelineFileOverrideProperty -Object $Override -Name 'subtitles'
    $burnTrack = Get-FileOverrideSubtitleBurnTrack -SubtitleOverride $subtitleOverride
    if ($null -ne $burnTrack) {
        $burnStreamIndex = Get-MediaPipelineFileOverrideSelectorStreamIndex -Rule $burnTrack
        if ($null -eq $burnStreamIndex) {
            throw "Invalid file override combination: subtitles.burnTrack requires an exact streamIndex selector."
        }
        if ($configMap.Contains('RouteForce') -and [string]$configMap['RouteForce'] -eq 'remux') {
            throw "Invalid file override combination: routing.profile=remux cannot be combined with subtitles.burnTrack because subtitle burn-in requires encode."
        }
        $configMap['RouteForce'] = 'encode'
        $configMap['RoutePolicyReason'] = 'file override subtitles.burnTrack requires encode'
        $configMap['SubtitleBurnEncodeProfile'] = 'current_encode_style'
    }
    return $configMap
}

function Get-FileOverrideAudioSettings {
    <#
    .SYNOPSIS
        Extract the audio section from the active file override (stored in
        $script:ActiveOverrides under the '_FileOverride' key).
    .OUTPUTS
        PSObject | $null — the audio sub-object, or $null if no audio override.
    #>
    try {
        if ($script:ActiveOverrides -and $script:ActiveOverrides.ContainsKey('_FileOverride')) {
            $fo = $script:ActiveOverrides['_FileOverride']
            if ($fo) {
                $audio = $null
                try {
                    $audio = $fo.audio
                } catch {}
                if ($null -eq $audio) {
                    try {
                        $prop = $fo.PSObject.Properties['audio']
                        if ($prop) { $audio = $prop.Value }
                    } catch {}
                }
                return $audio
            }
        }
    } catch {}
    return $null
}

function Get-FileOverrideSubtitleSettings {
    <#
    .SYNOPSIS
        Extract the subtitles section from the active file override.
    .OUTPUTS
        PSObject | $null
    #>
    try {
        if ($script:ActiveOverrides -and $script:ActiveOverrides.ContainsKey('_FileOverride')) {
            $fo = $script:ActiveOverrides['_FileOverride']
            if ($fo) {
                $subs = $null
                try {
                    $subs = $fo.subtitles
                } catch {}
                if ($null -eq $subs) {
                    try {
                        $prop = $fo.PSObject.Properties['subtitles']
                        if ($prop) { $subs = $prop.Value }
                    } catch {}
                }
                return $subs
            }
        }
    } catch {}
    return $null
}

function Get-MediaPipelineFileOverrideSelectorStreamIndex {
    param($Rule)

    foreach ($name in @('streamIndex','stream_index','trackIndex','track_index','index')) {
        $value = Get-MediaPipelineFileOverrideProperty -Object $Rule -Name $name
        if ($null -eq $value) { continue }
        $text = ([string]$value).Trim()
        if ([string]::IsNullOrWhiteSpace($text)) { continue }
        $parsed = 0
        if (-not [int]::TryParse($text, [ref]$parsed) -or $parsed -lt 0) {
            throw "Invalid file override selector streamIndex '$text'. Exact stream selectors must be non-negative integers."
        }
        return $parsed
    }
    return $null
}

function Test-MediaPipelineFileOverrideTrackKindMatches {
    param(
        [Parameter(Mandatory)] [ValidateSet('audio','subtitle')] [string] $ExpectedKind,
        $Track
    )

    $kind = Get-MediaPipelineFileOverrideProperty -Object $Track -Name 'codec_type'
    if ($null -eq $kind) { $kind = Get-MediaPipelineFileOverrideProperty -Object $Track -Name 'kind' }
    if ($null -eq $kind) { $kind = Get-MediaPipelineFileOverrideProperty -Object $Track -Name 'type' }
    if ($null -eq $kind -or [string]::IsNullOrWhiteSpace([string]$kind)) {
        return $true
    }
    $normalized = ([string]$kind).Trim().ToLowerInvariant()
    if ($ExpectedKind -eq 'subtitle') {
        return ($normalized -in @('subtitle','subtitles'))
    }
    return ($normalized -eq 'audio')
}

function Test-MediaPipelineFileOverrideRuleMatchesTrack {
    param(
        [Parameter(Mandatory)] [string] $Kind,
        $Rule,
        [string] $Language,
        [int] $Channels = 0,
        [string] $Title = '',
        [string] $Codec = '',
        [bool] $IsForced = $false,
        $StreamIndex = $null
    )

    $exactIndex = Get-MediaPipelineFileOverrideSelectorStreamIndex -Rule $Rule
    if ($null -ne $exactIndex) {
        if ($null -eq $StreamIndex) { return $false }
        try {
            if ([int]$StreamIndex -ne [int]$exactIndex) { return $false }
        } catch {
            return $false
        }
    }

    $lang = Normalize-MediaPipelineFileOverrideLanguage $Language
    $titleText = if ($null -eq $Title) { '' } else { [string]$Title }
    $codecText = if ([string]::IsNullOrWhiteSpace($Codec)) { '' } else { $Codec.Trim().ToLowerInvariant() }

    $ruleLang = Get-MediaPipelineFileOverrideProperty -Object $Rule -Name 'language'
    if ($null -ne $ruleLang -and -not [string]::IsNullOrWhiteSpace([string]$ruleLang)) {
        if ($lang -ne (Normalize-MediaPipelineFileOverrideLanguage ([string]$ruleLang))) { return $false }
    }

    $ruleCodec = Get-MediaPipelineFileOverrideProperty -Object $Rule -Name 'codec'
    if ($null -ne $ruleCodec -and -not [string]::IsNullOrWhiteSpace([string]$ruleCodec)) {
        if ($codecText -ne ([string]$ruleCodec).Trim().ToLowerInvariant()) { return $false }
    }

    if ($Kind -eq 'audio') {
        $ruleChannels = Get-MediaPipelineFileOverrideProperty -Object $Rule -Name 'channels'
        if ($null -ne $ruleChannels -and -not [string]::IsNullOrWhiteSpace([string]$ruleChannels)) {
            $parsedChannels = 0
            if (-not [int]::TryParse(([string]$ruleChannels).Trim(), [ref]$parsedChannels) -or $parsedChannels -le 0) {
                throw "Invalid file override selector channels '$ruleChannels'. Audio selector channels must be positive integers."
            }
            if ($Channels -ne $parsedChannels) { return $false }
        }
    }

    if ($Kind -eq 'subtitle') {
        $forcedProp = $null
        try { $forcedProp = $Rule.PSObject.Properties['forced'] } catch {}
        if ($forcedProp) {
            if ([bool]$forcedProp.Value -ne [bool]$IsForced) { return $false }
        }
    }

    $ruleTitle = Get-MediaPipelineFileOverrideProperty -Object $Rule -Name 'title'
    if ($null -ne $ruleTitle -and -not [string]::IsNullOrWhiteSpace([string]$ruleTitle)) {
        if (-not ($titleText -like [string]$ruleTitle)) { return $false }
    }

    return $true
}

function Assert-FileOverrideExactTrackSelectorsResolvable {
    param(
        [Parameter(Mandatory)] [ValidateSet('audio','subtitle')] [string] $TrackKind,
        [array] $Tracks,
        $OverrideSection
    )

    if ($null -eq $OverrideSection) { return }
    $trackList = @($Tracks)
    foreach ($fieldName in @('keepTracks','dropTracks','burnTrack')) {
        $rules = $null
        try {
            $prop = $OverrideSection.PSObject.Properties[$fieldName]
            if ($prop -and $prop.Value) {
                $rules = if ($fieldName -eq 'burnTrack') { @($prop.Value) } else { @($prop.Value) }
            }
        } catch {}
        if ($null -eq $rules -or $rules.Count -eq 0) { continue }
        for ($i = 0; $i -lt $rules.Count; $i++) {
            $rule = $rules[$i]
            if ($null -eq $rule) { continue }
            $exactIndex = Get-MediaPipelineFileOverrideSelectorStreamIndex -Rule $rule
            if ($null -eq $exactIndex) { continue }
            $matched = $false
            foreach ($track in $trackList) {
                if (-not (Test-MediaPipelineFileOverrideTrackKindMatches -ExpectedKind $TrackKind -Track $track)) {
                    continue
                }
                $streamIndex = Get-MediaPipelineFileOverrideProperty -Object $track -Name 'index'
                $language = 'und'
                $title = ''
                try {
                    if ($track.tags -and $track.tags.language) { $language = ([string]$track.tags.language).ToLowerInvariant() }
                    if ($track.tags -and $track.tags.title) { $title = [string]$track.tags.title }
                } catch {}
                $codec = ''
                try { if ($track.codec_name) { $codec = ([string]$track.codec_name).Trim().ToLowerInvariant() } } catch {}
                $channels = 0
                try { if ($track.PSObject.Properties['channels']) { $channels = [int]$track.channels } } catch {}
                $isForced = $false
                try { $isForced = ($track.disposition.forced -eq 1) } catch {}
                if (Test-MediaPipelineFileOverrideRuleMatchesTrack `
                        -Kind $TrackKind `
                        -Rule $rule `
                        -Language $language `
                        -Channels $channels `
                        -Title $title `
                        -Codec $codec `
                        -IsForced:$isForced `
                        -StreamIndex $streamIndex) {
                    $matched = $true
                    break
                }
            }
            if (-not $matched) {
                $section = if ($TrackKind -eq 'audio') { 'audio' } else { 'subtitles' }
                $fieldPath = if ($fieldName -eq 'burnTrack') { '{0}.{1}' -f $section, $fieldName } else { '{0}.{1}[{2}]' -f $section, $fieldName, $i }
                throw "FILE_OVERRIDE_EXACT_TRACK_UNAVAILABLE: $fieldPath streamIndex $exactIndex does not match any detected $TrackKind stream."
            }
        }
    }
}

function Test-AudioTrackKeptByOverride {
    <#
    .SYNOPSIS
        Test whether an audio track passes the per-file keepTracks/dropTracks filter.
    .PARAMETER Language
        ISO 639-2 language tag (lowercase), e.g. "eng", "jpn", "und".
    .PARAMETER Channels
        Number of audio channels (integer).
    .PARAMETER Title
        Raw title tag from the source file (may be empty).
    .PARAMETER Codec
        Source codec name from ffprobe.
    .PARAMETER StreamIndex
        Global ffprobe stream index for exact-track selectors.
    .PARAMETER AudioOverride
        The audio sub-object from Resolve-FileOverride (or Get-FileOverrideAudioSettings).
        If $null, no filtering is applied and the track is always kept.
    .OUTPUTS
        [bool]  $true = keep the track, $false = drop it.
    .DESCRIPTION
        Resolution:
          1. If dropTracks rules exist and the track matches ANY drop rule → drop.
          2. If keepTracks rules exist and the track matches NONE of them → drop.
          3. Otherwise → keep.

        A rule matches a track when ALL non-null fields in the rule match the
        corresponding track property:
          language  — case-insensitive ISO 639-2 match (also handles "und")
          streamIndex — exact global ffprobe stream index
          codec     — case-insensitive codec name
          channels  — exact integer match
          title     — glob pattern (wildcards: * ? [...])
    #>
    param(
        [string] $Language,
        [int]    $Channels,
        [string] $Title,
        [string] $Codec = '',
        $StreamIndex = $null,
        $AudioOverride
    )

    if ($null -eq $AudioOverride) { return $true }

    # Get dropTracks and keepTracks lists
    $dropRules = $null
    $keepRules = $null
    try {
        $drProp = $AudioOverride.PSObject.Properties['dropTracks']
        if ($drProp -and $drProp.Value) { $dropRules = @($drProp.Value) }
    } catch {}
    try {
        $krProp = $AudioOverride.PSObject.Properties['keepTracks']
        if ($krProp -and $krProp.Value) { $keepRules = @($krProp.Value) }
    } catch {}

    # 1. Drop rule match → always drop
    if ($null -ne $dropRules -and $dropRules.Count -gt 0) {
        foreach ($rule in $dropRules) {
            if ($null -ne $rule -and (Test-MediaPipelineFileOverrideRuleMatchesTrack `
                    -Kind 'audio' `
                    -Rule $rule `
                    -Language $Language `
                    -Channels $Channels `
                    -Title $Title `
                    -Codec $Codec `
                    -StreamIndex $StreamIndex)) { return $false }
        }
    }

    # 2. keepTracks exists but track doesn't match any rule → drop
    if ($null -ne $keepRules -and $keepRules.Count -gt 0) {
        $matched = $false
        foreach ($rule in $keepRules) {
            if ($null -ne $rule -and (Test-MediaPipelineFileOverrideRuleMatchesTrack `
                    -Kind 'audio' `
                    -Rule $rule `
                    -Language $Language `
                    -Channels $Channels `
                    -Title $Title `
                    -Codec $Codec `
                    -StreamIndex $StreamIndex)) { $matched = $true; break }
        }
        if (-not $matched) { return $false }
    }

    return $true
}

function Test-SubtitleTrackKeptByOverride {
    <#
    .SYNOPSIS
        Test whether a subtitle track passes the per-file keepTracks/dropTracks filter.
    .PARAMETER Language
        ISO 639-2 language tag (lowercase).
    .PARAMETER IsForced
        $true if the track has the forced flag set.
    .PARAMETER Title
        Raw title tag from the source file.
    .PARAMETER Codec
        Source codec name from ffprobe.
    .PARAMETER StreamIndex
        Global ffprobe stream index for exact-track selectors.
    .PARAMETER SubtitleOverride
        The subtitles sub-object from Resolve-FileOverride (or Get-FileOverrideSubtitleSettings).
    .OUTPUTS
        [bool]  $true = keep the track, $false = drop it.
    #>
    param(
        [string] $Language,
        [bool]   $IsForced,
        [string] $Title,
        [string] $Codec = '',
        $StreamIndex = $null,
        $SubtitleOverride
    )

    if ($null -eq $SubtitleOverride) { return $true }

    if ($null -ne (Get-FileOverrideSubtitleBurnTrack -SubtitleOverride $SubtitleOverride)) {
        return $false
    }

    # stripAll shortcut
    $stripAll = $false
    try { $stripAll = [bool]$SubtitleOverride.stripAll } catch {}
    if ($stripAll) { return $false }

    $dropRules = $null
    $keepRules = $null
    try {
        $drProp = $SubtitleOverride.PSObject.Properties['dropTracks']
        if ($drProp -and $drProp.Value) { $dropRules = @($drProp.Value) }
    } catch {}
    try {
        $krProp = $SubtitleOverride.PSObject.Properties['keepTracks']
        if ($krProp -and $krProp.Value) { $keepRules = @($krProp.Value) }
    } catch {}

    # Drop rule wins
    if ($null -ne $dropRules -and $dropRules.Count -gt 0) {
        foreach ($rule in $dropRules) {
            if ($null -ne $rule -and (Test-MediaPipelineFileOverrideRuleMatchesTrack `
                    -Kind 'subtitle' `
                    -Rule $rule `
                    -Language $Language `
                    -Title $Title `
                    -Codec $Codec `
                    -IsForced:$IsForced `
                    -StreamIndex $StreamIndex)) { return $false }
        }
    }
    # Not in keepTracks → drop
    if ($null -ne $keepRules -and $keepRules.Count -gt 0) {
        $matched = $false
        foreach ($rule in $keepRules) {
            if ($null -ne $rule -and (Test-MediaPipelineFileOverrideRuleMatchesTrack `
                    -Kind 'subtitle' `
                    -Rule $rule `
                    -Language $Language `
                    -Title $Title `
                    -Codec $Codec `
                    -IsForced:$IsForced `
                    -StreamIndex $StreamIndex)) { $matched = $true; break }
        }
        if (-not $matched) { return $false }
    }
    return $true
}

function Test-SubtitleTrackBurnedByOverride {
    param(
        [string] $Language,
        [bool]   $IsForced,
        [string] $Title,
        [string] $Codec = '',
        $StreamIndex = $null,
        $SubtitleOverride
    )

    $burnTrack = Get-FileOverrideSubtitleBurnTrack -SubtitleOverride $SubtitleOverride
    if ($null -eq $burnTrack) { return $false }
    return (Test-MediaPipelineFileOverrideRuleMatchesTrack `
        -Kind 'subtitle' `
        -Rule $burnTrack `
        -Language $Language `
        -Title $Title `
        -Codec $Codec `
        -IsForced:$IsForced `
        -StreamIndex $StreamIndex)
}

function Get-AudioTrackTitleOverride {
    <#
    .SYNOPSIS
        Return the newTitle string from a matching renameTracks rule, or $null.
    .PARAMETER Language
        ISO 639-2 language tag (lowercase).
    .PARAMETER Channels
        Output channel count (after downmix).
    .PARAMETER AudioOverride
        The audio sub-object.
    .OUTPUTS
        [string] | $null
    #>
    param(
        [string] $Language,
        [int]    $Channels,
        $AudioOverride
    )

    if ($null -eq $AudioOverride) { return $null }

    $renameRules = $null
    try {
        $rp = $AudioOverride.PSObject.Properties['renameTracks']
        if ($rp -and $rp.Value) { $renameRules = @($rp.Value) }
    } catch {}

    if ($null -eq $renameRules -or $renameRules.Count -eq 0) { return $null }

    $lang = Normalize-MediaPipelineFileOverrideLanguage $Language

    foreach ($rule in $renameRules) {
        if ($null -eq $rule) { continue }
        # language match
        $ruleLang = $null
        try { $ruleLang = [string]$rule.language } catch {}
        if (-not [string]::IsNullOrWhiteSpace($ruleLang)) {
            if ($lang -ne (Normalize-MediaPipelineFileOverrideLanguage $ruleLang)) { continue }
        }
        # channels match
        $ruleChannels = $null
        try { $ruleChannels = [int]$rule.channels } catch {}
        if ($null -ne $ruleChannels -and $ruleChannels -gt 0 -and $Channels -ne $ruleChannels) { continue }
        # matched — return newTitle
        $newTitle = $null
        try { $newTitle = [string]$rule.newTitle } catch {}
        if (-not [string]::IsNullOrWhiteSpace($newTitle)) { return $newTitle }
    }
    return $null
}

function Get-SubtitleTrackTitleOverride {
    <#
    .SYNOPSIS
        Return the newTitle string from a matching subtitle renameTracks rule, or $null.
    .PARAMETER Language
        ISO 639-2 language tag (lowercase).
    .PARAMETER IsForced
        $true if the track has the forced flag.
    .PARAMETER SubtitleOverride
        The subtitles sub-object.
    .OUTPUTS
        [string] | $null
    #>
    param(
        [string] $Language,
        [bool]   $IsForced,
        $SubtitleOverride
    )

    if ($null -eq $SubtitleOverride) { return $null }

    $renameRules = $null
    try {
        $rp = $SubtitleOverride.PSObject.Properties['renameTracks']
        if ($rp -and $rp.Value) { $renameRules = @($rp.Value) }
    } catch {}

    if ($null -eq $renameRules -or $renameRules.Count -eq 0) { return $null }

    $lang = Normalize-MediaPipelineFileOverrideLanguage $Language

    foreach ($rule in $renameRules) {
        if ($null -eq $rule) { continue }
        $ruleLang = $null
        try { $ruleLang = [string]$rule.language } catch {}
        if (-not [string]::IsNullOrWhiteSpace($ruleLang)) {
            if ($lang -ne (Normalize-MediaPipelineFileOverrideLanguage $ruleLang)) { continue }
        }
        $ruleForced = $null
        try {
            $fp = $rule.PSObject.Properties['forced']
            if ($fp) { $ruleForced = [bool]$fp.Value }
        } catch {}
        if ($null -ne $ruleForced -and $ruleForced -ne $IsForced) { continue }
        $newTitle = $null
        try { $newTitle = [string]$rule.newTitle } catch {}
        if (-not [string]::IsNullOrWhiteSpace($newTitle)) { return $newTitle }
    }
    return $null
}

function Merge-FileOverrideIntoActiveOverrides {
    <#
    .SYNOPSIS
        Inject the per-file override for $SourcePath into $script:ActiveOverrides.
    .DESCRIPTION
        Reads file_overrides.json (cached), resolves the entry for $SourcePath,
        and stores it under the '_FileOverride' key in $script:ActiveOverrides.
        Flat config-style fields (maxChannels, downmixMode, etc.) are also
        promoted to top-level ActiveOverrides keys so existing Get-Effective*
        functions pick them up without modification.
    .PARAMETER SourcePath
        The full source file path.
    #>
    param([string]$SourcePath)

    # Invalidate the manifest cache on every new file so edits made during
    # a long pipeline run are picked up.
    $script:CachedFileOverridesManifest = $null
    $script:LastFileOverrideConfigMap = [ordered]@{}
    $script:LastFileOverrideMatch = $null

    $match = Resolve-FileOverrideMatch -SourcePath $SourcePath
    if ($null -eq $match -or $null -eq $match.Entry) {
        # Ensure any previous file's _FileOverride is cleared
        if ($script:ActiveOverrides -and $script:ActiveOverrides.ContainsKey('_FileOverride')) {
            $script:ActiveOverrides.Remove('_FileOverride')
        }
        return
    }
    $override = $match.Entry

    if ($null -eq $script:ActiveOverrides) { $script:ActiveOverrides = @{} }

    # Store the full structured override for track-filter functions
    $script:ActiveOverrides['_FileOverride'] = $override
    $script:LastFileOverrideMatch = $match

    # Promote flat audio config fields into top-level ActiveOverrides so that
    # existing Get-EffectiveAudio* functions work without modification.
    $fileConfigMap = ConvertTo-MediaPipelineFileOverrideConfigMap -Override $override
    foreach ($key in $fileConfigMap.Keys) {
        $script:ActiveOverrides[$key] = $fileConfigMap[$key]
    }
    $script:LastFileOverrideConfigMap = $fileConfigMap

    $routeVideoFields = @(Get-MediaPipelineFileOverrideRouteVideoFieldPaths -Override $override)
    if ($routeVideoFields.Count -gt 0) {
        $fieldText = $routeVideoFields -join ', '
        Write-Log "FILE OVERRIDE: applied route/video override for '$SourcePath' (scope=$($match.Scope), matched=$($match.MatchedPath), fields=$fieldText)" "INFO"
        if ($fileConfigMap.Contains('RouteForce') -and [string]$fileConfigMap['RouteForce'] -eq 'encode') {
            Write-Log "FILE OVERRIDE: route/video override forces transcode for '$SourcePath'." "WARN"
        }
    }
}
