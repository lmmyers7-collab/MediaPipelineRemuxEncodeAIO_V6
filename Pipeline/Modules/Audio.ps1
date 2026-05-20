# ==============================================================================
# Modules\Audio.ps1
# ==============================================================================
# Audio stream selection, language preference, and ffmpeg audio-argument helpers.
#
# Dot-sourced from MediaPipeline_chatgpt.ps1. Reads at call time:
#   $ffprobePath
#   $CompatibleAudioCodecs
#   $AudioPassthroughProfile
#   $AudioTranscodeCodec, $AudioTranscodeBitrate, $AudioDownmixMode,
#   $AudioMaxChannels, $AllowNoAudio
#   $PreferredDefaultAudioLanguages
#   $script:PreferredDefaultAudioLanguages
#
# Cross-module helpers:
#   Invoke-NativeCommand, Write-Log, DebugLog
# ==============================================================================
function Normalize-AudioLanguagePreferenceValue {
    param([string]$Value)

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

function Get-NormalizedPreferredAudioLanguages {
    $configuredLanguages = if ($script:ActiveOverrides -and $script:ActiveOverrides.ContainsKey('PreferredDefaultAudioLanguages') -and @($script:ActiveOverrides['PreferredDefaultAudioLanguages']).Count -gt 0) {
        @($script:ActiveOverrides['PreferredDefaultAudioLanguages'])
    } else {
        @($script:PreferredDefaultAudioLanguages)
    }
    $preferred = @(
        $configuredLanguages |
            ForEach-Object { Normalize-AudioLanguagePreferenceValue ([string]$_) } |
            Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
            Select-Object -Unique
    )
    if ($preferred.Count -eq 0) { return @('eng') }
    return $preferred
}

function Get-AudioCodecFidelityRank {
    param([string]$Codec)

    return Get-MediaAudioCodecFidelityRankValue -Codec $Codec
}

function Get-AudioFidelityScore {
    param(
        [string]$Codec,
        [int]$Channels
    )

    $safeChannels = [math]::Min([math]::Max($Channels, 0), 16)
    return ((Get-AudioCodecFidelityRank $Codec) * 1000) + ($safeChannels * 10)
}

function Test-IsPcmAudioCodec {
    param([string]$Codec)

    $normalized = if ($Codec) { $Codec.Trim().ToLowerInvariant() } else { '' }
    if ([string]::IsNullOrWhiteSpace($normalized)) { return $false }
    if ($normalized -eq 'pcm') { return $true }
    if ($normalized.StartsWith('pcm_')) { return $true }
    if ($normalized.StartsWith('a_pcm')) { return $true }
    return $false
}

function Get-EffectiveAudioTranscodeCodec {
    $value = if ($script:ActiveOverrides -and $script:ActiveOverrides.ContainsKey('AudioTranscodeCodec')) {
        [string]$script:ActiveOverrides['AudioTranscodeCodec']
    } elseif (Get-Variable -Name AudioTranscodeCodec -Scope Script -ErrorAction SilentlyContinue) {
        [string]$script:AudioTranscodeCodec
    } else { '' }
    $normalized = $value.Trim().ToLowerInvariant()
    if ($normalized -in @('eac3','ac3','aac')) { return $normalized }
    return 'eac3'
}

function Get-EffectiveAudioTranscodeBitrate {
    $value = if ($script:ActiveOverrides -and $script:ActiveOverrides.ContainsKey('AudioTranscodeBitrate')) {
        [string]$script:ActiveOverrides['AudioTranscodeBitrate']
    } elseif (Get-Variable -Name AudioTranscodeBitrate -Scope Script -ErrorAction SilentlyContinue) {
        [string]$script:AudioTranscodeBitrate
    } else { '' }
    $normalized = $value.Trim().ToLowerInvariant()
    if ($normalized -match '^\d+k$') { return $normalized }
    return '640k'
}

function Get-EffectiveAudioTranscodeAutoBitrateByChannels {
    # Suggestion #7 — opt-in flag (default $false for backwards compat)
    # that switches per-stream bitrate selection from the static
    # AudioTranscodeBitrate to a channel-count-aware table. Operators
    # who explicitly set 768k or 512k won't be silently overridden;
    # they must turn this on to get the scaled behavior.
    $value = if ($script:ActiveOverrides -and $script:ActiveOverrides.ContainsKey('AudioTranscodeAutoBitrateByChannels')) {
        $script:ActiveOverrides['AudioTranscodeAutoBitrateByChannels']
    } elseif (Get-Variable -Name AudioTranscodeAutoBitrateByChannels -Scope Script -ErrorAction SilentlyContinue) {
        $script:AudioTranscodeAutoBitrateByChannels
    } else { $null }
    if ($null -eq $value) { return $false }
    if ($value -is [bool]) { return [bool]$value }
    return ([string]$value).Trim() -match '^(?i:true|1|yes|y|on)$'
}

function Get-AudioTranscodeBitrateForChannels {
    <#
    .SYNOPSIS
    Suggestion #7 — pick an output bitrate appropriate for the codec /
    channel count combination instead of always emitting 640k.

    .DESCRIPTION
    640k EAC3 for a stereo source is wasteful (the bit-pool is twice
    what a 2.0 mix needs); 384k EAC3 for a 7.1 mix is starvation. AAC
    needs ~25% less bitrate than EAC3/AC3 for equivalent perceptual
    quality. The table below is conservative — slightly above what
    most reference guides recommend, so transparent on typical Plex
    direct-stream targets.

    Returns a string like '192k' that ffmpeg accepts as -b:a:N.
    #>
    param(
        [Parameter(Mandatory)] [string] $Codec,
        [Parameter(Mandatory)] [int]    $Channels
    )

    $codec = ([string]$Codec).Trim().ToLowerInvariant()
    $ch    = [math]::Max(1, [math]::Min(8, [int]$Channels))

    # eac3/ac3 share the same table because eac3 is bitstream-compatible
    # at typical bitrates and ac3 doesn't have a meaningful efficiency
    # advantage at the rates we use. AAC gets a ~25% discount.
    $eac3Table = @{
        1 = '96k';  2 = '192k'; 3 = '224k'; 4 = '256k'
        5 = '320k'; 6 = '448k'; 7 = '512k'; 8 = '640k'
    }
    $aacTable = @{
        1 = '96k';  2 = '160k'; 3 = '192k'; 4 = '224k'
        5 = '256k'; 6 = '384k'; 7 = '448k'; 8 = '512k'
    }
    $table = if ($codec -eq 'aac') { $aacTable } else { $eac3Table }
    if ($table.ContainsKey($ch)) { return [string]$table[$ch] }
    return '640k'
}

function Get-EffectiveAudioDownmixMode {
    $value = if ($script:ActiveOverrides -and $script:ActiveOverrides.ContainsKey('AudioDownmixMode')) {
        [string]$script:ActiveOverrides['AudioDownmixMode']
    } elseif (Get-Variable -Name AudioDownmixMode -Scope Script -ErrorAction SilentlyContinue) {
        [string]$script:AudioDownmixMode
    } else { '' }
    $normalized = $value.Trim().ToLowerInvariant()
    if ($normalized -in @('preserve','max_channels','stereo')) { return $normalized }
    return 'max_channels'
}

function Get-EffectiveAudioMaxChannels {
    $value = if ($script:ActiveOverrides -and $script:ActiveOverrides.ContainsKey('AudioMaxChannels')) {
        $script:ActiveOverrides['AudioMaxChannels']
    } elseif (Get-Variable -Name AudioMaxChannels -Scope Script -ErrorAction SilentlyContinue) {
        $script:AudioMaxChannels
    } else { 6 }
    try {
        $channels = [int]$value
        if ($channels -ge 1 -and $channels -le 16) { return $channels }
    } catch {}
    return 6
}

function Get-EffectiveAllowNoAudio {
    $value = if ($script:ActiveOverrides -and $script:ActiveOverrides.ContainsKey('AllowNoAudio')) {
        $script:ActiveOverrides['AllowNoAudio']
    } elseif (Get-Variable -Name AllowNoAudio -Scope Script -ErrorAction SilentlyContinue) {
        $script:AllowNoAudio
    } else { $false }
    return [bool]$value
}

function Get-EffectiveAudioPassthroughProfile {
    $hasOverrideCodecs = $script:ActiveOverrides -and $script:ActiveOverrides.ContainsKey('CompatibleAudioCodecs') -and @($script:ActiveOverrides['CompatibleAudioCodecs']).Count -gt 0
    $hasOverrideProfile = $script:ActiveOverrides -and $script:ActiveOverrides.ContainsKey('AudioPassthroughProfile')
    $configuredCodecs = if ($hasOverrideCodecs) {
        @($script:ActiveOverrides['CompatibleAudioCodecs'])
    } elseif (Get-Variable -Name CompatibleAudioCodecs -Scope Script -ErrorAction SilentlyContinue) {
        @($script:CompatibleAudioCodecs)
    } else {
        @()
    }
    if ($hasOverrideProfile) {
        return (Resolve-MediaPipelineAudioPassthroughProfile -Profile ([string]$script:ActiveOverrides['AudioPassthroughProfile']) -LegacyCompatibleAudioCodecs $configuredCodecs)
    }
    if ($hasOverrideCodecs) {
        return 'custom_codec_list'
    }
    if (Get-Variable -Name AudioPassthroughProfile -Scope Script -ErrorAction SilentlyContinue) {
        return (Resolve-MediaPipelineAudioPassthroughProfile -Profile ([string]$script:AudioPassthroughProfile) -LegacyCompatibleAudioCodecs $configuredCodecs)
    }
    return (Resolve-MediaPipelineAudioPassthroughProfile -Profile '' -LegacyCompatibleAudioCodecs $configuredCodecs)
}

function Get-EffectiveCompatibleAudioCodecs {
    $hasOverrideCodecs = $script:ActiveOverrides -and $script:ActiveOverrides.ContainsKey('CompatibleAudioCodecs') -and @($script:ActiveOverrides['CompatibleAudioCodecs']).Count -gt 0
    $configured = if ($hasOverrideCodecs) {
        @($script:ActiveOverrides['CompatibleAudioCodecs'])
    } elseif (Get-Variable -Name CompatibleAudioCodecs -Scope Script -ErrorAction SilentlyContinue) {
        @($script:CompatibleAudioCodecs)
    } else {
        @()
    }
    $profile = Get-EffectiveAudioPassthroughProfile
    if ($profile -ne 'custom_codec_list') {
        $configured = @(Get-MediaPipelineAudioPassthroughProfileCodecs -Profile $profile)
    }

    $effective = @(
        $configured |
            ForEach-Object { ([string]$_).Trim().ToLowerInvariant() } |
            Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
            Where-Object { -not (Test-IsPcmAudioCodec $_) } |
            Select-Object -Unique
    )

    if ($script:ActiveOverrides -and $script:ActiveOverrides.FlacAsCompatible) {
        $flacCodec = Get-MediaAudioCodecFlacName
        if ($effective -notcontains $flacCodec) {
            $effective = @($effective) + $flacCodec
            Write-Log "Audio: FlacAsCompatible override active — FLAC will be stream-copied" "DEBUG"
        }
    }

    return @($effective)
}

function Get-TranscodedAudioChannelCount {
    param([int]$SourceChannels)

    $safeChannels = if ($SourceChannels -gt 0) { $SourceChannels } else { 2 }
    switch (Get-EffectiveAudioDownmixMode) {
        'stereo'       { return 2 }
        'preserve'     { return $safeChannels }
        default        { return [math]::Min($safeChannels, (Get-EffectiveAudioMaxChannels)) }
    }
}

function Get-PreferredDefaultAudioIndex {
    param([array]$TrackMetadata)

    if ($null -eq $TrackMetadata -or $TrackMetadata.Count -eq 0) { return 0 }

    $preferred = Get-NormalizedPreferredAudioLanguages
    $pool = @($TrackMetadata | Where-Object { -not $_.IsCommentary })
    if ($pool.Count -eq 0) {
        $pool = @($TrackMetadata)
    }

    foreach ($entry in $pool) {
        $entry.PreferenceRank = $preferred.IndexOf($entry.NormalizedLang)
        if ($entry.PreferenceRank -lt 0) {
            $entry.PreferenceRank = [int]::MaxValue
        }
    }

    $preferredPool = @($pool | Where-Object { $_.PreferenceRank -lt [int]::MaxValue })
    if ($preferredPool.Count -gt 0) {
        $pool = $preferredPool
    }

    return [int](($pool | Sort-Object `
        @{ Expression = { $_.PreferenceRank } }, `
        @{ Expression = { $_.FidelityScore }; Descending = $true }, `
        @{ Expression = { $_.Index } } |
        Select-Object -First 1).Index)
}

function Set-LastAudioDecisionRecords {
    param([array] $Records = @())
    $script:LastAudioDecisionRecords = @($Records | Where-Object { $null -ne $_ })
}

function Get-LastAudioDecisionRecords {
    return @($script:LastAudioDecisionRecords)
}

function Build-AudioArgs {
    param([string]$FilePath)
    Set-LastAudioDecisionRecords @()

    # Resolve effective compatible-codec list. Folder/show overrides can narrow
    # passthrough behavior for a specific series or folder without changing the
    # global workstation profile.
    $effectiveCompat = @(Get-EffectiveCompatibleAudioCodecs)

    # Probe language AND title (title needed for commentary / descriptive detection).
    # channel_layout is also pulled for completeness though we derive the label
    # from the post-downmix channel count, not the source layout.
    $probeResult = Invoke-FFprobeCommand -ArgumentList @(
        "-v","error","-select_streams","a",
        "-show_entries","stream=index,codec_name,channels,channel_layout,disposition:stream_tags=language,title",
        "-of","json","--",$FilePath
    ) -TimeoutSeconds 30 -Stage 'audio-stream-probe'

    $audioStreams = @()
    if ($probeResult.ExitCode -eq 0) {
        try { $json = $probeResult.Output | ConvertFrom-Json; if ($json.streams) { $audioStreams = $json.streams } } catch {}
    }

    $mapArgs   = [System.Collections.Generic.List[string]]::new()
    $codecArgs = [System.Collections.Generic.List[string]]::new()
    $audioTrackMeta = [System.Collections.Generic.List[object]]::new()
    $audioDecisionRecords = [System.Collections.Generic.List[object]]::new()
    # CPU-A1 — track whether ANY audio stream is being transcoded so the
    # caller can lower the ffmpeg process priority and apply the CPU
    # thread cap.  A pure stream-copy AV stage is I/O-bound and doesn't
    # benefit from priority lowering.
    $transcodeActive = $false

    # Language tag (ISO 639-2/B code) -> human display name for the track title.
    # Unknown / untagged tracks get "Undefined". Codes not in the map fall back
    # to an uppercased raw code (e.g. "THA" for Thai), which is still legible.
    $LangDisplay = @{
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

    # Channel count -> Dolby-style layout label for the track title.
    # Uses the post-downmix channel count, not the source channel_layout,
    # so a 7.1 DTS-HD transcoded to 5.1 EAC3 reads "5.1 EAC3" not "7.1 EAC3".
    $ChannelLabel = @{
        1 = '1.0'; 2 = '2.0'; 3 = '2.1'; 4 = '4.0'
        5 = '4.1'; 6 = '5.1'; 7 = '6.1'; 8 = '7.1'
    }

    # Commentary / descriptive / audio-description detector. Runs against the
    # source title tag. These tracks are preserved but never marked default
    # (a viewer who sets Plex to auto-play English shouldn't hear director
    # commentary by accident).
    $CommentaryRegex = '(?i)commentary|director|cast|audio\s*description|descriptive|behind.the.scenes|isolated\s*score'
    $transcodeCodec = Get-EffectiveAudioTranscodeCodec
    $transcodeBitrate = Get-EffectiveAudioTranscodeBitrate
    # Suggestion #7 — when AudioTranscodeAutoBitrateByChannels is on,
    # ignore the static AudioTranscodeBitrate and pick a per-stream
    # bitrate from the channel-count table. Otherwise (default), the
    # static value is used as before.
    $autoScaleBitrate = Get-EffectiveAudioTranscodeAutoBitrateByChannels
    $transcodeCodecLabel = Get-MediaAudioCodecDisplayLabel -Codec $transcodeCodec

    if ($audioStreams.Count -eq 0) {
        $chk = Invoke-FFprobeCommand -ArgumentList @(
            "-v","error","-select_streams","a","-show_entries","stream=codec_type",
            "-of","default=noprint_wrappers=1:nokey=1","--",$FilePath
        ) -TimeoutSeconds 15 -Stage 'audio-presence-probe'
        if ([string]::IsNullOrWhiteSpace($chk.Output)) {
            $message = "SOURCE_MEDIA_AUDIO_MISSING: no audio streams found in $FilePath"
            if (Get-EffectiveAllowNoAudio) {
                Write-Log "$message; AllowNoAudio is enabled, output will omit audio." "WARN"
                Set-LastAudioDecisionRecords @([pscustomobject]@{
                    audio_ordinal       = $null
                    source_stream_index = $null
            action              = 'omit_all'
            reason              = 'allow_no_audio'
            passthrough_profile = Get-EffectiveAudioPassthroughProfile
            language            = 'und'
                    source_codec        = ''
                    source_channels     = 0
                    output_codec        = ''
                    output_channels     = 0
                    is_default          = $false
                    is_forced           = $false
                    is_commentary       = $false
                    title               = ''
                })
                return @('-an')
            }
            Write-Log $message "ERROR"
            throw $message
        }
        # The metadata probe failed even though ffprobe can see audio. Do not
        # guess 0:a:0 and risk dropping alternate/default/commentary tracks.
        $message = "SOURCE_MEDIA_AUDIO_METADATA_PROBE_FAILED: audio presence was detected but audio stream metadata could not be parsed for $FilePath"
        Write-Log $message "ERROR"
        throw $message
    }

    # Per-file override: resolve audio track filter + rename rules once before the loop.
    $audioOverride = Get-FileOverrideAudioSettings
    # Separate output ordinal (may differ from source index when tracks are filtered).
    $outOrdinal = 0

    for ($i = 0; $i -lt $audioStreams.Count; $i++) {
        $s        = $audioStreams[$i]
        $rawLang = "und"
        try {
            if ($s.tags -and $s.tags.language) { $rawLang = ([string]$s.tags.language).ToLowerInvariant() }
        } catch {}
        $rawTitle = ""
        try {
            if ($s.tags -and $s.tags.title) { $rawTitle = [string]$s.tags.title }
        } catch {}
        $codec = ([string]$s.codec_name).Trim().ToLowerInvariant()
        if ([string]::IsNullOrWhiteSpace($codec)) {
            throw "SOURCE_MEDIA_AUDIO_INVALID: audio stream $i is missing codec_name in ffprobe output"
        }
        $ch = 0
        try { $ch = [int]$s.channels } catch { $ch = 0 }
        if ($ch -le 0) {
            throw "SOURCE_MEDIA_AUDIO_INVALID: audio stream $i has missing or invalid channel count in ffprobe output"
        }
        $outCh    = Get-TranscodedAudioChannelCount -SourceChannels $ch
        $isForcedAudio = $false
        try { $isForcedAudio = ($s.disposition.forced -eq 1) } catch {}

        $isCommentary = ($rawTitle -match $CommentaryRegex)

        # --- Per-file override: track filter ---
        if (-not (Test-AudioTrackKeptByOverride -Language $rawLang -Channels $ch -Title $rawTitle -AudioOverride $audioOverride)) {
            $audioDecisionRecords.Add([pscustomobject]@{
                audio_ordinal       = $null
                source_stream_index = if ($null -ne $s.PSObject.Properties['index']) { $s.index } else { $null }
                action              = 'drop'
                reason              = 'file_override'
                passthrough_profile = Get-EffectiveAudioPassthroughProfile
                language            = $rawLang
                normalized_language = Normalize-AudioLanguagePreferenceValue $rawLang
                source_codec        = $codec
                source_channels     = $ch
                output_codec        = ''
                output_channels     = 0
                bitrate             = ''
                is_default          = $false
                is_forced           = $isForcedAudio
                is_commentary       = $isCommentary
                title               = $rawTitle
            }) | Out-Null
            Write-Log "Audio $i ($codec, ${ch}ch, $rawLang) -> dropped by file override" "DEBUG"
            continue
        }

        $mapArgs.AddRange([string[]]@("-map","0:a:$i"))

        # Map channel count to a canonical layout tag for transcoded audio.
        # Streamcopy preserves source packets/metadata and intentionally does
        # not receive -channel_layout.
        $LayoutTag = @{
            1 = 'mono';  2 = 'stereo'; 3 = '2.1';      4 = 'quad'
            5 = '4.1';   6 = '5.1';    7 = '6.1';      8 = '7.1'
        }

        # Decide copy vs transcode. effectiveCompat is the gate
        # (CompatibleAudioCodecs merged with any active per-show overrides).
        $standardizePcm = Test-IsPcmAudioCodec $codec
        if ($standardizePcm -or $codec -notin $effectiveCompat) {
            # Suggestion #7 — pick the per-stream bitrate from the
            # channel-count table when auto-scale is on, else use the
            # static configured bitrate. This lets a 2.0 commentary track
            # transcode at 192k while a 5.1 main track still gets 448k,
            # instead of both at 640k.
            $effectiveBitrate = if ($autoScaleBitrate) {
                Get-AudioTranscodeBitrateForChannels -Codec $transcodeCodec -Channels $outCh
            } else {
                $transcodeBitrate
            }
            $codecArgs.AddRange([string[]]@("-c:a:$outOrdinal",$transcodeCodec,"-b:a:$outOrdinal",$effectiveBitrate,"-ac:$outOrdinal","$outCh"))
            if ($LayoutTag.ContainsKey($outCh)) {
                $codecArgs.AddRange([string[]]@("-channel_layout:a:$outOrdinal", $LayoutTag[$outCh]))
            }
            $outCodecLabel = $transcodeCodecLabel
            $outChannels   = $outCh
            $reason = if ($standardizePcm) { 'PCM standardization' } else { 'codec outside compatibility list' }
            $action = 'transcode'
            $outputCodec = $transcodeCodec
            $transcodeActive = $true
            $bitrateSource = if ($autoScaleBitrate) { 'channel-scaled' } else { 'configured' }
            Write-Log "Audio $i ($codec, ${ch}ch, $rawLang) -> $transcodeCodecLabel ${outCh}ch @ $effectiveBitrate ($reason; bitrate $bitrateSource)" "DEBUG"
        } else {
            $codecArgs.AddRange([string[]]@("-c:a:$outOrdinal","copy"))
            # Do not emit channel_layout for streamcopy. FFmpeg cannot
            # reliably change codec properties while copying packets, and
            # some builds reject -channel_layout with -c:a copy.
            # Keep common codec labels readable in generated track titles.
            $outCodecLabel = Get-MediaAudioCodecDisplayLabel -Codec $codec
            $outChannels = $ch
            $reason = 'codec compatible'
            $action = 'copy'
            $outputCodec = $codec
            Write-Log "Audio $i ($codec, ${ch}ch, $rawLang) -> copy" "DEBUG"
        }

        # Language tag — THE critical fix. Previously this was logged but not
        # written back to the output. Plex uses this to match against the
        # user's audio language preference.
        $codecArgs.AddRange([string[]]@("-metadata:s:a:$outOrdinal","language=$rawLang"))

        # Title assembly. Format: "Language - Layout Codec [Commentary]"
        # e.g. "English - 5.1 EAC3"
        #      "Japanese - 2.0 FLAC"
        #      "English - 2.0 AAC [Commentary]"
        # NOTE: these locals are named with a `disp` suffix instead of the
        # obvious `$langDisplay` / `$layoutLabel` because PowerShell variable
        # names are CASE-INSENSITIVE. Using `$langDisplay` would rebind the
        # outer `$LangDisplay` hashtable to the lookup result (a string) on
        # the first loop iteration, and the second iteration would fail with
        # "[String] does not contain a method ContainsKey".
        $langDisp   = if ($LangDisplay.ContainsKey($rawLang)) { $LangDisplay[$rawLang] } else { $rawLang.ToUpper() }
        $layoutDisp = if ($ChannelLabel.ContainsKey($outChannels)) { $ChannelLabel[$outChannels] } else { "${outChannels}ch" }
        $title      = "$langDisp - $layoutDisp $outCodecLabel"
        if ($isCommentary) { $title += " [Commentary]" }
        # Per-file override: track title rename (applied after auto-generated title).
        $titleOverride = Get-AudioTrackTitleOverride -Language $rawLang -Channels $outChannels -AudioOverride $audioOverride
        if (-not [string]::IsNullOrWhiteSpace($titleOverride)) { $title = $titleOverride }
        $codecArgs.AddRange([string[]]@("-metadata:s:a:$outOrdinal","title=$title"))

        Write-Log "Audio $i -> out:$outOrdinal title: '$title'" "DEBUG"

        $audioTrackMeta.Add([pscustomobject]@{
            Index          = $outOrdinal
            NormalizedLang = Normalize-AudioLanguagePreferenceValue $rawLang
            IsCommentary   = $isCommentary
            IsForced        = $isForcedAudio
            FidelityScore  = Get-AudioFidelityScore -Codec $codec -Channels $ch
            PreferenceRank = [int]::MaxValue
        }) | Out-Null
        $audioDecisionRecords.Add([pscustomobject]@{
            audio_ordinal       = $outOrdinal
            source_stream_index = if ($null -ne $s.PSObject.Properties['index']) { $s.index } else { $null }
            action              = $action
            reason              = $reason
            passthrough_profile = Get-EffectiveAudioPassthroughProfile
            language            = $rawLang
            normalized_language = Normalize-AudioLanguagePreferenceValue $rawLang
            source_codec        = $codec
            source_channels     = $ch
            output_codec        = $outputCodec
            output_channels     = $outChannels
            # Suggestion #7 — record the actual per-stream bitrate, not
            # the static configured value, so sidecar audio_decisions
            # accurately reflects what ffmpeg got told.
            bitrate             = if ($action -eq 'transcode') { $effectiveBitrate } else { '' }
            is_default          = $false
            is_forced           = $isForcedAudio
            is_commentary       = $isCommentary
            title               = $title
        }) | Out-Null
        $outOrdinal++
    }

    # If every stream was dropped by the per-file override, honour AllowNoAudio or throw.
    if ($audioTrackMeta.Count -eq 0) {
        $message = "SOURCE_MEDIA_AUDIO_OVERRIDE_STRIPPED: all audio streams dropped by file override for $FilePath"
        if (Get-EffectiveAllowNoAudio) {
            Write-Log "$message; AllowNoAudio is enabled, output will omit audio." "WARN"
            Set-LastAudioDecisionRecords @($audioDecisionRecords)
            return @('-an')
        }
        Write-Log $message "ERROR"
        throw $message
    }

    # Default track selection:
    #   1st choice: first configured preferred language among non-commentary
    #   2nd choice: highest-fidelity non-commentary track
    #   last resort: highest-fidelity track overall if everything is commentary
    $defaultIdx = Get-PreferredDefaultAudioIndex -TrackMetadata @($audioTrackMeta)
    for ($j = 0; $j -lt $audioTrackMeta.Count; $j++) {
        $sourceDisposition = if ($j -lt $audioTrackMeta.Count -and $audioTrackMeta[$j].IsForced) { "forced" } else { "0" }
        $codecArgs.AddRange([string[]]@("-disposition:a:$j",$sourceDisposition))
    }
    $defaultDisposition = if ($defaultIdx -lt $audioTrackMeta.Count -and $audioTrackMeta[$defaultIdx].IsForced) { "default+forced" } else { "default" }
    $codecArgs.AddRange([string[]]@("-disposition:a:$defaultIdx",$defaultDisposition))
    foreach ($record in @($audioDecisionRecords)) {
        if ($null -ne $record -and [int]$record.audio_ordinal -eq $defaultIdx) {
            $record.is_default = $true
        }
    }
    Set-LastAudioDecisionRecords @($audioDecisionRecords)
    # R9 fix — surface the chosen default audio index AND total audio
    # track count so Do-Remux can emit explicit `--default-track aN:yes/no`
    # flags to mkvmerge. ffmpeg's -disposition flags carry through to
    # temp_av and mkvmerge usually preserves them, but making the
    # mkvmerge args explicit removes any dependency on cross-version
    # disposition translation behavior.
    $script:LastAudioDefaultIndex = [int]$defaultIdx
    $script:LastAudioTrackCount   = [int]$audioTrackMeta.Count
    # CPU-A1 — surface the transcode-active flag so Do-Remux's AV stage
    # (which would otherwise be pure stream-copy and I/O bound) can opt
    # into BelowNormal priority + CPU mutex when audio transcoding is
    # actually happening.
    $script:LastAudioTranscodeActive = [bool]$transcodeActive
    Write-Log "Audio default track: stream $defaultIdx" "DEBUG"
    if ($transcodeActive) {
        Write-Log "Audio: at least one stream will be transcoded; AV stage will run as CPU-bound work" "DEBUG"
    }

    return @($mapArgs) + @($codecArgs)
}
