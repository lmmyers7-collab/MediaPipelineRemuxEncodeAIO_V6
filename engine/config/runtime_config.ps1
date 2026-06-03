# ==============================================================================
# engine\config\runtime_config.ps1
# ==============================================================================
# Config resolution support for Pipeline\MediaPipeline.ps1.
#
# Dot-sourced so functions resolve the caller's $config / $script:* runtime
# variables by dynamic scope at call time (same convention as the Get-Config*
# getters in engine\config\getters.ps1).
#
# Phase 0 of the config-loader extraction (ADR / SESSION 2026-06-03):
#   Get-MediaPipelineResolvedConfigDump -- a complete, deterministic snapshot of
#   every config-derived runtime value. Used as a parity oracle to prove the
#   later resolver extraction is behaviour-neutral, and as operator-facing
#   "what did this run actually resolve" diagnostics. Read-only; no side effects.
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
        'EncodeThresholdGB','TVEncodeThresholdGB','MinFreeSpaceGB',
        'VideoCodec','VideoPreset','VideoQuality','OutputContainer','RemuxSafeVideoCodecs','SubKeepLanguages',
        'StripFormatting','MergeAdjacent','RemoveKaraoke','KeepSignsAndSongs',
        'ConvertTx3gToSrt','DropTx3gAfterConversion','CreateExternalTx3gSrtSidecars','Tx3gPreserveExistingSrt','Tx3gTreatForcedAsSeparate',
        'ConvertBdpgsToSrt','DropBdpgsAfterConversion','TreatBdpgsSignsSongsAsForced','BdpgsOcrToolPath','BdpgsOcrTessdataPath',
        'ConvertVobSubToSrt','DropVobSubAfterConversion','TreatVobSubSignsSongsAsForced','VobSubOcrToolPath',
        'TreatAssSignsSongsAsForced','TreatTx3gSignsSongsAsForced','AggressiveEpisodeParsing','AllowSystemTools',
        'MergeThresholdMs','LogRetentionDays',
        'FFmpegEncodeTimeoutSeconds','FFmpegCpuEncodeTimeoutSeconds','FFmpegRemuxTimeoutSeconds','MkvmergeRemuxTimeoutSeconds',
        'SubtitleExtractTimeoutSeconds','SubtitleProbeTimeoutSeconds','BdpgsOcrTimeoutSeconds','VobSubOcrTimeoutSeconds',
        'SourceScanIntervalSeconds','ProcessedIndexRefreshSeconds','RobocopyTimeoutSeconds','SourceScanTimeoutSeconds',
        'CleanupScanTimeoutSeconds','CleanupRemoteStaging','CleanupStaleAgeHours','TransientFailureRetryLimit',
        'IndexScanTimeoutSeconds','OutsourceMinFreeSpaceGB',
        'ExcludeSubtitleStyles','IncludeSubtitleStyles','Tx3gExtractLanguages','BdpgsExtractLanguages','VobSubExtractLanguages',
        'PriorityMarkers','MixPriorityPhase','QueueOrderingStrategy','MaxParallelEncodes','ParallelEncodeMode',
        'PreferredDefaultAudioLanguages','EncodeTuningPreset','EncodeLadder','RoutingProfile','SizeGuardMode',
        'AllowH264RemuxIfPlexCompatible','H264RemuxMaxBitrateMbps','H264RemuxMaxHeight','MaxEncodeGrowthPercent','CompatibilityEncodeGrowthPercent',
        'ExtraVideoFlags','AudioPassthroughProfile','CompatibleAudioCodecs','AudioTranscodeCodec','AudioTranscodeBitrate',
        'AudioDownmixMode','AudioMaxChannels','AllowNoAudio','AudioTranscodeAutoBitrateByChannels',
        'ProductVersion','PipelineVersion','MinPipelineVersion','ReprocessAll','DeferredPublish',
        'OutputSizeMultiplier','FallbackCpuQuality','CpuEncodePreset','CpuEncodeProcessPriority','CpuEncodeMaxThreads',
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
