# ==============================================================================
# engine\audio\audio\stream_decisions.ps1
# ==============================================================================
# Pure audio stream decision-plan helpers. These functions choose kept/dropped
# tracks, output metadata, default dispositions, and diagnostic records before
# Build-AudioArgs emits FFmpeg arguments or mutates audio globals.
# ==============================================================================

function Get-AudioDecisionOutputChannelCount {
    param(
        [Parameter(Mandatory)] [int] $SourceChannels,
        [Parameter(Mandatory)] [string] $DownmixMode,
        [Parameter(Mandatory)] [int] $MaxChannels
    )

    $safeChannels = if ($SourceChannels -gt 0) { $SourceChannels } else { 2 }
    switch ($DownmixMode) {
        'stereo'   { return 2 }
        'preserve' { return $safeChannels }
        default    { return [math]::Min($safeChannels, $MaxChannels) }
    }
}

function Get-AudioDecisionPreferredDefaultIndex {
    param(
        [array] $TrackMetadata,
        [string[]] $PreferredLanguages
    )

    if ($null -eq $TrackMetadata -or $TrackMetadata.Count -eq 0) { return 0 }

    $preferred = @($PreferredLanguages | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    if ($preferred.Count -eq 0) { $preferred = @('eng') }

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

function New-AudioOmitAllDecisionRecord {
    param([Parameter(Mandatory)] [string] $PassthroughProfile)

    return [pscustomobject]@{
        audio_ordinal       = $null
        source_stream_index = $null
        action              = 'omit_all'
        reason              = 'allow_no_audio'
        passthrough_profile = $PassthroughProfile
        language            = 'und'
        source_codec        = ''
        source_channels     = 0
        output_codec        = ''
        output_channels     = 0
        is_default          = $false
        is_forced           = $false
        is_commentary       = $false
        title               = ''
    }
}

function Build-AudioStreamDecisionPlan {
    param(
        [array] $AudioStreams,
        [object] $AudioOverride,
        [string[]] $EffectiveCompatibleAudioCodecs,
        [Parameter(Mandatory)] [string] $PassthroughProfile,
        [Parameter(Mandatory)] [string] $TranscodeCodec,
        [Parameter(Mandatory)] [string] $TranscodeBitrate,
        [Parameter(Mandatory)] [bool] $AutoScaleBitrate,
        [Parameter(Mandatory)] [string] $TranscodeCodecLabel,
        [Parameter(Mandatory)] [string] $DownmixMode,
        [Parameter(Mandatory)] [int] $MaxChannels,
        [string[]] $PreferredLanguages
    )

    $trackDecisions = [System.Collections.Generic.List[object]]::new()
    $audioTrackMeta = [System.Collections.Generic.List[object]]::new()
    $audioDecisionRecords = [System.Collections.Generic.List[object]]::new()
    $transcodeActive = $false

    if (Get-Command -Name Assert-FileOverrideExactTrackSelectorsResolvable -ErrorAction SilentlyContinue) {
        Assert-FileOverrideExactTrackSelectorsResolvable -TrackKind 'audio' -Tracks @($AudioStreams) -OverrideSection $AudioOverride
    }

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

    # Map channel count to a canonical layout tag for transcoded audio.
    # Streamcopy preserves source packets/metadata and intentionally does
    # not receive -channel_layout.
    $LayoutTag = @{
        1 = 'mono';  2 = 'stereo'; 3 = '2.1';      4 = 'quad'
        5 = '4.1';   6 = '5.1';    7 = '6.1';      8 = '7.1'
    }

    # Commentary / descriptive / audio-description detector. Runs against the
    # source title tag. These tracks are preserved but never marked default
    # (a viewer who sets Plex to auto-play English shouldn't hear director
    # commentary by accident).
    $CommentaryRegex = '(?i)commentary|director|cast|audio\s*description|descriptive|behind.the.scenes|isolated\s*score'

    $outOrdinal = 0
    for ($i = 0; $i -lt $AudioStreams.Count; $i++) {
        $s        = $AudioStreams[$i]
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

        $outCh = Get-AudioDecisionOutputChannelCount -SourceChannels $ch -DownmixMode $DownmixMode -MaxChannels $MaxChannels
        $isForcedAudio = $false
        try { $isForcedAudio = ($s.disposition.forced -eq 1) } catch {}

        $isCommentary = ($rawTitle -match $CommentaryRegex)
        $sourceStreamIndex = if ($null -ne $s.PSObject.Properties['index']) { $s.index } else { $null }

        if (-not (Test-AudioTrackKeptByOverride `
                -Language $rawLang `
                -Channels $ch `
                -Title $rawTitle `
                -Codec $codec `
                -StreamIndex $sourceStreamIndex `
                -AudioOverride $AudioOverride)) {
            $audioDecisionRecords.Add([pscustomobject]@{
                audio_ordinal       = $null
                source_stream_index = $sourceStreamIndex
                action              = 'drop'
                reason              = 'file_override'
                passthrough_profile = $PassthroughProfile
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
            $trackDecisions.Add([pscustomobject]@{
                AudioOrdinal      = $null
                SourceOrdinal     = $i
                SourceStreamIndex = $sourceStreamIndex
                Action            = 'drop'
                Reason            = 'file_override'
                Language          = $rawLang
                SourceCodec       = $codec
                SourceChannels    = $ch
                OutputCodec       = ''
                OutputCodecLabel  = ''
                OutputChannels    = 0
                Bitrate           = ''
                BitrateSource     = ''
                IsForced          = $isForcedAudio
                IsCommentary      = $isCommentary
                Title             = $rawTitle
                ChannelLayout     = ''
            }) | Out-Null
            continue
        }

        $standardizePcm = Test-IsPcmAudioCodec $codec
        if ($standardizePcm -or $codec -notin $EffectiveCompatibleAudioCodecs) {
            $effectiveBitrate = if ($AutoScaleBitrate) {
                Get-AudioTranscodeBitrateForChannels -Codec $TranscodeCodec -Channels $outCh
            } else {
                $TranscodeBitrate
            }
            $outCodecLabel = $TranscodeCodecLabel
            $outChannels   = $outCh
            $reason = if ($standardizePcm) { 'PCM standardization' } else { 'codec outside compatibility list' }
            $action = 'transcode'
            $outputCodec = $TranscodeCodec
            $transcodeActive = $true
            $bitrateSource = if ($AutoScaleBitrate) { 'channel-scaled' } else { 'configured' }
            $channelLayout = if ($LayoutTag.ContainsKey($outCh)) { $LayoutTag[$outCh] } else { '' }
        } else {
            $outCodecLabel = Get-MediaAudioCodecDisplayLabel -Codec $codec
            $outChannels = $ch
            $reason = 'codec compatible'
            $action = 'copy'
            $outputCodec = $codec
            $effectiveBitrate = ''
            $bitrateSource = ''
            $channelLayout = ''
        }

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
        $titleOverride = Get-AudioTrackTitleOverride -Language $rawLang -Channels $outChannels -AudioOverride $AudioOverride
        if (-not [string]::IsNullOrWhiteSpace($titleOverride)) { $title = $titleOverride }

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
            source_stream_index = $sourceStreamIndex
            action              = $action
            reason              = $reason
            passthrough_profile = $PassthroughProfile
            language            = $rawLang
            normalized_language = Normalize-AudioLanguagePreferenceValue $rawLang
            source_codec        = $codec
            source_channels     = $ch
            output_codec        = $outputCodec
            output_channels     = $outChannels
            bitrate             = if ($action -eq 'transcode') { $effectiveBitrate } else { '' }
            is_default          = $false
            is_forced           = $isForcedAudio
            is_commentary       = $isCommentary
            title               = $title
        }) | Out-Null
        $trackDecisions.Add([pscustomobject]@{
            AudioOrdinal      = $outOrdinal
            SourceOrdinal     = $i
            SourceStreamIndex = $sourceStreamIndex
            Action            = $action
            Reason            = $reason
            Language          = $rawLang
            SourceCodec       = $codec
            SourceChannels    = $ch
            OutputCodec       = $outputCodec
            OutputCodecLabel  = $outCodecLabel
            OutputChannels    = $outChannels
            Bitrate           = $effectiveBitrate
            BitrateSource     = $bitrateSource
            IsForced          = $isForcedAudio
            IsCommentary      = $isCommentary
            Title             = $title
            ChannelLayout     = $channelLayout
        }) | Out-Null
        $outOrdinal++
    }

    $defaultIdx = 0
    $dispositions = [System.Collections.Generic.List[object]]::new()
    if ($audioTrackMeta.Count -gt 0) {
        $defaultIdx = Get-AudioDecisionPreferredDefaultIndex -TrackMetadata @($audioTrackMeta) -PreferredLanguages $PreferredLanguages
        for ($j = 0; $j -lt $audioTrackMeta.Count; $j++) {
            $sourceDisposition = if ($j -lt $audioTrackMeta.Count -and $audioTrackMeta[$j].IsForced) { "forced" } else { "0" }
            $dispositions.Add([pscustomobject]@{
                AudioOrdinal = $j
                Value        = $sourceDisposition
            }) | Out-Null
        }
        $defaultDisposition = if ($defaultIdx -lt $audioTrackMeta.Count -and $audioTrackMeta[$defaultIdx].IsForced) { "default+forced" } else { "default" }
        $dispositions.Add([pscustomobject]@{
            AudioOrdinal = $defaultIdx
            Value        = $defaultDisposition
        }) | Out-Null
        foreach ($record in @($audioDecisionRecords)) {
            if ($null -ne $record -and [int]$record.audio_ordinal -eq $defaultIdx) {
                $record.is_default = $true
            }
        }
    }

    return [pscustomobject]@{
        Tracks          = @($trackDecisions)
        ChosenTracks    = @($trackDecisions | Where-Object { $null -ne $_.AudioOrdinal })
        TrackMetadata   = @($audioTrackMeta)
        Records         = @($audioDecisionRecords)
        Dispositions    = @($dispositions)
        DefaultIndex    = [int]$defaultIdx
        TrackCount      = [int]$audioTrackMeta.Count
        TranscodeActive = [bool]$transcodeActive
    }
}
