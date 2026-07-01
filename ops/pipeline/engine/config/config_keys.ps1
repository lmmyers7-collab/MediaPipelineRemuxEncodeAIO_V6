# ==============================================================================
# ops\pipeline\engine\config\config_keys.ps1
# ==============================================================================
# Canonical MediaPipeline PSD1 config-key registry for PowerShell callers.
# Keep this aligned with ops/pipeline/engine/config/config_schema.ps1 and DesktopApp
# config_keys.py.
# ==============================================================================

$script:MediaPipelineConfigKeyRegistry = [ordered]@{
    ConfigSchemaVersion = 'ConfigSchemaVersion'
    SourceMovies = 'SourceMovies'
    SourceTV = 'SourceTV'
    Outsource = 'Outsource'
    LibraryProfiles = 'LibraryProfiles'
    LocalBase = 'LocalBase'
    MovieRoute1080pTargetSizeGB = 'MovieRoute1080pTargetSizeGB'
    MovieRoute1440pTargetSizeGB = 'MovieRoute1440pTargetSizeGB'
    MovieRoute4KTargetSizeGB = 'MovieRoute4KTargetSizeGB'
    TVRoute1080pTargetSizeGB = 'TVRoute1080pTargetSizeGB'
    TVRoute1440pTargetSizeGB = 'TVRoute1440pTargetSizeGB'
    TVRoute4KTargetSizeGB = 'TVRoute4KTargetSizeGB'
    RoutingProfile = 'RoutingProfile'
    RouteThresholdMode = 'RouteThresholdMode'
    Route1080pUpperHeightTolerancePercent = 'Route1080pUpperHeightTolerancePercent'
    Route1080pMaxVideoBitrateMbps = 'Route1080pMaxVideoBitrateMbps'
    Route1440pLowerHeightTolerancePercent = 'Route1440pLowerHeightTolerancePercent'
    Route1440pUpperHeightTolerancePercent = 'Route1440pUpperHeightTolerancePercent'
    Route1440pMaxVideoBitrateMbps = 'Route1440pMaxVideoBitrateMbps'
    Route4KLowerHeightTolerancePercent = 'Route4KLowerHeightTolerancePercent'
    Route4KMaxVideoBitrateMbps = 'Route4KMaxVideoBitrateMbps'
    AllowH264RemuxIfPlexCompatible = 'AllowH264RemuxIfPlexCompatible'
    H264RemuxMaxBitrateMbps = 'H264RemuxMaxBitrateMbps'
    H264RemuxMaxHeight = 'H264RemuxMaxHeight'
    SizeGuardMode = 'SizeGuardMode'
    MaxEncodeGrowthPercent = 'MaxEncodeGrowthPercent'
    CompatibilityEncodeGrowthPercent = 'CompatibilityEncodeGrowthPercent'
    EncodeWasteGuardMode = 'EncodeWasteGuardMode'
    EncodeWasteGuardPreflightEnabled = 'EncodeWasteGuardPreflightEnabled'
    EncodeWasteGuardMinProgressPercent = 'EncodeWasteGuardMinProgressPercent'
    EncodeWasteGuardMinElapsedSeconds = 'EncodeWasteGuardMinElapsedSeconds'
    EncodeWasteGuardOversizeMarginPercent = 'EncodeWasteGuardOversizeMarginPercent'
    EncodeWasteGuardConsecutiveSamples = 'EncodeWasteGuardConsecutiveSamples'
    EncodeWasteGuardPollSeconds = 'EncodeWasteGuardPollSeconds'
    EncodeWasteGuardPreflightSampleSeconds = 'EncodeWasteGuardPreflightSampleSeconds'
    EncodeWasteGuardPreflightSampleCount = 'EncodeWasteGuardPreflightSampleCount'
    EncodeWasteGuardPreflightTimeoutSeconds = 'EncodeWasteGuardPreflightTimeoutSeconds'
    MinFreeSpaceGB = 'MinFreeSpaceGB'
    OutsourceMinFreeSpaceGB = 'OutsourceMinFreeSpaceGB'
    DeferredPublish = 'DeferredPublish'
    PendingPublishDrainMode = 'PendingPublishDrainMode'
    PendingPublishDrainBatchSize = 'PendingPublishDrainBatchSize'
    FinalLibraryPromotionEnabled = 'FinalLibraryPromotionEnabled'
    FinalLibraryPromotionRules = 'FinalLibraryPromotionRules'
    FinalLibraryPromotionVerificationMode = 'FinalLibraryPromotionVerificationMode'
    FinalLibraryPromotionCleanupAfterVerified = 'FinalLibraryPromotionCleanupAfterVerified'
    FinalLibraryPromotionOverwriteExisting = 'FinalLibraryPromotionOverwriteExisting'
    VideoCodec = 'VideoCodec'
    EncoderBackend = 'EncoderBackend'
    VideoPreset = 'VideoPreset'
    VideoQuality = 'VideoQuality'
    OutputContainer = 'OutputContainer'
    DynamicHdrPolicy = 'DynamicHdrPolicy'
    DoviToolPath = 'DoviToolPath'
    Hdr10PlusToolPath = 'Hdr10PlusToolPath'
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
    AllowSubtitleHelperFallback = 'AllowSubtitleHelperFallback'
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
    ConvertVobSubToSrt = 'ConvertVobSubToSrt'
    DropVobSubAfterConversion = 'DropVobSubAfterConversion'
    VobSubExtractLanguages = 'VobSubExtractLanguages'
    VobSubOcrToolPath = 'VobSubOcrToolPath'
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
    TreatVobSubSignsSongsAsForced = 'TreatVobSubSignsSongsAsForced'
    ExcludeSubtitleStyles = 'ExcludeSubtitleStyles'
    IncludeSubtitleStyles = 'IncludeSubtitleStyles'
    RemuxSafeVideoCodecs = 'RemuxSafeVideoCodecs'
    RenameMovieFilterOptions = 'RenameMovieFilterOptions'
    RenameMovieFilterTerms = 'RenameMovieFilterTerms'
    RenameMovieRemoveTerms = 'RenameMovieRemoveTerms'
    RenameTVFilterOptions = 'RenameTVFilterOptions'
    RenameTVFilterTerms = 'RenameTVFilterTerms'
    RenameTVRemoveTerms = 'RenameTVRemoveTerms'
    ValidExtensions = 'ValidExtensions'
    FileStabilityWait = 'FileStabilityWait'
    EnableWatchFolders = 'EnableWatchFolders'
    WatchFolderRoots = 'WatchFolderRoots'
    WatchDebounceSeconds = 'WatchDebounceSeconds'
    WatchScanTimeoutSeconds = 'WatchScanTimeoutSeconds'
    WatchAction = 'WatchAction'
    WatchRespectScheduleWindow = 'WatchRespectScheduleWindow'
    SkipStabilityCheck = 'SkipStabilityCheck'
    EnableIntegrityCheck = 'EnableIntegrityCheck'
    CreateTVSubfolder = 'CreateTVSubfolder'
    AggressiveEpisodeParsing = 'AggressiveEpisodeParsing'
    RobocopyFlags = 'RobocopyFlags'
    DebugMode = 'DebugMode'
    LogRetentionDays = 'LogRetentionDays'
    PipelineDebugLogMaxBytes = 'PipelineDebugLogMaxBytes'
    FailureArtifactWarningThresholdGB = 'FailureArtifactWarningThresholdGB'
    FailureArtifactRetentionDays = 'FailureArtifactRetentionDays'
    FailureArtifactCleanupTargetGB = 'FailureArtifactCleanupTargetGB'
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
    CpuEncodeMutexWaitSeconds = 'CpuEncodeMutexWaitSeconds'
    FFmpegRemuxTimeoutSeconds = 'FFmpegRemuxTimeoutSeconds'
    MkvmergeRemuxTimeoutSeconds = 'MkvmergeRemuxTimeoutSeconds'
    SubtitleExtractTimeoutSeconds = 'SubtitleExtractTimeoutSeconds'
    SubtitleProbeTimeoutSeconds = 'SubtitleProbeTimeoutSeconds'
    BdpgsOcrTimeoutSeconds = 'BdpgsOcrTimeoutSeconds'
    VobSubOcrTimeoutSeconds = 'VobSubOcrTimeoutSeconds'
    OutputValidationProbeTimeoutSeconds = 'OutputValidationProbeTimeoutSeconds'
    OutputValidationMinSizeBytes = 'OutputValidationMinSizeBytes'
    OutputValidationDurationToleranceSeconds = 'OutputValidationDurationToleranceSeconds'
    EnableQualityVerification = 'EnableQualityVerification'
    QualityMetric = 'QualityMetric'
    QualitySampleMode = 'QualitySampleMode'
    QualitySampleSeconds = 'QualitySampleSeconds'
    QualitySampleCount = 'QualitySampleCount'
    QualityWarnThreshold = 'QualityWarnThreshold'
    QualityFailThreshold = 'QualityFailThreshold'
    QualityFailAction = 'QualityFailAction'
    QualityVerifyTimeoutSeconds = 'QualityVerifyTimeoutSeconds'
    AllowSystemTools = 'AllowSystemTools'
    RobocopyTimeoutSeconds = 'RobocopyTimeoutSeconds'
    TransientFailureRetryLimit = 'TransientFailureRetryLimit'
    ConsecutiveRoundFailureBlockLimit = 'ConsecutiveRoundFailureBlockLimit'
    ConsecutiveRoundFailureProbeBackoffSeconds = 'ConsecutiveRoundFailureProbeBackoffSeconds'
    PendingPublishBacklogBlockThreshold = 'PendingPublishBacklogBlockThreshold'
    PendingPublishDeferredBlockThreshold = 'PendingPublishDeferredBlockThreshold'
    PauseFlagReviewSeconds = 'PauseFlagReviewSeconds'
    PauseFlagBlockSeconds = 'PauseFlagBlockSeconds'
    LocalWorkerHeartbeatGraceSeconds = 'LocalWorkerHeartbeatGraceSeconds'
    QueueExecutionMaxRunnablePerRound = 'QueueExecutionMaxRunnablePerRound'
    StateDbMaintenanceIntervalSeconds = 'StateDbMaintenanceIntervalSeconds'
    StateDbWalReviewBytes = 'StateDbWalReviewBytes'
    StateDbCompletedJobsMaxRows = 'StateDbCompletedJobsMaxRows'
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
    PlannerRolloutStage = 'PlannerRolloutStage'
    UsePythonPlanner = 'UsePythonPlanner'
    EnableHandBrakeSettingsUi = 'EnableHandBrakeSettingsUi'
    PlannerComparisonLogging = 'PlannerComparisonLogging'
    NewPlannerCutoverApproved = 'NewPlannerCutoverApproved'
    NetworkRole = 'NetworkRole'
    CoordinatorPort = 'CoordinatorPort'
    CoordinatorBindAddress = 'CoordinatorBindAddress'
    CoordinatorAlsoEncodeLocally = 'CoordinatorAlsoEncodeLocally'
    CoordinatorHeartbeatTimeoutMins = 'CoordinatorHeartbeatTimeoutMins'
    CoordinatorMaxJobRetries = 'CoordinatorMaxJobRetries'
    CoordinatorAuthToken = 'CoordinatorAuthToken'
    WorkerCoordinatorUrl = 'WorkerCoordinatorUrl'
    WorkerName = 'WorkerName'
    WorkerAuthToken = 'WorkerAuthToken'
    WorkerPollIntervalSecs = 'WorkerPollIntervalSecs'
    WorkerSourcePathMap = 'WorkerSourcePathMap'
    WorkerEncoderMap = 'WorkerEncoderMap'
    WorkerHonorCoordinatorPolicy = 'WorkerHonorCoordinatorPolicy'
    WorkerConfigOverrides = 'WorkerConfigOverrides'
}

$script:MediaPipelineNetworkConfigKeys = @(
    'NetworkRole',
    'CoordinatorPort',
    'CoordinatorBindAddress',
    'CoordinatorAlsoEncodeLocally',
    'CoordinatorHeartbeatTimeoutMins',
    'CoordinatorMaxJobRetries',
    'CoordinatorAuthToken',
    'WorkerCoordinatorUrl',
    'WorkerName',
    'WorkerAuthToken',
    'WorkerPollIntervalSecs',
    'WorkerSourcePathMap',
    'WorkerEncoderMap',
    'WorkerHonorCoordinatorPolicy',
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
