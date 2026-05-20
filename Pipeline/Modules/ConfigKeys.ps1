# ==============================================================================
# Modules\ConfigKeys.ps1
# ==============================================================================
# Canonical MediaPipeline PSD1 config-key registry for PowerShell callers.
# Keep this aligned with ConfigSchema.ps1 and DesktopApp config_keys.py.
# ==============================================================================

$script:MediaPipelineConfigKeyRegistry = [ordered]@{
    ConfigSchemaVersion = 'ConfigSchemaVersion'
    SourceMovies = 'SourceMovies'
    SourceTV = 'SourceTV'
    Outsource = 'Outsource'
    LocalBase = 'LocalBase'
    EncodeThresholdGB = 'EncodeThresholdGB'
    TVEncodeThresholdGB = 'TVEncodeThresholdGB'
    RoutingProfile = 'RoutingProfile'
    AllowH264RemuxIfPlexCompatible = 'AllowH264RemuxIfPlexCompatible'
    H264RemuxMaxBitrateMbps = 'H264RemuxMaxBitrateMbps'
    H264RemuxMaxHeight = 'H264RemuxMaxHeight'
    SizeGuardMode = 'SizeGuardMode'
    MaxEncodeGrowthPercent = 'MaxEncodeGrowthPercent'
    CompatibilityEncodeGrowthPercent = 'CompatibilityEncodeGrowthPercent'
    MinFreeSpaceGB = 'MinFreeSpaceGB'
    OutsourceMinFreeSpaceGB = 'OutsourceMinFreeSpaceGB'
    DeferredPublish = 'DeferredPublish'
    VideoCodec = 'VideoCodec'
    VideoPreset = 'VideoPreset'
    VideoQuality = 'VideoQuality'
    OutputContainer = 'OutputContainer'
    EncodeTuningPreset = 'EncodeTuningPreset'
    EncodeLadder = 'EncodeLadder'
    ExtraVideoFlags = 'ExtraVideoFlags'
    AudioPassthroughProfile = 'AudioPassthroughProfile'
    CompatibleAudioCodecs = 'CompatibleAudioCodecs'
    PreferredDefaultAudioLanguages = 'PreferredDefaultAudioLanguages'
    AudioTranscodeCodec = 'AudioTranscodeCodec'
    AudioTranscodeBitrate = 'AudioTranscodeBitrate'
    AudioTranscodeAutoBitrateByChannels = 'AudioTranscodeAutoBitrateByChannels'
    AudioDownmixMode = 'AudioDownmixMode'
    AudioMaxChannels = 'AudioMaxChannels'
    AllowNoAudio = 'AllowNoAudio'
    SubKeepLanguages = 'SubKeepLanguages'
    ConvertTx3gToSrt = 'ConvertTx3gToSrt'
    DropTx3gAfterConversion = 'DropTx3gAfterConversion'
    CreateExternalTx3gSrtSidecars = 'CreateExternalTx3gSrtSidecars'
    Tx3gExtractLanguages = 'Tx3gExtractLanguages'
    Tx3gPreserveExistingSrt = 'Tx3gPreserveExistingSrt'
    Tx3gTreatForcedAsSeparate = 'Tx3gTreatForcedAsSeparate'
    ConvertBdpgsToSrt = 'ConvertBdpgsToSrt'
    DropBdpgsAfterConversion = 'DropBdpgsAfterConversion'
    BdpgsExtractLanguages = 'BdpgsExtractLanguages'
    BdpgsOcrToolPath = 'BdpgsOcrToolPath'
    BdpgsOcrTessdataPath = 'BdpgsOcrTessdataPath'
    SubSDHTitleKeywords = 'SubSDHTitleKeywords'
    SubSupplementalKeywords = 'SubSupplementalKeywords'
    DropAssAfterConversion = 'DropAssAfterConversion'
    StripFormatting = 'StripFormatting'
    RemoveKaraoke = 'RemoveKaraoke'
    MergeAdjacent = 'MergeAdjacent'
    MergeThresholdMs = 'MergeThresholdMs'
    KeepSignsAndSongs = 'KeepSignsAndSongs'
    TreatAssSignsSongsAsForced = 'TreatAssSignsSongsAsForced'
    TreatTx3gSignsSongsAsForced = 'TreatTx3gSignsSongsAsForced'
    TreatBdpgsSignsSongsAsForced = 'TreatBdpgsSignsSongsAsForced'
    ExcludeSubtitleStyles = 'ExcludeSubtitleStyles'
    IncludeSubtitleStyles = 'IncludeSubtitleStyles'
    RemuxSafeVideoCodecs = 'RemuxSafeVideoCodecs'
    ValidExtensions = 'ValidExtensions'
    FileStabilityWait = 'FileStabilityWait'
    SkipStabilityCheck = 'SkipStabilityCheck'
    EnableIntegrityCheck = 'EnableIntegrityCheck'
    CreateTVSubfolder = 'CreateTVSubfolder'
    AggressiveEpisodeParsing = 'AggressiveEpisodeParsing'
    RobocopyFlags = 'RobocopyFlags'
    DebugMode = 'DebugMode'
    LogRetentionDays = 'LogRetentionDays'
    PriorityMarkers = 'PriorityMarkers'
    MixPriorityPhase = 'MixPriorityPhase'
    QueueOrderingStrategy = 'QueueOrderingStrategy'
    ConsoleLogLevel = 'ConsoleLogLevel'
    FileLogLevel = 'FileLogLevel'
    MaxParallelEncodes = 'MaxParallelEncodes'
    ParallelEncodeMode = 'ParallelEncodeMode'
    FallbackCpuQuality = 'FallbackCpuQuality'
    CpuEncodePreset = 'CpuEncodePreset'
    CpuEncodeProcessPriority = 'CpuEncodeProcessPriority'
    CpuEncodeMaxThreads = 'CpuEncodeMaxThreads'
    OutputSizeMultiplier = 'OutputSizeMultiplier'
    FFmpegEncodeTimeoutSeconds = 'FFmpegEncodeTimeoutSeconds'
    FFmpegCpuEncodeTimeoutSeconds = 'FFmpegCpuEncodeTimeoutSeconds'
    FFmpegRemuxTimeoutSeconds = 'FFmpegRemuxTimeoutSeconds'
    MkvmergeRemuxTimeoutSeconds = 'MkvmergeRemuxTimeoutSeconds'
    SubtitleExtractTimeoutSeconds = 'SubtitleExtractTimeoutSeconds'
    SubtitleProbeTimeoutSeconds = 'SubtitleProbeTimeoutSeconds'
    BdpgsOcrTimeoutSeconds = 'BdpgsOcrTimeoutSeconds'
    AllowSystemTools = 'AllowSystemTools'
    RobocopyTimeoutSeconds = 'RobocopyTimeoutSeconds'
    TransientFailureRetryLimit = 'TransientFailureRetryLimit'
    IndexScanTimeoutSeconds = 'IndexScanTimeoutSeconds'
    SourceScanTimeoutSeconds = 'SourceScanTimeoutSeconds'
    CleanupScanTimeoutSeconds = 'CleanupScanTimeoutSeconds'
    CleanupRemoteStaging = 'CleanupRemoteStaging'
    CleanupStaleAgeHours = 'CleanupStaleAgeHours'
    SourceScanIntervalSeconds = 'SourceScanIntervalSeconds'
    ProcessedIndexRefreshSeconds = 'ProcessedIndexRefreshSeconds'
    MinPipelineVersion = 'MinPipelineVersion'
    ReprocessAll = 'ReprocessAll'
    ShowOverrides = 'ShowOverrides'
    NetworkRole = 'NetworkRole'
    CoordinatorPort = 'CoordinatorPort'
    CoordinatorBindAddress = 'CoordinatorBindAddress'
    CoordinatorAlsoEncodeLocally = 'CoordinatorAlsoEncodeLocally'
    CoordinatorHeartbeatTimeoutMins = 'CoordinatorHeartbeatTimeoutMins'
    CoordinatorAuthToken = 'CoordinatorAuthToken'
    WorkerCoordinatorUrl = 'WorkerCoordinatorUrl'
    WorkerName = 'WorkerName'
    WorkerAuthToken = 'WorkerAuthToken'
    WorkerPollIntervalSecs = 'WorkerPollIntervalSecs'
    WorkerSourcePathMap = 'WorkerSourcePathMap'
    WorkerConfigOverrides = 'WorkerConfigOverrides'
}

$script:MediaPipelineNetworkConfigKeys = @(
    'NetworkRole',
    'CoordinatorPort',
    'CoordinatorBindAddress',
    'CoordinatorAlsoEncodeLocally',
    'CoordinatorHeartbeatTimeoutMins',
    'CoordinatorAuthToken',
    'WorkerCoordinatorUrl',
    'WorkerName',
    'WorkerAuthToken',
    'WorkerPollIntervalSecs',
    'WorkerSourcePathMap',
    'WorkerConfigOverrides'
)

function Get-MediaPipelineConfigKeyRegistry {
    $registry = [ordered]@{}
    foreach ($entry in $script:MediaPipelineConfigKeyRegistry.GetEnumerator()) {
        $registry[$entry.Key] = $entry.Value
    }
    return $registry
}

function Get-MediaPipelineKnownConfigKeys {
    return @($script:MediaPipelineConfigKeyRegistry.Values)
}

function Get-MediaPipelineNetworkConfigKeys {
    return @($script:MediaPipelineNetworkConfigKeys)
}

function Get-MediaPipelineConfigKeyOrder {
    return @($script:MediaPipelineConfigKeyRegistry.Values | Where-Object { $_ -notin $script:MediaPipelineNetworkConfigKeys })
}

function Get-MediaPipelineConfigKey {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Name
    )

    if ($script:MediaPipelineConfigKeyRegistry.Contains($Name)) {
        return [string]$script:MediaPipelineConfigKeyRegistry[$Name]
    }
    throw "Unknown MediaPipeline config-key registry entry: $Name"
}

function Test-MediaPipelineKnownConfigKey {
    param([string] $Key)

    if ([string]::IsNullOrWhiteSpace($Key)) { return $false }
    return @($script:MediaPipelineConfigKeyRegistry.Values) -contains $Key
}
