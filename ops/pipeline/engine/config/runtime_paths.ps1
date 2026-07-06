# ==============================================================================
# ops\pipeline\engine\config\runtime_paths.ps1
# ==============================================================================
# Resolved runtime config diagnostics.
# ==============================================================================

function Get-MediaPipelineResolvedConfigDump {
    [CmdletBinding()]
    param()

    # Every config-derived runtime variable the pipeline and its dot-sourced
    # engine modules read. Read from the caller scope via dynamic lookup so the
    # dump reflects the fully-resolved main-script state. Sorted + [ordered] so
    # the JSON serialization is stable and diffable.
    $names = @(
        'configPath','LocalBase','SourceMovies','SourceTV','Outsource',
        'MovieRoute1080pTargetSizeGB','MovieRoute1440pTargetSizeGB','MovieRoute4KTargetSizeGB',
        'TVRoute1080pTargetSizeGB','TVRoute1440pTargetSizeGB','TVRoute4KTargetSizeGB',
        'MinFreeSpaceGB',
        'VideoCodec','EncoderBackend','VideoPreset','VideoQuality','OutputContainer','DynamicHdrPolicy','DoviToolPath','Hdr10PlusToolPath','RemuxSafeVideoCodecs',
        'RenameMovieFilterOptions','RenameMovieFilterTerms','RenameMovieRemoveTerms',
        'RenameTVFilterOptions','RenameTVFilterTerms','RenameTVRemoveTerms','SubKeepLanguages',
        'StripFormatting','MergeAdjacent','RemoveKaraoke','KeepSignsAndSongs',
        'ConvertTx3gToSrt','DropTx3gAfterConversion','CreateExternalTx3gSrtSidecars','Tx3gPreserveExistingSrt','Tx3gTreatForcedAsSeparate',
        'ConvertBdpgsToSrt','DropBdpgsAfterConversion','TreatBdpgsSignsSongsAsForced','BdpgsOcrToolPath','BdpgsOcrTessdataPath',
        'ConvertVobSubToSrt','DropVobSubAfterConversion','TreatVobSubSignsSongsAsForced','VobSubOcrToolPath',
        'TreatAssSignsSongsAsForced','TreatTx3gSignsSongsAsForced','AggressiveEpisodeParsing','AllowSystemTools',
        'MergeThresholdMs','LogRetentionDays','FailureArtifactWarningThresholdGB','FailureArtifactRetentionDays','FailureArtifactCleanupTargetGB',
        'FFmpegEncodeTimeoutSeconds','FFmpegCpuEncodeTimeoutSeconds','CpuEncodeMutexWaitSeconds','FFmpegRemuxTimeoutSeconds','MkvmergeRemuxTimeoutSeconds',
        'SubtitleExtractTimeoutSeconds','SubtitleProbeTimeoutSeconds','BdpgsOcrTimeoutSeconds','VobSubOcrTimeoutSeconds',
        'EnableQualityVerification','QualityMetric','QualitySampleMode','QualitySampleSeconds','QualitySampleCount',
        'QualityWarnThreshold','QualityFailThreshold','QualityFailAction','QualityVerifyTimeoutSeconds',
        'SourceScanIntervalSeconds','ProcessedIndexRefreshSeconds','RobocopyTimeoutSeconds','SourceScanTimeoutSeconds',
        'CleanupScanTimeoutSeconds','CleanupRemoteStaging','CleanupStaleAgeHours','TransientFailureRetryLimit',
        'AutonomyPendingTotalReviewBytes','AutonomyPendingTotalBlockBytes',
        'IndexScanTimeoutSeconds','OutsourceMinFreeSpaceGB',
        'ExcludeSubtitleStyles','IncludeSubtitleStyles','Tx3gExtractLanguages','BdpgsExtractLanguages','VobSubExtractLanguages',
        'PriorityMarkers','MixPriorityPhase','QueueOrderingStrategy','MaxParallelEncodes','ParallelEncodeMode',
        'PreferredDefaultAudioLanguages','EncodeTuningPreset','EncodeLadder','RoutingProfile','RouteThresholdMode','SizeGuardMode',
        'Route1080pBucketMaxHeight','Route1080pUpperHeightTolerancePercent','Route1080pMaxVideoBitrateMbps',
        'Route1440pLowerHeightTolerancePercent','Route1440pUpperHeightTolerancePercent','Route1440pMaxVideoBitrateMbps',
        'Route4KLowerHeightTolerancePercent','Route4KBucketMinHeight','Route4KMaxVideoBitrateMbps',
        'AllowH264RemuxIfPlexCompatible','H264RemuxMaxBitrateMbps','H264RemuxMaxHeight','MaxEncodeGrowthPercent','CompatibilityEncodeGrowthPercent',
        'EncodeWasteGuardMode','EncodeWasteGuardPreflightEnabled','EncodeWasteGuardMinProgressPercent','EncodeWasteGuardMinElapsedSeconds',
        'EncodeWasteGuardOversizeMarginPercent','EncodeWasteGuardConsecutiveSamples','EncodeWasteGuardPollSeconds',
        'EncodeWasteGuardPreflightSampleSeconds','EncodeWasteGuardPreflightSampleCount','EncodeWasteGuardPreflightTimeoutSeconds',
        'ExtraVideoFlags','AudioPassthroughProfile','CompatibleAudioCodecs','AudioTranscodeCodec','AudioTranscodeBitrate',
        'AudioDownmixMode','AudioMaxChannels','AllowNoAudio','AudioTranscodeAutoBitrateByChannels',
        'ProductVersion','PipelineVersion','MinPipelineVersion','ReprocessAll','DeferredPublish',
        'OutputSizeMultiplier','FallbackCpuQuality','CpuEncodePreset','CpuEncodeProcessPriority','CpuEncodeMaxThreads','WatchScanTimeoutSeconds',
        'ConsoleLogLevel','FileLogLevel','ConfigSchemaVersion'
    ) | Sort-Object -Unique

    $dump = [ordered]@{}
    foreach ($n in $names) {
        $dump[$n] = Get-Variable -Name $n -ValueOnly -ErrorAction SilentlyContinue
    }
    # ShowOverrides is a hashtable; dump only its sorted pattern keys so the
    # snapshot is stable (hashtable enumeration order is otherwise noise).
    $so = Get-Variable -Name 'ShowOverrides' -ValueOnly -ErrorAction SilentlyContinue
    $dump['ShowOverrides_Keys'] = if ($so -is [hashtable]) { @($so.Keys | Sort-Object) } else { @() }
    return $dump
}
