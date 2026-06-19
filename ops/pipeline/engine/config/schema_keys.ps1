# ==============================================================================
# ops\pipeline\engine\config\schema_keys.ps1
# ==============================================================================
# Extracted from ops\pipeline\engine\config\config_schema.ps1. Keep public function names
# and config key semantics stable; config_schema.ps1 dot-sources this file.
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
        'MinFreeSpaceGB',
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
        'ValidExtensions','RenameMovieRemoveTerms','RenameTVRemoveTerms','RobocopyFlags','PriorityMarkers',
        'WatchFolderRoots',
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
            'MovieRoute1080pTargetSizeGB',
            'MovieRoute1440pTargetSizeGB',
            'MovieRoute4KTargetSizeGB',
            'TVRoute1080pTargetSizeGB',
            'TVRoute1440pTargetSizeGB',
            'TVRoute4KTargetSizeGB',
            'Route1080pUpperHeightTolerancePercent',
            'Route1080pMaxVideoBitrateMbps',
            'Route1440pLowerHeightTolerancePercent',
            'Route1440pUpperHeightTolerancePercent',
            'Route1440pMaxVideoBitrateMbps',
            'Route4KLowerHeightTolerancePercent',
            'Route4KMaxVideoBitrateMbps',
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
        'MovieRoute1080pTargetSizeGB','MovieRoute1440pTargetSizeGB','MovieRoute4KTargetSizeGB',
        'TVRoute1080pTargetSizeGB','TVRoute1440pTargetSizeGB','TVRoute4KTargetSizeGB',
        'RoutingProfile','RouteThresholdMode',
        'Route1080pUpperHeightTolerancePercent','Route1080pMaxVideoBitrateMbps',
        'Route1440pLowerHeightTolerancePercent','Route1440pUpperHeightTolerancePercent','Route1440pMaxVideoBitrateMbps',
        'Route4KLowerHeightTolerancePercent','Route4KMaxVideoBitrateMbps',
        'AllowH264RemuxIfPlexCompatible','H264RemuxMaxBitrateMbps','H264RemuxMaxHeight',
        'SizeGuardMode','MaxEncodeGrowthPercent','CompatibilityEncodeGrowthPercent',
        'EncodeWasteGuardMode','EncodeWasteGuardPreflightEnabled',
        'EncodeWasteGuardMinProgressPercent','EncodeWasteGuardMinElapsedSeconds',
        'EncodeWasteGuardOversizeMarginPercent','EncodeWasteGuardConsecutiveSamples',
        'EncodeWasteGuardPollSeconds','EncodeWasteGuardPreflightSampleSeconds',
        'EncodeWasteGuardPreflightSampleCount','EncodeWasteGuardPreflightTimeoutSeconds',
        'MinFreeSpaceGB','OutsourceMinFreeSpaceGB',
        'DeferredPublish',
        'FinalLibraryPromotionEnabled','FinalLibraryPromotionRules','FinalLibraryPromotionVerificationMode',
        'FinalLibraryPromotionCleanupAfterVerified','FinalLibraryPromotionOverwriteExisting',
        'VideoCodec','VideoPreset','VideoQuality','OutputContainer','DynamicHdrPolicy','DoviToolPath','Hdr10PlusToolPath','EncodeTuningPreset','EncodeLadder','ExtraVideoFlags',
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
        'RenameMovieFilterOptions','RenameMovieFilterTerms','RenameMovieRemoveTerms',
        'RenameTVFilterOptions','RenameTVFilterTerms','RenameTVRemoveTerms',
        'ValidExtensions','FileStabilityWait',
        'EnableWatchFolders','WatchFolderRoots','WatchDebounceSeconds','WatchAction','WatchRespectScheduleWindow',
        'SkipStabilityCheck',
        'EnableIntegrityCheck','CreateTVSubfolder','AggressiveEpisodeParsing',
        'RobocopyFlags',
        'DebugMode','LogRetentionDays','PriorityMarkers','MixPriorityPhase','QueueOrderingStrategy','ConsoleLogLevel','FileLogLevel',
        'MaxParallelEncodes','ParallelEncodeMode',
        'FallbackCpuQuality','CpuEncodePreset','CpuEncodeProcessPriority','CpuEncodeMaxThreads','OutputSizeMultiplier',
        'FFmpegEncodeTimeoutSeconds','FFmpegCpuEncodeTimeoutSeconds','FFmpegRemuxTimeoutSeconds','MkvmergeRemuxTimeoutSeconds','SubtitleExtractTimeoutSeconds','SubtitleProbeTimeoutSeconds','BdpgsOcrTimeoutSeconds','VobSubOcrTimeoutSeconds',
        'OutputValidationProbeTimeoutSeconds','OutputValidationMinSizeBytes','OutputValidationDurationToleranceSeconds',
        'EnableQualityVerification','QualityMetric','QualitySampleMode','QualitySampleSeconds','QualitySampleCount',
        'QualityWarnThreshold','QualityFailThreshold','QualityFailAction','QualityVerifyTimeoutSeconds',
        'AllowSystemTools','RobocopyTimeoutSeconds','TransientFailureRetryLimit',
        'IndexScanTimeoutSeconds','SourceScanTimeoutSeconds','CleanupScanTimeoutSeconds',
        'CleanupRemoteStaging','CleanupStaleAgeHours',
        'SourceScanIntervalSeconds','ProcessedIndexRefreshSeconds',
        'MinPipelineVersion','ReprocessAll',
        'ShowOverrides',
        'PlannerRolloutStage','UsePythonPlanner','EnableHandBrakeSettingsUi',
        'PlannerComparisonLogging','NewPlannerCutoverApproved'
    )
}
