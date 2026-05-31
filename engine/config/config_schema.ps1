# ==============================================================================
# engine\config\config_schema.ps1
# ==============================================================================
# Compatibility metadata for the live PSD1 config format. This is intentionally
# small: it centralizes schema version, required keys, array coercion keys, and
# stable output order while preserving the current Import-PowerShellDataFile flow.
# ==============================================================================

function Get-MediaPipelineConfigCurrentSchemaVersion {
    return 1
}

function Get-MediaPipelineConfigSchemaKey {
    return 'ConfigSchemaVersion'
}

function Get-MediaPipelineConfigRequiredKeys {
    return @(
        'SourceMovies','SourceTV','Outsource','LocalBase',
        'EncodeThresholdGB','TVEncodeThresholdGB','MinFreeSpaceGB',
        'VideoCodec','VideoPreset','VideoQuality','OutputContainer',
        'CompatibleAudioCodecs','SubKeepLanguages','SubSDHTitleKeywords',
        'SubSupplementalKeywords','DropAssAfterConversion','RemuxSafeVideoCodecs',
        'ValidExtensions','FileStabilityWait','EnableIntegrityCheck',
        'CreateTVSubfolder','RobocopyFlags','DebugMode','SkipStabilityCheck'
    )
}

function Get-MediaPipelineConfigArrayKeys {
    return @(
        'ExtraVideoFlags','CompatibleAudioCodecs','SubKeepLanguages',
        'SubSDHTitleKeywords','SubSupplementalKeywords','Tx3gExtractLanguages','BdpgsExtractLanguages','VobSubExtractLanguages',
        'PreferredDefaultAudioLanguages','RemuxSafeVideoCodecs',
        'ValidExtensions','RobocopyFlags','PriorityMarkers',
        'ExcludeSubtitleStyles','IncludeSubtitleStyles',
        'FinalLibraryPromotionRules','LibraryProfiles'
    )
}

function Get-MediaPipelineConfigLibraryOverrideKeysByGroup {
    return [ordered]@{
        editor = @(
            'RoutingProfile',
            'RouteThresholdMode',
            'SizeGuardMode',
            'EncodeTuningPreset',
            'EncodeLadder',
            'VideoCodec',
            'OutputContainer',
            'EncodeThresholdGB',
            'TVEncodeThresholdGB',
            'MovieRouteMaxVideoBitrateMbps',
            'TVRouteMaxVideoBitrateMbps',
            'MaxEncodeGrowthPercent',
            'CompatibilityEncodeGrowthPercent'
        )
        video = @(
            'VideoPreset',
            'VideoQuality',
            'AllowH264RemuxIfPlexCompatible',
            'H264RemuxMaxBitrateMbps',
            'H264RemuxMaxHeight',
            'RemuxSafeVideoCodecs',
            'FallbackCpuQuality',
            'CpuEncodePreset',
            'CpuEncodeProcessPriority',
            'CpuEncodeMaxThreads',
            'ExtraVideoFlags'
        )
        subtitles = @(
            'SubKeepLanguages',
            'ConvertTx3gToSrt',
            'DropTx3gAfterConversion',
            'CreateExternalTx3gSrtSidecars',
            'Tx3gExtractLanguages',
            'Tx3gPreserveExistingSrt',
            'Tx3gTreatForcedAsSeparate',
            'ConvertBdpgsToSrt',
            'DropBdpgsAfterConversion',
            'BdpgsExtractLanguages',
            'BdpgsOcrToolPath',
            'BdpgsOcrTessdataPath',
            'ConvertVobSubToSrt',
            'DropVobSubAfterConversion',
            'VobSubExtractLanguages',
            'VobSubOcrToolPath',
            'SubtitleExtractTimeoutSeconds',
            'SubtitleProbeTimeoutSeconds',
            'BdpgsOcrTimeoutSeconds',
            'VobSubOcrTimeoutSeconds',
            'SubSDHTitleKeywords',
            'SubSupplementalKeywords',
            'DropAssAfterConversion',
            'StripFormatting',
            'RemoveKaraoke',
            'MergeAdjacent',
            'MergeThresholdMs',
            'KeepSignsAndSongs',
            'TreatAssSignsSongsAsForced',
            'TreatTx3gSignsSongsAsForced',
            'TreatBdpgsSignsSongsAsForced',
            'TreatVobSubSignsSongsAsForced',
            'ExcludeSubtitleStyles',
            'IncludeSubtitleStyles'
        )
        audio = @(
            'AudioPassthroughProfile',
            'CompatibleAudioCodecs',
            'PreferredDefaultAudioLanguages',
            'AudioTranscodeCodec',
            'AudioTranscodeBitrate',
            'AudioTranscodeAutoBitrateByChannels',
            'AudioDownmixMode',
            'AudioMaxChannels',
            'AllowNoAudio'
        )
    }
}

function Get-MediaPipelineConfigLibraryOverrideKeys {
    $keys = New-Object System.Collections.Generic.List[string]
    $groups = Get-MediaPipelineConfigLibraryOverrideKeysByGroup
    foreach ($group in @('editor','video','subtitles','audio')) {
        foreach ($key in @($groups[$group])) {
            [void]$keys.Add([string]$key)
        }
    }
    return @($keys)
}

function Get-MediaPipelineConfigOrderedKeys {
    return @(
        'ConfigSchemaVersion',
        'SourceMovies','SourceTV','Outsource','LibraryProfiles','LocalBase',
        'EncodeThresholdGB','TVEncodeThresholdGB',
        'RoutingProfile','RouteThresholdMode','MovieRouteMaxVideoBitrateMbps','TVRouteMaxVideoBitrateMbps',
        'AllowH264RemuxIfPlexCompatible','H264RemuxMaxBitrateMbps','H264RemuxMaxHeight',
        'SizeGuardMode','MaxEncodeGrowthPercent','CompatibilityEncodeGrowthPercent',
        'MinFreeSpaceGB','OutsourceMinFreeSpaceGB',
        'DeferredPublish',
        'FinalLibraryPromotionEnabled','FinalLibraryPromotionRules','FinalLibraryPromotionVerificationMode',
        'FinalLibraryPromotionCleanupAfterVerified','FinalLibraryPromotionOverwriteExisting',
        'VideoCodec','VideoPreset','VideoQuality','OutputContainer','EncodeTuningPreset','EncodeLadder','ExtraVideoFlags',
        'AudioPassthroughProfile','CompatibleAudioCodecs','PreferredDefaultAudioLanguages',
        'AudioTranscodeCodec','AudioTranscodeBitrate','AudioTranscodeAutoBitrateByChannels','AudioDownmixMode','AudioMaxChannels','AllowNoAudio',
        'SubKeepLanguages','ConvertTx3gToSrt','DropTx3gAfterConversion','CreateExternalTx3gSrtSidecars',
        'Tx3gExtractLanguages','Tx3gPreserveExistingSrt','Tx3gTreatForcedAsSeparate',
        'ConvertBdpgsToSrt','DropBdpgsAfterConversion','BdpgsExtractLanguages','BdpgsOcrToolPath','BdpgsOcrTessdataPath',
        'ConvertVobSubToSrt','DropVobSubAfterConversion','VobSubExtractLanguages','VobSubOcrToolPath',
        'SubSDHTitleKeywords','SubSupplementalKeywords',
        'DropAssAfterConversion','StripFormatting','RemoveKaraoke',
        'MergeAdjacent','MergeThresholdMs','KeepSignsAndSongs','TreatAssSignsSongsAsForced','TreatTx3gSignsSongsAsForced','TreatBdpgsSignsSongsAsForced','TreatVobSubSignsSongsAsForced',
        'ExcludeSubtitleStyles','IncludeSubtitleStyles',
        'RemuxSafeVideoCodecs',
        'ValidExtensions','FileStabilityWait','SkipStabilityCheck',
        'EnableIntegrityCheck','CreateTVSubfolder','AggressiveEpisodeParsing',
        'RobocopyFlags',
        'DebugMode','LogRetentionDays','PriorityMarkers','MixPriorityPhase','QueueOrderingStrategy','ConsoleLogLevel','FileLogLevel',
        'MaxParallelEncodes','ParallelEncodeMode',
        'FallbackCpuQuality','CpuEncodePreset','CpuEncodeProcessPriority','CpuEncodeMaxThreads','OutputSizeMultiplier',
        'FFmpegEncodeTimeoutSeconds','FFmpegCpuEncodeTimeoutSeconds','FFmpegRemuxTimeoutSeconds','MkvmergeRemuxTimeoutSeconds','SubtitleExtractTimeoutSeconds','SubtitleProbeTimeoutSeconds','BdpgsOcrTimeoutSeconds','VobSubOcrTimeoutSeconds',
        'OutputValidationProbeTimeoutSeconds','OutputValidationMinSizeBytes','OutputValidationDurationToleranceSeconds',
        'AllowSystemTools','RobocopyTimeoutSeconds','TransientFailureRetryLimit',
        'IndexScanTimeoutSeconds','SourceScanTimeoutSeconds','CleanupScanTimeoutSeconds',
        'CleanupRemoteStaging','CleanupStaleAgeHours',
        'SourceScanIntervalSeconds','ProcessedIndexRefreshSeconds',
        'MinPipelineVersion','ReprocessAll',
        'ShowOverrides'
    )
}

function Get-MediaPipelineConfigExtraVideoFlagsDefault {
    param([string] $Codec)

    if ($Codec -eq 'hevc_nvenc') {
        return @(
            '-rc','vbr',
            '-rc-lookahead','60',
            '-spatial-aq','1',
            '-temporal-aq','1',
            '-aq-strength','8',
            '-multipass','fullres',
            '-bf','4',
            '-tune','hq'
        )
    }
    return @()
}

function Get-MediaPipelineVideoCodecNames {
    return @('hevc_nvenc','libx265','h264_nvenc','libx264','av1_nvenc')
}

function Get-MediaPipelineVideoPresetNames {
    return @('p1','p2','p3','p4','p5','p6','p7')
}

function Get-MediaPipelineOutputContainerNames {
    return @('mkv','mp4')
}

function Get-MediaPipelineEncodeTuningPresetNames {
    return @(
        'balanced_nvenc',
        'quality_nvenc',
        'fast_nvenc',
        'compatibility',
        'custom_legacy_flags'
    )
}

function Get-MediaPipelineEncodeTuningPresetDefault {
    return 'balanced_nvenc'
}

function Get-MediaPipelineCpuEncodePresetNames {
    # libx265 preset slugs accepted by `-preset`. Ordered from fastest to slowest.
    return @(
        'ultrafast','superfast','veryfast','faster','fast',
        'medium','slow','slower','veryslow','placebo'
    )
}

function Get-MediaPipelineCpuEncodePresetDefault {
    return 'medium'
}

function Resolve-MediaPipelineCpuEncodePreset {
    param([string] $Preset)
    $normalized = if ($Preset) { $Preset.Trim().ToLowerInvariant() } else { '' }
    if ([string]::IsNullOrWhiteSpace($normalized)) { return Get-MediaPipelineCpuEncodePresetDefault }
    if ($normalized -in (Get-MediaPipelineCpuEncodePresetNames)) { return $normalized }
    return Get-MediaPipelineCpuEncodePresetDefault
}

function Get-MediaPipelineCpuEncodeProcessPriorityNames {
    # Mirrors System.Diagnostics.ProcessPriorityClass with 'inherit' meaning leave alone.
    return @('inherit','idle','belownormal','normal','abovenormal','high')
}

function Get-MediaPipelineCpuEncodeProcessPriorityDefault {
    return 'belownormal'
}

function Resolve-MediaPipelineCpuEncodeProcessPriority {
    param([string] $Priority)
    $normalized = if ($Priority) { $Priority.Trim().ToLowerInvariant() } else { '' }
    if ([string]::IsNullOrWhiteSpace($normalized)) { return Get-MediaPipelineCpuEncodeProcessPriorityDefault }
    if ($normalized -in (Get-MediaPipelineCpuEncodeProcessPriorityNames)) { return $normalized }
    return Get-MediaPipelineCpuEncodeProcessPriorityDefault
}

function Get-MediaPipelineEncodeLadderNames {
    return @(
        'auto',
        'tv_balanced',
        'tv_space_saver',
        'movie_balanced',
        'movie_archive',
        'plex_compat'
    )
}

function Get-MediaPipelineEncodeLadderDefault {
    return 'auto'
}

function Get-MediaPipelineRoutingProfileNames {
    return @(
        'plex_direct_stream',
        'plex_direct_play',
        'archive_shrink',
        'archive_quality',
        'manual'
    )
}

function Get-MediaPipelineRoutingProfileDefault {
    return 'plex_direct_stream'
}

function Get-MediaPipelineRouteThresholdModeNames {
    return @(
        'compatibility_advisory',
        'size',
        'bitrate',
        'size_or_bitrate'
    )
}

function Get-MediaPipelineRouteThresholdModeDefault {
    return 'compatibility_advisory'
}

function Get-MediaPipelineSizeGuardModeNames {
    return @(
        'advisory',
        'strict',
        'off'
    )
}

function Get-MediaPipelineSizeGuardModeDefault {
    return 'advisory'
}

function Get-MediaPipelineFinalLibraryPromotionVerificationModeNames {
    return @('fast','cautious')
}

function Get-MediaPipelineAudioPassthroughProfileNames {
    return @(
        'plex_balanced',
        'compatibility',
        'lossless_passthrough',
        'custom_codec_list'
    )
}

function Get-MediaPipelineAudioPassthroughProfileDefault {
    return 'plex_balanced'
}

function Get-MediaPipelineAudioTranscodeCodecNames {
    return @('eac3','ac3','aac')
}

function Get-MediaPipelineAudioDownmixModeNames {
    return @('preserve','max_channels','stereo')
}

function Resolve-MediaPipelineAudioPassthroughProfile {
    param(
        [string] $Profile,
        [array] $LegacyCompatibleAudioCodecs = @()
    )

    $normalized = if ($Profile) { $Profile.Trim().ToLowerInvariant() } else { '' }
    if ([string]::IsNullOrWhiteSpace($normalized)) {
        if (@($LegacyCompatibleAudioCodecs).Count -gt 0) { return 'custom_codec_list' }
        return Get-MediaPipelineAudioPassthroughProfileDefault
    }
    if ($normalized -in (Get-MediaPipelineAudioPassthroughProfileNames)) {
        return $normalized
    }
    return Get-MediaPipelineAudioPassthroughProfileDefault
}

function Get-MediaPipelineAudioPassthroughProfileCodecs {
    param([string] $Profile)

    switch (Resolve-MediaPipelineAudioPassthroughProfile -Profile $Profile) {
        'compatibility' {
            return @('aac','ac3','eac3','mp3','opus','vorbis')
        }
        'lossless_passthrough' {
            return @('aac','ac3','eac3','mp3','opus','vorbis','truehd','mlp','dts','dts_hd_ma','dts-hd','flac','alac')
        }
        'custom_codec_list' {
            return @()
        }
        default {
            return @('aac','ac3','eac3','mp3','opus','vorbis','truehd','mlp')
        }
    }
}

function Resolve-MediaPipelineEncodeLadder {
    param([string] $Ladder)

    $normalized = if ($Ladder) { $Ladder.Trim().ToLowerInvariant() } else { '' }
    if ([string]::IsNullOrWhiteSpace($normalized)) {
        return Get-MediaPipelineEncodeLadderDefault
    }
    if ($normalized -in (Get-MediaPipelineEncodeLadderNames)) {
        return $normalized
    }
    return Get-MediaPipelineEncodeLadderDefault
}

function Resolve-MediaPipelineRoutingProfile {
    param([string] $Profile)

    $normalized = if ($Profile) { $Profile.Trim().ToLowerInvariant() } else { '' }
    if ([string]::IsNullOrWhiteSpace($normalized)) {
        return Get-MediaPipelineRoutingProfileDefault
    }
    if ($normalized -in (Get-MediaPipelineRoutingProfileNames)) {
        return $normalized
    }
    return Get-MediaPipelineRoutingProfileDefault
}

function Resolve-MediaPipelineRouteThresholdMode {
    param([string] $Mode)

    $normalized = if ($Mode) { $Mode.Trim().ToLowerInvariant() } else { '' }
    if ([string]::IsNullOrWhiteSpace($normalized)) {
        return Get-MediaPipelineRouteThresholdModeDefault
    }
    if ($normalized -in (Get-MediaPipelineRouteThresholdModeNames)) {
        return $normalized
    }
    return Get-MediaPipelineRouteThresholdModeDefault
}

function Resolve-MediaPipelineSizeGuardMode {
    param([string] $Mode)

    $normalized = if ($Mode) { $Mode.Trim().ToLowerInvariant() } else { '' }
    if ([string]::IsNullOrWhiteSpace($normalized)) {
        return Get-MediaPipelineSizeGuardModeDefault
    }
    if ($normalized -in (Get-MediaPipelineSizeGuardModeNames)) {
        return $normalized
    }
    return Get-MediaPipelineSizeGuardModeDefault
}

function Get-MediaPipelineParallelEncodeModeNames {
    return @('single','local_worker_slots')
}

function Get-MediaPipelineParallelEncodeModeDefault {
    return 'single'
}

function Resolve-MediaPipelineParallelEncodeMode {
    param([string] $Mode)

    $normalized = if ($Mode) { $Mode.Trim().ToLowerInvariant() } else { '' }
    if ([string]::IsNullOrWhiteSpace($normalized)) {
        return Get-MediaPipelineParallelEncodeModeDefault
    }
    if ($normalized -in (Get-MediaPipelineParallelEncodeModeNames)) {
        return $normalized
    }
    return Get-MediaPipelineParallelEncodeModeDefault
}

function Resolve-MediaPipelineEncodeTuningPreset {
    param(
        [string] $Preset,
        [array] $LegacyExtraVideoFlags = @()
    )

    $normalized = if ($Preset) { $Preset.Trim().ToLowerInvariant() } else { '' }
    if ([string]::IsNullOrWhiteSpace($normalized)) {
        if (@($LegacyExtraVideoFlags).Count -gt 0) { return 'custom_legacy_flags' }
        return Get-MediaPipelineEncodeTuningPresetDefault
    }

    if ($normalized -in (Get-MediaPipelineEncodeTuningPresetNames)) {
        return $normalized
    }
    return Get-MediaPipelineEncodeTuningPresetDefault
}

function Get-MediaPipelineEncodeTuningFlags {
    param(
        [string] $Preset,
        [string] $Codec,
        [array] $LegacyExtraVideoFlags = @()
    )

    $resolvedPreset = Resolve-MediaPipelineEncodeTuningPreset -Preset $Preset -LegacyExtraVideoFlags $LegacyExtraVideoFlags
    if ($resolvedPreset -eq 'custom_legacy_flags') {
        return @($LegacyExtraVideoFlags)
    }

    $codecText = if ($Codec) { $Codec.Trim().ToLowerInvariant() } else { '' }
    if ($codecText -notmatch 'nvenc') { return @() }

    switch ($resolvedPreset) {
        'quality_nvenc' {
            return @(
                '-rc','vbr',
                '-rc-lookahead','60',
                '-spatial-aq','1',
                '-temporal-aq','1',
                '-aq-strength','10',
                '-multipass','fullres',
                '-bf','4',
                '-tune','hq'
            )
        }
        'fast_nvenc' {
            return @(
                '-rc','vbr',
                '-rc-lookahead','20',
                '-spatial-aq','1',
                '-temporal-aq','0',
                '-aq-strength','6',
                '-multipass','disabled',
                '-bf','2',
                '-tune','ll'
            )
        }
        'compatibility' {
            return @(
                '-rc','vbr',
                '-spatial-aq','1',
                '-aq-strength','6',
                '-bf','2'
            )
        }
        default {
            return Get-MediaPipelineConfigExtraVideoFlagsDefault -Codec $Codec
        }
    }
}

function Get-MediaPipelineConfigDefaultValues {
    $videosRoot = Join-Path -Path 'C:\' -ChildPath 'Videos'
    $incomingRoot = Join-Path -Path $videosRoot -ChildPath 'Incoming'

    [ordered]@{
        ConfigSchemaVersion      = Get-MediaPipelineConfigCurrentSchemaVersion
        SourceMovies               = Join-Path -Path $incomingRoot -ChildPath 'Movies'
        SourceTV                   = Join-Path -Path $incomingRoot -ChildPath 'TV'
        Outsource                  = Join-Path -Path $videosRoot -ChildPath 'Processed'
        LibraryProfiles            = @(
            [ordered]@{
                id = 'movies'
                name = 'Movies'
                enabled = $true
                designation = 'movie'
                source_path = Join-Path -Path $incomingRoot -ChildPath 'Movies'
                output_path = Join-Path -Path $videosRoot -ChildPath 'Processed'
                promotion_enabled = $false
                promotion_destination = ''
                overrides = [ordered]@{
                    editor = [ordered]@{}
                    video = [ordered]@{}
                    subtitles = [ordered]@{}
                    audio = [ordered]@{}
                }
                default_tracking = [ordered]@{
                    schema_version = 'library_profile_default_tracking.v1'
                    inherited_fields = @('source_path','output_path')
                    field_default_keys = [ordered]@{ source_path = 'SourceMovies'; output_path = 'Outsource' }
                }
            },
            [ordered]@{
                id = 'tv'
                name = 'TV'
                enabled = $true
                designation = 'tv'
                source_path = Join-Path -Path $incomingRoot -ChildPath 'TV'
                output_path = Join-Path -Path $videosRoot -ChildPath 'Processed'
                promotion_enabled = $false
                promotion_destination = ''
                overrides = [ordered]@{
                    editor = [ordered]@{}
                    video = [ordered]@{}
                    subtitles = [ordered]@{}
                    audio = [ordered]@{}
                }
                default_tracking = [ordered]@{
                    schema_version = 'library_profile_default_tracking.v1'
                    inherited_fields = @('source_path','output_path')
                    field_default_keys = [ordered]@{ source_path = 'SourceTV'; output_path = 'Outsource' }
                }
            }
        )
        LocalBase                  = Join-Path -Path $videosRoot -ChildPath 'Scratch'
        EncodeThresholdGB          = 8
        TVEncodeThresholdGB        = 3
        RoutingProfile             = Get-MediaPipelineRoutingProfileDefault
        RouteThresholdMode         = Get-MediaPipelineRouteThresholdModeDefault
        MovieRouteMaxVideoBitrateMbps = 35
        TVRouteMaxVideoBitrateMbps = 18
        AllowH264RemuxIfPlexCompatible = $true
        H264RemuxMaxBitrateMbps    = 35
        H264RemuxMaxHeight         = 1080
        SizeGuardMode              = Get-MediaPipelineSizeGuardModeDefault
        MaxEncodeGrowthPercent     = 5
        CompatibilityEncodeGrowthPercent = 15
        MinFreeSpaceGB             = 50
        OutsourceMinFreeSpaceGB    = 50
        DeferredPublish            = $false
        FinalLibraryPromotionEnabled = $false
        FinalLibraryPromotionRules = @()
        FinalLibraryPromotionVerificationMode = 'cautious'
        FinalLibraryPromotionCleanupAfterVerified = $false
        FinalLibraryPromotionOverwriteExisting = $false
        VideoCodec                 = 'hevc_nvenc'
        VideoPreset                = 'p7'
        VideoQuality               = 22
        OutputContainer            = 'mkv'
        EncodeTuningPreset         = Get-MediaPipelineEncodeTuningPresetDefault
        EncodeLadder               = Get-MediaPipelineEncodeLadderDefault
        ExtraVideoFlags            = Get-MediaPipelineConfigExtraVideoFlagsDefault -Codec 'hevc_nvenc'
        AudioPassthroughProfile    = Get-MediaPipelineAudioPassthroughProfileDefault
        CompatibleAudioCodecs      = @('aac','ac3','eac3','mp3','opus','vorbis','truehd','mlp')
        PreferredDefaultAudioLanguages = @('english')
        AudioTranscodeCodec        = 'eac3'
        AudioTranscodeBitrate      = '640k'
        AudioTranscodeAutoBitrateByChannels = $false
        AudioDownmixMode           = 'max_channels'
        AudioMaxChannels           = 6
        AllowNoAudio               = $false
        SubKeepLanguages           = @('eng','en','und','')
        ConvertTx3gToSrt           = $true
        DropTx3gAfterConversion    = $false
        CreateExternalTx3gSrtSidecars = $false
        Tx3gExtractLanguages       = @('eng','en','und')
        Tx3gPreserveExistingSrt    = $true
        Tx3gTreatForcedAsSeparate  = $true
        ConvertBdpgsToSrt          = $false
        DropBdpgsAfterConversion   = $false
        BdpgsExtractLanguages      = @('eng','en','und')
        BdpgsOcrToolPath           = 'Tools\PgsToSrt\PgsToSrt.exe'
        BdpgsOcrTessdataPath       = 'Tools\PgsToSrt\tessdata'
        ConvertVobSubToSrt         = $false
        DropVobSubAfterConversion  = $false
        VobSubExtractLanguages     = @('eng','en','und')
        VobSubOcrToolPath          = 'Tools\SubtitleEdit\seconv.exe'
        SubSDHTitleKeywords        = @('sdh','hearing impaired','hearing-impaired','cc','closed caption','closedcaption')
        SubSupplementalKeywords    = @('sign','song','karaoke','chapter','opening','ending')
        DropAssAfterConversion     = $false
        StripFormatting            = $true
        RemoveKaraoke              = $true
        MergeAdjacent              = $true
        MergeThresholdMs           = 150
        KeepSignsAndSongs          = $true
        TreatAssSignsSongsAsForced = $false
        TreatTx3gSignsSongsAsForced = $false
        TreatBdpgsSignsSongsAsForced = $false
        TreatVobSubSignsSongsAsForced = $false
        ExcludeSubtitleStyles      = @(
            'Sign','Sign *','Sign-*',
            'Signs','Signs *','Signs-*',
            'OP','OP *','OP-*','OP_*','Opening*',
            'ED','ED *','ED-*','ED_*','Ending*',
            '*Lyrics*','*Romaji*','*Kanji*',
            'Song','Song *','Song-*',
            'Title','Show Title','Episode Title',
            'Next Episode','Next *',
            'Credits','Credit*',
            'Note','Note*',
            'Caption','Caption*',
            'fs'
        )
        IncludeSubtitleStyles      = @()
        RemuxSafeVideoCodecs       = @('hevc','h265','h.265')
        ValidExtensions            = @('.mkv','.mp4','.avi','.mov','.m4v','.ts','.m2ts')
        FileStabilityWait          = 15
        SkipStabilityCheck         = $false
        EnableIntegrityCheck       = $true
        CreateTVSubfolder          = $true
        AggressiveEpisodeParsing   = $false
        RobocopyFlags              = @('/J','/R:3','/W:15','/MT:2','/NP','/NDL','/NFL')
        DebugMode                  = $true
        LogRetentionDays           = 7
        PriorityMarkers            = @('!','[NOW]')
        MaxParallelEncodes         = 1
        ParallelEncodeMode         = Get-MediaPipelineParallelEncodeModeDefault
        FallbackCpuQuality         = 20
        CpuEncodePreset            = Get-MediaPipelineCpuEncodePresetDefault
        CpuEncodeProcessPriority   = Get-MediaPipelineCpuEncodeProcessPriorityDefault
        CpuEncodeMaxThreads        = 0
        OutputSizeMultiplier       = 0.7
        FFmpegEncodeTimeoutSeconds = 21600
        FFmpegCpuEncodeTimeoutSeconds = 43200
        FFmpegRemuxTimeoutSeconds  = 7200
        MkvmergeRemuxTimeoutSeconds = 7200
        SubtitleExtractTimeoutSeconds = 180
        SubtitleProbeTimeoutSeconds   = 30
        BdpgsOcrTimeoutSeconds        = 1800
        VobSubOcrTimeoutSeconds       = 1800
        OutputValidationProbeTimeoutSeconds = 60
        OutputValidationMinSizeBytes = 1024
        OutputValidationDurationToleranceSeconds = 2
        AllowSystemTools           = $false
        RobocopyTimeoutSeconds     = 14400
        TransientFailureRetryLimit  = 3
        SourceScanTimeoutSeconds   = 1800
        IndexScanTimeoutSeconds    = 1800
        CleanupScanTimeoutSeconds  = 300
        CleanupRemoteStaging       = $false
        CleanupStaleAgeHours       = 24
        SourceScanIntervalSeconds  = 300
        ProcessedIndexRefreshSeconds = 900
        ReprocessAll               = $false
    }
}

function Get-MediaPipelineConfigValue {
    param(
        [Parameter(Mandatory)] $Config,
        [Parameter(Mandatory)] [string] $Key
    )

    if ($Config -is [System.Collections.IDictionary] -and $Config.Contains($Key)) {
        return $Config[$Key]
    }
    $prop = $Config.PSObject.Properties[$Key]
    if ($prop) { return $prop.Value }
    return $null
}

function Test-MediaPipelineConfigHasKey {
    param(
        [Parameter(Mandatory)] $Config,
        [Parameter(Mandatory)] [string] $Key
    )

    if ($Config -is [System.Collections.IDictionary]) {
        return $Config.Contains($Key)
    }
    return $null -ne $Config.PSObject.Properties[$Key]
}

function ConvertTo-MediaPipelineConfigBool {
    param(
        [Parameter(Mandatory)] $Config,
        [Parameter(Mandatory)] [string] $Key,
        [bool] $Default = $false
    )

    if (-not (Test-MediaPipelineConfigHasKey -Config $Config -Key $Key)) { return $Default }
    $value = Get-MediaPipelineConfigValue -Config $Config -Key $Key
    if ($value -is [bool]) { return [bool]$value }
    if ($null -eq $value) { return $Default }
    $text = ([string]$value).Trim().ToLowerInvariant()
    if ($text -in @('true','1','yes','y','on')) { return $true }
    if ($text -in @('false','0','no','n','off')) { return $false }
    return $Default
}

function ConvertTo-MediaPipelineConfigMap {
    param($Value)

    $map = [ordered]@{}
    if ($null -eq $Value) { return $map }
    if ($Value -is [System.Collections.IDictionary]) {
        foreach ($key in $Value.Keys) {
            if ($null -ne $key) { $map[[string]$key] = $Value[$key] }
        }
        return $map
    }
    foreach ($property in @($Value.PSObject.Properties)) {
        if ($property -and -not [string]::IsNullOrWhiteSpace([string]$property.Name)) {
            $map[[string]$property.Name] = $property.Value
        }
    }
    return $map
}

function Test-MediaPipelineConfigChoiceValue {
    param(
        [Parameter(Mandatory)] $Config,
        [Parameter(Mandatory)] [string] $Key,
        [Parameter(Mandatory)] [string] $Label,
        [Parameter(Mandatory)] [array] $AllowedValues,
        [switch] $AllowBlank,
        [System.Collections.Generic.List[string]] $Errors
    )

    if (-not (Test-MediaPipelineConfigHasKey -Config $Config -Key $Key)) { return }
    $raw = Get-MediaPipelineConfigValue -Config $Config -Key $Key
    $value = ([string]$raw).Trim().ToLowerInvariant()
    if ($AllowBlank -and [string]::IsNullOrWhiteSpace($value)) { return }
    $allowed = @($AllowedValues | ForEach-Object { ([string]$_).Trim().ToLowerInvariant() })
    if ($value -notin $allowed) {
        $Errors.Add("$Label must be one of: $($allowed -join ', ').")
    }
}

function Test-MediaPipelineConfigIntegerRange {
    param(
        [Parameter(Mandatory)] $Config,
        [Parameter(Mandatory)] [string] $Key,
        [Parameter(Mandatory)] [string] $Label,
        [Nullable[int64]] $Minimum = $null,
        [Nullable[int64]] $Maximum = $null,
        [switch] $Optional,
        [System.Collections.Generic.List[string]] $Errors
    )

    if (-not (Test-MediaPipelineConfigHasKey -Config $Config -Key $Key)) { return }
    $raw = Get-MediaPipelineConfigValue -Config $Config -Key $Key
    if ($Optional -and ($null -eq $raw -or [string]::IsNullOrWhiteSpace([string]$raw))) { return }
    if (-not ($raw -is [byte] -or $raw -is [sbyte] -or $raw -is [int16] -or $raw -is [uint16] -or
              $raw -is [int] -or $raw -is [uint32] -or $raw -is [long] -or $raw -is [uint64])) {
        $Errors.Add("$Label must be an integer.")
        return
    }
    $number = [int64]$raw
    if ($null -ne $Minimum -and $number -lt [int64]$Minimum) {
        if ($null -ne $Maximum) {
            $Errors.Add("$Label must be between $Minimum and $Maximum.")
        } else {
            $Errors.Add("$Label must be at least $Minimum.")
        }
        return
    }
    if ($null -ne $Maximum -and $number -gt [int64]$Maximum) {
        if ($null -ne $Minimum) {
            $Errors.Add("$Label must be between $Minimum and $Maximum.")
        } else {
            $Errors.Add("$Label must be at most $Maximum.")
        }
    }
}

function Test-MediaPipelineConfigNumberRange {
    param(
        [Parameter(Mandatory)] $Config,
        [Parameter(Mandatory)] [string] $Key,
        [Parameter(Mandatory)] [string] $Label,
        [Nullable[double]] $Minimum = $null,
        [Nullable[double]] $Maximum = $null,
        [switch] $Optional,
        [System.Collections.Generic.List[string]] $Errors
    )

    if (-not (Test-MediaPipelineConfigHasKey -Config $Config -Key $Key)) { return }
    $raw = Get-MediaPipelineConfigValue -Config $Config -Key $Key
    if ($Optional -and ($null -eq $raw -or [string]::IsNullOrWhiteSpace([string]$raw))) { return }
    if (-not ($raw -is [byte] -or $raw -is [sbyte] -or $raw -is [int16] -or $raw -is [uint16] -or
              $raw -is [int] -or $raw -is [uint32] -or $raw -is [long] -or $raw -is [uint64] -or
              $raw -is [float] -or $raw -is [double] -or $raw -is [decimal])) {
        $Errors.Add("$Label must be numeric.")
        return
    }
    $number = [double]$raw
    if ($null -ne $Minimum -and $number -lt [double]$Minimum) {
        if ($null -ne $Maximum) {
            $Errors.Add("$Label must be between $Minimum and $Maximum.")
        } else {
            $Errors.Add("$Label must be at least $Minimum.")
        }
        return
    }
    if ($null -ne $Maximum -and $number -gt [double]$Maximum) {
        if ($null -ne $Minimum) {
            $Errors.Add("$Label must be between $Minimum and $Maximum.")
        } else {
            $Errors.Add("$Label must be at most $Maximum.")
        }
    }
}

function Normalize-MediaPipelineConfigPathForCompare {
    param([string] $Path)

    if ([string]::IsNullOrWhiteSpace($Path)) { return '' }
    $trimmed = $Path.Trim().Trim('"').Trim("'").TrimEnd('\','/')
    if ([string]::IsNullOrWhiteSpace($trimmed)) { return '' }
    try {
        return [System.IO.Path]::GetFullPath($trimmed).TrimEnd('\','/').ToLowerInvariant()
    } catch {
        return $trimmed.ToLowerInvariant()
    }
}

function Add-MediaPipelineLibraryOverrideValuesToMap {
    param(
        [Parameter(Mandatory)] [System.Collections.IDictionary] $Target,
        $Values
    )

    if ($null -eq $Values) { return }
    if ($Values -is [System.Collections.IDictionary]) {
        foreach ($key in $Values.Keys) {
            if ($null -ne $key) { $Target[[string]$key] = $Values[$key] }
        }
        return
    }
    foreach ($property in @($Values.PSObject.Properties)) {
        if ($property -and -not [string]::IsNullOrWhiteSpace([string]$property.Name)) {
            $Target[[string]$property.Name] = $property.Value
        }
    }
}

function Get-MediaPipelineLibraryProfileOverrideValues {
    param($Profile)

    $values = [ordered]@{}
    $overrides = Get-MediaPipelineConfigValue -Config $Profile -Key 'overrides'
    foreach ($group in @('editor','video','subtitles','subtitle','audio')) {
        if ($overrides) {
            Add-MediaPipelineLibraryOverrideValuesToMap -Target $values -Values (Get-MediaPipelineConfigValue -Config $overrides -Key $group)
        }
    }
    Add-MediaPipelineLibraryOverrideValuesToMap -Target $values -Values (Get-MediaPipelineConfigValue -Config $Profile -Key 'editor_overrides')
    Add-MediaPipelineLibraryOverrideValuesToMap -Target $values -Values (Get-MediaPipelineConfigValue -Config $Profile -Key 'media_overrides')
    return $values
}

function Get-MediaPipelineLibraryProfileOverrideKeyErrors {
    param(
        [Parameter(Mandatory)] $Profile,
        [Parameter(Mandatory)] [string] $Label
    )

    $errors = New-Object System.Collections.Generic.List[string]
    $keysByGroup = Get-MediaPipelineConfigLibraryOverrideKeysByGroup
    $allKeys = @(Get-MediaPipelineConfigLibraryOverrideKeys)
    $rawOverrides = Get-MediaPipelineConfigValue -Config $Profile -Key 'overrides'
    if ($rawOverrides) {
        $overrideMap = ConvertTo-MediaPipelineConfigMap -Value $rawOverrides
        foreach ($rawGroup in $overrideMap.Keys) {
            $group = if ([string]$rawGroup -eq 'subtitle') { 'subtitles' } else { [string]$rawGroup }
            if (-not $keysByGroup.Contains($group)) {
                $errors.Add("Library profile $Label override group is unsupported: $rawGroup.")
                continue
            }
            $values = ConvertTo-MediaPipelineConfigMap -Value $overrideMap[$rawGroup]
            foreach ($key in $values.Keys) {
                $keyText = [string]$key
                if ($keyText -notin @($keysByGroup[$group])) {
                    $errors.Add("Library profile $Label override $group.$keyText is not a supported library override key.")
                }
            }
        }
    }

    foreach ($legacyField in @('editor_overrides','media_overrides')) {
        $legacyValues = ConvertTo-MediaPipelineConfigMap -Value (Get-MediaPipelineConfigValue -Config $Profile -Key $legacyField)
        foreach ($key in $legacyValues.Keys) {
            $keyText = [string]$key
            if ($keyText -notin $allKeys) {
                $errors.Add("Library profile $Label $legacyField.$keyText is not a supported library override key.")
            }
        }
    }
    return @($errors)
}

function Test-MediaPipelineLibraryProfileOverrides {
    param(
        [Parameter(Mandatory)] $Config,
        [Parameter(Mandatory)] $Profile,
        [Parameter(Mandatory)] [string] $Label,
        [System.Collections.Generic.List[string]] $Errors,
        [System.Collections.Generic.List[string]] $Warnings
    )

    $keyErrors = @(Get-MediaPipelineLibraryProfileOverrideKeyErrors -Profile $Profile -Label $Label)
    foreach ($message in $keyErrors) {
        $Errors.Add($message)
    }
    if ($keyErrors.Count -gt 0) { return }

    $overrides = Get-MediaPipelineLibraryProfileOverrideValues -Profile $Profile
    if ($overrides.Count -le 0) { return }

    $candidate = Get-MediaPipelineConfigDefaultValues
    foreach ($key in @(Get-MediaPipelineConfigOrderedKeys)) {
        if (Test-MediaPipelineConfigHasKey -Config $Config -Key $key) {
            $candidate[$key] = Get-MediaPipelineConfigValue -Config $Config -Key $key
        }
    }
    foreach ($key in $overrides.Keys) {
        $candidate[$key] = $overrides[$key]
    }

    $overrideErrors = [System.Collections.Generic.List[string]]::new()
    $overrideWarnings = [System.Collections.Generic.List[string]]::new()
    Test-MediaPipelineConfigEncodeAudioPolicy -Config $candidate -Errors $overrideErrors -Warnings $overrideWarnings

    foreach ($message in @($overrideErrors)) {
        $Errors.Add("Library profile $Label override is invalid: $message")
    }
    foreach ($message in @($overrideWarnings)) {
        $Warnings.Add("Library profile $Label override review: $message")
    }
}

function Test-MediaPipelineConfigPathShape {
    param(
        [Parameter(Mandatory)] $Config,
        [System.Collections.Generic.List[string]] $Errors,
        [System.Collections.Generic.List[string]] $Warnings
    )

    $pathKeys = @('SourceMovies','SourceTV','Outsource','LocalBase')
    $normalized = @{}
    foreach ($key in $pathKeys) {
        if (-not (Test-MediaPipelineConfigHasKey -Config $Config -Key $key)) { continue }
        $raw = [string](Get-MediaPipelineConfigValue -Config $Config -Key $key)
        if ([string]::IsNullOrWhiteSpace($raw)) {
            $Errors.Add("$key cannot be empty.")
            continue
        }
        $normalized[$key] = Normalize-MediaPipelineConfigPathForCompare -Path $raw
    }

    foreach ($pair in @(
        @('LocalBase','Outsource'),
        @('LocalBase','SourceMovies'),
        @('LocalBase','SourceTV'),
        @('Outsource','SourceMovies'),
        @('Outsource','SourceTV')
    )) {
        $leftKey = $pair[0]
        $rightKey = $pair[1]
        if (-not $normalized.ContainsKey($leftKey) -or -not $normalized.ContainsKey($rightKey)) { continue }
        $left = [string]$normalized[$leftKey]
        $right = [string]$normalized[$rightKey]
        if ([string]::IsNullOrWhiteSpace($left) -or [string]::IsNullOrWhiteSpace($right)) { continue }
        if ($left -eq $right) {
            $Errors.Add("$leftKey and $rightKey must not point to the same path.")
        } elseif ($left.StartsWith($right + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase) -or
                  $right.StartsWith($left + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) {
            $Errors.Add("$leftKey and $rightKey must not be nested inside each other.")
        }
    }

    if ($normalized.ContainsKey('SourceMovies') -and $normalized.ContainsKey('SourceTV') -and
        [string]$normalized['SourceMovies'] -eq [string]$normalized['SourceTV']) {
        $Warnings.Add('SourceMovies and SourceTV point to the same location.')
    }

    if (Test-MediaPipelineConfigHasKey -Config $Config -Key 'LibraryProfiles') {
        $profiles = @(Get-MediaPipelineConfigValue -Config $Config -Key 'LibraryProfiles')
        $profileIds = @{}
        $profileSourceRoots = @{}
        foreach ($profile in $profiles) {
            if ($null -eq $profile) { continue }
            $id = [string](Get-MediaPipelineConfigValue -Config $profile -Key 'id')
            $name = [string](Get-MediaPipelineConfigValue -Config $profile -Key 'name')
            $label = if (-not [string]::IsNullOrWhiteSpace($name)) { $name } elseif (-not [string]::IsNullOrWhiteSpace($id)) { $id } else { 'Library profile' }
            if ([string]::IsNullOrWhiteSpace($id)) {
                $Errors.Add("$label is missing id.")
            } elseif ($profileIds.ContainsKey($id.ToLowerInvariant())) {
                $Errors.Add("Library profile id is duplicated: $id.")
            } else {
                $profileIds[$id.ToLowerInvariant()] = $true
            }

            $enabled = ConvertTo-MediaPipelineConfigBool -Config $profile -Key 'enabled' -Default $true
            $promotionEnabled = ConvertTo-MediaPipelineConfigBool -Config $profile -Key 'promotion_enabled' -Default $false
            $designation = ([string](Get-MediaPipelineConfigValue -Config $profile -Key 'designation')).Trim().ToLowerInvariant()
            if ($designation -in @('mixed','custom')) {
                $Warnings.Add("$label designation '$designation' is legacy; use auto.")
                $designation = 'auto'
            }
            if ($designation -notin @('movie','tv','auto')) {
                $Errors.Add("$label designation must be movie, tv, or auto.")
            }
            if ($id -in @('movies','tv') -and -not $enabled) {
                $Errors.Add("$label is a required default library and cannot be disabled.")
            }
            $sourcePath = [string](Get-MediaPipelineConfigValue -Config $profile -Key 'source_path')
            $outputPath = [string](Get-MediaPipelineConfigValue -Config $profile -Key 'output_path')
            $promotionDestination = [string](Get-MediaPipelineConfigValue -Config $profile -Key 'promotion_destination')
            if ($enabled -and [string]::IsNullOrWhiteSpace($sourcePath)) {
                $Errors.Add("$label source_path cannot be empty.")
            }
            if ($enabled -and $promotionEnabled -and [string]::IsNullOrWhiteSpace($promotionDestination)) {
                $Errors.Add("$label promotion_destination cannot be empty when promotion is enabled.")
            }
            if ($enabled -and -not [string]::IsNullOrWhiteSpace($sourcePath)) {
                $sourceKey = Normalize-MediaPipelineConfigPathForCompare -Path $sourcePath
                if (-not [string]::IsNullOrWhiteSpace($sourceKey)) {
                    if ($profileSourceRoots.ContainsKey($sourceKey)) {
                        $Errors.Add("$label shares an enabled source root with $($profileSourceRoots[$sourceKey]).")
                    } else {
                        $profileSourceRoots[$sourceKey] = $label
                    }
                }
            }
            Test-MediaPipelineLibraryProfileOverrides -Config $Config -Profile $profile -Label $label -Errors $Errors -Warnings $Warnings
        }
    }

    if (Test-MediaPipelineConfigHasKey -Config $Config -Key (Get-MediaPipelineConfigSchemaKey)) {
        $sameVolumeGroups = @{}
        foreach ($key in $pathKeys) {
            if (-not (Test-MediaPipelineConfigHasKey -Config $Config -Key $key)) { continue }
            $raw = [string](Get-MediaPipelineConfigValue -Config $Config -Key $key)
            if ([string]::IsNullOrWhiteSpace($raw)) { continue }
            try {
                $root = [System.IO.Path]::GetPathRoot([System.IO.Path]::GetFullPath($raw))
                if ([string]::IsNullOrWhiteSpace($root)) { continue }
                $rootKey = $root.ToLowerInvariant()
                if (-not $sameVolumeGroups.ContainsKey($rootKey)) {
                    $sameVolumeGroups[$rootKey] = [System.Collections.Generic.List[string]]::new()
                }
                [void]$sameVolumeGroups[$rootKey].Add($key)
            } catch {}
        }
        foreach ($rootKey in $sameVolumeGroups.Keys) {
            $keys = @($sameVolumeGroups[$rootKey])
            if ($keys.Count -gt 1 -and $keys -contains 'LocalBase') {
                $Warnings.Add("LocalBase shares volume $rootKey with $($keys -join ', '); this is supported, but large copy/encode/publish bursts can contend for the same free space and I/O.")
            }
        }
    }
}

function Test-MediaPipelineConfigSubtitleToggles {
    param(
        [Parameter(Mandatory)] $Config,
        [System.Collections.Generic.List[string]] $Errors
    )

    $convertTx3g = ConvertTo-MediaPipelineConfigBool -Config $Config -Key 'ConvertTx3gToSrt' -Default $true
    $dropTx3g = ConvertTo-MediaPipelineConfigBool -Config $Config -Key 'DropTx3gAfterConversion' -Default $false
    $externalTx3g = ConvertTo-MediaPipelineConfigBool -Config $Config -Key 'CreateExternalTx3gSrtSidecars' -Default $false
    if (-not $convertTx3g -and $dropTx3g) {
        $Errors.Add('DropTx3gAfterConversion requires ConvertTx3gToSrt.')
    }
    if (-not $convertTx3g -and $externalTx3g) {
        $Errors.Add('CreateExternalTx3gSrtSidecars requires ConvertTx3gToSrt.')
    }

    $convertBdpgs = ConvertTo-MediaPipelineConfigBool -Config $Config -Key 'ConvertBdpgsToSrt' -Default $false
    $dropBdpgs = ConvertTo-MediaPipelineConfigBool -Config $Config -Key 'DropBdpgsAfterConversion' -Default $false
    if (-not $convertBdpgs -and $dropBdpgs) {
        $Errors.Add('DropBdpgsAfterConversion requires ConvertBdpgsToSrt.')
    }
    if ($convertBdpgs) {
        $toolPath = [string](Get-MediaPipelineConfigValue -Config $Config -Key 'BdpgsOcrToolPath')
        if ([string]::IsNullOrWhiteSpace($toolPath)) {
            $Errors.Add('ConvertBdpgsToSrt requires BdpgsOcrToolPath.')
        }
    }

    $convertVobSub = ConvertTo-MediaPipelineConfigBool -Config $Config -Key 'ConvertVobSubToSrt' -Default $false
    $dropVobSub = ConvertTo-MediaPipelineConfigBool -Config $Config -Key 'DropVobSubAfterConversion' -Default $false
    if (-not $convertVobSub -and $dropVobSub) {
        $Errors.Add('DropVobSubAfterConversion requires ConvertVobSubToSrt.')
    }
    if ($convertVobSub) {
        $toolPath = [string](Get-MediaPipelineConfigValue -Config $Config -Key 'VobSubOcrToolPath')
        if ([string]::IsNullOrWhiteSpace($toolPath)) {
            $Errors.Add('ConvertVobSubToSrt requires VobSubOcrToolPath.')
        }
    }
}

function Test-MediaPipelineConfigEncodeAudioPolicy {
    param(
        [Parameter(Mandatory)] $Config,
        [System.Collections.Generic.List[string]] $Errors,
        [System.Collections.Generic.List[string]] $Warnings
    )

    foreach ($optionPolicy in @(
        @{ Key = 'VideoCodec'; Label = 'VideoCodec'; Allowed = @(Get-MediaPipelineVideoCodecNames) },
        @{ Key = 'VideoPreset'; Label = 'VideoPreset'; Allowed = @(Get-MediaPipelineVideoPresetNames) },
        @{ Key = 'OutputContainer'; Label = 'OutputContainer'; Allowed = @(Get-MediaPipelineOutputContainerNames) },
        @{ Key = 'FinalLibraryPromotionVerificationMode'; Label = 'FinalLibraryPromotionVerificationMode'; Allowed = @(Get-MediaPipelineFinalLibraryPromotionVerificationModeNames); AllowBlank = $true },
        @{ Key = 'CpuEncodePreset'; Label = 'CpuEncodePreset'; Allowed = @(Get-MediaPipelineCpuEncodePresetNames); AllowBlank = $true },
        @{ Key = 'CpuEncodeProcessPriority'; Label = 'CpuEncodeProcessPriority'; Allowed = @(Get-MediaPipelineCpuEncodeProcessPriorityNames); AllowBlank = $true },
        @{ Key = 'ParallelEncodeMode'; Label = 'ParallelEncodeMode'; Allowed = @(Get-MediaPipelineParallelEncodeModeNames); AllowBlank = $true }
    )) {
        Test-MediaPipelineConfigChoiceValue -Config $Config -Key ([string]$optionPolicy.Key) -Label ([string]$optionPolicy.Label) -AllowedValues @($optionPolicy.Allowed) -AllowBlank:([bool]$optionPolicy.AllowBlank) -Errors $Errors
    }

    if (Test-MediaPipelineConfigHasKey -Config $Config -Key 'EncodeTuningPreset') {
        $preset = [string](Get-MediaPipelineConfigValue -Config $Config -Key 'EncodeTuningPreset')
        if ((Resolve-MediaPipelineEncodeTuningPreset -Preset $preset) -ne $preset.Trim().ToLowerInvariant()) {
            $Errors.Add("EncodeTuningPreset must be one of: $((Get-MediaPipelineEncodeTuningPresetNames) -join ', ').")
        }
    } elseif (Test-MediaPipelineConfigHasKey -Config $Config -Key 'ExtraVideoFlags') {
        $extra = @(Get-MediaPipelineConfigValue -Config $Config -Key 'ExtraVideoFlags')
        if ($extra.Count -gt 0) {
            $Warnings.Add('ExtraVideoFlags is present without EncodeTuningPreset; runtime will preserve it as custom_legacy_flags.')
        }
    }
    if (Test-MediaPipelineConfigHasKey -Config $Config -Key 'EncodeLadder') {
        $ladder = [string](Get-MediaPipelineConfigValue -Config $Config -Key 'EncodeLadder')
        if ((Resolve-MediaPipelineEncodeLadder -Ladder $ladder) -ne $ladder.Trim().ToLowerInvariant()) {
            $Errors.Add("EncodeLadder must be one of: $((Get-MediaPipelineEncodeLadderNames) -join ', ').")
        }
    }

    if (Test-MediaPipelineConfigHasKey -Config $Config -Key 'RoutingProfile') {
        $routingProfile = [string](Get-MediaPipelineConfigValue -Config $Config -Key 'RoutingProfile')
        if ((Resolve-MediaPipelineRoutingProfile -Profile $routingProfile) -ne $routingProfile.Trim().ToLowerInvariant()) {
            $Errors.Add("RoutingProfile must be one of: $((Get-MediaPipelineRoutingProfileNames) -join ', ').")
        }
    }

    if (Test-MediaPipelineConfigHasKey -Config $Config -Key 'RouteThresholdMode') {
        $routeThresholdMode = [string](Get-MediaPipelineConfigValue -Config $Config -Key 'RouteThresholdMode')
        if ((Resolve-MediaPipelineRouteThresholdMode -Mode $routeThresholdMode) -ne $routeThresholdMode.Trim().ToLowerInvariant()) {
            $Errors.Add("RouteThresholdMode must be one of: $((Get-MediaPipelineRouteThresholdModeNames) -join ', ').")
        }
    }

    if (Test-MediaPipelineConfigHasKey -Config $Config -Key 'SizeGuardMode') {
        $sizeGuardMode = [string](Get-MediaPipelineConfigValue -Config $Config -Key 'SizeGuardMode')
        if ((Resolve-MediaPipelineSizeGuardMode -Mode $sizeGuardMode) -ne $sizeGuardMode.Trim().ToLowerInvariant()) {
            $Errors.Add("SizeGuardMode must be one of: $((Get-MediaPipelineSizeGuardModeNames) -join ', ').")
        }
    }

    foreach ($numericPolicy in @(
        @{ Kind = 'int'; Key = 'EncodeThresholdGB'; Label = 'EncodeThresholdGB'; Min = 1 },
        @{ Kind = 'int'; Key = 'TVEncodeThresholdGB'; Label = 'TVEncodeThresholdGB'; Min = 1 },
        @{ Kind = 'int'; Key = 'MovieRouteMaxVideoBitrateMbps'; Label = 'MovieRouteMaxVideoBitrateMbps'; Min = 1; Max = 500 },
        @{ Kind = 'int'; Key = 'TVRouteMaxVideoBitrateMbps'; Label = 'TVRouteMaxVideoBitrateMbps'; Min = 1; Max = 500 },
        @{ Kind = 'int'; Key = 'H264RemuxMaxBitrateMbps'; Label = 'H264RemuxMaxBitrateMbps'; Min = 1; Max = 500 },
        @{ Kind = 'int'; Key = 'H264RemuxMaxHeight'; Label = 'H264RemuxMaxHeight'; Min = 1; Max = 4320 },
        @{ Kind = 'int'; Key = 'MaxEncodeGrowthPercent'; Label = 'MaxEncodeGrowthPercent'; Min = 0; Max = 1000 },
        @{ Kind = 'int'; Key = 'CompatibilityEncodeGrowthPercent'; Label = 'CompatibilityEncodeGrowthPercent'; Min = 0; Max = 1000 },
        @{ Kind = 'int'; Key = 'MinFreeSpaceGB'; Label = 'MinFreeSpaceGB'; Min = 0 },
        @{ Kind = 'int'; Key = 'OutsourceMinFreeSpaceGB'; Label = 'OutsourceMinFreeSpaceGB'; Min = 0 },
        @{ Kind = 'int'; Key = 'VideoQuality'; Label = 'VideoQuality'; Min = 1; Max = 51 },
        @{ Kind = 'int'; Key = 'MergeThresholdMs'; Label = 'MergeThresholdMs'; Min = 0; Max = 5000 },
        @{ Kind = 'int'; Key = 'FFmpegEncodeTimeoutSeconds'; Label = 'FFmpegEncodeTimeoutSeconds'; Min = 1 },
        @{ Kind = 'int'; Key = 'FFmpegCpuEncodeTimeoutSeconds'; Label = 'FFmpegCpuEncodeTimeoutSeconds'; Min = 1 },
        @{ Kind = 'int'; Key = 'FFmpegRemuxTimeoutSeconds'; Label = 'FFmpegRemuxTimeoutSeconds'; Min = 1 },
        @{ Kind = 'int'; Key = 'MkvmergeRemuxTimeoutSeconds'; Label = 'MkvmergeRemuxTimeoutSeconds'; Min = 60; Max = 86400 },
        @{ Kind = 'int'; Key = 'SubtitleExtractTimeoutSeconds'; Label = 'SubtitleExtractTimeoutSeconds'; Min = 30; Max = 3600 },
        @{ Kind = 'int'; Key = 'SubtitleProbeTimeoutSeconds'; Label = 'SubtitleProbeTimeoutSeconds'; Min = 5; Max = 600 },
        @{ Kind = 'int'; Key = 'BdpgsOcrTimeoutSeconds'; Label = 'BdpgsOcrTimeoutSeconds'; Min = 60; Max = 14400 },
        @{ Kind = 'int'; Key = 'VobSubOcrTimeoutSeconds'; Label = 'VobSubOcrTimeoutSeconds'; Min = 60; Max = 14400 },
        @{ Kind = 'int'; Key = 'TransientFailureRetryLimit'; Label = 'TransientFailureRetryLimit'; Min = 1; Max = 100 },
        @{ Kind = 'int'; Key = 'SourceScanIntervalSeconds'; Label = 'SourceScanIntervalSeconds'; Min = 0 },
        @{ Kind = 'int'; Key = 'ProcessedIndexRefreshSeconds'; Label = 'ProcessedIndexRefreshSeconds'; Min = 0 },
        @{ Kind = 'int'; Key = 'RobocopyTimeoutSeconds'; Label = 'RobocopyTimeoutSeconds'; Min = 60; Max = 172800 },
        @{ Kind = 'int'; Key = 'SourceScanTimeoutSeconds'; Label = 'SourceScanTimeoutSeconds'; Min = 30; Max = 86400 },
        @{ Kind = 'int'; Key = 'IndexScanTimeoutSeconds'; Label = 'IndexScanTimeoutSeconds'; Min = 30; Max = 86400 },
        @{ Kind = 'int'; Key = 'CleanupScanTimeoutSeconds'; Label = 'CleanupScanTimeoutSeconds'; Min = 30; Max = 7200 },
        @{ Kind = 'int'; Key = 'CleanupStaleAgeHours'; Label = 'CleanupStaleAgeHours'; Min = 1; Max = 720 },
        @{ Kind = 'int'; Key = 'CpuEncodeMaxThreads'; Label = 'CpuEncodeMaxThreads'; Min = 0; Max = 256 },
        @{ Kind = 'int'; Key = 'FallbackCpuQuality'; Label = 'FallbackCpuQuality'; Min = 1; Max = 51; Optional = $true },
        @{ Kind = 'number'; Key = 'OutputSizeMultiplier'; Label = 'OutputSizeMultiplier'; Min = 0.1; Max = 2.0; Optional = $true }
    )) {
        if ([string]$numericPolicy.Kind -eq 'number') {
            Test-MediaPipelineConfigNumberRange -Config $Config -Key ([string]$numericPolicy.Key) -Label ([string]$numericPolicy.Label) -Minimum $numericPolicy.Min -Maximum $numericPolicy.Max -Optional:([bool]$numericPolicy.Optional) -Errors $Errors
        } else {
            Test-MediaPipelineConfigIntegerRange -Config $Config -Key ([string]$numericPolicy.Key) -Label ([string]$numericPolicy.Label) -Minimum $numericPolicy.Min -Maximum $numericPolicy.Max -Optional:([bool]$numericPolicy.Optional) -Errors $Errors
        }
    }

    if (Test-MediaPipelineConfigHasKey -Config $Config -Key 'AudioPassthroughProfile') {
        $audioProfile = [string](Get-MediaPipelineConfigValue -Config $Config -Key 'AudioPassthroughProfile')
        if ((Resolve-MediaPipelineAudioPassthroughProfile -Profile $audioProfile) -ne $audioProfile.Trim().ToLowerInvariant()) {
            $Errors.Add("AudioPassthroughProfile must be one of: $((Get-MediaPipelineAudioPassthroughProfileNames) -join ', ').")
        }
    }

    if (Test-MediaPipelineConfigHasKey -Config $Config -Key 'AudioTranscodeCodec') {
        $codec = ([string](Get-MediaPipelineConfigValue -Config $Config -Key 'AudioTranscodeCodec')).Trim().ToLowerInvariant()
        if ($codec -notin @(Get-MediaPipelineAudioTranscodeCodecNames)) {
            $Errors.Add("AudioTranscodeCodec must be one of: $((Get-MediaPipelineAudioTranscodeCodecNames) -join ', ').")
        }
    }

    if (Test-MediaPipelineConfigHasKey -Config $Config -Key 'AudioTranscodeBitrate') {
        $bitrate = ([string](Get-MediaPipelineConfigValue -Config $Config -Key 'AudioTranscodeBitrate')).Trim().ToLowerInvariant()
        if ($bitrate -notmatch '^\d+k$') {
            $Errors.Add('AudioTranscodeBitrate must use an ffmpeg bitrate value like 640k.')
        }
    }

    if (Test-MediaPipelineConfigHasKey -Config $Config -Key 'AudioDownmixMode') {
        $mode = ([string](Get-MediaPipelineConfigValue -Config $Config -Key 'AudioDownmixMode')).Trim().ToLowerInvariant()
        if ($mode -notin @(Get-MediaPipelineAudioDownmixModeNames)) {
            $Errors.Add("AudioDownmixMode must be one of: $((Get-MediaPipelineAudioDownmixModeNames) -join ', ').")
        }
    }

    Test-MediaPipelineConfigIntegerRange -Config $Config -Key 'AudioMaxChannels' -Label 'AudioMaxChannels' -Minimum 1 -Maximum 16 -Errors $Errors
}

function Resolve-MediaPipelineConfigSchemaVersion {
    param([Parameter(Mandatory)] $Config)

    $current = Get-MediaPipelineConfigCurrentSchemaVersion
    $schemaKey = Get-MediaPipelineConfigSchemaKey
    $warnings = [System.Collections.Generic.List[string]]::new()
    $raw = Get-MediaPipelineConfigValue -Config $Config -Key $schemaKey
    if ($null -eq $raw -or [string]::IsNullOrWhiteSpace([string]$raw)) {
        return [pscustomobject]@{
            EffectiveSchemaVersion = $current
            DeclaredSchemaVersion  = $null
            CurrentSchemaVersion   = $current
            Warnings               = @()
        }
    }

    try {
        $declared = [int]$raw
    } catch {
        $warnings.Add("ConfigSchemaVersion '$raw' is not an integer; using schema $current compatibility.")
        return [pscustomobject]@{
            EffectiveSchemaVersion = $current
            DeclaredSchemaVersion  = $raw
            CurrentSchemaVersion   = $current
            Warnings               = @($warnings)
        }
    }

    if ($declared -lt 1) {
        $warnings.Add("ConfigSchemaVersion $declared is invalid; using schema $current compatibility.")
        $declared = $current
    } elseif ($declared -lt $current) {
        $warnings.Add("ConfigSchemaVersion $declared is older than current schema $current; loading through compatibility mode.")
    } elseif ($declared -gt $current) {
        $warnings.Add("ConfigSchemaVersion $declared is newer than this pipeline understands ($current); loading with current compatibility checks.")
        $declared = $current
    }

    return [pscustomobject]@{
        EffectiveSchemaVersion = $declared
        DeclaredSchemaVersion  = $raw
        CurrentSchemaVersion   = $current
        Warnings               = @($warnings)
    }
}

function Test-MediaPipelineConfigSchema {
    param([Parameter(Mandatory)] $Config)

    $errors = [System.Collections.Generic.List[string]]::new()
    $warnings = [System.Collections.Generic.List[string]]::new()
    $version = Resolve-MediaPipelineConfigSchemaVersion -Config $Config
    foreach ($warning in @($version.Warnings)) {
        if (-not [string]::IsNullOrWhiteSpace([string]$warning)) {
            $warnings.Add([string]$warning)
        }
    }

    foreach ($key in @(Get-MediaPipelineConfigRequiredKeys)) {
        if (-not (Test-MediaPipelineConfigHasKey -Config $Config -Key $key)) {
            $errors.Add("Config missing key: $key")
        }
    }
    Test-MediaPipelineConfigPathShape -Config $Config -Errors $errors -Warnings $warnings
    Test-MediaPipelineConfigSubtitleToggles -Config $Config -Errors $errors
    Test-MediaPipelineConfigEncodeAudioPolicy -Config $Config -Errors $errors -Warnings $warnings

    return [pscustomobject]@{
        Ok                     = ($errors.Count -eq 0)
        Errors                 = @($errors)
        Warnings               = @($warnings)
        EffectiveSchemaVersion = [int]$version.EffectiveSchemaVersion
        CurrentSchemaVersion   = [int]$version.CurrentSchemaVersion
        RequiredKeys           = @(Get-MediaPipelineConfigRequiredKeys)
        ArrayKeys              = @(Get-MediaPipelineConfigArrayKeys)
        OrderedKeys            = @(Get-MediaPipelineConfigOrderedKeys)
    }
}
