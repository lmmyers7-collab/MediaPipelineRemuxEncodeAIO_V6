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
        'SubSDHTitleKeywords','SubSupplementalKeywords','Tx3gExtractLanguages','BdpgsExtractLanguages',
        'PreferredDefaultAudioLanguages','RemuxSafeVideoCodecs',
        'ValidExtensions','RobocopyFlags','PriorityMarkers',
        'ExcludeSubtitleStyles','IncludeSubtitleStyles'
    )
}

function Get-MediaPipelineConfigOrderedKeys {
    return @(
        'ConfigSchemaVersion',
        'SourceMovies','SourceTV','Outsource','LocalBase',
        'EncodeThresholdGB','TVEncodeThresholdGB',
        'RoutingProfile','MovieRouteMaxVideoBitrateMbps','TVRouteMaxVideoBitrateMbps',
        'AllowH264RemuxIfPlexCompatible','H264RemuxMaxBitrateMbps','H264RemuxMaxHeight',
        'SizeGuardMode','MaxEncodeGrowthPercent','CompatibilityEncodeGrowthPercent',
        'MinFreeSpaceGB','OutsourceMinFreeSpaceGB',
        'DeferredPublish',
        'VideoCodec','VideoPreset','VideoQuality','OutputContainer','EncodeTuningPreset','EncodeLadder','ExtraVideoFlags',
        'AudioPassthroughProfile','CompatibleAudioCodecs','PreferredDefaultAudioLanguages',
        'AudioTranscodeCodec','AudioTranscodeBitrate','AudioTranscodeAutoBitrateByChannels','AudioDownmixMode','AudioMaxChannels','AllowNoAudio',
        'SubKeepLanguages','ConvertTx3gToSrt','DropTx3gAfterConversion','CreateExternalTx3gSrtSidecars',
        'Tx3gExtractLanguages','Tx3gPreserveExistingSrt','Tx3gTreatForcedAsSeparate',
        'ConvertBdpgsToSrt','DropBdpgsAfterConversion','BdpgsExtractLanguages','BdpgsOcrToolPath','BdpgsOcrTessdataPath',
        'SubSDHTitleKeywords','SubSupplementalKeywords',
        'DropAssAfterConversion','StripFormatting','RemoveKaraoke',
        'MergeAdjacent','MergeThresholdMs','KeepSignsAndSongs','TreatAssSignsSongsAsForced','TreatTx3gSignsSongsAsForced','TreatBdpgsSignsSongsAsForced',
        'ExcludeSubtitleStyles','IncludeSubtitleStyles',
        'RemuxSafeVideoCodecs',
        'ValidExtensions','FileStabilityWait','SkipStabilityCheck',
        'EnableIntegrityCheck','CreateTVSubfolder','AggressiveEpisodeParsing',
        'RobocopyFlags',
        'DebugMode','LogRetentionDays','PriorityMarkers','MixPriorityPhase','QueueOrderingStrategy','ConsoleLogLevel','FileLogLevel',
        'MaxParallelEncodes','ParallelEncodeMode',
        'FallbackCpuQuality','CpuEncodePreset','CpuEncodeProcessPriority','CpuEncodeMaxThreads','OutputSizeMultiplier',
        'FFmpegEncodeTimeoutSeconds','FFmpegCpuEncodeTimeoutSeconds','FFmpegRemuxTimeoutSeconds','MkvmergeRemuxTimeoutSeconds','SubtitleExtractTimeoutSeconds','SubtitleProbeTimeoutSeconds','BdpgsOcrTimeoutSeconds',
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
        LocalBase                  = Join-Path -Path $videosRoot -ChildPath 'Scratch'
        EncodeThresholdGB          = 8
        TVEncodeThresholdGB        = 3
        RoutingProfile             = Get-MediaPipelineRoutingProfileDefault
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
}

function Test-MediaPipelineConfigEncodeAudioPolicy {
    param(
        [Parameter(Mandatory)] $Config,
        [System.Collections.Generic.List[string]] $Errors,
        [System.Collections.Generic.List[string]] $Warnings
    )

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

    if (Test-MediaPipelineConfigHasKey -Config $Config -Key 'SizeGuardMode') {
        $sizeGuardMode = [string](Get-MediaPipelineConfigValue -Config $Config -Key 'SizeGuardMode')
        if ((Resolve-MediaPipelineSizeGuardMode -Mode $sizeGuardMode) -ne $sizeGuardMode.Trim().ToLowerInvariant()) {
            $Errors.Add("SizeGuardMode must be one of: $((Get-MediaPipelineSizeGuardModeNames) -join ', ').")
        }
    }

    foreach ($numericPolicy in @(
        @{ Key = 'MovieRouteMaxVideoBitrateMbps'; Label = 'MovieRouteMaxVideoBitrateMbps'; Min = 1; Max = 500 },
        @{ Key = 'TVRouteMaxVideoBitrateMbps'; Label = 'TVRouteMaxVideoBitrateMbps'; Min = 1; Max = 500 },
        @{ Key = 'H264RemuxMaxBitrateMbps'; Label = 'H264RemuxMaxBitrateMbps'; Min = 1; Max = 500 },
        @{ Key = 'H264RemuxMaxHeight'; Label = 'H264RemuxMaxHeight'; Min = 1; Max = 4320 },
        @{ Key = 'MaxEncodeGrowthPercent'; Label = 'MaxEncodeGrowthPercent'; Min = 0; Max = 1000 },
        @{ Key = 'CompatibilityEncodeGrowthPercent'; Label = 'CompatibilityEncodeGrowthPercent'; Min = 0; Max = 1000 }
    )) {
        $policyKey = [string]$numericPolicy.Key
        if (-not (Test-MediaPipelineConfigHasKey -Config $Config -Key $policyKey)) { continue }
        try {
            $number = [double](Get-MediaPipelineConfigValue -Config $Config -Key $policyKey)
            if ($number -lt [double]$numericPolicy.Min -or $number -gt [double]$numericPolicy.Max) {
                $Errors.Add("$($numericPolicy.Label) must be between $($numericPolicy.Min) and $($numericPolicy.Max).")
            }
        } catch {
            $Errors.Add("$($numericPolicy.Label) must be numeric.")
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
        if ($codec -notin @('eac3','ac3','aac')) {
            $Errors.Add('AudioTranscodeCodec must be one of: eac3, ac3, aac.')
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
        if ($mode -notin @('preserve','max_channels','stereo')) {
            $Errors.Add('AudioDownmixMode must be one of: preserve, max_channels, stereo.')
        }
    }

    if (Test-MediaPipelineConfigHasKey -Config $Config -Key 'AudioMaxChannels') {
        try {
            $maxChannels = [int](Get-MediaPipelineConfigValue -Config $Config -Key 'AudioMaxChannels')
            if ($maxChannels -lt 1 -or $maxChannels -gt 16) {
                $Errors.Add('AudioMaxChannels must be between 1 and 16.')
            }
        } catch {
            $Errors.Add('AudioMaxChannels must be an integer.')
        }
    }
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
