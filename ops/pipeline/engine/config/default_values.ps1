# ==============================================================================
# ops\pipeline\engine\config\default_values.ps1
# ==============================================================================
# Extracted from ops\pipeline\engine\config\config_schema.ps1. Keep public function names
# and config key semantics stable; config_schema.ps1 dot-sources this file.
# ==============================================================================

function Get-MediaPipelineConfigRouteMaxHeightFromUpperTolerance {
    param(
        [int] $BaseHeight,
        [double] $TolerancePercent
    )

    return [int][Math]::Round([double]$BaseHeight * (1.0 + ([double]$TolerancePercent / 100.0)))
}

function Get-MediaPipelineConfigRouteMinHeightFromLowerTolerance {
    param(
        [int] $BaseHeight,
        [double] $TolerancePercent
    )

    return [int][Math]::Round([double]$BaseHeight * (1.0 - ([double]$TolerancePercent / 100.0)))
}

function Get-MediaPipelineConfigRouteHeightToleranceBoundaries {
    param(
        [double] $Route1080pUpperHeightTolerancePercent = 11.111111,
        [double] $Route1440pLowerHeightTolerancePercent = 16.597222,
        [double] $Route1440pUpperHeightTolerancePercent = 24.930556,
        [double] $Route4KLowerHeightTolerancePercent = 16.666667
    )

    $route1080pMaxHeight = Get-MediaPipelineConfigRouteMaxHeightFromUpperTolerance -BaseHeight 1080 -TolerancePercent $Route1080pUpperHeightTolerancePercent
    $route1440pMinHeight = Get-MediaPipelineConfigRouteMinHeightFromLowerTolerance -BaseHeight 1440 -TolerancePercent $Route1440pLowerHeightTolerancePercent
    $route1440pMaxHeight = Get-MediaPipelineConfigRouteMaxHeightFromUpperTolerance -BaseHeight 1440 -TolerancePercent $Route1440pUpperHeightTolerancePercent
    $route4kMinHeight = Get-MediaPipelineConfigRouteMinHeightFromLowerTolerance -BaseHeight 2160 -TolerancePercent $Route4KLowerHeightTolerancePercent

    return [pscustomobject]([ordered]@{
        Route1080pMaxHeight = [int]$route1080pMaxHeight
        Route1440pMinHeight = [int]$route1440pMinHeight
        Route1440pMaxHeight = [int]$route1440pMaxHeight
        Route4KMinHeight    = [int]$route4kMinHeight
        IsContiguous        = (($route1440pMinHeight -eq ($route1080pMaxHeight + 1)) -and ($route4kMinHeight -eq ($route1440pMaxHeight + 1)))
    })
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

function Get-MediaPipelineRenameMovieFilterOptionsDefault {
    $options = [ordered]@{}
    foreach ($category in @(Get-MediaPipelineRenameMovieFilterCategoryNames)) {
        $options[$category] = $true
    }
    return $options
}

function Get-MediaPipelineRenameMovieFilterTermsDefault {
    return [ordered]@{
        video_source = @(
            '2160p','1080p','1080i','720p','720i','480p','4k','uhd','hdr','hdr10','hdr10+','hlg','dv','dovi',
            'dolby vision','hevc','h264','h.264','h265','h.265','x264','x265','av1','avc','xvid','divx',
            'blu ray','bluray','brrip','bdrip','webrip','web dl','webdl','web','hdtv','hdrip','dvdrip','dvd',
            'dvdscr','ts','cam','scr','remux','hybrid','10 bit','8 bit'
        )
        audio_channels = @(
            'truehd','atmos','flac','opus','eac3','ac3','aac','dd','dd+','ddp','dts','dts hd','dts-x','dtsx',
            'dtshd','lpcm','pcm','mp3','mp2','1.0','2.0','5.1','7.1','stereo','mono','6ch','6 ch','8ch','8 ch'
        )
        editions = @(
            'imax','proper','repack','rerip','extended','remastered','remaster','restored','restoration','unrated',
            'theatrical','criterion','director cut','directors cut',"director's cut",'dc','final cut','open matte',
            'redux','special edition','se','anniversary','collectors edition','supercut'
        )
        file_size = @(
            '500mb','700mb','1400mb','1gb','1.5gb','2gb','3gb','4.7gb','5gb','6gb','8gb','10gb','15gb','20gb','25gb','30gb'
        )
        services_containers = @(
            'amzn','nf','dsnp','hmax','hulu','itunes','appletv','atvp','peacock','pck','vudu','stan','sho','mkv','mp4','m4v','avi','mov','wmv'
        )
        release_groups = @(
            'rarbg','rbg','yify','yts','yts lt','galaxyrg','bone','psa','tigole','kris','sparks','ntb','evo','tepes','flux','framestor','cmrg','neonoir'
        )
    }
}

function Get-MediaPipelineRenameMovieRemoveTermsDefault {
    return @('sample','trailer','extras','featurette','deleted scenes','behind the scenes')
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
    $defaultRoot = Join-Path -Path 'C:\' -ChildPath 'MediaPipeline'
    $incomingRoot = Join-Path -Path $defaultRoot -ChildPath 'Incoming'

    [ordered]@{
        ConfigSchemaVersion      = Get-MediaPipelineConfigCurrentSchemaVersion
        SourceMovies               = Join-Path -Path $incomingRoot -ChildPath 'Movies'
        SourceTV                   = Join-Path -Path $incomingRoot -ChildPath 'TV'
        Outsource                  = Join-Path -Path $defaultRoot -ChildPath 'Processed'
        LibraryProfiles            = @(
            [ordered]@{
                id = 'movies'
                name = 'Movies'
                enabled = $true
                designation = 'movie'
                source_path = Join-Path -Path $incomingRoot -ChildPath 'Movies'
                output_path = Join-Path -Path $defaultRoot -ChildPath 'Processed'
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
                output_path = Join-Path -Path $defaultRoot -ChildPath 'Processed'
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
        LocalBase                  = Join-Path -Path $defaultRoot -ChildPath 'Scratch'
        MovieRoute1080pTargetSizeGB = 8
        MovieRoute1440pTargetSizeGB = 8
        MovieRoute4KTargetSizeGB   = 8
        TVRoute1080pTargetSizeGB   = 3
        TVRoute1440pTargetSizeGB   = 3
        TVRoute4KTargetSizeGB      = 3
        RoutingProfile             = Get-MediaPipelineRoutingProfileDefault
        RouteThresholdMode         = Get-MediaPipelineRouteThresholdModeDefault
        Route1080pUpperHeightTolerancePercent = 11.111111
        Route1080pMaxVideoBitrateMbps = 20
        Route1440pLowerHeightTolerancePercent = 16.597222
        Route1440pUpperHeightTolerancePercent = 24.930556
        Route1440pMaxVideoBitrateMbps = 35
        Route4KLowerHeightTolerancePercent = 16.666667
        Route4KMaxVideoBitrateMbps = 35
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
        DynamicHdrPolicy           = Get-MediaPipelineDynamicHdrPolicyDefault
        DoviToolPath               = ''
        Hdr10PlusToolPath          = ''
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
        BdpgsOcrToolPath           = 'tools\PgsToSrt\PgsToSrt.exe'
        BdpgsOcrTessdataPath       = 'tools\PgsToSrt\tessdata'
        ConvertVobSubToSrt         = $false
        DropVobSubAfterConversion  = $false
        VobSubExtractLanguages     = @('eng','en','und')
        VobSubOcrToolPath          = 'tools\SubtitleEditLegacy\SubtitleEdit.exe'
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
        RenameMovieFilterOptions   = Get-MediaPipelineRenameMovieFilterOptionsDefault
        RenameMovieFilterTerms     = Get-MediaPipelineRenameMovieFilterTermsDefault
        RenameMovieRemoveTerms     = Get-MediaPipelineRenameMovieRemoveTermsDefault
        ValidExtensions            = @('.mkv','.mp4','.avi','.mov','.m4v','.ts','.m2ts')
        FileStabilityWait          = 15
        EnableWatchFolders         = $false
        WatchFolderRoots           = @()
        WatchDebounceSeconds       = 30
        WatchAction                = 'enqueue_only'
        WatchRespectScheduleWindow = $true
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
        EnableQualityVerification = $false
        QualityMetric = Get-MediaPipelineQualityMetricDefault
        QualitySampleMode = Get-MediaPipelineQualitySampleModeDefault
        QualitySampleSeconds = 10
        QualitySampleCount = 3
        QualityWarnThreshold = 90
        QualityFailThreshold = 75
        QualityFailAction = Get-MediaPipelineQualityFailActionDefault
        QualityVerifyTimeoutSeconds = 1800
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
        PlannerRolloutStage        = 'legacy'
        UsePythonPlanner           = $false
        EnableHandBrakeSettingsUi  = $false
        PlannerComparisonLogging   = $false
        NewPlannerCutoverApproved  = $false
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
